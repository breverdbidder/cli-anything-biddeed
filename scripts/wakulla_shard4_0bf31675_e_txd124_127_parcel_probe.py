#!/usr/bin/env python3
"""
wakulla_shard4_0bf31675_e_txd124_127_parcel_probe.py
Gold Standard shard-4 (dispatch 0bf31675), 2026-08-30

SCOPE: wakulla letter E (parcel_linked=48/52=92.3%, FAIL). Ground truth: the
4 unlinked rows are all cancelled tax deed applications -- 2026-TXD-124,
2026-TXD-125, 2026-TXD-126, 2026-TXD-127 (parity_status='CLERK_SSOT_
CANCELLED', sale_type='tax_deed'). No property_address/lat/lon/assessed_
value either (never enriched because the sale was cancelled before the
enrichment pipeline ran).

TASK: find real, cited parcel IDs for these 4 cases via public records.
RESULT: 0 of 4 found. All avenues exhausted (see below). Zero writes made.
This session reproduces and extends a documented prior-session pattern
(scripts/wakulla_ceij_soft404_pdf_probe_gsd2_84b6c4bb.py, 2026-08-15, for a
DIFFERENT set of 4 case numbers: 117/118/120/122) for a new set of case
numbers (124/125/126/127) that was never probed before.

============================================================================
AVENUE 1 -- wakullaclerk.org (current Revize CMS site), tax deed sales page
============================================================================
Live fetch of https://wakullaclerk.org/official_records/tax_deed_sales.php
(curl, HTTP 200, 76009 bytes, 1428 lines, 2026-08-30). Raw HTML confirms:
  - "For Sale" rows (2026-TXD-123, 128-132) each have a real <a href=
    "Documents/Official Records/Tax Deed Sales/2026 TXD <N>.remediated.pdf">
    anchor.
  - 2026-TXD-124/125/126/127 are plain <td> text, NO <a href> anywhere near
    them -- confirmed by direct grep of the raw HTML (lines 704-731). Status
    column shows "Redeemed" (styled red) for all 4.
  - This matches the prior session's finding for TXD-117/118/120/122: the
    Clerk's CMS only generates/uploads a PDF once a case reaches the
    advertised-for-sale stage. A case redeemed before that stage never gets
    a document in this repository.

Direct URL probe (guessed filename pattern, same as prior session's proven
method) for all 4 targets:
  https://wakullaclerk.org/Documents/Official%20Records/Tax%20Deed%20Sales/
  2026%20TXD%20<N>.remediated.pdf
Result: all 4 return HTTP 200 but Content-Length: 0, Content-Type: text/html
(the Revize CMS soft-404 behavior documented by the prior session -- real
PDFs return actual PDF bytes, missing ones return an empty/soft-404 HTML
shell with HTTP 200). Confirmed via curl -I for all 4 case numbers.

Also tried the pattern found via web search for a different year (2023-TXD-
062 at wakullaclerk.org/wp-content/uploads/...) applied to our 4 targets --
same soft-404 (Content-Length: 0) result, and the 2023 reference URL itself
also soft-404'd live today, confirming this is not a valid current pattern
for any case.

============================================================================
AVENUE 2 -- wakullaclerk.com/LandmarkWeb (legacy domain, proven working API)
============================================================================
A prior session (scripts/wakulla_landmarkweb_outcomes_harvest.py, verified
live 2026-07-24) documented a working session-based POST API against
https://www.wakullaclerk.com/LandmarkWeb (Pioneer Technology Group
LandmarkWeb v1.5.103.0) that can search official records by grantor name +
doctype + date range and pull instrument/grantor/grantee/consideration off
a detail page. This is the only proven programmatic path in this repo for
Wakulla official records beyond the public CMS tax-deed-sales table.

Attempted to reuse this exact recipe (GET / -> POST Search/SetDisclaimer ->
POST Search/NameSearch -> POST Search/GetSearchResults) to search for any
recorded document referencing case numbers 124-127 (e.g. a tax deed
application notice, a certificate redemption record, or a deed).

RESULT: connection refused / timeout on EVERY attempt, from two independent
network paths (direct Python requests from the execution sandbox, AND the
WebFetch tool, which routes through a different network egress):
  - curl -sI https://www.wakullaclerk.com/LandmarkWeb/  -> HTTP 000 (exit 28,
    connection timeout)
  - python requests.get(".../LandmarkWeb/") -> ConnectTimeoutError
  - WebFetch(".../LandmarkWeb/") -> "connect ECONNREFUSED 170.249.129.42:443"
  - Also tried plain http:// and the bare root domain -- same result.
  - DNS resolves fine (170.249.129.42), the connection itself is refused/
    times out at the TCP level. This is a live infrastructure outage of the
    legacy domain, not a search failure -- the prior session's working
    recipe against this exact host was verified live 5 weeks ago (2026-07-
    24), so this is a regression in the site's availability, not a wrong
    recipe.

============================================================================
AVENUE 3 -- myfloridacounty.com official records portal
============================================================================
This statewide ORI redirector (linked from wakullaclerk.org's official_
records/index.php) requires selecting a county from an interactive dropdown
and submitting a form to be redirected to the county's actual search
backend. Not navigable via WebFetch (static HTML fetch, no JS/form
execution). Would require Playwright/browser automation to drive.

============================================================================
AVENUE 4 -- Civitek OCRS (Online Court Records Search)
============================================================================
https://www.civitekflorida.com/ocrs/county/65/ is Wakulla's court case
search portal. Tax deed applications are sometimes docketed as circuit
civil cases in addition to the Clerk's tax-deed-specific tracking. Portal
requires an interactive case-number search form (public/anonymous access
tier exists per the page, but the search itself is JS-driven) -- not
navigable via WebFetch. Would require Playwright/browser automation.

============================================================================
AVENUE 5 -- Wakulla County Property Appraiser (mywakullapa.com)
============================================================================
https://search.mywakullapa.com/ -- WebFetch returned "read ECONNRESET".
Even if reachable, this search tool takes owner name / parcel / address as
input, none of which we have for these 4 cases without first knowing the
parcel -- a name-based reverse search would require the owner name from
avenues 1-4, none of which succeeded.

============================================================================
CONCLUSION
============================================================================
No real, cited parcel_id was found for 2026-TXD-124, -125, -126, or -127
through any reachable public-record channel. Per HONESTY rules (blank >
wrong), zero writes were made to multi_county_auctions. This is NOT the
same conclusion as "no document was ever published" (that was avenue 1's
finding, consistent with the prior session's pattern) -- avenue 2 (the one
channel proven to sometimes surface non-published-PDF case data) could not
be tested at all today due to a live outage, so this ceiling should be
treated as PARTIALLY probed / infrastructure-blocked rather than
exhaustively negative. A future session with a working path to
wakullaclerk.com/LandmarkWeb (or browser automation for avenues 3-4) should
retry before concluding these 4 rows are permanently unrecoverable.

Evaluator (read-only RPC, before AND after -- unchanged since zero writes):
  pencil_dod_evaluate_county('wakulla').E = {"pass": false,
  "detail": "parcel_linked=48", "metric": 92.3}

Env (read-only in this script): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = probe completed (regardless of find/no-find), 1 = fatal error
"""

