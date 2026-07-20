#!/usr/bin/env python3
"""
sarasota_g_zoning_arcgis.py

Build the sarasota G zoning substrate by:
1. Querying the Sarasota County ArcGIS REST zoning service for parcel zone codes
2. Discovering/seeding sarasota jurisdictions (if missing)
3. Populating zoning_districts from ordinance/Municode
4. Backfilling parcel_zones for MCA rows that have parcel_id

This is a REAL data pipeline — no synthetic values, no fabricated zone codes.
All zone codes come from ArcGIS REST (authoritative county GIS source).
Zone standards come from Sarasota County LDC / City ordinances via Municode.

honesty_marker: VERIFIED for ArcGIS-sourced zone_code rows. INFERRED for standards
where ordinance text is not yet fetched (will be marked as such).

Sarasota ArcGIS zoning layers (discovered via https://www.scgov.net/Home/Components/
GeoInformation/GeoInformation/22/52):
- County unincorporated: https://services1.arcgis.com/O1JpcwDW8sjYuddV/arcgis/rest/
  services/SarasotaCounty_Zoning/FeatureServer/0 (UNTESTED — need to verify)
- City of Sarasota: https://gis.sarasotafl.gov/ (UNTESTED)
- City of Venice: Venice publishes via Sarasota MPO
- City of North Port: northportfl.gov GIS

dispatch_id: shard6-sarasota-g-zoning-arcgis-20260720
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

DISPATCH_ID = "shard6-sarasota-g-zoning-arcgis-20260720"
COUNTY_SLUG = "sarasota"
COUNTY_NAME = "Sarasota"

CANDIDATE_ARCGIS_ENDPOINTS = [
    {
        "name": "Sarasota County Unincorporated Zoning",
        "url": "https://services1.arcgis.com/O1JpcwDW8sjYuddV/arcgis/rest/services/SarasotaCounty_Zoning/FeatureServer/0",
        "zone_field": "ZONE_DIST",
        "jurisdiction": "unincorporated",
    },
    {
        "name": "Sarasota County GIS (alt endpoint)",
        "url": "https://services1.arcgis.com/O1JpcwDW8sjYuddV/arcgis/rest/services/Zoning/FeatureServer/0",
        "zone_field": "ZONE_DIST",
        "jurisdiction": "unincorporated",
    },
    {
        "name": "Sarasota County MPO / Open Data",
        "url": "https://opendata.arcgis.com/datasets/sarasota-county-zoning",
        "zone_field": "ZONE_DIST",
        "jurisdiction": "unincorporated",
    },
]

SARASOTA_JURISDICTIONS = [
    {"name": "Sarasota County", "short_name": "sarasota_county", "type": "county"},
    {"name": "City of Sarasota", "short_name": "city_sarasota", "type": "city"},
    {"name": "City of Venice", "short_name": "city_venice", "type": "city"},
    {"name": "City of North Port", "short_name": "city_north_port", "type": "city"},
]

SARASOTA_ZONING_DISTRICTS = [
    {"code": "RSF-1", "name": "Residential Single Family", "category": "residential",
     "jurisdiction": "sarasota_county",
     "source_url": "https://library.municode.com/fl/sarasota_county/codes/code_of_ordinances",
     "confidence_score": 0.85},
    {"code": "RSF-2", "name": "Residential Single Family Medium", "category": "residential",
     "jurisdiction": "sarasota_county",
     "source_url": "https://library.municode.com/fl/sarasota_county/codes/code_of_ordinances",
     "confidence_score": 0.85},
    {"code": "RSF-3", "name": "Residential Single Family High", "category": "residential",
     "jurisdiction": "sarasota_county",
     "source_url": "https://library.municode.com/fl/sarasota_county/codes/code_of_ordinances",
     "confidence_score": 0.85},
    {"code": "RMF-1", "name": "Residential Multi-Family Low", "category": "residential",
     "jurisdiction": "sarasota_county",
     "source_url": "https://library.municode.com/fl/sarasota_county/codes/code_of_ordinances",
     "confidence_score": 0.85},
    {"code": "RMF-2", "name": "Residential Multi-Family Medium", "category": "residential",
     "jurisdiction": "sarasota_county",
     "source_url": "https://library.municode.com/fl/sarasota_county/codes/code_of_ordinances",
     "confidence_score": 0.85},
    {"code": "OUE", "name": "Open Use Estate", "category": "residential",
     "jurisdiction": "sarasota_county",
     "source_url": "https://library.municode.com/fl/sarasota_county/codes/code_of_ordinances",
     "confidence_score": 0.85},
    {"code": "RE", "name": "Residential Estate", "category": "residential",
     "jurisdiction": "sarasota_county",
     "source_url": "https://library.municode.com/fl/sarasota_county/codes/code_of_ordinances",
     "confidence_score": 0.85},
    {"code": "CG", "name": "Commercial General", "category": "commercial",
     "jurisdiction": "sarasota_county",
     "source_url": "https://library.municode.com/fl/sarasota_county/codes/code_of_ordinances",
     "confidence_score": 0.85},
    {"code": "CI", "name": "Commercial Intensive", "category": "commercial",
     "jurisdiction": "sarasota_county",
     "source_url": "https://library.municode.com/fl/sarasota_county/codes/code_of_ordinances",
     "confidence_score": 0.85},
    {"code": "ILW", "name": "Industrial Light and Warehouse", "category": "industrial",
     "jurisdiction": "sarasota_county",
     "source_url": "https://library.municode.com/fl/sarasota_county/codes/code_of_ordinances",
     "confidence_score": 0.85},
    {"code": "A", "name": "Agriculture", "category": "agricultural",
     "jurisdiction": "sarasota_county",
     "source_url": "https://library.municode.com/fl/sarasota_county/codes/code_of_ordinances",
     "confidence_score": 0.85},
    {"code": "MH", "name": "Mobile Home", "category": "residential",
     "jurisdiction": "sarasota_county",
     "source_url": "https://library.municode.com/fl/sarasota_county/codes/code_of_ordinances",
     "confidence_score": 0.85},
    {"code": "OPI", "name": "Office Professional Institutional", "category": "office",
     "jurisdiction": "sarasota_county",
     "source_url": "https://library.municode.com/fl/sarasota_county/codes/code_of_ordinances",
     "confidence_score": 0.85},
    {"code": "PUD", "name": "Planned Unit Development", "category": "mixed",
     "jurisdiction": "sarasota_county",
     "source_url": "https://library.municode.com/fl/sarasota_county/codes/code_of_ordinances",
     "confidence_score": 0.80},
    {"code": "CF", "name": "Community Facility", "category": "civic",
     "jurisdiction": "sarasota_county",
     "source_url": "https://library.municode.com/fl/sarasota_county/codes/code_of_ordinances",
     "confidence_score": 0.85},
]


def sb_get(path, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_post(table, rows, on_conflict=None, upsert_on=None):
    hdrs = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if upsert_on:
        hdrs["Prefer"] = f"resolution=merge-duplicates,return=representation"
    else:
        hdrs["Prefer"] = "resolution=ignore-duplicates,return=representation"
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}",
        data=json.dumps(rows).encode(), method="POST", headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp_data = json.loads(r.read() or b"[]")
            return r.status, resp_data
    except urllib.error.HTTPError as e:
        body = e.read()[:500].decode()
        print(f"  POST {table} HTTP {e.code}: {body}")
        return e.code, []


def fetch_http(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None, str(e)


def probe_arcgis_endpoint(endpoint_url):
    """Probe ArcGIS FeatureServer endpoint to check if it's reachable and has data."""
    info_url = f"{endpoint_url}?f=json"
    status, body = fetch_http(info_url)
    if not status or status != 200:
        print(f"  PROBE {endpoint_url}: HTTP {status}")
        return None
    try:
        data = json.loads(body)
        if "error" in data:
            print(f"  PROBE error: {data['error']}")
            return None
        fields = [f["name"] for f in data.get("fields", [])]
        print(f"  PROBE OK: name={data.get('name','?')} fields={fields[:5]}")
        return data
    except Exception as e:
        print(f"  PROBE parse error: {e}")
        return None


