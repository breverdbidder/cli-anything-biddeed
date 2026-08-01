#!/usr/bin/env python3
"""GOLD STANDARD miami_dade, letter I -- bucket (b) zoning-link-only gap
(87 rows after the geo backfill in
scripts/gold_standard_miami_dade_i_geo_backfill_20260801.py moved 36 rows
from bucket-a into this bucket). RESEARCH ONLY -- no DB writes. Produces
/tmp/miamidade_zoning_spatial_matches.json for a follow-up, deliberate
insert step that respects the documented G-regression guard rail (prior
session GOLD_STANDARD_SHARD12_MIAMI_DADE_RUN3786_SESSION_REPORT.md /
scripts/gold_standard_shard2_83c11ccb_miamidade_i_geo_and_zoning_research.py):
inserting a parcel_zones row whose zone_code has NO matching zoning_districts
row makes v_zoning_district_applicability default far/pk1000_applicable to
TRUE with NULL max_far/parking_per_1000sf, dragging G below the 95% gate.

For each gap-b row (has address+geo+value+parcel_id, but parcel_id doesn't
appear in v_zoning_gold_standard_card with zone_code IS NOT NULL), this
script:
  1. Point-in-polygon queries Miami-Dade's own countywide MunicipalZone_gdb
     ArcGIS layer (services.arcgis.com/8Pc9XBTAsYuxx9Ny/.../MunicipalZone_gdb)
     at the row's lat/long.
  2. Records MUNICNAME, ZONE, ZONEDESC, GENRLLUTYPE, DENSITY, FAR, MAXHEIGHT,
     MAXLOTCOV, MINLOTSIZE.
  3. Cross-references ZONE against the jurisdiction's EXISTING zoning_districts
     rows (already in the DB) to classify each match as:
       - existing_code: a parcel_zones row can be inserted immediately, safe
         (zoning_districts + applicability already resolved for this code).
       - new_code: inserting parcel_zones would need a companion
         zoning_districts row first (deferred to an explicit follow-up
         insert step, not done by this research script).

Usage: python3 scripts/gold_standard_miami_dade_i_zoning_spatial_research_20260801.py
"""
import os
import json
import time
import httpx

REF = "mocerqjnksmhcjzxrewo"
MGMT_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]

MUNI_ZONE_BASE = "https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/MunicipalZone_gdb/FeatureServer/0"


def mgmt_sql(query: str, retries=3):
    h = {"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"}
    last_exc = None
    for attempt in range(retries):
        try:
            r = httpx.post(f"https://api.supabase.com/v1/projects/{REF}/database/query",
                            headers=h, json={"query": query}, timeout=120)
            if r.status_code == 201:
                return r.json()
            last_exc = Exception(f"STATUS {r.status_code}: {r.text[:500]}")
        except Exception as e:
            last_exc = e
        time.sleep(2 * (attempt + 1))
    raise last_exc


def point_in_zone(lat, lng):
    r = httpx.get(f"{MUNI_ZONE_BASE}/query", params={
        "geometry": f"{lng},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "MUNICNAME,ZONE,ZONEDESC,GENRLLUTYPE,DENSITY,FAR,MAXHEIGHT,MAXLOTCOV,MINLOTSIZE",
        "returnGeometry": "false",
        "f": "json",
    }, timeout=30)
    r.raise_for_status()
    data = r.json()
    feats = data.get("features", [])
    if not feats:
        return None
    return feats[0]["attributes"]


def main():
    rows = mgmt_sql("""
      WITH scope AS (
        SELECT * FROM multi_county_auctions
        WHERE lower(county) = 'miami_dade'
          AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false) = true)
      ),
      zc AS (
        SELECT DISTINCT parcel_id, tax_account
        FROM v_zoning_gold_standard_card
        WHERE lower(county) = norm_county_key('miami_dade') AND zone_code IS NOT NULL
      )
      SELECT id, case_number, parcel_id, property_address,
        COALESCE(latitude, po_latitude::double precision) AS lat,
        COALESCE(longitude, po_longitude::double precision) AS lng
      FROM scope
      WHERE (property_address IS NOT NULL
           AND COALESCE(latitude, po_latitude::double precision) IS NOT NULL
           AND COALESCE(longitude, po_longitude::double precision) IS NOT NULL
           AND COALESCE(assessed_value, market_value) IS NOT NULL
           AND parcel_id IS NOT NULL)
           AND NOT (parcel_id IN (SELECT parcel_id FROM zc) OR parcel_id IN (SELECT tax_account FROM zc WHERE tax_account IS NOT NULL))
      ORDER BY case_number;
    """)
    print(f"Found {len(rows)} bucket-b (zoning-link-only) gap rows.")

    # Existing (jurisdiction_name -> set of zone_code) already in zoning_districts, for classification.
    existing = mgmt_sql("""
      SELECT j.name AS jurisdiction_name, j.id AS jurisdiction_id, d.code
      FROM zoning_districts d
      JOIN jurisdictions j ON j.id = d.jurisdiction_id
      WHERE lower(coalesce(j.county_name, j.county)) IN ('miami-dade','miami_dade');
    """)
    existing_codes = {}
    juris_id_by_name = {}
    for r in existing:
        name = r["jurisdiction_name"]
        existing_codes.setdefault(name, set()).add(r["code"])
        juris_id_by_name[name] = r["jurisdiction_id"]

    results = []
    no_zone_match = 0
    for row in rows:
        try:
            zone_attrs = point_in_zone(row["lat"], row["lng"])
        except Exception as e:
            print(f"  {row['case_number']}: query error {e}")
            zone_attrs = None
        if not zone_attrs or not zone_attrs.get("ZONE"):
            print(f"  {row['case_number']} ({row['property_address']}): NO MunicipalZone_gdb match")
            no_zone_match += 1
            continue
        muni = zone_attrs.get("MUNICNAME")
        zone = zone_attrs.get("ZONE")
        is_existing = zone in existing_codes.get(muni, set())
        results.append({
            "id": row["id"],
            "case_number": row["case_number"],
            "parcel_id": row["parcel_id"],
            "property_address": row["property_address"],
            "lat": row["lat"], "lng": row["lng"],
            "municname": muni,
            "jurisdiction_id": juris_id_by_name.get(muni),
            "zone": zone,
            "zonedesc": zone_attrs.get("ZONEDESC"),
            "genrllutype": zone_attrs.get("GENRLLUTYPE"),
            "density": zone_attrs.get("DENSITY"),
            "far": zone_attrs.get("FAR"),
            "maxheight": zone_attrs.get("MAXHEIGHT"),
            "maxlotcov": zone_attrs.get("MAXLOTCOV"),
            "minlotsize": zone_attrs.get("MINLOTSIZE"),
            "code_status": "existing_code" if is_existing else "new_code",
        })
        print(f"  {row['case_number']}: MUNICNAME={muni!r} ZONE={zone!r} GENRLLUTYPE={zone_attrs.get('GENRLLUTYPE')!r} "
              f"[{'existing_code' if is_existing else 'NEW_CODE'}]")
        time.sleep(0.1)

    existing_ct = sum(1 for r in results if r["code_status"] == "existing_code")
    new_ct = sum(1 for r in results if r["code_status"] == "new_code")
    print(f"\nTotal matched: {len(results)} (existing_code={existing_ct}, new_code={new_ct})  "
          f"no_zone_match={no_zone_match}  scanned={len(rows)}")

    with open("/tmp/miamidade_zoning_spatial_matches.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("Wrote /tmp/miamidade_zoning_spatial_matches.json")


if __name__ == "__main__":
    main()
