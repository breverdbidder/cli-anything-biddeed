-- GTM-22D Task A — close the service_role read path into vault.decrypted_secrets
-- for the 4 of 8 SECURITY INVOKER functions that are actually reachable by
-- service_role in production (proven via caller/trigger/cron audit below).
-- Converts them to SECURITY DEFINER (owner=postgres, who keeps SELECT on
-- vault.decrypted_secrets) with an explicit session_user guard, so the
-- privilege only transfers to callers who were already postgres/service_role
-- — not to anon/authenticated, which also hold EXECUTE on these functions.
--
-- Evidence (VERIFIED live against mocerqjnksmhcjzxrewo, 2026-07-19):
--
-- LEFT UNCHANGED (proven invoked ONLY as postgres — cron or nested-in-definer):
--   cc_release_staged_jobs               -> cron.job jobid=250 "cc-release-staged", username=postgres
--   po_harvest_drain                     -> cron.job jobid=24  "po-harvest-drain",  username=postgres
--   everest_worker_phase2_confirm_and_dispatch -> called only from everest_dispatch_tick
--                                            (SECURITY DEFINER owner=postgres), itself cron
--                                            jobid=5 "everest-dispatcher-v7", username=postgres.
--                                            No RPC/grep hit anywhere else in this repo.
--   everest_worker_phase3_confirm_dispatch     -> same chain as phase2, same cron job.
--   (All four still carry EXECUTE grants to service_role/anon/authenticated/PUBLIC —
--    that grant surface is unchanged by this migration; flagged separately in the
--    GTM-22D closing report as a follow-up, not touched here to avoid scope creep.)
--
-- CONVERTED (reachable by service_role today, no cron/nested-only proof):
--   eb_set_repo_secret            -> no cron, no internal caller; designed as a
--                                     standalone RPC target (p_owner/p_repo/p_secret_name/
--                                     p_secret_value signature) — must be assumed
--                                     RPC-invoked with the service_role key.
--   handle_commit_workflow_yaml_inline -> AFTER trigger (trg_handle_commit_workflow_yaml)
--                                     on public.summit_chat_dispatch. Confirmed multiple
--                                     GHA workflows (summit-biddeed-zonewise-dossier-widget.yml,
--                                     summit-understand-anything.yml, summit-battle-card-writer.yml,
--                                     ci-v65-artillery.yml) INSERT into summit_chat_dispatch using
--                                     SUPABASE_SERVICE_ROLE_KEY — this trigger DOES run as
--                                     service_role today.
--   upsert_staged_file_to_github  -> no cron, no internal caller; RPC-shaped signature
--                                     (p_dispatch_id/p_target_path/...) — must be assumed
--                                     RPC-invoked with the service_role key.
--   zw_extract_density_one        -> no cron, no internal caller; RPC-shaped signature
--                                     (p_district_id) used by batch density-extraction
--                                     workflows — must be assumed RPC-invoked with the
--                                     service_role key.
--
-- Rollback: re-run the prior CREATE OR REPLACE bodies without SECURITY DEFINER /
-- the session_user guard / SET search_path (see git history of this file's predecessor
-- commit for the exact prior bodies), or:
--   ALTER FUNCTION public.eb_set_repo_secret(text,text,text,text) SECURITY INVOKER;
--   ALTER FUNCTION public.handle_commit_workflow_yaml_inline() SECURITY INVOKER;
--   ALTER FUNCTION public.upsert_staged_file_to_github(uuid,text,text,text,text) SECURITY INVOKER;
--   ALTER FUNCTION public.zw_extract_density_one(integer) SECURITY INVOKER;
-- (reverting the guard/search_path is optional — SECURITY INVOKER makes them moot again)

