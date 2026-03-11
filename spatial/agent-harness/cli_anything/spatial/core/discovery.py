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
        "parcel_field": "PARCELID",
    },
}

FLORIDA_BBOX = {"lat_min": 24.5, "lat_max": 31.0, "lon_min": -87.6, "lon_max": -80.0}

client = httpx.Client(timeout=30, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})


def get_endpoint(county: str) -> Optional[dict]:
    """Get known GIS endpoint for a county."""
    return KNOWN_ENDPOINTS.get(county.lower())


def probe_fields(endpoint_url: str) -> dict:
    """Probe a GIS MapServer layer for field names and types."""
    resp = client.get(f"{endpoint_url}?f=json")
    data = resp.json()
    fields = {f["name"]: f["type"] for f in data.get("fields", [])}
    return {
        "name": data.get("name", ""),
        "geometry_type": data.get("geometryType", ""),
        "fields": fields,
    }


def probe_count(endpoint_url: str, where: str = "1=1") -> int:
    """Get total feature count from a GIS layer."""
    resp = client.get(f"{endpoint_url}/query", params={
        "where": where, "returnCountOnly": "true", "f": "json"
    })
    return resp.json().get("count", 0)


def probe_sample(endpoint_url: str, n: int = 5) -> list:
    """Get sample features to inspect data quality."""
    resp = client.get(f"{endpoint_url}/query", params={
        "where": "1=1", "outFields": "*", "returnGeometry": "false",
        "resultRecordCount": n, "f": "json"
    })
    return [f.get("attributes", {}) for f in resp.json().get("features", [])]


def discover_zones(endpoint_url: str, zone_field: str = "ZONING") -> dict:
    """Paginate through ALL features to enumerate distinct zones."""
    zones = {}
    offset = 0
    while True:
        resp = client.get(f"{endpoint_url}/query", params={
            "where": "1=1", "outFields": zone_field,
            "returnGeometry": "false", "resultOffset": offset,
            "resultRecordCount": 2000, "f": "json"
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
    """List all counties with known GIS endpoints."""
    return [{"county": k, "has_zoning": bool(v.get("zoning")),
             "has_parcels": bool(v.get("parcels"))} for k, v in KNOWN_ENDPOINTS.items()]


def validate_point_in_florida(lat: float, lon: float) -> bool:
    """Check if a point is within Florida bounding box."""
    return (FLORIDA_BBOX["lat_min"] <= lat <= FLORIDA_BBOX["lat_max"] and
            FLORIDA_BBOX["lon_min"] <= lon <= FLORIDA_BBOX["lon_max"])
