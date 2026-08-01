#!/usr/bin/env python3
"""
SHARD-4 Issue #17123 — Live evaluation of calhoun, sarasota, baker, suwannee
Dispatch: 61cdbda5-c47b-46e0-adca-64b627bbea64
"""
import os
import sys
import json
import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")

if not KEY:
    print("ERROR: No Supabase key found in environment")
    sys.exit(1)

HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
}

COUNTIES = ["calhoun", "sarasota", "baker", "suwannee"]

def evaluate_county(county):
    r = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        headers=HEADERS,
        json={"p_county": county},
        timeout=60,
    )
    if r.status_code == 200:
        return r.json()
    # Try alternate param name
    r2 = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        headers=HEADERS,
        json={"county_slug_arg": county},
        timeout=60,
    )
    if r2.status_code == 200:
        return r2.json()
    return {"error": f"{r.status_code}: {r.text[:200]}"}

def get_recent_calhoun_outcomes():
    """Check if any calhoun sales have closed since the last session."""
    r = httpx.get(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
        headers=HEADERS,
        params={
            "county": "eq.calhoun",
            "select": "case_number,auction_date,auction_status,sale_type,sold_amount,tier1_sale_status",
            "order": "auction_date.desc",
        },
        timeout=30,
    )
    if r.status_code == 200:
        return r.json()
    return []

def get_suwannee_status():
    """Check suwannee auctions for any closed sales."""
    r = httpx.get(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
        headers=HEADERS,
        params={
            "county": "eq.suwannee",
            "select": "case_number,auction_date,auction_status,sale_type,sold_amount,tier1_sale_status,parity_status",
            "order": "auction_date.desc",
        },
        timeout=30,
    )
    if r.status_code == 200:
        return r.json()
    return []

def get_baker_status():
    """Check baker auctions."""
    r = httpx.get(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
        headers=HEADERS,
        params={
            "county": "eq.baker",
            "select": "case_number,auction_date,auction_status,sale_type,parcel_id,property_address,parity_status",
            "order": "auction_date.desc",
            "limit": "20",
        },
        timeout=30,
    )
    if r.status_code == 200:
        return r.json()
    return []

def get_sarasota_j_gap():
    """Check sarasota bid_decisions coverage."""
    r = httpx.get(
        f"{SUPABASE_URL}/rest/v1/bid_decisions",
        headers=HEADERS,
        params={
            "county_slug": "eq.sarasota",
            "select": "count",
        },
        headers={**HEADERS, "Prefer": "count=exact"},
        timeout=30,
    )
    if r.status_code == 200:
        count = r.headers.get("content-range", "")
        return count
    return f"error: {r.status_code}"

def check_sarasota_g_zones():
    """Check sarasota pk1000 blocking districts."""
    r = httpx.get(
        f"{SUPABASE_URL}/rest/v1/zone_standards",
        headers=HEADERS,
        params={
            "zoning_district_id": "in.(12598,12335,12591,12902)",
            "select": "zoning_district_id,parking_per_1000sf,max_density_du_acre,max_far",
        },
        timeout=30,
    )
    if r.status_code == 200:
        return r.json()
    return []

if __name__ == "__main__":
    print("=== SHARD-4 LIVE EVALUATION — 2026-08-01 ===")
    print(f"Dispatch: 61cdbda5-c47b-46e0-adca-64b627bbea64\n")

    for county in COUNTIES:
        print(f"\n{'='*50}")
        print(f"COUNTY: {county.upper()}")
        print('='*50)
        result = evaluate_county(county)
        print(json.dumps(result, indent=2, default=str))

    print("\n\n=== CALHOUN AUCTIONS ===")
    calhoun = get_recent_calhoun_outcomes()
    for row in calhoun:
        print(f"  {row.get('case_number')} | {row.get('auction_date')} | {row.get('auction_status')} | sold={row.get('sold_amount')} | tier1={row.get('tier1_sale_status')}")

    print("\n\n=== SUWANNEE AUCTIONS ===")
    suwannee = get_suwannee_status()
    for row in suwannee:
        print(f"  {row.get('case_number')} | {row.get('auction_date')} | {row.get('auction_status')} | parity={row.get('parity_status')}")

    print("\n\n=== BAKER AUCTIONS ===")
    baker = get_baker_status()
    for row in baker:
        print(f"  {row.get('case_number')} | {row.get('auction_date')} | parcel={row.get('parcel_id')} | addr={row.get('property_address')} | parity={row.get('parity_status')}")

    print("\n\n=== SARASOTA G BLOCKING ZONES ===")
    zones = check_sarasota_g_zones()
    for z in zones:
        print(f"  district_id={z.get('zoning_district_id')} | pk1000={z.get('parking_per_1000sf')} | density={z.get('max_density_du_acre')} | far={z.get('max_far')}")
