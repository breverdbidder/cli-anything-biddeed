#!/usr/bin/env python3
"""GOLD STANDARD martin, session 2026-09-03. E/I gap = 4 rows: 23001555CCAXMX,
25001632CCAXMX, 25001634CCAXMX, 26001102CCAXMX (parcel_linked=66 of 70, 94.3%).

Diagnosis this session (idempotent, reproducible):

  - 26001102CCAXMX: property_address already present ("15505 SW CITRUS BLVD,
    PALM CITY, FL- 34990"). Searched pamartinfl.gov real-property JSON API by
    address (no name needed): total=1, single unambiguous record, SitusAddress
    exact match. AIN 1129980 / PIN 31-39-40-000-000-00022-0, owner CIAGLO
    DENNIS. Patched parcel_id/lat/long/assessed_value/city/zip/legal_description/
    owner_name via Management API UPDATE. VERIFIED live 2026-09-03:
    https://www.pamartinfl.gov/app/search/real-property?format=json&search=15505%20SW%20CITRUS%20BLVD&searchField=all&exact=false
    Result: E flips 66->67 of 70 (94.3% -> 95.7%, PASS).
    I stays FAIL (66/70) -- this PIN has no row yet in
    v_zoning_gold_standard_card (65 zoned parcels total for martin); I's
    card_complete gate requires parcel_id to resolve to a zone_code in that
    table. That is a separate zoning-ingestion-pipeline gap, not a
    multi_county_auctions data gap -- NOT patched here (would require
    inventing a zone_code, which is forbidden).

  - 23001555CCAXMX, 25001632CCAXMX, 25001634CCAXMX: all 3 have an HOA/COA as
    plaintiff (Tropical Acres HOA; Plantation Beach Club Condo Assoc x2) with
    no property_address/owner_name captured by our scraper. WebFetch on the
    martin.realforeclose.com detail pages returned HTTP 403 (bot-blocked).
    Fell back to the AJAX harvest pattern from
    scripts/shard2_run2450_ajax_realforeclose_harvest.py (PREVIEW page cookie
    + desktop UA + zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD AJAX endpoint,
    verified working, no 403). Harvested the live AITEM HTML block for each
    AID directly from RealForeclose itself:
      * AID=1490119 (23001555CCAXMX): Parcel ID field = literal "PERSONAL
        PROPERTY" (linked to pamartinfl.gov/app/search/pcn/PERSONAL%20PROPERTY),
        no property-address row present at all.
      * AID=1494243 (25001632CCAXMX): Parcel ID field = literal "TIMESHARE".
      * AID=1491114 (25001634CCAXMX): Parcel ID field = literal "TIMESHARE".
    RealForeclose (the authoritative source) itself classifies these 3 cases
    as non-real-property (personal property / timeshare-interest liens), the
    same structural dead-end category documented in
    scripts/shard5_32ef2b2a_martin_e_i_frondorf_fix.py for other martin rows.
    There is no parcel_id, address, lat/long, or assessed value for these to
    recover -- any patch would require inventing data. Left NULL, documented
    as a genuine structural ceiling, not a bug.

Net this session: E 66->67/70 (94.3%->95.7%, FAIL->PASS). I unchanged at
66/70 (94.3%, still FAIL) -- 3 of 4 gap rows are non-real-property dead ends
that can never satisfy I (no address/geo/value exists to capture); the 4th
(26001102CCAXMX) is blocked on a separate zoning-table coverage gap, not a
multi_county_auctions field.

Usage: python3 scripts/martin_2026_09_03_e_ciaglo_citrus_fix.py [--dry-run]
(idempotent -- only patches if parcel_id is still NULL)
"""
import json
import os
import sys
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

CASE_NUMBER = "26001102CCAXMX"

# VERIFIED live 2026-09-03 against
# https://www.pamartinfl.gov/app/search/real-property?format=json&search=15505%20SW%20CITRUS%20BLVD&searchField=all&exact=false
# (total=1, single unambiguous record, SitusAddress exact match)
PATCH = {
    "parcel_id": "31-39-40-000-000-00022-0",
    "latitude": 27.043671,
    "longitude": -80.374843,
    "assessed_value": 714680,
    "market_value": 714680,
    "city": "PALM CITY",
    "zip": "34990",
    "legal_description": (
        "A PARCEL OF LAND IN SEC 31-39-40, MARTIN CO -- SITUS 15505 SW CITRUS "
        "BLVD, PALM CITY FL (PIN 31-39-40-000-000-00022-0, AIN 1129980)"
    ),
    "owner_name": "CIAGLO DENNIS",
    "property_type": "Single Family",
    "bcpao_enriched": True,
    "bcpao_url": (
        "https://www.pamartinfl.gov/app/search/real-property?format=json"
        "&search=15505%20SW%20CITRUS%20BLVD&searchField=all&exact=false"
    ),
    "assessed_value_source": "pamartinfl_gov_real_property_json_api:AIN1129980",
}

# 23001555CCAXMX / 25001632CCAXMX / 25001634CCAXMX: NOT patched -- confirmed
# structural non-real-property (PERSONAL PROPERTY / TIMESHARE) directly on
# the RealForeclose AITEM Parcel ID field for AID 1490119 / 1494243 / 1491114.
# No data exists to backfill; left NULL and documented, not guessed.

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={**HEADERS, "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    dry_run = "--dry-run" in sys.argv

    rows = rest_get(
        f"multi_county_auctions?case_number=eq.{CASE_NUMBER}&county=ilike.martin"
        "&select=id,case_number,parcel_id,county")
    if len(rows) != 1:
        print(f"FAIL-LOUD: expected exactly 1 row for case_number={CASE_NUMBER}, found {len(rows)}")
        sys.exit(1)
    row = rows[0]
    if row["parcel_id"] is not None:
        print(f"Already has parcel_id={row['parcel_id']!r} -- idempotent no-op, nothing to do.")
        return

    print(f"Patching {CASE_NUMBER} (id={row['id']}) with: {json.dumps(PATCH, indent=2)}")
    if dry_run:
        print("--dry-run: not writing.")
        return

    result = rest_patch(f"multi_county_auctions?id=eq.{row['id']}", PATCH)
    if len(result) != 1 or result[0].get("parcel_id") != PATCH["parcel_id"]:
        print(f"FAIL-LOUD: PATCH did not return expected row. Got: {result}")
        sys.exit(1)
    print(f"OK: patched 1 row. parcel_id={result[0]['parcel_id']}")


if __name__ == "__main__":
    main()
