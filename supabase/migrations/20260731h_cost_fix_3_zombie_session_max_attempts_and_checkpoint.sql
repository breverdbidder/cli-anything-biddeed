-- COST-FIX-3: fix zombie sessions caused by GHA 6h ceiling exits without DoD.
-- dispatch_id: aebc0542-fa69-446a-af51-05713a597824
-- chat_session: cost-fix-session-window-202607311430
--
-- Root cause: launch_claude_code_session() hardcoded max_attempts=3 in its
-- INSERT INTO summit_chat_dispatch, so a session that times out at the GHA
-- 6h ceiling without meeting DoD gets redispatched up to 3x (confirmed
-- zombie durations: 136h/135h/134h wall-clock on single shards). This
-- migration (1) drops the hardcode to 1, and (2) adds a progress-checkpoint
-- so a session that times out mid-work can record which criteria already
-- pass, letting the next session (if any) target only what's failing
-- instead of re-running all 10 from scratch.

-- 1) launch_claude_code_session: both overloads, max_attempts 3 -> 1

CREATE OR REPLACE FUNCTION public.launch_claude_code_session(p_title text, p_body text, p_repo text DEFAULT 'breverdbidder/cli-anything-biddeed'::text, p_priority text DEFAULT 'p1'::text, p_workflow text DEFAULT 'cc-runner-ghonly.yml'::text)
 RETURNS TABLE(dispatch_id uuid, phase1_processed_id uuid, phase1_action text, phase1_detail text)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'net', 'vault', 'extensions'
AS $function$
DECLARE
  v_id       uuid;
  v_body     text;
  v_priority text;
BEGIN
  IF p_title IS NULL OR btrim(p_title) = '' THEN
    RAISE EXCEPTION 'launch_claude_code_session: title is required';
  END IF;
  IF p_body IS NULL OR btrim(p_body) = '' THEN
    RAISE EXCEPTION 'launch_claude_code_session: body is required';
  END IF;
  IF p_workflow IS NULL OR p_workflow NOT LIKE '%.yml' THEN
    RAISE EXCEPTION 'launch_claude_code_session: target_workflow must end in .yml (got %)', p_workflow;
  END IF;
  IF p_repo IS NULL OR p_repo NOT LIKE '%/%' THEN
    RAISE EXCEPTION 'launch_claude_code_session: repo must be owner/name (got %)', p_repo;
  END IF;

  v_priority := lower(coalesce(nullif(btrim(p_priority),''),'p1'));
  IF v_priority NOT IN ('p0','p1','normal') THEN v_priority := 'p1'; END IF;

  -- cc-runner-ghonly.yml reads the issue body as the Claude prompt via `gh issue view`.
  -- The @claude prefix is retained as harmless belt-and-suspenders for any issue-trigger path.
  v_body := CASE WHEN p_body ILIKE '%@claude%' THEN p_body
                 ELSE '@claude' || E'\n\n' || p_body END;

  INSERT INTO public.summit_chat_dispatch
    (chat_session_id, ai_architect_model, summit_title, summit_body,
     target_repo, target_workflow, priority, state,
     dispatch_inputs, touches_prod_web, verification_scope, max_attempts)
  VALUES
    ('architect-' || to_char(now(),'YYYYMMDD"T"HH24MISS'),
     'claude-opus-4-8',
     p_title, v_body,
     p_repo, p_workflow, v_priority, 'queued',
     '{}'::jsonb, false, 'supabase_only', 1)
  RETURNING id INTO v_id;

  RETURN QUERY
    SELECT v_id, w.processed_id, w.action, w.detail
    FROM public.everest_worker_phase1_create_issue() w;
END;
$function$;

CREATE OR REPLACE FUNCTION public.launch_claude_code_session(p_title text, p_body text, p_repo text DEFAULT 'breverdbidder/cli-anything-biddeed'::text, p_priority text DEFAULT 'p1'::text, p_workflow text DEFAULT 'cc-runner-ghonly.yml'::text, p_dod_sql text DEFAULT NULL::text)
 RETURNS TABLE(dispatch_id uuid, phase1_processed_id uuid, phase1_action text, phase1_detail text)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'net', 'vault', 'extensions'
AS $function$
DECLARE
  v_id       uuid;
  v_body     text;
  v_priority text;
