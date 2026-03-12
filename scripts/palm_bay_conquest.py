#!/usr/bin/env python3
"""
SUMMIT: PALM BAY CONQUEST V2
V1 bug: Parcel query returned 0 — wrong layer ID or field names.
V2: Try all layer IDs (0,1), try MapServer + FeatureServer, probe fields first.
"""
import httpx, json, os, sys, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

BASE = "https://gis.palmbayflorida.org/arcgis/rest/services"

c = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]})
        except: pass
    print(msg)

def sb_upsert(rows):
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    ok = err = 0
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = c.post(f"{SUPABASE_URL}/rest/v1/zoning_assignments?on_conflict=parcel_id",
                      headers=h, json=batch)
        if resp.status_code in (200, 201, 204): ok += len(batch)
        else: err += len(batch)
        time.sleep(0.3)
    return ok, err

def probe_layer(url):
    """Probe a layer: get fields, count, sample."""
    try:
        r = c.get(f"{url}?f=json", timeout=15)
        if r.status_code != 200:
            return None
        d = r.json()
        name = d.get("name", "?")
        fields = [f["name"] for f in d.get("fields", [])]
        geom = d.get("geometryType", "")
        
        r2 = c.get(f"{url}/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"}, timeout=15)
        count = r2.json().get("count", 0)
        
        return {"name": name, "fields": fields, "geometry": geom, "count": count, "url": url}
    except:
        return None

