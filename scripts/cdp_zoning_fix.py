#!/usr/bin/env python3
"""
SUMMIT: CDP ZONING FIX — Merritt Island (19K), Barefoot Bay (4K), Micco (1K)
These are CDPs (unincorporated) — county zoning polygons DO cover them.
Previous batch missed them (only downloaded 254K of 351K parcels).
Fix: targeted download + STRtree spatial join for CDP parcels only.
"""
import httpx, json, os, sys, time
from shapely.geometry import shape, Point
from shapely import STRtree

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
GIS_ZONING = "https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0"
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

CDPS = ["MERRITT ISLAND", "BAREFOOT BAY", "MICCO", "MIMS", "GRANT", "PALM SHORES",
        "MELBOURNE VILLAGE", "GRANT VALKARIA"]

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

def main():
    start = time.time()
    telegram("🏔️ CDP ZONING FIX — Downloading county zoning polygons...")

    # Phase 1: Download ALL county zoning polygons
    polys = []
    offset = 0
    while True:
        r = c.get(f"{GIS_ZONING}/query", params={
            "where": "1=1", "outFields": "ZONING", "returnGeometry": "true",
            "f": "json", "resultOffset": offset, "resultRecordCount": 1000
        })
        feats = r.json().get("features", [])
        if not feats: break
        for f in feats:
            try:
                geom = f.get("geometry", {})
                if not geom or "rings" not in geom: continue
                code = f["attributes"].get("ZONING", "")
                if not code: continue
                poly = shape({"type": "Polygon", "coordinates": geom["rings"]})
                if poly.is_valid and not poly.is_empty:
                    polys.append((poly, str(code).strip()))
            except: pass
        offset += len(feats)
        if not r.json().get("exceededTransferLimit") and len(feats) < 1000: break
        time.sleep(1)

    telegram(f"🏔️ Phase 1: {len(polys)} zoning polygons loaded")
    
    # Build STRtree
    geoms = [p[0] for p in polys]
    tree = STRtree(geoms)

    # Phase 2: Download CDP parcels with geometry
    telegram("🏔️ Phase 2: Downloading CDP parcels with geometry...")
    results = {}
    
    for city in CDPS:
        city_key = city.lower().replace(" ", "_")
        parcels = []
        offset = 0
        while True:
            r = c.get(f"{GIS_PARCELS}/query", params={
                "where": f"CITY='{city}'",
                "outFields": "PARCEL_ID,CITY",
                "returnGeometry": "true", "outSR": "2881",
                "f": "json", "resultOffset": offset, "resultRecordCount": 2000
            })
            feats = r.json().get("features", [])
            if not feats: break
            for f in feats:
                pid = f["attributes"].get("PARCEL_ID", "")
                if not pid: continue
                rings = f.get("geometry", {}).get("rings", [])
                if not rings: continue
                ring = rings[0]
                cx = sum(p[0] for p in ring) / len(ring)
                cy = sum(p[1] for p in ring) / len(ring)
                parcels.append({"pid": pid, "cx": cx, "cy": cy, "city": city_key})
            offset += len(feats)
            if not r.json().get("exceededTransferLimit") and len(feats) < 2000: break
            time.sleep(1)
        
        # Spatial join
        matched = 0
        rows = []
        for p in parcels:
            pt = Point(p["cx"], p["cy"])
            hits = tree.query(pt)
            zone = None
            for idx in hits:
                poly, code = polys[idx]
                if poly.contains(pt):
                    zone = code
                    break
            if zone:
                matched += 1
                rows.append({
                    "parcel_id": p["pid"],
                    "zone_code": zone,
                    "jurisdiction": p["city"],
                    "county": "brevard"
                })
        
        # Upsert
        ok, err = sb_upsert(rows) if rows else (0, 0)
        results[city] = {"total": len(parcels), "matched": matched, "upserted": ok}
        telegram(f"  {city}: {len(parcels):,} parcels → {matched:,} zoned ({matched/max(len(parcels),1)*100:.0f}%) → {ok:,} upserted")

    elapsed = int(time.time() - start)
    total_matched = sum(r["matched"] for r in results.values())
    total_parcels = sum(r["total"] for r in results.values())
    
    telegram(f"""🏔️ CDP ZONING FIX COMPLETE

{chr(10).join(f"  {city:25} {r['total']:>6,} parcels → {r['matched']:>6,} zoned ({r['matched']/max(r['total'],1)*100:.0f}%)" for city, r in results.items())}

📈 TOTAL: {total_matched:,} / {total_parcels:,} matched ({total_matched/max(total_parcels,1)*100:.0f}%)
⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

if __name__ == "__main__":
    main()
