#!/usr/bin/env python3
"""GTM-22j shard-6 (dispatch 1f302343, 2nd firing) — hillsborough I real fix.

The I criterion (v_zoning_gold_standard_card) needs a parcel_zones row keyed
by the auction's own parcel_id (STRAP) with a non-null zone_code. 259 of
hillsborough's 916 auction rows have a real STRAP, real address/geo/value,
but no matching parcel_zones row -- 204 of those 259 also carry a shared
placeholder centroid (27.9506,-82.4572) in multi_county_auctions, which is
why a coordinate-keyed spatial fix was refuted in the prior session.

This script sidesteps the placeholder entirely: it fetches each parcel's
REAL polygon geometry from the county Property Appraiser's own parcel layer
(gis.hcpafl.org WebParcels, keyed by strap -- ground truth, independent of
our stored lat/lon), then spatially intersects that real geometry against
the two confirmed-live zoning polygon layers (Hillsborough unincorporated
DSD_Viewer Zoning NZONE field, City of Tampa Zoning District ZONECLASS
field) to get the real zone code. Neither zoning layer exposes a folio/strap
attribute -- both are polygon-only, so attribute join is not possible and
spatial intersect against real (not placeholder) geometry is the correct
method, verified live against a Wimauma (unincorporated) and a Tampa sample
before this script was written.

Read-only by default -- prints the resolution plan + counts + writes a SQL
file. Never mutates the DB directly (this repo's Management-API path is
POST'd separately via `node migrations/run_migration.js`, after review).

REVISION 2 (post adversarial-verify, same session): the first pass used
esriSpatialRelIntersects against each parcel's full polygon, which produces
false-positive matches when a parcel's boundary merely *touches* an
adjacent zone polygon's edge (5 of 30 sampled rows were refuted on exactly
this bug). Fixed by querying zoning layers with the parcel's shapely
`representative_point()` (guaranteed strictly interior, unlike a bounding
centroid) instead of the full polygon -- a point-in-polygon test has no
edge-touch ambiguity. Also adds a third jurisdiction, Plant City, at a
live zoning FeatureServer three independent refuter agents found
(services5.arcgis.com/.../Plant_City_Zoning_WFL1/FeatureServer/15, field
PCZONING) that the first pass's source list omitted -- the earlier "no
Plant City GIS source exists" conclusion (repeated across many prior
sessions) was independently proven wrong this session, not just asserted.

Usage: python3 scripts/gtm22j_shard6_hillsborough_i_parcel_zoning_backfill.py
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

from shapely.geometry import shape

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
PROJECT_REF = SUPABASE_URL.split("//")[1].split(".")[0]
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

WEBPARCELS_URL = "https://gis.hcpafl.org/arcgis/rest/services/Webmaps/HillsboroughFL_WebParcels/MapServer/0/query"
COUNTY_ZONING_URL = "https://maps.hillsboroughcounty.org/arcgis/rest/services/DSD_Viewer_Services/DSD_Viewer_Zoning_Regulatory/MapServer/0/query"
TAMPA_ZONING_URL = "https://arcgis.tampagov.net/arcgis/rest/services/OpenData/Planning/MapServer/28/query"
PLANT_CITY_ZONING_URL = "https://services5.arcgis.com/jeNmEr1R5dgAmDnZ/arcgis/rest/services/Plant_City_Zoning_WFL1/FeatureServer/15/query"

JURISDICTION_UNINCORPORATED = 631
JURISDICTION_TAMPA = 867
JURISDICTION_PLANT_CITY = 961


def mgmt_query(sql: str, _retries: int = 6):
    for attempt in range(_retries):
        try:
            proc = subprocess.run(
                ["curl", "-s", "-X", "POST", MGMT_URL,
                 "-H", f"Authorization: Bearer {ACCESS_TOKEN}",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps({"query": sql})],
                capture_output=True, text=True, timeout=90,
            )
        except subprocess.TimeoutExpired:
            time.sleep(1.5 * (attempt + 1))
            continue
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            result = {"message": f"non-JSON response: {proc.stdout[:200]}"}
        msg = result.get("message", "") if isinstance(result, dict) else ""
        if "ThrottlerException" in msg or "Too Many Requests" in msg or "not accepting connections" in msg:
            time.sleep(2.0 * (attempt + 1))
            continue
        return result
    return result


def arcgis_get(url: str, params: dict, retries: int = 3):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{q}")
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == retries - 1:
                print(f"  ArcGIS query failed after retries ({url}): {e}", file=sys.stderr)
                return {}
            time.sleep(2)


def sql_escape(s: str) -> str:
    return s.replace("'", "''")


def fetch_gap_straps():
    sql = """
