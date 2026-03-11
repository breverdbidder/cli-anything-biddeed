#!/usr/bin/env python3
"""
SUMMIT: Conquer Brevard County — ZoneWise POC
Pure data engineering. Zero LLM calls. Zero API cost.
GIS queries → Supabase upserts → Telegram reports.
"""

import httpx
import json
import os
import sys
import time
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

GIS_BASE = "https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0"
BCPAO_API = "https://www.bcpao.us/api/v1/search"

JURISDICTIONS = ["UNINCORPORATED", "TITUSVILLE", "COCOA"]
TARGET_PARCELS = 133350
SAFEGUARD_PCT = 85

client = httpx.Client(timeout=30, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

# ── Telegram ──────────────────────────────────────────────────
def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT, "text": msg}
            )
        except Exception as e:
            print(f"[telegram] {e}", file=sys.stderr)
    print(msg)

# ── Supabase helpers ──────────────────────────────────────────
def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

def sb_upsert(table, rows, on_conflict="parcel_id"):
    """Batch upsert to Supabase. Max 500 rows per request."""
    headers = sb_headers()
    headers["Prefer"] = f"resolution=merge-duplicates"
    total = 0
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = client.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers=headers,
            json=batch
        )
        if resp.status_code in (200, 201, 204):
            total += len(batch)
        else:
            print(f"[upsert] Error {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        time.sleep(0.5)
    return total

def sb_count(table, filters=""):
    """Count rows with optional filter."""
    headers = sb_headers()
    headers["Prefer"] = "count=exact"
    url = f"{SUPABASE_URL}/rest/v1/{table}?select=id&limit=1"
    if filters:
        url += f"&{filters}"
    resp = client.get(url, headers=headers)
    count_header = resp.headers.get("content-range", "")
    if "/" in count_header:
        return int(count_header.split("/")[1])
    return 0

# ── Phase 1: RECON — Enumerate zoning districts ──────────────
def phase1_recon():
    telegram("🏔️ SUMMIT Phase 1: RECON — Enumerating zoning districts...")
    
    all_districts = {}
    
    for jur in JURISDICTIONS:
        print(f"[recon] Querying {jur}...")
        resp = client.get(f"{GIS_BASE}/query", params={
            "where": f"JUR='{jur}'",
            "outFields": "ZONING",
            "returnDistinctValues": "true",
            "f": "json"
        })
        data = resp.json()
        features = data.get("features", [])
        zones = sorted(set(
            f["attributes"]["ZONING"] 
            for f in features 
            if f.get("attributes", {}).get("ZONING")
        ))
        all_districts[jur] = zones
        print(f"  {jur}: {len(zones)} districts")
        time.sleep(2)
    
    total = sum(len(z) for z in all_districts.values())
    
    msg = f"""🏔️ SUMMIT RECON COMPLETE

Unincorporated: {len(all_districts.get('UNINCORPORATED', []))} districts
Titusville: {len(all_districts.get('TITUSVILLE', []))} districts
Cocoa: {len(all_districts.get('COCOA', []))} districts
Total: {total} zoning districts across 3 jurisdictions

Proceeding to Phase 2: Zone Assignment"""
    telegram(msg)
    
    return all_districts

# ── Phase 2: SPATIAL JOIN — Bulk zone assignment ─────────────
def phase2_assign(all_districts):
    telegram("🏔️ SUMMIT Phase 2: SPATIAL JOIN — Assigning zone codes to parcels...")
    
    total_assigned = 0
    
    for jur in JURISDICTIONS:
        zones = all_districts.get(jur, [])
        jur_count = 0
        
        for zone in zones:
            offset = 0
            zone_count = 0
            
            while True:
                print(f"[assign] {jur}/{zone} offset={offset}")
                try:
                    resp = client.get(f"{GIS_BASE}/query", params={
                        "where": f"JUR='{jur}' AND ZONING='{zone}'",
                        "outFields": "PARCELID,ZONING,JUR",
                        "returnGeometry": "false",
                        "resultOffset": offset,
                        "resultRecordCount": 1000,
                        "f": "json"
                    })
                    data = resp.json()
                    features = data.get("features", [])
                    
                    if not features:
                        break
                    
                    # Build upsert rows
                    rows = []
                    for f in features:
                        attrs = f.get("attributes", {})
                        pid = attrs.get("PARCELID")
                        zcode = attrs.get("ZONING")
                        if pid and zcode:
                            rows.append({
                                "parcel_id": str(pid),
                                "zone_code": zcode,
                                "jurisdiction": jur.lower(),
                                "county": "brevard",
                                "zone_updated_at": datetime.now(timezone.utc).isoformat()
                            })
                    
                    if rows:
                        # Try upsert — if sample_properties doesn't have these columns,
                        # we store in a new zoning_assignments table
                        upserted = sb_upsert("zoning_assignments", rows)
                        zone_count += upserted
                    
                    offset += len(features)
                    
                    # Check if there are more records
                    if not data.get("exceededTransferLimit", False) and len(features) < 1000:
                        break
                    
                    time.sleep(2)  # Rate limit
                    
                except Exception as e:
                    print(f"[assign] Error {jur}/{zone}: {e}", file=sys.stderr)
                    time.sleep(5)
                    break
            
            jur_count += zone_count
            if zone_count > 0:
                print(f"  ✓ {jur}/{zone}: {zone_count} parcels")
        
        total_assigned += jur_count
        
        msg = f"🏔️ {jur}: {jur_count:,} parcels assigned zone codes"
        telegram(msg)
    
    return total_assigned

# ── Phase 3: BCPAO Photos — Fetch masterPhotoUrl ─────────────
def phase3_photos():
    telegram("🏔️ SUMMIT Phase 3: Fetching BCPAO property photos (sampling)...")
    
    # Sample approach: get photos for first 1000 parcels to validate
    # Full photo fetch is a separate long-running job
    headers = sb_headers()
    resp = client.get(
        f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=parcel_id&limit=1000",
        headers=headers
    )
    
    if resp.status_code != 200:
        telegram("⚠️ Phase 3: Could not query parcels for photo fetch")
        return 0
    
    parcels = resp.json()
    photos_found = 0
    
    for i, p in enumerate(parcels[:200]):  # Sample 200
        pid = p.get("parcel_id", "").replace("-", "").replace("*", "").replace(" ", "")
        if not pid:
            continue
        
        try:
            resp = client.get(f"{BCPAO_API}?account={pid}", headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                data = resp.json()
                photo_url = None
                if isinstance(data, list) and data:
                    photo_url = data[0].get("masterPhotoUrl")
                elif isinstance(data, dict):
                    photo_url = data.get("masterPhotoUrl")
                
                if photo_url:
                    photos_found += 1
        except Exception:
            pass
        
        if i % 50 == 0 and i > 0:
            print(f"[photos] {i}/200 checked, {photos_found} found")
        
        time.sleep(3)  # Rate limit BCPAO
    
    pct = (photos_found / min(len(parcels), 200)) * 100 if parcels else 0
    telegram(f"🏔️ PHOTOS: {photos_found}/200 sampled ({pct:.0f}% have photos)")
    
    return photos_found

# ── Phase 4: VALIDATE + REPORT ───────────────────────────────
def phase4_report(all_districts, total_assigned):
    
    # Count what we have
    total_districts = sum(len(z) for z in all_districts.values())
    coverage_pct = (total_assigned / TARGET_PARCELS * 100) if TARGET_PARCELS > 0 else 0
    safeguard_met = "✅ MET" if coverage_pct >= SAFEGUARD_PCT else f"❌ {coverage_pct:.1f}% < {SAFEGUARD_PCT}%"
    
    msg = f"""🏔️ SUMMIT COMPLETE: BREVARD COUNTY

📊 COVERAGE:
  Parcels with zone_code: {total_assigned:,}
  Target: {TARGET_PARCELS:,}
  Coverage: {coverage_pct:.1f}%
  Safeguard (85%): {safeguard_met}

📋 ZONING DISTRICTS:
  Unincorporated: {len(all_districts.get('UNINCORPORATED', []))}
  Titusville: {len(all_districts.get('TITUSVILLE', []))}
  Cocoa: {len(all_districts.get('COCOA', []))}
  Total: {total_districts}

📈 vs MALABAR BENCHMARK:
  Malabar: 1,430 parcels, 100%, 13 districts
  Tier 1: {total_assigned:,} parcels, {coverage_pct:.1f}%, {total_districts} districts

💰 COST: $0 (GIS=free, BCPAO=free, Supabase=existing)
📋 github.com/breverdbidder/cli-anything-biddeed"""
    
    telegram(msg)

# ── MAIN ──────────────────────────────────────────────────────
def main():
    telegram(f"""🏔️ SUMMIT STARTED: CONQUER BREVARD COUNTY
Target: {TARGET_PARCELS:,} parcels at {SAFEGUARD_PCT}%+ coverage
Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}""")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        telegram("❌ SUMMIT ABORTED: Missing SUPABASE_URL or SUPABASE_KEY")
        sys.exit(1)
    
    # Verify Supabase connectivity
    try:
        count = sb_count("sample_properties", "county=eq.brevard")
        print(f"[init] Brevard parcels in DB: {count}")
    except Exception as e:
        print(f"[init] Supabase check: {e}")
    
    # Create zoning_assignments table if needed
    try:
        client.post(
            f"{SUPABASE_URL}/rest/v1/rpc",
            headers=sb_headers(),
            json={"query": """
                CREATE TABLE IF NOT EXISTS zoning_assignments (
                    id BIGSERIAL PRIMARY KEY,
                    parcel_id TEXT NOT NULL,
                    zone_code TEXT,
                    jurisdiction TEXT,
                    county TEXT DEFAULT 'brevard',
                    photo_url TEXT,
                    zone_updated_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(parcel_id)
                );
                CREATE INDEX IF NOT EXISTS idx_za_parcel ON zoning_assignments(parcel_id);
                CREATE INDEX IF NOT EXISTS idx_za_zone ON zoning_assignments(zone_code);
                CREATE INDEX IF NOT EXISTS idx_za_jur ON zoning_assignments(jurisdiction);
            """}
        )
    except Exception as e:
        print(f"[init] Table creation note: {e}")
    
    # Execute phases
    districts = phase1_recon()
    total = phase2_assign(districts)
    phase3_photos()
    phase4_report(districts, total)

if __name__ == "__main__":
    main()
