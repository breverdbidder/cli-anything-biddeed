#!/usr/bin/env python3
"""
MELBOURNE FIX ZONES V2 — Fixes the on_conflict bug.
Step 2 from cleanup failed (0 upserts). ~27K rows still have county junk zones.
This script re-runs the crosswalk upsert with on_conflict=parcel_id,
then queries Melbourne layer 109 for any remaining junk.
"""
import httpx, json, os, sys, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"
MEL_ADDR = "https://maps.mlbfl.org/services/rest/services/AGOL/CommunityDevelopmentViewer_AGOL/MapServer/128"
MEL_ZONING = "https://maps.mlbfl.org/services/rest/services/AGOL/CommunityDevelopmentViewer_AGOL/MapServer/109"

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]})
        except: pass
    print(msg)

def sb_upsert(rows):
    """Upsert with on_conflict=parcel_id."""
    total = 0
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = client.post(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?on_conflict=parcel_id",
            headers=h, json=batch
        )
        if resp.status_code in (200, 201, 204):
            total += len(batch)
        else:
            print(f"[upsert] {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        time.sleep(0.3)
    return total

def sb_count(extra=""):
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Prefer": "count=exact"}
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&jurisdiction=eq.melbourne{extra}", headers=h)
    cr = resp.headers.get("content-range", "")
    return int(cr.split("/")[1]) if "/" in cr else 0

def main():
    start = time.time()
    
    before = sb_count()
    junk_before = sb_count("&or=(zone_code.like.PUD*,zone_code.like.RU-*,zone_code.like.BU-*,zone_code.like.EU-*,zone_code.like.RR-*,zone_code.eq.AU,zone_code.eq.GU,zone_code.eq.IU,zone_code.like.TR-*,zone_code.eq.RP)")
    
    telegram(f"""🏔️ MELBOURNE FIX ZONES V2 (on_conflict fix)
Melbourne: {before:,} rows, {junk_before:,} with county junk zones
Strategy: Download Melbourne address layer 128 (TaxAcct+ZONE_ALL), crosswalk to PARCEL_ID, upsert""")
    
    # ═══ STEP 1: Build TaxAcct→PARCEL_ID crosswalk from BCPAO ═══
    telegram("🏔️ Building TaxAcct→PARCEL_ID crosswalk...")
    crosswalk = {}
    offset = 0
    while True:
        try:
            resp = client.get(f"{GIS_PARCELS}/query", params={
                "where": "CITY='MELBOURNE'",
                "outFields": "TaxAcct,PARCEL_ID",
                "returnGeometry": "true",
                "resultOffset": offset, "resultRecordCount": 2000, "f": "json"
            })
            data = resp.json()
            batch = data.get("features", [])
            if not batch: break
            for f in batch:
                a = f.get("attributes", {})
                geom = f.get("geometry", {})
                tax = a.get("TaxAcct")
                pid = a.get("PARCEL_ID", "")
                if tax and pid:
                    rings = geom.get("rings", [[]])
                    cx, cy = None, None
                    if rings and rings[0] and len(rings[0]) >= 3:
                        xs = [p[0] for p in rings[0]]
                        ys = [p[1] for p in rings[0]]
                        cx, cy = sum(xs)/len(xs), sum(ys)/len(ys)
                    crosswalk[str(tax)] = {"parcel_id": pid, "cx": cx, "cy": cy}
            offset += len(batch)
            if not data.get("exceededTransferLimit", False) and len(batch) < 2000: break
            time.sleep(1)
        except Exception as e:
            print(f"Error at {offset}: {e}", file=sys.stderr)
            time.sleep(5)
            offset += 2000
            if offset > 80000: break
    
    telegram(f"🏔️ Crosswalk: {len(crosswalk):,} mappings")
    
    # ═══ STEP 2: Download Melbourne address layer 128 (has ZONE_ALL) ═══
    telegram("🏔️ Downloading Melbourne address layer 128 (ZONE_ALL)...")
    addr_zones = {}  # TaxAcct → zone
    offset = 0
    while True:
        try:
            resp = client.get(f"{MEL_ADDR}/query", params={
                "where": "ZONE_ALL IS NOT NULL AND ZONE_ALL <> ''",
                "outFields": "TaxAcct,ZONE_ALL",
                "returnGeometry": "false",
                "resultOffset": offset, "resultRecordCount": 2000, "f": "json"
            })
            data = resp.json()
            if "error" in data:
                print(f"GIS error: {data['error']}", file=sys.stderr)
                break
            batch = data.get("features", [])
            if not batch: break
            for f in batch:
                a = f.get("attributes", {})
                tax = a.get("TaxAcct")
                zone = (a.get("ZONE_ALL") or "").strip()
                if tax and zone:
                    addr_zones[str(tax)] = zone
            offset += len(batch)
            if offset % 10000 == 0:
                telegram(f"🏔️ Address layer: {offset:,} downloaded, {len(addr_zones):,} unique")
            if not data.get("exceededTransferLimit", False) and len(batch) < 2000: break
            time.sleep(2)
        except Exception as e:
            print(f"Addr error at {offset}: {e}", file=sys.stderr)
            time.sleep(5)
            offset += 2000
            if offset > 60000: break
    
    telegram(f"🏔️ Address layer: {len(addr_zones):,} TaxAcct→ZONE_ALL mappings")
    
    # ═══ STEP 3: Crosswalk and upsert ═══
    telegram("🏔️ Crosswalking TaxAcct→PARCEL_ID + ZONE_ALL, upserting...")
    rows = []
    no_crosswalk = 0
    for tax, zone in addr_zones.items():
        mapping = crosswalk.get(tax)
        if mapping:
            rows.append({
                "parcel_id": mapping["parcel_id"],
                "zone_code": zone,
                "jurisdiction": "melbourne",
                "county": "brevard",
            })
        else:
            no_crosswalk += 1
    
    # Dedupe by parcel_id (keep first)
    seen = set()
    unique = []
    for r in rows:
        if r["parcel_id"] not in seen:
            seen.add(r["parcel_id"])
            unique.append(r)
    
    upserted = sb_upsert(unique)
    telegram(f"🏔️ Upserted: {upserted:,} / {len(unique):,} unique ({no_crosswalk} no crosswalk)")
    
    # ═══ STEP 4: Query layer 109 for any remaining junk ═══
    time.sleep(1)
    junk_remaining = sb_count("&or=(zone_code.like.PUD*,zone_code.like.RU-*,zone_code.like.BU-*,zone_code.like.EU-*,zone_code.like.RR-*,zone_code.eq.AU,zone_code.eq.GU,zone_code.eq.IU,zone_code.like.TR-*,zone_code.eq.RP)")
    
    if junk_remaining > 0:
        telegram(f"🏔️ {junk_remaining:,} still junk. Querying Melbourne layer 109 per-centroid...")
        
        # Get junk parcel_ids
        junk_pids = []
        offset = 0
        while True:
            resp = client.get(
                f"{SUPABASE_URL}/rest/v1/zoning_assignments?jurisdiction=eq.melbourne&or=(zone_code.like.PUD*,zone_code.like.RU-*,zone_code.like.BU-*,zone_code.like.EU-*,zone_code.like.RR-*,zone_code.eq.AU,zone_code.eq.GU,zone_code.eq.IU,zone_code.like.TR-*,zone_code.eq.RP)&select=parcel_id&offset={offset}&limit=1000&order=id.asc",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
            )
            data = resp.json()
            if not data: break
            junk_pids.extend(r["parcel_id"] for r in data)
            if len(data) < 1000: break
            offset += 1000
            time.sleep(0.3)
        
        # Build pid→centroid lookup
        pid_to_centroid = {info["parcel_id"]: (info["cx"], info["cy"]) for info in crosswalk.values() if info["cx"]}
        
        fixed = []
        errors = 0
        for i, pid in enumerate(junk_pids):
            c = pid_to_centroid.get(pid)
            if not c:
                errors += 1
                continue
            try:
                resp = client.get(f"{MEL_ZONING}/query", params={
                    "geometry": f"{c[0]},{c[1]}",
                    "geometryType": "esriGeometryPoint",
                    "inSR": "2881",
                    "spatialRel": "esriSpatialRelIntersects",
                    "outFields": "ZONE_ALL",
                    "returnGeometry": "false",
                    "f": "json"
                })
                feats = resp.json().get("features", [])
                if feats:
                    z = (feats[0]["attributes"].get("ZONE_ALL") or "").strip()
                    if z:
                        fixed.append({"parcel_id": pid, "zone_code": z, "jurisdiction": "melbourne", "county": "brevard"})
                    else:
                        errors += 1
                else:
                    errors += 1
            except:
                errors += 1
            if (i+1) % 50 == 0:
                time.sleep(0.3)
            if (i+1) % 2000 == 0:
                telegram(f"🏔️ Layer 109: {i+1}/{len(junk_pids)}, {len(fixed)} fixed")
        
        fix_upserted = sb_upsert(fixed) if fixed else 0
        telegram(f"🏔️ Layer 109: {fix_upserted:,} fixed, {errors} no match")
    
    # ═══ FINAL ═══
    time.sleep(2)
    after = sb_count()
    junk_after = sb_count("&or=(zone_code.like.PUD*,zone_code.like.RU-*,zone_code.like.BU-*,zone_code.like.EU-*,zone_code.like.RR-*,zone_code.eq.AU,zone_code.eq.GU,zone_code.eq.IU,zone_code.like.TR-*,zone_code.eq.RP)")
    
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Prefer": "count=exact"}
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.brevard", headers=h)
    cr = resp.headers.get("content-range", "")
    county_total = int(cr.split("/")[1]) if "/" in cr else 0
    coverage = county_total / 351585 * 100
    
    elapsed = int(time.time() - start)
    
    telegram(f"""🏔️ MELBOURNE FIX ZONES V2 COMPLETE

📊 Melbourne:
  Before: {before:,} ({junk_before:,} junk)
  After: {after:,} ({junk_after:,} junk remaining)
  Crosswalked: {upserted:,}

📈 BREVARD TOTAL:
  Records: {county_total:,} / 351,585
  Coverage: {coverage:.1f}%

⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

if __name__ == "__main__":
    main()
