#!/usr/bin/env python3
"""
Supabase SUMMIT Verifier v2 — Dual-Gate Enterprise-Grade

Combines two gates:
  1. Supabase-side claim verification (extracted from delivery_proof)
  2. EG14 14-point gate (dispatched via GHA for touches_prod_web=TRUE summits)

Writes dual_gate_verdict ∈ {PASS, FAIL, INSUFFICIENT_EVIDENCE}.
Only PASS allows state=verified (enforced by trg_require_dual_gate).
FAIL / INSUFFICIENT_EVIDENCE auto-route to failed / closed.

Usage:
    python supabase_summit_verifier.py --summit-id <uuid>
    python supabase_summit_verifier.py --session <chat_session_id>
    python supabase_summit_verifier.py --all-awaiting-verification
    python supabase_summit_verifier.py --auto-patrol   # cron mode, includes retro-verify
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
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
EG14_REPO = "breverdbidder/cli-anything-biddeed"
EG14_WORKFLOW = "eg14-gate.yml"
TIMEOUT = 20.0
EG14_DEBOUNCE_HOURS = 1         # per-summit cooldown
GLOBAL_RATE_LIMIT_MIN = 10      # no more than 1 EG14 dispatch per 10 min globally
EG14_WAIT_MAX_MIN = 20          # how long to wait for EG14 completion

# Verdicts (Supabase-side, per-claim)
CLAIM_DELIVERED = "DELIVERED-VERIFIED"
CLAIM_NOT_DELIVERED = "GHA-GREEN-NOT-DELIVERED"
CLAIM_DISPATCHED_ONLY = "DISPATCHED-ONLY"
CLAIM_BLOCKED = "BLOCKED-HONEST"

# Combined dual-gate verdicts
DG_PASS = "PASS"
DG_FAIL = "FAIL"
DG_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"

DEFAULT_REPO_POOL = [
    "breverdbidder/cli-anything-biddeed",
    "breverdbidder/zonewise-web",
    "breverdbidder/everest-content",
]


def _sanity() -> None:
    miss = []
    if not GH_TOKEN: miss.append("GH_TOKEN or GH_PAT")
    if not SB_KEY:   miss.append("SUPABASE_SERVICE_KEY or SUPABASE_KEY")
    if miss:
        print(f"::error::missing env: {', '.join(miss)}")
        sys.exit(2)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def gh_headers():
    return {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}


def sb_headers():
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}


def gh_get(path: str) -> Any:
    r = httpx.get(f"{GH_API}{path}", headers=gh_headers(), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def gh_post(path: str, body: dict) -> httpx.Response:
    return httpx.post(f"{GH_API}{path}", headers=gh_headers(), json=body, timeout=TIMEOUT)


def sb_get(path: str) -> Any:
    r = httpx.get(f"{SB_URL}{path}", headers=sb_headers(), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def sb_post(path: str, data: Any) -> httpx.Response:
    h = sb_headers(); h["Prefer"] = "return=representation"
    return httpx.post(f"{SB_URL}{path}", headers=h, json=data, timeout=TIMEOUT)


def sb_patch(path: str, data: dict) -> httpx.Response:
    h = sb_headers(); h["Prefer"] = "return=representation"
    return httpx.patch(f"{SB_URL}{path}", headers=h, json=data, timeout=TIMEOUT)


def tg_send(msg: str) -> None:
    if not TG_TOKEN: return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": msg[:4000], "parse_mode": "HTML"},
            timeout=10.0,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Supabase-side verification primitives
# ---------------------------------------------------------------------------
def verify_commit_exists(sha: str, repo: str) -> bool:
    try:
        gh_get(f"/repos/{repo}/commits/{sha}"); return True
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
        r = httpx.head(f"{SB_URL}/rest/v1/{table_name}?limit=0", headers=sb_headers(), timeout=TIMEOUT)
        return r.status_code in (200, 206)
    except Exception:
        return False


def verify_supabase_function_exists(func_name: str) -> bool:
    """Query pg_catalog via the exec_sql RPC (closes the 25% blind spot)."""
    try:
        r = httpx.post(
            f"{SB_URL}/rest/v1/rpc/pg_catalog_has_function",
            headers=sb_headers(), timeout=TIMEOUT,
            json={"p_name": func_name},
        )
        if r.status_code == 200:
            return bool(r.json())
        return False
    except Exception:
        return False


def verify_supabase_trigger_exists(trigger_name: str) -> bool:
    try:
        r = httpx.post(
            f"{SB_URL}/rest/v1/rpc/pg_catalog_has_trigger",
            headers=sb_headers(), timeout=TIMEOUT,
            json={"p_name": trigger_name},
        )
        if r.status_code == 200:
            return bool(r.json())
        return False
    except Exception:
        return False


def verify_url_live(url: str, expected_status: int | None = None) -> tuple[bool, int]:
    try:
        r = httpx.get(url, timeout=TIMEOUT, follow_redirects=True)
        ok = (r.status_code == expected_status) if expected_status else (200 <= r.status_code < 400)
        return ok, r.status_code
    except Exception:
        return False, 0


# ---------------------------------------------------------------------------
# Claim extraction + verdict
# ---------------------------------------------------------------------------
def extract_claims(summit: dict) -> list[dict]:
    claims: list[dict] = []
    body = summit.get("summit_body") or ""
    dp = summit.get("delivery_proof") or {}

    for gc in dp.get("github_commits") or []:
        if not isinstance(gc, dict): continue
        repo = gc.get("repo") or gc.get("target") or ""
        sha = gc.get("sha"); path = gc.get("path")
        if sha and repo and re.match(r"^[0-9a-f]{7,40}$", str(sha)):
            claims.append({"type": "commit", "target": sha, "repo": repo})
        if path and repo and re.match(r"^[\w./\-\[\]()]+\.\w{1,5}$", str(path)):
            claims.append({"type": "file", "target": path, "repo": repo})

    sa = dp.get("supabase_artifacts") or {}
    if isinstance(sa, dict):
        for key in ("table","function","trigger","view"):
            v = sa.get(key)
            if isinstance(v, str):
                ident = re.search(r"(?:public\.)?(\w+)", v)
                if ident: claims.append({"type": f"sb_{key}", "target": ident.group(1)})
        for key in ("views","tables","functions","triggers"):
            for item in sa.get(key) or []:
                if isinstance(item, str):
                    ident = re.search(r"(?:public\.)?(\w+)", item)
                    if ident: claims.append({"type": f"sb_{key[:-1]}", "target": ident.group(1)})

    hv = dp.get("hard_verification") or {}
    def _walk(obj):
        if isinstance(obj, dict):
            for v in obj.values(): _walk(v)
        elif isinstance(obj, list):
            for v in obj: _walk(v)
        elif isinstance(obj, str) and obj.startswith(("http://","https://")):
            claims.append({"type": "url_live", "target": obj})
    _walk(hv)

    for fp in re.findall(r"`([a-zA-Z0-9_./\-\[\]()]+\.[a-zA-Z]{1,5})`", body):
        if "/" in fp and not fp.startswith("http"):
            claims.append({"type": "file_any_repo", "target": fp})

    for pr in re.findall(r"PR\s*#?(\d+)", body):
        claims.append({"type": "pr", "target": int(pr), "repo": "breverdbidder/zonewise-web"})

    return claims


def verify_claim(claim: dict) -> tuple[str, str]:
    t = claim["type"]; target = claim["target"]
    if t == "commit":
        return (CLAIM_DELIVERED, f"commit {target[:10]} in {claim['repo']}") if verify_commit_exists(target, claim["repo"]) \
               else (CLAIM_NOT_DELIVERED, f"commit {target[:10]} NOT in {claim['repo']}")
    if t == "file":
        return (CLAIM_DELIVERED, f"{target} in {claim['repo']}") if verify_file_in_repo(target, claim["repo"]) \
               else (CLAIM_NOT_DELIVERED, f"{target} NOT in {claim['repo']}")
    if t == "file_any_repo":
        for r in DEFAULT_REPO_POOL:
            if verify_file_in_repo(target, r):
                return CLAIM_DELIVERED, f"{target} in {r}"
        return CLAIM_NOT_DELIVERED, f"{target} not in pool"
    if t == "pr":
        return (CLAIM_DELIVERED, f"PR #{target} has changes") if verify_pr_has_changes(target, claim["repo"]) \
               else (CLAIM_NOT_DELIVERED, f"PR #{target} missing or empty")
    if t in ("sb_table","sb_view"):
        return (CLAIM_DELIVERED, f"{t} '{target}' queryable") if verify_supabase_table_exists(target) \
               else (CLAIM_NOT_DELIVERED, f"{t} '{target}' not queryable")
    if t == "sb_function":
        if verify_supabase_function_exists(target):
            return CLAIM_DELIVERED, f"function '{target}' in pg_catalog"
        return CLAIM_NOT_DELIVERED, f"function '{target}' NOT in pg_catalog"
    if t == "sb_trigger":
        if verify_supabase_trigger_exists(target):
            return CLAIM_DELIVERED, f"trigger '{target}' in pg_catalog"
        return CLAIM_NOT_DELIVERED, f"trigger '{target}' NOT in pg_catalog"
    if t == "url_live":
        ok, status = verify_url_live(target)
        return (CLAIM_DELIVERED, f"{target} → HTTP {status}") if ok else (CLAIM_NOT_DELIVERED, f"{target} → HTTP {status}")
    return CLAIM_DISPATCHED_ONLY, f"no verifier for type {t}"


# ---------------------------------------------------------------------------
# EG14 dispatch + wait
# ---------------------------------------------------------------------------
def _last_eg14_for_summit(summit_uuid: str) -> dict | None:
    """Return {passed, failed, total, ran_at} for most recent EG14 run, or None."""
    try:
        rows = sb_get(f"/rest/v1/eg14_runs?summit_uuid=eq.{summit_uuid}&select=status,ran_at&order=ran_at.desc&limit=14")
        if not rows: return None
        ran_at = rows[0]["ran_at"]
        passed = sum(1 for r in rows if r["status"] == "PASS")
        failed = sum(1 for r in rows if r["status"] == "FAIL")
        return {"passed": passed, "failed": failed, "total": len(rows), "ran_at": ran_at}
    except Exception:
        return None


def _check_global_rate_limit() -> bool:
    """Return True if we may dispatch EG14 (no dispatch in last GLOBAL_RATE_LIMIT_MIN min)."""
    try:
        from urllib.parse import quote
        cutoff = quote((datetime.now(timezone.utc) - timedelta(minutes=GLOBAL_RATE_LIMIT_MIN)).isoformat(), safe="")
        rows = sb_get(f"/rest/v1/summit_verifier_runs?eg14_dispatched=eq.true&run_at=gte.{cutoff}&select=id&limit=1")
        return len(rows) == 0
    except Exception:
        return True  # fail-open on rate limit check


def dispatch_eg14(summit_uuid: str, target_url: str, scope: str) -> int | None:
    r = gh_post(
        f"/repos/{EG14_REPO}/actions/workflows/{EG14_WORKFLOW}/dispatches",
        {"ref": "main", "inputs": {
            "summit_id": summit_uuid,
            "target_url": target_url,
            "scope": scope,
        }},
    )
    if r.status_code != 204:
        print(f"::error::EG14 dispatch failed: {r.status_code} {r.text[:200]}")
        return None
    # Find the run we just dispatched
    time.sleep(5)
    runs = gh_get(f"/repos/{EG14_REPO}/actions/workflows/{EG14_WORKFLOW}/runs?per_page=3")
    for rn in runs.get("workflow_runs", []):
        if rn.get("event") == "workflow_dispatch" and rn["status"] in ("queued","in_progress"):
            return rn["id"]
    return None


def wait_eg14(run_id: int, max_min: int = EG14_WAIT_MAX_MIN) -> str:
    """Wait for EG14 run to complete. Returns conclusion or 'timeout'."""
    start = time.time()
    while time.time() - start < max_min * 60:
        try:
            run = gh_get(f"/repos/{EG14_REPO}/actions/runs/{run_id}")
            if run.get("status") == "completed":
                return run.get("conclusion") or "unknown"
        except Exception:
            pass
        time.sleep(15)
    return "timeout"


# ---------------------------------------------------------------------------
# Dual-gate orchestration
# ---------------------------------------------------------------------------
def verify_summit(summit: dict, auto_flip: bool = True) -> dict:
    sid = summit["id"]
    title = (summit.get("summit_title") or "")[:60]
    touches_web = summit.get("touches_prod_web") is not False  # fail-safe: NULL → True
    scope = summit.get("verification_scope") or "supabase_only"

    # ---- Gate 1: Supabase-side claim verification
    claims = extract_claims(summit)
    per_claim = [{"claim": c, "verdict": v, "evidence": ev}
                 for c in claims for v, ev in [verify_claim(c)]]
    nD = sum(1 for r in per_claim if r["verdict"] == CLAIM_DELIVERED)
    nND = sum(1 for r in per_claim if r["verdict"] == CLAIM_NOT_DELIVERED)
    nDO = sum(1 for r in per_claim if r["verdict"] == CLAIM_DISPATCHED_ONLY)
    nB = sum(1 for r in per_claim if r["verdict"] == CLAIM_BLOCKED)

    supabase_pass = (nND == 0 and nD > 0)
    supabase_insufficient = (nD == 0 and nND == 0)

    # ---- Gate 2: EG14 (only for prod-web)
    eg14_dispatched = False
    eg14_run_id = None
    eg14_passed = None
    eg14_failed = None
    eg14_total = None
    eg14_status = None

    if touches_web and supabase_pass:  # only run EG14 if supabase gate cleared
        target_url = summit.get("target_url") or "https://zonewise.ai"

        # Debounce: if recent EG14 exists and it passed, reuse
        existing = _last_eg14_for_summit(sid)
        if existing and existing["ran_at"]:
            ran_at_dt = datetime.fromisoformat(existing["ran_at"].replace("Z","+00:00"))
            age = datetime.now(timezone.utc) - ran_at_dt
            if age < timedelta(hours=EG14_DEBOUNCE_HOURS):
                eg14_passed = existing["passed"]
                eg14_failed = existing["failed"]
                eg14_total = existing["total"]
                eg14_status = "reused_recent"
                print(f"  [{sid[:8]}] reusing EG14 result from {age} ago: {eg14_passed}/{eg14_total}")

        # Dispatch fresh if no recent result
        if eg14_passed is None:
            if not _check_global_rate_limit():
                print(f"  [{sid[:8]}] global EG14 rate limit — deferring")
                eg14_status = "rate_limited"
            else:
                print(f"  [{sid[:8]}] dispatching EG14 (scope={scope}, url={target_url})")
                eg14_run_id = dispatch_eg14(sid, target_url, scope)
                if eg14_run_id:
                    eg14_dispatched = True
                    conclusion = wait_eg14(eg14_run_id)
                    eg14_status = conclusion
                    # Read results from eg14_runs
                    res = _last_eg14_for_summit(sid)
                    if res:
                        eg14_passed = res["passed"]
                        eg14_failed = res["failed"]
                        eg14_total = res["total"]
                else:
                    eg14_status = "dispatch_failed"

    # ---- Combined dual-gate verdict
    if not touches_web:
        # Supabase-only: Gate 1 decides
        if supabase_pass:       dual_gate = DG_PASS
        elif supabase_insufficient: dual_gate = DG_INSUFFICIENT
        elif nDO > 0 and nD > 0 and nND == 0: dual_gate = DG_INSUFFICIENT  # mixed with unverifiables
        else: dual_gate = DG_FAIL
    else:
        # Prod-web: both gates required
        if not supabase_pass:
            dual_gate = DG_INSUFFICIENT if supabase_insufficient else DG_FAIL
        elif eg14_passed is None:
            # EG14 couldn't run (rate limit, dispatch fail)
            dual_gate = DG_INSUFFICIENT
        elif eg14_failed and eg14_failed > 0:
            dual_gate = DG_FAIL
        elif eg14_total and eg14_passed >= max(int(eg14_total * 0.86), eg14_total - 1):
            # Require ≥86% OR ≤1 failure (whichever is tighter) — mirrors EG14 bar
            dual_gate = DG_PASS
        else:
            dual_gate = DG_FAIL

    # Overall claim verdict for back-compat
    if nND == 0 and nD > 0: overall = CLAIM_DELIVERED
    elif nND > 0 and nD == 0: overall = CLAIM_NOT_DELIVERED
    elif nND > 0 and nD > 0: overall = "MIXED"
    else: overall = CLAIM_DISPATCHED_ONLY

    run_row = {
        "summit_id": sid,
        "overall_verdict": overall,
        "claims_total": len(per_claim),
        "claims_delivered": nD,
        "claims_not_delivered": nND,
        "claims_dispatched_only": nDO,
        "claims_blocked": nB,
        "per_claim_verdicts": per_claim,
        "auto_flipped_to_failed": False,
        "eg14_dispatched": eg14_dispatched,
        "eg14_run_id": eg14_run_id,
        "eg14_passed": eg14_passed,
        "eg14_failed": eg14_failed,
        "eg14_total": eg14_total,
        "dual_gate_verdict": dual_gate,
        "verifier_completed_at": datetime.now(timezone.utc).isoformat(),
        "verifier_version": "v2.0-dual-gate",
    }

    # ---- State machine routing
    current_state = summit.get("state")
    if dual_gate == DG_PASS:
        # Allowed to transition to verified (trigger will validate)
        if current_state in ("awaiting_verification", "dispatched", "running"):
            r = sb_patch(f"/rest/v1/summit_chat_dispatch?id=eq.{sid}", {"state": "verified", "completed_at": datetime.now(timezone.utc).isoformat()})
            if r.status_code in (200, 204):
                print(f"  [{sid[:8]}] ✓ PROMOTED to verified")
            else:
                print(f"  [{sid[:8]}] promote failed: {r.status_code} {r.text[:120]}")

    elif dual_gate == DG_FAIL and auto_flip:
        if current_state == "verified":
            r = sb_patch(f"/rest/v1/summit_chat_dispatch?id=eq.{sid}", {"state": "failed"})
            if r.status_code in (200, 204):
                run_row["auto_flipped_to_failed"] = True
                sb_post("/rest/v1/honesty_violations", {
                    "domain": "summit_dispatch",
                    "claim": f"SUMMIT {sid} previously state=verified (self-attested)",
                    "tag_used": "VERIFIED",
                    "actual_truth": f"dual-gate verifier v2 verdict=FAIL (supabase_claims={nD}/{len(per_claim)}, eg14={eg14_passed}/{eg14_total})",
                    "severity": "CRITICAL",
                    "session_source": "supabase_summit_verifier_v2",
                    "corrective_action": "Auto-flipped to failed by dual-gate verifier.",
                })
                print(f"  [{sid[:8]}] ✗ FLIPPED verified→failed (dual_gate=FAIL)")

    elif dual_gate == DG_INSUFFICIENT and auto_flip:
        if current_state == "verified":
            r = sb_patch(f"/rest/v1/summit_chat_dispatch?id=eq.{sid}", {"state": "closed"})
            if r.status_code in (200, 204):
                print(f"  [{sid[:8]}] ⚪ ROUTED verified→closed (insufficient evidence)")

    sb_post("/rest/v1/summit_verifier_runs", run_row)
    return run_row


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------
def fetch_summits_by_session(session_id: str) -> list[dict]:
    return sb_get(f"/rest/v1/summit_chat_dispatch?chat_session_id=eq.{session_id}&select=*&order=created_at.asc")


def fetch_summit(summit_id: str) -> dict | None:
    rows = sb_get(f"/rest/v1/summit_chat_dispatch?id=eq.{summit_id}&select=*")
    return rows[0] if rows else None


def fetch_all_awaiting() -> list[dict]:
    return sb_get(f"/rest/v1/summit_chat_dispatch?state=eq.awaiting_verification&select=*")


def fetch_verified_since(hours: int = 24) -> list[dict]:
    from urllib.parse import quote
    since = quote((datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(), safe="")
    return sb_get(f"/rest/v1/summit_chat_dispatch?state=eq.verified&completed_at=gte.{since}&select=*")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--summit-id")
    g.add_argument("--session")
    g.add_argument("--all-awaiting-verification", action="store_true")
    g.add_argument("--auto-patrol", action="store_true")
    g.add_argument("--retro-verify-today", action="store_true", help="Re-verify today's self-attested verified summits")
    ap.add_argument("--no-auto-flip", action="store_true")
    ap.add_argument("--no-eg14", action="store_true", help="Skip EG14 (Supabase gate only)")
    args = ap.parse_args()

    _sanity()

    if args.summit_id:
        s = fetch_summit(args.summit_id); summits = [s] if s else []
    elif args.session:
        summits = fetch_summits_by_session(args.session)
    elif args.all_awaiting_verification:
        summits = fetch_all_awaiting()
    elif args.auto_patrol:
        summits = fetch_all_awaiting() + fetch_verified_since(2)  # patrol window
    elif args.retro_verify_today:
        summits = fetch_verified_since(24)

    print(f"[verifier] {len(summits)} SUMMIT(s) to audit")
    print(f"[verifier] EG14 chaining: {'DISABLED' if args.no_eg14 else 'ENABLED'} · auto_flip: {'NO' if args.no_auto_flip else 'YES'}")

    rollup = {DG_PASS: 0, DG_FAIL: 0, DG_INSUFFICIENT: 0}
    for s in summits:
        if not s: continue
        try:
            res = verify_summit(s, auto_flip=not args.no_auto_flip)
            rollup[res["dual_gate_verdict"]] = rollup.get(res["dual_gate_verdict"], 0) + 1
            marker = {"PASS":"🟢", "FAIL":"🔴", "INSUFFICIENT_EVIDENCE":"⚪"}.get(res["dual_gate_verdict"], "?")
            print(f"  {marker} {s['id'][:8]} [{res['dual_gate_verdict']:22s}] claims={res['claims_delivered']}/{res['claims_total']} eg14={res['eg14_passed']}/{res['eg14_total']} · {(s.get('summit_title') or '')[:50]}")
        except Exception as e:
            print(f"  ERR {s['id'][:8]}: {type(e).__name__}: {str(e)[:200]}")

    print(f"\n=== DUAL-GATE ROLLUP ===")
    print(f"  PASS:                 {rollup.get(DG_PASS, 0)}")
    print(f"  FAIL:                 {rollup.get(DG_FAIL, 0)}")
    print(f"  INSUFFICIENT_EVIDENCE:{rollup.get(DG_INSUFFICIENT, 0)}")


if __name__ == "__main__":
    main()
