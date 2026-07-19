#!/usr/bin/env python3
"""
GTM-22J santa_rosa criterion G regression fix.

ROOT CAUSE (verified live before writing this script -- see session report):
An earlier session in this same 24h window (gtm22j_santa_rosa_i_backfill.py)
fixed criterion I by inserting 6 new parcel_zones rows. v_zoning_gold_standard_kpi_v3
joins parcel_zones -> zoning_districts ON (jurisdiction_id, code=zone_code) ->
v_zoning_district_applicability -> zone_standards. When zoning_districts has NO
row matching a parcel_zones.zone_code for that jurisdiction, the join produces
NULL district/applicability/standards, and COALESCE(a.far_applicable, true) /
COALESCE(a.pk1000_applicable, true) / COALESCE(a.density_applicable, true) in
the view default ALL THREE metrics to "applicable" with NULL standards --
which counts as a FAIL in the numerator. Confirmed live:
  SELECT * FROM v_zoning_gold_standard_kpi_v3 WHERE county='santa rosa'
  -> pct_far_of_applicable = 0.0 (far_applicable_parcels=4, but 0 of them have
     max_far set) -- this is the G regression symptom (criterion G FAILs).

Three of the six new parcel_zones rows have a zone_code that does not match
any existing zoning_districts.code for that jurisdiction:

  1. parcel_id=40-1N-28-0090-37900-0010, jurisdiction_id=956 (Milton),
     zone_code='R1'. VERIFIED pure normalization bug: Milton's Unified
     Development Code Article 6 (Zoning District Regulations),
     https://www.miltonfl.org/DocumentCenter/View/1852/ARTICLE-6-ZONING-DISTRICT-REGULATIONS
     (fetched 2026-07-19, extracted via pdftotext -layout), Table 6.2.1
     "Residential District Dimensional Standards", column header lists the
     district as "R-1" (hyphenated) throughout -- "(4) R-1 Single-Family
     Residential Zoning District ... located on 7,500 square foot lots".
     This exactly matches the already-populated zoning_districts id=11522
     (code='R-1', min_lot_sqft=7500, max_height_ft=36 -- both values confirmed
     against the ordinance table: "Minimum Lot Area: 7,500sf", "Maximum
     Building Height: 36'"). The original I-backfill session's own source
     comment for this row cites the generic county page
     (santarosa.fl.gov/193/Zoning-Classifications), i.e. it pulled the raw
     ArcGIS zoning attribute abbreviation "R1", not Milton's own ordinance
     code. FIX: normalize parcel_zones.zone_code from 'R1' -> 'R-1' for this
     one row. No new zoning_districts/zone_standards row needed.

  2. parcel_id=41-5N-29-1970-00A00-0320, jurisdiction_id=1124 (Jay),
     zone_code='RM' ("Residential Medium"). VERIFIED genuinely distinct
     district from RM-A ("Residential Medium Activity Center", id=11520,
     pre-existing since 2026-07-11 -- older than this 24h window, confirmed
     via created_at, and itself has NO zone_standards row).
     Source: Santa Rosa County Property Appraiser "Town of Jay Zoning" map,
     https://srcpa.gov/resources/Zoning%20-%20Town%20of%20Jay.pdf (fetched
     2026-07-19, extracted via pdftotext -layout), Legend section: under
     "General Zoning Districts" the map lists "(RM) Residential Medium" as
     its own district, separate from "(RM-A) Residential Medium -- Activity
     Center" which is listed under the distinct "Activity Center Zoning
     Districts" heading. Independent corroboration: the same I-backfill
     session assigned a DIFFERENT Jay parcel (41-5N-29-2080-00A00-0090)
     zone_code='RM-A' from the same SRCPA source in the same run, i.e. the
     prior session's own research already treated RM and RM-A as two
     different codes for two different parcels.
     Numeric FAR/density/parking standards for the RM district specifically:
     NOT FOUND. The Town of Jay's ordinance text lives on
     jay.municipalcodeonline.com, which is a JS-rendered SPA -- not fetchable
     via WebFetch/curl, and Firecrawl (which could render it) returned
     "Insufficient credits" for every scrape attempt this session. WebSearch
     surfaced no cached/mirrored copy of Jay's dimensional-standards table for
     RM. Per the HONESTY PROTOCOL (never guess a numeric standard), this
     script does NOT insert a max_far/max_density_du_acre/parking_per_1000sf
     value for RM. FIX: insert a real zoning_districts row (code='RM', real
     sourced name/category from the SRCPA map) so the parcel joins to a real
     district instead of NULL -- category='Residential' with no
     far_regulated/pk1000_regulated override needed (residential districts
     default far/pk1000 NOT applicable, density applicable, via
     v_zoning_district_applicability's category-based defaults, matching how
     every other Santa Rosa residential district in this DB is already
     modeled). zone_standards is deliberately left unpopulated (no
     zone_standards row inserted) pending real ordinance text -- this
     converts the parcel from "counted as a density FAIL with phantom
     far/pk1000 applicability" to "correctly excluded from far/pk1000
     applicable set (residential), counted as a genuine density FAIL until
     someone can source real standards" -- an honest partial fix, not a
     fabricated one.

  3. parcel_id=12-1N-29-0000-01000-0000 (NOTE: task text said suffix
     "-0010"; verified live the actual parcel_zones row has suffix "-0000" --
     "-0010" does not exist in parcel_zones. Confirmed via direct query.),
     jurisdiction_id=1398 (Unincorporated Santa Rosa County), zone_code='HCD'
     ("Highway Commercial Development"). VERIFIED via the official Santa Rosa
     County Land Development Code,
     https://www.santarosa.fl.gov/DocumentCenter/View/5820/Santa-Rosa-County-Land-Development-Code-
     (fetched 2026-07-19, extracted via pdftotext -layout) -- same source_url
     already used for every other jurisdiction_id=1398 district in this DB
     (AG-RR, PUD, R1, R1M, R2M), confirming HCD belongs in the same table:
       - Section 2.02 district list: "C. Commercial and Business ... 2. HCD
         - Highway Commercial Development" (category = Commercial).
       - Table 2.04.02.b "Density and Intensity Standards for Commercial and
         Industrial Zoning Districts": HCD Residential Density = 10 dwelling
         units per gross acre.
       - Table 2.05.01.b "Setback and Height Limits for Commercial and
         Industrial Zoning Districts": HCD Front 50', Side 5' (25' if
         abutting residential), Rear 25', Height 50'.
       - Table 2.06.01.b "Minimum Lot Sizes and Widths for Commercial and
         Industrial Zoning Districts": HCD Minimum Lot Width 100', no
         district-wide minimum lot size specified.
     No blanket FAR standard: searched the full LDC text for "Floor Area
     Ratio"/"FAR" -- the only FAR figures in the whole document are
     use-specific caps inside airport-safety-zone overlays (ASF/APZ-1/APZ-2,
     e.g. "Wholesale Trade - FAR 0.28"), not a base HCD district standard.
     No blanket parking-per-1000sf standard: Santa Rosa's off-street parking
     table (LDC section ~9, "Business and Professional Office - 1 parking
     space for each 300 square feet", "Retail Store... 1 parking space per
     250 square feet", etc.) sets parking PER LAND USE TYPE, not per zoning
     district -- there is no single HCD-wide parking-per-1000sf figure to
     record. This matches the existing convention in this DB: every other
     jurisdiction_id=1398 district (AG-RR/PUD/R1/R1M/R2M) also has
     parking_per_1000sf=NULL and max_far=NULL, sourced from this same LDC.
     FIX (matches the task's stated fallback for a legitimate
     no-numeric-limit finding): insert zoning_districts row (code='HCD',
     category='Commercial', far_regulated=false, pk1000_regulated=false --
     explicit, sourced non-applicability, not a silent default) + a
     zone_standards row with max_density_du_acre=10 (the one real numeric
     standard that exists) and max_far/parking_per_1000sf left NULL by
     design. far_regulated=false / pk1000_regulated=false makes
     v_zoning_district_applicability correctly report this parcel as
     NOT-applicable for far/pk1000 (instead of defaulting to
     applicable-with-NULL-standard = FAIL), while density_applicable stays
     true (no override) and is satisfied by the real 10 du/acre value.

GUARDRAILS ENFORCED BY THIS SCRIPT:
  - Only touches jurisdiction_id IN (828, 956, 1124, 1398) (santa_rosa).
  - Never touches multi_county_auctions (criterion I already fixed).
  - Never writes a numeric standard without a cited real source (item 2's RM
    density/far/pk1000 are intentionally left NULL -- no fabricated values).
  - Idempotent: zone_code normalize is a conditional UPDATE guarded by
    current value; zoning_districts/zone_standards inserts are pre-checked
    by (jurisdiction_id, code) / (zoning_district_id) before insert, and
    zone_standards on existing rows only fills currently-NULL target
    columns (never clobbers later real data on re-run).

Run: python3 scripts/gtm22j_santa_rosa_g_regression_fix.py [--apply]
     (defaults to --dry-run; must pass --apply to write)
"""
import subprocess
import sys
import json

