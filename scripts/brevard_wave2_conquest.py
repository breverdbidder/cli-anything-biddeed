#!/usr/bin/env python3
"""
SUMMIT WAVE 2: Conquer remaining Brevard municipalities.
Strategy: Extract hidden feature service URLs from AGOL web maps (same as Melbourne).
Squad: spatial-conquest + data-pipeline + supabase-architect + security-auditor

Melbourne approach worked because:
1. City's web app had a webmap_id
2. Webmap data contained feature service URLs
3. Feature service had zoning data per address point

Apply same technique to ALL remaining municipalities.
"""

import httpx
import json
import os
import sys
import time
import re
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

client = httpx.Client(timeout=30, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

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

# ── TECHNIQUE 1: AGOL Search — find web maps for each municipality ────
def search_agol_for_municipality(city_name):
    """Search ArcGIS Online for zoning web maps belonging to a municipality."""
    results = []
    for query in [f"zoning {city_name} florida", f"zoning {city_name} brevard", f"future land use {city_name} florida"]:
        try:
            resp = client.get("https://www.arcgis.com/sharing/rest/search", params={
                "q": query, "f": "json", "num": 10,
                "sortField": "modified", "sortOrder": "desc"
            })
            data = resp.json()
            for item in data.get("results", []):
                itype = item.get("type", "")
                title = item.get("title", "").lower()
                owner = item.get("owner", "").lower()
                if ("Feature" in itype or "Web Map" in itype) and \
                   (city_name.lower().replace("_", " ") in title or
                    city_name.lower().replace("_", "") in owner):
                    results.append({
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "type": itype,
                        "url": item.get("url", ""),
                        "owner": item.get("owner"),
                    })
            time.sleep(1)
        except:
            pass
    # Deduplicate
    seen = set()
    unique = []
    for r in results:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)
    return unique

# ── TECHNIQUE 2: Extract feature service URLs from web maps ───────────
def extract_feature_services(item_id):
    """Get feature service URLs from a web map or web app."""
    urls = []
    for endpoint in [
        f"https://www.arcgis.com/sharing/rest/content/items/{item_id}/data?f=json",
        f"https://www.arcgis.com/sharing/rest/content/items/{item_id}?f=json",
    ]:
        try:
            resp = client.get(endpoint, timeout=15)
            raw = resp.text
            # Find all MapServer/FeatureServer URLs
            found = re.findall(r'https?://[^"\']+(?:MapServer|FeatureServer)[^"\']*', raw)
            # Filter out basemap/reference layers
            for u in found:
                if not any(skip in u.lower() for skip in [
                    "arcgisonline.com", "basemap", "reference", "ocean", "imagery",
                    "world_street", "world_topo", "dark_gray", "light_gray",
                    "nationalmap.gov", "world_terrain"
                ]):
                    urls.append(u)
        except:
            pass
        time.sleep(1)
    return list(set(urls))

# ── TECHNIQUE 3: Probe feature service for zoning data ────────────────
def probe_for_zoning(url):
    """Check if a feature service URL has zoning data we can download."""
    try:
        # Remove any layer suffix to get the service root
        base = re.sub(r'/\d+$', '', url)
        
        # Get service info
        resp = client.get(f"{base}?f=json", timeout=10)
        data = resp.json()
        layers = data.get("layers", [])
        
        for layer in layers:
            lname = layer.get("name", "").lower()
            lid = layer["id"]
            
            if any(kw in lname for kw in ["zon", "zone", "district", "flu", "future land", "land use"]):
                layer_url = f"{base}/{lid}"
                
                # Get fields
                resp2 = client.get(f"{layer_url}?f=json", timeout=10)
                data2 = resp2.json()
                fields = data2.get("fields", [])
                geom_type = data2.get("geometryType", "")
                
                # Find zone field
                zone_field = None
                for field in fields:
                    fname = field["name"].upper()
                    if any(kw in fname for kw in ["ZONING", "ZONE_ALL", "ZONE_CODE", "ZONE", "ZN_", "ZONING_"]):
                        zone_field = field["name"]
                        break
                
                # Count features
                count_resp = client.get(f"{layer_url}/query", params={
                    "where": "1=1", "returnCountOnly": "true", "f": "json"
                }, timeout=10)
                count = count_resp.json().get("count", 0)
                
                if zone_field and count > 0:
                    return {
                        "url": layer_url,
                        "layer_name": layer.get("name"),
                        "zone_field": zone_field,
                        "geometry_type": geom_type,
                        "count": count,
                        "all_fields": [f["name"] for f in fields],
                    }
        
        # Also check if address point layer has zone field (Melbourne pattern)
        for layer in layers:
            lname = layer.get("name", "").lower()
            lid = layer["id"]
            if "address" in lname or "parcel" in lname:
                layer_url = f"{base}/{lid}"
                resp3 = client.get(f"{layer_url}?f=json", timeout=10)
                data3 = resp3.json()
                for field in data3.get("fields", []):
                    if any(kw in field["name"].upper() for kw in ["ZONE", "ZONING"]):
                        count = client.get(f"{layer_url}/query", params={
                            "where": "1=1", "returnCountOnly": "true", "f": "json"
                        }).json().get("count", 0)
                        if count > 0:
                            return {
                                "url": layer_url,
                                "layer_name": layer.get("name"),
                                "zone_field": field["name"],
                                "geometry_type": data3.get("geometryType", ""),
                                "count": count,
                                "pattern": "address_points_with_zone",
                            }
    except Exception as e:
        print(f"  Probe error: {e}")
    return None

