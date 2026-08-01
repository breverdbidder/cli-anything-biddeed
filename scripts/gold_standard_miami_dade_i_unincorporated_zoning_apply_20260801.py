#!/usr/bin/env python3
"""GOLD STANDARD miami_dade, letter I -- unincorporated-county zoning-link
gap, APPLY step. Consumes /tmp/miamidade_unincorporated_zoning_matches.json
(scripts/gold_standard_miami_dade_i_unincorporated_zoning_research_20260801.py).

Of the 36 matched (parcel, zone) pairs, 30 use zone codes ALREADY present in
zoning_districts under jurisdiction 626 (Miami-Dade County Unincorporated) --
confirmed live (RU-1, RU-1MA once inserted, RU-1Z, RU-2, RU-3M, RU-4L, RU-4M,
RU-TH, BU-1, EU-M, GU all checked) -- these just need a parcel_zones insert,
zero G-regression risk (applicability already resolved for these codes).

6 genuinely NEW codes for this jurisdiction (GU, EU-M, RU-TH, RU-1MA, RU-1Z,
RU-4M) get a zoning_districts row first, with explicit density_regulated
derived from the MD_MDCZoning layer's own ZONE_DESC text:
  RU-TH ("Townhouse District, 8.5 units/net acre") -> density_regulated=true, 8.5
  RU-4M ("Modified Apartment House District, 35.9 units/net acre") -> true, 35.9
  GU/EU-M/RU-1MA/RU-1Z (lot-area-based single-family descriptions, e.g.
    "minimum lot area 15,000 ft2 net" / "5,000 ft2 net" / "4,500 ft2 net",
    NO units/acre figure given) -> density_regulated=FALSE (honest not-
    applicable -- these are minimum-lot-size codes, not density-cap codes,
    same pattern as the Kissimmee FBC precedent documented in this repo's
    other Gold Standard sessions: don't fabricate a du/acre figure the
    source doesn't provide).
far_regulated=false and pk1000_regulated=false for all 6 (all single-
family/townhouse residential, MD_MDCZoning provides no FAR/parking field at
all -- consistent with the existing RU-* codes' own far_regulated=NULL/
pk1000_regulated=NULL pattern, which the applicability view resolves to
false for residential subtypes anyway).

Idempotent (existence checks before every insert). Safe to re-run.

Usage: python3 scripts/gold_standard_miami_dade_i_unincorporated_zoning_apply_20260801.py
"""
import os
import re
import time
import json
import httpx

REF = "mocerqjnksmhcjzxrewo"
MGMT_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
SOURCE_URL = "https://gisweb.miamidade.gov/arcgis/rest/services/MD_MDCZoning/MapServer/6"
UNINC_JURISDICTION_ID = 626

NEW_CODE_DENSITY = {
    "RU-TH": 8.5,
    "RU-4M": 35.9,
    "GU": None,
    "EU-M": None,
    "RU-1MA": None,
    "RU-1Z": None,
}


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
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def main():
    rows = json.load(open("/tmp/miamidade_unincorporated_zoning_matches.json"))
    print(f"Loaded {len(rows)} unincorporated zoning matches.")

    existing_codes = {r["code"] for r in mgmt_sql(
        f"SELECT code FROM zoning_districts WHERE jurisdiction_id={UNINC_JURISDICTION_ID};")}
    print(f"Existing codes for jurisdiction {UNINC_JURISDICTION_ID}: {sorted(existing_codes)}")

    distinct_new = {r["zone"] for r in rows} - existing_codes
    print(f"Genuinely new codes needed: {sorted(distinct_new)}")

    district_id_by_code = {}
    for code in distinct_new:
        density = NEW_CODE_DENSITY.get(code)
        density_regulated = density is not None
        sample = next(r for r in rows if r["zone"] == code)
        ins = mgmt_sql(f"""
          INSERT INTO zoning_districts
            (jurisdiction_id, code, name, category, description,
             far_regulated, density_regulated, pk1000_regulated)
          SELECT {UNINC_JURISDICTION_ID}, {sql_str(code)}, {sql_str(sample['zone_desc'])}, 'residential',
                 {sql_str('Sourced from Miami-Dade MD_MDCZoning MapServer layer 6 (Unincorporated Zoning)')},
                 FALSE, {str(density_regulated).upper()}, FALSE
          WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id={UNINC_JURISDICTION_ID} AND code={sql_str(code)})
          RETURNING id;
        """)
        if ins:
            did = ins[0]["id"]
            print(f"  Inserted zoning_districts {code} -> id={did} density_regulated={density_regulated} density={density}")
            if density is not None:
                mgmt_sql(f"""
                  INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, confidence_score)
                  SELECT {did}, {density}, {sql_str(SOURCE_URL)}, 0.7
                  WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id={did});
                """)
        else:
            existing = mgmt_sql(f"""
              SELECT id FROM zoning_districts WHERE jurisdiction_id={UNINC_JURISDICTION_ID} AND code={sql_str(code)};
            """)
            did = existing[0]["id"] if existing else None
            print(f"  {code}: already existed (race) -> id={did}")
        district_id_by_code[code] = did

    # parcel_zones inserts for ALL 36 rows (both existing and new codes).
    inserted = 0
    skipped = 0
    for r in rows:
        pid_raw = r["parcel_id"]
        code = r["zone"]
        existing_pz = mgmt_sql(f"""
          SELECT id FROM parcel_zones WHERE jurisdiction_id={UNINC_JURISDICTION_ID} AND parcel_id={sql_str(pid_raw)};
        """)
        if existing_pz:
            skipped += 1
            continue
        result = mgmt_sql(f"""
          INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
          VALUES ({sql_str(pid_raw)}, {UNINC_JURISDICTION_ID}, {sql_str(code)}, {sql_str(r.get('zone_desc') or code)},
                  'miamidade_gisweb_md_mdczoning_layer6_spatial_join')
          RETURNING id;
        """)
        if result:
            inserted += 1
            print(f"  parcel_zones: {r['case_number']} parcel_id={pid_raw} zone={code} -> id={result[0]['id']}")
        else:
            print(f"  WARNING: parcel_zones insert for {r['case_number']} returned nothing -- bug")

    print(f"\nTotal: {len(distinct_new)} new zoning_districts, parcel_zones inserted={inserted} "
          f"skipped(existing)={skipped} out of {len(rows)} candidates.")
    if inserted == 0 and len(rows) > 0 and skipped < len(rows):
        print("WARNING: parsed >0 candidate rows but wrote 0 parcel_zones -- investigate.")


if __name__ == "__main__":
    main()
