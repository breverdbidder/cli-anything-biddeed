#!/usr/bin/env python3
"""
SUMMIT: Conquer ALL Brevard County Municipalities
Squad: spatial-conquest + data-pipeline + supabase-architect + analytics + security-auditor

Intelligence gathered:
- Melbourne: maps.mlbfl.org layer 109 = Zoning Districts (polygons), layer 128 = Address Points with ZONE_ALL field
- Titusville: gis.titusville.com has PlanningInformation service
- Palm Bay: probe needed
- Cocoa: probe needed
- County parcel layer has CITY field to filter by municipality

Strategy:
1. Melbourne — use layer 109 (Zoning Districts polygons) + Shapely STRtree
2. Melbourne fallback — layer 128 has ZONE_ALL per address point (128K records, no spatial join needed!)
3. Titusville — probe gis.titusville.com for zoning polygons
4. Palm Bay + Cocoa — probe common GIS patterns
5. Remaining municipalities — filter county parcels by CITY, use county zoning layer overlap
"""

import httpx
import json
import os
import sys
import time
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

MUNICIPALITIES = {
    "melbourne": {
        "parcels_target": 62135,
        "gis_base": "https://maps.mlbfl.org/services/rest/services/AGOL/CommunityDevelopmentViewer_AGOL/MapServer",
        "zoning_layer": 109,    # Zoning Districts — POLYGON layer
        "address_layer": 128,   # Address Points — has ZONE_ALL field (128K records)
        "zone_field": "ZONE_ALL",
    },
    "titusville": {
        "parcels_target": 28118,
        "probe_urls": [
            "https://gis.titusville.com/arcgis/rest/services/PlanningInformation/MapServer",
            "https://gis.titusville.com/arcgis/rest/services/Zoning_FLU_Map/MapServer",
        ],
    },
    "palm_bay": {
        "parcels_target": 78697,
        "probe_urls": [
            "https://gis.palmbayflorida.org/arcgis/rest/services",
            "https://maps.palmbayflorida.org/arcgis/rest/services",
            "https://services.arcgis.com/palm-bay/arcgis/rest/services",
        ],
    },
    "cocoa": {
        "parcels_target": 29882,
        "probe_urls": [
            "https://gis.cocoafl.org/arcgis/rest/services",
            "https://maps.cocoafl.org/arcgis/rest/services",
        ],
    },
    "rockledge": {"parcels_target": 17869, "probe_urls": ["https://gis.cityofrockledge.org/arcgis/rest/services"]},
    "west_melbourne": {"parcels_target": 10365, "probe_urls": ["https://gis.westmelbourne.gov/arcgis/rest/services"]},
    "cocoa_beach": {"parcels_target": 10843, "probe_urls": []},
    "satellite_beach": {"parcels_target": 8524, "probe_urls": []},
    "melbourne_beach": {"parcels_target": 7337, "probe_urls": []},
    "cape_canaveral": {"parcels_target": 7355, "probe_urls": []},
    "indialantic": {"parcels_target": 5205, "probe_urls": []},
    "indian_harbour_beach": {"parcels_target": 4496, "probe_urls": []},
    "grant_valkaria": {"parcels_target": 3065, "probe_urls": []},
    "palm_shores": {"parcels_target": 433, "probe_urls": []},
    "melbourne_village": {"parcels_target": 319, "probe_urls": []},
}

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]})
        except:
            pass
    print(msg)

def sb_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}

