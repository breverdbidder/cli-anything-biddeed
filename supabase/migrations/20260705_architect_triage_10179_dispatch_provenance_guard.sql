-- ARCHITECT TRIAGE issue #10179 (2026-07-05): root-cause fix for the recurring
-- github_issue_number mislink bug already flagged in decision_log ids 96-98
-- (issues #10204, #10181, #10125). Live evidence this session: net._http_response
-- id=14 was the phase1_request_id for ~30 distinct summit_chat_dispatch rows
-- spanning 2026-06-23 through 2026-07-04 (e.g. dispatch 02e2b751
-- "duval,sarasota,flagler,bradford" vs 9e70dcd7 "duval,sarasota,holmes,union"
-- both reading id=14), cross-linking github_issue_number/url between unrelated
-- shard dispatches. Issue #10179's live GitHub body/title (duval, sarasota,
-- holmes, union) never matched its dod_sql/task_label (duval, sarasota,
-- flagler, bradford) as a result -- the guard was gating on the wrong shard's
-- certification, so 3 genuinely-successful engineer sessions kept tripping it.
--
-- Fix: verify the created issue's own body echoes this row's 'dispatch_id: '
-- footer (embedded by phase1) before trusting github_issue_number/url read
-- back from net._http_response. This is robust regardless of *why* the
-- response id collides (pg_net id reuse/reset), because it checks content
-- provenance instead of trusting the id.
CREATE OR REPLACE FUNCTION public.everest_worker_phase2_confirm_and_dispatch()
 RETURNS TABLE(processed_id uuid, action text, detail text)
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_row       public.summit_chat_dispatch%ROWTYPE;
  v_pat       text;
  v_req1_id   bigint;
  v_resp      record;
  v_issue_n   int;
  v_issue_url text;
  v_req2_id   bigint;
  v_body_js   jsonb;
  v_qreason   text;
  v_inputs    jsonb;
