#!/usr/bin/env python3
"""GOLD STANDARD gadsden I -- zone the 3 newly-parcel-linked unincorporated rows.

CONTEXT: this session's companion script
(scripts/gold_standard_gadsden_ei_courtscribe_backfill.py) resolved gadsden E
to 100% (65/65 parcel_linked) via CourtScribe address discovery. I stayed at
90.8% (59/65) because pencil_dod_evaluate_county's I criterion additionally
requires the parcel_id to resolve a zone_code via v_zoning_gold_standard_card
(parcel_zones join), not just multi_county_auctions.parcel_id being non-null.

Of the 6 newly-linked parcels, 3 sit in incorporated municipalities (Havana,
Midway, Gretna) -- prior sessions (dispatch 47974994, both firings) already
established there is NO discoverable per-parcel municipal zoning source for
any Gadsden municipality, so these 3 are correctly left unzoned (dead end,
not re-attempted here). The other 3 sit in unincorporated county land
(fl_parcels.phy_city='COUNTY'):

  26000063CA / MDB Investments -- parcel_id 2-09-3N-4W-0000-00330-0000
    (Glory Rd) -- point-in-polygon query against Gadsden_FLUM layer 2 (Ag2,
    ZONE='AG') -- ONE match, no cross-layer overlap (checked layers 1/2/3/10/13).
  25000900CA / Hills -- parcel_id 2-34-3N-3W-3330-00000-0020 (Mary Brown Rd)
    -- layer 13 (RuralRes, ZONE='RR') -- ONE match.
  25000952CA / Derico -- parcel_id 2-33-3N-2W-0258-0000A-0370 (Sugarmill Ct)
    -- layer 13 (RuralRes, ZONE='RR') -- ONE match.

Source: https://services8.arcgis.com/N3lCn6dEKCL6LidU/arcgis/rest/services/
Gadsden_FLUM/FeatureServer (same service used by the prior gadsden G session,
dispatch 47974994, migration 20260719_gold_standard_shard13_gadsden_uninc_
rr_ag_verified.sql -- this script extends the SAME jurisdiction (id=1474,
"Unincorporated Gadsden County") and the SAME zoning_districts rows (RR/AG-2,
already present, not re-inserted), only adding 3 new parcel_zones rows.
Confirmed the FLUM layer's "AG" ZONE value for layer 2 == the existing AG-2
zoning_districts.code by cross-checking a known AG-2-tagged parcel
(2-07-3N-2W-0000-00133-0100) resolves to the same ZONE='AG' from layer 2.

Does NOT touch zoning_districts/zone_standards (no new district codes) or any
existing parcel_zones row (only inserts 3 new rows for previously-unlinked
parcels). G is unaffected (its density/far/pk1000 aggregate already includes
these categories; adding more RR/AG-2 rows cannot regress a metric that is
already 100.0 with far/pk1000 both inapplicable=null per the existing
confidence_score=0.85 caveat).

Usage: python3 scripts/gold_standard_gadsden_i_flum_zone_3rows.py [--dry-run]
"""
from __future__ import annotations
import json
import os
import sys
import urllib.error
import urllib.request

JURISDICTION_ID = 1474  # Unincorporated Gadsden County
DRY_RUN = "--dry-run" in sys.argv

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# (parcel_id, zone_code, zone_name, future_land_use, source)
ROWS = [
    (
        "2-09-3N-4W-0000-00330-0000", "AG-2", "Agriculture-2", "Agriculture-2",
        "gadsden_flum_arcgis_layer2_ag2_pip_verified_20260813:glory_rd_mary_brown_sugarmill_3row_backfill",
    ),
    (
        "2-34-3N-3W-3330-00000-0020", "RR", "Rural Residential", "Rural Residential",
        "gadsden_flum_arcgis_layer13_ruralres_pip_verified_20260813:glory_rd_mary_brown_sugarmill_3row_backfill",
    ),
    (
        "2-33-3N-2W-0258-0000A-0370", "RR", "Rural Residential", "Rural Residential",
        "gadsden_flum_arcgis_layer13_ruralres_pip_verified_20260813:glory_rd_mary_brown_sugarmill_3row_backfill",
    ),
]


def rest_get(path):
    req = urllib.request.Request(f"{BASE}/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def rest_post(table, data):
    url = f"{BASE}/{table}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={**HEADERS, "Prefer": "return=representation"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main():
    log = print
    inserted = 0

    for parcel_id, zone_code, zone_name, flu, source in ROWS:
        log(f"\n=== {parcel_id} -> {zone_code} ===")
        existing = rest_get(f"parcel_zones?parcel_id=eq.{parcel_id}&jurisdiction_id=eq.{JURISDICTION_ID}")
        if existing:
            log(f"NOTE: parcel_zones row already exists for {parcel_id}, skipping: {existing}")
            continue

        # confirm the target zoning_districts row exists (RR/AG-2 already seeded by prior session)
        d = rest_get(f"zoning_districts?jurisdiction_id=eq.{JURISDICTION_ID}&code=eq.{zone_code}")
        if len(d) != 1:
            log(f"FAIL-LOUD: expected exactly 1 zoning_districts row for code={zone_code}, got {len(d)}. Aborting this row.")
            continue

        payload = {
            "parcel_id": parcel_id,
            "jurisdiction_id": JURISDICTION_ID,
            "zone_code": zone_code,
            "zone_name": zone_name,
            "future_land_use": flu,
            "source": source,
        }
        log(f"About to INSERT parcel_zones: {json.dumps(payload, indent=2)}")

        if DRY_RUN:
            log("DRY RUN -- no write performed.")
            continue

        status, body = rest_post("parcel_zones", payload)
        log(f"INSERT result: HTTP {status}")
        if status not in (200, 201):
            log(f"FAIL-LOUD: write did not succeed cleanly for {parcel_id}. Body: {body}")
            continue
        log(f"Wrote row for {parcel_id}: {body}")

        check = rest_get(f"parcel_zones?parcel_id=eq.{parcel_id}&jurisdiction_id=eq.{JURISDICTION_ID}&select=parcel_id,zone_code")
        log(f"Post-write verify: {check}")
        if not check or check[0]["zone_code"] != zone_code:
            log(f"FAIL-LOUD: post-write verification does not show expected zone_code for {parcel_id}.")
            continue
        log(f"VERIFIED: {parcel_id} now has zone_code={zone_code} in parcel_zones.")
        inserted += 1

    log(f"\n=== SUMMARY: {inserted}/{len(ROWS)} parcel_zones rows inserted ===")


if __name__ == "__main__":
    main()
