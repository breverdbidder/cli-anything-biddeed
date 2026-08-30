#!/usr/bin/env python3
"""Gold Standard shard (dispatch 53580a68): pinellas G pk1000 residual fix.

TARGET: pinellas G (min(density_pct, far_pct, pk1000_pct) >= 95%).
Baseline (VERIFIED live via rpc/pencil_dod_evaluate_county('pinellas') at session
start): G FAIL metric=0.0, detail="density=94.3 far=100.0 pk1000=0.0".

BACKGROUND (confirmed live this session by joining multi_county_auctions.parcel_id
(county='pinellas') -> parcel_zones -> zoning_districts -> zone_standards, and by
reading the prior session's own migration comment, which documents the view's
"applicable" logic and its own investigation of every (jurisdiction_id, code) pair
touched by the preceding I-fix):

  Only ONE (jurisdiction_id, code) pair in the pinellas auction parcel universe is
  pk1000_applicable=true under v_zoning_district_applicability's fallback rule
  (category IN commercial/industrial/mixed-use AND name !~ 'pud', since this
  district's pk1000_regulated column is NULL):

    zoning_districts.id = 2559 -- jurisdiction_id=1094 (Indian Rocks Beach),
    code='B', name='Business District', category='Commercial', far_regulated=true.
    Linked parcel: 143001420300300210 (multi_county_auctions, zone_code='B' per
    parcel_zones, zone_name note: "(Indian Rocks Beach zoning class, per PPC layer)").

  zone_standards row id=6391 for this district already has max_far=0.55 and
  max_density_du_acre=18.00 (written by the prior session,
  20260827i_gold_standard_pinellas_g_i_regression_flum_backfill.sql), citing
  Indian Rocks Beach Code Sec. 110-131(6)(e)(3) and Sec. 110-131(6)(h). That
  session explicitly left parking_per_1000sf NULL because a good-faith search at
  the time only surfaced an unconfirmed WebSearch snippet ("1 space per 200 sq
  ft") with no verifiable section citation -- correctly not written per
  BLANK > WRONG.

THIS SESSION'S FIND (VERIFIED via a genuine primary-source government PDF, not a
mirror/snippet):

  City of Indian Rocks Beach ORDINANCE NO. 2011-12 (signed by Mayor-Commissioner
  R.B. Johnson, attested by City Clerk Deanne B. O'Reilly, approved as to form by
  City Attorney Maura J. Kiefer; published in the St. Petersburg Times Sept 7 and
  28, 2011; adopted on second/final reading Oct 11, 2011), fetched directly from
  the Municode ordinance archive (mcclibraryfunctions.azurewebsites.us/api/
  ordinanceDownload/12039/508371/pdf), SECTION 3, amending:

    Sec. 110-372. Required number of parking spaces; parking for compact cars.
    (15) Other businesses: "Whenever any building is erected, reconstructed or
    converted for business purposes, there shall be provided parking space in
    the ratio of one space for each 250 gross square feet of floorspace or
    fraction thereof, but in no case less than two parking spaces per business
    entity."

  This is the general/catch-all commercial parking standard governing the B
  (Business) district's retail/general-commercial uses (no more specific B-district
  retail provision was located after exhaustive search of Sec. 110-372(1)-(17),
  none of which name "retail" or "B district" specifically other than this
  catch-all). 1 space / 250 sq ft = 1000/250 = 4.0 spaces per 1,000 sq ft.

  SUPERSESSION CHECK: located exactly one later ordinance touching Sec. 110-371/
  110-372 -- ORDINANCE NO. 2014-30 (adopted second/final reading Jan 13, 2015).
  Read in full (3-page PDF, mcclibraryfunctions.azurewebsites.us/api/
  ordinanceDownload/12039/721911/pdf): it amends ONLY Sec. 110-371(b)(2) (removes
  the "change in use" / "increase in seats" trigger for additional parking). It
  does NOT touch Sec. 110-372 or any numeric ratio in subsection (15). No other
  ordinance amending 110-372(15) was found after multiple WebSearch/brightdata
  search-engine queries spanning 2011-2026. The 4.0/1000sf figure from Ord.
  2011-12 remains the last confirmed value for this subsection.

  NOT a generic default: this is a per-section, per-subsection cited ordinance
  value read directly from a signed/published municipal ordinance PDF, distinct
  from the "Synthetic"/(INFERRED)-tagged parking_per_1000sf=2.0 values found
  elsewhere in zone_standards for unrelated R-1 districts (those were NOT
  extended to this district -- they are a different, lower-confidence fleet
  pattern this script intentionally does not replicate).

WRITE: UPDATE zone_standards SET parking_per_1000sf = 4.00 WHERE id = 6391
  (zoning_district_id = 2559), only if currently NULL (idempotent).

RESIDUALS (explicitly not touched, no fabrication):
  - 635/RM (Pinellas County Unincorporated, zoning_district_id=13264): still has
    NO zone_standards row at all. This district is purely residential (density
    measured in du/acre only; RM has no FAR per Pinellas County Code, confirmed
    this session) so it is NOT pk1000_applicable or far_applicable under the
    view's category-fallback rule -- it does not affect this letter's pk1000 or
    far sub-metrics. It DOES remain a density-sub-metric residual (documented as
    genuinely blocked by an unreliable parcel geocode in the prior session's
    migration; not re-investigated this session, out of scope for the pk1000 gap
    this dispatch targets).
  - No other district in the pinellas auction universe is pk1000_applicable, so
    no further parking_per_1000sf writes are needed to move this sub-metric.

DoD:
  SELECT pct_pk1000_of_applicable FROM v_zoning_gold_standard_kpi_v3
    WHERE county='pinellas' -> expect 100.0 (was 0.0)
  RPC pencil_dod_evaluate_county('pinellas') -> G.metric = min(density, far,
    pk1000) -> expect min(94.3, 100.0, 100.0) = 94.3 (still FAIL, <95, but the
    LEAST-bound blocker moves from pk1000 to density -- density's own residual
    (635/RM) is out of scope for this dispatch and is left as an explicit
    residual, not silently dropped).
"""
import json
import os
import sys
import urllib.error
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY", "")
)
REST_BASE = f"{SUPABASE_URL}/rest/v1"

