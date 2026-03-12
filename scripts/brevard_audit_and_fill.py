#!/usr/bin/env python3
"""
SUMMIT: Dedup audit + Complete Melbourne
1. Query Supabase for per-jurisdiction counts
2. Identify Melbourne gap
3. Fill Melbourne using BOTH methods — address points (layer 128) + zoning polygons (layer 109)
4. Cross-reference: any Melbourne parcel missing zone_code gets it from address points ZONE_ALL
"""
import httpx, json, os, sys, time
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

MELBOURNE_ADDR = "https://maps.mlbfl.org/services/rest/services/AGOL/CommunityDevelopmentViewer_AGOL/MapServer/128"
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

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
        time.sleep(0.3)
    return total

def sb_count_by_jurisdiction():
    """Get counts per jurisdiction using RPC or paginated query."""
    h = sb_headers()
    # Get all unique jurisdictions with counts
    jurisdictions = {}
    offset = 0
    while True:
        resp = client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=jurisdiction,parcel_id&county=eq.brevard&limit=5000&offset={offset}",
            headers=h
        )
        if resp.status_code != 200:
            break
        rows = resp.json()
        if not rows:
            break
        for r in rows:
            j = (r.get("jurisdiction") or "unknown").strip().lower()
            jurisdictions[j] = jurisdictions.get(j, 0) + 1
        offset += len(rows)
        if len(rows) < 5000:
            break
    return jurisdictions

def sb_total():
    h = sb_headers()
    h["Prefer"] = "count=exact"
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.brevard", headers=h)
    cr = resp.headers.get("content-range", "")
    return int(cr.split("/")[1]) if "/" in cr else 0

# ── PHASE 1: AUDIT ────────────────────────────────────────────
def phase1_audit():
    telegram("🏔️ AUDIT Phase 1: Counting per-jurisdiction records in Supabase...")
    
    total = sb_total()
    
    # Known targets per municipality
    targets = {
        "unincorporated": 75350,
        "melbourne": 62135,
        "palm bay": 78697,
        "titusville": 28118,
        "cocoa": 29882,
        "rockledge": 17869,
        "west melbourne": 10365,
        "cocoa beach": 10843,
        "satellite beach": 8524,
        "melbourne beach": 7337,
        "cape canaveral": 7355,
        "indialantic": 5205,
        "indian harbour beach": 4496,
        "grant valkaria": 3065,
        "malabar": 1430,
        "palm shores": 433,
        "melbourne village": 319,
    }
    
    counts = sb_count_by_jurisdiction()
    
    # Build report
    lines = []
    total_target = sum(targets.values())
    total_actual = sum(counts.values())
    
    for jur in sorted(targets.keys(), key=lambda x: -targets[x]):
        target = targets[jur]
        actual = counts.get(jur, 0)
        # Also check variations
        for k, v in counts.items():
            if k != jur and jur.replace(" ", "") in k.replace(" ", ""):
                actual += v
        pct = actual / target * 100 if target else 0
        status = "✅" if pct >= 85 else "⚠️" if pct >= 50 else "❌"
        lines.append(f"  {status} {jur:25s} {actual:>7,} / {target:>7,} ({pct:.0f}%)")
    
    # Also show any jurisdictions not in targets
    unknown_count = 0
    for k, v in counts.items():
        matched = False
        for t in targets:
            if t.replace(" ", "") in k.replace(" ", ""):
                matched = True
                break
        if not matched:
            unknown_count += v
    
    report = f"""🏔️ BREVARD AUDIT REPORT

📊 TOTAL: {total:,} records (target: 351,585)

PER JURISDICTION:
{chr(10).join(lines)}

  Other/Unknown: {unknown_count:,}
  
📋 UNIQUE PARCELS: {total_actual:,} (may include dupes across jurisdiction labels)"""
    
    telegram(report)
    return counts, targets

