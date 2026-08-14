#!/usr/bin/env python3
"""
Gold Standard shard-1 (dispatch 3ce988ac-bdcf-4554-aaa2-1f9b7653bc45) — gulf county, letter G.

PROBLEM (verified via pencil_dod_evaluate_county('gulf') before this script ran):
  G FAIL at 0.0 (density=86.7 far=0.0 pk1000=0.0)
  v_zoning_gold_standard_kpi_v3 for gulf: parcels=15, far_applicable_parcels=2,
  pct_far_of_applicable=0.0, pk1000_applicable_parcels=2, pct_pk1000_of_applicable=0.0.

ROOT CAUSE (verified):
  Joined gulf's 15 auction parcel_ids -> parcel_zones -> zoning_districts. Two of the
  15 parcels are zoned by the City of Port St Joe (jurisdiction_id=952) with codes
  R-3 (parcel 05004050R) and R-2B (parcel 05762000R). Port St Joe's zoning_districts
  catalog (as of this session) had exactly ONE row for jurisdiction 952: code=R-1.
  R-2B and R-3 had NO catalog row at all.

  This is the documented KNOWN REGRESSION TRAP: v_zoning_gold_standard_kpi_v3 /
  v_zoning_district_applicability treat an unmatched zone_code as "FAR/parking
  applicable but standards missing" rather than correctly inferring N/A, which is
  exactly the far_applicable_parcels=2 / pct_far=0.0 signature observed.

RESEARCH (verified — real source, not fabricated):
  Downloaded City of Port St Joe's official Land Development Regulations PDF
  (https://www.cityofportstjoe.com/pdf/comp/LDR-FINAL.pdf, 161 pages) and extracted
  full text with pypdf. Confirmed:
    - Sec. 3.04 "Same--District R-2": defines subdistrict R-2A and subdistrict R-2B.
      R-2B: uses permitted (multi-family, boarding/lodging, hospitals/clinics, guest
      houses, etc), building height limit 60 ft, building site/min floor area table
      by unit count, front yard >=15ft, side yard 7-10ft (lot-width conditional),
      rear yard >=15ft. "Density and intensity shall be the same in district R-2B as
      in R-2A" -> R-2A: "No more than seven (7) units per acre... intensity no more
      than 60 percent lot coverage" (Sec 3.04(1)h). So R-2B: max_density_du_acre=7,
      max_lot_coverage_pct=60, max_height_ft=60.
    - Sec. 3.05 "Same--District R-3": "No more than fifteen (15) units per acre...
      intensity of no more than 80 percent lot coverage." Building height limit 60 ft
      (no height bonus clause referenced for R-3, unlike R-2A/R-2B). So R-3:
      max_density_du_acre=15, max_lot_coverage_pct=80, max_height_ft=60.
    - Sec. 5.08(a) "Required parking spaces": parking is expressed PER DWELLING UNIT
      for residential uses ("Residential (single-family or duplex): Two spaces per
      dwelling unit." / "Residential (multifamily): Two and one-half spaces per
      dwelling unit.") for ALL residential districts, R-1 through R-4. There is no
      per-1,000-sq-ft parking ratio anywhere in the LDR for residential uses — sqft-
      based ratios (e.g. "one space per 300 sq ft") appear ONLY for nonresidential
      use types (offices, retail, clinics, etc), not for residential zoning districts.
    - grep of the full 161-page extracted text for "floor area ratio" and standalone
      "FAR" returns ZERO matches anywhere in the document. Port St Joe's LDR does not
      regulate FAR for ANY district (residential or commercial) — it regulates bulk
      via max_lot_coverage_pct and max_height_ft instead. This mirrors the existing
      R-1 catalog row already in the DB (max_far=NULL, sourced by a prior session
      with the identical documented rationale).

  CONCLUSION: R-2B and R-3 are residential multi-family districts. Per the actual
  LDR text, FAR is not regulated (genuinely N/A, not missing data) and parking is
  regulated per-dwelling-unit, not per-1000sf (also genuinely N/A for the pk1000
  metric). This is NOT a case of "go find the real FAR/parking-per-1000sf number" —
  the county's LDR structurally does not use those metrics for residential zones.
  The correct fix is the same pattern already used for R-1: category='Residential'
  (matches the view's residential heuristic: far_applicable=false, pk1000_applicable
  =false, density_applicable=true) PLUS explicit far_regulated=false and
  pk1000_regulated=false (evidence-based override, since we have direct textual
  proof, not just a category fallback) so v_zoning_district_applicability correctly
  classifies these two districts as FAR/pk1000 N/A instead of "applicable but
  missing".

WRITES PERFORMED BY THIS SCRIPT:
  1. INSERT zoning_districts: 2 new rows (R-2B, R-3) for jurisdiction_id=952
     (City of Port St Joe), category='Residential', far_regulated=false,
     pk1000_regulated=false, density_regulated=null (residential is never excluded
     per the column's own documented semantics -- NULL means "use category
     heuristic", and category='Residential' already yields density_applicable=true
     which is correct).
  2. INSERT zone_standards: 2 new rows (one per new zoning_districts.id) with
     max_density_du_acre, max_lot_coverage_pct, max_height_ft, parking_per_unit
     populated from the LDR sections above. max_far and parking_per_1000sf are
     intentionally left NULL with source_url + description explaining why (LDR
     does not regulate these for residential districts) -- following the exact
     precedent already set by the existing R-1 zone_standards row (id=4785).

NOT written: no changes to multi_county_auctions, parcel_zones, or any other table.
No DDL. No changes to v_zoning_gold_standard_kpi_v3 or v_zoning_district_applicability
(views, not writable from this script; not required since evidence-based override
columns are respected by the view per its own documented purpose).
"""
import os
import sys
import json
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

