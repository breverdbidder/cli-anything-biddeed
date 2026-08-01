#!/usr/bin/env python3
"""GOLD STANDARD miami_dade, letter G regression fix (caused by this session's
letter-I zoning_districts/parcel_zones inserts in
scripts/gold_standard_miami_dade_i_zoning_apply_20260801.py).

Root cause (CONFIRMED via v_zoning_gold_standard_kpi_v3 before/after diff):
this session's new parcel_zones rows link additional parcels into EXISTING,
pre-session zoning_districts codes (Miami Gardens R-1/R-15, Homestead
PUD/R-TH/R-1, North Miami Beach RM-23/RS-4/MU-IB, Doral MF-1/PUD) that were
already missing zone_standards.max_density_du_acre BEFORE this session --
surfacing a pre-existing data gap, not creating a new bug. density metric
dropped 99.3->94.1%, flipping G to FAIL.

This script backfills ONLY zone_standards.max_density_du_acre (NULL-only,
idempotent) for these exact 10 (jurisdiction, code) pairs, using the SAME
real, sourced DENSITY field from Miami-Dade's countywide MunicipalZone_gdb
ArcGIS layer already captured in /tmp/miamidade_zoning_spatial_matches.json
this session -- not a new source, not guessed.

Usage: python3 scripts/gold_standard_miami_dade_g_density_backfill_20260801.py
"""
import os
import time
import httpx

REF = "mocerqjnksmhcjzxrewo"
MGMT_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
SOURCE_URL = "https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/MunicipalZone_gdb/FeatureServer/0"

# (jurisdiction_name, zone_code, max_density_du_acre) -- all sourced live this
# session from MunicipalZone_gdb's DENSITY field (see
# gold_standard_miami_dade_i_zoning_spatial_research_20260801.py output).
BACKFILL = [
    ("Homestead", "PUD", 20.0),
    ("Doral", "MF-1", 10.0),
    ("Miami Gardens", "R-1", 6.0),
    ("Miami Gardens", "R-15", 15.0),
    ("Homestead", "R-1", 4.57),
    ("North Miami Beach", "RM-23", 23.0),
    ("North Miami Beach", "RS-4", 8.0),
    ("Homestead", "R-TH", 8.4),
    ("Doral", "PUD", 10.0),
    ("North Miami Beach", "MU/IB", 40.0),
]


def mgmt_sql(query: str, retries=3):
    h = {"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"}
    last_exc = None
    for attempt in range(retries):
        try:
            r = httpx.post(f"https://api.supabase.com/v1/projects/{REF}/database/query",
                            headers=h, json={"query": query}, timeout=120)
            if r.status_code == 201:
                return r.json()
            last_exc = Exception(f"STATUS {r.status_code}: {r.text[:800]}")
        except Exception as e:
            last_exc = e
        time.sleep(2 * (attempt + 1))
    raise last_exc


def sql_str(v):
    return "'" + str(v).replace("'", "''") + "'"


def main():
    fixed = 0
    for juris_name, code, density in BACKFILL:
        result = mgmt_sql(f"""
          UPDATE zone_standards s
          SET max_density_du_acre = {density}, source_url = COALESCE(s.source_url, {sql_str(SOURCE_URL)})
          FROM zoning_districts d, jurisdictions j
          WHERE s.zoning_district_id = d.id
            AND d.jurisdiction_id = j.id
            AND j.name = {sql_str(juris_name)}
            AND d.code = {sql_str(code)}
            AND s.max_density_du_acre IS NULL
          RETURNING s.zoning_district_id;
        """)
        if result:
            print(f"  {juris_name}/{code}: backfilled max_density_du_acre={density}")
            fixed += 1
        else:
            # Might mean zone_standards row doesn't exist yet, or already non-null. Check which.
            check = mgmt_sql(f"""
              SELECT s.id, s.max_density_du_acre FROM zoning_districts d
              JOIN jurisdictions j ON j.id=d.jurisdiction_id
              LEFT JOIN zone_standards s ON s.zoning_district_id=d.id
              WHERE j.name={sql_str(juris_name)} AND d.code={sql_str(code)};
            """)
            if check and check[0].get("id") is None:
                # No zone_standards row exists at all -- insert one.
                did = mgmt_sql(f"""
                  SELECT d.id FROM zoning_districts d JOIN jurisdictions j ON j.id=d.jurisdiction_id
                  WHERE j.name={sql_str(juris_name)} AND d.code={sql_str(code)};
                """)[0]["id"]
                ins = mgmt_sql(f"""
                  INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, confidence_score)
                  SELECT {did}, {density}, {sql_str(SOURCE_URL)}, 0.7
                  WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id={did})
                  RETURNING id;
                """)
                if ins:
                    print(f"  {juris_name}/{code}: inserted new zone_standards row, max_density_du_acre={density}")
                    fixed += 1
                else:
                    print(f"  {juris_name}/{code}: WARNING insert returned nothing")
            else:
                print(f"  {juris_name}/{code}: no-op (already non-null: {check[0].get('max_density_du_acre') if check else 'row not found'})")

    print(f"\nTotal backfilled: {fixed} of {len(BACKFILL)}")


if __name__ == "__main__":
    main()
