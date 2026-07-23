#!/usr/bin/env python3
"""Turn the gs-shard10-volusia-hamilton-research workflow's zoning research
output into a zoning_districts + zone_standards SQL migration.

Usage: python3 gold_standard_shard10_apply_zoning_research.py workflow_result.json > migration.sql

Only emits zone_standards rows for CONFIRMED values (never UNKNOWN/null) --
this is the honesty gate. UNKNOWN codes still get a zoning_districts row
(with far_regulated/pk1000_regulated/density_regulated set false where the
research explicitly found "no ordinance value" for a non-residential/
commercial category) so the applicability view can correctly mark them N/A
rather than leaving them silently missing.
"""
import json
import sys

JUR_ID = {
    'Daytona Beach': 938, 'DeBary': 1139, 'DeLand': 823, 'Deltona': 897,
    'Edgewater': 1135, 'Holly Hill': 1136, 'Lake Helen': 1141,
    'New Smyrna Beach': 911, 'Oak Hill': 1143, 'Orange City': 1138,
    'Ormond Beach': 819, 'Pierson': 1142, 'Port Orange': 885,
    'South Daytona': 1137,
}


def jur_expr(jurisdiction_label):
    # research agents return a human label like "City of Deltona, Volusia County, FL"
    # or "Unincorporated Volusia County, FL" or "Daytona Beach Shores, Volusia County, FL"
    low = jurisdiction_label.lower()
    if 'unincorporated' in low:
        return "(SELECT id FROM jurisdictions WHERE name='Volusia County (Unincorporated)')"
    if 'daytona beach shores' in low:
        return "(SELECT id FROM jurisdictions WHERE name='Daytona Beach Shores')"
    for name, jid in JUR_ID.items():
        if name.lower() in low:
            return str(jid)
    raise ValueError(f"unmapped jurisdiction label: {jurisdiction_label}")


def esc(s):
    if s is None:
        return None
    return str(s).replace("'", "''")


def sql_val(v, numeric=False):
    if v is None:
        return 'NULL'
    if numeric:
        return str(v)
    return f"'{esc(v)}'"


def main():
    data = json.load(open(sys.argv[1]))
    zoning = data.get('zoning', data)  # allow either the full workflow result or just the zoning array
    if isinstance(zoning, dict) and 'zoning' in zoning:
        zoning = zoning['zoning']

    district_rows = []
    standards_rows = []
    skipped = []

    for entry in zoning:
        jur_label = entry.get('jurisdiction') or entry['result']['jurisdiction']
        result = entry.get('result', entry)
        try:
            jexpr = jur_expr(jur_label)
        except ValueError as e:
            skipped.append(str(e))
            continue
        for c in result.get('codes', []):
            code = c['code']
            category = c.get('category', 'other')
            far_reg = c.get('max_far') is not None
            pk_reg = c.get('parking_per_1000sf') is not None
            dens_reg = c.get('max_density_du_acre') is not None
            # For UNKNOWN confirmed-absent standards (e.g. code confirmed to have
            # no ordinance FAR at all, not just "we didn't check"), we still want
            # far_regulated/pk1000_regulated explicit-false so the applicability
            # view doesn't default them on for commercial/industrial codes.
            note = (c.get('note') or '').replace("'", "''")
            name = f"{code} ({category})"
            district_rows.append(
                f"(({jexpr}), '{esc(code)}', '{esc(name)}', '{esc(category)}', "
                f"{sql_val(c.get('ordinance_section'))}, "
                f"{str(far_reg).upper() if c.get('confidence')=='CONFIRMED' else 'NULL'}, "
                f"{str(dens_reg).upper() if c.get('confidence')=='CONFIRMED' else 'NULL'}, "
                f"{str(pk_reg).upper() if c.get('confidence')=='CONFIRMED' else 'NULL'})"
            )
            if c.get('confidence') == 'CONFIRMED' and (c.get('max_density_du_acre') is not None or c.get('max_far') is not None or c.get('parking_per_1000sf') is not None):
                standards_rows.append({
                    'jexpr': jexpr, 'code': code,
                    'density': c.get('max_density_du_acre'),
                    'far': c.get('max_far'),
                    'pk': c.get('parking_per_1000sf'),
                    'section': c.get('ordinance_section'),
                    'note': note,
                    'url': result.get('source_ordinance_url', ''),
                })

    out = []
    out.append("-- GOLD STANDARD SHARD-10: Volusia G fix -- real ordinance-sourced zoning_districts + zone_standards")
    out.append("-- Every CONFIRMED value below traces to actual ordinance/GIS-crosswalk text read by a live research")
    out.append("-- agent (Municode, county GRM Zoning Classification Summary Sheets, or the county's own GIS crosswalk).")
    out.append("-- UNKNOWN codes get a zoning_districts row (so parcel_zones joins resolve) but NO zone_standards row --")
    out.append("-- an honest gap, not a guess. See gold_standard_ultraloop_audit for the research provenance.")
    out.append("SET statement_timeout = 0;")
    out.append("")
    out.append("INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, density_regulated, pk1000_regulated)")
    out.append("VALUES\n" + ",\n".join(district_rows) + "\nON CONFLICT (jurisdiction_id, code) DO UPDATE SET category=EXCLUDED.category, ordinance_section=EXCLUDED.ordinance_section, far_regulated=EXCLUDED.far_regulated, density_regulated=EXCLUDED.density_regulated, pk1000_regulated=EXCLUDED.pk1000_regulated;")
    out.append("")
    out.append("INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, ordinance_section, source_url, confidence_score)")
    std_rows = []
    for s in standards_rows:
        std_rows.append(
            f"((SELECT id FROM zoning_districts WHERE jurisdiction_id=({s['jexpr']}) AND code='{esc(s['code'])}'), "
            f"{sql_val(s['density'], numeric=True)}, {sql_val(s['far'], numeric=True)}, {sql_val(s['pk'], numeric=True)}, "
            f"{sql_val(s['section'])}, {sql_val(s['url'])}, 1.0)"
        )
    out.append("VALUES\n" + ",\n".join(std_rows) + "\nON CONFLICT (zoning_district_id) DO UPDATE SET max_density_du_acre=EXCLUDED.max_density_du_acre, max_far=EXCLUDED.max_far, parking_per_1000sf=EXCLUDED.parking_per_1000sf, ordinance_section=EXCLUDED.ordinance_section, source_url=EXCLUDED.source_url;")
    out.append("")
    out.append("SELECT * FROM v_zoning_gold_standard_kpi_v3 WHERE county='volusia';")

    print('\n'.join(out))
    if skipped:
        print('\n'.join(f'-- SKIPPED: {s}' for s in skipped), file=sys.stderr)


if __name__ == "__main__":
    main()
