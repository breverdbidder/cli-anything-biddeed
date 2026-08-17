-- Fix #19174: persist bidder_activity_tier as a real column on lead_profiles.
-- The original #19174 brief referenced lead_profiles.bidder_activity_tier as
-- if it were a real column -- it never was, it was a one-off regex
-- classification computed transiently in an earlier chat-session query and
-- never persisted. As a result #19174 generated lead-audit cards for ALL
-- source='auction_llc_expansion' leads including institutional lenders
-- (FREEDOM MORTGAGE CORPORATION, LAKEVIEW LOAN SERVICING LLC -- confirmed
-- banks/servicers, not real BidDeed prospects).
--
-- Additive only (CC_META_PROMPT.md 3.4): new column, no existing column
-- altered or dropped. Backfill scoped to source='auction_llc_expansion' only
-- (288 rows); all other rows keep bidder_activity_tier NULL.

ALTER TABLE public.lead_profiles ADD COLUMN IF NOT EXISTS bidder_activity_tier text;

UPDATE public.lead_profiles
SET bidder_activity_tier = CASE
    WHEN name ~* '(HOMEOWNERS ASSOCIATION|CONDOMINIUM ASSOCIATION|PROPERTY OWNERS ASSOCIATION|MASTER ASSOCIATION|COMMUNITY ASSOCIATION|APARTMENTS ASSOCIATION)' THEN 'HOA_CONDO_ASSOCIATION'
    WHEN name ~* '(MARRIOTT|DISNEY|SHERATON|VISTANA|SILVERLEAF|HOLIDAY INN CLUB)' THEN 'RESORT_TIMESHARE_MAJOR'
    WHEN name ~* '(MORTGAGE|LOAN SERVIC|LENDING|LOAN FUNDER|SERVICING)' THEN 'INSTITUTIONAL_LENDER'
    WHEN name ~* ', LLC$| LLC$|, INC\.?$| INC\.?$|, L\.L\.C\.$|INCORPORATED$' THEN 'INVESTOR_LLC'
    ELSE 'OTHER'
  END,
  updated_at = now()
WHERE source = 'auction_llc_expansion';

-- Verified live 2026-08-17: INVESTOR_LLC=185, INSTITUTIONAL_LENDER=48,
-- HOA_CONDO_ASSOCIATION=44, RESORT_TIMESHARE_MAJOR=7, OTHER=4 (n=288 total,
-- matches the brief's 185 figure exactly). Re-running this UPDATE is a
-- deterministic no-op on the resulting tier values (verified by running
-- twice in-session).
