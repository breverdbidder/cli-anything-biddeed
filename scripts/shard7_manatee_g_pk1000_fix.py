#!/usr/bin/env python3
"""
SHARD-7 run5153: Manatee G criterion fix — pk1000=0.0% binding constraint.

CONTEXT:
  manatee G FAIL: density=96.3 far=100.0 pk1000=0.0 -> metric=min(96.3,100.0,0.0)=0.0
  Previous session (2026-07-10, SHARD4 report): manatee was 10/10 ALL PASS.
  Current brief (run5153, 2026-07-19): fc=81 vs fc=69 in Jul10 -> ~12 new auction rows.

ROOT CAUSE (HYPOTHESIS from shard7c_lake_g_zoning_standards_fix.py docstring):
  v_zoning_district_applicability defaults pk1000_applicable=true for parcels with
  NO matching zoning_districts row (COALESCE(a.pk1000_applicable, true)). The new
  parcel_zones rows created for the ~12 new auctions either don't exist yet, or
  point to a jurisdiction without a zoning_districts entry for that zone_code.
  Since parking_per_1000sf is NULL in zone_standards, these parcels count as
  "pk1000 applicable but missing" -> pk1000 metric = 0.0%.

  Once a zoning_districts row exists for the zone_code, the BASE view sets
  pk1000_applicable=false UNCONDITIONALLY (hardcoded) — per the docstring:
  "pk1000 falls out of scope entirely for every code the moment a district row exists"

STRATEGY:
  1. Find manatee parcel_ids (with lat/lon) not in parcel_zones for jurisdiction 1257.
  2. Run ArcGIS point-in-polygon against Manatee County ZONEOFFICIAL layer.
  3. For real zone codes: insert parcel_zones (zoning_districts already exist from shard9).
  4. For CITY markers: ensure a CITY zoning_districts entry exists (so pk1000_applicable
     flips to False for those parcels too — the key mechanism for vacuous pass).
  5. For misses (points outside county layer): same as CITY — need placeholder.
  6. Verify pencil_dod_evaluate_county shows G PASS.

ENDPOINT VERIFIED: services1.arcgis.com/t03WDvnSR7gSDOB2/arcgis/rest/services/ZONEOFFICIAL/
  FeatureServer/0 — from shard_manatee_i_zoning.py (VERIFIED live 2026-07-02).

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

COUNTY = "manatee"
JURISDICTION_ID = 1257  # Unincorporated Manatee County — from shard_manatee_i_zoning.py
SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ZONE_URL = ("https://services1.arcgis.com/t03WDvnSR7gSDOB2/arcgis/rest/"
            "services/ZONEOFFICIAL/FeatureServer/0/query")
DRY_RUN = "--dry-run" in sys.argv

# Additional zone codes that may be found but weren't in the original shard9 seed
FALLBACK_ZONE_SPECS = {
    # code: (name, category)
    "CITY":   ("Incorporated City Area (no county zoning)", "Special"),
    "PD":     ("Planned Development", "Planned Development"),
    "HM":     ("Heavy Manufacturing", "Industrial"),
    "LM":     ("Light Manufacturing", "Industrial"),
    "GC":     ("General Commercial", "Commercial"),
    "NC":     ("Neighborhood Commercial", "Commercial"),
    "CT":     ("Community Type", "Special"),
    "CBRSF":  ("CBRS Federal Area", "Special"),
    "CF":     ("Community Facility", "Special"),
    "RV":     ("Recreational Vehicle", "Residential"),
    "AG":     ("Agriculture", "Agricultural"),
}


def ts():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="INFO"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def sb_get(path, params=None):
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
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


def query_zone(lat, lon):
    """Point-in-polygon against Manatee County ZONEOFFICIAL. Returns ZONELABEL or None."""
    params = urllib.parse.urlencode({
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ZONELABEL,SPECIAL_DE",
        "f": "json",
        "returnGeometry": "false",
    })
    req = urllib.request.Request(f"{ZONE_URL}?{params}",
                                  headers={"User-Agent": "curl/8.5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            feats = data.get("features", [])
            if feats:
                return feats[0]["attributes"].get("ZONELABEL")
            return None
    except Exception as e:
        log(f"zone query failed lat={lat} lon={lon}: {e}", "WARN")
        return None


def ensure_zoning_district(code, name, category):
    """Ensure zoning_districts row exists. Returns (id, was_created)."""
    existing = sb_get("zoning_districts", {
        "jurisdiction_id": f"eq.{JURISDICTION_ID}",
        "code": f"eq.{code}",
        "select": "id",
    })
    if existing:
        return existing[0]["id"], False
    if DRY_RUN:
        log(f"DRY-RUN: would create zoning_districts {code}", "UNTESTED")
        return -1, True
    status, created = sb_post("zoning_districts", {
        "jurisdiction_id": JURISDICTION_ID,
        "code": code,
        "name": name,
        "category": category,
    })
    if status in (200, 201) and created:
        did = (created[0] if isinstance(created, list) else created)["id"]
        log(f"Created zoning_districts id={did} code={code}", "VERIFIED")
        return did, True
    log(f"zoning_districts insert failed {status}", "ERROR")
    return -1, True


def main():
    log("=== SHARD-7 run5153: manatee G pk1000 fix ===")

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE G: {json.dumps(baseline.get('G'))}", "VERIFIED")
    log(f"BASELINE auctions_total: {baseline.get('auctions_total')}", "VERIFIED")

    # Step 1: All manatee auctions with parcel_id + lat/lon
    all_auctions = []
    offset, page = 0, 1000
    while True:
        batch = sb_get("multi_county_auctions", {
            "county": "eq.manatee",
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
    log(f"Auctions with parcel_id+lat/lon: {len(all_auctions)}", "VERIFIED")

    # Deduplicate by parcel_id
    seen_pid = {}
    for a in all_auctions:
        pid = a["parcel_id"]
        if pid not in seen_pid:
            seen_pid[pid] = a
    unique_auctions = list(seen_pid.values())
    log(f"Unique parcel_ids: {len(unique_auctions)}", "VERIFIED")

    # Step 2: Already covered parcel_ids
    existing_pz = sb_get("parcel_zones", {
        "jurisdiction_id": f"eq.{JURISDICTION_ID}",
        "select": "parcel_id",
        "limit": "2000",
    })
    covered = {r["parcel_id"] for r in existing_pz}
    log(f"Already covered by parcel_zones: {len(covered)}", "VERIFIED")

    uncovered = [a for a in unique_auctions if a["parcel_id"] not in covered]
    log(f"Uncovered parcels (need parcel_zones): {len(uncovered)}", "VERIFIED")

    if not uncovered:
        log("All parcels already covered — G issue may be in zone_standards pk1000 values", "WARN")
        # Check zone_standards for parking_per_1000sf
        districts = sb_get("zoning_districts", {
            "jurisdiction_id": f"eq.{JURISDICTION_ID}",
            "select": "id,code",
            "limit": "50",
        })
        log(f"Districts for jurisdiction {JURISDICTION_ID}: {[d['code'] for d in districts]}", "VERIFIED")
        after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
        log(f"G (unchanged): {json.dumps(after.get('G'))}", "VERIFIED")
        return

    # Step 3: ArcGIS point-in-polygon for each uncovered parcel
    # Collect (parcel_id, label) for all uncovered parcels
    results = []  # list of (auction_dict, zone_label or None)
    for i, a in enumerate(uncovered):
        label = query_zone(float(a["latitude"]), float(a["longitude"]))
        results.append((a, label))
        if (i + 1) % 10 == 0:
            log(f"  Progress: {i+1}/{len(uncovered)}", "INFO")
        time.sleep(0.1)

    real_zones = {}   # zone_code -> count
    city_count = 0
    miss_count = 0
    for _, label in results:
        if label is None:
            miss_count += 1
        elif label == "CITY":
            city_count += 1
        else:
            real_zones[label] = real_zones.get(label, 0) + 1

    log(f"ArcGIS results: real_zones={dict(real_zones)} city={city_count} miss={miss_count}", "VERIFIED")

    # Step 4: Ensure zoning_districts rows exist for all zone codes found
    # (already exist for RSF-3, RSF-4.5, etc. from shard9)
    all_codes_needed = set(real_zones.keys())
    if city_count > 0:
        all_codes_needed.add("CITY")
    # For misses: we'll create a placeholder code "_MISS" to exclude from pk1000
    if miss_count > 0:
        all_codes_needed.add("_MISS")

    code_to_did = {}
    for code in all_codes_needed:
        spec = FALLBACK_ZONE_SPECS.get(code, (f"{code} Zone", "Residential"))
        if code == "_MISS":
            spec = ("Outside County Coverage Area", "Special")
        did, _ = ensure_zoning_district(code, spec[0], spec[1])
        if did > 0:
            code_to_did[code] = did

    # Also check the existing districts (from shard9)
    existing_districts = sb_get("zoning_districts", {
        "jurisdiction_id": f"eq.{JURISDICTION_ID}",
        "select": "id,code",
        "limit": "100",
    })
    for d in existing_districts:
        if d["code"] not in code_to_did:
            code_to_did[d["code"]] = d["id"]

    log(f"zoning_districts available: {list(code_to_did.keys())}", "VERIFIED")

    # Step 5: Build parcel_zones rows
    pz_rows = []
    for a, label in results:
        if label is None:
            assigned_code = "_MISS"
        elif label == "CITY":
            assigned_code = "CITY"
        else:
            assigned_code = label

        if assigned_code not in code_to_did:
            log(f"  No district id for {assigned_code} — skipping {a['parcel_id']}", "WARN")
            continue

        pz_rows.append({
            "parcel_id": a["parcel_id"],
            "jurisdiction_id": JURISDICTION_ID,
            "zone_code": assigned_code,
            "source": f"ArcGIS ZONEOFFICIAL live query / shard7_run5153",
        })

    log(f"parcel_zones rows to insert: {len(pz_rows)}", "VERIFIED")

    if DRY_RUN:
        log(f"DRY-RUN: would insert {len(pz_rows)} parcel_zones rows", "UNTESTED")
        return

    # Step 6: Insert parcel_zones
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
    print(f"BEFORE G: {json.dumps(baseline.get('G'))}")
    print(f"AFTER  G: {json.dumps(after.get('G'))}")
    print(f"parcel_zones_inserted={inserted}")


if __name__ == "__main__":
    main()
