#!/usr/bin/env python3
"""
SUMMIT: Clean Brevard data — delete bad zone_codes, dedup, re-fill gaps.
Step 1: Delete records with USE_CODE descriptions as zone_code
Step 2: Dedup on parcel_id (keep latest)
Step 3: Audit what's left per jurisdiction
Step 4: Re-fill gaps using county + municipal spatial joins
"""
import httpx, json, os, sys, time
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
MGMT_KEY = "sbp_cbf04a175a130c466eddbe40a3f49b79aaec6214"
PROJECT_REF = "mocerqjnksmhcjzxrewo"
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

GIS_ZONING = "https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0"
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"
MEL_ZONING = "https://maps.mlbfl.org/services/rest/services/AGOL/CommunityDevelopmentViewer_AGOL/MapServer/109"

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]})
        except: pass
    print(msg)

def mgmt_sql(sql):
    """Execute SQL via Supabase Management API."""
    resp = httpx.post(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        headers={"Authorization": f"Bearer {MGMT_KEY}", "Content-Type": "application/json"},
        json={"query": sql}, timeout=120
    )
    return resp.status_code, resp.json() if resp.status_code == 201 else resp.text

def sb_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}

def sb_count(extra_filter=""):
    h = {**sb_headers(), "Prefer": "count=exact"}
    url = f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.brevard"
    if extra_filter:
        url += f"&{extra_filter}"
    resp = client.get(url, headers=h)
    cr = resp.headers.get("content-range", "0-0/0")
    return int(cr.split("/")[1]) if "/" in cr else 0

def sb_upsert(rows):
    h = sb_headers()
    total = 0
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = client.post(f"{SUPABASE_URL}/rest/v1/zoning_assignments", headers=h, json=batch)
        if resp.status_code in (200, 201, 204):
            total += len(batch)
        time.sleep(0.3)
    return total

