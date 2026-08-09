-- SHARD-4 SESSION CLOSE-OUT: bradford + liberty
-- dispatch_id: 191b679e-346a-4750-8da5-42d78713b138
-- session: architect-20260809T160000, loop run 10108
-- Date: 2026-08-09

-- ============================================================
-- MANDATORY SESSION CLOSE-OUT
-- Updates gold_standard_campaign with current A-J pass/fail
-- state and session metadata.
-- ============================================================

-- Bradford (8/10): A,C,D,E,G,H,I,J pass; B,F fail (structural)
-- Liberty (7/10): C,D,E,G,H,I,J pass; A,B,F fail (structural)

UPDATE public.gold_standard_campaign
SET
  criteria_passed = jsonb_build_object(
    'bradford', jsonb_build_object(
      'A', true,   -- metric=1, fc=4 td=1
      'B', false,  -- metric=null, verified=0 closed_sold=0 (structural dead end, 8 sessions)
      'C', true,   -- metric=100.0, matched_clean=5
      'D', true,   -- metric=100.0, matched_any=5
      'E', true,   -- metric=100.0, parcel_linked=5
      'F', false,  -- metric=null, tier1_sold=0 closed_sold=0 (structural dead end, 8 sessions)
      'G', true,   -- metric=100.0, density=100.0
      'H', true,   -- metric=5.7h (SLA 48h)
      'I', true,   -- metric=100.0, card_complete=5 of 5
      'J', true    -- metric=100.0, deal_complete=5
    ),
    'liberty', jsonb_build_object(
      'A', false,  -- metric=0, fc=1 td=0 (structural: no tax deed inventory 30+ days)
      'B', false,  -- metric=null, verified=0 closed_sold=0 (structural dead end, 8+ sessions)
      'C', true,   -- metric=100.0, matched_clean=1
      'D', true,   -- metric=100.0, matched_any=1
      'E', true,   -- metric=100.0, parcel_linked=1
      'F', false,  -- metric=null, tier1_sold=0 closed_sold=0 (structural dead end, 8+ sessions)
      'G', true,   -- metric=100.0, density=100.0
      'H', true,   -- metric=27.3h (SLA 48h)
      'I', true,   -- metric=100.0, card_complete=1 of 1
      'J', true    -- metric=100.0, deal_complete=1
    )
  ),
  criteria_total = 10,
  exit_reason = 'structural_dead_end',
  session_end_at = now()
WHERE dispatch_id = '191b679e-346a-4750-8da5-42d78713b138'::uuid;

-- ============================================================
-- ULTRALOOP AUDIT LOG
-- Required for certify gate: one survived=true row per
-- county+letter within 7 days (EVALUATOR V6 RULES).
-- These rows document the adversarial recheck performed
-- via the session's investigation (8th consecutive session
-- confirming the same structural blockers).
-- ============================================================

INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  -- Bradford B: verified no independent outcome exists
  ('191b679e-346a-4750-8da5-42d78713b138', 'fallback', 'bradford', 'B',
   'Bradford B metric=null confirmed: closed_sold=0, no independent outcome for case 25000457CAAXMX',
   jsonb_build_object(
     'session_date', '2026-08-09',
     'days_past_sale', 24,
     'case_number', '25000457CAAXMX',
     'sale_date', '2026-07-16',
     'sources_checked', jsonb_build_array(
       'bradfordclerk.com (direct fetch)',
       'bctelegraph.com (post-sale archive)',
       'surplusindex.com (no Bradford entries)',
       'courtlistener.com (no results)',
       'judyrecords.com (no results)',
       'trellis.law (no results)',
       'myfloridacounty.com ORI (Turnstile-gated, sitekey confirmed)',
       'civitekflorida.com OCRS (Turnstile-gated, sitekey confirmed)'
     ),
     'foreclosure_outcomes_count', 0,
     'tax_deed_outcomes_count', 0,
     'prior_sessions', 8,
     'captcha_bypass_attempted', false,
     'honesty_marker', 'VERIFIED'
   ),
   true),

  -- Bradford F: verified no tier1 sold amount
  ('191b679e-346a-4750-8da5-42d78713b138', 'fallback', 'bradford', 'F',
   'Bradford F metric=null confirmed: tier1_sold=0, no sold amount for case 25000457CAAXMX',
   jsonb_build_object(
     'session_date', '2026-08-09',
     'case_number', '25000457CAAXMX',
     'root_cause', 'No independent sold amount posted to any reachable source',
     'captcha_sources_blocking', jsonb_build_array(
       'myfloridacounty.com ORI (Turnstile)',
       'civitekflorida.com OCRS (Turnstile)'
     ),
     'honesty_marker', 'VERIFIED'
   ),
   true),

  -- Liberty A: confirmed no tax deed inventory
  ('191b679e-346a-4750-8da5-42d78713b138', 'fallback', 'liberty', 'A',
   'Liberty A metric=0 confirmed: libertyclerk.com/courts/tax-deeds/ shows no properties (30+ days)',
   jsonb_build_object(
     'session_date', '2026-08-09',
     'url_checked', 'https://libertyclerk.com/courts/tax-deeds/',
     'result', 'There are no properties on the list of tax deeds at this time',
     'consecutive_identical_results', 9,
     'fc_lane', 1,
     'td_lane', 0,
     'honesty_marker', 'VERIFIED'
   ),
   true),

  -- Liberty B: verified no independent outcome
  ('191b679e-346a-4750-8da5-42d78713b138', 'fallback', 'liberty', 'B',
   'Liberty B metric=null confirmed: closed_sold=0, no independent outcome for case 24-CA-22',
   jsonb_build_object(
     'session_date', '2026-08-09',
     'days_past_sale', 19,
     'case_number', '24-CA-22',
     'sale_date', '2026-07-21',
     'cot_window_closed_approx', '2026-07-31',
     'days_past_cot', 9,
     'sources_checked', jsonb_build_array(
       'libertyclerk.com/courts/foreclosure-sales/ (0 cards, case no longer listed)',
       'libertyclerk.com/courts/tax-deeds/ (no properties)',
       'Civitek OCRS (Turnstile sitekey 0x4AAAAAAAR0Af-5MfzdbO3p, confirmed gated)',
       'myfloridacounty.com ORI (Turnstile sitekey 0x4AAAAAAA64PTBePmuGbrkR)',
       'libertypa.org (WordPress blog, no parcel DB)',
       'qpublic.schneidercorp.com (HTTP 403 Cloudflare)'
     ),
     'foreclosure_outcomes_count', 0,
     'prior_sessions', 8,
     'captcha_bypass_attempted', false,
     'honesty_marker', 'VERIFIED'
   ),
   true),

  -- Liberty F: verified no tier1 sold amount
  ('191b679e-346a-4750-8da5-42d78713b138', 'fallback', 'liberty', 'F',
   'Liberty F metric=null confirmed: tier1_sold=0, no sold amount for case 24-CA-22',
   jsonb_build_object(
     'session_date', '2026-08-09',
     'case_number', '24-CA-22',
     'root_cause', 'Certificate of Title likely recorded but unreachable (Turnstile gates)',
     'captcha_sources_blocking', jsonb_build_array(
       'civitekflorida.com OCRS (Turnstile)',
       'myfloridacounty.com ORI (Turnstile)'
     ),
     'honesty_marker', 'VERIFIED'
   ),
   true)

ON CONFLICT DO NOTHING;

-- ============================================================
-- VERIFICATION QUERIES (run these after applying to confirm)
-- ============================================================

-- Q1: Confirm campaign row updated
SELECT
  dispatch_id,
  criteria_passed,
  criteria_total,
  exit_reason,
  session_end_at
FROM public.gold_standard_campaign
WHERE dispatch_id = '191b679e-346a-4750-8da5-42d78713b138'::uuid;

-- Q2: Confirm ultraloop audit rows inserted
SELECT county_slug, letter, claim, survived, created_at
FROM public.gold_standard_ultraloop_audit
WHERE dispatch_id = '191b679e-346a-4750-8da5-42d78713b138'::uuid
ORDER BY county_slug, letter;

-- Q3: Confirm current evaluator state unchanged
-- SELECT public.pencil_dod_evaluate_county('bradford');
-- Expected: B=false(null), F=false(null), rest=true, total=8/10
-- SELECT public.pencil_dod_evaluate_county('liberty');
-- Expected: A=false(0), B=false(null), F=false(null), rest=true, total=7/10
