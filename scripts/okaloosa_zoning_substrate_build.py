#!/usr/bin/env python3
"""
Okaloosa Zoning Substrate Build (2026-07-19, GTM-22J shard3 continuation, I fix)
=================================================================================
Fixes the "I" (property card complete) criterion in pencil_dod_evaluate_county
for county='okaloosa' (was card_complete=0 of 40) by inserting real
parcel_zones rows for the 36 okaloosa auction rows in multi_county_auctions
that already carry a real parcel_id + latitude/longitude (from a prior
session's GIS enrichment, see scripts/okaloosa_parcel_gis_enrich.py).

The gap: parcel_zones had exactly 7 rows for okaloosa, all SYNTHETIC bootstrap
placeholders (parcel_id like 'OKA-TD-0001', 'SYN-OKA-FC-001') that match none
of the real APN-format parcel_ids on the real auction rows. This script
replaces that gap with real, GIS-sourced zone_code rows keyed by the real
parcel_id, via a point-in-polygon query of each parcel's lat/long against the
correct zoning authority for its location.

JURISDICTION RESOLUTION (per parcel):
  1. Query Okaloosa County's own incorporated-city-limits layer:
       https://okgis.myokaloosa.com/arcgis/rest/services/Admin-Boundaries/
       Admin_Boundaries/MapServer/99  (field ICLPY_CITY_CODE)
     Confirmed live this session: values seen for our 36 points were
     UNINCORPORATED, CRESTVIEW, FORT WALTON BEACH, NICEVILLE, DESTIN.
  2. If ICLPY_CITY_CODE == 'UNINCORPORATED' -> jurisdiction is the new
     "Unincorporated Okaloosa County" jurisdictions row (id inserted via
     supabase/migrations/20260719_shard3_okaloosa_i_unincorporated_jurisdiction.sql),
     zone_code source is the County Zoning layer:
       https://okgis.myokaloosa.com/arcgis/rest/services/Planning-Development/
       Zoning/MapServer/25  (field ZNGPY_ZONE)

     CORRECTION 2026-08-28: the service's layer IDs were renumbered upstream
     at some point after this script was written -- MapServer/28 is now
     "Coastal Construction Control Line" (no ZNGPY_ZONE field at all; every
     query against it returns HTTP 400 "Failed to execute query"), which
     silently blocked 2 genuinely-resolvable Unincorporated-area parcels this
     session. Re-enumerated the service's live layer list
     (MapServer?f=json) and confirmed layer 25 ("County Zoning") is the real
     current zoning layer, with the same ZNGPY_ZONE field this script always
     expected. Updated COUNTY_ZONING_URL to /25.
  3. If ICLPY_CITY_CODE is an incorporated city already present in
     `jurisdictions` (Crestview/Fort Walton Beach/Niceville/Destin -- the
     only 4 that appeared among our 36 points; Mary Esther/Shalimar/
     Valparaiso/Cinco Bayou/Laurel Hill had zero auction parcels this pass),
     zone_code is fetched from THAT city's own zoning GIS layer instead --
     confirmed live this session that Okaloosa's County Zoning layer
     (MapServer/28) returns ZERO features for points inside any incorporated
     city (each municipality is its own zoning authority), so the county
     layer is NOT a valid fallback for in-city parcels:
       Crestview          -> services9.arcgis.com/zvdDL6ILvlkPNTg8/arcgis/
                              rest/services/Zoning_and_FLU/FeatureServer/0
                              (field ZONE) -- discovered via the city's
                              public ArcGIS WebAppBuilder viewer
                              (arcgis.com item 4b4761b5e0ed466a9a63c75c906a8c78
                              -> webmap item ae4ca95f00d84d9cbc43a826ac401dc4)
       Fort Walton Beach   -> gis.fwb.org/arcgis/rest/services/Maps/Zoning/
                              MapServer/0 (field Zoning)
       Niceville           -> gis.nicevillefl.gov/server/rest/services/
                              Zoning/MapServer/0 (field Zoning_2015)
       Destin              -> okgis.myokaloosa.com/arcgis/rest/services/
                              LocalGovernment/Destin_EnerGov/MapServer/6
                              (field Zone_ABBR) -- lives on the SAME county
                              ArcGIS host under a LocalGovernment folder,
                              distinct from the County Zoning layer
     Any other incorporated-city code seen in the future (Mary Esther,
     Shalimar, Valparaiso, Cinco Bayou, Laurel Hill) has NO discovered
     zoning GIS layer as of this session -- those parcels are left OUT
     (BLANK > WRONG), not guessed against the county layer.

FAIL LOUD (same invariant as okaloosa_parcel_gis_enrich.py): if the script
finds >0 resolvable parcels but inserts 0 rows, it raises -- a real write
failure, not silent no-op. If a parcel's centroid returns 0 or >1 zoning
features from its correct authority, or its city code has no known zoning
source, it is left OUT of the insert and reported, never guessed.

Write pattern: POST (insert) to /rest/v1/parcel_zones -- parcel_zones has no
unique constraint on parcel_id alone (only on tax_account+jurisdiction_id,
both NULL for these rows), so this script first checks for any pre-existing
row with the same parcel_id and skips it (no duplicate insert) rather than
relying on upsert semantics.

Env (required): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success (>=1 row inserted), 1 = fatal error
"""
import json
import os
import sys

