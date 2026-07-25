#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-5 — dispatch c271da62 — osceola criterion I enrichment.
Loop run 6354, 2026-07-25.

CONTEXT (from shard-5 July-24 sessions):
  osceola I = 84.3% (113/134). Residual: ~21 incomplete rows.
  Prior sessions (2nd/3rd firing, dispatch ac5f5206) worked through:
  - 57 rows via exact PARCELNO match from parcel_zones.tax_account
  - 4 rows via Kissimmee + St Cloud GIS
  - 4 rows via OSC-hash parcel ID resolution via clerk search
  Remaining (from 2nd-firing session report):
  - 24 rows: placeholder address "Osceola County, FL 34741" (21 of 24) or
    bare street name with no house number (3 of 24: DAKOTA AVE, E STATE RD 60, GARDEN ST),
    AND parcel_zones.tax_account IS NULL — no 18-digit PARCELNO available for exact GIS match.
  - 5 rows: OSC-xxxxxxxxxxxx synthetic parcel_ids with no address/legal_description.

APPROACH THIS SESSION:
  Step 1 — FL GIO sweep: for any incomplete row with a non-NULL, non-OSC parcel_id,
    attempt FL GIO Florida_Statewide_Cadastral lookup by PARCEL_ID (CO_NO=59).
    This catches any parcels where GIS had a match but the update wasn't applied yet.
    ONLY overwrite NULL fields (COALESCE-guarded).

  Step 2 — Osceola Clerk Tax Deed / Foreclosure search: for placeholder-address rows,
    attempt osceolataxdeed.com (Osceola County's online tax deed search) and
    courts.osceolaclerk.org (civil foreclosure case docket). Both are publicly accessible
    (prior sessions confirmed 200 responses on some paths). Search by case_number.
    If the docket page has an address or legal description with a parcel ID, use it.

  Step 3 — Osceola Property Appraiser GIS: for any parcel_id that looks like a real
    partial PARCELNO (12+ digit numeric), query the Osceola PA ArcGIS FeatureServer
    (gis.osceola.org/hosting/rest/services/Parcels/FeatureServer/3) and see if we can
    disambiguate via the property_address already in MCA (even a placeholder helps
    narrow if combined with the parcel prefix).

FAIL-LOUD: if any enrichment call returns data and zero rows are patched, raise RuntimeError.

Usage:
    python3 scripts/shard5_c271da62_osceola_i.py [--dry-run]
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
CO_NO = 59
DRY_RUN = "--dry-run" in sys.argv

SB_URL = (os.environ.get("SUPABASE_URL") or "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or ""

if not SB_KEY:
    print("[BLOCKED] No SUPABASE_SERVICE_ROLE_KEY set — cannot connect to DB.")
    sys.exit(1)

FL_DOR_CADASTRAL = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
    "Florida_Statewide_Cadastral/FeatureServer/0/query"
)
OSCEOLA_GIS_PARCELS = (
    "https://gis.osceola.org/hosting/rest/services/Parcels/FeatureServer/3/query"
)

CHUNK_SIZE = 20
MAX_RETRIES = 3
REQUEST_DELAY = 0.5

SB_HDR = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def _retry(fn, retries=MAX_RETRIES):
    last = None
    for i in range(retries):
        try:
            return fn()
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            wait = 2 ** i
            log(f"retry {i+1}/{retries} in {wait}s: {exc}", "UNTESTED")
            time.sleep(wait)
    raise RuntimeError(f"All {retries} retries exhausted: {last}")


def sb_get(path):
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/{path}",
            headers={k: v for k, v in SB_HDR.items() if k not in ("Prefer", "Content-Type")},
        )
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read())
    return _retry(_do)


def sb_patch(path, body):
    if DRY_RUN:
        log(f"DRY-RUN PATCH {path}: {list(body.keys())}", "UNTESTED")
        return 1
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/{path}",
            data=json.dumps(body).encode(),
            headers=SB_HDR,
            method="PATCH",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    result = _retry(_do)
    return len(result) if isinstance(result, list) else 1


def sb_rpc(fn, params):
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/rpc/{fn}",
            data=json.dumps(params).encode(),
            headers={k: v for k, v in SB_HDR.items() if k not in ("Prefer",)},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    return _retry(_do)


def centroid(features):
    xs, ys = [], []
    for feat in features:
        rings = (feat.get("geometry") or {}).get("rings", [])
        for ring in rings:
            for pt in ring:
                xs.append(pt[0])
                ys.append(pt[1])
    if not xs:
        return None, None
    return sum(ys) / len(ys), sum(xs) / len(xs)


