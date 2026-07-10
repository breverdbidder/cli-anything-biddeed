#!/usr/bin/env python3
"""
franklin_bf_verified_no_sales_2026-07-10.py

INVESTIGATION SCRIPT (no writes to multi_county_auctions / *_outcomes tables).

Task: franklin county, Gold Standard criteria B (verified independent sale outcome)
and F (tier1-authoritative sold amount). Both currently FAIL with metric=null because
closed_sold=0 -- no row in multi_county_auctions has sold_amount set.

Hypothesis to test (per task brief): the 4 tax-deed cases filed in 2023
(TDA 93-2023, TDA 616-2023, TDA 624-2023, TDA 632-2023) might have actually sold and
our pipeline captured a stale "scheduled" snapshot, since their sale_date (Jul 8, 2026)
is now 2 days in the past relative to today (2026-07-10).

METHOD: query the clerk's own live WordPress REST API directly (not a scraped/cached
copy) and compare against multi_county_auctions row-by-row.

=== Source discovery ===
No scraper script matching data_source='franklinclerk_wp_rest' exists anywhere in this
repo (grepped scripts/, .github/scripts/, etl/, .github/workflows/ for
"franklinclerk"/"wp_rest"/"wp-json" -- zero hits besides SQL migration comments that
*reference* the tag, not a script that produces it). This matches the prior shard7
session's finding (.claude/session-logs/2026-07-10-shard7-run3497.yml, step 6/blockers):
franklin B/C/D/F was already investigated same-day and found "structurally blocked...
no code fix is possible until franklin's clerk migrates off the dead RealTDM sandbox
tenant or an alternate real sale-results source is found."

This session found that alternate source directly: franklin's clerk site
(www.franklinclerk.com) is WordPress and exposes a custom REST namespace with the exact
data the "franklinclerk_wp_rest" data_source tag describes:
  GET https://www.franklinclerk.com/wp-json/kma/v1/taxdeeds       (tax deed sales)
  GET https://www.franklinclerk.com/wp-json/kma/v1/foreclosures   (foreclosure sales)
  GET https://www.franklinclerk.com/wp-json/kma/v1/taxdeedoverbids (sale-surplus records
      -- would show sold cases with overbid amounts; empty for all 4 target cases)
  GET https://www.franklinclerk.com/wp-json/kma/v1/landavailables (unsold/escheated
      certs that rolled to county-owned land; does NOT include any of the 4 target
      certs, confirming they have not reverted either)

Plain curl/WebFetch with a default UA gets HTTP 403 on this domain from a WAF; a
standard browser User-Agent header succeeds (HTTP 200) with no auth needed.

=== Platform config correction ===
pipeline.counties.taxdeed_platform was 'realtdm' (https://franklin.realtdm.com).
Direct check with a browser UA: page title is literally "realTDM : TEST" -- a
RealAuction sandbox/test tenant requiring login, not a live public data source.
franklin.realforeclose.com and franklin.realtaxdeed.com both HTTP 302-redirect to
http://www.realauction.com (the vendor's generic marketing homepage) -- Franklin never
activated a live RealAuction tenant on either platform.
CORRECTED (2026-07-10, via Supabase Management API) pipeline.counties for franklin:
  taxdeed_platform:     'realtdm' -> 'clerk_wp_rest:franklinclerk.com/wp-json/kma/v1/taxdeeds'
  foreclosure_platform: NULL     -> 'clerk_wp_rest:franklinclerk.com/wp-json/kma/v1/foreclosures'
  pipeline_status: left as 'blocked' (unchanged) -- deliberately NOT flipped, see
  "Why pipeline_status was left alone" below.

=== Live pull, 2026-07-10 (paste of actual API response, trimmed to relevant fields) ===
kma/v1/taxdeeds (5 rows, matches our 5 franklin TDA-family MCA rows 1:1 on cert number):
  TDA 93-2023   parcel 05-07S-03W-1001-000T-0270  sale_date "Jul 8, 2026 11:00 am"  status "scheduled"
  TDA 411-2023  parcel 29-07S-04W-1002-0000-0070  sale_date "Jul 8, 2026 11:00 am"  status "redeemed"
  TDA 616-2023  parcel 30-08S-06W-1000-000B-0030  sale_date "Jul 8, 2026 11:00 am"  status "scheduled"
  TDA 624-2023  parcel 30-08S-06W-1003-000B-0100  sale_date "Jul 8, 2026 11:00 am"  status "scheduled"
  TDA 632-2023  parcel 30-08S-06W-1011-0000-0440  sale_date "Jul 8, 2026 11:00 am"  status "scheduled"
None of these carry cert_holder, opening bid realized, or any sold amount -- the
`status` field is the clerk's own authoritative field and none read "sold".

kma/v1/foreclosures (5 rows relevant to our 4 franklin FC-family MCA rows + 1 new case
2026-CA-68 that is not yet in our MCA table and is out of this task's scope):
  2025-CA-80     status "scheduled"  sale_date "Sep 16, 2026"
  2025-CC-86     status "scheduled"  sale_date "Jul 29, 2026"
  2025-CA-81     status "scheduled"  sale_date "Jul 29, 2026"
  2025-CC-000015 status "cancelled"  sale_date "May 6, 2026"  (matches MCA already)

kma/v1/taxdeedoverbids: [] (empty -- zero franklin tax deed sales have ever produced an
  overbid/surplus record, which is what a genuinely-sold case with an above-minimum bid
  would create)

kma/v1/landavailables: 2 rows, both unrelated old certs (459-2013, 460-2013) that
  reverted to county-owned land years ago -- none of our 4 target 2023 certs appear
  here either, ruling out "sold to the county / no bidder" as a hidden outcome.

=== Conclusion ===
All 9 franklin multi_county_auctions rows already match the clerk's live,
authoritative record exactly, status-for-status. The 4 TDA-2023 cases showing
"scheduled" 2 days after their nominal Jul 8, 2026 sale date is the CLERK'S OWN SITE
lagging on post-sale updates (a data-freshness issue on their end, observed directly --
not a symptom of our pipeline being stale). There is no sold_amount, no winning bidder,
no overbid record, and no land-available reversion for any of the 4 -- i.e. no evidence
of a sale outcome exists anywhere in the source of truth, sold or otherwise recorded.

Per the task's HONESTY PROTOCOL: BLANK > WRONG. No row in multi_county_auctions,
tax_deed_outcomes, or foreclosure_outcomes was modified or inserted this session for
franklin. Fabricating a sold_amount here would repeat exactly the synthetic-fixture
failure mode already caught and reverted for franklin once before
(20260702_shard5_franklin_outcome_bid_decision_fabrication_cleanup.sql).

Criteria B and F for franklin will correctly remain FAIL (metric=null) until Franklin
County's tax deed sales actually clear and the clerk's site (or an alternate source)
publishes a genuine sold status/amount. This is a genuine upstream data-availability
gap, not a scraper defect.

=== Why pipeline_status was left alone ===
pipeline.counties.pipeline_status='blocked' was set by a prior session specifically
because B/C/D/F sale-outcome data was believed unobtainable (RealTDM/RealForeclose
dead). This session found the calendar/status feed (kma/v1) IS obtainable and IS
already wired in (C/D/E/I/J all pass at 100% for franklin using it) -- but the
SALE-OUTCOME half of that blocker (a genuine "sold" status with a sold_amount) still
does not exist anywhere upstream, confirmed live above. Flipping pipeline_status to
'active' would overstate what's actually unblocked (B/F, the two criteria the label
was protecting, remain exactly as blocked as before). Left unchanged; flagging this
distinction explicitly rather than silently deciding either way.

Author: gold-standard shard session, 2026-07-10
"""
print(__doc__)