def sb_upsert(table, rows):
    total = 0
    h = sb_headers()
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=h, json=batch)
        if resp.status_code in (200, 201, 204):
            total += len(batch)
        else:
            print(f"[upsert] {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        time.sleep(0.3)
    return total

# ── PRONG 1: Melbourne direct — Address Points already have ZONE_ALL ──
def conquer_melbourne():
    telegram("🏔️ MELBOURNE: Downloading 128K address points with ZONE_ALL...")
    
    base = MUNICIPALITIES["melbourne"]["gis_base"]
    layer = MUNICIPALITIES["melbourne"]["address_layer"]
    url = f"{base}/{layer}"
    
    all_records = []
    offset = 0
    
    while True:
        try:
            resp = client.get(f"{url}/query", params={
                "where": "ZONE_ALL IS NOT NULL AND ZONE_ALL <> ''",
                "outFields": "TaxAcct,ZONE_ALL,FLUM,Address,SiteCity,SiteZip5,Lat,Long",
                "returnGeometry": "false",
                "resultOffset": offset,
                "resultRecordCount": 2000,
                "f": "json"
            })
            data = resp.json()
            features = data.get("features", [])
            if not features:
                break
            
            for f in features:
                a = f.get("attributes", {})
                tax = a.get("TaxAcct")
                zone = a.get("ZONE_ALL", "").strip()
                if tax and zone:
                    all_records.append({
                        "parcel_id": str(tax),
                        "zone_code": zone,
                        "jurisdiction": "melbourne",
                        "county": "brevard",
                        "centroid_lat": a.get("Lat"),
                        "centroid_lon": a.get("Long"),
                    })
            
            offset += len(features)
            if offset % 20000 == 0:
                print(f"  Melbourne: {offset:,} records...")
            
            if not data.get("exceededTransferLimit", False) and len(features) < 2000:
                break
            time.sleep(2)
        except Exception as e:
            print(f"  Melbourne error at {offset}: {e}", file=sys.stderr)
            time.sleep(5)
            offset += 2000
            if offset > 200000:
                break
    
    # Deduplicate by TaxAcct
    seen = set()
    unique = []
    for r in all_records:
        if r["parcel_id"] not in seen:
            seen.add(r["parcel_id"])
            unique.append(r)
    
    # Upsert
    upserted = 0
    if unique and SUPABASE_URL:
        upserted = sb_upsert("zoning_assignments", unique)
    
    zones = {}
    for r in unique:
        z = r["zone_code"]
        zones[z] = zones.get(z, 0) + 1
    
    telegram(f"🏔️ MELBOURNE CONQUERED: {len(unique):,} parcels, {len(zones)} districts, {upserted:,} persisted")
    return len(unique), zones

# ── PRONG 2: Melbourne Zoning Districts (polygon layer for Shapely) ──
def conquer_melbourne_polygons():
    """Alternative: download zoning district polygons for Shapely join."""
    base = MUNICIPALITIES["melbourne"]["gis_base"]
    url = f"{base}/109"  # Zoning Districts layer
    
    try:
        # Probe layer
        resp = client.get(f"{url}?f=json", timeout=10)
        data = resp.json()
        fields = [f["name"] for f in data.get("fields", [])]
        geom = data.get("geometryType", "")
        print(f"  Melbourne layer 109: {geom}, fields: {fields[:10]}")
        
        count_resp = client.get(f"{url}/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"})
        count = count_resp.json().get("count", 0)
        print(f"  Melbourne zoning polygons: {count}")
        
        return count
    except Exception as e:
        print(f"  Melbourne polygons probe failed: {e}")
        return 0

# ── PRONG 3: Probe other municipalities ───────────────────────────────
def probe_municipality(name, urls):
    """Try to find zoning layers on a municipality's GIS server."""
    for url in urls:
        try:
            resp = client.get(f"{url}?f=json", timeout=10)
            data = resp.json()
            services = data.get("services", [])
            folders = data.get("folders", [])
            
            # Search for zoning
            for svc in services:
                sname = svc.get("name", "").lower()
                if any(kw in sname for kw in ["zon", "plan", "land", "flu", "community"]):
                    stype = svc.get("type", "MapServer")
                    svc_url = f"{url}/{svc['name']}/{stype}"
                    
                    try:
                        resp2 = client.get(f"{svc_url}?f=json", timeout=10)
                        data2 = resp2.json()
                        layers = data2.get("layers", [])
                        for layer in layers:
                            if any(kw in layer.get("name", "").lower() for kw in ["zon", "zone", "district"]):
                                layer_url = f"{svc_url}/{layer['id']}"
                                count = client.get(f"{layer_url}/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"}).json().get("count", 0)
                                if count > 0:
                                    return {"url": layer_url, "layer": layer["name"], "count": count}
                    except:
                        pass
            
            # Search folders
            for folder in folders:
                if any(kw in folder.lower() for kw in ["zon", "plan", "land", "community"]):
                    try:
                        resp3 = client.get(f"{url}/{folder}?f=json", timeout=10)
                        for svc in resp3.json().get("services", []):
                            stype = svc.get("type", "MapServer")
                            svc_url = f"{url}/{svc['name']}/{stype}"
                            resp4 = client.get(f"{svc_url}?f=json", timeout=10)
                            for layer in resp4.json().get("layers", []):
                                if any(kw in layer.get("name", "").lower() for kw in ["zon", "zone"]):
                                    layer_url = f"{svc_url}/{layer['id']}"
                                    count = client.get(f"{layer_url}/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"}).json().get("count", 0)
                                    if count > 0:
                                        return {"url": layer_url, "layer": layer["name"], "count": count}
                    except:
                        pass
            
            time.sleep(2)
        except:
            continue
    return None

