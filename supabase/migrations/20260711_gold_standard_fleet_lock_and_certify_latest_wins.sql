-- Fix Gold Standard cert thrash, continuation (issue #11593, dispatch c21e1624).
--
-- The prior fix (27a01c9c, same dispatch) closed the direct race between
-- gold_loop_watchdog and gold_standard_autopilot by wiring in
-- gold_county_has_alive_campaign / gold_county_has_active_watchdog. That fix
-- is confirmed live and did NOT fully close the thrash: flagler B/F flipped
-- FAIL(01:50:47)->PASS(02:01:57) in gold_standard_ultraloop_audit within the
-- first 3h after that deploy (verified via live REST query, 2026-07-11).
--
-- ROOT CAUSE #1 (CONFIRMED, closes an unaddressed launch-race gap):
-- public.launch_gold_standard_fleet() -- called 3x/day by cron jobs
-- gold-standard-session-am/pm/night, NOT one of the 4 originally-named 5-min
-- jobs -- has ZERO mutual-exclusion check. It blindly re-partitions ALL
-- uncertified counties into shards and launches a fresh parallel session for
-- each shard every 8 hours, with no check for whether a prior fleet cycle's
-- session on the same county is still alive (gold_standard_campaign proves
-- flagler was targeted by SHARD-1/3483/3485/3489/3497, SHARD-9/3534,
-- SHARD-6/3645, SHARD-5/3679 -- every single 8h cycle since 2026-07-08,
-- never excluded). The prior fix wired the lock-check helpers into
-- gold_loop_watchdog and gold_standard_autopilot only; this function was
-- missed. FIX: same exclusion checks, applied during candidate ranking so
-- the shard partition stays deterministic and non-overlapping.
--
-- ROOT CAUSE #2 (CONFIRMED via row-level inspection of
-- gold_standard_ultraloop_audit, the deeper mechanism -- not a concurrent-
-- write race but a semantics bug that AMPLIFIES any noise into visible
-- cert-flag thrash): public.gold_standard_certify()'s "letters_survived"
-- count uses OR-semantics -- ANY row with survived=true in the trailing 7
-- days counts that letter as survived, forever, regardless of what a LATER
-- row for the same county+letter says. Independent CC sessions do not use a
-- consistent convention for `survived`: e.g. gold_standard_ultraloop_audit
-- id=4974 (flagler, letter B, 2026-07-11 02:01:57) has claim text
-- "Independently verified: fresh RPC pass=false ... Genuine residual,
-- correctly reported as FAIL" yet survived=true (here `survived` means "the
-- adversarial audit of this claim holds up", not "the criterion passes").
-- Because certify()'s query only cares about the boolean, a row like this
-- keeps a genuinely-FAILing letter counted as "survived" for up to 7 days.
-- Combined with the existing revoke-on-any-not-gold-run branch, a single
-- noisy evaluation of letters_survived can flip `certified` off (or on) with
-- no real regression/fix having occurred -- this is the actual mechanism
-- behind "Charlotte gold at 7:05am, not gold at 9:30am" and counties
-- flipping in/out of the digest's "Gold certified: N/67" figure.
-- FIX: use the MOST RECENT audit row per (county_slug, letter) instead of
-- any-ever-true. This is a strict tightening, not a loosening: a stale true
-- row can no longer indefinitely outrank a later, fresher finding for the
-- SAME letter in either direction. ten_pass, calendar-parity, and
-- denominator-integrity gates are untouched.
--
-- NOTE (residual, out of scope for this migration): individual CC sessions
-- still write ad hoc INSERTs to gold_standard_ultraloop_audit with
-- inconsistent `survived` conventions. This migration cannot rewrite future
-- agent-authored migrations' wording. It removes that noise's ability to
-- move the certified flag; it does not guarantee the raw audit table itself
-- will never show a same-letter true/false pair from one session's own
-- diagnose-then-verify workflow. Flagged for follow-up, not silently
-- dropped.

BEGIN;

-- ============================================================================
-- 1. launch_gold_standard_fleet -- exclude counties an alive campaign or
--    active watchdog session already owns from shard candidate ranking.
--    All other logic (shard count, per-shard size, stagger sleep) unchanged.
-- ============================================================================
CREATE OR REPLACE FUNCTION public.launch_gold_standard_fleet(p_shards integer DEFAULT 5, p_per_shard integer DEFAULT 3)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_result jsonb := '[]'::jsonb; v_one jsonb; i int; v_targets text[];
BEGIN
  FOR i IN 1..p_shards LOOP
    SELECT array_agg(county_slug) INTO v_targets FROM (
      SELECT county_slug, row_number() OVER (ORDER BY pass_count DESC, county_slug) AS rn
      FROM gold_standard_scoreboard sb
      WHERE NOT EXISTS (SELECT 1 FROM gold_standard_certifications c
                         WHERE c.county_slug = sb.county_slug AND c.certified)
        -- RACE FIX: don't re-launch a session on a county a prior fleet
        -- cycle (or watchdog) already has an alive session on.
        AND NOT public.gold_county_has_alive_campaign(sb.county_slug)
        AND NOT public.gold_county_has_active_watchdog(sb.county_slug)
    ) ranked
    WHERE (rn - 1) % p_shards = (i - 1) AND rn <= p_shards * p_per_shard;

    IF v_targets IS NOT NULL THEN
      v_one := public.launch_gold_standard_session(v_targets, 'SHARD-' || i);
      v_result := v_result || jsonb_build_array(v_one);
      PERFORM pg_sleep(3);  -- stagger dispatches
    END IF;
  END LOOP;
  RETURN jsonb_build_object('shards_launched', jsonb_array_length(v_result), 'sessions', v_result);
END $function$;

-- ============================================================================
-- 2. gold_standard_certify -- letters_survived = latest audit row per letter,
--    not any-ever-true-in-7-days. ten_pass / guards / idempotency-per-run
--    (Jul 10 #11368 fix) unchanged.
-- ============================================================================
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

COMMIT;
