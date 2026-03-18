#!/usr/bin/env python3
"""
MELBOURNE CLEANUP — Deduplicate, crosswalk TaxAcct→PARCEL_ID, fix county junk zones.

Problem:
  60,420 rows with PARCEL_ID format (33K good Melbourne zones + 27K junk county zones)
  32,924 rows with TaxAcct format (all good Melbourne zones, wrong key)

Strategy:
  1. Download TaxAcct→PARCEL_ID crosswalk from BCPAO (Melbourne parcels)
  2. For each TaxAcct row: find matching PARCEL_ID, upsert with correct key + zone
  3. Delete ALL TaxAcct-format rows
  4. For remaining PARCEL_ID rows with county junk zones: query Melbourne zoning layer 109
  5. Verify final count
"""
import httpx, json, os, sys, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"
MEL_ZONING = "https://maps.mlbfl.org/services/rest/services/AGOL/CommunityDevelopmentViewer_AGOL/MapServer/109"

COUNTY_JUNK_PREFIXES = ("PUD", "RU-", "BU-", "EU-", "RR-", "AU", "GU", "IU", "TR-", "RP")

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]})
        except: pass
    print(msg)

def sb_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}

def sb_upsert(rows):
    total = 0
    h = sb_headers()
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = client.post(f"{SUPABASE_URL}/rest/v1/zoning_assignments", headers=h, json=batch)
        if resp.status_code in (200, 201, 204):
            total += len(batch)
        else:
            print(f"[upsert] {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        time.sleep(0.3)
    return total

def sb_delete_batch(ids):
    """Delete rows by id list."""
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    total = 0
    for i in range(0, len(ids), 200):
        batch = ids[i:i+200]
        id_filter = ",".join(str(x) for x in batch)
        resp = client.delete(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?id=in.({id_filter})",
            headers=h
        )
        if resp.status_code in (200, 204):
            total += len(batch)
        else:
            print(f"[delete] {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        time.sleep(0.3)
    return total

def sb_count(extra_filter=""):
    h = sb_headers()
    h["Prefer"] = "count=exact"
    url = f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&jurisdiction=eq.melbourne{extra_filter}"
    resp = client.get(url, headers=h)
    cr = resp.headers.get("content-range", "")
    return int(cr.split("/")[1]) if "/" in cr else 0

def main():
    start = time.time()
    
    before_total = sb_count()
    before_taxacct = sb_count("&parcel_id=not.ilike.*%20*")
    before_parcelid = sb_count("&parcel_id=ilike.*%20*")
    
    telegram(f"""🏔️ MELBOURNE CLEANUP STARTING
Before: {before_total:,} total ({before_parcelid:,} PARCEL_ID + {before_taxacct:,} TaxAcct)
Step 1: Build TaxAcct→PARCEL_ID crosswalk from BCPAO
Step 2: Upsert TaxAcct zones with correct PARCEL_ID keys
Step 3: Delete TaxAcct-format rows
Step 4: Fix remaining county junk zones via Melbourne layer 109""")
    
    # ═══ STEP 1: Build TaxAcct→PARCEL_ID crosswalk ═══
    telegram("🏔️ Step 1: Downloading BCPAO Melbourne parcels (TaxAcct + PARCEL_ID)...")
    crosswalk = {}  # TaxAcct → {parcel_id, cx, cy}
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
            print(f"BCPAO error at {offset}: {e}", file=sys.stderr)
            time.sleep(5)
            offset += 2000
            if offset > 80000: break
    
    telegram(f"🏔️ Step 1: {len(crosswalk):,} TaxAcct→PARCEL_ID mappings built")
    
    # ═══ STEP 2: Read TaxAcct rows, crosswalk, upsert with correct PARCEL_ID ═══
    telegram("🏔️ Step 2: Crosswalking TaxAcct rows → PARCEL_ID format...")
    taxacct_rows = []
    taxacct_ids_to_delete = []
    offset = 0
    while True:
        resp = client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?jurisdiction=eq.melbourne&parcel_id=not.ilike.*%20*&select=id,parcel_id,zone_code&offset={offset}&limit=1000&order=id.asc",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        )
        data = resp.json()
        if not data: break
        for r in data:
            taxacct_ids_to_delete.append(r["id"])
            mapping = crosswalk.get(r["parcel_id"])
            if mapping:
                taxacct_rows.append({
                    "parcel_id": mapping["parcel_id"],
                    "zone_code": r["zone_code"],
                    "jurisdiction": "melbourne",
                    "county": "brevard",
                })
        offset += len(data)
        if len(data) < 1000: break
        time.sleep(0.3)
    
    # Upsert crosswalked rows (this will UPDATE existing PARCEL_ID rows if zone conflicts)
    crosswalked = 0
    if taxacct_rows:
        crosswalked = sb_upsert(taxacct_rows)
    
    telegram(f"🏔️ Step 2: {len(taxacct_rows):,} crosswalked, {crosswalked:,} upserted (overwrites county junk)")
    
    # ═══ STEP 3: Delete TaxAcct-format rows ═══
    telegram(f"🏔️ Step 3: Deleting {len(taxacct_ids_to_delete):,} TaxAcct-format rows...")
    deleted = sb_delete_batch(taxacct_ids_to_delete)
    telegram(f"🏔️ Step 3: {deleted:,} TaxAcct rows deleted")
    
    # ═══ STEP 4: Fix remaining county junk zones via Melbourne layer 109 ═══
    # First count remaining junk
    time.sleep(1)
    junk_parcel_ids = []
    junk_centroids = {}
    offset = 0
    while True:
        # Get PARCEL_ID rows that still have county junk zone codes
        filters = "&or=(zone_code.like.PUD*,zone_code.like.RU-*,zone_code.like.BU-*,zone_code.like.EU-*,zone_code.like.RR-*,zone_code.like.AU*,zone_code.like.GU*,zone_code.like.IU*,zone_code.like.TR-*,zone_code.like.RP*)"
        resp = client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?jurisdiction=eq.melbourne&parcel_id=ilike.*%20*{filters}&select=parcel_id,zone_code&offset={offset}&limit=1000&order=id.asc",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        )
        data = resp.json()
        if not data: break
        for r in data:
            junk_parcel_ids.append(r["parcel_id"])
        offset += len(data)
        if len(data) < 1000: break
        time.sleep(0.3)
    
    telegram(f"🏔️ Step 4: {len(junk_parcel_ids):,} rows still have county junk zones. Querying Melbourne layer 109...")
    
    # Build centroids from crosswalk (reverse lookup by PARCEL_ID)
    pid_to_centroid = {}
    for tax, info in crosswalk.items():
        if info["cx"] and info["cy"]:
            pid_to_centroid[info["parcel_id"]] = (info["cx"], info["cy"])
    
    # Query Melbourne zoning layer 109 per-centroid for junk parcels
    fixed_rows = []
    fix_errors = 0
    for i, pid in enumerate(junk_parcel_ids):
        centroid = pid_to_centroid.get(pid)
        if not centroid:
            fix_errors += 1
            continue
        
        try:
            resp = client.get(f"{MEL_ZONING}/query", params={
                "geometry": f"{centroid[0]},{centroid[1]}",
                "geometryType": "esriGeometryPoint",
                "inSR": "2881",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "ZONE_ALL",
                "returnGeometry": "false",
                "f": "json"
            })
            feats = resp.json().get("features", [])
            if feats:
                zone = (feats[0]["attributes"].get("ZONE_ALL") or "").strip()
                if zone:
                    fixed_rows.append({
                        "parcel_id": pid,
                        "zone_code": zone,
                        "jurisdiction": "melbourne",
                        "county": "brevard",
                    })
                else:
                    fix_errors += 1
            else:
                fix_errors += 1
        except:
            fix_errors += 1
        
        if (i + 1) % 100 == 0:
            time.sleep(0.5)
        if (i + 1) % 2000 == 0:
            telegram(f"🏔️ Step 4: {i+1}/{len(junk_parcel_ids)} queried, {len(fixed_rows)} fixed")
    
    fix_upserted = 0
    if fixed_rows:
        fix_upserted = sb_upsert(fixed_rows)
    
    telegram(f"🏔️ Step 4: {fix_upserted:,} junk zones fixed via Melbourne layer 109 ({fix_errors} no match)")
    
    # ═══ FINAL VERIFICATION ═══
    time.sleep(2)
    after_total = sb_count()
    after_taxacct = sb_count("&parcel_id=not.ilike.*%20*")
    after_junk = sb_count("&or=(zone_code.like.PUD*,zone_code.like.RU-*,zone_code.like.BU-*,zone_code.like.EU-*,zone_code.like.RR-*)")
    
    # Full county count
    h = sb_headers()
    h["Prefer"] = "count=exact"
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.brevard", headers=h)
    cr = resp.headers.get("content-range", "")
    county_total = int(cr.split("/")[1]) if "/" in cr else 0
    coverage = county_total / 351585 * 100
    
    elapsed = int(time.time() - start)
    
    telegram(f"""🏔️ MELBOURNE CLEANUP COMPLETE

📊 BEFORE:
  Melbourne: {before_total:,} ({before_parcelid:,} PARCEL_ID + {before_taxacct:,} TaxAcct)

📊 AFTER:
  Melbourne: {after_total:,} ({after_taxacct} TaxAcct remaining)
  Junk zones remaining: {after_junk:,}
  
🔧 ACTIONS:
  Crosswalked: {len(taxacct_rows):,} TaxAcct→PARCEL_ID
  Deleted: {deleted:,} TaxAcct rows
  Fixed junk zones: {fix_upserted:,}
  No match: {fix_errors}

📈 BREVARD TOTAL:
  Records: {county_total:,} / 351,585
  Coverage: {coverage:.1f}%
  
⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

if __name__ == "__main__":
    main()
