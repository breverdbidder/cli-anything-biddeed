#!/usr/bin/env python3
"""GOLD STANDARD shard-5, martin, dispatch 32ef2b2a-3ee0-4ac9-8209-5ec91a35cf5c (2026-08-10).

martin E/I gap = 6 rows with parcel_id IS NULL (35/41 = 85.4%). Prior sessions
(5+ since 2026-07-18, most recently 2026-08-09 dispatch 643e111c) confirmed 3
of the 6 are a genuine dead end (case_classification_code=NON_REAL_PROPERTY,
timeshare/personal property). The other 3 (26000299CAAXMX, 25000496CAAXMX,
25000102CAAXMX) were re-investigated this session:

  - court.martinclerk.com QuickSearch/DetailsSummary AJAX (anonymous, no
    CAPTCHA -- a genuinely new access path vs. the previously-exhausted
    Landmark Web / courthouse-CAPTCHA routes) returned real case metadata:
    all 3 are actually CLOSED foreclosure cases with real plaintiff/defendant
    names, contradicting the "pre-judgment $0.00 stub" read of the
    RealForeclose calendar item (which is just stale/incomplete there).
  - www.pamartinfl.gov's real-property search backend
    (/app/search/real-property?format=json&search=<name>) is a plain
    curl-able JSON API (found via its own webpack bundle, no browser
    needed). Searching by defendant/plaintiff surname:
      * FRONDORF -> single unambiguous match. Deed history (Grantor
        "FRONDORF, BONNIE A & FRONDORF, WILLI[AM]" -> Grantee "FRONDORF,
        NATALIE I") matches case 26000299CAAXMX's parties (plaintiff William
        Frondorf as PR for Estate of Dorothy Miller; defendant Natalie
        Frondorf) exactly. VERIFIED live against the API a second time
        independently before writing (see below).
      * ONEILL/O'NEILL and WISNIESKI (case 25000102CAAXMX) -> no confident
        match; multiple same-surname owners with none pairing the 4 named
        parties, current-owner-of-record data doesn't reach back to a
        deceased original borrower's estate. Left NULL, not guessed.
      * DE LA BAHIA CONDOMINIUM ASSOCIATION (case 25000496CAAXMX) -> HOA
        co-defendant, not the unit owner; not attempted (owner name unknown).

This script patches ONLY case 26000299CAAXMX. The other 5 gap rows are
untouched -- E/I move from 35/41 (85.4%) to 36/41 (87.8%), still FAIL under
the 95% threshold, honestly reported as partial progress, not a flip to PASS.

Source of truth for every field: pamartinfl.gov real-property JSON API,
single record, AIN 29570 / PIN 18-38-41-009-002-00070-8. Idempotent (only
patches if parcel_id is still NULL). DB access: PostgREST only.

Usage: python3 scripts/shard5_32ef2b2a_martin_e_i_frondorf_fix.py [--dry-run]
"""
import json
import os
import sys
import urllib.error
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

ROW_ID = "aacd4b1b-775d-4f2a-92c6-edf1c2a268fd"
CASE_NUMBER = "26000299CAAXMX"

# VERIFIED live 2026-08-10 against
# https://www.pamartinfl.gov/app/search/real-property?format=json&search=FRONDORF&searchField=all&exact=false
# (total=1, single unambiguous record)
PATCH = {
    "parcel_id": "18-38-41-009-002-00070-8",
    "property_address": "3078 SW VIRGINIA AVE, PALM CITY, FL- 34990",
    "city": "PALM CITY",
    "zip": "34990",
    "legal_description": "PALM HEIGHTS LOT 7 & N1/2 OF LOT 8 BLK 2",
    "assessed_value": 103842,
    "market_value": 254510,
    "latitude": 27.1674734166,
    "longitude": -80.2829634839,
    "property_type": "Single Family",
    "bcpao_enriched": True,
    "bcpao_url": "https://www.pamartinfl.gov/app/search/real-property?format=json&search=FRONDORF&searchField=all&exact=false",
    "assessed_value_source": "pamartinfl_gov_real_property_json_api:AIN29570",
}

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
        f"multi_county_auctions?id=eq.{ROW_ID}&case_number=eq.{CASE_NUMBER}"
        "&select=id,case_number,parcel_id,county")
    if len(rows) != 1:
        print(f"FAIL-LOUD: expected exactly 1 row for id={ROW_ID}, found {len(rows)}")
        sys.exit(1)
    row = rows[0]
    if row["county"] != "martin":
        print(f"FAIL-LOUD: expected county=martin, got {row['county']}")
        sys.exit(1)
    if row["parcel_id"] is not None:
        print(f"Already has parcel_id={row['parcel_id']!r} -- idempotent no-op, nothing to do.")
        return

    print(f"Patching {CASE_NUMBER} (id={ROW_ID}) with: {json.dumps(PATCH, indent=2)}")
    if dry_run:
        print("--dry-run: not writing.")
        return

    result = rest_patch(f"multi_county_auctions?id=eq.{ROW_ID}", PATCH)
    if len(result) != 1 or result[0].get("parcel_id") != PATCH["parcel_id"]:
        print(f"FAIL-LOUD: PATCH did not return expected row. Got: {result}")
        sys.exit(1)
    print(f"OK: patched 1 row. parcel_id={result[0]['parcel_id']}")


if __name__ == "__main__":
    main()
