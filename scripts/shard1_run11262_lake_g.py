#!/usr/bin/env python3
"""
Lake G: fix the "unmatched zone_code defaults to pk1000_applicable=true" bug
(fleet-wide precedent: supabase/migrations/20260718f_gold_standard_shard3_seminole_g_pk1000_applicability_fix_run26f01b9b.sql)
hitting 2 Tavares zone codes with no zoning_districts row.

Live-verified this session (dispatch 7bcb4434, loop run 11262):
  - pencil_dod_evaluate_county('lake') G detail = "density=91.4 far=82.4 pk1000=25.0"
  - v_zoning_district_applicability join over all 114 lake parcel_zones rows
    yields exactly 4 pk1000_applicable parcels (denominator=4, numerator=1 -> 25.0%)
  - 2 of those 4 (Tavares jurisdiction_id=926, zone_code='R-6' and 'RSF-2') have
    ZERO matching zoning_districts row, so they fall into the KPI's
    COALESCE(pk1000_applicable, true) unmatched-code fallback and are wrongly
    counted as pk1000-applicable-but-missing.
  - parcel_zones.zone_name for both is unambiguously residential
    ('Urban Residential' / 'Single-Family Residential (Tavares)'),
    source='tavares_cityzoning_gis_2026-08-11' (fresh, authoritative GIS).
  - Tavares' existing district rows for the SAME jurisdiction (RSF-1 id=13016,
    RMF-2/RMF-3/RMH-S ids=13731/13730/13732) are all category='residential'
    (lowercase, 3 of 4) / 'Residential' (1 of 4) -- this fix matches the
    majority lowercase convention.

Fix: register 2 structural-placeholder zoning_districts rows (category only,
no far/density/parking value fabricated) so these codes stop hitting the
unmatched-code fallback and correctly resolve via the existing category
formula (residential != commercial/industrial/mixed-use -> pk1000_applicable
false). This drops the pk1000 denominator 4->2, numerator stays 1 (Groveland
Town Core) -> pk1000 25.0% -> 50.0%.

Idempotency guard: abort with no writes if either code already exists for
jurisdiction_id=926 (confirmed empty live this session before writing this
script).

Residual/out of scope: Leesburg C-1 parking_per_1000sf remains NULL/BLOCKED
(Municode 403 x3, zoneomics.com mirror missing the ratio table, 5 WebSearch
variants empty) -- would be needed to push pk1000 from 50% toward 100%, not
attempted here. density=91.4 and far=82.4 are untouched by this fix and
remain the larger blockers for G to reach PASS (>=95% all three).

dispatch_id: 7bcb4434-c068-4a5d-b140-0dcf65c8c87f (loop run 11262, pair lake-G)
"""
import json
import os
import sys

import httpx

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

JURISDICTION_ID = 926  # Tavares

NEW_ROWS = [
    {
        "jurisdiction_id": JURISDICTION_ID,
        "code": "R-6",
        "name": "R-6 Urban Residential (Tavares)",
        "category": "residential",
        "description": (
            "City of Tavares zoning district, GIS-sourced 2026-08-11 "
            "(parcel_zones.source='tavares_cityzoning_gis_2026-08-11', "
            "zone_name='Urban Residential'). Structural placeholder registering "
            "category only -- no far/density/parking value fabricated. Purpose: "
            "stop this code from hitting v_zoning_district_applicability's "
            "unmatched-code COALESCE(pk1000_applicable, true) fallback, which "
            "was wrongly counting it as pk1000-applicable-but-missing. 'Urban "
            "Residential' naming matches Tavares' existing RSF-1/RMF-2/RMF-3/"
            "RMH-S district rows, all correctly category=residential."
        ),
        "far_regulated": None,
        "density_regulated": None,
        "pk1000_regulated": None,
    },
    {
        "jurisdiction_id": JURISDICTION_ID,
        "code": "RSF-2",
        "name": "RSF-2 Single-Family Residential (Tavares)",
        "category": "residential",
        "description": (
            "City of Tavares zoning district, GIS-sourced 2026-08-11 "
            "(parcel_zones.source='tavares_cityzoning_gis_2026-08-11', "
            "zone_name='Single-Family Residential (Tavares)'). Structural "
            "placeholder registering category only -- no far/density/parking "
            "value fabricated. Same rationale/precedent as R-6 sibling row in "
            "this same fix."
        ),
        "far_regulated": None,
        "density_regulated": None,
        "pk1000_regulated": None,
    },
]


def main():
    with httpx.Client(timeout=30) as client:
        # Idempotency guard
        r = client.get(
            f"{BASE}/zoning_districts",
            headers=HEADERS,
            params={
                "jurisdiction_id": f"eq.{JURISDICTION_ID}",
                "code": "in.(R-6,RSF-2)",
                "select": "id,code",
            },
        )
        if r.status_code != 200:
            raise SystemExit(f"Guard query FAILED: {r.status_code} {r.text[:300]}")
        existing = r.json()
        if existing:
            print(f"ABORT: {len(existing)} row(s) already exist for jurisdiction_id={JURISDICTION_ID} "
                  f"code in (R-6,RSF-2): {existing} -- no writes made")
            sys.exit(0)
        print("Guard: 0 existing rows for (926, R-6/RSF-2) -- proceeding with insert")

        r2 = client.post(
            f"{BASE}/zoning_districts",
            headers=HEADERS,
            content=json.dumps(NEW_ROWS),
        )
        if r2.status_code not in (200, 201):
            raise SystemExit(f"Insert FAILED: {r2.status_code} {r2.text[:500]}")
        inserted = r2.json()
        print(f"zoning_districts: {len(inserted)} rows inserted")
        for row in inserted:
            print(f"  id={row.get('id')} code={row.get('code')} category={row.get('category')}")

        if len(inserted) != 2:
            raise SystemExit(
                f"Fail-loud guard: expected 2 rows inserted, got {len(inserted)} -- "
                f"aborting before verification claim"
            )

    # Verify via live RPC
    r3 = httpx.post(
        f"{BASE}/rpc/pencil_dod_evaluate_county",
        headers=HEADERS,
        content=json.dumps({"p_county": "lake"}),
        timeout=30,
    )
    if r3.status_code != 200:
        raise SystemExit(f"Post-fix verification RPC FAILED: {r3.status_code} {r3.text[:300]}")
    result = r3.json()
    g = result.get("G", {})
    print(f"\nPOST-FIX pencil_dod_evaluate_county('lake') G: {json.dumps(g)}")


if __name__ == "__main__":
    main()
