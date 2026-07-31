-- COST-FIX-4: launch_gold_standard_fleet -- skip gate-ready counties CC
-- cannot help.
--
-- 15 counties sit at 10/10 pass with both precert guards (calendar_parity,
-- denominator_integrity) green in the trailing 7 days. The only thing still
-- blocking gold certification for those counties is adversarial_survival --
-- time-series evidence accumulated across gold_standard_ultraloop_audit rows
-- from prior loop runs, not something a CC session can produce on demand.
-- launch_gold_standard_fleet() was still ranking and launching full 6h CC
-- sessions on these counties every cycle, burning cost for zero possible
-- progress. FIX: exclude gate-ready counties (10/10 pass + both guards
-- green) from the shard candidate ranking, same place the existing
-- alive-campaign / active-watchdog exclusions live. All other logic (shard
-- count, per-shard size, stagger sleep) unchanged.

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
        -- COST GATE: skip gate-ready counties -- 10/10 pass with both
        -- precert guards green means the only residual is
        -- adversarial_survival, which a CC session cannot fix.
        AND NOT (
          sb.pass_count = 10
          AND EXISTS (SELECT 1 FROM gold_standard_precert_guards g WHERE g.county_slug=sb.county_slug
                      AND g.guard_type='calendar_parity' AND g.passed AND g.created_at > now()-interval '7 days')
          AND EXISTS (SELECT 1 FROM gold_standard_precert_guards g WHERE g.county_slug=sb.county_slug
                      AND g.guard_type='denominator_integrity' AND g.passed AND g.created_at > now()-interval '7 days')
        )
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
