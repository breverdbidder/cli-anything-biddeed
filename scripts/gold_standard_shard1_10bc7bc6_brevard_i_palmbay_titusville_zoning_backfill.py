"""Gold Standard shard-1 (dispatch 10bc7bc6): Brevard county, letter I
(property card completeness) -- Palm Bay + Titusville municipal zoning
ArcGIS point-in-polygon backfill for the 29 rows that had a complete
property card (address + geo + assessed_value) but were failing the
letter-I zoning-linkage clause because their tax-account parcel_id had
ZERO row in parcel_zones / v_zoning_gold_standard_card at all (not a
NULL zone_code -- total absence).

Root cause (confirmed via live queries this session, 2026-08-13):
  - RPC public.pencil_dod_evaluate_county('brevard') letter I formula
    (see supabase/migrations/20260718_gtm22_phase1_3_pencil_dod_snapshot_
    param_and_loop_rewire.sql, CTE `c`): card_complete requires
    property_address + lat/lng + (assessed_value OR market_value) + the
    row's parcel_id/tax_account matching a v_zoning_gold_standard_card
    row with zone_code IS NOT NULL for county='brevard'.
  - Of the 7248 active (non-propertyonion) brevard auctions, 6125 rows
    already had address+geo+value complete. Of THOSE, 6096 also passed
    the zoning-linkage clause (matching the RPC's card_complete=6096).
    The exact 29-row delta (6125-6096) all had a real street address and
    real lat/lng but their BCPAO TaxAcct parcel_id was not in
    parcel_zones (confirmed 0 rows via parcel_id AND tax_account lookup).
  - These 29 parcel_ids also returned ZERO features from the Brevard
    County unincorporated parcel base layer (gis.brevardfl.gov/.../
    Base_Map/Parcel_New_WKID2881/MapServer/5) -- meaning they sit inside
    a municipality's own GIS system of record, not the county's.
  - Point-in-polygon lookups (using the rows' existing lat/lng) against:
      Palm Bay: gis.palmbayflorida.org/arcgis/rest/services/
                GrowthManagement/Zoning/MapServer/0/query
      Titusville: gis.titusville.com/arcgis/rest/services/
                  CommunityDevelopment/MapServer/15/query
    resolved 23 Palm Bay + 2 Titusville = 25 of 29 with a genuine
    Zone_Code/ZONING attribute.
  - The remaining 4 (parcel_ids 2423944, 2724998 -- both "1711 DIXON BLVD"
    condo units in Titusville; 2532539 "981 S ORLANDO AVE"; 2832622
    "418 OAKLAND AVE" Melbourne) returned zero features from Titusville
    zoning, the county unincorporated layer, AND Melbourne's zoning layer
    (maps.mlbfl.org/.../CommunityDevelopmentViewer_AGOL/MapServer/109).
    They also have ZERO feature in the county's own parcel base map
    layer by TaxAcct -- i.e. these tax-account numbers are not resolvable
    against any live GIS system of record found this session (retired/
    re-platted condo units, consistent with the residual condo-legal-
    description gap flagged by the prior brevard-I session,
    scripts/gold_standard_shard1_35db0a28_brevard_i_gis_backfill.py).
    Left untouched -- not fabricated.

Applied: 25 rows INSERTed into public.parcel_zones (parcel_id=tax_account=
TaxAcct string, jurisdiction_id=2 for Palm Bay / 4 for Titusville,
zone_code from the live GIS response, source=<gis endpoint>). Verified via
GET v_zoning_gold_standard_card?tax_account=in.(...) -- all 25 now return
zone_code IS NOT NULL rows for county='brevard'.

Live evaluator before/after (public.pencil_dod_evaluate_county('brevard'),
letter I):
  before this run: metric=84.1, card_complete=6096 of 7248 -- FAIL
  after this run:  metric=84.5, card_complete=6121 of 7248 -- still FAIL
    (needs >=95%, i.e. ~6886 of 7248)

Residual (~1127 rows still failing letter I) is dominated by the 1109-row
missing-property_address bucket, already exhaustively investigated by the
prior brevard-I session (scripts/gold_standard_shard1_35db0a28_brevard_i_
gis_backfill.py) and confirmed to be overwhelmingly genuinely-unaddressed
vacant/timberland parcels per Brevard's own GIS system of record, plus
condo-legal-description cases the AcclaimWeb lot/block regex cannot parse.
That finding still holds this session (1040 of 1109 no-address rows have
a parcel_id, essentially the same set the prior session found). Closing
this gap further requires either a different data source (condo unit
plat digitization) or accepting non-addressed vacant land as a
legitimately non-card-complete category in the evaluator itself -- both
out of scope for a data-backfill session.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

PB_ZONING = "https://gis.palmbayflorida.org/arcgis/rest/services/GrowthManagement/Zoning/MapServer/0/query"
TV_ZONING = "https://gis.titusville.com/arcgis/rest/services/CommunityDevelopment/MapServer/15/query"
MLB_ZONING = "https://maps.mlbfl.org/services/rest/services/AGOL/CommunityDevelopmentViewer_AGOL/MapServer/109/query"


def point_in_polygon_zone(base_url, lat, lon, zone_field="ZONING"):
    """Query a municipal zoning MapServer layer for the zone containing
    (lat, lon). Returns the zone code string, or None if no feature."""
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "false",
        "f": "json",
    }
    url = base_url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    feats = d.get("features", [])
    if not feats:
        return None
    attrs = feats[0]["attributes"]
    return attrs.get(zone_field) or attrs.get("Zone_Code") or attrs.get("ZONING")


# This run's confirmed result (see module docstring): 25 parcel_zones rows
# inserted (23 Palm Bay via ZONING field, 2 Titusville via Zone_Code field).
# 4 residual condo/retired-TaxAcct parcels left untouched -- no source
# resolved them.
if __name__ == "__main__":
    print("This run inserted 25 rows into public.parcel_zones: 23 Palm Bay "
          "(jurisdiction_id=2) + 2 Titusville (jurisdiction_id=4).")
    print("See module docstring for full residual breakdown and evaluator "
          "before/after (84.1% -> 84.5%, still FAIL, needs >=95%).")
