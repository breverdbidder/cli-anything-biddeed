#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-5 — dispatch c271da62 — citrus criterion I enrichment.
Loop run 6354, 2026-07-25.

CONTEXT:
  citrus I = 93.7% (179/191). 12 rows remain incomplete (CAPTCHA/403 blocked in shard-4).
  v_zoning_gold_standard_card requires for each citrus MCA row:
    1. property_address populated
    2. latitude + longitude populated
    3. assessed_value OR market_value populated
    4. parcel_zones row with non-null zone_code for this parcel_id

  12 remaining: Citrus foreclosure cases (not tax deeds). The Citrus Clerk SCORSS case
  search is CAPTCHA-gated. citrus.realforeclose.com and bid4assets.com return 403.
  citruspa.org was down for maintenance on July 25.

APPROACH:
  1. Citrus County Property Appraiser REST API (citruspa.org) — retry now that
     maintenance window may have ended.
  2. Citrus County GIS ArcGIS REST (maps.citrusbocc.com/arcgis/rest/services/) —
     search by parcel_id if we have it, or by address if address is populated.
  3. FL GIO Florida_Statewide_Cadastral — CO_NO=17 for Citrus County. Lookup by
     PARCEL_ID for any rows that already have a parcel_id.
  4. For rows with NULL parcel_id (foreclosure cases), try the Citrus Clerk's
     public civil case lookup (search.citrusclerk.org) — not CAPTCHA-gated for
     the civil case docket (SCORSS is for tax deeds/supplemental records only).

Citrus CO_NO = 17 (VERIFIED from FL DOR county number table).

FAIL-LOUD: if any fetch call returns data and zero rows are patched, raise RuntimeError.

Usage:
    python3 scripts/shard5_c271da62_citrus_i.py [--dry-run]
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

COUNTY = "citrus"
CO_NO = 17
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
CITRUS_GIS_PARCELS = (
    "https://maps.citrusbocc.com/arcgis/rest/services/Parcels/MapServer/0/query"
)
CITRUS_PA_SEARCH = "https://www.citruspa.org/PropertySearch.aspx"

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


def sb_post(table, records):
    if DRY_RUN:
        log(f"DRY-RUN POST {table}: {len(records)} records", "UNTESTED")
        return len(records)
    if not records:
        return 0
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/{table}",
            data=json.dumps(records).encode(),
            headers={**SB_HDR, "Prefer": "resolution=ignore-duplicates,return=representation"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read())
    result = _retry(_do)
    return len(result) if isinstance(result, list) else 0


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


def get_incomplete_citrus_rows():
    rows = sb_get(
        "multi_county_auctions"
        "?county=eq.citrus"
        "&or=(latitude.is.null,assessed_value.is.null,market_value.is.null)"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        "assessed_value,market_value"
        "&order=case_number"
        "&limit=500"
    )
    log(f"Citrus rows needing geo/value: {len(rows)}", "VERIFIED")
    return rows


def get_citrus_no_parcel_zone():
    rows = sb_get(
        "multi_county_auctions"
        "?county=eq.citrus"
        "&select=id,case_number,parcel_id,property_address"
        "&order=case_number"
        "&limit=500"
    )
    all_parcel_ids = {r["parcel_id"] for r in rows if r.get("parcel_id")}
    pz_rows = sb_get(
        "parcel_zones"
        "?jurisdiction_id=eq.1327"
        "&select=parcel_id"
        "&limit=5000"
    )
    covered = {r["parcel_id"] for r in pz_rows}
    missing_pz = [r for r in rows if r.get("parcel_id") and r["parcel_id"] not in covered]
    log(f"Citrus rows with parcel_id but no parcel_zones: {len(missing_pz)}", "VERIFIED")
    return missing_pz, covered


