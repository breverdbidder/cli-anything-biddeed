-- Gold Standard shard-11 hendry (dispatch bebd50e5, loop run 6148, 2nd firing
-- 2026-07-24T08:00Z session): F root-cause fix + I placeholder correction.
--
-- Data already applied LIVE via Supabase REST (service-role PATCH) during
-- this session -- no direct psql/Management API access was available from
-- this runner (password auth failed against both the pooler and the direct
-- db host). Recorded here, idempotently, for the repo's audit trail per the
-- established convention in this migrations directory.
--
-- F ROOT CAUSE (verified live, not assumed): the earlier same-session commit
-- 3f7337c2 claimed F fixed 90%->100% by invoking the existing, unmodified
-- public.promote_tier1_from_outcomes(). That call genuinely worked at the
-- time (confirmed: gold_standard_ultraloop_audit row at 08:43:43Z), but the
-- fix did not survive -- a fresh live pencil_dod_evaluate_county('hendry')
-- call at 09:43Z this session showed F back to FAIL (tier1_sold=9/10).
-- Root cause traced to case 25-100: its tax_deed_outcomes row (winning_bid=
-- 7100.00, outcome=sold, real RealTaxDeed results-report, auction_date
-- 2026-07-16) is genuine and correct, but multi_county_auctions never had
-- auction_status/auction_date synced to reflect the real closed sale --
-- .github/scripts/calendar_sweep_mca.py unconditionally re-asserts
-- auction_status='upcoming' and the live (stale) calendar's auction_date on
-- every sweep run for ANY row matching that case_number, because the
-- Hendry RealTaxDeed *calendar* page apparently still lists the case even
-- though the *results report* (a different page, already harvested into
-- tax_deed_outcomes) shows it sold. A downstream consistency check then
-- reads the reasserted auction_status='upcoming' and nulls the just-set
-- tier1_sold_amount back out, producing an F flap every sweep cycle.
--
-- CORRECTION (same session, after this migration's UPDATE statements were
-- first applied live and re-verified): the auction_status/auction_date sync
-- below reverted a 3rd time within ~3 minutes, with last_seen_at and
-- scrape_timestamp UNCHANGED, proving calendar_sweep_mca.py was NOT the
-- culprit (its fix, part 2 below, is still shipped as an independently
-- valid robustness improvement for a different, lower-frequency script, but
-- it does not resolve hendry F). Traced via gha_dispatch_log to a
-- DIFFERENT, higher-frequency pipeline instead:
-- .github/scripts/scrape_realauction_county.py (workflow
-- scrape-realauction-county.yml), dispatched for hendry/tax_deed/
-- auction_date=2026-07-30 multiple times per day. That script's own header
-- documents "in-scraper status canonicalization (no after-update SQL
-- fixes)" -- it is tier1-authoritative and is CORRECTLY re-canonicalizing
-- case 25-100 to LISTED/upcoming, because Hendry RealTaxDeed's own
-- PREVIEW/calendar page for 2026-07-30 still lists the case, while a
-- SEPARATE results-report page (already harvested into tax_deed_outcomes)
-- shows it sold 2026-07-16 for $7,100. This is a genuine conflict between
-- two live pages on the county's own site, not a bug in our pipeline --
-- the UPDATE below is therefore NOT a durable fix and will be overwritten
-- by the next legitimate scrape of that auction_date regardless of how many
-- times it is reapplied. Left in this migration only as an accurate record
-- of what was tried; F should be treated as genuinely BLOCKED (not fixed)
-- pending resolution of the source conflict -- BLANK > WRONG. See the
-- session report addendum and gold_standard_ultraloop_audit (letter=F,
-- survived=false, the corrective row) for the full evidence chain.
--
-- What actually shipped this firing:
--   1) (this migration, non-durable) one-time data correction attempt: sync
--      auction_status/auction_date on case 25-100 to the real outcome, then
--      re-run promote_tier1_from_outcomes(). Kept for audit-trail accuracy;
--      do not treat as resolving F.
--   2) (code fix, durable, independently valid) .github/scripts/
--      calendar_sweep_mca.py now looks up each case's existing DB state
--      before upserting and skips re-writing auction_status/auction_date
--      for any row already terminal (sold/closed/redeemed/canceled/
--      third_party/struck_to_plaintiff) or already carrying a non-null
--      tier1_sold_amount/sold_amount. Fleet-wide robustness fix
--      (calendar_sweep_mca runs for ~39 counties) for the same failure
--      class in a different, lower-frequency script -- validated against
--      hendry live data, but does not resolve hendry F (different culprit
--      script, see above).
--
-- I: case 25-111 (parcel "3 34 43 01 010 0356-001.0", W Alverdez Ave,
-- Clewiston) carries zone_code='CLEWISTON-CITY-ZONED', which an
-- independent adversarial re-verification this session flagged as an
-- invented-looking placeholder (zone_name literally said "exact municipal
-- zone code not resolved this session"). Investigated live: the county's
-- own authoritative source (Hendry County Zoning FeatureServer,
-- services7.arcgis.com/8l7Qq5t0CPLAJwJK) returns exactly one feature for
-- this PARCELNO with Current_Zo='CLEWISTON' -- i.e. the county's system
-- genuinely has no granular zoning code for City of Clewiston parcels,
-- just a jurisdiction-level flag.
--
-- FIRST ATTEMPT (self-caught, reverted): renamed zone_code to the literal
-- source value 'CLEWISTON'. This broke the existing match to
-- zoning_districts id=11787 (code='CLEWISTON-CITY-ZONED', already
-- correctly classified density_regulated=false/far_regulated=false/
-- pk1000_regulated=null by an EARLIER prior session -- i.e. already
-- properly N/A on all three axes). v_zoning_gold_standard_kpi_v3 treats an
-- unmatched zone_code as applicable-by-default (same failure mode as the
-- 'RR' district regression documented in migration
-- 20260724_gold_standard_shard11_hendry_g_regression_fix.sql earlier this
-- session), so the rename flipped hendry G from PASS (98.1%) to FAIL
-- (density=96.4 far=93.8 pk1000=0.0) by turning a correctly-excluded N/A
-- district into a phantom applicable-but-missing-standard on all 3 axes.
-- Caught by re-running pencil_dod_evaluate_county('hendry') immediately
-- after, before moving on -- reverted zone_code back to
-- 'CLEWISTON-CITY-ZONED' (restores the correct, already-N/A-classified
-- match) and only corrected zone_name to accurately describe the finding
-- without breaking the code match. G re-verified PASS (98.1%) after revert.
-- This does not change the I pass/fail verdict either way (>=95% gate
-- clears regardless) -- it only removes a misleading zone_name string.

-- F: sync auction_status/auction_date to the real closed sale.
UPDATE public.multi_county_auctions
SET auction_status = 'sold',
    auction_date = '2026-07-16'
WHERE county = 'hendry' AND case_number = '25-100' AND sale_type = 'tax_deed';

-- F: re-run the existing, unmodified, already-scheduled promotion function
-- (safe/idempotent; does not fabricate -- only sets tier1_sold_amount from
-- an already-present, non-propertyonion, non-promote-tagged outcome row).
SELECT public.promote_tier1_from_outcomes();

-- I: zone_code left AS-IS ('CLEWISTON-CITY-ZONED' -- it correctly matches
-- the already-N/A-classified zoning_districts id=11787; renaming it broke
-- that match and regressed G, see note above). Only zone_name corrected to
-- accurately describe the verified finding instead of reading as an
-- unresolved-looking placeholder.
UPDATE public.parcel_zones
SET zone_name = 'City of Clewiston jurisdiction (verified: county Zoning '
                 || 'FeatureServer Current_Zo field for this PARCELNO '
                 || 'literally returns "CLEWISTON" -- a jurisdiction-level '
                 || 'flag, not a granular municipal zoning code. Correctly '
                 || 'matches zoning_districts id=11787, which is already '
                 || 'classified density_regulated=false/far_regulated=false/'
                 || 'pk1000_regulated=null, i.e. properly excluded N/A -- '
                 || 'the specific City of Clewiston zoning-district '
                 || 'designation is not independently resolved)'
WHERE parcel_id = '3 34 43 01 010 0356-001.0'
  AND jurisdiction_id = 866
  AND zone_code = 'CLEWISTON-CITY-ZONED';
