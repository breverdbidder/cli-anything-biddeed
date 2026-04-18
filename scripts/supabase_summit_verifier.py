#!/usr/bin/env python3
"""
Supabase SUMMIT Verifier — closes the 'self-attested evidence keys' loophole
in trg_prevent_ghost_success.

Problem
-------
The schema trigger trg_prevent_ghost_success requires evidence keys to be
present on any state=verified transition. But the *contents* of those keys
are self-attested by whoever wrote them. The canonical
scripts/spec_fulfillment_verifier.py closes this by checking claims against
real artifacts — but it operates on GitHub issues, and most SUMMITs are
created directly in Supabase without filing an issue.

This wrapper bridges that gap: iterates verified Supabase SUMMITs, extracts
claims from summit_body + delivery_proof, runs each claim through the same
verify_* functions as the canonical verifier, aggregates verdicts, persists
to summit_verifier_runs, and (critically) flips state=verified → failed
when the overall verdict is GHA-GREEN-NOT-DELIVERED.

Usage
-----
    python supabase_summit_verifier.py --session chat-2026-04-18-autonomous-5repo
    python supabase_summit_verifier.py --summit-id <uuid>
    python supabase_summit_verifier.py --all-verified-today
    python supabase_summit_verifier.py --auto-patrol  # cron mode
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GH_API = "https://api.github.com"
GH_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GH_PAT", "")
SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")
TG_TOKEN = os.environ.get("BIDDEED_BOT_TOKEN", "")
TG_CHAT = os.environ.get("BIDDEED_BOT_CHAT_ID", "740118343")
TIMEOUT = 20.0

# Verdicts — IDENTICAL to spec_fulfillment_verifier.py
DELIVERED = "DELIVERED-VERIFIED"
NOT_DELIVERED = "GHA-GREEN-NOT-DELIVERED"
DISPATCHED_ONLY = "DISPATCHED-ONLY"
BLOCKED_HONEST = "BLOCKED-HONEST"
MIXED = "MIXED"

# Default repo for file/PR/commit lookups when not otherwise specified
DEFAULT_REPO_POOL = [
    "breverdbidder/cli-anything-biddeed",
    "breverdbidder/zonewise-web",
    "breverdbidder/everest-content",
]


def _sanity_check_env() -> None:
    missing = []
    if not GH_TOKEN: missing.append("GH_TOKEN or GH_PAT")
    if not SB_KEY:   missing.append("SUPABASE_SERVICE_KEY or SUPABASE_KEY")
    if missing:
        print(f"::error::missing required env: {', '.join(missing)}")
        sys.exit(2)


# ---------------------------------------------------------------------------
# HTTP helpers (same shape as canonical verifier)
# ---------------------------------------------------------------------------
def gh_headers():
    return {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}


def sb_headers():
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}


def gh_get(path: str) -> Any:
    r = httpx.get(f"{GH_API}{path}", headers=gh_headers(), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def sb_get(path: str) -> Any:
    r = httpx.get(f"{SB_URL}{path}", headers=sb_headers(), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def sb_post(path: str, data: dict) -> httpx.Response:
    h = sb_headers()
    h["Prefer"] = "return=representation"
    return httpx.post(f"{SB_URL}{path}", headers=h, json=data, timeout=TIMEOUT)


def sb_patch(path: str, data: dict) -> httpx.Response:
    h = sb_headers()
    h["Prefer"] = "return=representation"
    return httpx.patch(f"{SB_URL}{path}", headers=h, json=data, timeout=TIMEOUT)


def tg_send(msg: str) -> bool:
    if not TG_TOKEN:
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": msg[:4000], "parse_mode": "HTML"},
            timeout=10.0,
        )
        return r.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Verification primitives — logic IDENTICAL to canonical verifier,
# but adapted to accept owner/repo rather than hardcoding.
# ---------------------------------------------------------------------------
def verify_commit_exists(sha: str, repo: str) -> bool:
    try:
        gh_get(f"/repos/{repo}/commits/{sha}")
        return True
    except Exception:
        return False


def verify_pr_has_changes(pr_number: int, repo: str) -> bool:
    try:
        pr = gh_get(f"/repos/{repo}/pulls/{pr_number}")
        return (pr.get("additions", 0) + pr.get("deletions", 0)) > 0
    except Exception:
        return False


def verify_file_in_repo(file_path: str, repo: str, branch: str = "main") -> bool:
    try:
        from urllib.parse import quote
        enc = quote(file_path, safe="/")
        res = gh_get(f"/repos/{repo}/contents/{enc}?ref={branch}")
        return isinstance(res, dict) and res.get("size", 0) > 0
    except Exception:
        return False


def verify_supabase_table_exists(table_name: str) -> bool:
    try:
        r = httpx.head(
            f"{SB_URL}/rest/v1/{table_name}?limit=0",
            headers=sb_headers(),
            timeout=TIMEOUT,
        )
        return r.status_code in (200, 206)
    except Exception:
        return False


def verify_supabase_row_count(table_name: str) -> int:
    try:
        h = sb_headers()
        h["Prefer"] = "count=exact"
        r = httpx.get(
            f"{SB_URL}/rest/v1/{table_name}?select=*&limit=1",
            headers=h, timeout=TIMEOUT,
        )
        if r.status_code not in (200, 206):
            return -1
        # content-range header shape: "0-0/<total>"
        cr = r.headers.get("content-range", "")
        m = re.search(r"/(\d+)$", cr)
        return int(m.group(1)) if m else 0
    except Exception:
        return -1


def verify_url_live(url: str, expected_status: int | None = None) -> tuple[bool, int]:
    """Probe a URL. Returns (is_live_and_matches_expected, actual_status)."""
    try:
        r = httpx.get(url, timeout=TIMEOUT, follow_redirects=True)
        ok = (r.status_code == expected_status) if expected_status else (200 <= r.status_code < 400)
        return ok, r.status_code
    except Exception:
        return False, 0


# ---------------------------------------------------------------------------
# Claim extraction — pulls verifiable claims from summit_body + delivery_proof
# ---------------------------------------------------------------------------
def extract_claims(summit: dict) -> list[dict]:
    """Extract discrete verifiable claims from a SUMMIT row.

    Sources:
      1. delivery_proof.github_commits[*] — {repo, sha|path}
      2. delivery_proof.supabase_migrations[*] — migration names
      3. delivery_proof.supabase_artifacts — tables, views, functions, triggers
      4. delivery_proof.hard_verification.*_url — URL liveness probes
      5. summit_body — file paths in backticks, PR refs, commit SHAs

    Each claim: {type, target, repo?, kind, source}
    """
    claims: list[dict] = []
    body = summit.get("summit_body") or ""
    dp = summit.get("delivery_proof") or {}

    # 1. github_commits — file-path or sha claims
    for gc in dp.get("github_commits") or []:
        if not isinstance(gc, dict):
            continue
        repo = gc.get("repo") or gc.get("target") or ""
        sha = gc.get("sha")
        path = gc.get("path")
        if sha and repo:
            claims.append({"type": "commit", "target": sha, "repo": repo, "source": "delivery_proof.github_commits"})
        if path and repo:
            claims.append({"type": "file", "target": path, "repo": repo, "source": "delivery_proof.github_commits"})

    # 2. supabase_migrations
    for mig in dp.get("supabase_migrations") or []:
        if isinstance(mig, str):
            claims.append({"type": "migration", "target": mig, "source": "delivery_proof.supabase_migrations"})

    # 3. supabase_artifacts
    sa = dp.get("supabase_artifacts") or {}
    if isinstance(sa, dict):
        # Common shapes we saw: {trigger: "name on table"}, {function: "name"}, {views: [...]}
        for key in ("table", "function", "trigger", "view"):
            v = sa.get(key)
            if isinstance(v, str):
                # Try to extract a bare identifier
                ident = re.search(r"(?:public\.)?(\w+)", v)
                if ident:
                    claims.append({"type": f"sb_{key}", "target": ident.group(1), "source": f"delivery_proof.supabase_artifacts.{key}"})
        for key in ("views", "tables", "functions", "triggers"):
            arr = sa.get(key) or []
            for item in arr:
                if isinstance(item, str):
                    ident = re.search(r"(?:public\.)?(\w+)", item)
                    if ident:
                        claims.append({"type": f"sb_{key[:-1]}", "target": ident.group(1), "source": f"delivery_proof.supabase_artifacts.{key}"})

    # 4. hard_verification — URL liveness
    hv = dp.get("hard_verification") or {}
    if isinstance(hv, dict):
        def _walk_urls(obj, path=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    _walk_urls(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    _walk_urls(v, f"{path}[{i}]")
            elif isinstance(obj, str):
                if obj.startswith(("http://", "https://")):
                    claims.append({"type": "url_live", "target": obj, "source": f"delivery_proof.hard_verification{path}"})
        _walk_urls(hv)

    # 5. summit_body — backtick file paths + PR refs
    for fp in re.findall(r"`([a-zA-Z0-9_./-]+\.[a-zA-Z]{1,5})`", body):
        if "/" in fp:
            # Guess repo from context: look for owner/repo pattern near the path
            # Default to DEFAULT_REPO_POOL — we'll try each
            claims.append({"type": "file_any_repo", "target": fp, "source": "summit_body.backticks"})

    for pr in re.findall(r"PR\s*#?(\d+)", body):
        # Default to zonewise-web (most PRs this session)
        claims.append({"type": "pr", "target": int(pr), "repo": "breverdbidder/zonewise-web", "source": "summit_body.PR_ref"})

    return claims


def verify_claim(claim: dict) -> tuple[str, str]:
    """Run a claim through the appropriate verifier. Returns (verdict, evidence)."""
    t = claim["type"]
    target = claim["target"]

    if t == "commit":
        return (DELIVERED, f"commit {target[:10]} in {claim['repo']}") if verify_commit_exists(target, claim["repo"]) \
               else (NOT_DELIVERED, f"commit {target[:10]} NOT in {claim['repo']}")
    if t == "file":
        return (DELIVERED, f"{target} in {claim['repo']}") if verify_file_in_repo(target, claim["repo"]) \
               else (NOT_DELIVERED, f"{target} NOT in {claim['repo']}")
    if t == "file_any_repo":
        for r in DEFAULT_REPO_POOL:
            if verify_file_in_repo(target, r):
                return DELIVERED, f"{target} in {r}"
        return NOT_DELIVERED, f"{target} not in any of {DEFAULT_REPO_POOL}"
    if t == "pr":
        return (DELIVERED, f"PR #{target} has changes") if verify_pr_has_changes(target, claim["repo"]) \
               else (NOT_DELIVERED, f"PR #{target} missing or empty")
    if t == "migration":
        # Check if migration is logged in supabase_migrations system table
        try:
            rows = sb_get(f"/rest/v1/rpc/pg_migrations_list") if False else None
            # Fallback: look up via listed migrations endpoint — but we can't from anon REST,
            # so we fall back to "the named artifact exists" heuristic: at least one of the
            # things the migration creates must exist.
        except Exception:
            pass
        return DISPATCHED_ONLY, f"migration name '{target}' recorded but cannot verify remotely from REST"
    if t in ("sb_table", "sb_function", "sb_trigger", "sb_view"):
        # For tables + views, confirm queryable existence
        if t in ("sb_table", "sb_view"):
            return (DELIVERED, f"{t} '{target}' queryable") if verify_supabase_table_exists(target) \
                   else (NOT_DELIVERED, f"{t} '{target}' not queryable")
        # For functions + triggers, we can't check from REST without a dedicated RPC
        return DISPATCHED_ONLY, f"{t} '{target}' cannot be verified from REST"
    if t == "url_live":
        ok, status = verify_url_live(target)
        return (DELIVERED, f"{target} → HTTP {status}") if ok else (NOT_DELIVERED, f"{target} → HTTP {status}")

    return DISPATCHED_ONLY, f"no verifier for type {t}"


# ---------------------------------------------------------------------------
# SUMMIT-level orchestration
# ---------------------------------------------------------------------------
def verify_summit(summit: dict, auto_flip: bool = False) -> dict:
    claims = extract_claims(summit)
    results = [{"claim": c, "verdict": v, "evidence": ev}
               for c in claims for v, ev in [verify_claim(c)]]

    n = len(results)
    nD = sum(1 for r in results if r["verdict"] == DELIVERED)
    nND = sum(1 for r in results if r["verdict"] == NOT_DELIVERED)
    nDO = sum(1 for r in results if r["verdict"] == DISPATCHED_ONLY)
    nB = sum(1 for r in results if r["verdict"] == BLOCKED_HONEST)

    # Overall verdict rule
    if n == 0:
        overall = DISPATCHED_ONLY  # no verifiable claims, can't judge either way
    elif nND == 0 and nD > 0:
        overall = DELIVERED
    elif nND > 0 and nD == 0:
        overall = NOT_DELIVERED
    elif nND > 0 and nD > 0:
        overall = MIXED
    else:
        overall = DISPATCHED_ONLY

    # Persist
    run_payload = {
        "summit_id": summit["id"],
        "overall_verdict": overall,
        "claims_total": n,
        "claims_delivered": nD,
        "claims_not_delivered": nND,
        "claims_dispatched_only": nDO,
        "claims_blocked": nB,
        "per_claim_verdicts": results,
        "auto_flipped_to_failed": False,
    }

    # Auto-flip if enabled and overall is NOT_DELIVERED
    if auto_flip and overall == NOT_DELIVERED and summit.get("state") == "verified":
        patch_r = sb_patch(
            f"/rest/v1/summit_chat_dispatch?id=eq.{summit['id']}",
            {
                "state": "failed",
                "last_error": f"supabase_summit_verifier: {overall} ({nND}/{n} claims NOT_DELIVERED)",
            },
        )
        if patch_r.status_code in (200, 204):
            run_payload["auto_flipped_to_failed"] = True
            # Also log an honesty violation
            sb_post("/rest/v1/honesty_violations", {
                "domain": "summit_dispatch",
                "claim": f"SUMMIT {summit['id']} claimed state=verified",
                "tag_used": "VERIFIED",
                "actual_truth": f"supabase_summit_verifier verdict={overall}. {nND}/{n} claims NOT_DELIVERED.",
                "severity": "CRITICAL",
                "session_source": "supabase_summit_verifier",
                "corrective_action": "State auto-flipped to failed by verifier. Review per_claim_verdicts in summit_verifier_runs.",
            })

    sb_post("/rest/v1/summit_verifier_runs", run_payload)
    return run_payload


def fetch_summits_by_session(session_id: str) -> list[dict]:
    return sb_get(f"/rest/v1/summit_chat_dispatch?chat_session_id=eq.{session_id}&select=*")


def fetch_summit(summit_id: str) -> dict | None:
    rows = sb_get(f"/rest/v1/summit_chat_dispatch?id=eq.{summit_id}&select=*")
    return rows[0] if rows else None


def fetch_verified_since(hours: int = 24) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    return sb_get(f"/rest/v1/summit_chat_dispatch?state=eq.verified&completed_at=gte.{since}&select=*")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--summit-id")
    g.add_argument("--session")
    g.add_argument("--all-verified-today", action="store_true")
    g.add_argument("--auto-patrol", action="store_true", help="cron mode: verify last 24h of state=verified")
    ap.add_argument("--auto-flip", action="store_true", help="flip verified→failed on NOT_DELIVERED verdict")
    ap.add_argument("--telegram", action="store_true", help="send summary to Telegram")
    args = ap.parse_args()

    _sanity_check_env()

    if args.summit_id:
        s = fetch_summit(args.summit_id)
        summits = [s] if s else []
    elif args.session:
        summits = fetch_summits_by_session(args.session)
    elif args.all_verified_today or args.auto_patrol:
        summits = fetch_verified_since(24)

    # Only verify summits currently in verified state (others are already terminal)
    summits = [s for s in summits if s.get("state") == "verified"]
    print(f"[verifier] {len(summits)} verified SUMMITs to audit")

    rollup = {DELIVERED: 0, NOT_DELIVERED: 0, DISPATCHED_ONLY: 0, MIXED: 0, BLOCKED_HONEST: 0}
    flipped = 0
    detail_lines = []

    for s in summits:
        title = (s.get("summit_title") or "")[:60]
        try:
            result = verify_summit(s, auto_flip=args.auto_flip)
        except Exception as e:
            print(f"  ERR {s['id'][:8]}: {e}")
            continue
        v = result["overall_verdict"]
        rollup[v] = rollup.get(v, 0) + 1
        if result["auto_flipped_to_failed"]:
            flipped += 1
        marker = "🟢" if v == DELIVERED else ("🔴" if v == NOT_DELIVERED else ("🟡" if v == MIXED else "⚪"))
        line = f"  {marker} {s['id'][:8]} [{v:25s}] {result['claims_delivered']}/{result['claims_total']} delivered · {title}"
        detail_lines.append(line)
        print(line)

    summary = (
        f"\n=== ROLLUP ===\n"
        f"  DELIVERED-VERIFIED:      {rollup.get(DELIVERED, 0)}\n"
        f"  GHA-GREEN-NOT-DELIVERED: {rollup.get(NOT_DELIVERED, 0)}\n"
        f"  MIXED:                   {rollup.get(MIXED, 0)}\n"
        f"  DISPATCHED-ONLY:         {rollup.get(DISPATCHED_ONLY, 0)}\n"
        f"  BLOCKED-HONEST:          {rollup.get(BLOCKED_HONEST, 0)}\n"
        f"  AUTO-FLIPPED TO FAILED:  {flipped}\n"
    )
    print(summary)

    if args.telegram:
        tg_msg = f"<b>SUMMIT Verifier</b>\n{summary}\n\n" + "\n".join(detail_lines[:10])
        tg_send(tg_msg)


if __name__ == "__main__":
    main()
