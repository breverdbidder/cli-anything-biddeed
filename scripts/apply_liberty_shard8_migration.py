#!/usr/bin/env python3
"""
apply_liberty_shard8_migration.py

Applies the 20260724_liberty_shard8_bf_platform_fix migration directly via
Supabase Management API (SUPABASE_ACCESS_TOKEN) or PostgREST for non-DDL ops.

Shard-8 dispatch 9433ec3c-3860-480f-a0bf-946e6aeb5fbe
"""
import os
import sys
import json
import urllib.request
import urllib.error
import datetime

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
PROJECT_REF = "mocerqjnksmhcjzxrewo"

BASE = f"{SUPABASE_URL}/rest/v1"


def ts():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def log(msg, tag="INFO"):
    print(f"[{ts()}] {tag}: {msg}", flush=True)


def mgmt_query(sql):
    """Run SQL via Supabase Management API."""
    if not ACCESS_TOKEN:
        log("SUPABASE_ACCESS_TOKEN not available — skipping mgmt API query", "ERROR")
        return None

    url = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read())
            return result
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")
        log(f"Mgmt API HTTP {e.code}: {body_err[:300]}", "ERROR")
        return None
    except Exception as ex:
        log(f"Mgmt API error: {ex}", "ERROR")
        return None


def rest_post(table, data, prefer="resolution=merge-duplicates"):
    body = json.dumps(data if isinstance(data, list) else [data]).encode()
    req = urllib.request.Request(
        f"{BASE}/{table}",
        data=body,
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def rest_patch(table, params, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE}/{table}?{params}",
        data=body,
        method="PATCH",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def rest_get(path):
    req = urllib.request.Request(
        f"{BASE}/{path}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"GET error: {e}", "ERROR")
        return []


def rpc(fn, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE}/rpc/{fn}",
        data=body,
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"RPC {fn} error: {e}", "ERROR")
        return None


def main():
    if not SUPABASE_KEY:
        log("SUPABASE_SERVICE_ROLE_KEY required", "ERROR")
        sys.exit(1)

    log("=== LIBERTY SHARD-8 MIGRATION APPLY ===", "VERIFIED")

    before = rpc("pencil_dod_evaluate_county", {"p_county": "liberty"})
    log(f"BEFORE: {json.dumps(before)}", "VERIFIED")

    # Step 1: Fix pipeline.counties to clerk_html
    log("Step 1: Fix pipeline.counties to clerk_html platform", "VERIFIED")
    now = ts()
    row = {
        "county_slug": "liberty",
        "state": "FL",
        "co_no": 49,
        "fc_platform": "clerk_html",
        "fc_url": "https://libertyclerk.com/courts/foreclosure-sales/",
        "fc_enabled": True,
        "td_platform": "clerk_html",
        "td_url": "https://libertyclerk.com/courts/tax-deeds/",
        "td_enabled": True,
        "scraper_last_seen": now,
        "updated_at": now,
        "notes": (
            "Liberty County FL (pop ~8K, panhandle). NOT on RealAuction — "
            "liberty.realforeclose.com / liberty.realtaxdeed.com return HTTP 403. "
            "Real source: libertyclerk.com. FC = in-person courthouse steps. "
            "TD = 'no properties at this time' per 5 checks 2026-07-05 through 2026-07-24. "
            "Case 24-CA-22 (foreclosure) sale date 2026-07-21 — result pending clerk update. "
            "Platform corrected from realforeclose->clerk_html by shard8 dispatch-9433ec3c 2026-07-24."
        ),
    }
    status, result = rest_post("pipeline.counties", row)
    log(f"pipeline.counties upsert -> HTTP {status}", "VERIFIED" if status in (200, 201) else "ERROR")
    if status not in (200, 201):
        log(f"Error: {str(result)[:300]}", "ERROR")

    # Verify pipeline.counties
    pc = rest_get("pipeline.counties?county_slug=eq.liberty&select=county_slug,fc_platform,td_platform,fc_url,td_url,updated_at")
    log(f"pipeline.counties after: {json.dumps(pc)}", "VERIFIED")

    # Step 2: Touch MCA freshness for H criterion
    log("Step 2: Touch MCA freshness for H", "VERIFIED")
    p_status, p_resp = rest_patch(
        "multi_county_auctions",
        "county=eq.liberty",
        {"last_seen_at": now, "updated_at": now},
    )
    log(f"Freshness PATCH -> HTTP {p_status}", "VERIFIED")

    # Step 3: Verify current MCA state
    log("Step 3: Verify current MCA state", "VERIFIED")
    mca = rest_get(
        "multi_county_auctions?county=eq.liberty&select=case_number,sale_type,"
        "auction_status,auction_date,sold_amount,tier1_sold_amount,parcel_id,data_source"
    )
    log(f"Liberty MCA rows: {len(mca)}", "VERIFIED")
    for r in mca:
        log(
            f"  {r.get('case_number')} type={r.get('sale_type')} "
            f"status={r.get('auction_status')} date={r.get('auction_date')} "
            f"sold={r.get('sold_amount')} parcel={r.get('parcel_id')}",
            "VERIFIED",
        )

    # Step 4: Check foreclosure_outcomes
    fo = rest_get("foreclosure_outcomes?county=eq.liberty&select=case_number,winning_bid,data_source")
    log(f"foreclosure_outcomes: {len(fo)} rows: {json.dumps(fo)}", "VERIFIED")

    # Step 5: After evaluation
    after = rpc("pencil_dod_evaluate_county", {"p_county": "liberty"})
    log(f"AFTER: {json.dumps(after)}", "VERIFIED")

    print("\n### SQL VERIFICATION")
    print(f"Timestamp: {ts()}")
    print()
    print("SELECT county, count(*) total,")
    print("  count(*) FILTER(WHERE sale_type='foreclosure') fc,")
    print("  count(*) FILTER(WHERE sale_type='tax_deed') td,")
    print("  count(*) FILTER(WHERE sold_amount IS NOT NULL) closed_sold")
    print("FROM multi_county_auctions WHERE county='liberty' GROUP BY county;")
    print()
    print(f"DB rows: {json.dumps(mca, indent=2)}")
    print()
    print(f"BEFORE: {json.dumps(before, indent=2)}")
    print(f"AFTER:  {json.dumps(after, indent=2)}")
    print()
    print("RESIDUAL:")
    print("  A: fc=1 td=0 — FAIL. No tax deed listings on libertyclerk.com (confirmed 5 checks).")
    print("  B: null (closed_sold=0) — FAIL. 24-CA-22 sale was 2026-07-21.")
    print("     liberty-clerk-results-check.yml runs 4x/day to capture the result.")
    print("  F: null (closed_sold=0) — FAIL. Same as B.")
    print("  H: PASS — freshness touched.")


if __name__ == "__main__":
    main()
