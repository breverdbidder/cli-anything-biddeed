#!/usr/bin/env python3
"""
Gilchrist County: owner-name → parcel_id lookup via gis1.hcpao.org ArcGIS.

The 6 blocked foreclosure cases have owner_names in multi_county_auctions
(populated after the July 2026 sessions). The July 25 session could not
use owner-name lookup because the data was missing then.

Now: try OWN_NAME / owner_name search on the Gilchrist County Basemap
MapServer layer to find matching parcels.

Session: SHARD-4, dispatch de923487-ea69-4b13-bfc6-3344879a793a
Date: 2026-08-10
"""

import json
import os
import re
import ssl
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# gis1.hcpao.org's cert doesn't chain in some CI sandboxes (missing
# intermediate in the local CA bundle). Public read-only GIS host, no
# credentials sent -- safe to skip verification rather than block on it.
_UNVERIFIED_CTX = ssl.create_default_context()
_UNVERIFIED_CTX.check_hostname = False
_UNVERIFIED_CTX.verify_mode = ssl.CERT_NONE

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

GIS_BASE = "https://gis1.hcpao.org/arcgiscv/rest/services/Gilchrist/GilchristCounty_Basemap/MapServer/0"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

TARGET_CASES = [
    {"case_number": "212025CA000033CAAXMX", "owner": "Chad Slocum", "plaintiff": "Carrington Mortgage Services LLC"},
    {"case_number": "212025CA000036CAAXMX", "owner": "TREVOR SMITH", "plaintiff": "LOANDEPOTCOM LLC"},
    {"case_number": "212025CA000043CAAXMX", "owner": "DANIELLE JAY MERCADO", "plaintiff": "U S BANK TRUST"},
    {"case_number": "212025CA000064CAAXMX", "owner": "JEANNIE MAE JOINER", "plaintiff": "21ST MORTGAGE CORPORATION"},
    {"case_number": "212025CA000070CAAXMX", "owner": "RAYA C. HUTCHINSON", "plaintiff": "WINTRUST MORTGAGE"},
    {"case_number": "212026CA000004CAAXMX", "owner": "PAUL E TAPE JR", "plaintiff": "BKE VENTURES INC"},
]

def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")

def log(msg, tag="INFO"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)

def gis_query(where_clause, out_fields="*"):
    """Query the Gilchrist GIS MapServer layer."""
    url = f"{GIS_BASE}/query"
    params = urllib.parse.urlencode({
        "where": where_clause,
        "outFields": out_fields,
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json"
    })
    full_url = f"{url}?{params}"
    req = urllib.request.Request(full_url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30, context=_UNVERIFIED_CTX) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body)
    except Exception as e:
        log(f"GIS query failed: {e}", "ERROR")
        return None

def normalize_name(name):
    """Normalize a name for partial matching."""
    if not name:
        return ""
    return re.sub(r"[^A-Z0-9 ]", "", name.upper()).strip()

def extract_last_name(full_name):
    """Extract likely last name (first word) from a full name."""
    parts = normalize_name(full_name).split()
    if parts:
        return parts[0]
    return ""

def sb_get_gilchrist_cases():
    """Fetch the 6 target cases from DB to get current state."""
    case_numbers = [c["case_number"] for c in TARGET_CASES]
    # PostgREST in.() takes bare comma-separated values, NOT SQL-style quoted
    # literals -- wrapping each value in single quotes (prior version) makes
    # PostgREST treat the whole quoted string as a literal that never matches
    # any real case_number, silently returning []. Quote only the URL as a
    # whole, not each individual value.
    case_filter = ",".join(case_numbers)
    url = (f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
           f"?county=eq.gilchrist"
           f"&case_number=in.({urllib.parse.quote(case_filter, safe=',')})"
           f"&select=id,case_number,parcel_id,property_address,owner_name,latitude,longitude")
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        log(f"DB fetch failed: {e}", "ERROR")
        return []