-- ── eb_set_repo_secret ──────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.eb_set_repo_secret(p_owner text, p_repo text, p_secret_name text, p_secret_value text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path = ''
AS $function$
DECLARE v_token text; v_srk text; v_resp extensions.http_response;
BEGIN
  IF session_user NOT IN ('postgres', 'service_role') THEN
    RAISE EXCEPTION 'unauthorized: % may not invoke eb_set_repo_secret', session_user;
  END IF;

  SELECT decrypted_secret INTO v_token FROM vault.decrypted_secrets WHERE name = 'fork_heartbeat_token';
  SELECT decrypted_secret INTO v_srk   FROM vault.decrypted_secrets WHERE name = 'service_role_key';
  v_resp := extensions.http(ROW(
    'POST'::extensions.http_method,
    'https://mocerqjnksmhcjzxrewo.supabase.co/functions/v1/set-repo-secret',
    ARRAY[
      extensions.http_header('Authorization', 'Bearer ' || v_srk),
      extensions.http_header('apikey', v_srk),
      extensions.http_header('Content-Type', 'application/json')
    ],
    'application/json',
    jsonb_build_object('token', v_token, 'owner', p_owner, 'repo', p_repo,
                       'secret_name', p_secret_name, 'secret_value', p_secret_value)::text
  )::extensions.http_request);
  RETURN jsonb_build_object('http_status', v_resp.status, 'body', v_resp.content::jsonb);
END $function$;

-- ── handle_commit_workflow_yaml_inline (trigger) ────────────────────────────
CREATE OR REPLACE FUNCTION public.handle_commit_workflow_yaml_inline()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path = ''
AS $function$
DECLARE
  v_artifact_id uuid;
  v_target_path text;
  v_content text;
  v_b64 text;
  v_filename text;
  v_repo text;
  v_branch text;
  v_shared text;
  v_resp extensions.http_response;
  v_body jsonb;
  v_payload jsonb;
  v_post_action text;
  v_post_workflow text;
  v_post_inputs jsonb;
  v_pat text;
  v_dispatch_resp extensions.http_response;
BEGIN
  IF session_user NOT IN ('postgres', 'service_role') THEN
    RAISE EXCEPTION 'unauthorized: % may not invoke handle_commit_workflow_yaml_inline', session_user;
  END IF;

  IF NEW.dispatch_inputs->>'kind' IS DISTINCT FROM 'commit_workflow_yaml' THEN
    RETURN NEW;
  END IF;

  v_artifact_id := (NEW.dispatch_inputs->>'extrep_artifact_id')::uuid;
  v_target_path := NEW.dispatch_inputs->>'target_path';
  v_repo := NEW.target_repo;
  v_branch := COALESCE(NEW.dispatch_inputs->>'branch', 'main');

  IF v_artifact_id IS NULL OR v_target_path IS NULL OR v_repo IS NULL THEN
    NEW.state := 'quarantined';
    NEW.last_error := 'commit_workflow_yaml requires dispatch_inputs.{extrep_artifact_id, target_path} and target_repo';
    NEW.quarantine_reason := 'missing_fields';
    NEW.completed_at := NOW();
    RETURN NEW;
  END IF;

  SELECT content INTO v_content FROM public.extrep_artifacts WHERE id = v_artifact_id;
  IF v_content IS NULL THEN
    NEW.state := 'quarantined';
    NEW.last_error := 'extrep_artifact ' || v_artifact_id || ' not found or empty';
    NEW.quarantine_reason := 'artifact_missing';
    NEW.completed_at := NOW();
    RETURN NEW;
  END IF;

  v_b64 := translate(encode(convert_to(v_content, 'UTF8'), 'base64'), E'\n\r', '');
  v_filename := split_part(v_target_path, '/', -1);
  v_shared := public.cli_anything_get_secret('cli_anything_shared_secret');

  v_payload := jsonb_build_object(
    'repo', v_repo,
    'branch', v_branch,
    'message', COALESCE(NEW.dispatch_inputs->>'commit_message', 'feat(ci): commit ' || v_filename),
    'vault_secret_name', 'everest_gh_pat',
    'conc_strict', true,
    'files', jsonb_build_array(jsonb_build_object(
      'path', v_target_path,
      'content_b64', v_b64,
      'message', COALESCE(NEW.dispatch_inputs->>'commit_message', 'feat(ci): commit ' || v_filename)
    ))
  );

  v_resp := extensions.http(ROW(
    'POST'::extensions.http_method,
    'https://mocerqjnksmhcjzxrewo.supabase.co/functions/v1/cli-anything-gh-push-v4',
    ARRAY[
      extensions.http_header('X-Everest-Auth', v_shared),
      extensions.http_header('Content-Type', 'application/json'),
      extensions.http_header('User-Agent', 'commit-workflow-yaml-trigger')
    ],
    'application/json',
    v_payload::text
  )::extensions.http_request);

  v_body := v_resp.content::jsonb;

  IF v_resp.status BETWEEN 200 AND 299 AND (v_body->>'ok')::boolean = true THEN
    NEW.state := 'closed';
    NEW.completed_at := NOW();
    NEW.last_error := NULL;
    NEW.dispatch_inputs := NEW.dispatch_inputs || jsonb_build_object(
      'handled_by', 'handle_commit_workflow_yaml_inline trigger',
      'commit_sha', v_body->'results'->0->>'commit_sha',
      'file_sha',   v_body->'results'->0->>'sha'
    );

    UPDATE public.extrep_artifacts
    SET deployment_status = 'deployed',
        deployed_at = NOW(),
        deployed_by = 'commit_workflow_yaml dispatch ' || NEW.id::text,
        deployed_commit_sha = v_body->'results'->0->>'commit_sha'
    WHERE id = v_artifact_id;

    v_post_action := NEW.dispatch_inputs->>'post_commit_action';
    IF v_post_action = 'trigger_workflow_dispatch' THEN
      v_post_workflow := NEW.dispatch_inputs->>'post_commit_workflow';
      v_post_inputs := NEW.dispatch_inputs->'post_commit_inputs';
      IF v_post_workflow IS NOT NULL THEN
        SELECT decrypted_secret INTO v_pat FROM vault.decrypted_secrets WHERE name = 'everest_gh_pat';
        v_dispatch_resp := extensions.http(ROW(
          'POST'::extensions.http_method,
          'https://api.github.com/repos/' || v_repo || '/actions/workflows/' || v_post_workflow || '/dispatches',
          ARRAY[
            extensions.http_header('Authorization', 'Bearer ' || v_pat),
            extensions.http_header('Accept', 'application/vnd.github+json'),
            extensions.http_header('User-Agent', 'commit-workflow-yaml-trigger')
          ],
          'application/json',
          jsonb_build_object('ref', v_branch, 'inputs', COALESCE(v_post_inputs, '{}'::jsonb))::text
        )::extensions.http_request);
        NEW.dispatch_inputs := NEW.dispatch_inputs || jsonb_build_object(
          'post_commit_dispatch_status', v_dispatch_resp.status
        );
      END IF;
    END IF;
  ELSE
    NEW.state := 'quarantined';
    NEW.last_error := 'cli-anything-gh-push-v4 returned: ' || v_resp.status || ' / ' || COALESCE(v_body::text, '(no body)');
    NEW.quarantine_reason := 'push_failed';
    NEW.completed_at := NOW();
  END IF;

  RETURN NEW;
EXCEPTION
  WHEN OTHERS THEN
    NEW.state := 'quarantined';
    NEW.last_error := 'trigger exception: ' || SQLERRM;
    NEW.quarantine_reason := 'trigger_exception';
    NEW.completed_at := NOW();
    RETURN NEW;
END $function$;

-- ── upsert_staged_file_to_github ────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.upsert_staged_file_to_github(p_dispatch_id uuid, p_target_path text, p_repo text DEFAULT 'breverdbidder/cli-anything-biddeed'::text, p_branch text DEFAULT 'main'::text, p_message text DEFAULT 'chore: update staged file'::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path = ''
AS $function$
DECLARE
  v_b64 text; v_token text; v_sha text;
  v_get extensions.http_response; v_put extensions.http_response; v_body jsonb;
BEGIN
  IF session_user NOT IN ('postgres', 'service_role') THEN
    RAISE EXCEPTION 'unauthorized: % may not invoke upsert_staged_file_to_github', session_user;
  END IF;

  SELECT content_b64 INTO v_b64 FROM public.dispatch_file_staging
   WHERE dispatch_id=p_dispatch_id AND target_path=p_target_path;
  IF v_b64 IS NULL THEN RETURN jsonb_build_object('error','No staged file','path',p_target_path); END IF;

  SELECT decrypted_secret INTO v_token FROM vault.decrypted_secrets WHERE name='everest_gh_pat';

  -- look up current blob sha (if the file already exists)
  SELECT * INTO v_get FROM extensions.http((
    'GET',
    'https://api.github.com/repos/'||p_repo||'/contents/'||p_target_path||'?ref='||p_branch,
    ARRAY[
      extensions.http_header('Authorization','Bearer '||v_token),
      extensions.http_header('Accept','application/vnd.github+json'),
      extensions.http_header('X-GitHub-Api-Version','2022-11-28'),
      extensions.http_header('User-Agent','everest-summit-dispatch')
    ], NULL, NULL)::extensions.http_request);
  IF v_get.status = 200 THEN
    v_sha := (v_get.content::jsonb)->>'sha';
  END IF;

  v_body := jsonb_build_object('message',p_message,'content',v_b64,'branch',p_branch);
  IF v_sha IS NOT NULL THEN v_body := v_body || jsonb_build_object('sha',v_sha); END IF;

  SELECT * INTO v_put FROM extensions.http((
    'PUT',
    'https://api.github.com/repos/'||p_repo||'/contents/'||p_target_path,
    ARRAY[
      extensions.http_header('Authorization','Bearer '||v_token),
      extensions.http_header('Accept','application/vnd.github+json'),
      extensions.http_header('X-GitHub-Api-Version','2022-11-28'),
      extensions.http_header('User-Agent','everest-summit-dispatch')
    ],
    'application/json',
    v_body::text)::extensions.http_request);

  RETURN jsonb_build_object(
    'status', v_put.status,
    'path', p_target_path,
    'action', CASE WHEN v_sha IS NOT NULL THEN 'update' ELSE 'create' END,
    'commit_sha', (v_put.content::jsonb)->'commit'->>'sha',
    'error', CASE WHEN v_put.status>=400 THEN (v_put.content::jsonb)->>'message' ELSE NULL END
  );
END; $function$;

-- ── zw_extract_density_one ──────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.zw_extract_density_one(p_district_id integer)
 RETURNS TABLE(district_id integer, juris text, zone text, density numeric, basis text, conf numeric, evidence text)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path = ''
AS $function$
DECLARE
  q RECORD; prompt text; resp jsonb; mtext text; js jsonb; jtxt text;
  v_density numeric; v_basis text; v_conf numeric; v_evi text; v_src text; v_status text;
BEGIN
  IF session_user NOT IN ('postgres', 'service_role') THEN
    RAISE EXCEPTION 'unauthorized: % may not invoke zw_extract_density_one', session_user;
  END IF;

  SELECT * INTO q FROM public.zw_density_extraction_queue z WHERE z.district_id = p_district_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'district % not found', p_district_id; END IF;

  prompt := format(
$tmpl$You are a Florida zoning code analyst. Search for the official municipal zoning ordinance for %s, Florida, zoning district "%s" (%s). Determine ONLY whether the ordinance EXPLICITLY STATES a maximum residential density in dwelling units per acre (du/acre).

STRICT RULES:
- Report a number ONLY if the ordinance text literally states a maximum density in units per acre / dwelling units per acre.
- NEVER calculate or derive du/acre from a minimum lot size. A minimum lot size is NOT a stated density.
- If the district only specifies a minimum lot size (no explicit du/acre), set density null and basis "lot_governed".
- If there is no density standard, or it is project-specific (PUD/PD/overlay), set density null and basis "not_stated".
- Do NOT guess. If unsure, use null.

Output ONLY this JSON (no markdown, no prose). evidence under 150 chars, citation = code section or city (NO long URLs):
{"density_du_per_acre": <number|null>, "basis": "stated_max_density|lot_governed|not_stated", "evidence": "<short quote/section>", "citation": "<city + section>", "confidence": <0.0-1.0>}$tmpl$,
    q.juris_name, q.zone_code, coalesce(q.district_name,''));

  PERFORM extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS','75000');

  SELECT r.content::jsonb INTO resp
  FROM extensions.http((
    'POST','https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent',
    ARRAY[ extensions.http_header('X-goog-api-key',(SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name='gemini_api_key')) ],
    'application/json',
    jsonb_build_object(
      'tools', jsonb_build_array(jsonb_build_object('google_search', jsonb_build_object())),
      'generationConfig', jsonb_build_object('temperature',0,'maxOutputTokens',2048),
      'contents', jsonb_build_array(jsonb_build_object('parts', jsonb_build_array(jsonb_build_object('text', prompt))))
    )::text
  )::extensions.http_request) r;

  mtext := resp #>> '{candidates,0,content,parts,0,text}';
  IF mtext IS NULL THEN
    UPDATE public.zw_density_extraction_queue z SET status='error',
      evidence='no_text fr='||coalesce(resp#>>'{candidates,0,finishReason}','?'), updated_at=now() WHERE z.district_id=p_district_id;
    RETURN QUERY SELECT p_district_id,q.juris_name,q.zone_code,NULL::numeric,'error'::text,NULL::numeric,
      ('no text fr='||coalesce(resp#>>'{candidates,0,finishReason}','?'))::text; RETURN;
  END IF;

  jtxt := (regexp_match(mtext, '\{[\s\S]*\}'))[1];
  IF jtxt IS NULL THEN
    UPDATE public.zw_density_extraction_queue z SET status='review', evidence='prose: '||left(mtext,400), updated_at=now() WHERE z.district_id=p_district_id;
    RETURN QUERY SELECT p_district_id,q.juris_name,q.zone_code,NULL::numeric,'review(prose)'::text,NULL::numeric,left(mtext,200); RETURN;
  END IF;

  js := jtxt::jsonb;
  v_density := NULLIF(js->>'density_du_per_acre','null')::numeric;
  v_basis   := js->>'basis';
  v_conf    := NULLIF(js->>'confidence','null')::numeric;
  v_evi     := left(js->>'evidence', 300);
  v_src     := js->>'citation';
  v_status  := CASE v_basis WHEN 'stated_max_density' THEN 'extracted'
                            WHEN 'lot_governed' THEN 'lot_governed'
                            WHEN 'not_stated' THEN 'not_stated' ELSE 'review' END;

  UPDATE public.zw_density_extraction_queue z SET
    extracted_density=v_density, confidence=v_conf,
    evidence=coalesce(v_evi,'')||' | basis='||coalesce(v_basis,'?')||' | cite='||coalesce(v_src,''),
    status=v_status, completed_at=now(), updated_at=now() WHERE z.district_id=p_district_id;

  RETURN QUERY SELECT p_district_id,q.juris_name,q.zone_code,v_density,v_basis,v_conf,v_evi;
EXCEPTION WHEN others THEN
  UPDATE public.zw_density_extraction_queue z SET status='error', evidence='parse_err: '||left(coalesce(jtxt,mtext,SQLERRM),300), updated_at=now() WHERE z.district_id=p_district_id;
  RETURN QUERY SELECT p_district_id,q.juris_name,q.zone_code,NULL::numeric,'error'::text,NULL::numeric,left(coalesce(jtxt,mtext,SQLERRM),200);
END;
$function$;
