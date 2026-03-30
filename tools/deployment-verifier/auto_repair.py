#!/usr/bin/env python3
"""
auto_repair.py — Deployment Auto-Repair Engine
Issue: breverdbidder/cli-anything-biddeed#101

On deployment failure:
1. Calls Gemini Flash to generate fix suggestions
2. Auto-creates a SUMMIT GitHub issue for known patterns
3. Logs incident to Supabase deployment_incidents table

Usage:
    python auto_repair.py --signals signals.json
    python auto_repair.py --signals signals.json --create-issue --repo breverdbidder/cli-anything-biddeed
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Optional

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
GITHUB_TOKEN = os.getenv("GH_PAT", os.getenv("GH_TOKEN", ""))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Gemini Flash — free tier, used for fix suggestion generation
GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


# ── Auto-Repairable Pattern Map ───────────────────────────────────────────────
# Maps signal_type → (issue_title_template, known_fix_hint)

KNOWN_PATTERNS: dict[str, dict[str, str]] = {
    "build_error": {
        "title": "SUMMIT P0: Vercel build error — {url}",
        "hint": (
            "Check Vercel deployment logs for the failing build. "
            "Common causes: missing env vars, import errors, getServerSideProps throwing. "
            "Run `vercel logs --follow` or check the Vercel dashboard for the error trace."
        ),
        "label": "p0,deployment,auto-generated",
    },
    "http_error": {
        "title": "SUMMIT P1: HTTP {http_code} on {url}",
        "hint": (
            "Investigate server-side error. For 503: check if the service is running "
            "(`docker ps` on Hetzner). For 500: check application logs. "
            "For 502: check reverse proxy / nginx config."
        ),
        "label": "p1,deployment,auto-generated",
    },
    "hydration_failure": {
        "title": "SUMMIT P0: Next.js hydration failure on {url}",
        "hint": (
            "Missing __NEXT_DATA__ means the Next.js app failed to SSR. "
            "Check for: 1) build output errors, 2) env vars not set, "
            "3) getStaticProps/getServerSideProps returning null unexpectedly."
        ),
        "label": "p0,deployment,auto-generated",
    },
    "playwright_error": {
        "title": "SUMMIT P1: Deployment verification error — {url}",
        "hint": (
            "Playwright failed to reach or render the page. "
            "Check: 1) Is the URL reachable? 2) Are there TLS/DNS issues? "
            "3) Did a deploy just happen that broke routing?"
        ),
        "label": "p1,deployment,auto-generated",
    },
}


# ── Data Models ───────────────────────────────────────────────────────────────

@dataclass
class RepairAction:
    signal_type: str
    url: str
    suggestion: str          # LLM-generated or rule-based fix suggestion
    issue_url: Optional[str] = None   # GitHub issue URL if created
    persisted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "url": self.url,
            "suggestion": self.suggestion,
            "issue_url": self.issue_url,
            "persisted": self.persisted,
        }


# ── Gemini Flash Fix Generator ────────────────────────────────────────────────

async def generate_fix_suggestion(signal: dict, api_key: str) -> str:
    """Call Gemini Flash to generate a fix suggestion for a deployment signal."""
    if not api_key:
        # Fall back to rule-based hint
        pattern = KNOWN_PATTERNS.get(signal.get("signal_type", ""), {})
        return pattern.get("hint", "No fix suggestion available — set GEMINI_API_KEY for AI-powered suggestions.")

    prompt = (
        "You are a deployment engineer for a Next.js + Vercel + Supabase application called ZoneWise.AI "
        "(Florida foreclosure data platform). A deployment verification check just failed.\n\n"
        f"Signal type: {signal.get('signal_type')}\n"
        f"URL: {signal.get('url')}\n"
        f"Severity: {signal.get('severity')}\n"
        f"Message: {signal.get('message')}\n"
        f"Evidence: {signal.get('evidence')}\n\n"
        "Provide a concise (3-5 bullet points) diagnosis + fix plan. "
        "Focus on actionable steps, not theory. Be specific to the stack (Next.js, Vercel, Supabase, Hetzner, Docker)."
    )

    try:
        import httpx
        url = GEMINI_ENDPOINT.format(model=GEMINI_MODEL) + f"?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 512, "temperature": 0.3},
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:
        # Non-fatal — fall back to rule hint
        pattern = KNOWN_PATTERNS.get(signal.get("signal_type", ""), {})
        fallback = pattern.get("hint", "Check deployment logs.")
        return f"{fallback}\n\n(Gemini suggestion failed: {exc})"


# ── GitHub Issue Creator ──────────────────────────────────────────────────────

async def create_github_issue(
    signal: dict,
    suggestion: str,
    repo: str,
    token: str,
) -> Optional[str]:
    """Create a SUMMIT GitHub issue for a critical deployment failure. Returns issue URL."""
    if not token:
        print("[issue] GH_PAT not set — skipping issue creation", file=sys.stderr)
        return None

    pattern = KNOWN_PATTERNS.get(signal.get("signal_type", ""), {})
    if not pattern:
        print(f"[issue] No known pattern for {signal.get('signal_type')} — skipping issue", file=sys.stderr)
        return None

    title = pattern["title"].format(
        url=signal.get("url", "unknown"),
        http_code=signal.get("http_code", ""),
    )
    labels = pattern.get("label", "deployment,auto-generated").split(",")

    body = f"""## Deployment Failure Detected

