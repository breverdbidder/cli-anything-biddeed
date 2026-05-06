-- ============================================================================
-- cli_anything router: zero-HITL agent dispatch through Smart Router
-- ----------------------------------------------------------------------------
-- HARD RULE per ariel: NEVER use anthropic_api_key.
--   TIER_1: anthropic_oauth_bearer (Max OAuth, free)
--   TIER_2: gemini_api_key          (fallback)
-- Companion: PR #7422 (merge 99995d6) shipped the 36 voltagent agent .md files.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS cli_anything;

CREATE TABLE IF NOT EXISTS cli_anything.agents (
  namespace text PRIMARY KEY,
  category_slug text NOT NULL,
  agent_name text NOT NULL,
  description text NOT NULL,
  system_prompt text NOT NULL,
  source_url text,
  source_sha text,
  upstream_model_hint text,
  active boolean DEFAULT true,
  quarantined boolean DEFAULT false,
  quarantine_reason text,
  consecutive_failures int DEFAULT 0,
  last_invoked_at timestamptz,
  last_success_at timestamptz,
  total_invocations int DEFAULT 0,
  total_cost_cents numeric DEFAULT 0,
  imported_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cli_anything.tasks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_task_id uuid REFERENCES cli_anything.tasks(id),
  user_task text NOT NULL,
  requested_by text DEFAULT 'ariel-chat',
  chat_session_id text,
  agent_namespace text REFERENCES cli_anything.agents(namespace),
  routing_mode text DEFAULT 'explicit'
    CHECK (routing_mode IN ('explicit','router','parallel')),
  status text DEFAULT 'queued'
    CHECK (status IN ('queued','dispatching','running','complete','failed','timeout')),
  source text DEFAULT 'cli_anything'
    CHECK (source IN ('cli_anything','ecu_chat','summit_dispatch','cairn_supervisor',
                      'biddeed','zonewise','property360','compliance_agent','manual','other')),
  model text DEFAULT 'smart-router',
  max_tokens int DEFAULT 4096,
  llm_request_id bigint REFERENCES public.llm_requests(id),
  llm_response_id bigint REFERENCES public.llm_responses(id),
  routing_tier text,
  auth_kind text,
  response_text text,
  response_usage jsonb,
  error text,
  created_at timestamptz DEFAULT now(),
  dispatched_at timestamptz,
  completed_at timestamptz
);
CREATE INDEX IF NOT EXISTS tasks_status_created_idx ON cli_anything.tasks (status, created_at);
CREATE INDEX IF NOT EXISTS tasks_agent_idx          ON cli_anything.tasks (agent_namespace);
CREATE INDEX IF NOT EXISTS tasks_parent_idx         ON cli_anything.tasks (parent_task_id);
CREATE INDEX IF NOT EXISTS tasks_source_date_idx    ON cli_anything.tasks (source, (created_at::date));

CREATE TABLE IF NOT EXISTS cli_anything.budget (
  scope text PRIMARY KEY,
  daily_cap_cents numeric NOT NULL,
  hard_cap_cents numeric NOT NULL,
  notes text
);
INSERT INTO cli_anything.budget (scope, daily_cap_cents, hard_cap_cents, notes) VALUES
  ('global',          1000, 1500, '$10/day soft, $15 hard'),
  ('ecu_chat',         200,  400, 'User-facing chat'),
  ('summit_dispatch',  500,  800, 'Autonomous dispatch'),
  ('cli_anything',     300,  500, 'Direct chat invocations')
ON CONFLICT (scope) DO NOTHING;

-- All function bodies (budget_check, update_agent_health, pick_agents,
-- invoke_sync, invoke, auto_invoke, parallel_invoke) and views
-- (v_agent_health, v_budget_today) are emitted in the canonical
-- per-function migrations applied in project mocerqjnksmhcjzxrewo.
-- This file is the SCHEMA SSOT — function bodies are pulled from
-- pg_get_functiondef() in the live database for replay.

-- ============================================================================
-- Function definitions (extracted from live DB via pg_get_functiondef)
-- ============================================================================

CREATE OR REPLACE FUNCTION cli_anything.auto_invoke(p_task text, p_source text DEFAULT 'cli_anything'::text, p_max_tokens integer DEFAULT 2000, p_chat_session_id text DEFAULT NULL::text)
 RETURNS TABLE(picked_namespace text, pick_score real, out_task_id uuid, out_status text, out_response text, out_tier text, out_cost_cents numeric, out_latency_ms integer, out_error text)
 LANGUAGE plpgsql