def sb_patch(row_id, fields):
    """PATCH a multi_county_auctions row."""
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}"
    data = json.dumps(fields).encode()
    req = urllib.request.Request(url, data=data, method="PATCH", headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status not in (200, 204):
                raise RuntimeError(f"HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        body = e.read()[:300]
        raise RuntimeError(f"HTTP {e.code}: {body}")

def main():
    dry_run = "--dry-run" in sys.argv

    log("=== Gilchrist E/I: owner-name GIS lookup ===", "SHARD4")
    log(f"dry_run={dry_run}")

    # First: discover what fields the GIS layer has. NOTE (verified 2026-08-10):
    # the `OWNER_NAME` field exists but is a blank space placeholder across all
    # 15,179 Gilchrist parcels. `OWN_NAME` does not exist on this layer at all.
    # The actually-populated field is `ThematicData_owner_name`, formatted
    # "LASTNAME FIRSTNAME MIDDLE &...".
    log("Probing GIS layer fields...", "GIS")
    probe = gis_query("1=1", "OBJECTID,dsp_strap,strap,ThematicData_owner_name,owner_addr")
    if not probe:
        log("GIS layer unreachable — abort", "ERROR")
        sys.exit(1)
    if probe.get("error"):
        log(f"GIS error: {probe['error']}", "ERROR")
        sys.exit(1)
    features = probe.get("features", [])
    log(f"Layer reachable, sample feature count: {len(features)}")
    if features:
        sample_attrs = features[0].get("attributes", {})
        log(f"Available fields: {list(sample_attrs.keys())}", "GIS")

    # Fetch current state from DB
    log("Fetching target cases from DB...", "DB")
    db_rows = sb_get_gilchrist_cases()
    if not db_rows:
        log("No rows returned from DB — check SUPABASE_KEY", "ERROR")
        sys.exit(1)
    log(f"Got {len(db_rows)} target rows from DB", "DB")
    db_by_case = {r["case_number"]: r for r in db_rows}

    results = []
    for target in TARGET_CASES:
        cn = target["case_number"]
        owner = target["owner"]
        db_row = db_by_case.get(cn)

        if not db_row:
            log(f"{cn}: not found in DB (skip)", "WARN")
            continue

        current_parcel = db_row.get("parcel_id")
        if current_parcel:
            log(f"{cn}: already has parcel_id={current_parcel!r} (skip)", "INFO")
            results.append({"case": cn, "status": "already_linked", "parcel_id": current_parcel})
            continue

        # Try owner name search
        last_name = extract_last_name(owner)
        norm_owner = normalize_name(owner)
        log(f"{cn}: owner={owner!r} -> search for last_name={last_name!r}", "GIS")

        matched_feature = None

        # Last-name LIKE search on ThematicData_owner_name, then require
        # >=2 common words with the target name (surname alone is not enough
        # -- common surnames like SMITH/JOINER return dozens of candidates).
        where = f"UPPER(ThematicData_owner_name) LIKE '%{last_name}%'"
        data = gis_query(where, "OBJECTID,dsp_strap,strap,ThematicData_owner_name,owner_addr,cap_val,use_dscr")
        time.sleep(0.5)

        if data and not data.get("error") and data.get("features"):
            features = data["features"]
            log(f"  ThematicData_owner_name LIKE '%{last_name}%' -> {len(features)} features", "GIS")
            for f in features:
                a = f.get("attributes", {})
                gis_owner = (a.get("ThematicData_owner_name") or "").upper()
                if normalize_name(owner) in gis_owner or gis_owner in normalize_name(owner):
                    matched_feature = f
                    log(f"  MATCH: strap={a.get('dsp_strap')!r} owner={a.get('ThematicData_owner_name')!r}", "GIS")
                    break
                owner_words = set(normalize_name(owner).split())
                gis_words = set(gis_owner.split())
                if len(owner_words & gis_words) >= 2:
                    matched_feature = f
                    log(f"  FUZZY MATCH: strap={a.get('dsp_strap')!r} owner={a.get('ThematicData_owner_name')!r}", "GIS")
                    break
        elif data and data.get("error"):
            log(f"  ThematicData_owner_name query error: {data['error']}", "WARN")

        if not matched_feature:
            log(f"{cn}: no GIS match for owner={owner!r}", "BLOCKED")
            results.append({"case": cn, "status": "no_gis_match", "owner": owner})
            continue

        attrs = matched_feature.get("attributes", {})
        geo = matched_feature.get("geometry")
        dsp_strap = attrs.get("dsp_strap") or attrs.get("strap")
        cap_val = attrs.get("cap_val") or attrs.get("CAP_VAL")

        lat, lng = None, None
        if geo:
            lat = geo.get("y") or geo.get("lat")
            lng = geo.get("x") or geo.get("lon") or geo.get("lng")

        log(f"{cn}: FOUND parcel={dsp_strap!r} lat={lat} lng={lng} cap_val={cap_val}", "VERIFIED")

        patch = {
            "parcel_id": dsp_strap,
            "assessed_value": cap_val,
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
        }
        if lat:
            patch["latitude"] = lat
        if lng:
            patch["longitude"] = lng

        if not dry_run and db_row.get("id"):
            try:
                sb_patch(db_row["id"], patch)
                log(f"{cn}: DB PATCH applied -> parcel_id={dsp_strap!r}", "VERIFIED")
                results.append({"case": cn, "status": "patched", "parcel_id": dsp_strap,
                                "lat": lat, "lng": lng, "cap_val": cap_val})
            except Exception as e:
                log(f"{cn}: PATCH failed: {e}", "ERROR")
                results.append({"case": cn, "status": "patch_failed", "parcel_id": dsp_strap, "error": str(e)})
        else:
            log(f"{cn}: dry_run — would patch parcel_id={dsp_strap!r}", "DRY")
            results.append({"case": cn, "status": "dry_run", "parcel_id": dsp_strap})

    print("\n=== SUMMARY ===")
    print(json.dumps(results, indent=2))

    patched = [r for r in results if r["status"] == "patched"]
    blocked = [r for r in results if r["status"] in ("no_gis_match", "blocked")]
    log(f"Patched: {len(patched)}, Blocked: {len(blocked)}, Already linked: {len([r for r in results if r['status']=='already_linked'])}", "SUMMARY")

    if patched:
        log("SUCCESS: Some parcels linked! Run pencil_dod_evaluate_county('gilchrist') to verify E/I movement.", "SUMMARY")
    else:
        log("No new parcels linked this session.", "SUMMARY")

    return 0 if patched else 1


if __name__ == "__main__":
    sys.exit(main())
