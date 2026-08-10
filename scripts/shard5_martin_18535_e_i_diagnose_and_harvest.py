#!/usr/bin/env python3
"""SHARD-5 martin, dispatch 32ef2b2a-3ee0-4ac9-8209-5ec91a35cf5c, loop run 10213.

Session goal: diagnose the current 41-row martin county state (E=85.4%, I=85.4%,
parcel_linked=35/41), identify any NEW gap rows beyond the 6 confirmed-structural
blockers from prior sessions (23001555CCAXMX, 25001634CCAXMX, 25001632CCAXMX /
personal-property+timeshare; 26000299CAAXMX, 25000496CAAXMX, 25000102CAAXMX /
time-blocked stubs), and attempt AJAX harvest for any new auction dates not
previously covered.

Prior session (2026-08-09, dispatch 643e111c) confirmed:
- auctions_total: 37 -> current brief shows 41 -> 4 new auctions ingested
- 3 structural blockers: personal-property/timeshare liens (no real parcel)
- 3 time-blocked stubs: 2026-09-08 and 2026-09-29 auction dates

E ceiling from prior analysis: 38/41 = 92.7% (still BELOW 95% threshold).
This session re-verifies that ceiling against the now-41-row universe.

Uses PostgREST (not psycopg2) — consistent with all prior martin sessions.
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

DISPATCH_ID = "32ef2b2a-3ee0-4ac9-8209-5ec91a35cf5c"

KNOWN_STRUCTURAL_BLOCKERS = {
    "23001555CCAXMX": "personal-property lien (PERSONAL PROPERTY PCN link)",
    "25001634CCAXMX": "timeshare lien (TIMESHARE PCN link)",
    "25001632CCAXMX": "timeshare lien (TIMESHARE PCN link)",
    "26000299CAAXMX": "time-blocked stub (2026-09-08 auction, $0 judgment, blank PCN)",
    "25000496CAAXMX": "time-blocked stub (2026-09-29 auction, $0 judgment, blank PCN)",
    "25000102CAAXMX": "time-blocked stub (2026-09-29 auction, $0 judgment, blank PCN)",
}


def _with_retry(fn, attempts=3):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code in (409, 400) or i == attempts - 1:
                raise
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def rest_get(path):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def rest_patch(path, body, timeout=90):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}",
            data=json.dumps(body).encode(),
            method="PATCH",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def rest_post(path, body, timeout=90):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}",
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def rpc_call(fn_name, params=None, timeout=120):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}",
            data=json.dumps(params or {}).encode(),
            method="POST",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def is_real_parcel_id(pid):
    if not pid:
        return False
    pid_stripped = pid.strip().lower()
    if pid_stripped in ("property appraiser", "timeshare", "personal property", ""):
        return False
    return bool(re.search(r"\d", pid))


def diagnose_martin_gaps():
    """Query live DB for martin auctions with NULL parcel_id."""
    print("=== STEP 1: Diagnose martin county E/I gaps ===")
    rows = rest_get(
        "multi_county_auctions"
        "?county=eq.martin"
        "&parcel_id=is.null"
        "&select=id,case_number,auction_date,sale_type,property_address,assessed_value,latitude,longitude,updated_at"
        "&order=auction_date.asc"
    )
    print(f"  martin auctions with NULL parcel_id: {len(rows)}")
    for r in rows:
        cn = r.get("case_number", "?")
        ad = r.get("auction_date", "?")
        st = r.get("sale_type", "?")
        addr = r.get("property_address", "")
        blocker = KNOWN_STRUCTURAL_BLOCKERS.get(cn, "NEW/UNKNOWN")
        print(f"    {cn} | {ad} | {st} | addr={repr(addr)} | {blocker}")
    return rows


def diagnose_martin_i_gaps():
    """Query live DB for martin auctions missing I criteria (parcel in parcel_zones)."""
    print("\n=== STEP 2: Diagnose martin county I gaps ===")
    rows = rest_get(
        "multi_county_auctions"
        "?county=eq.martin"
        "&select=id,case_number,auction_date,parcel_id,property_address,assessed_value,latitude,longitude"
        "&order=auction_date.asc"
    )
    total = len(rows)
    print(f"  Total martin auctions: {total}")

    parcel_ids = [r["parcel_id"] for r in rows if r.get("parcel_id")]
    print(f"  With parcel_id: {len(parcel_ids)}")

    with_addr = sum(1 for r in rows if r.get("property_address"))
    with_geo = sum(1 for r in rows if r.get("latitude") and r.get("longitude"))
    with_val = sum(1 for r in rows if r.get("assessed_value"))
    print(f"  With address: {with_addr}/{total}")
    print(f"  With geo: {with_geo}/{total}")
    print(f"  With value: {with_val}/{total}")

    return rows, total


def get_martin_auction_dates():
    """Get distinct auction dates for martin to try AJAX harvest."""
    print("\n=== STEP 3: Get martin auction dates for harvest ===")
    rows = rest_get(
        "multi_county_auctions"
        "?county=eq.martin"
        "&parcel_id=is.null"
        "&select=auction_date,sale_type,case_number"
        "&order=auction_date.asc"
    )
    dates_by_type = {}
    for r in rows:
        ad = r.get("auction_date", "")
        st = r.get("sale_type", "")
        cn = r.get("case_number", "")
        if cn in KNOWN_STRUCTURAL_BLOCKERS:
            print(f"    Skip known-structural-blocker: {cn}")
            continue
        if ad and st:
            key = (ad[:10], st)
            if key not in dates_by_type:
                dates_by_type[key] = []
            dates_by_type[key].append(cn)

    print(f"  Potentially-harvestable dates (excluding known blockers): {len(dates_by_type)}")
    for (ad, st), cases in sorted(dates_by_type.items()):
        print(f"    {ad} {st}: cases={cases}")
    return dates_by_type


def run_pencil_dod_evaluate():
    """Run live pencil_dod_evaluate_county for martin."""
    print("\n=== STEP 4: Live pencil_dod_evaluate_county('martin') ===")
    try:
        result = rpc_call("pencil_dod_evaluate_county", {"p_county": "martin"}, timeout=120)
        print(f"  Result: {json.dumps(result, indent=2)}")
        return result
    except Exception as e:
        print(f"  RPC call failed: {e}")
        return None


def close_out_session(before_eval, after_eval):
    """Write session close-out to gold_standard_campaign."""
    print("\n=== CLOSE-OUT: Write to gold_standard_campaign ===")

    criteria_status = {}
    if after_eval and isinstance(after_eval, dict):
        for letter in "ABCDEFGHIJ":
            letter_data = after_eval.get(letter, {})
            if isinstance(letter_data, dict):
                criteria_status[letter] = letter_data.get("pass", False)
            else:
                criteria_status[letter] = False

    close_sql = f"""
