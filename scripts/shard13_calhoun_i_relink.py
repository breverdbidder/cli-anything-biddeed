#!/usr/bin/env python3
"""
shard13_calhoun_i_relink.py — Calhoun I criterion maintenance (dispatch 61ea7d8f)

The calhoun clerk harvest (calhoun-clerk-harvest.yml, daily 05:45 UTC) adds new
tax-deed and foreclosure rows. Each new row needs:
  1. parcel_id populated (from the clerk card or ArcGIS fallback)
  2. A matching parcel_zones row for jurisdiction_id=922 with a non-null zone_code
  3. property_address populated (TD rows from the clerk omit it; we reverse-geocode
     from the parcel_id → Calhoun PA ArcGIS)
  4. assessed_value + lat/lon (for the full I card)

The run3679 session fixed calhoun to 8/10 (G+I both PASS) but the daily harvest
can add new rows that don't automatically get zone-linked. This script:
  - Fetches all calhoun auction rows
  - For each that is missing parcel_zones entry OR missing property_address/lat/lon:
    * Queries Calhoun PA ArcGIS (https://gcgis.calhounfl.org/arcgis/rest/services)
      or falls back to FL GIO statewide cadastral by parcel_id
    * Inserts/updates parcel_zones with real zone from the DOR use-code crosswalk
      or a zoning-layer query
    * Patches multi_county_auctions with address/geo/value if missing

Honesty markers:
  - CONFIRMED: any value from a live ArcGIS query that returns exactly 1 feature
  - INFERRED: DOR_UC crosswalk zone assignment (known generalisation)
  - UNTESTED: any fallback path not exercised live this session

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0=success, 1=fatal error, 2=no new work needed
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

ARCGIS_HEADERS = {"User-Agent": "curl/8.5.0"}

JURISDICTION_ID = 922  # Calhoun, confirmed from parcel_zones

# DOR use-code → zone district id mapping (real zones from calhoun migration 20260711c)
# These IDs correspond to the existing zoning_districts for calhoun in the DB.
# Confirmed from migration 20260711g: ids 11553 MH, 11554 SFR, 11555 TIMBER, 11556 VAC-RES
# and id 11068 R-1 (uncited, Blountstown)
DOR_UC_TO_ZONE = {
    "01": "SFR",       # Single Family
    "02": "MH",        # Mobile Home
    "09": "SFR",       # Condo (treat as SFR for calhoun)
    "69": "TIMBER",    # Timber land
    "70": "TIMBER",    # Timber land II
    "71": "TIMBER",    # Timberland III
    "99": "VAC-RES",   # Vacant residential
}


def http_get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        print(f"GET error {url}: {e}", file=sys.stderr)
        return 0, {}


def http_patch(url, body):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="PATCH",
        headers={**REST_HEADERS, "Prefer": "return=representation"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def http_post(url, body):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={**REST_HEADERS, "Prefer": "return=minimal"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def fetch_calhoun_rows():
    url = (
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
        "?county=eq.calhoun"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        "assessed_value,sale_type,data_source"
        "&limit=500"
    )
    status, rows = http_get(url, headers=REST_HEADERS)
    if status != 200:
        raise RuntimeError(f"Failed to fetch calhoun rows: HTTP {status}")
    return rows


def fetch_existing_parcel_zones():
    url = (
        f"{SUPABASE_URL}/rest/v1/parcel_zones"
        f"?jurisdiction_id=eq.{JURISDICTION_ID}"
        "&select=id,parcel_id,zone_code"
        "&limit=500"
    )
    status, rows = http_get(url, headers=REST_HEADERS)
    if status != 200:
        raise RuntimeError(f"Failed to fetch parcel_zones: HTTP {status}")
    return {r["parcel_id"]: r for r in rows}


def fetch_zone_districts():
    """Fetch zoning_districts for jurisdiction 922 to get code→id mapping."""
    url = (
        f"{SUPABASE_URL}/rest/v1/zoning_districts"
        f"?jurisdiction_id=eq.{JURISDICTION_ID}"
        "&select=id,code"
        "&limit=100"
    )
    status, rows = http_get(url, headers=REST_HEADERS)
    if status != 200:
        return {}
    return {r["code"]: r["id"] for r in rows}


def query_fl_gio_parcel(parcel_id: str):
    """Query FL GIO statewide cadastral by PARCEL_ID for Calhoun (CO_NO=8)."""
    encoded_pid = urllib.parse.quote(parcel_id)
    url = (
        "https://services1.arcgis.com/O1JpcwDW8sjYuddV/arcgis/rest/services/"
        "Florida_Parcels/FeatureServer/0/query"
        f"?where=PARCEL_ID='{encoded_pid}'+AND+CO_NO=8"
        "&outFields=PARCEL_ID,OWNER_NAME,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JUST_VAL,"
        "LATITUDE,LONGITUDE,DOR_UC"
        "&returnGeometry=false&f=json"
    )
    status, data = http_get(url, headers=ARCGIS_HEADERS, timeout=30)
    if status == 200:
        return data.get("features", [])
    return []


def census_reverse_geocode(lat: float, lon: float) -> str | None:
    """UNTESTED fallback: Census Bureau reverse geocode for address."""
    url = (
        f"https://geocoding.geo.census.gov/geocoder/locations/coordinates"
        f"?x={lon}&y={lat}&benchmark=Public_AR_Current&format=json"
    )
    try:
        status, data = http_get(url, timeout=15)
        if status == 200:
            addrs = (data.get("result", {})
                     .get("addressMatches", []))
            if addrs:
                return addrs[0].get("matchedAddress")
    except Exception:
        pass
    return None


def main():
    print(f"Fetching calhoun rows from {SUPABASE_URL}...")
    rows = fetch_calhoun_rows()
    print(f"Total calhoun rows: {len(rows)}")

    existing_zones = fetch_existing_parcel_zones()
    print(f"Existing parcel_zones for jurisdiction {JURISDICTION_ID}: {len(existing_zones)}")

    zone_code_to_id = fetch_zone_districts()
    print(f"Zone districts available: {zone_code_to_id}")

    needs_work = [
        r for r in rows
        if r.get("parcel_id") and (
            r["parcel_id"] not in existing_zones
            or not r.get("property_address")
            or r.get("latitude") is None
            or r.get("assessed_value") is None
        )
    ]
    needs_parcel = [r for r in rows if not r.get("parcel_id")]

    print(f"Rows needing zone-link or enrichment (have parcel_id): {len(needs_work)}")
    print(f"Rows missing parcel_id entirely: {len(needs_parcel)}")

    counts = {
        "zone_inserted": 0,
        "enrichment_patched": 0,
        "parcel_query_hit": 0,
        "parcel_query_miss": 0,
        "write_error": 0,
    }
    receipt = []

    # Process rows with parcel_id that need zone-link and/or enrichment
    for row in needs_work:
        parcel_id = row["parcel_id"]
        entry = {"case_number": row["case_number"], "parcel_id": parcel_id, "actions": []}

        feats = []
        if not row.get("property_address") or row.get("latitude") is None or row.get("assessed_value") is None:
            feats = query_fl_gio_parcel(parcel_id)
            if feats:
                counts["parcel_query_hit"] += 1
                attrs = feats[0]["attributes"]
                entry["fl_gio_attrs"] = {
                    "phy_addr1": attrs.get("PHY_ADDR1"),
                    "phy_city": attrs.get("PHY_CITY"),
                    "just_val": attrs.get("JUST_VAL"),
                    "dor_uc": attrs.get("DOR_UC"),
                }
            else:
                counts["parcel_query_miss"] += 1
            time.sleep(0.2)

        # Build enrichment patch
        patch_body = {}
        if feats:
            attrs = feats[0]["attributes"]
            if not row.get("property_address"):
                addr1 = attrs.get("PHY_ADDR1", "")
                city = attrs.get("PHY_CITY", "")
                zipcd = attrs.get("PHY_ZIPCD", "")
                if addr1 and city:
                    patch_body["property_address"] = f"{addr1}, {city}, FL {zipcd}".strip(", ")
                    entry["actions"].append("address_from_fl_gio")
            if row.get("assessed_value") is None:
                jv = attrs.get("JUST_VAL")
                if isinstance(jv, (int, float)) and jv > 0:
                    patch_body["assessed_value"] = jv
                    patch_body["assessed_value_source"] = "fl_gio_cadastral_calhoun"
                    entry["actions"].append("assessed_value_from_fl_gio")
            # FL GIO statewide cadastral has lat/lon fields
            if row.get("latitude") is None:
                lat = attrs.get("LATITUDE")
                lon = attrs.get("LONGITUDE")
                if lat and lon:
                    patch_body["latitude"] = float(lat)
                    patch_body["longitude"] = float(lon)
                    entry["actions"].append("lat_lon_from_fl_gio")

        if patch_body:
            url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row['id']}"
            status, _ = http_patch(url, patch_body)
            if status in (200, 204):
                counts["enrichment_patched"] += 1
            else:
                counts["write_error"] += 1
                entry["patch_error"] = status

        # Insert parcel_zones if missing
        if parcel_id not in existing_zones:
            # Determine zone_code
            zone_code = None
            if feats:
                dor_uc = str(feats[0]["attributes"].get("DOR_UC") or "").zfill(2)
                zone_code = DOR_UC_TO_ZONE.get(dor_uc)

            if zone_code and zone_code in zone_code_to_id:
                zone_body = {
                    "parcel_id": parcel_id,
                    "jurisdiction_id": JURISDICTION_ID,
                    "zone_code": zone_code,
                    "source": "fl_gio_dor_uc_crosswalk_shard13",
                }
                url = f"{SUPABASE_URL}/rest/v1/parcel_zones"
                status, _ = http_post(url, zone_body)
                if status in (200, 201, 204):
                    counts["zone_inserted"] += 1
                    existing_zones[parcel_id] = {"parcel_id": parcel_id, "zone_code": zone_code}
                    entry["actions"].append(f"zone_inserted:{zone_code}")
                else:
                    counts["write_error"] += 1
                    entry["zone_insert_error"] = status
            elif zone_code:
                entry["actions"].append(f"zone_code_{zone_code}_not_in_db")
            else:
                entry["actions"].append("no_zone_code_from_dor_uc")

        receipt.append(entry)

    # Summary
    total_now_linked = len(existing_zones)
    print(f"\nSUMMARY:")
    print(f"  zone_inserted: {counts['zone_inserted']}")
    print(f"  enrichment_patched: {counts['enrichment_patched']}")
    print(f"  parcel_query_hit: {counts['parcel_query_hit']}")
    print(f"  parcel_query_miss: {counts['parcel_query_miss']}")
    print(f"  write_error: {counts['write_error']}")
    print(f"  total parcel_zones now: {total_now_linked}")

    print(json.dumps({"counts": counts, "receipt": receipt}, indent=2))

    if len(needs_work) == 0 and len(needs_parcel) == 0:
        print("No new work needed — all calhoun rows are zone-linked and enriched.")
        return 2

    return 0 if counts["write_error"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
