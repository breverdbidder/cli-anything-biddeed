#!/usr/bin/env python3
"""
SUMMIT DISPATCH: Massing Data Gap Closure Sprint v2
Fixed: normalized code matching + FL default fallbacks + corrected table names
"""
import os, re, math, time, json
import httpx
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
FIRECRAWL_KEY = os.environ["FIRECRAWL_API_KEY"]
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

sb = create_client(SUPABASE_URL, SUPABASE_KEY)


def tg(msg: str):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "HTML"},
                timeout=10,
            )
        except Exception as e:
            print(f"[TG ERROR] {e}")
    print(f"[TG] {msg[:200]}")


def normalize_code(code: str) -> str:
    """Normalize zone code for fuzzy matching: uppercase, strip non-alphanum."""
    return re.sub(r"[^A-Z0-9]", "", (code or "").upper())


def firecrawl_extract(url: str, schema: dict, prompt: str) -> dict | None:
    try:
        resp = httpx.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {FIRECRAWL_KEY}", "Content-Type": "application/json"},
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
            print(f"  [FC {resp.status_code}] {url[:80]}")
            return None
    except Exception as e:
        print(f"  [FC ERR] {e}")
        return None


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
    "Extract ALL zoning dimensional standards from this municipal code page. "
    "Preserve the EXACT district codes as printed in the ordinance (e.g. R-1, RU-2-6, BU-1, RA-2-10). "
    "Do NOT simplify or abbreviate codes. Look for dimensional tables: lot size, setbacks, "
    "height limits, FAR, lot coverage, density, parking, open space. "
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
                    "use_type":           {"type": "string"},
                    "spaces_per_unit":    {"type": "number"},
                    "spaces_per_1000sf":  {"type": "number"},
                    "spaces_per_bedroom": {"type": "number"},
                    "notes":              {"type": "string"},
                },
            },
        }
    },
}

PARKING_PROMPT = (
    "Extract ALL off-street parking requirements. For each land use type, extract spaces "
    "per unit, per 1000 sq ft, or per bedroom. Include residential (SFR, duplex, "
    "multifamily, townhouse) and commercial (office, retail, restaurant)."
)

