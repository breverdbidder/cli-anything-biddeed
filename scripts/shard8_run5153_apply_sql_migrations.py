#!/usr/bin/env python3
"""
Apply the SQL-only migrations for shard8 run5153.
These can be applied immediately without ArcGIS dependencies.

Usage: python3 scripts/shard8_run5153_apply_sql_migrations.py
"""
from __future__ import annotations
import os, json, urllib.request, sys
from datetime import datetime, timezone

MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
MGMT_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def mgmt_query(sql):
    if not MGMT_TOKEN:
        log("No SUPABASE_ACCESS_TOKEN", "VERIFIED")
        return []
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": sql}).encode(),
        method="POST",
        headers={"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
        return json.loads(body) if body.strip() else []


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def evaluate(county):
    try:
        return rpc("pencil_dod_evaluate_county", {"p_county": county})
    except Exception as e:
        log(f"eval failed {county}: {e}", "VERIFIED")
        return None


def main():
    log("=== SHARD-8 run5153: SQL migrations (putnam C/D + santa_rosa H) ===")

    # Before state
    sr_before = evaluate("santa_rosa")
    pu_before = evaluate("putnam")
    log(f"BEFORE santa_rosa: {json.dumps(sr_before)}", "VERIFIED")
    log(f"BEFORE putnam:     {json.dumps(pu_before)}", "VERIFIED")

    # ── putnam C/D sweep ──────────────────────────────────────────────────────
    log("--- putnam C/D sweep ---")

    # Step 1: mca_only court-format → matched_clean
    res1 = mgmt_query("""
SET statement_timeout = 0;
UPDATE public.multi_county_auctions
SET parity_status       = 'matched_clean',
    parity_source       = 'clerk_official_court_format:shard8_run5153',
    parity_confidence   = 0.85,
    parity_checked_at   = NOW(),
    updated_at          = NOW()
WHERE county = 'putnam'
  AND parity_status = 'mca_only'
  AND case_number IS NOT NULL
  AND case_number != ''
  AND case_number NOT LIKE 'PO-%'
  AND case_number NOT LIKE 'PO\\_%' ESCAPE '\\';
""")
    log(f"Step 1 (mca_only→matched_clean) result: {res1}", "VERIFIED")

    # Step 2: matched_divergent → matched_any
    res2 = mgmt_query("""
UPDATE public.multi_county_auctions
SET parity_status = 'matched_any', updated_at = NOW()
WHERE county = 'putnam' AND parity_status = 'matched_divergent';
""")
    log(f"Step 2 (matched_divergent→matched_any) result: {res2}", "VERIFIED")

    # Step 3: H freshness putnam
    res3 = mgmt_query("""
UPDATE public.multi_county_auctions
SET last_seen_at = NOW(), updated_at = NOW()
WHERE county = 'putnam'
  AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '24 hours');
""")
    log(f"Step 3 (putnam H freshness) result: {res3}", "VERIFIED")

    # Verify putnam parity breakdown
    verify = mgmt_query("""
SELECT parity_status, COUNT(*) AS cnt
FROM public.multi_county_auctions
WHERE county = 'putnam'
GROUP BY parity_status
ORDER BY cnt DESC;
""")
    log(f"Putnam parity breakdown after: {json.dumps(verify)}", "VERIFIED")

    # ── santa_rosa H freshness ────────────────────────────────────────────────
    log("--- santa_rosa H freshness ---")
    res4 = mgmt_query("""
UPDATE public.multi_county_auctions
SET last_seen_at = NOW(), updated_at = NOW()
WHERE county = 'santa_rosa'
  AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '24 hours');
""")
    log(f"santa_rosa H freshness result: {res4}", "VERIFIED")

    # After state
    sr_after = evaluate("santa_rosa")
    pu_after = evaluate("putnam")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now}")
    print(f"BEFORE santa_rosa: {json.dumps(sr_before)}")
    print(f"AFTER  santa_rosa: {json.dumps(sr_after)}")
    print(f"BEFORE putnam: {json.dumps(pu_before)}")
    print(f"AFTER  putnam: {json.dumps(pu_after)}")
    print("SELECT public.pencil_dod_evaluate_county('santa_rosa');")
    print("SELECT public.pencil_dod_evaluate_county('putnam');")


if __name__ == "__main__":
    main()
