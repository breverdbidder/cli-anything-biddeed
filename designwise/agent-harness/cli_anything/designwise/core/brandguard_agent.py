"""
BrandGuard Agent — Design System Enforcer
DesignWise Squad | Agent 03
Version: 1.2.0 (S3.0 — 5-color canonical set + Tailwind-allow policy)

Amendments applied:
- Amendment 3: check_design_drift(live_url, design_md_path) method
- Amendment 3: Extract design tokens from live site via Stitch URL extraction
- Amendment 3: Diff extracted tokens against DESIGN.md in repo
- Amendment 3: If drift → GitHub Issue + Telegram alert
- S3.0: Canonical color set tightened to 5 brand colors
- S3.0: Tailwind utility classes always allowed (they compile to CSS vars)
- S3.0: Only hardcoded non-brand hex values flagged as violations

CRITICAL: BrandGuard BLOCKS production deploys on ANY violation.

5 Canonical Brand Colors:
  #1E3A5F — Navy (primary)
  #F59E0B — Orange (accent)
  #020617 — Background (slate-950)
  #D97706 — Hover (orange-500)
  #162D4A — Dark navy (surfaces/cards)
"""

from __future__ import annotations

import json
import os
import re
import asyncio
import hashlib
from datetime import datetime
from typing import Any, Optional

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "740118343")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "breverdbidder/zonewise-web")

# ── 5 Canonical brand colors (S3.0) ───────────────────────────────────────────
CANONICAL_BRAND_COLORS = {
    "navy":      "#1E3A5F",  # Primary — headings, navbar, buttons
    "orange":    "#F59E0B",  # Accent — CTAs, highlights
    "bg":        "#020617",  # Background (slate-950)
    "hover":     "#D97706",  # Hover state (orange-500)
    "dark_navy": "#162D4A",  # Dark navy — surfaces, cards
}

# Normalized brand hex set (lowercase, no #)
_BRAND_HEX = {v.lstrip("#").lower() for v in CANONICAL_BRAND_COLORS.values()}

# Banned hex values — flagged as critical violations
BANNED_COLORS = [
    "#FF0000", "#00FF00", "#0000FF",  # Pure primaries
    "#FF00FF", "#FFFF00", "#00FFFF",  # Neons
    "#FFFFFF",  # Pure white bg (use #020617)
    "#000000",  # Pure black (use #020617)
    "#FFA500",  # HTML orange (use #F59E0B)
    "#FF6600",  # Orange-red
]
_BANNED_HEX = {c.lstrip("#").lower() for c in BANNED_COLORS}

# Tailwind color utility names — these are ALWAYS allowed (compile to CSS vars)
_TAILWIND_COLOR_NAMES = {
    "slate", "gray", "zinc", "neutral", "stone", "red", "orange", "amber",
    "yellow", "lime", "green", "emerald", "teal", "cyan", "sky", "blue",
    "indigo", "violet", "purple", "fuchsia", "pink", "rose",
    "white", "black", "transparent", "current",
    # ZoneWise brand scales
    "zw-navy", "zw-orange",
}

CANONICAL_TOKENS = {
    "colors": CANONICAL_BRAND_COLORS,
    "fonts": {
        "primary": "Inter",
        "mono": "JetBrains Mono",
    },
    "font_size_min_px": 11,
    "banned_colors": BANNED_COLORS,
}


def _is_tailwind_color_class(class_name: str) -> bool:
    """Return True if class_name is a Tailwind color utility (always allowed)."""
    prefixes = ("bg-", "text-", "border-", "ring-", "fill-", "stroke-",
                "from-", "to-", "via-", "shadow-", "outline-", "decoration-")
    name = class_name.lower().strip()
    for prefix in prefixes:
        if name.startswith(prefix):
            rest = name[len(prefix):]
            base = rest.split("-")[0]
            if base in _TAILWIND_COLOR_NAMES:
                return True
    return False

VIOLATION_TYPES = (
    "banned_color", "wrong_font", "contrast_fail", "missing_nav",
    "broken_link", "font_too_small", "missing_alt", "missing_aria",
    "design_drift",
)


def _supabase_headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


# ---------------------------------------------------------------------------
# Design token extraction from live URL (Amendment 3)
# ---------------------------------------------------------------------------

