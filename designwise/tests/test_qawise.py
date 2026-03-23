"""
test_qawise.py — QAWise Agent (S3.1)
12 binary tests: visual regression, E2E, Lighthouse, baseline capture.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Import check ───────────────────────────────────────────────────────────────

def test_qawise_import():
    from cli_anything.designwise.core.qawise_agent import QAWiseAgent
    assert QAWiseAgent is not None


def test_qawise_constants():
    from cli_anything.designwise.core.qawise_agent import VIEWPORTS, E2E_FLOW, LIGHTHOUSE_TARGETS, DIFF_THRESHOLD
    assert len(VIEWPORTS) == 3
    assert VIEWPORTS[0]["width"] == 1280
    assert VIEWPORTS[1]["width"] == 768
    assert VIEWPORTS[2]["width"] == 375
    assert "landing" in E2E_FLOW
    assert LIGHTHOUSE_TARGETS["performance"] == 80
    assert LIGHTHOUSE_TARGETS["accessibility"] == 90
    assert LIGHTHOUSE_TARGETS["seo"] == 80
    assert DIFF_THRESHOLD == 0.01


def test_qawise_init():
    from cli_anything.designwise.core.qawise_agent import QAWiseAgent
    agent = QAWiseAgent(supabase_url="http://test", supabase_key="testkey")
    assert agent.supabase_url == "http://test"
    assert agent.supabase_key == "testkey"


def test_qawise_playwright_check():
    from cli_anything.designwise.core.qawise_agent import QAWiseAgent
    agent = QAWiseAgent()
    result = agent._check_playwright()
    assert isinstance(result, bool)


def test_capture_screenshots_no_playwright():
    """Without Playwright installed, returns descriptive error dict."""
    from cli_anything.designwise.core.qawise_agent import QAWiseAgent
    agent = QAWiseAgent()
    agent._playwright_available = False
    result = asyncio.run(agent.capture_screenshots("https://zonewise.ai"))
    assert result["url"] == "https://zonewise.ai"
    assert "viewports" in result
    for vp in result["viewports"].values():
        assert "error" in vp


def test_capture_screenshots_returns_three_viewports():
    """Always returns desktop/tablet/mobile keys."""
    from cli_anything.designwise.core.qawise_agent import QAWiseAgent
    agent = QAWiseAgent()
    agent._playwright_available = False
    result = asyncio.run(agent.capture_screenshots("https://zonewise.ai"))
    assert "desktop" in result["viewports"]
    assert "tablet" in result["viewports"]
    assert "mobile" in result["viewports"]


def test_e2e_flow_no_playwright():
    """E2E flow skipped gracefully when Playwright unavailable."""
    from cli_anything.designwise.core.qawise_agent import QAWiseAgent
    agent = QAWiseAgent()
    agent._playwright_available = False
    result = asyncio.run(agent.run_e2e_flow("https://zonewise.ai"))
    assert result["status"] == "skipped"
    assert "flow" in result


def test_e2e_flow_contains_all_steps():
    """E2E flow skipped result includes all 9 flow steps."""
    from cli_anything.designwise.core.qawise_agent import QAWiseAgent, E2E_FLOW
    agent = QAWiseAgent()
    agent._playwright_available = False
    result = asyncio.run(agent.run_e2e_flow("https://zonewise.ai"))
    assert result["flow"] == E2E_FLOW
    assert len(result["flow"]) == 9


def test_lighthouse_no_cli():
    """Lighthouse returns informative dict when CLI not installed."""
    from cli_anything.designwise.core.qawise_agent import QAWiseAgent
    with patch("shutil.which", return_value=None):
        agent = QAWiseAgent()
        result = asyncio.run(agent.run_lighthouse_ci("https://zonewise.ai"))
    assert "scores" in result
    assert result["passed"] is False


def test_diff_against_baseline_no_db():
    """diff_against_baseline returns error when Supabase not configured."""
    from cli_anything.designwise.core.qawise_agent import QAWiseAgent
    agent = QAWiseAgent(supabase_url="", supabase_key="")
    result = asyncio.run(agent.diff_against_baseline("/"))
    assert "error" in result or "status" in result


def test_run_requires_url():
    """run() without URL returns error."""
    from cli_anything.designwise.core.qawise_agent import QAWiseAgent
    agent = QAWiseAgent()
    result = asyncio.run(agent.run())
    assert "error" in result


def test_run_returns_all_sections():
    """run() with URL returns screenshots + e2e + lighthouse sections."""
    from cli_anything.designwise.core.qawise_agent import QAWiseAgent
    agent = QAWiseAgent()
    agent._playwright_available = False
    with patch("shutil.which", return_value=None):
        result = asyncio.run(agent.run(url="https://zonewise.ai"))
    assert "screenshots" in result
    assert "e2e" in result
    assert "lighthouse" in result
    assert result["url"] == "https://zonewise.ai"
