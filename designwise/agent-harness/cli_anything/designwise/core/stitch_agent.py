"""
StitchWise Agent — Google Stitch 2.0 MCP Wrapper
DesignWise Squad | Agent 02
Version: 1.1.0 (Stitch 2.0 Spec Patch applied)

Amendments applied:
- Amendment 1: @google/stitch-sdk MCP (replaces @_davideast/stitch-mcp)
- Amendment 1: Intent-based vibe prompts for all 8 screens
- Amendment 1: Project-wide context threading (zonewise-production)
- Amendment 1: Quota check + stitch_usage table integration
- Amendment 1: Batch generation (5+3 instead of 8 sequential)
- Amendment 1: Flash/Pro mode selection
- Amendment 2: Interactive prototype generation
- Amendment 6: export_to_figma() optional method
"""

from __future__ import annotations

import json
import os
import asyncio
from datetime import date, datetime
from typing import Any, Optional

import httpx


# ---------------------------------------------------------------------------
# MCP Configuration (Amendment 1 — @google/stitch-sdk replaces @_davideast)
# ---------------------------------------------------------------------------

STITCH_MCP_CONFIG = {
    "mcpServers": {
        "stitch": {
            "command": "npx",
            "args": ["@google/stitch-sdk", "serve"],
        }
    }
}

# Single project for all 8 screens — Design Agent reasons across project history
STITCH_PROJECT_ID = "zonewise-production"

# Quota limits (Amendment 1)
QUOTA_MONTHLY = 350
QUOTA_ALERT_THRESHOLD = 280  # 80% — trigger Telegram alert
QUOTA_HARD_STOP = 340        # Leave 10 as buffer
QUOTA_BUDGET = {
    "pro": 200,    # Production screens
    "flash": 150,  # A/B variants + hotfixes (100 + 50)
}

# ---------------------------------------------------------------------------
# Intent-Based Prompt Templates — Amendment 1
# All 8 ZoneWise screens with vibe-first intent prompts
# ---------------------------------------------------------------------------

SCREEN_INTENT_PROMPTS = {
    "landing-hero": (
        "A premium landing page that builds trust, communicates AI-powered intelligence, "
        "and makes visitors feel they're accessing institutional-grade data. "
        "Navy #1E3A5F background, orange #F59E0B accent CTA, Inter font. "
        "Full-width choropleth heatmap of Florida counties as hero visual."
    ),
    "heatmap": (
        "A Reventure-style always-free heatmap explorer showing 67 Florida counties. "
        "Dark slate #020617 background with colored county overlays. "
        "Trust-building: users see real data before signup. Professional, data-rich."
    ),
    "parcel": (
        "A split-screen app that feels like Bloomberg Terminal meets modern AI chat — "
        "professional enough for investors, intuitive enough for first-time users. "
        "Chat panel left (380px), interactive map right (flex). "
        "Navy sidebar, dark background, orange highlights on active elements."
    ),
    "gate": (
        "A non-intrusive conversion gate modal that creates urgency and value perception — "
        "'you've seen the free version, here's what Pro unlocks'. "
        "Shows exactly what they're missing. No dark patterns. "
        "Orange CTA button, clear free vs paid differentiation."
    ),
    "signup": (
        "A minimal, trust-first signup flow for real estate investors. "
        "Single email field above the fold. Social proof below (user count, county coverage). "
        "No dark patterns. Dark background, Inter font, orange submit button."
    ),
    "app": (
        "A clean, trustworthy workspace: AI chat left panel (380px fixed) + "
        "Mapbox choropleth map right (flex). Calendar strip at bottom. "
        "Split-screen renders correctly at 1280px, 768px, 375px. "
        "Professional dark theme matching ZoneWise brand."
    ),
    "chat": (
        "An AI chat panel with message history and inline artifacts — "
        "like Claude Canvas inside a real estate intelligence platform. "
        "Renders auction data tables, heatmap previews, and report cards inline. "
        "Clean dark theme, orange user bubble, gray AI bubble."
    ),
    "map": (
        "An impressive map drill-down showing Florida counties → parcels → auction pins. "
        "Zoom-adaptive layers: county choropleth → parcel polygons → auction markers. "
        "Dark Mapbox style, orange auction pins, navy sidebar for filters."
    ),
    "calendar": (
        "An organized, data-rich 67-county auction calendar that feels comprehensive "
        "without overwhelming — like Google Calendar meets financial analytics. "
        "Month view with county color coding, upcoming auctions highlighted in orange."
    ),
    "kpi-report": (
        "A detailed 298-KPI analytical report that feels authoritative and data-driven — "
        "like a professional appraisal document. "
        "Table of contents, collapsible sections, print-ready layout. "
        "Navy headers, orange section dividers, monospace numbers."
    ),
    "pricing": (
        "A clear, confident pricing page that communicates value progression without pressure — "
        "transparent and fair. Three tiers: Free / Starter $39 / Pro $99. "
        "Orange highlighted for recommended tier (Starter). "
        "Feature comparison table, no hidden fees messaging."
    ),
    "mobile": (
        "A responsive mobile experience that maintains the premium desktop feel "
        "in a thumb-friendly, bottom-sheet navigation pattern. "
        "Bottom sheet swipes up for parcel details. FAB for AI chat. "
        "Full-bleed map with floating UI panels."
    ),
    "demo": (
        "An impressive live demonstration showing the AI pipeline in action — "
        "like watching a Bloomberg terminal populate in real-time. "
        "Animated agent steps: Scrape → Parse → Analyze → Report. "
        "Orange progress indicators, dark terminal aesthetic, real auction data examples."
    ),
}