BEGIN
  IF p_title IS NULL OR btrim(p_title) = '' THEN
    RAISE EXCEPTION 'launch_claude_code_session: title is required';
  END IF;
  IF p_body IS NULL OR btrim(p_body) = '' THEN
    RAISE EXCEPTION 'launch_claude_code_session: body is required';
  END IF;
  IF p_workflow IS NULL OR p_workflow NOT LIKE '%.yml' THEN
    RAISE EXCEPTION 'launch_claude_code_session: target_workflow must end in .yml (got %)', p_workflow;
  END IF;
  IF p_repo IS NULL OR p_repo NOT LIKE '%/%' THEN
    RAISE EXCEPTION 'launch_claude_code_session: repo must be owner/name (got %)', p_repo;
  END IF;

  v_priority := lower(coalesce(nullif(btrim(p_priority),''),'p1'));
  IF v_priority NOT IN ('p0','p1','normal') THEN v_priority := 'p1'; END IF;

  -- cc-runner-ghonly.yml reads the issue body as the Claude prompt via `gh issue view`.
  -- The @claude prefix is retained as harmless belt-and-suspenders for any issue-trigger path.
  v_body := CASE WHEN p_body ILIKE '%@claude%' THEN p_body
                 ELSE '@claude' || E'\n\n' || p_body END;

  INSERT INTO public.summit_chat_dispatch
    (chat_session_id, ai_architect_model, summit_title, summit_body,
     target_repo, target_workflow, priority, state,
     dispatch_inputs, touches_prod_web, verification_scope, max_attempts, dod_sql)
  VALUES
    ('architect-' || to_char(now(),'YYYYMMDD"T"HH24MISS'),
     'claude-opus-4-8',
     p_title, v_body,
     p_repo, p_workflow, v_priority, 'queued',
     '{}'::jsonb, false, 'supabase_only', 1, nullif(btrim(p_dod_sql), ''))
  RETURNING id INTO v_id;

  RETURN QUERY
    SELECT v_id, w.processed_id, w.action, w.detail
    FROM public.everest_worker_phase1_create_issue() w;
END;
$function$;

-- 2) gold_standard_campaign: progress-checkpoint columns

ALTER TABLE public.gold_standard_campaign ADD COLUMN IF NOT EXISTS criteria_passed jsonb DEFAULT '{}';
ALTER TABLE public.gold_standard_campaign ADD COLUMN IF NOT EXISTS criteria_total int DEFAULT 10;
ALTER TABLE public.gold_standard_campaign ADD COLUMN IF NOT EXISTS exit_reason text; -- 'certified','timeout','spend_gate','manual_stop'
ALTER TABLE public.gold_standard_campaign ADD COLUMN IF NOT EXISTS session_end_at timestamptz;

-- 3) gold_standard_session_brief_for(): append MANDATORY SESSION CLOSE-OUT
-- block so every new CC session prompt carries the checkpoint instructions.

CREATE OR REPLACE FUNCTION public.gold_standard_session_brief_for(p_counties text[])
 RETURNS text
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
WITH latest AS (SELECT max(loop_run_id) AS run FROM gold_standard_county_status),
detail AS (
  SELECT s.county_slug,
         max(sb.pass_count) AS pass_count,
         string_agg(s.letter || ' ' || s.status || ' metric=' || coalesce(s.metric::text,'null')
                    || ' [' || s.detail || ']', E'\n    ' ORDER BY s.letter) AS letters
  FROM gold_standard_county_status s
  JOIN gold_standard_scoreboard sb USING (county_slug), latest
  WHERE s.loop_run_id = latest.run AND s.county_slug = ANY(p_counties)
  GROUP BY s.county_slug
)
SELECT 'YOUR ASSIGNED SHARD (work ONLY these counties) — loop run ' || (SELECT run FROM latest) || E':\n\n' ||
       string_agg('## ' || county_slug || ' (' || pass_count || '/10)' || E'\n    ' || letters,
                  E'\n\n' ORDER BY pass_count DESC, county_slug)
       || E'\n\n' || $brief_closeout$## MANDATORY SESSION CLOSE-OUT (run in final 20 minutes regardless of DoD status)

Before your session ends, you MUST write your progress to the database:

```sql
UPDATE public.gold_standard_campaign
SET
  criteria_passed = '{"A": true/false, "B": true/false, ...}'::jsonb,  -- fill actual A-J status
  criteria_total = 10,
  exit_reason = 'timeout',  -- or 'certified' if DoD met
  session_end_at = now()
WHERE dispatch_id = (SELECT id FROM summit_chat_dispatch WHERE state='processing' ORDER BY updated_at DESC LIMIT 1);
```

This checkpoint means the NEXT session for this county starts knowing exactly which criteria already pass and can focus only on failing ones instead of re-running all 10.$brief_closeout$
FROM detail
$function$;