def main():
    start = time.time()
    telegram("🏔️ PALM BAY CONQUEST V2\n")

    # Step 1: Discover ALL layers
    telegram("🏔️ Step 1: Discovering all Palm Bay GIS layers...")
    
    services_to_check = [
        f"{BASE}/CommonServices/Parcels/MapServer",
        f"{BASE}/CommonServices/Parcels/FeatureServer",
        f"{BASE}/GrowthManagement/Zoning/MapServer",
        f"{BASE}/GrowthManagement/Zoning/FeatureServer",
        f"{BASE}/Building/IMS/MapServer",
        f"{BASE}/CommonServices/Units/MapServer",
        f"{BASE}/CommonServices/Units/FeatureServer",
    ]
    
    all_layers = []
    for svc_url in services_to_check:
        try:
            r = c.get(f"{svc_url}?f=json", timeout=15)
            if r.status_code != 200:
                continue
            d = r.json()
            layers = d.get("layers", [])
            for layer in layers:
                lid = layer["id"]
                lname = layer.get("name", "?")
                info = probe_layer(f"{svc_url}/{lid}")
                if info and info["count"] > 0:
                    has_parcel = any("parcel" in f.lower() for f in info["fields"])
                    has_zone = any(kw in " ".join(info["fields"]).upper() for kw in ["ZONE", "ZON", "COMP", "FLU", "LAND_USE"])
                    tag = ""
                    if has_parcel: tag += " [PARCEL]"
                    if has_zone: tag += " [ZONING]"
                    telegram(f"  {svc_url.split('services/')[1]}/{lid}: {lname} ({info['count']:,} features){tag}")
                    if has_parcel or has_zone:
                        all_layers.append(info)
        except Exception as e:
            telegram(f"  Error probing {svc_url.split('services/')[1]}: {str(e)[:60]}")
        time.sleep(1)
    
    # Step 2: Find best parcel layer with zoning
    telegram(f"\n🏔️ Step 2: Finding parcel + zoning data...")
    parcel_layer = None
    zoning_layer = None
    
    for info in all_layers:
        fields_upper = [f.upper() for f in info["fields"]]
        has_pid = any("PARCELID" in f or "PARCEL_ID" in f for f in fields_upper)
        has_zone = any(kw in f for f in fields_upper for kw in ["ZONING", "ZONE_ALL", "COMPPLAN", "COMP_PLAN"])
        
        if has_pid and not parcel_layer:
            parcel_layer = info
            telegram(f"  Parcel layer: {info['name']} ({info['count']:,} features)")
            telegram(f"    Fields: {[f for f in info['fields'] if any(kw in f.upper() for kw in ['PARCEL','ZONE','COMP','FLU'])]}")
            
            # Sample
            r = c.get(f"{info['url']}/query", params={
                "where": "1=1", "outFields": "*", "resultRecordCount": "3",
                "returnGeometry": "false", "f": "json"
            }, timeout=15)
            for feat in r.json().get("features", []):
                a = feat["attributes"]
                relevant = {k:v for k,v in a.items() if v and any(kw in k.upper() for kw in ["PARCEL","ZONE","COMP","ZONING"])}
                telegram(f"    Sample: {json.dumps(relevant)[:200]}")
        
        if "ZONING" in " ".join(fields_upper) and info.get("geometry") == "esriGeometryPolygon" and not zoning_layer:
            zoning_layer = info
            telegram(f"  Zoning polygon layer: {info['name']} ({info['count']:,} polygons)")

    # Step 3: Download parcels with CompPlan/zoning if available
    if parcel_layer:
        telegram(f"\n🏔️ Step 3: Downloading parcels...")
        # Find the right field names
        pid_field = next((f for f in parcel_layer["fields"] if "parcelid" in f.lower()), None)
        zone_field = next((f for f in parcel_layer["fields"] if any(kw in f.lower() for kw in ["zoning", "compplan", "comp_plan", "zone_all"])), None)
        
        if not pid_field:
            pid_field = next((f for f in parcel_layer["fields"] if "parcel" in f.lower()), None)
        
        telegram(f"  PID field: {pid_field}")
        telegram(f"  Zone field: {zone_field}")
        
        if pid_field:
            records = []
            offset = 0
            out_fields = pid_field
            if zone_field:
                out_fields += f",{zone_field}"
            
            while True:
                try:
                    r = c.get(f"{parcel_layer['url']}/query", params={
                        "where": "1=1",
                        "outFields": out_fields,
                        "returnGeometry": "true" if zoning_layer else "false",
                        "resultOffset": offset,
                        "resultRecordCount": 1000,
                        "f": "json"
                    }, timeout=30)
                    feats = r.json().get("features", [])
                    if not feats:
                        break
                    for f in feats:
                        a = f["attributes"]
                        pid = (str(a.get(pid_field, "")) or "").strip()
                        zone = (str(a.get(zone_field, "")) or "").strip() if zone_field else ""
                        if pid:
                            records.append({"pid": pid, "zone": zone, "geom": f.get("geometry")})
                    offset += len(feats)
                    if offset % 10000 == 0:
                        telegram(f"  {offset:,} parcels downloaded...")
                    if len(feats) < 1000:
                        break
                    time.sleep(1)
                except Exception as e:
                    telegram(f"  Error at offset {offset}: {e}")
                    offset += 1000
                    time.sleep(5)
                    if offset > 100000:
                        break
            
            telegram(f"  Total downloaded: {len(records):,}")
            
            # If we have zone data directly, use it
            zoned = [r for r in records if r["zone"]]
            if zoned:
                telegram(f"  With direct zoning: {len(zoned):,}")
                rows = []
                seen = set()
                for r in zoned:
                    if r["pid"] not in seen:
                        seen.add(r["pid"])
                        rows.append({"parcel_id": r["pid"], "zone_code": r["zone"],
                                    "jurisdiction": "palm_bay", "county": "brevard"})
                
                telegram(f"🏔️ Step 4: Upserting {len(rows):,} records...")
                ok, err = sb_upsert(rows)
                telegram(f"  Upserted: {ok:,} ok, {err:,} err")
            
            # If not, do spatial join with zoning polygons
            elif zoning_layer:
                telegram(f"  No direct zoning — doing spatial join with {zoning_layer['count']:,} polygons...")
                try:
                    from shapely.geometry import shape, Point
                    from shapely import STRtree
                    
                    # Download zoning polygons
                    polys = []
                    z_offset = 0
                    z_field = next((f for f in zoning_layer["fields"] if "ZONING" in f.upper()), "ZONING")
                    while True:
                        r = c.get(f"{zoning_layer['url']}/query", params={
                            "where": "1=1", "outFields": z_field,
                            "returnGeometry": "true", "resultOffset": z_offset,
                            "resultRecordCount": 1000, "f": "json"
                        })
                        feats = r.json().get("features", [])
                        if not feats: break
                        for f in feats:
                            try:
                                geom = f.get("geometry", {})
                                if not geom or "rings" not in geom: continue
                                code = f["attributes"].get(z_field, "")
                                if not code: continue
                                poly = shape({"type": "Polygon", "coordinates": geom["rings"]})
                                if poly.is_valid and not poly.is_empty:
                                    polys.append((poly, str(code).strip()))
                            except: pass
                        z_offset += len(feats)
                        if len(feats) < 1000: break
                        time.sleep(1)
                    
                    telegram(f"  {len(polys)} valid polygons, building STRtree...")
                    tree = STRtree([p[0] for p in polys])
                    
                    rows = []
                    seen = set()
                    for r in records:
                        if r["pid"] in seen: continue
                        seen.add(r["pid"])
                        geom = r.get("geom")
                        if not geom or "rings" not in geom: continue
                        ring = geom["rings"][0]
                        cx = sum(p[0] for p in ring) / len(ring)
                        cy = sum(p[1] for p in ring) / len(ring)
                        pt = Point(cx, cy)
                        for idx in tree.query(pt):
                            poly, code = polys[idx]
                            if poly.contains(pt):
                                rows.append({"parcel_id": r["pid"], "zone_code": code,
                                            "jurisdiction": "palm_bay", "county": "brevard"})
                                break
                    
                    telegram(f"  Spatial join: {len(rows):,} matched")
                    if rows:
                        ok, err = sb_upsert(rows)
                        telegram(f"  Upserted: {ok:,} ok, {err:,} err")
                except Exception as e:
                    telegram(f"  Spatial join error: {e}")
    else:
        telegram("  ❌ No parcel layer found with ParcelId field")

    elapsed = int(time.time() - start)
    telegram(f"\n🏔️ PALM BAY CONQUEST V2 COMPLETE\n⏱️ Duration: {elapsed//60}m {elapsed%60}s\n💰 Cost: $0")

if __name__ == "__main__":
    main()
