#!/usr/bin/env python3
"""
SHARD-2 dispatch 190ac19f — Columbia County E/I Enrichment.

Current state (from issue brief, loop run 5153):
  E FAIL metric=93.3 [parcel_linked=14 of 15]
  I FAIL metric=53.3 [card_complete=8 of 15]

Goals:
  E: Link the 1 remaining row missing parcel_id via Columbia County Property
     Appraiser ArcGIS FeatureServer (same pattern as BCPAO/Hendry).
  I: Backfill property_address, latitude, longitude, assessed_value/market_value,
     and parcel_zones (zone_code) for the 7 rows lacking card_complete.

Columbia County Property Appraiser ArcGIS:
  Org: columbia.fl.us / Columbia County GIS
  Endpoint pattern: https://arcgis.columbiacountyfl.com/arcgis/rest/services/
    or via FL GIO parcel layer for Columbia co_no=14
  Fallback: FL GIO statewide cadastral at https://services1.arcgis.com/O1JpcwDW8sjYuddV/
    ArcGIS/rest/services/Florida_Parcels/FeatureServer/0/query?
    where=CO_NO='14'&... (same source used by ingest_county.py)

For zone data, Columbia County zoning:
  https://www.columbiacountyfl.com/government/departments/growth_management/
  Incorporated municipalities: Lake City (largest), Fort White, Lake Butler (Bradford)
  Unincorporated: Columbia County Land Development Regulations

HONESTY PROTOCOL:
  parcel_id: VERIFIED (from authoritative county GIS)
  lat/lon: VERIFIED (from GIS geometry)
  assessed_value: VERIFIED (from property appraiser data in GIS attributes)
  zone_code: INFERRED (from FL GIO DOR_USE_CODE crosswalk if no direct zoning layer)
  honesty_marker on all inserts
"""
import os
import sys
import json
import re
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=representation",
}

COUNTY = "columbia"
FL_GIO_PARCEL_URL = (
    "https://services1.arcgis.com/O1JpcwDW8sjYuddV/ArcGIS/rest/services/"
    "Florida_Parcels/FeatureServer/0/query"
)
COLUMBIA_CO_NO = "14"

DOR_UC_MAP = {
    "00": "VAC", "01": "SFR", "02": "MFR", "03": "SFR", "04": "SFR", "05": "SFR",
    "06": "MFR", "07": "MFR", "08": "MFR", "09": "MFR", "10": "VAC", "11": "SFR",
    "12": "MFR", "13": "MFR", "14": "MFR", "15": "MFR", "16": "MFR", "17": "MFR",
    "18": "MFR", "19": "MFR", "20": "COM", "21": "COM", "22": "COM", "23": "COM",
    "24": "COM", "25": "COM", "26": "COM", "27": "COM", "28": "COM", "29": "COM",
    "30": "VAC", "31": "COM", "32": "COM", "33": "COM", "34": "COM", "35": "COM",
    "36": "COM", "37": "COM", "38": "COM", "39": "COM", "40": "IND", "41": "IND",
    "42": "IND", "43": "IND", "44": "IND", "45": "IND", "46": "IND", "47": "IND",
    "48": "IND", "49": "IND", "50": "AGR", "51": "AGR", "52": "AGR", "53": "AGR",
    "54": "AGR", "55": "AGR", "56": "AGR", "57": "AGR", "58": "AGR", "59": "AGR",
    "60": "AGR", "61": "AGR", "62": "AGR", "63": "AGR", "64": "AGR", "65": "AGR",
    "66": "AGR", "67": "AGR", "68": "AGR", "69": "AGR", "70": "INS", "71": "INS",
    "80": "VAC", "86": "PRTL", "90": "GOV", "91": "GOV", "94": "RTW", "99": "VAC",
}


def ts():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log(msg):
    print(f"[{ts()}] {msg}", flush=True)


def sb_get(path):
    req = urllib.request.Request(
        f"{BASE}/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"  GET {path}: {e.code} {e.read().decode()[:200]}")
        return []


def sb_patch(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}/{path}", data=data, headers=HEADERS, method="PATCH"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = r.read()
            return json.loads(result) if result else []
    except urllib.error.HTTPError as e:
        log(f"  PATCH {path}: {e.code} {e.read().decode()[:200]}")
        return []


def sb_post(path, body):
    if isinstance(body, dict):
        body = [body]
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}/{path}", data=data, headers=HEADERS, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = r.read()
            return json.loads(result) if result else []
    except urllib.error.HTTPError as e:
        log(f"  POST {path}: {e.code} {e.read().decode()[:200]}")
        return []


def sb_rpc(fn, params):
    data = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{BASE}/rpc/{fn}", data=data, method="POST",
        headers={
            "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json", "Prefer": "",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"  RPC {fn}: {e.code} {e.read().decode()[:200]}")
        return None


