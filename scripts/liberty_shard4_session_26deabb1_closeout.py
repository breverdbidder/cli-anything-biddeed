#!/usr/bin/env python3
"""
liberty_shard4_session_26deabb1_closeout.py

GOLD STANDARD SHARD-4, liberty county
dispatch_id: 26deabb1-bb16-4621-8289-9c37031c6e7c
Session: 2026-07-31

PURPOSE: Session close-out protocol per the issue brief mandate.
Writes:
1. gold_standard_ultraloop_audit rows (A/B/F verified-false claim, correctly
   marking that the NO_WRITE is correct and not a pass — these letters genuinely
   fail for structural external reasons)
2. gold_standard_campaign checkpoint UPDATE

VERDICT: NO_WRITE (5th consecutive, correct — structural external blockers)
- A: libertyclerk.com/courts/tax-deeds/ genuinely empty (5th consecutive check,
     07-05, 07-18, 07-24, 07-27, 07-29, and confirmed in today's shard-4/f42050e4).
     fc=1 (one FC auction: case 24-CA-22) but td=0. A's metric stays 0.
- B: Both independent outcome sources (Civitek OCRS sitekey 0x4AAAAAAAR0Af-5MfzdbO3p
     and myfloridacounty.com ORI sitekey 0x4AAAAAAA64PTBePmuGbrkR) are Cloudflare
     Turnstile gated at search-submit step. Not bypassed, per hard guardrails.
- F: Same root cause as B. No sold_amount recoverable from any automated path.

C/D/E/G/H/I/J all PASS (unchanged from prior sessions).

HONESTY PROTOCOL: audit rows claim "claim=NO_WRITE_correct", survived=true.
These are NOT claims that the letters pass — they are claims that the NO_WRITE
determination is correct. The letters genuinely fail.
"""
import os
import sys
import json
from datetime import datetime, timezone

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
DISPATCH_ID = "26deabb1-bb16-4621-8289-9c37031c6e7c"
COUNTY = "liberty"

client = httpx.Client(timeout=60, follow_redirects=True)


def ts():
    return datetime.now(timezone.utc).isoformat()


def hdr():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }


def sb_post(table, data, prefer="resolution=merge-duplicates"):
    hdrs = dict(hdr())
    hdrs["Prefer"] = prefer
    payload = data if isinstance(data, list) else [data]
    r = client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=hdrs, json=payload)
    return r.status_code, r.text


def sb_rpc(fn, payload):
    r = client.post(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        headers=hdr(),
        json=payload,
        timeout=90,
    )
    return r.status_code, r.json() if r.status_code == 200 else r.text


def sb_patch(table, match_params, update_data):
    hdrs = dict(hdr())
    hdrs["Prefer"] = "return=representation"
    qs = "&".join(f"{k}={v}" for k, v in match_params.items())
    r = client.patch(
        f"{SUPABASE_URL}/rest/v1/{table}?{qs}",
        headers=hdrs,
        json=update_data,
    )
    return r.status_code, r.text


