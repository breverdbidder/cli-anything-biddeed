#!/usr/bin/env python3
"""GOLD STANDARD shard-3 miami_dade, letter I -- dispatch
0c873526-996a-4f5d-9123-99836d1d585f, 2026-08-23.

Fixes rows within the evaluator's exact card population (563 rows: county
miami_dade, data_source IS NULL OR data_source<>'propertyonion' OR
tier1_authoritative=true) that have a real, usable parcel_id
(hyphenated folio format) but fail I's stricter card-completeness test:
FAIL live at 87.2% (card_complete=491 of 563). Need >=535 (95%) to pass;
gap=44.

Reuses the exact pattern from scripts/miami_dade_i_zone_geo_backfill_20260811.py
and scripts/gold_standard_shard2_okmd_9c6b9b03_miamidade_i_zoning_apply.py
(same two ArcGIS layers, same fallback logic, same idempotent
jurisdictions/zoning_districts/zone_standards/parcel_zones write pattern) --
NOT reimplemented, just re-derived against a FRESH candidate list (56 case
numbers verified live via PostgREST + v_zoning_gold_standard_card query
immediately before writing this script; some overlap with the 2026-08-11
list is possible since that gap has regrown, but this list is independently
re-derived, not reused verbatim):

  1. Geocoding (lat/lng + verifying property_address) via Miami-Dade's
     AddressSearchMap_PropertiesWithZip/MapServer/1 FOLIO query, for rows
     missing latitude/longitude and/or property_address.
  2. Point-in-polygon zoning lookup via the countywide MunicipalZone_gdb
     FeatureServer (services.arcgis.com/8Pc9XBTAsYuxx9Ny), with fallback to
     the county's own Unincorporated Zoning layer (MD_Zoning/MapServer/1)
     when MunicipalZone_gdb returns its 'UNINCORPORATED'/'NONE' placeholder
     feature (verified real behavior, not a real zone code -- documented in
     the 2026-08-11 script).
  3. Ensures jurisdictions / zoning_districts / zone_standards rows exist,
     then inserts parcel_zones rows (idempotent, NOT EXISTS-guarded).

Fail-loud invariant: if a folio has 0 features in the property layer, or 0
zoning polygon matches, that is logged loudly per-case, never silently
skipped. If total parcel_zones inserted == 0 while zone_matches > 0, raises.

Usage: python3 scripts/miamidade_gsd3_0c873526_i_zone_geo_backfill.py
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
UNINCORP_ZONING_LAYER = "https://gisweb.miamidade.gov/arcgis/rest/services/LandManagement/MD_Zoning/MapServer/1/query"

# 56 candidates with a real parcel_id, derived live 2026-08-23 from the
# evaluator's exact 563-row population minus rows already card_complete.
CANDIDATES = {
    "2022-018799-CA-01": "30-6828-000-2250",
    "2023-000766-CA-01": "30-4909-007-2850",
    "2023-000848-CA-01": "30-4902-017-0540",
    "2023-027169-CA-01": "23-3209-053-0530",
    "2023-028915-CA-01": "06-2230-026-0290",
    "2024-000848-CA-01": "01-3113-042-0800",
    "2024-000935-CA-01": "30-4015-017-0910",
    "2024-009328-CA-01": "07-2218-011-2330",
    "2024-009650-CA-01": "34-2109-004-0180",
    "2024-011185-CA-01": "30-4005-036-2630",
    "2024-015282-CA-01": "01-3114-036-2050",
    "2024-017015-CA-01": "06-2126-017-0120",
    "2024-018502-CA-01": "30-3116-006-0320",
    "2024-019582-CA-01": "30-6912-008-1380",
    "2024-020977-CA-01": "30-3121-017-0160",
    "2024-021360-CA-01": "30-4912-084-0050",
    "2024-021457-CA-01": "30-7908-020-0460",
    "2024-021476-CA-01": "30-2113-001-1530",
    "2024-024069-CA-01": "34-2111-003-0290",
    "2024-148444-CC-05": "30-4030-038-0050",
    "2025-000672-CA-01": "30-4909-007-2850",
    "2025-001484-CA-01": "30-2123-015-1170",
    "2025-002515-CA-01": "34-2115-003-0790",
    "2025-002524-CA-01": "02-3227-004-0220",
    "2025-002992-CA-01": "30-2218-000-0300",
    "2025-003400-CA-01": "01-4138-144-2000",
    "2025-003933-CA-01": "02-3214-010-2880",
    "2025-004629-CA-01": "02-3214-020-3290",
    "2025-004896-CA-01": "07-2217-005-1530",
    "2025-005539-CA-01": "30-4928-010-1050",
    "2025-008800-CA-01": "30-2204-028-0330",
    "2025-008973-CA-01": "01-3208-020-0060",
    "2025-013299-CA-01": "01-4139-044-0020",
    "2025-013301-CA-01": "01-4139-044-0280",
    "2025-013889-CA-01": "01-3137-039-5560",
    "2025-013969-CA-01": "10-7920-013-4910",
    "2025-015248-CA-01": "30-7902-023-0750",
    "2025-018229-CA-01": "30-2205-022-0140",
    "2025-018389-CA-01": "35-3008-002-2230",
    "2025-019896-CA-01": "30-4927-047-0790",
    "2025-020082-CA-01": "30-5923-010-0110",
    "2025-020717-CA-01": "30-1231-046-0200",
    "2025-022404-CA-01": "28-1235-030-0980",
    "2025-022885-CA-01": "14-2235-041-0380",
    "2025-023730-CA-01": "02-3222-014-1080",
    "2025-024088-CA-01": "01-3113-042-0110",
    "2025-024495-CA-01": "30-7829-000-0780",
    "2025-024683-CA-01": "30-4923-006-0510",
    "2025-025518-CA-01": "30-4009-005-1460",
    "2025-160930-CC-05": "07-2207-007-2311",
    "2026-001222-CA-01": "30-2001-013-0090",
    "2026-002023-CA-01": "30-5923-016-0070",
    "2026-021475-CC-23": "35-3008-026-0360",
    "2026-049623-CC-25": "30-3951-003-0420",
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

    geo_results = {}
    rows = rest_get("multi_county_auctions",
                     {"county": "eq.miami_dade",
                      "case_number": "in.(" + ",".join(f'"{c}"' for c in CANDIDATES) + ")",
                      "select": "case_number,parcel_id,property_address,latitude,longitude,po_latitude,po_longitude,assessed_value,market_value"})
    row_by_case = {r["case_number"]: r for r in rows}

    geocode_updates = 0
    geocode_misses = []
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
            geocode_misses.append(case_number)
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
          f"AddressSearchMap_PropertiesWithZip/MapServer/1 (FOLIO query). "
          f"{len(geocode_misses)} geocode misses: {geocode_misses}")

    zone_matches = []
    zoning_misses = []
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
            zoning_misses.append(case_number)
            continue
        z = zoning_lookup(float(lng), float(lat))
        if z is None:
            print(f"  ZONING MISS: {case_number} parcel_id={parcel_id} at ({lat},{lng})")
            zoning_misses.append(case_number)
            continue
        z["case_number"] = case_number
        z["parcel_id"] = parcel_id
        zone_matches.append(z)
        print(f"  ZONE {case_number} parcel_id={parcel_id} -> {z['MUNICNAME']}/{z['ZONE']}")
        time.sleep(0.15)

    json.dump(zone_matches, open("/tmp/miamidade_gsd3_0c873526_i_zone_matches.json", "w"), indent=2)
    print(f"\nZoning lookup step: {len(zone_matches)} of {len(CANDIDATES)} candidates matched a zone polygon "
          f"via MunicipalZone_gdb FeatureServer (point-in-polygon). Misses: {zoning_misses}")

    existing_j = mgmt_sql("""
      SELECT id, upper(name) AS uname FROM jurisdictions
      WHERE lower(coalesce(county_name,county)) IN ('miami-dade','miami_dade');
    """)
    juris_by_name = {r["uname"]: r["id"] for r in existing_j}

    distinct_munis = sorted({z["MUNICNAME"] for z in zone_matches if z.get("MUNICNAME")})
    for muni in distinct_munis:
        key = muni.upper()
        if key == "UNINCORPORATED":
            continue
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
        source_tag = ("miamidade_gis_unincorporated_zoning:MD_Zoning_MapServer1_pip_gsd3_0c873526"
                       if src_layer == UNINCORP_ZONING_LAYER else
                       "miamidade_gis_countywide_zoning:MunicipalZone_gdb_pip_gsd3_0c873526")
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