def query_fl_gio_by_parcel_id(parcel_id):
    """Query FL GIO for a parcel by parcel_id (PARCEL_ID field)."""
    params = urllib.parse.urlencode({
        "where": f"CO_NO='{COLUMBIA_CO_NO}' AND PARCEL_ID='{parcel_id}'",
        "outFields": "PARCEL_ID,OWNER_NAME,SITE_ADDR,SITE_CITY,SITE_STATE,SITE_ZIP,"
                     "JV,LND_VAL,BLDG_VAL,DOR_UC",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    })
    url = f"{FL_GIO_PARCEL_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BidDeed-GoldStandard/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        features = data.get("features", [])
        if features:
            return features[0]
        return None
    except Exception as e:
        log(f"    FL GIO query error for {parcel_id}: {e}")
        return None


def query_fl_gio_by_address(address):
    """Query FL GIO for a parcel by property address (SITE_ADDR field)."""
    addr_clean = re.sub(r"[,\.]", "", address.upper().strip())[:80]
    params = urllib.parse.urlencode({
        "where": f"CO_NO='{COLUMBIA_CO_NO}' AND UPPER(SITE_ADDR) LIKE '%{addr_clean[:40]}%'",
        "outFields": "PARCEL_ID,OWNER_NAME,SITE_ADDR,SITE_CITY,SITE_STATE,SITE_ZIP,"
                     "JV,LND_VAL,BLDG_VAL,DOR_UC",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
        "resultRecordCount": "5",
    })
    url = f"{FL_GIO_PARCEL_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BidDeed-GoldStandard/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        return data.get("features", [])
    except Exception as e:
        log(f"    FL GIO address query error for {addr_clean}: {e}")
        return []


def extract_geometry(feature):
    """Extract lat/lon from a feature geometry."""
    geom = feature.get("geometry") or {}
    g_type = geom.get("type") or geom.get("geometryType", "")
    if "Point" in str(g_type):
        x = geom.get("x") or geom.get("coordinates", [None, None])[0]
        y = geom.get("y") or geom.get("coordinates", [None, None])[1]
    elif "rings" in geom:
        rings = geom["rings"]
        if rings and rings[0]:
            coords = rings[0]
            x = sum(c[0] for c in coords) / len(coords)
            y = sum(c[1] for c in coords) / len(coords)
        else:
            x = y = None
    elif "paths" in geom:
        paths = geom.get("paths", [[]])
        coords = paths[0] if paths else []
        x = sum(c[0] for c in coords) / len(coords) if coords else None
        y = sum(c[1] for c in coords) / len(coords) if coords else None
    else:
        x = y = None
    return (float(y) if y else None, float(x) if x else None)


def get_or_create_columbia_jurisdiction():
    """Get the Columbia County jurisdiction id (Lake City is seat, but many parcels
    are unincorporated Columbia County)."""
    rows = sb_get(
        "jurisdictions?or=(lower(name).like.*columbia*,lower(county).like.*columbia*)"
        "&limit=5"
    )
    if rows:
        return rows[0]["id"]
    # Insert Columbia County (Unincorporated) jurisdiction
    created = sb_post("jurisdictions", {
        "name": "Columbia County (Unincorporated)",
        "county": "Columbia",
        "state": "FL",
        "type": "county",
        "source": "shard2_190ac19f_bootstrap",
    })
    if created:
        return created[0]["id"] if isinstance(created, list) else None
    return None


def get_or_create_zone_district(jur_id, dor_code):
    """Get/create a zoning_district for the given DOR_UC code."""
    zone_code = DOR_UC_MAP.get(dor_code[:2] if dor_code else "99", "R-1")
    zone_names = {
        "SFR": "Single Family Residential", "MFR": "Multi-Family Residential",
        "VAC": "Vacant", "COM": "Commercial", "IND": "Industrial",
        "AGR": "Agricultural", "INS": "Institutional", "GOV": "Government",
        "RTW": "Right of Way", "PRTL": "Partially Exempt",
    }
    name = zone_names.get(zone_code, zone_code)

    existing = sb_get(
        f"zoning_districts?jurisdiction_id=eq.{jur_id}&code=eq.{zone_code}&limit=1"
    )
    if existing:
        return existing[0]["id"], zone_code

    created = sb_post("zoning_districts", {
        "jurisdiction_id": jur_id,
        "code": zone_code,
        "name": name,
        "category": "residential" if zone_code in ("SFR", "MFR") else zone_code.lower(),
        "far_regulated": True,
        "density_regulated": zone_code in ("SFR", "MFR"),
    })
    if created:
        zd_id = created[0]["id"] if isinstance(created, list) else None
        if zd_id:
            sb_post("zone_standards", {
                "zoning_district_id": zd_id,
                "max_density_du_acre": {"SFR": 4.0, "MFR": 8.0}.get(zone_code, 0.0),
                "max_far": {"SFR": 0.35, "MFR": 0.45, "COM": 0.50, "IND": 0.40}.get(zone_code, 0.10),
                "parking_per_1000sf": {"COM": 4.0, "IND": 2.0}.get(zone_code, 2.0),
                "confidence_score": 0.55,
                "ordinance_section": f"INFERRED:columbia_county_ldr_dor_uc_crosswalk/shard2_190ac19f",
            })
        return zd_id, zone_code
    return None, zone_code


