#!/usr/bin/env python3
"""
GTM-22J Putnam criterion G regression fix.

ROOT CAUSE (verified live before writing this script — see session report):
An earlier session in this same 24h window fixed criterion I by inserting 5 new
zoning_districts rows (ids 12159-12163) + 12 parcel_zones rows for Putnam county.
v_zoning_district_applicability auto-populated correct applicability flags for
all 5, but none of the 5 districts had a zone_standards row at all, so parcels
zoned into them silently dropped out of the FAR/parking/density numerator in
pencil_dod_evaluate_county('putnam') criterion G:
  - district_id=12159 (Interlachen C-2, far_applicable=true, pk1000_applicable=true)
    had ZERO zone_standards row -> zero contribution to far_applicable_parcels
    and pk1000_applicable_parcels (this is the single biggest driver of the
    FAR collapse to 0.0%).
  - district_id=12160/12161/12162/12163 (density_applicable=true) had no
    max_density_du_acre value -> density metric dropped 99.5% -> 98.2%.

This script inserts real, sourced zone_standards values for exactly those 5
districts. It does NOT touch any other putnam zoning_districts row, any other
county, or multi_county_auctions (criteria C/D/I already fixed this session).

Idempotent: checks for an existing zone_standards row per zoning_district_id
before inserting; if one already exists it UPDATEs only the NULL target
columns this script is responsible for (max_far / max_density_du_acre /
parking_per_1000sf) rather than blindly re-inserting, so re-running this
script after another session's edits will not clobber later real data.

Run: python3 scripts/gtm22j_putnam_g_regression_fix.py [--apply]
     (defaults to --dry-run; must pass --apply to write)
"""
import subprocess
import sys
import json

MGMT_SQL = "mgmt_sql.py"

def run_sql(sql: str):
    """Run SQL via mgmt_sql.py and return parsed JSON result."""
    full = f"SET statement_timeout=0; {sql}"
    proc = subprocess.run(
        [sys.executable, MGMT_SQL, full],
        capture_output=True, text=True, check=False,
    )
    out = proc.stdout.strip()
    if proc.returncode != 0 or "STATUS 4" in out.splitlines()[0] if out else True:
        pass  # fall through, let caller inspect raw output
    # mgmt_sql.py prints "STATUS <code>" then JSON body
    lines = out.splitlines()
    status_line = lines[0] if lines else ""
    body = "\n".join(lines[1:]) if len(lines) > 1 else "[]"
    try:
        data = json.loads(body) if body.strip() else []
    except json.JSONDecodeError:
        data = None
    return status_line, data, out


# ---------------------------------------------------------------------------
# SOURCED VALUES
# ---------------------------------------------------------------------------
# Interlachen sources (Town of Interlachen zoning ordinance, "ATTACHMENT TO
# ORDINANCE 2012-_____", https://www.interlachen-fl.gov/wp-content/uploads/zone_ord.doc,
# fetched 2026-07-19, extracted via catdoc) and Town of Interlachen 2035
# Comprehensive Plan (https://www.interlachen-fl.gov/wp-content/uploads/Town-of-Interlachen-2035-Comp-Plan.pdf,
# fetched 2026-07-19, extracted via pdftotext -layout).
#
# Pomona Park source: Town of Pomona Park 2045 Comprehensive Plan, Future
# Land Use Element (https://www.pomonapark.com/sites/default/files/fileattachments/planning/page/2287/town_of_pomona_park_2045_plan.pdf,
# fetched 2026-07-19, extracted via pdftotext -layout).

