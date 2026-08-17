-- Centralize the lead <-> multi_county_auctions "auctions won / total deployed"
-- computation into ONE reusable view (SMS-channel + join-fix task, #19176
-- follow-through, 2026-08-17).
--
-- ROOT CAUSE (verified live, not guessed): a prior ad-hoc query in another
-- chat session joined `ON mca.winning_bidder = lp.name` -- exact string
-- equality, no case-fold, no county scope, no auction_date bound. Live
-- comparison against the 60 INVESTOR_LLC leads with a skip-traced phone
-- number:
--   buggy_zero_won   = 42 of 60 (naive exact-match join)
--   fixed_nonzero_won = 19 of 60 (case/whitespace-insensitive + county-scoped join)
--   won_count actually differs on 3 leads (AMERICAN PRIME LLC 0->2,
--     HOLLYGROVE DEVELOPMENT LLC 0->1, NEW VISTA PROPERTIES INC 2->0 --
--     the last one is a false-positive fix: an exact-name match against a
--     DIFFERENT county's auction, only caught once county scoping was added)
--   total_deployed recovers real dollars on 6 leads where sold_amount was
--     NULL but tier1_sold_amount (the authoritative post-close figure) was
--     populated -- e.g. DANIEL VARGO LLC: $0/NULL -> $150,100.
-- Sample confirmed root cause for the case mismatches: lead_profiles.name is
-- upper-cased ("AMERICAN PRIME, LLC"), multi_county_auctions.winning_bidder
-- retains title case ("American Prime, LLC") -- same string, different case,
-- so `=` fails and `upper(trim(x))=upper(trim(y))` succeeds.
--
-- This exact corrected join already existed independently inside
-- scripts/generate_lead_audit_card.py's VARIANT_A_SAMPLE_SQL (#19174/#19175)
-- -- this migration promotes that logic to a single shared view so every
-- consumer (cards, email, SMS if/when built, countdown-cron) reads the same
-- numbers instead of each hand-rolling the join.
CREATE OR REPLACE VIEW public.lead_auction_activity AS
SELECT
  lp.id                    AS lead_id,
  lp.name,
  lp.county,
  lp.bidder_activity_tier,
  COUNT(mca.id)                                            AS auctions_won,
  SUM(COALESCE(mca.tier1_sold_amount, mca.sold_amount))    AS total_deployed
FROM public.lead_profiles lp
LEFT JOIN public.multi_county_auctions mca
  ON upper(trim(mca.winning_bidder)) = upper(trim(lp.name))
 AND mca.county = lp.county
 AND mca.auction_date <= CURRENT_DATE
GROUP BY lp.id, lp.name, lp.county, lp.bidder_activity_tier;

COMMENT ON VIEW public.lead_auction_activity IS
  'Single source of truth for per-lead auctions_won/total_deployed. Case/whitespace-insensitive, county-scoped, past-sales-only join against multi_county_auctions.winning_bidder. Replaces ad-hoc per-script joins (#19176 join-fix task). auctions_won=0 is a real zero (no NOT EXISTS/HAVING filter here -- callers filter as needed, e.g. HAVING auctions_won > 0 for card generation). total_deployed NULL means no dollar figure was ever captured on a real matched win, not $0.';

INSERT INTO public.ssot_registry_components
  (project_key, layer, domain, component_name, source_catalog, source_ref, governance_tier, status, honesty_marker, notes)
SELECT 'biddeed_ai', 'table', 'leads', 'lead_auction_activity_view', 'internal_view', 'supabase/migrations/20260817d_lead_auction_activity_view.sql', 'active', 'active', 'VERIFIED',
  'Reusable view: per-lead auctions_won + total_deployed, joining lead_profiles to multi_county_auctions on case/whitespace-insensitive winning_bidder + county + auction_date<=today. Fixes a naive exact-match join bug found live in a prior ad-hoc query (42/60 INVESTOR_LLC phone leads showed auctions_won=0 under the naive join vs 19/60 with a real match under this view; 3 leads had wrong won-counts corrected, one of them -- NEW VISTA PROPERTIES INC -- was a false positive from missing county scoping; 6 leads recovered a real total_deployed dollar figure via tier1_sold_amount coalesce). Intended consumers: scripts/generate_lead_audit_card.py Variant A, scripts/skiptrace_lead_email_send.py, any future SMS send script, countdown-cron personalization if/when it adds won/deployed stats. Verified live 2026-08-17 via Supabase Management API against 60 real INVESTOR_LLC leads.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.ssot_registry_components
  WHERE project_key = 'biddeed_ai' AND component_name = 'lead_auction_activity_view'
);