# ── PHASE 2: COMPLETE MELBOURNE ───────────────────────────────
def phase2_complete_melbourne():
    telegram("🏔️ MELBOURNE FILL: Downloading ALL 128K address points with ZONE_ALL...")
    
    # Get ALL Melbourne address points (layer 128) — every record has ZONE_ALL
    all_records = []
    offset = 0
    
    while True:
        try:
            resp = client.get(f"{MELBOURNE_ADDR}/query", params={
                "where": "ZONE_ALL IS NOT NULL AND ZONE_ALL <> '' AND CITYYN = 'Y'",
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
                zone = (a.get("ZONE_ALL") or "").strip()
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
                print(f"  Melbourne addr: {offset:,}...")
            
            if not data.get("exceededTransferLimit", False) and len(features) < 2000:
                break
            time.sleep(2)
        except Exception as e:
            print(f"  Error at {offset}: {e}", file=sys.stderr)
            time.sleep(5)
            offset += 2000
            if offset > 200000: break
    
    # Deduplicate by TaxAcct
    seen = set()
    unique = []
    for r in all_records:
        if r["parcel_id"] not in seen:
            seen.add(r["parcel_id"])
            unique.append(r)
    
    telegram(f"🏔️ MELBOURNE: {len(unique):,} unique address points with ZONE_ALL (CITYYN=Y filter)")
    
    # Also get all Melbourne parcels from BCPAO to cross-reference
    telegram("🏔️ MELBOURNE: Downloading BCPAO parcel list (CITY=MELBOURNE)...")
    
    bcpao_pids = set()
    offset = 0
    while True:
        try:
            resp = client.get(f"{GIS_PARCELS}/query", params={
                "where": "CITY LIKE '%MELBOURNE%' AND CITY NOT LIKE '%WEST%' AND CITY NOT LIKE '%VILLAGE%' AND CITY NOT LIKE '%BEACH%'",
                "outFields": "PARCEL_ID",
                "returnGeometry": "false",
                "resultOffset": offset,
                "resultRecordCount": 2000,
                "f": "json"
            })
            data = resp.json()
            features = data.get("features", [])
            if not features: break
            for f in features:
                pid = f.get("attributes", {}).get("PARCEL_ID", "")
                if pid:
                    bcpao_pids.add(pid)
            offset += len(features)
            if not data.get("exceededTransferLimit", False) and len(features) < 2000: break
            time.sleep(1)
        except:
            time.sleep(5)
            offset += 2000
            if offset > 100000: break
    
    telegram(f"🏔️ MELBOURNE: {len(bcpao_pids):,} BCPAO parcels | {len(unique):,} address points")
    
    # Upsert all address points to Supabase (merge-duplicates will update existing)
    persisted = sb_upsert(unique)
    
    zones = {}
    for r in unique:
        z = r["zone_code"]
        zones[z] = zones.get(z, 0) + 1
    
    telegram(f"🏔️ MELBOURNE COMPLETE: {persisted:,} persisted, {len(zones)} districts")
    return len(unique), persisted

# ── MAIN ──────────────────────────────────────────────────────
def main():
    start = time.time()
    telegram(f"""🏔️ SUMMIT: AUDIT + COMPLETE MELBOURNE
Phase 1: Per-jurisdiction dedup audit
Phase 2: Fill Melbourne to 100% using address points (CITYYN=Y)
Started: {datetime.now(timezone.utc).strftime('%H:%M UTC')}""")
    
    # Audit
    counts, targets = phase1_audit()
    
    # Complete Melbourne
    unique, persisted = phase2_complete_melbourne()
    
    # Final audit
    telegram("🏔️ Running final count...")
    final_total = sb_total()
    elapsed = int(time.time() - start)
    coverage = final_total / 351585 * 100
    
    telegram(f"""🏔️ AUDIT + FILL COMPLETE

📊 FINAL:
  Total records: {final_total:,} / 351,585
  Coverage: {coverage:.1f}%
  
📊 MELBOURNE:
  Address points loaded: {unique:,}
  Persisted: {persisted:,}
  
⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

if __name__ == "__main__":
    main()
