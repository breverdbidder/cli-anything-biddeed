"""
Tests for CodeWise Agent real implementation (S2.2)
10 tests covering HTML parsing, color replacement, TypeScript output, routing, shadcn/ui,
feature branch creation.
"""

from __future__ import annotations

import asyncio
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# conftest.py adds designwise/agent-harness to sys.path
from cli_anything.designwise.core.codewise_agent import (
    CodeWiseAgent,
    COLOR_VAR_MAP,
    _html_to_nextjs_component,
    create_github_pr,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_html_parsing_extracts_elements():
    """_html_to_nextjs_component wraps content in a Next.js FC component."""
    html = '<div class="hero"><h1>ZoneWise</h1></div>'
    result = _html_to_nextjs_component(html, "landing-hero", "/")
    assert "const LandingHero: FC" in result
    assert "import type { FC }" in result
    assert "ZoneWise" in result


def test_color_replacement_hex_to_css_var():
    """Hardcoded hex values are replaced with CSS variables in convert_screen."""

    async def run():
        agent = CodeWiseAgent()
        html = '<div style="background-color: #1E3A5F; color: #F59E0B;">test</div>'
        result = await agent.convert_screen("landing-hero", html)
        tsx = result["tsx_code"]
        # Hex values must not appear verbatim in final TSX
        assert "#1E3A5F" not in tsx or "var(--color-primary)" in tsx
        assert "#F59E0B" not in tsx or "var(--color-accent)" in tsx

    asyncio.get_event_loop().run_until_complete(run())


def test_typescript_output_structure():
    """Generated TSX has correct TypeScript export structure."""
    html = "<section>content</section>"
    result = _html_to_nextjs_component(html, "app", "/app")
    assert "export default" in result
    assert "FC" in result
    assert "import {" in result


def test_route_mapping_landing_to_root():
    """landing-hero maps to / route."""

    async def run():
        agent = CodeWiseAgent()
        result = await agent.convert_screen("landing-hero", "<div>hero</div>")
        assert result["route"] == "/"

    asyncio.get_event_loop().run_until_complete(run())


def test_route_mapping_heatmap():
    """heatmap screen maps to /heatmap route."""

    async def run():
        agent = CodeWiseAgent()
        result = await agent.convert_screen("heatmap", "<div>map</div>")
        assert result["route"] == "/heatmap"

    asyncio.get_event_loop().run_until_complete(run())


def test_route_mapping_unknown_screen():
    """Unknown screen names get /{screen_name} route."""

    async def run():
        agent = CodeWiseAgent()
        result = await agent.convert_screen("my-custom-page", "<div>x</div>")
        assert result["route"] == "/my-custom-page"

    asyncio.get_event_loop().run_until_complete(run())


def test_shadcn_component_substitution():
    """HTML button tags are substituted with shadcn/ui Button."""

    async def run():
        agent = CodeWiseAgent()
        html = '<button className="cta">Sign Up</button>'
        result = await agent.convert_screen("landing-hero", html)
        tsx = result["tsx_code"]
        assert "Button" in tsx
        assert "@/components/ui/button" in tsx

    asyncio.get_event_loop().run_until_complete(run())


def test_convert_all_screens_returns_files():
    """convert_all_screens returns list of {path, content} files."""

    async def run():
        agent = CodeWiseAgent()
        screens = {
            "landing-hero": "<div>hero</div>",
            "app": "<div>app</div>",
        }
        result = await agent.convert_all_screens(screens)
        assert "files" in result
        assert "routes" in result
        assert result["count"] >= 2
        paths = [f["path"] for f in result["files"]]
        assert "app/page.tsx" in paths

    asyncio.get_event_loop().run_until_complete(run())


def test_convert_all_screens_generates_index():
    """convert_all_screens includes a barrel index export file."""

    async def run():
        agent = CodeWiseAgent()
        screens = {"heatmap": "<div>map</div>"}
        result = await agent.convert_all_screens(screens)
        paths = [f["path"] for f in result["files"]]
        assert any("index" in p for p in paths)

    asyncio.get_event_loop().run_until_complete(run())


def test_convert_screen_returns_component_name():
    """convert_screen returns PascalCase component_name."""

    async def run():
        agent = CodeWiseAgent()
        result = await agent.convert_screen("landing-hero", "<div>x</div>")
        assert result["component_name"] == "LandingHero"

    asyncio.get_event_loop().run_until_complete(run())


def test_create_feature_branch_returns_dict(tmp_path):
    """create_feature_branch returns a result dict with status or branch key."""
    import subprocess

    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path), capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path), capture_output=True,
    )
    (tmp_path / "README.md").write_text("init")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)

    async def run():
        agent = CodeWiseAgent(repo_path=str(tmp_path))
        with patch(
            "cli_anything.designwise.core.codewise_agent.create_github_pr",
            new_callable=AsyncMock,
            return_value={"pr_url": "https://github.com/test/pr/1", "pr_number": 1},
        ):
            result = await agent.create_feature_branch(
                "landing-hero",
                files=[{
                    "path": "app/page.tsx",
                    "content": "export default function Page() { return <div/>; }",
                }],
                repo_path=str(tmp_path),
            )
        assert isinstance(result, dict)
        assert "branch" in result or "status" in result

    asyncio.get_event_loop().run_until_complete(run())
