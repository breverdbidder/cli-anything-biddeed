"""Gold Standard shard-1 continuation (prior dispatch 62c0b00c identified the
candidate set; this session executes the fix), brevard county, letter I
(property card completeness).

SCOPE: the prior 2026-08-30 session (62c0b00c) identified 5 rows in
multi_county_auctions that already have a complete card (property_address +
lat/lng + assessed_value) but whose parcel_id had ZERO row in
zoning_assignments / parcel_zones at all (confirmed live at session start,
both tables, both zero rows for all 5 parcel_ids):

  case_number  parcel_id  property_address
  260133       2001122    0 UNKNOWN (28.7217721, -80.9134172 -- far NW
                                       Brevard, near Mims/Scottsmoor)
  260197       2411122    118 VANGUARD CIR, COCOA, FL-32926
  260213       2317272    367 MAC ARTHUR CIR, COCOA, FL-32927
  260214       2400286    4815 SHERRY LN, COCOA, FL-32926
  260215       2400440    4824 LAKE SUPERIOR DR, COCOA, FL-32926

SOURCES TRIED (in the order specified by the dispatch brief), all via
live point-in-polygon query against the row's own lat/lng:

  1. City of Cocoa's own hosted ArcGIS Online zoning feature service
     (https://services1.arcgis.com/Tex1uhbqnOZPx6qT/arcgis/rest/services/
     Cocoa_Zoning_with_Split_Lots/FeatureServer/0/query) -- tried BOTH a
     TaxAcct attribute match (IN clause) AND a geometry-based
     point-in-polygon query for all 5 points. ZERO features returned for
     ALL 5 by EITHER method -- confirms none of these 5 parcels are inside
     Cocoa city limits, despite 4/5 having a Cocoa postal address.

  2. Brevard County's own unincorporated zoning polygon layer
     (https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/
     Zoning_WKID2881/MapServer/0/query, point-in-polygon, outFields=
     ZONING,DENSCAP, inSR=4326) -- ALL 5 resolved, each with exactly ONE
     unambiguous feature (verified via a feature-count check to guard
     against the "conflicting sources" case in the dispatch brief -- no
     conflict was possible since Cocoa returned zero features for every
     point):
       2001122 -> ZONING=GU     (General Use / Government)
       2411122 -> ZONING=TR-1   (Transitional Residential-1)
       2317272 -> ZONING=TR-1
       2400286 -> ZONING=TR-1
       2400440 -> ZONING=TRC-1  (Transitional Residential Commercial-1)
     Note gis.brevardfl.gov's bare `/arcgis/rest/services` root now 302s to
     the county's marketing page -- the working live path for this specific
     zoning MapServer is under `/gissrv/rest/services/...`, distinct from
     the `/arcgis/rest/services/Base_Map/Parcel_New_WKID2881/...` parcel
     BASE layer used by earlier brevard-I sessions (10bc7bc6, 35db0a28).

FABRICATION GUARD: only wrote a zone_code that came directly from a live
ArcGIS feature attribute (ZONING field) for that exact lat/lon, with
exactly one feature returned (no ambiguity, no picking a "closest"
polygon, no copying a neighboring parcel).

WRITES APPLIED (this session, both live-verified via REST):

  1. public.parcel_zones (id 876157-876161) -- THIS is the table
     v_zoning_gold_standard_card / pencil_dod_evaluate_county() letter-I
     actually reads (confirmed live: the view's `parcel_id` column holds a
     BCPAO strap-format string and `tax_account` holds the plain numeric
     account; the evaluator's `zc` CTE matches
     `multi_county_auctions.parcel_id` against EITHER `zc.parcel_id` OR
     `zc.tax_account`). Wrote parcel_id=tax_account=<the 7-digit number>
     (no strap available this session), jurisdiction_id=13
     ("Unincorporated Brevard County" per public.jurisdictions),
     zone_code from the live query, source='gissrv:Zoning_WKID2881'.

  2. public.zoning_assignments (ids 9677085-9677089) -- kept in sync for
     ecosystem consistency (this table is also read directly elsewhere,
     e.g. indian_river/sebastian rows observed live this session). Same
     parcel_id/zone_code/lat/lon values, jurisdiction='unincorporated'
     (matching the exact existing convention for brevard county-sourced
     Zoning_WKID2881 rows, confirmed by inspecting 5 pre-existing rows
     with zone_source='gissrv:Zoning_WKID2881' before writing), county=
     'brevard', co_no=15, zone_confidence='point_in_polygon'.

VERIFICATION (live, this session):
  - v_zoning_gold_standard_card?tax_account=in.(2001122,2411122,2317272,
    2400286,2400440): all 5 now return, each with zone_code IS NOT NULL,
    county='brevard'.
  - pencil_dod_evaluate_county('brevard') letter I:
      BEFORE: card_complete=6316 of 7348, metric=86.0, pass=false
      AFTER:  card_complete=6321 of 7348, metric=86.0, pass=false
    (+5 card_complete rows, exactly the 5 parcels fixed; displayed metric
    still rounds to 86.0% at 1 decimal place because 5/7348 ~= 0.07pp --
    still FAIL, needs >=95%, i.e. ~6981 of 7348. This is an honest partial
    fix, not a resolution of letter I.)

Residual: letter I remains FAIL. This session closed exactly the 5-row gap
it was scoped to close and did not attempt the much larger remaining
zoning-unlinked / missing-address population (out of scope for this
dispatch; see the 999b87f8/62c0b00c/c62ab4fb prior-session docstrings for
that residual's characterization).

dispatch: 62c0b00c (execution session, 2026-08-31)
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

COCOA_ZONING = ("https://services1.arcgis.com/Tex1uhbqnOZPx6qT/arcgis/rest/"
                 "services/Cocoa_Zoning_with_Split_Lots/FeatureServer/0/query")
COUNTY_ZONING = ("https://gis.brevardfl.gov/gissrv/rest/services/"
                  "Planning_Development/Zoning_WKID2881/MapServer/0/query")

# (case_number, parcel_id, lat, lon) -- all 5 confirmed live in
# multi_county_auctions at session start with complete address+geo+value.
CANDIDATES = [
    ("260133", "2001122", 28.7217721008716, -80.9134172436216),
    ("260197", "2411122", 28.414159, -80.758943),
    ("260213", "2317272", 28.455597, -80.766408),
    ("260214", "2400286", 28.430421, -80.774672),
    ("260215", "2400440", 28.430643, -80.776101),
]

UNINCORPORATED_JURISDICTION_ID = 13  # public.jurisdictions: "Unincorporated Brevard County"


def cocoa_point_in_polygon(lat, lon):
    params = {"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint",
              "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
              "outFields": "TaxAcct,Zoning,ZoneDesc", "returnGeometry": "false", "f": "json"}
    url = COCOA_ZONING + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    return d.get("features", [])


def county_zoning_point(lat, lon):
    params = {"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint",
              "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
              "outFields": "ZONING,DENSCAP", "returnGeometry": "false", "f": "json"}
    url = COUNTY_ZONING + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    return d.get("features", [])


def sb_headers():
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}


def sb_insert(table, rows):
    body = json.dumps(rows).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}", data=body, method="POST",
        headers={**sb_headers(), "Content-Type": "application/json",
                 "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]


def main():
    assert SB_URL and SB_KEY, "SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required"
    resolved = []
    for case_number, parcel_id, lat, lon in CANDIDATES:
        cocoa_feats = cocoa_point_in_polygon(lat, lon)
        if cocoa_feats:
            print(f"{case_number} {parcel_id}: RESOLVED via Cocoa GIS -> {cocoa_feats}")
            continue  # not hit this session -- see docstring, zero Cocoa features for all 5
        county_feats = county_zoning_point(lat, lon)
        if len(county_feats) == 1:
            zone = county_feats[0]["attributes"]["ZONING"]
            resolved.append((case_number, parcel_id, lat, lon, zone))
            print(f"{case_number} {parcel_id}: RESOLVED via county Zoning_WKID2881 -> {zone}")
        elif len(county_feats) > 1:
            print(f"{case_number} {parcel_id}: CONFLICT -- {len(county_feats)} overlapping "
                  f"features, NOT writing (HYPOTHESIS only): {county_feats}")
        else:
            print(f"{case_number} {parcel_id}: BLOCKED -- zero features from Cocoa or county "
                  f"zoning layers")

    print(f"\n=== {len(resolved)}/{len(CANDIDATES)} resolved this run ===")

    pz_rows = [{
        "parcel_id": pid, "tax_account": pid,
        "jurisdiction_id": UNINCORPORATED_JURISDICTION_ID,
        "zone_code": zone, "zone_name": None,
        "source": "gissrv:Zoning_WKID2881",
    } for (_, pid, _, _, zone) in resolved]

    za_rows = [{
        "parcel_id": pid, "zone_code": zone, "jurisdiction": "unincorporated",
        "county": "brevard", "centroid_lat": lat, "centroid_lon": lon,
        "zone_source": "gissrv:Zoning_WKID2881", "zone_confidence": "point_in_polygon",
        "co_no": 15, "dor_uc": None,
    } for (_, pid, lat, lon, zone) in resolved]

    if pz_rows:
        status, body = sb_insert("parcel_zones", pz_rows)
        print(f"parcel_zones INSERT status={status}")
        status, body = sb_insert("zoning_assignments", za_rows)
        print(f"zoning_assignments INSERT status={status}")


if __name__ == "__main__":
    main()
