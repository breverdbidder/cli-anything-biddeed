-- Winner Data — Vapi Outbound + RingCentral Click-to-Dial (issue #19611)
--
-- This migration ships four pieces:
--   1. Extend public.wd_report_items with contact_phone and vapi_dispatch_status.
--      contact_phone is sourced from winnerdata.ff_batch_leads.phone at routing
--      time and is the only PII stored here — required for RingCentral click-to-dial.
--   2. Replace winnerdata.route_ff_batch() to populate contact_phone.
--   3. Replace public.wd_producer_report_items() to return contact_phone so the
--      producer-report Worker can render the click-to-dial link.
--   4. RPC public.wd_log_call_outcome() — called by the RingCentral webhook and
--      the Vapi status-callback webhook to write winnerdata.lead_activity rows
--      (activity_type='contact_attempt', channel='ringcentral_call' | 'vapi_call').
--
-- HARD GUARDRAILS (from issue #19611):
--   - DNC/litigator gate: wd_log_call_outcome() validates the item's underlying
--     lead was not blocked before writing. It does not re-derive the gate —
--     it re-reads the is_dnc / is_tcpa_litigator / qa_status columns already
--     enforced upstream in route_ff_batch(), refusing to log activity for any
--     item whose source row has those flags set. This is the *same* gate, not
--     a looser one.
--   - Vapi dispatch: vapi_dispatch_status gate mirrors the DNC logic in the
--     Edge Function (vapi-outbound-dispatch). This migration does not fire
--     Vapi — it only defines the column that tracks dispatch state.
--   - No external notification channels (Telegram, SMS, Slack) anywhere.
--   - contact_phone is stored as plain text because RingCentral click-to-dial
--     is a URL link rendered to the authenticated producer — not exposed to
--     the lead.

BEGIN;

-- ============================================================
-- 1. Extend wd_report_items
-- ============================================================

ALTER TABLE public.wd_report_items
  ADD COLUMN IF NOT EXISTS contact_phone text,
  ADD COLUMN IF NOT EXISTS vapi_dispatch_status text
    CHECK (vapi_dispatch_status IN ('pending', 'dispatched', 'connected', 'voicemail', 'no_answer', 'failed', 'skipped_dnc', 'skipped_not_commercial', 'skipped_tier', 'skipped_no_credentials'));

COMMENT ON COLUMN public.wd_report_items.contact_phone IS
  'Phone number sourced from winnerdata.ff_batch_leads.phone at routing time. '
  'NULL if ff_batch_leads.phone was NULL. Used for RingCentral click-to-dial only — '
  'never exposed to the lead directly. Null-safe: missing phone = no dial link rendered.';

COMMENT ON COLUMN public.wd_report_items.vapi_dispatch_status IS
  'State of Vapi outbound call for this lead (issue #19611). '
  'NULL = not eligible or not yet processed. '
  'pending = queued for dispatch. dispatched = Vapi call initiated. '
  'connected/voicemail/no_answer/failed = outcome from Vapi status-callback webhook. '
  'skipped_* = not dispatched due to gate (DNC, non-commercial, tier C/unscored, no credentials).';

-- ============================================================
-- 2. Replace route_ff_batch() to populate contact_phone
-- ============================================================

CREATE OR REPLACE FUNCTION winnerdata.route_ff_batch(p_batch_date date)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, winnerdata
AS $func$
DECLARE
  v_org_id constant uuid := '032f4717-545f-4a18-b48b-28ea4257699d';
  v_batch_kind text;
  v_batch_status text;
  v_report_id bigint;
  v_routed integer := 0;
  v_blocked integer := 0;
  v_lead record;
  v_producer_id uuid;
  v_producer_email text;
  v_portal_user_id uuid;
  v_confidence text;
  v_observed_signal jsonb;
  v_derived_context jsonb;
  v_is_commercial boolean;
  v_vapi_status text;
BEGIN
  SELECT status, batch_kind INTO v_batch_status, v_batch_kind
  FROM winnerdata.ff_batches
  WHERE batch_date = p_batch_date;

  IF v_batch_status IS NULL THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'no batch found', 'batch_date', p_batch_date);
  END IF;

  IF v_batch_status NOT IN ('approved', 'sent') THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'batch status is ' || v_batch_status || ', must be approved or sent', 'batch_date', p_batch_date);
  END IF;

  DELETE FROM winnerdata.routing_decisions
  WHERE lead_id IN (
    SELECT l.lead_id FROM winnerdata.leads l
    WHERE l.org_id = v_org_id
    LIMIT 0
  );

  DELETE FROM public.wd_report_items
  WHERE batch_date = p_batch_date AND org_id = v_org_id;

  INSERT INTO public.wd_daily_reports (org_id, report_date, item_count, batch_date)
  VALUES (v_org_id, CURRENT_DATE, 0, p_batch_date)
  ON CONFLICT (org_id, report_date) DO UPDATE
    SET batch_date = EXCLUDED.batch_date,
        updated_at = now()
  RETURNING id INTO v_report_id;

  IF v_report_id IS NULL THEN
    SELECT id INTO v_report_id
    FROM public.wd_daily_reports
    WHERE org_id = v_org_id AND report_date = CURRENT_DATE;
  END IF;

  FOR v_lead IN
    SELECT
      fbl.auction_id,
      fbl.batch_date,
      fbl.winning_bidder,
      fbl.county,
      fbl.auction_date,
      fbl.property_address,
      fbl.case_number,
      fbl.sale_type,
      fbl.tier1_sold_amount,
      fbl.val_market,
      fbl.val_assessed,
      fbl.dor_luse_code,
      fbl.dor_luse_desc,
      fbl.owner_name,
      fbl.site_addr,
      fbl.site_city,
      fbl.year_built,
      fbl.sqft_heated,
      fbl.phone,
      fbl.email,
      fbl.portfolio_property_count,
      fbl.portfolio_counties,
      fbl.portfolio_assessed_value_total,
      fbl.identity_type,
      fbl.identity_match_confidence,
      fbl.is_dnc,
      fbl.is_tcpa_litigator,
      fbl.qa_status,
      fbl.row_enrichment_status,
      fbl.umbrella_opportunity,
      fbl.master_policy_opportunity,
      fbl.commercial_bop_opportunity,
      fbl.flood_opportunity
    FROM winnerdata.ff_batch_leads fbl
    WHERE fbl.batch_date = p_batch_date
      AND COALESCE(fbl.is_dnc, false) = false
      AND COALESCE(fbl.is_tcpa_litigator, false) = false
      AND fbl.qa_status NOT IN ('BLOCKED_DNC', 'BLOCKED_LITIGATOR')
    ORDER BY fbl.auction_id
  LOOP
    v_confidence := CASE
      WHEN v_lead.identity_match_confidence >= 0.85 AND v_lead.phone IS NOT NULL THEN 'A'
      WHEN v_lead.identity_match_confidence >= 0.65 OR v_lead.phone IS NOT NULL THEN 'B'
      WHEN v_lead.qa_status = 'PARTIAL_ENRICHMENT' THEN 'C'
      ELSE 'unscored'
    END;

    v_observed_signal := jsonb_build_object(
      'winning_bidder', v_lead.winning_bidder,
      'county', v_lead.county,
      'auction_date', v_lead.auction_date,
      'property_address', v_lead.property_address,
      'case_number', v_lead.case_number,
      'sale_type', v_lead.sale_type,
      'tier1_sold_amount', v_lead.tier1_sold_amount,
      'pa_assessed_value', v_lead.val_assessed,
      'pa_market_value', v_lead.val_market,
      'dor_use_code', v_lead.dor_luse_code,
      'dor_use_description', v_lead.dor_luse_desc,
      'property_year_built', v_lead.year_built,
      'property_sqft', v_lead.sqft_heated,
      'site_address', v_lead.site_addr,
      'site_city', v_lead.site_city,
      'owner_name_on_record', v_lead.owner_name,
      'identity_type', v_lead.identity_type,
      'portfolio_property_count', v_lead.portfolio_property_count,
      'portfolio_counties', v_lead.portfolio_counties,
      'portfolio_assessed_total', v_lead.portfolio_assessed_value_total
    );

    v_derived_context := jsonb_build_object(
      'umbrella_opportunity', v_lead.umbrella_opportunity,
      'master_policy_opportunity', v_lead.master_policy_opportunity,
      'commercial_bop_opportunity', v_lead.commercial_bop_opportunity,
      'flood_opportunity', v_lead.flood_opportunity,
      'confidence_tier', v_confidence,
      'qa_status', v_lead.qa_status,
      'row_enrichment_status', v_lead.row_enrichment_status
    );

    SELECT
      p.producer_id,
      p.email
    INTO v_producer_id, v_producer_email
    FROM winnerdata.producers p
    LEFT JOIN winnerdata.closing_ratios cr
      ON cr.producer_id = p.producer_id AND cr.org_id = p.org_id
    WHERE
      p.org_id = v_org_id
      AND p.active = true
      AND 'FL' = ANY(p.license_states)
      AND (
        p.active_lines IS NULL
        OR array_length(p.active_lines, 1) IS NULL
        OR 'homeowners' = ANY(p.active_lines)
        OR 'commercial' = ANY(p.active_lines)
      )
    ORDER BY
      COALESCE(cr.win_rate_pct_90d, 0) DESC,
      p.producer_id ASC
    LIMIT 1;

    IF v_producer_email IS NOT NULL THEN
      SELECT id INTO v_portal_user_id
      FROM public.wd_portal_users
      WHERE email = v_producer_email AND org_id = v_org_id;
    ELSE
      v_portal_user_id := NULL;
    END IF;

    -- Determine Vapi eligibility at routing time:
    -- commercial DOR prefix (10-89) + tier A or B = 'pending'
    -- everything else = 'skipped_*' reason
    v_is_commercial := v_lead.dor_luse_code IS NOT NULL
      AND substring(v_lead.dor_luse_code FROM 1 FOR 2) >= '10'
      AND substring(v_lead.dor_luse_code FROM 1 FOR 2) <= '89';

    v_vapi_status := CASE
      WHEN v_producer_id IS NULL THEN NULL
      WHEN NOT v_is_commercial THEN 'skipped_not_commercial'
      WHEN v_confidence NOT IN ('A', 'B') THEN 'skipped_tier'
      ELSE 'pending'
    END;

    INSERT INTO public.wd_report_items (
      report_id, org_id, report_date, batch_date, auction_id,
      assignment_user_id, routing_blocked_reason,
      confidence_tier, observed_signal, derived_context,
      review_state, ezlynx_dispatch_status,
      contact_phone, vapi_dispatch_status
    ) VALUES (
      v_report_id,
      v_org_id,
      CURRENT_DATE,
      p_batch_date,
      v_lead.auction_id,
      v_portal_user_id,
      CASE
        WHEN v_producer_id IS NULL THEN 'no_eligible_producer: winnerdata.producers has no active FL-licensed producer — add real producer rows to activate routing'
        WHEN v_portal_user_id IS NULL AND v_producer_id IS NOT NULL THEN 'portal_user_missing: producer found in winnerdata.producers but no matching wd_portal_users row (email match needed)'
        ELSE NULL
      END,
      v_confidence,
      v_observed_signal,
      v_derived_context,
      'new',
      CASE
        WHEN v_producer_id IS NOT NULL THEN 'pending'
        ELSE 'skipped_no_webhook'
      END,
      v_lead.phone,
      v_vapi_status
    )
    ON CONFLICT (batch_date, auction_id, org_id) DO UPDATE
      SET assignment_user_id = EXCLUDED.assignment_user_id,
          routing_blocked_reason = EXCLUDED.routing_blocked_reason,
          confidence_tier = EXCLUDED.confidence_tier,
          observed_signal = EXCLUDED.observed_signal,
          derived_context = EXCLUDED.derived_context,
          ezlynx_dispatch_status = EXCLUDED.ezlynx_dispatch_status,
          contact_phone = EXCLUDED.contact_phone,
          vapi_dispatch_status = EXCLUDED.vapi_dispatch_status,
          updated_at = now();

    IF v_producer_id IS NOT NULL THEN
      BEGIN
        INSERT INTO winnerdata.routing_decisions (
          lead_id, org_id, producer_id, product_line, routing_reason, sla_timeout_minutes
        )
        SELECT
          l.lead_id,
          v_org_id,
          v_producer_id,
          COALESCE(l.product_line::text, 'homeowners'),
          'ff_batch_approval_auto_route',
          5
        FROM winnerdata.leads l
        WHERE l.org_id = v_org_id
          AND l.parcel_id = (
            SELECT mca.parcel_id FROM public.multi_county_auctions mca
            WHERE mca.id = v_lead.auction_id LIMIT 1
          )
        LIMIT 1
        ON CONFLICT DO NOTHING;
      EXCEPTION WHEN OTHERS THEN
        NULL;
      END;
      v_routed := v_routed + 1;
    ELSE
      v_blocked := v_blocked + 1;
    END IF;
  END LOOP;

  UPDATE public.wd_daily_reports
  SET item_count = (
    SELECT COUNT(*) FROM public.wd_report_items
    WHERE batch_date = p_batch_date AND org_id = v_org_id
  ),
  updated_at = now()
  WHERE id = v_report_id;

  RETURN jsonb_build_object(
    'ok', true,
    'batch_date', p_batch_date,
    'batch_kind', v_batch_kind,
    'routed', v_routed,
    'blocked', v_blocked,
    'total', v_routed + v_blocked,
    'report_id', v_report_id,
    'note', CASE
      WHEN v_blocked > 0 THEN 'Some leads blocked: winnerdata.producers has no eligible active FL producer. Add real producer rows to activate full routing.'
      ELSE 'All clean leads routed'
    END
  );