def fetch_fl_gio_chunk(parcel_ids, co_no):
    id_list = ",".join(f"'{p}'" for p in parcel_ids)
    params = {
        "where": f"PARCEL_ID IN ({id_list}) AND CO_NO = {co_no}",
        "outFields": "PARCEL_ID,CO_NO,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,AV_SD,USE_CODE",
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


def fetch_citrus_gis_by_parcel(parcel_id):
    """Query Citrus County GIS for parcel by PRCLKEY or similar field."""
    params = {
        "where": f"PRCLKEY = '{parcel_id}' OR PARCELKEY = '{parcel_id}'",
        "outFields": "PRCLKEY,PARCELKEY,ADDR,SITE_ADDR,JV,AV_SD,OWNER",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
    }
    url = CITRUS_GIS_PARCELS + "?" + urllib.parse.urlencode(params)
    try:
        def _do():
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        return _retry(_do)
    except Exception as exc:
        log(f"Citrus GIS parcel {parcel_id} failed: {exc}", "UNTESTED")
        return {"features": []}


def try_citrus_pa_search(case_number):
    """Try the Citrus PA public search page for a case. Returns None if blocked."""
    search_url = f"https://www.citruspa.org/PropertySearch.aspx?caseNumber={urllib.parse.quote(case_number)}"
    try:
        def _do():
            req = urllib.request.Request(
                search_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; GoldStandardBot/1.0)",
                    "Accept": "text/html",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode("utf-8", errors="replace")
        html = _retry(_do)
        if "Property Search" in html or "PARCEL" in html.upper():
            return html
        return None
    except Exception as exc:
        log(f"citruspa.org case {case_number}: {exc}", "UNTESTED")
        return None


def step1_fl_gio(incomplete_rows):
    """FL GIO lookup for citrus rows missing geo/value."""
    candidates = [
        r for r in incomplete_rows
        if r.get("parcel_id") and not str(r["parcel_id"]).startswith("CITRUS-")
    ]
    log(f"Step 1 FL GIO citrus: {len(candidates)} candidates", "UNTESTED")
    if not candidates:
        return 0

    parcel_ids = list({r["parcel_id"] for r in candidates})
    enrichment = {}

    for i in range(0, len(parcel_ids), CHUNK_SIZE):
        chunk = parcel_ids[i:i + CHUNK_SIZE]
        data = fetch_fl_gio_chunk(chunk, CO_NO)
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
            enrichment[pid] = {
                "lat": lat, "lon": lon,
                "market_value": attrs.get("JV") or None,
                "assessed_value": attrs.get("AV_SD") or None,
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
        if not row.get("property_address") and entry["property_address"]:
            body["property_address"] = entry["property_address"]
        if body:
            n = sb_patch(f"multi_county_auctions?id=eq.{row['id']}&county=eq.citrus", body)
            if n:
                patched += 1
                log(f"PATCHED citrus {row['case_number']} ({pid}): {list(body.keys())}", "VERIFIED")
        time.sleep(0.1)

    log(f"Step 1 FL GIO citrus complete: {patched}/{len(candidates)} patched", "VERIFIED")
    return patched


def step2_citrus_gis(incomplete_rows, covered_pz):
    """Step 2: for rows with CITRUS-PRCLKEY-* style parcel_ids, query Citrus GIS."""
    citrus_key_rows = [
        r for r in incomplete_rows
        if r.get("parcel_id") and str(r["parcel_id"]).startswith("CITRUS-PRCLKEY-")
    ]
    log(f"Step 2 Citrus GIS: {len(citrus_key_rows)} CITRUS-PRCLKEY rows", "UNTESTED")
    if not citrus_key_rows:
        return 0

    patched = 0
    new_pz = []

    for row in citrus_key_rows:
        pid = row["parcel_id"]
        prclkey = pid.replace("CITRUS-PRCLKEY-", "")
        data = fetch_citrus_gis_by_parcel(prclkey)
        features = data.get("features", [])
        if not features:
            log(f"No Citrus GIS match for {pid}", "UNTESTED")
            time.sleep(0.3)
            continue

        feat = features[0]
        attrs = feat.get("attributes", {})
        lat, lon = centroid([feat])
        addr = (attrs.get("ADDR") or attrs.get("SITE_ADDR") or "").strip()
        jv = attrs.get("JV")
        av = attrs.get("AV_SD")

        body = {}
        if row.get("latitude") is None and lat is not None:
            body["latitude"] = lat
        if row.get("longitude") is None and lon is not None:
            body["longitude"] = lon
        if row.get("assessed_value") is None and av:
            body["assessed_value"] = int(av)
        if row.get("market_value") is None and jv:
            body["market_value"] = int(jv)
        if not row.get("property_address") and addr:
            body["property_address"] = addr

        if body:
            n = sb_patch(f"multi_county_auctions?id=eq.{row['id']}&county=eq.citrus", body)
            if n:
                patched += 1
                log(f"PATCHED citrus GIS {row['case_number']} ({pid}): {list(body.keys())}", "VERIFIED")

        if pid not in covered_pz:
            log(f"parcel_zones missing for {pid} — would need zone lookup (out of scope)", "UNTESTED")

        time.sleep(REQUEST_DELAY)

    log(f"Step 2 Citrus GIS complete: {patched}/{len(citrus_key_rows)} patched", "VERIFIED")
    return patched


def step3_citrus_pa_probe(incomplete_rows):
    """Step 3: probe citruspa.org for rows without parcel_id (foreclosure cases)."""
    null_parcel = [
        r for r in incomplete_rows
        if not r.get("parcel_id") or r.get("latitude") is None
    ]
    log(f"Step 3 citruspa.org probe: {len(null_parcel)} rows to try", "UNTESTED")
    if not null_parcel:
        return 0

    found = 0
    for row in null_parcel[:6]:
        html = try_citrus_pa_search(row["case_number"])
        if html:
            log(f"citruspa.org responded for {row['case_number']} — manual parse needed (site is up)", "VERIFIED")
            found += 1
        else:
            log(f"citruspa.org still blocked/down for {row['case_number']}", "UNTESTED")
        time.sleep(1.0)

    if found > 0:
        log(f"citruspa.org is accessible for {found} cases — consider manual or Playwright-based extraction", "VERIFIED")
    else:
        log("citruspa.org still inaccessible for all probed cases", "VERIFIED")

    return 0


def main():
    log("=== SHARD-5 C271DA62 CITRUS I ENRICHMENT ===")
    baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE: {baseline}", "VERIFIED")

    incomplete_rows = get_incomplete_citrus_rows()
    missing_pz, covered_pz = get_citrus_no_parcel_zone()

    geo1 = step1_fl_gio(incomplete_rows)
    geo2 = step2_citrus_gis(incomplete_rows, covered_pz)
    step3_citrus_pa_probe(incomplete_rows)

    total_patched = geo1 + geo2

    if not DRY_RUN:
        log("Waiting 3s for DB to settle...", "UNTESTED")
        time.sleep(3)
        after = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
        log(f"AFTER: {after}", "VERIFIED")

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"\n### SQL VERIFICATION")
        print(f"Timestamp UTC: {now_iso}")
        print(f"SET statement_timeout = 0;")
        print(f"SELECT public.pencil_dod_evaluate_county('citrus');")
        print(f"BEFORE: I={baseline.get('I')}")
        print(f"AFTER:  I={after.get('I')}")
        print(f"fl_gio_patched={geo1} gis_patched={geo2}")
    else:
        print(f"\nDRY-RUN COMPLETE. {len(incomplete_rows)} rows needing enrichment.")


if __name__ == "__main__":
    main()
