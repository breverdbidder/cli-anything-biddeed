#!/usr/bin/env python3
"""Gold Standard shard-3 (dispatch 0c873526-996a-4f5d-9123-99836d1d585f): Lee
County letter I (property card completeness) zone-linkage backfill.

BASELINE (live pencil_dod_evaluate_county, verified this session):
  I: card_complete=309 of 327 (94.5%) -- FAIL, need >=95% (311/327)

ROOT CAUSE: 7 rows in the I population have parcel_id set but fail the
zone_code join against v_zoning_gold_standard_card. Of these:
  - 3 are unresolvable placeholder parcel_id values ("MULTIPLE PARCEL",
    "TIMESHARE", "Property Appraiser" -- non-standard-collateral, not real
    STRAPs; not touched, consistent with prior sessions).
  - 4 have real STRAPs already present with full address/geo/value, but no
    parcel_zones row -> pure zone-linkage gap:
      25-CA-005045  29-43-25-11-00000.0670  2311 WESTWOOD RD
      25-CA-006178  22-43-24-03-00013.0010  3915 SABAL SPRINGS BLVD
      25-CA-006427  33-44-26-L3-07014.0040  712/714 GILBERT AVE S
      25-CA-006956  21-44-22-02-00000.009A  5638 EASY ST  ** NOT APPLIED, see below **

REGRESSION FOUND AND REVERTED (25-CA-006956 / TFC-2): inserting a parcel_zones
row with zone_code='TFC-2' (jurisdiction_id=630) flipped letter G from PASS
(pk1000=100.0) to FAIL (pk1000=88.9). Root cause: TFC-2's zoning_districts
row has category='commercial' and pk1000_regulated=NULL, so
v_zoning_district_applicability's fallback rule marks it pk1000_applicable=
true; its zone_standards row (id=3956) has parking_per_1000sf=NULL (a
pre-existing low-confidence 0.65 scrape with every numeric field null), so
the new parcel counted against the pk1000 denominator with no filled value
-- exactly the "unfillable liability" regression class this dispatch's
KNOWN HISTORY section warned about. Per the hard prohibition on fabricating
zoning-standard values, the correct fix (researching Lee County's real
TFC-2 parking ordinance to fill parking_per_1000sf, or confirming via
ordinance text that TFC-2 parking is negotiated per-project like the
okeechobee PD precedent and setting pk1000_regulated=false) was judged
out of scope for this narrow I-only session. Reverted: DELETE FROM
parcel_zones WHERE id=868747 (confirmed via REST DELETE
return=representation, and via a fresh pencil_dod_evaluate_county call
showing G back to PASS/97.5%/pk1000=100.0). 25-CA-006956 remains an I
residual, NOT fabricated, NOT silently dropped -- documented here.

Net: 3 of the 4 zone-linkage-gap rows applied (RS-1/RPD/RM-2, all under
jurisdiction 630 with pre-existing zoning_districts + zone_standards rows
and pk1000_applicable=false, i.e. no G-denominator risk from these three --
verified live, G stayed at pk1000=100.0 with these three alone). This is
sufficient: I population 327, need >=311 (95%), 309 (baseline) + 3 = 312
(95.4%) -- PASS.

METHOD: Cross-verified via TWO independent live Lee County sources:
  1. Lee County Property Appraiser Parcels FeatureServer (STRAP exact match,
     normalized digits-only):
     https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/Lee_County_Parcels/FeatureServer/0/query
     field ZONING.
  2. Lee County DCD_Zoning MapServer, layer 0 "Zoning" (unincorporated Lee,
     jurisdiction_id=630), authoritative parcel-level zoning layer used in
     the precedent migration (20260803_gold_standard_shard2_lee_lake_i_zone_gap.sql):
     https://gismapserver.leegov.com/gisserver910/rest/services/Layers/DCD_Zoning/MapServer/0/query
     point-in-polygon query at the row's own stored latitude/longitude,
     field ZONING.
  Both sources agree exactly for 3 of 4 rows (RS-1, RPD, RM-2). For the 4th
  (25-CA-006956) the Parcels FeatureServer's ZONING field returns "TFC2"
  (no dash) while DCD_Zoning (the more authoritative, spatially-verified
  source) returns "TFC-2" (with dash) -- used "TFC-2" since it is both the
  more authoritative source and the pre-existing zoning_districts.code value
  (id=11215, "Transitional Fringe Commercial").

All 4 zone codes ALREADY EXIST in zoning_districts for jurisdiction_id=630
(verified live before insert -- no new zoning_districts rows needed, so this
does not expand the G-denominator or create an unfillable code):
  RS-1  -> zoning_districts.id=11108
  RPD   -> zoning_districts.id=11210
  RM-2  -> zoning_districts.id=11208
  TFC-2 -> zoning_districts.id=11215

3 residual rows NOT touched (real, documented dead-ends, consistent with
prior sessions' findings):
  24-CA-007460  parcel_id='Property Appraiser' (placeholder, not a real
                 STRAP) -- missing assessed_value/market_value too.
  25-CA-003367  parcel_id='MULTIPLE PARCEL' -- no property_address, not
                 resolvable to a single STRAP.
  25-CA-004116  parcel_id='TIMESHARE' -- no property_address/geo, not
                 resolvable to a single STRAP.
"""
import json
import os
import urllib.error
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

FIXES = [
    {
        "case_number": "25-CA-005045",
        "parcel_id": "29-43-25-11-00000.0670",
        "zone_code": "RS-1",
        "zone_name": "Residential Single-Family Low Density",
    },
    {
        "case_number": "25-CA-006178",
        "parcel_id": "22-43-24-03-00013.0010",
        "zone_code": "RPD",
        "zone_name": "Residential Planned Development",
    },
    {
        "case_number": "25-CA-006427",
        "parcel_id": "33-44-26-L3-07014.0040",
        "zone_code": "RM-2",
        "zone_name": "Residential Multiple Low Density",
    },
    # 25-CA-006956 / TFC-2 deliberately EXCLUDED -- see module docstring
    # "REGRESSION FOUND AND REVERTED". Inserting it flips letter G to FAIL
    # via the pk1000 commercial-category fallback + NULL parking_per_1000sf.
    # Left as a documented I residual, not fabricated, not silently dropped.
]

JURISDICTION_ID = 630  # Lee County (Unincorporated)


def sb_post(path, data, prefer="return=representation"):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=body,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main():
    inserted = 0
    for fix in FIXES:
        row = {
            "parcel_id": fix["parcel_id"],
            "jurisdiction_id": JURISDICTION_ID,
            "zone_code": fix["zone_code"],
            "zone_name": fix["zone_name"],
            "source": "lee_gsd3_0c873526_dcdzoning_crosscheck_20260823",
        }
        status, resp = sb_post(
            "parcel_zones", [row], prefer="resolution=ignore-duplicates,return=representation"
        )
        print(f"{fix['case_number']} ({fix['parcel_id']}) -> zone_code={fix['zone_code']} : status={status} resp={resp[:200]}")
        if status in (200, 201):
            try:
                parsed = json.loads(resp)
                if parsed:
                    inserted += 1
                else:
                    print(f"  WARNING: 0 rows written for {fix['case_number']} despite {status} status (possible silent duplicate-ignore)")
            except Exception:
                pass
        else:
            print(f"  ERROR: non-2xx status for {fix['case_number']}")

    print(f"\nTotal parcel_zones rows inserted: {inserted} of {len(FIXES)}")
    if inserted < len(FIXES):
        print("FAIL-LOUD: not all fixes wrote successfully. Investigate before claiming improvement.")


if __name__ == "__main__":
    main()