BEGIN
  SELECT decrypted_secret INTO v_pat FROM vault.decrypted_secrets WHERE name='everest_gh_pat' LIMIT 1;
  IF v_pat IS NULL THEN RETURN; END IF;

  FOR v_row IN
    SELECT * FROM public.summit_chat_dispatch
    WHERE state = 'queued'
      AND delivery_proof ? 'phase1_request_id'
      AND NOT (delivery_proof ? 'phase2_dispatch_request_id')
    ORDER BY picked_up_at ASC NULLS LAST
    LIMIT 5
    FOR UPDATE SKIP LOCKED
  LOOP
    v_req1_id := (v_row.delivery_proof->>'phase1_request_id')::bigint;

    SELECT status_code, content::text AS content_text
      INTO v_resp FROM net._http_response WHERE id = v_req1_id;

    IF NOT FOUND THEN CONTINUE; END IF;

    -- RECYCLED-RECEIPT GUARD: a "phase1" response referencing workflow-dispatch
    -- means the pg_net ID was recycled to another request. Requeue phase1.
    IF COALESCE(v_resp.content_text,'') ILIKE '%workflow-dispatch%'
       OR COALESCE(v_resp.content_text,'') ILIKE '%workflows#create%' THEN
      UPDATE public.summit_chat_dispatch
        SET state = 'queued',
            attempt_number = COALESCE(attempt_number,1) + 1,
            last_error = 'phase2: recycled pg_net receipt detected, re-running phase1',
            delivery_proof = delivery_proof - 'phase1_request_id' - 'phase1_sent_at'
        WHERE id = v_row.id;
      RETURN QUERY SELECT v_row.id, 'recycled_receipt_requeued'::text, format('req_id=%s recycled', v_req1_id);
      CONTINUE;
    END IF;

    IF v_resp.status_code BETWEEN 400 AND 499 THEN
      v_qreason := CASE
        WHEN v_resp.status_code = 401 THEN 'auth_failure'
        WHEN v_resp.status_code = 403 THEN 'forbidden'
        WHEN v_resp.status_code = 404 THEN 'repo_not_found_or_no_access'
        WHEN v_resp.status_code = 410 THEN 'issues_disabled_on_repo'
        WHEN v_resp.status_code = 422 THEN 'validation_failed'
        ELSE format('permanent_4xx_%s', v_resp.status_code)
      END;
      UPDATE public.summit_chat_dispatch
        SET state='quarantined', quarantine_reason=v_qreason,
            quarantine_diagnosis=format('phase1 HTTP %s: %s', v_resp.status_code, LEFT(COALESCE(v_resp.content_text,''),400)),
            last_error=format('phase1 HTTP %s', v_resp.status_code),
            delivery_proof = delivery_proof - 'phase1_request_id' - 'phase1_sent_at'
        WHERE id = v_row.id;
      RETURN QUERY SELECT v_row.id, 'quarantined_phase1'::text, format('http=%s reason=%s', v_resp.status_code, v_qreason);
      CONTINUE;
    END IF;

    IF v_resp.status_code IS NULL OR v_resp.status_code >= 500 THEN
      UPDATE public.summit_chat_dispatch
        SET state = CASE WHEN COALESCE(attempt_number,1) >= COALESCE(max_attempts,3) THEN 'quarantined' ELSE 'queued' END,
            last_error = format('phase1 HTTP %s (transient)', COALESCE(v_resp.status_code::text,'null')),
            retry_after = now() + (INTERVAL '2 minutes' * COALESCE(attempt_number,1)),
            delivery_proof = delivery_proof - 'phase1_request_id' - 'phase1_sent_at',
            quarantine_reason = CASE WHEN COALESCE(attempt_number,1) >= COALESCE(max_attempts,3) THEN 'max_attempts_exceeded' ELSE quarantine_reason END
        WHERE id = v_row.id;
      RETURN QUERY SELECT v_row.id, 'phase1_transient'::text, format('http=%s', v_resp.status_code);
      CONTINUE;
    END IF;

    BEGIN
      v_body_js   := v_resp.content_text::jsonb;
      v_issue_n   := (v_body_js->>'number')::int;
      v_issue_url := v_body_js->>'html_url';
    EXCEPTION WHEN OTHERS THEN
      v_issue_n := NULL; v_issue_url := NULL;
    END;

    -- NULL-GUARD: never dispatch {"issues": null}. Requeue phase1 instead.
    IF v_issue_n IS NULL OR v_issue_url IS NULL OR position('/issues/' in v_issue_url) = 0 THEN
      UPDATE public.summit_chat_dispatch
        SET state = CASE WHEN COALESCE(attempt_number,1) >= COALESCE(max_attempts,3) THEN 'quarantined' ELSE 'queued' END,
            attempt_number = COALESCE(attempt_number,1) + 1,
            quarantine_reason = CASE WHEN COALESCE(attempt_number,1) >= COALESCE(max_attempts,3) THEN 'phase1_issue_number_unrecoverable' ELSE quarantine_reason END,
            last_error = 'phase2 null-guard: issue number missing/invalid, re-running phase1',
            delivery_proof = delivery_proof - 'phase1_request_id' - 'phase1_sent_at'
        WHERE id = v_row.id;
      RETURN QUERY SELECT v_row.id, 'null_guard_requeued'::text, 'issue number missing - phase1 rerun';
      CONTINUE;
    END IF;

    -- PROVENANCE GUARD (added 2026-07-05, AI Architect triage on issue #10179):
    -- see migration header for the confirmed cross-linking evidence.
    IF COALESCE(v_body_js->>'body','') NOT ILIKE ('%dispatch_id: ' || v_row.id::text || '%') THEN
      UPDATE public.summit_chat_dispatch
        SET state = CASE WHEN COALESCE(attempt_number,1) >= COALESCE(max_attempts,3) THEN 'quarantined' ELSE 'queued' END,
            attempt_number = COALESCE(attempt_number,1) + 1,
            quarantine_reason = CASE WHEN COALESCE(attempt_number,1) >= COALESCE(max_attempts,3) THEN 'phase1_receipt_cross_linked' ELSE quarantine_reason END,
            last_error = format('phase2 provenance guard: response id=%s body does not carry this row''s dispatch_id (cross-linked receipt), re-running phase1', v_req1_id),
            delivery_proof = delivery_proof - 'phase1_request_id' - 'phase1_sent_at'
        WHERE id = v_row.id;
      RETURN QUERY SELECT v_row.id, 'provenance_guard_requeued'::text, format('req_id=%s cross-linked to another dispatch - phase1 rerun', v_req1_id);
      CONTINUE;
    END IF;

    v_inputs := CASE
                  WHEN v_row.target_workflow = 'cc-runner-ghonly.yml'
                    THEN jsonb_build_object('issues', v_issue_n::text)
                  ELSE jsonb_build_object('issue_number', v_issue_n::text)
                END;

    SELECT net.http_post(
      url := 'https://api.github.com/repos/' || v_row.target_repo || '/actions/workflows/' || v_row.target_workflow || '/dispatches',
      body := jsonb_build_object('ref','main','inputs', v_inputs),
      headers := jsonb_build_object(
        'Authorization','Bearer ' || v_pat,
        'Accept','application/vnd.github+json',
        'Content-Type','application/json',
        'X-GitHub-Api-Version','2022-11-28',
        'User-Agent','everest-dispatcher-v8-zeroquarantine'
      )
    ) INTO v_req2_id;

    UPDATE public.summit_chat_dispatch
      SET state='issue_created', github_issue_number=v_issue_n, github_issue_url=v_issue_url,
          delivery_proof = delivery_proof || jsonb_build_object(
            'phase2_dispatch_request_id', v_req2_id, 'issue_created_at', now())
      WHERE id = v_row.id;

    RETURN QUERY SELECT v_row.id, 'issue_created_dispatched'::text, format('#%s dispatch_req=%s', v_issue_n, v_req2_id);
  END LOOP;
END;
$function$;

-- Non-critical row correction, scoped to this triage's assigned issue only
-- (per PARALLEL-FLEET boundaries): cc_redispatch_guard for #10179 was gating
-- on the wrong shard (flagler,bradford) instead of the shard actually posted
-- to GitHub (holmes,union). Reset attempts so the standing campaign resumes.
UPDATE public.cc_redispatch_guard
SET dod_sql = $$SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications WHERE county_slug = ANY(ARRAY['duval','sarasota','holmes','union']) AND certified)$$,
    task_label = 'GOLD STANDARD SHARD-14: duval, sarasota, holmes, union — parallel 6h session (SHIP TO MAIN)',
    attempts = 0,
    status = 'active',
    last_error = NULL
WHERE issue_number = 10179;
