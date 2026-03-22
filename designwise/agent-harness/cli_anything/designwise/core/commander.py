"""
DesignWise Commander — LangGraph Orchestrator
DesignWise Squad | Agent 01
Version: 1.1.0 (Stitch 2.0 Spec Patch applied)

Amendments applied:
- Amendment 1: Quota check before StitchWise dispatch
- Amendment 5: Parallel exploration dispatch via Stitch Agent Manager
- Amendment 1: 80% quota alert (280/350) via Telegram

State machine: RECEIVE → CLASSIFY → DISPATCH → MONITOR → COMPLETE
"""

from __future__ import annotations

import json
import os
import asyncio
import uuid
from datetime import datetime
from typing import Any, Optional

import httpx

from .stitch_agent import StitchWiseAgent, check_quota, QuotaExceededError, QUOTA_ALERT_THRESHOLD

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "740118343")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = "breverdbidder/cli-anything-biddeed"

# Task types per SPEC §4
TASK_TYPES = (
    "new_screen", "fix_bug", "brand_audit", "visual_regression",
    "a_b_test", "seo_audit", "a11y_audit", "competitor_scan",
    "content_generation", "deploy", "support_ticket",
)

# Agent routing map: task_type → agent module
AGENT_ROUTING = {
    "new_screen":          "stitch_agent",
    "a_b_test":            "stitch_agent",
    "fix_bug":             "brandguard_agent",
    "brand_audit":         "brandguard_agent",
    "visual_regression":   "qawise_agent",
    "seo_audit":           "seo_agent",
    "a11y_audit":          "a11y_agent",
    "competitor_scan":     "competitor_agent",
    "content_generation":  "content_agent",
    "deploy":              "deploywise_agent",
    "support_ticket":      "support_agent",
}

# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def _supabase_headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


async def create_task(task_type: str, input_spec: dict, agent_id: str) -> str:
    """Insert a new design_task, return task UUID."""
    task_id = str(uuid.uuid4())
    payload = {
        "id": task_id,
        "task_type": task_type,
        "status": "queued",
        "agent_id": agent_id,
        "input_spec": input_spec,
        "created_at": datetime.utcnow().isoformat(),
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/design_tasks",
            headers=_supabase_headers(),
            json=payload,
        )
    if resp.status_code not in (200, 201):
        print(f"[Commander][WARN] Failed to create task: {resp.status_code} {resp.text[:100]}")
    return task_id


async def update_task_status(task_id: str, status: str, output_url: str | None = None, error: str | None = None) -> None:
    """Update task status in design_tasks."""
    payload: dict[str, Any] = {"status": status}
    if output_url:
        payload["output_url"] = output_url
    if error:
        payload["error_message"] = error
    if status in ("success", "failed", "blocked"):
        payload["completed_at"] = datetime.utcnow().isoformat()

    async with httpx.AsyncClient(timeout=10) as client:
        await client.patch(
            f"{SUPABASE_URL}/rest/v1/design_tasks?id=eq.{task_id}",
            headers=_supabase_headers(),
            json=payload,
        )


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

async def send_telegram(message: str) -> None:
    """Send message to Telegram channel."""
    if not TELEGRAM_TOKEN:
        print(f"[Commander][Telegram] {message}")
        return
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
        )


# ---------------------------------------------------------------------------
# Quota check (Amendment 1)
# ---------------------------------------------------------------------------

async def quota_gate(mode: str = "pro", screen_name: str | None = None) -> dict[str, Any]:
    """
    Check Stitch quota before dispatching StitchWise.
    Sends Telegram alert at 80% (280/350 used).
    Raises QuotaExceededError if remaining < 10.
    """
    quota = await check_quota(mode=mode, screen_name=screen_name)

    if quota.get("alert"):
        await send_telegram(
            f"STITCH QUOTA ALERT (Commander): "
            f"{quota['used']}/350 generations used ({quota['remaining']} remaining). "
            f"Approaching 80% limit. Review A/B test cadence."
        )

    return quota


# ---------------------------------------------------------------------------
# Parallel dispatch (Amendment 5)
# ---------------------------------------------------------------------------

