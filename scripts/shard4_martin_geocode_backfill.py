#!/usr/bin/env python3
"""SHARD-4 (palm_beach/hernando/santa_rosa/martin), dispatch 84d095d7-0a1a-46ee-b7aa-7ac21b7f06f7.

Martin criterion I/J support fix: 5 martin rows newly parity-matched this
session (via scripts/shard11_run3534_santa_rosa_cd_harvest.py run against
martin's realforeclose calendar) already carry a real property_address and
real assessed_value but no latitude/longitude. Same lever as the prior
Duval/Bay I-fixes: the free, public, no-key US Census Bureau geocoder
(geocoding.geo.census.gov) -- real government address-point data, never
invented.

Writes ONLY latitude/longitude, and ONLY on a returned address match.
No-match -> left NULL, never guessed. Idempotent (only patches rows still
missing latitude).

Usage: python3 scripts/shard4_martin_geocode_backfill.py [--dry-run]
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/address"

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# (id, street, city, state, zip) -- the 5 rows newly parity-matched this
# session that had a real property_address but NULL latitude.
TARGETS = [
    ("93e40748-c159-4d0f-af7f-cda8bf1f5270", "5530 SW ORCHID BAY DR", "PALM CITY", "FL", "34990"),
    ("1c413aa5-2cd5-430e-83b4-09292d96dd86", "5612 SW PEACH PALM PL", "PALM CITY", "FL", "34990"),
    ("47ffe827-d919-4920-9bf7-9c64d02dcd5d", "996 SW 29TH TER", "PALM CITY", "FL", "34990"),
    ("dd69461c-4729-4669-8a9c-5865fbeef3e7", "5755 SW RANCHITO ST", "PALM CITY", "FL", "34990"),
    ("5771d80c-d2bc-470a-bec0-900e2c672efd", "2077 NE 21ST TER", "JENSEN BEACH", "FL", "34957"),
]


def rest_patch(row_id, lat, lon):
    body = json.dumps({"latitude": lat, "longitude": lon}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}",
        data=body, method="PATCH",
        headers={**REST_HEADERS, "Prefer": "return=minimal"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def geocode(street, city, state, zipc):
    params = urllib.parse.urlencode({
        "street": street, "city": city, "state": state, "zip": zipc,
        "benchmark": "Public_AR_Current", "format": "json",
    })
    req = urllib.request.Request(f"{CENSUS_URL}?{params}")
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return None
    coords = matches[0]["coordinates"]
    return coords["y"], coords["x"]


def main():
    dry_run = "--dry-run" in sys.argv
    fixed = 0
    for row_id, street, city, state, zipc in TARGETS:
        try:
            match = geocode(street, city, state, zipc)
        except Exception as e:
            print(f"{row_id}: {street} -> GEOCODE ERROR {e}")
            continue
        if not match:
            print(f"{row_id}: {street} -> NO MATCH (left NULL)")
            continue
        lat, lon = match
        print(f"{row_id}: {street} -> {lat},{lon}")
        if not dry_run:
            status = rest_patch(row_id, lat, lon)
            print(f"  PATCHED (HTTP {status})")
        fixed += 1
    print(f"\nTOTAL geocoded: {fixed}/{len(TARGETS)}")


if __name__ == "__main__":
    main()
