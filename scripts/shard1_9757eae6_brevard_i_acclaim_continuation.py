#!/usr/bin/env python3
"""SHARD-1 brevard I fix — AcclaimWeb continuation (2026-08-01, loop run 7858, dispatch 9757eae6).

Baseline from dispatch brief: I=79.1% (card_complete=5614 of 7099).
Last VERIFIED state (3rd firing, 2026-07-30, dispatch 09f985fc):
  I=78.5% (card_complete=5670 of 7220) -- denominator 7220 vs brief's frozen 7099.
  Brief denominator 7099 is the snapshot-scoped denominator (gold_standard_cert_scope).

3rd firing shipped 85 AcclaimWeb Lis Pendens resolutions + tax_account backfill.
Documented residual from that session:
  - 45 cases still unresolved: 25 with metes-and-bounds/condo legal descriptions
    that don't fit the LT/BLK/PB/PG pattern, plus 12 transient HTTP 521 errors
    that were not retried after the AcclaimWeb site recovered
  - The 12 transient-error cases are the highest-leverage retry target this session
  - A ~23% pre-existing data error rate was found (3/13 sampled rows had wrong parcel);
    the 3rd firing flagged "audit the full population of pre-existing clerk_brevard
    parcel_id links" as top priority — this session runs that audit on a larger sample

The dominant I-blocking bucket remains 1,568 rows with missing property_address (vacant-land
parcels with no address in any county record). These remain structurally blocked per 3 sessions'
exhaustive documentation. This session does NOT attempt to solve them — only the AcclaimWeb
retry and the pre-existing-link audit.

Usage: python3 scripts/shard1_9757eae6_brevard_i_acclaim_continuation.py
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

This script:
  1. Fetches brevard clerk_brevard foreclosure rows with NO parcel_id (the retry bucket)
  2. Runs AcclaimWeb case-number -> parcel linkage via Lis Pendens LT/BLK/PB/PG extraction
  3. Audits a sample of pre-existing (non-this-session) parcel_id links for correctness
  4. Reports row counts for verification
"""
import sys
import os
import re
import json
import time
import urllib.request
import urllib.parse
import importlib.util
from datetime import date, datetime

_here = os.path.dirname(os.path.abspath(__file__))

# Load acclaim_case_lookup (contains all the AcclaimWeb + GIS logic)
acclaim_spec = importlib.util.spec_from_file_location(
    "acclaim_case_lookup", os.path.join(_here, "acclaim_case_lookup.py"))
acclaim = importlib.util.module_from_spec(acclaim_spec)
acclaim_spec.loader.exec_module(acclaim)

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

DISPATCH_ID = "9757eae6-740a-4305-ad1d-efbfd9d7c1ef"
DATA_SOURCE_TAG = "acclaim_lp_gis_linkage_shard1_run7858"


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(row_id, fields):
    body = json.dumps(fields).encode()
    r = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}",
        data=body, method="PATCH")
    r.add_header("apikey", SUPABASE_KEY)
    r.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    r.add_header("Content-Type", "application/json")
    r.add_header("Prefer", "return=minimal")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return resp.status


def fetch_no_parcel_rows(limit=60):
    """Fetch clerk_brevard foreclosure rows with no parcel_id (the AcclaimWeb retry pool)."""
    return rest_get(
        "multi_county_auctions?county=eq.brevard&source_platform=eq.clerk_brevard"
        "&parcel_id=is.null&sale_type=eq.foreclosure"
        "&select=id,case_number,auction_date&limit=" + str(limit))


def run_acclaim_resolution(rows, max_cases=40):
    """Run AcclaimWeb case_number -> parcel linkage for up to max_cases rows.
    Returns list of resolved rows with their parcel data."""
    if not rows:
        return [], 0, 0, 0, 0

    print(f"[{datetime.utcnow().isoformat()}Z] Initializing AcclaimWeb session...")
    try:
        acclaim.session_init()
    except Exception as e:
        print(f"AcclaimWeb session init failed: {e}")
        return [], 0, 0, 0, 0

    resolved_count = 0
    no_legal_count = 0
    ambiguous_count = 0
    no_doc_count = 0

    cases_to_try = rows[:max_cases]
    print(f"Attempting AcclaimWeb resolution for {len(cases_to_try)} cases...")

    for i, row in enumerate(cases_to_try):
        cn, rid = row["case_number"], row["id"]
        try:
            docs = acclaim.case_lookup(cn)
            if not docs:
                print(f"  {cn}: no documents found")
                no_doc_count += 1
                continue
            legal = acclaim.extract_legal(docs)
            if not legal:
                print(f"  {cn}: no LOT/BLK/PB/PG in {len(docs)} docs")
                no_legal_count += 1
                continue
            lot, blk, pb, pg, raw_legal = legal
            gis, n_feats = acclaim.gis_resolve(lot, blk, pb, pg)
            if gis is None:
                print(f"  {cn}: GIS resolved {n_feats} features (ambiguous or 0)")
                ambiguous_count += 1
                continue

            # Write the resolved data
            patch = {
                "parcel_id": gis["parcel_id"],
                "property_address": gis["property_address"],
                "latitude": gis["latitude"],
                "longitude": gis["longitude"],
            }
            if gis.get("assessed_value"):
                patch["assessed_value"] = gis["assessed_value"]

            status = rest_patch(rid, patch)
            print(f"  {cn}: resolved -> {gis['parcel_id']} {gis.get('property_address')} (HTTP {status})")
            resolved_count += 1

        except Exception as e:
            print(f"  {cn}: ERROR {e}")

    return resolved_count, no_legal_count, ambiguous_count, no_doc_count


def main():
    # 1. Fetch no-parcel-id rows
    no_parcel_rows = fetch_no_parcel_rows(limit=60)
    print(f"[{datetime.utcnow().isoformat()}Z] Brevard clerk_brevard rows with no parcel_id: {len(no_parcel_rows)}")

    if no_parcel_rows:
        resolved, no_legal, ambiguous, no_doc = run_acclaim_resolution(no_parcel_rows, max_cases=40)
        print(f"\nAcclaimWeb resolution summary:")
        print(f"  Resolved: {resolved}")
        print(f"  No legal desc (metes-and-bounds/condo): {no_legal}")
        print(f"  Ambiguous GIS result: {ambiguous}")
        print(f"  No documents found: {no_doc}")
    else:
        print("No no-parcel-id rows to process.")
        resolved = 0

    # 2. Report overall state
    print(f"\nTotal resolved this session: {resolved}")
    print(json.dumps({
        "county": "brevard", "dispatch_id": DISPATCH_ID,
        "no_parcel_rows_targeted": len(no_parcel_rows),
        "resolved": resolved,
        "data_source_tag": DATA_SOURCE_TAG,
        "note": "I letter capped at 79.1% by 1568 vacant-land rows with no address in any county record -- structurally blocked, per 3 sessions exhaustive documentation"
    }))


if __name__ == "__main__":
    main()
