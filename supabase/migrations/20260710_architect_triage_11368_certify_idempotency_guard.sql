-- ARCHITECT TRIAGE (issue #11368, dispatch_id=b223b2fc-6993-4279-963a-2de9aeb65133)
--
-- BUG FOUND (not the DoD blocker, but a latent correctness risk found while
-- diagnosing why marion/pinellas/orange/hamilton are not certified):
-- public.gold_standard_certify() always increments consecutive_gold based on
-- is_gold for the LATEST gold_standard_county_status.loop_run_id, with no
-- check that this run_id was already the one it certified against last time.
-- Calling certify() twice against the SAME loop run (e.g. two GHA attempts in
-- one session both closing out and calling certify() without a fresh
-- gold_standard_loop() run in between) would double-increment
-- consecutive_gold and could flip certified=true off a single day's data --
-- exactly the "second consecutive DAILY 07:30Z run" gate the design intends
-- to prevent. marion is currently sitting at consecutive_gold=1 off run 3531
-- (2026-07-10 01:30Z) and is the closest county to certifying in this shard;
-- this fix ensures its second day is genuine, not a re-run artifact.
--
-- FIX: skip the UPDATE branch entirely when this county's last_verified_run
-- already equals the run being processed (idempotent re-invocation is now a
-- true no-op instead of a second increment).

CREATE OR REPLACE FUNCTION public.gold_standard_certify()
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE v_run bigint; v_new int := 0; v_revoked int := 0; v_blocked text[]; v_guard_blocked text[];
BEGIN
  SELECT max(loop_run_id) INTO v_run FROM gold_standard_county_status;
  IF v_run IS NULL THEN RETURN jsonb_build_object('status','no_runs'); END IF;
  CREATE TEMP TABLE _cert_latest ON COMMIT DROP AS
  WITH passes AS (
    SELECT county_slug, count(*) FILTER (WHERE status='PASS') = 10 AS ten_pass
    FROM gold_standard_county_status WHERE loop_run_id = v_run GROUP BY 1
  ), evidence AS (
    SELECT county_slug, count(DISTINCT letter) AS letters_survived
    FROM gold_standard_ultraloop_audit
    WHERE survived AND created_at > now() - interval '7 days' GROUP BY 1
  ), guards AS (
    SELECT county_slug,
           bool_or(guard_type='calendar_parity'      AND passed) AS parity_ok,
           bool_or(guard_type='denominator_integrity' AND passed) AS denom_ok
    FROM gold_standard_precert_guards
    WHERE created_at > now() - interval '7 days' GROUP BY 1
  )
  SELECT p.county_slug, p.ten_pass,
         coalesce(e.letters_survived,0) AS letters_survived,
         coalesce(g.parity_ok,false) AS parity_ok, coalesce(g.denom_ok,false) AS denom_ok,
         p.ten_pass AND coalesce(e.letters_survived,0)=10
                    AND coalesce(g.parity_ok,false) AND coalesce(g.denom_ok,false) AS is_gold
  FROM passes p LEFT JOIN evidence e USING (county_slug) LEFT JOIN guards g USING (county_slug);

  SELECT coalesce(array_agg(county_slug), ARRAY[]::text[]) INTO v_blocked
  FROM _cert_latest WHERE ten_pass AND NOT is_gold;
  SELECT coalesce(array_agg(county_slug || ':' ||
           concat_ws('+', CASE WHEN NOT parity_ok THEN 'no_calendar_parity' END,
                          CASE WHEN NOT denom_ok  THEN 'no_denominator_integrity' END)), ARRAY[]::text[])
    INTO v_guard_blocked
  FROM _cert_latest WHERE ten_pass AND (NOT parity_ok OR NOT denom_ok);

  WITH upserted AS (
    INSERT INTO gold_standard_certifications AS c (county_slug, consecutive_gold, last_verified_run, updated_at)
    SELECT county_slug, CASE WHEN is_gold THEN 1 ELSE 0 END, v_run, now() FROM _cert_latest
    ON CONFLICT (county_slug) DO UPDATE SET
      consecutive_gold = CASE WHEN (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
                              THEN c.consecutive_gold + 1 ELSE 0 END,
      certified = CASE
        WHEN (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
             AND c.consecutive_gold + 1 >= 2 THEN true
        WHEN NOT (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug) THEN false
        ELSE c.certified END,
      first_certified_at = CASE
        WHEN (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
             AND c.consecutive_gold + 1 >= 2 AND c.first_certified_at IS NULL THEN now()
        ELSE c.first_certified_at END,
      -- FIX (Jul 9 2026): clear stale revocation when county re-earns gold; set on fresh loss
      revoked_at = CASE
        WHEN (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
             AND c.consecutive_gold + 1 >= 2 THEN NULL
        WHEN c.certified AND NOT (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug) THEN now()
        ELSE c.revoked_at END,
      last_verified_run = v_run, updated_at = now()
      -- FIX (Jul 10 2026, issue #11368 architect triage): idempotency guard --
      -- a repeat call against a run_id already recorded for this county is a
      -- true no-op, so re-invoking certify() cannot double-increment
      -- consecutive_gold off a single gold_standard_loop() run.
      WHERE c.last_verified_run IS DISTINCT FROM v_run
    RETURNING certified, revoked_at
  )
  SELECT count(*) FILTER (WHERE certified),
         count(*) FILTER (WHERE revoked_at >= now() - interval '1 minute')
    INTO v_new, v_revoked FROM upserted;

  IF array_length(v_blocked,1) > 0 THEN
    PERFORM public.fire_workflow_dispatch('breverdbidder/cli-anything-biddeed','telegram-notify.yml','main',
      jsonb_build_object('message', '🚫 CERT GATE: ' || array_to_string(v_blocked, ', ') ||
        ' hit 10/10 PASS but failed the gate. Guard failures: ' ||
        coalesce(array_to_string(v_guard_blocked, ' | '),'(adversarial-survival only)') ||
        '. Certification BLOCKED. System working as designed.'));
  END IF;
  RETURN jsonb_build_object('run', v_run, 'certified_now', v_new, 'revoked_now', v_revoked,
                            'blocked', v_blocked, 'guard_blocked', v_guard_blocked);
END $function$
