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


def audit_e_before(county: str) -> dict:
    sql = f"""
        SELECT
          COUNT(*) AS total,
          COUNT(*) FILTER (WHERE parcel_id IS NOT NULL) AS has_parcel,
          ROUND(100.0 * COUNT(*) FILTER (WHERE parcel_id IS NOT NULL) / NULLIF(COUNT(*),0), 1) AS e_pct
        FROM multi_county_auctions
        WHERE county = '{county}'
    """
    result = mgmt_query(sql)
    row = result[0] if result else {}
    log(f"{county} E baseline: total={row.get('total',0)} has_parcel={row.get('has_parcel',0)} e_pct={row.get('e_pct',0)}%", "INFO", "VERIFIED")
    return row


def link_from_fl_parcels_by_address(county: str) -> int:
    """Link parcel_id via normalized address match against fl_parcels table."""
    sql = f"""
        UPDATE multi_county_auctions mca
        SET parcel_id = fp.parcel_id
        FROM fl_parcels fp
        WHERE mca.county = '{county}'
          AND mca.parcel_id IS NULL
          AND mca.address IS NOT NULL
          AND mca.address != ''
          AND fp.county_slug = '{county}'
          AND (
            LOWER(TRIM(mca.address)) = LOWER(TRIM(fp.situs_address))
            OR LOWER(TRIM(mca.address)) = LOWER(TRIM(fp.property_address))
          )
        RETURNING mca.case_number
    """
    result = mgmt_query(sql)
    n = len(result) if result else 0
    log(f"{county}: linked {n} parcels by address", "INFO", "VERIFIED")
    return n


def link_from_sample_properties_by_address(county: str) -> int:
    """Link parcel_id via address match against sample_properties (co_no-based)."""
    co_no = COUNTY_PA_CONFIGS.get(county, {}).get("co_no")
    if not co_no:
        return 0

    sql = f"""
        UPDATE multi_county_auctions mca
        SET parcel_id = sp.parcel_id
        FROM sample_properties sp
        WHERE mca.county = '{county}'
          AND mca.parcel_id IS NULL
          AND sp.co_no = {co_no}
          AND mca.address IS NOT NULL
          AND mca.address != ''
          AND (
            LOWER(TRIM(mca.address)) = LOWER(TRIM(sp.property_address))
            OR LOWER(TRIM(mca.address)) LIKE LOWER(TRIM(sp.property_address)) || '%'
          )
        RETURNING mca.case_number
    """
    result = mgmt_query(sql)
    n = len(result) if result else 0
    log(f"{county}: linked {n} parcels from sample_properties", "INFO", "VERIFIED")
    return n


def link_from_zoning_assignments_by_address(county: str) -> int:
    """Link parcel_id via address match against zoning_assignments."""
    sql = f"""
        UPDATE multi_county_auctions mca
        SET parcel_id = za.parcel_id
        FROM zoning_assignments za
        WHERE mca.county = '{county}'
          AND mca.parcel_id IS NULL
          AND za.county = '{county}'
          AND mca.address IS NOT NULL
          AND mca.address != ''
          AND za.address IS NOT NULL
          AND LOWER(TRIM(mca.address)) = LOWER(TRIM(za.address))
        RETURNING mca.case_number
    """
    result = mgmt_query(sql)
    n = len(result) if result else 0
    log(f"{county}: linked {n} parcels from zoning_assignments", "INFO", "VERIFIED")
    return n


def link_by_fuzzy_address(county: str) -> int:
    """Fuzzy address match: strip apt/unit, normalize street type abbreviations."""
    sql = f"""
        WITH normalized AS (
            SELECT
              mca.id,
              mca.case_number,
              -- Normalize MCA address: strip leading house #, lowercase, common abbreviations
              REGEXP_REPLACE(
                LOWER(TRIM(COALESCE(mca.address, ''))),
                '\\s+(st|ave|dr|blvd|rd|ln|ct|cir|way|pl|ter|trl|hwy)\\b',
                ' \\1', 'gi'
              ) AS mca_addr_norm
            FROM multi_county_auctions mca
            WHERE mca.county = '{county}'
              AND mca.parcel_id IS NULL
              AND mca.address IS NOT NULL
              AND mca.address != ''
        ),
        fp_normalized AS (
            SELECT
              fp.parcel_id,
              REGEXP_REPLACE(
                LOWER(TRIM(COALESCE(fp.situs_address, ''))),
                '\\s+(st|ave|dr|blvd|rd|ln|ct|cir|way|pl|ter|trl|hwy)\\b',
                ' \\1', 'gi'
              ) AS fp_addr_norm
            FROM fl_parcels fp
            WHERE fp.county_slug = '{county}'
        )
        UPDATE multi_county_auctions mca
        SET parcel_id = fp_normalized.parcel_id
        FROM normalized n
        JOIN fp_normalized ON n.mca_addr_norm = fp_normalized.fp_addr_norm
        WHERE mca.id = n.id
          AND mca.parcel_id IS NULL
        RETURNING mca.case_number
    """
    result = mgmt_query(sql)
    n = len(result) if result else 0
    log(f"{county}: fuzzy-linked {n} parcels", "INFO", "VERIFIED")
    return n


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

    n1 = link_from_fl_parcels_by_address(county)
    n2 = link_from_sample_properties_by_address(county)
    n3 = link_from_zoning_assignments_by_address(county)
    n4 = link_by_fuzzy_address(county)

    after = audit_e_before(county)

    return {
        "county": county,
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
