#!/usr/bin/env python3
"""
franklin_liberty_bf_recheck_2026-07-18.py

INVESTIGATION SCRIPT (no writes to multi_county_auctions / *_outcomes tables).

Dispatch: gold-standard shard-3, dispatch_id 26f01b9b-e405-422e-9908-229f26e0ae5a.

Task: franklin (9 auctions) and liberty (1 auction) county, Gold Standard criteria
B (verified independent sale outcome) and F (tier1-authoritative sold amount). Both
currently FAIL with metric=null in pencil_dod_evaluate_county() because closed_sold=0
for both counties. Determine whether this is a genuine accrual gap (no auction has
reached/resolved its sale date yet) or a stale-status bug (a real-world sale outcome
exists upstream but our multi_county_auctions row still shows open/pending).

=== multi_county_auctions live query (PostgREST, county in franklin,liberty) ===
franklin: 9 rows total.
  2025-CC-000015  auction_date=2026-05-06  auction_status=cancelled   sale_type=foreclosure
  TDA 93-2023      auction_date=2026-07-08  auction_status=scheduled  sale_type=tax_deed
  TDA 411-2023     auction_date=2026-07-08  auction_status=redeemed   sale_type=tax_deed
  TDA 624-2023     auction_date=2026-07-08  auction_status=scheduled  sale_type=tax_deed
  TDA 616-2023     auction_date=2026-07-08  auction_status=scheduled  sale_type=tax_deed
  TDA 632-2023     auction_date=2026-07-08  auction_status=scheduled  sale_type=tax_deed
  2025-CA-81       auction_date=2026-07-29  auction_status=scheduled  sale_type=foreclosure  (future)
  2025-CC-86       auction_date=2026-07-29  auction_status=scheduled  sale_type=foreclosure  (future)
  2025-CA-80       auction_date=2026-09-16  auction_status=scheduled  sale_type=foreclosure  (future)
liberty: 1 row total.
  24-CA-22         auction_date=2026-07-21  auction_status=upcoming   sale_type=foreclosure  (future, 3 days out)

Relative to today (2026-07-18), 4 franklin tax-deed rows (TDA 93/616/624/632-2023) have
a PAST auction_date (2026-07-08, 10 days ago) but still carry auction_status=scheduled
-- the stale-status pattern the dispatch asked to rule out. All are data_source=
'franklinclerk_wp_rest'.  liberty's sole row has a FUTURE auction_date (2026-07-21, 3
days from now) with auction_status=upcoming -- no stale-status question applies, it
simply hasn't happened yet.

=== Fresh live re-check, 2026-07-18 ===
This exact franklin question was already investigated twice before, same 4 certs:
  scripts/franklin_bf_verified_no_sales_2026-07-10.py (2026-07-10, initial discovery of
    the franklinclerk.com wp-json/kma/v1 REST API + platform config correction)
  scripts/franklin_bf_recheck_2026-07-11.py (2026-07-11, first re-check, unchanged)
This session re-ran the live pull a third time, one week later, to see if the clerk had
since updated the record with a real sale outcome.

GET https://www.franklinclerk.com/wp-json/kma/v1/taxdeeds (browser UA, default UA 403s)
-> HTTP 200, 5 rows, STILL UNCHANGED from 2026-07-10/07-11:
  TDA 93-2023   status "scheduled"  modified 2026-05-19T15:34:13  cert_holder="" opening_bid="2500.00"
  TDA 411-2023  status "redeemed"   modified 2026-06-01T11:29:05  cert_holder="" opening_bid="5400.00"
  TDA 616-2023  status "scheduled"  modified 2026-05-19T15:30:37  cert_holder="" opening_bid="4000.00"
  TDA 624-2023  status "scheduled"  modified 2026-05-19T15:26:27  cert_holder="" opening_bid="3900.00"
  TDA 632-2023  status "scheduled"  modified 2026-06-01T11:23:43  cert_holder="" opening_bid="3900.00"
All `modified` timestamps remain frozen at May/June 2026 -- before the Jul 8 sale date
even occurred. No cert has a populated cert_holder or any indication of a sold amount.

GET https://www.franklinclerk.com/wp-json/kma/v1/taxdeedoverbids -> HTTP 200, [] (still
empty -- no franklin tax-deed sale has ever produced a surplus/overbid record).

GET https://www.franklinclerk.com/wp-json/kma/v1/foreclosures -> HTTP 200, 5 rows. One
change since 2026-07-10: case 2025-CC-86 (1760 B-2 E Gulf Bch Dr) now shows
status="cancelled" (modified 2026-07-13T09:14:23), vs "scheduled" in our current MCA
row -- this IS a genuine upstream status drift, but "cancelled" is not a sale outcome
(no sold_amount, no closed_sold contribution) so it does not affect B/F either way. Not
corrected in this session since it is outside the B/F scope and touches auction_status
only (out of scope for this dispatch, which is B/F-specific); flagged here for a future
session's auction_status freshness pass if in scope.

GET https://libertyclerk.com/courts/foreclosure-sales/ (browser UA) -> HTTP 200. Page
lists case 24-CA-22 exactly once, under "Upcoming Foreclosure Sales":
  Status: active | Sale Date: 07/21/2026 | Case Number: 24-CA-22 |
  Judgement Amount: $108,683.02 | Parcel ID: R026-15-6W-00725-000
No "sold"/"past sales" section on the page contains this case. Confirms our MCA row
(auction_status='upcoming', auction_date='2026-07-21') is accurate -- the sale is 3
days in the future and has not occurred.

=== Conclusion ===
Both counties are GENUINELY ACCRUAL-BLOCKED for B and F, not victims of a stale-status
bug:
  - franklin's 4 past-due tax-deed certs are confirmed live, third check in a row
    (07-10, 07-11, 07-18), to have no sale outcome recorded anywhere upstream. The
    clerk's own post-modification timestamps prove the records have been dormant since
    before the sale date -- this is an upstream data-entry lag at the clerk's office,
    not a scraper defect.
  - liberty's sole auction has not reached its sale date yet (2026-07-21, 3 days from
    this check).

No row was written to multi_county_auctions, tax_deed_outcomes, or foreclosure_outcomes.
Per HONESTY PROTOCOL BLANK > WRONG, and per this county's documented fabrication history
(supabase/migrations/20260702_shard5_franklin_outcome_bid_decision_fabrication_cleanup.sql),
no placeholder or inferred sold_amount was substituted, and no data_source ILIKE
'%promote%' row was used to satisfy B (none exists for either county regardless).

pencil_dod_evaluate_county('franklin') / ('liberty') at time of this check:
  franklin: A=pass(4) B=fail(null) C=pass(100) D=pass(100) E=pass(100) F=fail(null)
            G=pass(100) H=pass(1.0h) I=pass(100) J=pass(100) -- 8/10, unchanged from 07-11.
  liberty:  A=fail(0) B=fail(null) C=pass(100) D=pass(100) E=pass(100) F=fail(null)
            G=pass(100) H=pass(0.2h) I=pass(100) J=pass(100) -- 7/10.
  (liberty A also fails independently: fc=1 td=0, i.e. A's own td>=1 threshold isn't
  met -- unrelated to B/F, out of this dispatch's scope, noted for completeness only.)

Per the campaign rule "if a target blocks on long-accrual data, switch to the next
county/letter rather than idling" -- this session does not idle further on franklin/
liberty B/F. No further action taken this session.

Author: gold-standard shard-3 session, 2026-07-18 (dispatch 26f01b9b-e405-422e-9908-229f26e0ae5a)
"""
print(__doc__)
