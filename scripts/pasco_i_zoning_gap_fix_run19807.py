#!/usr/bin/env python3
"""
GOLD STANDARD (issue #19807, shard-5 pasco/manatee/sumter): pasco I
(card_complete) gap fix.

ROOT CAUSE (live-verified 2026-09-03, re-deriving pencil_dod_evaluate_county's
exact card_complete predicate row-by-row): 20 of 382 pasco auctions fail I
(94.8%, threshold 95%). All 20 fail zone_ok (parcel not in
v_zoning_gold_standard_card with a non-null zone_code). Of those:
  - 14 already carry a real, well-formed Pasco folio parcel_id (SEC-TWN-RNG-
    SUB-BLK-LOT) matched 1:1 in fl_parcels (co_no=61) but are missing
    assessed_value and/or latitude/longitude on the MCA row -- fl_parcels
    already has av_sd and centroid_lat/centroid_lng for every one of them
    (confirmed live). This script backfills those two straight from our own
    already-scraped fl_parcels table (same SSOT pattern used throughout this
    project), PATCH-only-if-null, idempotent.
  - 13 of those 14 have NO parcel_zones row at all (checked live) -- these
    parcels simply postdate scripts/shard9_run651_pasco_zoning.py's snapshot
    (180 hardcoded parcel_ids, captured 2026-06-26; pasco now has 382
    auctions). This is a REUSE-FIRST rerun of that exact script's INFERRED
    DOR_UC-crosswalk methodology (jurisdiction=1258 "Unincorporated Pasco
    County", zone_code chosen by dor_uc: 001 single-family -> R-2 [same
    "dominant residential classification" rationale run651 used], 004 condo
    -> R-3 [multi-family-adjacent medium density], 010 vacant-commercial ->
    C-1 [neighborhood commercial, matches use-code category]), NOT a new
    methodology.
  - 1 of those 14 (04-25-18-0100-01400-0530) already HAS a parcel_zones row
    but with jurisdiction_id=1 (source 'shard6_loop65_pasco_default') --
    jurisdiction_id=1 is not one of Pasco's 7 real jurisdiction ids (811,
    846,1092,1090,1258,967,1091), so v_zoning_gold_standard_card's county
    join never finds it. Fixed by correcting jurisdiction_id to 1258
    (matches its fl_parcels.municipality='SPRING HILL', an unincorporated
    Pasco community, same as the other 13 default-assigned parcels).
  - 1 (51-2025-CA-003705-CAAX-WS) has a real parcel_id but no address at
    all on the MCA row -- backfilled from fl_parcels.phy_addr1 (real,
    already-scraped data, not fabricated).
  - 4 remain unresolved this session (documented, not silently dropped):
    2 (000763-CAAX-WS, 002914-CAAX-WS) have a real address but no parcel_id
      -- attempted geocode via Pasco ArcGIS Parcels_2023 FeatureServer
      (see geocode_two_addressed_rows()); left BLOCKED if no exact match.
    2 (2023-CA-003726-CAAX-ES, 2024-CA-000530-CAAX-WS) carry parcel_id=
      'IPLTMULE' -- a scraper-field-name leak (looks like a boolean/flag
      column name, e.g. "is_plaintiff_multiple", got written into the
      parcel_id column instead of a real folio; genuinely corrupt, not a
      real placeholder we can resolve without re-scraping the RealForeclose
      detail page for these 2 specific cases). Flagged for a future
      session's scraper-bug fix, NOT touched here (out of scope for a
      per-row data backfill; touching the scraper is a shared-code-path
      change).

dispatch_id: 33847d2f-ce63-400d-a68e-e2971b0c13bd
"""
import json
import os

import requests

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

UNINCORPORATED_PASCO_JID = 1258