AS $function$
DECLARE v_pick record; v_inv record;
BEGIN
  SELECT * INTO v_pick FROM cli_anything.pick_agents(p_task, 1) LIMIT 1;
  IF v_pick.namespace IS NULL THEN
    RAISE EXCEPTION 'cli_anything: no eligible agent for task';
  END IF;
  SELECT * INTO v_inv FROM cli_anything.invoke_sync(
    v_pick.namespace, p_task, p_max_tokens, NULL, p_chat_session_id, NULL, p_source);
  RETURN QUERY SELECT v_pick.namespace, v_pick.score,
    v_inv.out_task_id, v_inv.out_status, v_inv.out_response,
    v_inv.out_routing_tier, v_inv.out_cost_cents, v_inv.out_latency_ms, v_inv.out_error;
END $function$
;

CREATE OR REPLACE FUNCTION cli_anything.budget_check(p_source text DEFAULT 'cli_anything'::text)
 RETURNS TABLE(allowed boolean, reason text)
 LANGUAGE plpgsql
 STABLE
AS $function$
DECLARE
  v_spent numeric; v_hard numeric;
  v_global_spent numeric; v_global_cap numeric;
BEGIN
  SELECT COALESCE(sum((response_usage->>'cost_cents')::numeric), 0) INTO v_spent
  FROM cli_anything.tasks WHERE source = p_source AND created_at::date = current_date;
  SELECT hard_cap_cents INTO v_hard
  FROM cli_anything.budget WHERE scope = p_source;
  IF v_hard IS NOT NULL AND v_spent >= v_hard THEN
    RETURN QUERY SELECT false, format('scope %s hard cap %s¢ exceeded (spent %s¢)', p_source, v_hard, v_spent);
    RETURN;
  END IF;
  SELECT COALESCE(sum((response_usage->>'cost_cents')::numeric), 0) INTO v_global_spent
  FROM cli_anything.tasks WHERE created_at::date = current_date;
  SELECT hard_cap_cents INTO v_global_cap FROM cli_anything.budget WHERE scope = 'global';
  IF v_global_cap IS NOT NULL AND v_global_spent >= v_global_cap THEN
    RETURN QUERY SELECT false, format('global hard cap %s¢ exceeded (spent %s¢)', v_global_cap, v_global_spent);
    RETURN;
  END IF;
  RETURN QUERY SELECT true, 'within caps'::text;
END $function$
;

CREATE OR REPLACE FUNCTION cli_anything.invoke(p_namespace text, p_task text, p_max_tokens integer DEFAULT 4096, p_source text DEFAULT 'cli_anything'::text, p_chat_session_id text DEFAULT NULL::text, p_parent_id uuid DEFAULT NULL::uuid)
 RETURNS uuid
 LANGUAGE plpgsql
AS $function$
DECLARE v_inv record;
BEGIN
  SELECT * INTO v_inv FROM cli_anything.invoke_sync(
    p_namespace, p_task, p_max_tokens, NULL, p_chat_session_id, p_parent_id, p_source);
  RETURN v_inv.out_task_id;
END $function$
;

CREATE OR REPLACE FUNCTION cli_anything.invoke_sync(p_namespace text, p_task text, p_max_tokens integer DEFAULT 4096, p_force_tier text DEFAULT NULL::text, p_chat_session_id text DEFAULT NULL::text, p_parent_id uuid DEFAULT NULL::uuid, p_source text DEFAULT 'cli_anything'::text)
 RETURNS TABLE(out_task_id uuid, out_status text, out_response text, out_routing_tier text, out_auth_kind text, out_input_tokens integer, out_output_tokens integer, out_cost_cents numeric, out_latency_ms integer, out_llm_request_id bigint, out_error text)
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_id uuid; v_system_prompt text; v_router_result jsonb;
  v_request_id bigint; v_response record; v_routing jsonb;
  v_budget record; v_succeeded boolean;
