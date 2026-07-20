-- Architect triage, issue #12866 (Gold Standard shard-2: hendry/okeechobee/bay/gulf)
-- dispatch_id: 9f630661-2838-44c5-8cdd-607b9b555be9
--
-- ROOT CAUSE (VERIFIED live, 2026-07-20): gold_standard_certify()'s `latest_audit` CTE
-- picks the adversarial-survival verdict for each (county_slug, letter) via
--   DISTINCT ON (county_slug, letter) ... ORDER BY county_slug, letter, created_at DESC
-- with NO tiebreaker beyond created_at. gold_standard_ultraloop_audit routinely receives
-- multiple independent sub-claim rows for the same letter in one batch insert, which land
-- with an IDENTICAL created_at timestamp (same statement's now()). Reproduced live:
-- okeechobee letter I has 3 rows at created_at=2026-07-19 20:43:36.191317+00 (ids 7379,
-- 7380 survived=true; id 7384 survived=false, documenting 2 genuinely-orphaned parcels
-- still blocked by Cloudflare Turnstile on OCRS). On an exact-timestamp tie, Postgres'
-- DISTINCT ON has no defined winner, so successive gold_standard_certify() calls against
-- the SAME loop_run_id observed letters_survived flip between 10/10 and 9/10 for
-- okeechobee with no underlying data change -- confirmed by running certify() twice in
-- this session and diffing the printed evidence counts.
--
-- FIX: add a deterministic, fail-closed tiebreaker: on an exact created_at tie, prefer
-- survived=false (ASC puts false before true) so a genuinely-disputed/ambiguous claim set
-- for a letter never silently rounds up to "survived" by accident of row insertion order.
-- `id DESC` is added last purely for full determinism among same-verdict ties (does not
-- change the aggregated boolean any CTE consumer sees). This is a pure tiebreak fix -- it
-- does not change behavior for the overwhelming majority of (county,letter) pairs that
-- have no created_at collision.
--
-- HONESTY MARKER: VERIFIED (reproduced the flip live via two back-to-back certify() calls
-- against loop_run_id=5493; confirmed via direct SELECT of the 3 colliding rows).

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
    ORDER BY county_slug, letter, created_at DESC, survived ASC, id DESC
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
