#!/usr/bin/env python3
"""
Holmes C/D/B/F Residual Investigation (GOLD-STANDARD shard6, dispatch 95f77ed6, 2026-07-18)
==============================================================================================
THIRD consecutive session on this exact gap (after shard12/run3534 2026-07-10 and shard9/
ddbb047c 2026-07-10). Baseline unchanged across all three: 6/10, B/C/D/F failing.
  B: verified=0 closed_sold=0
  C: matched_clean=8 of 13 (61.5%)
  D: matched_any=8 of 13 (61.5%)
  F: tier1_sold=0 closed_sold=0
The 5 unmatched TD# cases are IDENTICAL across all three sessions:
  TD#2020-589, TD#2023-185, TD#2023-225, TD#2023-496, TD#2023-584 (all auction_status='upcoming')

THIS SESSION'S NEW ATTEMPTS (not tried in either prior session):

1. Firecrawl (map + scrape) against holmesclerk.com, myfloridacounty.com/orisearch/30, and
   qpublic.net/holmes -- BLOCKED. Both /v1/map and /v1/scrape return:
     {"success": false, "error": "Insufficient credits to perform this request. ..."}
   The FIRECRAWL_API_KEY env var is set (fc-fa11295...) but the account has zero remaining
   credits. This closes off the JS-rendering avenue the brief specifically flagged as new
   for this session.

2. Fresh plain-HTTP re-scrape of holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/
   (2026-07-18, page self-reports "Updated 7/17/2026" -- genuinely current, not the 8-day-
   stale copy). Live page shows exactly 4 cases: TD#2023-330, TD#2023-509, TD#2020-349,
   TD#2024-185 -- all 4 already parity_status='matched_clean' in our DB. The 5 target cases
   plus TD#2023-753 (which WAS matched previously) have rolled off entirely. Confirms the
   run3534 finding still holds 8 days later -- not a stale-scrape artifact.

3. Holmes County Official Records Index Search (myfloridacounty.com/orisearch/30) --
   genuinely new source, discovered via a footer link on holmesclerk.com homepage
   ("https://www.myfloridacounty.com/orisearch/30"). This is a real per-instrument
   recording index (deeds, certificates, liens, judgments) that in principle could carry a
   recorded Tax Deed / Certificate of Title with a grantee + consideration amount. BLOCKED:
   any POST to the search action returns "Please verify you are human" -- a bot/CAPTCHA
   challenge that plain requests/curl cannot pass. Would require a real interactive browser
   session (Firecrawl-browser or Playwright) which is out of scope given zero Firecrawl
   credits this session.

4. Holmes County Tax Collector (holmescountytaxcollector.com) -- genuinely new source,
   NOT gated by Cloudflare or CAPTCHA (plain POST to /Property/search works). Queried by
   propertynumber (parcel_id) for all 5 target cases, using parcel_id + plaintiff/owner name
   already present in our own multi_county_auctions rows (captured 2026-06-19 bootstrap,
   before these cases rolled off the clerk site). All 5 parcels resolved successfully,
   each returning 11 tax-bill rows (tax years 2015-2025). Key finding: ALL 5 parcels show
   STATUS='TD' (tax deed application) for tax year 2025, the most recent roll year --
   i.e. still in active/pending tax-deed-application status, NOT 'PD' (paid), 'CC'
   (cancelled), 'RD' (redeemed) or any other code that would indicate resolution.
   This is CONSISTENT WITH the DB's existing auction_status='upcoming', but it is a roll
   status code, not an auction-disposition record -- it carries no sale date, no winning
   bidder, no consideration amount, and cannot be used as a tier1 parity match or a B/F
   sold_amount source. The /Property/TaxBill AJAX detail endpoint (which might carry more
   fields) returned "The service was not able to retrieve information" when queried
   directly via curl -- it likely requires additional session state set by client-side JS
   that a plain POST does not reproduce. Did not pursue further given session budget.

CONCLUSION (honest, no DB write made this session): the C/D gap for holmes remains a
genuine source-coverage gap, not a matcher bug -- confirmed for a 3rd time with 3 new,
previously-untried avenues (Firecrawl, Official Records index, Tax Collector roll lookup),
all of which either failed structurally (Firecrawl: no credits; Official Records: CAPTCHA)
or returned data that is real but insufficient to satisfy the evaluator's tier1 parity /
sold_amount bar (Tax Collector: roll status only, no disposition/dollar field).

RECOMMENDATION for the next session (do not repeat any of the above 4 attempts as if new):
  - The Official Records CAPTCHA is the single most promising remaining lead (it is a real
    recording index that could carry actual Tax Deed / Certificate of Title recordings with
    dollar amounts) but requires either (a) Firecrawl credits topped up, or (b) a genuine
    Playwright/browser-use session capable of passing myfloridacounty.com's human challenge.
  - Do NOT re-attempt plain curl/requests against myfloridacounty.com/orisearch/30 -- this
    is now confirmed CAPTCHA-gated, not a UA/header issue.
  - Do NOT re-attempt Firecrawl until FIRECRAWL_API_KEY has confirmed available credits
    (test with a trivial /v1/scrape call first before spending session time on it).
  - The Tax Collector roll STATUS codes (CC/TD/CI/BL) are not yet decoded against an
    official legend; if a legend can be found (e.g. via the Collector's help page or a
    phone call script), 'TD' persisting into a later year than the case's origin year might
    become a soft signal worth surfacing to a human reviewer, but it is NOT sufficient on
    its own for automated tier1 matched_clean / sold_amount writes.

No writes were made to multi_county_auctions, tax_deed_outcomes, or foreclosure_outcomes
this session -- fail-loud, no fabrication, per campaign brief.

Env used (read-only checks only): FIRECRAWL_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit: this is a documentation/evidence script, not an executable pipeline. No main().
"""

SESSION_META = {
    "dispatch_id": "95f77ed6-fc70-4c15-9db4-b9b64bef5d1c",
    "date": "2026-07-18",
    "county": "holmes",
    "prior_sessions_on_same_gap": [
        "shard12/run3534 (2026-07-10)",
        "shard9/ddbb047c (2026-07-10)",
    ],
    "unmatched_case_numbers": [
        "TD#2020-589", "TD#2023-185", "TD#2023-225", "TD#2023-496", "TD#2023-584",
    ],
    "new_avenues_tried_this_session": [
        "firecrawl_map_and_scrape (blocked: zero credits)",
        "myfloridacounty.com/orisearch/30 official records index (blocked: CAPTCHA)",
        "holmescountytaxcollector.com Property/search by parcel_id (succeeded, but roll "
        "status only -- no disposition/dollar field)",
        "qpublic.net/holmes property appraiser (blocked: Cloudflare JS challenge, 403)",
    ],
    "letters_moved": [],
    "writes_made": False,
}

if __name__ == "__main__":
    import json
    print(json.dumps(SESSION_META, indent=2))
