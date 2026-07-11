#!/usr/bin/env python3
"""GOLD STANDARD shard-2, county=putnam, dispatch d9229958, run3786 -- letter I fix.

Baseline (VERIFIED live via pencil_dod_evaluate_county this session):
  I: card_complete=228 of 450 = 50.7% FAIL
  G: density=99.2 PASS (must not regress)

Root cause (VERIFIED, exact replica of pencil_dod_evaluate_county's live SQL via
pg_get_functiondef): card_complete requires property_address + geo (lat/lon) +
value (assessed/market) + parcel_id present in v_zoning_gold_standard_card WHERE
zone_code IS NOT NULL. Breakdown this session:
  missing_addr=5, missing_geo=212, missing_val=212, missing_parcel_id=8,
  missing_zone_link=214 (parcel_id NOT NULL, not present in parcel_zones w/ zone_code
  for jurisdiction 931) -- the dominant blocker, matching the dispatch's diagnosis.

Of the 214 zone-link-missing rows, 213 have a real-format parcel_id
(digits+hyphens, >=8 chars stripped) and 1 has a scraper-artifact literal
'Property Appraiser' (not a parcel_id at all -- left untouched, not fabricated).

Sibling precedent (commit 946df428, same dispatch lineage, a few hours earlier):
fixed 8 putnam parcels via the identical Tax_Parcel_AGO + Zoning_Districts_AGO
centroid-intersect method, at a time when auctions_total was 239 (now 450 -- many
new rows added since). That run found 2 parcels with genuinely zero zoning-polygon
coverage at their location (37-10-26-6850-3390-0070, 42-10-27-6850-2850-1600) --
re-confirmed live again this session (bbox + exact-point + JSON-geometry query
variants all return zero features for both).

Method (VERIFIED live this session):
  1. Batch-query Tax_Parcel_AGO by PARCELID IN (...) (up to 50/batch, advancedQueryCapabilities
     confirmed live) with returnGeometry=true&returnCentroid=true&outSR=4326 -- gives a
     real polygon-service centroid (not a manual ring average).
  2. For each matched parcel, spatially query Zoning_Districts_AGO with the centroid point,
     esriSpatialRelIntersects, outSR=4326 -- gives real ZONECLASS/ZONEDESC.
  3. Insert into parcel_zones only for parcels where step 2 returned a real zone. Parcels
     with zero Tax_Parcel_AGO match, or zero Zoning_Districts_AGO intersect, are residual
     -- reported, never fabricated.
  4. Guard rail: before inserting any new zone_code not already in zoning_districts for
     jurisdiction_id=931, insert a zoning_districts row first with far_regulated=NULL and
     density_regulated=NULL (matches every existing sibling code's convention -- confirmed
     live: all 26 existing jurisdiction_id=931 codes have density_regulated=NULL, and only
     AP-1/DB/DR/HD have far_regulated=true, everything else NULL). This is the exact guard
     rail that a prior session (946df428) discovered was necessary after a G regression.
  5. Opportunistic PATCH of multi_county_auctions.property_address/assessed_value (from
     SITEADDRESS/CNTASSDVAL) and latitude/longitude (from the same centroid) where those
     fields are currently NULL on our row -- idempotent, fill-NULL-only, never overwrite.

Usage: python3 scripts/gold_standard_shard2_putnam_run3786_i_zone_backfill.py
"""
import os
import sys
import json
import time
import urllib.request
import urllib.parse
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
MGMT_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]

TAX_PARCEL_LAYER = "https://services1.arcgis.com/YZc1OyqL6jbIOeOv/arcgis/rest/services/Tax_Parcel_AGO/FeatureServer/0/query"
ZONING_LAYER = "https://services1.arcgis.com/YZc1OyqL6jbIOeOv/arcgis/rest/services/Zoning_Districts_AGO/FeatureServer/0/query"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

JUR_ID = 931  # Putnam, VERIFIED live this session (all 229 pre-existing rows use this)
SOURCE_TAG = "shard2_run3786/putnam_gis_live:Zoning_Districts_AGO+Tax_Parcel_AGO_centroid_intersect"

BATCH_SIZE = 50

RESULTS = {
    "candidates": 0,
    "skipped_bad_parcel_id": [],
    "tax_parcel_matched": 0,
    "tax_parcel_not_found": [],
    "zone_matched": 0,
    "zone_not_found": [],
    "new_zoning_district_codes": [],
    "parcel_zones_inserted": 0,
    "parcel_zones_errors": [],
    "mca_addr_patched": 0,
    "mca_geo_patched": 0,
    "mca_value_patched": 0,
    "mca_patch_errors": [],
}


