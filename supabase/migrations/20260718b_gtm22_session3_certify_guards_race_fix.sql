-- GTM-22 Session 3: gold_standard_certify() precert-guard evidence race fix
--
-- Discovered while regenerating Duval/Manatee/Polk/Brevard ultraloop_audit
-- evidence: the guards CTE used bool_or(passed) across the full 7-day
-- window, so a stale PASS from earlier in the week can mask a currently
-- FAILING guard. This is the exact same evidence-staleness class the
-- ultraloop_audit CTE was already race-fixed for ("RACE FIX: most recent
-- adversarial assessment... wins" comment, present since prior session) --
-- the guards CTE just never got the same treatment.
--
-- Scope-checked against all 67 counties before writing this: exactly one
-- county is currently affected -- brevard's calendar_parity guard has
-- failed every day since at least 2026-07-14 (c_metric 94.9-95.0%, see
-- insights.id=c61a42e5 for the root cause: gold_standard_precert_guard_
-- refresh.py evaluates unscoped/live data, ignoring brevard's authorized
-- snapshot freeze) but an older PASS row inside the 7-day window was
-- letting bool_or() mask it. Without this fix, re-enabling the frozen
-- crons risks brevard silently accruing consecutive_gold off a guard that
-- is not actually passing right now. Duval/manatee/polk unaffected either
-- way (their guards have been genuinely, currently passing every day).
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
  ), latest_audit AS (
    -- RACE FIX: most recent adversarial assessment per (county, letter) wins
    -- -- a stale survived=true row can no longer outrank a later, fresher
    -- finding for the same letter (was: ANY true in trailing 7 days, which
    -- let noise/ambiguous historical rows keep a letter counted forever).
    SELECT DISTINCT ON (county_slug, letter) county_slug, letter, survived
    FROM gold_standard_ultraloop_audit
    WHERE created_at > now() - interval '7 days'
    ORDER BY county_slug, letter, created_at DESC
  ), evidence AS (
    SELECT county_slug, count(DISTINCT letter) AS letters_survived
    FROM latest_audit WHERE survived GROUP BY 1
  ), latest_guards AS (
    -- RACE FIX (same class as latest_audit above): most recent guard row
    -- per (county, guard_type) wins -- a stale PASS from earlier in the
    -- 7-day window can no longer mask a currently-failing guard.
    SELECT DISTINCT ON (county_slug, guard_type) county_slug, guard_type, passed
    FROM gold_standard_precert_guards
    WHERE created_at > now() - interval '7 days'
    ORDER BY county_slug, guard_type, created_at DESC
  ), guards AS (
    SELECT county_slug,
           bool_or(guard_type='calendar_parity'      AND passed) AS parity_ok,
           bool_or(guard_type='denominator_integrity' AND passed) AS denom_ok
    FROM latest_guards GROUP BY 1
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
      revoked_at = CASE
        WHEN (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
             AND c.consecutive_gold + 1 >= 2 THEN NULL
        WHEN c.certified AND NOT (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug) THEN now()
        ELSE c.revoked_at END,
      last_verified_run = v_run, updated_at = now()
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
END $function$;
