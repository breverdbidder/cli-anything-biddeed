#!/usr/bin/env python3
"""
gold_standard_shard4_marion_i_zone_linkage_backfill.py

GOLD STANDARD marion letter I fix (dispatch 7d59c973-434c-4b8c-a699-e820f9093c39).

BACKGROUND (VERIFIED live 2026-08-24 via pencil_dod_evaluate_county('marion')):
  I: card_complete=563 of 595 (94.6%), need >=566/595=95%.

The prior-stage diagnosis for this dispatch identified 32 gap rows in the
595-row card_rows set. Of those, 21 have a real numeric parcel_id: 2 were
already excluded by an earlier script (gold_standard_marion_i_geo_zone_backfill_d979d926.py)
because their Marion GIS ZONE1 codes (R1A, PD05) have no corresponding row in
zoning_districts under jurisdiction_id=1403 -- inserting them would silently
fail letter G. The remaining 19 numeric-parcel rows were never targeted by any
prior marion-I script and have zero existing parcel_zones rows (re-verified
live in this session, empty result).

Re-verified live in THIS session (2026-08-24) before writing:
  - All 19 target multi_county_auctions rows already have property_address,
    latitude/longitude, and assessed_value populated -- ONLY the zone linkage
    (parcel_zones row -> zone_code) is missing. So this script writes to
    parcel_zones only, no lat/lon/address/value patch needed.
  - Queried Marion County Property Appraiser's own ArcGIS FeatureServer
    (https://gis.marionfl.org/public/rest/services/General/Parcels/MapServer/0/query)
    live via WHERE ALT_Key IN (...): all 19 matched, ASSD_VAL agrees with our
    DB's assessed_value to the cent for every row, confirming correct parcel
    match.
  - zoning_districts under jurisdiction_id=1403 currently has exactly 9 codes:
    A1, B2, PUD, RPUD, R1, R2, R3, R4, MH. 18 of the 19 target ZONE1 codes
    fall in this set. Parcel 3584317's ZONE1='R1A' does NOT -- same unmapped-
    code wall hit by the two previously-excluded parcels (1259924 R1A, 2013290
    PD05). Per BLANK > WRONG, 3584317 is skipped, not inserted with a
    fabricated/guessed mapping.

WRITE PERFORMED (fail-loud: parsed>0 AND written==0 raises):
  INSERT into parcel_zones (parcel_id=ALT_Key, zone_code=ZONE1 trimmed,
  jurisdiction_id=1403 [Unincorporated Marion County -- the only jurisdiction
  with populated zoning_districts/zone_standards for this GIS source, per the
  prior script's hard-won correction], source=
  'marion_gis_arcgis_7d59c973', effective_date=today) for the 18 fixable
  parcel_ids. Verified live pre-write that none of these 19 parcel_ids
  currently exist in parcel_zones -- zero conflict risk, plain INSERT.

NOT WRITTEN / OUT OF SCOPE (per prior-stage diagnosis, unchanged):
  - 3584317 (ZONE1='R1A', unmapped under jurisdiction 1403) -- left BLANK.
  - 9 rows with parcel_id IS NULL entirely (would need a docket lookup to
    first establish a parcel_id).
  - 2 rows with parcel_id='MULTIPLE PARCELS' (structurally unresolvable to a
    single parcel).
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

MARION_GIS_URL = (
    "https://gis.marionfl.org/public/rest/services/General/Parcels/MapServer/0/query"
)

TARGET_PARCEL_IDS = [
    "731641", "243710", "3518888", "631396", "954781", "1810175", "644064",
    "3915151", "1662443", "916005", "1290198", "767468", "874469", "1681065",
    "3584317", "2950030", "3944429", "2751827", "1148456",
]

DEFAULT_JURISDICTION = 1403  # Unincorporated Marion County (see docstring)
SOURCE_TAG = "marion_gis_arcgis_7d59c973"

# Zone codes confirmed present in zoning_districts under jurisdiction_id=1403
# (re-verified live 2026-08-24). Codes NOT in this set must be skipped
# (BLANK > WRONG) rather than inserted with an unmapped code that would
# silently fail letter G's FAR/pk1000/density coverage.
KNOWN_MAPPED_ZONE_CODES = {"A1", "B2", "MH", "PUD", "R1", "R2", "R3", "R4", "RPUD"}


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def fetch_gis(parcel_ids):
    id_list = ",".join(str(int(p)) for p in parcel_ids)
    params = {
        "where": f"ALT_Key IN ({id_list})",
        "outFields": "PARCEL,ALT_Key,SITUS_1,ASSD_VAL,TOT_VAL,ZONE1,ZONE2,ZONE3",
        "outSR": "4326",
        "returnGeometry": "false",
        "f": "json",
    }
    url = MARION_GIS_URL + "?" + urllib.parse.urlencode(params)
    d = http_get(url)
    if "error" in d:
        raise RuntimeError(f"Marion GIS error: {d['error']}")
    return d.get("features", [])


def get_existing_parcel_zone_ids(parcel_ids):
    ids = ",".join(f'"{urllib.parse.quote(p)}"' for p in parcel_ids)
    url = f"{SB}/rest/v1/parcel_zones?parcel_id=in.({ids})&select=parcel_id"
    req = urllib.request.Request(url, headers=H, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        rows = json.loads(resp.read().decode())
    return {r["parcel_id"] for r in rows}


def insert_parcel_zone(parcel_id, zone_code, jurisdiction_id, source):
    url = f"{SB}/rest/v1/parcel_zones"
    payload = {
        "parcel_id": parcel_id,
        "zone_code": zone_code,
        "jurisdiction_id": jurisdiction_id,
        "source": source,
        "effective_date": date.today().isoformat(),
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=H, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read().decode())
            return len(rows)
    except urllib.error.HTTPError as exc:
        print(f"FAIL insert parcel_zones {parcel_id}: {exc.code} {exc.read().decode()}", file=sys.stderr)
        return 0


def main():
    existing = get_existing_parcel_zone_ids(TARGET_PARCEL_IDS)
    if existing:
        print(f"Already in parcel_zones (skip, idempotent re-run): {sorted(existing)}")

    feats = fetch_gis(TARGET_PARCEL_IDS)
    print(f"GIS matched: {len(feats)} of {len(TARGET_PARCEL_IDS)}")

    gis_by_pid = {str(f["attributes"]["ALT_Key"]): f for f in feats}

    parsed = 0
    written = 0
    skipped_unmapped = []
    unmatched = []

    for pid in TARGET_PARCEL_IDS:
        feat = gis_by_pid.get(pid)
        if not feat:
            unmatched.append(pid)
            continue
        parsed += 1
        if pid in existing:
            print(f"SKIP {pid}: parcel_zones row already exists")
            continue
        zone_code = (feat["attributes"].get("ZONE1") or "").strip()
        if zone_code and zone_code in KNOWN_MAPPED_ZONE_CODES:
            n = insert_parcel_zone(pid, zone_code, DEFAULT_JURISDICTION, SOURCE_TAG)
            if n:
                written += 1
                print(f"OK zone {pid}: zone_code={zone_code} jurisdiction_id={DEFAULT_JURISDICTION}")
            else:
                print(f"NO-OP/FAIL zone {pid}")
        elif zone_code:
            skipped_unmapped.append((pid, zone_code))
            print(f"SKIP {pid}: zone_code={zone_code} not mapped under jurisdiction 1403 (BLANK > WRONG)")
        else:
            print(f"SKIP {pid}: ZONE1 blank")

    print(f"\nParsed (GIS-matched): {parsed}")
    print(f"parcel_zones rows written: {written}")
    print(f"Unmapped zone codes (left blank): {skipped_unmapped}")
    print(f"Unmatched (no GIS feature): {unmatched}")

    if parsed > 0 and written == 0:
        raise RuntimeError("FAIL-LOUD: parsed>0 but zero writes performed.")


if __name__ == "__main__":
    main()
