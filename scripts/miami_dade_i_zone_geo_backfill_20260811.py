#!/usr/bin/env python3
"""GOLD STANDARD miami_dade, letter I -- dispatch 8d4cd6c7 / workstream md_I.

Fixes the 33 (of 51 total gap) rows that have a real, usable parcel_id
(hyphenated 10-13 digit folio format matching multi_county_auctions.parcel_id)
by:

  1. Geocoding (lat/lng + verifying property_address) via Miami-Dade's
     AddressSearchMap_PropertiesWithZip/MapServer/1 FOLIO query, for the 19
     rows missing latitude/longitude and/or property_address.
  2. Point-in-polygon zoning lookup via the countywide MunicipalZone_gdb
     FeatureServer (services.arcgis.com/8Pc9XBTAsYuxx9Ny) -- covers BOTH
     unincorporated and municipal parcels with one layer, using the parcel
     centroid, for all 33 rows (16 already-complete-card zone-gap rows + the
     19 geo-gap rows once geocoded).
  3. Ensures jurisdictions / zoning_districts / zone_standards rows exist,
     then inserts parcel_zones rows (idempotent, NOT EXISTS-guarded).

The remaining 13 gap rows (of 51) have NO usable parcel_id (NULL, or garbage
placeholder text like 'Property Appraiser' / 'MULTIPLE PARCELS') AND no
property_address -- these are empty stub records from realtaxdeed/unknown
scrape sources with zero plaintiff/address data. They are a structural
blocker: fixing them requires a court-docket lookup by case_number to
discover a real parcel/address, which is out of scope for a spatial-GIS
zoning fix. Reported honestly, not forced.

Usage: python3 scripts/miami_dade_i_zone_geo_backfill_20260811.py
"""
import os
import re
import time
import json
import httpx

REF = "mocerqjnksmhcjzxrewo"
MGMT_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

PROPERTY_LAYER = "https://gisweb.miamidade.gov/arcgis/rest/services/AddressSearchMap_PropertiesWithZip/MapServer/1/query"
ZONING_LAYER = "https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/MunicipalZone_gdb/FeatureServer/0/query"
# The countywide MunicipalZone_gdb layer stores a real placeholder
# MUNICNAME='UNINCORPORATED'/ZONE='NONE' feature (verified live, OBJECTID=2629,
# ZONEDESC='NONE', DENSITY/FAR/MINLOTSIZE all '0') meaning "this parcel is in
# unincorporated Miami-Dade, not covered by this municipal layer" -- NOT a real
# zone code. For those points we must fall back to the county's own dedicated
# Unincorporated Zoning layer, which DOES carry real zone codes (e.g. RU-3M, AU).
UNINCORP_ZONING_LAYER = "https://gisweb.miamidade.gov/arcgis/rest/services/LandManagement/MD_Zoning/MapServer/1/query"

