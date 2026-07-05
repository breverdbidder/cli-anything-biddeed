#!/usr/bin/env python3
"""
Wakulla RealTDM Exhaustive Probe (2026-07-05)
==============================================
Session goal: wakulla was 1/10 (auctions_total=0, a prior fabricated-ghost-success
row set having been correctly purged in 20260703_shard_wakulla_cd_ghost_success_purge_and_refresh.sql
and 20260704_shard4_desoto_wakulla_ghost_success_revert.sql). This script documents
the live-verified attempt to source GENUINE multi_county_auctions rows for wakulla
before concluding the county has zero real inventory to ingest.

Endpoints probed (all with a real desktop browser User-Agent):

1. https://wakulla.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR
   -> HTTP 302 -> http://www.realauction.com (generic marketing homepage).
   No active foreclosure lane. CONFIRMED dead end.

2. https://wakulla.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR
   -> HTTP 302 -> http://www.realauction.com (generic marketing homepage).
   Not the live tax-deed lane for wakulla. CONFIRMED dead end.

3. https://wakulla.realtdm.com/index.cfm?zaction=USER&zmethod=CALENDAR
   -> HTTP 200, 5784 bytes, but this is a *login splash page* (username/password
   form), not a calendar -- no case data present regardless of auth state for
   this zaction/zmethod pair.

4. https://wakulla.realtdm.com/public/cases/List (discovered via
   realauction_subdomains.final_url from a prior session's DNS/HTTP validation
   pass) -> HTTP 200, 19047 bytes. This IS a real "Public Case Search" form
   (Case Status / Party Name / Case Number / Parcel Number / Application Number
   / Certificate Number / Property Address / Sale Date Range filters), submitted
   via a plain HTML form POST (see submitCaseFilters() in includes/javascript/public/public.js)
   to https://wakulla.realtdm.com/public/cases/list.

   This script issues that POST exhaustively:
     - ALL 20 case-status codes selected at once (Active, Active-Sold,
       Active-SoldBidder, Active-SoldApplicant, Active-BidderDefaulted,
       Active-ApplicantDefaulted, Active-Redemption, Active-Resale(4Adv),
       Active-Resale30Day(1Adv), Canceled, Canceled-PerCounty,
       Canceled-PerOrder, Canceled-PerBankruptcy, Canceled-Reschedule,
       ListOfLands, Completed, Completed-Redeemed, Completed-Purchased,
       Completed-SoldApplicant, Completed-SoldBidder)
     - sale date range 2000-01-01 .. 2027-12-31 (super-set of any real window)
     - wildcard property-address filter ("a")

   RESULT (every variant): server returns "NO CASES FOUND" (a real, different
   message than the "NO CASE FILTERS SELECTED" validation error shown when no
   filter is supplied at all -- proving the POST reached and was processed by
   the real search backend, not just re-rendering the empty form).

CONCLUSION: Wakulla's RealTDM tenant currently has ZERO case records exposed to
this public search endpoint. The tenant splash header displays "TEST" / "Test
Clerk" rather than "Wakulla" -- consistent with a provisioned-but-not-yet-
populated Clerk tenant, not a scraper defect on our side.

HONESTY: No multi_county_auctions rows were written by this script. Per HARD
RULES, BLANK > WRONG -- inserting placeholder/fabricated rows to hit a number
is explicitly banned. This script is left as a reusable live-probe utility for
a future session to re-run (e.g. monthly) to detect the moment Wakulla's Clerk
populates real cases, at which point build_rows()/insert-to-MCA logic from
scripts/shard5_bradford_wakulla_bootstrap.py should be reused to ingest them.

Usage:
    python3 scripts/shard_wakulla_realtdm_exhaustive_probe.py
Exits 0 with a summary either way; never writes to Supabase (probe-only).
"""
import sys
import urllib.request
import urllib.parse
import http.cookiejar

UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

BASE = "https://wakulla.realtdm.com"
LIST_PAGE = f"{BASE}/public/cases/List"
SEARCH_URL = f"{BASE}/public/cases/list"

ALL_STATUS_CODES = [
    "122", "128", "130", "129", "124", "123", "126", "442", "441",  # Active family
    "131", "134", "135", "132", "136",                              # Canceled family
    "143",                                                          # List of Lands
    "137", "140", "139", "141", "142",                              # Completed family
]

