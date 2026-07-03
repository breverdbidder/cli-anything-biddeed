-- SPRINT4 H1 P0-1: fix summit_chat_dispatch rows stuck at state='issue_created'.
--
-- RCA (live DB, 2026-07-03 12:xx UTC): everest_worker_phase3_confirm_dispatch()
-- looks up net._http_response by the phase2 dispatch request id and, on NOT FOUND,
-- just CONTINUEs — no quarantine, no retry counter, no timeout. net._http_response
-- rows are ephemeral (pgnet-response-trim cron deletes rows >6h old every hour;
-- this project's sequence also shows an unexplained reset — ids 1-24 from an
-- 08:00 UTC dispatch batch are gone, current table only holds ids 1-4 from ~12:05
-- UTC). 5 rows from chat_session_id='architect-20260703T080000' reference request
-- ids 15/17/20/21/22/23/24 that no longer exist, so every phase3 tick hits NOT
-- FOUND on all 5 and leaves them at 'issue_created' forever. Because the query is
-- `ORDER BY picked_up_at ASC ... LIMIT 5` these 5 dead rows sort first and
-- permanently occupy the whole LIMIT window, starving every legitimate row behind
-- them -- including this session's own two dispatch rows (req ids 3 and 4), which
-- already have real status_code=204 responses sitting in net._http_response but
-- were never reached.
--
-- Note for the record: the sprint3 rows named in this SUMMIT's DOD
-- (chat_session_id LIKE 'claude-app-2026-07-02-sprint3%') are NOT the ones
-- affected -- live query shows all 5 already at state IN ('dispatched','closed').
-- The actual 7 rows currently stuck at 'issue_created' are 5x
-- 'architect-20260703T080000' + this session's own 2 rows
-- ('claude-app-2026-07-03-sprint4-hygiene', '...-sprint4-onboarding'). Same
-- defect class, different batch -- fixed and backfilled below.
--
-- Fix: bounded wait (10 min from delivery_proof.issue_created_at, which phase2
-- sets in the same UPDATE as phase2_dispatch_request_id) then quarantine with an
-- honest reason instead of looping forever. This also unblocks the LIMIT 5 queue
-- for legitimate rows.

CREATE OR REPLACE FUNCTION public.everest_worker_phase3_confirm_dispatch()
 RETURNS TABLE(processed_id uuid, action text, detail text)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'net'
AS $function$
DECLARE
  v_row     public.summit_chat_dispatch%ROWTYPE;
  v_resp    record;
  v_req2    bigint;
  v_body_t  text;
  v_qreason text;
BEGIN
  FOR v_row IN
    SELECT * FROM public.summit_chat_dispatch
    WHERE state = 'issue_created'
      AND delivery_proof ? 'phase2_dispatch_request_id'
    ORDER BY picked_up_at ASC NULLS LAST
    LIMIT 5
    FOR UPDATE SKIP LOCKED
  LOOP
    v_req2 := (v_row.delivery_proof->>'phase2_dispatch_request_id')::bigint;
    SELECT status_code, content::text AS body_text
      INTO v_resp
      FROM net._http_response WHERE id = v_req2;

    IF NOT FOUND THEN
      -- Give pg_net a bounded window to land the response (normally lands in
      -- seconds). Past that, the response is gone for good (pruned or lost) --
      -- quarantine instead of blocking this row's LIMIT 5 slot forever.
      IF COALESCE((v_row.delivery_proof->>'issue_created_at')::timestamptz, v_row.picked_up_at, v_row.created_at)
           < now() - INTERVAL '10 minutes' THEN
        UPDATE public.summit_chat_dispatch
          SET state                = 'quarantined',
              quarantine_reason    = 'phase3_response_not_found',
              quarantine_diagnosis = format('phase3: net._http_response id=%s never landed (pruned/lost) after 10+ min wait', v_req2),
              last_error           = format('phase3: http response id=%s not found', v_req2)
          WHERE id = v_row.id;
        RETURN QUERY SELECT v_row.id, 'quarantined'::text, format('response id=%s not found after wait', v_req2);
      END IF;
      CONTINUE;
    END IF;

    IF v_resp.status_code = 204 THEN
      UPDATE public.summit_chat_dispatch
        SET state          = 'dispatched',
            delivery_proof = delivery_proof || jsonb_build_object('dispatched_at', now())
        WHERE id = v_row.id;
      RETURN QUERY SELECT v_row.id, 'dispatched'::text, 'workflow triggered'::text;

    ELSIF v_resp.status_code BETWEEN 400 AND 499 THEN
      v_body_t := COALESCE(v_resp.body_text, '');
      v_qreason := CASE
        WHEN v_body_t ILIKE '%disabled workflow%'  THEN 'workflow_disabled'
        WHEN v_body_t ILIKE '%does not exist%'     THEN 'workflow_not_found'
        WHEN v_resp.status_code = 401             THEN 'auth_failure'
        WHEN v_resp.status_code = 403             THEN 'forbidden'
        WHEN v_resp.status_code = 404             THEN 'not_found'
        ELSE format('permanent_4xx_%s', v_resp.status_code)
      END;
      UPDATE public.summit_chat_dispatch
        SET state                = 'quarantined',
            quarantine_reason    = v_qreason,
            quarantine_diagnosis = format('phase3 HTTP %s: %s', v_resp.status_code, LEFT(v_body_t, 400)),
            last_error           = format('phase3 workflow_dispatch HTTP %s', v_resp.status_code)
        WHERE id = v_row.id;
      RETURN QUERY SELECT v_row.id, 'quarantined'::text, format('http=%s reason=%s', v_resp.status_code, v_qreason);

    ELSE
      -- 5xx / network: transient, leave as failed for retry
      UPDATE public.summit_chat_dispatch
        SET state      = 'failed',
            last_error = format('phase3 workflow_dispatch HTTP %s (transient)', COALESCE(v_resp.status_code::text,'null'))
        WHERE id = v_row.id;
      RETURN QUERY SELECT v_row.id, 'failed_transient'::text, format('http=%s', v_resp.status_code);
    END IF;
  END LOOP;
END;
$function$;
