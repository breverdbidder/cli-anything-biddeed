#!/usr/bin/env python3
"""
Okaloosa C/D/E fix (SHARD-9 RUN-6080, 2026-07-24)
===================================================
Gold Standard work-package 3 of 5, county=okaloosa ONLY.

Baseline (pencil_dod_evaluate_county, live-verified this session):
  C=89.5% (matched_clean=51/57), D=93.0% (matched_any=53/57),
  E=89.5% (parcel_linked=51/57) — all FAIL (threshold >=95%, i.e. >=55/57).

Root cause: 6 rows with parcel_id IS NULL / matched_clean gap. Of those:
  - 2024-CA-000470, 2024-TDD-000089: documented STALE PLACEHOLDERS
    (confirmed absent from Bid4Assets platform across 3+ prior sessions).
    Left untouched — honest residual, do NOT fabricate.
  - 2025-CA-002043-F, 2025-CA-002956-C, 2025-CA-003450-C, 2025CA000832F:
    real rows with real street addresses, no parcel_id. RESOLVED this run
    via single-match SITE_ADDR queries against the okaloosa parcel GIS
    layer (Land-Ownership/Parcels_with_Addressing/MapServer/121).

    Notably 2025-CA-003450-C had been flagged "known_unresolvable_separate_
    agent" by an unmerged prior script (shard4_run5668) with a hardcoded
    skip and no investigation. Re-attempted fresh this run: query
    "SITE_ADDR LIKE '4320 Cooper%'" (broader prefix than the naive
    "4320 Cooper LANCE%" since the GIS layer normalizes "Lance" -> "LN")
    returns exactly 1 result, PIN 08-2N-25-0000-0008-0000, whose feature
    centroid matches the row's pre-existing lat/lon to 6+ decimal places
    — strong corroboration. It was NOT actually unresolvable.

Address-normalization / GIS-match logic adapted from an unmerged prior
session (branch claude/issue-12952-20260721-1601,
scripts/shard4_run5668_okaloosa_cei_g_fix.py) — every match was
independently re-verified live in this session, not trusted as ground
truth.

Result (all 4 real cases matched, single-result-only, no guessing):
  case_number          | parcel_id (PIN)             | match query
  2025-CA-002043-F      | 09-1S-22-0730-0005-0290     | SITE_ADDR LIKE '2419%EDGEWATER%'
  2025-CA-002956-C      | 27-3N-23-1001-0000-0900     | SITE_ADDR LIKE '414 CHICKADEE ST%'
  2025-CA-003450-C      | 08-2N-25-0000-0008-0000     | SITE_ADDR LIKE '4320 Cooper%'
  2025CA000832F         | 08-3N-23-1720-000R-0220     | SITE_ADDR LIKE '1201 WALTER AVE%'

For each match: parcel_id=PIN; assessed_value/market_value backfilled
from ASSEDVAL/TOTALAPPR ONLY where the DB field was NULL (never
overwrite real data); latitude/longitude backfilled from ring-centroid
ONLY where NULL; parity_status='matched_clean'; parity_source=
'tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:Parcels_with_Addressing:121:shard9_okaloosa_run6080'.

Post-fix (pencil_dod_evaluate_county, live-verified):
  C=96.5% (55/57) PASS, D=96.5% (55/57) PASS, E=96.5% (55/57) PASS.

This was executed interactively via one-off scripts against the REST
API this session; this file documents the exact logic used and is safe
to re-run (idempotent -- rows already parcel_id + matched_clean are
naturally excluded since the GIS queries below are keyed off case
addresses, not existing DB state, but callers should still check
current state before overwriting).

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

COUNTY = "okaloosa"
GIS_BASE = (
    "https://okgis.myokaloosa.com/arcgis/rest/services/"
    "Land-Ownership/Parcels_with_Addressing/MapServer/121/query"
)
PARITY_SOURCE = (
    "tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:"
    "Parcels_with_Addressing:121:shard9_okaloosa_run6080"
)

# case_number -> confirmed single-match SITE_ADDR LIKE prefix (verified
# live 2026-07-24; each returns exactly 1 GIS feature).
CASE_MATCH_QUERIES = {
    "2025-CA-002043-F": "SITE_ADDR LIKE '2419%EDGEWATER%'",
    "2025-CA-002956-C": "SITE_ADDR LIKE '414 CHICKADEE ST%'",
    "2025-CA-003450-C": "SITE_ADDR LIKE '4320 Cooper%'",
    "2025CA000832F": "SITE_ADDR LIKE '1201 WALTER AVE%'",
}

# Documented stale placeholders -- confirmed absent from Bid4Assets across
# multiple prior sessions. NEVER attempt to backfill; honest residual.
STALE_PLACEHOLDER_CASES = {"2024-CA-000470", "2024-TDD-000089"}


def _sb_headers(key):
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _gis_query(where):
    params = {
        "where": where,
        "outFields": "PIN,SITE_ADDR,TOTALAPPR,ASSEDVAL",
        "outSR": "4326",
        "f": "json",
        "returnGeometry": "true",
    }
    req = urllib.request.Request(
        GIS_BASE + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "curl/8"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    if "error" in data:
        raise RuntimeError(f"GIS query error: {data['error']} (where={where})")
    return data.get("features", [])


def _centroid(feature):
    geom = feature.get("geometry")
    if not geom or "rings" not in geom or not geom["rings"]:
        return None
    ring = geom["rings"][0]
    if not ring:
        return None
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return (sum(lats) / len(lats), sum(lons) / len(lons))


def resolve_and_patch(sb_url, sb_key, dry_run=True):
    sb_url = sb_url.rstrip("/")
    results = []
    for case_number, where in CASE_MATCH_QUERIES.items():
        feats = _gis_query(where)
        if len(feats) != 1:
            results.append((case_number, "unresolved", f"{len(feats)}_results_for_{where!r}"))
            continue
        attrs = feats[0]["attributes"]
        cen = _centroid(feats[0])

        # Fetch current row state so we never overwrite real values.
        get_url = (
            f"{sb_url}/rest/v1/multi_county_auctions?county=eq.{COUNTY}"
            f"&case_number=eq.{urllib.parse.quote(case_number)}"
            "&select=assessed_value,market_value,latitude,longitude,parcel_id"
        )
        req = urllib.request.Request(get_url, headers=_sb_headers(sb_key))
        with urllib.request.urlopen(req, timeout=30) as r:
            rows = json.loads(r.read())
        if not rows:
            results.append((case_number, "unresolved", "row_not_found_in_db"))
            continue
        cur = rows[0]

        body = {
            "parcel_id": attrs["PIN"],
            "parity_status": "matched_clean",
            "parity_source": PARITY_SOURCE,
        }
        if cur.get("assessed_value") is None and attrs.get("ASSEDVAL") is not None:
            body["assessed_value"] = attrs["ASSEDVAL"]
        if cur.get("market_value") is None and attrs.get("TOTALAPPR") is not None:
            body["market_value"] = attrs["TOTALAPPR"]
        if cur.get("latitude") is None and cen:
            body["latitude"], body["longitude"] = cen

        if dry_run:
            results.append((case_number, "dry_run", body))
            continue

        patch_url = (
            f"{sb_url}/rest/v1/multi_county_auctions?county=eq.{COUNTY}"
            f"&case_number=eq.{urllib.parse.quote(case_number)}"
        )
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            patch_url,
            data=data,
            headers={**_sb_headers(sb_key), "Prefer": "return=representation"},
            method="PATCH",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                result = json.loads(r.read())
                results.append((case_number, "patched", len(result)))
        except urllib.error.HTTPError as e:
            results.append((case_number, "failed", f"{e.code} {e.read().decode()[:200]}"))
    return results


if __name__ == "__main__":
    import sys

    dry = "--apply" not in sys.argv
    sb_url = os.environ["SUPABASE_URL"]
    sb_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    for case_number, status, detail in resolve_and_patch(sb_url, sb_key, dry_run=dry):
        print(f"{case_number}: {status} {detail}")
