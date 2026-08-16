#!/usr/bin/env python3
"""Gold Standard flagler I -- geo + zoning backfill for the 8 v_auction_property_card
gap rows (94.97% / 151/159, need >=152/159 to flip to PASS), 2026-08-16.

Live-confirmed (this session, via v_auction_property_card + raw multi_county_auctions
query) that the task brief's row 58ef3cf4 was STALE: it actually has latitude=NULL /
longitude=NULL in the live DB too (not "has lat/lon" as briefed) -- so 5 rows need geo,
not 4. Documented as a correction, not silently reconciled.

Two independent sub-fixes, same lever set proven in
supabase/migrations/20260801_gold_standard_shard3_run7858_flagler_i_arcgis_zoning.sql
and scripts/shard_escambia_i_geocode_backfill_20260724.py:

1. GEO (5 Palm Coast rows, sections 07-11-31/20-10-31/35-11-31): free US Census
   Bureau geocoder (geocoding.geo.census.gov, Public_AR_Current benchmark). Fixes the
   scraper's missing-space-after-housenumber bug ("91VERANDA WAY" -> "91 VERANDA WAY")
   before geocoding -- confirmed necessary by a failed first-pass query.

2. ZONING (all 8 rows, once lat/lon is known): live ArcGIS point-in-polygon query
   against the same two FeatureServers proven in the 0801 migration --
   PalmCoastFL_Zoning (services1.arcgis.com/tpnsCwhQRDqwL3mq, field LAYER) for the 6
   Palm Coast parcels, Flagler Unincorporated_Zoning
   (services3.arcgis.com/hSKL9bYjhP4rHxSD) for the 2 Bunnell parcels. This is a live
   spatial lookup, not a same-section-neighbor inference -- parcel_zones has ZERO
   existing rows for any of these 8 exact parcel_ids (verified live query this
   session), so the same-section INFERRED pattern from
   20260724_gold_standard_shard7_flagler_i_subdivision_zone_match.sql does not apply
   here; every zone_code written by this script traces to its own parcel's real
   point-in-polygon hit.

Row 78713ea7-59d2-440a-858a-f66e0150bf34 (2025 CC 000553) is explicitly OUT OF SCOPE:
parcel_id IS NULL, property_address IS NULL, and its stored lat/lon
(29.6469,-81.2088) is the same known-fake constant placeholder already identified and
partially cleaned in the 0801 migration (comment #4) -- a scraper artifact, not a real
geocode. No parcel_id means no zoning join is possible and no real address means no
real re-geocode is possible either. Left untouched -- BLANK > WRONG.

DB writes via PostgREST only (direct pooler confirmed stale, per every prior shard
session). Idempotent: geocode only overwrites rows currently NULL on both lat/lon;
zoning INSERT uses NOT EXISTS guard on parcel_zones(parcel_id, jurisdiction_id) so
re-running does not create new dedup-defect duplicates (flagged, not fixed, per task
brief -- this script only ever inserts against parcel_ids with zero pre-existing rows).
"""
import json
import os
import re
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

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/address"
PALMCOAST_ZONING_URL = (
    "https://services1.arcgis.com/tpnsCwhQRDqwL3mq/arcgis/rest/services/"
    "PalmCoastFL_Zoning/FeatureServer/0/query"
)
UNINCORP_ZONING_URL = (
    "https://services3.arcgis.com/hSKL9bYjhP4rHxSD/arcgis/rest/services/"
    "Unincorporated_Zoning/FeatureServer/0/query"
)

PALMCOAST_JURISDICTION_ID = 966
UNINCORP_JURISDICTION_ID = 1184

GEO_TARGETS = [
    {"id": "a817ed79-5509-4108-b370-3d1c18408384", "case_number": "2025 CA 000505",
     "parcel_id": "07-11-31-0310-00020-0720", "addr": "91VERANDA WAY, PALM COAST, FL- 32137",
     "jurisdiction": "palmcoast"},
    {"id": "fa706ae9-acca-4495-b0f4-8b06b0b8e309", "case_number": "2025 CA 000656",
     "parcel_id": "35-11-31-4075-00000-0220", "addr": "44DEL PALMA DR, PALM COAST, FL- 32137",
     "jurisdiction": "palmcoast"},
    {"id": "7c6013d5-1130-4c29-a93b-8217c4a1cf33", "case_number": "2025 CA 000462",
     "parcel_id": "20-10-31-0300-00150-0000", "addr": "9SWEETBAY DR, PALM COAST, FL- 32137",
     "jurisdiction": "palmcoast"},
    {"id": "2e7aef04-be0d-43c7-93cf-3d74ffedd3f6", "case_number": "2024 CC 000454",
     "parcel_id": "20-10-31-3050-00080-0050", "addr": "89JOHNSON BEACH WAY, PALM COAST, FL- 32137",
     "jurisdiction": "palmcoast"},
    {"id": "58ef3cf4-2522-46c6-8bf6-30c88417633e", "case_number": "2025 CA 000688",
     "parcel_id": "07-11-31-7025-00160-0170", "addr": "2PERROTTI PL, PALM COAST, FL- 32164",
     "jurisdiction": "palmcoast"},
]

