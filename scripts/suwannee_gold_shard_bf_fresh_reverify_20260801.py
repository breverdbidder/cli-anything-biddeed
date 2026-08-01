#!/usr/bin/env python3
"""Suwannee County B/F FRESH VERIFICATION (2026-08-01, GOLD-SHARD4 session).

Not a rebuild -- suwannee has grown from 14 auctions (last SHARD-12 session,
2026-07-25) to 35 auctions today (4 foreclosure, 31 tax deed). This script
re-runs the established probing pattern from
scripts/suwannee_outcome_harvester.py and
scripts/shard11_run3679_suwannee_bf_taxdeed_result_probe.py against the
CURRENT dataset to check whether any of the newly-added or newly-past-due
auctions produced a genuine closed sale that would move B/F off closed_sold=0.

RESULT: still genuinely blocked. Zero writes made. Full findings below.

=== Live dataset as of 2026-08-01 ===
35 total auctions (4 foreclosure, 31 tax deed). Only 3 cases have an
auction_date in the past relative to today:
  - 4666 (tax deed, 07/09/2026) -- auction_status='redeemed' (pre-existing)
  - 4667 (tax deed, 07/09/2026) -- auction_status='redeemed' (pre-existing)
  - 25-CA-197 (foreclosure, 07/23/2026) -- auction_status='upcoming' (NEW past-due)
  - 25-CA-170 (foreclosure, 07/28/2026) -- auction_status='upcoming' (NEW past-due)
All 31 remaining auctions (the 08/06/2026 batch of 8 tax-deed cases + 2
foreclosure cases, and the 09/03/2026 batch of 21 tax-deed cases) are
genuinely future-dated -- not yet auctioned, correctly not closed.

=== Avenues re-checked this session (all negative, matching prior sessions) ===

1. suwannee.realforeclose.com calendar (zaction=USER&zmethod=CALENDAR):
   0 dayid entries -- HTTP 200, 25249 bytes, zero highlighted auction days.
   Confirms (again) foreclosure sales are NOT tracked on this platform at all.

2. suwannee.realforeclose.com PREVIEW pages for 07/23/2026 and 07/28/2026
   (the 2 new past-due FC cases, 25-CA-197 and 25-CA-170): both requests
   return a 369-byte stub containing only
   `document.location = "/index.cfm?zaction=HOME&zmethod=error";` -- i.e.
   the site itself redirects to its generic error page. No calendar entry
   exists for either date. Confirms these sales are genuinely
   courthouse-steps-only, not an electronic-platform gap.

3. www.suwgov.org/court-services/foreclosures/ -> live docx
   (Foreclosure-List-2-1-12.docx): fetched fresh, Last-Modified header
   still "Mon, 20 Jul 2026 15:32:50 GMT" (unchanged since the last session's
   check on 07-25). Both 25-CA-197 (Jaren Dowdy, 7/23/2026) and 25-CA-170
   (Pedro Saavedra, 7/28/2026) STILL appear on the schedule list -- the
   clerk has not removed/updated them post-sale. Document explicitly states:
   "All sales begin at 11:00 a.m. and take place on the front steps of the
   Courthouse." -- confirms these are in-person courthouse-steps sales with
   no electronic results feed.

4. myfloridacounty.com/orisearch/61 (Suwannee Official Records, Civitek/
   Cloudflare platform) -- form loads at www.myfloridacounty.com (previous
   sessions had the wrong hostname, onlinesearch.myfloridacounty.com, which
   does not resolve). Submitted a real POST search for party name "Dowdy"
   (25-CA-197's defendant). Response: `Please verify you are human` /
   `onTurnstileSuccess` -- Cloudflare Turnstile wall, confirmed dead end,
   same as every prior session.

5. suwannee.realtaxdeed.com AJAX PREVIEW/RESULTS for 07/09/2026 (cases
   4666/4667, already 'redeemed' in DB): PREVIEW AITEM blocks show
   sold_to_text=None for both cases (empty ASTAT_MSG_SOLDTO_MSG div).
   RESULTS grid (Zmethod=RESULTS, both AREA=W and AREA=C) returns an EMPTY
   rlist for both areas -- zero rows, no sale posted. Matches DB's existing
   'redeemed' status (no sale occurred -- owner paid off pre-sale).

6. suwannee.realtaxdeed.com FNC=UPDATE AJAX status endpoint
   (ref=1505795,1505796, single-session run: calendar -> PREVIEW -> AJAX,
   to avoid the session-fragility SHARD-12's adversarial pass flagged):
   returned `"ADATA":{"AITEM":[],"COUNT":0}` -- empty. The PREVIEW page
   shell itself no longer even contains the case numbers 4666/4667 (the
   date has rolled off the visible calendar window, being >3 weeks past).
   Cannot reproduce the "Redeemed" text finding from any AJAX/DOM read this
   session either way -- moot regardless, since redeemed = no sale = correctly
   excluded from closed_sold under either finding.

7. suwanneepa.com (Property Appraiser) GIS/record-search: the previously
   working GSA-corp TRS-prefixed parcel URL pattern
   (suwannee-search.gsacorp.io/parcel/<TRS-ID>) returns a generic empty-title
   WordPress page for the 2 new FC parcels' raw parcel_ids (04200620080,
   08767000011) -- the TRS-prefix conversion for these specific parcels was
   not available this session (time-boxed; the working examples from the
   07-11 probe were for different parcels 10591001000/11016001003). Left as
   UNTESTED for these 2 parcels specifically, not claimed as a dead end.

=== Conclusion ===

No new closed sale found. B and F remain correctly FAIL
(verified=0/closed_sold=0, tier1_sold=0/closed_sold=0) after 35 auctions,
same root cause identified across 7+ prior sessions since 2026-07-11:
Suwannee's foreclosure and (recently) some tax-deed sales are conducted
courthouse-steps / in-person, with the electronic RealForeclose/RealTaxDeed
platform and the myfloridacounty.com Official Records search either not
covering these cases at all or Turnstile-gated. This is a structural data
availability gap, not a pipeline bug.

ZERO writes made to multi_county_auctions, foreclosure_outcomes, or
tax_deed_outcomes this session. Live pencil_dod_evaluate_county('suwannee')
called before and after -- identical result, confirming no drift.

Re-run trigger for a future session: the moment
www.suwgov.org/court-services/foreclosures/ Foreclosure-List docx's
Last-Modified header changes (currently 2026-07-20), or the clerk's phone
line (386-362-0500/0575) is called for a manual records request -- neither
of which happened this session.
"""

if __name__ == "__main__":
    print(__doc__)