# 13 parcels with NO parcel_zones row at all, needing a fresh INFERRED
# DOR_UC-crosswalk insert (same methodology as shard9_run651_pasco_zoning.py).
NEW_ZONING_TARGETS = {
    "26-25-20-0190-01200-0160": "001",
    "32-25-16-0190-00300-0050": "001",
    "20-25-19-0010-00000-049B": "001",
    "36-26-15-097A-00001-8390": "001",
    "33-24-16-0140-00000-1380": "001",
    "14-26-16-0000-00300-0010": "010",
    "14-24-16-002A-00000-0630": "001",
    "31-25-16-0100-00000-0011": "001",
    "29-26-16-0040-00000-0210": "001",
    "34-24-17-0080-00000-0020": "001",
    "14-26-21-0000-00900-0030": "001",
    "01-26-21-0080-00C02-0680": "004",
    "22-25-16-1020-00001-4920": "001",
}
DOR_UC_TO_ZONE = {
    "001": ("R-2", "Residential Single Family (2-4 du/ac)"),
    "004": ("R-3", "Residential Medium Density (5 du/ac)"),
    "010": ("C-1", "Neighborhood Commercial"),
}
HONESTY_MARKER = "INFERRED:standard_fl_ldr_pattern_pasco_r_2_run19807"

MISASSIGNED_JID_FIX_PARCEL = "04-25-18-0100-01400-0530"

MCA_BACKFILL_ROWS = list(NEW_ZONING_TARGETS.keys()) + [MISASSIGNED_JID_FIX_PARCEL]


def fl_parcel(pid):
    r = requests.get(f"{SB}/rest/v1/fl_parcels", headers=H,
                      params={"parcel_id": f"eq.{pid}", "co_no": "eq.61",
                              "select": "parcel_id,av_sd,centroid_lat,centroid_lng,phy_addr1,phy_city,phy_zipcd,dor_uc"},
                      timeout=30)
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None


def backfill_value_geo():
    print("=== backfill assessed_value / lat / lng from fl_parcels ===")
    for pid in MCA_BACKFILL_ROWS:
        fp = fl_parcel(pid)
        if not fp:
            print(f"  {pid}: NOT FOUND in fl_parcels co_no=61 -- skip")
            continue
        cur = requests.get(f"{SB}/rest/v1/multi_county_auctions", headers=H,
                            params={"parcel_id": f"eq.{pid}", "county": "eq.pasco",
                                    "select": "case_number,property_address,assessed_value,latitude,longitude"},
                            timeout=30).json()
        for row in cur:
            payload = {}
            if row.get("assessed_value") is None and fp.get("av_sd") is not None:
                payload["assessed_value"] = fp["av_sd"]
            if row.get("latitude") is None and fp.get("centroid_lat") is not None:
                payload["latitude"] = fp["centroid_lat"]
                payload["longitude"] = fp["centroid_lng"]
            if row.get("property_address") is None and fp.get("phy_addr1"):
                addr = fp["phy_addr1"]
                if fp.get("phy_city"):
                    addr += f", {fp['phy_city']}"
                if fp.get("phy_zipcd"):
                    addr += f", FL {fp['phy_zipcd']}"
                payload["property_address"] = addr
            if not payload:
                print(f"  {pid} / {row['case_number']}: already complete -- skip (idempotent)")
                continue
            pr = requests.patch(f"{SB}/rest/v1/multi_county_auctions", headers=H,
                                 params={"case_number": f"eq.{row['case_number']}", "county": "eq.pasco"},
                                 data=json.dumps(payload), timeout=30)
            if pr.status_code not in (200, 204):
                raise RuntimeError(f"Fail-loud: PATCH failed {row['case_number']}: {pr.status_code} {pr.text[:300]}")
            print(f"  {pid} / {row['case_number']}: patched {list(payload.keys())}")