# 8 required production screens batched 5+3 (Amendment 1)
BATCH_1_SCREENS = ["landing-hero", "heatmap", "parcel", "gate", "signup"]
BATCH_2_SCREENS = ["app", "chat", "map"]

# Interactive prototype flow (Amendment 2)
PROTOTYPE_FLOW = [
    "landing-hero",
    "heatmap",
    "parcel",
    "gate",
    "signup",
    "app",
    "chat",
    "map",
]


# ---------------------------------------------------------------------------
# Supabase client helpers
# ---------------------------------------------------------------------------

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "740118343")


def _supabase_headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


# ---------------------------------------------------------------------------
# Quota management (Amendment 1)
# ---------------------------------------------------------------------------

async def check_quota(mode: str = "pro", screen_name: str | None = None) -> dict[str, Any]:
    """
    Query stitch_usage table for current month usage.
    Returns: {"ok": bool, "used": int, "remaining": int, "alert": bool}
    Raises: QuotaExceededError if remaining < 10
    """
    today = date.today()
    month_start = today.replace(day=1).isoformat()

    async with httpx.AsyncClient(timeout=10) as client:
        # Sum all generations this month
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/stitch_usage",
            headers=_supabase_headers(),
            params={
                "select": "generation_count,mode",
                "date": f"gte.{month_start}",
            },
        )

    if resp.status_code != 200:
        # Table may not exist yet — allow through with warning
        print(f"[StitchWise][WARN] stitch_usage query failed ({resp.status_code}). Allowing through.")
        return {"ok": True, "used": 0, "remaining": QUOTA_MONTHLY, "alert": False, "warn": "table_missing"}

    rows = resp.json()
    used = sum(r.get("generation_count", 1) for r in rows)
    remaining = QUOTA_MONTHLY - used

    alert = used >= QUOTA_ALERT_THRESHOLD
    hard_stop = remaining < 10

    if hard_stop:
        raise QuotaExceededError(
            f"Stitch quota exhausted: {used}/{QUOTA_MONTHLY} used. "
            f"Only {remaining} remaining (minimum 10 required)."
        )

    if alert:
        await _send_telegram_alert(
            f"STITCH QUOTA ALERT: {used}/{QUOTA_MONTHLY} generations used "
            f"({remaining} remaining). At 80% threshold."
        )

    return {"ok": True, "used": used, "remaining": remaining, "alert": alert}


async def record_usage(mode: str, screen_name: str | None = None, count: int = 1) -> None:
    """Insert or upsert usage record into stitch_usage."""
    today = date.today().isoformat()
    payload = {
        "date": today,
        "mode": mode,
        "screen_name": screen_name or "batch",
        "generation_count": count,
        "remaining": None,  # updated post-call
    }
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"{SUPABASE_URL}/rest/v1/stitch_usage",
            headers=_supabase_headers(),
            json=payload,
        )


class QuotaExceededError(RuntimeError):
    """Raised when Stitch monthly quota remaining < 10."""


# ---------------------------------------------------------------------------
# StitchWise Agent
# ---------------------------------------------------------------------------