TARGET_ZONE_STANDARDS_ID = 6391
TARGET_ZONING_DISTRICT_ID = 2559
PARKING_PER_1000SF = 4.00
ORDINANCE_CITATION = (
    "Indian Rocks Beach Code of Ordinances Sec. 110-372(15) \"Other businesses\": "
    "\"Whenever any building is erected, reconstructed or converted for business "
    "purposes, there shall be provided parking space in the ratio of one space for "
    "each 250 gross square feet of floorspace or fraction thereof, but in no case "
    "less than two parking spaces per business entity.\" (= 4.0 spaces / 1,000 sq "
    "ft). Source: City of Indian Rocks Beach Ordinance No. 2011-12, Section 3, "
    "signed/attested/published (St. Petersburg Times, Sept 7 & 28 2011; adopted "
    "2nd reading Oct 11 2011). Fetched from primary municipal ordinance archive "
    "(mcclibraryfunctions.azurewebsites.us/api/ordinanceDownload/12039/508371/pdf). "
    "Supersession check: Ordinance No. 2014-30 (adopted 2nd reading Jan 13 2015) "
    "is the only later amendment located touching Sec. 110-371/372; it amends only "
    "110-371(b)(2) (change-in-use trigger), NOT 110-372(15) -- ratio unchanged. "
    "GS-PINELLAS-G-53580A68."
)


def rest_get(endpoint: str, params: str) -> list:
    url = f"{REST_BASE}/{endpoint}?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def rest_patch(endpoint: str, filter_params: str, body: dict) -> list:
    url = f"{REST_BASE}/{endpoint}?{filter_params}"
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body_bytes = r.read()
        return json.loads(body_bytes) if body_bytes else []


def rest_rpc(fn: str, args: dict):
    url = f"{REST_BASE}/rpc/{fn}"
    payload = json.dumps(args).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body_bytes = r.read()
        return json.loads(body_bytes) if body_bytes else {}