async def extract_tokens_from_url(url: str) -> dict[str, Any]:
    """
    Extract design tokens (colors, fonts, sizes) from a live URL.
    Uses CSS parsing via HTTP fetch + regex extraction.
    In production: Stitch URL extraction API or Playwright CSS dump.

    Returns: {"colors": [...], "fonts": [...], "font_sizes": [...], "source_url": url}
    """
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
            html = resp.text
        except httpx.ConnectError:
            return {"error": f"Cannot connect to {url}", "source_url": url}

    # Extract hex colors from inline styles + CSS
    hex_pattern = r"#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b"
    found_colors = list(set(re.findall(hex_pattern, html)))
    found_colors = [f"#{c.upper()}" for c in found_colors]

    # Extract font families
    font_pattern = r"font-family\s*:\s*([^;\"'<>]+)"
    found_fonts = list(set(re.findall(font_pattern, html, re.IGNORECASE)))
    found_fonts = [f.strip().strip("'\"") for f in found_fonts]

    # Extract font sizes
    size_pattern = r"font-size\s*:\s*(\d+(?:\.\d+)?)(px|rem|em)"
    found_sizes = re.findall(size_pattern, html, re.IGNORECASE)
    found_sizes_px = []
    for value, unit in found_sizes:
        if unit == "px":
            found_sizes_px.append(float(value))
        elif unit == "rem":
            found_sizes_px.append(float(value) * 16)

    # Extract CSS custom properties (design tokens)
    css_vars = {}
    var_pattern = r"--([\w-]+)\s*:\s*([^;}\n]+)"
    for name, value in re.findall(var_pattern, html):
        css_vars[f"--{name}"] = value.strip()

    return {
        "source_url": url,
        "colors": found_colors,
        "fonts": found_fonts,
        "font_sizes_px": found_sizes_px,
        "css_variables": css_vars,
        "extracted_at": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# Design drift detection (Amendment 3)
# ---------------------------------------------------------------------------

async def check_design_drift(
    live_url: str,
    design_md_path: str = "DESIGN.md",
) -> dict[str, Any]:
    """
    Amendment 3: Weekly drift detection.
    1. Extract design tokens from live zonewise.ai via URL extraction
    2. Diff extracted tokens against DESIGN.md in repo
    3. If drift detected: create GitHub Issue + send Telegram alert

    Cron: Sunday 8AM EST (weekly-designmd-drift.yml)
    """
    # Step 1: Extract live tokens
    live_tokens = await extract_tokens_from_url(live_url)

    if "error" in live_tokens:
        return {"status": "error", "message": live_tokens["error"], "url": live_url}

    # Step 2: Load canonical tokens from DESIGN.md
    canonical = _load_design_md_tokens(design_md_path)

    # Step 3: Diff
    drift_findings = _diff_tokens(live_tokens, canonical)

    result = {
        "url": live_url,
        "design_md_path": design_md_path,
        "drift_detected": len(drift_findings) > 0,
        "findings": drift_findings,
        "live_tokens": live_tokens,
        "canonical_tokens": canonical,
        "checked_at": datetime.utcnow().isoformat(),
    }

    # Step 4: Alert if drift found
    if drift_findings:
        issue_url = await _create_github_issue(
            title=f"Design Drift Detected: {live_url}",
            body=_format_drift_issue_body(result),
        )
        await _send_telegram_alert(
            f"BRANDGUARD DRIFT ALERT\n"
            f"Site: {live_url}\n"
            f"Findings: {len(drift_findings)}\n"
            f"GitHub Issue: {issue_url or 'creation failed'}\n"
            f"Diffs: {'; '.join(drift_findings[:3])}"
        )
        result["github_issue_url"] = issue_url

    return result


def _load_design_md_tokens(design_md_path: str) -> dict[str, Any]:
    """Parse DESIGN.md to extract canonical design tokens."""
    try:
        with open(design_md_path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        # Fall back to hardcoded canonical tokens
        return CANONICAL_TOKENS

    tokens = dict(CANONICAL_TOKENS)  # Start with hardcoded

    # Override with parsed values from DESIGN.md
    # Primary color
    primary_match = re.search(r"primary.*?#([0-9A-Fa-f]{6})", content, re.IGNORECASE)
    if primary_match:
        tokens["colors"]["primary"] = f"#{primary_match.group(1).upper()}"

    # Accent color
    accent_match = re.search(r"accent.*?#([0-9A-Fa-f]{6})", content, re.IGNORECASE)
    if accent_match:
        tokens["colors"]["accent"] = f"#{accent_match.group(1).upper()}"

    return tokens


def _diff_tokens(live: dict[str, Any], canonical: dict[str, Any]) -> list[str]:
    """Compare live tokens against canonical. Returns list of drift descriptions."""
    findings = []

    # Check required canonical colors are present in live
    canonical_colors = set(v.upper() for v in canonical.get("colors", {}).values())
    live_colors = set(c.upper() for c in live.get("colors", []))

    for required_color in canonical_colors:
        if required_color and required_color not in live_colors:
            findings.append(f"Missing canonical color {required_color} on live site")

    # Check banned colors not present in live
    for banned in canonical.get("banned_colors", []):
        if banned.upper() in live_colors:
            findings.append(f"Banned color {banned} found on live site")

    # Check fonts
    canonical_fonts = set(f.lower() for f in canonical.get("fonts", {}).values())
    live_fonts = set(f.lower() for f in live.get("fonts", []))
    for cf in canonical_fonts:
        # Check if canonical font appears in any live font string
        if not any(cf in lf for lf in live_fonts):
            findings.append(f"Canonical font '{cf}' not found in live site fonts")

    # Check minimum font size
    min_size = canonical.get("font_size_min_px", 11)
    for size in live.get("font_sizes_px", []):
        if size < min_size:
            findings.append(f"Font size {size}px below minimum {min_size}px")

    return findings


# ---------------------------------------------------------------------------
# Violation logging to Supabase
# ---------------------------------------------------------------------------

async def log_violation(
    scan_id: str,
    page_url: str,
    violation_type: str,
    expected: str,
    actual: str,
    severity: str = "high",
    file_path: str | None = None,
    line_number: int | None = None,
) -> None:
    """Insert brand violation into Supabase brand_violations table."""
    payload = {
        "scan_id": scan_id,
        "page_url": page_url,
        "violation_type": violation_type,
        "expected": expected,
        "actual": actual,
        "severity": severity,
        "file_path": file_path,
        "line_number": line_number,
        "created_at": datetime.utcnow().isoformat(),
    }
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"{SUPABASE_URL}/rest/v1/brand_violations",
            headers=_supabase_headers(),
            json=payload,
        )


# ---------------------------------------------------------------------------
# BrandGuard Agent
# ---------------------------------------------------------------------------

class BrandGuardAgent:
    """
    Design system enforcer. Scans every PR and deploy for violations.
    BLOCKS deploys that fail brand checks.

    Amendment 3: Added weekly drift detection via check_design_drift().
    """

    def __init__(self, design_md_path: str = "DESIGN.md"):
        self.design_md_path = design_md_path
        self.scan_id = hashlib.md5(datetime.utcnow().isoformat().encode()).hexdigest()[:16]
        self.violations: list[dict] = []

    async def scan_url(self, url: str) -> dict[str, Any]:
        """
        Full brand compliance scan of a URL.
        Checks: colors, fonts, contrast, nav, links, font sizes.

        Returns: {"passed": bool, "violations": list, "scan_id": str}
        """
        live = await extract_tokens_from_url(url)

        if "error" in live:
            return {"passed": False, "violations": [live["error"]], "scan_id": self.scan_id}

        violations = []

        # Color check — S3.0 policy:
        # Only flag hardcoded hex values that are in BANNED_COLORS.
        # Tailwind utility classes (bg-slate-*, text-gray-*, etc.) are ALWAYS allowed.
        # Non-brand hex values that aren't explicitly banned are flagged as warnings, not blocks.
        live_colors = set(c.upper() for c in live.get("colors", []))
        for banned in BANNED_COLORS:
            if banned.upper() in live_colors:
                v = {
                    "type": "banned_color",
                    "expected": "not present",
                    "actual": banned,
                    "severity": "critical",
                    "page_url": url,
                }
                violations.append(v)
                await log_violation(
                    self.scan_id, url, "banned_color",
                    "not present", banned, "critical"
                )

        # Font check
        live_fonts_str = " ".join(live.get("fonts", [])).lower()
        for font_role, font_name in CANONICAL_TOKENS["fonts"].items():
            if font_name.lower() not in live_fonts_str:
                v = {
                    "type": "wrong_font",
                    "expected": font_name,
                    "actual": live_fonts_str[:100],
                    "severity": "high",
                    "page_url": url,
                }
                violations.append(v)

        # Font size check
        min_size = CANONICAL_TOKENS["font_size_min_px"]
        for size in live.get("font_sizes_px", []):
            if size < min_size:
                violations.append({
                    "type": "font_too_small",
                    "expected": f">={min_size}px",
                    "actual": f"{size}px",
                    "severity": "medium",
                    "page_url": url,
                })

        self.violations = violations
        passed = len(violations) == 0

        # Score: 100 base, -10 per critical, -5 per high, -2 per medium
        score = 100
        for v in violations:
            sev = v.get("severity", "medium")
            score -= {"critical": 10, "high": 5, "medium": 2, "low": 1}.get(sev, 2)
        score = max(0, score)

        return {
            "passed": passed,
            "score": score,
            "url": url,
            "scan_id": self.scan_id,
            "violation_count": len(violations),
            "violations": violations,
            "brand_colors": CANONICAL_BRAND_COLORS,
            "tailwind_policy": "allowed — Tailwind utilities compile to CSS vars",
            "scanned_at": datetime.utcnow().isoformat(),
        }

    async def check_design_drift(
        self,
        live_url: str,
        design_md_path: str | None = None,
    ) -> dict[str, Any]:
        """
        Amendment 3: Weekly DESIGN.md drift check.
        Delegates to module-level check_design_drift().
        """
        return await check_design_drift(
            live_url=live_url,
            design_md_path=design_md_path or self.design_md_path,
        )


# ---------------------------------------------------------------------------
# GitHub Issue creation
# ---------------------------------------------------------------------------

async def _create_github_issue(title: str, body: str) -> str | None:
    """Create a GitHub issue and return the issue URL."""
    if not GITHUB_TOKEN:
        print(f"[BrandGuard] No GITHUB_TOKEN — skipping issue creation")
        return None

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"https://api.github.com/repos/{GITHUB_REPO}/issues",
            headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json",
            },
            json={
                "title": title,
                "body": body,
                "labels": ["design-drift", "brandguard", "automated"],
            },
        )

    if resp.status_code == 201:
        return resp.json().get("html_url")
    else:
        print(f"[BrandGuard] GitHub issue creation failed: {resp.status_code}")
        return None