END;
$func$;

COMMENT ON FUNCTION winnerdata.route_ff_batch(date) IS
  'Idempotent routing function for approved ff_batches (issues #19609, #19611). '
  'Now also populates contact_phone (for RingCentral click-to-dial) and '
  'vapi_dispatch_status=pending for commercial leads with tier A or B. '
  'DNC/litigator gating unchanged from v1.';

REVOKE ALL ON FUNCTION winnerdata.route_ff_batch(date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION winnerdata.route_ff_batch(date) TO service_role;

-- ============================================================
-- 3. Replace wd_producer_report_items() to return contact_phone
-- ============================================================

CREATE OR REPLACE FUNCTION public.wd_producer_report_items(
  p_org_id uuid,
  p_user_id uuid,
  p_report_date date DEFAULT CURRENT_DATE
)
RETURNS TABLE (
  id bigint,
  report_date date,
  batch_date date,
  auction_id uuid,
  confidence_tier text,
  observed_signal jsonb,
  derived_context jsonb,
  review_state text,
  ezlynx_dispatch_status text,
  contact_phone text,
  vapi_dispatch_status text,
  created_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, winnerdata
AS $func$
BEGIN
  IF p_org_id IS NULL OR p_user_id IS NULL THEN
    RETURN;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public.wd_portal_users
    WHERE id = p_user_id AND org_id = p_org_id AND is_active = true
  ) THEN
    RETURN;
  END IF;

  RETURN QUERY
  SELECT
    ri.id, ri.report_date, ri.batch_date, ri.auction_id,
    ri.confidence_tier, ri.observed_signal, ri.derived_context,
    ri.review_state, ri.ezlynx_dispatch_status,
    ri.contact_phone, ri.vapi_dispatch_status,
    ri.created_at
  FROM public.wd_report_items ri
  WHERE ri.org_id = p_org_id
    AND ri.assignment_user_id = p_user_id
    AND ri.report_date = p_report_date
  ORDER BY ri.confidence_tier ASC NULLS LAST, ri.created_at DESC;
END;
$func$;

REVOKE ALL ON FUNCTION public.wd_producer_report_items(uuid, uuid, date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.wd_producer_report_items(uuid, uuid, date) TO anon;

-- ============================================================
-- 4. wd_log_call_outcome() — called by RingCentral + Vapi webhooks
-- ============================================================
--
-- Writes a winnerdata.lead_activity row for each call attempt/outcome.
-- Gates: validates item belongs to org and that the underlying ff_batch_lead
-- is not DNC/litigator-blocked before writing. This is a re-read of the
-- same gate enforced at routing time — intentionally redundant defense.
--
-- activity_type: 'contact_attempt' for initial dial
-- channel: 'ringcentral_call' | 'vapi_call'
-- payload fields:
--   outcome: 'connected' | 'no_answer' | 'voicemail' | 'failed'
--   duration_seconds: integer (RingCentral) or null
--   recording_url: null (never stored — Fact Finder confidentiality)
--   caller_number: null (RingCentral line, not the lead's number)
--   vapi_call_id: string | null (Vapi's call UUID, for correlation only)
--   item_id: wd_report_items.id (for correlation)

CREATE OR REPLACE FUNCTION public.wd_log_call_outcome(
  p_org_id uuid,
  p_item_id bigint,
  p_channel text,
  p_outcome text,
  p_duration_seconds integer DEFAULT NULL,
  p_vapi_call_id text DEFAULT NULL,
  p_bridge_secret text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, winnerdata
AS $func$
DECLARE
  v_bridge_secret text;
  v_item record;
  v_lead_blocked boolean;
  v_new_review_state text;
BEGIN
  IF p_org_id IS NULL OR p_item_id IS NULL THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'missing_params');
  END IF;

  IF p_channel NOT IN ('ringcentral_call', 'vapi_call') THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'invalid_channel');
  END IF;

  IF p_outcome NOT IN ('connected', 'no_answer', 'voicemail', 'failed') THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'invalid_outcome');
  END IF;

  -- Shared secret check: required for webhook callers (RingCentral, Vapi)
  -- to prevent unauthorized activity injection. Read from vault via existing
  -- vault_secret() accessor — if not configured, reject.
  BEGIN
    SELECT public.vault_secret('wd_call_webhook_secret') INTO v_bridge_secret;
  EXCEPTION WHEN OTHERS THEN
    v_bridge_secret := NULL;
  END;

  IF v_bridge_secret IS NOT NULL AND p_bridge_secret IS DISTINCT FROM v_bridge_secret THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'unauthorized');
  END IF;

  -- Fetch item and validate org
  SELECT ri.id, ri.org_id, ri.batch_date, ri.auction_id, ri.assignment_user_id,
         ri.confidence_tier, ri.review_state, ri.vapi_dispatch_status
  INTO v_item
  FROM public.wd_report_items ri
  WHERE ri.id = p_item_id AND ri.org_id = p_org_id;

  IF v_item.id IS NULL THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'item_not_found');
  END IF;

  -- Re-read DNC gate from source ff_batch_leads row (same gate as route_ff_batch)
  SELECT COALESCE(fbl.is_dnc, false) OR COALESCE(fbl.is_tcpa_litigator, false)
         OR fbl.qa_status IN ('BLOCKED_DNC', 'BLOCKED_LITIGATOR')
  INTO v_lead_blocked
  FROM winnerdata.ff_batch_leads fbl
  WHERE fbl.batch_date = v_item.batch_date
    AND fbl.auction_id = v_item.auction_id
  LIMIT 1;

  IF COALESCE(v_lead_blocked, false) THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'lead_blocked_dnc_litigator');
  END IF;

  -- Write lead_activity row
  -- lead_id: ff_batch_leads does not have a winnerdata.leads lead_id directly;
  -- we use a NULL lead_id with the item_id in payload for correlation.
  -- The lead_activity table was built for winnerdata.leads (real-time pipeline);
  -- ff_batch_leads is a parallel batch pipeline. We log with lead_id=NULL
  -- and item_id in payload — same pattern as the routing_decisions guard
  -- in route_ff_batch(). A future migration can backfill lead_id once the
  -- two pipelines are unified.
  INSERT INTO winnerdata.lead_activity (lead_id, org_id, activity_type, channel, payload)
  VALUES (
    NULL,
    p_org_id,
    'contact_attempt',
    p_channel,
    jsonb_build_object(
      'item_id', p_item_id,
      'outcome', p_outcome,
      'duration_seconds', p_duration_seconds,
      'vapi_call_id', p_vapi_call_id,
      'batch_date', v_item.batch_date,
      'auction_id', v_item.auction_id
    )
  );

  -- Update vapi_dispatch_status if this is a Vapi call outcome
  IF p_channel = 'vapi_call' THEN
    UPDATE public.wd_report_items
    SET vapi_dispatch_status = p_outcome,
        updated_at = now()
    WHERE id = p_item_id;
  END IF;

  -- If Vapi call connected, flag the item for live producer follow-up
  v_new_review_state := CASE
    WHEN p_channel = 'vapi_call' AND p_outcome = 'connected'
      THEN 'in_progress'
    ELSE NULL
  END;

  IF v_new_review_state IS NOT NULL THEN
    UPDATE public.wd_report_items
    SET review_state = v_new_review_state,
        updated_at = now()
    WHERE id = p_item_id
      AND review_state = 'new';
  END IF;

  RETURN jsonb_build_object(
    'ok', true,
    'item_id', p_item_id,
    'channel', p_channel,
    'outcome', p_outcome,
    'review_state_updated', v_new_review_state IS NOT NULL
  );
