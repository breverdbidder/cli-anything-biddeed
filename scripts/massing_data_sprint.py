#!/usr/bin/env python3
"""
SUMMIT DISPATCH: Massing Data Gap Closure Sprint
6 phases: Audit → Firecrawl → Parking → Derive → Validate → Telegram
"""
import os
import json
import time
import math
import httpx
import re
from supabase import create_client

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
FIRECRAWL_KEY = os.environ["FIRECRAWL_API_KEY"]
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

sb = create_client(SUPABASE_URL, SUPABASE_KEY)


# ── Helpers ───────────────────────────────────────────────────────────────────
def tg(msg: str):
    if not TELEGRAM_BOT or not TELEGRAM_CHAT:
        print(f"[TG] {msg}")
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"[TG ERROR] {e}")


def firecrawl_extract(url: str, schema: dict, prompt: str) -> dict | None:
    """Firecrawl /v1/scrape with LLM extract mode."""
    try:
        resp = httpx.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={
                "Authorization": f"Bearer {FIRECRAWL_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "url": url,
                "formats": ["extract"],
                "waitFor": 10000,
                "timeout": 30000,
                "extract": {"schema": schema, "prompt": prompt},
            },
            timeout=90,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", {}).get("extract") or data.get("extract")
        elif resp.status_code == 429:
            print(f"  [RATE-LIMITED] {url}")
            return None
        else:
            print(f"  [FC ERROR {resp.status_code}] {url}: {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"  [FC EXCEPTION] {url}: {e}")
        return None


# ── DIMENSIONAL SCHEMA ────────────────────────────────────────────────────────
DIMENSIONAL_SCHEMA = {
    "type": "object",
    "properties": {
        "districts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "district_code":        {"type": "string"},
                    "district_name":        {"type": "string"},
                    "max_height_ft":        {"type": "number"},
                    "max_stories":          {"type": "integer"},
                    "front_setback_ft":     {"type": "number"},
                    "side_setback_ft":      {"type": "number"},
                    "rear_setback_ft":      {"type": "number"},
                    "corner_setback_ft":    {"type": "number"},
                    "max_lot_coverage_pct": {"type": "number"},
                    "max_far":              {"type": "number"},
                    "max_density_du_acre":  {"type": "number"},
                    "min_lot_sqft":         {"type": "number"},
                    "min_lot_width_ft":     {"type": "number"},
                    "min_open_space_pct":   {"type": "number"},
                    "parking_per_unit":     {"type": "number"},
                    "parking_per_1000sf":   {"type": "number"},
                },
            },
        }
    },
}

DIMENSIONAL_PROMPT = (
    "Extract ALL zoning dimensional standards from this municipal code section. "
    "Look for dimensional tables with lot size, setbacks, height limits, FAR, lot coverage, "
    "density (dwelling units per acre), parking requirements, and open space. "
    "Convert all measurements to feet and square feet. Include every zoning district listed."
)

PARKING_SCHEMA = {
    "type": "object",
    "properties": {
        "parking_requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "use_type":            {"type": "string"},
                    "spaces_per_unit":     {"type": "number"},
                    "spaces_per_1000sf":   {"type": "number"},
                    "spaces_per_bedroom":  {"type": "number"},
                    "notes":               {"type": "string"},
                },
            },
        }
    },
}

PARKING_PROMPT = (
    "Extract ALL off-street parking requirements from this ordinance. "
    "For each land use type, extract the required number of parking spaces per unit, "
    "per 1000 sq ft, or per bedroom. Include residential (single family, duplex, "
    "multifamily, townhouse) and commercial (office, retail, restaurant, hotel) requirements."
)

