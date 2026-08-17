-- Fix #19174 followup: correct the ssot_registry_components notes for
-- lead_audit_card_renderer (registered 20260817_ssot_register_lead_audit_card_renderer.sql).
-- The original notes claimed "10 Variant A ... card generated and verified
-- live" without disclosing that the population was unfiltered
-- source='auction_llc_expansion' (288 rows, including institutional
-- lenders). This corrects the record: bidder_activity_tier is now a real
-- persisted column (see 20260817b_lead_profiles_bidder_activity_tier.sql)
-- and Variant A generation is scoped to bidder_activity_tier='INVESTOR_LLC'
-- only.
UPDATE public.ssot_registry_components
SET notes = 'Shared HTML/CSS/Playwright card renderer with two data-bound variants. Variant A (source_type=lead_audit_card_a): personalized per-lead card for lead_profiles rows with source=auction_llc_expansion AND bidder_activity_tier=''INVESTOR_LLC'' (real persisted column, regex-classified, backfilled 2026-08-17 -- see 20260817b_lead_profiles_bidder_activity_tier.sql), joined to multi_county_auctions on winning_bidder+county (auctions won, total sold_amount deployed, upcoming-30d count in-county); status=draft, email-attachment only, never auto-sent. Variant B (source_type=lead_audit_card_b): generic per-county card reusing social_banner_history 7-day rotation, real county-level aggregate stats (completed auctions tracked, upcoming count); status=draft, social-ready but not auto-posted (no LinkedIn OAuth). Reuses the navy #0B1929/orange #F97316/Inter render+upload(social-banners bucket)+social_content_queue-insert pipeline shipped in scripts/generate_daily_auction_banner.py (#19128/#19129/#19130). CORRECTION 2026-08-17 (issue #19174 followup): the original 10 Variant A cards generated 2026-08-17 01:11 UTC used an unfiltered source=auction_llc_expansion population (288 rows) that included institutional lenders (FREEDOM MORTGAGE CORPORATION, LAKEVIEW LOAN SERVICING LLC); 5 of those 10 were wrong and were deleted (queue rows + storage objects) same day. bidder_activity_tier is now a real persisted column; live counts for source=auction_llc_expansion (n=288): INVESTOR_LLC=185, INSTITUTIONAL_LENDER=48, HOA_CONDO_ASSOCIATION=44, RESORT_TIMESHARE_MAJOR=7, OTHER=4. Card generation is now scoped to INVESTOR_LLC only; 10 new correctly-scoped cards generated 2026-08-17 01:26 UTC, for a total of 15 correct INVESTOR_LLC-only Variant A cards live in social_content_queue (all status=draft, none ever auto-published).',
    updated_at = now()
WHERE project_key = 'biddeed_ai' AND component_name = 'lead_audit_card_renderer';
