-- Variance AI Agent — Phase 1 MCP-precursor functions
-- Issue: breverdbidder/cli-anything-biddeed#19094
-- Spec: VARIANCE_AI_AGENT_METAPROMPT.md section 7 (2 of 6 tools, Phase 1 scope only)
-- SQL functions today; full MCP tool wrapping into mcp.zonewise.ai is a later issue.
-- jurisdiction param accepts the municode-slug form used throughout this mission
-- (e.g. 'cocoa_beach'), matched against jurisdictions.name normalized to that form.

CREATE OR REPLACE FUNCTION public.check_variance_eligibility(
  p_jurisdiction TEXT,
  p_variance_type TEXT
) RETURNS JSONB
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_jurisdiction_id BIGINT;
  v_jurisdiction_name TEXT;
  v_rule public.variance_jurisdiction_rules%ROWTYPE;
BEGIN
  SELECT id, name INTO v_jurisdiction_id, v_jurisdiction_name
  FROM public.jurisdictions
  WHERE lower(replace(name, ' ', '_')) = lower(p_jurisdiction)
  LIMIT 1;

  IF v_jurisdiction_id IS NULL THEN
    RETURN jsonb_build_object(
      'jurisdiction', p_jurisdiction,
      'variance_type', p_variance_type,
      'researched', false,
      'status', 'not_yet_researched',
      'message', format('Jurisdiction "%s" not found in jurisdictions table.', p_jurisdiction)
    );
  END IF;

  SELECT * INTO v_rule
  FROM public.variance_jurisdiction_rules
  WHERE jurisdiction_id = v_jurisdiction_id AND variance_type = p_variance_type
  LIMIT 1;

  IF NOT FOUND THEN
    RETURN jsonb_build_object(
      'jurisdiction', v_jurisdiction_name,
      'variance_type', p_variance_type,
      'researched', false,
      'status', 'not_yet_researched',
      'message', format('No variance_jurisdiction_rules row for %s / %s — this has not been researched yet, not confirmed prohibited.', v_jurisdiction_name, p_variance_type)
    );
  END IF;

  RETURN jsonb_build_object(
    'jurisdiction', v_jurisdiction_name,
    'variance_type', p_variance_type,
    'researched', true,
    'status', CASE WHEN v_rule.is_permitted THEN 'permitted' ELSE 'prohibited' END,
    'is_permitted', v_rule.is_permitted,
    'board_type', v_rule.board_type,
    'statutory_criteria_section', v_rule.statutory_criteria_section,
    'prohibition_note', v_rule.prohibition_note,
    'application_fee', v_rule.application_fee,
    'typical_timeline_weeks', v_rule.typical_timeline_weeks,
    'source_url', v_rule.source_url,
    'verified_at', v_rule.verified_at
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.find_variance_precedents(
  p_jurisdiction TEXT,
  p_variance_type TEXT,
  p_parcel_id TEXT DEFAULT NULL
) RETURNS TABLE (
  application_id BIGINT,
  address TEXT,
  parcel_id TEXT,
  case_status TEXT,
  vote_result TEXT,
  approval_date DATE,
  current_requirement TEXT,
  requested_relief TEXT,
  attorney TEXT
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_jurisdiction_id BIGINT;
BEGIN
  SELECT id INTO v_jurisdiction_id
  FROM public.jurisdictions
  WHERE lower(replace(name, ' ', '_')) = lower(p_jurisdiction)
  LIMIT 1;

  IF v_jurisdiction_id IS NULL THEN
    RETURN;
  END IF;

  RETURN QUERY
  SELECT va.id, va.address, va.parcel_id, va.case_status, va.vote_result,
         va.approval_date, va.current_requirement, va.requested_relief, va.attorney
  FROM public.variance_applications va
  WHERE va.jurisdiction_id = v_jurisdiction_id
    AND va.variance_type = p_variance_type
    AND (p_parcel_id IS NULL OR va.parcel_id IS DISTINCT FROM p_parcel_id)
  ORDER BY va.approval_date DESC NULLS LAST, va.id;
END;
$$;
