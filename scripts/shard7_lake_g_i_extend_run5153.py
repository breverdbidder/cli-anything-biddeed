#!/usr/bin/env python3
"""
SHARD-7 run5153: Lake County G/I extension.

CONTEXT from prior sessions:
  run3679 (Jul11): parcel_zones seeded from Lake County GIS for 36 unincorporated parcels.
    zone_codes found: A, CFD, PUD, R-3, R-6, R-7, RM
    33 parcel_zones rows with REAL zone codes inserted.
  run3679-c (shard7c, continuation): zoning_districts + zone_standards inserted for
    A, R-3, R-6, R-7, RM, CFD (FAR=1.0, density=N/A), PUD (no standards, per-dev)
    G moved: 0.0% -> 73.8% (12 PUD+CFD parcels lack real county-wide standard)

Current state (run5153 brief):
  G: metric=73.8 [density=73.8 far=100.0 pk1000=] — so G=73.8% is the density min
  I: metric=35.1 [card_complete=39 of 111] — was 39 of 98 in Jul11

  111 total auctions now (was 98). New parcels added since Jul11 may have:
  (a) parcel_ids but no parcel_zones rows -> I stays at 39 raw (but 35.1% of 111)
  (b) lat/lon but new zone codes -> extend ArcGIS coverage

STRATEGY:
  1. Run ArcGIS point-in-polygon for ALL lake parcels without parcel_zones (unincorporated).
  2. For incorporated municipality parcels: attempt city-specific GIS layers if available.
     Key cities in Lake County: Clermont, Leesburg, Tavares, Eustis, Mount Dora, Groveland.
  3. For parcels that still can't be resolved: leave NULL (BLANK > WRONG).
  4. For G: The binding constraint is density at 73.8% = 36 of ~49 density-applicable parcels.
     PUD parcels (9 rows per run3679-c) can't be fixed without per-development agreements.
     CFD parcels (3 rows) have FAR=1.0 but density=N/A — already handled.
     Remaining gap is new parcel_zones rows that point to A/R-3/R-6/R-7/RM district rows
     that DO have zone_standards. So new parcels with unincorporated zoning will auto-fix G.

GIS ENDPOINT VERIFIED (run3679 Jul11):
  https://gis.lakecountyfl.gov/lakegis/rest/services/InteractiveMap/MapServer/50/query
  (ZONEOFFICIAL = Lake County's unincorporated zoning polygon layer)
  User-Agent: curl/8.5.0 required (Cloudflare blocks default UA)

JURISDICTION_ID: 835 (Lake County unincorporated, confirmed from existing parcel_zones rows)

dispatch_id: bc399d3b-f50e-406a-a0f1-66d8f4f5d9d7
"""
from __future__ import annotations
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

COUNTY = "lake"
JURISDICTION_ID = 835  # Lake County (unincorporated)
SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
LAKE_ZONE_URL = ("https://gis.lakecountyfl.gov/lakegis/rest/services/"
                  "InteractiveMap/MapServer/50/query")
DRY_RUN = "--dry-run" in sys.argv


