#!/usr/bin/env python3
"""Summit: Brevard Real Zoning Conquest
Replace USE_CODE fallbacks with real GIS spatial joins.

Phase 1: Unincorporated Brevard (80K parcels) via county Zoning_WKID2881 layer
Phase 2: Probe municipal GIS endpoints for remaining USE_CODE cities
Phase 3: Spatial join and update zoning_assignments
"""
import httpx, json, os, sys, time, math
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

# GIS endpoints
COUNTY_ZONING = "https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0"
BCPAO_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

# Municipal GIS endpoints to probe
MUNICIPAL_GIS = {
    "cocoa": [
        "https://maps.cocoafl.org/arcgis/rest/services",
        "https://gis.cocoafl.org/arcgis/rest/services",
    ],
    "cocoa_beach": [
        "https://gis.cityofcocoabeach.com/arcgis/rest/services",
    ],
    "satellite_beach": [
        "https://gis.satellitebeach.org/arcgis/rest/services",
    ],
}

# BCPAO CITY names for each jurisdiction
CITY_NAMES = {
    "unincorporated_brevard": ["UNINCORPORATED"],
    "cocoa": ["COCOA"],
    "cocoa_beach": ["COCOA BEACH"],
    "satellite_beach": ["SATELLITE BEACH"],
    "malabar": ["MALABAR"],
    "grant_valkaria": ["GRANT VALKARIA", "GRANT-VALKARIA"],
    "melbourne_village": ["MELBOURNE VILLAGE"],
    "palm_shores": ["PALM SHORES"],
}

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})


def tg(msg):
    """Send Telegram notification."""
    print(msg)
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]}, timeout=10)
        except:
            pass


def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def sb_upsert(rows, table="zoning_assignments"):
    """Upsert rows to Supabase in batches of 500."""
    h = {**sb_headers(), "Prefer": "resolution=merge-duplicates"}
    total = 0
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=h, json=batch)
        if resp.status_code in (200, 201, 204):
            total += len(batch)
        else:
            tg(f"⚠️ Upsert error batch {i}: {resp.status_code} {resp.text[:200]}")
        time.sleep(0.3)
    return total


def download_zoning_polygons():
    """Download all county zoning polygons with geometry in EPSG:2881."""
    tg("🏔️ Phase 1: Downloading 10,096 county zoning polygons...")
    features = []
    offset = 0
    while True:
        resp = client.get(f"{COUNTY_ZONING}/query", params={
            "where": "1=1",
            "outFields": "ZONING,DENSCAP",
            "returnGeometry": "true",
            "outSR": "2881",
            "resultOffset": offset,
            "resultRecordCount": 1000,
            "f": "json"
        })
        data = resp.json()
        batch = data.get("features", [])
        if not batch:
            break
        features.extend(batch)
        offset += len(batch)
        tg(f"  Downloaded {len(features)} polygons...")
        if not data.get("exceededTransferLimit", False) and len(batch) < 1000:
            break
        time.sleep(0.5)
    tg(f"✅ Downloaded {len(features)} zoning polygons")
    return features


def download_parcel_centroids(city_name):
    """Download parcel centroids from BCPAO for a given CITY."""
    tg(f"🏔️ Downloading parcels for CITY='{city_name}'...")
    features = []
    offset = 0
    while True:
        resp = client.get(f"{BCPAO_PARCELS}/query", params={
            "where": f"CITY='{city_name}'",
            "outFields": "PARCEL_ID,CITY",
            "returnGeometry": "true",
            "returnCentroid": "true",
            "outSR": "2881",
            "resultOffset": offset,
            "resultRecordCount": 2000,
            "f": "json"
        })
        data = resp.json()
        batch = data.get("features", [])
        if not batch:
            break
        features.extend(batch)
        offset += len(batch)
        if not data.get("exceededTransferLimit", False) and len(batch) < 2000:
            break
        time.sleep(0.3)
    tg(f"  Got {len(features)} parcels for {city_name}")
    return features


def get_centroid(feature):
    """Extract centroid from parcel feature (use centroid if available, else rings center)."""
    geom = feature.get("geometry", {})
    # Try centroid first
    if "centroid" in feature:
        c = feature["centroid"]
        return c.get("x"), c.get("y")
    # Compute from rings
    rings = geom.get("rings", [])
    if rings and rings[0]:
        xs = [p[0] for p in rings[0]]
        ys = [p[1] for p in rings[0]]
        return sum(xs)/len(xs), sum(ys)/len(ys)
    return None, None


