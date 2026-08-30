#!/usr/bin/env python3
"""
wakulla_shard4_0bf31675_j_generator_real.py
Gold Standard shard-4 (dispatch 0bf31675), 2026-08-30

SCOPE: wakulla letter J (deal_complete). Live evaluator reports
deal_complete=45/52=86.5% (FAIL, canon requires >=95%), but that number is
INFLATED by a confirmed cross-county collision bug in
public.pencil_dod_evaluate_county's J EXISTS-join (joins bid_decisions to
multi_county_auctions on case_number ONLY, no county filter -- see
GOLD_STANDARD_J_EVALUATOR_CROSS_COUNTY_COLLISION_FINDING_20260830.md for the
full writeup and live query evidence). Case 25-CA-145 is counted as
deal_complete for wakulla via a bid_decisions row whose county_slug=
'jefferson' (a different case in a different county that happens to share
the case_number string, arv=170034). Excluding that collision, wakulla's
TRUE deal_complete is 44/52=84.6%.

TASK (per this session's explicit scope): attempt a REAL fix for the 8
case_numbers with no genuine wakulla-scoped bid_decisions row:
  2026-TXD-124, 2026-TXD-125, 2026-TXD-126, 2026-TXD-127,
  26-CA-19, 26-CA-31, 25-CA-9, 25-CA-145
Reused pattern: scripts/shard7_wakulla_j_generator_real.py (wakulla-specific
Shapira V14 XGBoost real-J pattern) and
scripts/shard8_run6080_suwannee_j_generator_real.py (CMA/ARV/ml_score/
factors shape). Not built from scratch.

RESULT: 0/8 fixed. All 8 have a genuine, documented reason they cannot be
scored without fabricating an input (see per-case detail below). No
bid_decisions rows were written this session. This is NOT a fabrication --
per HONESTY rules (blank > wrong), a case with no assessed_value/
market_value cannot be assigned a real ARV without inventing a number, and
judgment_amount (the foreclosure debt owed) is not a substitute for ARV --
they can diverge arbitrarily (e.g. an underwater or over-encumbered
property).

============================================================================
Live input-state check this session (multi_county_auctions, VERIFIED)
============================================================================

2026-TXD-124, -125, -126, -127 (tax_deed, auction_status='CANCELLED',
parity_status='CLERK_SSOT_CANCELLED'):
  - parcel_id: NULL (all 4)
  - property_address: NULL (all 4)
  - assessed_value / market_value: NULL (all 4)
  - lat/lon: NULL (all 4)
  This exact set was investigated THIS SAME SESSION by the wakulla letter-E
  task (scripts/wakulla_shard4_0bf31675_e_txd124_127_parcel_probe.py):
  5 avenues probed (wakullaclerk.org guessed-PDF pattern -- soft-404 all 4;
  wakullaclerk.com/LandmarkWeb -- connection refused/timeout, live outage;
  myfloridacounty.com and civitek OCRS -- require browser automation not
  available; mywakullapa.com -- ECONNRESET), 0/4 parcel_ids recovered.
  No new avenue exists for the J task beyond what E already exhausted --
  without a parcel_id/address, there is no property to compute an ARV for
  at all, so J is unreachable for these 4 regardless of value-source
  availability. SKIPPED (no underlying data).

25-CA-9, 26-CA-19, 26-CA-31, 25-CA-145 (foreclosure, all 4 have real
parcel_id + property_address + judgment_amount + lat/lon, confirmed live
this session):
  - assessed_value: NULL (all 4)
  - market_value: NULL (all 4)
  Both reference generators (shard7_wakulla_j_generator_real.py's real_arv()
  and shard8_run6080_suwannee_j_generator_real.py's real_arv()) compute ARV
  strictly as GREATEST(assessed_value, market_value) or the first non-null
  of the two -- with both null, no real ARV formula in this pipeline's
  established pattern can run. judgment_amount was explicitly NOT
  substituted (foreclosure judgment amounts are the debt+fees owed, not an
  appraised property value -- using it as ARV would be inventing a value
  estimate, not reading one).

============================================================================
Avenues attempted this session to source a real assessed/market value
============================================================================

1. FL GIO Statewide Cadastral FeatureServer (the proven source used by
   scripts/ingest_county.py for county-expansion parcel ingestion,
   CO_NO=75 for wakulla per live fl_counties query):
     https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/
     Florida_Statewide_Cadastral/FeatureServer/0/query
   Exact-parcel_id query (4 attempts, one per target PARCEL_ID) returned
   HTTP 200 with features_found=0 for all 4 -- our stored dashed
   PARCEL_ID format (e.g. "00-00-075-262-10242-B02") does not match
   whatever raw string format FL GIO's PARCEL_ID field actually uses for
   wakulla, so an exact-match WHERE clause finds nothing. A broader
   CO_NO=75-only sample query and an address-LIKE query (run earlier this
   session to discover the real format) both TIMED OUT (curl -m 25, HTTP
   000) -- this reproduces the exact failure mode already documented as a
   known issue in scripts/ingest_county.py's own comments ("Use OBJECTID
   range approach since WHERE CO_NO=X times out on count"). Not retried
   further per this session's one-attempt-per-approach cost-discipline
   rule; a future session should use the OBJECTID-range pagination
   ingest_county.py already implements to discover wakulla's real
   PARCEL_ID format without hitting the count-query timeout.

2. Wakulla County Property Appraiser search (search.mywakullapa.com):
     curl -sI returned no response (empty/connection issue).
     Independently reproduces the E-task's same-session ECONNRESET finding
     against the same host.

3. qpublic.schneidercorp.com (statewide Schneider GIS portal used by many
   FL county appraisers): HTTP 403 (blocked), no AppID/LayerID known for
   wakulla specifically, would require discovering the right AppID first
   even if unblocked.

CONCLUSION: no real, cited assessed_value or market_value source was
reachable this session for any of the 4 foreclosure cases. Per HONESTY
rules (blank > wrong), ZERO bid_decisions rows were written for these 4.
This ceiling should be treated as infrastructure-blocked (FL GIO cadastral
timeout on wakulla CO_NO=75 queries is a documented, pre-existing issue),
not permanently unrecoverable -- a future session with working FL GIO
pagination (OBJECTID range approach, per ingest_county.py's own workaround)
or browser automation for mywakullapa.com/qpublic should retry.

Evaluator (read-only RPC, before AND after -- unchanged since zero writes
were made to bid_decisions this session):
  pencil_dod_evaluate_county('wakulla').J = {"pass": false,
  "detail": "deal_complete=45 (triangle + two-arm CMA + ml_score + max_bid)",
  "metric": 86.5}
  TRUE corrected metric (excluding the documented case_number collision on
  25-CA-145, computed by hand, NOT written to any table): 44/52 = 84.6%.
  See GOLD_STANDARD_J_EVALUATOR_CROSS_COUNTY_COLLISION_FINDING_20260830.md.

Env (read-only in this script): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = probe completed (regardless of find/no-find), 1 = fatal error
"""