WITH zc AS (
  SELECT DISTINCT parcel_id, tax_account
  FROM v_zoning_gold_standard_card
  WHERE lower(county) = norm_county_key('hillsborough') AND zone_code IS NOT NULL
)
SELECT DISTINCT a2.parcel_id AS strap
FROM multi_county_auctions a2
WHERE lower(a2.county) = 'hillsborough'
  AND (COALESCE(a2.data_source,'') <> 'propertyonion' OR COALESCE(a2.tier1_authoritative,false) = true)
  AND a2.parcel_id IS NOT NULL
  AND a2.property_address IS NOT NULL
  AND COALESCE(a2.latitude, a2.po_latitude::double precision) IS NOT NULL
  AND COALESCE(a2.assessed_value, a2.market_value) IS NOT NULL
  AND NOT (a2.parcel_id IN (SELECT parcel_id FROM zc) OR a2.parcel_id IN (SELECT tax_account FROM zc WHERE tax_account IS NOT NULL))
ORDER BY 1;
"""
    result = mgmt_query(sql)
    if not isinstance(result, list):
        raise RuntimeError(f"fetch_gap_straps: expected list, got {result!r}")
    return [r["strap"] for r in result]


def fetch_geometries(straps):
    """Batch-fetch real parcel polygons from HCPAFL WebParcels, keyed by strap."""
    geoms = {}
    BATCH = 40
    for i in range(0, len(straps), BATCH):
        batch = straps[i:i + BATCH]
        in_list = ",".join(f"'{sql_escape(s)}'" for s in batch)
        data = arcgis_get(WEBPARCELS_URL, {
            "where": f"strap IN ({in_list})",
            "outFields": "folio,strap,SiteCity",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
        })
        for feat in data.get("features", []):
            attrs = feat["attributes"]
            geoms[attrs["strap"]] = {
                "folio": attrs.get("folio"),
                "site_city": attrs.get("SiteCity"),
                "geometry": feat.get("geometry"),
            }
        time.sleep(0.4)
    return geoms


def interior_point(geometry):
    """A point strictly inside the polygon -- avoids the boundary-touch false
    positives esriSpatialRelIntersects produces against a full polygon when
    two adjacent zone polygons share an edge with the parcel."""
    # Esri JSON uses "rings", not GeoJSON "coordinates" -- convert before shapely.
    poly = shape({"type": "Polygon", "coordinates": geometry["rings"]})
    pt = poly.representative_point()
    return {"x": pt.x, "y": pt.y, "spatialReference": {"wkid": 4326}}


def spatial_zone_lookup(url, geometry, out_field):
    pt = interior_point(geometry)
    data = arcgis_get(url, {
        "geometry": json.dumps(pt),
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": out_field,
        "returnGeometry": "false",
        "f": "json",
    })
    feats = data.get("features", [])
    if not feats:
        return None
    if len(feats) > 1:
        # A single interior point should resolve to exactly one zone; more
        # than one means an overlapping-polygon data issue in the source
        # layer itself, not something we can safely resolve -- leave unresolved.
        return None
    return feats[0]["attributes"].get(out_field)


def main():
    straps = fetch_gap_straps()
    print(f"gap straps to resolve: {len(straps)}")

    geoms = fetch_geometries(straps)
    print(f"real geometry found in HCPAFL WebParcels: {len(geoms)} of {len(straps)}")
    no_geom = [s for s in straps if s not in geoms]

    resolved_county = []
    resolved_tampa = []
    resolved_plant_city = []
    unresolved = []

    for i, strap in enumerate(straps):
        g = geoms.get(strap)
        if not g or not g.get("geometry"):
            unresolved.append((strap, "no_geometry_in_webparcels"))
            continue
        geometry = g["geometry"]

        nzone = spatial_zone_lookup(COUNTY_ZONING_URL, geometry, "NZONE")
        if nzone:
            resolved_county.append((strap, g["folio"], nzone))
            time.sleep(0.25)
            continue
        time.sleep(0.25)

        zoneclass = spatial_zone_lookup(TAMPA_ZONING_URL, geometry, "ZONECLASS")
        if zoneclass:
            resolved_tampa.append((strap, g["folio"], zoneclass))
            time.sleep(0.25)
            continue
        time.sleep(0.25)

        pczoning = spatial_zone_lookup(PLANT_CITY_ZONING_URL, geometry, "PCZONING")
        if pczoning:
            resolved_plant_city.append((strap, g["folio"], pczoning))
            time.sleep(0.25)
            continue
        time.sleep(0.25)

        unresolved.append((strap, f"no_intersect (site_city={g.get('site_city')})"))
        if (i + 1) % 25 == 0:
            print(f"  ... {i + 1}/{len(straps)} processed")

    print(f"\nresolved via unincorporated county zoning: {len(resolved_county)}")
    print(f"resolved via Tampa zoning: {len(resolved_tampa)}")
    print(f"resolved via Plant City zoning: {len(resolved_plant_city)}")
    print(f"unresolved (no geometry or no point-in-polygon match in any of the 3 layers): {len(unresolved)}")
    for strap, reason in unresolved:
        print(f"  UNRESOLVED {strap}: {reason}")

    out = {
        "resolved_county": resolved_county,
        "resolved_tampa": resolved_tampa,
        "resolved_plant_city": resolved_plant_city,
        "unresolved": unresolved,
    }
    with open("/tmp/hillsborough_i_resolution.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nWrote /tmp/hillsborough_i_resolution.json")

    sql_lines = ["-- GTM-22j shard-6 hillsborough I: real parcel_zones backfill",
                 "-- source: gis.hcpafl.org WebParcels geometry (strap-keyed, ground truth)",
                 "--         interior-point-in-polygon test against confirmed-live county/Tampa/Plant City zoning layers",
                 "INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source) VALUES"]
    values = []
    for strap, folio, nzone in resolved_county:
        values.append(
            f"('{sql_escape(strap)}', {JURISDICTION_UNINCORPORATED}, '{sql_escape(nzone)}', "
            f"'gtm22j_shard6_hcpafl_spatial_county')"
        )
    for strap, folio, zoneclass in resolved_tampa:
        values.append(
            f"('{sql_escape(strap)}', {JURISDICTION_TAMPA}, '{sql_escape(zoneclass)}', "
            f"'gtm22j_shard6_hcpafl_spatial_tampa')"
        )
    for strap, folio, pczoning in resolved_plant_city:
        values.append(
            f"('{sql_escape(strap)}', {JURISDICTION_PLANT_CITY}, '{sql_escape(pczoning)}', "
            f"'gtm22j_shard6_hcpafl_spatial_plantcity')"
        )
    if values:
        sql_lines.append(",\n".join(values) + "\nON CONFLICT DO NOTHING;")
        with open("/tmp/hillsborough_i_backfill.sql", "w") as f:
            f.write("\n".join(sql_lines) + "\n")
        print("Wrote /tmp/hillsborough_i_backfill.sql")
    else:
        print("No resolved rows -- no SQL written.")


if __name__ == "__main__":
    main()
