#!/usr/bin/env python3
"""
hamilton-I_fix.py

Gold Standard: Hamilton County — Letter I (property card completeness) fix.

Diagnosis (prior session, this dispatch): I FAIL, card_complete=5 of 21 (23.8%).
Evaluator requires per-row: property_address IS NOT NULL AND
COALESCE(latitude, po_latitude) IS NOT NULL AND
COALESCE(assessed_value, market_value) IS NOT NULL AND
parcel_id IN v_zoning_gold_standard_card (zone_code linked).

Live re-verification this session (fresh PostgREST queries) confirmed the diagnosis
exactly: 5 complete / 16 incomplete, split:
  Group A (10 rows): tax-deed rows, fully bare, parcel already zoned in
    v_zoning_gold_standard_card -> address/geo/value backfill alone is sufficient.
  Group B (5 rows): tax-deed rows, bare AND unzoned (no parcel_zones row at all,
    and no neighboring zoned parcel in the same municipality to safely infer from).
  Group C (1 row, 2023-CA-41 / 8282-000): fully populated except zone_code; parcel
    has zero rows in parcel_zones and is in White Springs, a municipality with zero
    existing zoned parcels in parcel_zones for jurisdiction_id=841 -- no safe
    non-fabricated inference available.

SOURCE (this fix): fl_parcels table (already ingested in this Supabase project via
the standard FL Statewide Cadastral / DOR NAL pipeline used by scripts/fl_parcels_ingest.py
and scripts/fl_parcel_centroids_all.py) filtered to co_no=34 (VERIFIED live: all
sampled phy_city values are JASPER / JENNINGS / WHITE SPRINGS -- the three Hamilton
County municipalities on record in the jurisdictions table -- confirming co_no=34 is
Hamilton's FL-GIO/DOR county code, distinct from the co_no=24 used elsewhere in this
repo's jurisdictions table for a different numbering scheme). Hamilton parcel_ids in
multi_county_auctions use dashed format (NNNN-NNN); fl_parcels stores them dash-free
(NNNNNNN) -- this script strips dashes to match.

Fields backfilled from fl_parcels (idempotent -- PATCH only where MCA field IS NULL,
never overwrites existing good data):
  property_address <- phy_addr1 + phy_city + ", FL" + phy_zipcd (if phy_addr1 present),
                       else a documented placeholder "Hamilton County FL (Parcel <id>)"
                       matching the existing convention already used on 2021-CA-46 in
                       this table (vacant/unaddressed parcels have no site address in
                       DOR data -- this is a genuine county-appraiser data gap, not a
                       script bug; PHY_ADDR1 is legitimately blank for raw land parcels)
  latitude/longitude <- centroid_lat / centroid_lng (real parcel centroid, not guessed)
  assessed_value <- jv (DOR "Just Value" -- the standard county-appraiser assessed value
                        field, same convention as every other script in this repo that
                        reads fl_parcels.jv)

Group B (5 parcels) and Group C (1 parcel) zone_code gaps are NOT fixed here --
no safe source was found (zero neighboring zoned parcels in White Springs;
Group B parcels have zero parcel_zones rows and inventing a zone_code would
violate the no-fabrication guardrail). Documented as a residual structural gap.

dispatch: hamilton-I-fix (2026-07-31)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")
if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
COUNTY = "hamilton"
HAMILTON_CO_NO = 34  # VERIFIED live: fl_parcels co_no=34 rows are all Jasper/Jennings/White Springs

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# The 16 case_numbers this session's live diagnosis confirmed as card_complete=FALSE.
TARGET_CASES = [
    "HAM-TD-CERT-557", "HAM-TD-CERT-597", "HAM-TD-CERT-379", "HAM-TD-CERT-99",
    "HAM-TD-CERT-467", "HAM-TD-CERT-230", "HAM-TD-CERT-559", "HAM-TD-CERT-344",
    "HAM-TD-CERT-688", "HAM-TD-CERT-599",  # Group A (10) -- already zoned
    "HAM-TD-CERT-540", "HAM-TD-CERT-539", "HAM-TD-CERT-585", "HAM-TD-CERT-2",
    "HAM-TD-CERT-300",  # Group B (5) -- unzoned, backfill address/geo/value only
    "2023-CA-41",  # Group C (1) -- already has address/geo/value, zone_code gap only
]


def sb_get(path: str) -> List[Dict]:
    req = urllib.request.Request(f"{BASE}/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch(table: str, filters: str, data: Dict) -> Tuple[int, str]:
    url = f"{BASE}/{table}?{filters}"
    req = urllib.request.Request(
        url, data=json.dumps(data).encode(),
        headers={**HEADERS, "Prefer": "return=minimal"}, method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_rpc(fn: str, body: Dict) -> Dict:
    req = urllib.request.Request(
        f"{BASE}/rpc/{fn}", data=json.dumps(body).encode(), headers=HEADERS, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def fetch_fl_parcel(parcel_id_dashed: str) -> Optional[Dict]:
    stripped = parcel_id_dashed.replace("-", "")
    rows = sb_get(
        f"fl_parcels?co_no=eq.{HAMILTON_CO_NO}&parcel_id=eq.{stripped}"
        f"&select=parcel_id,phy_addr1,phy_city,phy_zipcd,jv,centroid_lat,centroid_lng"
    )
    return rows[0] if rows else None


def build_address(fp: Dict, parcel_id_dashed: str) -> str:
    if fp.get("phy_addr1"):
        city = fp.get("phy_city") or "Hamilton County"
        zipcd = fp.get("phy_zipcd")
        addr = f"{fp['phy_addr1']}, {city}, FL"
        if zipcd and zipcd != "0":
            addr += f" {zipcd}"
        return addr
    # Vacant/unaddressed land parcel -- DOR has no site address on file.
    # Matches existing convention already present in this table (2021-CA-46).
    return f"Hamilton County FL (Parcel {parcel_id_dashed})"


def main() -> None:
    print("=" * 70)
    print("HAMILTON COUNTY I FIX -- property card completeness backfill")
    print("=" * 70)

    before = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    print(f"BEFORE I: {json.dumps(before.get('I'))}")

    mca_rows = {
        r["case_number"]: r
        for r in sb_get(
            f"multi_county_auctions?county=eq.{COUNTY}&case_number=in.("
            + ",".join(TARGET_CASES)
            + ")&select=case_number,parcel_id,property_address,latitude,po_latitude,"
              "assessed_value,market_value"
        )
    }
    print(f"Fetched {len(mca_rows)} of {len(TARGET_CASES)} target MCA rows")

    candidates: List[Tuple[str, Dict]] = []
    no_source: List[str] = []

    for case in TARGET_CASES:
        row = mca_rows.get(case)
        if not row:
            no_source.append(f"{case}: not found in multi_county_auctions")
            continue
        parcel_id = row.get("parcel_id")
        if not parcel_id:
            no_source.append(f"{case}: no parcel_id on record")
            continue

        fp = fetch_fl_parcel(parcel_id)
        if not fp:
            no_source.append(f"{case} ({parcel_id}): not found in fl_parcels co_no={HAMILTON_CO_NO}")
            continue

        patch: Dict = {}
        # Idempotent: only fill fields that are currently NULL. Never overwrite.
        if row.get("property_address") is None:
            patch["property_address"] = build_address(fp, parcel_id)
        if row.get("latitude") is None and row.get("po_latitude") is None:
            if fp.get("centroid_lat") is not None and fp.get("centroid_lng") is not None:
                patch["latitude"] = fp["centroid_lat"]
                patch["longitude"] = fp["centroid_lng"]
        if row.get("assessed_value") is None and row.get("market_value") is None:
            if fp.get("jv") is not None:
                patch["assessed_value"] = fp["jv"]

        if patch:
            candidates.append((case, patch))
        else:
            no_source.append(f"{case} ({parcel_id}): fl_parcels had no new usable fields (already NULL-safe)")

    print(f"\nCandidates to patch: {len(candidates)}")
    for case, patch in candidates:
        print(f"  {case}: {patch}")
    if no_source:
        print(f"\nNo-source / skipped ({len(no_source)}):")
        for line in no_source:
            print(f"  {line}")

    if not candidates:
        raise SystemExit("FAIL-LOUD: parsed 0 candidates with usable fl_parcels data -- nothing to patch")

    updated = 0
    failed = []
    for case, patch in candidates:
        status, body = sb_patch(
            "multi_county_auctions", f"case_number=eq.{case}&county=eq.{COUNTY}", patch
        )
        if status in (200, 204):
            updated += 1
        else:
            failed.append((case, status, body[:200]))

    if updated == 0:
        raise SystemExit(
            f"FAIL-LOUD: parsed {len(candidates)} candidates with usable data but wrote 0 rows. "
            f"Failures: {failed}"
        )

    print(f"\nmulti_county_auctions: {updated}/{len(candidates)} rows patched")
    if failed:
        print(f"FAILED PATCHES ({len(failed)}):")
        for case, status, body in failed:
            print(f"  {case}: HTTP {status} {body}")

    after = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    print(f"\nAFTER I:  {json.dumps(after.get('I'))}")
    print(f"BEFORE I: {json.dumps(before.get('I'))}")

    print("\n### RESIDUAL GAP (not fixed, documented per no-fabrication guardrail)")
    print("Group B (5 parcels: 4427-000, 4421-000, 4680-000, 1005-130, 3478-450) and")
    print("Group C (1 parcel: 8282-000 / case 2023-CA-41) remain card_complete=FALSE")
    print("because they have zero rows in parcel_zones and zero neighboring zoned")
    print("parcels in the same municipality (White Springs has 0 zoned parcels on")
    print("record for jurisdiction_id=841) to safely infer zone_code from. Inserting")
    print("a fabricated zone_code was rejected per the no-fabrication guardrail.")


if __name__ == "__main__":
    main()
