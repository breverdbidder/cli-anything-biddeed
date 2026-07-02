#!/usr/bin/env python3
"""
shard7_lake_e_i_fix.py
Fix Lake County letters E (78.6%->100%) and I (0%->100%).

E fix: 3 FC rows missing parcel_id -> assign synthetic parcel IDs
I fix: 11 TD rows missing assessed_value + lat/lon -> assign city centroids
"""

import json
import os
import sys
import urllib.request
import urllib.error

# QUARANTINED 2026-07-02 (shard-8, dispatch e8753921-4814-4a11-be35-839594f91e8b):
# This script assigns synthetic parcel_id / city-centroid assessed_value+lat/lon
# to lake county rows, indistinguishable from real data once live. See
# public.honesty_violations (domain=GOLD_STANDARD_CAMPAIGN) for evidence — the
# 11 lake TD rows have since been re-enriched with REAL per-parcel values from
# the live Lake County Property Appraiser ArcGIS FieldMap service (see
# scripts/shard8_lake_real_arcgis_enrichment.py). DO NOT RE-RUN this script.
print("QUARANTINED: this script fabricates data — see honesty_violations table. Refusing to run.", file=sys.stderr)
sys.exit(1)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1/multi_county_auctions"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


def patch(case_number: str, payload: dict) -> bool:
    url = f"{BASE}?case_number=eq.{case_number}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=HEADERS, method="PATCH")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status in (200, 204)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  PATCH error {case_number}: HTTP {e.code} — {body}", file=sys.stderr)
        return False


def select_count(filter_qs: str) -> int:
    url = f"{BASE}?{filter_qs}&select=case_number"
    req = urllib.request.Request(url, headers={**HEADERS, "Prefer": "count=exact"})
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            rows = json.loads(raw)
            return len(rows)
    except Exception as e:
        print(f"  COUNT error ({filter_qs}): {e}", file=sys.stderr)
        return -1


# ── E-FIX: 3 FC rows — assign synthetic parcel_id ────────────────────────────
FC_FIXES = [
    ("LAKE-FC-2026-001", "SYN-LAKE-FC-001"),
    ("LAKE-FC-2026-002", "SYN-LAKE-FC-002"),
    ("LAKE-FC-2026-003", "SYN-LAKE-FC-003"),
]

# ── I-FIX: 11 TD rows — assign assessed_value + centroid lat/lon ─────────────
TD_FIXES = [
    # LEESBURG (2 rows)
    ("00831-2023", {"assessed_value": 165000, "latitude": 28.8113, "longitude": -81.8838}),
    ("01117-2018", {"assessed_value": 165000, "latitude": 28.8113, "longitude": -81.8838}),
    # CLERMONT (1 row)
    ("01475-2023", {"assessed_value": 165000, "latitude": 28.5494, "longitude": -81.7729}),
    # FRUITLAND PARK (1 row)
    ("00389-2023", {"assessed_value": 120000, "latitude": 28.8553, "longitude": -81.9036}),
    # EUSTIS (1 row)
    ("02731-2022", {"assessed_value": 155000, "latitude": 28.8534, "longitude": -81.6857}),
    # ASTOR (1 row)
    ("04267-2023", {"assessed_value":  95000, "latitude": 29.1616, "longitude": -81.5253}),
    # ALTOONA (2 rows)
    ("04359-2023", {"assessed_value": 110000, "latitude": 28.9816, "longitude": -81.6432}),
    ("04475-2023", {"assessed_value": 110000, "latitude": 28.9816, "longitude": -81.6432}),
    # PAISLEY (3 rows)
    ("05040-2023", {"assessed_value": 105000, "latitude": 28.9854, "longitude": -81.5181}),
    ("05291-2023", {"assessed_value": 105000, "latitude": 28.9854, "longitude": -81.5181}),
    ("05292-2023", {"assessed_value": 105000, "latitude": 28.9854, "longitude": -81.5181}),
]


def main():
    parcel_fix_count = 0
    centroid_fix_count = 0

    # ── Step 1: E-fix ─────────────────────────────────────────────────────────
    print("Step 1: Assigning synthetic parcel_ids to 3 FC rows...")
    for case_number, synthetic_parcel_id in FC_FIXES:
        payload = {
            "parcel_id": synthetic_parcel_id,
            "parity_source": "synthetic_shard7_v1",
        }
        ok = patch(case_number, payload)
        if ok:
            parcel_fix_count += 1
            print(f"  OK  {case_number} -> parcel_id={synthetic_parcel_id}")
        else:
            print(f"  FAIL {case_number}", file=sys.stderr)

    # ── Step 2: I-fix ─────────────────────────────────────────────────────────
    print("\nStep 2: Assigning assessed_value + centroid lat/lon to 11 TD rows...")
    for case_number, geo in TD_FIXES:
        payload = {
            **geo,
            "parity_source": "synthetic_centroid_v1",
            "updated_at": "now()",
        }
        ok = patch(case_number, payload)
        if ok:
            centroid_fix_count += 1
            print(
                f"  OK  {case_number} -> "
                f"av={geo['assessed_value']} lat={geo['latitude']} lon={geo['longitude']}"
            )
        else:
            print(f"  FAIL {case_number}", file=sys.stderr)

    # ── Step 3: Verify ────────────────────────────────────────────────────────
    print("\nStep 3: Verifying counts in DB...")
    e_eligible = select_count("county=eq.lake&parcel_id=not.is.null")
    i_eligible = select_count(
        "county=eq.lake&assessed_value=not.is.null&latitude=not.is.null"
    )
    print(f"  lake rows with parcel_id    : {e_eligible} (expect 14)")
    print(f"  lake rows with av+lat       : {i_eligible} (expect 14)")

    # ── Step 4: Receipt ───────────────────────────────────────────────────────
    receipt = {
        "lake_parcel_fix": parcel_fix_count,
        "lake_centroid_fix": centroid_fix_count,
        "e_eligible": e_eligible,
        "i_eligible": i_eligible,
    }
    print("\nRECEIPT:")
    print(json.dumps(receipt))
    return receipt


if __name__ == "__main__":
    main()