BEGIN
  SELECT a.system_prompt INTO v_system_prompt
  FROM cli_anything.agents a
  WHERE a.namespace = p_namespace AND a.active AND NOT a.quarantined;
  IF v_system_prompt IS NULL THEN
    RAISE EXCEPTION 'cli_anything: unknown, inactive, or quarantined agent: %', p_namespace;
  END IF;

  SELECT * INTO v_budget FROM cli_anything.budget_check(p_source);
  IF NOT v_budget.allowed THEN
    INSERT INTO cli_anything.tasks (
      user_task, agent_namespace, model, max_tokens, chat_session_id, parent_task_id,
      routing_mode, status, source, error, completed_at
    ) VALUES (
      p_task, p_namespace, 'smart-router', p_max_tokens, p_chat_session_id, p_parent_id,
      'explicit', 'failed', p_source, 'BUDGET_EXCEEDED: ' || v_budget.reason, now()
    ) RETURNING id INTO v_id;
    RETURN QUERY SELECT v_id, 'failed'::text, NULL::text, 'BUDGET_GATE'::text, NULL::text,
                        0, 0, 0::numeric, 0, NULL::bigint, ('BUDGET_EXCEEDED: ' || v_budget.reason);
    RETURN;
  END IF;

  INSERT INTO cli_anything.tasks (
    user_task, agent_namespace, model, max_tokens, chat_session_id, parent_task_id,
    routing_mode, status, dispatched_at, source
  ) VALUES (
    p_task, p_namespace, 'smart-router', p_max_tokens, p_chat_session_id, p_parent_id,
    'explicit', 'dispatching', now(), p_source
  ) RETURNING id INTO v_id;

  v_router_result := public.ecu_route_chat_llm(
    p_messages      => jsonb_build_array(jsonb_build_object('role','user','content', p_task)),
    p_system_prompt => v_system_prompt,
    p_max_tokens    => p_max_tokens,
    p_force_tier    => p_force_tier
  );

  v_request_id := (v_router_result->>'request_id')::bigint;
  v_routing := v_router_result->'routing';

  SELECT r.id AS response_id, r.text AS resp_text,
         r.input_tokens, r.output_tokens, r.cost_cents, r.latency_ms,
         r.error_type, r.error_message
  INTO v_response
  FROM public.llm_responses r
  WHERE r.request_id = v_request_id;

  v_succeeded := (v_router_result->>'ok')::boolean;

  UPDATE cli_anything.tasks
  SET status = CASE WHEN v_succeeded THEN 'complete' ELSE 'failed' END,
      llm_request_id = v_request_id, llm_response_id = v_response.response_id,
      routing_tier = COALESCE(v_routing->>'tier', v_router_result->>'tier'),
      auth_kind = v_router_result->>'auth_kind',
      response_text = v_response.resp_text,
      response_usage = jsonb_build_object(
        'input_tokens', v_response.input_tokens,
        'output_tokens', v_response.output_tokens,
        'cost_cents', v_response.cost_cents,
        'latency_ms', v_response.latency_ms,
        'fallback_used', v_routing->'fallback_used'
      ),
      error = COALESCE(v_response.error_message, v_router_result->>'error_message'),
      completed_at = now()
  WHERE id = v_id;

  PERFORM cli_anything.update_agent_health(p_namespace, v_succeeded, COALESCE(v_response.cost_cents, 0));

  RETURN QUERY
  SELECT t.id, t.status, t.response_text, t.routing_tier, t.auth_kind,
         (t.response_usage->>'input_tokens')::int,
         (t.response_usage->>'output_tokens')::int,
         (t.response_usage->>'cost_cents')::numeric,
         (t.response_usage->>'latency_ms')::int,
         t.llm_request_id, t.error
  FROM cli_anything.tasks t WHERE t.id = v_id;
END $function$
;

CREATE OR REPLACE FUNCTION cli_anything.parallel_invoke(p_task text, p_top_k integer DEFAULT 3, p_source text DEFAULT 'cli_anything'::text, p_max_tokens integer DEFAULT 2000, p_chat_session_id text DEFAULT NULL::text)
 RETURNS TABLE(picked_namespace text, pick_score real, out_task_id uuid, out_status text, out_response text, out_tier text, out_cost_cents numeric, out_latency_ms integer, out_error text)
 LANGUAGE plpgsql
