-- GOLD STANDARD sumter, letter C (matched_clean parity) -- 4-row gap diagnosis,
-- session 2026-08-29. Documentation artifact matching the gadsden C precedent
-- (supabase/migrations/20260823_shard2_gadsden_C_tax_deed_outcomes_redeemed.sql):
-- genuine outcome data inserted for the audit trail, sanctioned matcher called,
-- but the shared refresh function structurally cannot reach these rows. This is
-- NOT the same gap as sumter's already-exhausted E/I/J owner-name/address dead
-- end (2026-08-27 / 2026-08-28 sessions) -- that covers 3 different foreclosure
-- cases (2026-CA-000074/090/129) and different letters entirely.
--
-- BASELINE (VERIFIED live via public.pencil_dod_evaluate_county('sumter'),
-- 2026-08-29): C pass=false, matched_clean=28 of 32 (87.5%), threshold >=95%
-- (i.e. >=31/32). D (matched_any) already passes at 100.0% (32/32). Gap = 4.
--
-- ROOT CAUSE (VERIFIED, exact same structural class as gadsden 2026-08-23):
-- the 4 rows in matched_any but NOT matched_clean are ALL tax-deed certs with
-- parity_status='CLERK_SSOT_CANCELLED', parity_source='sumter_clerk_tax_deed':
--   cert 1078 | 33 CR 489A, Lake Panasoffkee, FL      | parcel J16C020
--   cert 1400 | 349 C 478 W, Webster, FL 33597         | parcel N33-021
--   cert 1159 | 4206 C 575, Wahoo, FL                  | parcel M06C003
--   cert 104  | 9038 CR 229, Wildwood, FL              | parcel C27-268
-- All 4 have auction_status='CANCELLED' (generic), auction_date=2026-09-10.
--
-- LIVE FINDING (2026-08-29, VERIFIED): fetched sumterclerk.com's own live tax
-- deed sale page directly (https://www.sumterclerk.com/public-records/tax-deeds/
-- tax-deed-sales/ -- a Vue component with taxdeeds="[...]" HTML-entity-encoded
-- JSON baked into the page source, same structure documented in
-- scripts/clerk_ssot/parsers/sumter.py). Fetched with curl + a real Chrome UA
-- (plain WebFetch returned a JS-shell page with no embedded data -- had to use
-- curl directly, per the same approach documented for gadsden's Cloudflare-
-- blocked sheet). All 4 certs are present with an explicit status field:
--   1078 | JACKSON, MARTIN                       | status: "redeemed"
--   1400 | GRINER, ANDREW & SEAN (JTWROS)         | status: "redeemed"
--   1159 | CROMER, BRENDA                         | status: "redeemed"
--   104  | TRUSTEES OF THE OAK HILL CEMETERY      | status: "redeemed"
-- This CONFIRMS our DB's CLERK_SSOT_CANCELLED classification is CORRECT and
-- CURRENT -- not stale, not a mismatch, not a bug. Per scripts/clerk_ssot/
-- parsers/sumter.py CANCELLED_STATUSES = {"cancelled","canceled","redeemed"},
-- "redeemed" is intentionally treated as a cancellation class (the tax deed
-- sale will never happen because the certificate was paid off) -- and per
-- scripts/clerk_ssot/run_parity.py's diff_and_reconcile(), an agreed-cancelled
-- row ALWAYS routes to the cancelled_mismatch bucket -> CLERK_SSOT_CANCELLED,
-- NEVER to PARITY_OK/CLERK_VERIFIED. There is no code path in the live
-- reconciliation logic that produces a "clean" classification for a redeemed
-- tax deed. This is by design (see migration 20260810_gold_standard_shard3_
-- lake_clerk_ssot_cd_recognition.sql: "CLERK_SSOT_CANCELLED as matched_any
-- (not clean -- it represents a divergence that clerk_ssot found and
-- corrected)").
--
-- ACTION TAKEN: inserted 4 tax_deed_outcomes rows below with outcome='redeemed'
-- and data_source='sumter_clerk_tax_deed_page_verified_20260829' (a genuinely
-- new, independent source label distinct from the existing
-- parity_source='sumter_clerk_tax_deed' already on the multi_county_auctions
-- rows). Then called the sanctioned refresh_parity_tier1_outcomes('sumter')
-- function (NOT hand-written parity_status).
--
-- RESULT (VERIFIED, does NOT flip C, matches gadsden precedent exactly):
-- pencil_dod_evaluate_county('sumter') C metric was 87.5% (28/32) before this
-- migration. Root cause, confirmed by reading the live refresh_parity_tier1_
-- outcomes definition (supabase/migrations/20260704_shard13_run3025_2nd_
-- dispatch_refresh_parity_snapshot_fix.sql line 44): the reset step only
-- clears parity_status/parity_source when "parity_source IS NULL OR
-- parity_source IN ('tier1_tax_deed_outcome','tier1_foreclosure_outcome')".
-- All 4 sumter rows carry parity_source='sumter_clerk_tax_deed' (set by the
-- clerk_ssot upstream process directly, not one of those two literals), so
-- they are PERMANENTLY excluded from the reset and from the candidate CTE's
-- "WHERE a.parity_source IS NULL" gate -- regardless of what real outcome
-- data exists in tax_deed_outcomes. Per the hard rules for this dispatch,
-- refresh_parity_tier1_outcomes is NOT edited here -- a real fix to unblock C
-- would require a fleet-wide, reviewed change to that shared function's
-- parity_source allow-list, which is out of scope for a single county-scoped
-- pass and would affect every clerk_ssot county (brevard, gadsden, highlands,
-- lake, okeechobee, st_johns, sumter, suwannee, union, wakulla, and others in
-- the PARSERS dict).
--
-- CONCLUSION: BLOCKED. Not a data error on our side -- the classification is
-- verified-current and verified-correct against the live clerk source. The
-- gap is a structural ceiling in the shared matched_clean scoring formula
-- (CLERK_SSOT_CANCELLED is intentionally excluded from "clean" by the
-- 2026-08-10 migration's own design), not a resolvable per-county data fix.
-- 32 total sumter auctions with 4 confirmed-redeemed tax deed certs means the
-- structural ceiling for sumter C is 28/32 = 87.5% until the shared function
-- is widened -- identical mechanism, same ceiling shape as gadsden's 56/66.
--
-- Applied live via Supabase REST (PostgREST) during this session; this file
-- documents that already-applied change. ON CONFLICT guards make re-running
-- a no-op.

INSERT INTO public.tax_deed_outcomes
  (case_number, county, auction_date, outcome, property_address, parcel_id, data_source, source_url)
VALUES
  ('1078', 'sumter', '2026-09-10', 'redeemed', '33 CR 489A, Lake Panasoffkee, FL', 'J16C020', 'sumter_clerk_tax_deed_page_verified_20260829', 'https://www.sumterclerk.com/public-records/tax-deeds/tax-deed-sales/'),
  ('1400', 'sumter', '2026-09-10', 'redeemed', '349 C 478 W, Webster, FL 33597', 'N33-021', 'sumter_clerk_tax_deed_page_verified_20260829', 'https://www.sumterclerk.com/public-records/tax-deeds/tax-deed-sales/'),
  ('1159', 'sumter', '2026-09-10', 'redeemed', '4206 C 575, Wahoo, FL', 'M06C003', 'sumter_clerk_tax_deed_page_verified_20260829', 'https://www.sumterclerk.com/public-records/tax-deeds/tax-deed-sales/'),
  ('104',  'sumter', '2026-09-10', 'redeemed', '9038 CR 229, Wildwood, FL', 'C27-268', 'sumter_clerk_tax_deed_page_verified_20260829', 'https://www.sumterclerk.com/public-records/tax-deeds/tax-deed-sales/')
ON CONFLICT (case_number, county, auction_date) DO NOTHING;

-- Sanctioned matcher call (no-op today given the parity_source gating finding
-- above; kept for idempotent re-run in case the shared function is ever
-- widened by a separate, reviewed change).
SELECT * FROM public.refresh_parity_tier1_outcomes('sumter');