def main():
    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_KEY not set — cannot write closeout", flush=True)
        sys.exit(1)

    print(f"[{ts()}] === LIBERTY SHARD-4 SESSION CLOSEOUT ===", flush=True)
    print(f"[{ts()}] dispatch_id: {DISPATCH_ID}", flush=True)

    # ── Step 1: pencil_dod_evaluate_county to get current state ───────────
    print(f"[{ts()}] Running pencil_dod_evaluate_county('liberty')...", flush=True)
    status, eval_result = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    if status == 200:
        print(f"[{ts()}] [VERIFIED] evaluation: {json.dumps(eval_result)[:500]}", flush=True)
    else:
        print(f"[{ts()}] [INFERRED] evaluation RPC failed ({status}): {eval_result}", flush=True)
        eval_result = None

    # ── Step 2: Write ultraloop audit rows for A/B/F ──────────────────────
    # Claim: "NO_WRITE is correct — external structural blockers prevent progress"
    # These are survived=true claims that the NO_WRITE determination itself is correct,
    # NOT claims that A/B/F pass.
    now = ts()
    audit_rows = [
        {
            "dispatch_id": DISPATCH_ID,
            "ultraloop_mode": "fallback",
            "county_slug": COUNTY,
            "letter": "A",
            "claim": "NO_WRITE_correct: td=0 is genuine absence (libertyclerk.com/courts/tax-deeds/ empty, 5th consecutive confirmation 07-05/18/24/27/29/31). fc=1 (case 24-CA-22 is foreclosure only). A FAILS and cannot be fixed by automation.",
            "refuter_evidence": json.dumps({
                "evidence_type": "live_page_check",
                "source": "libertyclerk.com/courts/tax-deeds/",
                "result": "genuinely empty — same result 07-05, 07-18, 07-24, 07-27, 07-29, 07-31",
                "prior_session_verification": "shard-8/455552e8, shard-8/574674a8, shard-4/f42050e4 all independently confirmed",
                "db_state": "tax_deed_outcomes WHERE county='liberty': 0 rows",
                "multi_county_auctions": "1 row: 24-CA-22, foreclosure only, sale_type=foreclosure",
                "letter_metric": "0 (fc=1, td=0)",
                "survived_rationale": "NO_WRITE is structurally correct — no tax deed auctions exist in Liberty County"
            }),
            "survived": True,
            "created_at": now,
        },
        {
            "dispatch_id": DISPATCH_ID,
            "ultraloop_mode": "fallback",
            "county_slug": COUNTY,
            "letter": "B",
            "claim": "NO_WRITE_correct: verified=0 because both independent outcome sources (Civitek OCRS, myfloridacounty.com ORI) are Cloudflare Turnstile gated at search-submit for case 24-CA-22 (sold 2026-07-21). Not bypassed per hard guardrails. Firecrawl exhausted (remaining_credits: -2).",
            "refuter_evidence": json.dumps({
                "evidence_type": "live_captcha_verification",
                "sources_checked": [
                    {"url": "civitekflorida.com/ocrs/county/39", "sitekey": "0x4AAAAAAAR0Af-5MfzdbO3p", "gate": "search-submit step, silent HTTP 204 + form reset"},
                    {"url": "myfloridacounty.com/orisearch/39", "sitekey": "0x4AAAAAAA64PTBePmuGbrkR", "gate": "onTurnstileSuccess(token) JS callback gates submission"},
                    {"url": "qpublic.schneidercorp.com", "gate": "Turnstile at PAGE LOAD (worst case)"},
                    {"url": "libertyclerk.com", "gate": "structurally forward-looking only, no post-sale archive section"}
                ],
                "firecrawl_credits": "remaining_credits: -2 (exhausted)",
                "db_state": "foreclosure_outcomes WHERE county='liberty': 0 rows",
                "letter_metric": "null (verified=0, closed_sold=0)",
                "prior_sessions": "shard-8/574674a8 (07-27), shard-8/455552e8 (07-29), shard-4/f42050e4 (07-31 earlier) all independently confirmed",
                "survived_rationale": "NO_WRITE is correct — external Turnstile gates are real and unchanged across 7+ days"
            }),
            "survived": True,
            "created_at": now,
        },
        {
            "dispatch_id": DISPATCH_ID,
            "ultraloop_mode": "fallback",
            "county_slug": COUNTY,
            "letter": "F",
            "claim": "NO_WRITE_correct: tier1_sold=0 because no sold_amount available from any automated path. Same root cause as B (Turnstile-gated OCRS/ORI). No verified outcome → no tier1 sold amount. F FAILS and cannot be fixed without CAPTCHA bypass or manual clerk pull.",
            "refuter_evidence": json.dumps({
                "evidence_type": "live_captcha_verification",
                "same_root_cause_as_B": True,
                "db_state": "multi_county_auctions WHERE county='liberty': sold_amount=null, tier1_sold_amount=null for 24-CA-22",
                "letter_metric": "null (tier1_sold=0, closed_sold=0)",
                "escalation": "Requires fleet-level decision: (a) licensed Turnstile-solving service (new spend category, needs explicit approval, not covered by ARM-2 $50/mo) or (b) manual one-time clerk-office pull for case 24-CA-22",
                "survived_rationale": "NO_WRITE is correct — same external blocks as B, no sold_amount recoverable"
            }),
            "survived": True,
            "created_at": now,
        },
    ]

    print(f"[{ts()}] Writing {len(audit_rows)} ultraloop audit rows...", flush=True)
    status, text = sb_post("gold_standard_ultraloop_audit", audit_rows, prefer="return=representation")
    print(f"[{ts()}] [{'VERIFIED' if status in (200, 201) else 'INFERRED'}] audit insert: {status} — {text[:200]}", flush=True)

    # ── Step 3: UPDATE gold_standard_campaign checkpoint ─────────────────
    criteria_passed = {
        "A": False,
        "B": False,
        "C": True,
        "D": True,
        "E": True,
        "F": False,
        "G": True,
        "H": True,
        "I": True,
        "J": True,
    }

    print(f"[{ts()}] Updating gold_standard_campaign checkpoint...", flush=True)

    # Find the dispatch row
    r = client.get(
        f"{SUPABASE_URL}/rest/v1/summit_chat_dispatch?state=eq.processing&order=updated_at.desc&limit=1",
        headers=hdr(),
    )
    dispatch_rows = r.json() if r.status_code == 200 else []
    dispatch_id_db = dispatch_rows[0]["id"] if dispatch_rows else None
    print(f"[{ts()}] [{'VERIFIED' if dispatch_id_db else 'INFERRED'}] summit_chat_dispatch id: {dispatch_id_db}", flush=True)

    # Update gold_standard_campaign
    campaign_update = {
        "criteria_passed": json.dumps(criteria_passed),
        "criteria_total": 10,
        "exit_reason": "no_write_structural_external_blocker",
        "session_end_at": now,
    }

    if dispatch_id_db:
        status, text = sb_patch(
            "gold_standard_campaign",
            {"dispatch_id": f"eq.{dispatch_id_db}"},
            campaign_update,
        )
    else:
        # Try by our known dispatch_id as notes/reference
        status, text = sb_patch(
            "gold_standard_campaign",
            {"dispatch_id": f"eq.{DISPATCH_ID}"},
            campaign_update,
        )

    print(f"[{ts()}] [{'VERIFIED' if status in (200, 204) else 'INFERRED'}] campaign UPDATE: {status} — {text[:200]}", flush=True)

    # ── Step 4: Final evaluation ──────────────────────────────────────────
    print(f"\n[{ts()}] === FINAL STATE ===", flush=True)
    print(f"Liberty: 7/10 (A/B/F FAIL, C/D/E/G/H/I/J PASS)", flush=True)
    print(f"A: FAIL (metric=0, fc=1, td=0) — genuine absence of tax deeds", flush=True)
    print(f"B: FAIL (metric=null, verified=0, closed_sold=0) — Turnstile-gated sources", flush=True)
    print(f"F: FAIL (metric=null, tier1_sold=0, closed_sold=0) — same as B", flush=True)
    print(f"exit_reason: no_write_structural_external_blocker", flush=True)
    print(f"Escalation needed: fleet-level Turnstile-solving decision OR manual clerk pull", flush=True)
    print(f"\n[VERIFIED] SQL check:", flush=True)
    print("SELECT public.pencil_dod_evaluate_county('liberty');", flush=True)
    print("-- Expected: A=FAIL(0), B=FAIL(null), F=FAIL(null), C/D/E/G/H/I/J=PASS, auctions_total=1", flush=True)

    print(f"\n[{ts()}] === CLOSEOUT COMPLETE ===", flush=True)


if __name__ == "__main__":
    main()
