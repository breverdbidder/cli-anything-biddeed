#!/usr/bin/env python3
"""
SUMMIT V5B: Cocoa + Rockledge — Correct AGOL Endpoints
Cocoa: services1.arcgis.com AGOL-hosted, CRS 2881 native, 8993 polygons
Rockledge: gis-rockledge.cityofrockledge.org, FeatureServer/0

Pattern: BCPAO centroids → point query against city zoning → Supabase upsert
"""
import httpx, json, os, time
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

BCPAO = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

CITIES = {
    "cocoa": {
        "bcpao_city": "COCOA",
        "target": 29882,
        "zoning_url": "https://services1.arcgis.com/Tex1uhbqnOZPx6qT/arcgis/rest/services/Public_View_Cocoa_Zoning_with_Split_Lots_June_2023_view/FeatureServer/1",
        "zone_field": "Zoning",
        "extra_fields": "ZoneDesc",
        "needs_reproject": False,
        # Zoning extent filter — parcels outside this range won't match
        "extent_filter": {"xmin": 711088, "ymin": 1458431, "xmax": 746154, "ymax": 1484864},
    },
    "rockledge": {
        "bcpao_city": "ROCKLEDGE",
        "target": 8000,
        "zoning_url": "https://gis-rockledge.cityofrockledge.org/server/rest/services/Planning_Building_Public/FeatureServer/0",
        "zone_field": None,  # Will auto-detect
        "extra_fields": "",
        "needs_reproject": False,  # Will check at runtime
        "extent_filter": None,
    },
}

c = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise)"})

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]}, timeout=10)
        except: pass
    print(msg)

def sb_upsert(rows):
    if not rows: return 0, 0
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    ok = err = 0
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        try:
            resp = c.post(f"{SUPABASE_URL}/rest/v1/zoning_assignments?on_conflict=parcel_id",
                          headers=h, json=batch)
            if resp.status_code in (200, 201, 204): ok += len(batch)
            else: err += len(batch)
        except: err += len(batch)
        time.sleep(0.3)
    return ok, err

