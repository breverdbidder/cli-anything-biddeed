#!/usr/bin/env python3
"""
stlucie_audit_refresh_2026-07-27.py

Dispatch: gold-standard shard-4 (st_lucie-only), dispatch_id
8198896f-0420-4072-9f46-30ab50c7779e, ultracode fan-out (Workflow: 6 parallel
adversarial refuter agents, one per stale letter A/B/E/F/H/J -- letters C/D/G/I
were already fresh from 2026-07-25 and skipped), logged to
gold_standard_ultraloop_audit ids 10405-10411.

Task: st_lucie shard brief claimed 10/10 PASS, but 6 of 10 letters
(A/B/E/F/H/J) had their last survived=true ultraloop_audit evidence from
2026-07-10/07-18 -- stale beyond the EVALUATOR V6 7-day certify window.
Session goal: independently re-verify each stale letter against live Supabase
data via REST API (psql direct connection failed with a password-auth error
in this sandbox; PostgREST over HTTPS worked throughout), adversarially
refute before logging, fix any real bug found, and refresh the audit trail.

=== Findings ===

A -- SURVIVED. fc=98 td=13 matches evaluator and brief exactly. Refuter flagged
the tax_deed lane (13 rows) as a frozen ~3-month-stale batch: all auction_date
in {2026-04-06, 2026-05-04}, 10/13 upcoming-past-due (needs_source_rescrape),
3/13 cancelled, 0 sold -- vs the foreclosure lane's active pipeline (25/98
upcoming >= today, 2 sold). This is a genuine evaluator-design gap (A checks
lane existence, not lane activity) flagged as a residual for architect
review, not a data bug -- the reported numbers are accurate.

B -- SURVIVED. foreclosure_outcomes has exactly 2 rows (case 2025CA000393
$356,000; case 2025CA001029 $261,100), data_source=realforeclose:... (RealAuction,
independent, zero PropertyOnion markers). tax_deed_outcomes=0. multi_county_auctions
sold/closed=2, exact cross-match. Full auction_status breakdown (upcoming:96,
cancelled:13, sold:2) rules out a hidden denominator bucket. Ratio 100.0% is
genuine, not the Brevard/Duval-style inflated-ratio anomaly.

E -- GHOST-SUCCESS FOUND AND FIXED LIVE. Original claim (parcel_linked=109/111,
98.2% PASS) was refuted: 7 of the 109 "linked" rows had non-parcel garbage
strings in parcel_id -- 'Property Appraiser' x4 (case 2024CA001834,
2025CC001033, 2023CA002852, 2023CA000465... see below), 'AIRCRAFT' x1,
'MULTIPLE PARCEL' x1, 'TIMESHARE' x1 -- clearly scraper artifacts (UI labels
captured instead of real parcel numbers), not real parcel identifiers.
FIXED LIVE: UPDATE multi_county_auctions SET parcel_id=NULL WHERE
county='st_lucie' AND parcel_id IN ('Property Appraiser','AIRCRAFT',
'MULTIPLE PARCEL','TIMESHARE') -- 7 rows corrected (case_numbers
2024CA001834, 2025CC001033, 2023CA002852, 2024CA000958, 2024CA000330,
2025CA002738, 2023CA000465). E now honestly reports FAIL, parcel_linked=102/111
= 91.9% (was ghost-PASS 98.2%). Per HONESTY PROTOCOL an honest FAIL is correct
and required over a false PASS.

F -- SURVIVED. tier1_sold_amount populated for both of the 2 sold rows,
exactly matching sold_amount. Reverse scope check (tier1_sold_amount NOT NULL,
any status) returns the identical 2 rows -- no numerator/denominator
scope-mismatch. Ratio 100.0% genuine.

H -- SURVIVED, and the refuter's own initial refutation was OVERTURNED on
independent orchestrator re-check. The refuter computed elapsed time from
last_seen_at alone (max 2026-07-27T15:56:06Z vs then-current ~19:29:35Z =
~3.56h) and flagged the RPC's reported metric=0.1h as inconsistent. But the
evaluator's actual SQL (supabase/migrations/20260718_gtm22_phase1_3_pencil_dod_
snapshot_param_and_loop_rewire.sql) computes last_seen as
max(GREATEST(last_changed_at, last_seen_at, scraped_at, scrape_timestamp,
created_at)) per row -- not last_seen_at alone. Independently queried all 5
columns across all 111 rows: MAX(scraped_at)=2026-07-27T19:32:22.955194Z
(case 2026CA000534), captured 6 seconds before an orchestrator RPC call at
19:32:16Z (HTTP Date header confirmed) -- i.e. a live scrape was actively
running during this very session. True GREATEST-based elapsed time is
genuinely ~0.0-0.1h. The refuter's methodology (checking only 1 of 5 GREATEST
columns) was the error, not the evaluator or the data.

I -- SIDE-EFFECT REGRESSION disclosed (not one of the 6 original stale
targets -- last audited 2026-07-25, still fresh at session start). Fixing E's
ghost-linkage directly caused I to regress live from 96.4% (card_complete=
107/111) to 91.9% (card_complete=102/111): the same 7 rows' zoning-card
completeness depended on the same fabricated parcel_id matching a zoning
parcel. I's TRUE completeness was always 102/111 -- the prior 107/111 was
itself ghost-inflated by the same 7 bad values.

J -- GHOST-SUCCESS FLAGGED, NOT FIXED THIS SESSION. Mechanical field-
completeness claim confirmed true (all 110 distinct MCA case_numbers have a
matching bid_decisions row with arv/max_bid/ml_score non-null and all 5
required factor keys present -- RPC J=100.0 genuinely reflects field
presence). But independently reproduced the refuter's deeper finding: across
all 142 county_slug=st_lucie bid_decisions rows, ml_score takes only 3
distinct values (0.75:71, 0.82:21, 0.58:50), the (distress_owner,
distress_location, distress_property) triple collapses to just 3 distinct
combinations (85 rows / 50 rows / 7 rows), and cma_distressed.value is
65000.0 in 50 rows and 32500.0 in 16 rows (46% of all 142 rows sharing just 2
values) despite covering 111 structurally different properties. This is a
templated/bucket-fill pattern, not genuine per-property Shapira-model +
two-arm-CMA computation, even though values carry honesty_marker=INFERRED.
J's evaluator only checks field presence, not value authenticity, so this
ghost-success is invisible to the current metric. Repairing the bid_decisions/
CMA generator pipeline is out of scope for an audit-refresh session; flagged
for architect-level triage, consistent with the fleet-wide J concern
documented 2026-06-12 in this campaign's own brief history.

=== Net result ===
st_lucie moves from a stale/ghost-inflated "10/10" to a verified, freshly-
audited 8/10 (E and I now honestly FAIL) with J flagged as a currently-PASSing
but suspect letter requiring architect review. This is a disclosed regression
caused by removing fabricated data, which HONESTY PROTOCOL and SHIP GATE both
require over silently carrying a false PASS toward certification.

=== Next-session priorities ===
1. E/I: backfill real parcel_id for the 7 identified cases via St Lucie
   Property Appraiser GIS. 2 of 7 (2025CA002738, 2023CA000465) have no
   source_url at all (genuine source gap). 4 of the remaining 5 have
   placeholder addresses ("St. Lucie County FL -- <case>", also fabricated).
   Only case 2024CA000958 has a real street address (436 SW CRAWFISH DR,
   PORT SAINT LUCIE FL 34953) immediately usable for a live GIS lookup.
2. J: architect-level review of the bid_decisions/CMA generator for st_lucie
   (and likely fleet-wide) -- the templated-bucket pattern found here should
   be checked against other counties' bid_decisions before assuming J passes
   are generally trustworthy.
3. A: fleet-level decision on whether criterion A should also check lane
   activity/freshness (not just lane existence) -- st_lucie's tax_deed lane
   has been frozen since ~2026-05-04 with zero live scrape activity.
"""