DEAD_END_REDIRECTS = [
    ("foreclosure", "https://wakulla.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR"),
    ("tax_deed", "https://wakulla.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR"),
]


def fetch(url, cj, method="GET", data=None, referer=None):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    headers = {"User-Agent": UA_DESKTOP}
    if referer:
        headers["Referer"] = referer
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def check_dead_end_redirects():
    print("\n=== Step 1: confirm realforeclose/realtaxdeed dead-end redirects ===")
    for sale_type, url in DEAD_END_REDIRECTS:
        cj = http.cookiejar.CookieJar()
        req = urllib.request.Request(url, headers={"User-Agent": UA_DESKTOP})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                final_url = resp.geturl()
                print(f"  [{sale_type}] final_url={final_url} status={resp.status}")
        except urllib.error.HTTPError as e:
            print(f"  [{sale_type}] HTTPError {e.code} -- {e.reason}")


def exhaustive_case_search():
    print("\n=== Step 2: exhaustive RealTDM public case search (wakulla) ===")
    cj = http.cookiejar.CookieJar()
    status, _ = fetch(LIST_PAGE, cj)
    print(f"  GET {LIST_PAGE} -> {status}")

    variants = [
        ("all_statuses_no_dates", {
            "filterPageNumber": "1", "filterFiltered": "1", "sectionRouteCode": "",
            "isPublic": "1", "filtercasestatus": ",".join(ALL_STATUS_CODES),
            "filterPartyName": "", "filterCaseNumber": "", "filterParcelNumber": "",
            "filterAppNumber": "", "filterCertNumber": "", "filterPropAddress": "",
            "filterSaleDateStart": "", "filterSaleDateStop": "",
            "filterCasesPerPage": "100",
        }),
        ("all_statuses_wide_date_range", {
            "filterPageNumber": "1", "filterFiltered": "1", "sectionRouteCode": "",
            "isPublic": "1", "filtercasestatus": ",".join(ALL_STATUS_CODES),
            "filterPartyName": "", "filterCaseNumber": "", "filterParcelNumber": "",
            "filterAppNumber": "", "filterCertNumber": "", "filterPropAddress": "",
            "filterSaleDateStart": "01/01/2000", "filterSaleDateStop": "12/31/2027",
            "filterCasesPerPage": "100",
        }),
        ("wildcard_address", {
            "filterPageNumber": "1", "filterFiltered": "1", "sectionRouteCode": "",
            "isPublic": "1", "filtercasestatus": "",
            "filterPartyName": "", "filterCaseNumber": "", "filterParcelNumber": "",
            "filterAppNumber": "", "filterCertNumber": "", "filterPropAddress": "a",
            "filterSaleDateStart": "", "filterSaleDateStop": "",
            "filterCasesPerPage": "100",
        }),
    ]

    results = {}
    for name, payload in variants:
        status, html = fetch(SEARCH_URL, cj, method="POST", data=payload, referer=LIST_PAGE)
        if "NO CASES FOUND" in html:
            outcome = "NO_CASES_FOUND (query reached real backend, zero matches)"
        elif "NO CASE FILTERS SELECTED" in html:
            outcome = "NO_CASE_FILTERS_SELECTED (validation error -- filter not applied!)"
        else:
            outcome = "UNEXPECTED -- real case rows may be present, inspect manually"
        results[name] = outcome
        print(f"  [{name}] HTTP {status} bytes={len(html)} -> {outcome}")

    return results


def main():
    check_dead_end_redirects()
    results = exhaustive_case_search()

    print("\n=== SUMMARY ===")
    all_empty = all("NO_CASES_FOUND" in v for v in results.values())
    if all_empty:
        print("CONFIRMED: Wakulla RealTDM has zero public case records under every")
        print("filter combination tried. No multi_county_auctions rows written --")
        print("BLANK > WRONG. Re-run this script periodically to detect when the")
        print("Clerk populates real inventory.")
        return 0
    else:
        print("UNEXPECTED RESULT -- inspect manually before writing any MCA rows:")
        for k, v in results.items():
            print(f"  {k}: {v}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
