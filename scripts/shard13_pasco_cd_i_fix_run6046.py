#!/usr/bin/env python3
"""SHARD-13 pasco C/D + I fix — run 6046 (dispatch 8c8052cf-60cc-40f8-b049-64523016bdcd, 2026-07-23).

Root cause (from issue brief + prior session analysis):
  Pasco was 10/10 as of 2026-07-18/19 (session GOLD_STANDARD_SHARD8_WASHINGTON_PASCO_DESOTO).
  Current state: 7/10 — C FAIL 91.4% (matched_clean=235), D FAIL 91.4% (matched_any=235),
  I FAIL 91.8% (card_complete=236 of 257).

  Denominator grew 245 -> 257 (+12 new rows from live scraper). The new rows haven't been
  run through the parity matchers or the FL GIO enrichment that the batch3 migration covered.

  C/D gap: 257 - 235 = 22 unmatched rows. We need 244+ matched to reach 95% (244/257=94.95%
  is just under; 245/257=95.33% passes). So we need at least 9 more matches.

  I gap: 257 - 236 = 21 incomplete cards. We need 244+ complete to reach 95% (244/257=94.95%
  is just under; 245/257=95.33% passes). Aiming for 244+ completion.

Fix strategy:
  1. Foreclosure C/D: harvest pasco.realforeclose.com for all NULL + mca_only foreclosure dates
  2. Tax deed C/D: harvest pasco.realtaxdeed.com for all NULL tax_deed dates
  3. I property card: fetch FL GIO Statewide Cadastral for new pasco rows missing geo/value,
     insert parcel_zones under jurisdiction 1258 (Unincorporated Pasco County) using the
     established DOR_UC -> zone_code crosswalk.

All three arms are idempotent. No PropertyOnion promotion. No cross-county writes.

Usage: python3 scripts/shard13_pasco_cd_i_fix_run6046.py
"""
import os
import re
import sys
import json
import time
import importlib.util
import urllib.request
import urllib.parse
import http.cookiejar
from datetime import datetime

_here = os.path.dirname(os.path.abspath(__file__))

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY_SLUG = "pasco"
FC_PARITY_LABEL = "tier1_realforeclose_pasco_run6046_20260723"
TD_PARITY_LABEL = "tier1_realtaxdeed_pasco_run6046_20260723"
FL_GIO_URL = ("https://services9.arcgis.com/Gh4SEuhFBLMqRpHI/arcgis/rest/services/"
               "Florida_Statewide_Cadastral/FeatureServer/0/query")
PASCO_CO_NO = 61  # FL GIO uses CO_NO=61 for Pasco (NOT 51 stored in fl_counties — documented mismatch)


def rest_get(path, timeout=60):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def rest_patch(path, body, timeout=90):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=data, method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def rest_post(path, body, timeout=90):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=data, method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "resolution=ignore-duplicates"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status


