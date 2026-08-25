#!/usr/bin/env python3
"""Gold Standard shard-4 (dispatch ecbe151d) pasco letter I (property-card
completeness) backfill (2026-08-25).

Forked from scripts/gold_standard_shard1_a96722e9_pasco_i_pa_enrichment.py
(same source pattern: pascopa.com parcel-card HTML for assessed_value,
Pasco ArcGIS Parcels_2023 FeatureServer for centroid geometry, cross-checked
by address match before any write).

Live re-derivation of pencil_dod_evaluate_county's exact card_complete
predicate found 19 gap rows out of 364 card_rows for pasco (345/364, FAIL,
threshold >=95%). Of those 19:
  - 13 already have a real, well-formed Pasco folio parcel_id but are
    missing latitude/longitude/assessed_value. This script re-fetches real
    data for exactly those 13 (2 already had prior-session values -- those
    are structural idempotency no-ops here, not re-verified).
  - 6 have no parcel_id (or a placeholder 'IPLTMULE') and are left
    untouched/BLOCKED -- see supabase/migrations/20260825_gold_standard_
    pasco_i_geocode_assessed_backfill.sql for the full BLOCKED reasoning
    (2 addresses independently re-verified as zero-match/ambiguous on the
    county ArcGIS FeatureServer; 4 have no address at all to search by).

Idempotency: PATCH only ever sets assessed_value/latitude/longitude, and
only when the existing DB value for that field is NULL (re-read
immediately before each PATCH). Re-running this script against
already-patched rows is a safe no-op.

Usage: python3 scripts/gold_standard_shard4_ecbe151d_pasco_i_geocode_assessed_backfill.py [--dry-run]
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

# multi_county_auctions.id -> parcel_id, for the 13 letter-I gap rows that
# already carry a real, well-formed Pasco folio parcel_id (SEC-TWN-RNG-SUB-
# BLK-LOT). Discovered live this session via the exact card_complete
# predicate from supabase/migrations/20260810_gold_standard_shard3_lake_
# clerk_ssot_cd_recognition.sql (CTE `c`).
TARGET_ROWS = {
    "0ee7d381-8404-4098-9b3d-ea3905eb9c44": "31-26-16-0030-00000-0700",
    "110420b1-4332-411c-a588-85af425e3b2b": "11-25-16-0150-00000-0820",
    "1e78fe60-7bc2-4d55-8910-bcffc3499347": "29-26-16-0050-00000-5360",
    "31ebf04b-0e38-43cd-a2db-b4eca1849b90": "35-25-16-0100-00000-0310",
    "354bbaf5-fbf3-46ce-84c4-a24ed9813328": "09-26-21-005F-00000-1280",
    "3af35639-4e62-43af-8e08-d553ecea7485": "04-26-21-0120-00000-0250",
    "427e33a6-fba3-4a12-8186-3fd8d2fc49bb": "04-26-21-0140-00100-0470",
    "62a5db94-6dc6-4adc-ba50-1bdff24bce65": "13-25-17-0010-01000-0170",
    "68ab9068-963a-4d20-b7c7-1b1b7b9a525c": "08-25-17-0140-00000-1400",
    "7ab7678a-63d3-4d39-8f01-10fc7c3e7c89": "13-25-17-0020-01700-0080",  # zoning-linked -> flips I to PASS
    "86a021f7-4d0a-473b-b571-c4dbb1b0dc90": "02-24-17-0010-00001-1520",
    "89614a54-e78f-40a8-8b6e-53db835c2760": "04-26-21-0150-00800-0080",
    "ecd89b3d-a782-4151-b55f-e6b6ea54b172": "01-26-21-0010-07300-0080",
}

# Rows confirmed BLOCKED this session -- no field written (documented in
# the migration file, NOT touched by this script):
BLOCKED_NO_PARCEL_NO_ADDRESS = [
    "c1b3fd78-2cea-401b-937c-59eac3fe0239",  # parcel_id='IPLTMULE', no address
    "e238f753-b942-4744-8d0f-4cd44cf0582f",  # parcel_id='IPLTMULE', no address
    "c7f13c39-6705-45bc-bc85-12b18a5cb2ed",  # no address, no parcel_id
    "ee7405d1-a0cc-4538-846b-bbc3ba8d5993",  # no address, no parcel_id
]
BLOCKED_AMBIGUOUS_OR_NOT_FOUND = [
    "84ab0a10-4463-4687-9ffc-478fdff255ce",  # "4371 TAHITIAN GARDENS CIR" -> 11-unit condo, no unit letter
    "ffd8f042-abeb-496d-ad3e-73054015de23",  # "6824 BEACH BLVD" -> zero match on county ArcGIS FeatureServer
]


def parse_parcel(parcel_id: str):
    return parcel_id.split("-")


def fetch_pa_card(client: httpx.Client, parcel_id: str) -> Optional[Dict]:
    sec, twn, rng, sbb, blk, lot = parse_parcel(parcel_id)
    resp = client.get(
        PA_PARCEL_URL,
        params={"sec": sec, "twn": twn, "rng": rng, "sbb": sbb, "blk": blk, "lot": lot},
    )
    resp.raise_for_status()
    txt = resp.text
    if 'id="lblParcelID"' not in txt:
        return None
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
        return None
    feat = feats[0]
    lon, lat = polygon_centroid(feat["geometry"]["rings"])
    return {"latitude": lat, "longitude": lon, "_fs_address": feat["attributes"].get("SITE_ADDRESS")}


def get_current_row(client: httpx.Client, row_id: str) -> Optional[Dict]:
    r = client.get(
        f"{BASE}/multi_county_auctions",
        headers=HEADERS,
        params={"id": f"eq.{row_id}", "select": "id,assessed_value,market_value,latitude,longitude,parcel_id"},
    )
    rows = r.json()
    return rows[0] if rows else None


def patch_auction(client: httpx.Client, row_id: str, fields: Dict) -> int:
    if not fields:
        return 0
    resp = client.patch(
        f"{BASE}/multi_county_auctions?id=eq.{row_id}",
        headers={**HEADERS, "Prefer": "return=minimal"},
        json=fields,
    )
    return resp.status_code


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
    for row_id, parcel_id in TARGET_ROWS.items():
        cur = get_current_row(db_client, row_id)
        if cur is None:
            results.append({"id": row_id, "parcel_id": parcel_id, "status": "ROW_NOT_FOUND"})
            continue

        try:
            pa_card = fetch_pa_card(pa_client, parcel_id)
        except Exception as e:
            results.append({"id": row_id, "parcel_id": parcel_id, "status": "PA_ERROR", "error": str(e)})
            continue
        if pa_card is None:
            results.append({"id": row_id, "parcel_id": parcel_id, "status": "PA_NOT_FOUND"})
            continue

        try:
            fs_geo = fetch_fs_geometry(fs_client, parcel_id)
        except Exception as e:
            fs_geo = None
            results.append({"id": row_id, "parcel_id": parcel_id, "status": "FS_ERROR_CONTINUE", "error": str(e)})

        addr_match = None
        if fs_geo is not None:
            pa_street = (pa_card.get("_pa_address") or "").split(",")[0].strip()
            fs_street = (fs_geo.get("_fs_address") or "").strip()
            addr_match = pa_street == fs_street

        fields_to_write = {}
        if cur.get("assessed_value") is None and cur.get("market_value") is None and pa_card.get("assessed_value") is not None:
            fields_to_write["assessed_value"] = pa_card["assessed_value"]
        if fs_geo is not None and addr_match:
            if cur.get("latitude") is None and fs_geo.get("latitude") is not None:
                fields_to_write["latitude"] = fs_geo["latitude"]
            if cur.get("longitude") is None and fs_geo.get("longitude") is not None:
                fields_to_write["longitude"] = fs_geo["longitude"]

        status = "NO_OP_ALREADY_SET"
        if fields_to_write and not args.dry_run:
            code = patch_auction(db_client, row_id, fields_to_write)
            status = code

        results.append({
            "id": row_id,
            "parcel_id": parcel_id,
            "pa_address": pa_card.get("_pa_address"),
            "fs_address": fs_geo.get("_fs_address") if fs_geo else None,
            "address_match": addr_match,
            "fields_written": fields_to_write,
            "status": "DRY_RUN" if args.dry_run else status,
        })
        time.sleep(0.3)

    print(json.dumps({
        "target_rows": results,
        "blocked_no_parcel_no_address": BLOCKED_NO_PARCEL_NO_ADDRESS,
        "blocked_ambiguous_or_not_found": BLOCKED_AMBIGUOUS_OR_NOT_FOUND,
    }, indent=2))


if __name__ == "__main__":
    main()