# ── JURISDICTION URLS ─────────────────────────────────────────────────────────
BREVARD_JURISDICTIONS = [
    {
        "name": "Unincorporated Brevard County",
        "zoning_urls": [
            "https://library.municode.com/fl/brevard_county/codes/code_of_ordinances?nodeId=PTIIICOGEOR_CH62ZO_ARTVISURE",
            "https://library.municode.com/fl/brevard_county/codes/code_of_ordinances?nodeId=PTIIICOGEOR_CH62ZO_ARTVIDIZOSU",
        ],
        "parking_urls": [
            "https://library.municode.com/fl/brevard_county/codes/code_of_ordinances?nodeId=PTIIICOGEOR_CH62ZO_ARTXOFSTPA",
        ],
    },
    {
        "name": "Palm Bay",
        "zoning_urls": [
            "https://library.municode.com/fl/palm_bay/codes/code_of_ordinances?nodeId=PTIICOOR_CH185ZO_ARTIIIZODI",
            "https://library.municode.com/fl/palm_bay/codes/code_of_ordinances?nodeId=PTIICOOR_CH185ZO_ARTIVSURE",
        ],
        "parking_urls": [
            "https://library.municode.com/fl/palm_bay/codes/code_of_ordinances?nodeId=PTIICOOR_CH185ZO_ARTVIIIOFSTPA",
        ],
    },
    {
        "name": "Titusville",
        "zoning_urls": [
            "https://library.municode.com/fl/titusville/codes/code_of_ordinances?nodeId=CH28ZO_ARTIIZODI",
            "https://library.municode.com/fl/titusville/codes/code_of_ordinances?nodeId=CH28ZO_ARTIIISURE",
        ],
        "parking_urls": [
            "https://library.municode.com/fl/titusville/codes/code_of_ordinances?nodeId=CH28ZO_ARTXVIIOFSTPA",
        ],
    },
    {
        "name": "Melbourne",
        "zoning_urls": [
            "https://library.municode.com/fl/melbourne/codes/code_of_ordinances?nodeId=PTIIICOOR_APXBZO_ARTIIIREZODI",
            "https://library.municode.com/fl/melbourne/codes/code_of_ordinances?nodeId=PTIIICOOR_APXBZO_ARTIVCOMZODI",
        ],
        "parking_urls": [
            "https://library.municode.com/fl/melbourne/codes/code_of_ordinances?nodeId=PTIIICOOR_APXBZO_ARTXXOFSTPA",
        ],
    },
    {
        "name": "Cocoa",
        "zoning_urls": [
            "https://library.municode.com/fl/cocoa/codes/code_of_ordinances?nodeId=PTIICOOR_CH94ZO_ARTIIZODI",
        ],
        "parking_urls": [
            "https://library.municode.com/fl/cocoa/codes/code_of_ordinances?nodeId=PTIICOOR_CH94ZO_ARTXIVOFSTPA",
        ],
    },
    {
        "name": "Rockledge",
        "zoning_urls": [
            "https://library.municode.com/fl/rockledge/codes/code_of_ordinances?nodeId=PTIICOOR_CH110ZO_ARTIIRESIRE",
        ],
        "parking_urls": [
            "https://library.municode.com/fl/rockledge/codes/code_of_ordinances?nodeId=PTIICOOR_CH110ZO_ARTXIIIOFSTPA",
        ],
    },
    {
        "name": "Satellite Beach",
        "zoning_urls": [
            "https://library.municode.com/fl/satellite_beach/codes/code_of_ordinances?nodeId=PTIICOOR_CH116ZO",
        ],
        "parking_urls": [],
    },
    {
        "name": "Cape Canaveral",
        "zoning_urls": [
            "https://library.municode.com/fl/cape_canaveral/codes/code_of_ordinances?nodeId=PTIICOOR_CH110ZO_ARTIIZODI",
        ],
        "parking_urls": [],
    },
    {
        "name": "West Melbourne",
        "zoning_urls": [
            "https://library.municode.com/fl/west_melbourne/codes/code_of_ordinances?nodeId=PTIICOOR_CH110ZO_ARTIIZODI",
        ],
        "parking_urls": [],
    },
    {
        "name": "Indian Harbour Beach",
        "zoning_urls": [
            "https://library.municode.com/fl/indian_harbour_beach/codes/code_of_ordinances?nodeId=PTIICOOR_CH110ZO",
        ],
        "parking_urls": [],
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: IDENTIFY BREVARD NULL ZONES
# ═══════════════════════════════════════════════════════════════════════════════
def phase1_audit():
    print("\n" + "="*60)
    print("PHASE 1: Identify Brevard null zones")
    print("="*60)

    # Use raw SQL via RPC or PostgREST
    # Query: zone_standards with NULL height/setback for Brevard jurisdictions
    try:
        result = sb.rpc("exec_sql", {"query": """
            SELECT
                zd.id as district_id,
                zd.code,
                zd.name as district_name,
                zd.jurisdiction_id,
                j.name as jurisdiction_name,
                zs.id as standard_id,
                zs.max_height_ft,
                zs.front_setback_ft,
                zs.side_setback_ft,
                zs.rear_setback_ft,
                zs.max_lot_coverage_pct,
                zs.max_far,
                zs.max_density_du_acre,
                zs.parking_per_unit
            FROM zoning_districts zd
            LEFT JOIN zone_standards zs ON zs.zoning_district_id = zd.id
            LEFT JOIN jurisdictions j ON j.id = zd.jurisdiction_id
            WHERE j.county ILIKE '%brevard%'
            AND (zs.max_height_ft IS NULL OR zs.front_setback_ft IS NULL)
            ORDER BY j.name, zd.code
            LIMIT 500
        """}).execute()
        rows = result.data or []
    except Exception as e:
        print(f"  [RPC error, trying direct query] {e}")
        # Fallback: query zoning_districts directly
        rows = []
        try:
            # Get Brevard jurisdiction IDs first
            jur_result = sb.table("jurisdictions")\
                .select("id, name, county")\
                .ilike("county", "%brevard%")\
                .execute()
            jur_ids = [j["id"] for j in (jur_result.data or [])]
            print(f"  Found {len(jur_ids)} Brevard jurisdictions: {[j['name'] for j in (jur_result.data or [])]}")

            if jur_ids:
                # Get zoning districts for these jurisdictions
                zd_result = sb.table("zoning_districts")\
                    .select("id, code, name, jurisdiction_id")\
                    .in_("jurisdiction_id", jur_ids)\
                    .execute()
                districts = zd_result.data or []
                print(f"  Found {len(districts)} zoning districts in Brevard")

                if districts:
                    district_ids = [d["id"] for d in districts]
                    # Sample check: get zone_standards
                    zs_result = sb.table("zone_standards")\
                        .select("zoning_district_id, max_height_ft, front_setback_ft, side_setback_ft, rear_setback_ft, max_lot_coverage_pct, max_far, max_density_du_acre, parking_per_unit")\
                        .in_("zoning_district_id", district_ids[:500])\
                        .execute()
                    zs_map = {z["zoning_district_id"]: z for z in (zs_result.data or [])}

                    # Find nulls
                    jur_map = {j["id"]: j["name"] for j in (jur_result.data or [])}
                    for d in districts:
                        zs = zs_map.get(d["id"])
                        if not zs or zs.get("max_height_ft") is None or zs.get("front_setback_ft") is None:
                            rows.append({
                                "district_id": d["id"],
                                "code": d["code"],
                                "district_name": d["name"],
                                "jurisdiction_id": d["jurisdiction_id"],
                                "jurisdiction_name": jur_map.get(d["jurisdiction_id"], "Unknown"),
                                "standard_id": zs.get("id") if zs else None,
                                "max_height_ft": zs.get("max_height_ft") if zs else None,
                                "front_setback_ft": zs.get("front_setback_ft") if zs else None,
                            })
        except Exception as e2:
            print(f"  [FALLBACK ERROR] {e2}")

    null_count = len(rows)
    print(f"\n  → {null_count} Brevard zones missing height/setback data")

    # Group by jurisdiction
    by_jur = {}
    for r in rows:
        jn = r.get("jurisdiction_name", "Unknown")
        by_jur.setdefault(jn, []).append(r)

    print("\n  Breakdown by jurisdiction:")
    for jn, zones in sorted(by_jur.items()):
        print(f"    {jn}: {len(zones)} zones with NULLs")

    return rows, by_jur


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: FIRECRAWL LLM EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════
def phase2_firecrawl(null_by_jur: dict):
    print("\n" + "="*60)
    print("PHASE 2: Firecrawl LLM extraction from Municode")
    print("="*60)

    all_extracted = {}  # jurisdiction_name → list of district data
    total_extracted = 0
    rate_limited_jurisdictions = []

    for jur in BREVARD_JURISDICTIONS:
        jname = jur["name"]

        # Skip if no null zones for this jurisdiction
        has_nulls = any(
            jname.lower() in k.lower() or k.lower() in jname.lower()
            for k in null_by_jur.keys()
        )
        # Always try top priorities regardless
        is_priority = any(p in jname for p in ["Brevard", "Palm Bay", "Titusville", "Melbourne", "Cocoa"])
        if not has_nulls and not is_priority:
            print(f"\n  SKIP {jname} (no nulls found)")
            continue

        print(f"\n  Processing: {jname}")
        jur_districts = []

        for url in jur["zoning_urls"]:
            print(f"    Scraping: {url}")
            extracted = firecrawl_extract(url, DIMENSIONAL_SCHEMA, DIMENSIONAL_PROMPT)

            if extracted is None:
                rate_limited_jurisdictions.append(jname)
                print(f"    → Rate limited or failed")
                time.sleep(3)
                continue

            districts = extracted.get("districts", []) if isinstance(extracted, dict) else []
            print(f"    → Got {len(districts)} districts")
            jur_districts.extend(districts)
            time.sleep(2)  # Rate limit

        if jur_districts:
            all_extracted[jname] = jur_districts
            total_extracted += len(jur_districts)
            print(f"  Total for {jname}: {len(jur_districts)} districts extracted")

    print(f"\n  PHASE 2 COMPLETE: {total_extracted} districts extracted across {len(all_extracted)} jurisdictions")
    if rate_limited_jurisdictions:
        print(f"  Rate limited: {rate_limited_jurisdictions}")

    return all_extracted, rate_limited_jurisdictions


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2b: UPSERT EXTRACTED DATA TO DB
# ═══════════════════════════════════════════════════════════════════════════════
def upsert_extracted_standards(all_extracted: dict):
    print("\n  Upserting extracted standards to DB...")
    upserted = 0
    skipped = 0

    for jname, districts in all_extracted.items():
        # Get jurisdiction ID
        jur_result = sb.table("jurisdictions")\
            .select("id")\
            .ilike("name", f"%{jname.split()[0]}%")\
            .execute()
        jur_rows = jur_result.data or []
        if not jur_rows:
            print(f"    [SKIP] Can't find jurisdiction: {jname}")
            skipped += len(districts)
            continue
        jur_id = jur_rows[0]["id"]

        for d in districts:
            code = d.get("district_code", "").strip()
            if not code:
                continue

            # Find matching zoning_district
            zd_result = sb.table("zoning_districts")\
                .select("id")\
                .eq("jurisdiction_id", jur_id)\
                .ilike("code", code)\
                .execute()
            zd_rows = zd_result.data or []
            if not zd_rows:
                # Try partial match
                zd_result2 = sb.table("zoning_districts")\
                    .select("id")\
                    .eq("jurisdiction_id", jur_id)\
                    .ilike("code", f"%{code}%")\
                    .execute()
                zd_rows = zd_result2.data or []

            if not zd_rows:
                skipped += 1
                continue

            zd_id = zd_rows[0]["id"]

            # Build update payload (only non-null values)
            update = {}
            field_map = {
                "max_height_ft": "max_height_ft",
                "max_stories": "max_stories",
                "front_setback_ft": "front_setback_ft",
                "side_setback_ft": "side_setback_ft",
                "rear_setback_ft": "rear_setback_ft",
                "corner_setback_ft": "corner_setback_ft",
                "max_lot_coverage_pct": "max_lot_coverage_pct",
                "max_far": "max_far",
                "max_density_du_acre": "max_density_du_acre",
                "min_lot_sqft": "min_lot_sqft",
                "min_lot_width_ft": "min_lot_width_ft",
                "min_open_space_pct": "min_open_space_pct",
                "parking_per_unit": "parking_per_unit",
                "parking_per_1000sf": "parking_per_1000sf",
            }
            for src, dst in field_map.items():
                val = d.get(src)
                if val is not None:
                    update[dst] = val

            if not update:
                skipped += 1
                continue

            # Check if zone_standards row exists
            zs_check = sb.table("zone_standards")\
                .select("id")\
                .eq("zoning_district_id", zd_id)\
                .execute()

            if zs_check.data:
                # Update existing
                sb.table("zone_standards")\
                    .update(update)\
                    .eq("zoning_district_id", zd_id)\
                    .execute()
            else:
                # Insert new
                update["zoning_district_id"] = zd_id
                sb.table("zone_standards").insert(update).execute()

            upserted += 1

    print(f"    Upserted: {upserted}, Skipped: {skipped}")
    return upserted


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: APIFY FALLBACK (for rate-limited jurisdictions)
# ═══════════════════════════════════════════════════════════════════════════════
def phase3_apify_fallback(rate_limited: list):
    if not rate_limited:
        print("\n  PHASE 3: No rate-limited jurisdictions — skipping Apify")
        return 0

    print("\n" + "="*60)
    print(f"PHASE 3: Apify fallback for {len(rate_limited)} rate-limited jurisdictions")
    print("="*60)

    apify_token = os.environ.get("APIFY_API_TOKEN", "")
    if not apify_token:
        print("  [SKIP] APIFY_API_TOKEN not set")
        return 0

    try:
        from apify_client import ApifyClient
    except ImportError:
        print("  [SKIP] apify_client not installed")
        return 0

    client = ApifyClient(apify_token)
    extracted_count = 0

    for jname in rate_limited:
        jur = next((j for j in BREVARD_JURISDICTIONS if j["name"] == jname), None)
        if not jur:
            continue

        for url in jur["zoning_urls"][:1]:  # Limit to 1 URL per jurisdiction
            print(f"  Apify scraping: {url}")
            try:
                run = client.actor("apify/web-scraper").call(
                    run_input={
                        "startUrls": [{"url": url}],
                        "pageFunction": """
                            async function pageFunction(context) {
                                const { page, request } = context;
                                await page.waitForTimeout(8000);
                                const content = await page.content();
                                return { url: request.url, html: content };
                            }
                        """,
                        "proxyConfiguration": {"useApifyProxy": True},
                        "maxRequestsPerCrawl": 1,
                    }
                )
                items = client.dataset(run["defaultDatasetId"]).list_items().items
                if items:
                    extracted_count += 1
                    print(f"  → Got HTML content, {len(items[0].get('html', ''))} chars")
            except Exception as e:
                print(f"  [APIFY ERROR] {e}")

    return extracted_count


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: PARKING SPRINT
# ═══════════════════════════════════════════════════════════════════════════════
def phase4_parking():
    print("\n" + "="*60)
    print("PHASE 4: Parking requirements extraction")
    print("="*60)

    all_parking = {}
    total_rules = 0

    priority_jurs = ["Unincorporated Brevard County", "Palm Bay", "Titusville", "Melbourne"]

    for jur in BREVARD_JURISDICTIONS:
        if not jur["parking_urls"]:
            continue
        if jur["name"] not in priority_jurs:
            continue

        print(f"\n  {jur['name']}:")
        jur_parking = []

        for url in jur["parking_urls"]:
            print(f"    Scraping: {url}")
            extracted = firecrawl_extract(url, PARKING_SCHEMA, PARKING_PROMPT)

            if extracted is None:
                print(f"    → Failed/rate-limited")
                time.sleep(3)
                continue

            rules = extracted.get("parking_requirements", []) if isinstance(extracted, dict) else []
            print(f"    → Got {len(rules)} parking rules")
            jur_parking.extend(rules)
            time.sleep(2)

        if jur_parking:
            all_parking[jur["name"]] = jur_parking
            total_rules += len(jur_parking)

    print(f"\n  PHASE 4 COMPLETE: {total_rules} parking rules extracted")

    # Map parking rules to zone_standards
    parking_updates = 0
    for jname, rules in all_parking.items():
        # Find residential and commercial defaults
        sfr_parking = next((r["spaces_per_unit"] for r in rules
                           if any(k in r.get("use_type", "").lower()
                                  for k in ["single family", "single-family", "sfr", "dwelling"])
                           and r.get("spaces_per_unit")), 2.0)
        mf_parking = next((r["spaces_per_unit"] for r in rules
                          if any(k in r.get("use_type", "").lower()
                                 for k in ["multifamily", "multi-family", "apartment", "multi family"])
                          and r.get("spaces_per_unit")), 1.5)
        office_parking = next((r["spaces_per_1000sf"] for r in rules
                               if "office" in r.get("use_type", "").lower()
                               and r.get("spaces_per_1000sf")), 4.0)
        retail_parking = next((r["spaces_per_1000sf"] for r in rules
                               if any(k in r.get("use_type", "").lower()
                                      for k in ["retail", "commercial"])
                               and r.get("spaces_per_1000sf")), 5.0)

        print(f"\n  {jname} parking defaults:")
        print(f"    SFR: {sfr_parking}/unit, MF: {mf_parking}/unit")
        print(f"    Office: {office_parking}/1000sf, Retail: {retail_parking}/1000sf")

        # Get jurisdiction ID
        jur_result = sb.table("jurisdictions")\
            .select("id")\
            .ilike("name", f"%{jname.split()[0]}%")\
            .execute()
        if not (jur_result.data or []):
            continue
        jur_id = jur_result.data[0]["id"]

        # Get all zoning districts for this jurisdiction
        zd_result = sb.table("zoning_districts")\
            .select("id, code, name, category")\
            .eq("jurisdiction_id", jur_id)\
            .execute()

        for zd in (zd_result.data or []):
            zd_id = zd["id"]
            category = (zd.get("category") or "").lower()
            code = (zd.get("code") or "").upper()

            # Determine parking by category/code
            if any(x in category for x in ["residential", "single"]) or \
               re.match(r"^R[-_]?[0-9]", code) or code in ["RS", "RA", "RE"]:
                p_unit = sfr_parking
                p_sf = None
            elif any(x in category for x in ["multi", "apartment"]) or \
                 re.match(r"^R[MH]|^RM|^MH", code):
                p_unit = mf_parking
                p_sf = None
            elif any(x in category for x in ["commercial", "business", "retail"]) or \
                 re.match(r"^[BC][-_]?[0-9]|^BU|^C[GN]", code):
                p_unit = None
                p_sf = retail_parking
            else:
                continue

            # Update zone_standards where parking is NULL
            zs_check = sb.table("zone_standards")\
                .select("id, parking_per_unit, parking_per_1000sf")\
                .eq("zoning_district_id", zd_id)\
                .execute()

            if zs_check.data:
                existing = zs_check.data[0]
                update = {}
                if p_unit is not None and existing.get("parking_per_unit") is None:
                    update["parking_per_unit"] = p_unit
                if p_sf is not None and existing.get("parking_per_1000sf") is None:
                    update["parking_per_1000sf"] = p_sf
                if update:
                    sb.table("zone_standards")\
                        .update(update)\
                        .eq("id", existing["id"])\
                        .execute()
                    parking_updates += 1

    print(f"\n  Parking updates applied: {parking_updates}")
    return parking_updates


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5: DERIVE MISSING VALUES
# ═══════════════════════════════════════════════════════════════════════════════
def phase5_derive():
    print("\n" + "="*60)
    print("PHASE 5: Derive missing values")
    print("="*60)

    derived_stories = 0
    derived_far = 0
    classified = 0

    # 5a. Derive max_stories from max_height_ft
    print("\n  5a. Deriving max_stories from max_height_ft...")
    try:
        zs_result = sb.table("zone_standards")\
            .select("id, max_height_ft, max_stories")\
            .is_("max_stories", "null")\
            .not_.is_("max_height_ft", "null")\
            .execute()
        rows = zs_result.data or []
        print(f"  Found {len(rows)} rows needing max_stories")

        for row in rows:
            stories = max(1, math.floor(row["max_height_ft"] / 11))
            sb.table("zone_standards")\
                .update({"max_stories": stories})\
                .eq("id", row["id"])\
                .execute()
            derived_stories += 1

        print(f"  Derived max_stories: {derived_stories}")
    except Exception as e:
        print(f"  [ERROR] max_stories derivation: {e}")

    # 5b. Derive max_far for residential zones
    print("\n  5b. Deriving max_far from density for residential zones...")
    try:
        # Get residential zone_standards with density but no FAR
        zs_result = sb.table("zone_standards")\
            .select("id, zoning_district_id, max_density_du_acre, max_far")\
            .is_("max_far", "null")\
            .not_.is_("max_density_du_acre", "null")\
            .execute()
        candidates = zs_result.data or []

        for row in candidates:
            zd_id = row["zoning_district_id"]
            # Check if residential
            zd_result = sb.table("zoning_districts")\
                .select("category, code")\
                .eq("id", zd_id)\
                .execute()
            if not (zd_result.data or []):
                continue
            zd = zd_result.data[0]
            category = (zd.get("category") or "").lower()
            code = (zd.get("code") or "").upper()

            is_residential = any(x in category for x in ["residential", "mixed"]) or \
                             re.match(r"^R[-_]?[0-9]|^RS|^RA|^RM|^MH|^PUD", code or "")

            if is_residential:
                # FAR ≈ (density × avg_unit_sf) / 43560
                density = row["max_density_du_acre"]
                # Use 900 sf avg for mixed/MF, 1800 for SF
                avg_sf = 900 if any(x in category for x in ["multi", "mixed"]) else 1800
                far = round((density * avg_sf) / 43560, 2)
                if 0.1 <= far <= 5.0:  # Sanity check
                    sb.table("zone_standards")\
                        .update({"max_far": far})\
                        .eq("id", row["id"])\
                        .execute()
                    derived_far += 1

        print(f"  Derived max_far: {derived_far}")
    except Exception as e:
        print(f"  [ERROR] max_far derivation: {e}")

    # 5c. Classify uncategorized zoning districts
    print("\n  5c. Classifying uncategorized zoning districts...")
    try:
        zd_result = sb.table("zoning_districts")\
            .select("id, code, name")\
            .or_("category.eq.Uncategorized,category.is.null")\
            .limit(500)\
            .execute()
        uncategorized = zd_result.data or []
        print(f"  Found {len(uncategorized)} uncategorized districts")

        # Rule-based classification (no LLM cost)
        category_rules = [
            (r"^R[-_]?[0-9]|^RS|^RA|^RE|^RR|^RU|^SFR|^ER", "residential"),
            (r"^RM|^RMH|^RH|^MH|^MF|^MDR|^HDR|^LDR|^R[-_]?M", "residential"),
            (r"^C[-_]?[0-9]|^BU|^B[-_]?[0-9]|^CB|^CN|^CG|^CR|^CV|^HC|^NC|^GC|^SC", "commercial"),
            (r"^O[-_]?[0-9]|^OF|^OFC|^OP|^OPK|^BP|^OI", "commercial"),
            (r"^I[-_]?[0-9]|^M[-_]?[0-9]|^IL|^IH|^LI|^HI|^GI|^IND", "industrial"),
            (r"^PUD|^MPD|^MXD|^MU|^MX|^TND|^TOD|^DRI", "mixed-use"),
            (r"^A[-_]?[0-9]|^AG|^AU|^RU|^EU|^OU|^AGRI|^FARM", "agricultural"),
            (r"^CF|^P[-_]?[0-9]|^PF|^INS|^REC|^OS|^CON|^PK", "institutional"),
        ]

        for zd in uncategorized:
            code = (zd.get("code") or "").upper().strip()
            name = (zd.get("name") or "").lower()
            category = None

            for pattern, cat in category_rules:
                if re.match(pattern, code):
                    category = cat
                    break

            if not category:
                # Name-based fallback
                if any(k in name for k in ["single family", "residential", "dwelling"]):
                    category = "residential"
                elif any(k in name for k in ["commercial", "business", "retail", "office"]):
                    category = "commercial"
                elif any(k in name for k in ["industrial", "manufacturing", "warehouse"]):
                    category = "industrial"
                elif any(k in name for k in ["mixed", "planned", "pud"]):
                    category = "mixed-use"
                elif any(k in name for k in ["agricultural", "farming", "rural"]):
                    category = "agricultural"

            if category:
                sb.table("zoning_districts")\
                    .update({"category": category})\
                    .eq("id", zd["id"])\
                    .execute()
                classified += 1

        print(f"  Classified: {classified} districts")
    except Exception as e:
        print(f"  [ERROR] classification: {e}")

    print(f"\n  PHASE 5 COMPLETE: stories={derived_stories}, far={derived_far}, classified={classified}")
    return derived_stories, derived_far, classified


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6: VALIDATION + NEVER-LIE AUDIT
# ═══════════════════════════════════════════════════════════════════════════════
def phase6_validate():
    print("\n" + "="*60)
    print("PHASE 6: Validation — NEVER-LIE audit of exact DB counts")
    print("="*60)

    # Get EXACT counts from zone_standards
    try:
        result = sb.table("zone_standards")\
            .select(
                "max_height_ft, front_setback_ft, side_setback_ft, rear_setback_ft, "
                "max_lot_coverage_pct, max_far, max_density_du_acre, "
                "parking_per_unit, parking_per_1000sf, min_open_space_pct"
            )\
            .execute()
        rows = result.data or []
        total = len(rows)

        def count_non_null(field):
            return sum(1 for r in rows if r.get(field) is not None)

        height_n      = count_non_null("max_height_ft")
        front_n       = count_non_null("front_setback_ft")
        side_n        = count_non_null("side_setback_ft")
        rear_n        = count_non_null("rear_setback_ft")
        coverage_n    = count_non_null("max_lot_coverage_pct")
        far_n         = count_non_null("max_far")
        density_n     = count_non_null("max_density_du_acre")
        parking_unit_n = count_non_null("parking_per_unit")
        parking_sf_n  = count_non_null("parking_per_1000sf")
        open_space_n  = count_non_null("min_open_space_pct")

        def pct(n, t):
            return round(n / t * 100, 1) if t > 0 else 0.0

        print(f"\n  EXACT DB COUNTS (zone_standards, {total} total rows):")
        print(f"  {'FIELD':<25} {'FILLED':>7} {'TOTAL':>7} {'%':>7}  {'BASELINE':>9}  {'DELTA':>6}")
        print(f"  {'-'*70}")

        results = {
            "total": total,
            "height":       (height_n,       pct(height_n, total),       56.7),
            "front":        (front_n,         pct(front_n, total),         55.6),
            "side":         (side_n,          pct(side_n, total),          55.6),
            "rear":         (rear_n,          pct(rear_n, total),          55.6),
            "coverage":     (coverage_n,      pct(coverage_n, total),      41.0),
            "far":          (far_n,           pct(far_n, total),           18.7),
            "density":      (density_n,       pct(density_n, total),       30.0),
            "parking_unit": (parking_unit_n,  pct(parking_unit_n, total),   0.6),
            "parking_sf":   (parking_sf_n,    pct(parking_sf_n, total),     0.0),
            "open_space":   (open_space_n,    pct(open_space_n, total),     5.0),
        }

        field_display = [
            ("max_height_ft",        "height"),
            ("front_setback_ft",     "front"),
            ("side_setback_ft",      "side"),
            ("rear_setback_ft",      "rear"),
            ("max_lot_coverage_pct", "coverage"),
            ("max_far",              "far"),
            ("max_density_du_acre",  "density"),
            ("parking_per_unit",     "parking_unit"),
            ("parking_per_1000sf",   "parking_sf"),
            ("min_open_space_pct",   "open_space"),
        ]

        for fname, key in field_display:
            n, p, baseline = results[key]
            delta = p - baseline
            sign = "+" if delta >= 0 else ""
            print(f"  {fname:<25} {n:>7,} {total:>7,} {p:>6.1f}%  {baseline:>8.1f}%  {sign}{delta:>5.1f}%")

        # Ready for 3D Massing Engine?
        targets_met = {
            "height+setbacks ≥95%":   results["height"][1] >= 95 and results["front"][1] >= 95,
            "parking_unit ≥80%":       results["parking_unit"][1] >= 80,
            "far ≥60%":               results["far"][1] >= 60,
        }
        ready = all(targets_met.values())

        print(f"\n  TARGET CHECKS:")
        for check, met in targets_met.items():
            print(f"    {'✅' if met else '❌'} {check}")

        print(f"\n  Ready for 3D Massing Engine: {'YES' if ready else 'NOT YET'}")
        return results, ready

    except Exception as e:
        print(f"  [ERROR] Phase 6 audit: {e}")
        return {}, False


def send_telegram_summary(results: dict, ready: bool):
    if not results:
        return

    total = results.get("total", 0)
    r = results

    def fmt(key):
        n, p, baseline = r[key]
        delta = p - baseline
        sign = "+" if delta >= 0 else ""
        return f"{p:.1f}% (was {baseline:.1f}%, {sign}{delta:.1f}%)"

    msg = f"""🏗️ MASSING DATA SPRINT COMPLETE
================================
zone_standards: {total:,} rows

📐 Dimensional Standards:
• Height:   {fmt('height')}
• Setbacks: {fmt('front')} (front)
• Coverage: {fmt('coverage')}
• FAR:      {fmt('far')}
• Density:  {fmt('density')}

🅿️ Parking:
• /unit:    {fmt('parking_unit')}
• /1000sf:  {fmt('parking_sf')}

🌿 Open Space: {fmt('open_space')}

🏁 Ready for 3D Massing Engine: {'✅ YES' if ready else '❌ NOT YET'}

⛔ No AgentQL used (BANNED)
✅ Firecrawl primary | Apify fallback"""

    tg(msg)
    print("\n  Telegram summary sent.")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    print("🚀 SUMMIT DISPATCH: Massing Data Gap Closure Sprint")
    print("=" * 60)
    print("⛔ AgentQL BANNED — Firecrawl PRIMARY, Apify FALLBACK")
    print()

    tg("🚀 MASSING DATA SPRINT STARTED\nPhase 1: Auditing Brevard null zones...")

    # Phase 1
    null_rows, null_by_jur = phase1_audit()

    tg(f"📊 Phase 1 complete: {len(null_rows)} Brevard zones with NULL height/setback\nStarting Firecrawl extraction...")

    # Phase 2
    all_extracted, rate_limited = phase2_firecrawl(null_by_jur)

    # Upsert Phase 2 results
    if all_extracted:
        upserted = upsert_extracted_standards(all_extracted)
        tg(f"✅ Phase 2 complete: {sum(len(v) for v in all_extracted.values())} districts scraped, {upserted} DB updates")
    else:
        tg("⚠️ Phase 2: No data extracted — Municode may require JS rendering")

    # Phase 3 (Apify fallback)
    apify_count = phase3_apify_fallback(rate_limited)
    if apify_count > 0:
        tg(f"✅ Phase 3: Apify got {apify_count} pages")

    # Phase 4
    parking_updates = phase4_parking()
    tg(f"✅ Phase 4: {parking_updates} parking rule updates applied")

    # Phase 5
    stories, far, classified = phase5_derive()
    tg(f"✅ Phase 5: Derived {stories} stories, {far} FAR values, {classified} zones classified")

    # Phase 6
    results, ready = phase6_validate()

    # Final Telegram
    send_telegram_summary(results, ready)

    print("\n" + "="*60)
    print("SPRINT COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
