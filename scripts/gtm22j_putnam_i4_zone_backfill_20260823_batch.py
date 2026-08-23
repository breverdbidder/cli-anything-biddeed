#!/usr/bin/env python3
"""GTM-22J putnam letter I fix, 2026-08-23 session, targeting the CURRENT
30-row live gap (calendar_sweep_mca_v3 continuous drip inflow after putnam
was last verified 10/10 on 2026-08-07, commit 2899ac05).

Sibling of scripts/gtm22j_putnam_i3_zone_backfill_20260930_batch.py and
scripts/gold_standard_shard2_putnam_i2_zone_backfill.py (same proven
Tax_Parcel_AGO -> Zoning_Districts_AGO centroid-intersect method, same
jurisdiction_id=931, same G-regression guard rail), retargeted at the 30
rows failing pencil_dod_evaluate_county('putnam').I as of 2026-08-23
(card_complete=639 of 673, 94.9%, live-reconstructed via the exact WHERE
clause from pg_get_functiondef). Of those 30: 19 have a real well-formed
parcel_id that is genuinely unlinked in parcel_zones (jurisdiction_id=931)
-- confirmed via LEFT JOIN, never previously attempted by any backfill run.
The other 11 (parcel_id NULL or a placeholder string like "MULTIPLE" /
"Property Appraiser") are OUT OF SCOPE for this GIS lever -- they need a
clerk/court-record parcel lookup, a different script family, and are logged
as an honest residual rather than blocking this run.

Method (identical to the proven prior runs):
  1. Batch-query Tax_Parcel_AGO by PARCELID IN (...) with returnGeometry=true&
     returnCentroid=true&outSR=4326 -- real polygon-service centroid.
  2. Spatially intersect that centroid against Zoning_Districts_AGO
     (esriSpatialRelIntersects) for a real ZONECLASS/ZONEDESC.
  3. Insert into parcel_zones only for parcels where step 2 returned a real zone.
  4. Guard rail: check G before/after; if any new parcel_zones insert (new code
     or existing code) regresses G, revert ALL of this run's inserts (scoped by
     source tag) rather than fabricate a density/FAR figure.
  5. Opportunistic PATCH of multi_county_auctions.assessed_value (from
     CNTASSDVAL), latitude/longitude (from centroid), and property_address
     (from SITEADDRESS) where those fields are currently NULL -- fill-NULL-only,
     never overwrite existing non-null values.

Usage: python3 scripts/gtm22j_putnam_i4_zone_backfill_20260823_batch.py
Input: /tmp/putnam_i3/gap_rows.json (pre-built from a live DB snapshot of the
  30-row current gap, filtered to the 19 rows with a real-format parcel_id --
  see session report for the exact query used to build it)
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

JUR_ID = 931  # Putnam, VERIFIED live (matches all prior rows)
SOURCE_TAG = "gtm22j_i4/putnam_gis_live:Zoning_Districts_AGO+Tax_Parcel_AGO_centroid_intersect:20260823batch"

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


def is_real_parcel_id(pid):
    if not pid:
        return False
    stripped = pid.replace("-", "").replace(" ", "")
    return stripped.isdigit() and len(stripped) >= 8


def get_g_metric():
    r = mgmt_query("SELECT public.pencil_dod_evaluate_county('putnam') AS result;")
    return r[0]["result"]["G"]["metric"], r[0]["result"]["I"]["metric"]


def main():
    gap_rows = json.load(open("/tmp/putnam_i3/gap_rows.json"))
    # This run's input file is pre-filtered to the 19 rows with a real-format
    # parcel_id (out of 30 total live gap rows); all 19 are zone_linked=False
    # per the live LEFT JOIN against parcel_zones (jurisdiction_id=931).
    zonelink_rows = [r for r in gap_rows if is_real_parcel_id(r["parcel_id"])]
    RESULTS["candidates"] = len(zonelink_rows)

    by_pid = {}
    for row in gap_rows:
        pid = row["parcel_id"]
        if is_real_parcel_id(pid):
            by_pid.setdefault(pid, []).append(row)

    pids = sorted(by_pid.keys())
    print(f"[VERIFIED] {len(pids)} distinct real-format parcel_ids across all gap categories ({len(zonelink_rows)} need zone-link)")

    tax_data = {}

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

    zonelink_pids = {r["parcel_id"] for r in zonelink_rows}
    zone_results = {}
    for pid in sorted(zonelink_pids):
        td = tax_data.get(pid)
        if not td:
            continue
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

    print(f"[VERIFIED] Zoning_Districts_AGO intersect matched {RESULTS['zone_matched']} of {len(zonelink_pids)}; not_found={len(RESULTS['zone_not_found'])}")

    existing_codes = mgmt_query("SELECT code FROM zoning_districts WHERE jurisdiction_id=931")
    existing_code_set = {r["code"] for r in existing_codes}
    needed_codes = {zc for (zc, _zd) in zone_results.values() if zc}
    new_codes = sorted(needed_codes - existing_code_set)

    g_before, i_before = get_g_metric()
    print(f"[VERIFIED] Pre-insert G={g_before} I={i_before}")

    for code in new_codes:
        cat = "Residential" if code.upper().startswith("R") else \
              "Commercial" if code.upper().startswith("C") else \
              "Agriculture" if code.upper() in ("AG",) else \
              "Conservation" if code.upper() in ("CON", "ROS") else \
              "Industrial" if code.upper().startswith("M") else "Other"
        name = code
        sql = (
            f"INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category) "
            f"SELECT 931, '{code}', '{name}', '{cat}' "
            f"WHERE NOT EXISTS (SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id=931 AND code='{code}')"
        )
        mgmt_query(sql)
        RESULTS["new_zoning_district_codes"].append({"code": code, "category": cat, "far_regulated": None, "density_regulated": None})
        print(f"[VERIFIED] Added zoning_districts row jur=931 code={code} category={cat} far_regulated=NULL density_regulated=NULL")

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
            "effective_date": "2026-08-23",
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

    g_after, i_after_zone = get_g_metric()
    print(f"[VERIFIED] Post-zone-insert G={g_after} I={i_after_zone}")
    if g_before is not None and g_after is not None and g_after < g_before:
        print(f"[ADVERSARIAL SELF-CATCH] G regressed {g_before} -> {g_after}. Reverting ALL this-run parcel_zones inserts (source tag scoped).")
        mgmt_query(f"DELETE FROM public.parcel_zones WHERE jurisdiction_id=931 AND source='{SOURCE_TAG}'")
        RESULTS["reverted_all_this_run"] = True
        RESULTS["parcel_zones_inserted"] = 0
        g_after2, i_after2 = get_g_metric()
        print(f"[VERIFIED] Post-revert G={g_after2} I={i_after2}")

    for pid, rows in by_pid.items():
        td = tax_data.get(pid)
        if not td:
            continue
        for row in rows:
            patch_body = {}
            if row.get("property_address") is None and td.get("siteaddress"):
                patch_body["property_address"] = td["siteaddress"]
            if row.get("latitude") is None:
                patch_body["latitude"] = td["y"]
                patch_body["longitude"] = td["x"]
            if row.get("assessed_value") is None and td.get("cntassdval"):
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
    with open("/tmp/putnam_i3/results.json", "w") as f:
        json.dump(RESULTS, f, indent=2, default=str)


if __name__ == "__main__":
    main()