# The 33 rows with a real parcel_id, from the live gap query (case_number -> parcel_id).
# 16 already have complete address/geo/value (pure zone-gap).
# 17 are missing lat/lng only. 2 are missing property_address only.
CANDIDATES = {
    # pure zone-gap (card already complete)
    "2011-043379-CA-01": "30-5902-005-0760",
    "2019-002201-CA-01": "30-5904-065-0620",
    "2019-026350-CA-01": "30-6934-021-4860",
    "2020-005042-CA-01": "30-5902-039-0270",
    "2022-022739-CA-01": "30-5921-018-0090",
    "2024-003696-CA-01": "30-5032-037-0110",
    "2024-016654-CA-01": "30-6926-026-0050",
    "2025-006136-CA-01": "30-2205-037-1640",
    "2025-007496-CA-01": "30-3104-003-5140",
    "2025-008657-CA-01": "30-4922-032-1880",
    "2025-016135-CA-01": "30-2232-015-0450",
    "2025-018364-CA-01": "30-6030-003-6690",
    "2025-018560-CA-01": "30-2204-050-0050",
    "2025-023434-CA-01": "30-3056-054-0120",
    "2026-001478-CA-01": "30-2205-048-0580",
    "2026A00191": "30-5032-004-1300",
    # missing lat/lng (need geocode + zoning)
    "2024-008781-CA-01": "34-2102-008-0420",
    "2025-007971-CA-01": "30-5922-007-0190",
    "2025-009306-CA-01": "10-7921-026-3000",
    "2025-010211-CA-01": "10-7916-002-2490",
    "2025-010500-CA-01": "04-3105-004-0730",
    "2025-013100-CA-01": "31-2211-073-0040",
    "2025-014301-CA-01": "30-2127-034-1110",
    "2025-015181-CA-01": "10-7917-020-0550",
    "2025-016017-CA-01": "02-3211-023-0880",
    "2025-016565-CA-01": "24-5205-059-0800",
    "2025-021159-CA-01": "10-7921-029-1120",
    "2025-021836-CA-01": "23-3209-037-0280",
    "2025-021985-CA-01": "10-7920-013-2740",
    "2025-021988-CA-01": "06-2230-059-1410",
    "2025-074993-CC-05": "07-2208-002-0271",
    "2026-002752-CA-01": "30-2123-002-0260",
    "2026-007833-CA-01": "06-2219-010-0730",
    # missing property_address only (has geo already)
    "2026A00187": "01-4104-013-0290",
    "2026A00192": "30-3112-023-0720",
}


def rest_get(path, params, retries=5):
    h = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
    last_exc = None
    for attempt in range(retries):
        try:
            r = httpx.get(f"{SUPABASE_URL}/rest/v1/{path}", headers=h, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            last_exc = Exception(f"STATUS {r.status_code}: {r.text[:300]}")
        except Exception as e:
            last_exc = e
        time.sleep(2 * (attempt + 1))
    raise last_exc


def rest_patch(path, params, body, retries=5):
    h = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}",
         "Content-Type": "application/json", "Prefer": "return=minimal"}
    last_exc = None
    for attempt in range(retries):
        try:
            r = httpx.patch(f"{SUPABASE_URL}/rest/v1/{path}", headers=h, params=params, json=body, timeout=30)
            if r.status_code in (200, 204):
                return r
            last_exc = Exception(f"STATUS {r.status_code}: {r.text[:300]}")
        except Exception as e:
            last_exc = e
        time.sleep(2 * (attempt + 1))
    raise last_exc


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


def to_folio(parcel_id: str) -> str:
    return re.sub(r"\D", "", parcel_id)


def polygon_centroid(rings):
    """Simple average-of-vertices centroid (good enough for point-in-polygon re-query)."""
    pts = [pt for ring in rings for pt in ring]
    n = len(pts)
    x = sum(p[0] for p in pts) / n
    y = sum(p[1] for p in pts) / n
    return x, y


