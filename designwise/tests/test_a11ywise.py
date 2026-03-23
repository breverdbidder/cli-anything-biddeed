"""
test_a11ywise.py — AccessibilityWise Agent (S3.4)
10 binary tests: axe scan, keyboard nav, ARIA labels, motion, color.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_a11ywise_import():
    from cli_anything.designwise.core.a11y_agent import A11yWiseAgent
    assert A11yWiseAgent is not None


def test_a11ywise_constants():
    from cli_anything.designwise.core.a11y_agent import WCAG_AA_TARGET, KEYBOARD_NAV_ELEMENTS, ARIA_REQUIRED_ELEMENTS
    assert WCAG_AA_TARGET == 90
    assert "button" in KEYBOARD_NAV_ELEMENTS
    assert "input" in KEYBOARD_NAV_ELEMENTS
    assert "button" in ARIA_REQUIRED_ELEMENTS


def test_a11ywise_init():
    from cli_anything.designwise.core.a11y_agent import A11yWiseAgent
    agent = A11yWiseAgent(supabase_url="http://test", supabase_key="key")
    assert agent.supabase_url == "http://test"


def test_axe_scan_no_playwright():
    """axe scan returns score=0 + note when Playwright unavailable."""
    from cli_anything.designwise.core.a11y_agent import A11yWiseAgent
    agent = A11yWiseAgent()
    agent._playwright_available = False
    result = asyncio.run(agent.run_axe_scan("https://zonewise.ai"))
    assert result["score"] == 0
    assert "note" in result
    assert result["url"] == "https://zonewise.ai"


def test_keyboard_nav_no_playwright():
    """Keyboard nav test skips gracefully without Playwright."""
    from cli_anything.designwise.core.a11y_agent import A11yWiseAgent
    agent = A11yWiseAgent()
    agent._playwright_available = False
    result = asyncio.run(agent.test_keyboard_nav("https://zonewise.ai"))
    assert result["status"] == "skipped"


def test_aria_audit_no_playwright():
    """ARIA audit skips gracefully without Playwright."""
    from cli_anything.designwise.core.a11y_agent import A11yWiseAgent
    agent = A11yWiseAgent()
    agent._playwright_available = False
    result = asyncio.run(agent.audit_aria_labels("https://zonewise.ai"))
    assert result["status"] == "skipped"


def test_color_independence_check():
    """Color independence check returns partial status (requires manual review)."""
    from cli_anything.designwise.core.a11y_agent import A11yWiseAgent
    agent = A11yWiseAgent()
    result = asyncio.run(agent.check_color_independence("https://zonewise.ai"))
    assert result["status"] == "partial"
    assert "note" in result


def test_motion_preferences_no_playwright():
    """Motion preferences check skips without Playwright."""
    from cli_anything.designwise.core.a11y_agent import A11yWiseAgent
    agent = A11yWiseAgent()
    agent._playwright_available = False
    result = asyncio.run(agent.check_motion_preferences("https://zonewise.ai"))
    assert result["status"] == "skipped"


def test_run_requires_url():
    """run() without URL returns error."""
    from cli_anything.designwise.core.a11y_agent import A11yWiseAgent
    agent = A11yWiseAgent()
    result = asyncio.run(agent.run())
    assert "error" in result


def test_run_returns_all_sections():
    """run() with URL returns axe_scan + keyboard_nav + aria_labels sections."""
    from cli_anything.designwise.core.a11y_agent import A11yWiseAgent
    agent = A11yWiseAgent()
    agent._playwright_available = False
    result = asyncio.run(agent.run(url="https://zonewise.ai"))
    assert "axe_scan" in result
    assert "keyboard_nav" in result
    assert "aria_labels" in result
    assert "score" in result
    assert result["wcag_target"] == 90
