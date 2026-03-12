#!/usr/bin/env python3
"""
PALM BAY V4 — Get centroids from BCPAO (works), query zoning from Palm Bay (works).
V3 bug: Palm Bay parcel geometry uses curveRings → can't extract centroids.
Fix: BCPAO GIS parcel layer has normal geometry. Get centroids there,
then query Palm Bay's zoning server at each point.
"""
import httpx, json, os, sys, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

BCPAO_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"
PB_ZONING = "https://gis.palmbayflorida.org/arcgis/rest/services/GrowthManagement/Zoning/MapServer/0"

c = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise)"})

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

def main():
    start = time.time()
    telegram("🏔️ PALM BAY V4 — BCPAO centroids + PB zoning server\n")

    # Test PB zoning
    test = None
    try:
        r = c.get(f"{PB_ZONING}/query", params={
            "geometry": "770000,1310000", "geometryType": "esriGeometryPoint",
            "spatialRel": "esriSpatialRelIntersects", "outFields": "ZONING",
            "returnGeometry": "false", "f": "json"
        }, timeout=10)
        feats = r.json().get("features", [])
        test = feats[0]["attributes"]["ZONING"] if feats else None
    except: pass
    telegram(f"  PB zoning test: {test}")
    if not test:
        telegram("  ❌ Palm Bay zoning not responding")
        return

    # Step 1: Download Palm Bay parcels from BCPAO with centroids
    telegram("🏔️ Step 1: Downloading Palm Bay parcels from BCPAO...")
    parcels = []
    offset = 0
    while True:
        r = c.get(f"{BCPAO_PARCELS}/query", params={
            "where": "CITY='PALM BAY'",
            "outFields": "PARCEL_ID",
            "returnGeometry": "true", "outSR": "2881",
            "resultOffset": offset, "resultRecordCount": 2000, "f": "json"
        })
        feats = r.json().get("features", [])
        if not feats: break
        for f in feats:
            pid = (f["attributes"].get("PARCEL_ID") or "").strip()
            if not pid: continue
            rings = f.get("geometry", {}).get("rings", [])
            if not rings: continue
            ring = rings[0]
            cx = sum(p[0] for p in ring) / len(ring)
            cy = sum(p[1] for p in ring) / len(ring)
            parcels.append({"pid": pid, "x": cx, "y": cy})
        offset += len(feats)
        if offset % 10000 == 0:
            telegram(f"  {offset:,} parcels, {len(parcels):,} with centroids")
        if not r.json().get("exceededTransferLimit") and len(feats) < 2000:
            break
        time.sleep(1)

    # Dedup
    seen = {}
    for p in parcels:
        if p["pid"] not in seen:
            seen[p["pid"]] = p
    parcels = list(seen.values())
    telegram(f"  Total unique: {len(parcels):,}")

    # Step 2: Server-side zoning lookup at Palm Bay
    telegram(f"\n🏔️ Step 2: Querying Palm Bay zoning for {len(parcels):,} parcels...")
    rows = []
    no_zone = 0

    for i, p in enumerate(parcels):
        try:
            r = c.get(f"{PB_ZONING}/query", params={
                "geometry": f"{p['x']},{p['y']}",
                "geometryType": "esriGeometryPoint",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "ZONING",
                "returnGeometry": "false",
                "f": "json"
            }, timeout=10)
            feats = r.json().get("features", [])
            if feats:
                zone = feats[0]["attributes"].get("ZONING", "")
                if zone:
                    rows.append({
                        "parcel_id": p["pid"],
                        "zone_code": zone.strip(),
                        "jurisdiction": "palm_bay",
                        "county": "brevard"
                    })
                else:
                    no_zone += 1
            else:
                no_zone += 1
        except:
            no_zone += 1

        if (i + 1) % 5000 == 0:
            telegram(f"  {i+1:,}/{len(parcels):,} — {len(rows):,} zoned ({len(rows)/(i+1)*100:.0f}%)")
        if (i + 1) % 100 == 0:
            time.sleep(0.5)

    telegram(f"\n  Final: {len(rows):,} zoned, {no_zone:,} unzoned")

    # Step 3: Upsert
    if rows:
        telegram(f"\n🏔️ Step 3: Upserting {len(rows):,} records...")
        ok, err = sb_upsert(rows)
        telegram(f"  Upserted: {ok:,} ok, {err:,} err")

    elapsed = int(time.time() - start)
    telegram(f"""
🏔️ PALM BAY V4 COMPLETE

📊 BCPAO parcels: {len(parcels):,}
📊 Zoned by PB server: {len(rows):,} ({len(rows)/max(len(parcels),1)*100:.0f}%)
📊 Unzoned: {no_zone:,}

⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

if __name__ == "__main__":
    main()
