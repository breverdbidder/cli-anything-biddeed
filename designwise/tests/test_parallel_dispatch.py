"""
Tests: Commander Parallel Exploration Dispatch
DesignWise Spec Patch — Amendment 5
5+ tests covering parallel mode, quota pre-check, and result aggregation
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Test 1: parallel_stitch_dispatch fires all explorations concurrently
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_dispatch_fires_all():
    """parallel_stitch_dispatch generates all requested explorations."""
    from designwise.agent_harness.cli_anything.designwise.core.commander import (
        parallel_stitch_dispatch
    )

    explorations = [
        {"screen_name": "landing-hero", "extra_context": "Variant A — minimal"},
        {"screen_name": "landing-hero", "extra_context": "Variant B — bold"},
        {"screen_name": "landing-hero", "extra_context": "Variant C — data-forward"},
    ]

    with patch(
        "designwise.agent_harness.cli_anything.designwise.core.commander.check_quota",
        new_callable=AsyncMock,
        return_value={"ok": True, "used": 50, "remaining": 300, "alert": False}
    ), \
    patch(
        "designwise.agent_harness.cli_anything.designwise.core.commander.StitchWiseAgent"
    ) as MockAgentCls:
        mock_agent = AsyncMock()
        MockAgentCls.return_value = mock_agent
        mock_agent.load_design_context = MagicMock(return_value="design context")
        mock_agent.generate_screen.return_value = {"status": "ok", "html": "<div/>"}

        results = await parallel_stitch_dispatch(explorations, mode="flash")

    assert len(results) == 3
    assert mock_agent.generate_screen.call_count == 3


# ---------------------------------------------------------------------------
# Test 2: parallel_stitch_dispatch defaults to flash mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_dispatch_uses_flash_by_default():
    """parallel_stitch_dispatch uses flash mode (not pro) for exploration."""
    from designwise.agent_harness.cli_anything.designwise.core.commander import (
        parallel_stitch_dispatch
    )

    mode_used = {}

    with patch(
        "designwise.agent_harness.cli_anything.designwise.core.commander.check_quota",
        new_callable=AsyncMock,
        return_value={"ok": True, "used": 0, "remaining": 350, "alert": False}
    ), \
    patch(
        "designwise.agent_harness.cli_anything.designwise.core.commander.StitchWiseAgent"
    ) as MockAgentCls:
        mock_agent = AsyncMock()
        MockAgentCls.side_effect = lambda mode=None, **kw: (mode_used.update({"mode": mode}), mock_agent)[1]
        mock_agent.load_design_context = MagicMock(return_value="ctx")
        mock_agent.generate_screen.return_value = {"status": "ok"}

        await parallel_stitch_dispatch(
            [{"screen_name": "landing-hero", "extra_context": "A"}],
            # No mode specified — defaults to flash
        )

    assert mode_used.get("mode") == "flash"


# ---------------------------------------------------------------------------
# Test 3: Quota pre-check blocks dispatch if insufficient
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_dispatch_blocked_by_quota():
    """parallel_stitch_dispatch raises QuotaExceededError when quota < exploration count."""
    from designwise.agent_harness.cli_anything.designwise.core.commander import (
        parallel_stitch_dispatch
    )
    from designwise.agent_harness.cli_anything.designwise.core.stitch_agent import QuotaExceededError

    explorations = [
        {"screen_name": "landing-hero", "extra_context": f"Variant {i}"}
        for i in range(5)
    ]

    with patch(
        "designwise.agent_harness.cli_anything.designwise.core.commander.check_quota",
        new_callable=AsyncMock,
        return_value={"ok": True, "used": 347, "remaining": 3, "alert": True}
    ):
        with pytest.raises(QuotaExceededError) as exc_info:
            await parallel_stitch_dispatch(explorations, mode="flash")

    assert "3" in str(exc_info.value) or "insufficient" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Test 4: Partial failure returns error entry, not exception
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_dispatch_partial_failure_continues():
    """If one exploration fails, result contains error entry but others succeed."""
    from designwise.agent_harness.cli_anything.designwise.core.commander import (
        parallel_stitch_dispatch
    )

    call_count = 0

    async def flaky_generate(screen_name, mode=None, extra_context=""):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("Stitch API timeout")
        return {"status": "ok", "screen_name": screen_name}

    with patch(
        "designwise.agent_harness.cli_anything.designwise.core.commander.check_quota",
        new_callable=AsyncMock,
        return_value={"ok": True, "used": 0, "remaining": 350, "alert": False}
    ), \
    patch(
        "designwise.agent_harness.cli_anything.designwise.core.commander.StitchWiseAgent"
    ) as MockAgentCls:
        mock_agent = MagicMock()
        MockAgentCls.return_value = mock_agent
        mock_agent.load_design_context.return_value = "ctx"
        mock_agent.generate_screen = flaky_generate

        results = await parallel_stitch_dispatch(
            [
                {"screen_name": "landing-hero", "extra_context": "A"},
                {"screen_name": "landing-hero", "extra_context": "B"},
                {"screen_name": "landing-hero", "extra_context": "C"},
            ],
            mode="flash"
        )

    assert len(results) == 3
    error_entries = [r for r in results if "error" in r]
    success_entries = [r for r in results if "status" in r]
    assert len(error_entries) == 1
    assert len(success_entries) == 2


# ---------------------------------------------------------------------------
# Test 5: Empty explorations returns empty list (no API calls)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_dispatch_empty_returns_empty():
    """parallel_stitch_dispatch with empty list returns [] without API calls."""
    from designwise.agent_harness.cli_anything.designwise.core.commander import (
        parallel_stitch_dispatch
    )

    with patch(
        "designwise.agent_harness.cli_anything.designwise.core.commander.check_quota",
        new_callable=AsyncMock
    ) as mock_quota:
        result = await parallel_stitch_dispatch([])

    assert result == []
    assert mock_quota.call_count == 0


# ---------------------------------------------------------------------------
# Test 6: Commander routes a_b_test to parallel_stitch_dispatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_commander_ab_test_uses_parallel_dispatch():
    """Commander dispatches a_b_test tasks via parallel_stitch_dispatch."""
    from designwise.agent_harness.cli_anything.designwise.core.commander import CommanderAgent

    agent = CommanderAgent()

    with patch(
        "designwise.agent_harness.cli_anything.designwise.core.commander.create_task",
        new_callable=AsyncMock,
        return_value="test-task-uuid"
    ), \
    patch(
        "designwise.agent_harness.cli_anything.designwise.core.commander.update_task_status",
        new_callable=AsyncMock
    ), \
    patch(
        "designwise.agent_harness.cli_anything.designwise.core.commander.send_telegram",
        new_callable=AsyncMock
    ), \
    patch(
        "designwise.agent_harness.cli_anything.designwise.core.commander.quota_gate",
        new_callable=AsyncMock,
        return_value={"ok": True, "used": 0, "remaining": 350, "alert": False}
    ), \
    patch(
        "designwise.agent_harness.cli_anything.designwise.core.commander.parallel_stitch_dispatch",
        new_callable=AsyncMock,
        return_value=[{"status": "ok"}, {"status": "ok"}, {"status": "ok"}]
    ) as mock_parallel:
        result = await agent.process({
            "task_type": "a_b_test",
            "screen_name": "landing-hero",
            "mode": "flash",
        })

    assert mock_parallel.called
    assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Test 7: Commander quota_gate sends Telegram at 80% usage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_commander_quota_gate_alerts_at_80_pct():
    """quota_gate sends Telegram alert when stitch_usage reports alert=True."""
    from designwise.agent_harness.cli_anything.designwise.core.commander import quota_gate

    with patch(
        "designwise.agent_harness.cli_anything.designwise.core.commander.check_quota",
        new_callable=AsyncMock,
        return_value={"ok": True, "used": 280, "remaining": 70, "alert": True}
    ), \
    patch(
        "designwise.agent_harness.cli_anything.designwise.core.commander.send_telegram",
        new_callable=AsyncMock
    ) as mock_tg:
        result = await quota_gate(mode="pro")

    assert mock_tg.called
    alert_msg = mock_tg.call_args[0][0]
    assert "quota" in alert_msg.lower() or "QUOTA" in alert_msg
    assert result["alert"] is True
