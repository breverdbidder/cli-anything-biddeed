-- GOLD STANDARD shard-2 (dispatch d3ebfbe4): walton C/D fix.
--
-- ROOT CAUSE (confirmed live 2026-08-18): 10 walton tax_deed rows were bulk-flipped to
-- parity_status='PHANTOM_NOT_ON_CLERK' at a single timestamp (2026-08-18 07:18:52 UTC) by
-- a process with no corresponding script anywhere in this repo (grep for
-- PHANTOM_NOT_ON_CLERK + walton across scripts/, migrations/, .github/workflows/ returns
-- nothing) -- an untracked/erroneous direct write, not a genuine reconciliation finding.
-- All 10 sale dates are still in the future (today through 2026-09-29), making a
-- "not confirmed on clerk after the sale" classification a logical impossibility. All 10
-- also have pre-existing sale_type='foreclosure' sibling rows (same case_number/parcel_id)
-- left untouched at matched_clean by the same 07:18:52 write, consistent with a
-- sale_type-scoped bug in whatever produced the flip.
--
-- Live re-verified all 10 case numbers against Walton County Clerk's own Tax Deed Division
-- search system (https://taxsmart.clerkofcourts.co.walton.fl.us, via its
-- /Home/GridSearchData?SearchType=Case%20%23 JSON endpoint) -- all 10 are real, valid cases
-- with status REDEEMED (owner paid off delinquent taxes pre-sale, a normal outcome), parcel
-- IDs and sale dates matching our DB exactly. Independently re-sampled 4/10 by a separate
-- adversarial-refuter agent against the same live source -- all 4 confirmed.
--
-- Applied live via Supabase Management API during this session; this migration file
-- documents that already-applied change for the repo's audit trail. Re-running it is a
-- no-op if the rows are already matched_clean.

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:manual_reverify_20260818_walton_live_recheck'
WHERE county = 'walton' AND sale_type = 'tax_deed'
  AND parity_status = 'PHANTOM_NOT_ON_CLERK'
  AND case_number IN ('2026-0078TD','2026-0070TD','2026-0062TD','2026-0058TD',
                       '2026-0061TD','2026-0064TD','2026-0105TD','2026-0104TD',
                       '2026-0120TD','2026-0124TD');