# ── TECHNIQUE 4: Download zoning data from discovered endpoints ───────
def download_zoning(endpoint_info, municipality):
    """Download all zoning records from a discovered endpoint."""
    url = endpoint_info["url"]
    zone_field = endpoint_info["zone_field"]
    all_fields = endpoint_info.get("all_fields", [zone_field])
    
    # Pick useful fields
    out_fields = [zone_field]
    for f in all_fields:
        fu = f.upper()
        if any(kw in fu for kw in ["TAX", "PARCEL", "ACCOUNT", "ID", "ADDR", "ADDRESS", "LAT", "LONG", "LON"]):
            out_fields.append(f)
    
    records = []
    offset = 0
    
    while True:
        try:
            resp = client.get(f"{url}/query", params={
                "where": f"{zone_field} IS NOT NULL",
                "outFields": ",".join(out_fields[:10]),
                "returnGeometry": "true" if "Point" in endpoint_info.get("geometry_type", "") else "false",
                "resultOffset": offset,
                "resultRecordCount": 2000,
                "outSR": "4326",
                "f": "json"
            })
            data = resp.json()
            features = data.get("features", [])
            if not features:
                break
            
            for f in features:
                a = f.get("attributes", {})
                geom = f.get("geometry", {})
                zone = a.get(zone_field, "")
                if not zone or not str(zone).strip():
                    continue
                
                # Find parcel ID field
                pid = None
                for key in ["TaxAcct", "TAX_ACCOUNT", "PARCEL_ID", "ACCOUNT", "OBJECTID"]:
                    if key in a and a[key]:
                        pid = str(a[key])
                        break
                if not pid:
                    pid = f"auto_{municipality}_{offset + len(records)}"
                
                rec = {
                    "parcel_id": pid,
                    "zone_code": str(zone).strip(),
                    "jurisdiction": municipality,
                    "county": "brevard",
                }
                
                # Add lat/lon if available
                if geom:
                    rec["centroid_lat"] = geom.get("y") or geom.get("lat")
                    rec["centroid_lon"] = geom.get("x") or geom.get("lon") or geom.get("long")
                for key in ["Lat", "LAT", "LATITUDE"]:
                    if key in a and a[key]:
                        rec["centroid_lat"] = a[key]
                for key in ["Long", "LONG", "LON", "LONGITUDE"]:
                    if key in a and a[key]:
                        rec["centroid_lon"] = a[key]
                
                records.append(rec)
            
            offset += len(features)
            if offset % 10000 == 0:
                print(f"  {municipality}: {offset:,} downloaded...")
            
            if not data.get("exceededTransferLimit", False) and len(features) < 2000:
                break
            time.sleep(2)
        except Exception as e:
            print(f"  Download error at {offset}: {e}")
            time.sleep(5)
            offset += 2000
            if offset > 200000:
                break
    
    # Deduplicate
    seen = set()
    unique = []
    for r in records:
        if r["parcel_id"] not in seen:
            seen.add(r["parcel_id"])
            unique.append(r)
    
    return unique