import httpx

CITY_LIMITS_URL = "https://okgis.myokaloosa.com/arcgis/rest/services/Admin-Boundaries/Admin_Boundaries/MapServer/99/query"
COUNTY_ZONING_URL = "https://okgis.myokaloosa.com/arcgis/rest/services/Planning-Development/Zoning/MapServer/25/query"

# Per-city zoning source registry. Only cities we've actually confirmed a
# live, working zoning layer for are listed -- anything else (a city code
# seen on a future run that isn't here) is left unresolved, not guessed.
CITY_ZONING_SOURCES = {
    "CRESTVIEW": {
        "jurisdiction_name": "Crestview",
        "url": "https://services9.arcgis.com/zvdDL6ILvlkPNTg8/arcgis/rest/services/Zoning_and_FLU/FeatureServer/0/query",
        "zone_field": "ZONE",
        "source_tag": "crestview_gis:zoning_and_flu_featureserver:0",
    },
    "FORT WALTON BEACH": {
        "jurisdiction_name": "Fort Walton Beach",
        "url": "https://gis.fwb.org/arcgis/rest/services/Maps/Zoning/MapServer/0/query",
        "zone_field": "Zoning",
        "source_tag": "fwb_gis:maps/zoning:0",
    },
    "NICEVILLE": {
        "jurisdiction_name": "Niceville",
        "url": "https://gis.nicevillefl.gov/server/rest/services/Zoning/MapServer/0/query",
        "zone_field": "Zoning_2015",
        "source_tag": "niceville_gis:zoning:0",
    },
    "DESTIN": {
        "jurisdiction_name": "Destin",
        "url": "https://okgis.myokaloosa.com/arcgis/rest/services/LocalGovernment/Destin_EnerGov/MapServer/6/query",
        "zone_field": "Zone_ABBR",
        "source_tag": "okaloosa_gis:localgovernment/destin_energov:6",
    },
}

UNINCORPORATED_JURISDICTION_NAME = "Unincorporated Okaloosa County"
COUNTY_ZONING_SOURCE_TAG = "okaloosa_gis:planning-development/zoning:28"


def _req(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env: {name}")
    return v


def _supa_headers() -> dict:
    key = _req("SUPABASE_SERVICE_ROLE_KEY")
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def fetch_rows() -> list[dict]:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    resp = httpx.get(
        f"{supa_url}/rest/v1/multi_county_auctions",
        params={
            "county": "eq.okaloosa",
            "parcel_id": "not.is.null",
            "latitude": "not.is.null",
            "longitude": "not.is.null",
            "select": "case_number,parcel_id,latitude,longitude",
        },
        headers=_supa_headers(), timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_jurisdictions() -> dict[str, int]:
    """Returns {jurisdiction_name: id} for all Okaloosa jurisdictions."""
    supa_url = _req("SUPABASE_URL").rstrip("/")
    resp = httpx.get(
        f"{supa_url}/rest/v1/jurisdictions",
        params={"county": "eq.Okaloosa", "select": "id,name"},
        headers=_supa_headers(), timeout=30,
    )
    resp.raise_for_status()
    return {row["name"]: row["id"] for row in resp.json()}


def fetch_existing_parcel_ids(parcel_ids: list[str]) -> set[str]:
    """Avoid duplicate inserts -- check which of our target parcel_ids
    already have a parcel_zones row (from any source)."""
    if not parcel_ids:
        return set()
    supa_url = _req("SUPABASE_URL").rstrip("/")
    quoted = ",".join(f'"{p}"' for p in parcel_ids)
    resp = httpx.get(
        f"{supa_url}/rest/v1/parcel_zones",
        params={"parcel_id": f"in.({quoted})", "select": "parcel_id"},
        headers=_supa_headers(), timeout=30,
    )
    resp.raise_for_status()
    return {row["parcel_id"] for row in resp.json()}


def _point_query(url: str, lon: float, lat: float, out_fields: str) -> list[dict]:
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": out_fields,
        "returnGeometry": "false",
        "f": "json",
    }
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"GIS query error at {url}: {data['error']}")
    return data.get("features", [])


def resolve_city_code(lat: float, lon: float) -> str | None:
    feats = _point_query(CITY_LIMITS_URL, lon, lat, "ICLPY_CITY_CODE")
    if len(feats) != 1:
        return None
    return feats[0]["attributes"]["ICLPY_CITY_CODE"]


