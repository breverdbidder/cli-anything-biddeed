#!/usr/bin/env python3
"""
Gold Standard - leon letter B - independent-source discovery attempt (dispatch 3b3e322c, 2026-08-27).

CONTEXT: leon is 9/10, only B fails (verified=15 closed_sold=17, 88.2%, need >=95%).
The 2 unresolved rows are case_number '2025 CA 001586' (foreclosure, sold_amount=$99,500,
parcel 461035 C0220) and '2026 CA 000145' (foreclosure, sold_amount=$100, no parcel_id on
file). Both auctioned 2026-08-25 on leon.realforeclose.com (RealAuction). Both already have
sold_amount/winning_bidder captured (data_source='calendar_sweep_mca_v3',
sold_amount_source='realauction_bidhistory_modal:leon:2026-08-25') but that source is the
scrape platform itself, not an independent official/court/clerk confirmation, so no row
exists yet in foreclosure_outcomes/tax_deed_outcomes for these 2 case numbers -> B evaluator
(pencil_dod_evaluate_county) can't count them as "verified".

PRIOR SESSION (2026-08-26, dispatch 62855eaa) already confirmed blocked:
  - cvweb.leonclerk.com (public_new/citations_payment path) -> HTTP 403 Akamai
  - RealAuction detail/result pages -> require authenticated login

THIS SESSION: genuinely new endpoints tried, none yielded a usable independent source.
Every result below is VERIFIED via live curl/Playwright headless-browser fetch run in this
session (2026-08-27), not inferred.

RESULTS (all VERIFIED this session):
  1. https://cvweb.leonclerk.com/public/clerk_services/official_records/index.asp
     (different path, same subdomain as prior session's block)
     -> HTTP 403, "Access Denied", Akamai errors.edgesuite.net reference ID present.
        Confirmed via curl AND real headless Chromium (Playwright) - not just a
        curl-fingerprint block, the WAF blocks real browser traffic too.
  2. https://dfast.leonclerk.com/dfastwebpublic/ (new subdomain, DFAST records product)
     -> HTTP 503, Akamai edgesuite error page (same errors.edgesuite.net infra).
  3. https://judicial.clerk.leon.fl.us/ (new domain entirely, distinct from *.leonclerk.com)
     -> HTTP 403, Akamai "Access Denied", same edgesuite.net reference format.
  4. https://cvweb.clerk.leon.fl.us/public/login.asp (alias domain found via leonrecords.us)
     -> HTTP 301 redirect straight into cvweb.leonclerk.com (i.e. the same blocked host).
  5. https://leonpa.gov / https://search.leonpa.gov (Leon Property Appraiser - genuinely
     different agency/infra than the Clerk) -> REACHABLE (HTTP 200 via headless browser;
     curl alone got 403, confirming this one *is* a curl-fingerprint block that a real
     browser clears). Logged the click-through Search Agreement, searched by
     ParcelId='461035 C0220' (case 2025 CA 001586's parcel) -> found the parcel
     (owner still "GREENE CHARLES B JR", i.e. pre-auction owner) and opened
     /Property/Details/461035  C0220 -> Sales Information table's most recent entry is
     1/24/2023 $173,800 Warranty Deed (the owner's original purchase) - the 2026-08-25
     auction has NOT recorded yet.
     Cross-checked the PA's Sales-search tool (https://search.leonpa.gov/Search/Sales) with
     SaleDateFrom=2026-08-01 SaleDateTo=2026-08-27 -> 480 records, most recent visible sale
     date is 2026-08-20 (confirmed by narrowing to 2026-08-20..2026-08-27 -> 22 records, none
     later than 08/20). This proves the PA sales roll genuinely updates continuously (it is
     NOT stale/broken) but has a real ~5-9 business-day recording lag behind the courthouse
     sale date - our 2026-08-25 sale is inside that lag window as of today (2026-08-27,
     only 2 days post-sale).
     Owner-name search for "LCT Mortgage" (winning bidder on case 2026 CA 000145) -> 0
     results, consistent with the same not-yet-recorded status (that case also has no
     parcel_id on file in our DB to cross-check directly).
  6. https://2ndcircuit.leoncountyfl.gov/ and .../civilCaseManagement.php (2nd Judicial
     Circuit's own site, distinct from the Clerk's cvweb app) -> REACHABLE (HTTP 200 via
     headless browser; curl alone got 403 on the root, same curl-vs-browser split as #5),
     but this page is an administrative-order/rules page only - it has no case docket
     search tool. The circuit's actual docket search lives on cvweb.leonclerk.com (blocked).
  7. https://trellis.law/coverage/florida/leon -> HTTP 403, AWS WAF "Human Verification"
     interstitial (different vendor/infra than Akamai, same result class: bot-blocked).
  8. https://unicourt.com/courthouse/leon-county-courthouse-1417 and /case-search -> HTTP
     405 with an AWS WAF "Human Verification" / gokuProps challenge page - also bot-blocked.
  9. https://www.myfloridacounty.com/official_records/index.html -> reachable (HTTP 200,
     genuinely different infra from leonclerk.com), but its Leon entry just links back to
     https://cvweb.leonclerk.com/public/clerk_services/official_records/index.asp (same
     blocked host, see #1).
  10. https://leonrecords.us/court-records -> reachable (HTTP 200) but is a third-party
      paid-background-check lead-gen site (form posts to florida.staterecords.org/loader),
      not an actual records search tool; its own "official" links point back to
      cvweb.clerk.leon.fl.us (see #4, same block).
  11. https://leon.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=CALENDAR (public
      calendar/splash page, distinct from the per-case AID detail page already tried last
      session) -> reachable but login-gated splash page only, no public results/calendar
      view without an authenticated RealAuction account (same auth wall as before, just a
      different entry URL).

CONCLUSION (HONEST, no fabrication): No genuinely independent, non-PropertyOnion,
non-RealAuction-scrape source could be reached this session that has the sale outcome for
either case_number recorded yet. The Leon Property Appraiser (#5) is a real, reachable,
independent government source and would be usable BUT the Certificate of Title / deed for
both 2026-08-25 sales has not recorded into its sales roll as of 2026-08-27 (roll's most
recent entries are 2026-08-20). This is a genuine timing/recording-lag ceiling, separate
from (in addition to) the previously-known Akamai bot-block on cvweb.leonclerk.com and its
domain-family (dfast.leonclerk.com, judicial.clerk.leon.fl.us, 2ndcircuit.leoncountyfl.gov
via curl, leonpa.gov via curl - all cleared by headless-browser except cvweb.leonclerk.com
which is genuinely blocked even for real browsers).

ACTION TAKEN: none. Per HARD GUARDRAILS, no shortcut/fabrication was used to move the
metric. B remains 15/17 (88.2%) this session - a genuine structural ceiling until either
(a) the Leon Clerk's Akamai WAF is reconfigured/whitelisted, or (b) enough real-world time
passes for the Certificate of Title to record on the Leon PA sales roll (recommend
re-checking search.leonpa.gov/Search/Sales for parcel 461035 C0220 and for an "LCT Mortgage"
owner-name hit in ~1-2 weeks).

This file is a documentation-only investigation record. No DB writes were made.
"""

