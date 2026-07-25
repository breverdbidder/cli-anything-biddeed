#!/usr/bin/env python3
"""
sumter_i_reverse_geocode_fix.py
 
Gold Standard shard-5 (sumter): fix Criterion I (property card completeness)
for case 2025-CA-000255 / parcel D29A024.

CONTEXT (from prior session archaeology, 2026-07-11 through 2026-07-25):
- All other 10 sumter auctions already have property_address (6 real addresses
  from FL DOR cadastral + 3 reverse-geocoded via Sumter County ArcGIS Geocoder)
- D29A024 is a vacant industrial parcel in Wildwood, FL (Wildwood Phase One LLC)
  with parcel geometry confirmed via SWFWMD + FL DOR cadastral cross-check
- parcel_id=D29A024, lat=28.893758, lon=-82.035730 (set by 2026-07-24 migration)
- assessed_value=1133690, zone_code linked via parcel_zones (G=PASS)
- ONLY missing field is property_address (evaluator requires it for card_complete)

APPROACH: Sumter County ArcGIS reverseGeocode endpoint
(same endpoint used by shard14 session for TD-5056, TD-5058, TD-5054 vacant parcels)
Endpoint: https://gis.sumtercountyfl.gov/sumtergis/rest/services/Operations/
           Sumter_Geocoder/GeocodeServer/reverseGeocode
Parameters: location=-82.03573,28.89376&distance=500&outSR=4326&f=json

Fallback: US Census TIGER/Line geocoder (reverseGeocode via coordinates)
URL: https://geocoding.geo.census.gov/geocoder/locations/coordinates

If both fail: document as permanent structural gap (honesty protocol).
"""

import json
import os
import sys
import urllib.error
import urllib.request
import urllib.parse

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
SUPABASE_PROJECT_REF = "mocerqjnksmhcjzxrewo"

MCA_ID = "8ea8c278-94ae-4e8c-ba6e-6e1538aae148"
CASE_NUMBER = "2025-CA-000255"
COUNTY = "sumter"
PARCEL_ID = "D29A024"
LAT = 28.893758
LON = -82.035730

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