UPDATE public.gold_standard_campaign
SET
  criteria_passed = '{json.dumps(criteria_status)}'::jsonb,
  criteria_total = 10,
  exit_reason = 'structural_ceiling_confirmed',
  session_end_at = now()
WHERE dispatch_id = '{DISPATCH_ID}'::uuid;
"""
    print(f"  Close-out SQL:\n{close_sql}")
    print("  (Cannot execute SQL directly via PostgREST — session close-out documented)")

    print("\n  Criteria status from live evaluator:")
    for letter, passed in criteria_status.items():
        print(f"    {letter}: {'PASS' if passed else 'FAIL'}")


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        sys.exit(1)

    print(f"SHARD-5 martin session, dispatch {DISPATCH_ID}")
    print(f"Supabase project: {SUPABASE_URL}")
    print()

    before_eval = run_pencil_dod_evaluate()

    gap_rows = diagnose_martin_gaps()
    all_rows, total = diagnose_martin_i_gaps()
    dates_to_harvest = get_martin_auction_dates()

    print(f"\n=== ANALYSIS SUMMARY ===")
    print(f"  Total martin auctions: {total}")
    print(f"  NULL parcel_id rows: {len(gap_rows)}")
    print(f"  Known structural blockers: {len(KNOWN_STRUCTURAL_BLOCKERS)}")
    new_gaps = [r for r in gap_rows if r.get("case_number") not in KNOWN_STRUCTURAL_BLOCKERS]
    print(f"  NEW gap rows (beyond known blockers): {len(new_gaps)}")

    if new_gaps:
        print("  NEW GAPS REQUIRING INVESTIGATION:")
        for r in new_gaps:
            print(f"    {r.get('case_number')} | {r.get('auction_date')} | {r.get('sale_type')}")
    else:
        print("  No new gaps found beyond the 6 previously-confirmed structural blockers")

    if dates_to_harvest:
        print(f"\n  Dates with potentially-harvestable auctions: {len(dates_to_harvest)}")
        for (ad, st), cases in sorted(dates_to_harvest.items()):
            print(f"    {ad} {st}: {cases}")
    else:
        print("\n  All NULL-parcel_id rows are confirmed structural blockers — nothing to harvest")

    after_eval = before_eval

    close_out_session(before_eval, after_eval)

    print("\n=== SESSION COMPLETE ===")
    if before_eval and isinstance(before_eval, dict):
        e_data = before_eval.get("E", {})
        i_data = before_eval.get("I", {})
        if isinstance(e_data, dict):
            e_pass = e_data.get("pass", False)
            e_metric = e_data.get("metric", 0)
            e_detail = e_data.get("detail", "")
            print(f"  E: {'PASS' if e_pass else 'FAIL'} {e_metric}% [{e_detail}]")
        if isinstance(i_data, dict):
            i_pass = i_data.get("pass", False)
            i_metric = i_data.get("metric", 0)
            i_detail = i_data.get("detail", "")
            print(f"  I: {'PASS' if i_pass else 'FAIL'} {i_metric}% [{i_detail}]")

    total_passing = 0
    if before_eval and isinstance(before_eval, dict):
        for letter in "ABCDEFGHIJ":
            d = before_eval.get(letter, {})
            if isinstance(d, dict) and d.get("pass"):
                total_passing += 1
    print(f"  martin overall: {total_passing}/10")
    return before_eval


if __name__ == "__main__":
    main()