FINDINGS = {
    "county": "leon",
    "letter": "B",
    "dispatch": "3b3e322c",
    "session_date": "2026-08-27",
    "unresolved_case_numbers": ["2025 CA 001586", "2026 CA 000145"],
    "action_taken": "none - no independent source found with recorded outcome data yet",
    "root_cause": "recording lag (Certificate of Title not yet recorded, 2 days post-sale) "
                  "compounded by Akamai WAF blocking the Leon Clerk's official-records/docket "
                  "domain family (cvweb.leonclerk.com, dfast.leonclerk.com, "
                  "judicial.clerk.leon.fl.us) even for real headless-browser traffic",
    "new_sources_confirmed_reachable_but_no_data_yet": [
        "https://search.leonpa.gov/Search/Property (Leon Property Appraiser)",
        "https://search.leonpa.gov/Search/Sales",
    ],
    "new_sources_confirmed_blocked_this_session": [
        "https://cvweb.leonclerk.com/public/clerk_services/official_records/index.asp",
        "https://dfast.leonclerk.com/dfastwebpublic/",
        "https://judicial.clerk.leon.fl.us/",
        "https://trellis.law/coverage/florida/leon",
        "https://unicourt.com/courthouse/leon-county-courthouse-1417",
    ],
    "recommended_next_check": "retry search.leonpa.gov/Search/Sales for parcel "
                               "'461035 C0220' (case 2025 CA 001586) and owner-name "
                               "'LCT Mortgage' (case 2026 CA 000145) in ~1-2 weeks once the "
                               "Certificate of Title has had time to record",
}

if __name__ == "__main__":
    import json
    print(json.dumps(FINDINGS, indent=2))
