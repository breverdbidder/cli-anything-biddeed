#!/usr/bin/env python3
"""GOLD STANDARD miami_dade, letter I -- bucket (b) zoning-link gap, APPLY
step. Adapted, unedited logic from
scripts/gold_standard_miami_dade_i_zoning_apply_20260801.py (see that file
for full rationale, especially the anti-G-regression far_regulated/
density_regulated/pk1000_regulated derivation and the verbatim-hyphenated
parcel_id join-key requirement) -- re-dated per this session's file-naming
convention, original preserved as audit history. NOT a rewrite -- same
guard rails followed exactly, no "improvements".

Consumes /tmp/miamidade_zoning_spatial_matches_okmd.json (produced by
gold_standard_shard2_okmd_9c6b9b03_miamidade_i_zoning_research.py) and, for
every row with a REAL (non-UNINCORPORATED/NONE) municipal zone match:

  1. Inserts any missing `jurisdictions` row for the municipality (idempotent
     NOT-EXISTS-gated; live check at session start found all municipalities
     in this batch already have a jurisdiction row -- kept for safety/re-run).
  2. Inserts a `zoning_districts` row for every (jurisdiction, zone_code)
     pair NOT already present, with EXPLICIT far_regulated/density_regulated/
     pk1000_regulated booleans derived from real MunicipalZone_gdb fields:
       density_regulated = true (DENSITY is populated for every zone here)
       far_regulated = true only when MunicipalZone_gdb's own FAR field is a
         genuine positive parseable number (Miami transect zones T3-* often
         report FAR=0 meaning "not FAR-regulated" -- never fabricate a
         positive cap)
       pk1000_regulated = false always -- Miami-Dade municipal residential
         codes regulate parking per-dwelling-unit, not per-1000sqft; this
         layer has no parking field at all.
  3. Populates zone_standards (max_density_du_acre from DENSITY, max_far from
     FAR when far_regulated, source_url citing the ArcGIS layer).
  4. Inserts `parcel_zones` rows (NOT-EXISTS-gated, idempotent) using the
     real folio VERBATIM in the same hyphenated format as
     multi_county_auctions.parcel_id -- do NOT strip hyphens.

Idempotent: every insert checks for an existing row first. Safe to re-run.

Usage: python3 scripts/gold_standard_shard2_okmd_9c6b9b03_miamidade_i_zoning_apply.py
"""
import os
import re
import json
import httpx
import time

REF = "mocerqjnksmhcjzxrewo"
MGMT_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
SOURCE_URL = "https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/MunicipalZone_gdb/FeatureServer/0"
INPUT_PATH = "/tmp/miamidade_zoning_spatial_matches_okmd.json"


def mgmt_sql(query: str, retries=4):
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


def parse_far(far_val):
    """Return (far_regulated: bool, max_far: float|None)."""
    if far_val is None:
        return False, None
    s = str(far_val).strip()
    if s == "" or s.lower() in ("none", "na", "n/a"):
        return False, None
    m = re.match(r"^-?\d+(\.\d+)?$", s)
    if not m:
        return False, None
    val = float(s)
    if val <= 0:
        return False, None
    return True, val


def parse_density(density_val):
    if density_val is None:
        return None
    s = str(density_val).strip()
    m = re.match(r"^-?\d+(\.\d+)?$", s)
    if not m:
        return None
    return float(s)