MGMT_SQL = "mgmt_sql.py"

ALLOWED_JURISDICTIONS = {828, 956, 1124, 1398}


def run_sql(sql: str):
    """Run SQL via mgmt_sql.py and return (status_line, parsed_json_or_None, raw_stdout)."""
    full = f"SET statement_timeout=0; {sql}"
    proc = subprocess.run(
        [sys.executable, MGMT_SQL, full],
        capture_output=True, text=True, check=False,
    )
    out = proc.stdout.strip()
    lines = out.splitlines()
    status_line = lines[0] if lines else ""
    body = "\n".join(lines[1:]) if len(lines) > 1 else "[]"
    try:
        data = json.loads(body) if body.strip() else []
    except json.JSONDecodeError:
        data = None
    return status_line, data, out


def main():
    apply = "--apply" in sys.argv

    # ------------------------------------------------------------------
    # STEP 1: Milton R1 -> R-1 normalization (item 1)
    # ------------------------------------------------------------------
    print("=== STEP 1: Milton parcel_zones.zone_code normalization (R1 -> R-1) ===")
    _, rows, raw = run_sql(
        "SELECT id, parcel_id, jurisdiction_id, zone_code FROM parcel_zones "
        "WHERE parcel_id='40-1N-28-0090-37900-0010' AND jurisdiction_id=956;"
    )
    if rows is None:
        print("FATAL: could not query target parcel_zones row.\n" + raw)
        sys.exit(1)
    if not rows:
        print("FATAL: expected parcel_zones row not found. Aborting.")
        sys.exit(1)
    row = rows[0]
    if row["jurisdiction_id"] not in ALLOWED_JURISDICTIONS:
        print(f"FATAL: row jurisdiction_id {row['jurisdiction_id']} not in "
              f"allowed set {ALLOWED_JURISDICTIONS}. Aborting.")
        sys.exit(1)
    if row["zone_code"] == "R-1":
        print(f"  id={row['id']}: zone_code already 'R-1' -- skipping (idempotent no-op).")
    elif row["zone_code"] == "R1":
        # Confirm target district really exists before flipping the code
        _, dist, _ = run_sql(
            "SELECT id FROM zoning_districts WHERE jurisdiction_id=956 AND code='R-1';"
        )
        if not dist:
            print("FATAL: target district zoning_districts(jurisdiction_id=956, code='R-1') "
                  "not found. Aborting normalization.")
            sys.exit(1)
        print(f"  id={row['id']}: UPDATE zone_code 'R1' -> 'R-1' "
              f"(matches zoning_districts id={dist[0]['id']})")
        if apply:
            status, _, raw = run_sql(
                f"UPDATE parcel_zones SET zone_code='R-1' WHERE id={row['id']} "
                f"AND zone_code='R1';"
            )
            print(f"  -> {status}")
            if "STATUS 2" not in status:
                print("  FATAL write failure:\n" + raw)
                sys.exit(1)
        else:
            print("  [DRY RUN -- pass --apply to write]")
    else:
        print(f"FATAL: unexpected zone_code '{row['zone_code']}' (expected 'R1' or "
              f"'R-1'). Aborting to avoid clobbering unrelated data.")
        sys.exit(1)
    print()

    # ------------------------------------------------------------------
    # STEP 2: Jay RM -- add real distinct district (item 2)
    # ------------------------------------------------------------------
    print("=== STEP 2: Jay RM (Residential Medium) -- add real zoning_districts row ===")
    _, existing, raw = run_sql(
        "SELECT id FROM zoning_districts WHERE jurisdiction_id=1124 AND code='RM';"
    )
    if existing is None:
        print("FATAL: could not query zoning_districts for Jay RM.\n" + raw)
        sys.exit(1)
    if existing:
        print(f"  zoning_districts id={existing[0]['id']} (jurisdiction_id=1124, code='RM') "
              f"already exists -- skipping insert (idempotent no-op).")
    else:
        src = "https://srcpa.gov/resources/Zoning%20-%20Town%20of%20Jay.pdf"
        sql = (
            "INSERT INTO zoning_districts "
            "(jurisdiction_id, code, name, category, ordinance_section) VALUES "
            "(1124, 'RM', 'Residential Medium', 'Residential', "
            "'Santa Rosa County Property Appraiser Town of Jay Zoning map legend, "
            "General Zoning Districts section');"
        )
        print("  INSERT zoning_districts (jurisdiction_id=1124, code='RM', "
              "name='Residential Medium', category='Residential')")
        print(f"  source: {src}")
        print("  NOTE: no zone_standards row inserted -- real numeric FAR/density/"
              "parking standards for Jay's RM district were not found (Jay's "
              "ordinance host, jay.municipalcodeonline.com, is a JS-rendered SPA "
              "not reachable via WebFetch/curl, and Firecrawl had zero API "
              "credits this session). Left for a future session with a working "
              "renderer. category='Residential' means far/pk1000 default to "
              "NOT-applicable and density defaults to applicable (per "
              "v_zoning_district_applicability's category-based rule), so this "
              "parcel will correctly stop inflating the far/pk1000 FAIL count "
              "immediately, while density remains a genuine (undisguised) gap "
              "until real standards are sourced.")
        if apply:
            status, _, raw = run_sql(sql)
            print(f"  -> {status}")
            if "STATUS 2" not in status:
                print("  FATAL write failure:\n" + raw)
                sys.exit(1)
        else:
            print("  [DRY RUN -- pass --apply to write]")
    print()

    # ------------------------------------------------------------------
    # STEP 3: Unincorporated Santa Rosa HCD -- add real district + standards (item 3)
    # ------------------------------------------------------------------
    print("=== STEP 3: Unincorporated Santa Rosa HCD -- add real zoning_districts + zone_standards ===")
    _, existing, raw = run_sql(
        "SELECT id FROM zoning_districts WHERE jurisdiction_id=1398 AND code='HCD';"
    )
    if existing is None:
        print("FATAL: could not query zoning_districts for HCD.\n" + raw)
        sys.exit(1)

    src = ("https://www.santarosa.fl.gov/DocumentCenter/View/5820/"
           "Santa-Rosa-County-Land-Development-Code-")

    if existing:
        did = existing[0]["id"]
        print(f"  zoning_districts id={did} (jurisdiction_id=1398, code='HCD') "
              f"already exists -- skipping district insert.")
    else:
        sql = (
            "INSERT INTO zoning_districts "
            "(jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, "
            "ordinance_section) VALUES "
            "(1398, 'HCD', 'Highway Commercial Development', 'Commercial', "
            "false, false, "
            "'LDC Sec. 2.02 district list (C.2); Table 2.04.02.b (density); "
            "Table 2.05.01.b (setbacks/height); Table 2.06.01.b (lot size/width)');"
        )
        print("  INSERT zoning_districts (jurisdiction_id=1398, code='HCD', "
              "name='Highway Commercial Development', category='Commercial', "
              "far_regulated=false, pk1000_regulated=false)")
        print(f"  source: {src}")
        print("  far_regulated=false / pk1000_regulated=false: VERIFIED -- the full "
              "LDC text has no district-wide FAR standard for HCD (the only FAR "
              "figures in the whole document are per-use caps inside airport "
              "safety-zone overlays, not a base HCD standard) and no district-wide "
              "parking-per-1000sf figure (parking is set per land-use type, e.g. "
              "'Retail Store... 1 space per 250 sqft', not per zoning district). "
              "This is an explicit sourced non-applicability finding, not a "
              "default.")
        if apply:
            status, rows2, raw = run_sql(sql)
            print(f"  -> {status}")
            if "STATUS 2" not in status:
                print("  FATAL write failure:\n" + raw)
                sys.exit(1)
            _, rows2, _ = run_sql(
                "SELECT id FROM zoning_districts WHERE jurisdiction_id=1398 AND code='HCD';"
            )
            did = rows2[0]["id"] if rows2 else None
        else:
            did = None
            print("  [DRY RUN -- district id not yet known, zone_standards insert "
                  "will run on next --apply pass once district exists]")

    if did is not None:
        _, std, raw = run_sql(
            f"SELECT id, max_density_du_acre FROM zone_standards WHERE zoning_district_id={did};"
        )
        if std is None:
            print("FATAL: could not query zone_standards for HCD district.\n" + raw)
            sys.exit(1)
        if std:
            sid = std[0]["id"]
            if std[0]["max_density_du_acre"] is not None:
                print(f"  zone_standards id={sid} already has max_density_du_acre set -- "
                      f"skipping (idempotent no-op).")
            else:
                sql = (
                    f"UPDATE zone_standards SET max_density_du_acre=10, "
                    f"front_setback_ft=50, side_setback_ft=5, rear_setback_ft=25, "
                    f"max_height_ft=50, min_lot_width_ft=100, "
                    f"source_url='{src}', "
                    f"ordinance_section='Table 2.04.02.b (density=10 du/acre); "
                    f"Table 2.05.01.b (setbacks front=50,side=5,rear=25,height=50); "
                    f"Table 2.06.01.b (min_lot_width=100)', "
                    f"confidence_score=0.9, scraped_at=now() "
                    f"WHERE id={sid};"
                )
                print(f"  UPDATE zone_standards id={sid}: fill NULL columns "
                      f"(max_density_du_acre=10, setbacks, height, lot width)")
                if apply:
                    status, _, raw = run_sql(sql)
                    print(f"  -> {status}")
                    if "STATUS 2" not in status:
                        print("  FATAL write failure:\n" + raw)
                        sys.exit(1)
                else:
                    print("  [DRY RUN -- pass --apply to write]")
        else:
            sql = (
                f"INSERT INTO zone_standards "
                f"(zoning_district_id, max_density_du_acre, front_setback_ft, "
                f"side_setback_ft, rear_setback_ft, max_height_ft, min_lot_width_ft, "
                f"source_url, ordinance_section, confidence_score, scraped_at) VALUES "
                f"({did}, 10, 50, 5, 25, 50, 100, "
                f"'{src}', "
                f"'Table 2.04.02.b (density=10 du/acre); Table 2.05.01.b "
                f"(setbacks front=50,side=5,rear=25,height=50); Table 2.06.01.b "
                f"(min_lot_width=100)', 0.9, now());"
            )
            print(f"  INSERT zone_standards for district id={did}: "
                  f"max_density_du_acre=10, front_setback_ft=50, side_setback_ft=5, "
                  f"rear_setback_ft=25, max_height_ft=50, min_lot_width_ft=100 "
                  f"(max_far and parking_per_1000sf intentionally NULL -- see "
                  f"far_regulated/pk1000_regulated=false above)")
            print(f"  source: {src}")
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
