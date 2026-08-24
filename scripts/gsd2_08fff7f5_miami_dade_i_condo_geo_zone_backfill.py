#!/usr/bin/env python3
"""GOLD STANDARD miami_dade, letter I -- dispatch 08fff7f5.

Targets the 15 remaining card_complete-gap rows that carry a REAL Miami-Dade
folio-format parcel_id (NN-NNNN-NNN-NNNN) for condo/multi-unit properties
whose unit-level folio is NOT present in the county's cadastral parcel
polygon layer (MD_LandInformation/MapServer/26 "Parcels @ PaParcel") --
only the condo BUILDING's master/base folio (9-digit prefix + trailing
"0001") is. This is standard Miami-Dade cadastral practice: individual
condo units don't have separate ground footprints, so the county tracks
one polygon per building.

Mechanism (verified live 2026-08-24):
  1. Try exact 13-digit FOLIO match against PaParcel layer.
  2. Fall back to a 9-digit prefix LIKE match (condo master parcel) --
     verified this resolves all 15 target rows to a real, distinct,
     geographically-plausible building footprint centroid.
  3. Compute centroid from the returned polygon rings (vertex average,
     same method as prior scripts in this repo).
  4. Patch multi_county_auctions.latitude/longitude for rows missing geo.
  5. Point-in-polygon zoning lookup via the countywide MunicipalZone_gdb
     FeatureServer at the resolved centroid (same layer prior scripts use),
     with fallback to the county's own Unincorporated Zoning layer when
     MunicipalZone_gdb returns the MUNICNAME='UNINCORPORATED'/ZONE='NONE'
     placeholder.
  6. Ensure jurisdictions / zoning_districts / zone_standards rows exist,
     then insert parcel_zones rows keyed by the ORIGINAL unit-level
     parcel_id (not the master folio) so v_zoning_gold_standard_card joins
     correctly against multi_county_auctions.parcel_id.

NEVER-LIE: building-level centroid is the correct/standard granularity for
condo geocoding (no ground-truth unit-level footprint exists). Zone code is
real, sourced from county GIS at that exact point -- not guessed.

Usage: python3 scripts/gsd2_08fff7f5_miami_dade_i_condo_geo_zone_backfill.py
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

PARCEL_LAYER = "https://gisweb.miamidade.gov/arcgis/rest/services/MD_LandInformation/MapServer/26/query"
ZONING_LAYER = "https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/MunicipalZone_gdb/FeatureServer/0/query"
UNINCORP_ZONING_LAYER = "https://gisweb.miamidade.gov/arcgis/rest/services/LandManagement/MD_Zoning/MapServer/1/query"

# 15 rows: real folio-format parcel_id, missing latitude/longitude (verified
# live 2026-08-24 against pencil_dod_evaluate_county letter-I gap query).
CANDIDATES = [
    "2023-027169-CA-01",
    "2024-021360-CA-01",
    "2024-148444-CC-05",
    "2025-003400-CA-01",
    "2025-003933-CA-01",
    "2025-004629-CA-01",
    "2025-013299-CA-01",
    "2025-013301-CA-01",
    "2025-013889-CA-01",
    "2025-018229-CA-01",
    "2025-019896-CA-01",
    "2025-020717-CA-01",
    "2025-022404-CA-01",
    "2025-022885-CA-01",
    "2026-021475-CC-23",
]


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
    """Try exact 13-digit FOLIO, then fall back to 9-digit prefix (condo
    master/building parcel) against the county's PaParcel cadastral layer."""
    for trunc_len in (13, 9):
        key = folio[:trunc_len]
        where = f"FOLIO='{key}'" if trunc_len == 13 else f"FOLIO LIKE '{key}%'"
        params = {"where": where, "outFields": "FOLIO,TRUE_SITE_ADDR",
                  "returnGeometry": "true", "outSR": "4326", "f": "json"}
        r = httpx.get(PARCEL_LAYER, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        feats = data.get("features", [])
        if not feats:
            continue
        f = feats[0]
        geom = f.get("geometry")
        if not geom or "rings" not in geom:
            continue
        x, y = polygon_centroid(geom["rings"])
        return {"lat": y, "lng": x, "matched_folio": f["attributes"]["FOLIO"], "trunc_len": trunc_len}
    return None


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
        return zoning_lookup_unincorporated(lng, lat)
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

    rows = rest_get("multi_county_auctions",
                     {"county": "eq.miami_dade",
                      "case_number": "in.(" + ",".join(f'"{c}"' for c in CANDIDATES) + ")",
                      "select": "case_number,parcel_id,property_address,latitude,longitude,po_latitude,po_longitude,assessed_value,market_value"})
    row_by_case = {r["case_number"]: r for r in rows}

    geo_results = {}
    geocode_updates = 0
    for case_number in CANDIDATES:
        row = row_by_case.get(case_number)
        if row is None:
            print(f"  WARNING: {case_number} not found in live table anymore, skip")
            continue
        parcel_id = row.get("parcel_id")
        if not parcel_id:
            print(f"  WARNING: {case_number} has no parcel_id now, skip")
            continue
        needs_geo = row.get("latitude") is None and row.get("po_latitude") is None
        if not needs_geo:
            print(f"  {case_number}: already has geo, skip geocode")
            continue
        folio = to_folio(parcel_id)
        g = geocode_folio(folio)
        if g is None:
            print(f"  GEOCODE MISS: {case_number} parcel_id={parcel_id} folio={folio} -- no PaParcel match")
            continue
        geo_results[case_number] = g
        patch = {"latitude": g["lat"], "longitude": g["lng"]}
        rest_patch("multi_county_auctions",
                    {"county": "eq.miami_dade", "case_number": f"eq.{case_number}"},
                    patch)
        geocode_updates += 1
        print(f"  GEOCODED {case_number} parcel_id={parcel_id} folio={folio} -> "
              f"matched_folio={g['matched_folio']} (trunc_len={g['trunc_len']}) lat={g['lat']:.6f} lng={g['lng']:.6f}")
        time.sleep(0.2)

    print(f"\nGeocode step: {geocode_updates} rows patched via PaParcel FOLIO/prefix lookup.")

    # Step B: point-in-polygon zoning lookup for all candidates using best-known lat/lng.
    zone_matches = []
    for case_number in CANDIDATES:
        row = row_by_case.get(case_number, {})
        parcel_id = row.get("parcel_id")
        if not parcel_id:
            continue
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
        time.sleep(0.2)

    json.dump(zone_matches, open("/tmp/gsd2_08fff7f5_miamidade_i_zone_matches.json", "w"), indent=2)
    print(f"\nZoning lookup step: {len(zone_matches)} of {len(CANDIDATES)} candidates matched a zone polygon.")

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

    # Step E: insert parcel_zones (idempotent), keyed by the ORIGINAL unit-level parcel_id.
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
        source_tag = ("miamidade_gis_unincorporated_zoning:MD_Zoning_MapServer1_pip_gsd2_08fff7f5"
                       if src_layer == UNINCORP_ZONING_LAYER else
                       "miamidade_gis_countywide_zoning:MunicipalZone_gdb_pip_gsd2_08fff7f5")
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


if __name__ == "__main__":
    main()
