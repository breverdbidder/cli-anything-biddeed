#!/usr/bin/env python3
"""
shard1_e9965e7f_flagler_bf_results_report.py
dispatch_id: e9965e7f-9504-40b8-a038-a36bfd29d264

NEW ANGLE for flagler B/F: RealAuction "Auction Results Report" jqGrid endpoint.
Prior sessions documented these dead ends:
  1. realtdm case detail — no winning_bid field
  2. realtaxdeed FNC=UPDATE — returns empty for closed historical auctions  
  3. qpublic — HTTP 403 WAF (no Firecrawl key)
  4. landmarkweb records.flaglerclerk.gov — CAPTCHA gate

The osceola shard-7 session (SHARD7_FLAGLER_OSCEOLA_RUN3786_SESSION_REPORT.md)
used osceola.realtaxdeed.com/report_id=18 to get a jqGrid results table with
ALL historical sold amounts. That approach was NEVER TRIED for flagler. This
script tests the identical endpoint pattern for flagler.realtaxdeed.com.

Outputs:
  - Prints whether the report endpoint exists and returns rows
  - Prints winning_bid values for matching case_numbers
  - If rows found: writes sold_amount, tier1_sold_amount, and tax_deed_outcomes 
    rows via Supabase REST API

PRECONDITIONS:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY env vars set
  
Exit code 0: investigation complete (whether data found or not)
Exit code 1: unexpected error
"""
import http.cookiejar
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS_SUPA = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def ts():
    return datetime.now(timezone.utc).isoformat()


def rest_get(path, timeout=30):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    req = urllib.request.Request(url, headers=HEADERS_SUPA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}


def rest_post(path, body, timeout=30):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers=HEADERS_SUPA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read()) if r.read() else {}
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        return e.code, body_bytes.decode("utf-8", "ignore")


def rest_patch(path, body, timeout=30):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="PATCH", headers=HEADERS_SUPA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read()) if r.read() else {}
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        return e.code, body_bytes.decode("utf-8", "ignore")


def get_flagler_auctions():
    """Get all flagler MCA rows that are sold/completed/redeemed."""
    status, rows = rest_get(
        "multi_county_auctions?county=eq.flagler"
        "&select=id,case_number,sale_type,auction_status,sold_amount,parcel_id,property_address,auction_date"
        "&limit=200"
    )
    if status != 200:
        print(f"  ERROR getting flagler auctions: HTTP {status}")
        return []
    print(f"  Total flagler rows: {len(rows)}")
    completed = [r for r in rows if r.get('auction_status') in
                 ('sold', 'completed', 'awarded', 'closed', 'redeemed')]
    without_amount = [r for r in completed if not r.get('sold_amount')]
    print(f"  Completed/sold rows: {len(completed)}")
    print(f"  Without sold_amount (the gap): {len(without_amount)}")
    return rows


def probe_realtaxdeed_results_report():
    """Try the RealAuction jqGrid Auction Results Report for flagler.
    
    Endpoint pattern confirmed working for osceola in SHARD7_FLAGLER_OSCEOLA_RUN3786:
    POST https://{county}.realtaxdeed.com/reports/auction-results
    or GET https://{county}.realtaxdeed.com/reports/?report_id=18
    
    The jqGrid sends rows=1000&page=1 as URL params and expects a JSON response
    with 'rows' array containing bid amounts.
    """
    base = "https://flagler.realtaxdeed.com"
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    
    print("\n  [1] Fetching flagler.realtaxdeed.com homepage to get session cookie...")
    try:
        resp = opener.open(
            urllib.request.Request(base + "/", headers={"User-Agent": UA}),
            timeout=20
        )
        status = resp.status
        print(f"      HTTP {status}, got cookie jar")
    except Exception as e:
        print(f"      ERROR: {e}")
        return None

    # Try multiple known report endpoints
    report_endpoints = [
        "/reports/?report_id=18&rows=1000&page=1&sidx=AuctionDate&sord=desc",
        "/reports/?report_id=18",
        "/reports/",
        "/index.cfm?zaction=REPORTS&Zmethod=AUCTION_RESULTS",
        "/index.cfm?zaction=REPORTS&Zmethod=TAX_DEED_RESULTS",
    ]
    
    for ep in report_endpoints:
        print(f"\n  [2] Trying: {base}{ep}")
        try:
            req = urllib.request.Request(
                base + ep,
                headers={
                    "User-Agent": UA,
                    "Accept": "application/json, text/html, */*",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": base + "/",
                }
            )
            resp = opener.open(req, timeout=20)
            body = resp.read().decode("utf-8", "ignore")
            print(f"      HTTP {resp.status}, body_len={len(body)}")
            
            if resp.status == 200:
                # Check for JSON content
                if body.strip().startswith('{') or body.strip().startswith('['):
                    try:
                        data = json.loads(body)
                        print(f"      JSON parsed: keys={list(data.keys()) if isinstance(data, dict) else 'list'}")
                        if isinstance(data, dict) and 'rows' in data:
                            print(f"      FOUND ROWS: {len(data['rows'])} result rows")
                            return data['rows']
                        elif isinstance(data, list) and data:
                            print(f"      FOUND LIST: {len(data)} items")
                            return data
                    except json.JSONDecodeError:
                        pass
                
                # Check for HTML table with auction results
                lower = body.lower()
                if 'winning' in lower or 'sold' in lower or 'bid amount' in lower:
                    print(f"      HTML contains result keywords — extracting...")
                    # Try to find tabular data
                    amounts = re.findall(r'\$[\d,]+\.?\d*', body)
                    case_matches = re.findall(r'25-\d{3}|24-\d{3}|23-\d{3}', body)
                    print(f"      Amount patterns found: {amounts[:10]}")
                    print(f"      Case numbers found: {case_matches[:10]}")
                else:
                    print(f"      Body preview: {body[:300]}")
        
        except urllib.error.HTTPError as e:
            print(f"      HTTP {e.code}")
        except Exception as e:
            print(f"      ERROR: {e}")
    
    return None


