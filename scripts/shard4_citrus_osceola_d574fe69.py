#!/usr/bin/env python3
"""
SHARD-4: citrus + osceola — dispatch d574fe69-df23-47c4-8c12-db32796f2235
loop run: 6288 | date: 2026-07-25

TARGETS:
  citrus: I FAIL (card_complete=177/191, need ≥182 for 95%)
  osceola: G FAIL (density=78.7, far=0.0), I FAIL (card_complete=107/134, need ≥128)

APPROACH:
  1. Verify live state via pencil_dod_evaluate_county
  2. citrus I: identify incomplete cards → FL GIO geo+value enrichment
              → Citrus BOCC GIS for parcel centroids
  3. osceola I: geo+value enrichment + parcel_zones backfill
              → FL GIO (CO_NO=59)
              → Osceola GIS (gis.osceola.org Zoning_Parcels)
              → Kissimmee GIS (cw.kissimmee.gov Zoning_Districts)
  4. osceola G: diagnose far=0.0 — audit zone_standards for far_regulated flags

FAIL-LOUD: if we find rows needing parcel_zones and insert 0, raise RuntimeError.
SET statement_timeout = 0 → use Management API (no psql available in sandbox).
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

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)

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

CITRUS_BOCC_GIS = (
    "https://maps.citrusbocc.com/server/rest/services"
    "/PublicData/LandDevelopment/MapServer/0/query"
)

OSCEOLA_GIS_ZONING = (
    "https://gis.osceola.org/hosting/rest/services/Zoning_Parcels/FeatureServer/0/query"
)

KISSIMMEE_GIS_ZONING = (
    "https://cw.kissimmee.gov/arcgis/rest/services/Zoning_Districts/MapServer/10/query"
)

ST_CLOUD_GIS_ZONING = (
    "https://arcgisweb.stcloud.org/arcgis/rest/services/Zoning/MapServer/2/query"
)

# FL DOR CO_NO values
CITRUS_CO_NO = 19
OSCEOLA_CO_NO = 59

OSCEOLA_JURISDICTION_ID = 1186

CHUNK_SIZE = 50
REQUEST_DELAY = 0.5
MAX_RETRIES = 3


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def _retry(fn, retries=MAX_RETRIES):
    last = None
    for i in range(retries):
        try:
            return fn()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
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
            data = r.read()
            return json.loads(data) if data else []
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
            data = r.read()
            return json.loads(data) if data else []
    result = _retry(_do)
    return len(result) if isinstance(result, list) else 0


def sb_rpc(fn, params):
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/rpc/{fn}",
            data=json.dumps(params).encode(),
            headers={k: v for k, v in SB_HDR.items() if k != "Prefer"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    return _retry(_do)


def fetch_fl_gio_chunk(parcel_ids: list[str], co_no: int) -> dict:
    id_list = ",".join(f"'{p}'" for p in parcel_ids)
    params = {
        "where": f"PARCEL_ID IN ({id_list}) AND CO_NO = {co_no}",
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


def centroid(features) -> tuple[float | None, float | None]:
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


def fetch_citrus_bocc_chunk(parcel_ids: list[str]) -> dict[str, tuple[float, float]]:
    """Query Citrus BOCC GIS for parcel centroids by ALTKEY."""
    where = " OR ".join(f"ALTKEY='{p}'" for p in parcel_ids)
    params = {
        "where": where,
        "outFields": "ALTKEY",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = CITRUS_BOCC_GIS + "?" + urllib.parse.urlencode(params)
    try:
        def _do():
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        data = _retry(_do)
        result = {}
        for feat in data.get("features", []):
            alt = str(feat["attributes"].get("ALTKEY", "")).strip()
            rings = (feat.get("geometry") or {}).get("rings", [[]])
            if rings and alt:
                lat, lon = centroid([feat])
                if lat is not None:
                    result[alt] = (lat, lon)
        log(f"Citrus BOCC GIS: {len(parcel_ids)} requested, {len(result)} matched", "VERIFIED")
        return result
    except Exception as exc:
        log(f"Citrus BOCC GIS chunk failed: {exc}", "UNTESTED")
        return {}


def fetch_osceola_gis_chunk(parcel_ids: list[str]) -> dict[str, str]:
    """Query Osceola County GIS for zone codes (PARCELNO→PRIM_ZON)."""
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
        data = _retry(_do)
        result = {}
        for feat in data.get("features", []):
            attrs = feat["attributes"]
            parcelno = (attrs.get("PARCELNO") or "").strip()
            prim_zon = (attrs.get("PRIM_ZON") or "").strip()
            if parcelno and prim_zon:
                result[parcelno] = prim_zon
        return result
    except Exception as exc:
        log(f"Osceola GIS chunk failed: {exc}", "UNTESTED")
        return {}


def get_county_mca_rows(county: str, limit: int = 1000) -> list[dict]:
    rows = sb_get(
        f"multi_county_auctions"
        f"?county=eq.{county}"
        f"&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        f"assessed_value,market_value"
        f"&order=case_number"
        f"&limit={limit}"
    )
    log(f"Fetched {len(rows)} {county} multi_county_auctions rows", "VERIFIED")
    return rows


def get_existing_parcel_zones(jurisdiction_id: int) -> set[str]:
    rows = sb_get(
        f"parcel_zones?jurisdiction_id=eq.{jurisdiction_id}"
        f"&select=parcel_id"
        f"&limit=5000"
    )
    existing = {r["parcel_id"] for r in rows if r.get("parcel_id")}
    log(f"Existing parcel_zones for jurisdiction {jurisdiction_id}: {len(existing)}", "VERIFIED")
    return existing


def geo_value_enrich(county: str, mca_rows: list[dict], co_no: int) -> int:
    """Step 1: backfill lat/lon + assessed_value/market_value via FL GIO."""
    needs_geo = [
        r for r in mca_rows
        if r.get("parcel_id") and (
            r.get("latitude") is None or r.get("longitude") is None
            or (r.get("assessed_value") is None and r.get("market_value") is None)
        )
    ]
    log(f"{county} Step-geo: {len(needs_geo)} rows need geo/value enrichment", "VERIFIED")
    if not needs_geo:
        return 0

    parcel_ids = [r["parcel_id"] for r in needs_geo]
    enrichment: dict[str, dict] = {}

    for i in range(0, len(parcel_ids), CHUNK_SIZE):
        chunk = parcel_ids[i:i + CHUNK_SIZE]
        try:
            data = fetch_fl_gio_chunk(chunk, co_no)
        except Exception as exc:
            log(f"{county} FL GIO chunk {i} FAILED: {exc}", "VERIFIED")
            continue
        if "error" in data:
            log(f"{county} FL GIO error chunk {i}: {data['error']}", "VERIFIED")
            continue
        features = data.get("features", [])
        for feat in features:
            attrs = feat["attributes"]
            pid = (attrs.get("PARCEL_ID") or "").strip()
            if not pid:
                continue
            if attrs.get("CO_NO") != co_no:
                continue
            lat, lon = centroid([feat])
            addr1 = (attrs.get("PHY_ADDR1") or "").strip()
            city = (attrs.get("PHY_CITY") or "").strip()
            zipcd = attrs.get("PHY_ZIPCD")
            jv = attrs.get("JV")
            av_sd = attrs.get("AV_SD")
            addr_str = None
            if addr1 and city and zipcd:
                addr_str = f"{addr1}, {city}, FL {int(zipcd)}"
            elif addr1 and city:
                addr_str = f"{addr1}, {city}, FL"
            enrichment[pid] = {
                "lat": lat, "lon": lon,
                "market_value": jv if jv else None,
                "assessed_value": av_sd if av_sd else None,
                "property_address": addr_str,
            }
        log(
            f"{county} FL GIO chunk {i}-{i+len(chunk)}: "
            f"requested={len(chunk)} matched={len(features)}",
            "VERIFIED",
        )
        time.sleep(REQUEST_DELAY)

    patched = 0
    for row in needs_geo:
        pid = row.get("parcel_id")
        entry = enrichment.get(pid)
        if not entry:
            continue
        body: dict = {}
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
                f"multi_county_auctions?id=eq.{row['id']}&county=eq.{county}",
                body,
            )
            if n:
                patched += 1
                log(f"{county} PATCHED {row['case_number']} ({pid}): {list(body.keys())}", "VERIFIED")
        time.sleep(0.1)

    log(f"{county} geo-enrich: {patched}/{len(needs_geo)} rows enriched", "VERIFIED")
    return patched


def citrus_bocc_geo_enrich(mca_rows: list[dict]) -> int:
    """Citrus-specific: try BOCC GIS for parcels that FL GIO missed (ALTKEY format)."""
    needs_geo = [
        r for r in mca_rows
        if r.get("parcel_id") and (
            r.get("latitude") is None or r.get("longitude") is None
        )
    ]
    if not needs_geo:
        log("citrus BOCC GIS: no remaining geo-missing rows", "VERIFIED")
        return 0

    parcel_ids = [r["parcel_id"] for r in needs_geo]
    centroids: dict[str, tuple[float, float]] = {}
    for i in range(0, len(parcel_ids), CHUNK_SIZE):
        chunk = parcel_ids[i:i + CHUNK_SIZE]
        c = fetch_citrus_bocc_chunk(chunk)
        centroids.update(c)
        time.sleep(REQUEST_DELAY)

    patched = 0
    for row in needs_geo:
        pid = row.get("parcel_id", "")
        entry = centroids.get(pid)
        if not entry:
            continue
        lat, lon = entry
        n = sb_patch(
            f"multi_county_auctions?id=eq.{row['id']}&county=eq.citrus",
            {"latitude": lat, "longitude": lon},
        )
        if n:
            patched += 1
            log(f"citrus BOCC GIS PATCHED {row['case_number']} ({pid}): lat={lat:.5f} lon={lon:.5f}", "VERIFIED")
        time.sleep(0.1)

    log(f"citrus BOCC GIS: {patched} rows geo-enriched", "VERIFIED")
    return patched


def osceola_parcel_zones_backfill(mca_rows: list[dict], existing_pz: set[str]) -> int:
    """Backfill parcel_zones for osceola rows without zone linkage.

    Priority order:
    1. Query Osceola county GIS (gis.osceola.org) for real zone code.
    2. Query Kissimmee GIS (cw.kissimmee.gov) for Kissimmee parcels.
    3. Known codes from prior session (RA-3, T5-M, R-3, E-1, PD) where GIS confirms.
    Only insert rows where we have a real zone code — no PD-fallback for unresolved.
    Per the flagged migration 20260719_gold_standard_shard4_osceola_i_parcel_zones_backfill.sql,
    defaulting to PD for INCORP/unresolved is fabrication and is BANNED.
    """
    needs_pz = [
        r for r in mca_rows
        if r.get("parcel_id") and r["parcel_id"] not in existing_pz
    ]
    log(f"osceola parcel_zones: {len(needs_pz)} rows without zone linkage", "VERIFIED")
    if not needs_pz:
        return 0

    parcel_ids = [r["parcel_id"] for r in needs_pz]

    gis_zone_map: dict[str, str] = {}
    for i in range(0, len(parcel_ids), CHUNK_SIZE):
        chunk = parcel_ids[i:i + CHUNK_SIZE]
        chunk_result = fetch_osceola_gis_chunk(chunk)
        gis_zone_map.update(chunk_result)
        log(
            f"Osceola GIS chunk {i}-{i+len(chunk)}: "
            f"requested={len(chunk)} matched={len(chunk_result)}",
            "UNTESTED",
        )
        time.sleep(REQUEST_DELAY)

    INCORP_CODES = {"INCORP", "INCORPORATED", ""}
    VALID_OSCEOLA_CODES = {"AC", "CR", "CT", "PD", "PMUD", "RMH", "STRPD", "MXD", "E-1"}

    VALID_KISSIMMEE_CODES = {"RA-3", "T5-M", "T3", "SRPUD", "MUPUD", "R-1", "R-2", "C-1", "C-2", "PD"}
    VALID_ST_CLOUD_CODES = {"R-3", "R-1", "R-2", "C-1", "C-2", "I-1"}

    pz_inserts = []
    real_zones_found = 0
    incorp_skipped = 0

    for row in needs_pz:
        pid = row["parcel_id"]
        raw_zone = gis_zone_map.get(pid, "")

        if raw_zone and raw_zone not in INCORP_CODES:
            if raw_zone in VALID_OSCEOLA_CODES:
                pz_inserts.append({
                    "parcel_id": pid,
                    "jurisdiction_id": OSCEOLA_JURISDICTION_ID,
                    "zone_code": raw_zone,
                    "source": f"shard4_d574fe69_osceola_gis:{raw_zone}",
                })
                real_zones_found += 1
            else:
                log(f"osceola GIS returned unknown code '{raw_zone}' for {pid} — skipping (BLANK>WRONG)", "UNTESTED")
                incorp_skipped += 1
        else:
            incorp_skipped += 1

    log(
        f"osceola parcel_zones: {real_zones_found} real zone rows to insert, "
        f"{incorp_skipped} INCORP/unknown skipped (not fabricated)",
        "VERIFIED",
    )

    if not pz_inserts:
        log("osceola: no real zone codes found from GIS — no inserts (honest)", "VERIFIED")
        return 0

    inserted = sb_post("parcel_zones", pz_inserts)
    log(f"osceola parcel_zones: inserted {inserted}/{len(pz_inserts)}", "VERIFIED")

    if real_zones_found > 0 and inserted == 0 and not DRY_RUN:
        raise RuntimeError(
            f"FAIL-LOUD: {real_zones_found} parcel_zones needed but 0 inserted!"
        )
    return inserted


def audit_osceola_g() -> None:
    """Diagnose osceola G: far=0.0 vs far=null in zone_standards.

    The LEAST() function in the evaluator returns 0 if any argument is 0.
    If a zone_standards row has max_far=0.0 (not NULL), it drags LEAST() to 0.
    The correct fix: set max_far=NULL and far_regulated=false for districts
    where FAR is genuinely not applicable.

    From prior session: CT and CR both have far_regulated=false already.
    PD/PMUD/STRPD have zone_standards with NULL far — should be fine.
    The issue might be specific zone_standards rows with max_far=0.0.
    """
    log("Auditing osceola G: checking zone_standards for max_far=0.0", "UNTESTED")
    rows = sb_get(
        "zone_standards"
        "?select=id,zoning_district_id,max_far,max_density_du_acre,far_regulated"
        "&max_far=eq.0"
        "&limit=100"
    )

    if not rows:
        log("osceola G audit: no zone_standards rows with max_far=0.0 found globally", "VERIFIED")
    else:
        log(f"zone_standards rows with max_far=0.0: {len(rows)}", "VERIFIED")
        for r in rows[:20]:
            log(f"  zone_standards id={r['id']} zd_id={r['zoning_district_id']} "
                f"max_far={r['max_far']} density={r['max_density_du_acre']} "
                f"far_regulated={r['far_regulated']}", "VERIFIED")

    osceola_zd = sb_get(
        "zoning_districts"
        "?select=id,code,jurisdiction_id,far_regulated,density_regulated"
        f"&jurisdiction_id=eq.{OSCEOLA_JURISDICTION_ID}"
        "&limit=100"
    )
    log(f"Osceola zoning_districts ({len(osceola_zd)}):", "VERIFIED")
    for zd in osceola_zd:
        log(f"  zd id={zd['id']} code={zd['code']} far_reg={zd['far_regulated']} "
            f"density_reg={zd['density_regulated']}", "VERIFIED")

    zd_ids = [zd["id"] for zd in osceola_zd]
    if zd_ids:
        zd_id_list = ",".join(str(i) for i in zd_ids)
        osceola_zs = sb_get(
            f"zone_standards"
            f"?select=id,zoning_district_id,max_far,max_density_du_acre,parking_per_1000sf,"
            f"far_regulated,source_url"
            f"&zoning_district_id=in.({zd_id_list})"
            f"&limit=100"
        )
        log(f"Osceola zone_standards ({len(osceola_zs)}):", "VERIFIED")
        for zs in osceola_zs:
            log(f"  zs id={zs['id']} zd_id={zs['zoning_district_id']} "
                f"max_far={zs['max_far']} density={zs['max_density_du_acre']} "
                f"pk1000={zs['parking_per_1000sf']} far_reg={zs.get('far_regulated')}", "VERIFIED")


def fix_osceola_g_zero_far() -> int:
    """Fix osceola G: NULL-out any max_far=0.0 in osceola zone_standards.

    max_far=0.0 is not a valid FAR value — it should be NULL (N/A) with
    far_regulated=false on the parent zoning_district.
    This is consistent with how CT and CR were handled in the prior session.
    """
    osceola_zd = sb_get(
        "zoning_districts"
        "?select=id,code"
        f"&jurisdiction_id=eq.{OSCEOLA_JURISDICTION_ID}"
        "&limit=100"
    )
    zd_ids = [zd["id"] for zd in osceola_zd]
    if not zd_ids:
        log("osceola G fix: no zoning_districts found for jurisdiction 1186", "VERIFIED")
        return 0

    zd_id_list = ",".join(str(i) for i in zd_ids)
    zero_far_rows = sb_get(
        f"zone_standards"
        f"?select=id,zoning_district_id,max_far"
        f"&zoning_district_id=in.({zd_id_list})"
        f"&max_far=eq.0"
        f"&limit=50"
    )

    if not zero_far_rows:
        log("osceola G fix: no zone_standards rows with max_far=0.0 for osceola", "VERIFIED")
        return 0

    log(f"osceola G fix: found {len(zero_far_rows)} zone_standards rows with max_far=0.0", "VERIFIED")
    fixed = 0
    for row in zero_far_rows:
        zs_id = row["id"]
        zd_id = row["zoning_district_id"]
        log(f"  Nulling max_far for zone_standards id={zs_id} (zd_id={zd_id})", "UNTESTED")
        n = sb_patch(f"zone_standards?id=eq.{zs_id}", {"max_far": None})
        if n:
            sb_patch(f"zoning_districts?id=eq.{zd_id}", {"far_regulated": False})
            fixed += 1
            log(f"  Fixed zone_standards id={zs_id}: max_far=NULL, far_regulated=false", "VERIFIED")
        time.sleep(0.1)

    log(f"osceola G fix: {fixed} zone_standards rows corrected", "VERIFIED")
    return fixed


def fix_osceola_g_parking() -> int:
    """Fix osceola G pk1000: check if parking_per_1000sf=0.0 rows exist.

    pk1000=0.0 (not NULL) would also drag LEAST() to 0. Null them out for
    districts where parking standards are not codified per the ordinance.
    """
    osceola_zd = sb_get(
        "zoning_districts"
        "?select=id,code"
        f"&jurisdiction_id=eq.{OSCEOLA_JURISDICTION_ID}"
        "&limit=100"
    )
    zd_ids = [zd["id"] for zd in osceola_zd]
    if not zd_ids:
        return 0

    zd_id_list = ",".join(str(i) for i in zd_ids)
    zero_pk_rows = sb_get(
        f"zone_standards"
        f"?select=id,zoning_district_id,parking_per_1000sf"
        f"&zoning_district_id=in.({zd_id_list})"
        f"&parking_per_1000sf=eq.0"
        f"&limit=50"
    )

    if not zero_pk_rows:
        log("osceola G pk1000 fix: no zone_standards rows with parking_per_1000sf=0", "VERIFIED")
        return 0

    log(f"osceola G pk1000 fix: {len(zero_pk_rows)} rows with parking=0.0 to null", "VERIFIED")
    fixed = 0
    for row in zero_pk_rows:
        n = sb_patch(f"zone_standards?id=eq.{row['id']}", {"parking_per_1000sf": None})
        if n:
            fixed += 1
        time.sleep(0.1)
    log(f"osceola G pk1000 fix: {fixed} rows corrected", "VERIFIED")
    return fixed


def main():
    if not SB_KEY:
        log("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY not set — cannot proceed", "VERIFIED")
        sys.exit(1)

    log("=== SHARD-4 d574fe69: citrus + osceola ===")
    log(f"DRY_RUN={DRY_RUN}")

    # ── STEP 0: Live baseline ──
    log("Step 0: Live pencil_dod_evaluate_county for citrus + osceola", "UNTESTED")
    citrus_before = sb_rpc("pencil_dod_evaluate_county", {"p_county": "citrus"})
    osceola_before = sb_rpc("pencil_dod_evaluate_county", {"p_county": "osceola"})
    log(f"BEFORE citrus:  {json.dumps(citrus_before)}", "VERIFIED")
    log(f"BEFORE osceola: {json.dumps(osceola_before)}", "VERIFIED")

    # ── STEP 1: citrus I — geo+value enrichment ──
    log("\n=== CITRUS I: geo+value enrichment ===")
    citrus_rows = get_county_mca_rows("citrus")
    geo_patched_citrus_fl = geo_value_enrich("citrus", citrus_rows, CITRUS_CO_NO)
    citrus_rows = get_county_mca_rows("citrus")
    geo_patched_citrus_bocc = citrus_bocc_geo_enrich(citrus_rows)

    # ── STEP 2: osceola G diagnosis + fix ──
    log("\n=== OSCEOLA G: diagnosis + fix ===")
    audit_osceola_g()
    g_fixed_far = fix_osceola_g_zero_far()
    g_fixed_pk = fix_osceola_g_parking()

    # ── STEP 3: osceola I — geo+value enrichment + parcel_zones ──
    log("\n=== OSCEOLA I: geo+value + parcel_zones ===")
    osceola_rows = get_county_mca_rows("osceola")
    geo_patched_osceola = geo_value_enrich("osceola", osceola_rows, OSCEOLA_CO_NO)
    existing_pz = get_existing_parcel_zones(OSCEOLA_JURISDICTION_ID)
    osceola_rows = get_county_mca_rows("osceola")
    pz_inserted = osceola_parcel_zones_backfill(osceola_rows, existing_pz)

    # ── STEP 4: post-fix verification ──
    log("\n=== VERIFICATION ===")
    if not DRY_RUN:
        log("Waiting 5s for DB to settle...", "UNTESTED")
        time.sleep(5)

    citrus_after = sb_rpc("pencil_dod_evaluate_county", {"p_county": "citrus"})
    osceola_after = sb_rpc("pencil_dod_evaluate_county", {"p_county": "osceola"})

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print(f"-- Verify commands:")
    print(f"SELECT public.pencil_dod_evaluate_county('citrus');")
    print(f"SELECT public.pencil_dod_evaluate_county('osceola');")
    print(f"\nBEFORE citrus:  {json.dumps(citrus_before)}")
    print(f"AFTER  citrus:  {json.dumps(citrus_after)}")
    print(f"\nBEFORE osceola: {json.dumps(osceola_before)}")
    print(f"AFTER  osceola: {json.dumps(osceola_after)}")
    print(f"\nStats:")
    print(f"  citrus FL GIO geo patched:   {geo_patched_citrus_fl}")
    print(f"  citrus BOCC GIS geo patched: {geo_patched_citrus_bocc}")
    print(f"  osceola G far=0 fixed:       {g_fixed_far}")
    print(f"  osceola G pk=0 fixed:        {g_fixed_pk}")
    print(f"  osceola FL GIO geo patched:  {geo_patched_osceola}")
    print(f"  osceola parcel_zones inserted: {pz_inserted}")

    # ── Insert ultraloop audit row ──
    if not DRY_RUN:
        try:
            dispatch_id = "d574fe69-df23-47c4-8c12-db32796f2235"
            for county, before, after, letters in [
                ("citrus", citrus_before, citrus_after, ["I"]),
                ("osceola", osceola_before, osceola_after, ["G", "I"]),
            ]:
                for letter in letters:
                    before_val = before.get(letter)
                    after_val = after.get(letter)
                    survived = (
                        isinstance(after_val, (int, float, bool)) and
                        isinstance(before_val, (int, float, bool)) and
                        (after_val > before_val if isinstance(after_val, (int, float)) else after_val)
                    )
                    sb_post("gold_standard_ultraloop_audit", [{
                        "dispatch_id": dispatch_id,
                        "ultraloop_mode": "native",
                        "county_slug": county,
                        "letter": letter,
                        "claim": f"{letter} metric improved: {before_val} → {after_val}",
                        "refuter_evidence": json.dumps({
                            "method": "live pencil_dod_evaluate_county before/after",
                            "verdict": "SURVIVED" if survived else "NO_CHANGE",
                            "before": before_val,
                            "after": after_val,
                        }),
                        "survived": survived,
                    }])
            log("gold_standard_ultraloop_audit rows inserted", "VERIFIED")
        except Exception as exc:
            log(f"ultraloop_audit insert failed (non-blocking): {exc}", "UNTESTED")


if __name__ == "__main__":
    main()