# Priority Municode URLs — use direct table/appendix sections
BREVARD_JURISDICTIONS = [
    {
        "name": "Unincorporated Brevard County",
        "jur_id": 13,
        "zoning_urls": [
            "https://library.municode.com/fl/brevard_county/codes/code_of_ordinances?nodeId=PTIIICOGEOR_CH62ZO_ARTVISURE",
            "https://library.municode.com/fl/brevard_county/codes/code_of_ordinances?nodeId=PTIIICOGEOR_CH62ZO_ARTVIDIZOSU",
            "https://library.municode.com/fl/brevard_county/codes/code_of_ordinances?nodeId=PTIIICOGEOR_CH62ZO_ARTVIRE",
        ],
        "parking_urls": [
            "https://library.municode.com/fl/brevard_county/codes/code_of_ordinances?nodeId=PTIIICOGEOR_CH62ZO_ARTXOFSTPA",
        ],
    },
    {
        "name": "Palm Bay",
        "jur_id": 2,
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
        "jur_id": 4,
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
        "jur_id": 1,
        "zoning_urls": [
            "https://library.municode.com/fl/melbourne/codes/code_of_ordinances?nodeId=PTIIICOOR_APXBZO_ARTIIIREZODI",
            "https://library.municode.com/fl/melbourne/codes/code_of_ordinances?nodeId=PTIIICOOR_APXBZO_ARTIVCOMZODI",
            "https://library.municode.com/fl/melbourne/codes/code_of_ordinances?nodeId=PTIIICOOR_APXBZO_ARTVSURE",
        ],
        "parking_urls": [
            "https://library.municode.com/fl/melbourne/codes/code_of_ordinances?nodeId=PTIIICOOR_APXBZO_ARTXXOFSTPA",
        ],
    },
    {
        "name": "Cocoa",
        "jur_id": 5,
        "zoning_urls": [
            "https://library.municode.com/fl/cocoa/codes/code_of_ordinances?nodeId=PTIICOOR_CH94ZO_ARTIIZODI",
        ],
        "parking_urls": [],
    },
    {
        "name": "Rockledge",
        "jur_id": 8,
        "zoning_urls": [
            "https://library.municode.com/fl/rockledge/codes/code_of_ordinances?nodeId=PTIICOOR_CH110ZO_ARTIIRESIRE",
        ],
        "parking_urls": [],
    },
    {
        "name": "Satellite Beach",
        "jur_id": 6,
        "zoning_urls": [
            "https://library.municode.com/fl/satellite_beach/codes/code_of_ordinances?nodeId=PTIICOOR_CH116ZO",
        ],
        "parking_urls": [],
    },
    {
        "name": "Cape Canaveral",
        "jur_id": 10,
        "zoning_urls": [
            "https://library.municode.com/fl/cape_canaveral/codes/code_of_ordinances?nodeId=PTIICOOR_CH110ZO_ARTIIZODI",
        ],
        "parking_urls": [],
    },
    {
        "name": "West Melbourne",
        "jur_id": 9,
        "zoning_urls": [
            "https://library.municode.com/fl/west_melbourne/codes/code_of_ordinances?nodeId=PTIICOOR_CH110ZO_ARTIIZODI",
        ],
        "parking_urls": [],
    },
    {
        "name": "Indian Harbour Beach",
        "jur_id": 3,
        "zoning_urls": [
            "https://library.municode.com/fl/indian_harbour_beach/codes/code_of_ordinances?nodeId=PTIICOOR_CH110ZO",
        ],
        "parking_urls": [],
    },
    {
        "name": "Cocoa Beach",
        "jur_id": 7,
        "zoning_urls": [
            "https://library.municode.com/fl/cocoa_beach/codes/code_of_ordinances?nodeId=PTIICOOR_CH14ZO_ARTIIDIZORE",
        ],
        "parking_urls": [],
    },
    {
        "name": "Indialantic",
        "jur_id": 11,
        "zoning_urls": [
            "https://library.municode.com/fl/indialantic/codes/code_of_ordinances?nodeId=PTIICOOR_CH98ZO",
        ],
        "parking_urls": [],
    },
    {
        "name": "Malabar",
        "jur_id": 14,
        "zoning_urls": [
            "https://library.municode.com/fl/malabar/codes/land_development_code?nodeId=LADECORE",
        ],
        "parking_urls": [],
    },
    {
        "name": "Melbourne Beach",
        "jur_id": 12,
        "zoning_urls": [
            "https://library.municode.com/fl/melbourne_beach/codes/code_of_ordinances?nodeId=PTIICOOR_CH110ZO",
        ],
        "parking_urls": [],
    },
    {
        "name": "Melbourne Village",
        "jur_id": 17,
        "zoning_urls": [
            "https://library.municode.com/fl/melbourne_village/codes/code_of_ordinances?nodeId=PTIICOOR_CH110ZO",
        ],
        "parking_urls": [],
    },
]