def main():
    data = json.load(open(INPUT_PATH))
    real_rows = [r for r in data if not (r["municname"] == "UNINCORPORATED" and r["zone"] == "NONE")]
    unincorp_residual = [r for r in data if r["municname"] == "UNINCORPORATED" and r["zone"] == "NONE"]
    print(f"Loaded {len(data)} total matches, {len(real_rows)} with a real municipal zone code, "
          f"{len(unincorp_residual)} UNINCORPORATED/NONE residual (no municipal zoning coverage).")

    # --- Step 1: ensure jurisdiction rows exist for all municipalities involved.
    juris_by_name = {}
    existing = mgmt_sql("""
      SELECT id, name FROM jurisdictions
      WHERE lower(coalesce(county_name,county)) IN ('miami-dade','miami_dade');
    """)
    for r in existing:
        juris_by_name[r["name"].upper()] = r["id"]

    needed_munis = sorted(set(r["municname"] for r in real_rows))
    for muni_upper in needed_munis:
        if muni_upper in juris_by_name:
            continue
        muni_title = muni_upper.title()
        result = mgmt_sql(f"""
          INSERT INTO jurisdictions (name, county, state, county_name)
          SELECT {sql_str(muni_title)}, 'Miami-Dade', 'FL', 'Miami-Dade'
          WHERE NOT EXISTS (
            SELECT 1 FROM jurisdictions WHERE upper(name) = {sql_str(muni_upper)}
              AND lower(coalesce(county_name,county)) IN ('miami-dade','miami_dade')
          )
          RETURNING id, name;
        """)
        if result:
            juris_by_name[muni_upper] = result[0]["id"]
            print(f"  Inserted jurisdiction: {muni_title} (id={result[0]['id']})")
        else:
            r2 = mgmt_sql(f"""
              SELECT id FROM jurisdictions WHERE upper(name)={sql_str(muni_upper)}
                AND lower(coalesce(county_name,county)) IN ('miami-dade','miami_dade');
            """)
            if r2:
                juris_by_name[muni_upper] = r2[0]["id"]

    existing = mgmt_sql("""
      SELECT id, name FROM jurisdictions
      WHERE lower(coalesce(county_name,county)) IN ('miami-dade','miami_dade');
    """)
    for r in existing:
        juris_by_name[r["name"].upper()] = r["id"]

    # --- Step 2+3: ensure zoning_districts (+ zone_standards) rows exist for every (muni, zone).
    seen_pairs = {}
    for r in real_rows:
        key = (r["municname"], r["zone"])
        seen_pairs[key] = r

    district_id_by_key = {}
    for (muni, zone), r in sorted(seen_pairs.items()):
        jid = juris_by_name.get(muni)
        if jid is None:
            print(f"  SKIP zoning_districts for {muni}/{zone}: no jurisdiction id resolved")
            continue
        existing_d = mgmt_sql(f"""
          SELECT id FROM zoning_districts WHERE jurisdiction_id={jid} AND code={sql_str(zone)};
        """)
        if existing_d:
            district_id_by_key[(muni, zone)] = existing_d[0]["id"]
            continue

        far_regulated, max_far = parse_far(r.get("far"))
        density = parse_density(r.get("density"))
        name = r.get("zonedesc") or zone
        category = {"RSF": "residential", "RMF": "residential", "RC": "residential"}.get(r.get("genrllutype"), None)

        ins = mgmt_sql(f"""
          INSERT INTO zoning_districts
            (jurisdiction_id, code, name, category, description,
             far_regulated, density_regulated, pk1000_regulated)
          VALUES
            ({jid}, {sql_str(zone)}, {sql_str(name)}, {sql_str(category)},
             {sql_str('Sourced from Miami-Dade countywide MunicipalZone_gdb ArcGIS layer (GENRLLUTYPE=' + str(r.get('genrllutype')) + ')')},
             {str(far_regulated).upper()}, TRUE, FALSE)
          ON CONFLICT DO NOTHING
          RETURNING id;
        """)
        if not ins:
            existing_d = mgmt_sql(f"""
              SELECT id FROM zoning_districts WHERE jurisdiction_id={jid} AND code={sql_str(zone)};
            """)
            if not existing_d:
                print(f"  WARNING: insert for {muni}/{zone} returned nothing and no row found -- bug")
                continue
            did = existing_d[0]["id"]
        else:
            did = ins[0]["id"]
        district_id_by_key[(muni, zone)] = did
        print(f"  zoning_districts {muni}/{zone} -> id={did} far_regulated={far_regulated} "
              f"density={density} max_far={max_far}")

        mgmt_sql(f"""
          INSERT INTO zone_standards
            (zoning_district_id, max_far, max_density_du_acre, source_url, confidence_score)
          SELECT {did}, {max_far if max_far is not None else 'NULL'},
                 {density if density is not None else 'NULL'},
                 {sql_str(SOURCE_URL)}, 0.7
          WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id={did});
        """)

    # --- Step 4: insert parcel_zones rows (idempotent, NULL-only via NOT EXISTS).
    inserted = 0
    skipped = 0
    for r in real_rows:
        key = (r["municname"], r["zone"])
        did = district_id_by_key.get(key)
        jid = juris_by_name.get(r["municname"])
        if jid is None:
            skipped += 1
            continue
        pid_raw = r["parcel_id"]
        existing_pz = mgmt_sql(f"""
          SELECT id FROM parcel_zones WHERE jurisdiction_id={jid} AND parcel_id={sql_str(pid_raw)};
        """)
        if existing_pz:
            skipped += 1
            continue
        result = mgmt_sql(f"""
          INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
          VALUES ({sql_str(pid_raw)}, {jid}, {sql_str(r['zone'])}, {sql_str(r.get('zonedesc') or r['zone'])},
                  'miamidade_gis_countywide_zoning:MunicipalZone_gdb_spatial_join')
          RETURNING id;
        """)
        if result:
            inserted += 1
            print(f"  parcel_zones: {r['case_number']} parcel_id={pid_raw} zone={r['zone']} -> id={result[0]['id']}")
        else:
            print(f"  WARNING: parcel_zones insert for {r['case_number']} returned nothing -- bug")

    print(f"\nTotal: jurisdictions ensured, zoning_districts ensured for {len(district_id_by_key)} pairs, "
          f"parcel_zones inserted={inserted} skipped(existing/no-jid)={skipped} out of {len(real_rows)} candidates.")
    print(f"UNINCORPORATED/NONE residual (no municipal zoning coverage in MunicipalZone_gdb): {len(unincorp_residual)} "
          f"cases: {[r['case_number'] for r in unincorp_residual]}")
    if inserted == 0 and len(real_rows) > 0 and skipped < len(real_rows):
        print("WARNING: parsed >0 candidate rows but wrote 0 parcel_zones -- investigate.")


if __name__ == "__main__":
    main()
