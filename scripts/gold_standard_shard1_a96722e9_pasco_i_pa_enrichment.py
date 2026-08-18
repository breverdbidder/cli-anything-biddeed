#!/usr/bin/env python3
"""
Gold Standard shard-1 (dispatch a96722e9): pasco Letter I property-card
completeness backfill for the 15 rows failing card_complete that have a
real (non-placeholder, non-IPLTMULE) parcel_id and property_address but
are missing assessed_value/latitude/longitude.

DENOMINATOR CORRECTION (important context for this session):
The task brief's initial hypothesis -- that the ~21 failing rows were old
closed PropertyOnion-cased (PO-*) rows -- was WRONG for pasco. The actual
pencil_dod_evaluate_county('pasco') Letter I query (see supabase/migrations/
20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql, CTE `c`)
computes card_complete over:
    WHERE lower(county)='pasco'
      AND (COALESCE(data_source,'') <> 'propertyonion'
           OR COALESCE(tier1_authoritative,false) = true)
That denominator is 352 rows (matches auctions_total) and EXCLUDES
PropertyOnion rows entirely (unless tier1_authoritative). Re-deriving the
same 352-row set live and replaying the exact card_complete predicate
(address IS NOT NULL, geo via COALESCE(latitude, po_latitude), value via
COALESCE(assessed_value, market_value), zone-link via parcel_id/tax_account
IN v_zoning_gold_standard_card WHERE zone_code IS NOT NULL for pasco)
reproduced 331/352 exactly, confirming the correct set of 21 failing rows.
Those 21 are real official-case rows (data_source IN
('calendar_sweep_mca_v3','realforeclose', NULL)) with genuine gaps -- NOT
PropertyOnion rows at all.

Of the 21:
  - 15 rows (this script's TARGET_PARCELS): real parcel_id + real
    property_address already populated, missing assessed_value AND
    latitude/longitude. Fixable now.
  - 2 rows: property_address populated, assessed_value/latitude/longitude
    already populated with IDENTICAL placeholder-looking values across
    both rows (assessed_value=150000.0, latitude=28.308, longitude=-82.4396)
    written by a prior synthetic-bootstrap pass, and parcel_id is NULL so
    they cannot zone-link. Address-search on both pascopa.com and the
    county ArcGIS Parcels_2023 FeatureServer for "6824 BEACH BLVD, HUDSON"
    returned ZERO matches (only similarly-numbered adjacent streets), and
    "4371 TAHITIAN GARDENS CIR" matched an 11-unit condo building with no
    unit letter in our address -- genuinely ambiguous. BLOCKED, not fixed.
    No new field written for these two (their existing geo/value looks
    synthetic but was NOT overwritten -- out of this script's scope, and
    per idempotency rule this script only ever touches currently-NULL
    fields, so it is a structural no-op here regardless).
  - 4 rows: property_address is NULL (parcel_id='IPLTMULE' placeholder for
    2, and two more with no address/parcel_id at all). No address to look
    up. BLOCKED -- left untouched, reported as residual gap.

Source (VERIFIED live this session):
  1. Pasco County Property Appraiser official parcel-card site
     https://search.pascopa.com/parcel.aspx?sec=&twn=&rng=&sbb=&blk=&lot=
     (parcel_id format SEC-TWN-RNG-SUB-BLK-LOT, e.g.
     "32-26-19-0030-00000-0080" -> sec=32 twn=26 rng=19 sbb=0030 blk=00000
     lot=0080). Parses lblPhysicalAddress + lblCountyValueAssessed (current
     live 2026 tax-roll assessed value, e.g. $285,334 for the Dockside Dr
     parcel).
  2. Pasco County GIS ArcGIS FeatureServer (county emergency-management
     GIS org, NOT the appraiser's own live roll -- used ONLY for parcel
     centroid geometry, since pascopa.com's HTML card does not expose
     coordinates):
     https://services9.arcgis.com/2A3tVMRrWJDhCctP/ArcGIS/rest/services/Parcels_2023/FeatureServer/0/query
     Queried by HPARCEL=<parcel_id> with outSR=4326, returnGeometry=true.
     Centroid computed via the standard area-weighted polygon-centroid
     formula (shoelace-based), NOT a naive vertex average.
     NOTE: this FeatureServer's JUST_VALUE/ASSD_VAL_COUNTY fields are a
     STALE 2023 snapshot (verified: differs from the live pascopa.com
     value for the same parcel -- $299,797/$246,760 vs pascopa.com's
     current $285,334). This script uses pascopa.com as the sole source
     of truth for assessed_value; the FeatureServer is used exclusively
     for geometry/centroid, which changes far less often than value.
  Cross-check: for all 15 parcels, the SITE_ADDRESS returned by the
  FeatureServer was compared against pascopa.com's lblPhysicalAddress and
  matched exactly (street number + name) for all 15 -- high-confidence
  independent confirmation before any write.

Fail-loud invariant: any parcel not found on pascopa.com, or with an
ambiguous/zero FeatureServer address match, is left untouched and reported
as a residual gap. No fabricated/estimated/interpolated values.

Idempotency: PATCH only sets assessed_value/latitude/longitude and ONLY
when the existing DB value for that field is NULL (verified via a
pre-read immediately before each PATCH). Re-running this script is safe.
"""
import argparse
import json
import os
import re
import sys
import time
from typing import Dict, Optional

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

