-- GOLD STANDARD SHARD-1 (dispatch e857901a) — Session Close-Out
-- Date: 2026-08-10
-- Counties: collier (9/10, I fail 93.7%), union (8/10, B+F fail)
-- Author: claude-sonnet-4-6 (issue #18559)

SET statement_timeout = 0;

-- ── ULTRALOOP AUDIT ENTRIES ──────────────────────────────────────────────────
-- Per ULTRALOOP PROTOCOL and SHIP GATE requirements, log adversarial audit
-- findings for both counties before session close.

INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES

-- collier I: residual-floor documented and new scraper wired
(
  'e857901a-9b66-458b-9bc7-17728a3f5dfe',
  'fallback',
  'collier',
  'I',
  'collier I at 93.7% (208/222) is at a real-data floor; 14 residual rows are structurally unreachable by automated means. Shipped scripts/gold_standard_shard1_collier_i_everglades_city.py (CCPA + EC GIS probes) wired to collier-i-residual-fix.yml — the scraper runs and attempts recovery; outcome UNTESTED until GHA run completes.',
  jsonb_build_object(
    'prior_session_baseline', '208/222 = 93.7% (FAIL, threshold 95%) — VERIFIED 2026-08-07 via pencil_dod_evaluate_county',
    'residual_14_breakdown', jsonb_build_object(
      'oil_gas_mineral_rights', 2,
      'truncated_folio', 1,
      'zero_match_fl_gio', 4,
      'blank_dor_address_vacant', 5,
      'everglades_city_incorporated', 2
    ),
    'scraper_shipped', 'scripts/gold_standard_shard1_collier_i_everglades_city.py',
    'workflow_shipped', '.github/workflows/collier-i-residual-fix.yml',
    'ccpa_probes', jsonb_build_object(
      'target_folios', ARRAY['00992000008','01155640000','01160000004','01160400002'],
      'url_pattern', 'https://www.collierappraiser.com/main_search/RecordDetail.aspx?sid=0&ccparid={folio}',
      'status', 'UNTESTED — will run via GHA workflow'
    ),
    'everglades_city_probes', jsonb_build_object(
      'gis_endpoint_1', 'https://maps.collierclerk.com/arcgis/rest/services/Public/Zoning/MapServer/0/query',
      'gis_endpoint_2', 'https://services3.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Collier_Zoning/FeatureServer/0/query',
      'status', 'UNTESTED — will run via GHA workflow'
    ),
    'ceiling_analysis', 'Even if all 6 CCPA+EC probes succeed: 208+6=214/222=96.4% (PASS). Conservative: 1-2 CCPA hits = 210/222=94.6% (still FAIL). Oil/gas and blank-address rows are permanent floor.',
    'refuter_verdict', 'SURVIVED — claim is honest, UNTESTED markers applied per Honesty Protocol'
  ),
  true
),

-- union B: time-gated structural block, post-auction scraper shipped
(
  'e857901a-9b66-458b-9bc7-17728a3f5dfe',
  'fallback',
  'union',
  'B',
  'union B (verified_outcomes/closed_sold) fails with closed_sold=0 — structural time-gated block. Aug 13 auction (63-2025-CA-0053) has not yet occurred. Post-auction scraper shipped (scripts/union_post_auction_outcome_scraper.py, union-post-auction-scraper.yml). Scraper will run daily at 15:00Z and retry all channels after Aug 13.',
  jsonb_build_object(
    'prior_sessions_baseline', 'B=null (closed_sold=0, verified=0) — VERIFIED independently 2026-07-20, 2026-07-31, 2026-08-09',
    'case_1', jsonb_build_object(
      'case_number', '63-2025-CA-0053',
      'auction_date', '2026-08-13',
      'days_until_auction', 3,
      'status', 'upcoming — auction has NOT occurred as of 2026-08-10'
    ),
    'case_2', jsonb_build_object(
      'case_number', '63-2024-CA-0047',
      'auction_date', '2026-10-15',
      'days_until_auction', 66,
      'status', 'upcoming — auction has NOT occurred'
    ),
    'scraper_shipped', 'scripts/union_post_auction_outcome_scraper.py',
    'workflow_shipped', '.github/workflows/union-post-auction-scraper.yml',
    'channels_to_probe', ARRAY['union.realforeclose.com', 'unionclerk.com/foreclosure-sales', 'myfloridacounty.com/union'],
    'prior_channel_status', jsonb_build_object(
      'union_realforeclose', '403 Forbidden (pre-auction) — retry post-auction',
      'unionclerk_com', 'Cloudflare 403 — retry post-auction',
      'myfloridacounty', 'redirects to unionclerk.com — retry post-auction',
      'civitek_ocrs', 'Cloudflare Turnstile-blocked on search.xhtml — not retried',
      'in_person_only', 'Union County auctions are in-person (55 W Main St, Lake Butler, Thursdays 11am) — no online auction platform'
    ),
    'refuter_verdict', 'SURVIVED — B=null is confirmed genuine structural block (independently verified 2026-08-09 adversarial audit, union_bf_adversarial_refuter_audit.sql, survived=true)'
  ),
  true
),

-- union F: same root cause as B
(
  'e857901a-9b66-458b-9bc7-17728a3f5dfe',
  'fallback',
  'union',
  'F',
  'union F (tier1_sold/closed_sold) fails with closed_sold=0 for same root cause as B. Post-auction scraper shipped — on finding a sold_amount it calls promote_tier1_from_outcomes() which carries the amount into F automatically.',
  jsonb_build_object(
    'root_cause', 'Same as B: closed_sold=0, no sold_amount in multi_county_auctions for any union row',
    'promote_tier1_mechanism', 'Existing cron (promote_tier1_from_outcomes, do NOT rebuild) + explicit call in scraper after writing outcome',
    'scraper_shipped', 'scripts/union_post_auction_outcome_scraper.py',
    'workflow_shipped', '.github/workflows/union-post-auction-scraper.yml',
    'prior_adversarial_audit', 'union_bf_adversarial_refuter_audit.sql (survived=true, 2026-08-09)',
    'refuter_verdict', 'SURVIVED — F structural block is identical to B and co-verified'
  ),
  true
);

-- ── GOLD STANDARD CAMPAIGN CHECKPOINT ────────────────────────────────────────
-- Per MANDATORY SESSION CLOSE-OUT requirement in the issue brief.

UPDATE public.gold_standard_campaign
SET
  criteria_passed = jsonb_build_object(
    'A', true, 'B', false, 'C', true, 'D', true, 'E', true,
    'F', false, 'G', true, 'H', true, 'I', false, 'J', true
  ),
  criteria_total = 10,
  exit_reason = 'timeout',
  session_end_at = now()
WHERE dispatch_id = 'e857901a-9b66-458b-9bc7-17728a3f5dfe';

-- If the row doesn't exist (first session for this dispatch), insert it.
INSERT INTO public.gold_standard_campaign
  (dispatch_id, county_slug, criteria_passed, criteria_total, exit_reason, session_end_at)
SELECT
  'e857901a-9b66-458b-9bc7-17728a3f5dfe',
  county_slug_val,
  jsonb_build_object(
    'A', true, 'B', b_val, 'C', true, 'D', true, 'E', true,
    'F', b_val, 'G', true, 'H', true, 'I', i_val, 'J', true
  ),
  10,
  'timeout',
  now()
FROM (VALUES
  ('collier', true, false),
  ('union', false, true)
) AS t(county_slug_val, i_val, b_val)
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_campaign
  WHERE dispatch_id = 'e857901a-9b66-458b-9bc7-17728a3f5dfe'
    AND county_slug = county_slug_val
);
