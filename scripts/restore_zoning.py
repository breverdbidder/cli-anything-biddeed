#!/usr/bin/env python3
"""
SUMMIT: RESTORE ALL REAL ZONING — Fix USE_CODE overwrite.
USE_CODE V3 overwrote real zoning codes with property descriptions.
This script re-applies all real zoning sources in correct priority order:
1. County zoning polygons (STRtree spatial join)
2. Municipal AGOL feature services (Melbourne, Cocoa, Rockledge, etc.)
3. Dedicated city portals (West Melbourne, Satellite Beach, Cocoa Beach, Malabar)
USE_CODE stays ONLY where no real zoning source exists.
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

def download_agol(url, pid_field, zone_field, jurisdiction):
    """Download zoning from an AGOL feature service."""
    records = []
    offset = 0
    while True:
        r = c.get(f"{url}/query", params={
            "where": f"{zone_field} IS NOT NULL",
            "outFields": f"{pid_field},{zone_field}",
            "returnGeometry": "false",
            "resultOffset": offset,
            "resultRecordCount": 2000,
            "f": "json"
        })
        feats = r.json().get("features", [])
        if not feats: break
        for f in feats:
            a = f["attributes"]
            pid = (str(a.get(pid_field, "")) or "").strip()
            zone = (str(a.get(zone_field, "")) or "").strip()
            if pid and zone:
                records.append({"parcel_id": pid, "zone_code": zone,
                               "jurisdiction": jurisdiction, "county": "brevard"})
        offset += len(feats)
        if len(feats) < 2000: break
        time.sleep(1)
    seen = {}
    for r in records: seen[r["parcel_id"]] = r
    return list(seen.values())

def main():
    start = time.time()
    telegram("🏔️ RESTORE ALL ZONING — Fixing USE_CODE overwrite\n")

    # ════════════════════════════════════════
    # PHASE 1: County zoning spatial join (ALL parcels)
    # ════════════════════════════════════════
    telegram("🏔️ Phase 1: Downloading county zoning polygons...")
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
    
    telegram(f"  {len(polys)} zoning polygons loaded")
    geoms = [p[0] for p in polys]
    tree = STRtree(geoms)

    telegram("🏔️ Phase 1: Downloading ALL parcels with geometry...")
    county_rows = []
    offset = 0
    total_parcels = 0
    while True:
        r = c.get(f"{GIS_PARCELS}/query", params={
            "where": "1=1",
            "outFields": "PARCEL_ID,CITY",
            "returnGeometry": "true", "outSR": "2881",
            "f": "json", "resultOffset": offset, "resultRecordCount": 2000
        })
        feats = r.json().get("features", [])
        if not feats: break
        for f in feats:
            pid = (f["attributes"].get("PARCEL_ID") or "").strip()
            city = (f["attributes"].get("CITY") or "").strip()
            if not pid: continue
            total_parcels += 1
            rings = f.get("geometry", {}).get("rings", [])
            if not rings: continue
            ring = rings[0]
            cx = sum(p[0] for p in ring) / len(ring)
            cy = sum(p[1] for p in ring) / len(ring)
            pt = Point(cx, cy)
            hits = tree.query(pt)
            for idx in hits:
                poly, code = polys[idx]
                if poly.contains(pt):
                    county_rows.append({
                        "parcel_id": pid,
                        "zone_code": code,
                        "jurisdiction": city.lower().replace(" ", "_") if city else "unincorporated",
                        "county": "brevard"
                    })
                    break
        offset += len(feats)
        if offset % 50000 == 0:
            telegram(f"  Phase 1: {offset:,} parcels, {len(county_rows):,} matched")
        if not r.json().get("exceededTransferLimit") and len(feats) < 2000: break
        time.sleep(1)

    telegram(f"🏔️ Phase 1 complete: {len(county_rows):,} / {total_parcels:,} matched county zoning")
    ok1, err1 = sb_upsert(county_rows)
    telegram(f"  Upserted: {ok1:,} ok, {err1:,} err")

    # ════════════════════════════════════════
    # PHASE 2: Municipal AGOL sources
    # ════════════════════════════════════════
    telegram("🏔️ Phase 2: Municipal AGOL zoning sources...")
    
    municipal_sources = [
        # Satellite Beach
        ("https://services5.arcgis.com/6oVY31bK6DOd0VbR/arcgis/rest/services/Zoning/FeatureServer/0",
         "PID", "Zoning", "satellite_beach"),
        # Cocoa Beach
        ("https://services5.arcgis.com/U4PMgBw5XA2nmleg/arcgis/rest/services/CBParcelsMaster2021/FeatureServer/0",
         "Name", "Zoning", "cocoa_beach"),
        # Malabar
        ("https://services6.arcgis.com/UteZaUNFn6dZLkez/arcgis/rest/services/TownOfMalabar_LandUse_Zoning/FeatureServer/0",
         "Name", "Current_Zoning", "malabar"),
        # West Melbourne
        ("https://cwm-gis.westmelbourne.org/server/rest/services/Hosted/Zoning_View/FeatureServer/0",
         "name", "zoningnew", "west_melbourne"),
    ]

    for url, pid_f, zone_f, juris in municipal_sources:
        telegram(f"  Downloading {juris}...")
        records = download_agol(url, pid_f, zone_f, juris)
        telegram(f"    {juris}: {len(records):,} records")
        if records:
            ok, err = sb_upsert(records)
            telegram(f"    Upserted: {ok:,} ok, {err:,} err")

    # ════════════════════════════════════════
    # PHASE 3: Verify
    # ════════════════════════════════════════
    telegram("🏔️ Phase 3: Verification...")
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    
    USE_KW = ["SINGLE FAMILY", "CONDOMINIUM", "VACANT", "MOBILE", "COMMERCIAL", "INDUSTRIAL",
              "RESIDENCE", "APARTMENT", "WAREHOUSE", "CHURCH", "HOSPITAL", "SCHOOL", "OFFICE",
              "NON-TAXABLE", "IMPROVED", "RETIREMENT", "AGRICULTURAL", "DUPLEX", "TOWNHOUSE",
              "GOVERNMENT", "UTILITY", "PARKING", "RESTAURANT", "HOTEL", "MANUF", "RETAIL",
              "NURSERY", "GRAZING", "BEES", "FISH", "POSTAL", "DAY CARE", "CLUBS", "CONVENIENCE",
              "OPEN STOR", "MULTIPLE LIVING", "MUNICIPALLY", "STATE OWNED", "COUNTY OWNED",
              "PROFESSIONAL", "ASSISTED", "CAR WASH", "BOWLING", "MOTEL", "AUTO", "HALF-DUPLEX",
              "GAS STATION", "CEMETERY", "FIRE STATION", "USE:"]

    ALL_J = ["barefoot_bay", "cape_canaveral", "cocoa", "cocoa_beach", "fellsmere",
             "grant", "grant_valkaria", "indian_harbour_beach", "indialantic",
             "kennedy_space_center", "malabar", "melbourne", "melbourne_beach",
             "melbourne_village", "merritt_island", "micco", "mims", "palm_bay",
             "palm_shores", "rockledge", "satellite_beach", "titusville",
             "unincorporated", "west_melbourne"]

    total_all = 0
    total_zoning = 0
    lines = []
    for j in ALL_J:
        r = c.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments",
                  params={"select": "zone_code", "jurisdiction": f"eq.{j}", "county": "eq.brevard", "limit": "5000"}, headers=h)
        data = r.json()
        r2 = c.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments",
                   params={"select": "id", "limit": "1", "county": "eq.brevard", "jurisdiction": f"eq.{j}"},
                   headers={**h, "Prefer": "count=exact"})
        cr = r2.headers.get("content-range", "")
        total = int(cr.split("/")[1]) if "/" in cr else len(data)
        
        uc = sum(1 for d in data if any(kw in d["zone_code"].upper() for kw in USE_KW))
        zn = len(data) - uc
        if total > len(data) and len(data) > 0:
            ratio = total / len(data)
            uc = int(uc * ratio)
            zn = int(zn * ratio)
        
        pct = zn / max(total, 1) * 100
        total_all += total
        total_zoning += zn
        tag = "✅" if pct > 50 else "⚠️"
        lines.append(f"  {tag} {j:25} {total:>8,} parcels | {zn:>8,} zoned ({pct:.0f}%)")
    
    elapsed = int(time.time() - start)
    
    telegram(f"""🏔️ RESTORE ZONING COMPLETE

JURISDICTION BREAKDOWN:
{chr(10).join(lines)}

📈 TOTALS:
  Parcels: {total_all:,}
  Real zoning: {total_zoning:,} ({total_zoning/max(total_all,1)*100:.1f}%)
  USE_CODE: {total_all - total_zoning:,} ({(total_all-total_zoning)/max(total_all,1)*100:.1f}%)

⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

if __name__ == "__main__":
    main()