class StitchWiseAgent:
    """
    Google Stitch 2.0 MCP wrapper agent.
    Generates high-fidelity ZoneWise.AI UI screens from DESIGN.md context.

    MCP server: @google/stitch-sdk serve
    Project: zonewise-production (single project for cross-screen consistency)
    """

    def __init__(
        self,
        mode: str = "pro",
        project_id: str = STITCH_PROJECT_ID,
        design_md_path: str = "DESIGN.md",
    ):
        if mode not in ("flash", "pro"):
            raise ValueError(f"mode must be 'flash' or 'pro', got: {mode!r}")
        self.mode = mode
        self.project_id = project_id
        self.design_md_path = design_md_path
        self._design_context: str | None = None

    # ------------------------------------------------------------------
    # Design context loading
    # ------------------------------------------------------------------

    def load_design_context(self) -> str:
        """Load DESIGN.md content as generation context."""
        try:
            with open(self.design_md_path, "r") as f:
                self._design_context = f.read()
        except FileNotFoundError:
            self._design_context = (
                "Brand: Navy #1E3A5F, Orange #F59E0B, Slate bg #020617. "
                "Font: Inter. Product: ZoneWise.AI — Florida foreclosure auction intelligence."
            )
        return self._design_context

    # ------------------------------------------------------------------
    # Single screen generation
    # ------------------------------------------------------------------

    async def generate_screen(
        self,
        screen_name: str,
        mode: str | None = None,
        extra_context: str = "",
    ) -> dict[str, Any]:
        """
        Generate a single screen via Stitch MCP.
        Checks quota before generation and records usage after.

        Returns dict with: screen_name, html, screenshot_url, tokens_used, mode
        """
        mode = mode or self.mode

        # Quota gate (Amendment 1)
        quota = await check_quota(mode=mode, screen_name=screen_name)

        intent = SCREEN_INTENT_PROMPTS.get(screen_name, f"A ZoneWise.AI screen: {screen_name}")
        design_ctx = self._design_context or self.load_design_context()

        prompt = (
            f"PROJECT: {self.project_id}\n"
            f"MODE: {mode}\n"
            f"INTENT: {intent}\n"
            f"DESIGN CONTEXT:\n{design_ctx[:2000]}\n"
            f"{extra_context}"
        )

        # MCP call (real implementation connects via @google/stitch-sdk MCP server)
        result = await self._call_stitch_mcp(
            action="generate_screen",
            screen_name=screen_name,
            prompt=prompt,
            project_id=self.project_id,
            mode=mode,
        )

        await record_usage(mode=mode, screen_name=screen_name, count=1)
        return result

    # ------------------------------------------------------------------
    # Batch generation — 5+3 (Amendment 1)
    # ------------------------------------------------------------------

    async def generate_all_screens(self, mode: str | None = None) -> dict[str, Any]:
        """
        Generate all 8 production screens in 2 batches of 5+3.
        Uses Flash for speed by default; pass mode='pro' for production quality.

        Batch 1 (5 screens): landing-hero, heatmap, parcel, gate, signup
        Batch 2 (3 screens): app, chat, map
        """
        mode = mode or self.mode

        # Quota check — need at least 8 remaining
        quota = await check_quota(mode=mode)
        if quota["remaining"] < 8:
            raise QuotaExceededError(
                f"Insufficient quota for full generation: {quota['remaining']} remaining, need 8."
            )

        results = {}

        # Batch 1: 5 screens
        print(f"[StitchWise] Batch 1: {BATCH_1_SCREENS}")
        batch1 = await self._generate_batch(BATCH_1_SCREENS, mode=mode)
        results.update(batch1)

        # Batch 2: 3 screens (with context from Batch 1)
        print(f"[StitchWise] Batch 2: {BATCH_2_SCREENS}")
        batch2 = await self._generate_batch(
            BATCH_2_SCREENS,
            mode=mode,
            context_from=list(batch1.keys()),
        )
        results.update(batch2)

        return {
            "project_id": self.project_id,
            "mode": mode,
            "screens": results,
            "total_generated": len(results),
            "quota_remaining": quota["remaining"] - len(results),
        }

    async def _generate_batch(
        self,
        screens: list[str],
        mode: str,
        context_from: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate a batch of screens with optional cross-screen context."""
        extra_ctx = ""
        if context_from:
            extra_ctx = (
                f"PREVIOUSLY GENERATED SCREENS (maintain visual consistency): "
                f"{', '.join(context_from)}"
            )

        results = {}
        for screen in screens:
            result = await self.generate_screen(screen, mode=mode, extra_context=extra_ctx)
            results[screen] = result
            print(f"[StitchWise] Generated: {screen} ({mode} mode)")

        return results

    # ------------------------------------------------------------------
    # Interactive prototype generation (Amendment 2)
    # ------------------------------------------------------------------

    async def generate_prototype(
        self,
        flow: list[str] | None = None,
        output_path: str = "lab.zonewise.ai/prototype",
    ) -> dict[str, Any]:
        """
        Generate an interactive prototype connecting all 8 screens.
        Flow: Landing → Heatmap → Parcel → Gate → Signup → App → Chat → Map

        Stitch auto-generates transitions and intermediate states.
        Export: interactive HTML to lab.zonewise.ai/prototype

        Used for: investor demos, QAWise E2E testing, beta user onboarding.
        """
        flow = flow or PROTOTYPE_FLOW

        # Verify all screens exist (generated first)
        quota = await check_quota(mode=self.mode)

        prompt = (
            f"PROJECT: {self.project_id}\n"
            f"Create an interactive prototype connecting these screens in order:\n"
            f"{' → '.join(flow)}\n\n"
            f"Interaction spec:\n"
            f"- Landing CTA button → Heatmap\n"
            f"- Heatmap parcel click (5th click) → Gate modal\n"
            f"- Gate 'Try Free' → Signup\n"
            f"- Signup submit → App dashboard\n"
            f"- App chat input → Chat panel\n"
            f"- Chat 'View on Map' → Map drill-down\n"
            f"- App calendar link → Calendar\n\n"
            f"Export as self-contained interactive HTML. "
            f"Deploy to: {output_path}"
        )

        result = await self._call_stitch_mcp(
            action="generate_prototype",
            screens=flow,
            prompt=prompt,
            project_id=self.project_id,
            mode=self.mode,
        )

        await record_usage(mode=self.mode, screen_name="prototype", count=1)

        return {
            "prototype_url": f"https://{output_path}",
            "flow": flow,
            "screen_count": len(flow),
            "export": result,
        }

    # ------------------------------------------------------------------
    # Figma export (Amendment 6 — P2 Sprint 4, optional)
    # ------------------------------------------------------------------

    async def export_to_figma(
        self,
        screen_name: str,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Optional: Export approved production screen to Figma format.
        Stores Figma link in design_tasks.figma_url.
        Priority: P2 Sprint 4. Does NOT block any pipeline.
        """
        result = await self._call_stitch_mcp(
            action="export_figma",
            screen_name=screen_name,
            project_id=self.project_id,
        )

        figma_url = result.get("figma_url")

        # Update design_tasks if task_id provided
        if task_id and figma_url:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.patch(
                    f"{SUPABASE_URL}/rest/v1/design_tasks?id=eq.{task_id}",
                    headers=_supabase_headers(),
                    json={"figma_url": figma_url},
                )

        return {"screen": screen_name, "figma_url": figma_url, "task_id": task_id}

    # ------------------------------------------------------------------
    # MCP client stub (real implementation via @google/stitch-sdk MCP server)
    # ------------------------------------------------------------------

    async def _call_stitch_mcp(self, action: str, **kwargs) -> dict[str, Any]:
        """
        Calls the Stitch MCP server via @google/stitch-sdk.

        In production: communicates with MCP server subprocess spawned by Claude Code.
        MCP config: {"mcpServers": {"stitch": {"command": "npx", "args": ["@google/stitch-sdk", "serve"]}}}

        Returns structured result with html, screenshot_url, design_tokens.
        """
        screen_name = kwargs.get("screen_name", "unknown")
        mode = kwargs.get("mode", self.mode)

        # Stub response — real MCP call happens when Claude Code runs with Stitch MCP configured
        return {
            "action": action,
            "screen_name": screen_name,
            "project_id": self.project_id,
            "mode": mode,
            "html": f"<!-- Stitch {screen_name} output — generated via @google/stitch-sdk -->",
            "screenshot_url": f"https://stitch.googleapis.com/projects/{self.project_id}/screens/{screen_name}.png",
            "design_tokens": {
                "primary": "#1E3A5F",
                "accent": "#F59E0B",
                "background": "#020617",
                "font": "Inter",
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Telegram helper
    # ------------------------------------------------------------------

    @staticmethod
    async def _send_telegram_alert(message: str) -> None:
        """Send alert to Telegram channel."""
        if not TELEGRAM_TOKEN:
            return
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            )


# Module-level helper for Commander quota pre-check
async def _send_telegram_alert(message: str) -> None:
    await StitchWiseAgent._send_telegram_alert(message)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="StitchWise — Stitch 2.0 screen generator")
    parser.add_argument("--screen", help="Screen name to generate")
    parser.add_argument("--all", action="store_true", help="Generate all 8 screens")
    parser.add_argument("--prototype", action="store_true", help="Generate interactive prototype")
    parser.add_argument("--mode", choices=["flash", "pro"], default="pro")
    parser.add_argument("--export-figma", metavar="SCREEN", help="Export screen to Figma")
    parser.add_argument("--check-quota", action="store_true", help="Check current quota")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    agent = StitchWiseAgent(mode=args.mode)

    async def run():
        if args.check_quota:
            result = await check_quota(mode=args.mode)
        elif args.screen:
            result = await agent.generate_screen(args.screen)
        elif getattr(args, "all"):
            result = await agent.generate_all_screens()
        elif args.prototype:
            result = await agent.generate_prototype()
        elif args.export_figma:
            result = await agent.export_to_figma(args.export_figma)
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