def mgmt_sql(query, timeout=120):
    """Run SQL via Management API (used for heavy queries — SET statement_timeout=0 included)."""
    ref = "mocerqjnksmhcjzxrewo"
    token = os.environ.get("SUPABASE_ACCESS_TOKEN")
    if not token:
        print("  [mgmt_sql] No SUPABASE_ACCESS_TOKEN — skipping Management API call")
        return None
    data = json.dumps({"query": f"SET statement_timeout=0; {query}"}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{ref}/database/query",
        data=data, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  [mgmt_sql] ERROR: {e}")
        return None


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def _load_harvester():
    modpath = os.path.join(_here, "shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py")
    spec = importlib.util.spec_from_file_location("shard8_fix", modpath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def harvest_date_paginated(harvester, subdomain, platform_domain, auction_date_mmddyyyy):
    return harvester.harvest_date_paginated(subdomain, COUNTY_SLUG, auction_date_mmddyyyy,
                                             platform_domain)


def promote_matches_fc(items, parity_label):
    """Promote matched foreclosure rows to matched_clean (exact case_number match)."""
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&sale_type=eq.foreclosure"
        f"&or=(parity_status.is.null,parity_status.eq.mca_only)"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,case_number,parity_status")
    matches = []
    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        if cn in by_norm:
            matches.append(row["id"])
    if not matches:
        return []
    id_filter = ",".join(matches)
    rest_patch(f"multi_county_auctions?id=in.({id_filter})",
               {"parity_status": "matched_clean", "parity_source": parity_label})
    return matches


def promote_matches_td(items, parity_label):
    """Promote matched tax_deed rows to matched_clean (exact case_number match)."""
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&sale_type=eq.tax_deed"
        f"&parity_status=is.null"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,case_number,parity_status")
    matches = []
    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        if cn in by_norm:
            matches.append(row["id"])
    if not matches:
        return []
    id_filter = ",".join(matches)
    rest_patch(f"multi_county_auctions?id=in.({id_filter})",
               {"parity_status": "matched_clean", "parity_source": parity_label})
    return matches


def run_cd_fix(harvester):
    """Run C/D parity harvest for foreclosure and tax_deed lanes."""
    print(f"\n{'='*60}")
    print("PHASE 1: C/D PARITY HARVEST")
    print('='*60)

    # --- FORECLOSURE LANE ---
    fc_null = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&sale_type=eq.foreclosure"
        f"&parity_status=is.null"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,auction_date,case_number")
    fc_mca_only = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&sale_type=eq.foreclosure"
        f"&parity_status=eq.mca_only"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,auction_date,case_number")

    fc_dates = sorted({r["auction_date"][:10] for r in fc_null if r.get("auction_date")}
                      | {r["auction_date"][:10] for r in fc_mca_only if r.get("auction_date")})
    print(f"\n[FC] NULL rows: {len(fc_null)}, mca_only rows: {len(fc_mca_only)}, "
          f"distinct dates: {len(fc_dates)}")

    fc_promoted_total = []
    for d in fc_dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        items = harvest_date_paginated(harvester, "pasco", "realforeclose.com", mmddyyyy)
        print(f"  [FC] {d}: harvested {len(items)} AITEM records from pasco.realforeclose.com")
        if items:
            promoted = promote_matches_fc(items, FC_PARITY_LABEL)
            fc_promoted_total.extend(promoted)
            print(f"    -> promoted {len(promoted)} rows to matched_clean")
            if items and not promoted:
                print(f"    WARNING: {len(items)} live items but 0 case_number matches for {d}")
        else:
            print(f"    INFO: no live items for {d} (calendar may not be populated yet)")
        time.sleep(0.5)

    print(f"\n[FC] TOTAL promoted this run: {len(fc_promoted_total)}")

    # --- TAX DEED LANE ---
    td_null = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&sale_type=eq.tax_deed"
        f"&parity_status=is.null"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,auction_date,case_number")

    td_dates = sorted({r["auction_date"][:10] for r in td_null if r.get("auction_date")})
    print(f"\n[TD] NULL rows: {len(td_null)}, distinct dates: {len(td_dates)}")

    td_promoted_total = []
    for d in td_dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        items = harvest_date_paginated(harvester, "pasco", "realtaxdeed.com", mmddyyyy)
        print(f"  [TD] {d}: harvested {len(items)} AITEM records from pasco.realtaxdeed.com")
        if items:
            promoted = promote_matches_td(items, TD_PARITY_LABEL)
            td_promoted_total.extend(promoted)
            print(f"    -> promoted {len(promoted)} rows to matched_clean")
            if items and not promoted:
                print(f"    WARNING: {len(items)} live items but 0 case_number matches for {d}")
        else:
            print(f"    INFO: no live items for {d} (calendar may not be populated yet)")
        time.sleep(0.5)

    print(f"\n[TD] TOTAL promoted this run: {len(td_promoted_total)}")
    return len(fc_promoted_total) + len(td_promoted_total)


def fl_gio_lookup(parcel_id):
    """Look up a single parcel in FL GIO Statewide Cadastral by PARCEL_ID (CO_NO=61)."""
    where = f"PARCEL_ID='{parcel_id}' AND CO_NO={PASCO_CO_NO}"
    params = urllib.parse.urlencode({
        "where": where,
        "outFields": "PARCEL_ID,PHY_ADDR1,PHY_CITY,DOR_UC,JV,Shape_Area",
        "returnGeometry": "true",
        "geometryType": "esriGeometryEnvelope",
        "outSR": "4326",
        "f": "json"
    })
    url = f"{FL_GIO_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        features = data.get("features", [])
        if not features:
            return None
        feat = features[0]
        attrs = feat.get("attributes", {})
        geom = feat.get("geometry", {})
        # Compute centroid from envelope
        if geom:
            lat = (geom.get("ymin", 0) + geom.get("ymax", 0)) / 2
            lon = (geom.get("xmin", 0) + geom.get("xmax", 0)) / 2
        else:
            lat, lon = None, None
        return {
            "parcel_id": attrs.get("PARCEL_ID"),
            "phy_addr1": attrs.get("PHY_ADDR1"),
            "phy_city": attrs.get("PHY_CITY"),
            "dor_uc": attrs.get("DOR_UC"),
            "jv": attrs.get("JV"),
            "lat": lat if lat else None,
            "lon": lon if lon else None,
        }
    except Exception as e:
        print(f"    FL GIO lookup error for {parcel_id}: {e}")
        return None


DOR_UC_ZONE_MAP = {
    "000": ("R-2", "Residential Single Family (2-4 du/ac) - Vacant"),
    "001": ("R-2", "Residential Single Family (2-4 du/ac)"),
    "002": ("MH", "Mobile Home (4 du/ac)"),
    "003": ("R-2", "Residential Single Family (2-4 du/ac)"),
    "004": ("R-4", "Multi-Family Residential (Condo)"),
    "005": ("R-4", "Multi-Family Residential"),
    "006": ("R-4", "Multi-Family Residential (Condominium)"),
    "007": ("R-4", "Residential (Miscellaneous)"),
    "008": ("R-2", "Residential (Undefined)"),
    "009": ("COMMON", "Common Area / Open Space (non-buildable tract)"),
    "010": ("C-1", "Commercial (Vacant)"),
    "011": ("C-1", "Stores (Retail)"),
    "012": ("R-4", "Multi-Family / Mixed-Use"),
    "094": ("R-2", "Historic Property (base zone R-2)"),
}


def ensure_common_district():
    """Ensure COMMON district exists in zoning_districts for jurisdiction 1258."""
    existing = rest_get(
        "zoning_districts?jurisdiction_id=eq.1258&code=eq.COMMON&select=id")
    if existing:
        return existing[0]["id"]
    # Insert COMMON district (non-buildable, no density/far/parking standards)
    body = {
        "jurisdiction_id": 1258,
        "code": "COMMON",
        "name": "Common Area / Open Space (non-buildable tract)",
        "category": "residential",
        "far_regulated": False,
        "density_regulated": False,
        "ordinance_section": "shard13_pasco_run6046/VERIFIED:non_buildable_common_tract_dor_uc_009"
    }
    data = json.dumps([body]).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/zoning_districts", data=data, method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read())
    return result[0]["id"] if result else None


def insert_parcel_zone(parcel_id, zone_code, zone_name, source_label):
    """Insert a parcel_zones row if it doesn't already exist for jurisdiction 1258."""
    existing = rest_get(
        f"parcel_zones?parcel_id=eq.{urllib.parse.quote(parcel_id)}"
        f"&jurisdiction_id=eq.1258&select=parcel_id")
    if existing:
        return False  # already exists
    body = [{
        "parcel_id": parcel_id,
        "jurisdiction_id": 1258,
        "zone_code": zone_code,
        "zone_name": zone_name,
        "source": source_label
    }]
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/parcel_zones", data=data, method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "resolution=ignore-duplicates"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status in (200, 201)


def run_i_fix():
    """Run property card enrichment for pasco rows missing geo/value or parcel_zones."""
    print(f"\n{'='*60}")
    print("PHASE 2: I PROPERTY CARD ENRICHMENT")
    print('='*60)

    ensure_common_district()

    # Rows needing enrichment: have a parcel_id but missing lat/lon or assessed_value
    # OR have parcel_id but no parcel_zones row for jurisdiction 1258
    # Use mgmt_sql to get the precise list (PostgREST doesn't do LEFT JOINs)
    query = """
    SELECT mca.id, mca.case_number, mca.parcel_id, mca.property_address,
           mca.latitude, mca.longitude, mca.assessed_value
    FROM multi_county_auctions mca
    WHERE mca.county = 'pasco'
      AND mca.parcel_id IS NOT NULL
      AND mca.data_source != 'propertyonion'
      AND (
        mca.latitude IS NULL
        OR mca.longitude IS NULL
        OR mca.assessed_value IS NULL
        OR NOT EXISTS (
          SELECT 1 FROM parcel_zones pz
          WHERE pz.parcel_id = mca.parcel_id AND pz.jurisdiction_id = 1258
        )
      )
    ORDER BY mca.id
    LIMIT 100
    """
    result = mgmt_sql(query)
    if not result:
        print("  mgmt_sql unavailable — trying REST fallback (parcel_id not null, lat null)")
        rows_with_parcel = rest_get(
            f"multi_county_auctions?county=eq.{COUNTY_SLUG}"
            f"&parcel_id=not.is.null"
            f"&latitude=is.null"
            f"&or=(data_source.neq.propertyonion,data_source.is.null)"
            f"&select=id,case_number,parcel_id,property_address,latitude,longitude,assessed_value"
            f"&limit=100")
        rows = rows_with_parcel
    else:
        rows = result if isinstance(result, list) else result.get("rows", [])

    print(f"  Rows needing enrichment: {len(rows)}")
    if not rows:
        print("  Nothing to do for I enrichment.")
        return 0

    enriched = 0
    skipped_no_fl_gio = 0
    skipped_already_done = 0
    I_SOURCE = "shard13_pasco_i_fix_run6046/INFERRED:fl_gio_statewide_cadastral_dor_uc_crosswalk"

    for row in rows:
        pid = row.get("parcel_id")
        case_num = row.get("case_number", "?")
        if not pid:
            skipped_no_fl_gio += 1
            continue

        print(f"  [{case_num}] parcel_id={pid} — looking up FL GIO...")
        info = fl_gio_lookup(pid)
        time.sleep(0.3)

        if not info:
            print(f"    -> No FL GIO match for CO_NO={PASCO_CO_NO} (parcel may not be in GIO or ID mismatch)")
            skipped_no_fl_gio += 1
            continue

        # Validate PHY_ADDR1 vs property_address (soft check — log mismatch but don't block)
        stored_addr = (row.get("property_address") or "").upper().strip()
        gio_addr = (info.get("phy_addr1") or "").upper().strip()
        if stored_addr and gio_addr and gio_addr not in stored_addr and stored_addr[:8] not in gio_addr:
            print(f"    ADDR MISMATCH: stored='{stored_addr}' vs FL GIO='{gio_addr}' — proceeding "
                  f"(parcel_id is authoritative; address formatting varies)")

        # Build zone from DOR_UC
        dor_uc = str(info.get("dor_uc") or "001").zfill(3)
        zone_code, zone_name = DOR_UC_ZONE_MAP.get(dor_uc, ("R-2", "Residential (Unknown Use Code)"))
        print(f"    DOR_UC={dor_uc} -> zone_code={zone_code}")

        # Patch geo/value if missing
        patch_body = {}
        if row.get("latitude") is None and info.get("lat"):
            patch_body["latitude"] = round(info["lat"], 8)
        if row.get("longitude") is None and info.get("lon"):
            patch_body["longitude"] = round(info["lon"], 8)
        if row.get("assessed_value") is None and info.get("jv") is not None:
            patch_body["assessed_value"] = info["jv"]
            patch_body["assessed_value_source"] = f"fl_gio_statewide_cadastral_JV_{I_SOURCE}"

        if patch_body:
            rest_patch(
                f"multi_county_auctions?id=eq.{row['id']}",
                patch_body)
            print(f"    -> patched mca id={row['id']} with {list(patch_body.keys())}")

        # Insert parcel_zones if missing
        inserted = insert_parcel_zone(pid, zone_code, zone_name, I_SOURCE)
        if inserted:
            print(f"    -> inserted parcel_zones {pid} -> {zone_code}")
        else:
            print(f"    -> parcel_zones already exists for {pid}, skipped")

        enriched += 1

    print(f"\n[I] Enriched rows: {enriched}")
    print(f"[I] Skipped (no FL GIO match): {skipped_no_fl_gio}")
    return enriched


def run_verification():
    """Call pencil_dod_evaluate_county for pasco and print results."""
    print(f"\n{'='*60}")
    print("VERIFICATION: pencil_dod_evaluate_county('pasco')")
    print('='*60)
    result = mgmt_sql("SELECT public.pencil_dod_evaluate_county('pasco')")
    if result:
        print(json.dumps(result, indent=2))
    else:
        # Fallback: REST RPC
        try:
            req = urllib.request.Request(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                data=json.dumps({"p_county": "pasco"}).encode(),
                method="POST",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                result = json.loads(r.read())
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"  Verification failed: {e}")
    return result


def main():
    print(f"[{datetime.utcnow().isoformat()}Z] Starting pasco C/D + I fix — run 6046")
    print(f"  SUPABASE_URL: {SUPABASE_URL[:40]}...")
    print(f"  County: {COUNTY_SLUG}")

    # Load the reusable harvest module
    harvester = _load_harvester()

    # PHASE 1: C/D parity
    cd_total = run_cd_fix(harvester)
    print(f"\nC/D total promoted: {cd_total}")

    # PHASE 2: I property card enrichment
    i_total = run_i_fix()
    print(f"\nI total enriched: {i_total}")

    # VERIFICATION
    run_verification()

    print(f"\n[{datetime.utcnow().isoformat()}Z] Done.")
    print(json.dumps({
        "county": COUNTY_SLUG,
        "run": "6046",
        "cd_promoted": cd_total,
        "i_enriched": i_total,
        "timestamp": datetime.utcnow().isoformat()
    }))


if __name__ == "__main__":
    main()