LDR_SOURCE = "https://www.cityofportstjoe.com/pdf/comp/LDR-FINAL.pdf"


def rest_request(method, path, body=None, extra_headers=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = dict(HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"HTTPError {e.code} on {method} {path}: {err_body}", file=sys.stderr)
        raise


def rpc(fn, payload):
    return rest_request("POST", f"rpc/{fn}", payload)


def main():
    print("=== BEFORE: pencil_dod_evaluate_county('gulf') ===")
    before = rpc("pencil_dod_evaluate_county", {"p_county": "gulf"})
    print(json.dumps(before, indent=2))

    # ---- Step 1: insert zoning_districts catalog rows for R-2B and R-3 ----
    districts_payload = [
        {
            "jurisdiction_id": 952,
            "code": "R-2B",
            "name": "R-2B Multi-Family Residential District",
            "category": "Residential",
            "description": (
                "City of Port St Joe R-2B residential subdistrict (LDR Sec. 3.04(2)): "
                "multi-family dwellings, boarding/lodging houses, hospitals/clinics "
                "(non-animal), guest houses, community centers; max height 60ft "
                "(Sec.3.04(2)k); front yard >=15ft (Sec.3.04(2)m); rear yard >=15ft "
                "(Sec.3.04(2)o); side yard 7-10ft lot-width-conditional (Sec.3.04(2)n); "
                "'Density and intensity shall be the same in district R-2B as in R-2A' "
                "(Sec.3.04(2)p) -> R-2A allows no more than 7 units/acre and 60% lot "
                "coverage (Sec.3.04(1)h). Parking per Sec.5.08(a): 'Residential "
                "(multifamily): Two and one-half spaces per dwelling unit.' LDR PDF "
                "metadata 'Final Adopted LDRs 100908' (~2008-10-09)."
            ),
            "ordinance_section": "Sec. 3.04(1)h,(2)k,(2)m,(2)n,(2)o,(2)p; Sec. 5.08(a)",
            "far_regulated": False,
            "pk1000_regulated": False,
        },
        {
            "jurisdiction_id": 952,
            "code": "R-3",
            "name": "R-3 Residential District",
            "category": "Residential",
            "description": (
                "City of Port St Joe R-3 residential district (LDR Sec. 3.05): any use "
                "permitted in any other residential district; no more than 15 units/acre "
                "and intensity of no more than 80% lot coverage (Sec.3.05(b)); max "
                "building height 60ft (Sec.3.05(d)); building site/min floor area per "
                "unit-count table (Sec.3.05(c)). Parking per Sec.5.08(a): 'Residential "
                "(multifamily): Two and one-half spaces per dwelling unit.' LDR PDF "
                "metadata 'Final Adopted LDRs 100908' (~2008-10-09)."
            ),
            "ordinance_section": "Sec. 3.05(b),(c),(d); Sec. 5.08(a)",
            "far_regulated": False,
            "pk1000_regulated": False,
        },
    ]

    # Idempotent: check first, only insert codes that don't already exist for
    # jurisdiction 952 (this script may be re-run after a partial failure).
    existing = rest_request(
        "GET",
        "zoning_districts?jurisdiction_id=eq.952&code=in.(R-2B,R-3)&select=id,code",
    )
    existing_codes = {row["code"] for row in existing} if existing else set()
    to_insert = [row for row in districts_payload if row["code"] not in existing_codes]

    print("\n=== INSERT zoning_districts (R-2B, R-3 for jurisdiction 952) ===")
    if to_insert:
        newly_inserted = rest_request(
            "POST",
            "zoning_districts",
            to_insert,
            extra_headers={"Prefer": "return=representation"},
        )
    else:
        newly_inserted = []
    print(json.dumps(newly_inserted, indent=2))

    id_by_code = {row["code"]: row["id"] for row in newly_inserted}
    for row in existing:
        id_by_code[row["code"]] = row["id"]
    print(f"(already existed: {sorted(existing_codes)}, newly inserted: {sorted(r['code'] for r in newly_inserted)})")
    assert "R-2B" in id_by_code and "R-3" in id_by_code, "Insert did not return expected codes"

    # ---- Step 2: insert zone_standards rows for the two new districts ----
    standards_payload = [
        {
            "zoning_district_id": id_by_code["R-2B"],
            "max_height_ft": 60.0,
            "front_setback_ft": 15.0,
            "rear_setback_ft": 15.0,
            "max_lot_coverage_pct": 60.0,
            "max_far": None,
            "max_density_du_acre": 7.0,
            "parking_per_unit": 2.5,
            "parking_per_1000sf": None,
            "source_url": (
                f"{LDR_SOURCE} (City of Port St Joe LDR, Sec. 3.04(2) District R-2B: "
                "height Sec.3.04(2)k; front/rear setback Sec.3.04(2)m/(2)o; density+"
                "coverage per Sec.3.04(2)p 'same as R-2A' -> Sec.3.04(1)h = 7 DU/acre, "
                "60% lot coverage; parking Sec.5.08(a) 'Residential (multifamily): Two "
                "and one-half spaces per dwelling unit'). max_far and "
                "parking_per_1000sf intentionally NULL -- verified by full-text search "
                "of the 161-page LDR PDF: zero occurrences of 'floor area ratio' or "
                "'FAR' anywhere in the document, and all residential parking ratios "
                "in Sec.5.08(a) are per-dwelling-unit, never per-1,000-sq-ft (sqft-"
                "based ratios in that section apply only to nonresidential use types)."
            ),
            "ordinance_section": "Sec. 3.04(1)h,(2)k,(2)m,(2)n,(2)o,(2)p; Sec. 5.08(a)",
            "confidence_score": 0.85,
        },
        {
            "zoning_district_id": id_by_code["R-3"],
            "max_height_ft": 60.0,
            "front_setback_ft": None,
            "rear_setback_ft": None,
            "max_lot_coverage_pct": 80.0,
            "max_far": None,
            "max_density_du_acre": 15.0,
            "parking_per_unit": 2.5,
            "parking_per_1000sf": None,
            "source_url": (
                f"{LDR_SOURCE} (City of Port St Joe LDR, Sec. 3.05 District R-3: "
                "density+coverage Sec.3.05(b) '15 units/acre, 80% lot coverage'; "
                "height Sec.3.05(d); parking Sec.5.08(a) 'Residential (multifamily): "
                "Two and one-half spaces per dwelling unit'). max_far and "
                "parking_per_1000sf intentionally NULL -- verified by full-text search "
                "of the 161-page LDR PDF: zero occurrences of 'floor area ratio' or "
                "'FAR' anywhere in the document, and all residential parking ratios "
                "in Sec.5.08(a) are per-dwelling-unit, never per-1,000-sq-ft (sqft-"
                "based ratios in that section apply only to nonresidential use types)."
            ),
            "ordinance_section": "Sec. 3.05(b),(c),(d); Sec. 5.08(a)",
            "confidence_score": 0.85,
        },
    ]

    existing_standards = rest_request(
        "GET",
        "zone_standards?zoning_district_id=in.(%s)&select=id,zoning_district_id"
        % ",".join(str(v) for v in id_by_code.values()),
    )
    existing_std_district_ids = (
        {row["zoning_district_id"] for row in existing_standards} if existing_standards else set()
    )
    standards_to_insert = [
        row for row in standards_payload
        if row["zoning_district_id"] not in existing_std_district_ids
    ]

    print("\n=== INSERT zone_standards (R-2B, R-3) ===")
    if standards_to_insert:
        inserted_standards = rest_request(
            "POST",
            "zone_standards",
            standards_to_insert,
            extra_headers={"Prefer": "return=representation"},
        )
    else:
        inserted_standards = []
    print(json.dumps(inserted_standards, indent=2))
    print(f"(zone_standards already existed for district_ids: {sorted(existing_std_district_ids)})")

    print("\n=== AFTER: pencil_dod_evaluate_county('gulf') ===")
    after = rpc("pencil_dod_evaluate_county", {"p_county": "gulf"})
    print(json.dumps(after, indent=2))

    print("\n=== SUMMARY ===")
    print(f"zoning_districts rows newly inserted this run: {len(newly_inserted)}")
    print(f"zone_standards rows newly inserted this run: {len(inserted_standards)}")
    print(f"G before: {before['G']}")
    print(f"G after:  {after['G']}")


if __name__ == "__main__":
    main()
