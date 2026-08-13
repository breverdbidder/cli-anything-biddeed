#!/usr/bin/env python3
"""
Gold Standard shard-2, Gulf County Letter I (property card completeness),
dispatch 72cb38f7.

Root cause (VERIFIED this session):
  - Gulf I = 86.7% (13/15 card_complete)
  - 2 rows have every field the v_zoning_gold_standard_card view needs EXCEPT
    a parcel_zones row with a non-null zone_code:
      1. case_number=2025-010, parcel_id=05762000R, "256 AVE C"
      2. case_number=2025-018, parcel_id=05004050R, "KNOWLES AVE"

Research performed (VERIFIED):
  - Gulf County GIS (arcgis5.roktech.net/gulf/GoMaps4/MapServer) confirmed
    both parcel_ids via the "Parcels" layer (id=12), PIN_NODELIM exact match,
    ST_CITY=PORT ST JOE for both -> jurisdiction = Port St. Joe (id=952),
    confirmed independently via the "City Limits of Port St Joe" layer (id=7)
    spatial-intersects both lat/lon points.
  - Gulf County GIS has NO dedicated zoning layer (only "Land Use"/FLU,
    layer 40), so county GIS alone cannot supply a real zone_code here.
  - Real zone_code per parcel found via address-exact secondary sources,
    cross-checked against the official City of Port St Joe Zoning Map
    (cityofportstjoe.com, ZONING_2010-120926-V9, R-1/R-2A/R-2B/R-3/... legend)
    and the Gulf County Clerk's official Property Information Report (PIR)
    for legal-description confirmation:
      * 05762000R (256 Ave C): Redfin MLS# 990187, exact address match,
        listing text states "R-2B zoning" + "Future Land Use of Mixed Use",
        X-Flood Zone, ~50x118 ft lot -- consistent with Gulf GIS legal
        description "N 79 ft of Lot 20, Block 1004, Port Saint Joe, PB1 PG17".
        Source: https://www.redfin.com/FL/Port-Saint-Joe/256-Avenue-C-32456/home/138408555
      * 05004050R (Knowles Ave): Gulf County Clerk PIR
        (https://www.gulfclerk.com/uploads/PIR05004-050R-1.pdf) confirms legal
        description "Lots 11-20, Block 44, St Joseph's Addition Unit No. 3,
        PB1 PG32" -- matches Gulf GIS subdivision/block/lot exactly (SUBD=5045,
        BLOCK=44). Zoning found via Corcoran/98 Real Estate Group listing for
        this same parcel (TBD Knowles Avenue, 3.2ac vacant, "zoning on R-3 is
        flexible ... single family home to a triplex ... four additional lots
        could be available") -- matches parcel size (3.22 acres) and multi-lot
        legal description exactly.
        Source: https://www.corcoran.com/listing/for-sale/tbd-knowles-avenue-port-st-joe-fl-32456/87834240/regionId/104

  NOTE ON CONFIDENCE: both zone codes are corroborated by an address-exact
  match to a specific listing/legal description (not a generic area guess),
  but the listing sources are secondary (MLS/broker text), not a government
  zoning API (Gulf County's own GIS/appraiser sites are Cloudflare-gated and
  returned HTTP 403 for every endpoint tried this session: qpublic.net,
  beacon.schneidercorp.com, gulfpa.com). Tagged INFERRED per HONESTY PROTOCOL
  -- not fabricated, but not a primary-government zoning record either.

This script:
1. Verifies the 2 gap parcels still have no parcel_zones row for jurisdiction
   952 (idempotency guard).
2. Inserts parcel_zones rows with the verified zone_code + a fully-cited
   source string.
3. Does not touch zoning_districts / zone_standards -- letter I only
   requires zone_code IS NOT NULL, not FAR/setback/density coverage.

honesty_markers:
  - CONFIRMED: jurisdiction (Port St Joe) via county GIS parcel + city-limits
    spatial intersect; legal description match via Gulf Clerk PIR
  - INFERRED: zone_code itself, from address-exact MLS/broker listings
    (government zoning source was unreachable, not merely unresearched)

Author: Claude (Gold Standard shard-2, dispatch 72cb38f7, 2026-08-13)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)

DISPATCH_ID = "72cb38f7"
PIPELINE_RUN_ID = f"gold_standard_shard2_gulf_i_dispatch{DISPATCH_ID}"
JURISDICTION_ID_PSJ = 952  # Port St. Joe (VERIFIED via jurisdictions table)
DRY_RUN = "--apply" not in sys.argv

TARGET_ROWS = [
    {
        "parcel_id": "05762000R",
        "jurisdiction_id": JURISDICTION_ID_PSJ,
        "zone_code": "R-2B",
        "zone_name": "R-2B Medium Density Residential District",
        "source": (
            f"{PIPELINE_RUN_ID}/redfin_mls_990187_address_exact:"
            "https://www.redfin.com/FL/Port-Saint-Joe/256-Avenue-C-32456/home/138408555"
            " (case_number=2025-010, 256 AVE C, X-Flood Zone, ~50x118ft, FLU=Mixed Use;"
            " cross-checked vs City of Port St Joe official Zoning Map"
            " cityofportstjoe.com/pdf/maps/City Zoning Map Sep-26-2012"
            " and Gulf GIS parcel legal desc N79ft Lot20 Blk1004 PB1 PG17)"
        ),
    },
    {
        "parcel_id": "05004050R",
        "jurisdiction_id": JURISDICTION_ID_PSJ,
        "zone_code": "R-3",
        "zone_name": "R-3 Residential District",
        "source": (
            f"{PIPELINE_RUN_ID}/corcoran_98realestategroup_listing_legal_desc_exact:"
            "https://www.corcoran.com/listing/for-sale/tbd-knowles-avenue-port-st-joe-fl-32456/87834240/regionId/104"
            " (case_number=2025-018, Knowles Ave, 3.2ac, 'R-3 ... single family"
            " home to a triplex'; legal desc confirmed via Gulf County Clerk PIR"
            " gulfclerk.com/uploads/PIR05004-050R-1.pdf: Lots 11-20 Blk 44"
            " St Joseph's Addition Unit 3 PB1 PG32, matches Gulf GIS"
            " SUBD=5045 BLOCK=44 exactly)"
        ),
    },
]


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, level: str = "INFO", tag: str = "UNTESTED"):
    print(f"[{ts()}] {level} [{tag}]: {msg}", flush=True)


def sb_headers(extra: dict | None = None) -> dict:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def rest_get(path: str) -> list:
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        log(f"rest_get {path} HTTP {e.code}: {body[:300]}", "WARN", "VERIFIED")
        return []
    except Exception as e:
        log(f"rest_get {path} failed: {e}", "WARN", "VERIFIED")
        return []


def rest_post(path: str, rows: list) -> int:
    if DRY_RUN:
        log(f"DRY-RUN POST {path} ({len(rows)} rows) -- pass --apply to write", "INFO", "UNTESTED")
        return 0
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    body = json.dumps(rows).encode()
    req = urllib.request.Request(
        url, data=body, headers=sb_headers({"Prefer": "return=representation"}), method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
            return len(resp)
    except urllib.error.HTTPError as e:
        body_text = e.read()
        log(f"rest_post {path} HTTP {e.code}: {body_text[:400]}", "ERROR", "VERIFIED")
        return 0
    except Exception as e:
        log(f"rest_post {path} failed: {e}", "ERROR", "VERIFIED")
        return 0


def main():
    if not SUPABASE_KEY:
        log("SUPABASE_KEY not set -- aborting", "ERROR", "VERIFIED")
        sys.exit(1)

    log(f"Gold Standard shard-2 Gulf I fix -- dispatch {DISPATCH_ID}", "INFO", "UNTESTED")
    log(f"DRY_RUN={DRY_RUN}", "INFO", "UNTESTED")

    parcel_ids = [r["parcel_id"] for r in TARGET_ROWS]
    in_clause = ",".join(parcel_ids)
    existing = rest_get(
        f"parcel_zones?parcel_id=in.({urllib.parse.quote(in_clause)})&select=parcel_id,jurisdiction_id,zone_code"
    )
    existing_ids = {r["parcel_id"] for r in existing}
    log(f"Existing parcel_zones rows for target parcels: {existing}", "INFO", "VERIFIED")

    insert_rows = [r for r in TARGET_ROWS if r["parcel_id"] not in existing_ids]
    if not insert_rows:
        log("Both parcels already have parcel_zones rows -- nothing to do", "INFO", "VERIFIED")
        sys.exit(0)

    log(f"Rows to insert: {len(insert_rows)}", "INFO", "VERIFIED")
    for r in insert_rows:
        log(f"  {r['parcel_id']} -> zone_code={r['zone_code']} jurisdiction_id={r['jurisdiction_id']}", "INFO", "UNTESTED")

    n = rest_post("parcel_zones", insert_rows)
    log(f"Inserted {n} parcel_zones rows", "INFO", "VERIFIED" if not DRY_RUN else "UNTESTED")

    print("\n### SQL VERIFICATION -- GULF LETTER I PROPERTY-CARD FIX (dispatch 72cb38f7)")
    print(f"Timestamp UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"DRY_RUN: {DRY_RUN}")
    print(f"Rows inserted: {n}")
    print("\nVerification query:")
    print(
        "  SELECT parcel_id, jurisdiction_id, zone_code, source FROM parcel_zones "
        "WHERE parcel_id IN ('05762000R','05004050R');"
    )
    print("  SELECT public.pencil_dod_evaluate_county('gulf');")


if __name__ == "__main__":
    main()