def mgmt_query(sql):
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": sql}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {MGMT_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) supabase-cli/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=100) as r:
        body = r.read()
        return json.loads(body) if body.strip() else []


def rest_patch(table, filter_qs, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}?{filter_qs}",
        data=json.dumps(body).encode(),
        method="PATCH",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def rest_post(table, body, prefer="return=minimal"):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()[:800]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:800]


def arcgis_query(url, params):
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def norm_parcel(pid):
    return pid.strip()


def is_real_parcel_id(pid):
    if not pid:
        return False
    stripped = pid.replace("-", "").replace(" ", "")
    return stripped.isdigit() and len(stripped) >= 8


def main():
    gap_rows = json.load(open("/tmp/putnam_fix/gap_rows.json"))
    RESULTS["candidates"] = len(gap_rows)
    by_pid = {}
    for row in gap_rows:
        pid = row["parcel_id"]
        if not is_real_parcel_id(pid):
            RESULTS["skipped_bad_parcel_id"].append({"id": row["id"], "case_number": row["case_number"], "parcel_id": pid})
            continue
        by_pid.setdefault(pid, []).append(row)

    pids = list(by_pid.keys())
    print(f"[VERIFIED] {len(pids)} distinct real-format parcel_ids to process ({RESULTS['candidates']} candidate rows, {len(RESULTS['skipped_bad_parcel_id'])} skipped bad-format)")

    tax_data = {}  # pid -> {siteaddress, cntassdval, lndvalue, centroid_x, centroid_y}

    for i in range(0, len(pids), BATCH_SIZE):
        batch = pids[i:i + BATCH_SIZE]
        where_list = ",".join("'" + p.replace("'", "''") + "'" for p in batch)
        where = f"PARCELID IN ({where_list})"
        try:
            data = arcgis_query(TAX_PARCEL_LAYER, {
                "where": where,
                "outFields": "PARCELID,SITEADDRESS,CNTASSDVAL,LNDVALUE",
                "returnGeometry": "true",
                "returnCentroid": "true",
                "outSR": "4326",
                "f": "json",
            })
        except Exception as e:
            print(f"[ERROR] Tax_Parcel_AGO batch {i}: {e}", file=sys.stderr)
            for p in batch:
                RESULTS["tax_parcel_not_found"].append({"parcel_id": p, "reason": f"batch_query_error:{e}"})
            continue

        feats = data.get("features", [])
        found_pids = set()
        for f in feats:
            attrs = f["attributes"]
            pid = attrs.get("PARCELID")
            centroid = f.get("centroid")
            if not centroid:
                continue
            found_pids.add(pid)
            tax_data[pid] = {
                "siteaddress": attrs.get("SITEADDRESS"),
                "cntassdval": attrs.get("CNTASSDVAL"),
                "lndvalue": attrs.get("LNDVALUE"),
                "x": centroid["x"],
                "y": centroid["y"],
            }
        for p in batch:
            if p not in found_pids:
                RESULTS["tax_parcel_not_found"].append({"parcel_id": p, "reason": "no_tax_parcel_match"})
        RESULTS["tax_parcel_matched"] += len(found_pids)
        time.sleep(0.2)

    print(f"[VERIFIED] Tax_Parcel_AGO matched {RESULTS['tax_parcel_matched']} of {len(pids)}; not_found={len(RESULTS['tax_parcel_not_found'])}")

    # Step 2: zoning intersect per matched parcel (point queries; ArcGIS REST does not
    # support a batched multi-point spatial intersect in one call, so this is per-parcel).
    zone_results = {}  # pid -> (zone_code, zone_desc)
    for pid, td in tax_data.items():
        try:
            zdata = arcgis_query(ZONING_LAYER, {
                "geometry": f"{td['x']},{td['y']}",
                "geometryType": "esriGeometryPoint",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "ZONECLASS,ZONEDESC",
                "outSR": "4326",
                "returnGeometry": "false",
                "f": "json",
            })
        except Exception as e:
            RESULTS["zone_not_found"].append({"parcel_id": pid, "reason": f"query_error:{e}"})
            time.sleep(0.15)
            continue

        zfeats = zdata.get("features", [])
        if not zfeats:
            RESULTS["zone_not_found"].append({"parcel_id": pid, "reason": "no_zoning_polygon_at_centroid"})
        else:
            zattrs = zfeats[0]["attributes"]
            zone_results[pid] = (zattrs.get("ZONECLASS"), zattrs.get("ZONEDESC"))
            RESULTS["zone_matched"] += 1
        time.sleep(0.15)

    print(f"[VERIFIED] Zoning_Districts_AGO intersect matched {RESULTS['zone_matched']} of {len(tax_data)}; not_found={len(RESULTS['zone_not_found'])}")

    # Step 3: guard-rail -- ensure every new zone_code exists in zoning_districts for jur 931
    existing_codes = mgmt_query("SELECT code FROM zoning_districts WHERE jurisdiction_id=931")
    existing_code_set = {r["code"] for r in existing_codes}
    needed_codes = {zc for (zc, _zd) in zone_results.values() if zc}
    new_codes = sorted(needed_codes - existing_code_set)

    for code in new_codes:
        # Category inference matched to existing sibling naming, NULL-flags convention
        cat = "Residential" if code.upper().startswith("R") else \
              "Commercial" if code.upper().startswith("C") else \
              "Agriculture" if code.upper() in ("AG",) else \
              "Conservation" if code.upper() in ("CON", "ROS") else \
              "Industrial" if code.upper().startswith("M") else "Other"
        name = code  # honest: no invented descriptive name beyond the code itself
        sql = (
            f"INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category) "
            f"SELECT 931, '{code}', '{name}', '{cat}' "
            f"WHERE NOT EXISTS (SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id=931 AND code='{code}')"
        )
        mgmt_query(sql)
        RESULTS["new_zoning_district_codes"].append({"code": code, "category": cat, "far_regulated": None, "density_regulated": None})
        print(f"[VERIFIED] Added zoning_districts row jur=931 code={code} category={cat} far_regulated=NULL density_regulated=NULL")

    # Step 4: batch-insert parcel_zones rows for all zone-matched parcels
    pz_rows = []
    for pid, (zc, zd) in zone_results.items():
        if not zc:
            continue
        pz_rows.append({
            "parcel_id": pid,
            "tax_account": pid,
            "jurisdiction_id": JUR_ID,
            "zone_code": zc,
            "zone_name": zd or zc,
            "source": SOURCE_TAG,
            "effective_date": "2026-07-11",
        })

    if pz_rows:
        for i in range(0, len(pz_rows), 100):
            chunk = pz_rows[i:i + 100]
            status, resp = rest_post("parcel_zones", chunk, prefer="resolution=merge-duplicates,return=minimal")
            if status in (200, 201, 204):
                RESULTS["parcel_zones_inserted"] += len(chunk)
            else:
                RESULTS["parcel_zones_errors"].append({"chunk_start": i, "status": status, "msg": resp})

    print(f"[VERIFIED] parcel_zones inserted={RESULTS['parcel_zones_inserted']} (attempted={len(pz_rows)}) errors={len(RESULTS['parcel_zones_errors'])}")

    # Step 5: opportunistic PATCH of multi_county_auctions NULL fields only
    for pid, rows in by_pid.items():
        td = tax_data.get(pid)
        if not td:
            continue
        for row in rows:
            patch_body = {}
            if row.get("property_address") is None and td.get("siteaddress"):
                patch_body["property_address"] = td["siteaddress"]
            if row.get("latitude") is None and row.get("po_latitude") is None:
                patch_body["latitude"] = td["y"]
                patch_body["longitude"] = td["x"]
            if row.get("assessed_value") is None and row.get("market_value") is None and td.get("cntassdval"):
                patch_body["assessed_value"] = td["cntassdval"]

            if not patch_body:
                continue
            status, msg = rest_patch("multi_county_auctions", f"id=eq.{row['id']}", patch_body)
            if status in (200, 204):
                if "property_address" in patch_body:
                    RESULTS["mca_addr_patched"] += 1
                if "latitude" in patch_body:
                    RESULTS["mca_geo_patched"] += 1
                if "assessed_value" in patch_body:
                    RESULTS["mca_value_patched"] += 1
            else:
                RESULTS["mca_patch_errors"].append({"id": row["id"], "parcel_id": pid, "status": status, "msg": msg})

    print(json.dumps(RESULTS, indent=2, default=str))
    with open("/tmp/putnam_fix/results.json", "w") as f:
        json.dump(RESULTS, f, indent=2, default=str)


if __name__ == "__main__":
    main()