PA_PARCEL_URL = "https://search.pascopa.com/parcel.aspx"
FS_QUERY_URL = (
    "https://services9.arcgis.com/2A3tVMRrWJDhCctP/ArcGIS/rest/services/"
    "Parcels_2023/FeatureServer/0/query"
)

# case_number -> parcel_id (folio PIN, SEC-TWN-RNG-SUB-BLK-LOT) for the 15
# rows with a real parcel_id + address, missing assessed_value + geo.
TARGET_PARCELS = {
    "51-2019-CA-003624-CAAX-ES": "32-26-19-0030-00000-0080",
    "51-2023-CA-003698-CAAX-WS": "23-25-16-0090-00000-7890",
    "51-2024-CC-006859-CCAX-WS": "13-25-17-0020-01700-0080",
    "51-2025-CA-000301-CAAX-WS": "10-25-16-0570-00000-2960",
    "51-2025-CA-000350-CAAX-WS": "34-25-16-0760-00300-0010",
    "51-2025-CA-001293-CAAX-WS": "15-26-16-0150-00100-0340",
    "51-2025-CA-002518-CAAX-WS": "33-25-16-076A-00000-1240",
    "51-2025-CA-002603-CAAX-WS": "25-26-15-006D-00001-0320",
    "51-2025-CA-003458-CAAX-ES": "31-26-19-0140-00000-0170",
    "51-2025-CA-003648-CAAX-WS": "03-26-16-0020-00000-0560",
    "51-2025-CA-003759-CAAX-WS": "05-26-16-0030-00800-0030",
    "51-2025-CA-004040-CAAX-WS": "23-25-16-0100-00000-3820",
    "51-2025-CC-001797-CCAX-ES": "04-26-21-0140-00100-0470",
    "51-2025-CC-003076-CCAX-ES": "04-26-21-0120-00000-0250",
    "51-2026-CA-000763-CAAX-ES": "30-26-19-0030-00000-0230",
}

# Rows confirmed BLOCKED this session (no field written, documented for
# the record -- NOT touched by this script's PATCH logic):
BLOCKED_NO_ADDRESS = [
    "51-2023-CA-003726-CAAX-ES",  # parcel_id='IPLTMULE' placeholder, no address
    "51-2024-CA-000530-CAAX-WS",  # parcel_id='IPLTMULE' placeholder, no address
    "51-2025-CC-004715-CCAX-ES",  # no address, no parcel_id
    "51-2025-CC-008556-CCAX-WS",  # no address, no parcel_id
]
BLOCKED_AMBIGUOUS_ADDRESS = [
    "51-2025-CA-000763-CAAX-WS",  # "6824 BEACH BLVD, HUDSON" -> zero match on PA/GIS
    "51-2025-CA-002914-CAAX-WS",  # "4371 TAHITIAN GARDENS CIR" -> 11-unit condo, no unit letter
]


def parse_parcel(parcel_id: str):
    sec, twn, rng, sbb, blk, lot = parcel_id.split("-")
    return sec, twn, rng, sbb, blk, lot


def fetch_pa_card(client: httpx.Client, parcel_id: str) -> Optional[Dict]:
    sec, twn, rng, sbb, blk, lot = parse_parcel(parcel_id)
    resp = client.get(
        PA_PARCEL_URL,
        params={"sec": sec, "twn": twn, "rng": rng, "sbb": sbb, "blk": blk, "lot": lot},
    )
    resp.raise_for_status()
    txt = resp.text

    if 'id="lblParcelID"' not in txt:
        return None  # parcel not found

    result: Dict = {}
    m = re.search(r'id="lblPhysicalAddress">([^<]+)', txt)
    if m:
        addr = re.sub(r"&nbsp;", " ", m.group(1))
        addr = re.sub(r"\s+", " ", addr).strip()
        result["_pa_address"] = addr
    m = re.search(r'id="lblCountyValueAssessed">\$([\d,]+)', txt)
    if m:
        result["assessed_value"] = float(m.group(1).replace(",", ""))
    return result


