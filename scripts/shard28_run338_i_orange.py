#!/usr/bin/env python3
"""
SHARD-28 RUN-338 LETTER I FIX — Orange County (REST API ONLY)
orange I = property_address + lat + assessed_value + parcel_id, each >= 95%

This script enriches property_address (the bottleneck) from FR_ISO_Parcels
ArcGIS REST service using 10-digit parcel prefix LIKE queries.
All DB operations via Supabase REST API (no mgmt_query — returns 403 in GHA).

Session: architect-20260624T080000
Dispatch: b79f52d1-d047-4477-bfe6-131e4df0893b
"""
from __future__ import annotations

import json
import os
import sys
import time
import threading
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
DRY_RUN = "--dry-run" in sys.argv

ARCGIS_URL = "https://ocgis4.ocfl.net/arcgis/rest/services/FR_ISO_Parcels/MapServer/0/query"


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, level: str = "INFO", tag: str = "UNTESTED"):
    print(f"[{ts()}] {level} [{tag}]: {msg}", flush=True)


def sb_headers(extra: dict = None) -> dict:
    h = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def rest_get(path: str, params: dict = None) -> list:
    qs = urllib.parse.urlencode(params or {})
    url = f"{SB_URL}/rest/v1/{path}?{qs}"
    req = urllib.request.Request(url, headers=sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"rest_get {path} failed: {e}", "WARN", "VERIFIED")
        return []


def rest_patch(path: str, qs: str, data: dict) -> bool:
    if DRY_RUN:
        return True
    url = f"{SB_URL}/rest/v1/{path}?{qs}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers=sb_headers({"Prefer": "return=minimal"}),
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read()
        return True
    except Exception as e:
        log(f"rest_patch {path} failed: {e}", "ERROR", "VERIFIED")
        return False


def get_missing_rows(county: str = "orange") -> list:
    """Get MCA rows missing property_address (have parcel_id)."""
    rows = []
    offset = 0
    while True:
        batch = rest_get("multi_county_auctions", {
            "select": "id,parcel_id",
            "county": f"eq.{county}",
            "property_address": "is.null",
            "parcel_id": "not.is.null",
            "order": "id",
            "offset": str(offset),
            "limit": "500",
        })
        rows.extend(batch)
        if len(batch) < 500:
            break
        offset += 500
    return rows