def resolve_zone(city_code: str, lat: float, lon: float) -> tuple[str | None, str | None]:
    """Returns (zone_code, source_tag) or (None, reason) on failure."""
    if city_code == "UNINCORPORATED":
        feats = _point_query(COUNTY_ZONING_URL, lon, lat, "ZNGPY_ZONE")
        if len(feats) != 1:
            return None, f"county_zoning_layer_{len(feats)}_results"
        zone = feats[0]["attributes"].get("ZNGPY_ZONE")
        if not zone:
            return None, "county_zoning_layer_null_zone_field"
        return zone, COUNTY_ZONING_SOURCE_TAG

    cfg = CITY_ZONING_SOURCES.get(city_code)
    if not cfg:
        return None, f"no_known_zoning_source_for_city_code_{city_code!r}"
    feats = _point_query(cfg["url"], lon, lat, cfg["zone_field"])
    if len(feats) != 1:
        return None, f"{cfg['jurisdiction_name']}_zoning_layer_{len(feats)}_results"
    zone = feats[0]["attributes"].get(cfg["zone_field"])
    if not zone:
        return None, f"{cfg['jurisdiction_name']}_zoning_layer_null_zone_field"
    return zone, cfg["source_tag"]


def jurisdiction_id_for_city_code(city_code: str, jurisdictions: dict[str, int]) -> int | None:
    if city_code == "UNINCORPORATED":
        return jurisdictions.get(UNINCORPORATED_JURISDICTION_NAME)
    cfg = CITY_ZONING_SOURCES.get(city_code)
    if not cfg:
        return None
    return jurisdictions.get(cfg["jurisdiction_name"])


def insert_parcel_zones(rows: list[dict]) -> None:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    headers = {
        **_supa_headers(),
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    resp = httpx.post(
        f"{supa_url}/rest/v1/parcel_zones",
        headers=headers, json=rows, timeout=30,
    )
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"POST parcel_zones failed: {resp.status_code} {resp.text[:500]}")
    body = resp.json()
    if len(body) != len(rows):
        raise RuntimeError(
            f"FAIL LOUD: POSTed {len(rows)} parcel_zones rows but got "
            f"{len(body)} back -- partial/silent write failure"
        )


def main() -> int:
    auction_rows = fetch_rows()
    jurisdictions = fetch_jurisdictions()
    if UNINCORPORATED_JURISDICTION_NAME not in jurisdictions:
        raise RuntimeError(
            f"'{UNINCORPORATED_JURISDICTION_NAME}' jurisdiction row not found -- "
            "run supabase/migrations/20260719_shard3_okaloosa_i_unincorporated_jurisdiction.sql first"
        )

    existing = fetch_existing_parcel_ids([r["parcel_id"] for r in auction_rows])

    to_insert = []
    unresolved = []
    skipped_existing = []

    for r in auction_rows:
        parcel_id = r["parcel_id"]
        if parcel_id in existing:
            skipped_existing.append((r["case_number"], parcel_id))
            continue

        lat, lon = r["latitude"], r["longitude"]
        try:
            city_code = resolve_city_code(lat, lon)
        except Exception as exc:
            unresolved.append((r["case_number"], parcel_id, f"city_limits_query_error: {exc}"))
            continue
        if city_code is None:
            unresolved.append((r["case_number"], parcel_id, "city_limits_layer_ambiguous_or_zero_results"))
            continue

        jur_id = jurisdiction_id_for_city_code(city_code, jurisdictions)
        if jur_id is None:
            unresolved.append((r["case_number"], parcel_id, f"no_jurisdiction_row_for_city_code_{city_code!r}"))
            continue

        try:
            zone_code, source_or_reason = resolve_zone(city_code, lat, lon)
        except Exception as exc:
            unresolved.append((r["case_number"], parcel_id, f"zoning_query_error: {exc}"))
            continue
        if zone_code is None:
            unresolved.append((r["case_number"], parcel_id, source_or_reason))
            continue

        to_insert.append({
            "parcel_id": parcel_id,
            "jurisdiction_id": jur_id,
            "zone_code": zone_code,
            "source": source_or_reason,
        })
        print(f"    RESOLVED {r['case_number']} parcel_id={parcel_id} city={city_code} zone={zone_code} jurisdiction_id={jur_id}")

    print(f"\n>>> Auction rows with parcel_id+lat/long: {len(auction_rows)}")
    print(f">>> Already had a parcel_zones row (skipped, not re-inserted): {len(skipped_existing)}")
    print(f">>> Resolved (ready to insert): {len(to_insert)}")
    print(f">>> Unresolved (left OUT, not guessed): {len(unresolved)}")
    for cn, pid, reason in unresolved:
        print(f"    UNRESOLVED {cn} (parcel_id={pid}): {reason}")

    if not to_insert:
        if unresolved or skipped_existing:
            print("\n>>> Nothing new to insert (all rows already covered or unresolved). Exiting cleanly.")
            return 0
        raise RuntimeError("Zero resolvable parcels found across all rows -- GIS endpoints or logic likely broken")

    insert_parcel_zones(to_insert)
    print(f"\n>>> INSERTED {len(to_insert)} parcel_zones rows")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
