#!/usr/bin/env python3
"""Osceola I fix — incomplete property cards (shard-4 dispatch 41bd7ce3, 2026-08-02).

CONTEXT: Osceola I=75.9% (card_complete=104 of 137). The 33 incomplete cards
fall into these documented categories (per shard6 dispatch 091fb9f9 session
report, 2026-07-31):
  1. ~24 rows with placeholder addresses (no real geo/value yet)
  2. ~3 rows with OSC- synthetic IDs / PDFs that couldn't be resolved
  3. ~3 rows needing Kissimmee/St.Cloud jurisdiction reassignment + zoning
  4. ~3 rows from the 3rd-firing SRPUD parcel that was refuted on procedural grounds

This script:
1. Fetches all osceola multi_county_auctions missing card_complete fields
   (from v_zoning_gold_standard_card definition: address+geo+value+zone).
2. For each, tries:
   a. FL GIO Statewide Cadastral ArcGIS (PARCEL_ID lookup) for address/geo/value
   b. If parcel_id is truncated (~12 digits), tries RealAuction calendar AJAX
      disambiguation to get full parcel_id (same approach as shard5_osceola)
   c. Osceola County GIS for zone if parcel_id resolved
3. Writes only confirmed real data.

STOPPING CONDITION: If a row's parcel_id is OSC- prefix (synthetic),
cannot be resolved via FL GIO (wrong format), and has a placeholder address
(e.g. "Osceola County FL"), skip it — do not fabricate.

Usage:
    python3 scripts/shard4_17241_osceola_i_incomplete_cards_fix.py [--dry-run]
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
CO_NO = 59

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

FL_DOR_CADASTRAL = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
    "Florida_Statewide_Cadastral/FeatureServer/0/query"
)

OSCEOLA_GIS = (
    "https://gis.osceola.org/arcgis/rest/services/Property/"
    "Parcels/FeatureServer/0/query"
)

REALTAXDEED_AJAX = (
    "https://osceola.realtaxdeed.com/index.cfm"
)

OSCEOLA_JURIS_IDS = {
    "Kissimmee": 957,
    "St. Cloud": 958,
    "Osceola County": 1186,
    "Celebration": None,
    "Poinciana": None,
}


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def sb_get(path):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def sb_patch(path, body):
    if DRY_RUN:
        log(f"DRY-RUN PATCH {path}: {list(body.keys())}", "UNTESTED")
        return 1
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers=SB_HDR)
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read())
        return len(result) if isinstance(result, list) else 1


def sb_post(path, body):
    if DRY_RUN:
        log(f"DRY-RUN POST {path}: {list(body.keys())}", "UNTESTED")
        return [body]
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers=SB_HDR)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(params).encode(), method="POST",
        headers={k: v for k, v in SB_HDR.items() if k != "Prefer"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def centroid_from_feature(feat):
    xs, ys = [], []
    for ring in (feat.get("geometry") or {}).get("rings", []):
        for pt in ring:
            xs.append(pt[0])
            ys.append(pt[1])
    if not xs:
        return None, None
    return sum(ys) / len(ys), sum(xs) / len(xs)


def fetch_fl_gio_by_parcel_id(parcel_id: str):
    """Exact PARCEL_ID match in FL GIO."""
    params = {
        "where": f"PARCEL_ID='{parcel_id}' AND CO_NO={CO_NO}",
        "outFields": "PARCEL_ID,CO_NO,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,AV_SD",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
    }
    url = FL_DOR_CADASTRAL + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        return data.get("features", [])
    except Exception as e:
        log(f"FL GIO query failed for {parcel_id}: {e}", "INFERRED")
    return []


def fetch_fl_gio_by_prefix(prefix: str):
    """PARCEL_ID LIKE prefix% match for truncated parcel IDs."""
    clean = prefix.replace("-", "").replace(".", "")
    params = {
        "where": f"PARCEL_ID LIKE '{clean}%' AND CO_NO={CO_NO}",
        "outFields": "PARCEL_ID,CO_NO,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,AV_SD",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
    }
    url = FL_DOR_CADASTRAL + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=45) as r:
            data = json.loads(r.read())
        return data.get("features", [])
    except Exception as e:
        log(f"FL GIO prefix query failed for {prefix}: {e}", "INFERRED")
    return []


def get_zone_for_parcel(parcel_id: str):
    """Query Osceola GIS for zone code of a parcel."""
    params = {
        "where": f"PARCELNO='{parcel_id}'",
        "outFields": "PARCELNO,ZONING,MUNICIPALITY",
        "returnGeometry": "false",
        "f": "json",
    }
    url = OSCEOLA_GIS + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        feats = data.get("features", [])
        if feats:
            return feats[0]["attributes"]
    except Exception as e:
        log(f"Osceola GIS zone query failed for {parcel_id}: {e}", "INFERRED")
    return None


def get_parcel_zone_row(parcel_id: str):
    """Check if parcel_zones already has a row for this parcel."""
    rows = sb_get(
        f"parcel_zones?parcel_id=eq.{urllib.parse.quote(parcel_id)}"
        f"&select=id,zone_code,jurisdiction_id"
    )
    return rows[0] if rows else None


def get_district_by_code(jur_id: int, code: str):
    rows = sb_get(
        f"zoning_districts?jurisdiction_id=eq.{jur_id}"
        f"&code=eq.{urllib.parse.quote(code)}&select=id,name"
    )
    return rows[0] if rows else None


def is_placeholder_address(addr: str | None) -> bool:
    """True if the address is a placeholder, not a real property address."""
    if not addr:
        return True
    a = addr.strip().lower()
    placeholder_patterns = [
        "osceola county fl",
        "osceola county, fl",
        "florida",
        "fl fl",
        "kissimmee fl",
        "saint cloud fl",
    ]
    for p in placeholder_patterns:
        if a == p or a.startswith(p + " ") or a.endswith(" " + p):
            return True
    if len(a) < 10:
        return True
    # Real addresses have a number first
    parts = a.split()
    if parts and not parts[0][0].isdigit():
        return True
    return False


def build_address(attrs: dict) -> str | None:
    addr1 = (attrs.get("PHY_ADDR1") or "").strip()
    city = (attrs.get("PHY_CITY") or "").strip()
    zipcd = attrs.get("PHY_ZIPCD")
    if addr1 and city:
        if zipcd:
            return f"{addr1}, {city}, FL {int(zipcd)}"
        return f"{addr1}, {city}, FL"
    return None


def main():
    log("=== OSCEOLA I FIX — incomplete cards (shard4 dispatch 41bd7ce3, 2026-08-02) ===")

    baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE: {json.dumps(baseline)}", "VERIFIED")
    i_before = baseline.get("I", {})
    log(f"I: metric={i_before.get('metric')} detail={i_before.get('detail')}", "VERIFIED")

    # Fetch all osceola auctions
    all_rows = sb_get(
        "multi_county_auctions"
        "?county=eq.osceola"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        "assessed_value,market_value,auction_status"
        "&order=created_at.asc"
    )
    log(f"Total osceola auctions fetched: {len(all_rows)}", "VERIFIED")

    # Find gaps: missing lat/lon, assessed_value, market_value, or no parcel_zones
    existing_zones = sb_get("parcel_zones?select=parcel_id")
    zoned_pids = {r["parcel_id"] for r in existing_zones if r.get("parcel_id")}

    gap_rows = [
        r for r in all_rows
        if (
            r.get("latitude") is None or
            r.get("longitude") is None or
            r.get("assessed_value") is None or
            r.get("market_value") is None or
            (r.get("parcel_id") and r["parcel_id"] not in zoned_pids)
        )
    ]
    log(f"Rows with card gaps: {len(gap_rows)}", "VERIFIED")

    patched_geo = 0
    patched_zone = 0
    skipped = 0

    for row in gap_rows:
        pid = row.get("parcel_id") or ""
        addr = row.get("property_address") or ""
        case = row.get("case_number", "?")

        # Skip synthetic OSC- prefixed IDs — no real GIS match
        if pid.startswith("OSC-"):
            log(f"  {case}: synthetic parcel_id {pid} — SKIP (no write)", "VERIFIED")
            skipped += 1
            continue

        # Skip rows without parcel_id and placeholder address
        if not pid and is_placeholder_address(addr):
            log(f"  {case}: no parcel_id + placeholder addr '{addr[:40]}' — SKIP", "VERIFIED")
            skipped += 1
            continue

        log(f"  Processing {case} parcel={pid[:20]} addr={addr[:40]}", "UNTESTED")

        fl_feats = []
        resolved_pid = pid

        if pid and len(pid) >= 15:
            # Try exact match first
            fl_feats = fetch_fl_gio_by_parcel_id(pid)
            if not fl_feats:
                # Try without dashes
                clean_pid = pid.replace("-", "").replace(".", "")
                fl_feats = fetch_fl_gio_by_parcel_id(clean_pid)
                if fl_feats:
                    resolved_pid = clean_pid
        elif pid and 8 <= len(pid) < 15:
            # Truncated prefix — query with LIKE
            fl_feats = fetch_fl_gio_by_prefix(pid)
            if len(fl_feats) == 1:
                # Exactly one match — safe to use
                resolved_pid = fl_feats[0]["attributes"]["PARCEL_ID"]
                log(f"  {case}: prefix {pid} resolved to {resolved_pid}", "VERIFIED")
            elif len(fl_feats) > 1:
                log(f"  {case}: prefix {pid} matched {len(fl_feats)} parcels — ambiguous, SKIP", "VERIFIED")
                skipped += 1
                continue

        if not fl_feats:
            log(f"  {case}: no FL GIO match for {pid} — SKIP", "VERIFIED")
            skipped += 1
            continue

        feat = fl_feats[0]
        attrs = feat["attributes"]
        lat, lon = centroid_from_feature(feat)
        built_addr = build_address(attrs)
        jv = attrs.get("JV")
        av_sd = attrs.get("AV_SD")

        # Validate: FL GIO parcel must be in CO_NO=59 (Osceola)
        if attrs.get("CO_NO") != CO_NO:
            log(f"  {case}: FL GIO returned CO_NO={attrs.get('CO_NO')}, not 59 — SKIP", "VERIFIED")
            skipped += 1
            continue

        patch_body: dict = {}
        if row.get("latitude") is None and lat is not None:
            patch_body["latitude"] = lat
        if row.get("longitude") is None and lon is not None:
            patch_body["longitude"] = lon
        if row.get("assessed_value") is None and av_sd:
            patch_body["assessed_value"] = av_sd
        if row.get("market_value") is None and jv:
            patch_body["market_value"] = jv
        if is_placeholder_address(addr) and built_addr and not is_placeholder_address(built_addr):
            patch_body["property_address"] = built_addr

        if patch_body:
            n = sb_patch(f"multi_county_auctions?id=eq.{row['id']}&county=eq.osceola", patch_body)
            if n:
                patched_geo += 1
                log(f"  {case}: PATCHED {list(patch_body.keys())} (resolved_pid={resolved_pid})", "VERIFIED")
        else:
            log(f"  {case}: all geo/value fields already populated", "VERIFIED")

        # Zone assignment if missing
        if pid and pid not in zoned_pids and resolved_pid:
            gis_zone = get_zone_for_parcel(resolved_pid)
            if gis_zone:
                zone_code = gis_zone.get("ZONING", "")
                muni = gis_zone.get("MUNICIPALITY", "")
                log(f"  {case}: Osceola GIS zone={zone_code} muni={muni}", "VERIFIED")

                if not zone_code:
                    log(f"  {case}: no zone returned — SKIP zone", "VERIFIED")
                    continue

                # Determine jurisdiction
                jur_id = None
                if muni and "kissimmee" in muni.lower():
                    jur_id = 957
                elif muni and ("cloud" in muni.lower() or "st. cloud" in muni.lower()):
                    jur_id = 958
                elif not muni or "unincorporated" in muni.lower() or muni.strip() == "":
                    jur_id = 1186
                else:
                    # Try lookup
                    jur_rows = sb_get(
                        f"jurisdictions?county_name=eq.Osceola"
                        f"&name=ilike.%25{urllib.parse.quote(muni[:12])}%25&select=id,name"
                    )
                    if jur_rows:
                        jur_id = jur_rows[0]["id"]
                        log(f"  {case}: jurisdiction found: {jur_rows[0]['name']} ({jur_id})", "VERIFIED")

                if not jur_id:
                    log(f"  {case}: cannot determine jurisdiction for muni={muni} — SKIP zone", "VERIFIED")
                    continue

                dist = get_district_by_code(jur_id, zone_code)
                if not dist:
                    log(f"  {case}: zone {zone_code} not in DB for jur {jur_id} — SKIP zone (no fabrication)", "VERIFIED")
                    continue

                pz_body = {
                    "parcel_id": pid,
                    "jurisdiction_id": jur_id,
                    "zone_code": zone_code,
                    "zone_name": dist["name"],
                    "source": f"shard4_17241_20260802:osceola_gis_zone_assignment",
                }
                try:
                    sb_post("parcel_zones", pz_body)
                    zoned_pids.add(pid)
                    patched_zone += 1
                    log(f"  {case}: INSERTED parcel_zones zone={zone_code} jur={jur_id}", "VERIFIED")
                except Exception as e:
                    log(f"  {case}: parcel_zones insert failed: {e}", "INFERRED")
            else:
                log(f"  {case}: Osceola GIS no zone for {resolved_pid} — SKIP zone", "VERIFIED")

        time.sleep(0.15)

    log(f"Summary: patched_geo={patched_geo}, patched_zone={patched_zone}, skipped={skipped}", "VERIFIED")

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE — no writes performed")
        return

    after = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER: {json.dumps(after)}", "VERIFIED")
    i_after = after.get("I", {})
    log(f"I after: metric={i_after.get('metric')} detail={i_after.get('detail')}", "VERIFIED")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print("SELECT public.pencil_dod_evaluate_county('osceola');")
    print(f"BEFORE I: {i_before.get('metric')} ({i_before.get('detail')})")
    print(f"AFTER  I: {i_after.get('metric')} ({i_after.get('detail')})")
    print(f"patched_geo={patched_geo} patched_zone={patched_zone} skipped={skipped}")


if __name__ == "__main__":
    main()
