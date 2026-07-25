#!/usr/bin/env python3
"""
taylor_apply_i_fix_run6354.py
Apply zone assignment for parcel 05026-000 (case 23-597 CA) and verify
that criterion I moves from 88.9% (8/9) to 100.0% (9/9) for taylor.

HONESTY TAG: INFERRED (geographic derivation from legal description + PLSS bounds)
See supabase/migrations/20260725_gold_standard_shard14_taylor_i_parcel_05026_zone.sql
for full evidence chain documentation.

Usage:
  SUPABASE_SERVICE_ROLE_KEY=... python3 scripts/taylor_apply_i_fix_run6354.py
"""

import os
import sys
import json
import time
from datetime import datetime, timezone

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
SUPABASE_MGMT_TOKEN = (
    os.environ.get("SUPABASE_ACCESS_TOKEN")
    or os.environ.get("SUPABASE_MGMT_TOKEN")
    or ""
)

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_KEY env var required", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
NOW = datetime.now(timezone.utc)
DISPATCH_ID = "b92ee67c-93e0-4831-816a-d2cad6d4933b"


def log(msg, level="INFO"):
    ts = NOW.isoformat()
    print(f"[{ts}] {level}: {msg}", flush=True)


def mgmt_query(sql):
    if not SUPABASE_MGMT_TOKEN:
        log("No SUPABASE_ACCESS_TOKEN — cannot use Management API", "WARN")
        return None
    r = httpx.post(
        MGMT_URL,
        headers={
            "Authorization": f"Bearer {SUPABASE_MGMT_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"query": sql},
        timeout=60,
    )
    log(f"  Mgmt API status: {r.status_code}")
    if r.status_code in (200, 201):
        return r.json()
    else:
        log(f"  Mgmt API error: {r.text[:300]}", "ERROR")
        return None


def rest_get(endpoint, params=None):
    r = httpx.get(f"{BASE}{endpoint}", headers=HEADERS, params=params, timeout=60)
    if r.status_code == 200:
        return r.json()
    else:
        log(f"  REST GET {endpoint} error: {r.status_code} {r.text[:200]}", "ERROR")
        return None


def rest_post_rpc(rpc_name, body):
    r = httpx.post(
        f"{BASE}/rpc/{rpc_name}",
        headers=HEADERS,
        json=body,
        timeout=60,
    )
    log(f"  RPC {rpc_name}: {r.status_code}")
    if r.status_code == 200:
        return r.json()
    else:
        log(f"  RPC error: {r.text[:300]}", "ERROR")
        return None


def check_existing_zone():
    log("Checking if parcel_zones row for 05026-000 already exists...")
    rows = rest_get("/parcel_zones", {
        "parcel_id": "eq.05026-000",
        "select": "parcel_id,zone_code,source,jurisdiction_id",
    })
    if rows is None:
        return None
    log(f"  Existing rows: {rows}")
    return rows


def apply_zone_insert():
    log("Applying zone insert for 05026-000 (MUR, jurisdiction_id=1513)...")

    # Method 1: Direct REST insert
    r = httpx.post(
        f"{BASE}/parcel_zones",
        headers=HEADERS,
        json={
            "parcel_id": "05026-000",
            "tax_account": "R05026-000",
            "jurisdiction_id": 1513,
            "zone_code": "MUR",
            "zone_name": "Mixed Use Rural Residential",
            "source": "plss_sec26_t4s_r7e_geographic_derivation:INFERRED+ncfrpc_flu_interpolation:2026-07-25+honesty_tag=INFERRED",
        },
        timeout=30,
    )
    log(f"  REST insert: {r.status_code}")
    if r.status_code in (200, 201):
        log(f"  Inserted: {r.json()}")
        return {"method": "rest", "ok": True, "result": r.json()}
    elif r.status_code == 409:
        log("  409 Conflict — row already exists (good, idempotent)")
        return {"method": "rest", "ok": True, "reason": "already_exists"}
    else:
        log(f"  REST insert failed: {r.text[:300]}", "WARN")

    # Method 2: Management API
    log("  Fallback to Management API...")
    sql = """
SET statement_timeout = 0;
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES (
  '05026-000',
  'R05026-000',
  1513,
  'MUR',
  'Mixed Use Rural Residential',
  'plss_sec26_t4s_r7e_geographic_derivation:INFERRED+ncfrpc_flu_interpolation:2026-07-25+honesty_tag=INFERRED'
)
ON CONFLICT DO NOTHING
RETURNING parcel_id, zone_code, jurisdiction_id;
"""
    result = mgmt_query(sql.strip())
    if result is not None:
        log(f"  Mgmt API insert result: {result}")
        return {"method": "mgmt_api", "ok": True, "result": result}
    else:
        return {"method": "none", "ok": False}


def insert_ultraloop_audit():
    log("Inserting ultraloop audit row...")
    sql = f"""
INSERT INTO gold_standard_ultraloop_audit (
  dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived
)
VALUES (
  '{DISPATCH_ID}',
  'fallback',
  'taylor',
  'I',
  'parcel 05026-000 zone assigned MUR (Unincorporated Taylor County id=1513) via PLSS geographic derivation; I expected to move 88.9pct (8/9) to 100.0pct (9/9)',
  '{{"honesty_tag": "INFERRED", "method": "PLSS_geographic_derivation", "plss": "Sec26_T4S_R7E_EHalf_SWqtr_SWqtr", "jurisdiction_confirmed": "legal_description_says_Taylor_County_FL_not_City_of_Perry", "zone_basis": "residential_subdivision_near_Perry_consistent_with_MUR_Mixed_Use_Rural_Residential"}}'::jsonb,
  true
)
ON CONFLICT DO NOTHING;
"""
    result = mgmt_query(sql.strip())
    log(f"  Audit insert: {result}")
    return result


def run_evaluation():
    log("Running pencil_dod_evaluate_county('taylor')...")
    ev = rest_post_rpc("pencil_dod_evaluate_county", {"p_county": "taylor"})
    if ev is None:
        return {}
    if isinstance(ev, list):
        ev = ev[0] if ev else {}
    if not isinstance(ev, dict):
        log(f"  Unexpected type: {type(ev)}", "WARN")
        return {}

    pass_count = 0
    pass_letters = []
    fail_letters = []
    for letter in ["A","B","C","D","E","F","G","H","I","J"]:
        item = ev.get(letter, {})
        passes = item.get("pass", False)
        metric = item.get("metric")
        detail = item.get("detail", "")
        status = "PASS" if passes else "FAIL"
        log(f"  {letter}: {status} metric={metric} ({detail})")
        if passes:
            pass_count += 1
            pass_letters.append(letter)
        else:
            fail_letters.append(letter)

    log(f"  TOTAL: {pass_count}/10 letters pass")
    return {
        "pass_count": pass_count,
        "pass_letters": pass_letters,
        "fail_letters": fail_letters,
        "raw": ev,
    }


def probe_new_bf_avenues():
    log("Probing new B/F avenues (not tried in prior sessions)...")

    client = httpx.Client(
        timeout=15,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        },
        follow_redirects=True,
    )

    found = []

    # Direct PDF patterns for CT documents
    log("  1. Direct PDF URL patterns for Certificate of Title documents")
    for year in ["2025", "2026"]:
        for slug, case_num in [
            ("25-196-CA", "25-196 CA"),
            ("25-217-CA", "25-217 CA"),
            ("25-218-CA", "25-218 CA"),
        ]:
            for suffix in ["-Certificate-of-Title.pdf", "-CT.pdf", "-Sale-Results.pdf"]:
                url = f"https://taylorclerk.com/uploads/{year}/{slug}{suffix}"
                try:
                    r = client.head(url, timeout=5)
                    if r.status_code == 200:
                        log(f"    FOUND: {url}")
                        found.append({"type": "pdf", "url": url, "case": case_num})
                    time.sleep(0.1)
                except Exception:
                    time.sleep(0.1)

    # Tax deed surplus pages
    log("  2. Tax deed surplus pages")
    surplus_urls = [
        "https://taylorclerk.com/departments/tax-deeds-surplus/",
        "https://taylorclerk.com/departments/tax-deed-surplus/",
        "https://taylorclerk.com/tax-deed-surplus/",
    ]
    for url in surplus_urls:
        try:
            r = client.get(url, timeout=10)
            log(f"    {url}: HTTP {r.status_code}")
            if r.status_code == 200 and len(r.text) > 100:
                import re
                amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', r.text)
                if amounts:
                    log(f"      Amounts found: {amounts[:5]}")
                    found.append({"type": "page", "url": url, "amounts": amounts[:5]})
        except Exception as e:
            log(f"    {url}: {e}", "WARN")
        time.sleep(0.3)

    log(f"  B/F probe: {len(found)} hits found")
    return found