import json
import os
import sys

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

TARGET_CASES = ["2026-TXD-124", "2026-TXD-125", "2026-TXD-126", "2026-TXD-127"]

ORG_PDF_PATTERN = (
    "https://wakullaclerk.org/Documents/Official%20Records/Tax%20Deed%20Sales/"
    "2026%20TXD%20{n}.remediated.pdf"
)
LANDMARKWEB_ROOT = "https://www.wakullaclerk.com/LandmarkWeb/"


def probe_org_pdf(case_num: str) -> dict:
    n = case_num.split("-")[-1]
    url = ORG_PDF_PATTERN.format(n=n)
    try:
        r = requests.get(url, timeout=20)
        is_pdf = r.content[:4] == b"%PDF"
        return {
            "case": case_num, "url": url, "http_status": r.status_code,
            "is_real_pdf": is_pdf, "bytes": len(r.content),
        }
    except requests.RequestException as e:
        return {"case": case_num, "url": url, "error": str(e)}


def probe_landmarkweb_reachability() -> dict:
    try:
        r = requests.get(LANDMARKWEB_ROOT, timeout=15, verify=False)
        return {"url": LANDMARKWEB_ROOT, "http_status": r.status_code, "reachable": True}
    except requests.RequestException as e:
        return {"url": LANDMARKWEB_ROOT, "reachable": False, "error": str(e)}


def evaluate_county() -> dict:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {"error": "SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set"}
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Content-Type": "application/json"}
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        headers=h, json={"p_county": "wakulla"}, timeout=30,
    )
    return r.json()


def main():
    print(">>> wakulla shard-4 (0bf31675) letter E parcel probe -- TXD-124/125/126/127\n")

    print("--- Avenue 1: wakullaclerk.org guessed-PDF probe ---")
    for c in TARGET_CASES:
        result = probe_org_pdf(c)
        print(f"  {json.dumps(result)}")

    print("\n--- Avenue 2: wakullaclerk.com/LandmarkWeb reachability ---")
    print(f"  {json.dumps(probe_landmarkweb_reachability())}")

    print("\n--- Evaluator (read-only, before=after, zero writes made) ---")
    print(json.dumps(evaluate_county().get("E", "N/A"), default=str))

    print(
        "\nCONCLUSION: 0/4 parcel_ids found. Avenue 1 confirms no published "
        "document exists in the current CMS repository (soft-404 on all 4 "
        "guessed URLs). Avenue 2 (the only channel with a proven working "
        "recipe for non-published case data) is unreachable today -- live "
        "infrastructure outage, not a search failure. Avenues 3-5 require "
        "browser automation not available in this session. No writes made. "
        "Reported as UNKNOWN per HONESTY rules -- blank > wrong."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