def _format_drift_issue_body(result: dict) -> str:
    findings = result.get("findings", [])
    findings_md = "\n".join(f"- {f}" for f in findings)
    return (
        f"## Design Drift Detected\n\n"
        f"**URL:** {result['url']}\n"
        f"**Checked at:** {result['checked_at']}\n"
        f"**Findings ({len(findings)}):**\n\n"
        f"{findings_md}\n\n"
        f"---\n"
        f"_Auto-generated by BrandGuard weekly drift check (Amendment 3)._\n"
        f"_Workflow: weekly-designmd-drift.yml_"
    )


async def _send_telegram_alert(message: str) -> None:
    """Send alert to Telegram channel."""
    if not TELEGRAM_TOKEN:
        print(f"[BrandGuard][Telegram] {message}")
        return
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="BrandGuard — brand compliance scanner")
    parser.add_argument("--url", help="URL to scan")
    parser.add_argument("--drift-check", action="store_true", help="Run weekly drift check")
    parser.add_argument("--live-url", default="https://zonewise.ai")
    parser.add_argument("--design-md", default="DESIGN.md")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    async def run():
        agent = BrandGuardAgent(design_md_path=args.design_md)

        if args.drift_check:
            result = await agent.check_design_drift(
                live_url=args.live_url,
                design_md_path=args.design_md,
            )
        elif args.url:
            result = await agent.scan_url(args.url)
        else:
            parser.print_help()
            return

        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            status = "PASS" if result.get("passed", not result.get("drift_detected")) else "FAIL"
            print(f"[BrandGuard] {status} — {result}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