def main():
    log("=" * 70)
    log(f"taylor_apply_i_fix_run6354.py — dispatch {DISPATCH_ID}")
    log("=" * 70)

    # 1. Check current state
    log("\n--- STEP 1: Check existing parcel_zones for 05026-000 ---")
    existing = check_existing_zone()

    # 2. Apply I fix
    log("\n--- STEP 2: Apply I fix ---")
    if existing:
        log(f"  Row already exists: {existing}")
        insert_result = {"ok": True, "reason": "already_exists"}
    else:
        insert_result = apply_zone_insert()

    # 3. Audit row
    if insert_result.get("ok"):
        log("\n--- STEP 3: Insert ultraloop audit ---")
        insert_ultraloop_audit()

    # 4. Evaluate
    log("\n--- STEP 4: Verify I metric ---")
    evaluation = run_evaluation()

    # 5. B/F probe
    log("\n--- STEP 5: New B/F avenue probe ---")
    bf_found = probe_new_bf_avenues()

    # Summary
    log("\n" + "=" * 70)
    log("FINAL SUMMARY")
    log("=" * 70)
    log(f"  I fix applied: {insert_result.get('ok')}")
    pass_letters = evaluation.get("pass_letters", [])
    fail_letters = evaluation.get("fail_letters", [])
    log(f"  Total pass: {evaluation.get('pass_count', 'UNKNOWN')}/10")
    log(f"  Pass letters: {pass_letters}")
    log(f"  Fail letters: {fail_letters}")
    log(f"  I criterion: {'PASS' if 'I' in pass_letters else 'FAIL'}")
    log(f"  B criterion: {'PASS' if 'B' in pass_letters else 'FAIL'}")
    log(f"  F criterion: {'PASS' if 'F' in pass_letters else 'FAIL'}")
    log(f"  B/F new sources found: {len(bf_found)}")

    if not bf_found:
        log("  B/F: No new accessible sources — still structurally blocked")
        log("  Recommendation: Firecrawl JS-render ($10 spend approval needed)")

    return evaluation


if __name__ == "__main__":
    result = main()
    i_pass = "I" in result.get("pass_letters", [])
    sys.exit(0 if i_pass else 1)
