#!/usr/bin/env python3
"""Gold Standard, county=brevard, letter I (property card completeness).

Dispatch: 2026-08-26 fresh brevard-I diagnose session (this session).

DIAGNOSIS (this session, VERIFIED live via pencil_dod_evaluate_county +
direct PostgREST pagination reproducing the exact evaluator SQL from
supabase/migrations/20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql):

  Live baseline: I card_complete=6265 of 7300 (85.8%), needs >=95%
  (~6935 of 7300) to PASS -- a ~670-row gap.

  Full row-level classification of every one of the 1035 failing rows
  (recomputed independently and reconciled EXACTLY against the live
  evaluator's 6265/7300 -- see session notes) breaks down as:
    977 rows: property_address IS NULL (dominant reason, ~94% of the gap)
     41 rows: parcel_id IS NULL entirely (no lever without new legal-desc
               source -- AcclaimWeb lot/block regex already exhausted per
               scripts/brevard_i_clerk_platform_legal_backfill_e91f7a52.py
               and scripts/gold_standard_shard1_35db0a28_brevard_i_gis_backfill.py)
      6 rows: address+geo+value ALL present, ONLY the zoning-linkage EXISTS
               clause fails (parcel_id/tax_account has zero row in
               v_zoning_gold_standard_card with zone_code IS NOT NULL)

  Of the 977 address-missing rows (976 numeric TaxAcct + 1 formatted
  PARCEL_ID), a full live re-query of Brevard County's own GIS parcel base
  layer (Base_Map/Parcel_New_WKID2881/MapServer/5, the same source proven
  in every prior brevard-I session) found:
    - 788 distinct TaxAccts: STREET_NAME='UNKNOWN'/blank in the county's
      OWN system of record -- confirmed genuine vacant-land ceiling,
      consistent with dispatch 35db0a28 (2026-08-10) and 3ce988ac
      (2026-08-14) sessions, which found the identical pattern at ~97-99%
      UNKNOWN rate on their own snapshots of this same bucket.
    - 50 distinct TaxAccts: zero features returned at all (retired/
      re-platted account numbers not in the live layer) -- same finding
      as the 35db0a28 session ("50 of the 897 distinct parcel_ids returned
      zero ArcGIS features at all").
    - 1 distinct TaxAcct (2209912): STREET_NAME='CONFIDENTIAL' (Address
      Confidentiality Program) -- real GIS value but not a writable
      property_address per this task's fabrication guard.
  FL DOR Statewide Cadastral (ALT_KEY point/IN-list queries) and bcpao.us
  were NOT re-attempted this session: both are already documented dead
  ends with fresh evidence from dispatch a96722e9 (2026-08-14) --
  DOR ALT_KEY point/IN-list queries return HTTP 400 or time out; bcpao.us
  is Cloudflare-challenged (HTTP 403) from this environment. Re-running
  either against the same negative-signal accounts would not be a new
  lever. THE 977-ROW ADDRESS-MISSING BUCKET IS THEREFORE A CONFIRMED,
  RE-VERIFIED STRUCTURAL CEILING -- not touched by this script.

  Of the 6 zoning-linkage-only rows, 4 (case_numbers 180428, 180341,
  180404, 170965 / TaxAccts 2423944, 2532539, 2832622, 2724998) are the
  EXACT 4 cases already documented as permanently blocked (zero features
  in county Base_Map, county Zoning_WKID2881, AND all 3 municipal zoning
  layers checked) by
  scripts/brevard_i_cocoa_countyzoning_backfill_e91f7a52.py -- re-verified
  live this session, unchanged, left untouched.

  The remaining 2 rows are NEW (never targeted by any prior brevard-I
  script by case_number):
    case_number=05-2026-CA-011747-XXCA-BC  TaxAcct=2408900
    case_number=05-2025-CC-018279-XXCC-BC  TaxAcct=2411339
  Both already have real property_address/geo/value (only zoning-link is
  missing). This script resolves the zone for both via Brevard County's
  own Planning_Development/Zoning_WKID2881/MapServer/0 point-in-polygon
  query against each parcel's Base_Map centroid (same 2-step method as
  the e91f7a52 session), then INSERTs into parcel_zones.

RESULT (this session): 2 rows resolved and inserted. Both TaxAccts:
  2408900 (826 MALLARD RD, COCOA) -> ZONING=RU-1-13 (Suburban Estate/
    single-family) via county Zoning_WKID2881 point-in-polygon.
  2411339 (3712 WINDSOR DR, COCOA) -> ZONING=EU (Estate Use) via same.
  (Cocoa's own ArcGIS Online Cocoa_Zoning_with_Split_Lots FeatureService
  was checked FIRST for both TaxAccts and returned zero features -- these
  2 parcels are inside unincorporated county zoning jurisdiction despite
  a Cocoa postal city, consistent with Brevard's postal-vs-jurisdiction
  mismatch documented in earlier sessions.)

FABRICATION GUARD: only writes a zone_code that came directly from a live
ArcGIS feature attribute (ZONING field). No inference, no fallback value.

RESIDUAL: the 670-row gap is a genuine data ceiling this session, not a
gap this session failed to close. 977 address-missing rows are re-
confirmed (3rd independent session, exact same finding) as either
STREET_NAME=UNKNOWN vacant land or retired TaxAccts in Brevard's own GIS
-- writing a fabricated address would violate the hard fabrication-guard
rule. 41 no-parcel-id rows need a legal-description source already proven
unparseable (condo unit descriptions) or unresolvable (no LT/BLK/PB/PG
pattern). Closing this gap further requires either a fundamentally new
Brevard data source not yet discovered, or accepting non-addressed vacant
land as a legitimately non-card-complete category at the evaluator level
(out of scope for a data-backfill session).

Usage:
  python3 scripts/gold_standard_brevard_i_countyzoning_2row_20260826.py            # dry-run
  python3 scripts/gold_standard_brevard_i_countyzoning_2row_20260826.py --apply    # write live

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
assert SB_URL and SB_KEY, "SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

BASE_PARCEL = ("https://gis.brevardfl.gov/gissrv/rest/services/"
               "Base_Map/Parcel_New_WKID2881/MapServer/5/query")
COCOA_ZONING = ("https://services1.arcgis.com/Tex1uhbqnOZPx6qT/arcgis/rest/"
                 "services/Cocoa_Zoning_with_Split_Lots/FeatureServer/0/query")
COUNTY_ZONING = ("https://gis.brevardfl.gov/gissrv/rest/services/"
                  "Planning_Development/Zoning_WKID2881/MapServer/0/query")

COCOA_JURISDICTION_ID = 5  # public.jurisdictions row: name='Cocoa', county='Brevard'

# The 2 NEW candidate rows this session (case_number, TaxAcct), confirmed
# live to already have property_address/geo/value complete and to fail
# I ONLY on the zoning-linkage EXISTS clause.
CANDIDATES = [
    ("05-2026-CA-011747-XXCA-BC", "2408900"),
    ("05-2025-CC-018279-XXCC-BC", "2411339"),
]


def sb_headers():
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def already_zone_linked(tax_account):
    url = (f"{SB_URL}/rest/v1/v_zoning_gold_standard_card?select=tax_account"
           f"&county=eq.brevard&zone_code=not.is.null&tax_account=eq.{tax_account}")
    return len(get(url, sb_headers())) > 0


def base_parcel_centroid(tax_account):
    params = {"where": f"TaxAcct={tax_account}",
              "outFields": "TaxAcct,PARCEL_ID,STREET_NUMBER,STREET_NAME,STREET_TYPE,CITY",
              "returnGeometry": "true", "outSR": "4326", "f": "json"}
    d = get(BASE_PARCEL + "?" + urllib.parse.urlencode(params))
    feats = d.get("features", [])
    if len(feats) != 1:
        return None
    f = feats[0]
    ring = (f.get("geometry") or {}).get("rings", [[]])[0]
    if not ring:
        return None
    lon = sum(p[0] for p in ring) / len(ring)
    lat = sum(p[1] for p in ring) / len(ring)
    return lat, lon, f["attributes"]


def cocoa_zoning_lookup(tax_account):
    params = {"where": f"TaxAcct={tax_account}", "outFields": "TaxAcct,Zoning,ZoneDesc",
              "returnGeometry": "false", "f": "json"}
    d = get(COCOA_ZONING + "?" + urllib.parse.urlencode(params))
    return d.get("features", [])


def county_zoning_point(lat, lon):
    params = {"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint",
              "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
              "outFields": "ZONING,DENSCAP", "returnGeometry": "false", "f": "json"}
    d = get(COUNTY_ZONING + "?" + urllib.parse.urlencode(params))
    feats = d.get("features", [])
    if not feats:
        return None
    return feats[0]["attributes"].get("ZONING")


def sb_insert_parcel_zone(tax_account, jurisdiction_id, zone_code, zone_name, source):
    body = json.dumps({
        "parcel_id": tax_account,
        "tax_account": tax_account,
        "jurisdiction_id": jurisdiction_id,
        "zone_code": zone_code,
        "zone_name": zone_name,
        "source": source,
    }).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/parcel_zones", data=body, method="POST",
        headers={**sb_headers(), "Content-Type": "application/json", "Prefer": "return=minimal"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        print(f"  INSERT ERROR TaxAcct={tax_account}: {e.code} {e.read().decode()[:300]}", file=sys.stderr)
        return e.code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write resolved rows live (default: dry-run)")
    args = ap.parse_args()

    resolved = []
    for case_number, tax_acct in CANDIDATES:
        if already_zone_linked(tax_acct):
            print(f"{case_number} TaxAcct={tax_acct}: already zone-linked, skipping")
            continue

        cocoa_feats = cocoa_zoning_lookup(tax_acct)
        if cocoa_feats:
            for feat in cocoa_feats:
                a = feat["attributes"]
                resolved.append((case_number, tax_acct, a.get("Zoning"), a.get("ZoneDesc"),
                                  "cocoa_arcgis_online_zoning"))
                print(f"{case_number} TaxAcct={tax_acct}: RESOLVED via Cocoa GIS -> {a.get('Zoning')}")
            continue

        centroid = base_parcel_centroid(tax_acct)
        if centroid is None:
            print(f"{case_number} TaxAcct={tax_acct}: BLOCKED (no unique feature in Base_Map parcel layer)")
            continue
        lat, lon, attrs = centroid
        zone_code = county_zoning_point(lat, lon)
        if zone_code:
            resolved.append((case_number, tax_acct, zone_code, None, "brevard_county_zoning_wkid2881"))
            print(f"{case_number} TaxAcct={tax_acct}: RESOLVED via county Zoning_WKID2881 -> {zone_code} "
                  f"(addr={attrs.get('STREET_NUMBER')} {attrs.get('STREET_NAME')} {attrs.get('STREET_TYPE')}, "
                  f"{attrs.get('CITY')})")
        else:
            print(f"{case_number} TaxAcct={tax_acct}: BLOCKED (no feature in Cocoa GIS or county Zoning_WKID2881)")

    print(f"\n=== SUMMARY: resolved={len(resolved)}/{len(CANDIDATES)} ===")

    if args.apply:
        applied = 0
        for case_number, tax_acct, zone_code, zone_name, source in resolved:
            status = sb_insert_parcel_zone(tax_acct, COCOA_JURISDICTION_ID, zone_code, zone_name, source)
            print(f"  APPLIED INSERT TaxAcct={tax_acct} zone_code={zone_code} status={status}")
            if status in (200, 201, 204):
                applied += 1
        print(f"\nTOTAL applied: {applied}/{len(resolved)}")
    else:
        print("\nDRY-RUN: re-run with --apply to INSERT the resolved rows into parcel_zones.")


if __name__ == "__main__":
    main()