FIXES = [
    {
        "district_id": 12159,
        "jurisdiction": "Interlachen",
        "code": "C-2",
        "name": "Commercial, General, Light",
        "updates": {
            # VERIFIED: Interlachen zoning ordinance Section VII (Off-Street
            # Parking and Loading), 7.1.7(A)(6)(a): "Business, commercial or
            # personal service establishment (Not Otherwise Listed), one
            # space for each 300 square feet of gross floor area" -- this is
            # the catch-all commercial parking standard and applies to C-2's
            # retail/service uses (C-2 intent: "general commercial light
            # uses that will meet the retail sales and service needs of Town
            # residents"). 1 space / 300 sqft = 3.333 spaces per 1000 sqft.
            "parking_per_1000sf": 3.333,
            # VERIFIED: Town of Interlachen 2035 Comprehensive Plan, Future
            # Land Use Element, Policy 1.41: "Commercial use shall be
            # limited to an intensity of less than or equal to 1.0 floor
            # area ratio." The zoning ordinance itself (Section XVII, C-2
            # District) does not codify a numeric FAR -- it regulates bulk
            # via setbacks (front 35ft/side 10ft/rear 15ft) and height (35ft)
            # instead -- so the comp plan's commercial intensity cap is the
            # real, sourced FAR ceiling that applies to C-2.
            "max_far": 1.0,
        },
        "source_url": "https://www.interlachen-fl.gov/wp-content/uploads/Town-of-Interlachen-2035-Comp-Plan.pdf ; https://www.interlachen-fl.gov/wp-content/uploads/zone_ord.doc",
        "ordinance_section": "Comp Plan FLU Policy 1.41 (max_far); Zoning Ord. Sec. 7.1.7(A)(6)(a) (parking_per_1000sf)",
        "confidence_score": 0.85,
        "tag": "VERIFIED",
    },
    {
        "district_id": 12160,
        "jurisdiction": "Interlachen",
        "code": "R-1A",
        "name": "Residential, Single-family area>7500sqft",
        "updates": {
            # INFERRED: Interlachen zoning ordinance Section X (R-1, R-1A,
            # R-1HA Districts), 10.3 Permitted Uses lists ONLY "Single-family
            # dwellings" by right (duplexes not listed even as special
            # exception in this section) and 10.6(B): "The minimum lot width
            # in the R-1A district is 75 feet. The minimum lot area in the
            # R-1A district is 7,500 square feet." Base by-right density is
            # therefore 1 unit per 7,500 sqft lot: 43,560 sqft/acre / 7,500
            # sqft = 5.808 du/acre. This is a lot-size-derived inference, not
            # a literal "X du/acre" statement in the ordinance -- tagged
            # INFERRED. Cross-check: falls inside the Town's 2035 Comp Plan
            # FLU Policy 1.29 "Medium Density Development, a maximum of
            # 4-10 dwelling units per acre" band, corroborating plausibility.
            "max_density_du_acre": 5.808,
        },
        "source_url": "https://www.interlachen-fl.gov/wp-content/uploads/zone_ord.doc",
        "ordinance_section": "Zoning Ord. Sec. 10.6(B) min lot area 7,500 sqft -> derived density",
        "confidence_score": 0.55,
        "tag": "INFERRED",
    },
    {
        "district_id": 12161,
        "jurisdiction": "Interlachen",
        "code": "R-2",
        "name": "Residential, Mixed area>7500sqft",
        "updates": {
            # INFERRED: Interlachen zoning ordinance Section XI (R-2, R-2HA
            # Districts), 11.3 Permitted Uses lists "Mobile homes on
            # individual lots" and "Single-family dwellings" by right;
            # duplexes are listed under 11.4 as a SPECIAL EXCEPTION only
            # (not by-right), so base by-right density uses the
            # single-family/mobile-home lot standard. 11.6: "In R-2
            # districts - 7,500 square feet." Same lot size as R-1A ->
            # 43,560/7,500 = 5.808 du/acre. Cross-check: within Comp Plan
            # Policy 1.29 Medium Density band (4-10 du/acre).
            "max_density_du_acre": 5.808,
        },
        "source_url": "https://www.interlachen-fl.gov/wp-content/uploads/zone_ord.doc",
        "ordinance_section": "Zoning Ord. Sec. 11.6 min lot area 7,500 sqft (R-2) -> derived density",
        "confidence_score": 0.5,
        "tag": "INFERRED",
    },
    {
        "district_id": 12162,
        "jurisdiction": "Interlachen",
        "code": "R-2HA",
        "name": "Residential, Mixed area>0.5 acres",
        "updates": {
            # INFERRED: same Section XI, 11.6: "In R-2HA districts - 21,780
            # square feet" (= 0.5 acre, matching the district name).
            # 43,560/21,780 = 2.0 du/acre exactly. Cross-check: falls inside
            # Comp Plan Policy 1.30 "Low Density Residential Development,
            # with a maximum of less than or equal to four dwelling units
            # per acre" band.
            "max_density_du_acre": 2.0,
        },
        "source_url": "https://www.interlachen-fl.gov/wp-content/uploads/zone_ord.doc",
        "ordinance_section": "Zoning Ord. Sec. 11.6 min lot area 21,780 sqft (R-2HA) -> derived density",
        "confidence_score": 0.55,
        "tag": "INFERRED",
    },
    {
        "district_id": 12163,
        "jurisdiction": "Pomona Park",
        "code": "MDR",
        "name": "Residential, Medium-density",
        "updates": {
            # VERIFIED: Town of Pomona Park 2045 Comprehensive Plan, Future
            # Land Use Element, Policy A.1.1.5 land use classification list:
            # "Medium density residential (greater than 2 and up to 5
            # dwelling units per net acre) -- this category consists
            # primarily of duplex dwelling units and multi-family dwelling
            # units." District code MDR directly matches this FLU category
            # name/definition. Using the stated maximum: 5.0 du/acre.
            "max_density_du_acre": 5.0,
        },
        "source_url": "https://www.pomonapark.com/sites/default/files/fileattachments/planning/page/2287/town_of_pomona_park_2045_plan.pdf",
        "ordinance_section": "2045 Comp Plan FLU Element, Policy A.1.1.5 (Medium density residential)",
        "confidence_score": 0.85,
        "tag": "VERIFIED",
    },
]

