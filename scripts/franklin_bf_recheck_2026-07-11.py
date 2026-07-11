#!/usr/bin/env python3
"""
franklin_bf_recheck_2026-07-11.py

FOLLOW-UP INVESTIGATION (no writes to multi_county_auctions / *_outcomes tables).

Context: scripts/franklin_bf_verified_no_sales_2026-07-10.py ran one day ago and found
franklin's clerk (www.franklinclerk.com) exposes a real, authoritative, no-auth
WordPress REST API (kma/v1 namespace) whose 5 taxdeed rows match our 5 franklin
TDA-family MCA rows 1:1 by cert number -- all status='scheduled' or 'redeemed' with a
Jul 8, 2026 sale_date, no sold amount, no overbid record, no land-available reversion.
Criteria B (verified independent sale outcome) and F (tier1-authoritative sold amount)
both FAIL with metric=null because closed_sold=0.

Task (2026-07-11, 3 days past the Jul 8 sale_date, 1 day past the prior check): do ONE
fresh live re-check to see if the clerk's site has updated with real sale outcomes
since then.

=== Fresh live pull, 2026-07-11 (browser UA required, default UA still 403s) ===
GET https://www.franklinclerk.com/wp-json/kma/v1/taxdeeds -> HTTP 200, 5 rows, UNCHANGED
from 2026-07-10:
  TDA 93-2023   parcel 05-07S-03W-1001-000T-0270  status "scheduled"  modified 2026-05-19T15:34:13Z
  TDA 411-2023  parcel 29-07S-04W-1002-0000-0070  status "redeemed"   modified 2026-06-01T11:29:05Z (approx, list view)
  TDA 616-2023  parcel 30-08S-06W-1000-000B-0030  status "scheduled"  modified 2026-05-19T15:30:37Z
  TDA 624-2023  parcel 30-08S-06W-1003-000B-0100  status "scheduled"  modified 2026-05-19T15:26:27Z
  TDA 632-2023  parcel 30-08S-06W-1011-0000-0440  status "scheduled"  modified 2026-06-01T11:23:43Z (approx, list view)
None of the 5 rows' `modified` timestamps are later than early June 2026 -- i.e. the
clerk has not touched a single one of these records since well BEFORE the Jul 8 sale
date, let alone updated them with a post-sale outcome. This is stronger evidence than
yesterday's status-only comparison: it proves the record is stale-by-construction, not
just stale-in-appearance.

GET https://www.franklinclerk.com/wp-json/kma/v1/taxdeedoverbids -> HTTP 200, [] (still
empty -- zero surplus/overbid records for any franklin tax deed sale, ever).

GET https://www.franklinclerk.com/wp-json/kma/v1/landavailables -> HTTP 200, 2 rows,
both pre-existing 2013-vintage certs (459-2013, 460-2013) unrelated to the 4 target
2023 certs -- confirms no hidden "reverted to county" outcome either.

=== Additional checks this session (beyond yesterday's investigation) ===
1. Enumerated the FULL kma/v1 route table (GET /wp-json/kma/v1/) to rule out an
   undiscovered "sale results" endpoint:
     announcements, announcement, alerts, events, event, foreclosures, foreclosure,
     taxdeeds, taxdeed, taxdeedoverbids, taxdeedoverbid, landavailables, landavailable,
     team, person, site-search
   No results/sales-outcome endpoint exists beyond what was already checked.
2. Probed common guessed endpoint names (taxdeedsales, taxdeedresults, saleresults,
   results, salesresults) -- all HTTP 404, confirming no hidden endpoint.
3. Pulled the singular per-record detail endpoint (GET /wp-json/kma/v1/taxdeed?id=1730,
   the raw WordPress ACF post meta for TDA 93-2023) to rule out the list view
   truncating a sold value: status="scheduled", original_bid="" (empty -- this is the
   field that would carry a winning bid amount), cert_holder="" (empty). Confirms the
   list view is not hiding anything -- the underlying WP post itself has no sold data.
4. Cross-checked all 9 franklin multi_county_auctions rows (case_number, data_source,
   sold_amount, tier1_sold_amount, tier1_sale_status, auction_status, auction_date,
   tier1_authoritative, parity_source) against the live API: zero drift, 1:1 match on
   every field. data_source='franklinclerk_wp_rest' confirms the 2026-07-10 platform
   correction persisted correctly.

=== Conclusion ===
No new sale-outcome data exists anywhere upstream for franklin's 4 target 2023 tax-deed
certs. The clerk's own post-modification timestamps prove these specific records have
been dormant since before the sale even occurred -- the clerk has not yet performed
whatever manual post-sale data-entry step would populate status/original_bid/cert_holder,
if such a step is even part of their workflow at all. This is a genuine, still-unresolved
upstream data-availability gap, not a scraper defect and not new information changing the
2026-07-10 conclusion.

Criteria B and F for franklin correctly remain FAIL (metric=null). No row was written to
multi_county_auctions, tax_deed_outcomes, or foreclosure_outcomes. Per HONESTY PROTOCOL
BLANK > WRONG, and per this county's documented fabrication history
(20260702_shard5_franklin_outcome_bid_decision_fabrication_cleanup.sql), no placeholder
or inferred value was substituted.

pencil_dod_evaluate_county('franklin') before this check and after this check are
IDENTICAL: A=4 pass, B=fail(null), C=100.0 pass, D=100.0 pass, E=100.0 pass, F=fail(null),
G=100.0 pass, H=11.5h pass, I=100.0 pass, J=100.0 pass. 8/10, unchanged.

Author: gold-standard shard-6 session, 2026-07-11 (dispatch e9951859-29fe-4c2e-aa04-ca05ced1d0c7)
"""
print(__doc__)
