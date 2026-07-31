#!/usr/bin/env python3
"""
Apply shard-4 run7622 changes via Supabase Management API + REST API.
Handles both the ultraloop audit inserts and the citrus duplicate-case fix.

Usage: python3 scripts/shard4_run7622_apply.py
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
PROJECT_REF = "mocerqjnksmhcjzxrewo"
DISPATCH_ID = "0f07f453-008b-41a6-9ede-579226e44ddc"


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="INFO"):
    print(f"[{ts()}] {tag}: {msg}")


def mgmt_api_query(sql: str):
    """Execute SQL via Supabase Management API."""
    if not ACCESS_TOKEN:
        log("SUPABASE_ACCESS_TOKEN not set — cannot use mgmt_api_query", "WARN")
        return None, "ACCESS_TOKEN missing"
    url = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
    payload = json.dumps({"query": sql}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode('utf-8')}"


def rest_rpc(fn_name: str, params: dict):
    """Call a Supabase RPC function via REST."""
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}"
    payload = json.dumps(params).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode('utf-8')}"


def rest_get(table: str, params: str):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    req = urllib.request.Request(
        url, method="GET",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode('utf-8')}"


def rest_post(table: str, data: list):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=ignore-duplicates,return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            return body, None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode('utf-8')}"


def evaluate_county(county: str):
    result, err = rest_rpc("pencil_dod_evaluate_county", {"p_county": county})
    if err:
        log(f"eval {county} ERROR: {err}", "ERROR")
        return None
    log(f"{county}: {json.dumps(result)}")
    return result


def write_audit_rows():
    """Insert ultraloop audit rows via SQL (handles ON CONFLICT DO NOTHING)."""
    sql = f"""
SET statement_timeout = 0;

INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  ('{DISPATCH_ID}', 'fallback', 'leon', 'A',
   'Leon A=70 (fc=119,td=70) PASS — run7622',
   '{{"source":"loop_run_7622_brief","metric":70,"fc":119,"td":70,"pass":true,"honesty":"VERIFIED"}}'::jsonb, true),
  ('{DISPATCH_ID}', 'fallback', 'leon', 'B',
   'Leon B=100.0% (verified=15/closed=15) PASS — run7622',
   '{{"source":"loop_run_7622_brief","metric":100.0,"verified":15,"closed_sold":15,"pass":true,"honesty":"VERIFIED"}}'::jsonb, true),
  ('{DISPATCH_ID}', 'fallback', 'leon', 'C',
   'Leon C=99.5% (matched_clean=188/189) PASS — run7622',
   '{{"source":"loop_run_7622_brief","metric":99.5,"matched_clean":188,"total":189,"pass":true,"honesty":"VERIFIED"}}'::jsonb, true),
  ('{DISPATCH_ID}', 'fallback', 'leon', 'D',
   'Leon D=99.5% (matched_any=188/189) PASS — run7622',
   '{{"source":"loop_run_7622_brief","metric":99.5,"matched_any":188,"total":189,"pass":true,"honesty":"VERIFIED"}}'::jsonb, true),
  ('{DISPATCH_ID}', 'fallback', 'leon', 'E',
   'Leon E=99.5% (parcel_linked=188/189) PASS — run7622',
   '{{"source":"loop_run_7622_brief","metric":99.5,"parcel_linked":188,"total":189,"pass":true,"honesty":"VERIFIED"}}'::jsonb, true),
  ('{DISPATCH_ID}', 'fallback', 'leon', 'F',
   'Leon F=100.0% (tier1_sold=15/closed=15) PASS — run7622',
   '{{"source":"loop_run_7622_brief","metric":100.0,"tier1_sold":15,"closed_sold":15,"pass":true,"honesty":"VERIFIED"}}'::jsonb, true),
  ('{DISPATCH_ID}', 'fallback', 'leon', 'G',
   'Leon G=98.9% (density=98.9) PASS — run7622',
   '{{"source":"loop_run_7622_brief","metric":98.9,"density":98.9,"pass":true,"honesty":"VERIFIED — ordinance fix from run6148 still holding"}}'::jsonb, true),
  ('{DISPATCH_ID}', 'fallback', 'leon', 'H',
   'Leon H=0.1h since last_seen PASS — run7622',
   '{{"source":"loop_run_7622_brief","metric":0.1,"pass":true,"honesty":"VERIFIED"}}'::jsonb, true),
  ('{DISPATCH_ID}', 'fallback', 'leon', 'I',
   'Leon I=96.3% (card_complete=182/189) PASS — run7622',
   '{{"source":"loop_run_7622_brief","metric":96.3,"card_complete":182,"total":189,"pass":true,"honesty":"VERIFIED — ghost-purge from 2f4312f9 confirmed genuine"}}'::jsonb, true),
  ('{DISPATCH_ID}', 'fallback', 'leon', 'J',
   'Leon J=99.5% (deal_complete=188/189) PASS — run7622',
   '{{"source":"loop_run_7622_brief","metric":99.5,"deal_complete":188,"total":189,"pass":true,"honesty":"INFERRED — mechanical-placeholder flag applies fleet-wide but leon not specifically purged"}}'::jsonb, true),
  -- Citrus failures (honest documentation)
  ('{DISPATCH_ID}', 'fallback', 'citrus', 'E',
   'Citrus E=94.2% (parcel_linked=180/191) FAIL — 11 rows blocked — run7622',
   '{{"source":"dispatch_6060708f_2026-07-31T01:11Z","metric":94.2,"parcel_linked":180,"total":191,"pass":false,"honesty":"VERIFIED"}}'::jsonb, false),
  ('{DISPATCH_ID}', 'fallback', 'citrus', 'I',
   'Citrus I=94.2% (card_complete=180/191) FAIL — run7622',
   '{{"source":"dispatch_6060708f_2026-07-31T01:11Z","metric":94.2,"card_complete":180,"total":191,"pass":false,"honesty":"VERIFIED"}}'::jsonb, false),
  -- Madison failures
  ('{DISPATCH_ID}', 'fallback', 'madison', 'A',
   'Madison A=0 (fc=5,td=0) FAIL — run7622',
   '{{"source":"loop_run_7622_brief","metric":0,"fc":5,"td":0,"pass":false,"honesty":"VERIFIED"}}'::jsonb, false),
  ('{DISPATCH_ID}', 'fallback', 'madison', 'B',
   'Madison B=null (verified=0,closed_sold=0) FAIL — external blockers — run7622',
   '{{"source":"dispatch_2f4312f9+loop_run_7622_brief","metric":null,"verified":0,"closed_sold":0,"pass":false,"honesty":"VERIFIED"}}'::jsonb, false),
  ('{DISPATCH_ID}', 'fallback', 'madison', 'F',
   'Madison F=null (tier1_sold=0,closed_sold=0) FAIL — run7622',
   '{{"source":"loop_run_7622_brief","metric":null,"tier1_sold":0,"closed_sold":0,"pass":false,"honesty":"VERIFIED"}}'::jsonb, false)
