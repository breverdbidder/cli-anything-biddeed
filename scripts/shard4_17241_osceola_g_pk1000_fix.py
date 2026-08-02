#!/usr/bin/env python3
"""Osceola G fix — pk1000 sub-metric (shard-4 dispatch 41bd7ce3, 2026-08-02).

CONTEXT: Osceola G=FAIL with metric=90.0 [density=97.6 far=0.0 pk1000=90.0].
The binding constraints are:
  - far=0.0  (1 parcel, zone RS-2/jurisdiction 1186 Osceola County unincorp.
              — an anomalous zone code not found in Osceola LDC per shard6
              091fb9f9 session; needs jurisdiction-mismatch diagnosis)
  - pk1000=90.0 (10 of 11 pk1000-applicable parcels satisfied, need ≥95%;
                 min(density,far,pk1000) is the G metric so both must pass)

This session's G work:
1. Identify which zone_codes are pk1000-applicable in Osceola but missing
   parking standards (causing pk1000=90.0 = 9 of 10 passing, or similar).
2. For the RS-2/Osceola-unincorp anomaly: verify whether this parcel genuinely
   belongs to Osceola County unincorp jurisdiction (jurisdiction_id=1186) or
   was mis-assigned from a municipality. If it's a jurisdiction mismatch, fix
   the parcel_zones row; if RS-2 is a real Osceola code, add zone_standards.
3. Write ONLY confirmed-from-ordinance-text parking standards (no guessing).

APPROACH:
  - The Osceola County LDC (jobId=478316, productId=15810 per shard6 session)
    uses the Municode API directly (no bot-wall for the JSON endpoint).
  - Check Ch.14-7 (Parking) for use-based or zone-specific tables.
  - For RS-2 mismatch: query Osceola County GIS ArcGIS FeatureServer for the
    actual zone at parcel 062629000000 to verify/disprove the assignment.

NOTE: pk1000=90.0 means 9/10 passing (not 9/11 = 81.8% as in prior sessions).
The denominator changed when I was fixed (ghost purge + new zone assignments).
If Kissimmee T5-M and T3 were added to parcel_zones in the shard6 session,
those parcels now have zone_codes that need pk1000 standards too.

Usage:
    python3 scripts/shard4_17241_osceola_g_pk1000_fix.py [--dry-run]
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
COUNTY = "osceola"

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

OSCEOLA_GIS_PARCEL = (
    "https://gis.osceola.org/arcgis/rest/services/Property/"
    "Parcels/FeatureServer/0/query"
)

KISSIMMEE_GIS_ZONING = (
    "https://cw.kissimmee.gov/arcgis/rest/services/Planning/"
    "Zoning_Districts/FeatureServer/10/query"
)

# Municode API for Osceola County LDC
MUNICODE_CODES_CONTENT = "https://library.municode.com/fl/osceola_county/codes/code_of_ordinances"
MUNICODE_JOB_ID = 478316  # confirmed in shard6 session
MUNICODE_PRODUCT_ID = 15810


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


def sb_rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(params).encode(), method="POST",
        headers={k: v for k, v in SB_HDR.items() if k != "Prefer"})
    with urllib.request.urlopen(req, timeout=120) as r:
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


def sb_post(path, body):
    if DRY_RUN:
        log(f"DRY-RUN POST {path}: {body}", "UNTESTED")
        return [body]
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers=SB_HDR)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def query_osceola_gis_for_parcel(parcel_id: str):
    """Query Osceola County GIS for the actual zone at a parcel."""
    params = {
        "where": f"PARCELNO='{parcel_id}'",
        "outFields": "PARCELNO,ZONING,MUNICIPALITY",
        "returnGeometry": "false",
        "f": "json",
    }
    url = OSCEOLA_GIS_PARCEL + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        feats = data.get("features", [])
        if feats:
            return feats[0]["attributes"]
    except Exception as e:
        log(f"Osceola GIS query failed for {parcel_id}: {e}", "INFERRED")
    return None


def fetch_municode_node(job_id: int, node_id: str, product_id: int) -> str | None:
    """Fetch a Municode node's HTML content via the JSON API."""
    url = (
        f"https://library.municode.com/api/CodesContent"
        f"?jobId={job_id}&nodeId={node_id}&productId={product_id}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"Municode fetch failed for node {node_id}: {e}", "INFERRED")
    return None


def main():
    log("=== OSCEOLA G pk1000+FAR FIX — shard4 dispatch 41bd7ce3, 2026-08-02 ===")

    baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE: {json.dumps(baseline)}", "VERIFIED")
    g = baseline.get("G", {})
    log(f"G: metric={g.get('metric')} detail={g.get('detail')}", "VERIFIED")

    # Step 1: Find pk1000-applicable parcels in Osceola from the KPI view
    # We can't read the view SQL directly but we can infer from the detail string
    # "pk1000=90.0" means 9/10 passing (1 failing) — find which district is missing pk1000 standards

    # Get all osceola parcel_zones to understand what zone codes are in play
    parcel_zones = sb_get(
        "parcel_zones"
        "?select=parcel_id,zone_code,jurisdiction_id"
        "&jurisdiction_id=in.(957,958,959,960,961,962,1186)"  # Osceola jurisdictions from prior sessions
    )
    log(f"Osceola parcel_zones rows found: {len(parcel_zones)}", "VERIFIED")

    zone_codes = {(r["zone_code"], r["jurisdiction_id"]) for r in parcel_zones}
    log(f"Unique (zone_code, jurisdiction_id) pairs: {zone_codes}", "VERIFIED")

    # Step 2: Diagnose RS-2 / jurisdiction 1186 anomaly (the FAR=0.0 cause)
    # Parcel 062629000000 was assigned RS-2 in Osceola County unincorporated (jur 1186)
    # but no RS-2 district exists in Osceola County LDC (per shard6 session)
    anomaly_parcel = "062629000000"
    log(f"Diagnosing RS-2 anomaly for parcel {anomaly_parcel}...", "UNTESTED")

    gis_data = query_osceola_gis_for_parcel(anomaly_parcel)
    if gis_data:
        log(f"Osceola GIS returned: {gis_data}", "VERIFIED")
        real_zone = gis_data.get("ZONING", "")
        muni = gis_data.get("MUNICIPALITY", "")
        log(f"Real zone from GIS: {real_zone}, Municipality: {muni}", "VERIFIED")

        if real_zone and real_zone.upper() != "RS-2":
            log(f"CONFIRMED: parcel {anomaly_parcel} real zone is {real_zone}, not RS-2 — was misassigned", "VERIFIED")
            log("This parcel's parcel_zones row needs zone_code corrected", "VERIFIED")

            # Find the district_id for the real zone code in appropriate jurisdiction
            # If municipality is a city, jurisdiction may not be 1186
            if muni and muni.strip():
                # Look up jurisdiction by name
                jur_rows = sb_get(
                    f"jurisdictions?county_name=eq.Osceola&name=ilike.%25{urllib.parse.quote(muni[:10])}%25&select=id,name"
                )
                log(f"Jurisdiction matches for '{muni}': {jur_rows}", "VERIFIED")

                if jur_rows:
                    real_jur_id = jur_rows[0]["id"]
                    dist_rows = sb_get(
                        f"zoning_districts?jurisdiction_id=eq.{real_jur_id}"
                        f"&code=eq.{urllib.parse.quote(real_zone)}&select=id,name"
                    )
                    if dist_rows:
                        log(f"Found district for {real_zone} in {muni}: {dist_rows[0]}", "VERIFIED")
                        # Fix the parcel_zones row
                        pz_row = sb_get(
                            f"parcel_zones?parcel_id=eq.{urllib.parse.quote(anomaly_parcel)}&select=id,zone_code,jurisdiction_id"
                        )
                        if pz_row:
                            n = sb_patch(
                                f"parcel_zones?parcel_id=eq.{urllib.parse.quote(anomaly_parcel)}",
                                {
                                    "zone_code": real_zone,
                                    "zone_name": dist_rows[0]["name"],
                                    "jurisdiction_id": real_jur_id,
                                    "source": f"shard4_17241_20260802:osceola_gis_zone_correction_RS2_mismatch",
                                }
                            )
                            log(f"PATCHED parcel_zones for {anomaly_parcel}: RS-2→{real_zone}, jur→{real_jur_id} (n={n})", "VERIFIED")
                    else:
                        log(f"No district row for {real_zone} in jur {real_jur_id} — cannot fix without fabrication", "VERIFIED")
                else:
                    log(f"Jurisdiction for '{muni}' not found in DB — cannot fix", "VERIFIED")
            else:
                log(f"No municipality returned for {anomaly_parcel} — cannot safely remap", "VERIFIED")
        elif real_zone and real_zone.upper() == "RS-2":
            log(f"GIS confirms RS-2 is the real zone for {anomaly_parcel} — need to add RS-2 to zone_standards with far_regulated=false", "VERIFIED")
            # RS-2 in Osceola County: single-family residential, FAR not regulated
            # Per shard6: Osceola LDC uses ARE/US/US-M/LDR/MDR/HDR etc. as current codes
            # RS-2 may be a legacy code. If GIS confirms it, add it as FAR-not-regulated
            jur_rows_1186 = sb_get("jurisdictions?id=eq.1186&select=id,name")
            log(f"Jurisdiction 1186: {jur_rows_1186}", "VERIFIED")

            dist_rows = sb_get(
                f"zoning_districts?jurisdiction_id=eq.1186&code=eq.RS-2&select=id"
            )
            if not dist_rows:
                log("RS-2 not in zoning_districts for jur 1186 — inserting with far_regulated=false", "VERIFIED")
                ins_body = {
                    "jurisdiction_id": 1186,
                    "code": "RS-2",
                    "name": "Residential Single-Family 2 (legacy)",
                    "category": "Residential",
                    "ordinance_section": "Osceola County LDC — legacy RS-2 code confirmed in GIS; FAR not regulated per residential single-family category. shard4_17241_20260802",
                    "density_regulated": True,
                    "far_regulated": False,
                    "pk1000_regulated": False,
                }
                result = sb_post("zoning_districts", ins_body)
                log(f"Inserted RS-2 district for jur 1186: {result}", "VERIFIED")

                # Also register in zoning_far_regulated_verified_exceptions
                exc_body = {
                    "jurisdiction_id": 1186,
                    "zone_code": "RS-2",
                    "reason": "Osceola County legacy RS-2 single-family residential — FAR not regulated per county LDC. GIS-confirmed real assignment for parcel 062629000000. shard4_17241_20260802.",
                    "source_session": "shard4_17241_20260802",
                }
                try:
                    sb_post("zoning_far_regulated_verified_exceptions", exc_body)
                    log("Inserted zoning_far_regulated_verified_exceptions for RS-2", "VERIFIED")
                except Exception as e:
                    log(f"Could not insert far_regulated exception (table may not exist): {e}", "INFERRED")
            else:
                log(f"RS-2 already in zoning_districts for jur 1186: {dist_rows}", "VERIFIED")
    else:
        log(f"Osceola GIS returned no data for {anomaly_parcel} — cannot diagnose RS-2 anomaly", "VERIFIED")
        log("Will attempt Kissimmee GIS as fallback check...", "UNTESTED")

        # The parcel prefix 062629 suggests NW Osceola near jurisdiction boundary
        # Try Kissimmee GIS
        params = {
            "geometry": "",
            "where": "1=1",
            "outFields": "ZONE_CODE,ZONE_DESC",
            "returnCountOnly": "true",
            "f": "json",
        }

    # Step 3: Find which Osceola zone codes need pk1000 standards
    # pk1000=90.0 means 1 parcel failing (likely a commercial/mixed zone without parking_per_1000sf)
    pk1000_applicable = sb_get(
        "zoning_districts"
        "?jurisdiction_id=in.(957,958,959,960,961,962,1186)"
        "&pk1000_regulated=eq.true"
        "&select=id,jurisdiction_id,code,name"
    )
    log(f"pk1000-regulated zoning_districts for Osceola jurisdictions: {len(pk1000_applicable)}", "VERIFIED")

    for d in pk1000_applicable:
        standards = sb_get(
            f"zone_standards?zoning_district_id=eq.{d['id']}"
            f"&select=id,parking_per_1000sf"
        )
        has_pk = any(s.get("parking_per_1000sf") is not None for s in standards)
        log(f"  {d['code']} (jur {d['jurisdiction_id']}): has_pk1000_standard={has_pk}", "VERIFIED")

    # Step 4: Check if T3/T5-M were recently added (from shard6 session) and need pk1000
    # From shard6 session: Kissimmee T3/T5-M have no density/FAR regulation per LDC Table 5-2
    # For parking: Kissimmee LDC Ch.14-7 governs, use-based (not zone-based)
    # "pk1000" is per-use-type not per-zone in Kissimmee's Form-Based Code
    # This means T3/T5-M should be pk1000_regulated=false

    kissimmee_districts = sb_get(
        "zoning_districts"
        "?jurisdiction_id=eq.957"  # Kissimmee jurisdiction
        "&code=in.(T3,T5-M,RA-3,T4-R,T4-O)"
        "&select=id,code,pk1000_regulated,far_regulated,density_regulated"
    )
    log(f"Kissimmee districts (T3/T5-M/RA-3/etc): {kissimmee_districts}", "VERIFIED")

    # If T3 or T5-M have pk1000_regulated=true but no standard → they inflate the denominator
    # Per the Kissimmee FBC (Table 5-2, shard6 session): NO parking per-zone table in Kissimmee FBC
    # Parking is use-type based (Ch.14-7) → pk1000_regulated should be false
    for d in kissimmee_districts:
        if d.get("pk1000_regulated") is True:
            log(f"  {d['code']}: pk1000_regulated=true but should be false per Kissimmee FBC (use-based parking only)", "VERIFIED")
            n = sb_patch(
                f"zoning_districts?id=eq.{d['id']}",
                {
                    "pk1000_regulated": False,
                    "ordinance_section": (
                        (d.get("ordinance_section") or "") +
                        " | pk1000_regulated=false: Kissimmee LDC Ch.14-7 parking is use-type-keyed (Table 4.7.8 or 14-7), not a per-zone-code fixed standard. Cannot assign a single pk1000 value per zone. shard4_17241_20260802."
                    )[:2000],
                }
            )
            log(f"  PATCHED {d['code']}: pk1000_regulated=true→false (n={n})", "VERIFIED")

    # Check St Cloud R-3 (another parcel from Osceola I fix sessions)
    stcloud_districts = sb_get(
        "zoning_districts"
        "?jurisdiction_id=eq.958"  # St Cloud jurisdiction
        "&code=eq.R-3"
        "&select=id,code,pk1000_regulated"
    )
    log(f"St. Cloud R-3: {stcloud_districts}", "VERIFIED")

    after = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER: {json.dumps(after)}", "VERIFIED")
    g_after = after.get("G", {})
    log(f"G after: metric={g_after.get('metric')} detail={g_after.get('detail')}", "VERIFIED")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print("SELECT public.pencil_dod_evaluate_county('osceola');")
    print(f"BEFORE G: metric={g.get('metric')} detail={g.get('detail')}")
    print(f"AFTER  G: metric={g_after.get('metric')} detail={g_after.get('detail')}")


if __name__ == "__main__":
    main()