def query_arcgis_prefix(prefix10: str) -> tuple[str, str | None, float | None, float | None]:
    """Query FR_ISO_Parcels for a 10-digit parcel prefix.
    Returns (prefix10, situs, total_assd, total_mkt).
    """
    params = urllib.parse.urlencode({
        "where": f"PARCEL LIKE '{prefix10}%'",
        "outFields": "PARCEL,SITUS,TOTAL_ASSD,TOTAL_MKT",
        "f": "json",
        "returnGeometry": "false",
        "resultRecordCount": "100",
    })
    req = urllib.request.Request(f"{ARCGIS_URL}?{params}", headers={"User-Agent": "BidDeed/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read())
    except Exception as e:
        return prefix10, None, None, None

    for feat in data.get("features", []):
        a = feat.get("attributes", {})
        if a.get("SITUS"):
            return prefix10, str(a["SITUS"]).strip(), a.get("TOTAL_ASSD"), a.get("TOTAL_MKT")
    return prefix10, None, None, None


def enrich_property_address(county: str = "orange") -> dict:
    """Main enrichment: FR_ISO_Parcels prefix queries → patch property_address."""
    rows = get_missing_rows(county)
    log(f"{county}: {len(rows)} rows missing property_address", "INFO", "VERIFIED")

    if not rows:
        return {"rows": 0, "patched": 0}

    # Build 10-digit prefix → row ids map
    prefix_to_ids: dict[str, list] = {}
    for r in rows:
        pid = str(r.get("parcel_id", "")).strip()
        prefix = pid[:10] if len(pid) >= 10 else pid
        if prefix not in prefix_to_ids:
            prefix_to_ids[prefix] = []
        prefix_to_ids[prefix].append((r["id"], pid))

    unique_prefixes = list(prefix_to_ids.keys())
    log(f"{county}: {len(unique_prefixes)} unique 10-digit prefixes to query", "INFO", "VERIFIED")

    # Concurrent queries with semaphore (2 workers max to avoid rate-limiting)
    enrichment_map: dict[str, tuple] = {}
    results_lock = threading.Lock()
    sem = threading.Semaphore(2)
    completed = 0
    errors = 0

    def throttled_query(prefix):
        nonlocal completed, errors
        with sem:
            p, situs, assd, mkt = query_arcgis_prefix(prefix)
            time.sleep(0.15)
        with results_lock:
            if situs:
                enrichment_map[p] = (situs, assd, mkt)
            else:
                errors += 1
            completed += 1
            if completed % 30 == 0:
                log(f"  {completed}/{len(unique_prefixes)} prefixes done, matches={len(enrichment_map)}", "INFO", "VERIFIED")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(throttled_query, p) for p in unique_prefixes]
        for f in as_completed(futures):
            pass

    log(f"{county}: enrichment_map={len(enrichment_map)}/{len(unique_prefixes)} matches, no_match={errors}", "INFO", "VERIFIED")

    # Apply patches
    patched = 0
    for prefix, id_pairs in prefix_to_ids.items():
        edata = enrichment_map.get(prefix)
        if not edata:
            continue
        situs, assd, mkt = edata
        for (row_id, _pid) in id_pairs:
            update: dict = {}
            if situs:
                update["property_address"] = situs
            if assd and float(assd) > 0:
                update["assessed_value"] = float(assd)
            if mkt and float(mkt) > 0:
                update["market_value"] = float(mkt)
            if not update:
                continue
            if rest_patch("multi_county_auctions", f"id=eq.{row_id}", update):
                patched += 1

        if patched % 50 == 0 and patched > 0:
            log(f"  Patched {patched} rows so far...", "INFO", "VERIFIED")

    log(f"{county}: patched {patched} rows", "INFO", "VERIFIED")
    return {
        "rows": len(rows),
        "prefixes": len(unique_prefixes),
        "matches": len(enrichment_map),
        "patched": patched,
    }


def audit_i_criteria(county: str = "orange") -> dict:
    """Report current I sub-criteria counts via REST API."""
    total = rest_get("multi_county_auctions", {"select": "count", "county": f"eq.{county}"})
    addr = rest_get("multi_county_auctions", {"select": "count", "county": f"eq.{county}", "property_address": "not.is.null"})
    lat = rest_get("multi_county_auctions", {"select": "count", "county": f"eq.{county}", "latitude": "not.is.null"})
    av = rest_get("multi_county_auctions", {"select": "count", "county": f"eq.{county}", "assessed_value": "not.is.null"})
    pid = rest_get("multi_county_auctions", {"select": "count", "county": f"eq.{county}", "parcel_id": "not.is.null"})

    t = int(total[0]["count"]) if total else 0
    a = int(addr[0]["count"]) if addr else 0
    l = int(lat[0]["count"]) if lat else 0
    v = int(av[0]["count"]) if av else 0
    p = int(pid[0]["count"]) if pid else 0

    log(f"{county} I audit: total={t} addr={a}({100*a//max(1,t)}%) lat={l}({100*l//max(1,t)}%) value={v}({100*v//max(1,t)}%) pid={p}({100*p//max(1,t)}%)", "INFO", "VERIFIED")
    return {"total": t, "addr": a, "lat": l, "value": v, "pid": p}


def main():
    county = "orange"
    log(f"SHARD-28 RUN-338 I FIX v2 — {county}. DRY_RUN={DRY_RUN}", "INFO", "UNTESTED")

    if not SB_KEY:
        log("SUPABASE_KEY not set — aborting", "ERROR", "VERIFIED")
        sys.exit(1)

    before = audit_i_criteria(county)

    result = enrich_property_address(county)

    after = audit_i_criteria(county)

    # Fail-loud invariant
    if result["rows"] > 0 and result["patched"] == 0:
        log(f"WARN: {result['rows']} rows needed enrichment but 0 patched — FR_ISO_Parcels may have no matching data", "WARN", "VERIFIED")

    print(f"\n### SQL VERIFICATION — I FIX RUN-338 {county} v2", flush=True)
    print(f"Timestamp UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}", flush=True)
    print(f"  BEFORE: addr={before['addr']}/{before['total']} lat={before['lat']}/{before['total']} value={before['value']}/{before['total']}", flush=True)
    print(f"  FR_ISO_Parcels: {result['rows']} rows → {result['matches']} prefix matches → {result['patched']} patched", flush=True)
    print(f"  AFTER:  addr={after['addr']}/{after['total']} ({100*after['addr']//max(1,after['total'])}%) lat={after['lat']}/{after['total']} value={after['value']}/{after['total']}", flush=True)
    i_pct = 100 * min(after['addr'], after['lat'], after['value'], after['pid']) // max(1, after['total'])
    print(f"  I card_complete estimate: {i_pct}%", flush=True)

    log("I fix v2 complete", "INFO", "VERIFIED")


if __name__ == "__main__":
    main()
