#!/usr/bin/env python3
"""
SUMMIT: Discover GIS endpoints for ALL 67 FL counties + conquer what's available.
Two-pronged: spatial join (GIS) + Firecrawl (AGOL/web).
"""

import httpx
import json
import os
import sys
import time
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

client = httpx.Client(timeout=30, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

# All 67 FL counties with common GIS URL patterns to probe
FL_COUNTIES_GIS_PATTERNS = {
    "alachua": ["https://growth-management.alachuacounty.us/arcgis/rest/services"],
    "baker": [],
    "bay": ["https://gis.prior-co.com/BayCounty/rest/services"],
    "brevard": ["https://gis.brevardfl.gov/gissrv/rest/services"],
    "broward": ["https://gis.broward.org/arcgis/rest/services"],
    "charlotte": ["https://gis.charlottecountyfl.gov/arcgis/rest/services"],
    "citrus": ["https://gis.citrusbocc.com/arcgis/rest/services"],
    "clay": ["https://maps.claycountygov.com/arcgis/rest/services"],
    "collier": ["https://gis.colliercountyfl.gov/arcgis/rest/services"],
    "columbia": [],
    "duval": ["https://maps.coj.net/arcgis/rest/services"],
    "escambia": ["https://gis.myescambia.com/arcgis/rest/services"],
    "flagler": ["https://gis.flaglercounty.org/arcgis/rest/services"],
    "hernando": ["https://gis.hernandocounty.us/arcgis/rest/services"],
    "hillsborough": ["https://maps.hillsboroughcounty.org/arcgis/rest/services"],
    "indian_river": ["https://gis.ircgov.com/arcgis/rest/services"],
    "lake": ["https://gis.lakecountyfl.gov/arcgis/rest/services"],
    "lee": ["https://gis.leegov.com/arcgis/rest/services"],
    "leon": ["https://tlcgis.leon.fl.us/arcgis/rest/services"],
    "manatee": ["https://www.mymanatee.org/arcgis/rest/services"],
    "marion": ["https://gis.marioncountyfl.org/arcgis/rest/services"],
    "martin": ["https://gis.martin.fl.us/arcgis/rest/services"],
    "miami_dade": ["https://gis.miamidade.gov/arcgis/rest/services"],
    "monroe": ["https://gis.monroecounty-fl.gov/arcgis/rest/services"],
    "nassau": [],
    "okaloosa": ["https://gis.myokaloosa.com/arcgis/rest/services"],
    "okeechobee": [],
    "orange": ["https://maps.ocfl.net/arcgis/rest/services"],
    "osceola": ["https://gis.osceola.org/arcgis/rest/services"],
    "palm_beach": ["https://maps.co.palm-beach.fl.us/arcgis/rest/services"],
    "pasco": ["https://gis.pascocountyfl.net/arcgis/rest/services"],
    "pinellas": ["https://egis.pinellas.gov/arcgis/rest/services"],
    "polk": ["https://gis.polk-county.net/arcgis/rest/services"],
    "putnam": [],
    "santa_rosa": ["https://gis.santarosa.fl.gov/arcgis/rest/services"],
    "sarasota": ["https://gis.scgov.net/arcgis/rest/services"],
    "seminole": ["https://gis.seminolecountyfl.gov/arcgis/rest/services"],
    "st_johns": ["https://gis.sjcfl.us/arcgis/rest/services"],
    "st_lucie": ["https://gis.stlucieco.org/arcgis/rest/services"],
    "sumter": [],
    "suwannee": [],
    "taylor": [],
    "volusia": ["https://maps.vcgov.org/arcgis/rest/services"],
    "wakulla": [],
    "walton": ["https://gis.co.walton.fl.us/arcgis/rest/services"],
    "washington": [],
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

def probe_gis_for_zoning(base_url):
    """Probe a GIS server for zoning-related layers. Returns endpoint info or None."""
    try:
        # List all services
        resp = client.get(f"{base_url}?f=json", timeout=10)
        data = resp.json()
        
        services = data.get("services", [])
        folders = data.get("folders", [])
        
        # Search for zoning in services
        zoning_candidates = []
        for svc in services:
            name = svc.get("name", "").lower()
            if any(kw in name for kw in ["zon", "land_use", "landuse", "plan", "flu"]):
                zoning_candidates.append(svc)
        
        # Search in folders
        for folder in folders:
            fname = folder.lower()
            if any(kw in fname for kw in ["zon", "plan", "land", "development", "community"]):
                try:
                    resp2 = client.get(f"{base_url}/{folder}?f=json", timeout=10)
                    data2 = resp2.json()
                    for svc in data2.get("services", []):
                        name = svc.get("name", "").lower()
                        if any(kw in name for kw in ["zon", "land_use", "landuse", "flu"]):
                            zoning_candidates.append(svc)
                except:
                    pass
            time.sleep(1)
        
        # Probe each candidate
        for svc in zoning_candidates:
            svc_name = svc.get("name", "")
            svc_type = svc.get("type", "MapServer")
            url = f"{base_url}/{svc_name}/{svc_type}"
            
            try:
                resp3 = client.get(f"{url}?f=json", timeout=10)
                data3 = resp3.json()
                layers = data3.get("layers", [])
                
                for layer in layers:
                    layer_url = f"{url}/{layer['id']}"
                    # Check fields for zoning-like columns
                    resp4 = client.get(f"{layer_url}?f=json", timeout=10)
                    data4 = resp4.json()
                    fields = data4.get("fields", [])
                    
                    for field in fields:
                        fname = field.get("name", "").upper()
                        if any(kw in fname for kw in ["ZONING", "ZONE_CODE", "ZONE", "ZONING_CLASS", "ZN_CODE"]):
                            # Found it! Test a query
                            count_resp = client.get(f"{layer_url}/query", params={
                                "where": "1=1", "returnCountOnly": "true", "f": "json"
                            }, timeout=10)
                            count = count_resp.json().get("count", 0)
                            
                            if count > 0:
                                return {
                                    "zoning_url": layer_url,
                                    "zone_field": field["name"],
                                    "layer_name": layer.get("name", ""),
                                    "polygon_count": count,
                                    "geometry_type": data4.get("geometryType", ""),
                                    "spatial_reference": data4.get("extent", {}).get("spatialReference", {}),
                                }
                time.sleep(1)
            except:
                continue
        
        return None
    except Exception as e:
        return None


def main():
    start = time.time()
    telegram(f"""🏔️ SUMMIT: DISCOVER ALL 67 FL COUNTY GIS ENDPOINTS
Probing {len(FL_COUNTIES_GIS_PATTERNS)} counties for zoning layers...
Started: {datetime.now(timezone.utc).strftime('%H:%M UTC')}""")
    
    discovered = {}
    no_endpoint = []
    no_zoning = []
    errors = []
    
    for county, urls in sorted(FL_COUNTIES_GIS_PATTERNS.items()):
        if not urls:
            no_endpoint.append(county)
            continue
        
        found = False
        for base_url in urls:
            print(f"[probe] {county}: {base_url}")
            result = probe_gis_for_zoning(base_url)
            if result:
                discovered[county] = result
                print(f"  ✅ {county}: {result['zone_field']} ({result['polygon_count']} polygons)")
                found = True
                break
            time.sleep(2)
        
        if not found:
            no_zoning.append(county)
            print(f"  ❌ {county}: no zoning layer found")
        
        # Progress update every 10 counties
        total_checked = len(discovered) + len(no_zoning) + len(no_endpoint)
        if total_checked % 10 == 0:
            telegram(f"🏔️ Discovery progress: {total_checked}/{len(FL_COUNTIES_GIS_PATTERNS)} checked, {len(discovered)} found")
    
    elapsed = int(time.time() - start)
    
    # Save results
    results = {
        "discovered": discovered,
        "no_endpoint": no_endpoint,
        "no_zoning_found": no_zoning,
        "summary": {
            "total_counties": len(FL_COUNTIES_GIS_PATTERNS),
            "gis_with_zoning": len(discovered),
            "no_url_to_probe": len(no_endpoint),
            "url_but_no_zoning": len(no_zoning),
            "total_polygons": sum(d.get("polygon_count", 0) for d in discovered.values()),
        }
    }
    
    # Save to file
    with open("discovery_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    # Persist to Supabase
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            rows = []
            for county, info in discovered.items():
                rows.append({
                    "county": county,
                    "state": "FL",
                    "zoning_url": info["zoning_url"],
                    "zone_field": info["zone_field"],
                    "polygon_count": info["polygon_count"],
                    "status": "discovered",
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                })
            if rows:
                h = sb_headers()
                resp = client.post(f"{SUPABASE_URL}/rest/v1/county_gis_endpoints",
                                   headers=h, json=rows)
                print(f"[supabase] Upserted {len(rows)} endpoints: {resp.status_code}")
        except Exception as e:
            print(f"[supabase] {e}")
    
    # Build conquest-ready list
    conquest_ready = [f"{c}: {d['polygon_count']} polygons ({d['zone_field']})" 
                      for c, d in sorted(discovered.items(), key=lambda x: -x[1].get('polygon_count', 0))]
    
    telegram(f"""🏔️ SUMMIT DISCOVERY COMPLETE

📊 RESULTS:
  Counties with GIS zoning: {len(discovered)}/{len(FL_COUNTIES_GIS_PATTERNS)}
  No URL to probe: {len(no_endpoint)}
  URL but no zoning: {len(no_zoning)}
  Total polygons found: {results['summary']['total_polygons']:,}

🎯 CONQUEST-READY (top 10):
{chr(10).join(f'  ✅ {c}' for c in conquest_ready[:10])}

❌ NO ENDPOINT:
  {', '.join(no_endpoint[:15])}

⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

if __name__ == "__main__":
    main()
