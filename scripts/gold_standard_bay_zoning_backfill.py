"""
Bay County gold-standard criterion I (card_complete) backfill.

Sources missing zoning/parcel/geo data for Bay County multi_county_auctions
rows from Bay County's live ArcGIS REST services:
  - gis.baycountyfl.gov/arcgis/rest/services/Land_Use_Planning/MapServer/1 (Zoning)
  - gis.baycountyfl.gov/arcgis/rest/services/TEST_Parcels/MapServer/1 (parcel appraisal data)

Both are public, unauthenticated, live Bay County government ArcGIS REST
endpoints (verified 2026-07-10). No fabricated data: every zone_code, parcel_id,
lat/lon, and assessed_value inserted here traces to a specific GIS feature
returned by one of these two services.

Usage: read-only discovery script. The actual INSERT/UPDATE statements run in
this session were executed by hand via the Supabase Management API (raw SQL)
against parcel_zones, jurisdictions, and multi_county_auctions -- this script
documents and reproduces the *lookup* logic so it can be rerun for other
counties or re-verified.

Result this session (2026-07-10):
  I (card_complete): 66.9% (79/118) -> 94.1% (111/118)
  E (has_parcel):     96.6% (114/118) -> 99.2% (117/118)
  jurisdiction added: "Unincorporated Bay County" (id=1332) -- Bay County's
    own zoning layer covers unincorporated county + all 5 municipalities but
    our jurisdictions table only had the 5 municipalities, not the county
    itself. This was the dominant root cause of the I gap (SUB_ZONING=1 rows).

Residual gap (7 rows, NOT fixed -- documented, not fabricated):
  - 3 rows: real parcel_id, Bay County zoning layer legend explicitly returns
    "See FLU" (no usable ZONING attribute) for 09647-000-000, 10024-000-000,
    15124-000-000. Confirmed via direct A1RENUM lookup against TEST_Parcels
    that its own Zoning/FLU fields are also null for these three. This is a
    genuine gap in Bay County's published GIS data (likely PUD/agricultural
    FLU-governed parcels), not a mismatch we can resolve without a paid or
    non-public data source. Left alone per BLANK > WRONG.
  - 3 rows: parser-artifact placeholder parcel_ids ("TIMESHARE",
    "Property Appraiser", "MULTIPLE PARCELS") from the AJAX calendar decoder.
    Not real parcel numbers; no property_address either. Would require
    independent case-record research to resolve; out of scope, not attempted.
  - 1 row (case 25000874CA): no parcel_id, no address, no geo, no value at
    all in source data. Nothing to backfill from.
"""

import json
import time
import urllib.parse
import urllib.request

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
ZONING_URL = (
    "https://gis.baycountyfl.gov/arcgis/rest/services/"
    "Land_Use_Planning/MapServer/1/query"
)
PARCEL_URL = (
    "https://gis.baycountyfl.gov/arcgis/rest/services/"
    "TEST_Parcels/MapServer/1/query"
)

SUB_ZONING_JURISDICTION_NAME = {
    1: "Bay County",           # maps to "Unincorporated Bay County" jurisdiction
    2: "Callaway",
    3: "Lynn Haven",
    4: "Mexico Beach",
    5: "Panama City",
    6: "Panama City Beach",
}

RATE_LIMIT_SECONDS = 2.0


def _get(url: str, params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{qs}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def lookup_zoning_by_point(lat: float, lon: float, buffer_deg: float = 0.0004) -> dict | None:
    """Query Bay County's Zoning layer via a small envelope around (lat, lon).

    Exact-point (esriGeometryPoint) queries against this service reliably
    return zero features even for points well inside a polygon (observed
    2026-07-10) -- use a small bounding-box envelope instead.
    """
    time.sleep(RATE_LIMIT_SECONDS)
    env = f"{lon - buffer_deg},{lat - buffer_deg},{lon + buffer_deg},{lat + buffer_deg}"
    data = _get(
        ZONING_URL,
        {
            "geometry": env,
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "ZONING,SUB_ZONING,Label",
            "returnGeometry": "false",
            "f": "json",
        },
    )
    feats = data.get("features", [])
    if not feats:
        return None
    attrs = feats[0]["attributes"]
    return {
        "zone_code": attrs.get("ZONING"),
        "sub_zoning": attrs.get("SUB_ZONING"),
        "jurisdiction_name": SUB_ZONING_JURISDICTION_NAME.get(attrs.get("SUB_ZONING")),
        "label": attrs.get("Label"),
        "n_features": len(feats),  # >1 means ambiguous, tighten buffer_deg
    }


def lookup_parcel_by_id(parcel_id: str) -> dict | None:
    """Query Bay County's parcel appraisal layer (TEST_Parcels/1) by A1RENUM."""
    time.sleep(RATE_LIMIT_SECONDS)
    where = f"A1RENUM='{parcel_id}'"
    data = _get(
        PARCEL_URL,
        {
            "where": where,
            "outFields": "A1RENUM,DSITEADDR,VASJUST,VASTOTAL,Zoning,FLU",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
        },
    )
    feats = data.get("features", [])
    if not feats:
        return None
    return feats[0]


def lookup_parcel_by_address(address_fragment: str) -> dict | None:
    """Query Bay County's parcel appraisal layer by DSITEADDR LIKE match.

    address_fragment should be a short distinctive substring, e.g.
    "2817%LONGLEAF%" (SQL LIKE wildcards).
    """
    time.sleep(RATE_LIMIT_SECONDS)
    where = f"DSITEADDR LIKE '{address_fragment}'"
    data = _get(
        PARCEL_URL,
        {
            "where": where,
            "outFields": "A1RENUM,DSITEADDR,VASJUST,VASTOTAL",
            "returnGeometry": "false",
            "f": "json",
        },
    )
    feats = data.get("features", [])
    if not feats:
        return None
    return feats


def polygon_centroid(rings: list) -> tuple[float, float]:
    """Simple vertex-average centroid (sufficient for small parcel polygons)."""
    ring = rings[0]
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return sum(ys) / len(ys), sum(xs) / len(xs)  # (lat, lon)


if __name__ == "__main__":
    # Example: reproduce the R-2 lookup for 30167-010-000 (PCB unincorporated area)
    result = lookup_zoning_by_point(30.167213665013, -85.771661040351)
    print(result)