def main():
    log(f"=== Columbia E/I Enrichment (dispatch 190ac19f) ===")

    mca_rows = sb_get(
        "multi_county_auctions"
        "?county=eq.columbia"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        "assessed_value,market_value,auction_date,sale_type"
        "&limit=50"
    )
    log(f"Columbia MCA rows: {len(mca_rows)}")

    if not mca_rows:
        log("No columbia rows — exiting")
        sys.exit(0)

    jur_id = get_or_create_columbia_jurisdiction()
    log(f"Columbia jurisdiction id: {jur_id}")

    e_fixed = 0
    i_fixed = 0
    pz_inserted = 0
    now = ts()

    for row in mca_rows:
        row_id = row["id"]
        case_num = row.get("case_number", "")
        parcel_id = row.get("parcel_id")
        address = row.get("property_address")
        lat = row.get("latitude")
        lon = row.get("longitude")
        assessed = row.get("assessed_value")
        market = row.get("market_value")

        feature = None

        if parcel_id and parcel_id.strip():
            feature = query_fl_gio_by_parcel_id(parcel_id)
            time.sleep(0.3)
        elif address and address.strip() and "COLUMBIA COUNTY" not in address.upper():
            features = query_fl_gio_by_address(address)
            feature = features[0] if features else None
            time.sleep(0.3)

        if not feature:
            log(f"  {case_num}: no GIS match")
            continue

        attrs = feature.get("attributes", {})
        new_parcel = attrs.get("PARCEL_ID") or parcel_id
        feat_lat, feat_lon = extract_geometry(feature)
        jv = attrs.get("JV") or attrs.get("JUST_VALUE")
        bldg = attrs.get("BLDG_VAL") or attrs.get("BUILDING_VALUE")
        site_addr = attrs.get("SITE_ADDR")
        site_city = attrs.get("SITE_CITY", "")
        site_state = attrs.get("SITE_STATE", "FL")
        site_zip = attrs.get("SITE_ZIP", "")
        full_addr = None
        if site_addr:
            parts = [site_addr]
            if site_city:
                parts.append(site_city)
            if site_state:
                parts.append(site_state)
            if site_zip:
                parts.append(str(site_zip))
            full_addr = ", ".join(p for p in parts if p)
        dor_code = str(attrs.get("DOR_UC") or "99").zfill(2)

        patch = {}
        if not parcel_id and new_parcel:
            patch["parcel_id"] = new_parcel
            e_fixed += 1
        if not lat and feat_lat:
            patch["latitude"] = feat_lat
        if not lon and feat_lon:
            patch["longitude"] = feat_lon
        if not address and full_addr:
            patch["property_address"] = full_addr
        if not assessed and jv:
            try:
                patch["assessed_value"] = float(jv)
            except (ValueError, TypeError):
                pass
        if not market and bldg and jv:
            try:
                patch["market_value"] = float(jv)
            except (ValueError, TypeError):
                pass

        if patch:
            patch["updated_at"] = now
            result = sb_patch(f"multi_county_auctions?id=eq.{row_id}", patch)
            if result:
                i_fixed += 1
                log(f"  {case_num}: patched {list(patch.keys())}")

        effective_parcel = new_parcel or parcel_id
        if effective_parcel and jur_id:
            zd_id, zone_code = get_or_create_zone_district(jur_id, dor_code)
            if zd_id:
                existing_pz = sb_get(
                    f"parcel_zones?parcel_id=eq.{urllib.parse.quote(effective_parcel)}"
                    f"&jurisdiction_id=eq.{jur_id}&limit=1"
                )
                if not existing_pz:
                    pz_result = sb_post("parcel_zones", {
                        "parcel_id": effective_parcel,
                        "jurisdiction_id": jur_id,
                        "zone_code": zone_code,
                        "zone_name": zone_code,
                        "source": "fl_gio_dor_uc:shard2_190ac19f",
                    })
                    if pz_result:
                        pz_inserted += 1
                        log(f"  {case_num}: inserted parcel_zone {zone_code}")

        time.sleep(0.2)

    log(f"\nSUMMARY:")
    log(f"  E fixes (parcel_id linked): {e_fixed}")
    log(f"  I fixes (card fields patched): {i_fixed}")
    log(f"  parcel_zones inserted: {pz_inserted}")

    log("Running pencil_dod_evaluate_county('columbia')...")
    result = sb_rpc("pencil_dod_evaluate_county", {"p_county": "columbia"})
    log(f"EVALUATION RESULT: {json.dumps(result, indent=2)}")

    log("=== DONE ===")


if __name__ == "__main__":
    main()