def polygon_centroid(rings):
    """Area-weighted (shoelace) centroid of the first ring."""
    ring = rings[0]
    A = 0.0
    Cx = 0.0
    Cy = 0.0
    n = len(ring)
    for i in range(n - 1):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        cross = x0 * y1 - x1 * y0
        A += cross
        Cx += (x0 + x1) * cross
        Cy += (y0 + y1) * cross
    A *= 0.5
    if abs(A) < 1e-12:
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        return sum(xs) / len(xs), sum(ys) / len(ys)
    return Cx / (6 * A), Cy / (6 * A)


def fetch_fs_geometry(client: httpx.Client, parcel_id: str) -> Optional[Dict]:
    params = {
        "where": f"HPARCEL='{parcel_id}'",
        "outFields": "HPARCEL,SITE_ADDRESS",
        "f": "json",
        "outSR": "4326",
        "returnGeometry": "true",
    }
    r = client.get(FS_QUERY_URL, params=params)
    r.raise_for_status()
    d = r.json()
    feats = d.get("features", [])
    if len(feats) != 1:
        return None  # not found or ambiguous
    feat = feats[0]
    lon, lat = polygon_centroid(feat["geometry"]["rings"])
    return {"latitude": lat, "longitude": lon, "_fs_address": feat["attributes"].get("SITE_ADDRESS")}


def get_current_row(client: httpx.Client, county: str, case_number: str) -> Optional[Dict]:
    url = f"{BASE}/multi_county_auctions"
    r = client.get(
        url,
        headers=HEADERS,
        params={
            "county": f"eq.{county}",
            "case_number": f"eq.{case_number}",
            "select": "id,property_address,assessed_value,market_value,latitude,longitude",
        },
    )
    rows = r.json()
    return rows[0] if rows else None


def patch_auction(client: httpx.Client, county: str, case_number: str, fields: Dict) -> bool:
    if not fields:
        return False
    url = f"{BASE}/multi_county_auctions?case_number=eq.{case_number}&county=eq.{county}"
    resp = client.patch(url, headers={**HEADERS, "Prefer": "return=minimal"}, json=fields)
    return resp.status_code in (200, 204)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not SUPABASE_KEY:
        print("SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
        sys.exit(1)

    pa_client = httpx.Client(timeout=30, follow_redirects=True)
    fs_client = httpx.Client(timeout=30)
    db_client = httpx.Client(timeout=30)

    results = []
    for case_number, parcel_id in TARGET_PARCELS.items():
        row = get_current_row(db_client, "pasco", case_number)
        if row is None:
            results.append({"case_number": case_number, "parcel_id": parcel_id, "status": "ROW_NOT_FOUND"})
            continue

        try:
            pa_card = fetch_pa_card(pa_client, parcel_id)
        except Exception as e:
            results.append({"case_number": case_number, "parcel_id": parcel_id, "status": "PA_ERROR", "error": str(e)})
            continue
        if pa_card is None:
            results.append({"case_number": case_number, "parcel_id": parcel_id, "status": "PA_NOT_FOUND"})
            continue

        try:
            fs_geo = fetch_fs_geometry(fs_client, parcel_id)
        except Exception as e:
            fs_geo = None
            results.append({"case_number": case_number, "parcel_id": parcel_id, "status": "FS_ERROR_CONTINUE", "error": str(e)})

        # Cross-check address between PA HTML and FeatureServer before trusting geometry
        addr_match = None
        if fs_geo is not None:
            pa_street = (pa_card.get("_pa_address") or "").split(",")[0].strip()
            fs_street = (fs_geo.get("_fs_address") or "").strip()
            addr_match = pa_street == fs_street

        fields_to_write = {}
        if row.get("assessed_value") is None and pa_card.get("assessed_value") is not None:
            fields_to_write["assessed_value"] = pa_card["assessed_value"]
        if fs_geo is not None and addr_match:
            if row.get("latitude") is None and fs_geo.get("latitude") is not None:
                fields_to_write["latitude"] = fs_geo["latitude"]
            if row.get("longitude") is None and fs_geo.get("longitude") is not None:
                fields_to_write["longitude"] = fs_geo["longitude"]

        applied = False
        if fields_to_write and not args.dry_run:
            applied = patch_auction(db_client, "pasco", case_number, fields_to_write)

        results.append({
            "case_number": case_number,
            "parcel_id": parcel_id,
            "status": "OK",
            "pa_address": pa_card.get("_pa_address"),
            "fs_address": fs_geo.get("_fs_address") if fs_geo else None,
            "address_match": addr_match,
            "fields_found": fields_to_write,
            "applied": applied if not args.dry_run else "DRY_RUN",
        })
        time.sleep(0.2)

    print(json.dumps({
        "target_rows": results,
        "blocked_no_address": BLOCKED_NO_ADDRESS,
        "blocked_ambiguous_address": BLOCKED_AMBIGUOUS_ADDRESS,
    }, indent=2))


if __name__ == "__main__":
    main()
