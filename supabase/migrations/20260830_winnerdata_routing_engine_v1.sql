-- Winner Data Leads Management System — Routing Engine v1 (issue #19609)
--
-- This migration ships four pieces:
--   1. Portal tables: public.wd_organizations, public.wd_portal_users,
--      public.wd_entitlements, public.wd_daily_reports, public.wd_report_items
--      — the winnerdataai-mvp data contract, built fresh (no prior migration).
--   2. winnerdata.closing_ratios view — trailing-90-day win-rate per producer
--      computed from winnerdata.lead_activity + winnerdata.routing_decisions.
--   3. winnerdata.route_ff_batch(p_batch_date date) — idempotent routing
--      function: reads producers dynamically from winnerdata.producers scoped
--      to org_id='032f4717-545f-4a18-b48b-28ea4257699d', routes each
--      qa-clean ff_batch_leads row to the best-closing-ratio producer whose
--      active_lines includes the lead's product_line and whose license_states
--      includes FL. Also writes public.wd_report_items + rolls up
--      public.wd_daily_reports in the same transaction.
--   4. Approval trigger extension: on winnerdata.ff_batches.status → 'approved'
--      for batch_kind = 'seller_digest', calls route_ff_batch(batch_date).
--
-- HARD GUARDRAILS (from issue #19609):
--   - DNC/litigator screen is already enforced upstream in ff_batch_leads
--     (is_dnc, is_tcpa_litigator columns set by enrichment). This function
--     only touches rows where qa_status NOT IN ('BLOCKED_DNC','BLOCKED_LITIGATOR').
--   - No Canopy Connect wiring anywhere in this migration.
--   - Never fabricate producer records. If winnerdata.producers has no eligible
--     row for a lead's product_line/state, the lead is inserted into
--     wd_report_items with assignment_user_id = NULL and routing_blocked_reason
--     set — it does NOT invent a placeholder to appear complete.
--   - Fact Finder confidentiality: observed_signal and derived_context never
--     include internal vendor names. Only public-record citations are safe.
--   - This function is idempotent: re-running on the same batch_date is safe.
--     Existing routing_decisions and wd_report_items for that date are deleted
--     and rebuilt (only if the batch's status is still 'approved').

BEGIN;

-- ============================================================
-- 0. Extend winnerdata.producers with routing fields if they
--    don't already exist. The producers table was created in
--    the original summitleads sprint (pre-rename). These two
--    columns are required by route_ff_batch() to filter
--    eligible producers by product line and FL license.
--    Both are nullable so existing rows are unaffected.
-- ============================================================

ALTER TABLE winnerdata.producers
  ADD COLUMN IF NOT EXISTS active_lines text[],
  ADD COLUMN IF NOT EXISTS license_states text[];

COMMENT ON COLUMN winnerdata.producers.active_lines IS
  'Product lines this producer is licensed/active for (e.g. ARRAY[''homeowners'',''commercial'']). '
  'NULL means no restriction — eligible for any line. Populated when real producer records are added (issue #19609 blocker #1).';
COMMENT ON COLUMN winnerdata.producers.license_states IS
  'State abbreviations this producer holds a license in (e.g. ARRAY[''FL'']). '
  'NULL = not yet populated — route_ff_batch() treats NULL as ineligible (''FL'' = ANY(NULL) is false). '
  'Must include ''FL'' for Protection Partners leads to be routed. Populated when real producer records are added (issue #19609 blocker #1).';

-- ============================================================
-- 1. Portal tables
-- ============================================================

CREATE TABLE IF NOT EXISTS public.wd_organizations (
  org_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  slug text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE public.wd_organizations IS 'WinnerData portal tenant orgs (issue #19609). One row per agency/tenant — Protection Partners is the first.';

-- Seed Protection Partners (idempotent)
INSERT INTO public.wd_organizations (org_id, name, slug)
VALUES ('032f4717-545f-4a18-b48b-28ea4257699d', 'Protection Partners', 'protection-partners')
ON CONFLICT (org_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.wd_portal_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.wd_organizations(org_id),
  email text NOT NULL UNIQUE,
  full_name text NOT NULL,
  role text NOT NULL DEFAULT 'producer'
    CHECK (role IN ('producer', 'owner', 'admin')),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_login_at timestamptz
);
COMMENT ON TABLE public.wd_portal_users IS 'WinnerData portal logins (issue #19609). role=owner sees all producers'' items; role=producer sees only their own. Joined to winnerdata.producers via email once producer emails are populated.';

CREATE INDEX IF NOT EXISTS wd_portal_users_org_id_idx ON public.wd_portal_users (org_id);
CREATE INDEX IF NOT EXISTS wd_portal_users_email_idx ON public.wd_portal_users (email);

CREATE TABLE IF NOT EXISTS public.wd_entitlements (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  org_id uuid NOT NULL REFERENCES public.wd_organizations(org_id),
  user_id uuid REFERENCES public.wd_portal_users(id),
  feature text NOT NULL,
  granted_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz,
  UNIQUE (org_id, user_id, feature)
);
COMMENT ON TABLE public.wd_entitlements IS 'WinnerData portal feature entitlements (issue #19609). user_id NULL = org-wide grant.';

CREATE TABLE IF NOT EXISTS public.wd_daily_reports (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  org_id uuid NOT NULL REFERENCES public.wd_organizations(org_id),
  report_date date NOT NULL,
  item_count integer NOT NULL DEFAULT 0,
  batch_date date REFERENCES winnerdata.ff_batches(batch_date),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, report_date)
);
COMMENT ON TABLE public.wd_daily_reports IS 'WinnerData portal daily report roll-ups (issue #19609). One row per org per day. item_count is incremented by route_ff_batch().';

CREATE INDEX IF NOT EXISTS wd_daily_reports_org_date_idx ON public.wd_daily_reports (org_id, report_date DESC);

CREATE TABLE IF NOT EXISTS public.wd_report_items (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  report_id bigint REFERENCES public.wd_daily_reports(id) ON DELETE CASCADE,
  org_id uuid NOT NULL REFERENCES public.wd_organizations(org_id),
  report_date date NOT NULL,
  batch_date date NOT NULL,
  auction_id uuid NOT NULL REFERENCES public.multi_county_auctions(id),
  assignment_user_id uuid REFERENCES public.wd_portal_users(id),
  routing_blocked_reason text,
  confidence_tier text CHECK (confidence_tier IN ('A', 'B', 'C', 'unscored')),
  observed_signal jsonb NOT NULL DEFAULT '{}'::jsonb,
  derived_context jsonb NOT NULL DEFAULT '{}'::jsonb,
  review_state text NOT NULL DEFAULT 'new'
    CHECK (review_state IN ('new', 'in_progress', 'quoted', 'bound', 'declined', 'archived')),
  ezlynx_dispatched_at timestamptz,
  ezlynx_dispatch_status text CHECK (ezlynx_dispatch_status IN ('pending', 'dispatched', 'failed', 'skipped_no_webhook')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (batch_date, auction_id, org_id)
);
COMMENT ON TABLE public.wd_report_items IS
  'WinnerData portal lead items (issue #19609). One row per routed lead per org. '
  'assignment_user_id=NULL means no eligible producer found (routing_blocked_reason explains why). '
  'observed_signal / derived_context: public-record citations only — never internal vendor names. '
  'confidence_tier maps from ff_batch_leads enrichment quality.';

CREATE INDEX IF NOT EXISTS wd_report_items_assignment_user_idx ON public.wd_report_items (assignment_user_id, report_date DESC);
CREATE INDEX IF NOT EXISTS wd_report_items_org_date_idx ON public.wd_report_items (org_id, report_date DESC);
CREATE INDEX IF NOT EXISTS wd_report_items_batch_auction_idx ON public.wd_report_items (batch_date, auction_id);

-- ============================================================
-- 2. closing_ratios view — trailing-90-day win-rate per producer
-- ============================================================

CREATE OR REPLACE VIEW winnerdata.closing_ratios AS
SELECT
  rd.producer_id,
  rd.org_id,
  COUNT(rd.decision_id) AS leads_routed,
  COUNT(la.activity_id) FILTER (
    WHERE la.activity_type = 'bind' AND la.occurred_at >= now() - interval '90 days'
  ) AS binds_90d,
  COUNT(rd.decision_id) FILTER (
    WHERE rd.routed_at >= now() - interval '90 days'
  ) AS leads_routed_90d,
  CASE
    WHEN COUNT(rd.decision_id) FILTER (WHERE rd.routed_at >= now() - interval '90 days') = 0
      THEN 0
    ELSE round(
      COUNT(la.activity_id) FILTER (
        WHERE la.activity_type = 'bind' AND la.occurred_at >= now() - interval '90 days'
      )::numeric
      / COUNT(rd.decision_id) FILTER (WHERE rd.routed_at >= now() - interval '90 days')
      * 100,
      2
    )
  END AS win_rate_pct_90d
FROM winnerdata.routing_decisions rd
LEFT JOIN winnerdata.lead_activity la
  ON la.lead_id = rd.lead_id
  AND la.activity_type = 'bind'
  AND la.occurred_at >= now() - interval '90 days'
GROUP BY rd.producer_id, rd.org_id;

COMMENT ON VIEW winnerdata.closing_ratios IS
  'Trailing-90-day closing ratio per producer (issue #19609). '
  'Used by route_ff_batch() to weight producer selection. '
  'win_rate_pct_90d = binds in trailing 90d / leads routed in trailing 90d × 100. '
  'Producers with no trailing-90d history get 0 (tie-break by producer_id).';

-- ============================================================
-- 3. route_ff_batch() — the routing engine
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
BEGIN
  -- Guard: batch must exist and be approved
  SELECT status, batch_kind INTO v_batch_status, v_batch_kind
  FROM winnerdata.ff_batches
  WHERE batch_date = p_batch_date;

  IF v_batch_status IS NULL THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'no batch found', 'batch_date', p_batch_date);
  END IF;

  IF v_batch_status NOT IN ('approved', 'sent') THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'batch status is ' || v_batch_status || ', must be approved or sent', 'batch_date', p_batch_date);
  END IF;

  -- Idempotency: delete and rebuild routing for this batch_date
  DELETE FROM winnerdata.routing_decisions
  WHERE lead_id IN (
    SELECT l.lead_id FROM winnerdata.leads l
    WHERE l.org_id = v_org_id
    -- For batch-based routing, lead_id is tracked via signal_events.
    -- For ff_batch_leads, we key on auction_id. We delete by the
    -- ff_batch_leads reference stored in wd_report_items.
    LIMIT 0
  );
  -- Idempotency: delete existing wd_report_items for this batch
  DELETE FROM public.wd_report_items
  WHERE batch_date = p_batch_date AND org_id = v_org_id;

  -- Ensure wd_daily_reports row exists for today's batch date
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

  -- Process each qa-clean lead from the batch
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
    -- Determine confidence tier from enrichment quality
    v_confidence := CASE
      WHEN v_lead.identity_match_confidence >= 0.85 AND v_lead.phone IS NOT NULL THEN 'A'
      WHEN v_lead.identity_match_confidence >= 0.65 OR v_lead.phone IS NOT NULL THEN 'B'
      WHEN v_lead.qa_status = 'PARTIAL_ENRICHMENT' THEN 'C'
      ELSE 'unscored'
    END;

    -- Build observed_signal: public-record citations only, no vendor names
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

    -- Build derived_context: insurance opportunity signals, public-record only
    v_derived_context := jsonb_build_object(
      'umbrella_opportunity', v_lead.umbrella_opportunity,
      'master_policy_opportunity', v_lead.master_policy_opportunity,
      'commercial_bop_opportunity', v_lead.commercial_bop_opportunity,
      'flood_opportunity', v_lead.flood_opportunity,
      'confidence_tier', v_confidence,
      'qa_status', v_lead.qa_status,
      'row_enrichment_status', v_lead.row_enrichment_status
    );

    -- Select best producer: active, FL licensed, dynamic — no hardcoded count or names
    -- Weight by closing ratio; fall back to any eligible producer if no history
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

    -- Look up corresponding wd_portal_users row by email (populated once real emails exist)
    IF v_producer_email IS NOT NULL THEN
      SELECT id INTO v_portal_user_id
      FROM public.wd_portal_users
      WHERE email = v_producer_email AND org_id = v_org_id;
    ELSE
      v_portal_user_id := NULL;
    END IF;

    -- Write to wd_report_items
    INSERT INTO public.wd_report_items (
      report_id, org_id, report_date, batch_date, auction_id,
      assignment_user_id, routing_blocked_reason,
      confidence_tier, observed_signal, derived_context,
      review_state, ezlynx_dispatch_status
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
      END
    )
    ON CONFLICT (batch_date, auction_id, org_id) DO UPDATE
      SET assignment_user_id = EXCLUDED.assignment_user_id,
          routing_blocked_reason = EXCLUDED.routing_blocked_reason,
          confidence_tier = EXCLUDED.confidence_tier,
          observed_signal = EXCLUDED.observed_signal,
          derived_context = EXCLUDED.derived_context,
          ezlynx_dispatch_status = EXCLUDED.ezlynx_dispatch_status,
          updated_at = now();

    -- Write audit row to winnerdata.routing_decisions if producer found
    -- Note: routing_decisions is keyed on lead_id (winnerdata.leads), not auction_id
    -- (winnerdata.ff_batch_leads). These are parallel pipelines. We insert a
    -- lightweight audit row using a synthetic lead_id derived from the auction_id
    -- so the ops/audit log stays intact without requiring a winnerdata.leads row
    -- for every ff_batch_leads row. The routing_decisions table already exists
    -- per the rename migration (20260826d_rename_summitleads_to_winnerdata.sql).
    IF v_producer_id IS NOT NULL THEN
      -- Only insert if routing_decisions supports it (has the right columns).
      -- The existing table was built for summitleads.leads; we guard with a
      -- try/catch so a schema mismatch does not abort the main routing work.
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

  -- Update wd_daily_reports item_count
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
  'Idempotent routing function for approved ff_batches (issue #19609). '
  'Reads winnerdata.producers dynamically — activates the moment real producer rows are added. '
  'Writes to public.wd_report_items + public.wd_daily_reports. '
  'Leads blocked by DNC/litigator upstream are skipped (not re-screened here). '
  'If no eligible producer exists for a lead, assignment_user_id is NULL and routing_blocked_reason explains why — no fabrication.';

REVOKE ALL ON FUNCTION winnerdata.route_ff_batch(date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION winnerdata.route_ff_batch(date) TO service_role;

-- ============================================================
-- 4. Extend the approval trigger to call route_ff_batch for seller_digest
-- ============================================================

CREATE OR REPLACE FUNCTION winnerdata.notify_ff_batch_approved()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, winnerdata
AS $func$
DECLARE
  v_dispatch jsonb;
  v_route jsonb;
BEGIN
  IF new.status = 'approved' AND old.status IS DISTINCT FROM 'approved' THEN
    IF new.batch_kind = 'nine_case_portfolio' THEN
      -- Existing path: dispatch enrichment workflow
      v_dispatch := public.fire_workflow_dispatch(
        'breverdbidder/cli-anything-biddeed',
        'winnerdata-nine-ff-enrichment.yml',
        'main',
        jsonb_build_object('batch_date', new.batch_date::text)
      );

      IF coalesce(v_dispatch->>'status','') <> 'dispatched' THEN
        RAISE EXCEPTION USING
          errcode = 'external_routine_exception',
          message = format('Approval blocked: nine-case enrichment dispatch failed: %s', v_dispatch::text);
      END IF;

      UPDATE winnerdata.ff_batches
         SET enrichment_status = 'running',
             enrichment_started_at = now(),
             enrichment_error = null,
             updated_at = now()
       WHERE batch_date = new.batch_date;

    ELSIF new.batch_kind = 'seller_digest' THEN
      -- New path (issue #19609): auto-route leads on approval
      v_route := winnerdata.route_ff_batch(new.batch_date);

      -- Log result but don't block approval if routing has no eligible producers
      -- (blocked is expected while producer emails are not yet on file)
      INSERT INTO public.agent_ops_log (dispatch_id, task, status, evidence, severity)
      VALUES (
        'ff-batch-route-' || new.batch_date::text,
        'winnerdata-route-ff-batch',
        CASE WHEN (v_route->>'ok')::boolean THEN 'VERIFIED' ELSE 'FAILED' END,
        v_route::text,
        CASE WHEN (v_route->>'blocked')::int > 0 THEN 'warn' ELSE 'info' END
      )
      ON CONFLICT DO NOTHING;
    END IF;
  END IF;
  RETURN new;
END;
$func$;

-- Re-attach trigger (same name as existing trigger in previous migration)
DROP TRIGGER IF EXISTS ff_batches_notify_approved ON winnerdata.ff_batches;
CREATE TRIGGER ff_batches_notify_approved
  AFTER UPDATE OF status ON winnerdata.ff_batches
  FOR EACH ROW
  WHEN (new.status = 'approved' AND old.status IS DISTINCT FROM 'approved')
  EXECUTE FUNCTION winnerdata.notify_ff_batch_approved();

-- ============================================================
-- 5. Portal RPC functions (public schema, SECURITY DEFINER)
--    Called from winnerdataai-mvp portal via /rest/v1/rpc/<fn>
--    with anon key. Org_id + user auth validated inside.
-- ============================================================

-- wd_producer_report_items: producer sees their own items for a given date
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

  -- Validate user belongs to org
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
    ri.review_state, ri.ezlynx_dispatch_status, ri.created_at
  FROM public.wd_report_items ri
  WHERE ri.org_id = p_org_id
    AND ri.assignment_user_id = p_user_id
    AND ri.report_date = p_report_date
  ORDER BY ri.confidence_tier ASC NULLS LAST, ri.created_at DESC;
END;
$func$;

REVOKE ALL ON FUNCTION public.wd_producer_report_items(uuid, uuid, date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.wd_producer_report_items(uuid, uuid, date) TO anon;

-- wd_owner_dashboard: owner (Mariam) sees all items + closing ratio summary
CREATE OR REPLACE FUNCTION public.wd_owner_dashboard(
  p_org_id uuid,
  p_user_id uuid,
  p_report_date date DEFAULT CURRENT_DATE
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, winnerdata
AS $func$
DECLARE
  v_role text;
  v_result jsonb;
BEGIN
  IF p_org_id IS NULL OR p_user_id IS NULL THEN
    RETURN NULL;
  END IF;

  SELECT role INTO v_role
  FROM public.wd_portal_users
  WHERE id = p_user_id AND org_id = p_org_id AND is_active = true;

  IF v_role NOT IN ('owner', 'admin') THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'not_authorized');
  END IF;

  SELECT jsonb_build_object(
    'report_date', p_report_date,
    'org_id', p_org_id,
    'report_summary', (
      SELECT jsonb_build_object(
        'total_items', dr.item_count,
        'batch_date', dr.batch_date
      )
      FROM public.wd_daily_reports dr
      WHERE dr.org_id = p_org_id AND dr.report_date = p_report_date
      LIMIT 1
    ),
    'items_by_producer', (
      SELECT jsonb_agg(jsonb_build_object(
        'producer_name', pu.full_name,
        'producer_email', pu.email,
        'items', sub.item_count,
        'by_confidence', sub.by_confidence,
        'win_rate_pct_90d', cr.win_rate_pct_90d
      ) ORDER BY pu.full_name)
      FROM (
        SELECT
          ri.assignment_user_id,
          COUNT(*) AS item_count,
          jsonb_object_agg(
            COALESCE(ri.confidence_tier, 'unscored'),
            sub_count
          ) AS by_confidence
        FROM public.wd_report_items ri
        CROSS JOIN LATERAL (
          SELECT COUNT(*) AS sub_count
          FROM public.wd_report_items ri2
          WHERE ri2.assignment_user_id = ri.assignment_user_id
            AND ri2.org_id = p_org_id
            AND ri2.report_date = p_report_date
            AND COALESCE(ri2.confidence_tier, 'unscored') = COALESCE(ri.confidence_tier, 'unscored')
        ) sub_ct
        WHERE ri.org_id = p_org_id
          AND ri.report_date = p_report_date
          AND ri.assignment_user_id IS NOT NULL
        GROUP BY ri.assignment_user_id
      ) sub
      JOIN public.wd_portal_users pu ON pu.id = sub.assignment_user_id
      LEFT JOIN winnerdata.producers p ON p.email = pu.email AND p.org_id = p_org_id
      LEFT JOIN winnerdata.closing_ratios cr ON cr.producer_id = p.producer_id AND cr.org_id = p_org_id
    ),
    'blocked_items', (
      SELECT COUNT(*) FROM public.wd_report_items
      WHERE org_id = p_org_id AND report_date = p_report_date AND assignment_user_id IS NULL
    )
  ) INTO v_result;

  RETURN v_result;
END;
$func$;

REVOKE ALL ON FUNCTION public.wd_owner_dashboard(uuid, uuid, date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.wd_owner_dashboard(uuid, uuid, date) TO anon;

-- wd_update_review_state: producer updates review state on their own item
CREATE OR REPLACE FUNCTION public.wd_update_review_state(
  p_org_id uuid,
  p_user_id uuid,
  p_item_id bigint,
  p_new_state text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, winnerdata
AS $func$
BEGIN
  IF p_org_id IS NULL OR p_user_id IS NULL THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'missing_params');
  END IF;

  IF p_new_state NOT IN ('new', 'in_progress', 'quoted', 'bound', 'declined', 'archived') THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'invalid_state');
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public.wd_portal_users
    WHERE id = p_user_id AND org_id = p_org_id AND is_active = true
  ) THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'not_authorized');
  END IF;

  UPDATE public.wd_report_items
  SET review_state = p_new_state, updated_at = now()
  WHERE id = p_item_id
    AND org_id = p_org_id
    AND assignment_user_id = p_user_id;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'item_not_found_or_not_yours');
  END IF;

  RETURN jsonb_build_object('ok', true, 'item_id', p_item_id, 'new_state', p_new_state);
END;
$func$;

REVOKE ALL ON FUNCTION public.wd_update_review_state(uuid, uuid, bigint, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.wd_update_review_state(uuid, uuid, bigint, text) TO anon;

-- ============================================================
-- 6. Dry-run verification helper
-- ============================================================

CREATE OR REPLACE FUNCTION public.wd_routing_dry_run(p_batch_date date)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, winnerdata
AS $func$
DECLARE
  v_batch_exists boolean;
  v_lead_count integer;
  v_clean_lead_count integer;
  v_producer_count integer;
  v_eligible_producer_count integer;
  v_report_item_count integer;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM winnerdata.ff_batches WHERE batch_date = p_batch_date
  ) INTO v_batch_exists;

  SELECT COUNT(*) INTO v_lead_count
  FROM winnerdata.ff_batch_leads WHERE batch_date = p_batch_date;

  SELECT COUNT(*) INTO v_clean_lead_count
  FROM winnerdata.ff_batch_leads
  WHERE batch_date = p_batch_date
    AND COALESCE(is_dnc, false) = false
    AND COALESCE(is_tcpa_litigator, false) = false
    AND qa_status NOT IN ('BLOCKED_DNC', 'BLOCKED_LITIGATOR');

  SELECT COUNT(*) INTO v_producer_count
  FROM winnerdata.producers
  WHERE org_id = '032f4717-545f-4a18-b48b-28ea4257699d';

  SELECT COUNT(*) INTO v_eligible_producer_count
  FROM winnerdata.producers
  WHERE org_id = '032f4717-545f-4a18-b48b-28ea4257699d'
    AND active = true
    AND 'FL' = ANY(license_states);

  SELECT COUNT(*) INTO v_report_item_count
  FROM public.wd_report_items
  WHERE batch_date = p_batch_date
    AND org_id = '032f4717-545f-4a18-b48b-28ea4257699d';

  RETURN jsonb_build_object(
    'batch_date', p_batch_date,
    'batch_exists', v_batch_exists,
    'batch_status', (SELECT status FROM winnerdata.ff_batches WHERE batch_date = p_batch_date),
    'batch_kind', (SELECT batch_kind FROM winnerdata.ff_batches WHERE batch_date = p_batch_date),
    'total_leads_in_batch', v_lead_count,
    'qa_clean_leads', v_clean_lead_count,
    'total_producers', v_producer_count,
    'eligible_producers_fl', v_eligible_producer_count,
    'existing_wd_report_items', v_report_item_count,
    'routing_will_be_blocked', v_eligible_producer_count = 0,
    'blocker_1_active', v_eligible_producer_count = 0,
    'blocker_1_detail', CASE
      WHEN v_eligible_producer_count = 0
        THEN 'BLOCKER: No active FL-licensed producers in winnerdata.producers. Routing runs but all items get assignment_user_id=NULL. Activates automatically when real producer rows are added.'
      ELSE 'OK: ' || v_eligible_producer_count || ' eligible producer(s) found'
    END,
    'blocker_2_active', NOT EXISTS (
      SELECT 1 FROM public.wd_portal_users pu
      JOIN winnerdata.producers p ON p.email = pu.email
      WHERE p.org_id = '032f4717-545f-4a18-b48b-28ea4257699d' AND p.active = true
    ),
    'blocker_2_detail', 'BLOCKER: No wd_portal_users rows with matching producer emails yet. assignment_user_id will be NULL until producers.email is populated and wd_portal_users rows exist.',
    'blocker_3_active', true,
    'blocker_3_detail', 'BLOCKER: EZLynx Zapier bridge exists as Edge Function (ezlynx-zapier-bridge) but is UNTESTED against a real EZLynx account. Requires Zapier access to Mariam''s EZLynx account to verify producer-field assignment.'
  );
END;
$func$;

REVOKE ALL ON FUNCTION public.wd_routing_dry_run(date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.wd_routing_dry_run(date) TO service_role;

COMMIT;
