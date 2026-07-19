#!/usr/bin/env python3
"""
SHARD-7 run5153: Madison County B/F probe + tax-deed A fix.

CONTEXT:
  madison (7/10): A FAIL metric=0 [fc=5 td=0], B FAIL [verified=0], F FAIL [null]
  From SHARD4_RUN20260710 report:
    - A fails because td=0 (all 5 madison auctions are foreclosures, no tax deeds)
    - B/F null because no auctions have closed yet
    - Earliest madison auction was 2026-07-14 -> SOME may have closed by now (today=2026-07-19)
    - madison.realforeclose.com + realtaxdeed.com both 302 to www.realauction.com
      -> Madison is NOT on the RealAuction platform
    - Need to find the actual madison auction platform

  madison A=0: criterion A requires td>=1 (at least one tax deed). If madison only has
  foreclosure auctions (not tax deed), criterion A cannot pass until a TD case is
  ingested. The brief shows fc=5 td=0.

  Madison County Florida:
  - Small county, population ~18K
  - Tax deed sales: Madison County Tax Collector / Clerk of Courts
  - Official records: Madison County Clerk: https://www.madisoncountyflorida.org/
  - Tax deed auctions may be via Realforeclose or direct county site

STRATEGY:
  1. Check if any madison auction_status changed to 'sold'/'redeemed' since Jul14
     (monitoring realforeclose equivalent or direct probe)
  2. Probe Madison County's actual auction platform for tax deeds
  3. If tax deeds found: ingest to push A metric above 0
  4. If FC auctions closed: write foreclosure_outcomes to push B/F

  HONESTY: Madison County auction platform is INFERRED to be either RealTaxDeed.com
  or direct county site. Platform lookup needed before any data fetch.

dispatch_id: bc399d3b-f50e-406a-a0f1-66d8f4f5d9d7
"""
from __future__ import annotations
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

COUNTY = "madison"
SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def ts():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="INFO"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def sb_get(path, params=None):
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def probe_url(url, label):
    """Probe a URL and log the result."""
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            log(f"  {label}: HTTP {r.status} (OK)", "VERIFIED")
            return r.status, r.url  # r.url = final URL after redirects
    except urllib.error.HTTPError as e:
        log(f"  {label}: HTTP {e.code}", "VERIFIED")
        return e.code, url
    except Exception as e:
        log(f"  {label}: ERROR {e}", "WARN")
        return None, url


def main():
    log("=== SHARD-7 run5153: madison B/F probe + A analysis ===")

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE: {json.dumps({k: baseline.get(k) for k in ['A','B','C','D','E','F','G','H','I','J']})}", "VERIFIED")
    log(f"BASELINE auctions_total: {baseline.get('auctions_total')}", "VERIFIED")

    # Step 1: Check current madison auctions
    auctions = sb_get("multi_county_auctions", {
        "county": "eq.madison",
        "select": "case_number,auction_status,auction_date,auction_type,property_address,opening_bid",
        "limit": "50",
    })
    log(f"Madison auctions in DB: {len(auctions)}", "VERIFIED")
    for a in auctions:
        log(f"  {a.get('case_number')} | type={a.get('auction_type')} | status={a.get('auction_status')} | date={a.get('auction_date')}", "VERIFIED")

    # Step 2: Probe Madison County auction platforms
    log("Probing auction platforms for Madison County...", "INFO")
    platforms = [
        ("https://madison.realforeclose.com", "madison.realforeclose.com"),
        ("https://madison.realtaxdeed.com", "madison.realtaxdeed.com"),
        ("https://www.realauction.com/index-madison.html", "realauction.com/madison"),
        ("https://www.realauction.com/category.html?co=37", "realauction.com county=37"),
        ("https://www.madisoncountyflorida.org/clerkofcourts", "Madison Clerk main page"),
        ("https://www.madisoncountyflorida.org/departments/property-appraiser", "Madison PA"),
        ("https://bids.realforeclose.com/index.cfm?zaction=COUNTY&Zmethod=DISPLAY&COUNTY=Madison", "realforeclose bids madison"),
    ]
    for url, label in platforms:
        probe_url(url, label)

    # Step 3: Check pipeline.counties for madison
    pipeline_rows = sb_get("pipeline", {
        "select": "county_slug,foreclosure_url,taxdeed_url,foreclosure_platform,taxdeed_platform,notes",
        "county_slug": "eq.madison",
        "limit": "5",
    })
    log(f"pipeline.counties madison rows: {pipeline_rows}", "VERIFIED")

    # Also try 'counties' table
    county_rows = sb_get("counties", {
        "select": "*",
        "county_slug": "eq.madison",
        "limit": "5",
    })
    log(f"counties table madison rows: {county_rows}", "VERIFIED")

    # Step 4: Probe RealTaxDeed for madison tax deeds
    # Madison County's tax deed platform (if any)
    # Try: realforeclose.com (handles both FC and TD for some counties)
    # Try: Florida's generic realforeclose for county FIPS 37
    td_probes = [
        ("https://madison.realtaxdeed.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW", "madison realtaxdeed preview"),
        ("https://www.realforeclose.com/index.cfm?zaction=COUNTY&Zmethod=DISPLAY&county=Madison", "realforeclose madison"),
        ("https://www.realtaxdeed.com/index.cfm?zaction=COUNTY&Zmethod=DISPLAY&county=Madison", "realtaxdeed madison"),
    ]
    for url, label in td_probes:
        probe_url(url, label)

    # Step 5: Check auction_status for closed cases
    closed_statuses = ["sold", "redeemed", "completed", "cancelled", "canceled"]
    closed = [a for a in auctions if a.get("auction_status") in closed_statuses]
    log(f"Closed madison auctions: {len(closed)}", "VERIFIED")
    for a in closed:
        log(f"  CLOSED: {a.get('case_number')} | status={a.get('auction_status')} | date={a.get('auction_date')}", "VERIFIED")

    # Step 6: Summary of blockers
    log("\n=== BLOCKER ANALYSIS ===", "INFO")
    log("A criterion: td=0 — no tax deed auctions in DB for madison. To fix: ", "INFO")
    log("  (a) Find Madison County's tax deed auction platform", "INFO")
    log("  (b) Ingest tax deed cases to multi_county_auctions with auction_type='tax_deed'", "INFO")
    log("B criterion: verified=0 — no outcomes in foreclosure_outcomes for madison", "INFO")
    log("F criterion: tier1_sold=0 — same root cause as B", "INFO")
    log("Both B/F require closed auction outcomes with independent data_source", "INFO")
    log("Madison's foreclosure earliest date was 2026-07-14 — may have closed by now", "INFO")

    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n### PROBE COMPLETE\nTimestamp UTC: {now_iso}")
    print(f"madison auctions: {len(auctions)} (closed: {len(closed)})")
    print(f"BASELINE: {json.dumps({k: baseline.get(k) for k in ['A','B','F']})}")
    print("See log above for platform probe results")


if __name__ == "__main__":
    main()