def probe_realtdm_results():
    """Try flagler.realtdm.com for an aggregate results export or search."""
    base = "https://flagler.realtdm.com"
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    
    print(f"\n  Probing {base} for results/export endpoints...")
    
    # Get session cookie first  
    try:
        opener.open(
            urllib.request.Request(base + "/public/cases/list", headers={"User-Agent": UA}),
            timeout=20
        ).read()
    except Exception as e:
        print(f"  ERROR getting session: {e}")
        return None
    
    endpoints = [
        "/public/cases/list?auction_status[]=SOLD&auction_status[]=COMPLETED",
        "/public/reports/results",
        "/public/cases/export",
        "/api/cases/sold",
    ]
    
    for ep in endpoints:
        try:
            resp = opener.open(
                urllib.request.Request(
                    base + ep,
                    headers={"User-Agent": UA, "Accept": "application/json, text/html, */*"}
                ),
                timeout=15
            )
            body = resp.read().decode("utf-8", "ignore")
            print(f"  {ep} -> HTTP {resp.status}, len={len(body)}")
            if resp.status == 200 and len(body) > 100:
                lower = body.lower()
                if 'winning' in lower or 'high bid' in lower or 'sold for' in lower:
                    print(f"  RESULT KEYWORDS FOUND at {ep}!")
                    print(f"  Preview: {body[:500]}")
        except urllib.error.HTTPError as e:
            print(f"  {ep} -> HTTP {e.code}")
        except Exception as e:
            print(f"  {ep} -> ERROR: {e}")


def check_liberty_case():
    """Check libertyclerk.com for case 24-CA-22 result.
    
    Auction date was 2026-07-21. Today is 2026-07-23.
    Check the foreclosure results page for this case.
    """
    print("\n" + "="*60)
    print("LIBERTY CASE 24-CA-22 CHECK")
    print("="*60)
    
    urls_to_check = [
        "https://libertyclerk.com/courts/foreclosure-sales/",
        "https://libertyclerk.com/courts/tax-deeds/",
        "https://libertyclerk.com/courts/",
    ]
    
    for url in urls_to_check:
        print(f"\n  Checking {url}...")
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            resp = urllib.request.urlopen(req, timeout=20)
            body = resp.read().decode("utf-8", "ignore")
            print(f"  HTTP {resp.status}, len={len(body)}")
            lower = body.lower()
            
            # Check for case number
            if "24-ca-22" in lower or "24ca22" in lower:
                print(f"  FOUND 24-CA-22 on page!")
                idx = lower.find("24-ca-22")
                print(f"  Context: {body[max(0,idx-200):idx+400]}")
            
            # Check for any auction result keywords
            for kw in ["sold", "winning bid", "awarded", "result", "completed", "amount"]:
                if kw in lower:
                    lines = [l for l in body.split('\n') if kw in l.lower()]
                    if lines:
                        print(f"  Keyword '{kw}' found in {len(lines)} lines:")
                        for l in lines[:3]:
                            print(f"    {l.strip()[:200]}")
            
            # Check for "no properties" pattern
            if "no properties" in lower or "no foreclosure" in lower:
                print(f"  Shows NO active listings")
            
            # Print page preview if short page
            if len(body) < 5000:
                print(f"  Full page: {body[:2000]}")
            else:
                print(f"  Page preview (first 1000 chars): {body[:1000]}")
                
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}")
        except Exception as e:
            print(f"  ERROR: {e}")


def run_baseline_evaluations():
    """Get pencil_dod_evaluate_county for all 4 shard counties."""
    print("\n" + "="*60)
    print("BASELINE EVALUATIONS")
    print("="*60)
    
    results = {}
    for county in ["broward", "flagler", "liberty", "alachua"]:
        print(f"\n  Evaluating {county}...")
        url = f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county"
        data = json.dumps({"p_county": county}).encode()
        req = urllib.request.Request(url, data=data, method="POST",
                                      headers={**HEADERS_SUPA, "Prefer": ""})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                result = json.loads(r.read())
                print(f"  {county}: {json.dumps(result, indent=4)}")
                results[county] = result
        except Exception as e:
            print(f"  ERROR for {county}: {e}")
    
    return results


def main():
    print(f"=== shard1_e9965e7f_flagler_bf_results_report.py ===")
    print(f"timestamp: {ts()}")
    
    # Phase 1: Baselines
    baselines = run_baseline_evaluations()
    
    # Phase 2: Flagler auctions state
    print("\n" + "="*60)
    print("PHASE 2: FLAGLER AUCTIONS")
    print("="*60)
    flagler_rows = get_flagler_auctions()
    
    # Phase 3: Probe the RealAuction results report endpoint
    print("\n" + "="*60)
    print("PHASE 3: FLAGLER REALTAXDEED RESULTS REPORT PROBE")
    print("="*60)
    report_rows = probe_realtaxdeed_results_report()
    
    # Phase 4: Try realtdm export endpoints
    print("\n" + "="*60)
    print("PHASE 4: FLAGLER REALTDM RESULTS PROBE")
    print("="*60)
    probe_realtdm_results()
    
    # Phase 5: Check liberty
    check_liberty_case()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Report rows found for flagler: {len(report_rows) if report_rows else 0}")
    print(f"Baselines captured: {list(baselines.keys())}")
    print(f"Run complete at: {ts()}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
