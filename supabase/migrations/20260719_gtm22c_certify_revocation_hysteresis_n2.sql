-- GTM-22C: Revocation hysteresis (N=2) for gold_standard_certify()
--
-- Problem (verified against live DB 2026-07-19): certification is earned over
-- 2 consecutive gold runs but revoked on a single non-gold run. A transient
-- infra hiccup (one bad evaluation) destroys certification as fast as real
-- data degradation does. 54 counties were ever certified; only 11 remain
-- certified; 43 were revoked, many in tight batches at identical timestamps
-- (e.g. 13 counties revoked simultaneously at 2026-07-02 13:30:00), consistent
-- with a single bad loop_run flipping many counties at once rather than 43
-- independent real regressions.
--
-- Fix: require 2 consecutive evaluated non-gold runs to revoke, mirroring the
-- 2 consecutive gold runs required to certify. A county not represented in the
-- latest loop_run (partial/incomplete run) is already excluded from the
-- temp-table join below (_cert_latest only contains counties with rows for
-- loop_run_id = v_run) — that county's row is untouched entirely: no INSERT,
-- no UPDATE. This was already correct in the prior version; it is preserved
-- here, not changed.
--
-- is_gold criteria (ten_pass, letters_survived=10, parity_ok, denom_ok) are
-- UNCHANGED. Only the certified/revoked_at transition logic changes.

ALTER TABLE gold_standard_certifications
  ADD COLUMN IF NOT EXISTS consecutive_non_gold integer NOT NULL DEFAULT 0;

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
  CREATE TEMP TABLE _cert_latest ON COMMIT DROP AS
  WITH passes AS (
    SELECT county_slug, count(*) FILTER (WHERE status='PASS') = 10 AS ten_pass
    FROM gold_standard_county_status WHERE loop_run_id = v_run GROUP BY 1
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
    INSERT INTO gold_standard_certifications AS c
           (county_slug, consecutive_gold, consecutive_non_gold, last_verified_run, updated_at)
    SELECT county_slug, CASE WHEN is_gold THEN 1 ELSE 0 END,
                        CASE WHEN is_gold THEN 0 ELSE 1 END, v_run, now()
    FROM _cert_latest
    ON CONFLICT (county_slug) DO UPDATE SET
      consecutive_gold = CASE WHEN (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
                              THEN c.consecutive_gold + 1 ELSE 0 END,
      consecutive_non_gold = CASE WHEN (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
                              THEN 0 ELSE c.consecutive_non_gold + 1 END,
      -- earn: 2 consecutive gold runs (unchanged). revoke: 2 consecutive evaluated
      -- non-gold runs (was: 1). A single non-gold run now HOLDS the existing
      -- certified value instead of clearing it.
      certified = CASE
        WHEN (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
             AND c.consecutive_gold + 1 >= 2 THEN true
        WHEN NOT (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
             AND c.consecutive_non_gold + 1 >= 2 THEN false
        ELSE c.certified END,
      first_certified_at = CASE
        WHEN (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
             AND c.consecutive_gold + 1 >= 2 AND c.first_certified_at IS NULL THEN now()
        ELSE c.first_certified_at END,
      revoked_at = CASE
        WHEN (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
             AND c.consecutive_gold + 1 >= 2 THEN NULL
        WHEN c.certified AND NOT (SELECT is_gold FROM _cert_latest l WHERE l.county_slug = c.county_slug)
             AND c.consecutive_non_gold + 1 >= 2 THEN now()
        ELSE c.revoked_at END,
      last_verified_run = v_run, updated_at = now()
      WHERE c.last_verified_run IS DISTINCT FROM v_run
    RETURNING c.county_slug, c.certified, c.revoked_at, c.consecutive_non_gold
  )
  SELECT count(*) FILTER (WHERE certified),
         count(*) FILTER (WHERE revoked_at >= now() - interval '1 minute')
    INTO v_new, v_revoked FROM upserted;

  -- Revocation reason log. No new column authorized beyond consecutive_non_gold,
  -- so the reason (which criterion failed, on which loop_run_id, at what
  -- consecutive_non_gold count) is surfaced via this function's own jsonb
  -- return value and via the existing Telegram notification channel. It is
  -- also always reconstructable after the fact by joining last_verified_run
  -- (the loop_run_id) to gold_standard_county_status's per-letter columns and
  -- to gold_standard_precert_guards / gold_standard_ultraloop_audit.
  WITH revoked_now AS (
    SELECT * FROM (
      SELECT c.county_slug, c.revoked_at, c.consecutive_non_gold
      FROM gold_standard_certifications c
      WHERE c.last_verified_run = v_run AND c.revoked_at >= now() - interval '1 minute'
    ) x
  )
  SELECT coalesce(array_agg(
           r.county_slug || ' run=' || v_run || ' consecutive_non_gold=' || r.consecutive_non_gold || ' reason=' ||
           concat_ws('+',
             CASE WHEN NOT l.ten_pass THEN 'letters_failed' END,
             CASE WHEN l.letters_survived < 10 THEN 'adversarial_survival_' || l.letters_survived || '_of_10' END,
             CASE WHEN NOT l.parity_ok THEN 'no_calendar_parity' END,
             CASE WHEN NOT l.denom_ok THEN 'no_denominator_integrity' END)
         ), ARRAY[]::text[])
    INTO v_revoked_reasons
  FROM revoked_now r JOIN _cert_latest l ON l.county_slug = r.county_slug;

  IF array_length(v_blocked,1) > 0 THEN
    PERFORM public.fire_workflow_dispatch('breverdbidder/cli-anything-biddeed','telegram-notify.yml','main',
      jsonb_build_object('message', '🚫 CERT GATE: ' || array_to_string(v_blocked, ', ') ||
        ' hit 10/10 PASS but failed the gate. Guard failures: ' ||
        coalesce(array_to_string(v_guard_blocked, ' | '),'(adversarial-survival only)') ||
        '. Certification BLOCKED. System working as designed.'));
  END IF;

  IF array_length(v_revoked_reasons,1) > 0 THEN
    PERFORM public.fire_workflow_dispatch('breverdbidder/cli-anything-biddeed','telegram-notify.yml','main',
      jsonb_build_object('message', '🔻 CERT REVOKED (N=2 hysteresis, 2nd consecutive non-gold run): ' ||
        array_to_string(v_revoked_reasons, ' | ')));
  END IF;

  RETURN jsonb_build_object('run', v_run, 'certified_now', v_new, 'revoked_now', v_revoked,
                            'revoked_reasons', v_revoked_reasons,
                            'blocked', v_blocked, 'guard_blocked', v_guard_blocked);
END $function$;