**URL:** {signal.get('url')}
**Signal:** {signal.get('signal_type')}
**Severity:** {signal.get('severity')}
**Evidence:** {signal.get('evidence')}

## Fix Suggestion

{suggestion}

## Context

- Detected by: `tools/deployment-verifier/auto_repair.py`
- Auto-generated by deployment-verifier (Issue #101)
- Verify manually: `python tools/deployment-verifier/verify_deployment.py --url {signal.get('url')}`

## Acceptance Criteria
- [ ] Root cause identified
- [ ] Fix deployed
- [ ] `verify_deployment.py --url {signal.get('url')}` returns all checks ✅
- [ ] `deployment_checks` Supabase table shows `status=pass`
"""

    try:
        import httpx
        owner, repo_name = repo.split("/", 1)
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://api.github.com/repos/{owner}/{repo_name}/issues",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={
                    "title": title,
                    "body": body,
                    "labels": labels,
                },
            )
            resp.raise_for_status()
            issue_url = resp.json().get("html_url", "")
            print(f"[issue] Created: {issue_url}")
            return issue_url
    except Exception as exc:
        print(f"[issue] GitHub issue creation failed: {exc}", file=sys.stderr)
        return None


# ── Supabase Incident Logger ──────────────────────────────────────────────────

async def log_incident(signal: dict, suggestion: str, issue_url: Optional[str]) -> bool:
    """Log incident to deployment_incidents table."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    try:
        import httpx
        import datetime
        payload = {
            "url": signal.get("url"),
            "signal_type": signal.get("signal_type"),
            "severity": signal.get("severity"),
            "message": signal.get("message"),
            "evidence": signal.get("evidence"),
            "suggestion": suggestion[:2000],
            "issue_url": issue_url,
            "occurred_at": datetime.datetime.utcnow().isoformat() + "Z",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/deployment_incidents",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json=payload,
            )
            resp.raise_for_status()
            return True
    except Exception as exc:
        print(f"[log] Supabase log failed: {exc}", file=sys.stderr)
        return False


# ── Main Repair Pipeline ──────────────────────────────────────────────────────

async def repair(
    signals: list[dict],
    repo: str = "breverdbidder/cli-anything-biddeed",
    create_issue: bool = True,
) -> list[RepairAction]:
    """Run full repair pipeline for a list of signals."""
    actions: list[RepairAction] = []
    critical = [s for s in signals if s.get("severity") == "critical"]

    if not critical:
        print("[repair] No critical signals — nothing to repair")
        return actions

    for signal in critical:
        print(f"\n[repair] Processing: {signal.get('signal_type')} on {signal.get('url')}")

        # Step 1: Generate fix suggestion (Gemini Flash)
        suggestion = await generate_fix_suggestion(signal, GEMINI_API_KEY)
        print(f"[repair] Suggestion: {suggestion[:100]}...")

        # Step 2: Create GitHub issue if warranted
        issue_url: Optional[str] = None
        if create_issue and GITHUB_TOKEN:
            issue_url = await create_github_issue(signal, suggestion, repo, GITHUB_TOKEN)

        # Step 3: Log to Supabase
        persisted = await log_incident(signal, suggestion, issue_url)

        actions.append(RepairAction(
            signal_type=signal.get("signal_type", "unknown"),
            url=signal.get("url", ""),
            suggestion=suggestion,
            issue_url=issue_url,
            persisted=persisted,
        ))

    return actions


# ── CLI ───────────────────────────────────────────────────────────────────────

async def main() -> int:
    parser = argparse.ArgumentParser(description="Deployment auto-repair engine")
    parser.add_argument("--signals", required=True, help="JSON file from signal_detector.py")
    parser.add_argument("--repo", default="breverdbidder/cli-anything-biddeed", help="GitHub repo (owner/name)")
    parser.add_argument("--create-issue", action="store_true", help="Create GitHub issue on critical signal")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    with open(args.signals) as f:
        signals = json.load(f)

    actions = await repair(signals, repo=args.repo, create_issue=args.create_issue)

    if args.json:
        print(json.dumps([a.to_dict() for a in actions], indent=2))
    else:
        for a in actions:
            icon = "✅" if a.issue_url else "⚠️"
            print(f"\n{icon} {a.signal_type} — {a.url}")
            print(f"  Suggestion: {a.suggestion[:200]}...")
            if a.issue_url:
                print(f"  Issue: {a.issue_url}")
            print(f"  Persisted: {a.persisted}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
