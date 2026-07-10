#!/usr/bin/env python3
"""
verify_deployment.py — Dify Custom Tool: deployment-verifier
Issue: breverdbidder/cli-anything-biddeed#101

Headless Playwright browser → screenshot → verify → auto-report.
Adapted from JiuwenClaw's Playwright runtime (Apache 2.0), removing Huawei vendor coupling.

Usage:
    python verify_deployment.py --url https://zonewise.ai/chat-v2
    python verify_deployment.py --url https://zonewise.ai --selectors "#main-content,.hero"
    python verify_deployment.py --batch urls.txt
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# ── Constants ─────────────────────────────────────────────────────────────────

TIMEOUT_MS = 30_000          # 30-second page load timeout (JiuwenClaw default)
NETWORK_IDLE_MS = 10_000     # Max wait for networkidle
SCREENSHOT_DIR = Path("/tmp/deployment-verifier-screenshots")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
HETZNER_DIFY_URL = "http://87.99.129.125:3100"


# ── Data Models ───────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


@dataclass
class VerifyResult:
    url: str
    status: str           # "pass" | "fail" | "error"
    http_code: int
    load_ms: float
    checks: list[CheckResult] = field(default_factory=list)
    screenshot_b64: Optional[str] = None
    screenshot_path: Optional[str] = None
    errors: list[str] = field(default_factory=list)
    verified_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "status": self.status,
            "http_code": self.http_code,
            "load_ms": round(self.load_ms, 1),
            "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in self.checks],
            "screenshot_b64": self.screenshot_b64,
            "screenshot_path": self.screenshot_path,
            "errors": self.errors,
            "verified_at": self.verified_at,
        }


# ── Core Verifier ─────────────────────────────────────────────────────────────

class DeploymentVerifier:
    """
    Headless Chromium verifier.
    Checks HTTP status, CSS selectors, load time, and captures screenshots.
    """

    def __init__(
        self,
        selectors: Optional[list[str]] = None,
        screenshot: bool = True,
        viewport: tuple[int, int] = (1280, 800),
    ):
        self.selectors = selectors or []
        self.screenshot = screenshot
        self.viewport = {"width": viewport[0], "height": viewport[1]}
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    async def verify(self, url: str) -> VerifyResult:
        """Verify a single URL. Returns VerifyResult with all findings."""
        import datetime
        result = VerifyResult(
            url=url,
            status="error",
            http_code=0,
            load_ms=0.0,
            verified_at=datetime.datetime.utcnow().isoformat() + "Z",
        )

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            result.errors.append("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return result

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                page = await browser.new_page(viewport=self.viewport)

                # ── Navigation + timing ──────────────────────────────────────
                t0 = time.monotonic()
                try:
                    response = await page.goto(url, timeout=TIMEOUT_MS, wait_until="domcontentloaded")
                    await page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_MS)
                except Exception as nav_err:
                    result.errors.append(f"Navigation failed: {nav_err}")
                    await browser.close()
                    return result

                result.load_ms = (time.monotonic() - t0) * 1000
                result.http_code = response.status if response else 0

                # ── HTTP status check ────────────────────────────────────────
                ok_codes = {200, 301, 302, 307, 308}
                result.checks.append(CheckResult(
                    name="http_status",
                    passed=result.http_code in ok_codes,
                    detail=f"HTTP {result.http_code}",
                ))

                # ── Load time check (<8s acceptable) ─────────────────────────
                result.checks.append(CheckResult(
                    name="load_time",
                    passed=result.load_ms < 8000,
                    detail=f"{result.load_ms:.0f}ms",
                ))

                # ── NEXT_DATA / app hydration check ──────────────────────────
                next_data = await page.evaluate("() => !!window.__NEXT_DATA__")
                result.checks.append(CheckResult(
                    name="next_hydration",
                    passed=bool(next_data),
                    detail="__NEXT_DATA__ present" if next_data else "__NEXT_DATA__ missing",
                ))

                # ── Vercel build error detection ─────────────────────────────
                page_text = await page.inner_text("body") if result.http_code in ok_codes else ""
                vercel_error = any(
                    phrase in page_text
                    for phrase in [
                        "Application error",
                        "Internal Server Error",
                        "This page could not be found",
                        "500 Internal",
                        "Build failed",
                        "DEPLOYMENT_ERROR",
                    ]
                )
                result.checks.append(CheckResult(
                    name="no_vercel_error",
                    passed=not vercel_error,
                    detail="No Vercel build error" if not vercel_error else "Vercel error detected in body",
                ))

                # ── Custom CSS selector checks ────────────────────────────────
                for sel in self.selectors:
                    element = await page.query_selector(sel)
                    result.checks.append(CheckResult(
                        name=f"selector:{sel}",
                        passed=element is not None,
                        detail=f"'{sel}' {'found' if element else 'NOT found'}",
                    ))

                # ── Screenshot ───────────────────────────────────────────────
                if self.screenshot:
                    safe_name = url.replace("://", "_").replace("/", "_").replace(".", "-")[:60]
                    shot_path = SCREENSHOT_DIR / f"{safe_name}.png"
                    await page.screenshot(path=str(shot_path), full_page=False)
                    result.screenshot_path = str(shot_path)
                    with open(shot_path, "rb") as f:
                        result.screenshot_b64 = base64.b64encode(f.read()).decode()

                await browser.close()

        except Exception as exc:
            result.errors.append(f"Playwright error: {exc}")
            return result

        # ── Determine overall status ─────────────────────────────────────────
        failed = [c for c in result.checks if not c.passed]
        if result.errors:
            result.status = "error"
        elif failed:
            result.status = "fail"
        else:
            result.status = "pass"

        return result

    async def verify_batch(self, urls: list[str]) -> list[VerifyResult]:
        """Verify multiple URLs concurrently (max 3 parallel)."""
        sem = asyncio.Semaphore(3)

        async def _bounded(url: str) -> VerifyResult:
            async with sem:
                return await self.verify(url)

        return await asyncio.gather(*[_bounded(u) for u in urls])


# ── Supabase Persistence ──────────────────────────────────────────────────────

async def persist_result(result: VerifyResult) -> bool:
    """Write VerifyResult to deployment_checks table. Returns True on success."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[persist] SUPABASE_URL/SUPABASE_SERVICE_KEY not set — skipping DB write", file=sys.stderr)
        return False
    try:
        import httpx
        payload = {
            "url": result.url,
            "status": result.status,
            "http_code": result.http_code,
            "load_ms": result.load_ms,
            "checks_json": json.dumps([c.__dict__ for c in result.checks]),
            "errors_json": json.dumps(result.errors),
            "has_screenshot": result.screenshot_path is not None,
            "verified_at": result.verified_at,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/deployment_checks",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json=payload,
            )
            resp.raise_for_status()
            return True
    except Exception as exc:
        print(f"[persist] DB write failed: {exc}", file=sys.stderr)
        return False