def spatial_join(zoning_features, parcel_features, jurisdiction):
    """Shapely 2.x STRtree spatial join — parcel centroids into zoning polygons."""
    from shapely.geometry import Polygon, Point
    from shapely.strtree import STRtree

    tg(f"🏔️ Building STRtree for {len(zoning_features)} polygons...")

    # Build polygon geometries — parallel arrays (Shapely 2.x returns indices)
    geometries = []
    zone_codes = []
    skipped = 0
    for f in zoning_features:
        geom_data = f.get("geometry", {})
        attrs = f.get("attributes", {})
        zone = (attrs.get("ZONING") or "").strip()
        if not geom_data or not zone:
            skipped += 1
            continue
        rings = geom_data.get("rings", [])
        if not rings or len(rings[0]) < 3:
            skipped += 1
            continue
        try:
            geom = Polygon(rings[0])
            if geom.is_valid and not geom.is_empty:
                geometries.append(geom)
                zone_codes.append(zone)
        except:
            skipped += 1

    tg(f"  Built {len(geometries)} valid polygons (skipped {skipped})")
    tree = STRtree(geometries)

    # Match parcels
    results = []
    matched = 0
    unmatched = 0
    for pf in parcel_features:
        parcel_id = pf.get("attributes", {}).get("PARCEL_ID", "")
        if not parcel_id:
            continue
        x, y = get_centroid(pf)
        if x is None:
            unmatched += 1
            continue
        pt = Point(x, y)
        # Shapely 2.x: query returns numpy indices into geometries array
        candidate_indices = tree.query(pt)
        zone_code = None
        for idx in candidate_indices:
            idx = int(idx)
            if geometries[idx].contains(pt):
                zone_code = zone_codes[idx]
                break
        if zone_code:
            matched += 1
            results.append({
                "parcel_id": parcel_id,
                "zone_code": zone_code,
                "jurisdiction": jurisdiction,
                "county": "brevard",
                "zone_updated_at": datetime.now(timezone.utc).isoformat(),
            })
        else:
            unmatched += 1

    tg(f"  Matched: {matched}, Unmatched: {unmatched}")
    return results

def probe_municipal_gis(city_key):
    """Probe known GIS endpoints for a municipality."""
    endpoints = MUNICIPAL_GIS.get(city_key, [])
    for base_url in endpoints:
        try:
            resp = client.get(f"{base_url}?f=json", timeout=8)
            data = resp.json()
            services = data.get("services", []) + data.get("folders", [])
            if services:
                tg(f"  ✅ {city_key}: GIS found at {base_url} — {len(services)} items")
                return base_url
        except Exception as e:
            tg(f"  ❌ {city_key}: {base_url} — {e}")
    return None


def main():
    start = time.time()
    tg("🏔️ SUMMIT: Brevard Real Zoning Conquest")
    tg(f"  Target: Replace USE_CODE fallbacks with GIS spatial joins")
    tg(f"  Time: {datetime.now(timezone.utc).isoformat()}")

    # Install deps
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "shapely", "--break-system-packages", "-q"],
                   capture_output=True)

    # Phase 1: Download county zoning polygons (shared for all unincorporated parcels)
    zoning_polys = download_zoning_polygons()
    if not zoning_polys:
        tg("❌ FATAL: No zoning polygons downloaded. Aborting.")
        return

    # Phase 2: Process each USE_CODE jurisdiction
    total_updated = 0
    results_by_jurisdiction = {}

    for jurisdiction, city_names in CITY_NAMES.items():
        tg(f"\n{'='*50}")
        tg(f"🏔️ Processing: {jurisdiction}")
        
        all_parcels = []
        for city_name in city_names:
            parcels = download_parcel_centroids(city_name)
            all_parcels.extend(parcels)

        if not all_parcels:
            tg(f"  ⚠️ No parcels found for {jurisdiction}")
            continue

        # Spatial join against county zoning
        matched_rows = spatial_join(zoning_polys, all_parcels, jurisdiction)
        
        if matched_rows:
            upserted = sb_upsert(matched_rows)
            total_updated += upserted
            results_by_jurisdiction[jurisdiction] = {
                "total_parcels": len(all_parcels),
                "matched": len(matched_rows),
                "upserted": upserted,
                "pct": round(len(matched_rows) / len(all_parcels) * 100, 1) if all_parcels else 0
            }
            tg(f"  ✅ {jurisdiction}: {upserted}/{len(all_parcels)} updated ({results_by_jurisdiction[jurisdiction]['pct']}%)")
        else:
            results_by_jurisdiction[jurisdiction] = {
                "total_parcels": len(all_parcels),
                "matched": 0, "upserted": 0, "pct": 0
            }
            tg(f"  ⚠️ {jurisdiction}: 0 matches — county zoning may not cover this municipality")

    # Phase 3: Probe municipal GIS for cities that failed county join
    tg(f"\n{'='*50}")
    tg("🏔️ Phase 3: Probing municipal GIS endpoints...")
    for city_key in MUNICIPAL_GIS:
        result = results_by_jurisdiction.get(city_key, {})
        if result.get("pct", 0) < 50:
            found = probe_municipal_gis(city_key)
            if found:
                tg(f"  💡 {city_key} has GIS at {found} — needs separate spatial join script")

    # Summary
    elapsed = time.time() - start
    summary = f"""
🏔️ SUMMIT COMPLETE: Brevard Real Zoning Conquest
⏱️ Duration: {elapsed/60:.1f} minutes
📊 Total parcels updated: {total_updated:,}

RESULTS BY JURISDICTION:
"""
    for j, r in sorted(results_by_jurisdiction.items(), key=lambda x: -x[1].get("upserted", 0)):
        summary += f"  {j:<28} {r['upserted']:>8,}/{r['total_parcels']:>8,} ({r['pct']}%)\n"

    tg(summary)


if __name__ == "__main__":
    main()