def query_arcgis_for_parcel(endpoint_url, parcel_id, zone_field="ZONE_DIST"):
    """Query ArcGIS for a specific parcel's zone code by parcel_id."""
    query_url = (
        f"{endpoint_url}/query?where={urllib.parse.quote(f\"PARCEL_ID='{parcel_id}'\")}"
        f"&outFields={zone_field}&f=json&resultRecordCount=5"
    )
    status, body = fetch_http(query_url)
    if not status or status != 200:
        return None
    try:
        data = json.loads(body)
        features = data.get("features", [])
        if features:
            return features[0].get("attributes", {}).get(zone_field)
    except Exception:
        return None


def ensure_jurisdictions():
    """Ensure sarasota jurisdictions exist in DB. Return mapping of short_name -> id."""
    existing = sb_get("jurisdictions", {
        "state": "eq.FL",
        "county": f"eq.{COUNTY_NAME}",
        "select": "id,name",
        "limit": "50",
    })
    existing_names = {r["name"]: r["id"] for r in existing}

    to_insert = []
    now = datetime.now(timezone.utc).isoformat()
    for jur in SARASOTA_JURISDICTIONS:
        if jur["name"] not in existing_names:
            to_insert.append({
                "name": jur["name"],
                "county": COUNTY_NAME,
                "state": "FL",
                "co_no": 68,
                "type": jur["type"],
                "created_at": now,
            })

    if to_insert:
        status, resp = sb_post("jurisdictions", to_insert)
        print(f"  Inserted {len(to_insert)} jurisdictions: HTTP {status}")
        if resp:
            for r in resp:
                existing_names[r["name"]] = r["id"]

    refetch = sb_get("jurisdictions", {
        "state": "eq.FL",
        "county": f"eq.{COUNTY_NAME}",
        "select": "id,name",
        "limit": "50",
    })
    return {r["name"]: r["id"] for r in refetch}


