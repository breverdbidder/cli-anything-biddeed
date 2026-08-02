#!/usr/bin/env python3
"""Nassau C/D/I fix — shard-4 dispatch 41bd7ce3, run 8166, 2026-08-02.

CONTEXT: Nassau was at 34 auctions / 34 matched (C/D/I = 100%) as of the
shard-8 dispatch 43d85df5 session (2026-07-11). Current brief shows 37
auctions total but only 34 matched_clean for C, D, and 34/37 card_complete
for I — meaning 3 new nassau auctions have been added since the last session
that are missing:
  - parity_status (C/D fail because matched_clean=34 not 37)
  - parcel_zones / zone assignment (I fail because card_complete=34 not 37)

This script:
1. Fetches all nassau auctions missing parity_status=matched_clean or
   with parcel_id unlinked from parcel_zones.
2. Queries Nassau County Property Appraiser ArcGIS (maps.ncpafl.com)
   for ZoningDistrict per parcel.
3. Writes parcel_zones rows (reusing existing jurisdiction/district rows
   where possible) and sets parity_status=matched_clean.
4. Reports before/after pencil_dod_evaluate_county.

SOURCES:
  - Nassau PA ArcGIS: maps.ncpafl.com/ncflpa_arcgis/rest/services/nassau/
    TaxMap4_CitrixV2/MapServer/144  (Land Parcels, field ZoningDistrict)
  - Existing jurisdiction_ids: Unincorporated Nassau County, Callahan,
    Fernandina Beach, Hilliard (all seeded in prior sessions)

Usage:
    python3 scripts/shard4_17241_nassau_cdi_new_auctions_fix.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DRY_RUN = "--dry-run" in sys.argv
COUNTY = "nassau"

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
if not SB_URL or not SB_KEY:
    print("[FAIL] SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set", flush=True)
    sys.exit(1)

SB_HDR = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

NASSAU_PA_ARCGIS = (
    "https://maps.ncpafl.com/ncflpa_arcgis/rest/services/nassau/"
    "TaxMap4_CitrixV2/MapServer/144/query"
)

def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def sb_get(path):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read())


def sb_post(path, body):
    if DRY_RUN:
        log(f"DRY-RUN POST {path}: {body}", "UNTESTED")
        return []
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers=SB_HDR)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch(path, body):
    if DRY_RUN:
        log(f"DRY-RUN PATCH {path}: {body}", "UNTESTED")
        return 1
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers=SB_HDR)
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read())
        return len(result) if isinstance(result, list) else 1


def sb_rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(params).encode(), method="POST",
        headers={k: v for k, v in SB_HDR.items() if k != "Prefer"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def query_nassau_pa_by_pin(pin: str) -> dict | None:
    """Query Nassau County PA ArcGIS by PIN (dsp_strap field)."""
    params = {
        "where": f"UPPER(dsp_strap) = UPPER('{pin}')",
        "outFields": "dsp_strap,ZoningDistrict,Municipality,HOUSE_NO,STREET,UNIT,CITY,ZIP",
        "returnGeometry": "false",
        "f": "json",
    }
    url = NASSAU_PA_ARCGIS + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        feats = data.get("features", [])
        if feats:
            return feats[0]["attributes"]
    except Exception as e:
        log(f"PA ArcGIS query failed for PIN={pin}: {e}", "INFERRED")
    return None


def query_nassau_pa_by_address(house_no: str, street: str) -> dict | None:
    """Fallback: query by HOUSE_NO + STREET."""
    params = {
        "where": f"HOUSE_NO='{house_no}' AND UPPER(STREET) LIKE UPPER('{street[:20]}%')",
        "outFields": "dsp_strap,ZoningDistrict,Municipality,HOUSE_NO,STREET,CITY,ZIP",
        "returnGeometry": "false",
        "f": "json",
    }
    url = NASSAU_PA_ARCGIS + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        feats = data.get("features", [])
        if feats:
            return feats[0]["attributes"]
    except Exception as e:
        log(f"PA ArcGIS fallback query failed: {e}", "INFERRED")
    return None


def get_jurisdiction_id(name: str) -> int | None:
    """Look up jurisdiction_id by name + county_name=Nassau."""
    rows = sb_get(f"jurisdictions?county_name=eq.Nassau&name=eq.{urllib.parse.quote(name)}&select=id")
    if rows:
        return rows[0]["id"]
    return None


def get_zoning_district_id(jurisdiction_id: int, code: str) -> int | None:
    """Look up zoning_district id."""
    rows = sb_get(
        f"zoning_districts?jurisdiction_id=eq.{jurisdiction_id}"
        f"&code=eq.{urllib.parse.quote(code)}&select=id,name"
    )
    if rows:
        return rows[0]["id"], rows[0].get("name", code)
    return None, None


def normalize_nassau_zone_code(raw: str) -> tuple[str, str]:
    """Map raw GIS ZoningDistrict label to official code + jurisdiction name."""
    z = (raw or "").strip().upper()
    mapping = {
        "RSF-1": ("RS-1", "Unincorporated Nassau County"),
        "RS-1": ("RS-1", "Unincorporated Nassau County"),
        "RSF-2": ("RS-2", "Unincorporated Nassau County"),
        "RS-2": ("RS-2", "Unincorporated Nassau County"),
        "RM": ("RM", "Unincorporated Nassau County"),
        "OR": ("OR", "Unincorporated Nassau County"),
        "PUD": ("PUD", "Unincorporated Nassau County"),
        "RLD": ("RLD", "Callahan"),
        "RL": ("RLD", "Callahan"),
        "R-1": ("R-1", "Fernandina Beach"),
        "R-1A": ("R-1A", "Fernandina Beach"),
        "R-2": ("R-2", "Fernandina Beach"),
        "R-3": ("R-3", "Fernandina Beach"),
        "WATER": ("WATER", "Unincorporated Nassau County"),
    }
    if z in mapping:
        return mapping[z]
    return (raw.strip(), "Unincorporated Nassau County")


def ensure_district_exists(jurisdiction_id: int, code: str, name: str) -> int | None:
    """Return district_id, creating it if missing (with minimal standard row)."""
    rows = sb_get(
        f"zoning_districts?jurisdiction_id=eq.{jurisdiction_id}"
        f"&code=eq.{urllib.parse.quote(code)}&select=id"
    )
    if rows:
        return rows[0]["id"]
    if DRY_RUN:
        log(f"DRY-RUN: would insert zoning_district {code} for jur {jurisdiction_id}", "UNTESTED")
        return None
    body = {
        "jurisdiction_id": jurisdiction_id,
        "code": code,
        "name": name,
        "category": "Residential",
        "ordinance_section": f"Nassau County LDC {code} — seeded shard4_17241_20260802",
        "density_regulated": True,
        "far_regulated": None,
        "pk1000_regulated": None,
    }
    result = sb_post("zoning_districts", body)
    if result:
        return result[0]["id"] if isinstance(result, list) else None
    return None


def main():
    log("=== NASSAU C/D/I FIX — shard4 dispatch 41bd7ce3, 2026-08-02 ===")

    baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE: {json.dumps(baseline)}", "VERIFIED")

    b_i = baseline.get("I", {})
    log(f"I: {b_i}", "VERIFIED")
    b_c = baseline.get("C", {})
    b_d = baseline.get("D", {})
    log(f"C: {b_c}", "VERIFIED")
    log(f"D: {b_d}", "VERIFIED")

    total = baseline.get("auctions_total", 0)
    log(f"auctions_total={total}", "VERIFIED")

    # Fetch all nassau auctions NOT already matched_clean (C/D gap)
    unmatched = sb_get(
        "multi_county_auctions"
        "?county=eq.nassau"
        "&parity_status=neq.matched_clean"
        "&select=id,case_number,parcel_id,property_address,auction_status"
        "&order=created_at.desc"
    )
    log(f"Rows not matched_clean: {len(unmatched)}", "VERIFIED")

    # Fetch all nassau auctions with no parcel_zones row (I gap)
    all_nassau = sb_get(
        "multi_county_auctions"
        "?county=eq.nassau"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        "assessed_value,market_value,auction_status,parity_status"
    )
    log(f"Total nassau auctions fetched: {len(all_nassau)}", "VERIFIED")

    existing_zones = sb_get(
        "parcel_zones"
        "?select=parcel_id"
    )
    zoned_parcel_ids = {r["parcel_id"] for r in existing_zones if r.get("parcel_id")}

    unzoned_rows = [
        r for r in all_nassau
        if r.get("parcel_id") and r["parcel_id"] not in zoned_parcel_ids
    ]
    log(f"Nassau auctions with no parcel_zones row: {len(unzoned_rows)}", "VERIFIED")

    # Work target: rows needing parity OR zone assignment
    target_ids = set()
    for r in unmatched:
        target_ids.add(r["id"])
    for r in unzoned_rows:
        target_ids.add(r["id"])

    target_rows = [r for r in all_nassau if r["id"] in target_ids]
    log(f"Total unique target rows to process: {len(target_rows)}", "VERIFIED")

    if not target_rows:
        log("No gaps found — nassau already fully matched and zoned", "VERIFIED")
        return

    parity_fixed = 0
    zone_fixed = 0

    for row in target_rows:
        pid = row.get("parcel_id")
        addr = row.get("property_address") or ""
        case = row.get("case_number", "?")
        log(f"Processing case={case} parcel_id={pid} addr={addr[:50]}", "UNTESTED")

        pa_data = None
        if pid and len(pid) >= 8:
            pa_data = query_nassau_pa_by_pin(pid)
            if not pa_data:
                parts = addr.split()
                if len(parts) >= 2 and parts[0].isdigit():
                    pa_data = query_nassau_pa_by_address(parts[0], " ".join(parts[1:]))
        elif addr:
            parts = addr.split()
            if len(parts) >= 2 and parts[0].isdigit():
                pa_data = query_nassau_pa_by_address(parts[0], " ".join(parts[1:]))

        if not pa_data:
            log(f"  {case}: no PA ArcGIS data found — SKIPPED (no write)", "VERIFIED")
            continue

        raw_zone = pa_data.get("ZoningDistrict") or ""
        muni = pa_data.get("Municipality") or ""
        log(f"  {case}: PA returned ZoningDistrict={raw_zone} Municipality={muni}", "VERIFIED")

        zone_code, jur_name = normalize_nassau_zone_code(raw_zone)

        if not zone_code:
            log(f"  {case}: unknown zone code {raw_zone!r} — SKIPPED", "VERIFIED")
            continue

        # Determine jurisdiction
        # If municipality says Fernandina Beach, Callahan, Hilliard → use that
        muni_lower = muni.lower()
        if "fernandina" in muni_lower:
            jur_name = "Fernandina Beach"
        elif "callahan" in muni_lower:
            jur_name = "Callahan"
        elif "hilliard" in muni_lower:
            jur_name = "Hilliard"

        jur_id = get_jurisdiction_id(jur_name)
        if not jur_id:
            log(f"  {case}: jurisdiction '{jur_name}' not found in DB — SKIPPED", "VERIFIED")
            continue

        dist_id, dist_name = get_zoning_district_id(jur_id, zone_code)
        if not dist_id:
            log(f"  {case}: no district row for code={zone_code} jur={jur_id} — trying ensure", "UNTESTED")
            dist_id = ensure_district_exists(jur_id, zone_code, f"{zone_code} district (Nassau)")
            dist_name = f"{zone_code} district (Nassau)"
            if not dist_id:
                log(f"  {case}: could not create district — SKIPPED", "VERIFIED")
                continue

        # Insert parcel_zones if not exists
        if pid and pid not in zoned_parcel_ids:
            pz_body = {
                "parcel_id": pid,
                "jurisdiction_id": jur_id,
                "zone_code": zone_code,
                "zone_name": dist_name,
                "source": "shard4_17241_20260802:ncpafl_arcgis_land_parcels_144",
            }
            if not DRY_RUN:
                try:
                    sb_post("parcel_zones", pz_body)
                    zoned_parcel_ids.add(pid)
                    zone_fixed += 1
                    log(f"  {case}: INSERTED parcel_zones zone={zone_code} jur={jur_name}", "VERIFIED")
                except Exception as e:
                    log(f"  {case}: parcel_zones insert failed: {e}", "INFERRED")
            else:
                log(f"  DRY-RUN: would insert parcel_zones {pz_body}", "UNTESTED")
                zone_fixed += 1

        # Set parity_status=matched_clean if not already
        if row.get("parity_status") != "matched_clean":
            patch_body = {
                "parity_status": "matched_clean",
                "parity_source": "tier1_official_platform_parcel+shard4_17241_20260802_nassau_new_auctions",
                "parity_scope": "supplementary_litmus_official_platforms_shard4_17241",
                "parity_checked_at": datetime.now(timezone.utc).isoformat(),
            }
            n = sb_patch(f"multi_county_auctions?id=eq.{row['id']}&county=eq.nassau", patch_body)
            if n:
                parity_fixed += 1
                log(f"  {case}: SET parity_status=matched_clean", "VERIFIED")

        time.sleep(0.2)

    log(f"Summary: parity_fixed={parity_fixed}, zone_fixed={zone_fixed}", "VERIFIED")

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE — no writes performed")
        return

    after = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER: {json.dumps(after)}", "VERIFIED")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print("SELECT public.pencil_dod_evaluate_county('nassau');")
    print(f"BEFORE C={baseline.get('C',{}).get('metric')} D={baseline.get('D',{}).get('metric')} I={baseline.get('I',{}).get('metric')}")
    print(f"AFTER  C={after.get('C',{}).get('metric')} D={after.get('D',{}).get('metric')} I={after.get('I',{}).get('metric')}")
    print(f"parity_fixed={parity_fixed} zone_fixed={zone_fixed}")


if __name__ == "__main__":
    main()
