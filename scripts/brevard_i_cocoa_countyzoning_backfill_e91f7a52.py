#!/usr/bin/env python3
"""Brevard county, letter I (property card completeness) -- NEW lever this
session (dispatch e91f7a52): resolve the residual "zoning(unlinked)" bucket
for rows that already have a complete address+geo+value card but whose
parcel_id has ZERO row in parcel_zones, using two sources never tried by
prior brevard-I sessions:

  1. City of Cocoa's own hosted ArcGIS Online zoning feature service
     (discovered live this session via https://www.cocoafl.org -> "Planning
     & Zoning" page link to cocoacity.maps.arcgis.com, then an ArcGIS Online
     content search for "zoning cocoa"):
       https://services1.arcgis.com/Tex1uhbqnOZPx6qT/arcgis/rest/services/
       Cocoa_Zoning_with_Split_Lots/FeatureServer/0/query
     Keyed directly by TaxAcct (an attribute on the feature, not just a
     join key) -- covers parcels inside Cocoa city limits that are absent
     from Brevard County's own unincorporated parcel_zones population.

  2. Brevard County's OWN zoning polygon layer (as opposed to the parcel
     BASE layer already exhausted by every prior brevard-I session):
       https://gis.brevardfl.gov/gissrv/rest/services/
       Planning_Development/Zoning_WKID2881/MapServer/0/query
     This is a genuinely different ArcGIS service from
     Base_Map/Parcel_New_WKID2881/MapServer/5 (the parcel attribute layer
     every prior session queried by TaxAcct). Zoning_WKID2881 has no
     TaxAcct field at all -- it is a bare ZONING/DENSCAP polygon layer,
     usable only via point-in-polygon against a parcel's existing lat/lng.
     None of the 6a9e3c3a/a96722e9/35db0a28/3ce988ac/10bc7bc6 prior
     sessions ever queried this specific service; 10bc7bc6 queried Palm
     Bay, Titusville, and Melbourne's MUNICIPAL zoning layers for a
     different (now-resolved) 29-row batch but never the county's own
     unincorporated zoning layer.

SCOPE (live, 2026-08-24, via PostgREST against $SUPABASE_URL, canonical
pencil_dod_evaluate_county() card_rows population, county=brevard):
  13 rows fail I ONLY on the zoning-linkage clause (parcel_id present or
  absent) while everything else needed for the row is already resolvable:
    - 11 have address+geo+value ALREADY complete and fail purely because
      their parcel_id/tax_account has ZERO row in parcel_zones
      (v_zoning_gold_standard_card zone_code effectively NULL-by-absence).
    - 2 (05-2024-CA-053818-XXCA-BC, 05-2025-CA-039830-XXCA-BC) have
      parcel_id NULL entirely and their stored property_address is the
      DEFENDANT'S mailing address (Miami/Largo, not Brevard) -- out of
      scope for this script, which only ever writes a zone into an
      *existing*, already-verified parcel_zones-eligible row. Left
      untouched; documented as a separate residual (needs the AcclaimWeb
      legal-description lookup mechanism, not a zoning source).

Of the 11 zoning-only rows:
  - 7 resolved this session (parcel_zones INSERT, real, sourced data):
      2423749 (341 WOODS LAKE DR, COCOA)      -> county Zoning_WKID2881,
                                                  point-in-polygon, RU-1-11
      2421364 (1050 N FISKE BLVD 103, COCOA)  -> Cocoa Zoning FeatureService,
                                                  TaxAcct match, RU-2-15
      2421365 (1050 N FISKE BLVD 104, COCOA)  -> same, RU-2-15
      2421379 (1050 N FISKE BLVD 402, COCOA)  -> same, RU-2-15
      2421426 (1050 N FISKE BLVD 1203, COCOA) -> same, RU-2-15
      2421427 (1050 N FISKE BLVD 1204, COCOA) -> same, RU-2-15
      2421305 (1046 DIXON BLVD, COCOA)        -> same, split-lot parcel --
                                                  Cocoa's own layer returns
                                                  TWO zone polygons for this
                                                  TaxAcct (C-N Neighborhood
                                                  Commercial AND RU-1-7
                                                  Single-family Residential).
                                                  Both are genuine, sourced
                                                  values (not a guess) --
                                                  inserted BOTH as separate
                                                  parcel_zones rows (matches
                                                  this table's existing
                                                  1-parcel-to-many-zones
                                                  shape used elsewhere for
                                                  split lots); the I-gate
                                                  EXISTS-style join only
                                                  needs zone_code IS NOT
                                                  NULL for at least one row,
                                                  so this correctly flips
                                                  the card to complete
                                                  without picking a single
                                                  "winning" zone by guess.
  - 4 CONFIRMED still blocked, re-verified live this session (unchanged
    from the 10bc7bc6 session's finding -- these tax accounts return ZERO
    features from ALL of: county Base_Map parcel layer, county
    Zoning_WKID2881 point-in-polygon, Titusville zoning, Melbourne zoning):
      2724998 (1711 DIXON BLVD 228, case 170965)
      2423944 (1711 DIXON BLVD 246, case 180428)
      2532539 (981 S ORLANDO AVE, case 180341)
      2832622 (418 OAKLAND AVE, case 180404)
    These are retired/re-platted TaxAcct numbers not present in ANY live
    GIS system of record checked (county or all 3 neighboring
    municipalities). Left untouched -- not fabricated.

FABRICATION GUARD: only writes a zone_code that came directly from a live
GIS feature attribute (ZONING/Zoning field). No inference, no nearest-
neighbor, no "most common zone in area" substitution.

Usage:
  python3 scripts/brevard_i_cocoa_countyzoning_backfill_e91f7a52.py            # dry-run
  python3 scripts/brevard_i_cocoa_countyzoning_backfill_e91f7a52.py --apply    # write live

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
dispatch: e91f7a52 (brevard-I gold-standard session, 2026-08-24)
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

COCOA_ZONING = ("https://services1.arcgis.com/Tex1uhbqnOZPx6qT/arcgis/rest/"
                 "services/Cocoa_Zoning_with_Split_Lots/FeatureServer/0/query")
COUNTY_ZONING = ("https://gis.brevardfl.gov/gissrv/rest/services/"
                  "Planning_Development/Zoning_WKID2881/MapServer/0/query")

# The 13-row candidate set (case_number, tax_acct, lat, lon), pulled live
# this session from the canonical pencil_dod_evaluate_county() card_rows
# population (county=brevard) filtered to rows whose ONLY missing I-clause
# is the zoning-linkage EXISTS check. See module docstring for provenance.
CANDIDATES = [
    ("05-2025-CA-063757-XXCA-BC", "2423749", 28.3624330250908, -80.7675189517414),
    ("170965",                     "2724998", 28.3724930283935, -80.7576280968748),
    ("180341",                     "2532539", 28.300741,        -80.6093315),
    ("180404",                     "2832622", 28.0949517,       -80.5756077),
    ("180428",                     "2423944", 28.3724930283935, -80.7576280968748),
    ("260054",                     "2421364", None, None),
    ("260055",                     "2421365", None, None),
    ("260057",                     "2421379", None, None),
    ("260058",                     "2421305", None, None),
    ("260060",                     "2421427", None, None),
    ("260061",                     "2421426", None, None),
]

COCOA_JURISDICTION_ID = 5  # public.jurisdictions row: name='Cocoa', county='Brevard'


def sb_headers():
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}


def fetch_row_ids():
    """Look up multi_county_auctions.id for each candidate case_number
    (needed only for reporting; parcel_zones writes are keyed by
    parcel_id/tax_account, not auction id)."""
    cases = [c[0] for c in CANDIDATES]
    inlist = ",".join(cases)
    url = (f"{SB_URL}/rest/v1/multi_county_auctions?case_number=in.({inlist})"
           f"&select=id,case_number,parcel_id")
    req = urllib.request.Request(url, headers=sb_headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.loads(r.read().decode())
    return {r["case_number"]: r for r in rows}


def cocoa_zoning_lookup(tax_accts):
    where = "TaxAcct IN (" + ",".join(tax_accts) + ")"
    params = {"where": where, "outFields": "TaxAcct,Zoning,ZoneDesc",
              "returnGeometry": "false", "f": "json"}
    url = COCOA_ZONING + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    out = {}
    for feat in d.get("features", []):
        a = feat["attributes"]
        tax = str(a["TaxAcct"])
        out.setdefault(tax, []).append((a.get("Zoning"), a.get("ZoneDesc")))
    return out


def county_zoning_point(lat, lon):
    params = {"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint",
              "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
              "outFields": "ZONING,DENSCAP", "returnGeometry": "false", "f": "json"}
    url = COUNTY_ZONING + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
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
        headers={**sb_headers(), "Content-Type": "application/json",
                 "Prefer": "return=minimal"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        print(f"  INSERT ERROR TaxAcct={tax_account}: {e.code} {e.read().decode()[:300]}",
              file=sys.stderr)
        return e.code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                     help="Write resolved rows live (default: dry-run)")
    args = ap.parse_args()

    row_ids = fetch_row_ids()
    print(f"Fetched {len(row_ids)}/{len(CANDIDATES)} candidate rows from multi_county_auctions")

    cocoa_accts = [c[1] for c in CANDIDATES if c[2] is None]  # the 260054-260061 batch
    print(f"\n=== City of Cocoa zoning FeatureService lookup ({len(cocoa_accts)} TaxAccts) ===")
    cocoa_matches = cocoa_zoning_lookup(cocoa_accts)

    resolved = []
    blocked = []

    for case_number, tax_acct, lat, lon in CANDIDATES:
        row = row_ids.get(case_number)
        if row is None:
            blocked.append((case_number, tax_acct, "case_number not found in multi_county_auctions"))
            continue
        if tax_acct in cocoa_matches:
            zones = cocoa_matches[tax_acct]
            for zone_code, zone_name in zones:
                resolved.append((case_number, tax_acct, zone_code, zone_name,
                                  "cocoa_arcgis_online_zoning"))
            print(f"{case_number} TaxAcct={tax_acct}: RESOLVED via Cocoa GIS -> {zones}")
            continue
        if lat is not None and lon is not None:
            zone_code = county_zoning_point(lat, lon)
            if zone_code:
                resolved.append((case_number, tax_acct, zone_code, None,
                                  "brevard_county_zoning_wkid2881"))
                print(f"{case_number} TaxAcct={tax_acct}: RESOLVED via county Zoning_WKID2881 -> {zone_code}")
                continue
        blocked.append((case_number, tax_acct,
                         "no feature in Cocoa GIS or county Zoning_WKID2881 point-in-polygon"))
        print(f"{case_number} TaxAcct={tax_acct}: BLOCKED (no source resolves this TaxAcct)")

    print(f"\n=== SUMMARY: resolved={len(resolved)} rows to insert, blocked={len(blocked)} ===")
    for b in blocked:
        print("  BLOCKED:", b)

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