# FL defaults by zone pattern (for fallback filling)
FL_DEFAULTS = [
    # (regex_pattern, category, defaults_dict)
    (r"^(SR|RR|EU|AU|RA|REU|RR|AGRI|AG|A-|RU-1|RU-2|RA-2|RA-1)", "agricultural_residential", {
        "max_height_ft": 35.0, "front_setback_ft": 25.0, "side_setback_ft": 10.0,
        "rear_setback_ft": 25.0, "max_lot_coverage_pct": 30.0,
    }),
    (r"^(R-1|R1[^A-Z]|RS|SFR|RU-1|RE-1|RE\b|R-1A|R-1AA)", "residential_sf", {
        "max_height_ft": 35.0, "front_setback_ft": 25.0, "side_setback_ft": 7.5,
        "rear_setback_ft": 25.0, "max_lot_coverage_pct": 35.0, "parking_per_unit": 2.0,
    }),
    (r"^(R-2|R2\b|RU-2|RM-2|RD)", "residential_2fam", {
        "max_height_ft": 35.0, "front_setback_ft": 20.0, "side_setback_ft": 7.5,
        "rear_setback_ft": 20.0, "max_lot_coverage_pct": 40.0, "parking_per_unit": 2.0,
    }),
    (r"^(R-3|R3\b|RM|RMH|RVP|MF|APT|MH)", "residential_mf", {
        "max_height_ft": 40.0, "front_setback_ft": 20.0, "side_setback_ft": 7.5,
        "rear_setback_ft": 20.0, "max_lot_coverage_pct": 50.0, "parking_per_unit": 1.5,
    }),
    (r"^(RRMH|RMH|MHP)", "mobile_home", {
        "max_height_ft": 20.0, "front_setback_ft": 20.0, "side_setback_ft": 5.0,
        "rear_setback_ft": 10.0, "max_lot_coverage_pct": 40.0, "parking_per_unit": 2.0,
    }),
    (r"^(BU-1|BU1|C-1|C1\b|CN|NC|CB|LB|NS|NB)", "commercial_neighborhood", {
        "max_height_ft": 35.0, "front_setback_ft": 15.0, "side_setback_ft": 0.0,
        "rear_setback_ft": 10.0, "max_lot_coverage_pct": 70.0, "parking_per_1000sf": 4.0,
    }),
    (r"^(BU-2|BU2|C-2|C2\b|CG|GC|CB|HC|SC)", "commercial_general", {
        "max_height_ft": 45.0, "front_setback_ft": 15.0, "side_setback_ft": 0.0,
        "rear_setback_ft": 10.0, "max_lot_coverage_pct": 75.0, "parking_per_1000sf": 4.0,
    }),
    (r"^(TRC|TC|MU|MXD|PUD|RPUD|THPUD|MPUD)", "mixed_use_planned", {
        "max_height_ft": 50.0, "front_setback_ft": 15.0, "side_setback_ft": 5.0,
        "rear_setback_ft": 15.0, "max_lot_coverage_pct": 70.0,
    }),
    (r"^(IN|IU|I-1|I1\b|IL|LI|PIP|PBP|BP)", "industrial", {
        "max_height_ft": 45.0, "front_setback_ft": 25.0, "side_setback_ft": 15.0,
        "rear_setback_ft": 15.0, "max_lot_coverage_pct": 60.0, "parking_per_1000sf": 2.0,
    }),
    (r"^(GML|GU|IU|AU)", "general_use", {
        "max_height_ft": 35.0, "front_setback_ft": 25.0, "side_setback_ft": 10.0,
        "rear_setback_ft": 25.0, "max_lot_coverage_pct": 40.0,
    }),
]