import json
import os
import sys

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

TARGET_CASES = [
    "2026-TXD-124", "2026-TXD-125", "2026-TXD-126", "2026-TXD-127",
    "26-CA-19", "26-CA-31", "25-CA-9", "25-CA-145",
]

FORECLOSURE_CASES_WITH_PARCEL = {
    "25-CA-9": "00-00-075-262-10242-B02",
    "26-CA-19": "00-00-073-335-10187-025",
    "26-CA-31": "13-4S-02W-000-01923-000",
    "25-CA-145": "06-3S-01W-243-04301-039",
}

FL_GIO_BASE = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
    "Florida_Statewide_Cadastral/FeatureServer/0/query"
)
WAKULLA_CO_NO = 75


def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def fetch_current_state():
    cases_in = ",".join(TARGET_CASES)
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
        headers=sb_headers(),
        params={
            "county": "eq.wakulla",
            "case_number": f"in.({cases_in})",
            "select": "case_number,parcel_id,property_address,assessed_value,"
                      "market_value,judgment_amount,latitude,longitude,"
                      "auction_status,parity_status",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def probe_fl_gio_by_parcel(parcel_id: str) -> dict:
    try:
        r = requests.get(
            FL_GIO_BASE,
            params={
                "where": f"CO_NO={WAKULLA_CO_NO} AND PARCEL_ID='{parcel_id}'",
                "outFields": "PARCEL_ID,JV,LND_VAL,TOT_LVG_AR,PHY_ADDR1",
                "f": "json",
            },
            timeout=25,
        )
        data = r.json()
        feats = data.get("features", [])
        return {"parcel_id": parcel_id, "http_status": r.status_code, "features_found": len(feats)}
    except requests.RequestException as e:
        return {"parcel_id": parcel_id, "error": str(e)}


def check_existing_bid_decisions():
    cases_in = ",".join(TARGET_CASES)
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/bid_decisions",
        headers=sb_headers(),
        params={"case_number": f"in.({cases_in})", "select": "id,case_number,county_slug,arv"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def evaluate_county() -> dict:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {"error": "SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set"}
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        headers=sb_headers(), json={"p_county": "wakulla"}, timeout=30,
    )
    return r.json()


def main():
    print(">>> wakulla shard-4 (0bf31675) letter J real-fix attempt -- 8 target cases\n")

    print("--- Current multi_county_auctions state for 8 target cases ---")
    for row in fetch_current_state():
        print(f"  {json.dumps(row, default=str)}")

    print("\n--- Existing bid_decisions rows (case_number match, ANY county) ---")
    existing = check_existing_bid_decisions()
    for row in existing:
        flag = " <-- CROSS-COUNTY COLLISION (county_slug != wakulla)" if row.get("county_slug") != "wakulla" else ""
        print(f"  {json.dumps(row, default=str)}{flag}")
    if not existing:
        print("  (none)")

    print("\n--- FL GIO cadastral probe for the 4 foreclosure cases with real parcel_id ---")
    for case, pid in FORECLOSURE_CASES_WITH_PARCEL.items():
        result = probe_fl_gio_by_parcel(pid)
        print(f"  {case}: {json.dumps(result)}")

    print("\n--- Evaluator (read-only, before=after, zero bid_decisions writes made) ---")
    result = evaluate_county()
    print(json.dumps(result.get("J", "N/A"), default=str))

    total = result.get("auctions_total")
    j_detail = result.get("J", {}).get("detail", "")
    print(f"\nLive J metric: {result.get('J', {}).get('metric')} ({j_detail}), auctions_total={total}")
    print("True corrected metric excluding the 25-CA-145 collision (hand-computed, not written): 44/52 = 84.6%")

    print(
        "\nCONCLUSION: 0/8 cases fixed. 4 TXD cases have no underlying data "
        "(parcel_id/address/value all NULL, already exhaustively probed by "
        "this session's E task). 4 CA cases have real parcel_id/address but "
        "no assessed_value/market_value; FL GIO cadastral times out on "
        "wakulla CO_NO=75 queries (documented pre-existing issue), "
        "mywakullapa.com is unreachable, qpublic returns 403. No "
        "bid_decisions rows written. Reported as UNKNOWN per HONESTY rules "
        "-- blank > wrong."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