def main():
    start = time.time()
    before = sb_count()
    telegram(f"""🏔️ SUMMIT: CLEANUP + REFILL
Records before: {before:,}
Step 1: Delete USE_CODE descriptions from zone_code
Step 2: Dedup on parcel_id
Step 3: Audit
Step 4: Re-fill gaps
Started: {datetime.now(timezone.utc).strftime('%H:%M UTC')}""")

    # ── STEP 1: Delete bad zone_code records ──────────────────
    telegram("🏔️ Step 1: Deleting USE_CODE descriptions from zone_code...")

    bad_patterns = [
        "RESIDENCE", "VACANT", "COMMERCIAL", "INDUSTRIAL", "IMPROVED",
        "CONDOMINIUM", "MOBILE HOME", "AGRICULTURAL", "INSTITUTIONAL",
        "CHURCH", "SCHOOL", "HOSPITAL", "GOVERNMENT", "EXEMPT",
        "SINGLE FAMILY", "MULTI FAMILY", "DUPLEX", "APARTMENT",
        "MANUFACTURED", "COUNTY OWNED", "STATE OWNED", "MUNICIPAL",
        "NON-TAXABLE", "COMMON AREA", "HALF-DUPLEX", "OFFICE UNIT",
        "PROFESSIONAL", "RETAIL", "WAREHOUSE", "RESTAURANT",
    ]

    # Build SQL to delete bad records
    conditions = " OR ".join(f"zone_code ILIKE '%{p}%'" for p in bad_patterns)
    delete_sql = f"""
    DELETE FROM zoning_assignments
    WHERE county = 'brevard' AND ({conditions});
    """

    status, result = mgmt_sql(delete_sql)
    telegram(f"🏔️ Step 1: Delete bad zone_codes — SQL status {status}")

    after_delete = sb_count()
    deleted = before - after_delete
    telegram(f"🏔️ Step 1 DONE: Deleted {deleted:,} bad records. Remaining: {after_delete:,}")

    # ── STEP 2: Dedup on parcel_id ────────────────────────────
    telegram("🏔️ Step 2: Deduplicating on parcel_id (keep latest)...")

    dedup_sql = """
    DELETE FROM zoning_assignments a
    USING zoning_assignments b
    WHERE a.id < b.id
    AND a.parcel_id = b.parcel_id
    AND a.county = 'brevard'
    AND b.county = 'brevard';
    """

    status2, result2 = mgmt_sql(dedup_sql)
    telegram(f"🏔️ Step 2: Dedup — SQL status {status2}")

    after_dedup = sb_count()
    deduped = after_delete - after_dedup
    telegram(f"🏔️ Step 2 DONE: Removed {deduped:,} duplicates. Remaining: {after_dedup:,}")

    # ── STEP 3: Audit per jurisdiction ────────────────────────
    telegram("🏔️ Step 3: Auditing per jurisdiction...")

    audit_sql = """
    SELECT jurisdiction, COUNT(*) as cnt
    FROM zoning_assignments
    WHERE county = 'brevard'
    GROUP BY jurisdiction
    ORDER BY cnt DESC;
    """

    status3, result3 = mgmt_sql(audit_sql)
    if status3 == 201 and isinstance(result3, list):
        lines = []
        targets = {
            "palm_bay": 78697, "unincorporated": 75350, "melbourne": 62135,
            "cocoa": 29882, "titusville": 28118, "rockledge": 17869,
            "cocoa_beach": 10843, "west_melbourne": 10365, "satellite_beach": 8524,
            "melbourne_beach": 7337, "cape_canaveral": 7355, "indialantic": 5205,
            "indian_harbour_beach": 4496, "grant_valkaria": 3065, "malabar": 1430,
            "palm_shores": 433, "melbourne_village": 319,
            "merritt_island": 20000, "mims": 5500, "barefoot_bay": 4800, "micco": 1900,
        }
        for row in result3:
            jur = row.get("jurisdiction", "")
            cnt = row.get("cnt", 0)
            target = targets.get(jur, 0)
            if target:
                pct = cnt / target * 100
                status_icon = "✅" if pct >= 85 else "⚠️" if pct >= 50 else "❌"
            else:
                pct = 0
                status_icon = "❓"
            lines.append(f"  {status_icon} {jur:25s} {cnt:>8,} / {target:>8,} ({pct:.0f}%)")

        telegram(f"🏔️ CLEAN AUDIT:\n{chr(10).join(lines[:20])}")
    else:
        telegram(f"🏔️ Step 3: Audit query returned status {status3}")

    # ── STEP 4: Re-fill gaps using county spatial join ────────
    telegram("🏔️ Step 4: Re-filling gaps with county spatial join...")

    from shapely.geometry import Polygon, Point
    from shapely.strtree import STRtree

    # Download county zoning polygons
    features = []
    offset = 0
    while True:
        resp = client.get(f"{GIS_ZONING}/query", params={
            "where": "1=1", "outFields": "OBJECTID,ZONING",
            "returnGeometry": "true", "resultOffset": offset,
            "resultRecordCount": 1000, "f": "json"
        })
        data = resp.json()
        batch = data.get("features", [])
        if not batch: break
        features.extend(batch)
        offset += len(batch)
        if not data.get("exceededTransferLimit", False) and len(batch) < 1000: break
        time.sleep(1)

    # Build STRtree
    geometries = []
    zone_lookup = {}
    for f in features:
        geom_data = f.get("geometry", {})
        zone = f.get("attributes", {}).get("ZONING", "").strip()
        if not geom_data or not zone: continue
        rings = geom_data.get("rings", [])
        if not rings or len(rings[0]) < 3: continue
        try:
            geom = Polygon(rings[0])
            if geom.is_valid:
                idx = len(geometries)
                geometries.append(geom)
                zone_lookup[idx] = zone
        except: continue

    tree = STRtree(geometries)
    telegram(f"🏔️ County STRtree: {len(geometries)} polygons")

    # Get existing parcel_ids to skip
    telegram("🏔️ Loading existing parcel_ids to skip...")
    existing = set()
    off = 0
    while True:
        headers = {**sb_headers(), "Range": f"{off}-{off + 999}"}
        resp = client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=parcel_id&county=eq.brevard&order=id",
            headers=headers, timeout=30
        )
        rows = resp.json()
        if not rows or not isinstance(rows, list): break
        for r in rows:
            existing.add(r.get("parcel_id", ""))
        off += len(rows)
        if len(rows) < 1000: break
    telegram(f"🏔️ {len(existing):,} existing parcel_ids loaded")

    # Download ALL county parcels and fill gaps
    telegram("🏔️ Downloading all parcels + filling gaps...")
    offset = 0
    new_matched = 0
    total_scanned = 0
    buffer = []

    while True:
        try:
            resp = client.get(f"{GIS_PARCELS}/query", params={
                "where": "1=1", "outFields": "PARCEL_ID,CITY",
                "returnGeometry": "true",
                "resultOffset": offset, "resultRecordCount": 2000, "f": "json"
            })
            data = resp.json()
            batch = data.get("features", [])
            if not batch: break

            for f in batch:
                attrs = f.get("attributes", {})
                geom = f.get("geometry", {})
                pid = attrs.get("PARCEL_ID", "")
                city = (attrs.get("CITY") or "").strip().lower().replace(" ", "_")
                rings = geom.get("rings", [[]])

                if not pid or pid in existing: continue
                if not rings or not rings[0] or len(rings[0]) < 3: continue

                total_scanned += 1
                xs = [p[0] for p in rings[0]]
                ys = [p[1] for p in rings[0]]
                pt = Point(sum(xs)/len(xs), sum(ys)/len(ys))

                candidates = tree.query(pt)
                zone = None
                for idx in candidates:
                    if geometries[idx].contains(pt):
                        zone = zone_lookup.get(idx)
                        break

                if zone:
                    new_matched += 1
                    buffer.append({
                        "parcel_id": pid,
                        "zone_code": zone,
                        "jurisdiction": city if city else "unincorporated",
                        "county": "brevard",
                    })
                    existing.add(pid)

                if len(buffer) >= 5000:
                    sb_upsert(buffer)
                    buffer = []

            offset += len(batch)
            if offset % 50000 == 0:
                telegram(f"🏔️ Refill: {offset:,} scanned, {new_matched:,} new gaps filled")
            if not data.get("exceededTransferLimit", False) and len(batch) < 2000: break
            time.sleep(1)
        except Exception as e:
            print(f"Error at {offset}: {e}", file=sys.stderr)
            time.sleep(5)
            offset += 2000
            if offset > 400000: break

    if buffer:
        sb_upsert(buffer)

    # ── FINAL REPORT ──────────────────────────────────────────
    final = sb_count()
    elapsed = int(time.time() - start)

    # Final per-jurisdiction audit
    status4, result4 = mgmt_sql(audit_sql)
    jur_lines = []
    if status4 == 201 and isinstance(result4, list):
        targets = {
            "palm_bay": 78697, "unincorporated": 75350, "melbourne": 62135,
            "cocoa": 29882, "titusville": 28118, "rockledge": 17869,
            "cocoa_beach": 10843, "west_melbourne": 10365, "satellite_beach": 8524,
            "melbourne_beach": 7337, "cape_canaveral": 7355, "indialantic": 5205,
            "indian_harbour_beach": 4496, "grant_valkaria": 3065, "malabar": 1430,
            "palm_shores": 433, "melbourne_village": 319,
        }
        met = 0
        for row in result4:
            jur = row.get("jurisdiction", "")
            cnt = row.get("cnt", 0)
            target = targets.get(jur, 0)
            if target:
                pct = cnt / target * 100
                icon = "✅" if pct >= 85 else "❌"
                if pct >= 85: met += 1
                jur_lines.append(f"  {icon} {jur}: {cnt:,}/{target:,} ({pct:.0f}%)")
        jur_lines.append(f"\n  {met}/17 jurisdictions at 85%+")

    telegram(f"""🏔️ CLEANUP + REFILL COMPLETE

📊 CLEANUP:
  Before: {before:,}
  Bad zone_codes deleted: {deleted:,}
  Duplicates removed: {deduped:,}
  After cleanup: {after_dedup:,}

📊 REFILL:
  New parcels scanned: {total_scanned:,}
  New gaps filled: {new_matched:,}
  
📊 FINAL: {final:,} / 351,585 ({final/351585*100:.1f}%)

PER JURISDICTION:
{chr(10).join(jur_lines)}

⏱️ {elapsed//60}m {elapsed%60}s | 💰 $0""")

if __name__ == "__main__":
    main()
