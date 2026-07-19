-- GTM-22H (issue #12807): Revocation hysteresis N=3, absence-of-evidence
-- protection, persisted revocation reason, warn-before-revoke.
--
-- Builds on GTM-22C (20260719_gtm22c_certify_revocation_hysteresis_n2.sql,
-- commit 56481ff8), which raised the revoke threshold from 1 to 2 consecutive
-- evaluated non-gold runs. This migration raises it again to 3, and closes
-- three gaps the N=2 fix explicitly left open per its own session report:
--   1. Revocation reason was only ever surfaced via the function's jsonb
--      return value + Telegram -- never persisted, so it wasn't queryable
--      after the fact without reconstructing it from raw evidence tables.
--   2. A county with a partial run (fewer than 10 of the 10 A-J letters
--      actually attempted) was still treated as a real non-gold evaluation
--      and counted as a strike. Verified live: 5 (county, loop_run_id) pairs
--      -- madison/union/osceola/collier/holmes at loop_run_id=506 -- have
--      only 2 of 10 letters (C, D) present. Under the prior logic this is
--      indistinguishable from "evaluated all 10, failed genuinely" -- exactly
--      the ambiguity this ticket exists to remove.
--   3. No warning existed before a certified county actually lost
--      certification -- the first visible signal was the revocation itself.
--
-- Fix:
--   - Revoke threshold raised from 2 to 3 consecutive EVALUATED non-gold
--     runs (certify threshold, 2 consecutive gold runs, is UNCHANGED).
--   - A county's run is only counted as "evaluated" if it has all 10 DISTINCT
--     A-J letters present in gold_standard_county_status for that
--     loop_run_id (count(DISTINCT letter) = 10). This does not touch what
--     PASS/FAIL means for any single letter, is_gold's criteria, or
--     pencil_dod_evaluate_county -- it only gates whether an incomplete run
--     is allowed to count as a real evaluation at all. A county missing this
--     gate (not evaluated, or partial) is excluded from _cert_latest exactly
--     like a county absent from the run entirely -- untouched: no strike, no
--     change to certified/consecutive_gold/consecutive_non_gold.
--     NOTE: 4 (county, loop_run_id) pairs (duval@110, duval@112, gulf@1319,
--     levy@1319) have duplicate rows per letter (e.g. 20 rows instead of 10)
--     with occasionally conflicting PASS/FAIL on the same letter. This is a
--     pre-existing upstream ingestion duplication bug in whatever writes
--     gold_standard_county_status, unrelated to revocation hysteresis. It is
--     NOT fixed here (fixing it would touch the evaluator/ingestion, out of
--     scope per this ticket's own non-goals) -- flagged for follow-up only.
--   - revocation_reason (new column) is persisted on the certification row
--     itself at the moment of revocation: which criterion failed, the
--     loop_run_id, and the strike count that triggered it. Not cleared on
--     recertification -- it is a historical log, most recent revocation.
--   - last_evaluated_run_id (new column) is stamped every time a county is
--     evaluated (gold or not), independent of last_verified_run (kept
--     unchanged for backward compatibility with existing readers).
--   - On strike 1 and strike 2 (consecutive_non_gold becomes 1 or 2), a
--     public.insights row is written (severity encoded in
--     properties_affected/description -- insights has no severity column
--     and none is authorized by this ticket's DDL) naming the county and
--     strike count, so a starvation cascade is visible two ticks before it
--     costs a certification instead of zero.
--
-- Non-goals (unchanged): is_gold criteria, the A-J evaluator,
-- pencil_dod_evaluate_county, and gold_standard_scoreboard are not touched.
-- No previously revoked county is auto-restored by this migration.

ALTER TABLE gold_standard_certifications
  ADD COLUMN IF NOT EXISTS consecutive_non_gold integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS revocation_reason text,
  ADD COLUMN IF NOT EXISTS last_evaluated_run_id bigint;

CREATE OR REPLACE FUNCTION public.gold_standard_certify()
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_run bigint; v_new int := 0; v_revoked int := 0;
  v_blocked text[]; v_guard_blocked text[]; v_revoked_reasons text[];
BEGIN
  SELECT max(loop_run_id) INTO v_run FROM gold_standard_county_status;
  IF v_run IS NULL THEN RETURN jsonb_build_object('status','no_runs'); END IF;

  -- Only counties with all 10 distinct A-J letters present for this run are
  -- treated as "evaluated". A county with fewer (partial run) is excluded
  -- entirely below, same as a county absent from the run -- not a strike.
  CREATE TEMP TABLE _cert_latest ON COMMIT DROP AS
  WITH passes AS (
    SELECT county_slug, count(*) FILTER (WHERE status='PASS') = 10 AS ten_pass
    FROM gold_standard_county_status WHERE loop_run_id = v_run
    GROUP BY 1 HAVING count(DISTINCT letter) = 10
  ), latest_audit AS (
    SELECT DISTINCT ON (county_slug, letter) county_slug, letter, survived
    FROM gold_standard_ultraloop_audit
    WHERE created_at > now() - interval '7 days'
    ORDER BY county_slug, letter, created_at DESC
  ), evidence AS (
    SELECT county_slug, count(DISTINCT letter) AS letters_survived
    FROM latest_audit WHERE survived GROUP BY 1
  ), latest_guards AS (
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
                    AND coalesce(g.parity_ok,false) AND coalesce(g.denom_ok,false) AS is_gold,
         concat_ws('+',
           CASE WHEN NOT p.ten_pass THEN 'letters_failed' END,
           CASE WHEN coalesce(e.letters_survived,0) < 10 THEN 'adversarial_survival_' || coalesce(e.letters_survived,0) || '_of_10' END,
           CASE WHEN NOT coalesce(g.parity_ok,false) THEN 'no_calendar_parity' END,
           CASE WHEN NOT coalesce(g.denom_ok,false) THEN 'no_denominator_integrity' END) AS reason_detail
  FROM passes p LEFT JOIN evidence e USING (county_slug) LEFT JOIN guards g USING (county_slug);

  SELECT coalesce(array_agg(county_slug), ARRAY[]::text[]) INTO v_blocked
  FROM _cert_latest WHERE ten_pass AND NOT is_gold;
  SELECT coalesce(array_agg(county_slug || ':' ||
           concat_ws('+', CASE WHEN NOT parity_ok THEN 'no_calendar_parity' END,
                          CASE WHEN NOT denom_ok  THEN 'no_denominator_integrity' END)), ARRAY[]::text[])
    INTO v_guard_blocked
  FROM _cert_latest WHERE ten_pass AND (NOT parity_ok OR NOT denom_ok);

  -- Pre-update snapshot of certified state, used below to detect a genuine
  -- true->false TRANSITION (a real revocation event) rather than merely
  -- "certified is currently false" (true for every already-revoked county on
  -- every subsequent failing run, which is not a new event).
  CREATE TEMP TABLE _cert_before ON COMMIT DROP AS
  SELECT county_slug, certified FROM gold_standard_certifications
  WHERE county_slug IN (SELECT county_slug FROM _cert_latest);

  -- Materializing the upsert's RETURNING into a temp table (rather than
  -- aggregating it away into scalars, as the prior version did) is what lets
  -- the strike-warning and revocation-reason logic below key off "rows this
  -- exact call actually touched" instead of a recency heuristic. The WHERE
  -- clause on DO UPDATE means RETURNING contains ONLY counties whose row
  -- actually changed this call: if gold_standard_certify() is invoked twice
  -- for the same v_run (no new loop_run_id), the second call's UPDATE is a
  -- no-op for every already-processed county and _cert_upserted comes back
  -- empty for them -- no duplicate strike warnings, no duplicate revocation
  -- notifications, regardless of how much wall-clock time elapsed between
  -- the two calls (a fixed "now() - interval" recency window cannot make
  -- that guarantee, since a second call one second later would still fall
  -- inside any such window).
  CREATE TEMP TABLE _cert_upserted ON COMMIT DROP AS
  WITH upserted AS (
    INSERT INTO gold_standard_certifications AS c
           (county_slug, consecutive_gold, consecutive_non_gold, last_verified_run,
            last_evaluated_run_id, updated_at)
    SELECT county_slug, CASE WHEN is_gold THEN 1 ELSE 0 END,
                        CASE WHEN is_gold THEN 0 ELSE 1 END, v_run, v_run, now()
    FROM _cert_latest
    ON CONFLICT (county_slug) DO UPDATE SET
      consecutive_gold = CASE WHEN (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
                              THEN c.consecutive_gold + 1 ELSE 0 END,
      consecutive_non_gold = CASE WHEN (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
                              THEN 0 ELSE c.consecutive_non_gold + 1 END,
      -- earn: 2 consecutive gold runs (unchanged). revoke: 3 consecutive
      -- evaluated non-gold runs (was: 2 under GTM-22C, 1 originally). A
      -- streak below 3 HOLDS the existing certified value.
      certified = CASE
        WHEN (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
             AND c.consecutive_gold + 1 >= 2 THEN true
        WHEN NOT (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
             AND c.consecutive_non_gold + 1 >= 3 THEN false
        ELSE c.certified END,
      first_certified_at = CASE
        WHEN (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
             AND c.consecutive_gold + 1 >= 2 AND c.first_certified_at IS NULL THEN now()
        ELSE c.first_certified_at END,
      revoked_at = CASE
        WHEN (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
             AND c.consecutive_gold + 1 >= 2 THEN NULL
        WHEN c.certified AND NOT (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
             AND c.consecutive_non_gold + 1 >= 3 THEN now()
        ELSE c.revoked_at END,
      revocation_reason = CASE
        WHEN NOT (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
             AND c.consecutive_non_gold + 1 >= 3 THEN
          c.county_slug || ' run=' || v_run || ' consecutive_non_gold=' || (c.consecutive_non_gold + 1) ||
          ' reason=' || (SELECT reason_detail FROM _cert_latest l WHERE l.county_slug = c.county_slug)
        ELSE c.revocation_reason END,
      last_verified_run = v_run, last_evaluated_run_id = v_run, updated_at = now()
      WHERE c.last_verified_run IS DISTINCT FROM v_run
    RETURNING c.county_slug, c.certified, c.revoked_at, c.consecutive_non_gold, c.revocation_reason
  )
  SELECT * FROM upserted;

  SELECT count(*) FILTER (WHERE u.certified),
         count(*) FILTER (WHERE b.certified AND NOT u.certified)
    INTO v_new, v_revoked
  FROM _cert_upserted u LEFT JOIN _cert_before b USING (county_slug);

  -- Strike warnings: fires exactly once per non-gold streak at strike 1 and
  -- once at strike 2, because consecutive_non_gold strictly increases by 1
  -- per non-gold run within a streak (it can only be 1 or 2 on the run it
  -- first reaches that value, and only ever appears in _cert_upserted -- see
  -- above -- on the run where it actually changed). Visible BEFORE the
  -- 3rd-strike revocation.
  INSERT INTO public.insights (county, sale_type, anomaly_type, description, properties_affected, detected_at)
  SELECT u.county_slug, 'both', 'gtm22h_revocation_strike_warn',
         'severity=warn county=' || u.county_slug || ' strike=' || u.consecutive_non_gold ||
         '/3 loop_run_id=' || v_run || ' reason=' || l.reason_detail,
         jsonb_build_object('severity','warn','county',u.county_slug,'strike',u.consecutive_non_gold,
                             'threshold',3,'loop_run_id',v_run,'reason',l.reason_detail),
         now()
  FROM _cert_upserted u
  JOIN _cert_latest l USING (county_slug)
  WHERE u.consecutive_non_gold IN (1,2);

  -- Revoked-this-call = present in _cert_upserted (genuinely touched) AND a
  -- true->false transition versus the pre-update snapshot. This is what a
  -- county already revoked weeks ago and still failing every run does NOT
  -- match (certified was already false going in), so it does not re-fire.
  SELECT coalesce(array_agg(u.revocation_reason), ARRAY[]::text[]) INTO v_revoked_reasons
  FROM _cert_upserted u JOIN _cert_before b USING (county_slug)
  WHERE b.certified AND NOT u.certified;

  IF array_length(v_blocked,1) > 0 THEN
    PERFORM public.fire_workflow_dispatch('breverdbidder/cli-anything-biddeed','telegram-notify.yml','main',
      jsonb_build_object('message', '🚫 CERT GATE: ' || array_to_string(v_blocked, ', ') ||
        ' hit 10/10 PASS but failed the gate. Guard failures: ' ||
        coalesce(array_to_string(v_guard_blocked, ' | '),'(adversarial-survival only)') ||
        '. Certification BLOCKED. System working as designed.'));
  END IF;

  IF array_length(v_revoked_reasons,1) > 0 THEN
    PERFORM public.fire_workflow_dispatch('breverdbidder/cli-anything-biddeed','telegram-notify.yml','main',
      jsonb_build_object('message', '🔻 CERT REVOKED (N=3 hysteresis, 3rd consecutive evaluated non-gold run): ' ||
        array_to_string(v_revoked_reasons, ' | ')));
  END IF;

  RETURN jsonb_build_object('run', v_run, 'certified_now', v_new, 'revoked_now', v_revoked,
                            'revoked_reasons', v_revoked_reasons,
                            'blocked', v_blocked, 'guard_blocked', v_guard_blocked);
END $function$;