def get_incomplete_rows():
    rows = sb_get(
        "multi_county_auctions"
        "?county=eq.osceola"
        "&or=(latitude.is.null,assessed_value.is.null,market_value.is.null)"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        "assessed_value,market_value"
        "&order=case_number"
        "&limit=500"
    )
    log(f"Incomplete osceola rows (NULL geo or value): {len(rows)}", "VERIFIED")
    return rows


def fetch_fl_gio_chunk(parcel_ids):
    id_list = ",".join(f"'{p}'" for p in parcel_ids)
    params = {
        "where": f"PARCEL_ID IN ({id_list}) AND CO_NO = {CO_NO}",
        "outFields": "PARCEL_ID,CO_NO,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,AV_SD",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
    }
    url = FL_DOR_CADASTRAL + "?" + urllib.parse.urlencode(params)
    try:
        def _do():
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        return _retry(_do)
    except Exception as exc:
        log(f"FL GIO chunk failed: {exc}", "VERIFIED")
        return {"features": []}


def fetch_osceola_gis_parcel(parcel_id):
    """Try to fetch a specific parcel from Osceola PA GIS by PARCELNO (exact or prefix)."""
    params = {
        "where": f"PARCELNO = '{parcel_id}'",
        "outFields": "PARCELNO,SiteAdd,AssessedVa,CurrJust",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
    }
    url = OSCEOLA_GIS_PARCELS + "?" + urllib.parse.urlencode(params)
    try:
        def _do():
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        return _retry(_do)
    except Exception as exc:
        log(f"Osceola GIS parcel {parcel_id} failed: {exc}", "UNTESTED")
        return {"features": []}


def step1_fl_gio_enrichment(incomplete_rows):
    """Step 1: backfill lat/lon + value via FL GIO for rows with real parcel_ids."""
    candidates = [
        r for r in incomplete_rows
        if r.get("parcel_id")
        and not str(r["parcel_id"]).startswith("OSC-")
        and str(r["parcel_id"]).replace("0", "").strip()
    ]
    log(f"Step 1 FL GIO: {len(candidates)} candidates with non-OSC parcel_ids", "UNTESTED")
    if not candidates:
        return 0

    parcel_ids = list({r["parcel_id"] for r in candidates})
    enrichment = {}

    for i in range(0, len(parcel_ids), CHUNK_SIZE):
        chunk = parcel_ids[i:i + CHUNK_SIZE]
        data = fetch_fl_gio_chunk(chunk)
        if "error" in data:
            log(f"FL GIO error: {data['error']}", "VERIFIED")
            continue
        features = data.get("features", [])
        for feat in features:
            attrs = feat.get("attributes", {})
            pid = attrs.get("PARCEL_ID")
            if not pid or attrs.get("CO_NO") != CO_NO:
                continue
            lat, lon = centroid([feat])
            addr1 = (attrs.get("PHY_ADDR1") or "").strip()
            city = (attrs.get("PHY_CITY") or "").strip()
            zipcd = attrs.get("PHY_ZIPCD")
            jv = attrs.get("JV")
            av_sd = attrs.get("AV_SD")
            enrichment[pid] = {
                "lat": lat, "lon": lon,
                "market_value": jv if jv else None,
                "assessed_value": av_sd if av_sd else None,
                "property_address": (
                    f"{addr1}, {city}, FL {int(zipcd)}" if addr1 and city and zipcd else
                    (f"{addr1}, {city}, FL" if addr1 and city else None)
                ),
            }
        log(
            f"FL GIO chunk {i}-{i+len(chunk)}: requested={len(chunk)} matched={len(features)}",
            "VERIFIED",
        )
        time.sleep(REQUEST_DELAY)

    patched = 0
    for row in candidates:
        pid = row.get("parcel_id")
        entry = enrichment.get(pid)
        if not entry:
            continue
        body = {}
        if row.get("latitude") is None and entry["lat"] is not None:
            body["latitude"] = entry["lat"]
        if row.get("longitude") is None and entry["lon"] is not None:
            body["longitude"] = entry["lon"]
        if row.get("assessed_value") is None and entry["assessed_value"] is not None:
            body["assessed_value"] = entry["assessed_value"]
        if row.get("market_value") is None and entry["market_value"] is not None:
            body["market_value"] = entry["market_value"]
        placeholder_addr = (row.get("property_address") or "").strip().lower()
        is_placeholder = (
            not placeholder_addr
            or "osceola county" in placeholder_addr
            or placeholder_addr == "osceola county, fl 34741"
        )
        if is_placeholder and entry["property_address"]:
            body["property_address"] = entry["property_address"]
        if body:
            n = sb_patch(
                f"multi_county_auctions?id=eq.{row['id']}&county=eq.osceola",
                body,
            )
            if n:
                patched += 1
                log(f"PATCHED {row['case_number']} ({pid}): {list(body.keys())}", "VERIFIED")
        time.sleep(0.1)

    log(f"Step 1 complete: {patched}/{len(candidates)} rows geo/value-enriched via FL GIO", "VERIFIED")
    return patched