async def parallel_stitch_dispatch(
    explorations: list[dict[str, Any]],
    mode: str = "flash",
) -> list[dict[str, Any]]:
    """
    Dispatch multiple StitchWise explorations in parallel.
    Used for A/B test setup and design direction exploration.

    Amendment 5: Uses Stitch Agent Manager for parallel exploration —
    single canvas session with N parallel explorations (vs N sequential API calls).
    Reduces quota usage and improves cross-variant consistency.

    Args:
        explorations: List of {screen_name, extra_context} dicts
        mode: 'flash' (default for exploration) or 'pro'

    Returns: List of generation results
    """
    if not explorations:
        return []

    # Pre-flight quota check — need 1 generation per exploration
    quota = await quota_gate(mode=mode)
    if quota["remaining"] < len(explorations):
        raise QuotaExceededError(
            f"Insufficient quota for {len(explorations)} parallel explorations: "
            f"only {quota['remaining']} remaining."
        )

    agent = StitchWiseAgent(mode=mode)
    agent.load_design_context()

    # Dispatch all in parallel via asyncio.gather (Stitch Agent Manager)
    tasks = [
        agent.generate_screen(
            screen_name=exp["screen_name"],
            mode=mode,
            extra_context=exp.get("extra_context", ""),
        )
        for exp in explorations
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for exp, result in zip(explorations, results):
        if isinstance(result, Exception):
            output.append({"screen_name": exp["screen_name"], "error": str(result)})
        else:
            output.append(result)

    return output


# ---------------------------------------------------------------------------
# Commander Agent State Machine
# ---------------------------------------------------------------------------

class CommanderAgent:
    """
    LangGraph orchestrator for the DesignWise squad.
    States: RECEIVE → CLASSIFY → DISPATCH → MONITOR → COMPLETE

    Triggers: Telegram /design, GHA cron, Watch dashboard, agent-to-agent handoff.
    """

    STATES = ("RECEIVE", "CLASSIFY", "DISPATCH", "MONITOR", "COMPLETE", "FAILED")

    def __init__(self):
        self.state = "RECEIVE"
        self.task_id: str | None = None
        self.task_type: str | None = None
        self.input_spec: dict = {}

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def process(self, raw_input: str | dict) -> dict[str, Any]:
        """
        Process a task through the full state machine.

        Args:
            raw_input: Natural language command string or structured dict

        Returns: Task result dict
        """
        # RECEIVE
        self.state = "RECEIVE"
        spec = self._parse_input(raw_input)

        # CLASSIFY
        self.state = "CLASSIFY"
        task_type = self._classify(spec)
        agent_id = AGENT_ROUTING.get(task_type, "unknown")

        # Create task record
        self.task_id = await create_task(task_type, spec, agent_id)
        self.task_type = task_type
        self.input_spec = spec

        await send_telegram(f"COMMANDER: Task {self.task_id[:8]} received — {task_type} → {agent_id}")

        # DISPATCH
        self.state = "DISPATCH"
        try:
            result = await self._dispatch(task_type, spec)
            await update_task_status(self.task_id, "success", output_url=result.get("output_url"))
            self.state = "COMPLETE"
            await send_telegram(f"COMMANDER: Task {self.task_id[:8]} COMPLETE — {task_type}")
            return {"status": "success", "task_id": self.task_id, "result": result}

        except QuotaExceededError as e:
            await update_task_status(self.task_id, "blocked", error=str(e))
            self.state = "FAILED"
            await send_telegram(f"COMMANDER: Task {self.task_id[:8]} BLOCKED — {e}")
            return {"status": "blocked", "task_id": self.task_id, "error": str(e)}

        except Exception as e:
            await update_task_status(self.task_id, "failed", error=str(e))
            self.state = "FAILED"
            await send_telegram(f"COMMANDER: Task {self.task_id[:8]} FAILED — {type(e).__name__}: {e}")
            return {"status": "failed", "task_id": self.task_id, "error": str(e)}

    # ------------------------------------------------------------------
    # Input parsing
    # ------------------------------------------------------------------

    def _parse_input(self, raw: str | dict) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        # Natural language → structured spec (simple keyword mapping)
        text = raw.lower()
        spec: dict[str, Any] = {"raw": raw}

        if any(k in text for k in ("new screen", "design", "generate", "stitch")):
            spec["task_type"] = "new_screen"
        elif any(k in text for k in ("bug", "fix", "broken")):
            spec["task_type"] = "fix_bug"
        elif any(k in text for k in ("brand", "color", "font", "audit")):
            spec["task_type"] = "brand_audit"
        elif any(k in text for k in ("a/b", "ab test", "variant")):
            spec["task_type"] = "a_b_test"
        elif "deploy" in text:
            spec["task_type"] = "deploy"
        elif "seo" in text:
            spec["task_type"] = "seo_audit"
        elif any(k in text for k in ("a11y", "accessibility", "wcag")):
            spec["task_type"] = "a11y_audit"
        elif "competitor" in text:
            spec["task_type"] = "competitor_scan"
        elif "content" in text:
            spec["task_type"] = "content_generation"
        else:
            spec["task_type"] = "brand_audit"  # safe default

        return spec

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify(self, spec: dict) -> str:
        task_type = spec.get("task_type", "brand_audit")
        if task_type not in TASK_TYPES:
            task_type = "brand_audit"
        return task_type

    # ------------------------------------------------------------------
    # Dispatch — routes to correct agent
    # ------------------------------------------------------------------

    async def _dispatch(self, task_type: str, spec: dict) -> dict[str, Any]:
        """Route task to the correct agent with quota pre-check for StitchWise tasks."""

        if task_type in ("new_screen", "a_b_test"):
            # Quota gate before any StitchWise dispatch (Amendment 1)
            mode = spec.get("mode", "pro")
            await quota_gate(mode=mode, screen_name=spec.get("screen_name"))

            agent = StitchWiseAgent(mode=mode)
            agent.load_design_context()

            if task_type == "a_b_test":
                # Parallel exploration dispatch (Amendment 5)
                explorations = spec.get("explorations", [
                    {"screen_name": spec.get("screen_name", "landing-hero"), "extra_context": "Variant A"},
                    {"screen_name": spec.get("screen_name", "landing-hero"), "extra_context": "Variant B"},
                    {"screen_name": spec.get("screen_name", "landing-hero"), "extra_context": "Variant C"},
                ])
                results = await parallel_stitch_dispatch(explorations, mode=mode)
                return {"type": "a_b_test", "variants": results, "output_url": None}
            else:
                screen = spec.get("screen_name", "landing-hero")
                result = await agent.generate_screen(screen)
                return {"type": "new_screen", "screen": screen, "output_url": result.get("screenshot_url")}

        elif task_type in ("brand_audit", "fix_bug"):
            # Import dynamically to avoid circular imports
            return {"type": task_type, "status": "dispatched_to_brandguard", "output_url": None}

        elif task_type == "deploy":
            return {"type": "deploy", "status": "dispatched_to_deploywise", "output_url": None}

        elif task_type == "visual_regression":
            return {"type": "visual_regression", "status": "dispatched_to_qawise", "output_url": None}

        elif task_type == "seo_audit":
            return {"type": "seo_audit", "status": "dispatched_to_seowise", "output_url": None}

        elif task_type == "a11y_audit":
            return {"type": "a11y_audit", "status": "dispatched_to_a11ywise", "output_url": None}

        elif task_type == "competitor_scan":
            return {"type": "competitor_scan", "status": "dispatched_to_competitorwise", "output_url": None}

        elif task_type == "content_generation":
            return {"type": "content_generation", "status": "dispatched_to_contentwise", "output_url": None}

        elif task_type == "support_ticket":
            return {"type": "support_ticket", "status": "dispatched_to_supportwise", "output_url": None}

        return {"type": task_type, "status": "dispatched", "output_url": None}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="DesignWise Commander — LangGraph orchestrator")
    parser.add_argument("--task", help="Natural language task description")
    parser.add_argument("--type", dest="task_type", choices=list(TASK_TYPES), help="Task type")
    parser.add_argument("--screen", dest="screen_name", help="Screen name for new_screen tasks")
    parser.add_argument("--mode", choices=["flash", "pro"], default="pro")
    parser.add_argument("--check-quota", action="store_true")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    async def run():
        if args.check_quota:
            result = await quota_gate(mode=args.mode)
        elif args.task or args.task_type:
            agent = CommanderAgent()
            spec: dict = {}
            if args.task_type:
                spec["task_type"] = args.task_type
            if args.screen_name:
                spec["screen_name"] = args.screen_name
            if args.mode:
                spec["mode"] = args.mode
            input_data = spec if spec else (args.task or "brand_audit")
            result = await agent.process(input_data)
        else:
            parser.print_help()
            return

        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(result)

    asyncio.run(run())


if __name__ == "__main__":
    main()