ON CONFLICT DO NOTHING;
"""
    log("Applying audit rows via mgmt API...")
    result, err = mgmt_api_query(sql)
    if err:
        log(f"mgmt_api_query error: {err}", "ERROR")
        # Try REST fallback for just the leon rows
        log("Falling back to REST API for audit rows...")
        leon_rows = [
            {"dispatch_id": DISPATCH_ID, "ultraloop_mode": "fallback", "county_slug": "leon",
             "letter": ltr, "claim": f"Leon {ltr} PASS run7622",
             "refuter_evidence": {"source": "loop_run_7622_brief", "pass": True, "honesty": "VERIFIED"},
             "survived": True}
            for ltr in list("ABCDEFGHIJ")
        ]
        body, err2 = rest_post("gold_standard_ultraloop_audit", leon_rows)
        if err2:
            log(f"REST fallback also failed: {err2}", "ERROR")
        else:
            log(f"REST fallback succeeded: {body}")
        return False
    log(f"Audit rows result: {json.dumps(result)[:500]}")
    return True


def diagnose_and_fix_citrus():
    """Check and potentially fix the citrus duplicate case constraint."""
    log("=== Citrus duplicate case diagnosis ===")

    # Check both cases
    case_2022, err1 = rest_get(
        "multi_county_auctions",
        "county=eq.citrus&case_number=eq.2022 CA 000835 A&select=case_number,sale_date,auction_date,sale_type,auction_type,property_address,parcel_id,assessed_value,parity_status"
    )
    case_2025, err2 = rest_get(
        "multi_county_auctions",
        "county=eq.citrus&case_number=eq.2025 CA 000110 A&select=case_number,sale_date,auction_date,sale_type,auction_type,property_address,parcel_id,assessed_value,parity_status"
    )

    if err1:
        log(f"2022 case lookup error: {err1}", "WARN")
        return False, "lookup_error"
    if err2:
        log(f"2025 case lookup error: {err2}", "WARN")
        return False, "lookup_error"

    if not case_2022:
        log("2022 CA 000835 A: NOT IN DB", "WARN")
    else:
        log(f"2022 CA 000835 A: {json.dumps(case_2022[0])}")

    if not case_2025:
        log("2025 CA 000110 A: NOT IN DB", "WARN")
    else:
        log(f"2025 CA 000110 A: {json.dumps(case_2025[0])}")

    if not case_2022 or not case_2025:
        return False, "case_not_found"

    c22 = case_2022[0]
    c25 = case_2025[0]

    # Case 1: 2022 case already has parcel_id=1475589 and sale_date set
    if c22.get("parcel_id") == "1475589" and c22.get("sale_date") is not None:
        log("2022 case: has real sale_date + correct parcel — this IS a real prior auction. Cannot clear parcel_id safely.", "WARN")
        log("BLOCKED: 2022 case represents a real prior auction on the same parcel. Duplicate-case scenario.", "WARN")
        return False, "genuine_duplicate_prior_auction"

    # Case 2: 2022 case has sale_date=None — stale placeholder
    if c22.get("sale_date") is None and c22.get("parcel_id") == "1475589":
        log("2022 case: sale_date=NULL + parcel_id=1475589 → stale placeholder. Safe to clear and update 2025 case.")
        # Apply via mgmt API
        fix_sql = """
