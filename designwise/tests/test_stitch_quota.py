"""
Tests: StitchWise Quota Tracking and Enforcement
DesignWise Spec Patch — Amendment 1
5+ tests covering quota tracking, enforcement, and alert thresholds
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_usage_rows(used: int, mode: str = "pro") -> list[dict]:
    """Generate fake stitch_usage rows summing to `used` generations."""
    return [{"generation_count": used, "mode": mode}]


# ---------------------------------------------------------------------------
# Test 1: Quota check returns OK when under threshold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quota_check_ok_under_threshold():
    """Quota check passes and returns correct remaining when well under limit."""
    from designwise.agent_harness.cli_anything.designwise.core.stitch_agent import (
        check_quota, QUOTA_MONTHLY
    )

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = make_usage_rows(100)
        mock_client.get.return_value = mock_resp

        result = await check_quota(mode="pro")

    assert result["ok"] is True
    assert result["used"] == 100
    assert result["remaining"] == QUOTA_MONTHLY - 100
    assert result["alert"] is False


# ---------------------------------------------------------------------------
# Test 2: Alert triggered at 80% threshold (280/350)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quota_alert_at_80_percent():
    """Telegram alert fires when usage reaches 280 (80% of 350)."""
    from designwise.agent_harness.cli_anything.designwise.core.stitch_agent import (
        check_quota, QUOTA_ALERT_THRESHOLD
    )

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = make_usage_rows(QUOTA_ALERT_THRESHOLD)
        mock_client.get.return_value = mock_resp

        # Mock the telegram send
        mock_client.post.return_value = MagicMock(status_code=200)

        with patch(
            "designwise.agent_harness.cli_anything.designwise.core.stitch_agent._send_telegram_alert",
            new_callable=AsyncMock
        ) as mock_tg:
            result = await check_quota(mode="pro")
            assert mock_tg.called
            alert_msg = mock_tg.call_args[0][0]
            assert "QUOTA ALERT" in alert_msg.upper() or "quota" in alert_msg.lower()

    assert result["alert"] is True
    assert result["used"] == QUOTA_ALERT_THRESHOLD


# ---------------------------------------------------------------------------
# Test 3: QuotaExceededError raised when remaining < 10
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quota_exceeded_raises_error():
    """QuotaExceededError raised when only 5 remaining (< 10 minimum)."""
    from designwise.agent_harness.cli_anything.designwise.core.stitch_agent import (
        check_quota, QuotaExceededError, QUOTA_MONTHLY
    )

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # 345 used → 5 remaining (< 10)
        mock_resp.json.return_value = make_usage_rows(345)
        mock_client.get.return_value = mock_resp

        with patch(
            "designwise.agent_harness.cli_anything.designwise.core.stitch_agent._send_telegram_alert",
            new_callable=AsyncMock
        ):
            with pytest.raises(QuotaExceededError) as exc_info:
                await check_quota(mode="pro")

    assert "exhausted" in str(exc_info.value).lower() or "remaining" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Test 4: record_usage inserts correct payload to Supabase
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_usage_posts_correct_payload():
    """record_usage sends correct date, mode, screen_name to stitch_usage table."""
    from designwise.agent_harness.cli_anything.designwise.core.stitch_agent import record_usage

    captured_payload = {}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_client.post.return_value = mock_resp

        def capture_post(url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return mock_resp

        mock_client.post = AsyncMock(side_effect=capture_post)
        await record_usage(mode="flash", screen_name="landing-hero", count=1)

    assert captured_payload.get("mode") == "flash"
    assert captured_payload.get("screen_name") == "landing-hero"
    assert captured_payload.get("generation_count") == 1
    assert captured_payload.get("date") == date.today().isoformat()


# ---------------------------------------------------------------------------
# Test 5: Missing stitch_usage table returns warning, does not block
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quota_check_table_missing_allows_through():
    """If stitch_usage table doesn't exist (404), quota check warns but allows generation."""
    from designwise.agent_harness.cli_anything.designwise.core.stitch_agent import check_quota

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"error": "table not found"}
        mock_client.get.return_value = mock_resp

        result = await check_quota(mode="pro")

    assert result["ok"] is True
    assert result.get("warn") == "table_missing"


# ---------------------------------------------------------------------------
# Test 6: generate_all_screens checks batch quota requirements
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_all_screens_insufficient_quota():
    """generate_all_screens raises QuotaExceededError if < 8 generations remaining."""
    from designwise.agent_harness.cli_anything.designwise.core.stitch_agent import (
        StitchWiseAgent, QuotaExceededError
    )

    agent = StitchWiseAgent(mode="pro")

    with patch(
        "designwise.agent_harness.cli_anything.designwise.core.stitch_agent.check_quota",
        new_callable=AsyncMock,
        return_value={"ok": True, "used": 345, "remaining": 5, "alert": True}
    ):
        with pytest.raises(QuotaExceededError) as exc_info:
            await agent.generate_all_screens()

    assert "5" in str(exc_info.value) or "quota" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Test 7: Mode validation rejects invalid modes
# ---------------------------------------------------------------------------

def test_stitch_agent_invalid_mode_raises():
    """StitchWiseAgent raises ValueError for invalid mode."""
    from designwise.agent_harness.cli_anything.designwise.core.stitch_agent import StitchWiseAgent

    with pytest.raises(ValueError, match="mode must be 'flash' or 'pro'"):
        StitchWiseAgent(mode="turbo")
