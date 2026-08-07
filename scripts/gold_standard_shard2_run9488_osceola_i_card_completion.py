#!/usr/bin/env python3
"""Osceola criterion I fix — property card completion for ~10 gap cases.

dispatch_id: 43f9840a-a414-44fc-83d8-380262928abe
loop_run: 9488
date: 2026-08-07

CONTEXT: Osceola I=92.7% (127/137). 10 rows are card-incomplete.

v_zoning_gold_standard_card requires ALL of:
  1. property_address populated
  2. latitude + longitude populated
  3. assessed_value OR market_value populated
  4. parcel_zones row with non-null zone_code for this parcel_id

From prior sessions (dispatch ac5f5206, 3rd firing 2026-07-24):
- 24 placeholder-address rows (addr = 'Address Not Available' or similar)
- 3 refuted-PDF-address OSC- rows (synthethic IDs)
- Several rows blocked by truncated parcel_ids that can't be disambiguated

APPROACH:
1. Query DB for osceola MCA rows that fail card_complete (identify which AND-condition fails)
2. For rows with address/geo/value but no zone_code: add parcel_zones via Osceola GIS
   ArcGIS endpoints (Kissimmee, St Cloud, Osceola County):
   - gis.osceola.org/FeatureServer/Zoning_Parcels (county, confirmed in prior sessions)
   - cw.kissimmee.gov Zoning_Districts/10 (Kissimmee, confirmed in prior sessions)
   - arcgisweb.stcloud.org Zoning/2 (St Cloud, confirmed in prior sessions)
3. For rows with parcel_id + zone but no geo/value: try FL GIO enrichment
4. SKIP: placeholder-address rows (address='Address Not Available') — cannot geocode without real address
5. SKIP: synthetic OSC- IDs — no parcel appraiser record

HONESTY MARKERS:
  - Zone assignments from GIS: UNTESTED until run
  - FL GIO enrichment: UNTESTED until run

CO_NO for Osceola: 59
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

COUNTY = "osceola"
DISPATCH_ID = "43f9840a-a414-44fc-83d8-380262928abe"
DRY_RUN = "--dry-run" in sys.argv

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
if not SB_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

SB_HDR = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}
SB_HDR_MERGE = {**SB_HDR, "Prefer": "resolution=merge-duplicates,return=representation"}

# Osceola County GIS endpoints (verified in prior sessions)
# Osceola County unincorporated zoning: gis.osceola.org Zoning_Parcels FeatureServer
OSCEOLA_GIS_BASE = "https://gisapps.osceola.org"
OSCEOLA_ZONING_URL = f"{OSCEOLA_GIS_BASE}/arcgis/rest/services/Public/Zoning/MapServer"
# Alternative: the Parcels FeatureServer
OSCEOLA_PARCEL_URL = "https://gis.osceola.org/arcgis/rest/services/Property/Parcels/FeatureServer"

# Kissimmee zoning (jurisdiction 1187 or city zoning service)
KISSIMMEE_ZONING_URL = "https://cw.kissimmee.gov/arcgis/rest/services/Zoning/Zoning_Districts/FeatureServer/10"

# St Cloud zoning (jurisdiction — St Cloud)
STCLOUD_ZONING_URL = "https://arcgisweb.stcloud.org/arcgis/rest/services/Zoning/MapServer/2"

# FL GIO statewide cadastral
FL_GIO_URL = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
    "Florida_Statewide_Cadastral/FeatureServer/0/query"
)
OSCEOLA_CO_NO = 59


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def sb_get(path, params=""):
    url = f"{SB_URL}/rest/v1/{path}{'?' + params if params else ''}"
    req = urllib.request.Request(url, headers=SB_HDR)
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read())


def sb_post(table, rows):
    if not rows:
        return 0
    if DRY_RUN:
        log(f"DRY-RUN POST {table}: {len(rows)} rows", "UNTESTED")
        return len(rows)
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}",
        data=json.dumps(rows).encode(),
        headers=SB_HDR_MERGE,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
            return len(result) if isinstance(result, list) else 1
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        log(f"POST {table} error {e.code}: {body}", "VERIFIED")
        return 0


def sb_patch(path, body_dict):
    if DRY_RUN:
        log(f"DRY-RUN PATCH {path}: {body_dict}", "UNTESTED")
        return 1
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        data=json.dumps(body_dict).encode(),
        headers=SB_HDR,
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
            return len(result) if isinstance(result, list) else 1
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        log(f"PATCH {path} error {e.code}: {body}", "VERIFIED")
        return 0


def sb_rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(params).encode(),
        method="POST",
        headers={k: v for k, v in SB_HDR.items() if k != "Prefer"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def centroid_from_rings(rings):
    xs, ys = [], []
    for ring in rings:
        for pt in ring:
            xs.append(pt[0])
            ys.append(pt[1])
    if not xs:
        return None, None
    return sum(ys) / len(ys), sum(xs) / len(xs)


def query_arcgis_pip(base_url, lat, lon, out_fields="*", timeout=45):
    """Point-in-polygon query against an ArcGIS layer using lat/lon."""
    geom = {"x": lon, "y": lat}
    params = {
        "geometry": json.dumps(geom),
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": out_fields,
        "returnGeometry": "false",
        "outSR": "4326",
        "f": "json",
        "where": "1=1",
        "inSR": "4326",
    }
    url = base_url + "/query?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"ArcGIS PIP error ({base_url}): {e}", "VERIFIED")
        return {}


def query_arcgis_by_id(base_url, where, out_fields="*", timeout=45):
    params = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = base_url + "/query?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"ArcGIS byID error ({base_url}): {e}", "VERIFIED")
        return {}


def fetch_fl_gio(parcel_id):
    """Try to get parcel from FL GIO by exact PARCEL_ID. Osceola CO_NO=59."""
    params = {
        "where": f"PARCEL_ID='{parcel_id}' AND CO_NO={OSCEOLA_CO_NO}",
        "outFields": "PARCEL_ID,CO_NO,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,AV_SD",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = FL_GIO_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"FL GIO error for {parcel_id}: {e}", "VERIFIED")
        return {}


def get_osceola_jurisdictions():
    rows = sb_get("jurisdictions", "county=eq.Osceola&state=eq.FL&limit=50")
    return {r["name"]: r["id"] for r in rows}


def look_up_zone_for_parcel(lat, lon, parcel_id):
    """Try all 3 Osceola GIS sources for the zone code. Returns (zone_code, jurisdiction_name, source)."""
    # 1. Osceola County unincorporated
    result = query_arcgis_pip(OSCEOLA_ZONING_URL, lat, lon, out_fields="ZONE_CODE,ZONE_TYPE,DISTRICT")
    feats = result.get("features", [])
    if feats:
        attrs = feats[0].get("attributes", {})
        zc = attrs.get("ZONE_CODE") or attrs.get("ZONE_TYPE") or attrs.get("DISTRICT")
        if zc:
            return zc.strip(), "Unincorporated Osceola County", f"osceola_gis_zoning_pip:shard2_run9488"
    time.sleep(0.2)

    # 2. Kissimmee
    result = query_arcgis_pip(KISSIMMEE_ZONING_URL, lat, lon, out_fields="ZONE,ZONE_NAME,ZONE_CATEGORY")
    feats = result.get("features", [])
    if feats:
        attrs = feats[0].get("attributes", {})
        zc = attrs.get("ZONE") or attrs.get("ZONE_NAME")
        if zc:
            return zc.strip(), "Kissimmee", f"kissimmee_gis_zoning_pip:shard2_run9488"
    time.sleep(0.2)

    # 3. St Cloud
    result = query_arcgis_pip(STCLOUD_ZONING_URL, lat, lon, out_fields="ZONING,ZONE_NAME")
    feats = result.get("features", [])
    if feats:
        attrs = feats[0].get("attributes", {})
        zc = attrs.get("ZONING") or attrs.get("ZONE_NAME")
        if zc:
            return zc.strip(), "Saint Cloud", f"stcloud_gis_zoning_pip:shard2_run9488"
    time.sleep(0.2)

    return None, None, None


PLACEHOLDER_ADDRS = {
    "address not available", "not available", "n/a", "", "unknown", "null",
    "property address not available", "no address", "tbd"
}


def is_placeholder_address(addr):
    if addr is None:
        return True
    return addr.strip().lower() in PLACEHOLDER_ADDRS


def main():
    log("=" * 60)
    log(f"Osceola I — property card completion (dispatch {DISPATCH_ID})")
    log(f"DRY_RUN={DRY_RUN}")

    # Baseline
    try:
        baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
        log(f"BASELINE: {json.dumps(baseline)}", "VERIFIED")
        i_letter = baseline.get("I", {})
        log(f"BASELINE I: pass={i_letter.get('pass')} metric={i_letter.get('metric')} detail={i_letter.get('detail')}", "VERIFIED")
    except Exception as e:
        log(f"Baseline RPC error: {e}", "VERIFIED")
        baseline = {}

    # Get all osceola MCA rows
    mca_rows = sb_get(
        "multi_county_auctions",
        "county=eq.osceola&select=id,case_number,parcel_id,property_address,latitude,longitude,assessed_value,market_value&limit=300"
    )
    log(f"Total osceola MCA rows: {len(mca_rows)}", "VERIFIED")

    # Get all osceola parcel_zones
    jurisdictions = get_osceola_jurisdictions()
    log(f"Osceola jurisdictions: {list(jurisdictions.keys())}", "VERIFIED")

    existing_pz = {}
    for jname, jid in jurisdictions.items():
        rows = sb_get("parcel_zones", f"jurisdiction_id=eq.{jid}&select=parcel_id,zone_code&limit=500")
        for r in rows:
            if r.get("parcel_id") and r.get("zone_code"):
                existing_pz[r["parcel_id"]] = {"zone_code": r["zone_code"], "jurisdiction": jname, "jid": jid}
    log(f"Existing parcel_zones for osceola: {len(existing_pz)}", "VERIFIED")

    # Classify each MCA row's card completeness
    gaps = []
    for row in mca_rows:
        pid = row.get("parcel_id")
        has_address = bool(row.get("property_address")) and not is_placeholder_address(row.get("property_address"))
        has_geo = row.get("latitude") is not None and row.get("longitude") is not None
        has_value = row.get("assessed_value") is not None or row.get("market_value") is not None

        # Check parcel_zones: exact match or prefix match (truncated parcel_ids)
        has_zone = False
        zone_code = None
        if pid:
            if pid in existing_pz:
                has_zone = True
                zone_code = existing_pz[pid]["zone_code"]
            else:
                # Check for prefix match (osceola uses truncated ~12-digit parcel_ids)
                for epid in existing_pz:
                    if epid and (pid.startswith(epid) or epid.startswith(pid)):
                        has_zone = True
                        zone_code = existing_pz[epid]["zone_code"]
                        break

        is_complete = has_address and has_geo and has_value and has_zone
        if not is_complete:
            missing = []
            if not has_address:
                missing.append("address")
            if not has_geo:
                missing.append("geo")
            if not has_value:
                missing.append("value")
            if not has_zone:
                missing.append("zone")
            gaps.append({
                "row": row,
                "missing": missing,
                "has_address": has_address,
                "has_geo": has_geo,
                "has_value": has_value,
                "has_zone": has_zone,
                "zone_code": zone_code,
            })

    log(f"\nCard-incomplete rows: {len(gaps)}", "VERIFIED")
    for g in gaps:
        row = g["row"]
        log(f"  {row['case_number']} pid={row.get('parcel_id','NULL')} missing={g['missing']}", "VERIFIED")

    if len(gaps) == 0:
        log("All cards complete — I should already be passing. Check evaluator.", "VERIFIED")
        return

    # Focus on rows where only zone is missing (most actionable via GIS)
    zone_only_gap = [g for g in gaps if g["missing"] == ["zone"]]
    zone_and_value = [g for g in gaps if "zone" in g["missing"] and g["has_address"] and g["has_geo"]]
    geo_value_gap = [g for g in gaps if not g["has_geo"] or not g["has_value"]]

    log(f"\nGap breakdown:", "VERIFIED")
    log(f"  Zone only (have address+geo+value): {len(zone_only_gap)}", "VERIFIED")
    log(f"  Zone + other (have address+geo): {len(zone_and_value)}", "VERIFIED")
    log(f"  Geo/value gap: {len(geo_value_gap)}", "VERIFIED")

    pz_to_insert = []
    mca_patches = {}
    skipped_placeholder = 0
    skipped_synthetic = 0

    # Priority 1: Fix zone-only gaps (have geo, can do PIP lookup)
    for g in gaps:
        row = g["row"]
        pid = row.get("parcel_id")
        case_num = row["case_number"]

        # Skip placeholder addresses — cannot verify these
        if is_placeholder_address(row.get("property_address")) and not g["has_geo"]:
            log(f"  SKIP {case_num}: placeholder address, no geo — cannot resolve", "VERIFIED")
            skipped_placeholder += 1
            continue

        # Skip synthetic OSC- IDs
        if pid and pid.upper().startswith("OSC-"):
            log(f"  SKIP {case_num}: synthetic OSC- parcel ID — cannot resolve", "VERIFIED")
            skipped_synthetic += 1
            continue

        # If missing geo/value but have parcel_id, try FL GIO
        lat = row.get("latitude")
        lon = row.get("longitude")
        patch = {}

        if (not g["has_geo"] or not g["has_value"]) and pid and not pid.upper().startswith("OSC-"):
            log(f"  FL GIO lookup for {case_num} pid={pid}...", "UNTESTED")
            gio = fetch_fl_gio(pid)
            features = gio.get("features", [])
            if features:
                feat = features[0]
                attrs = feat["attributes"]
                rings = (feat.get("geometry") or {}).get("rings", [])
                glat, glon = centroid_from_rings(rings)
                if glat and glon and not g["has_geo"]:
                    lat, lon = glat, glon
                    patch["latitude"] = lat
                    patch["longitude"] = lon
                    log(f"    FL GIO → lat={lat:.6f} lon={lon:.6f}", "VERIFIED")
                if not g["has_value"]:
                    if attrs.get("AV_SD"):
                        patch["assessed_value"] = attrs["AV_SD"]
                    if attrs.get("JV"):
                        patch["market_value"] = attrs["JV"]
                if not g["has_address"] and attrs.get("PHY_ADDR1"):
                    addr1 = attrs.get("PHY_ADDR1", "").strip()
                    city = attrs.get("PHY_CITY", "").strip()
                    zipcd = attrs.get("PHY_ZIPCD")
                    if addr1 and city:
                        addr = f"{addr1}, {city}, FL" + (f" {int(zipcd)}" if zipcd else "")
                        patch["property_address"] = addr
                if patch:
                    mca_patches[row["id"]] = patch
            else:
                log(f"    FL GIO: no features for {pid}", "VERIFIED")
            time.sleep(0.3)

        # Refresh lat/lon after potential FL GIO fetch
        if not lat:
            lat = row.get("latitude")
        if not lon:
            lon = row.get("longitude")

        # If still no geo, skip zone lookup (can't do PIP without coordinates)
        if not lat or not lon:
            log(f"  SKIP zone lookup for {case_num}: no lat/lon available", "VERIFIED")
            continue

        # Zone lookup via GIS
        if not g["has_zone"] and pid:
            log(f"  Zone PIP lookup for {case_num} lat={lat:.6f} lon={lon:.6f}...", "UNTESTED")
            zone_code, jurisdiction_name, source = look_up_zone_for_parcel(lat, lon, pid)
            if zone_code and jurisdiction_name:
                jid = jurisdictions.get(jurisdiction_name)
                if not jid:
                    # Try partial match
                    for jn, ji in jurisdictions.items():
                        if jurisdiction_name.lower() in jn.lower() or jn.lower() in jurisdiction_name.lower():
                            jid = ji
                            jurisdiction_name = jn
                            break
                if jid:
                    pz_to_insert.append({
                        "parcel_id": pid,
                        "jurisdiction_id": jid,
                        "zone_code": zone_code,
                        "zone_name": f"Osceola {zone_code} ({jurisdiction_name})",
                        "source": source,
                    })
                    log(f"    → zone={zone_code} jurisdiction={jurisdiction_name}", "VERIFIED")
                else:
                    log(f"    SKIP: jurisdiction '{jurisdiction_name}' not found in DB", "VERIFIED")
            else:
                log(f"    No zone found via GIS PIP for {case_num}", "VERIFIED")

    # Apply MCA patches
    if mca_patches:
        log(f"\nApplying {len(mca_patches)} MCA geo/value/address patches...", "UNTESTED")
        for mca_id, patch in mca_patches.items():
            n = sb_patch(f"multi_county_auctions?id=eq.{mca_id}&county=eq.osceola", patch)
            if n:
                log(f"  PATCHED mca id={mca_id}: {list(patch.keys())}", "VERIFIED")

    # Insert parcel_zones
    log(f"\nInserting {len(pz_to_insert)} parcel_zones rows...", "UNTESTED")
    inserted = 0
    for pz in pz_to_insert:
        n = sb_post("parcel_zones", [pz])
        if n:
            inserted += 1
            log(f"  INSERTED parcel_zones for {pz['parcel_id']}: zone={pz['zone_code']}", "VERIFIED")
        time.sleep(0.1)

    log(f"\n  parcel_zones inserted: {inserted}/{len(pz_to_insert)}", "VERIFIED")
    log(f"  MCA patches: {len(mca_patches)}", "VERIFIED")
    log(f"  Skipped (placeholder address): {skipped_placeholder}", "VERIFIED")
    log(f"  Skipped (synthetic ID): {skipped_synthetic}", "VERIFIED")

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE — no writes performed")
        return

    # Post-fix evaluation
    try:
        after = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
        log(f"\nAFTER: {json.dumps(after)}", "VERIFIED")
        i_after = after.get("I", {})
        log(f"AFTER I: pass={i_after.get('pass')} metric={i_after.get('metric')} detail={i_after.get('detail')}", "VERIFIED")
    except Exception as e:
        log(f"After RPC error: {e}", "VERIFIED")
        after = {}

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print("SELECT public.pencil_dod_evaluate_county('osceola');")
    print(f"BEFORE I: {baseline.get('I', {})}")
    print(f"AFTER  I: {after.get('I', {})}")
    print(f"gap_rows_found={len(gaps)}")
    print(f"parcel_zones_inserted={inserted}")
    print(f"mca_patches={len(mca_patches)}")


if __name__ == "__main__":
    main()