AS $function$
DECLARE v_pick record; v_inv record;
BEGIN
  FOR v_pick IN SELECT * FROM cli_anything.pick_agents(p_task, p_top_k) LOOP
    SELECT * INTO v_inv FROM cli_anything.invoke_sync(
      v_pick.namespace, p_task, p_max_tokens, NULL, p_chat_session_id, NULL, p_source);
    RETURN QUERY SELECT v_pick.namespace, v_pick.score,
      v_inv.out_task_id, v_inv.out_status, v_inv.out_response,
      v_inv.out_routing_tier, v_inv.out_cost_cents, v_inv.out_latency_ms, v_inv.out_error;
  END LOOP;
END $function$
;

CREATE OR REPLACE FUNCTION cli_anything.pick_agents(p_task text, p_top_k integer DEFAULT 3)
 RETURNS TABLE(namespace text, score real, description text)
 LANGUAGE sql
 STABLE
AS $function$
  SELECT a.namespace,
    ts_rank(
      to_tsvector('english',
        a.description || ' ' || a.agent_name || ' ' || a.category_slug || ' ' ||
        regexp_replace(a.namespace, 'cli_anything\.', '', 'g')),
      plainto_tsquery('english', p_task)
    )
    + CASE WHEN p_task ILIKE '%' || a.agent_name || '%' THEN 0.5 ELSE 0 END
    + CASE WHEN p_task ILIKE '%' || a.category_slug || '%' THEN 0.2 ELSE 0 END
    AS score,
    a.description
  FROM cli_anything.agents a
  WHERE a.active AND NOT a.quarantined
  ORDER BY 2 DESC
  LIMIT p_top_k
$function$
;

CREATE OR REPLACE FUNCTION cli_anything.update_agent_health(p_namespace text, p_succeeded boolean, p_cost_cents numeric DEFAULT 0)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF p_succeeded THEN
    UPDATE cli_anything.agents
    SET consecutive_failures = 0, last_invoked_at = now(), last_success_at = now(),
        total_invocations = total_invocations + 1,
        total_cost_cents = total_cost_cents + COALESCE(p_cost_cents, 0)
    WHERE namespace = p_namespace;
  ELSE
    UPDATE cli_anything.agents
    SET consecutive_failures = consecutive_failures + 1,
        last_invoked_at = now(),
        total_invocations = total_invocations + 1,
        quarantined = (consecutive_failures + 1 >= 5),
        quarantine_reason = CASE WHEN consecutive_failures + 1 >= 5
                                 THEN 'auto-quarantined after 5 consecutive failures at ' || now()::text
                                 ELSE quarantine_reason END
    WHERE namespace = p_namespace;
  END IF;
END $function$
;


-- ============================================================================
-- View definitions
-- ============================================================================

CREATE OR REPLACE VIEW cli_anything.v_agent_health AS  SELECT category_slug,
    agent_name,
    namespace,
    active,
    quarantined,
    quarantine_reason,
    consecutive_failures,
    total_invocations,
    total_cost_cents,
    last_invoked_at,
    last_success_at,
        CASE
            WHEN quarantined THEN 'QUARANTINED'::text
            WHEN NOT active THEN 'INACTIVE'::text
            WHEN consecutive_failures >= 3 THEN 'DEGRADED'::text
            WHEN total_invocations = 0 THEN 'UNTESTED'::text
            ELSE 'HEALTHY'::text
        END AS health_state
   FROM cli_anything.agents
  ORDER BY namespace;

CREATE OR REPLACE VIEW cli_anything.v_budget_today AS  SELECT b.scope,
    COALESCE(t.calls_today, 0::bigint) AS calls_today,
    COALESCE(t.spent_cents, 0::numeric) AS spent_cents,
    b.daily_cap_cents,
    b.hard_cap_cents,
        CASE
            WHEN COALESCE(t.spent_cents, 0::numeric) >= b.hard_cap_cents THEN 'HARD_CAP_HIT'::text
            WHEN COALESCE(t.spent_cents, 0::numeric) >= b.daily_cap_cents THEN 'SOFT_CAP_HIT'::text
            ELSE 'OK'::text
        END AS status
   FROM cli_anything.budget b
     LEFT JOIN ( SELECT tasks.source,
            count(*) AS calls_today,
            sum((tasks.response_usage ->> 'cost_cents'::text)::numeric) AS spent_cents
           FROM cli_anything.tasks
          WHERE tasks.created_at::date = CURRENT_DATE
          GROUP BY tasks.source) t ON t.source = b.scope;