def main():
    start = time.time()
    telegram("🏔️ SUMMIT V5B: Cocoa + Rockledge (correct AGOL endpoints)\n")

    for city_key, cfg in CITIES.items():
        city_start = time.time()
        telegram(f"\n{'='*50}")
        telegram(f"🏔️ {city_key.upper()}")

        # Pre-flight: check endpoint
        zone_field = cfg["zone_field"]
        needs_reproject = cfg["needs_reproject"]

        try:
            r = c.get(f"{cfg['zoning_url']}?f=json", timeout=15)
            info = r.json()
            name = info.get("name", "?")
            fields = [f["name"] for f in info.get("fields", [])]
            sr = info.get("extent", {}).get("spatialReference", {})
            wkid = sr.get("latestWkid") or sr.get("wkid") or 2881
            needs_reproject = wkid not in (2881,)
            telegram(f"  ✅ Endpoint alive: {name}, SR={wkid}, fields={fields[:8]}")

            if not zone_field:
                for candidate in ["Zoning", "Zone_Code", "ZONING", "ZONE_ALL", "ZoneCode", "ZONE"]:
                    if candidate in fields:
                        zone_field = candidate
                        break
                if not zone_field:
                    for f in fields:
                        if "zon" in f.lower():
                            zone_field = f
                            break
            telegram(f"  Zone field: {zone_field}")
        except Exception as e:
            telegram(f"  ❌ Endpoint DEAD: {str(e)[:80]}")
            continue

        if not zone_field:
            telegram(f"  ❌ No zone field found. Skipping.")
            continue

        # Download parcels
        telegram(f"  📦 Downloading {cfg['bcpao_city']} parcels...")
        parcels = []
        offset = 0
        ext = cfg.get("extent_filter")
        geom_param = f"&geometry={ext['xmin']},{ext['ymin']},{ext['xmax']},{ext['ymax']}&geometryType=esriGeometryEnvelope&inSR=2881" if ext else ""

        while True:
            try:
                r = c.get(f"{BCPAO}/query", params={
                    "where": f"CITY='{cfg['bcpao_city']}'",
                    "outFields": "PARCEL_ID", "returnGeometry": "true", "outSR": "2881",
                    "resultOffset": offset, "resultRecordCount": 2000, "f": "json",
                } | ({"geometry": f"{ext['xmin']},{ext['ymin']},{ext['xmax']},{ext['ymax']}",
                      "geometryType": "esriGeometryEnvelope", "inSR": "2881"} if ext else {}))
                feats = r.json().get("features", [])
                if not feats: break
                for f in feats:
                    pid = (f["attributes"].get("PARCEL_ID") or "").strip()
                    if not pid: continue
                    rings = f.get("geometry", {}).get("rings", [])
                    if not rings or len(rings[0]) < 3: continue
                    ring = rings[0]
                    cx = sum(p[0] for p in ring) / len(ring)
                    cy = sum(p[1] for p in ring) / len(ring)
                    parcels.append({"pid": pid, "x": cx, "y": cy})
                offset += len(feats)
                if offset % 10000 == 0: telegram(f"    {offset:,} downloaded...")
                if not r.json().get("exceededTransferLimit") and len(feats) < 2000: break
                time.sleep(0.5)
            except Exception as e:
                telegram(f"    ⚠️ BCPAO error at {offset}: {str(e)[:60]}")
                time.sleep(2)
                continue

        seen = {}
        for p in parcels:
            if p["pid"] not in seen: seen[p["pid"]] = p
        parcels = list(seen.values())
        telegram(f"  📦 {len(parcels):,} unique parcels")

        if not parcels:
            telegram(f"  ❌ No parcels. Skipping.")
            continue

        # Also download ALL parcels (no extent filter) to get total
        if ext:
            r_all = c.get(f"{BCPAO}/query", params={
                "where": f"CITY='{cfg['bcpao_city']}'",
                "returnCountOnly": "true", "f": "json"})
            total_city = r_all.json().get("count", 0)
            telegram(f"  📊 {len(parcels):,} in zoning extent / {total_city:,} total city parcels")

        # CRS transform if needed
        transformer = None
        if needs_reproject:
            from pyproj import Transformer
            transformer = Transformer.from_crs("EPSG:2881", f"EPSG:{wkid}", always_xy=True)

        # Query zoning
        out_fields = zone_field
        if cfg.get("extra_fields"):
            out_fields += f",{cfg['extra_fields']}"

        telegram(f"  🔍 Querying zoning for {len(parcels):,} parcels...")
        rows = []
        misses = errors = 0
        total_upserted = 0

        for i, p in enumerate(parcels):
            try:
                qx, qy = p["x"], p["y"]
                if transformer:
                    qx, qy = transformer.transform(p["x"], p["y"])

                r = c.get(f"{cfg['zoning_url']}/query", params={
                    "geometry": f"{qx},{qy}", "geometryType": "esriGeometryPoint",
                    "spatialRel": "esriSpatialRelIntersects",
                    "outFields": out_fields, "returnGeometry": "false", "f": "json",
                }, timeout=15)
                feats = r.json().get("features", [])
                if feats:
                    zone = (feats[0]["attributes"].get(zone_field) or "").strip()
                    if zone:
                        row = {
                            "parcel_id": p["pid"],
                            "zone_code": zone,
                            "jurisdiction": city_key,
                            "county": "brevard",
                        }
                        rows.append(row)
                    else: misses += 1
                else: misses += 1
            except Exception as e:
                errors += 1
                if errors <= 3: telegram(f"    ⚠️ Error #{errors}: {str(e)[:60]}")
                time.sleep(1)
                continue

            if i % 10 == 0: time.sleep(0.1)
            if (i + 1) % 5000 == 0:
                telegram(f"    {i+1:,}/{len(parcels):,} — {len(rows):,} hits, {misses:,} misses")
            if len(rows) >= 2000:
                ok, er = sb_upsert(rows)
                total_upserted += ok
                telegram(f"    💾 Flushed {ok:,} ({er} errors)")
                rows = []

        if rows:
            ok, er = sb_upsert(rows)
            total_upserted += ok

        elapsed = time.time() - city_start
        hit_pct = (total_upserted / len(parcels) * 100) if parcels else 0
        telegram(f"\n📊 {city_key.upper()}: {total_upserted:,}/{len(parcels):,} ({hit_pct:.1f}%)")
        telegram(f"  Misses: {misses:,}, Errors: {errors:,}, Duration: {elapsed/60:.1f}m")

    elapsed_total = time.time() - start
    telegram(f"\n🏔️ SUMMIT V5B COMPLETE — {elapsed_total/60:.1f}m, $0")

if __name__ == "__main__":
    main()