# Already have real lat/lon -- zoning-only targets.
ZONING_ONLY_TARGETS = [
    {"id": "5b26cefa-92ed-4cd4-908e-43950eb4d9ee", "case_number": "2025 CA 000010",
     "parcel_id": "10-12-30-0850-01700-0040", "lat": 29.463977, "lon": -81.256023,
     "jurisdiction": "unincorp"},
    {"id": "d1fdb06a-16f9-44d8-879b-d66d0711ca9f", "case_number": "2022 CA 000405",
     "parcel_id": None, "lat": 29.441248761051, "lon": -81.338171262963,
     "jurisdiction": "unincorp"},
]


def rest_patch(row_id, body, retries=3):
    req_data = json.dumps(body).encode()
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}",
            data=req_data, method="PATCH",
            headers={**REST_HEADERS, "Prefer": "return=minimal"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (502, 503, 504) and attempt < retries - 1:
                print(f"    transient HTTP {e.code}, retrying ({attempt+1}/{retries})...")
                time.sleep(2 * (attempt + 1))
                continue
            raise
    raise last_err


def rest_post(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={**REST_HEADERS, "Prefer": "return=representation,resolution=ignore-duplicates"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=REST_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def parse_address(addr):
    parts = [p.strip() for p in addr.split(",")]
    street = parts[0]
    city = parts[1] if len(parts) > 1 else "PALM COAST"
    zipm = re.search(r"(\d{5})", parts[-1])
    zipc = zipm.group(1) if zipm else ""
    m = re.match(r"^(\d+)([A-Za-z].*)$", street)
    if m:
        street = f"{m.group(1)} {m.group(2)}"
    if not street or not zipc:
        return None
    return street, city, zipc


def census_geocode(street, city, zipc):
    params = urllib.parse.urlencode({
        "street": street, "city": city, "state": "FL", "zip": zipc,
        "benchmark": "Public_AR_Current", "format": "json",
    })
    req = urllib.request.Request(f"{CENSUS_URL}?{params}")
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return None
    m = matches[0]
    return m["coordinates"]["y"], m["coordinates"]["x"], m["matchedAddress"]


def arcgis_point_zoning(url, lat, lon, layer_field="LAYER"):
    """Point-in-polygon query. Returns zone code string or None."""
    params = urllib.parse.urlencode({
        "f": "json",
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "false",
    })
    req = urllib.request.Request(f"{url}?{params}")
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    feats = data.get("features", [])
    if not feats:
        return None
    attrs = feats[0]["attributes"]
    return attrs.get(layer_field) or attrs.get("ZONECODE") or attrs.get("ZONE") or attrs.get("ZONING")


def arcgis_point_zoning_buffered(url, lat, lon, layer_field, distance_m=30):
    """Buffered point-in-polygon. Returns zone code if ALL features agree,
    'AMBIGUOUS' if features disagree, None if zero features."""
    params = urllib.parse.urlencode({
        "f": "json",
        "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "distance": str(distance_m),
        "units": "esriSRUnit_Meter",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "false",
    })
    req = urllib.request.Request(f"{url}?{params}")
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    feats = data.get("features", [])
    if not feats:
        return None
    zones = set()
    for f in feats:
        attrs = f["attributes"]
        z = attrs.get(layer_field) or attrs.get("ZONECODE") or attrs.get("ZONE") or attrs.get("ZONING")
        if z:
            zones.add(z)
    if len(zones) == 1:
        return zones.pop()
    return "AMBIGUOUS"


def parcel_zone_exists(parcel_id, jurisdiction_id):
    rows = rest_get(
        f"parcel_zones?parcel_id=eq.{urllib.parse.quote(parcel_id)}"
        f"&jurisdiction_id=eq.{jurisdiction_id}&select=parcel_id")
    return len(rows) > 0


def insert_parcel_zone(parcel_id, jurisdiction_id, zone_code, source):
    if parcel_zone_exists(parcel_id, jurisdiction_id):
        print(f"    parcel_zones already has {parcel_id}/{jurisdiction_id} -- skip insert (dedup guard)")
        return "already_exists"
    status, body = rest_post("parcel_zones", {
        "parcel_id": parcel_id,
        "jurisdiction_id": jurisdiction_id,
        "zone_code": zone_code,
        "source": source,
    })
    print(f"    INSERT parcel_zones {parcel_id} zone_code={zone_code} -> HTTP {status}")
    return "inserted" if status in (200, 201) else f"fail_{status}"


def main():
    dry_run = "--dry-run" in sys.argv
    geo_fixed = 0
    zoning_fixed = 0
    results = []

    print("=== STEP 1: GEO backfill (Census geocoder) ===")
    geocoded = {}
    for row in GEO_TARGETS:
        parsed = parse_address(row["addr"])
        if not parsed:
            print(f"{row['case_number']}: '{row['addr']}' -> UNPARSEABLE")
            continue
        street, city, zipc = parsed
        try:
            match = census_geocode(street, city, zipc)
        except Exception as e:
            print(f"{row['case_number']}: {street} -> GEOCODE ERROR {e}")
            time.sleep(1)
            continue
        if not match:
            print(f"{row['case_number']}: {street}, {city} {zipc} -> NO CENSUS MATCH (left NULL)")
            time.sleep(0.3)
            continue
        lat, lon, matched = match
        print(f"{row['case_number']}: {street}, {city} {zipc} -> {lat},{lon} ({matched})")
        geocoded[row["id"]] = (lat, lon)
        if not dry_run:
            rest_patch(row["id"], {"latitude": lat, "longitude": lon})
            print(f"    PATCHED lat/lon")
        geo_fixed += 1
        time.sleep(0.3)

    print("\n=== STEP 2: ZONING backfill (ArcGIS point-in-polygon) ===")
    all_zoning_targets = []
    for row in GEO_TARGETS:
        if row["id"] in geocoded:
            lat, lon = geocoded[row["id"]]
            all_zoning_targets.append({**row, "lat": lat, "lon": lon})
    all_zoning_targets.extend(ZONING_ONLY_TARGETS)

    for row in all_zoning_targets:
        pid = row.get("parcel_id")
        if not pid:
            print(f"{row['case_number']}: parcel_id NULL -- cannot zone-link, skip (no fabrication)")
            continue
        lat, lon = row["lat"], row["lon"]
        if row["jurisdiction"] == "palmcoast":
            url, jid, field = PALMCOAST_ZONING_URL, PALMCOAST_JURISDICTION_ID, "LAYER"
        else:
            url, jid, field = UNINCORP_ZONING_URL, UNINCORP_JURISDICTION_ID, "ZONECODE"
        try:
            zone = arcgis_point_zoning(url, lat, lon, field)
        except Exception as e:
            print(f"{row['case_number']}: {pid} -> ARCGIS QUERY ERROR {e}")
            time.sleep(0.5)
            continue
        if not zone:
            # Retry with a small buffer (some points sit exactly on/near a
            # polygon boundary and miss a 0-tolerance point query). Only
            # trust the buffer result if ALL returned features within 30m
            # agree on the same zone code -- ambiguous/mixed results (e.g.
            # a boundary between two different zones) are left unzoned
            # rather than guessed, same standard as the 0801 migration's
            # "1 Windsor Pl" residual.
            try:
                buf_zone = arcgis_point_zoning_buffered(url, lat, lon, field, distance_m=30)
            except Exception as e:
                print(f"{row['case_number']}: {pid} -> BUFFER QUERY ERROR {e}")
                time.sleep(0.5)
                continue
            if buf_zone is None:
                print(f"{row['case_number']}: {pid} @ {lat},{lon} -> NO POLYGON HIT even at 30m buffer (left unzoned)")
                time.sleep(0.5)
                continue
            if buf_zone == "AMBIGUOUS":
                print(f"{row['case_number']}: {pid} @ {lat},{lon} -> MIXED zone codes within 30m buffer, not clean enough (left unzoned)")
                time.sleep(0.5)
                continue
            zone = buf_zone
            print(f"{row['case_number']}: {pid} @ {lat},{lon} -> zone_code={zone!r} (30m buffer, unanimous)")
        else:
            print(f"{row['case_number']}: {pid} @ {lat},{lon} -> zone_code={zone!r}")
        source = (f"gold_standard_flagler_i_8gap_20260816_arcgis_"
                  f"{'palmcoast' if row['jurisdiction']=='palmcoast' else 'unincorp'}_verified")
        if not dry_run:
            outcome = insert_parcel_zone(pid, jid, zone, source)
            if outcome == "inserted":
                zoning_fixed += 1
        else:
            zoning_fixed += 1
        results.append((row["case_number"], pid, zone))
        time.sleep(0.5)

    print(f"\nTOTALS: geo_fixed={geo_fixed} zoning_fixed={zoning_fixed}")
    print(f"Zoning results: {results}")

    if len(GEO_TARGETS) > 0 and geo_fixed == 0:
        raise RuntimeError("Parsed >0 geo candidate rows but wrote 0 fixes -- fail-loud, investigate")


if __name__ == "__main__":
    main()