def main() -> int:
    if not SB_KEY:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY not set")
        return 1

    print("=" * 70)
    print("fix(pinellas-G/53580a68): parking_per_1000sf backfill for the sole")
    print("pk1000-applicable pinellas district (Indian Rocks Beach B, id=2559)")
    print("=" * 70)

    # ── Step 0: BEFORE state ─────────────────────────────────────────────
    print("\n-- BEFORE --")
    before_eval = rest_rpc("pencil_dod_evaluate_county", {"p_county": "pinellas"})
    print("pencil_dod_evaluate_county('pinellas').G:",
          json.dumps(before_eval.get("G", {})))

    before_kpi = rest_get(
        "v_zoning_gold_standard_kpi_v3",
        "select=*&county=eq.pinellas",
    )
    print("v_zoning_gold_standard_kpi_v3:", json.dumps(before_kpi))

    before_row = rest_get(
        "zone_standards",
        f"select=id,zoning_district_id,max_far,max_density_du_acre,"
        f"parking_per_1000sf,parking_per_unit&id=eq.{TARGET_ZONE_STANDARDS_ID}",
    )
    if not before_row:
        print(f"ERROR: zone_standards.id={TARGET_ZONE_STANDARDS_ID} not found")
        return 1
    print("zone_standards row BEFORE:", json.dumps(before_row[0]))

    if before_row[0].get("parking_per_1000sf") is not None:
        print(
            f"\nSKIP: parking_per_1000sf already set to "
            f"{before_row[0]['parking_per_1000sf']} -- not overwriting an existing "
            f"value. Nothing to do."
        )
        return 0

    if before_row[0]["zoning_district_id"] != TARGET_ZONING_DISTRICT_ID:
        print(
            f"ERROR: expected zoning_district_id={TARGET_ZONING_DISTRICT_ID}, "
            f"found {before_row[0]['zoning_district_id']} -- aborting, schema "
            f"drifted since investigation."
        )
        return 1

    # ── Step 1: PATCH the real ordinance value ──────────────────────────
    print(
        f"\n-- WRITE: zone_standards.id={TARGET_ZONE_STANDARDS_ID} "
        f"parking_per_1000sf = {PARKING_PER_1000SF} --"
    )
    patched = rest_patch(
        "zone_standards",
        f"id=eq.{TARGET_ZONE_STANDARDS_ID}&parking_per_1000sf=is.null",
        {
            "parking_per_1000sf": PARKING_PER_1000SF,
            "ordinance_section": ORDINANCE_CITATION,
            "source_url": (
                "https://mcclibraryfunctions.azurewebsites.us/api/"
                "ordinanceDownload/12039/508371/pdf"
            ),
        },
    )
    if not patched:
        print("ERROR: PATCH affected 0 rows (already non-null or id mismatch)")
        return 1
    print("PATCH result:", json.dumps(patched))

    # ── Step 2: AFTER verification ───────────────────────────────────────
    print("\n-- AFTER --")
    after_row = rest_get(
        "zone_standards",
        f"select=id,zoning_district_id,max_far,max_density_du_acre,"
        f"parking_per_1000sf,parking_per_unit,ordinance_section&"
        f"id=eq.{TARGET_ZONE_STANDARDS_ID}",
    )
    print("zone_standards row AFTER:", json.dumps(after_row[0]) if after_row else "MISSING")

    after_kpi = rest_get(
        "v_zoning_gold_standard_kpi_v3",
        "select=*&county=eq.pinellas",
    )
    print("v_zoning_gold_standard_kpi_v3 AFTER:", json.dumps(after_kpi))

    after_eval = rest_rpc("pencil_dod_evaluate_county", {"p_county": "pinellas"})
    print("pencil_dod_evaluate_county('pinellas').G AFTER:",
          json.dumps(after_eval.get("G", {})))

    print("\n" + "=" * 70)
    g_after = after_eval.get("G", {})
    pk1000_fixed = (
        after_kpi
        and after_kpi[0].get("pct_pk1000_of_applicable") is not None
        and float(after_kpi[0]["pct_pk1000_of_applicable"]) >= 95.0
    )
    print(f"pk1000 sub-metric fixed (>=95%): {'YES' if pk1000_fixed else 'NO'}")
    print(f"G overall pass: {g_after.get('pass')} (metric={g_after.get('metric')})")
    if not g_after.get("pass"):
        print(
            "NOTE: G may still show FAIL overall -- density sub-metric (94.3%, "
            "blocked by the separate 635/RM unreliable-geocode residual documented "
            "in the prior session) is a different, out-of-scope blocker. This "
            "script's job (pk1000 0.0->100.0) is verified above independently."
        )
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
