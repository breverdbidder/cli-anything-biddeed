-- Issue #18307 — S5 v1.2 interactive HTML report route.
--
-- Additive only: new column on s5_pdf_cache + a gated SECURITY DEFINER RPC
-- so the Cloudflare Worker (anon key only, no service-role secret bound)
-- can resolve "does this API key own this report?" without a broad RLS
-- grant on s5_pdf_cache. Confirmed live 2026-08-06: anon SELECT on
-- s5_pdf_cache returns zero rows (RLS blocks it) while mcp_api_keys is
-- already anon-readable — this mirrors the existing claim_key_for_session
-- RPC pattern rather than opening new table-level access.
--
-- report_json caches the buildReport() JSON produced by the ONE billed
-- predict_auction_outcome call stripe-webhook already makes at purchase
-- time (v9 deliverReportPdf) — the Worker route reads this column instead
-- of calling the MCP tool per page-view, which would re-charge $25 on every
-- report view (predict_auction_outcome idempotency is keyed off a per-call
-- JSON-RPC request id, not case_number+county, so repeat page loads are NOT
-- deduped against the original purchase call).

ALTER TABLE public.s5_pdf_cache ADD COLUMN IF NOT EXISTS report_json JSONB;

CREATE OR REPLACE FUNCTION public.get_s5_report_access(p_key_hash text, p_mca_id text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $function$
DECLARE
  v_customer_id uuid;
  v_mca_id uuid;
  v_key_active boolean;
  v_row public.s5_pdf_cache%ROWTYPE;
BEGIN
  IF p_key_hash IS NULL OR p_mca_id IS NULL THEN
    RETURN jsonb_build_object('ok', false, 'error', 'invalid_request');
  END IF;

  BEGIN
    v_mca_id := p_mca_id::uuid;
  EXCEPTION WHEN invalid_text_representation THEN
    RETURN jsonb_build_object('ok', false, 'error', 'invalid_request');
  END;

  SELECT customer_id, (active AND is_active) INTO v_customer_id, v_key_active
  FROM public.mcp_api_keys
  WHERE key_hash = p_key_hash
  LIMIT 1;

  IF v_customer_id IS NULL OR NOT COALESCE(v_key_active, false) THEN
    RETURN jsonb_build_object('ok', false, 'error', 'invalid_key');
  END IF;

  SELECT * INTO v_row
  FROM public.s5_pdf_cache
  WHERE mca_id = v_mca_id AND customer_id = v_customer_id
  LIMIT 1;

  IF v_row.mca_id IS NULL THEN
    RETURN jsonb_build_object('ok', false, 'error', 'no_purchase');
  END IF;

  RETURN jsonb_build_object(
    'ok', true,
    'customer_id', v_row.customer_id,
    'report_json', v_row.report_json,
    'generated_at', v_row.generated_at,
    'is_outcome_complete', v_row.is_outcome_complete,
    'auction_status_at_generation', v_row.auction_status_at_generation
  );
END;
$function$;

GRANT EXECUTE ON FUNCTION public.get_s5_report_access(text, text) TO anon, authenticated;
