-- TOKEN-OPT-01: codify record_session_cache_metrics() + cc_session_cost.run_id
-- unique index into the repo. Both objects were already live in Supabase with
-- no corresponding migration file (repo/DB drift found during this session's
-- inspection step) -- this migration brings the repo back in sync with what
-- is already running. CREATE OR REPLACE / IF NOT EXISTS throughout: no-op on
-- a DB that already has these objects, creates them on one that doesn't.
--
-- BUGFIX (this session, live-tested): the pre-existing function's
-- `ON CONFLICT (run_id)` did not match cc_session_cost_run_id_idx, which is a
-- PARTIAL unique index (`WHERE run_id IS NOT NULL`). Postgres requires the
-- ON CONFLICT clause to carry the same WHERE predicate to infer a partial
-- index as the arbiter -- without it, EVERY call to this function errored
-- with 42P10 "no unique or exclusion constraint matching the ON CONFLICT
-- specification". Reproduced live: `SELECT record_session_cache_metrics(...)`
-- failed before this fix. This is the likely root cause of cc_session_cost
-- .cache_read_tokens / .cache_write_tokens being always 0 -- nothing that
-- called this function could ever have succeeded.

CREATE OR REPLACE FUNCTION public.record_session_cache_metrics(
  p_run_id text,
  p_issue integer,
  p_model text,
  p_cache_read bigint,
  p_cache_write bigint,
  p_input bigint,
  p_output bigint
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
  v_hit_pct    numeric;
  v_cost_usd   numeric;
  v_result     jsonb;
BEGIN
  -- Cache hit rate
  v_hit_pct := CASE
    WHEN (p_cache_read + p_cache_write) > 0
    THEN round(p_cache_read::numeric / (p_cache_read + p_cache_write) * 100, 1)
    ELSE NULL
  END;

  -- Cost estimate (Sonnet 5 introductory pricing, model-agnostic fallback)
  v_cost_usd := round(
    (p_input::numeric * 2.0
     + p_cache_read::numeric * 0.20
     + p_cache_write::numeric * 4.0
     + p_output::numeric * 10.0)
    / 1000000.0,
    6
  );

  -- Upsert cc_session_cost
  INSERT INTO cc_session_cost (
    run_id, issue_number, model,
    cache_read_tokens, cache_write_tokens,
    input_tokens, output_tokens,
    cost_usd, conclusion
  )
  VALUES (
    p_run_id, p_issue, p_model,
    p_cache_read, p_cache_write,
    p_input, p_output,
    v_cost_usd, 'reported'
  )
  ON CONFLICT (run_id) WHERE (run_id IS NOT NULL) DO UPDATE SET
    cache_read_tokens  = EXCLUDED.cache_read_tokens,
    cache_write_tokens = EXCLUDED.cache_write_tokens,
    input_tokens       = EXCLUDED.input_tokens,
    output_tokens      = EXCLUDED.output_tokens,
    cost_usd           = EXCLUDED.cost_usd,
    model              = EXCLUDED.model,
    conclusion         = CASE
                           WHEN cc_session_cost.conclusion IN ('success','failure')
                           THEN cc_session_cost.conclusion
                           ELSE 'reported'
                         END;

  -- Log to agent_ops_log
  INSERT INTO agent_ops_log (
    dispatch_id, task, status, evidence, severity,
    cache_read_tokens, cache_write_tokens,
    input_tokens, output_tokens,
    cache_hit_pct, model
  )
  VALUES (
    p_run_id,
    'cache_metrics_report',
    'VERIFIED',
    format(
      'model=%s cache_read=%s cache_write=%s hit_pct=%s%% input=%s output=%s cost_usd=%s',
      p_model, p_cache_read, p_cache_write,
      coalesce(v_hit_pct::text, 'n/a'),
      p_input, p_output, v_cost_usd
    ),
    CASE WHEN coalesce(v_hit_pct, 100) < 30 THEN 'warn' ELSE 'info' END,
    p_cache_read, p_cache_write,
    p_input, p_output,
    v_hit_pct, p_model
  );

  v_result := jsonb_build_object(
    'run_id',        p_run_id,
    'issue',         p_issue,
    'model',         p_model,
    'cache_hit_pct', v_hit_pct,
    'cost_usd',      v_cost_usd,
    'status',        'recorded'
  );

  RETURN v_result;
END;
$function$;

REVOKE ALL ON FUNCTION public.record_session_cache_metrics FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.record_session_cache_metrics TO service_role;

ALTER TABLE public.cc_session_cost ADD COLUMN IF NOT EXISTS run_id text;
CREATE UNIQUE INDEX IF NOT EXISTS cc_session_cost_run_id_idx
  ON public.cc_session_cost (run_id) WHERE (run_id IS NOT NULL);