def geocode_folio(folio: str):
    params = {"where": f"FOLIO='{folio}'", "outFields": "FOLIO,address,zipcode",
              "returnGeometry": "true", "outSR": "4326", "f": "json"}
    r = httpx.get(PROPERTY_LAYER, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    feats = data.get("features", [])
    if not feats:
        return None
    f = feats[0]
    addr = (f["attributes"].get("address") or "").strip()
    addr = re.sub(r"\s+", " ", addr)
    geom = f.get("geometry")
    if not geom or "rings" not in geom:
        return {"address": addr, "lat": None, "lng": None}
    x, y = polygon_centroid(geom["rings"])
    return {"address": addr, "lat": y, "lng": x}


def zoning_lookup_unincorporated(lng: float, lat: float):
    """Fallback: county's own Unincorporated Zoning layer (real ZONE codes,
    e.g. RU-3M, AU -- NOT the 'NONE' placeholder from MunicipalZone_gdb)."""
    params = {"geometry": f"{lng},{lat}", "geometryType": "esriGeometryPoint", "inSR": "4326",
              "spatialRel": "esriSpatialRelIntersects",
              "outFields": "ZONE,ZONE_DESC,MUNC", "returnGeometry": "false", "f": "json"}
    r = httpx.get(UNINCORP_ZONING_LAYER, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    feats = data.get("features", [])
    if not feats:
        return None
    a = feats[0]["attributes"]
    zone = (a.get("ZONE") or "").strip()
    if not zone or zone.upper() == "NONE":
        return None
    return {"MUNICNAME": "UNINCORPORATED", "ZONE": zone, "ZONEDESC": a.get("ZONE_DESC"),
            "MINLOTSIZE": None, "DENSITY": None, "FAR": None, "MAXHEIGHT": None,
            "GENRLLUTYPE": None, "_source_layer": UNINCORP_ZONING_LAYER}


def zoning_lookup(lng: float, lat: float):
    params = {"geometry": f"{lng},{lat}", "geometryType": "esriGeometryPoint", "inSR": "4326",
              "spatialRel": "esriSpatialRelIntersects",
              "outFields": "MUNICNAME,ZONE,ZONEDESC,MINLOTSIZE,DENSITY,FAR,MAXHEIGHT,GENRLLUTYPE",
              "returnGeometry": "false", "f": "json"}
    r = httpx.get(ZONING_LAYER, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    feats = data.get("features", [])
    if not feats:
        return None
    attrs = feats[0]["attributes"]
    # MunicipalZone_gdb encodes "not covered by this layer" as a REAL feature
    # with MUNICNAME='UNINCORPORATED'/ZONE='NONE' (verified live, OBJECTID=2629).
    # That is not a real zone code -- never write it. Fall back to the
    # dedicated Unincorporated Zoning layer instead.
    if (attrs.get("MUNICNAME") or "").strip().upper() == "UNINCORPORATED" and \
       (attrs.get("ZONE") or "").strip().upper() in ("NONE", ""):
        fallback = zoning_lookup_unincorporated(lng, lat)
        return fallback
    attrs["_source_layer"] = ZONING_LAYER
    return attrs


def parse_far(far_val):
    if far_val is None:
        return False, None
    s = str(far_val).strip()
    if s == "" or s.lower() in ("none", "na", "n/a"):
        return False, None
    if not re.match(r"^-?\d+(\.\d+)?$", s):
        return False, None
    val = float(s)
    if val <= 0:
        return False, None
    return True, val


def parse_density(density_val):
    if density_val is None:
        return None
    s = str(density_val).strip()
    if not re.match(r"^-?\d+(\.\d+)?$", s):
        return None
    return float(s)


def main():
    print(f"Processing {len(CANDIDATES)} candidate rows...")

    # Step A: geocode rows missing geo/address.
    geo_results = {}
    rows = rest_get("multi_county_auctions",
                     {"county": "eq.miami_dade",
                      "case_number": "in.(" + ",".join(f'"{c}"' for c in CANDIDATES) + ")",
                      "select": "case_number,parcel_id,property_address,latitude,longitude,po_latitude,po_longitude,assessed_value,market_value"})
    row_by_case = {r["case_number"]: r for r in rows}

    geocode_updates = 0
    for case_number, parcel_id in CANDIDATES.items():
        row = row_by_case.get(case_number)
        if row is None:
            print(f"  WARNING: {case_number} not found in live table anymore, skip")
            continue
        needs_geo = row.get("latitude") is None and row.get("po_latitude") is None
        needs_addr = row.get("property_address") is None
        if not (needs_geo or needs_addr):
            continue
        folio = to_folio(parcel_id)
        g = geocode_folio(folio)
        if g is None:
            print(f"  GEOCODE MISS: {case_number} folio={folio} -- no feature in AddressSearchMap Property layer")
            continue
        geo_results[case_number] = g
        patch = {}
        if needs_addr and g["address"]:
            patch["property_address"] = g["address"] + ", FL"
        if needs_geo and g["lat"] is not None and g["lng"] is not None:
            patch["latitude"] = g["lat"]
            patch["longitude"] = g["lng"]
        if patch:
            rest_patch("multi_county_auctions",
                        {"county": "eq.miami_dade", "case_number": f"eq.{case_number}"},
                        patch)
            geocode_updates += 1
            print(f"  GEOCODED {case_number} folio={folio}: {patch}")
        time.sleep(0.15)

    print(f"\nGeocode step: {geocode_updates} rows patched (address/geo) via "
          f"AddressSearchMap_PropertiesWithZip/MapServer/1 (FOLIO query).")

    # Step B: point-in-polygon zoning lookup for ALL candidates using best-known lat/lng.
    zone_matches = []
    for case_number, parcel_id in CANDIDATES.items():
        row = row_by_case.get(case_number, {})
        lat = row.get("latitude") or row.get("po_latitude")
        lng = row.get("longitude") or row.get("po_longitude")
        if lat is None or lng is None:
            g = geo_results.get(case_number)
            if g and g["lat"] is not None:
                lat, lng = g["lat"], g["lng"]
        if lat is None or lng is None:
            print(f"  NO GEO for zoning lookup: {case_number}")
            continue
        z = zoning_lookup(float(lng), float(lat))
        if z is None:
            print(f"  ZONING MISS: {case_number} parcel_id={parcel_id} at ({lat},{lng})")
            continue
        z["case_number"] = case_number
        z["parcel_id"] = parcel_id
        zone_matches.append(z)
        print(f"  ZONE {case_number} parcel_id={parcel_id} -> {z['MUNICNAME']}/{z['ZONE']}")
        time.sleep(0.15)

    json.dump(zone_matches, open("/tmp/miamidade_i_zone_geo_matches_20260811.json", "w"), indent=2)
    print(f"\nZoning lookup step: {len(zone_matches)} of {len(CANDIDATES)} candidates matched a zone polygon "
          f"via MunicipalZone_gdb FeatureServer (point-in-polygon).")

    # Step C: ensure jurisdictions exist for every distinct MUNICNAME.
    existing_j = mgmt_sql("""
      SELECT id, upper(name) AS uname FROM jurisdictions
      WHERE lower(coalesce(county_name,county)) IN ('miami-dade','miami_dade');
    """)
    juris_by_name = {r["uname"]: r["id"] for r in existing_j}

    distinct_munis = sorted({z["MUNICNAME"] for z in zone_matches if z.get("MUNICNAME")})
    for muni in distinct_munis:
        key = muni.upper()
        if key == "UNINCORPORATED":
            continue  # already exists as "Miami-Dade County (Unincorporated)"
        if key in juris_by_name:
            continue
        title = muni.title()
        ins = mgmt_sql(f"""
          INSERT INTO jurisdictions (name, county, state, county_name)
          SELECT {sql_str(title)}, 'Miami-Dade', 'FL', 'Miami-Dade'
          WHERE NOT EXISTS (SELECT 1 FROM jurisdictions WHERE upper(name)={sql_str(key)}
            AND lower(coalesce(county_name,county)) IN ('miami-dade','miami_dade'))
          RETURNING id;
        """)
        if ins:
            juris_by_name[key] = ins[0]["id"]
            print(f"  Inserted jurisdiction {title} -> id={ins[0]['id']}")

    def jid_for(municname):
        key = municname.upper()
        if key == "UNINCORPORATED":
            return juris_by_name.get("MIAMI-DADE COUNTY (UNINCORPORATED)")
        return juris_by_name.get(key)

    # Step D: ensure zoning_districts (+ zone_standards) for every (muni, zone) pair.
    pairs = {}
    for z in zone_matches:
        pairs[(z["MUNICNAME"], z["ZONE"])] = z

    district_id = {}
    for (muni, zone), z in sorted(pairs.items()):
        jid = jid_for(muni)
        if jid is None:
            print(f"  SKIP district for {muni}/{zone}: no jurisdiction id")
            continue
        existing_d = mgmt_sql(f"SELECT id FROM zoning_districts WHERE jurisdiction_id={jid} AND code={sql_str(zone)};")
        if existing_d:
            district_id[(muni, zone)] = existing_d[0]["id"]
            continue
        far_regulated, max_far = parse_far(z.get("FAR"))
        density = parse_density(z.get("DENSITY"))
        name = z.get("ZONEDESC") or zone
        src_layer = z.get("_source_layer") or ZONING_LAYER
        is_unincorp_fallback = src_layer == UNINCORP_ZONING_LAYER
        desc = ("Sourced from Miami-Dade Unincorporated Zoning ArcGIS layer (MD_Zoning/MapServer/1)"
                if is_unincorp_fallback else
                'Sourced from Miami-Dade countywide MunicipalZone_gdb ArcGIS layer (GENRLLUTYPE=' + str(z.get('GENRLLUTYPE')) + ')')
        # Unincorporated fallback layer has no DENSITY/FAR fields -- never claim regulated.
        district_far_regulated = False if is_unincorp_fallback else far_regulated
        district_density_regulated = False if is_unincorp_fallback else True
        ins = mgmt_sql(f"""
          INSERT INTO zoning_districts (jurisdiction_id, code, name, description,
            far_regulated, density_regulated, pk1000_regulated)
          VALUES ({jid}, {sql_str(zone)}, {sql_str(name)}, {sql_str(desc)},
            {str(district_far_regulated).upper()}, {str(district_density_regulated).upper()}, FALSE)
          ON CONFLICT DO NOTHING RETURNING id;
        """)
        if ins:
            did = ins[0]["id"]
        else:
            existing_d = mgmt_sql(f"SELECT id FROM zoning_districts WHERE jurisdiction_id={jid} AND code={sql_str(zone)};")
            if not existing_d:
                print(f"  WARNING: district insert for {muni}/{zone} returned nothing, no row -- bug")
                continue
            did = existing_d[0]["id"]
        district_id[(muni, zone)] = did
        print(f"  zoning_districts {muni}/{zone} -> id={did} far_regulated={district_far_regulated} density={density}")
        if not is_unincorp_fallback:
            mgmt_sql(f"""
              INSERT INTO zone_standards (zoning_district_id, max_far, max_density_du_acre, source_url, confidence_score)
              SELECT {did}, {max_far if max_far is not None else 'NULL'},
                     {density if density is not None else 'NULL'},
                     {sql_str(src_layer)}, 0.7
              WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id={did});
            """)

    # Step E: insert parcel_zones (idempotent).
    inserted = 0
    skipped = 0
    for z in zone_matches:
        muni, zone = z["MUNICNAME"], z["ZONE"]
        jid = jid_for(muni)
        did_key = (muni, zone)
        if jid is None or did_key not in district_id:
            skipped += 1
            continue
        pid_raw = z["parcel_id"]
        existing_pz = mgmt_sql(f"SELECT id FROM parcel_zones WHERE jurisdiction_id={jid} AND parcel_id={sql_str(pid_raw)};")
        if existing_pz:
            skipped += 1
            continue
        src_layer = z.get("_source_layer") or ZONING_LAYER
        source_tag = ("miamidade_gis_unincorporated_zoning:MD_Zoning_MapServer1_pip_20260811"
                       if src_layer == UNINCORP_ZONING_LAYER else
                       "miamidade_gis_countywide_zoning:MunicipalZone_gdb_pip_20260811")
        result = mgmt_sql(f"""
          INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
          VALUES ({sql_str(pid_raw)}, {jid}, {sql_str(zone)}, {sql_str(z.get('ZONEDESC') or zone)},
                  {sql_str(source_tag)})
          RETURNING id;
        """)
        if result:
            inserted += 1
            print(f"  parcel_zones INSERT {z['case_number']} parcel_id={pid_raw} zone={zone} -> id={result[0]['id']}")
        else:
            print(f"  WARNING: parcel_zones insert for {z['case_number']} returned nothing -- bug")

    print(f"\nFINAL: parcel_zones inserted={inserted} skipped(existing/no-jid)={skipped} "
          f"of {len(zone_matches)} zone matches (of {len(CANDIDATES)} total candidates).")
    if inserted == 0 and len(zone_matches) > 0:
        print("ERROR: parsed >0 candidate zone matches but wrote 0 parcel_zones rows -- investigate.")


if __name__ == "__main__":
    main()
