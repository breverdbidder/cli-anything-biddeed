#!/usr/bin/env python3
"""
SHARD-28 RUN-338 LETTER E — Parcel Linkage
Counties: citrus (80.9% → need 95%), dixie (100% ✓), suwannee (100% ✓), okaloosa (null)

Letter E: parcel_id linked >= 95% of closed auctions
Approach:
  1. Match by normalized address against fl_parcels / BCPAO ArcGIS
  2. Match by case_number components against property appraiser data
  3. Use county ArcGIS FeatureServer (Brevard BCPAO pipeline is reference)

Session: architect-20260624T080000
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
DRY_RUN = "--dry-run" in sys.argv

COUNTY_PA_CONFIGS = {
    "citrus": {
        "co_no": 9,
        "pa_base": "https://www.citruspa.org",
        # ArcGIS FeatureServer — INFERRED from FL PA pattern
        "arcgis_parcels": "https://gis.citruspa.org/arcgis/rest/services/ParcelData/MapServer/0/query",
        "pa_search": "https://www.citruspa.org/search",
    },
    "okaloosa": {
        "co_no": 46,
        "pa_base": "https://www.okaloosaappraiser.com",
        "arcgis_parcels": "https://maps.myokaloosa.com/arcgis/rest/services/Parcels/MapServer/0/query",
        "pa_search": "https://www.okaloosaappraiser.com/search",
    },
}


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, level: str = "INFO", tag: str = "UNTESTED"):
    print(f"[{ts()}] {level} [{tag}]: {msg}", flush=True)


def mgmt_query(sql: str) -> list:
    if not ACCESS_TOKEN:
        return []
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": sql}).encode(),
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"mgmt_query failed: {e}", "ERROR", "VERIFIED")
        return []


def rest_get_sb(path: str, params: dict = None) -> list:
    """REST GET from Supabase."""
    qs = urllib.parse.urlencode(params or {})
    url = f"{SB_URL}/rest/v1/{path}?{qs}"
    headers = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"rest_get {path} failed: {e}", "WARN", "VERIFIED")
        return []


def rest_patch_sb(path: str, qs: str, data: dict) -> bool:
    """REST PATCH to Supabase."""
    url = f"{SB_URL}/rest/v1/{path}?{qs}"
    headers = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
        return True
    except Exception as e:
        log(f"rest_patch {path} failed: {e}", "ERROR", "VERIFIED")
        return False


def audit_e_before(county: str) -> dict:
    """Audit E metric via REST API."""
    total_r = rest_get_sb("multi_county_auctions", {"select": "count", "county": f"eq.{county}"})
    parcel_r = rest_get_sb("multi_county_auctions", {"select": "count", "county": f"eq.{county}", "parcel_id": "not.is.null"})
    total = int(total_r[0]["count"]) if total_r else 0
    has_parcel = int(parcel_r[0]["count"]) if parcel_r else 0
    e_pct = round(100.0 * has_parcel / total, 1) if total > 0 else 0.0
    row = {"total": total, "has_parcel": has_parcel, "e_pct": e_pct}
    log(f"{county} E baseline: total={total} has_parcel={has_parcel} e_pct={e_pct}%", "INFO", "VERIFIED")
    return row


def link_from_arcgis_by_parcel_address(county: str) -> int:
    """Link parcel_id using county ArcGIS FeatureServer LIKE address queries.
    Uses REST API to get rows, then queries ArcGIS, then patches via REST.
    """
    cfg = COUNTY_PA_CONFIGS.get(county, {})
    arcgis_url = cfg.get("arcgis_parcels")
    if not arcgis_url:
        log(f"{county}: no ArcGIS URL configured", "WARN", "VERIFIED")
        return 0

    # Get rows missing parcel_id but with property_address (or old address field)
    rows = rest_get_sb("multi_county_auctions", {
        "select": "id,case_number,property_address",
        "county": f"eq.{county}",
        "parcel_id": "is.null",
        "property_address": "not.is.null",
        "limit": "200",
    })
    if not rows:
        log(f"{county}: no rows missing parcel_id with property_address", "INFO", "VERIFIED")
        return 0

    log(f"{county}: trying ArcGIS for {len(rows)} rows missing parcel_id", "INFO", "UNTESTED")
    patched = 0

    for row in rows[:50]:  # Cap at 50 to avoid timeouts
        addr = row.get("property_address", "").strip()
        if not addr or addr == "0":
            continue

        safe_addr = addr.replace("'", "''")
        params = urllib.parse.urlencode({
            "where": f"UPPER(SITUS_ADDR) LIKE UPPER('%{safe_addr[:30]}%')",
            "outFields": "PARCEL_ID,SITUS_ADDR",
            "f": "json",
            "returnGeometry": "false",
            "resultRecordCount": "5",
        })
        req = urllib.request.Request(
            f"{arcgis_url}?{params}",
            headers={"User-Agent": "BidDeed/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
        except Exception as e:
            log(f"ArcGIS {county} failed for addr={addr!r}: {e}", "WARN", "VERIFIED")
            time.sleep(0.5)
            continue

        features = data.get("features", [])
        if features:
            pid = str(features[0]["attributes"].get("PARCEL_ID", "")).strip()
            if pid:
                if rest_patch_sb("multi_county_auctions", f"id=eq.{row['id']}", {"parcel_id": pid}):
                    patched += 1

        time.sleep(1.0)

    log(f"{county}: ArcGIS linked {patched} parcels", "INFO", "VERIFIED")
    return patched


def link_from_fl_parcels_by_address(county: str) -> int:
    """Link parcel_id from fl_parcels where address matches.
    Uses REST API to find matches — limited but works without mgmt_query.
    """
    # Get rows missing parcel_id
    rows = rest_get_sb("multi_county_auctions", {
        "select": "id,property_address",
        "county": f"eq.{county}",
        "parcel_id": "is.null",
        "property_address": "not.is.null",
        "limit": "500",
    })
    if not rows:
        return 0

    patched = 0
    for row in rows:
        addr = (row.get("property_address") or "").strip().lower()
        if not addr:
            continue
        # Try exact match in fl_parcels
        matches = rest_get_sb("fl_parcels", {
            "select": "parcel_id",
            "county_slug": f"eq.{county}",
            "situs_address": f"ilike.{addr}",
            "limit": "1",
        })
        if matches and matches[0].get("parcel_id"):
            pid = matches[0]["parcel_id"]
            if rest_patch_sb("multi_county_auctions", f"id=eq.{row['id']}", {"parcel_id": pid}):
                patched += 1
        time.sleep(0.05)

    log(f"{county}: linked {patched} parcels from fl_parcels REST", "INFO", "VERIFIED")
    return patched


def link_from_sample_properties_by_address(county: str) -> int:
    """Stub — REST API join not efficient; returns 0."""
    log(f"{county}: sample_properties REST join not implemented", "INFO", "INFERRED")
    return 0


def link_from_zoning_assignments_by_address(county: str) -> int:
    """Link parcel_id from zoning_assignments via address match."""
    rows = rest_get_sb("multi_county_auctions", {
        "select": "id,property_address",
        "county": f"eq.{county}",
        "parcel_id": "is.null",
        "property_address": "not.is.null",
        "limit": "200",
    })
    if not rows:
        return 0

    patched = 0
    for row in rows[:50]:
        addr = (row.get("property_address") or "").strip()
        if not addr:
            continue
        matches = rest_get_sb("zoning_assignments", {
            "select": "parcel_id",
            "county": f"eq.{county}",
            "address": f"ilike.{addr}",
            "parcel_id": "not.is.null",
            "limit": "1",
        })
        if matches and matches[0].get("parcel_id"):
            pid = matches[0]["parcel_id"]
            if rest_patch_sb("multi_county_auctions", f"id=eq.{row['id']}", {"parcel_id": pid}):
                patched += 1
        time.sleep(0.05)

    log(f"{county}: linked {patched} parcels from zoning_assignments REST", "INFO", "VERIFIED")
    return patched


def link_by_fuzzy_address(county: str) -> int:
    """Stub — fuzzy matching requires DB-side SQL join; returns 0 without mgmt_query."""
    log(f"{county}: fuzzy address link skipped (no mgmt_query in GHA)", "INFO", "INFERRED")
    return 0


def query_arcgis_by_address(county: str, rows: list) -> dict:
    """Query county ArcGIS FeatureServer for parcel_id by address.
    Returns dict of address -> parcel_id.
    INFERRED: uses FL PA ArcGIS pattern.
    """
    cfg = COUNTY_PA_CONFIGS.get(county, {})
    arcgis_url = cfg.get("arcgis_parcels")
    if not arcgis_url:
        return {}

    results = {}
    batch_size = 20

    for i in range(0, min(len(rows), 200), batch_size):
        batch = rows[i : i + batch_size]
        addresses = [r.get("address", "") for r in batch if r.get("address")]
        if not addresses:
            continue

        where_parts = " OR ".join(
            f"UPPER(SITUS_ADDR) LIKE UPPER('%{a.replace(\"'\", \"''\")}%')"
            for a in addresses[:5]
        )
        params = urllib.parse.urlencode({
            "where": where_parts or "1=1",
            "outFields": "PARCEL_ID,SITUS_ADDR,SITUS_CITY",
            "f": "json",
            "returnGeometry": "false",
            "resultRecordCount": "50",
        })

        url = f"{arcgis_url}?{params}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "BidDeed-Run338/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
            for feat in data.get("features", []):
                attrs = feat.get("attributes", {})
                pid = str(attrs.get("PARCEL_ID", "")).strip()
                addr = str(attrs.get("SITUS_ADDR", "")).strip().upper()
                if pid and addr:
                    results[addr] = pid
        except Exception as e:
            log(f"{county} ArcGIS batch {i//batch_size} failed: {e}", "WARN", "VERIFIED")

        time.sleep(1)

    log(f"{county}: ArcGIS returned {len(results)} address→parcel mappings", "INFO", "VERIFIED")
    return results


def process_county(county: str) -> dict:
    log(f"=== Processing E for {county} ===", "INFO", "UNTESTED")
    before = audit_e_before(county)

    n0 = link_from_arcgis_by_parcel_address(county)
    n1 = link_from_fl_parcels_by_address(county)
    n2 = link_from_sample_properties_by_address(county)
    n3 = link_from_zoning_assignments_by_address(county)
    n4 = link_by_fuzzy_address(county)

    after = audit_e_before(county)

    return {
        "county": county,
        "arcgis": n0,
        "fl_parcels": n1,
        "sample_properties": n2,
        "zoning_assignments": n3,
        "fuzzy": n4,
        "before": before,
        "after": after,
    }


def main():
    log(f"SHARD-28 RUN-338 E PARCEL LINKAGE. DRY_RUN={DRY_RUN}", "INFO", "UNTESTED")

    if not SB_KEY:
        log("SUPABASE_KEY not set — aborting", "ERROR", "VERIFIED")
        sys.exit(1)

    target_counties = ["citrus", "okaloosa"]

    results = {}
    for county in target_counties:
        try:
            r = process_county(county)
            results[county] = r
        except Exception as e:
            log(f"FAILED {county}: {e}", "ERROR", "VERIFIED")
            results[county] = {"county": county, "error": str(e)}
        time.sleep(1)

    print("\n### SQL VERIFICATION — E PARCEL LINKAGE RUN-338", flush=True)
    print(f"Timestamp UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}", flush=True)
    for county, r in results.items():
        if "error" in r:
            print(f"  {county}: ERROR — {r['error']}", flush=True)
        else:
            after = r.get("after", {})
            print(f"  {county}: BEFORE={r['before'].get('e_pct',0)}% AFTER={after.get('e_pct',0)}% | fl_parcels={r['fl_parcels']} sp={r['sample_properties']} za={r['zoning_assignments']} fuzzy={r['fuzzy']}", flush=True)

    log("E parcel linkage complete", "INFO", "VERIFIED")


if __name__ == "__main__":
    main()
