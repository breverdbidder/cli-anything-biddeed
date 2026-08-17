-- Personalized lead-audit card template (outreach + social, reusable design system).
-- Registers the new shared renderer (scripts/generate_lead_audit_card.py) in
-- ssot_registry_components per the SSOT-check-first rule (BIDDEED_SSOT.md /
-- established in #19130).
--
-- This is NOT the same component as social_banner_history (registered
-- 20260815_ssot_register_social_banner_history.sql, status='unused' -- that
-- is a table, not a renderer, and this script does not use it for Variant A;
-- Variant B does write to it to preserve the existing 7-day county-rotation
-- pattern). The daily-banner HTML/CSS render pipeline itself
-- (scripts/generate_daily_auction_banner.py) was never registered as a
-- component either -- confirmed live via
-- `SELECT * FROM ssot_registry_components WHERE component_name ILIKE '%banner%'`
-- returning only the social_banner_history table row. So this renderer does
-- not build on an already-registered component; it is registered fresh here.
INSERT INTO public.ssot_registry_components
  (project_key, layer, domain, component_name, source_catalog, source_ref, governance_tier, status, honesty_marker, notes)
SELECT 'biddeed_ai', 'workflow', 'social', 'lead_audit_card_renderer', 'internal_script', 'scripts/generate_lead_audit_card.py', 'active', 'active', 'VERIFIED',
   'Shared HTML/CSS/Playwright card renderer with two data-bound variants. Variant A (source_type=lead_audit_card_a): personalized per-lead card for source=auction_llc_expansion leads joined to multi_county_auctions on winning_bidder+county (auctions won, total sold_amount deployed, upcoming-30d count in-county); status=draft, email-attachment only, never auto-sent. Variant B (source_type=lead_audit_card_b): generic per-county card reusing social_banner_history 7-day rotation, real county-level aggregate stats (completed auctions tracked, upcoming count); status=draft, social-ready but not auto-posted (no LinkedIn OAuth). Reuses the navy #0B1929/orange #F97316/Inter render+upload(social-banners bucket)+social_content_queue-insert pipeline shipped in scripts/generate_daily_auction_banner.py (#19128/#19129/#19130). 10 Variant A + 1 Variant B card generated and verified live on 2026-08-17 (real PNG bytes downloaded and confirmed 1200x630, real DB-backed numbers, no fabricated data).'
WHERE NOT EXISTS (
  SELECT 1 FROM public.ssot_registry_components
  WHERE project_key = 'biddeed_ai' AND component_name = 'lead_audit_card_renderer'
);