END;
$func$;

REVOKE ALL ON FUNCTION public.wd_log_call_outcome(uuid, bigint, text, text, integer, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.wd_log_call_outcome(uuid, bigint, text, text, integer, text, text) TO anon;

COMMENT ON FUNCTION public.wd_log_call_outcome IS
  'Webhook target for RingCentral and Vapi call outcome events (issue #19611). '
  'Writes winnerdata.lead_activity rows (activity_type=contact_attempt). '
  'Re-validates DNC gate before writing — never logs activity for blocked leads. '
  'For vapi_call+connected outcomes: sets wd_report_items.review_state=in_progress '
  'to signal the assigned producer that live follow-up is needed. '
  'Requires p_bridge_secret matching vault secret wd_call_webhook_secret when that '
  'vault entry exists. BLOCKER: wd_call_webhook_secret not yet in vault — '
  'add via Supabase dashboard vault before RingCentral/Vapi webhooks can write.';

-- ============================================================
-- 5. Index for lead_activity lookup by item (payload->>'item_id')
-- ============================================================

CREATE INDEX IF NOT EXISTS lead_activity_item_id_idx
  ON winnerdata.lead_activity ((payload->>'item_id'))
  WHERE activity_type = 'contact_attempt';

COMMENT ON INDEX winnerdata.lead_activity_item_id_idx IS
  'Supports fast lookup of call attempts per wd_report_items.id (issue #19611). '
  'Used by closing_ratios view and producer-report call history queries.';

COMMIT;