# ── CLI ───────────────────────────────────────────────────────────────────────

def _print_result(r: VerifyResult) -> None:
    icon = {"pass": "✅", "fail": "❌", "error": "💥"}.get(r.status, "?")
    print(f"\n{icon} {r.url} — {r.status.upper()} (HTTP {r.http_code}, {r.load_ms:.0f}ms)")
    for c in r.checks:
        sym = "✅" if c.passed else "❌"
        print(f"  {sym} {c.name}: {c.detail}")
    for e in r.errors:
        print(f"  ⚠️  {e}")
    if r.screenshot_path:
        print(f"  📸 Screenshot: {r.screenshot_path}")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Dify deployment-verifier tool")
    parser.add_argument("--url", help="Single URL to verify")
    parser.add_argument("--batch", help="File with one URL per line")
    parser.add_argument("--selectors", help="Comma-separated CSS selectors to check")
    parser.add_argument("--no-screenshot", action="store_true", help="Skip screenshot capture")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    parser.add_argument("--persist", action="store_true", help="Write results to Supabase deployment_checks")
    args = parser.parse_args()

    if not args.url and not args.batch:
        parser.print_help()
        return 1

    selectors = [s.strip() for s in args.selectors.split(",")] if args.selectors else []
    verifier = DeploymentVerifier(
        selectors=selectors,
        screenshot=not args.no_screenshot,
    )

    if args.url:
        urls = [args.url]
    else:
        urls = [line.strip() for line in Path(args.batch).read_text().splitlines() if line.strip()]

    results = await verifier.verify_batch(urls)

    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        for r in results:
            _print_result(r)

    if args.persist:
        for r in results:
            ok = await persist_result(r)
            if ok:
                print(f"  💾 Persisted to deployment_checks")

    # Exit 1 if any failures
    failed = [r for r in results if r.status in ("fail", "error")]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