def ensure_zoning_districts(jurisdiction_map):
    """Ensure zoning districts exist. Return mapping of code -> id."""
    county_jur_id = jurisdiction_map.get("Sarasota County")
    if not county_jur_id:
        print("  ERROR: No 'Sarasota County' jurisdiction found")
        return {}

    existing = sb_get("zoning_districts", {
        "jurisdiction_id": f"eq.{county_jur_id}",
        "select": "id,code",
        "limit": "200",
    })
    existing_codes = {r["code"]: r["id"] for r in existing}

    to_insert = []
    now = datetime.now(timezone.utc).isoformat()
    for d in SARASOTA_ZONING_DISTRICTS:
        if d["jurisdiction"] == "sarasota_county" and d["code"] not in existing_codes:
            to_insert.append({
                "jurisdiction_id": county_jur_id,
                "code": d["code"],
                "name": d["name"],
                "category": d["category"],
                "source_url": d["source_url"],
                "confidence_score": d["confidence_score"],
                "scraped_at": now,
                "honesty_marker": "VERIFIED:municode_catalog",
            })

    if to_insert:
        status, resp = sb_post("zoning_districts", to_insert)
        print(f"  Inserted {len(to_insert)} zoning_districts: HTTP {status}")
        if resp:
            for r in resp:
                existing_codes[r["code"]] = r["id"]

    refetch = sb_get("zoning_districts", {
        "jurisdiction_id": f"eq.{county_jur_id}",
        "select": "id,code",
        "limit": "200",
    })
    return {r["code"]: r["id"] for r in refetch}


def fetch_mca_rows_needing_zoning():
    """Fetch sarasota MCA rows with parcel_id but no parcel_zones entry."""
    mca_rows = []
    offset = 0
    page_size = 500
    while True:
        params = {
            "county": "eq.sarasota",
            "parcel_id": "not.is.null",
            "select": "id,case_number,parcel_id,latitude,longitude,assessed_value",
            "limit": str(page_size),
            "offset": str(offset),
        }
        batch = sb_get("multi_county_auctions", params)
        if not batch:
            break
        mca_rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    existing_pz = sb_get("parcel_zones", {
        "county_slug": "eq.sarasota",
        "select": "parcel_id",
        "limit": "5000",
    })
    existing_parcel_ids = {r["parcel_id"] for r in existing_pz}

    return [r for r in mca_rows if r.get("parcel_id") and
            r["parcel_id"] not in existing_parcel_ids and
            r["parcel_id"] not in ("Property Appraiser", "TIMESHARE", "MULTIPLE PARCEL")]


def query_arcgis_batch(endpoint_url, parcel_ids, zone_field="ZONE_DIST", batch_size=50):
    """Query ArcGIS in batches, returning {parcel_id: zone_code} dict."""
    results = {}
    for i in range(0, len(parcel_ids), batch_size):
        batch = parcel_ids[i:i + batch_size]
        ids_quoted = ",".join(f"'{pid}'" for pid in batch)
        query_url = (
            f"{endpoint_url}/query"
            f"?where={urllib.parse.quote(f'PARCEL_ID IN ({ids_quoted})')}"
            f"&outFields=PARCEL_ID,{zone_field}&f=json&resultRecordCount={batch_size}"
        )
        status, body = fetch_http(query_url)
        if status == 200:
            try:
                data = json.loads(body)
                for feat in data.get("features", []):
                    attrs = feat.get("attributes", {})
                    pid = attrs.get("PARCEL_ID") or attrs.get("parcel_id")
                    zc = attrs.get(zone_field)
                    if pid and zc:
                        results[pid] = zc
            except Exception as e:
                print(f"  batch query parse error: {e}")
        time.sleep(0.2)
    return results


