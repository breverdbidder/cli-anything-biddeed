#!/usr/bin/env python3
"""GOLD STANDARD martin, case 26000209CAAXMX (brand-new gap row, session 2026-08-15).

Method: replicates the exact court.martinclerk.com QuickSearch -> DetailsSummary
AJAX flow + pamartinfl.gov real-property JSON API + geoweb.martin.fl.us ArcGIS
zoning point-in-polygon pattern documented in
GOLD_STANDARD_SHARD5_MARTIN_DISPATCH_32EF2B2A_SESSION_REPORT.md (Frondorf fix).

Case classification (via court.martinclerk.com/CourtCase.aspx/DetailsSummary/1375220):
  Case Type: REAL PROPERTY/MORT FORECL-NONHOME $50,001-$249,999
  Status: CLOSED
  Plaintiff: BAY AREA LENDING SERVICES LLC
  Defendants: ALDERMAN HOLDINGS LLLP, ALDERMAN JOSEPH M III, TENANTS IN POSSESSION
              UNKNOWN, BLUE COAST CONSTRUCTION INC, FAMILY POOLS INC,
              THE SANDPEBBLE BEACH CLUB CONDOMINIUM ASSOCIATION
  Foreclosure sale event: 9/22/2026 10:00 AM ONLINE -- matches DB auction_date exactly.

Parcel identification (pamartinfl.gov real-property JSON API, search=ALDERMAN HOLDINGS):
  total=1, single unambiguous match. AIN 3546, PIN 24-37-41-004-005-01030-3.
  Legal: "SANDPEBBLE CONDOMINIUM PHASE 5 OCEAN BLDG 5 UNIT 103" -- matches
  co-defendant "The Sandpebble Beach Club Condominium Association" exactly.
  Owner "ALDERMAN HOLDINGS LTD" matches defendant "ALDERMAN HOLDINGS LLLP"
  (same PO Box mailing address, entity-form variant).

Zoning (geoweb.martin.fl.us ArcGIS Administrative_Areas/Future_Landuse_Zoning/
MapServer/1 point-in-polygon query at PIN centroid X=-80.1891411504,
Y=27.2363963882): single unanimous feature OBJECTID 84485, ZONING=PUD-R.

Idempotent (only patches if parcel_id is still NULL). DB access: PostgREST only.
"""
import json
import os
import sys
import urllib.error
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

CASE_NUMBER = "26000209CAAXMX"
COUNTY = "martin"

PATCH = {
    "parcel_id": "24-37-41-004-005-01030-3",
    "property_address": "2491 NE OCEAN BLVD 103, HUTCHINSON ISLAND, FL",
    "city": "HUTCHINSON ISLAND",
    # zip intentionally omitted: pamartinfl.gov situs record has no SitusZip field,
    # only MailCityStateZip (Belle Glade FL 33430, the owner's mailing address --
    # not the property's zip). Not fabricating/inferring from reverse-geocode.
    "legal_description": "SANDPEBBLE CONDOMINIUM PHASE 5 OCEAN BLDG 5 UNIT 103",
    "assessed_value": 412660,
    "market_value": 412660,
    "latitude": 27.2363963882,
    "longitude": -80.1891411504,
    "property_type": "Residential Condo",
    "bcpao_enriched": True,
    "bcpao_url": "https://www.pamartinfl.gov/app/search/real-property?format=json&search=ALDERMAN%20HOLDINGS&searchField=all&exact=false",
    "assessed_value_source": "pamartinfl_gov_real_property_json_api:AIN3546",
    "plaintiff": "BAY AREA LENDING SERVICES LLC",
    "owner_name": "ALDERMAN HOLDINGS LLLP",
    "assigned_judge": "ROBY, WILLIAM L",
    "parity_status": "matched_clean",
    "parity_source": "court_martinclerk_quicksearch+pamartinfl_gov_real_property_json_api",
    "parity_confidence": 0.97,
    "parity_checked_at": None,  # set at runtime
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


def rest_post(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={**HEADERS, "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    from datetime import datetime, timezone
    dry_run = "--dry-run" in sys.argv

    rows = rest_get(
        f"multi_county_auctions?case_number=eq.{CASE_NUMBER}&county=eq.{COUNTY}"
        "&select=id,case_number,parcel_id,county")
    if len(rows) != 1:
        print(f"FAIL-LOUD: expected exactly 1 row for case={CASE_NUMBER}, found {len(rows)}")
        sys.exit(1)
    row = rows[0]
    row_id = row["id"]
    if row["parcel_id"] is not None:
        print(f"Already has parcel_id={row['parcel_id']!r} -- idempotent no-op, nothing to do.")
        return

    patch_body = dict(PATCH)
    patch_body["parity_checked_at"] = datetime.now(timezone.utc).isoformat()

    print(f"Patching {CASE_NUMBER} (id={row_id}) with: {json.dumps(patch_body, indent=2)}")
    if dry_run:
        print("--dry-run: not writing.")
        return

    result = rest_patch(f"multi_county_auctions?id=eq.{row_id}", patch_body)
    if len(result) != 1 or result[0].get("parcel_id") != PATCH["parcel_id"]:
        print(f"FAIL-LOUD: PATCH did not return expected row. Got: {result}")
        sys.exit(1)
    print(f"OK: patched multi_county_auctions row. parcel_id={result[0]['parcel_id']}")

    # Check parcel_zones idempotency, then insert
    existing_zone = rest_get(f"parcel_zones?parcel_id=eq.{PATCH['parcel_id']}&select=id")
    if existing_zone:
        print(f"parcel_zones already has a row for {PATCH['parcel_id']} -- skipping insert.")
        return

    zone_body = {
        "parcel_id": PATCH["parcel_id"],
        "jurisdiction_id": 1331,  # Unincorporated Martin County
        "zone_code": "PUD-R",
        "zone_name": "Planned Unit Development - Residential (PUD-R)",
        "source": (
            "https://geoweb.martin.fl.us/arcgis/rest/services/Administrative_Areas/"
            "Future_Landuse_Zoning/MapServer/1/query "
            f"(parcel={PATCH['parcel_id']}, X=-80.1891411504, Y=27.2363963882, "
            "OBJECTID=84485, ZONING=PUD-R)"
        ),
    }
    zone_result = rest_post("parcel_zones", zone_body)
    print(f"OK: inserted parcel_zones row: {zone_result}")


if __name__ == "__main__":
    main()
