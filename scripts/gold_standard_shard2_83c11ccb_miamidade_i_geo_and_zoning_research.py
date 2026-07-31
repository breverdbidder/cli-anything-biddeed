#!/usr/bin/env python3
"""GOLD STANDARD shard-2, dispatch 83c11ccb-424b-4b3b-822b-909c6e8fccaa.

Scope: miami_dade ONLY, letter I (card_complete). FAIL at 80.1%
(card_complete=338 of 422). This session's diagnosis broke the 81 failing
rows into buckets (address/geo/value/zone-link) and worked the two
sub-tasks the dispatch specified, in priority order.

STEP 1 -- mechanical backfill of the ~14 non-zoning-blocked rows.
Live investigation via the AJAX RealAuction/RealTaxDeed harvester
(scripts/shard2_run2450_ajax_realforeclose_harvest.py, reused verbatim)
against the real, live miamidade.realforeclose.com / realtaxdeed.com
calendar for every auction date in this bucket found:

  - 4 rows where the calendar's own "Parcel ID:" link renders literal
    anchor text "Property Appraiser" -- NOT a decoder bug. Confirmed via
    raw HTML: the underlying <a href="...?folio="> has an EMPTY folio
    query param. Miami-Dade's own auction system has no folio on file for
    these listings. Cannot be fixed from this source.
  - 3 rows where Parcel ID is literally "MULTIPLE PARCELS" (multi-parcel
    foreclosure filings, no single folio exists) or "ALCOHOLIC BEVERAGE
    LICENSE" (a business-license repossession, not real property -- no
    folio by definition). Real, live, upstream data gaps.
  - 1 row (case 2026A00187, tax deed, assessed_value=$217) already has
    parcel_id + geo; the calendar genuinely has no Property Address field
    for this listing (very low assessed value suggests a vacant/land-only
    or easement parcel). Cannot be fixed from this source.
  - 1 row (case 2020-019662-CA-01 / duplicate rows for the same case,
    1150 EUCLID AVE 102, MIAMI BEACH) had parcel_id + address + value but
    NULL lat/long. fl_parcels (co_no=23) has no centroid for this exact
    condo-unit folio (02-4203-032-0020), but the US Census Bureau's public
    geocoder (geocoding.geo.census.gov, no key required) returned a real,
    verified match for the on-file address:
      lat=25.782391198104 lon=-80.135237872489
    Cross-checked against fl_parcels' centroid for the base-unit folio in
    the same building (0242030320001: 25.7825805, -80.1355023) -- matches
    closely, confirming accuracy. Patched (NULL-only, idempotent) via
    direct REST PATCH; this is the one row this script's Step 1 actually
    fixes. Result: I metric 338->339 of 422.

STEP 2 -- zoning-substrate research for the 51+16=67 zoning-link-blocked
rows (parcel_zones has ZERO rows for 12 of 22 miami_dade jurisdictions:
Opa-locka, Coral Gables, Sweetwater, Sunny Isles Beach, South Miami,
Miami Lakes, North Miami Beach, Pinecrest, Miami Springs, Hialeah Gardens,
Cutler Bay, Key Biscayne).

FOUND: Miami-Dade DOES publish a countywide, per-municipality zoning
polygon layer that covers ALL 12 zero-coverage municipalities:
  https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/MunicipalZone_gdb/FeatureServer
  layer 0 "MunicipalZone" -- fields: MUNICNAME, ZONE, ZONEDESC, MINLOTSIZE,
  DENSITY, FAR, MAXHEIGHT, MAXLOTCOV. Confirmed live: distinct MUNICNAME
  values include all 12 target municipalities plus every other Miami-Dade
  municipality. This is a POLYGON-geometry layer with NO folio/parcel_id
  attribute -- it requires a spatial (point-in-polygon) join against each
  parcel's centroid, exactly as the dispatch anticipated as the harder path.

The spatial join IS technically feasible and was verified live this
session: the ArcGIS REST `query` endpoint accepts a point geometry
(inSR=4326) with spatialRel=esriSpatialRelIntersects and returns the
authoritative intersecting zone polygon's attributes directly from the
county's own GIS server (not a guessed/approximate match -- a real
server-side spatial predicate). Ran this for all 51 zoning-link-blocked
rows that already have a stored lat/long:
  - 4 rows land inside one of the 12 target zero-coverage municipalities
    (Sunny Isles Beach x1, North Miami Beach x2, Coral Gables x1).
  - 24 rows land in "UNINCORPORATED" (folio prefix "30") -- already has
    54 parcel_zones rows for that jurisdiction, so these are a sparse-
    coverage gap within an already-partially-covered jurisdiction, not a
    zero-coverage jurisdiction. Out of this session's scoped target.
  - 23 rows land in Miami, Hialeah, Miami Gardens, Homestead, Doral,
    Miami Beach, Miami Shores, El Portal, Florida City -- all already
    have SOME parcel_zones rows (12-142 each), so these are the same
    sparse-coverage-gap pattern, not zero-coverage. Out of scope.
  - 0 no-match / error.

CRITICAL FINDING (why this session does NOT ingest the 4 in-scope rows):
inserted the 4 target-municipality zone_code rows into parcel_zones as a
trial (source='miamidade_gis_countywide_zoning:MunicipalZone_gdb') and
re-ran pencil_dod_evaluate_county live. Result: I moved 339->343 (+4,
correct), but G (density/FAR/parking KPI) REGRESSED 99.3->50.0 and
flipped PASS->FAIL. Root cause: v_zoning_gold_standard_kpi_v3's far/
pk1000 metrics have a tiny denominator for miami_dade (far_applicable=2,
pk1000_applicable=2 parcels total, pre-existing). The MunicipalZone_gdb
layer's ZONE codes (MUR, RM-23, RS-4, SFR) have no matching row in
zoning_districts/zone_standards, so v_zoning_district_applicability
defaults far_applicable/pk1000_applicable to TRUE (COALESCE(...,true))
with NULL max_far/parking_per_1000sf -- 2 more "applicable but missing"
parcels dropped both percentages to 50%, well under the 95% pass bar.
The 4 trial rows were DELETED immediately (ids 850576-850579) and
pencil_dod_evaluate_county re-run to confirm G returned to PASS
(99.3/100/100) and I returned to 339/422 (80.3%) -- i.e. net zero drift
from this finding, only the Step-1 geo fix survives.

NEXT STEPS FOR A FOLLOW-UP SESSION (do not skip this ordering):
  1. Before inserting ANY parcel_zones row sourced from MunicipalZone_gdb,
     first insert a matching zoning_districts row (jurisdiction_id + code)
     AND a zone_standards row with real max_far / max_density_du_acre /
     parking_per_1000sf sourced from the municipality's own zoning
     ordinance (Municode) or from MunicipalZone_gdb's own DENSITY/FAR
     fields (present in the schema, e.g. FAR='2.5' DENSITY='80' for the
     Sunny Isles Beach MUR row found this session) -- OR add a
     v_zoning_district_applicability row marking far_applicable=false /
     pk1000_applicable=false for zone types where those standards
     genuinely don't apply (e.g. single-family RS-4/SFR zones typically
     have no FAR or parking-per-1000sf standard at all in most FL
     municipal codes -- that would be an honest "not applicable", not a
     gap, and should shrink G's denominator instead of inflating its
     NULL-numerator problem).
  2. Only after (1) is done for a batch, re-run pencil_dod_evaluate_county
     and confirm G stays >=95 before considering the batch a net gain.
  3. The 47 sparse-coverage-gap rows (Miami/Hialeah/Miami Gardens/etc.)
     are a separate, larger opportunity (spatial-join method already
     proven) but were explicitly out of THIS dispatch's stated 12-
     municipality scope and share the same G-regression risk -- same
     ordering rule applies.
  4. The 16-row bucket (missing geo AND zone-link) mostly has NO centroid
     in fl_parcels (15 of 16) and NO match in Miami-Dade's own
     Parcelpoly_gdb countywide parcel-polygon layer either (spot-checked
     folio 30-4030-038-0050 / 3040300380050 -- zero results) -- these
     folios likely reference retired/merged/split parcels. Not resolved
     this session; flagged as a harder, lower-confidence sub-problem.

Usage: python3 scripts/gold_standard_shard2_83c11ccb_miamidade_i_geo_and_zoning_research.py
(re-runs the Step-1 geo backfill idempotently; Step 2 is research-only in
this script, no writes -- the trial parcel_zones insert/delete described
above was done ad hoc in-session and is NOT reproduced here, by design,
until the ordering fix in NEXT STEPS is implemented.)
"""
import os
import json
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# Verified live 2026-07-31 via geocoding.geo.census.gov/geocoder/locations/onelineaddress
# for "1150 EUCLID AVE, MIAMI BEACH, FL 33139" (case 2020-019662-CA-01, folio
# 02-4203-032-0020). Cross-checked against fl_parcels centroid for the same
# building's base unit (folio 0242030320001): 25.7825805, -80.1355023 -- close match.
GEO_BACKFILL = [
    {
        "id": "3857ea65-81d6-4f6a-8c4a-f47f4dfe9a53",
        "case_number": "2020-019662-CA-01",
        "latitude": 25.782391198104,
        "longitude": -80.135237872489,
    },
]


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    for row in GEO_BACKFILL:
        # NULL-only, idempotent: only patches if both fields are still NULL.
        result = rest_patch(
            f"multi_county_auctions?id=eq.{row['id']}&latitude=is.null&longitude=is.null",
            {"latitude": row["latitude"], "longitude": row["longitude"]})
        if result:
            print(f"  {row['case_number']}: geo backfilled lat={row['latitude']} lon={row['longitude']}")
        else:
            print(f"  {row['case_number']}: no-op (already non-null, or id not found)")


if __name__ == "__main__":
    main()