SET statement_timeout = 0;
-- Clear stale parcel_id on 2022 case (sale_date=NULL confirms no real outcome)
UPDATE multi_county_auctions 
SET parcel_id = NULL
WHERE county = 'citrus' AND case_number = '2022 CA 000835 A' AND sale_date IS NULL;

-- Set correct parcel_id on active 2025 case
UPDATE multi_county_auctions
SET parcel_id = '1475589',
    property_address = COALESCE(property_address, (
        SELECT property_address FROM multi_county_auctions 
        WHERE county = 'citrus' AND case_number = '2022 CA 000835 A' LIMIT 1
    ))
WHERE county = 'citrus' AND case_number = '2025 CA 000110 A' AND parcel_id IS NULL;
"""
        result, err = mgmt_api_query(fix_sql)
        if err:
            log(f"Fix SQL error: {err}", "ERROR")
            return False, "fix_sql_error"
        log(f"Fix SQL result: {json.dumps(result)[:500]}")
        return True, "fixed_stale_2022"

    # Case 3: 2022 case has different parcel_id or is already NULL
    if c22.get("parcel_id") is None:
        log("2022 case already has NULL parcel_id — constraint may be from another field")
        # Try just setting 2025 directly
        if c25.get("parcel_id") is None:
            fix_sql = """
UPDATE multi_county_auctions
SET parcel_id = '1475589'
WHERE county = 'citrus' AND case_number = '2025 CA 000110 A' AND parcel_id IS NULL;
"""
            result, err = mgmt_api_query(fix_sql)
            if err:
                log(f"Direct fix SQL error: {err}", "ERROR")
                return False, "fix_sql_error"
            log(f"Direct fix result: {json.dumps(result)[:500]}")
            return True, "direct_fix_2025"
        else:
            log(f"2025 case already has parcel_id={c25.get('parcel_id')}")
            return False, "already_set"

    log(f"2022 case parcel_id={c22.get('parcel_id')} sale_date={c22.get('sale_date')} — unhandled state", "WARN")
    return False, "unhandled_state"


def check_madison_detail():
    """Full Madison state check."""
    log("=== Madison full state ===")
    auctions, err = rest_get(
        "multi_county_auctions",
        "county=eq.madison&select=case_number,auction_type,sale_date,auction_date,parity_status,parcel_id&order=auction_date.desc"
    )
    if err:
        log(f"Madison auctions error: {err}", "ERROR")
        return
    log(f"Madison total: {len(auctions) if auctions else 0} auctions")
    if auctions:
        for a in auctions:
            log(f"  {a.get('case_number')} type={a.get('auction_type')} sale={a.get('sale_date')} auc={a.get('auction_date')} parity={a.get('parity_status')}")

    # Check if there are any RealAuction tax deed listings not in our DB
    # Madison uses myfloridacounty.com/orisearch/40 for official records
    log("Madison sources: foreclosure=realforeclose.com/madison, taxdeed=myfloridacounty.com/orisearch/40")
    log("INFERRED: Madison td=0 because no tax deed auctions are listed on the county's platform")


def main():
    if not SUPABASE_KEY and not ACCESS_TOKEN:
        log("No credentials — cannot connect to Supabase", "ERROR")
        sys.exit(1)

    log(f"=== SHARD-4 RUN 7622 dispatch={DISPATCH_ID} ===")

    # Baseline
    log("--- BASELINE ---")
    before = {c: evaluate_county(c) for c in ["leon", "citrus", "madison"]}

    # Write audit rows
    log("--- AUDIT ROWS ---")
    write_audit_rows()

    # Citrus fix attempt
    log("--- CITRUS DUPLICATE CASE FIX ---")
    fixed, reason = diagnose_and_fix_citrus()
    log(f"Citrus fix: fixed={fixed} reason={reason}")

    # Madison state
    log("--- MADISON STATE ---")
    check_madison_detail()

    # Post-fix evaluation
    log("--- POST-FIX EVALUATION ---")
    after = {c: evaluate_county(c) for c in ["leon", "citrus", "madison"]}

    # Summary
    log("=== SUMMARY ===")
    for county in ["leon", "citrus", "madison"]:
        b = before.get(county)
        a = after.get(county)
        bp = sum(1 for k, v in (b or {}).items() if isinstance(v, dict) and v.get("pass"))
        ap = sum(1 for k, v in (a or {}).items() if isinstance(v, dict) and v.get("pass"))
        log(f"{county}: {bp}/10 → {ap}/10")

    log("=== SQL VERIFICATION ===")
    for county in ["leon", "citrus", "madison"]:
        log(f"BEFORE {county}: {json.dumps(before.get(county))}")
    for county in ["leon", "citrus", "madison"]:
        log(f"AFTER  {county}: {json.dumps(after.get(county))}")


if __name__ == "__main__":
    main()
