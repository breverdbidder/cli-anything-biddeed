"""
Tests for StitchMCPClient (stitch_mcp.py)
S2.1 — 10 tests
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# conftest.py adds designwise/agent-harness to sys.path
from cli_anything.designwise.utils.stitch_mcp import StitchMCPClient
import cli_anything.designwise.utils.stitch_mcp as stitch_mcp_mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_stitch_mcp_client_initializes():
    """StitchMCPClient can be instantiated with defaults."""
    client = StitchMCPClient()
    assert client._proc is None
    assert client._request_id == 0
    assert client._timeout == 30


def test_cache_path_is_deterministic():
    """Cache path is the same for same project + key."""
    client = StitchMCPClient()
    p1 = client._cache_path("proj-a", "code_landing-hero")
    p2 = client._cache_path("proj-a", "code_landing-hero")
    assert p1 == p2
    assert "proj-a" in str(p1)


def test_cache_save_and_load(tmp_path, monkeypatch):
    """save_cache + load_cache round-trips JSON correctly."""
    monkeypatch.setattr(stitch_mcp_mod, "CACHE_DIR", tmp_path)
    client = StitchMCPClient()
    client._save_cache("proj", "key1", {"html": "<div>hello</div>"})
    loaded = client._load_cache("proj", "key1")
    assert loaded == {"html": "<div>hello</div>"}


def test_cache_miss_returns_none(tmp_path, monkeypatch):
    """load_cache returns None on cache miss."""
    monkeypatch.setattr(stitch_mcp_mod, "CACHE_DIR", tmp_path)
    client = StitchMCPClient()
    result = client._load_cache("proj", "nonexistent")
    assert result is None


def test_cache_save_overwrites_existing(tmp_path, monkeypatch):
    """Saving to the same key overwrites the previous value."""
    monkeypatch.setattr(stitch_mcp_mod, "CACHE_DIR", tmp_path)
    client = StitchMCPClient()
    client._save_cache("proj", "key", "v1")
    client._save_cache("proj", "key", "v2")
    assert client._load_cache("proj", "key") == "v2"


@pytest.mark.asyncio
async def test_get_screen_code_uses_cache(tmp_path, monkeypatch):
    """get_screen_code returns cached value without spawning subprocess."""
    monkeypatch.setattr(stitch_mcp_mod, "CACHE_DIR", tmp_path)
    client = StitchMCPClient()
    client._save_cache("proj", "code_hero", "<html>cached</html>")

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        result = await client.get_screen_code("proj", "hero")

    assert result == "<html>cached</html>"
    mock_exec.assert_not_called()


@pytest.mark.asyncio
async def test_get_screen_image_returns_base64(tmp_path, monkeypatch):
    """get_screen_image returns base64 string from cache."""
    monkeypatch.setattr(stitch_mcp_mod, "CACHE_DIR", tmp_path)
    client = StitchMCPClient()
    b64 = "aGVsbG8="  # "hello" base64
    client._save_cache("proj", "image_app", b64)
    result = await client.get_screen_image("proj", "app")
    assert result == b64


@pytest.mark.asyncio
async def test_build_sitemaps_returns_dict_type(tmp_path, monkeypatch):
    """build_sitemaps returns a dict (from cache if pre-seeded)."""
    monkeypatch.setattr(stitch_mcp_mod, "CACHE_DIR", tmp_path)
    client = StitchMCPClient()
    sitemap = {"/": "<html>landing</html>", "/app": "<html>app</html>"}
    routes = ["/", "/app"]
    key = f"sitemaps_proj_{'_'.join(r.strip('/') or 'root' for r in routes)}"
    client._save_cache("proj", key, sitemap)
    result = await client.build_sitemaps("proj", routes)
    assert isinstance(result, dict)
    assert "/" in result


@pytest.mark.asyncio
async def test_retry_on_connection_failure(tmp_path, monkeypatch):
    """_call_with_retry raises RuntimeError after exhausting retries."""
    monkeypatch.setattr(stitch_mcp_mod, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(stitch_mcp_mod, "MAX_RETRIES", 2)

    async def mock_exec(*args, **kwargs):
        raise ConnectionError("MCP unavailable")

    monkeypatch.setattr("asyncio.create_subprocess_exec", mock_exec)
    monkeypatch.setattr("asyncio.sleep", AsyncMock())

    client = StitchMCPClient(timeout=1)
    with pytest.raises(RuntimeError):
        await client._call_with_retry(
            "get_screen_code", {"project_id": "p", "screen_name": "s"}
        )


@pytest.mark.asyncio
async def test_clear_cache_removes_directory(tmp_path, monkeypatch):
    """clear_cache removes the cache directory for a project."""
    monkeypatch.setattr(stitch_mcp_mod, "CACHE_DIR", tmp_path)
    client = StitchMCPClient()
    client._save_cache("myproj", "key", "value")
    assert (tmp_path / "myproj").exists()
    client.clear_cache("myproj")
    assert not (tmp_path / "myproj").exists()