# ── MAIN ──────────────────────────────────────────────────────────────
def main():
    start = time.time()
    total_remaining = sum(m["parcels_target"] for m in MUNICIPALITIES.values())
    
    telegram(f"""🏔️ SUMMIT: CONQUER ALL BREVARD MUNICIPALITIES
Squad: spatial-conquest + data-pipeline + supabase-architect + analytics + security-auditor
Target: {total_remaining:,} parcels across {len(MUNICIPALITIES)} municipalities
Priority: Melbourne (62K) → Palm Bay (78K) → Titusville (28K) → Cocoa (30K)
Started: {datetime.now(timezone.utc).strftime('%H:%M UTC')}""")
    
    results = {}
    
    # 1. MELBOURNE — direct address point download (no spatial join needed!)
    mel_count, mel_zones = conquer_melbourne()
    results["melbourne"] = {"parcels": mel_count, "districts": len(mel_zones), "method": "address_points"}
    
    # 2. Probe all other municipalities
    telegram("🏔️ Probing remaining municipalities for GIS endpoints...")
    
    for name, config in MUNICIPALITIES.items():
        if name == "melbourne":
            continue
        
        urls = config.get("probe_urls", [])
        if not urls:
            results[name] = {"parcels": 0, "status": "no_urls_to_probe"}
            continue
        
        print(f"[probe] {name}...")
        found = probe_municipality(name, urls)
        if found:
            results[name] = {"parcels": 0, "status": "endpoint_found", **found}
            telegram(f"🏔️ {name.upper()}: GIS found — {found['layer']} ({found['count']} features)")
        else:
            results[name] = {"parcels": 0, "status": "no_zoning_found"}
            print(f"  {name}: no zoning layer found")
        
        time.sleep(2)
    
    # 3. Summary
    elapsed = int(time.time() - start)
    total_conquered = sum(r.get("parcels", 0) for r in results.values())
    
    conquered_list = [f"{k}: {v['parcels']:,}" for k, v in results.items() if v.get("parcels", 0) > 0]
    found_list = [f"{k}: {v.get('layer','')}" for k, v in results.items() if v.get("status") == "endpoint_found"]
    missing_list = [k for k, v in results.items() if v.get("status") in ("no_zoning_found", "no_urls_to_probe") and v.get("parcels", 0) == 0]
    
    telegram(f"""🏔️ SUMMIT MUNICIPALITIES COMPLETE

📊 CONQUERED:
{chr(10).join(f'  ✅ {c}' for c in conquered_list) or '  (none yet beyond Melbourne)'}

🔍 GIS ENDPOINTS FOUND (ready for Shapely):
{chr(10).join(f'  🎯 {f}' for f in found_list) or '  (none found)'}

❌ NO GIS FOUND:
  {', '.join(missing_list[:10])}

📈 BREVARD TOTAL:
  Previously conquered: 100,390 (Unincorp + Malabar)
  This session: {total_conquered:,}
  New total: {100390 + total_conquered:,} / 351,585
  Coverage: {(100390 + total_conquered) / 351585 * 100:.1f}%

⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")
    
    # Save results
    with open("municipality_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