MGMT_HEADERS = {
    "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


def fetch_json(url, timeout=15):
    """Fetch URL and return parsed JSON."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode()), resp.status


def run_sql(sql, label="query"):
    """Execute SQL via Supabase Management API."""
    payload = json.dumps({"query": sql}).encode()
    url = f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/database/query"
    req = urllib.request.Request(url, data=payload, headers=MGMT_HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        print(f"[SQL:{label}] HTTP {resp.status}")
        return data


def try_sumter_county_reverse_geocode():
    """
    Try Sumter County ArcGIS reverseGeocode endpoint.
    Returns address string if found, None otherwise.
    """
    print("\n=== Attempt 1: Sumter County ArcGIS reverseGeocode ===")
    url = (
        f"https://gis.sumtercountyfl.gov/sumtergis/rest/services/Operations/"
        f"Sumter_Geocoder/GeocodeServer/reverseGeocode"
        f"?location={LON},{LAT}&distance=500&outSR=4326&f=json"
    )
    try:
        data, status = fetch_json(url)
        print(f"HTTP {status}: {json.dumps(data)[:300]}")
        if "address" in data and data["address"].get("Address"):
            addr = data["address"]["Address"]
            city = data["address"].get("City", "")
            state = data["address"].get("State", "FL")
            zip_code = data["address"].get("Zip", "")
            if city:
                full = f"{addr}, {city}, {state}"
                if zip_code:
                    full += f" {zip_code}"
            else:
                full = f"{addr}, WILDWOOD, FL"
            print(f"FOUND address: {full}")
            return full, "sumter_gis_reversegeocode"
        elif "error" in data:
            print(f"Error in response: {data['error']}")
            return None, None
        else:
            print(f"No address in response: {list(data.keys())}")
            return None, None
    except urllib.error.HTTPError as e:
        print(f"HTTPError {e.code}: {e.read().decode()[:200]}")
        return None, None
    except Exception as e:
        print(f"Exception: {e}")
        return None, None


def try_census_reverse_geocode():
    """
    Try US Census TIGER reverseGeocode (returns nearest road from TIGER/Line).
    Returns address string if found, None otherwise.
    """
    print("\n=== Attempt 2: US Census TIGER reverse geocoder ===")
    url = (
        f"https://geocoding.geo.census.gov/geocoder/locations/coordinates"
        f"?x={LON}&y={LAT}&benchmark=2020&vintage=2010&layers=9&format=json"
    )
    try:
        data, status = fetch_json(url)
        print(f"HTTP {status}: {json.dumps(data)[:300]}")
        # Census reverse geocoder returns address matches in result.addressMatches
        matches = data.get("result", {}).get("addressMatches", [])
        if matches:
            m = matches[0]
            addr = m.get("matchedAddress", "")
            print(f"FOUND address: {addr}")
            return addr, "census_tiger_reversegeocode"
        else:
            print("No address matches returned")
            return None, None
    except Exception as e:
        print(f"Exception: {e}")
        return None, None


def try_nominatim_reverse_geocode():
    """
    Try OpenStreetMap Nominatim reverse geocoder (last resort).
    """
    print("\n=== Attempt 3: OpenStreetMap Nominatim reverse geocoder ===")
    url = (
        f"https://nominatim.openstreetmap.org/reverse"
        f"?lat={LAT}&lon={LON}&format=json&zoom=16&addressdetails=1"
    )
    headers = {"User-Agent": "BidDeed.AI Gold Standard GIS Research 2026"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            print(f"HTTP {resp.status}: {json.dumps(data)[:300]}")
            if "display_name" in data:
                # Parse to a usable address
                addr_parts = data.get("address", {})
                road = addr_parts.get("road", "")
                city = addr_parts.get("city", addr_parts.get("town", addr_parts.get("village", "")))
                state = addr_parts.get("state", "Florida")
                postcode = addr_parts.get("postcode", "")
                if road:
                    addr = road
                    if city:
                        addr += f", {city}, FL"
                    else:
                        addr += ", WILDWOOD, FL"
                    if postcode:
                        addr += f" {postcode}"
                    print(f"FOUND address: {addr}")
                    return addr, "nominatim_reversegeocode"
                else:
                    print(f"No road in Nominatim response: {list(addr_parts.keys())}")
                    return None, None
            return None, None
    except Exception as e:
        print(f"Exception: {e}")
        return None, None


def verify_current_state():
    """Query live DB for current state of D29A024 row."""
    print("\n=== Verifying current DB state ===")
    sql = f"""
SET statement_timeout = 0;
SELECT id, case_number, county, parcel_id, property_address,
       latitude, longitude, assessed_value, market_value
FROM multi_county_auctions
WHERE county = 'sumter' AND case_number = '2025-CA-000255';
"""
    try:
        result = run_sql(sql, "verify_current_state")
        print(json.dumps(result, indent=2)[:500])
        return result
    except Exception as e:
        print(f"SQL error: {e}")
        return None


def verify_parcel_zones():
    """Check if D29A024 has a parcel_zones entry."""
    sql = f"""
SELECT pz.id, pz.parcel_id, pz.jurisdiction_id, pz.zone_code, pz.zone_name, pz.source
FROM parcel_zones pz
WHERE pz.parcel_id = 'D29A024';
"""
    try:
        result = run_sql(sql, "verify_parcel_zones")
        print("parcel_zones for D29A024:", json.dumps(result, indent=2)[:500])
        return result
    except Exception as e:
        print(f"SQL error: {e}")
        return None


def apply_address_fix(address, source):
    """Write property_address to multi_county_auctions for the D29A024 row."""
    print(f"\n=== Applying address fix ===")
    print(f"Address: {address}")
    print(f"Source: {source}")
    sql = f"""
UPDATE multi_county_auctions
SET property_address = '{address.replace(chr(39), chr(39)+chr(39))}',
    updated_at = NOW()
WHERE county = 'sumter' AND case_number = '2025-CA-000255'
  AND property_address IS NULL;
"""
    try:
        result = run_sql(sql, "apply_address_fix")
        print("Apply result:", json.dumps(result, indent=2)[:300])
        return True
    except Exception as e:
        print(f"SQL error: {e}")
        return False


def evaluate_sumter():
    """Run pencil_dod_evaluate_county('sumter') and return result."""
    sql = "SELECT public.pencil_dod_evaluate_county('sumter');"
    try:
        result = run_sql(sql, "evaluate_sumter")
        print("\n=== pencil_dod_evaluate_county('sumter') ===")
        print(json.dumps(result, indent=2))
        return result
    except Exception as e:
        print(f"SQL error: {e}")
        return None


def main():
    print("=" * 60)
    print("sumter I fix: property_address for D29A024")
    print("=" * 60)

    if not SUPABASE_ACCESS_TOKEN:
        print("ERROR: SUPABASE_ACCESS_TOKEN not set")
        sys.exit(1)

    # Step 1: Verify current state
    before = evaluate_sumter()
    verify_parcel_zones()

    # Step 2: Try reverse geocoders in priority order
    address = None
    source = None

    addr, src = try_sumter_county_reverse_geocode()
    if addr:
        address, source = addr, src
    
    if not address:
        addr, src = try_census_reverse_geocode()
        if addr:
            address, source = addr, src
    
    if not address:
        addr, src = try_nominatim_reverse_geocode()
        if addr:
            address, source = addr, src

    if not address:
        print("\n=== ALL GEOCODERS FAILED ===")
        print("No address found for D29A024. I remains at 90.9% (10 of 11).")
        print("BLOCKED: no further approaches available without CAPTCHA solving.")
        sys.exit(1)

    print(f"\n=== ADDRESS FOUND: {address} (source={source}) ===")
    
    # Step 3: Apply fix
    ok = apply_address_fix(address, source)
    if not ok:
        print("Fix application failed")
        sys.exit(1)

    # Step 4: Verify metric moved
    after = evaluate_sumter()
    
    print("\n=== BEFORE vs AFTER ===")
    print(f"BEFORE: {json.dumps(before, indent=2)[:600]}")
    print(f"AFTER:  {json.dumps(after, indent=2)[:600]}")

    # Check if I PASS
    if after:
        # Parse the result
        try:
            result_data = after
            if isinstance(after, list) and len(after) > 0:
                result_data = after[0].get("pencil_dod_evaluate_county", after[0])
            i_data = result_data.get("I", {})
            i_pass = i_data.get("pass", False)
            i_metric = i_data.get("metric", 0)
            print(f"\nI criterion: pass={i_pass}, metric={i_metric}")
            if i_pass:
                print("SUCCESS: I is now PASSING!")
            else:
                print(f"I still failing at {i_metric}%")
        except Exception as e:
            print(f"Error parsing result: {e}")

    print(f"\nAddress written: {address}")
    print(f"Source: {source}")


if __name__ == "__main__":
    main()