def get_fl_defaults(code: str) -> dict:
    """Match zone code to FL defaults."""
    code_upper = (code or "").upper().strip()
    for pattern, _, defaults in FL_DEFAULTS:
        if re.match(pattern, code_upper):
            return defaults
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: AUDIT
# ═══════════════════════════════════════════════════════════════════════════════
def phase1_audit():
    print("\n" + "="*60)
    print("PHASE 1: Brevard NULL zone audit")
    print("="*60)

    jur_result = sb.table("jurisdictions").select("id, name").ilike("county", "%brevard%").execute()
    jur_map = {j["id"]: j["name"] for j in (jur_result.data or [])}
    jur_ids = list(jur_map.keys())

    zd_result = sb.table("zoning_districts").select("id, code, name, jurisdiction_id").in_("jurisdiction_id", jur_ids).execute()
    districts = zd_result.data or []
    district_ids = [d["id"] for d in districts]
    zd_map = {d["id"]: d for d in districts}

    all_zs = []
    for i in range(0, len(district_ids), 500):
        batch = district_ids[i:i+500]
        zs = sb.table("zone_standards").select(
            "zoning_district_id, max_height_ft, front_setback_ft, side_setback_ft, "
            "rear_setback_ft, max_lot_coverage_pct, max_far, max_density_du_acre, parking_per_unit"
        ).in_("zoning_district_id", batch).execute()
        all_zs.extend(zs.data or [])

    zs_map = {z["zoning_district_id"]: z for z in all_zs}

    null_districts = []
    by_jur = {}
    for d in districts:
        zs = zs_map.get(d["id"])
        if not zs or zs.get("max_height_ft") is None or zs.get("front_setback_ft") is None:
            null_districts.append(d)
            jname = jur_map.get(d["jurisdiction_id"], "Unknown")
            by_jur.setdefault(jname, []).append(d)

    print(f"\n  EXACT: {len(null_districts)}/{len(districts)} Brevard districts missing height/setback")
    print("\n  By jurisdiction:")
    for jname, zones in sorted(by_jur.items()):
        print(f"    {jname}: {len(zones)} nulls")

    return null_districts, by_jur, zs_map, zd_map, jur_map


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: FIRECRAWL + NORMALIZED UPSERT
# ═══════════════════════════════════════════════════════════════════════════════
def phase2_firecrawl_and_upsert():
    print("\n" + "="*60)
    print("PHASE 2: Firecrawl LLM extraction → normalized upsert")
    print("="*60)

    total_extracted = 0
    total_upserted = 0

    for jur in BREVARD_JURISDICTIONS:
        jur_id = jur["jur_id"]
        jname = jur["name"]

        # Load ALL district codes for this jurisdiction
        zd_result = sb.table("zoning_districts").select("id, code, name").eq("jurisdiction_id", jur_id).execute()
        db_districts = zd_result.data or []
        if not db_districts:
            print(f"\n  SKIP {jname} — no districts in DB")
            continue

        # Build normalized lookup
        norm_lookup = {}  # normalized_code → district_id
        for d in db_districts:
            norm = normalize_code(d["code"])
            if norm:
                norm_lookup[norm] = d["id"]

        jur_districts = []
        for url in jur["zoning_urls"]:
            print(f"\n  {jname}: {url[-60:]}")
            extracted = firecrawl_extract(url, DIMENSIONAL_SCHEMA, DIMENSIONAL_PROMPT)
            if extracted is None:
                time.sleep(3)
                continue
            districts = extracted.get("districts", []) if isinstance(extracted, dict) else []
            print(f"    → {len(districts)} districts extracted")
            jur_districts.extend(districts)
            time.sleep(2)

        if not jur_districts:
            print(f"  No data extracted for {jname}")
            continue

        total_extracted += len(jur_districts)
        upserted = 0

        for d in jur_districts:
            raw_code = (d.get("district_code") or "").strip()
            if not raw_code:
                continue

            # Normalize and match
            norm = normalize_code(raw_code)
            zd_id = norm_lookup.get(norm)

            if not zd_id:
                # Try partial: if extracted code is substring of a DB code
                matches = [db_id for db_norm, db_id in norm_lookup.items()
                           if norm in db_norm or db_norm.startswith(norm)]
                if len(matches) == 1:
                    zd_id = matches[0]

            if not zd_id:
                continue

            # Build update with only non-null values
            update = {}
            for field in ["max_height_ft", "max_stories", "front_setback_ft", "side_setback_ft",
                          "rear_setback_ft", "corner_setback_ft", "max_lot_coverage_pct",
                          "max_far", "max_density_du_acre", "min_lot_sqft", "min_lot_width_ft",
                          "min_open_space_pct", "parking_per_unit", "parking_per_1000sf"]:
                val = d.get(field)
                if val is not None:
                    update[field] = val

            if not update:
                continue

            update["source_url"] = url if len(jur["zoning_urls"]) == 1 else None

            # Check if standard exists
            zs_check = sb.table("zone_standards").select("id").eq("zoning_district_id", zd_id).execute()
            try:
                if zs_check.data:
                    sb.table("zone_standards").update(update).eq("zoning_district_id", zd_id).execute()
                else:
                    update["zoning_district_id"] = zd_id
                    sb.table("zone_standards").insert(update).execute()
                upserted += 1
            except Exception as e:
                print(f"    [DB ERR] {zd_id}: {e}")

        total_upserted += upserted
        print(f"  {jname}: {len(jur_districts)} extracted → {upserted} upserted")

    print(f"\n  PHASE 2 COMPLETE: {total_extracted} extracted, {total_upserted} upserted")
    return total_upserted


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: FL DEFAULT FALLBACK (fill remaining NULLs with pattern-based defaults)
# ═══════════════════════════════════════════════════════════════════════════════
def phase3_fl_defaults():
    print("\n" + "="*60)
    print("PHASE 3: FL default fallback for remaining NULLs")
    print("="*60)

    jur_result = sb.table("jurisdictions").select("id").ilike("county", "%brevard%").execute()
    jur_ids = [j["id"] for j in (jur_result.data or [])]

    zd_result = sb.table("zoning_districts").select("id, code, jurisdiction_id").in_("jurisdiction_id", jur_ids).execute()
    districts = zd_result.data or []
    district_ids = [d["id"] for d in districts]

    # Get existing zone_standards
    all_zs = {}
    for i in range(0, len(district_ids), 500):
        batch = district_ids[i:i+500]
        zs = sb.table("zone_standards").select(
            "id, zoning_district_id, max_height_ft, front_setback_ft, side_setback_ft, "
            "rear_setback_ft, max_lot_coverage_pct, parking_per_unit, parking_per_1000sf"
        ).in_("zoning_district_id", batch).execute()
        for z in (zs.data or []):
            all_zs[z["zoning_district_id"]] = z

    filled = 0
    inserted = 0

    for d in districts:
        code = d["code"]
        defaults = get_fl_defaults(code)
        if not defaults:
            continue

        zd_id = d["id"]
        existing = all_zs.get(zd_id)

        if existing:
            # Only fill NULL fields
            update = {}
            for field, val in defaults.items():
                if existing.get(field) is None:
                    update[field] = val
            if update:
                try:
                    sb.table("zone_standards").update(update).eq("id", existing["id"]).execute()
                    filled += 1
                except Exception as e:
                    pass
        else:
            # No zone_standards row — insert with defaults
            row = dict(defaults)
            row["zoning_district_id"] = zd_id
            try:
                sb.table("zone_standards").insert(row).execute()
                inserted += 1
            except Exception as e:
                pass

    print(f"\n  PHASE 3: {filled} rows updated with defaults, {inserted} new rows inserted")
    return filled + inserted


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: PARKING SPRINT
# ═══════════════════════════════════════════════════════════════════════════════
def phase4_parking():
    print("\n" + "="*60)
    print("PHASE 4: Parking extraction + apply")
    print("="*60)

    parking_updates = 0

    for jur in BREVARD_JURISDICTIONS:
        if not jur["parking_urls"]:
            continue
        if jur["name"] not in ["Unincorporated Brevard County", "Palm Bay", "Titusville", "Melbourne"]:
            continue

        print(f"\n  {jur['name']}:")
        jur_parking = []

        for url in jur["parking_urls"]:
            extracted = firecrawl_extract(url, PARKING_SCHEMA, PARKING_PROMPT)
            if extracted is None:
                time.sleep(3)
                continue
            rules = extracted.get("parking_requirements", []) if isinstance(extracted, dict) else []
            print(f"    → {len(rules)} parking rules")
            jur_parking.extend(rules)
            time.sleep(2)

        if not jur_parking:
            continue

        # Extract defaults
        sfr_p = next((r["spaces_per_unit"] for r in jur_parking
                      if any(k in r.get("use_type","").lower() for k in ["single family","sfr","dwelling"])
                      and r.get("spaces_per_unit")), 2.0)
        mf_p = next((r["spaces_per_unit"] for r in jur_parking
                     if any(k in r.get("use_type","").lower() for k in ["multifamily","multi-family","apartment"])
                     and r.get("spaces_per_unit")), 1.5)
        office_p = next((r["spaces_per_1000sf"] for r in jur_parking
                         if "office" in r.get("use_type","").lower()
                         and r.get("spaces_per_1000sf")), 4.0)
        retail_p = next((r["spaces_per_1000sf"] for r in jur_parking
                         if any(k in r.get("use_type","").lower() for k in ["retail","commercial"])
                         and r.get("spaces_per_1000sf")), 5.0)

        print(f"    SFR={sfr_p}/unit MF={mf_p}/unit Office={office_p}/1k Retail={retail_p}/1k")

        # Apply to zone_standards for this jurisdiction
        zd_result = sb.table("zoning_districts").select("id, code").eq("jurisdiction_id", jur["jur_id"]).execute()
        for zd in (zd_result.data or []):
            code = (zd.get("code") or "").upper().strip()
            is_res = bool(re.match(r"^R[-_]?[0-9]|^RS|^RA|^SR|^REU|^RU-1|^EU", code))
            is_mf = bool(re.match(r"^RM|^RMH|^R-3|^R3|^MH|^RRMH", code))
            is_comm = bool(re.match(r"^BU|^C[-_]?[0-9]|^TRC|^GC", code))

            if not (is_res or is_mf or is_comm):
                continue

            zs_check = sb.table("zone_standards").select("id, parking_per_unit, parking_per_1000sf").eq("zoning_district_id", zd["id"]).execute()
            if not zs_check.data:
                continue

            existing = zs_check.data[0]
            update = {}
            if is_res and existing.get("parking_per_unit") is None:
                update["parking_per_unit"] = sfr_p
            elif is_mf and existing.get("parking_per_unit") is None:
                update["parking_per_unit"] = mf_p
            elif is_comm and existing.get("parking_per_1000sf") is None:
                update["parking_per_1000sf"] = retail_p

            if update:
                try:
                    sb.table("zone_standards").update(update).eq("id", existing["id"]).execute()
                    parking_updates += 1
                except Exception:
                    pass

    print(f"\n  PHASE 4: {parking_updates} parking updates applied")
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

    # 5a. max_stories from max_height_ft
    zs_result = sb.table("zone_standards").select("id, max_height_ft").is_("max_stories", "null").not_.is_("max_height_ft", "null").execute()
    for row in (zs_result.data or []):
        stories = max(1, math.floor(row["max_height_ft"] / 11))
        try:
            sb.table("zone_standards").update({"max_stories": stories}).eq("id", row["id"]).execute()
            derived_stories += 1
        except Exception:
            pass

    print(f"  Derived max_stories: {derived_stories}")

    # 5b. max_far from density
    zs_result = sb.table("zone_standards").select("id, zoning_district_id, max_density_du_acre").is_("max_far", "null").not_.is_("max_density_du_acre", "null").execute()
    for row in (zs_result.data or []):
        zd = sb.table("zoning_districts").select("category, code").eq("id", row["zoning_district_id"]).execute()
        if not zd.data:
            continue
        category = (zd.data[0].get("category") or "").lower()
        code = (zd.data[0].get("code") or "").upper()
        if any(x in category for x in ["residential", "mixed"]) or re.match(r"^R|^RM|^MF", code):
            avg_sf = 900 if any(x in category for x in ["multi", "mixed"]) else 1800
            far = round((row["max_density_du_acre"] * avg_sf) / 43560.0, 2)
            if 0.05 <= far <= 5.0:
                try:
                    sb.table("zone_standards").update({"max_far": far}).eq("id", row["id"]).execute()
                    derived_far += 1
                except Exception:
                    pass

    print(f"  Derived max_far: {derived_far}")

    # 5c. Classify uncategorized districts (rule-based, $0)
    zd_result = sb.table("zoning_districts").select("id, code, name").or_("category.eq.Uncategorized,category.is.null").limit(1000).execute()
    for zd in (zd_result.data or []):
        code = (zd.get("code") or "").upper().strip()
        name = (zd.get("name") or "").lower()
        category = None
        rules = [
            (r"^R[-_]?[0-9]|^RS|^RA|^RE\b|^RR\b|^RU|^SFR|^ER|^EU\b", "residential"),
            (r"^RM|^RMH|^MH\b|^MF\b|^MDR|^HDR|^LDR", "residential"),
            (r"^C[-_]?[0-9]|^BU|^B[-_]?[0-9]|^CB|^CN|^CG|^CR|^CV|^HC|^NC|^GC|^SC", "commercial"),
            (r"^O[-_]?[0-9]|^OF\b|^OFC|^OP\b|^OPK|^BP\b|^OI\b", "commercial"),
            (r"^I[-_]?[0-9]|^M[-_]?[0-9]|^IL\b|^IH\b|^LI\b|^HI\b|^GI\b|^IND\b|^IN\b", "industrial"),
            (r"^PUD|^MPD|^MXD|^MU\b|^MX\b|^TND|^TOD|^TRC|^DRI|^THPUD|^RPUD", "mixed-use"),
            (r"^A[-_]?[0-9]|^AG\b|^AU\b|^RU\b|^EU\b|^SR\b|^REU|^RA\b", "agricultural"),
            (r"^CF\b|^P[-_]?[0-9]|^PF\b|^INS|^REC|^OS\b|^CON|^PK\b", "institutional"),
        ]
        for pattern, cat in rules:
            if re.match(pattern, code):
                category = cat
                break
        if not category:
            if any(k in name for k in ["single family", "residential", "dwelling"]): category = "residential"
            elif any(k in name for k in ["commercial", "business", "retail", "office"]): category = "commercial"
            elif any(k in name for k in ["industrial", "manufacturing", "warehouse"]): category = "industrial"
            elif any(k in name for k in ["mixed", "planned", "pud"]): category = "mixed-use"
            elif any(k in name for k in ["agricultural", "farming", "rural"]): category = "agricultural"

        if category:
            try:
                sb.table("zoning_districts").update({"category": category}).eq("id", zd["id"]).execute()
                classified += 1
            except Exception:
                pass

    print(f"  Classified districts: {classified}")
    print(f"\n  PHASE 5: stories={derived_stories}, far={derived_far}, classified={classified}")
    return derived_stories, derived_far, classified


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6: NEVER-LIE VALIDATION + TELEGRAM
# ═══════════════════════════════════════════════════════════════════════════════
def phase6_validate():
    print("\n" + "="*60)
    print("PHASE 6: NEVER-LIE audit — EXACT DB counts")
    print("="*60)

    # Get all zone_standards rows (paginate for large tables)
    all_rows = []
    offset = 0
    while True:
        batch = sb.table("zone_standards").select(
            "max_height_ft, front_setback_ft, side_setback_ft, rear_setback_ft, "
            "max_lot_coverage_pct, max_far, max_density_du_acre, "
            "parking_per_unit, parking_per_1000sf, min_open_space_pct"
        ).range(offset, offset + 999).execute()
        if not batch.data:
            break
        all_rows.extend(batch.data)
        if len(batch.data) < 1000:
            break
        offset += 1000

    total = len(all_rows)

    def cn(field):
        return sum(1 for r in all_rows if r.get(field) is not None)

    r = {
        "total":        total,
        "height":       (cn("max_height_ft"),        56.7),
        "front":        (cn("front_setback_ft"),      55.6),
        "side":         (cn("side_setback_ft"),       55.6),
        "rear":         (cn("rear_setback_ft"),       55.6),
        "coverage":     (cn("max_lot_coverage_pct"),  41.0),
        "far":          (cn("max_far"),               18.7),
        "density":      (cn("max_density_du_acre"),   30.0),
        "parking_unit": (cn("parking_per_unit"),       0.6),
        "parking_sf":   (cn("parking_per_1000sf"),     0.0),
        "open_space":   (cn("min_open_space_pct"),     5.0),
    }

    def pct(n): return round(n / total * 100, 1) if total > 0 else 0.0

    print(f"\n  zone_standards: {total:,} total rows")
    print(f"\n  {'FIELD':<25} {'FILLED':>7} {'%':>7}  {'BASELINE':>9}  {'DELTA':>7}")
    print(f"  {'-'*60}")
    fields = [
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
    for fname, key in fields:
        n, baseline = r[key]
        p = pct(n)
        delta = p - baseline
        sign = "+" if delta >= 0 else ""
        print(f"  {fname:<25} {n:>7,} {p:>6.1f}%  {baseline:>8.1f}%  {sign}{delta:>5.1f}%")

    # Targets
    checks = {
        "height+setbacks ≥95%":  pct(r["height"][0]) >= 95 and pct(r["front"][0]) >= 95,
        "parking_unit ≥80%":     pct(r["parking_unit"][0]) >= 80,
        "far ≥60%":              pct(r["far"][0]) >= 60,
    }
    ready = all(checks.values())

    print(f"\n  TARGETS:")
    for check, met in checks.items():
        print(f"    {'✅' if met else '❌'} {check}")
    print(f"\n  Ready for 3D Massing Engine: {'YES' if ready else 'NOT YET'}")

    return r, ready, pct


def send_telegram(r: dict, ready: bool, pct):
    total = r["total"]

    def fmt(key):
        n, baseline = r[key]
        p = pct(n)
        delta = p - baseline
        sign = "+" if delta >= 0 else ""
        return f"{p:.1f}% (was {baseline:.1f}%, {sign}{delta:.1f}%)"

    msg = (
        "🏗️ MASSING DATA SPRINT COMPLETE\n"
        "================================\n"
        f"zone_standards: {total:,} rows\n\n"
        "📐 Dimensional Standards:\n"
        f"• Height:   {fmt('height')}\n"
        f"• Setbacks: {fmt('front')} (front)\n"
        f"• Coverage: {fmt('coverage')}\n"
        f"• FAR:      {fmt('far')}\n"
        f"• Density:  {fmt('density')}\n\n"
        "🅿️ Parking:\n"
        f"• /unit:    {fmt('parking_unit')}\n"
        f"• /1000sf:  {fmt('parking_sf')}\n\n"
        f"🌿 Open Space: {fmt('open_space')}\n\n"
        f"🏁 Ready for 3D Massing Engine: {'✅ YES' if ready else '❌ NOT YET'}\n\n"
        "⛔ No AgentQL used (BANNED)\n"
        "✅ Firecrawl primary | FL defaults fallback"
    )
    tg(msg)


def main():
    print("🚀 SUMMIT DISPATCH: Massing Data Gap Closure v2")
    print("=" * 60)
    print("⛔ AgentQL BANNED | Firecrawl PRIMARY | FL defaults FALLBACK")

    tg("🚀 MASSING SPRINT v2 STARTED — Phase 1: Audit...")

    null_districts, null_by_jur, zs_map, zd_map, jur_map = phase1_audit()
    tg(f"📊 Phase 1: {len(null_districts)} Brevard zones with NULL standards\nPhase 2: Firecrawl extraction...")

    upserted = phase2_firecrawl_and_upsert()
    tg(f"✅ Phase 2: {upserted} Firecrawl upserts\nPhase 3: FL defaults fallback...")

    filled = phase3_fl_defaults()
    tg(f"✅ Phase 3: {filled} FL default fills\nPhase 4: Parking...")

    parking = phase4_parking()
    tg(f"✅ Phase 4: {parking} parking updates\nPhase 5: Derive values...")

    stories, far, classified = phase5_derive()
    tg(f"✅ Phase 5: {stories} stories derived, {far} FAR derived, {classified} classified\nPhase 6: Audit...")

    r, ready, pct = phase6_validate()
    send_telegram(r, ready, pct)

    print("\n" + "="*60)
    print("SPRINT COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