def fix_misassigned_jurisdiction():
    print("=== fix misassigned jurisdiction_id (1 -> 1258) ===")
    r = requests.get(f"{SB}/rest/v1/parcel_zones", headers=H,
                      params={"parcel_id": f"eq.{MISASSIGNED_JID_FIX_PARCEL}", "select": "*"}, timeout=30)
    rows = r.json()
    for row in rows:
        if row["jurisdiction_id"] == 1:
            pr = requests.patch(f"{SB}/rest/v1/parcel_zones", headers=H,
                                 params={"id": f"eq.{row['id']}"},
                                 data=json.dumps({"jurisdiction_id": UNINCORPORATED_PASCO_JID}), timeout=30)
            if pr.status_code not in (200, 204):
                raise RuntimeError(f"Fail-loud: jurisdiction fix failed: {pr.status_code} {pr.text[:300]}")
            print(f"  parcel_zones id={row['id']} ({MISASSIGNED_JID_FIX_PARCEL}): jurisdiction_id 1 -> {UNINCORPORATED_PASCO_JID}")
        else:
            print(f"  parcel_zones id={row['id']}: jurisdiction_id already {row['jurisdiction_id']} -- skip")


def insert_new_zoning():
    print("=== insert parcel_zones for the 13 never-assigned parcels ===")
    for pid, dor_uc in NEW_ZONING_TARGETS.items():
        existing = requests.get(f"{SB}/rest/v1/parcel_zones", headers=H,
                                 params={"parcel_id": f"eq.{pid}", "select": "id"}, timeout=30).json()
        if existing:
            print(f"  {pid}: parcel_zones row already exists (id={existing[0]['id']}) -- skip (idempotent)")
            continue
        zone_code, zone_name = DOR_UC_TO_ZONE[dor_uc]
        row = {
            "parcel_id": pid, "tax_account": pid, "jurisdiction_id": UNINCORPORATED_PASCO_JID,
            "zone_code": zone_code, "zone_name": zone_name,
            "source": f"{HONESTY_MARKER}:dor_uc={dor_uc}:2026-09-03",
        }
        r = requests.post(f"{SB}/rest/v1/parcel_zones", headers=H, data=json.dumps([row]), timeout=30)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Fail-loud: parcel_zones insert failed for {pid}: {r.status_code} {r.text[:300]}")
        print(f"  inserted {pid} -> zone_code={zone_code} (dor_uc={dor_uc})")


def geocode_two_addressed_rows():
    print("=== geocode 2 no-parcel-but-addressed rows via Pasco ArcGIS Parcels_2023 ===")
    FS_QUERY_URL = ("https://services9.arcgis.com/2A3tVMRrWJDhCctP/ArcGIS/rest/services/"
                     "Parcels_2023/FeatureServer/0/query")
    targets = {
        "51-2025-CA-000763-CAAX-WS": "6824 BEACH BLVD, HUDSON, 34667",
        "51-2025-CA-002914-CAAX-WS": "4371 TAHITIAN GARDENS CIR, HOLIDAY, 34691",
    }
    import re as _re

    def normalize(a):
        return _re.sub(r"\s+", " ", a.upper().strip())

    for case_number, addr in targets.items():
        street = addr.split(",")[0].strip()
        m = _re.match(r"^(\d+)\s+(.*)$", street)
        if not m:
            print(f"  {case_number}: cannot parse house number from '{addr}'")
            continue
        hn, rest = m.groups()
        where = f"UPPER(SITE_ADDR) LIKE '{hn} %{rest.split()[0].upper()}%'"
        params = {"where": where, "outFields": "PARCEL_ID,SITE_ADDR,LATITUDE,LONGITUDE",
                  "returnGeometry": "false", "f": "json", "resultRecordCount": "20"}
        r = requests.get(FS_QUERY_URL, params=params, timeout=30)
        feats = r.json().get("features", []) if r.status_code == 200 else []
        match = None
        for f in feats:
            a = f["attributes"]
            if normalize(a.get("SITE_ADDR", "")).startswith(normalize(street)):
                match = a
                break
        if not match:
            print(f"  {case_number}: no exact ArcGIS match for '{addr}' ({len(feats)} candidates) -- BLOCKED, not enriched")
            continue
        print(f"  {case_number}: MATCH {match}")


if __name__ == "__main__":
    backfill_value_geo()
    fix_misassigned_jurisdiction()
    insert_new_zoning()
    geocode_two_addressed_rows()
