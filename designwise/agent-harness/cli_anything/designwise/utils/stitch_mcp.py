"""
StitchMCPClient — Real MCP transport for Google Stitch 2.0
DesignWise Squad | Utility
Version: 1.0.0

JSON-RPC over stdio communication with:
  Primary:  npx @google/stitch-sdk serve
  Fallback: npx stitchmcp (community wrapper)

Methods match the 3 canonical Stitch MCP tools:
  - build_sitemaps(project_id, routes)  → dict[route, html]
  - get_screen_code(project_id, screen_name)  → HTML+CSS string
  - get_screen_image(project_id, screen_name) → base64 PNG

Cache: /tmp/stitch_cache/<project_id>/<screen_name>.json
Retry: 3 attempts per call before fallback
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache directory
# ---------------------------------------------------------------------------

CACHE_DIR = Path(tempfile.gettempdir()) / "stitch_cache"

# ---------------------------------------------------------------------------
# MCP subprocess commands
# ---------------------------------------------------------------------------

MCP_PRIMARY_CMD = ["npx", "--yes", "@google/stitch-sdk", "serve"]
MCP_FALLBACK_CMD = ["npx", "--yes", "stitchmcp"]

# JSON-RPC request timeout (seconds)
MCP_TIMEOUT = 30

# Maximum retries before fallback
MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# StitchMCPClient
# ---------------------------------------------------------------------------


class StitchMCPClient:
    """
    Real MCP client wrapping subprocess communication with the Stitch SDK.

    Usage:
        async with StitchMCPClient() as client:
            html = await client.get_screen_code("zonewise-production", "landing-hero")

    Or manual lifecycle:
        client = StitchMCPClient()
        await client.start()
        result = await client.build_sitemaps("zonewise-production", ["/", "/app"])
        await client.close()
    """

    def __init__(self, timeout: int = MCP_TIMEOUT):
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._timeout = timeout
        self._using_fallback = False
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Spawn the MCP subprocess. Tries primary SDK first, fallback if unavailable."""
        if self._proc and self._proc.returncode is None:
            return  # Already running

        for cmd, is_fallback in [(MCP_PRIMARY_CMD, False), (MCP_FALLBACK_CMD, True)]:
            try:
                self._proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                # Send initialize handshake
                await self._initialize()
                self._using_fallback = is_fallback
                logger.info(
                    "StitchMCP started (%s): %s",
                    "fallback" if is_fallback else "primary",
                    " ".join(cmd),
                )
                return
            except Exception as exc:
                logger.warning("StitchMCP start failed with %s: %s", cmd[2], exc)
                if self._proc:
                    try:
                        self._proc.terminate()
                    except Exception:
                        pass
                    self._proc = None

        raise RuntimeError(
            "StitchMCP: could not start either @google/stitch-sdk or stitchmcp. "
            "Ensure Node.js + npx are installed."
        )

    async def close(self) -> None:
        """Terminate the MCP subprocess."""
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except Exception:
                pass
        self._proc = None

    async def __aenter__(self) -> "StitchMCPClient":
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Public API — 3 canonical MCP tools
    # ------------------------------------------------------------------

    async def build_sitemaps(
        self,
        project_id: str,
        routes: list[str],
    ) -> dict[str, str]:
        """
        Call Stitch MCP `build_sitemaps` tool.
        Maps each route to its Stitch-generated HTML.

        Returns: dict[route, html]  e.g. {"/": "<html>...", "/app": "<html>..."}
        """
        cache_key = f"sitemaps_{project_id}_{'_'.join(r.strip('/') or 'root' for r in routes)}"
        cached = self._load_cache(project_id, cache_key)
        if cached is not None:
            return cached

        result = await self._call_with_retry(
            "build_sitemaps",
            {"project_id": project_id, "routes": routes},
        )

        # Normalise response: expect {"sitemaps": {route: html}} or direct dict
        if "sitemaps" in result:
            html_map = result["sitemaps"]
        elif "result" in result and isinstance(result["result"], dict):
            html_map = result["result"]
        else:
            # Best-effort: return whatever was returned
            html_map = {r: result.get("html", "") for r in routes}

        self._save_cache(project_id, cache_key, html_map)
        return html_map

    async def get_screen_code(
        self,
        project_id: str,
        screen_name: str,
    ) -> str:
        """
        Call Stitch MCP `get_screen_code` tool.
        Returns the HTML+CSS string for the named screen.
        """
        cached = self._load_cache(project_id, f"code_{screen_name}")
        if cached is not None:
            return cached if isinstance(cached, str) else cached.get("html", "")

        result = await self._call_with_retry(
            "get_screen_code",
            {"project_id": project_id, "screen_name": screen_name},
        )

        # Normalise: expect {"html": "..."} or {"code": "..."} or raw string
        if "html" in result:
            html = result["html"]
        elif "code" in result:
            html = result["code"]
        elif "result" in result:
            html = str(result["result"])
        else:
            html = str(result)

        self._save_cache(project_id, f"code_{screen_name}", html)
        return html

    async def get_screen_image(
        self,
        project_id: str,
        screen_name: str,
    ) -> str:
        """
        Call Stitch MCP `get_screen_image` tool.
        Returns base64-encoded PNG screenshot.
        """
        cached = self._load_cache(project_id, f"image_{screen_name}")
        if cached is not None:
            return cached if isinstance(cached, str) else cached.get("base64", "")

        result = await self._call_with_retry(
            "get_screen_image",
            {"project_id": project_id, "screen_name": screen_name},
        )

        # Normalise: expect {"base64": "..."} or {"image": "..."} or raw string
        if "base64" in result:
            b64 = result["base64"]
        elif "image" in result:
            b64 = result["image"]
        elif "data" in result:
            b64 = result["data"]
        else:
            b64 = str(result)

        self._save_cache(project_id, f"image_{screen_name}", b64)
        return b64

    # ------------------------------------------------------------------
    # Internal: JSON-RPC over stdio
    # ------------------------------------------------------------------

    async def _initialize(self) -> None:
        """Send MCP initialize handshake."""
        await self._send_request("initialize", {"protocolVersion": "2024-11-05",
                                                  "capabilities": {},
                                                  "clientInfo": {"name": "DesignWise", "version": "1.0.0"}})

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a single JSON-RPC request and read the response."""
        if not self._proc or self._proc.returncode is not None:
            raise RuntimeError("MCP subprocess not running")

        req_id = self._next_id()
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        line = json.dumps(request) + "\n"

        async with self._lock:
            assert self._proc.stdin is not None
            self._proc.stdin.write(line.encode())
            await self._proc.stdin.drain()

            # Read response line(s) until we find the matching id
            assert self._proc.stdout is not None
            deadline = time.monotonic() + self._timeout
            while time.monotonic() < deadline:
                try:
                    raw = await asyncio.wait_for(
                        self._proc.stdout.readline(),
                        timeout=max(1, deadline - time.monotonic()),
                    )
                except asyncio.TimeoutError:
                    break
                if not raw:
                    break
                try:
                    response = json.loads(raw.decode().strip())
                    if response.get("id") == req_id:
                        if "error" in response:
                            raise RuntimeError(f"MCP error: {response['error']}")
                        return response.get("result", {})
                except json.JSONDecodeError:
                    # Log line and continue (might be server debug output)
                    logger.debug("StitchMCP non-JSON line: %s", raw[:200])
                    continue

        raise TimeoutError(f"StitchMCP: no response to {method} within {self._timeout}s")

    async def _call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a named MCP tool via tools/call."""
        return await self._send_request(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
        )

    async def _call_with_retry(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Call an MCP tool with up to MAX_RETRIES attempts.
        On persistent failure, try to restart subprocess and retry once more.
        """
        last_exc: Optional[Exception] = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if not self._proc or self._proc.returncode is not None:
                    await self.start()
                return await self._call_mcp_tool(tool_name, arguments)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "StitchMCP %s attempt %d/%d failed: %s",
                    tool_name, attempt, MAX_RETRIES, exc,
                )
                await asyncio.sleep(0.5 * attempt)

        # Final attempt: full restart
        try:
            await self.close()
            await self.start()
            return await self._call_mcp_tool(tool_name, arguments)
        except Exception as exc:
            logger.error("StitchMCP %s failed after restart: %s", tool_name, exc)
            raise RuntimeError(
                f"StitchMCP: {tool_name} failed after {MAX_RETRIES} retries + restart: {last_exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_path(self, project_id: str, key: str) -> Path:
        safe_key = key.replace("/", "_").replace(":", "_")
        return CACHE_DIR / project_id / f"{safe_key}.json"

    def _load_cache(self, project_id: str, key: str) -> Any | None:
        path = self._cache_path(project_id, key)
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        return None

    def _save_cache(self, project_id: str, key: str, value: Any) -> None:
        path = self._cache_path(project_id, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(json.dumps(value))
        except Exception as exc:
            logger.warning("StitchMCP cache write failed: %s", exc)

    def clear_cache(self, project_id: str | None = None) -> None:
        """Clear cache for a project (or all if project_id is None)."""
        target = CACHE_DIR / project_id if project_id else CACHE_DIR
        import shutil
        if target.exists():
            shutil.rmtree(target)
