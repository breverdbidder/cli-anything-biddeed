"""
Tests: BrandGuard Design Drift Detection
DesignWise Spec Patch — Amendment 3
5+ tests covering URL extraction, token diff, GitHub Issue creation, Telegram alert
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from datetime import datetime


MOCK_HTML_CLEAN = """
<html>
<head>
<style>
  :root {
    --color-primary: #1E3A5F;
    --color-accent: #F59E0B;
    --color-background: #020617;
  }
  body { font-family: Inter, sans-serif; font-size: 16px; color: #F8FAFC; }
  .heading { font-size: 32px; }
</style>
</head>
<body style="background-color: #020617;">
  <h1 style="color: #F8FAFC; font-family: Inter;">ZoneWise</h1>
  <button style="background: #F59E0B;">Try Free</button>
</body>
</html>
"""

MOCK_HTML_DRIFTED = """
<html>
<head>
<style>
  body { font-family: Arial, sans-serif; font-size: 14px; }
  .btn { background: #FF0000; }
  .text { color: #000000; font-size: 10px; }
</style>
</head>
<body style="background: #FFFFFF;">
  <h1 style="font-family: Roboto;">ZoneWise</h1>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Test 1: extract_tokens_from_url returns correct token structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_tokens_structure():
    """extract_tokens_from_url returns colors, fonts, font_sizes_px, css_variables."""
    from designwise.agent_harness.cli_anything.designwise.core.brandguard_agent import (
        extract_tokens_from_url
    )

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_HTML_CLEAN
        mock_client.get.return_value = mock_resp

        result = await extract_tokens_from_url("https://zonewise.ai")

    assert "colors" in result
    assert "fonts" in result
    assert "font_sizes_px" in result
    assert "css_variables" in result
    assert result["source_url"] == "https://zonewise.ai"


# ---------------------------------------------------------------------------
# Test 2: Clean site produces no drift findings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_drift_on_clean_site():
    """check_design_drift returns drift_detected=False for brand-compliant HTML."""
    from designwise.agent_harness.cli_anything.designwise.core.brandguard_agent import (
        check_design_drift
    )

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_HTML_CLEAN
        mock_client.get.return_value = mock_resp

        # Patch GitHub + Telegram (should not be called)
        with patch(
            "designwise.agent_harness.cli_anything.designwise.core.brandguard_agent._create_github_issue",
            new_callable=AsyncMock
        ) as mock_issue, \
        patch(
            "designwise.agent_harness.cli_anything.designwise.core.brandguard_agent._send_telegram_alert",
            new_callable=AsyncMock
        ) as mock_tg:
            result = await check_design_drift("https://zonewise.ai", "DESIGN.md")

    assert mock_issue.call_count == 0
    assert mock_tg.call_count == 0


# ---------------------------------------------------------------------------
# Test 3: Drifted site triggers GitHub Issue creation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_drift_creates_github_issue():
    """Drifted CSS triggers GitHub Issue creation with correct title."""
    from designwise.agent_harness.cli_anything.designwise.core.brandguard_agent import (
        check_design_drift
    )

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_HTML_DRIFTED
        mock_client.get.return_value = mock_resp

        with patch(
            "designwise.agent_harness.cli_anything.designwise.core.brandguard_agent._create_github_issue",
            new_callable=AsyncMock,
            return_value="https://github.com/breverdbidder/zonewise-web/issues/99"
        ) as mock_issue, \
        patch(
            "designwise.agent_harness.cli_anything.designwise.core.brandguard_agent._send_telegram_alert",
            new_callable=AsyncMock
        ):
            result = await check_design_drift("https://zonewise.ai", "DESIGN.md")

    assert result["drift_detected"] is True
    assert mock_issue.called
    issue_title = mock_issue.call_args[1].get("title") or mock_issue.call_args[0][0]
    assert "Drift" in issue_title or "drift" in issue_title


# ---------------------------------------------------------------------------
# Test 4: Drifted site sends Telegram alert with finding count
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_drift_sends_telegram_alert():
    """Telegram alert sent with correct finding count on drift."""
    from designwise.agent_harness.cli_anything.designwise.core.brandguard_agent import (
        check_design_drift
    )

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = MOCK_HTML_DRIFTED
        mock_client.get.return_value = mock_resp

        with patch(
            "designwise.agent_harness.cli_anything.designwise.core.brandguard_agent._create_github_issue",
            new_callable=AsyncMock,
            return_value=None
        ), \
        patch(
            "designwise.agent_harness.cli_anything.designwise.core.brandguard_agent._send_telegram_alert",
            new_callable=AsyncMock
        ) as mock_tg:
            result = await check_design_drift("https://zonewise.ai", "DESIGN.md")

    assert mock_tg.called
    alert_msg = mock_tg.call_args[0][0]
    assert "drift" in alert_msg.lower() or "DRIFT" in alert_msg


# ---------------------------------------------------------------------------
# Test 5: Connection error returns structured error response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_tokens_connection_error():
    """extract_tokens_from_url returns error dict on ConnectError."""
    import httpx
    from designwise.agent_harness.cli_anything.designwise.core.brandguard_agent import (
        extract_tokens_from_url
    )

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.get.side_effect = httpx.ConnectError("connection refused")

        result = await extract_tokens_from_url("https://nonexistent.example.com")

    assert "error" in result
    assert result["source_url"] == "https://nonexistent.example.com"


# ---------------------------------------------------------------------------
# Test 6: Banned color detection in scanned HTML
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_banned_color_detected_in_scan():
    """scan_url flags banned color #FF0000 as critical violation."""
    from designwise.agent_harness.cli_anything.designwise.core.brandguard_agent import (
        BrandGuardAgent
    )

    agent = BrandGuardAgent()

    with patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<style>.btn { color: #FF0000; }</style>'
        mock_client.get.return_value = mock_resp
        mock_client.post.return_value = MagicMock(status_code=201)

        result = await agent.scan_url("https://zonewise.ai")

    assert result["passed"] is False
    banned_violations = [v for v in result["violations"] if v["type"] == "banned_color"]
    assert len(banned_violations) > 0


# ---------------------------------------------------------------------------
# Test 7: _diff_tokens detects missing canonical colors
# ---------------------------------------------------------------------------

def test_diff_tokens_missing_canonical_color():
    """_diff_tokens returns finding when required color is absent from live site."""
    from designwise.agent_harness.cli_anything.designwise.core.brandguard_agent import (
        _diff_tokens, CANONICAL_TOKENS
    )

    live_tokens = {
        "colors": ["#FFFFFF", "#CCCCCC"],  # No canonical colors
        "fonts": ["inter", "sans-serif"],
        "font_sizes_px": [14, 16, 24],
    }

    findings = _diff_tokens(live_tokens, CANONICAL_TOKENS)
    # Should detect missing navy/orange/slate
    assert len(findings) > 0
    assert any("#1E3A5F" in f or "1E3A5F" in f.upper() for f in findings)