# ── TECHNIQUE 5: Web search for municipality GIS ──────────────────────
def search_web_for_gis(city_name):
    """Try common GIS URL patterns for a municipality."""
    patterns = [
        f"https://gis.{city_name.replace('_','')}.org/arcgis/rest/services",
        f"https://gis.{city_name.replace('_','')}.com/arcgis/rest/services",
        f"https://maps.{city_name.replace('_','')}.org/arcgis/rest/services",
        f"https://gis.cityof{city_name.replace('_','')}.org/arcgis/rest/services",
        f"https://gis.cityof{city_name.replace('_','')}.com/arcgis/rest/services",
        f"https://gis.{city_name.replace('_','')}.gov/arcgis/rest/services",
    ]
    
    for url in patterns:
        try:
            resp = client.get(f"{url}?f=json", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("services") or data.get("folders"):
                    return url
        except:
            pass
    return None

# ── MAIN ──────────────────────────────────────────────────────────────
def main():
    start = time.time()
    
    remaining = {
        "palm_bay": 78697,
        "titusville": 28118,
        "cocoa": 29882,
        "rockledge": 17869,
        "west_melbourne": 10365,
        "cocoa_beach": 10843,
        "satellite_beach": 8524,
        "melbourne_beach": 7337,
        "cape_canaveral": 7355,
        "indialantic": 5205,
        "indian_harbour_beach": 4496,
        "grant_valkaria": 3065,
        "palm_shores": 433,
        "melbourne_village": 319,
    }
    
    telegram(f"""🏔️ SUMMIT WAVE 2: CONQUER REMAINING BREVARD
Squad: spatial-conquest + data-pipeline + supabase-architect + security-auditor
Technique: AGOL web map extraction (cracked Melbourne with this)
Target: {sum(remaining.values()):,} parcels across {len(remaining)} municipalities
Started: {datetime.now(timezone.utc).strftime('%H:%M UTC')}""")
    
    total_conquered = 0
    report = {}
    
    for city, target in remaining.items():
        city_display = city.replace("_", " ").title()
        print(f"\n{'='*50}")
        print(f"[{city_display}] Target: {target:,} parcels")
        
        # Step 1: Search AGOL
        print(f"  Searching AGOL...")
        agol_items = search_agol_for_municipality(city)
        print(f"  Found {len(agol_items)} AGOL items")
        
        # Step 2: Extract feature services from web maps
        all_feature_urls = []
        for item in agol_items[:5]:  # Limit to top 5
            urls = extract_feature_services(item["id"])
            if urls:
                print(f"  From '{item['title']}': {len(urls)} feature services")
                all_feature_urls.extend(urls)
            time.sleep(1)
        
        # Step 3: Also try direct GIS URL patterns
        direct_gis = search_web_for_gis(city)
        if direct_gis:
            print(f"  Direct GIS found: {direct_gis}")
            all_feature_urls.append(direct_gis)
        
        # Step 4: Probe each URL for zoning data
        endpoint = None
        for url in list(set(all_feature_urls))[:10]:
            print(f"  Probing: {url[:80]}...")
            result = probe_for_zoning(url)
            if result:
                endpoint = result
                print(f"  🎯 FOUND: {result['layer_name']} ({result['zone_field']}, {result['count']} features)")
                break
            time.sleep(1)
        
        if not endpoint:
            report[city] = {"status": "no_zoning_found", "agol_items": len(agol_items), "urls_probed": len(all_feature_urls)}
            print(f"  ❌ No zoning data found")
            telegram(f"❌ {city_display}: No zoning data found ({len(agol_items)} AGOL items, {len(all_feature_urls)} URLs probed)")
            continue
        
        # Step 5: Download zoning data
        print(f"  Downloading zoning data...")
        records = download_zoning(endpoint, city)
        
        # Step 6: Persist to Supabase
        persisted = 0
        if records and SUPABASE_URL:
            persisted = sb_upsert("zoning_assignments", records)
        
        zones = {}
        for r in records:
            z = r["zone_code"]
            zones[z] = zones.get(z, 0) + 1
        
        total_conquered += len(records)
        report[city] = {
            "status": "conquered",
            "parcels": len(records),
            "districts": len(zones),
            "persisted": persisted,
            "endpoint": endpoint["url"],
        }
        
        telegram(f"✅ {city_display}: {len(records):,} parcels, {len(zones)} districts, {persisted:,} persisted")
        time.sleep(2)
    
    # Final report
    elapsed = int(time.time() - start)
    conquered = {k: v for k, v in report.items() if v.get("status") == "conquered"}
    missing = {k: v for k, v in report.items() if v.get("status") != "conquered"}
    
    prev_total = 133324  # Unincorp + Melbourne + Malabar
    new_total = prev_total + total_conquered
    
    telegram(f"""🏔️ SUMMIT WAVE 2 COMPLETE

✅ CONQUERED THIS WAVE:
{chr(10).join(f'  {k.replace("_"," ").title()}: {v["parcels"]:,} parcels, {v["districts"]} districts' for k,v in conquered.items()) or '  (none)'}

❌ NO ZONING FOUND:
{chr(10).join(f'  {k.replace("_"," ").title()}: {v.get("agol_items",0)} AGOL items, {v.get("urls_probed",0)} URLs probed' for k,v in missing.items()) or '  (none)'}

📈 BREVARD TOTAL:
  Previous: {prev_total:,}
  This wave: {total_conquered:,}
  New total: {new_total:,} / 351,585
  Coverage: {new_total / 351585 * 100:.1f}%
  
⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")
    
    with open("wave2_results.json", "w") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    main()
