"""Spatial conquest engine — Shapely STRtree point-in-polygon matching."""

import httpx
import time
from typing import Optional
from dataclasses import dataclass, field

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

SAFEGUARD_PCT = 85


@dataclass
class ConquestResult:
    county: str
    polygons_downloaded: int = 0
    valid_geometries: int = 0
    districts_found: int = 0
    parcels_downloaded: int = 0
    parcels_matched: int = 0
    coverage_pct: float = 0.0
    safeguard_met: bool = False
    districts: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "county": self.county,
            "polygons": self.polygons_downloaded,
            "valid_geometries": self.valid_geometries,
            "districts_found": self.districts_found,
            "parcels_downloaded": self.parcels_downloaded,
            "parcels_matched": self.parcels_matched,
            "coverage_pct": round(self.coverage_pct, 1),
            "safeguard_met": self.safeguard_met,
            "top_zones": sorted(self.districts.items(), key=lambda x: -x[1])[:10],
            "errors": self.errors[:10],
        }


def download_zone_polygons(endpoint_url: str, zone_field: str = "ZONING") -> tuple:
    """Phase 1: Download all zone polygons with geometry from GIS."""
    features = []
    zones = {}
    offset = 0

    while True:
        resp = client.get(f"{endpoint_url}/query", params={
            "where": "1=1", "outFields": f"OBJECTID,{zone_field}",
            "returnGeometry": "true", "outSR": "4326",
            "resultOffset": offset, "resultRecordCount": 1000, "f": "json"
        })
        data = resp.json()
        batch = data.get("features", [])
        if not batch:
            break
        features.extend(batch)
        for f in batch:
            z = f.get("attributes", {}).get(zone_field, "").strip()
            if z:
                zones[z] = zones.get(z, 0) + 1
        offset += len(batch)
        if not data.get("exceededTransferLimit", False) and len(batch) < 1000:
            break
        time.sleep(1)

    return features, zones


def build_spatial_index(features, zone_field: str = "ZONING"):
    """Phase 2: Build Shapely STRtree from zone polygons."""
    from shapely.geometry import Polygon
    from shapely.strtree import STRtree

    geometries = []
    zone_lookup = {}

    for f in features:
        geom_data = f.get("geometry", {})
        zone = f.get("attributes", {}).get(zone_field, "").strip()
        if not geom_data or not zone:
            continue
        rings = geom_data.get("rings", [])
        if not rings or len(rings[0]) < 3:
            continue
        try:
            geom = Polygon(rings[0])
            if geom.is_valid:
                idx = len(geometries)
                geometries.append(geom)
                zone_lookup[idx] = zone
        except Exception:
            continue

    tree = STRtree(geometries)
    return tree, geometries, zone_lookup


def download_parcel_centroids(parcel_endpoint: str, parcel_field: str = "PARCELID",
                               progress_callback=None) -> list:
    """Phase 3: Download parcel centroids from GIS."""
    parcels = []
    offset = 0

    while True:
        try:
            resp = client.get(f"{parcel_endpoint}/query", params={
                "where": "1=1", "outFields": f"{parcel_field},SITEADDR",
                "returnGeometry": "true", "outSR": "4326",
                "resultOffset": offset, "resultRecordCount": 2000, "f": "json"
            })
            data = resp.json()
            features = data.get("features", [])
            if not features:
                break

            for f in features:
                attrs = f.get("attributes", {})
                geom = f.get("geometry", {})
                pid = attrs.get(parcel_field, "")
                rings = geom.get("rings", [[]])
                if pid and rings and rings[0]:
                    xs = [p[0] for p in rings[0]]
                    ys = [p[1] for p in rings[0]]
                    parcels.append({
                        "parcel_id": str(pid),
                        "address": attrs.get("SITEADDR", ""),
                        "lon": sum(xs) / len(xs),
                        "lat": sum(ys) / len(ys),
                    })

            offset += len(features)
            if progress_callback and offset % 20000 == 0:
                progress_callback(offset)

            if not data.get("exceededTransferLimit", False) and len(features) < 2000:
                break
            time.sleep(1)
        except Exception as e:
            time.sleep(5)
            offset += 2000
            if offset > 500000:
                break

    return parcels


def spatial_join(tree, geometries, zone_lookup, parcels, batch_callback=None) -> list:
    """Phase 4: Point-in-polygon matching."""
    from shapely.geometry import Point

    results = []
    for i, p in enumerate(parcels):
        pt = Point(p["lon"], p["lat"])
        candidates = tree.query(pt)
        zone = None
        for idx in candidates:
            if geometries[idx].contains(pt):
                zone = zone_lookup.get(idx)
                break
        if zone:
            results.append({
                "parcel_id": p["parcel_id"],
                "zone_code": zone,
                "centroid_lat": round(p["lat"], 6),
                "centroid_lon": round(p["lon"], 6),
            })
        if batch_callback and (i + 1) % 50000 == 0:
            batch_callback(len(results), i + 1)

    return results


def conquer_county(county: str, zoning_endpoint: str, parcel_endpoint: str,
                   zone_field: str = "ZONING", parcel_field: str = "PARCELID",
                   progress_callback=None) -> ConquestResult:
    """Full conquest pipeline: download → index → match → return results."""
    result = ConquestResult(county=county)

    try:
        # Phase 1
        features, zones = download_zone_polygons(zoning_endpoint, zone_field)
        result.polygons_downloaded = len(features)
        result.districts = zones
        result.districts_found = len(zones)

        # Phase 2
        tree, geometries, zone_lookup = build_spatial_index(features, zone_field)
        result.valid_geometries = len(geometries)

        # Phase 3
        parcels = download_parcel_centroids(parcel_endpoint, parcel_field, progress_callback)
        result.parcels_downloaded = len(parcels)

        # Phase 4
        matched = spatial_join(tree, geometries, zone_lookup, parcels)
        result.parcels_matched = len(matched)
        result.coverage_pct = len(matched) / len(parcels) * 100 if parcels else 0
        result.safeguard_met = result.coverage_pct >= SAFEGUARD_PCT

        return result, matched

    except Exception as e:
        result.errors.append(str(e))
        return result, []
