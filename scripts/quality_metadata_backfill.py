#!/usr/bin/env python3
"""
SUMMIT: Quality Metadata Backfill
Populates zone_source and zone_confidence for all Brevard parcels.

Logic:
  - zone_code in DOR_UC_VALUES → zone_source='use_code_crosswalk', zone_confidence='low'
  - All other zone_codes (real zoning) → zone_source='spatial_join', zone_confidence='high'
  - Rows with PENDING_SPATIAL → zone_source='spatial_join', zone_confidence='low'
  - NULL zone_code rows → skipped (not yet assigned)

Issue: #112 — Envelope Conquest Gaps → 85%+
"""
import httpx, os, sys, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

# All known DOR USE_CODE values from ingest_county.py DOR_UC_MAP
DOR_UC_VALUES = {
    "VAC-RES", "SFR", "MH", "MFR-10", "MFR-CONDO", "COOP", "RETIRE", "MISC-RES",
    "MFR", "RES-COMMON", "VAC-COM", "RETAIL", "MIXED-USE", "DEPT-STORE", "SUPER",
    "REGIONAL", "COMM-PARK", "OFFICE", "PROF-SVC", "HOTEL", "VAC-IND", "LIGHT-IND",
    "HEAVY-IND", "LUMBER", "PACKING", "MINING", "UTIL", "AUTO-SVC", "PARKING",
    "WHOLESALE", "VAC-AG", "CROP", "PASTURE", "TIMBER", "DAIRY", "BEE", "NURSERY",
    "ORCHARD", "POULTRY", "AG-OTHER", "VAC-INST", "CHURCH", "PVT-SCHOOL", "PVT-HOSP",
    "NURSING", "CEMETERY", "GOV-OTHER", "MILITARY", "FOREST-ST", "MUNI-OWNED",
    "SCHOOL-BD", "COLLEGE", "CHURCH-EX", "EDUCATION", "HOSPITAL", "NURSING-EX",
    "MISC-EXEMPT", "GOV-MUNI", "GOV-COUNTY", "GOV-STATE", "GOV-FED", "SCHOOL-PUB",
    "COLLEGE-PUB", "HOSPITAL-PUB", "GOV-SPEC", "WATER-MGMT", "CONSERVATION",
    "LEASED-GOV", "UTIL-EX", "TRANSPORT", "PARK-REC", "HISTORIC", "CULTURAL",
    "MISC-GOV", "ACREAGE-NOT",
}

c = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})


def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]})
        except Exception:
            pass
    print(msg)


def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }


def count_null_source():
    h = sb_headers()
    h["Prefer"] = "count=exact"
    resp = c.get(
        f"{SUPABASE_URL}/rest/v1/zoning_assignments"
        f"?select=id&limit=1&county=eq.brevard&zone_source=is.null&zone_code=not.is.null",
        headers=h,
    )
    cr = resp.headers.get("content-range", "")
    return int(cr.split("/")[1]) if "/" in cr else 0


def fetch_batch(offset, limit=1000):
    h = sb_headers()
    resp = c.get(
        f"{SUPABASE_URL}/rest/v1/zoning_assignments"
        f"?select=parcel_id,zone_code"
        f"&county=eq.brevard&zone_source=is.null&zone_code=not.is.null"
        f"&offset={offset}&limit={limit}",
        headers=h,
    )
    if resp.status_code != 200:
        return []
    return resp.json()


def upsert_batch(rows):
    if not rows:
        return 0
    h = sb_headers()
    ok = 0
    for i in range(0, len(rows), 500):
        batch = rows[i:i + 500]
        resp = c.post(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?on_conflict=parcel_id",
            headers=h,
            json=batch,
        )
        if resp.status_code in (200, 201, 204):
            ok += len(batch)
        else:
            print(f"  Upsert error: {resp.status_code} {resp.text[:200]}", file=sys.stderr)
        time.sleep(0.2)
    return ok


def classify(zone_code):
    """Return (zone_source, zone_confidence) for a zone_code."""
    if not zone_code:
        return None, None
    if zone_code == "PENDING_SPATIAL":
        return "spatial_join", "low"
    if zone_code.upper() in DOR_UC_VALUES:
        return "use_code_crosswalk", "low"
    return "spatial_join", "high"


def main():
    start = time.time()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_KEY required", file=sys.stderr)
        sys.exit(1)

    null_count = count_null_source()
    telegram(
        f"🏔️ QUALITY METADATA BACKFILL — Issue #112\n"
        f"📊 Rows with null zone_source: {null_count:,}\n"
        f"Strategy: DOR_UC codes → use_code_crosswalk/low, real codes → spatial_join/high"
    )

    total_processed = 0
    total_upserted = 0
    use_code_count = 0
    spatial_count = 0
    offset = 0

    while True:
        batch = fetch_batch(offset)
        if not batch:
            break

        rows = []
        for row in batch:
            parcel_id = row.get("parcel_id")
            zone_code = row.get("zone_code")
            source, confidence = classify(zone_code)
            if source and parcel_id:
                rows.append({
                    "parcel_id": parcel_id,
                    "zone_source": source,
                    "zone_confidence": confidence,
                    "county": "brevard",
                })
                if source == "use_code_crosswalk":
                    use_code_count += 1
                else:
                    spatial_count += 1

        if rows:
            upserted = upsert_batch(rows)
            total_upserted += upserted

        total_processed += len(batch)
        offset += len(batch)

        if total_processed % 10000 == 0:
            telegram(f"🏔️ Progress: {total_processed:,} processed, {total_upserted:,} upserted")

        if len(batch) < 1000:
            break

    # Final verification — query from DB
    h = sb_headers()
    h["Prefer"] = "count=exact"

    resp_spatial = c.get(
        f"{SUPABASE_URL}/rest/v1/zoning_assignments"
        f"?select=id&limit=1&county=eq.brevard&zone_source=eq.spatial_join",
        headers=h,
    )
    cr = resp_spatial.headers.get("content-range", "")
    spatial_db = int(cr.split("/")[1]) if "/" in cr else 0

    resp_uc = c.get(
        f"{SUPABASE_URL}/rest/v1/zoning_assignments"
        f"?select=id&limit=1&county=eq.brevard&zone_source=eq.use_code_crosswalk",
        headers=h,
    )
    cr = resp_uc.headers.get("content-range", "")
    uc_db = int(cr.split("/")[1]) if "/" in cr else 0

    resp_null = c.get(
        f"{SUPABASE_URL}/rest/v1/zoning_assignments"
        f"?select=id&limit=1&county=eq.brevard&zone_source=is.null&zone_code=not.is.null",
        headers=h,
    )
    cr = resp_null.headers.get("content-range", "")
    still_null = int(cr.split("/")[1]) if "/" in cr else 0

    elapsed = int(time.time() - start)
    telegram(
        f"🏔️ QUALITY METADATA BACKFILL COMPLETE\n\n"
        f"📊 Processed: {total_processed:,}\n"
        f"📊 Upserted: {total_upserted:,}\n"
        f"  spatial_join (VERIFIED DB): {spatial_db:,}\n"
        f"  use_code_crosswalk (VERIFIED DB): {uc_db:,}\n"
        f"  still null (VERIFIED DB): {still_null:,}\n"
        f"⏱️ Duration: {elapsed // 60}m {elapsed % 60}s\n"
        f"💰 Cost: $0"
    )


if __name__ == "__main__":
    main()
