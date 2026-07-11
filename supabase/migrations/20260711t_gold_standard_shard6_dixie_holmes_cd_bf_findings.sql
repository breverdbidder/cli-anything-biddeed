-- GOLD STANDARD shard-6 (dixie, holmes; dispatch f790053e-7def-44f4-914c-0af228ef16b1,
-- chat_session architect-20260711T160000): scoped integrity fix + pipeline metadata
-- correction, plus documented structural findings for C/D (dixie) and B/C/D/F (holmes)
-- after live re-verification of every available online source for both counties.
--
-- ============================================================================
-- FIX 1: DIXIE ghost-success recurrence (case 15-2023-CA-57)
-- ============================================================================
-- ROOT CAUSE (VERIFIED live 2026-07-11): this exact ghost was already purged once
-- (supabase/migrations/20260703_shard11_dixie_cd_fix.sql) -- an UPCOMING foreclosure
-- (auction_date=2026-07-21, status='upcoming', confirmed still "Scheduled" with no
-- sold amount on live https://dixieclerk.com/departments-services/court-services/
-- foreclosure-sales/ today) carrying parity_status='matched_clean' with
-- parity_source=NULL. It does NOT count toward the C/D numerator (evaluator requires
-- parity_source LIKE 'tier1%%'), so this has zero effect on the C/D metric either way
-- -- this is a data-integrity fix, not a metric-moving one.
--
-- The row's updated_at (2026-07-11 12:23:05 UTC, hours before this session) shows it
-- was re-touched by live fleet automation since the 07-03 purge, most likely
-- pg_cron job 204 'gold-calendar-parity-cycle' (*/5 * * * *) -> public.
-- promote_upcoming_tier1_cards() -> biddeed.flow_card_to_mca(), which appears to
-- stamp matched_clean on card promotion without checking for a real backing
-- tax_deed_outcomes/foreclosure_outcomes row. That function is SHARED across all 67
-- counties and touching it is out of scope for a dixie/holmes-scoped shard session
-- (PARALLEL-FLEET RULES) -- flagged here as a residual for a dedicated future session,
-- not silently left unfixed at the symptom layer only.
UPDATE public.multi_county_auctions
SET parity_status = NULL, parity_source = NULL, updated_at = now()
WHERE lower(county) = 'dixie'
  AND case_number = '15-2023-CA-57'
  AND parity_status = 'matched_clean'
  AND parity_source IS NULL;

-- ============================================================================
-- FIX 2: HOLMES pipeline.counties taxdeed platform metadata correction
-- ============================================================================
-- VERIFIED live 2026-07-11: https://holmes.realtaxdeed.com (both bare root and
-- /index.cfm?zaction=USER&zmethod=CALENDAR) 302-redirects off-host to the generic
-- https://www.realauction.com marketing homepage -- holmes tax deeds are NOT
-- actually live-hosted on RealAuction, despite pipeline.counties.taxdeed_platform
-- claiming 'realtaxdeed'. The real, live source is the WordPress-authored schedule
-- at https://holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/ (same clerk_html
-- pattern already correctly configured for holmes's foreclosure_platform/foreclosure_url).
-- This corrects the metadata so future sessions/dispatchers don't waste a cycle probing
-- a dead RealAuction subdomain for holmes tax deeds.
UPDATE pipeline.counties
SET taxdeed_platform = 'clerk_html',
    taxdeed_url = 'https://holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/'
WHERE county_slug = 'holmes'
  AND taxdeed_platform = 'realtaxdeed';

-- ============================================================================
-- STRUCTURAL FINDINGS (no further action possible this session -- BLANK > WRONG)
-- ============================================================================
-- DIXIE C/D: auctions_total=32, matched_clean=matched_any=24 (75.0%%, need >=31 to
-- pass 95%%). Of the 8 unmatched: 2 are genuinely future (2026-07-13 tax deed,
-- 2026-07-21 foreclosure -- the case fixed above) and cannot resolve today by
-- definition. The other 6 (tax deed sales 2025-08-12 x3, 2025-08-26 x3) were
-- live-refetched from dixieclerk.com's embedded JSON feed AND their archival PDF
-- sale lists (dixie-clerk.s3.amazonaws.com) today -- both sources still show
-- status="scheduled"/blank "Results of Sale" nearly a year after the sale date, an
-- unresolved inconsistency on the source site itself (same finding as the prior
-- 2026-07-10 session, re-confirmed, not stale). STRUCTURAL CEILING: even a perfect
-- resolution of all 6 caps matched=30/32=93.75%%, still under the 95%% threshold --
-- C/D CANNOT pass for dixie this session regardless of scraping effort, because the
-- 2 future auctions are baked into the denominator. Adversarially verified by 2
-- independent refuter agents (gold_standard_ultraloop_audit, letters C and D,
-- claim="dixie_cd_structural_ceiling_93_75pct").
--
-- HOLMES B/C/D/F: closed_sold=0 (all 13 auctions have sold_amount IS NULL), which
-- structurally blocks B and F regardless of match work (both divide by closed_sold).
-- Of 13 auctions, only 2 are past-dated: a foreclosure (2026-06-11, already
-- matched_clean via parcel) and a tax deed (TD#2023-225, 2026-07-07, unmatched).
-- Live-checked every available online source for a sold amount on either: (1)
-- holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/ shows judgment amount
-- only, no winning-bid/sold field, for the foreclosure; (2) holmesclerk.com/courts/
-- foreclosures-tax-deeds/tax-deeds/ is a forward-looking "Scheduled Sales" list only
-- (exactly the 5 already-matched future rows; TD#2023-225 and the other 4 unmatched
-- case numbers are absent, with zero occurrences of sold/redeemed/cancelled/results
-- text anywhere on the page); (3) lands-available-for-taxes/ (the unsold-parcel
-- fallback) explicitly has no LOLA files and does not list any of the 5 gap parcels;
-- (4) holmes.realtaxdeed.com is dead (fixed above); (5) myfloridacounty.com/
-- orisearch/30 (official records / Certificate of Title search, where a real sold
-- consideration could be found) is Cloudflare-Turnstile CAPTCHA-gated on every
-- search POST -- not scriptable. No legitimate online source publishes a sold
-- amount or a resolution for any of these 5-6 gap cases. B, C, D, F remain
-- correctly blocked at their current values pending manual phone/in-person Holmes
-- Clerk contact -- a human research task for a future session, not a scraper gap.
-- Adversarially verified by 2 independent refuter agents (gold_standard_ultraloop_audit,
-- letters B, C, D, F, claim="holmes_bcdf_no_online_source").
--
-- Verification (this session): SELECT public.pencil_dod_evaluate_county('dixie');
--                               SELECT public.pencil_dod_evaluate_county('holmes');
-- gold_standard_loop()/gold_standard_certify() NOT invoked (PARALLEL-FLEET RULES --
-- other shards may be mid-session).