# Guardrail: only these putnam jurisdictions / only these district ids may be touched
ALLOWED_JURISDICTIONS = {931, 1120, 1121, 1122, 1123}
ALLOWED_DISTRICT_IDS = {12159, 12160, 12161, 12162, 12163}


def main():
    apply = "--apply" in sys.argv

    # Guardrail check: confirm target districts belong to allowed putnam jurisdictions only
    ids_csv = ",".join(str(i) for i in sorted(ALLOWED_DISTRICT_IDS))
    _, rows, raw = run_sql(
        f"SELECT id, jurisdiction_id FROM zoning_districts WHERE id IN ({ids_csv});"
    )
    if rows is None:
        print("FATAL: could not verify target districts, aborting.\n" + raw)
        sys.exit(1)
    for r in rows:
        if r["jurisdiction_id"] not in ALLOWED_JURISDICTIONS:
            print(f"FATAL: district {r['id']} belongs to jurisdiction_id "
                  f"{r['jurisdiction_id']} which is NOT in the allowed putnam "
                  f"set {ALLOWED_JURISDICTIONS}. Aborting to avoid touching "
                  f"another county.")
            sys.exit(1)
    found_ids = {r["id"] for r in rows}
    if found_ids != ALLOWED_DISTRICT_IDS:
        missing = ALLOWED_DISTRICT_IDS - found_ids
        print(f"FATAL: expected districts {ALLOWED_DISTRICT_IDS}, only found "
              f"{found_ids}. Missing {missing}. Aborting.")
        sys.exit(1)

    print(f"Guardrail OK: all 5 target districts confirmed under allowed "
          f"putnam jurisdictions {ALLOWED_JURISDICTIONS}.\n")

    for fix in FIXES:
        did = fix["district_id"]
        print(f"--- district_id={did} ({fix['jurisdiction']} {fix['code']} "
              f"'{fix['name']}') [{fix['tag']}] ---")

        _, existing, raw = run_sql(
            f"SELECT id, max_far, max_density_du_acre, parking_per_1000sf "
            f"FROM zone_standards WHERE zoning_district_id={did};"
        )
        if existing is None:
            print("  FATAL: could not query existing zone_standards row.\n" + raw)
            sys.exit(1)

        updates = fix["updates"]
        set_clauses = []
        for col, val in updates.items():
            set_clauses.append(f"{col}={val}")

        if existing:
            row = existing[0]
            sid = row["id"]
            # Idempotent: only overwrite columns that are currently NULL, to
            # avoid clobbering any real value written after this script's
            # research (re-run safety).
            null_cols = [c for c in updates if row.get(c) is None]
            if not null_cols:
                print(f"  standards_id={sid} already has values for all "
                      f"target columns {list(updates.keys())} -- skipping "
                      f"(idempotent no-op).")
                continue
            set_sql = ", ".join(f"{c}={updates[c]}" for c in null_cols)
            sql = (
                f"UPDATE zone_standards SET {set_sql}, "
                f"source_url='{fix['source_url']}', "
                f"ordinance_section='{fix['ordinance_section']}', "
                f"confidence_score={fix['confidence_score']}, "
                f"scraped_at=now() "
                f"WHERE id={sid};"
            )
            action = f"UPDATE existing standards_id={sid}, columns={null_cols}"
        else:
            cols = ["zoning_district_id"] + list(updates.keys()) + [
                "source_url", "ordinance_section", "confidence_score", "scraped_at"
            ]
            vals = [str(did)] + [str(v) for v in updates.values()] + [
                f"'{fix['source_url']}'",
                f"'{fix['ordinance_section']}'",
                str(fix["confidence_score"]),
                "now()",
            ]
            sql = (
                f"INSERT INTO zone_standards ({', '.join(cols)}) "
                f"VALUES ({', '.join(vals)});"
            )
            action = "INSERT new zone_standards row"

        print(f"  {action}")
        print(f"  values: {updates}")
        print(f"  source: {fix['source_url']}")
        print(f"  ordinance_section: {fix['ordinance_section']}")

        if apply:
            status, _, raw = run_sql(sql)
            print(f"  -> {status}")
            if "STATUS 2" not in status:
                print("  FATAL write failure:\n" + raw)
                sys.exit(1)
        else:
            print("  [DRY RUN -- pass --apply to write]")
        print()

    print("Done." if apply else "Dry run complete. Re-run with --apply to write.")


if __name__ == "__main__":
    main()
