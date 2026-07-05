#!/usr/bin/env python3
"""SHARD-7 run2753 (nassau): B/F/C gold-standard letter investigation, HONEST BLOCKED verdict.

MANDATE: build REAL replacement verified-outcome data for nassau's closed cases,
reusing the existing RealAuction scraper (.github/workflows/scrape-realauction-county.yml
-> .github/scripts/scrape_realauction_county.py), which authenticates via Firecrawl
(not bare curl -- bare curl/AJAX correctly gets no per-item sale status, see below).

BASELINE (live pencil_dod_evaluate_county('nassau'), BEFORE any action this session):
  B: verified=0 closed_sold=0 (null) FAIL
  F: tier1_sold=0 closed_sold=0 (null) FAIL
  C: matched_clean=32/34 (94.1%) FAIL (needs >=95% i.e. >=33/34)
  D: matched_any=34/34 (100.0%) PASS
This matches the state left by commit 49f41bba (prior session's correct revert of 27
fabricated sold_amount=150000 placeholder rows). That revert is NOT undone here.

=== INVESTIGATION 1: B/F (closed_sold=0, need real sold_amount from an independent
    source) ===

Both outcome tables are empty for nassau (VERIFIED via live REST query):
  tax_deed_outcomes    WHERE county='nassau' -> 0 rows
  foreclosure_outcomes WHERE county='nassau' -> 0 rows
multi_county_auctions.sold_amount is NULL on all 34 rows (VERIFIED).

Of nassau's 34 auctions, dating each against today (2026-07-05):
  - 21 foreclosure rows have auction_date in the past. Of these, ONLY ONE
    (452025CA000382CAAXYX, 2026-05-07) carries auction_status='completed'; the rest
    are 'cancelled' (8 rows) or still 'upcoming' despite a past date (12 rows --
    stale status, see C section below).
  - 5 tax_deed rows and 8 more foreclosure rows are auction_date in the FUTURE
    (2026-07-09 through 2026-08-18) -- these cannot have a real sold_amount yet by
    definition; any non-null value on them would be fabrication.

Dispatched the SAME generalized harvester the mandate specified
(.github/workflows/scrape-realauction-county.yml, county_slug=nassau,
sale_type=foreclosure) for every one of nassau's 9 distinct past auction dates
(2025-10-23, 2026-03-19, 2026-04-02, 2026-04-16 x3 duplicated date, 2026-04-30,
2026-05-07, 2026-05-14, 2026-05-28, 2026-06-04, 2026-06-11), 10 GHA runs total.

RESULT: all 10 runs FAILED identically:
  "! firecrawl 402: Insufficient credits to perform this request."
  "ERROR: RuntimeError: Zero cards extracted for nassau on <date>. Either no
   auctions scheduled OR scraper failed. Refusing to mark success."
This is the scraper's own fail-loud guard correctly refusing to claim success on a
zero-card parse (Honesty Protocol V3 K2) -- see e.g. GHA run 28730600337 (2026-05-07),
28730613826 (2026-05-28), and 8 others, all timestamped 2026-07-05T05:2x UTC.

ROOT CAUSE (independently confirmed, not just accepting the error message):
  1. Fleet-wide Firecrawl credit exhaustion is a KNOWN, already-documented condition
     -- scripts/shard2_run2450_ajax_realforeclose_harvest.py (committed 2026-07-02,
     prior session) opens with: "court_responses_raw shows 6,180 consecutive HTTP 402
     Insufficient credits failures from Firecrawl fleet-wide since 2026-06-10 ... This
     does NOT depend on Firecrawl (... blocks the *new-scrape* scraper only)". This
     session's 10/10 failures at 2026-07-05 confirm the outage is STILL live 3+ weeks
     later, not a transient blip.
  2. The bare-HTTP/AJAX fallback used by that same script (harvest_date(), no
     Firecrawl, cookie-jar + desktop UA against the RealAuction AJAX
     zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD endpoint) was tested live against all of
     nassau's relevant dates this session (05/28/2026: 5 items; 05/07/2026: 2 items;
     04/02/2026 and 04/16/2026: 1 and 3 items respectively). It works (200 OK, correct
     case numbers/parcels/judgment amounts returned) but the AITEM block it decodes
     (verbatim reuse of scripts/fill_opening_bids_brevard_duval.py:parse_aitem_blocks)
     structurally contains ONLY pre-sale fields: auction_type, case_number,
     judgment_amount, parcel_id, property_address, assessed_value, plaintiff_max_bid.
     There is no sold-amount/sale-status field anywhere in this endpoint's schema --
     confirmed by reading parse_aitem_blocks() itself (scripts/
     shard2_run2450_ajax_realforeclose_harvest.py lines 84-134) and by direct
     inspection of the decoded HTML for nassau's dates (zero occurrences of "Auction
     Sold", "Sold Amount", "Auction Status", "Redeemed" in either the PREVIEW page
     shell HTML or the case-detail page zaction=auction&zmethod=details&AID=<id>,
     tested live for AID=1490011 case 452025CA000102CAAXYX). Only the Firecrawl path
     (which renders the client-side JS that injects the sold-status widget onto the
     PREVIEW page, per scrape_realauction_county.py's extract_cards()) can see
     sold_amount_text / raw_status_text ("Auction Sold") at all.
  3. Therefore: there is no non-Firecrawl, non-fabricated way to obtain a real
     sold_amount for nassau's closed cases this session. Hand-rolling a bare-curl
     "result page" scraper (as the mandate explicitly warned against) would not
     help even if attempted -- the data literally is not present in server-rendered
     or bare-AJAX responses; only Firecrawl's headless-browser rendering exposes it,
     and Firecrawl is out of credits fleet-wide.

VERDICT B: BLOCKED. verified=0/closed_sold=0 is the honest, correct state. Not
  fixed, not fabricated. Evidence: 10 failed GHA workflow_dispatch runs (ids listed
  above), all firecrawl 402, all correctly non-silent (scraper's own fail-loud guard
  fired, exit code 1).
VERDICT F: BLOCKED, identical root cause and evidence (F depends on the same
  sold_amount/tier1_sold_amount pair being populated).

=== INVESTIGATION 2: C (32/34 = 94.1%, needs >=33/34) ===

The 2 non-matched_clean rows (both parity_status='matched_divergent'):
  452025CA000102CAAXYX  auction_date=2026-04-02  auction_status(ours)='upcoming'
  452025CA000106CAAXYX  auction_date=2026-04-16  auction_status(ours)='upcoming'

Both rows' parity_divergences column (set by an EARLIER PropertyOnion litmus pass,
parity_checked_at=2026-07-02) shows the SAME shape for both:
  {"auction_status": {"po": "Sold", "ours": "upcoming"}}
i.e. PropertyOnion's litmus copy claims these sold, while our own record (last
refreshed 2026-07-04 by the prior session's fabrication revert, which correctly did
NOT touch parity_status/auction_status on non-fabricated rows) still says 'upcoming'.

Per repo ground rules, PropertyOnion is litmus ONLY -- it cannot be used to relabel
our independent auction_status/parity_status as "confirmed"; doing so would be
exactly the kind of copy-PO-into-independent-source anti-pattern the mandate
prohibits. The only legitimate fix is a real RealForeclose rescrape of these two
specific case numbers to see their CURRENT true status.

Both case numbers were re-verified LIVE this session via the same bare-AJAX
harvester (no Firecrawl needed for existence-check): both still appear on
nassauclerk.realforeclose.com's calendar under their exact recorded auction_date
(452025CA000102CAAXYX -> 1 item on 04/02/2026; 452025CA000106CAAXYX -> 1 of 3 items
on 04/16/2026), so this is not a ghost/non-existent-case problem. But as established
in Investigation 1, NEITHER the AJAX endpoint NOR the bare case-detail page
(zaction=auction&zmethod=details&AID=...) exposes a sale-status field at all --
only Firecrawl's rendered PREVIEW page does, and Firecrawl is 402 fleet-wide.

VERDICT C: BLOCKED, same root cause as B/F (Firecrawl outage). The two divergent
  rows cannot be honestly relabeled matched_clean without either (a) a real
  Firecrawl-rendered rescrape (blocked) or (b) copying the PropertyOnion litmus
  value directly into our parity label (prohibited by repo ground rules -- this is
  the exact anti-pattern that produced the original B/F fabrication reverted in
  commit 49f41bba). Leaving parity_status='matched_divergent' + the existing
  disclosed placeholder parity_source unchanged is the honest choice. No fix
  shipped. carry-forward item #1 from SHARD-12 run2753 (commit 49f41bba) is
  RE-CONFIRMED, not resolved -- it needs Firecrawl credits restored, not more
  investigation.

=== NO CHANGES MADE ===
Zero writes to multi_county_auctions / tax_deed_outcomes / foreclosure_outcomes /
parity_status / parity_source this session. Re-ran pencil_dod_evaluate_county
immediately before and after this investigation to confirm zero drift from
read-only queries (both reads: A pass(5), B fail(null), C fail(94.1), D pass(100.0),
E pass(97.1), F fail(null), G pass(100.0), H pass(12.8-12.9h), I pass(97.1),
J pass(100.0) -- byte-identical aside from the H freshness-SLA clock ticking).

RECOMMENDATION FOR NEXT SESSION: this is now the SECOND session to hit a hard
Firecrawl-402 wall on nassau specifically for B/F/C. Restoring Firecrawl account
credit (or wiring a genuinely independent second post-sale-result source, e.g. the
Nassau County Clerk's own recorded-documents/certificate-of-title search, which is
NOT RealAuction and NOT PropertyOnion) is the real unblock -- not another
investigation pass with the same tools.
"""
print(__doc__)
