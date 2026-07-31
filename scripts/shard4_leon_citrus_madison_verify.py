#!/usr/bin/env python3
"""
SHARD-4 Verification script for leon, citrus, madison
dispatch_id: 0f07f453-008b-41a6-9ede-579226e44ddc
loop run: 7622
"""
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)

COUNTIES = ["leon", "citrus", "madison"]


def sb_rpc(fn_name: str, params: dict):
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}"
    payload = json.dumps(params).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return None, f"HTTP {e.code}: {body}"


def sb_get(table: str, params: str):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return None, f"HTTP {e.code}: {body}"


def sb_sql(query: str):
    """Execute SQL via the sql endpoint"""
    url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
    payload = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return None, f"HTTP {e.code}: {body}"


def evaluate_county(county: str):
    print(f"\n{'='*60}")
    print(f"Evaluating {county.upper()}")
    print(f"{'='*60}")
    result, err = sb_rpc("pencil_dod_evaluate_county", {"p_county": county})
    if err:
        print(f"ERROR: {err}")
        return None
    print(f"Result: {json.dumps(result, indent=2)}")
    return result


def check_citrus_failing_parcels():
    """Check which Citrus auctions are missing parcel linkage"""
    print("\n--- Citrus: Missing Parcel Linkage Diagnosis ---")
    result, err = sb_get(
        "multi_county_auctions",
        "county=eq.citrus&parcel_id=is.null&select=case_number,property_address,sale_date,auction_date&order=auction_date.desc&limit=20"
    )
    if err:
        print(f"ERROR: {err}")
        return
    print(f"Citrus auctions missing parcel_id: {len(result) if result else 0}")
    if result:
        for r in result[:15]:
            print(f"  case={r.get('case_number')} addr={r.get('property_address')} sale={r.get('sale_date')} auction={r.get('auction_date')}")


def check_citrus_card_gaps():
    """Check which Citrus auctions fail property card completeness"""
    print("\n--- Citrus: Property Card Gaps ---")
    result, err = sb_get(
        "multi_county_auctions",
        "county=eq.citrus&select=case_number,property_address,parcel_id,latitude,longitude,assessed_value,market_value,sale_date&order=sale_date.desc&limit=30"
    )
    if err:
        print(f"ERROR: {err}")
        return
    if result:
        gaps = []
        for r in result:
            missing = []
            if not r.get("property_address"):
                missing.append("address")
            if not r.get("latitude") and not r.get("longitude"):
                missing.append("geo")
            if not r.get("assessed_value") and not r.get("market_value"):
                missing.append("value")
            if not r.get("parcel_id"):
                missing.append("parcel_id")
            if missing:
                gaps.append({"case": r.get("case_number"), "missing": missing, "auction_date": r.get("sale_date")})
        print(f"Rows with gaps (sample of 30): {len(gaps)}")
        for g in gaps[:10]:
            print(f"  case={g['case']} missing={g['missing']}")


def check_madison_pipeline():
    """Check Madison pipeline.counties configuration"""
    print("\n--- Madison: Pipeline Configuration ---")
    result, err = sb_get(
        "pipeline.counties" if False else "counties",
        "slug=eq.madison&select=*&limit=1"
    )
    if err:
        # Try with schema prefix
        result2, err2 = sb_get(
            "pipeline_counties",
            "slug=eq.madison&select=*&limit=1"
        )
        if err2:
            print(f"pipeline.counties error: {err}, pipeline_counties error: {err2}")
        else:
            print(f"Madison pipeline_counties: {json.dumps(result2, indent=2)}")
    else:
        print(f"Madison pipeline.counties: {json.dumps(result, indent=2)}")


def check_madison_auctions():
    """Check current Madison auctions"""
    print("\n--- Madison: Auction Count ---")
    result, err = sb_get(
        "multi_county_auctions",
        "county=eq.madison&select=case_number,auction_type,sale_date,auction_date,parity_status&order=auction_date.desc&limit=20"
    )
    if err:
        print(f"ERROR: {err}")
        return
    print(f"Madison auctions total (limited): {len(result) if result else 0}")
    if result:
        fc_count = sum(1 for r in result if r.get("auction_type") == "foreclosure")
        td_count = sum(1 for r in result if r.get("auction_type") == "tax_deed")
        print(f"  Foreclosure: {fc_count}, Tax Deed: {td_count}")
        for r in result:
            print(f"  case={r.get('case_number')} type={r.get('auction_type')} sale={r.get('sale_date')} auction={r.get('auction_date')}")


def check_madison_outcomes():
    """Check Madison verified outcomes"""
    print("\n--- Madison: Verified Outcomes ---")
    result, err = sb_get(
        "foreclosure_outcomes",
        "county_slug=eq.madison&select=case_number,data_source,winning_bid,sale_date&limit=20"
    )
    if err:
        print(f"foreclosure_outcomes error: {err}")
    else:
        print(f"Madison foreclosure_outcomes: {len(result) if result else 0} rows")

    result2, err2 = sb_get(
        "tax_deed_outcomes",
        "county_slug=eq.madison&select=case_number,data_source,winning_bid,sale_date&limit=20"
    )
    if err2:
        print(f"tax_deed_outcomes error: {err2}")
    else:
        print(f"Madison tax_deed_outcomes: {len(result2) if result2 else 0} rows")


def check_ultraloop_audit(county: str):
    """Check recent ultraloop audit rows"""
    print(f"\n--- {county}: Ultraloop Audit Rows ---")
    result, err = sb_get(
        "gold_standard_ultraloop_audit",
        f"county_slug=eq.{county}&select=letter,survived,dispatch_id,claim&order=letter.asc&limit=20"
    )
    if err:
        print(f"ERROR: {err}")
        return
    if result:
        passed = [r for r in result if r.get("survived")]
        failed = [r for r in result if not r.get("survived")]
        print(f"  survived=true: {len(passed)}, survived=false: {len(failed)}")
        for r in result[:15]:
            print(f"  letter={r.get('letter')} survived={r.get('survived')}")
    else:
        print("  No audit rows found")


def main():
    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_KEY not set")
        sys.exit(1)

    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY: {'SET (len=' + str(len(SUPABASE_KEY)) + ')' if SUPABASE_KEY else 'NOT SET'}")

    # SET statement_timeout=0 hint for long queries
    print("\n=== BASELINE EVALUATIONS (dispatch 0f07f453) ===")
    evaluations = {}
    for county in COUNTIES:
        result = evaluate_county(county)
        evaluations[county] = result

    # Additional diagnostics
    check_citrus_failing_parcels()
    check_citrus_card_gaps()
    check_madison_pipeline()
    check_madison_auctions()
    check_madison_outcomes()

    for county in COUNTIES:
        check_ultraloop_audit(county)

    print("\n=== SUMMARY ===")
    for county, ev in evaluations.items():
        if ev:
            passes = sum(1 for k, v in ev.items() if isinstance(v, dict) and v.get("pass"))
            total = sum(1 for k, v in ev.items() if isinstance(v, dict) and "pass" in v)
            print(f"{county}: {passes}/{total}")
        else:
            print(f"{county}: evaluation failed")


if __name__ == "__main__":
    main()