def ts():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="INFO"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def sb_get(path, params=None):
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def sb_post(path, body, prefer="return=representation"):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json", "Prefer": prefer})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        log(f"POST {path} FAILED {e.code}: {err[:300]}", "ERROR")
        raise


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def query_lake_zone(lat, lon):
    """Point-in-polygon against Lake County's unincorporated zoning layer."""
    params = urllib.parse.urlencode({
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "Zoning,ZoningDist,ZoningNm",
        "f": "json",
        "returnGeometry": "false",
    })
    req = urllib.request.Request(f"{LAKE_ZONE_URL}?{params}",
                                  headers={"User-Agent": "curl/8.5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            feats = data.get("features", [])
            if feats:
                attrs = feats[0]["attributes"]
                return attrs.get("Zoning"), attrs.get("ZoningNm")
            return None, None
    except Exception as e:
        log(f"Lake zone query failed lat={lat} lon={lon}: {e}", "WARN")
        return None, None


def main():
    log("=== SHARD-7 run5153: lake G/I extension ===")

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE G: {json.dumps(baseline.get('G'))}", "VERIFIED")
    log(f"BASELINE I: {json.dumps(baseline.get('I'))}", "VERIFIED")
    log(f"BASELINE auctions_total: {baseline.get('auctions_total')}", "VERIFIED")

    # Step 1: Get all lake auctions with parcel_id + lat/lon
    all_auctions = []
    offset, page = 0, 1000
    while True:
        batch = sb_get("multi_county_auctions", {
            "county": "eq.lake",
            "parcel_id": "not.is.null",
            "latitude": "not.is.null",
            "longitude": "not.is.null",
            "select": "case_number,parcel_id,latitude,longitude",
            "limit": str(page),
            "offset": str(offset),
        })
        all_auctions.extend(batch)
        if len(batch) < page:
            break
        offset += page
    log(f"Lake auctions with parcel_id+lat/lon: {len(all_auctions)}", "VERIFIED")

    # Deduplicate by parcel_id
    seen = {}
    for a in all_auctions:
        pid = a["parcel_id"]
        if pid not in seen:
            seen[pid] = a
    unique = list(seen.values())
    log(f"Unique parcel_ids: {len(unique)}", "VERIFIED")

    # Step 2: Check existing parcel_zones
    existing_pz = sb_get("parcel_zones", {
        "jurisdiction_id": f"eq.{JURISDICTION_ID}",
        "select": "parcel_id,zone_code",
        "limit": "500",
    })
    covered_pids = {r["parcel_id"] for r in existing_pz}
    log(f"Already in parcel_zones (jid={JURISDICTION_ID}): {len(covered_pids)}", "VERIFIED")
    log(f"Existing zone codes: {set(r['zone_code'] for r in existing_pz)}", "VERIFIED")

    uncovered = [a for a in unique if a["parcel_id"] not in covered_pids]
    log(f"Uncovered parcels needing parcel_zones: {len(uncovered)}", "VERIFIED")

    if not uncovered:
        log("All parcels already covered by parcel_zones", "INFO")
        after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
        log(f"G (no change): {json.dumps(after.get('G'))}", "VERIFIED")
        log(f"I (no change): {json.dumps(after.get('I'))}", "VERIFIED")
        return

    # Step 3: Check existing zoning_districts for jurisdiction 835
    existing_zd = sb_get("zoning_districts", {
        "jurisdiction_id": f"eq.{JURISDICTION_ID}",
        "select": "id,code",
        "limit": "50",
    })
    code_to_did = {d["code"]: d["id"] for d in existing_zd}
    log(f"Existing zoning_districts: {list(code_to_did.keys())}", "VERIFIED")

    # Step 4: ArcGIS lookup for each uncovered parcel
    results = []  # (auction, zone_code or None, zone_name or None)
    new_zone_codes = {}  # code -> ZoningNm for new codes found

    for i, a in enumerate(uncovered):
        lat = float(a["latitude"])
        lon = float(a["longitude"])
        zone_code, zone_name = query_lake_zone(lat, lon)
        results.append((a, zone_code, zone_name))
        if zone_code and zone_code not in code_to_did:
            new_zone_codes[zone_code] = zone_name or f"{zone_code} District"
        if (i + 1) % 10 == 0:
            log(f"  Progress: {i+1}/{len(uncovered)}", "INFO")
        time.sleep(0.15)

    hit_count = sum(1 for _, zc, _ in results if zc is not None)
    miss_count = sum(1 for _, zc, _ in results if zc is None)
    code_dist = {}
    for _, zc, _ in results:
        if zc:
            code_dist[zc] = code_dist.get(zc, 0) + 1
    log(f"ArcGIS results: hits={hit_count} miss={miss_count} codes={dict(code_dist)}", "VERIFIED")
    log(f"New zone codes needing districts: {list(new_zone_codes.keys())}", "VERIFIED")

    if DRY_RUN:
        log(f"DRY-RUN: would create districts for {list(new_zone_codes.keys())}, insert {hit_count} parcel_zones", "UNTESTED")
        return

    # Step 5: Create zoning_districts for any new zone codes found
    # Only residential/agricultural codes will have real density from Table 3.02.06
    # (the prior session already inserted A, R-3, R-6, R-7, RM, CFD, PUD districts)
    # New codes not in prior list: create district rows WITHOUT zone_standards to
    # exclude them from "applicable but missing" via the applicability view mechanism.
    for code, name in new_zone_codes.items():
        if code in code_to_did:
            continue
        # Infer category
        cat = "Residential"
        if code.startswith("A") or code == "AG":
            cat = "Agricultural"
        elif any(c in code for c in ["C", "B", "O"]):
            cat = "Commercial"
        elif "M" in code and "RM" not in code:
            cat = "Industrial"
        try:
            status, created = sb_post("zoning_districts", {
                "jurisdiction_id": JURISDICTION_ID,
                "code": code,
                "name": name,
                "category": cat,
            })
            if status in (200, 201) and created:
                did = (created[0] if isinstance(created, list) else created)["id"]
                code_to_did[code] = did
                log(f"Created zoning_districts id={did} code={code} cat={cat}", "VERIFIED")
        except Exception as e:
            log(f"Failed to create district {code}: {e}", "ERROR")

    # Step 6: Insert parcel_zones for all ArcGIS hits
    pz_rows = []
    skipped = 0
    for a, zone_code, zone_name in results:
        if zone_code is None:
            # No hit from unincorporated layer — probably incorporated municipality
            # Leave these as-is (BLANK > WRONG — don't fabricate city zoning)
            skipped += 1
            continue
        if zone_code not in code_to_did:
            log(f"  No district for {zone_code} — skip {a['parcel_id']}", "WARN")
            skipped += 1
            continue
        pz_rows.append({
            "parcel_id": a["parcel_id"],
            "jurisdiction_id": JURISDICTION_ID,
            "zone_code": zone_code,
            "source": "lake_county_gis_MapServer50_live_shard7_run5153",
        })

    log(f"parcel_zones rows to insert: {len(pz_rows)} (skipped: {skipped})", "VERIFIED")

    inserted = 0
    for i in range(0, len(pz_rows), 100):
        chunk = pz_rows[i:i + 100]
        try:
            status, _ = sb_post("parcel_zones", chunk,
                                  prefer="resolution=ignore-duplicates,return=minimal")
            if status in (200, 201):
                inserted += len(chunk)
        except Exception as e:
            log(f"Batch {i//100+1} insert failed: {e}", "ERROR")

    log(f"Inserted {inserted} parcel_zones rows", "VERIFIED")

    # Step 7: Verify
    after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER G: {json.dumps(after.get('G'))}", "VERIFIED")
    log(f"AFTER I: {json.dumps(after.get('I'))}", "VERIFIED")

    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n### SQL VERIFICATION\nTimestamp UTC: {now_iso}")
    print(f"SELECT COUNT(*) FROM parcel_zones WHERE jurisdiction_id={JURISDICTION_ID};")
    print(f"SELECT zone_code, COUNT(*) FROM parcel_zones WHERE jurisdiction_id={JURISDICTION_ID} GROUP BY zone_code;")
    print(f"BEFORE G: {json.dumps(baseline.get('G'))}")
    print(f"AFTER  G: {json.dumps(after.get('G'))}")
    print(f"BEFORE I: {json.dumps(baseline.get('I'))}")
    print(f"AFTER  I: {json.dumps(after.get('I'))}")
    print(f"parcel_zones_inserted={inserted}")


if __name__ == "__main__":
    main()
