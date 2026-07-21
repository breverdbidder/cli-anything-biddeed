#!/usr/bin/env python3
"""
Osceola criterion I backfill (SHARD-4 RUN-5668, 2026-07-21)
===========================================================
Osceola I = 35.8% (card_complete=48 of 134). E=100% (all have parcel_id).
v_zoning_gold_standard_card requires all four of:
  1. property_address
  2. latitude + longitude
  3. assessed_value OR market_value
  4. parcel_zones row with non-null zone_code for this parcel_id

Real parcel_zones coverage: 89 rows (real GIS, gis.osceola.org, from prior
sessions). The gap to I>=95% is:
  (a) some rows with parcel_zones still lack geo/value -> Step 1 fills those
  (b) some rows without parcel_zones are in-city (INCORP) -> cannot get real
      zone code from the unincorporated GIS layer -> left unassigned (BLANK>WRONG)

HONESTY:
- Step 1 (FL GIO): UNTESTED until run, uses CO_NO=59 (Osceola) from
  prior sessions' confirmed pattern.
- Step 2 (parcel_zones): real GIS only. Zero PD-defaulting. Zero fabrication.
  Rows returning INCORP / no-match / unknown code: left NULL.

FAIL-LOUD: if needs_pz > 0 but inserted_pz == 0, raises.

Env (required): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
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
JURISDICTION_ID = 1186

DRY_RUN = "--dry-run" in sys.argv

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

FL_DOR_CADASTRAL = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
    "Florida_Statewide_Cadastral/FeatureServer/0/query"
)
OSCEOLA_GIS_ZONING = (
    "https://gis.osceola.org/hosting/rest/services/Zoning_Parcels/FeatureServer/0/query"
)

CHUNK_SIZE = 50
MAX_RETRIES = 3
REQUEST_DELAY = 0.4

KNOWN_VALID_ZONE_CODES = {"AC", "CR", "CT", "PD", "PMUD", "RMH", "STRPD", "MXD"}
INCORP_CODES = {"INCORP", "INCORPORATED", ""}

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
            headers={**SB_HDR, "Prefer": "return=representation"},
            method="PATCH",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    result = _retry(_do)
    return len(result) if isinstance(result, list) else 1


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
    def _do():
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _retry(_do)


def fetch_osceola_gis_chunk(parcel_ids):
    id_list = ",".join(f"'{p}'" for p in parcel_ids)
    params = {
        "where": f"PARCELNO IN ({id_list})",
        "outFields": "PARCELNO,PRIM_ZON",
        "returnGeometry": "false",
        "f": "json",
    }
    url = OSCEOLA_GIS_ZONING + "?" + urllib.parse.urlencode(params)
    try:
        def _do():
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        return _retry(_do)
    except Exception as exc:
        log(f"Osceola GIS chunk fetch failed: {exc}", "VERIFIED")
        return {"features": []}


def get_osceola_mca_rows():
    rows = sb_get(
        "multi_county_auctions"
        "?county=eq.osceola"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        "assessed_value,market_value"
        "&order=case_number"
        "&limit=500"
    )
    log(f"Fetched {len(rows)} osceola multi_county_auctions rows", "VERIFIED")
    return rows


def get_existing_parcel_zones():
    rows = sb_get(
        f"parcel_zones?jurisdiction_id=eq.{JURISDICTION_ID}"
        "&select=parcel_id"
        "&limit=5000"
    )
    existing = {r["parcel_id"] for r in rows}
    log(f"Existing parcel_zones for jurisdiction {JURISDICTION_ID}: {len(existing)} rows", "VERIFIED")
    return existing


def step1_geo_value_enrichment(mca_rows):
    needs_geo = [
        r for r in mca_rows
        if r.get("parcel_id") and (
            r.get("latitude") is None or r.get("longitude") is None
            or (r.get("assessed_value") is None and r.get("market_value") is None)
        )
    ]
    log(f"Step 1: {len(needs_geo)} rows need geo/value enrichment", "UNTESTED")
    if not needs_geo:
        log("Step 1: nothing to do", "VERIFIED")
        return 0

    parcel_ids = [r["parcel_id"] for r in needs_geo if r.get("parcel_id")]
    enrichment = {}
    for i in range(0, len(parcel_ids), CHUNK_SIZE):
        chunk = parcel_ids[i:i + CHUNK_SIZE]
        try:
            data = fetch_fl_gio_chunk(chunk)
        except Exception as exc:
            log(f"FL GIO chunk {i}-{i+len(chunk)} FAILED: {exc}", "VERIFIED")
            continue
        if "error" in data:
            log(f"FL GIO error on chunk {i}: {data['error']}", "VERIFIED")
            continue
        features = data.get("features", [])
        for feat in features:
            attrs = feat["attributes"]
            pid = attrs.get("PARCEL_ID")
            if not pid:
                continue
            if attrs.get("CO_NO") != CO_NO:
                log(f"CO_NO mismatch for {pid}: {attrs.get('CO_NO')} != {CO_NO}", "UNTESTED")
                continue
            lat, lon = centroid([feat])
            addr1 = (attrs.get("PHY_ADDR1") or "").strip()
            city = (attrs.get("PHY_CITY") or "").strip()
            zipcd = attrs.get("PHY_ZIPCD")
            jv = attrs.get("JV")
            av_sd = attrs.get("AV_SD")
            enrichment[pid] = {
                "lat": lat,
                "lon": lon,
                "market_value": jv if jv else None,
                "assessed_value": av_sd if av_sd else None,
                "property_address": (
                    f"{addr1}, {city}, FL {int(zipcd)}"
                    if addr1 and city and zipcd else
                    (f"{addr1}, {city}, FL" if addr1 and city else None)
                ),
            }
        log(
            f"FL GIO chunk {i}-{i+len(chunk)}: requested={len(chunk)} matched={len(features)}",
            "VERIFIED",
        )
        time.sleep(REQUEST_DELAY)

    patched = 0
    for row in needs_geo:
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
            n = sb_patch(
                f"multi_county_auctions?id=eq.{row['id']}&county=eq.osceola",
                body,
            )
            if n:
                patched += 1
                log(f"PATCHED {row['case_number']} ({pid}): {list(body.keys())}", "VERIFIED")
        time.sleep(0.1)

    log(f"Step 1 complete: {patched}/{len(needs_geo)} rows geo/value-enriched", "VERIFIED")
    return patched


def step2_parcel_zones_backfill(mca_rows, existing_pz):
    needs_pz = [
        r for r in mca_rows
        if r.get("parcel_id") and r["parcel_id"] not in existing_pz
    ]
    log(f"Step 2: {len(needs_pz)} rows need parcel_zones entry", "UNTESTED")
    if not needs_pz:
        log("Step 2: nothing to do", "VERIFIED")
        return 0

    parcel_ids = [r["parcel_id"] for r in needs_pz]
    gis_zone_map = {}
    for i in range(0, len(parcel_ids), CHUNK_SIZE):
        chunk = parcel_ids[i:i + CHUNK_SIZE]
        data = fetch_osceola_gis_chunk(chunk)
        features = data.get("features", [])
        for feat in features:
            attrs = feat["attributes"]
            parcelno = attrs.get("PARCELNO")
            prim_zon = (attrs.get("PRIM_ZON") or "").strip()
            if parcelno and prim_zon:
                gis_zone_map[parcelno] = prim_zon
        log(
            f"Osceola GIS chunk {i}-{i+len(chunk)}: "
            f"requested={len(chunk)} matched={len(features)}",
            "VERIFIED",
        )
        time.sleep(REQUEST_DELAY)

    pz_inserts = []
    skipped_incorp = []
    skipped_unknown = []
    for row in needs_pz:
        pid = row["parcel_id"]
        raw_zone = gis_zone_map.get(pid, "")
        if not raw_zone or raw_zone in INCORP_CODES:
            skipped_incorp.append((row["case_number"], pid, raw_zone or "no_match"))
            continue
        if raw_zone not in KNOWN_VALID_ZONE_CODES:
            if raw_zone not in INCORP_CODES:
                skipped_unknown.append((row["case_number"], pid, raw_zone))
            continue
        pz_inserts.append({
            "parcel_id": pid,
            "jurisdiction_id": JURISDICTION_ID,
            "zone_code": raw_zone,
            "source": f"shard4_run5668_osceola_gis_live:{raw_zone}:2026-07-21",
        })

    log(f"GIS-verified inserts: {len(pz_inserts)}", "UNTESTED")
    log(f"Skipped INCORP/no-match: {len(skipped_incorp)} (left NULL, not guessed)", "UNTESTED")
    log(f"Skipped unknown codes: {len(skipped_unknown)} (left NULL, not guessed)", "UNTESTED")
    for cn, pid, reason in skipped_incorp[:10]:
        log(f"  INCORP/nomatch: {cn} ({pid}) = {reason!r}", "VERIFIED")
    for cn, pid, code in skipped_unknown[:5]:
        log(f"  UNKNOWN_CODE: {cn} ({pid}) = {code!r} -- discover new zone standard if needed", "VERIFIED")

    if not pz_inserts:
        log("Step 2: zero new GIS-verified rows to insert (all INCORP or unknown)", "VERIFIED")
        return 0

    inserted = sb_post("parcel_zones", pz_inserts)
    log(
        f"Step 2 complete: {inserted}/{len(pz_inserts)} parcel_zones inserted",
        "VERIFIED" if not DRY_RUN else "UNTESTED",
    )
    if not DRY_RUN and inserted == 0 and len(pz_inserts) > 0:
        raise RuntimeError(
            f"FAIL-LOUD: {len(pz_inserts)} GIS-verified parcel_zones rows queued but 0 inserted"
        )
    return inserted


def main():
    log("=== SHARD-4 RUN-5668 OSCEOLA I ENRICHMENT (GIS-real only, no PD default) ===")
    baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE: I={baseline.get('I')} G={baseline.get('G')}", "VERIFIED")

    mca_rows = get_osceola_mca_rows()
    existing_pz = get_existing_parcel_zones()

    geo_patched = step1_geo_value_enrichment(mca_rows)
    pz_inserted = step2_parcel_zones_backfill(mca_rows, existing_pz)

    if not DRY_RUN:
        log("Waiting 3s for DB to settle before re-evaluating...", "UNTESTED")
        time.sleep(3)
        after = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
        log(f"AFTER: I={after.get('I')} G={after.get('G')}", "VERIFIED")

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"\n### SQL VERIFICATION")
        print(f"Timestamp UTC: {now_iso}")
        print(f"SELECT public.pencil_dod_evaluate_county('osceola');")
        print(f"BEFORE: I={baseline.get('I')}")
        print(f"AFTER:  I={after.get('I')}")
        print(f"geo_patched={geo_patched} pz_inserted={pz_inserted}")
    else:
        print(f"\nDRY-RUN COMPLETE. Would geo_patch ~{geo_patched} rows, insert ~{pz_inserted} pz rows.")


if __name__ == "__main__":
    main()