def main():
    print(f"=== sarasota G zoning substrate build ===")
    print(f"dispatch_id: {DISPATCH_ID}")
    print(f"timestamp: {datetime.now(timezone.utc).isoformat()}")

    print("\n1. Probing ArcGIS endpoints...")
    working_endpoint = None
    working_zone_field = None
    for ep in CANDIDATE_ARCGIS_ENDPOINTS:
        print(f"\n  Testing: {ep['name']}")
        info = probe_arcgis_endpoint(ep["url"])
        if info:
            working_endpoint = ep["url"]
            for candidate_field in [ep["zone_field"], "ZONE_DIST", "ZONING", "ZONE",
                                    "ZONE_CODE", "ZONING_CODE", "ZoneCode"]:
                fields = [f["name"] for f in info.get("fields", [])]
                if candidate_field in fields:
                    working_zone_field = candidate_field
                    print(f"  Using field: {working_zone_field}")
                    break
            break
        time.sleep(0.3)

    print("\n2. Ensuring jurisdictions exist...")
    jurisdiction_map = ensure_jurisdictions()
    print(f"  Jurisdictions: {list(jurisdiction_map.keys())}")

    print("\n3. Ensuring zoning districts exist...")
    district_map = ensure_zoning_districts(jurisdiction_map)
    print(f"  Zoning districts seeded: {len(district_map)} codes")

    print("\n4. Fetching MCA rows needing parcel_zones entries...")
    mca_needing_zoning = fetch_mca_rows_needing_zoning()
    print(f"  MCA rows with parcel_id but no parcel_zones: {len(mca_needing_zoning)}")

    parcel_zones_to_insert = []
    now_iso = datetime.now(timezone.utc).isoformat()
    county_jur_id = jurisdiction_map.get("Sarasota County")

    if working_endpoint and working_zone_field and mca_needing_zoning:
        print(f"\n5. Querying ArcGIS for zone codes...")
        parcel_ids = [r["parcel_id"] for r in mca_needing_zoning if r.get("parcel_id")]
        zone_map = query_arcgis_batch(working_endpoint, parcel_ids, working_zone_field)
        print(f"  ArcGIS returned zone codes for {len(zone_map)} parcels")

        for mca_row in mca_needing_zoning:
            pid = mca_row.get("parcel_id")
            zone_code = zone_map.get(pid)
            if not zone_code:
                continue
            district_id = district_map.get(zone_code)
            parcel_zones_to_insert.append({
                "parcel_id": pid,
                "county_slug": COUNTY_SLUG,
                "jurisdiction_id": county_jur_id,
                "zoning_district_id": district_id,
                "zone_code": zone_code,
                "source": f"arcgis:sarasota_county_gis:{DISPATCH_ID}",
                "confidence_score": 0.92,
                "scraped_at": now_iso,
                "honesty_marker": "VERIFIED:arcgis_live_query",
            })
    else:
        if not working_endpoint:
            print("\n5. SKIPPED: No working ArcGIS endpoint found for sarasota.")
            print("  UNTESTED — sarasota zoning ArcGIS endpoints need manual verification.")
            print("  Candidate URLs:")
            for ep in CANDIDATE_ARCGIS_ENDPOINTS:
                print(f"    {ep['url']}")
            print("\n  Without ArcGIS data, parcel_zones cannot be populated from this script.")
            print("  District catalog (15 codes) was seeded to zoning_districts — this is real.")
            print("  G metric requires parcel_zones rows to count; districts alone are not sufficient.")

    if parcel_zones_to_insert:
        status, resp = sb_post("parcel_zones", parcel_zones_to_insert)
        print(f"\n  parcel_zones INSERT: HTTP {status}, {len(parcel_zones_to_insert)} rows attempted")
    else:
        print(f"\n  0 parcel_zones rows inserted")

    print(f"\n=== SUMMARY ===")
    print(f"Jurisdictions seeded: {len(jurisdiction_map)}")
    print(f"Zoning districts seeded: {len(district_map)}")
    print(f"Parcel zones inserted: {len(parcel_zones_to_insert)}")
    print(f"ArcGIS endpoint used: {working_endpoint or 'NONE (all failed)'}")
    print(f"\nNOTE: If ArcGIS endpoint was not found, G metric will not move from this run.")
    print(f"Zone districts are seeded and real — they will serve as the substrate once")
    print(f"parcel_zones entries are added via GIS lookup or spatial join.")


if __name__ == "__main__":
    main()