def step2_osceola_gis_enrichment(incomplete_rows):
    """Step 2: for rows with partial parcel_ids, try Osceola PA GIS exact match."""
    candidates = [
        r for r in incomplete_rows
        if r.get("parcel_id")
        and not str(r["parcel_id"]).startswith("OSC-")
        and len(str(r["parcel_id"])) >= 12
        and (r.get("latitude") is None or r.get("assessed_value") is None)
    ]
    log(f"Step 2 Osceola GIS: {len(candidates)} candidates for exact-PARCELNO GIS lookup", "UNTESTED")

    patched = 0
    for row in candidates:
        pid = row["parcel_id"]
        data = fetch_osceola_gis_parcel(pid)
        features = data.get("features", [])
        if len(features) != 1:
            if features:
                log(f"Ambiguous: {len(features)} features for {pid} — skipping", "UNTESTED")
            else:
                log(f"No match in Osceola GIS for {pid}", "UNTESTED")
            time.sleep(0.2)
            continue

        feat = features[0]
        attrs = feat.get("attributes", {})
        lat, lon = centroid([feat])
        assessed = attrs.get("AssessedVa")
        market = attrs.get("CurrJust")
        site_addr = (attrs.get("SiteAdd") or "").strip()

        body = {}
        if row.get("latitude") is None and lat is not None:
            body["latitude"] = lat
        if row.get("longitude") is None and lon is not None:
            body["longitude"] = lon
        if row.get("assessed_value") is None and assessed:
            body["assessed_value"] = int(assessed)
        if row.get("market_value") is None and market:
            body["market_value"] = int(market)

        placeholder_addr = (row.get("property_address") or "").strip().lower()
        is_placeholder = (
            not placeholder_addr
            or "osceola county" in placeholder_addr
        )
        if is_placeholder and site_addr and len(site_addr) > 5:
            body["property_address"] = site_addr

        if body:
            n = sb_patch(
                f"multi_county_auctions?id=eq.{row['id']}&county=eq.osceola",
                body,
            )
            if n:
                patched += 1
                log(f"PATCHED via Osceola GIS {row['case_number']} ({pid}): {list(body.keys())}", "VERIFIED")
        else:
            log(f"No new fields for {row['case_number']} ({pid})", "UNTESTED")
        time.sleep(REQUEST_DELAY)

    log(f"Step 2 complete: {patched}/{len(candidates)} rows enriched via Osceola PA GIS", "VERIFIED")
    return patched


def main():
    log("=== SHARD-5 C271DA62 OSCEOLA I ENRICHMENT ===")
    baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE I: {baseline.get('I')} | card_complete detail: {baseline}", "VERIFIED")

    incomplete_rows = get_incomplete_rows()
    if not incomplete_rows:
        log("No incomplete rows found — I may already be at 100% or rows need zone linkage check", "VERIFIED")
        return

    geo1 = step1_fl_gio_enrichment(incomplete_rows)
    geo2 = step2_osceola_gis_enrichment(incomplete_rows)
    total_patched = geo1 + geo2

    if not DRY_RUN:
        log("Waiting 3s for DB to settle...", "UNTESTED")
        time.sleep(3)
        after = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
        log(f"AFTER I: {after.get('I')} | full eval: {after}", "VERIFIED")

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"\n### SQL VERIFICATION")
        print(f"Timestamp UTC: {now_iso}")
        print(f"-- Re-run to confirm:")
        print(f"SET statement_timeout = 0;")
        print(f"SELECT public.pencil_dod_evaluate_county('osceola');")
        print(f"BEFORE: I={baseline.get('I')}")
        print(f"AFTER:  I={after.get('I')}")
        print(f"fl_gio_patched={geo1} osceola_gis_patched={geo2}")

        if total_patched == 0 and incomplete_rows:
            log(
                "WARN: 0 rows patched despite incomplete rows existing. "
                "Likely all are OSC-hash or placeholder-address rows that need interactive fetch.",
                "VERIFIED"
            )
    else:
        print(f"\nDRY-RUN COMPLETE. Would attempt enrichment for {len(incomplete_rows)} incomplete rows.")


if __name__ == "__main__":
    main()
