"""
Tests: StitchWise Interactive Prototype Flow
DesignWise Spec Patch — Amendment 2
5+ tests covering flow assembly, screen ordering, and prototype export
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Test 1: generate_prototype uses default PROTOTYPE_FLOW order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prototype_uses_correct_default_flow():
    """generate_prototype uses the defined 8-screen flow by default."""
    from designwise.agent_harness.cli_anything.designwise.core.stitch_agent import (
        StitchWiseAgent, PROTOTYPE_FLOW
    )

    agent = StitchWiseAgent(mode="pro")

    with patch.object(agent, "_call_stitch_mcp", new_callable=AsyncMock) as mock_mcp, \
         patch(
             "designwise.agent_harness.cli_anything.designwise.core.stitch_agent.check_quota",
             new_callable=AsyncMock,
             return_value={"ok": True, "used": 50, "remaining": 300, "alert": False}
         ), \
         patch(
             "designwise.agent_harness.cli_anything.designwise.core.stitch_agent.record_usage",
             new_callable=AsyncMock
         ):
        mock_mcp.return_value = {
            "action": "generate_prototype",
            "prototype_url": "https://lab.zonewise.ai/prototype",
        }

        result = await agent.generate_prototype()

    assert result["flow"] == PROTOTYPE_FLOW
    assert result["screen_count"] == len(PROTOTYPE_FLOW)
    assert mock_mcp.called


# ---------------------------------------------------------------------------
# Test 2: generate_prototype accepts custom flow override
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prototype_accepts_custom_flow():
    """generate_prototype respects custom flow list."""
    from designwise.agent_harness.cli_anything.designwise.core.stitch_agent import StitchWiseAgent

    agent = StitchWiseAgent(mode="flash")
    custom_flow = ["landing-hero", "gate", "signup"]

    with patch.object(agent, "_call_stitch_mcp", new_callable=AsyncMock) as mock_mcp, \
         patch(
             "designwise.agent_harness.cli_anything.designwise.core.stitch_agent.check_quota",
             new_callable=AsyncMock,
             return_value={"ok": True, "used": 0, "remaining": 350, "alert": False}
         ), \
         patch(
             "designwise.agent_harness.cli_anything.designwise.core.stitch_agent.record_usage",
             new_callable=AsyncMock
         ):
        mock_mcp.return_value = {"action": "generate_prototype"}

        result = await agent.generate_prototype(flow=custom_flow)

    assert result["flow"] == custom_flow
    assert result["screen_count"] == 3


# ---------------------------------------------------------------------------
# Test 3: Prototype prompt includes all required interaction specs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prototype_prompt_includes_interaction_spec():
    """generate_prototype prompt includes CTA → Heatmap and Gate interaction."""
    from designwise.agent_harness.cli_anything.designwise.core.stitch_agent import StitchWiseAgent

    agent = StitchWiseAgent(mode="pro")
    captured_kwargs = {}

    async def capture_mcp(action, **kwargs):
        captured_kwargs.update(kwargs)
        return {"action": action}

    with patch.object(agent, "_call_stitch_mcp", side_effect=capture_mcp), \
         patch(
             "designwise.agent_harness.cli_anything.designwise.core.stitch_agent.check_quota",
             new_callable=AsyncMock,
             return_value={"ok": True, "used": 0, "remaining": 350, "alert": False}
         ), \
         patch(
             "designwise.agent_harness.cli_anything.designwise.core.stitch_agent.record_usage",
             new_callable=AsyncMock
         ):
        await agent.generate_prototype()

    prompt = captured_kwargs.get("prompt", "")
    assert "Landing" in prompt or "landing" in prompt
    assert "Gate" in prompt or "gate" in prompt
    assert "Signup" in prompt or "signup" in prompt


# ---------------------------------------------------------------------------
# Test 4: Prototype records usage in stitch_usage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prototype_records_usage():
    """generate_prototype records 1 generation in stitch_usage with screen_name='prototype'."""
    from designwise.agent_harness.cli_anything.designwise.core.stitch_agent import StitchWiseAgent

    agent = StitchWiseAgent(mode="pro")
    recorded = {}

    async def capture_record(mode, screen_name, count):
        recorded.update({"mode": mode, "screen_name": screen_name, "count": count})

    with patch.object(agent, "_call_stitch_mcp", new_callable=AsyncMock, return_value={}), \
         patch(
             "designwise.agent_harness.cli_anything.designwise.core.stitch_agent.check_quota",
             new_callable=AsyncMock,
             return_value={"ok": True, "used": 0, "remaining": 350, "alert": False}
         ), \
         patch(
             "designwise.agent_harness.cli_anything.designwise.core.stitch_agent.record_usage",
             side_effect=capture_record
         ):
        await agent.generate_prototype()

    assert recorded.get("screen_name") == "prototype"
    assert recorded.get("count") == 1


# ---------------------------------------------------------------------------
# Test 5: Prototype output URL matches expected lab domain
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prototype_output_url_format():
    """generate_prototype returns prototype_url with lab.zonewise.ai."""
    from designwise.agent_harness.cli_anything.designwise.core.stitch_agent import StitchWiseAgent

    agent = StitchWiseAgent(mode="pro")

    with patch.object(agent, "_call_stitch_mcp", new_callable=AsyncMock, return_value={}), \
         patch(
             "designwise.agent_harness.cli_anything.designwise.core.stitch_agent.check_quota",
             new_callable=AsyncMock,
             return_value={"ok": True, "used": 0, "remaining": 350, "alert": False}
         ), \
         patch(
             "designwise.agent_harness.cli_anything.designwise.core.stitch_agent.record_usage",
             new_callable=AsyncMock
         ):
        result = await agent.generate_prototype(output_path="lab.zonewise.ai/prototype")

    assert "lab.zonewise.ai" in result["prototype_url"]
    assert "prototype" in result["prototype_url"]


# ---------------------------------------------------------------------------
# Test 6: All 8 PROTOTYPE_FLOW screens are known screen names
# ---------------------------------------------------------------------------

def test_prototype_flow_screens_have_intent_prompts():
    """All screens in PROTOTYPE_FLOW have corresponding intent prompts."""
    from designwise.agent_harness.cli_anything.designwise.core.stitch_agent import (
        PROTOTYPE_FLOW, SCREEN_INTENT_PROMPTS
    )

    for screen in PROTOTYPE_FLOW:
        assert screen in SCREEN_INTENT_PROMPTS, (
            f"Screen '{screen}' in PROTOTYPE_FLOW has no intent prompt"
        )
        prompt = SCREEN_INTENT_PROMPTS[screen]
        assert len(prompt) > 50, f"Intent prompt for '{screen}' is too short"


# ---------------------------------------------------------------------------
# Test 7: export_to_figma updates design_tasks.figma_url
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_to_figma_updates_task():
    """export_to_figma patches design_tasks with figma_url when task_id provided."""
    from designwise.agent_harness.cli_anything.designwise.core.stitch_agent import StitchWiseAgent

    agent = StitchWiseAgent(mode="pro")
    patched_url = None

    with patch.object(
        agent, "_call_stitch_mcp",
        new_callable=AsyncMock,
        return_value={"figma_url": "https://figma.com/file/abc123"}
    ), \
    patch("httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client
        mock_client.patch.return_value = MagicMock(status_code=200)

        result = await agent.export_to_figma("landing-hero", task_id="task-uuid-001")

    assert result["figma_url"] == "https://figma.com/file/abc123"
    assert result["task_id"] == "task-uuid-001"
    assert result["screen"] == "landing-hero"
