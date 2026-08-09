#!/usr/bin/env python3
"""Apply shard-4 bradford+liberty session closeout to live DB via REST API."""
import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

DISPATCH_ID = "191b679e-346a-4750-8da5-42d78713b138"


def ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rest_patch(path, params, body):
    qs = urllib.parse.urlencode(params)
    url = f"{SUPABASE_URL}/rest/v1/{path}?{qs}"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=HEADERS, method="PATCH"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read() or b"[]")


def rest_post(path, body, prefer="return=representation"):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    h = {**HEADERS, "Prefer": prefer}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"[]")
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", errors="replace")
        print(f"[ERROR] HTTP {e.code}: {body_txt[:300]}", file=sys.stderr)
        return e.code, []


def rest_get(path, params):
    qs = urllib.parse.urlencode(params)
    url = f"{SUPABASE_URL}/rest/v1/{path}?{qs}"
    req = urllib.request.Request(url, headers={**HEADERS, "Prefer": ""})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def call_rpc(fn, args):
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn}"
    req = urllib.request.Request(
        url, data=json.dumps(args).encode(), headers={**HEADERS, "Prefer": ""}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"[ERROR] RPC {fn}: {e}", file=sys.stderr)
        return None


def main():
    print(f"[{ts()}] Applying shard-4 session closeout — dispatch {DISPATCH_ID}")
    print()

    # Step 1: Update gold_standard_campaign
    print(f"[{ts()}] Step 1: Update gold_standard_campaign...")
    criteria_passed = {
        "bradford": {
            "A": True, "B": False, "C": True, "D": True, "E": True,
            "F": False, "G": True, "H": True, "I": True, "J": True
        },
        "liberty": {
            "A": False, "B": False, "C": True, "D": True, "E": True,
            "F": False, "G": True, "H": True, "I": True, "J": True
        }
    }
    status, rows = rest_patch(
        "gold_standard_campaign",
        {"dispatch_id": f"eq.{DISPATCH_ID}"},
        {
            "criteria_passed": criteria_passed,
            "criteria_total": 10,
            "exit_reason": "structural_dead_end",
            "session_end_at": ts(),
        }
    )
    print(f"  HTTP {status}, rows updated: {len(rows)}")
    if rows:
        print(f"  dispatch_id: {rows[0].get('dispatch_id')}")
        print(f"  exit_reason: {rows[0].get('exit_reason')}")
        print(f"  session_end_at: {rows[0].get('session_end_at')}")
    print()

    # Step 2: Insert ULTRALOOP audit rows
    print(f"[{ts()}] Step 2: Insert ULTRALOOP audit rows...")
    audit_rows = [
        {
            "dispatch_id": DISPATCH_ID,
            "ultraloop_mode": "fallback",
            "county_slug": "bradford",
            "letter": "B",
            "claim": "Bradford B metric=null confirmed: closed_sold=0, no independent outcome for case 25000457CAAXMX (8th session)",
            "refuter_evidence": {
                "session_date": "2026-08-09",
                "days_past_sale": 24,
                "case_number": "25000457CAAXMX",
                "sale_date": "2026-07-16",
                "sources_exhausted": ["bradfordclerk.com", "bctelegraph.com", "surplusindex.com", "courtlistener.com", "judyrecords.com", "trellis.law", "myfloridacounty.com ORI (Turnstile)", "civitekflorida.com OCRS (Turnstile)"],
                "foreclosure_outcomes_count": 0,
                "prior_sessions": 8,
                "captcha_bypass_attempted": False,
                "honesty_marker": "VERIFIED"
            },
            "survived": True,
        },
        {
            "dispatch_id": DISPATCH_ID,
            "ultraloop_mode": "fallback",
            "county_slug": "bradford",
            "letter": "F",
            "claim": "Bradford F metric=null confirmed: tier1_sold=0, no sold amount for case 25000457CAAXMX",
            "refuter_evidence": {
                "session_date": "2026-08-09",
                "case_number": "25000457CAAXMX",
                "root_cause": "No independent sold amount posted to any reachable source",
                "captcha_sources_blocking": ["myfloridacounty.com ORI (Turnstile)", "civitekflorida.com OCRS (Turnstile)"],
                "honesty_marker": "VERIFIED"
            },
            "survived": True,
        },
        {
            "dispatch_id": DISPATCH_ID,
            "ultraloop_mode": "fallback",
            "county_slug": "liberty",
            "letter": "A",
            "claim": "Liberty A metric=0 confirmed: libertyclerk.com/courts/tax-deeds/ shows no properties (9th consecutive check)",
            "refuter_evidence": {
                "session_date": "2026-08-09",
                "url_checked": "https://libertyclerk.com/courts/tax-deeds/",
                "expected_result": "There are no properties on the list of tax deeds at this time",
                "consecutive_identical_results": 9,
                "fc_lane": 1,
                "td_lane": 0,
                "honesty_marker": "VERIFIED"
            },
            "survived": True,
        },
        {
            "dispatch_id": DISPATCH_ID,
            "ultraloop_mode": "fallback",
            "county_slug": "liberty",
            "letter": "B",
            "claim": "Liberty B metric=null confirmed: closed_sold=0, no independent outcome for case 24-CA-22 (8th+ session)",
            "refuter_evidence": {
                "session_date": "2026-08-09",
                "days_past_sale": 19,
                "case_number": "24-CA-22",
                "sale_date": "2026-07-21",
                "cot_window_closed_approx": "2026-07-31",
                "days_past_cot": 9,
                "sources_checked": ["libertyclerk.com/courts/foreclosure-sales/ (0 cards)", "libertyclerk.com/courts/tax-deeds/ (no properties)", "Civitek OCRS (Turnstile)", "myfloridacounty.com ORI (Turnstile)", "libertypa.org (no parcel DB)", "qpublic (HTTP 403)"],
                "foreclosure_outcomes_count": 0,
                "prior_sessions": 8,
                "captcha_bypass_attempted": False,
                "honesty_marker": "VERIFIED"
            },
            "survived": True,
        },
        {
            "dispatch_id": DISPATCH_ID,
            "ultraloop_mode": "fallback",
            "county_slug": "liberty",
            "letter": "F",
            "claim": "Liberty F metric=null confirmed: tier1_sold=0, no sold amount for case 24-CA-22",
            "refuter_evidence": {
                "session_date": "2026-08-09",
                "case_number": "24-CA-22",
                "root_cause": "COT likely recorded but unreachable (Turnstile gates block ORI and OCRS search)",
                "captcha_sources_blocking": ["civitekflorida.com OCRS (Turnstile)", "myfloridacounty.com ORI (Turnstile)"],
                "honesty_marker": "VERIFIED"
            },
            "survived": True,
        },
    ]

    status, inserted = rest_post(
        "gold_standard_ultraloop_audit",
        audit_rows,
        prefer="resolution=ignore-duplicates,return=representation"
    )
    print(f"  HTTP {status}, rows inserted: {len(inserted)}")
    if inserted:
        for row in inserted:
            print(f"  id={row.get('id')} county={row.get('county_slug')} letter={row.get('letter')} survived={row.get('survived')}")
    print()

    # Step 3: Verify current evaluator state (per-county, no fleet loop)
    print(f"[{ts()}] Step 3: Verify current evaluator state...")
    for county in ["bradford", "liberty"]:
        dod = call_rpc("pencil_dod_evaluate_county", {"p_county": county})
        if dod:
            total = sum(1 for v in dod.values() if isinstance(v, dict) and v.get("pass"))
            b = dod.get("B", {})
            f_c = dod.get("F", {})
            a_c = dod.get("A", {})
            print(f"  {county}: {total}/10 | A={a_c.get('pass')}({a_c.get('metric')}) B={b.get('pass')}({b.get('metric')}) F={f_c.get('pass')}({f_c.get('metric')})")
        else:
            print(f"  {county}: eval failed (RPC error)")
    print()

    # Step 4: Verify campaign row
    print(f"[{ts()}] Step 4: Verify campaign row...")
    rows = rest_get(
        "gold_standard_campaign",
        {"dispatch_id": f"eq.{DISPATCH_ID}", "select": "dispatch_id,exit_reason,session_end_at,criteria_total"}
    )
    if rows:
        row = rows[0]
        print(f"  dispatch_id={row.get('dispatch_id')}")
        print(f"  exit_reason={row.get('exit_reason')}")
        print(f"  session_end_at={row.get('session_end_at')}")
        print(f"  criteria_total={row.get('criteria_total')}")
    else:
        print(f"  WARNING: dispatch {DISPATCH_ID} not found in gold_standard_campaign")
        print(f"  This may mean the dispatch row was not created (could be a missing INSERT)")
    print()

    print(f"[{ts()}] Session close-out complete.")
    print()
    print("### SQL VERIFICATION")
    print(f"Timestamp UTC: {ts()}")
    print("```sql")
    print(f"SELECT dispatch_id, exit_reason, session_end_at FROM public.gold_standard_campaign")
    print(f"WHERE dispatch_id = '{DISPATCH_ID}'::uuid;")
    print()
    print(f"SELECT county_slug, letter, survived FROM public.gold_standard_ultraloop_audit")
    print(f"WHERE dispatch_id = '{DISPATCH_ID}'::uuid ORDER BY county_slug, letter;")
    print()
    print("SELECT public.pencil_dod_evaluate_county('bradford');")
    print("-- Expected: 8/10 (B,F fail), all others pass")
    print("SELECT public.pencil_dod_evaluate_county('liberty');")
    print("-- Expected: 7/10 (A,B,F fail), all others pass")
    print("```")


if __name__ == "__main__":
    main()
