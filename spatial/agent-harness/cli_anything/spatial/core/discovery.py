"""GIS endpoint discovery and probing for Florida counties."""

import httpx
import time
from typing import Optional

# Known Florida county GIS endpoints
KNOWN_ENDPOINTS = {
    "brevard": {
        "zoning": "https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0",
        "parcels": "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5",
        "zone_field": "ZONING",
        "parcel_field": "PARCEL_ID",
        "notes": "Covers Unincorporated Brevard only (98,960 parcels, 56 districts). Municipal zoning (Melbourne, Palm Bay, Titusville, Cocoa) requires separate endpoints.",
    },
    "titusville": {
        "zoning": "https://gis.titusville.com/arcgis/rest/services/Zoning_FLU_Map/MapServer/0",
        "parcels": "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5",
        "zone_field": "TBD",
        "parcel_field": "PARCEL_ID",
        "status": "PARTIAL — Zoning layers exist but need probing. Use CITY='TITUSVILLE' filter on county parcel layer.",
        "notes": "28,118 parcels. GIS at gis.titusville.com has PlanningInformation and Zoning_FLU_Map services.",
    },
}

# Municipalities NOT YET conquered — need GIS endpoint discovery
PENDING_MUNICIPALITIES = {
    "melbourne": {
        "parcels": 62135,
        "gis_status": "AGOL only — no public REST endpoint found. Uses ArcGIS Online web app.",
        "webmap_id": "3f1f8b678a754f74ab7a58ba33c7911f",
        "approach": "Firecrawl scrape of AGOL web app, or contact city GIS dept for feature service URL.",
    },
    "palm_bay": {
        "parcels": 78697,
        "gis_status": "No public GIS endpoint found. Historical 503 issues.",
        "approach": "Contact city or use Firecrawl to scrape palm bay municipal code zoning maps.",
    },
    "cocoa": {
        "parcels": 29882,
        "gis_status": "No public GIS endpoint found at cocoafl.org.",
        "approach": "Contact city or scrape Municode zoning chapter.",
    },
    "rockledge": {"parcels": 17869, "gis_status": "UNVERIFIED"},
    "west_melbourne": {"parcels": 10365, "gis_status": "NOT_FOUND"},
    "cocoa_beach": {"parcels": 10843, "gis_status": "NOT_FOUND"},
    "satellite_beach": {"parcels": 8524, "gis_status": "NOT_FOUND"},
    "melbourne_beach": {"parcels": 7337, "gis_status": "NOT_FOUND"},
    "cape_canaveral": {"parcels": 7355, "gis_status": "NOT_FOUND"},
    "indialantic": {"parcels": 5205, "gis_status": "NOT_FOUND"},
    "indian_harbour_beach": {"parcels": 4496, "gis_status": "NOT_FOUND"},
    "grant_valkaria": {"parcels": 3065, "gis_status": "NOT_FOUND"},
    "malabar": {"parcels": 1430, "gis_status": "COMPLETE — POC benchmark"},
    "palm_shores": {"parcels": 433, "gis_status": "NOT_FOUND"},
    "melbourne_village": {"parcels": 319, "gis_status": "NOT_FOUND"},
}

FLORIDA_BBOX = {"lat_min": 24.5, "lat_max": 31.0, "lon_min": -87.6, "lon_max": -80.0}

client = httpx.Client(timeout=30, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})


def get_endpoint(county: str) -> Optional[dict]:
    return KNOWN_ENDPOINTS.get(county.lower().replace(" ", "_").replace("-", "_"))


def probe_fields(endpoint_url: str) -> dict:
    resp = client.get(f"{endpoint_url}?f=json")
    data = resp.json()
    fields = {f["name"]: f["type"] for f in data.get("fields", [])}
    return {"name": data.get("name", ""), "geometry_type": data.get("geometryType", ""), "fields": fields}


def probe_count(endpoint_url: str, where: str = "1=1") -> int:
    resp = client.get(f"{endpoint_url}/query", params={"where": where, "returnCountOnly": "true", "f": "json"})
    return resp.json().get("count", 0)


def probe_sample(endpoint_url: str, n: int = 5) -> list:
    resp = client.get(f"{endpoint_url}/query", params={
        "where": "1=1", "outFields": "*", "returnGeometry": "false", "resultRecordCount": n, "f": "json"
    })
    return [f.get("attributes", {}) for f in resp.json().get("features", [])]


def discover_zones(endpoint_url: str, zone_field: str = "ZONING") -> dict:
    zones = {}
    offset = 0
    while True:
        resp = client.get(f"{endpoint_url}/query", params={
            "where": "1=1", "outFields": zone_field, "returnGeometry": "false",
            "resultOffset": offset, "resultRecordCount": 2000, "f": "json"
        })
        data = resp.json()
        features = data.get("features", [])
        if not features:
            break
        for f in features:
            z = f.get("attributes", {}).get(zone_field, "").strip()
            if z:
                zones[z] = zones.get(z, 0) + 1
        offset += len(features)
        if not data.get("exceededTransferLimit", False) and len(features) < 2000:
            break
        time.sleep(1)
    return zones


def list_known_counties() -> list:
    return [{"county": k, "has_zoning": bool(v.get("zoning")),
             "has_parcels": bool(v.get("parcels"))} for k, v in KNOWN_ENDPOINTS.items()]


def list_pending() -> list:
    return [{"municipality": k, **v} for k, v in PENDING_MUNICIPALITIES.items()]


def validate_point_in_florida(lat: float, lon: float) -> bool:
    return (FLORIDA_BBOX["lat_min"] <= lat <= FLORIDA_BBOX["lat_max"] and
            FLORIDA_BBOX["lon_min"] <= lon <= FLORIDA_BBOX["lon_max"])
