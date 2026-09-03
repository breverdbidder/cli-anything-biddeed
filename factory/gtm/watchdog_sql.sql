-- CMO FACTORY (issue #19777) -- reference copy of public.gtm_watchdog().
--
-- This is a READ-ONLY reference copy for humans/agents browsing factory/gtm/
-- without wanting to open a migration file. The authoritative, applied
-- version lives in supabase/migrations/20260903*_cmo_factory_watchdog.sql --
-- if these two ever drift, the migration file is the source of truth. Keep
-- them in sync by hand; this file is not executed by any workflow.
--
-- 7 detectors (docs/gtm/META.md SS5), reading ONLY agent_ops_log,
-- cc_redispatch_guard, campaign_agent_log, and quota_gate_check() -- no
-- GitHub API calls from inside Postgres for the detection step itself
-- (pg_net is used, best-effort, only for the control-issue comment once a
-- trip has already been decided by pure SQL/plpgsql logic).
--
-- D1 same-issue revalidated >3x/3h        -- agent_ops_log, task ~ 'gtm_validate%'
-- D2 zero merges 48h with open GTM queue  -- agent_ops_log task ~ 'gtm_merge%' count=0
--                                              AND cc_redispatch_guard has an open
--                                              (status in ('pending','blocked')) GTM row
-- D3 spend >2x 7d median                  -- campaign_agent_log duration_ms, action ~ 'gtm_%'
-- D4 3 consecutive FAILs same journey     -- campaign_agent_log action='gtm_journey_validate',
--                                              details->>'journey', success=false
-- D5 publish attempted, approval NULL     -- campaign_agent_log action ~ 'gtm_publish%',
--                                              success=true, details->>'approved_at' is null (M1)
-- D6 compliance FAIL on main              -- agent_ops_log task ~ 'gtm_compliance%',
--                                              status='BLOCKED', evidence ~ 'main'
-- D7 quota NO_READING                     -- public.quota_gate_check('engineering')
--                                              ->> 'reason' = 'NO_READING'
--
-- On any trip: upsert spi_gates row 'gtm_factory_halt' (opened_at=now() if not
-- already open -- never re-opens an already-open row, matching STOP.md's "OR,
-- not AND" halt semantics: once halted, stays halted until Ariel closes it)
-- and best-effort pg_net POST a comment to the control issue. See
-- .factory/gtm/STOP.md for the full halt/resume contract.
create or replace function public.gtm_watchdog()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_d1 boolean := false; v_d1_detail jsonb := '{}'::jsonb;
  v_d2 boolean := false; v_d2_detail jsonb := '{}'::jsonb;
  v_d3 boolean := false; v_d3_detail jsonb := '{}'::jsonb;
  v_d4 boolean := false; v_d4_detail jsonb := '{}'::jsonb;
  v_d5 boolean := false; v_d5_detail jsonb := '{}'::jsonb;
  v_d6 boolean := false; v_d6_detail jsonb := '{}'::jsonb;
  v_d7 boolean := false; v_d7_detail jsonb := '{}'::jsonb;
  v_tripped_names text[] := '{}';
  v_result jsonb;
  v_already_open boolean;
begin
  -- D1: same dispatch_id (issue) revalidated more than 3x within a 3h window
  select coalesce(bool_or(cnt > 3), false), coalesce(jsonb_agg(jsonb_build_object('dispatch_id', dispatch_id, 'count', cnt)) filter (where cnt > 3), '[]'::jsonb)
  into v_d1, v_d1_detail
  from (
    select dispatch_id, count(*) as cnt
    from public.agent_ops_log
    where task ilike '%gtm%validate%'
      and created_at > now() - interval '3 hours'
    group by dispatch_id
  ) t;

  -- D2: zero gtm merges in 48h while an open GTM item exists in the redispatch queue
  select
    (not exists (
      select 1 from public.agent_ops_log
      where task ilike '%gtm%merge%' and status = 'VERIFIED'
        and created_at > now() - interval '48 hours'
    ) and exists (
      select 1 from public.cc_redispatch_guard
      where status in ('pending', 'blocked')
        and task_label ilike '%gtm%'
    )),
    jsonb_build_object(
      'merges_48h', (select count(*) from public.agent_ops_log
                      where task ilike '%gtm%merge%' and status = 'VERIFIED'
                        and created_at > now() - interval '48 hours'),
      'open_queue_rows', (select count(*) from public.cc_redispatch_guard
                           where status in ('pending', 'blocked') and task_label ilike '%gtm%')
    )
  into v_d2, v_d2_detail;

  -- D3: today's GTM compute spend (duration_ms proxy) > 2x the trailing 7-day median
  with daily as (
    select date_trunc('day', created_at) as d, sum(duration_ms) as total_ms
    from public.campaign_agent_log
    where action ilike 'gtm_%' and created_at > now() - interval '8 days'
    group by 1
  ),
  today as (select coalesce(sum(duration_ms), 0) as total_ms from public.campaign_agent_log
             where action ilike 'gtm_%' and created_at > now() - interval '24 hours'),
  med as (select percentile_cont(0.5) within group (order by total_ms) as median_ms
          from daily where d < date_trunc('day', now()))
  select (today.total_ms > 2 * coalesce(med.median_ms, 0)) and coalesce(med.median_ms, 0) > 0,
         jsonb_build_object('today_ms', today.total_ms, 'median_7d_ms', med.median_ms)
  into v_d3, v_d3_detail
  from today, med;

  -- D4: 3 consecutive FAILs on the same journey (most recent 3 rows per journey)
  select coalesce(bool_or(all_fail), false), coalesce(jsonb_agg(jsonb_build_object('journey', journey)) filter (where all_fail), '[]'::jsonb)
  into v_d4, v_d4_detail
  from (
    select details->>'journey' as journey,
           bool_and(not success) as all_fail
    from (
      select *, row_number() over (partition by details->>'journey' order by created_at desc) as rn
      from public.campaign_agent_log
      where action = 'gtm_journey_validate'
    ) x
    where rn <= 3
    group by details->>'journey'
    having count(*) = 3
  ) y;

  -- D5: a publish action succeeded with no approval recorded (M1 violation)
  select coalesce(bool_or(true), false), coalesce(jsonb_agg(jsonb_build_object('id', id, 'created_at', created_at)), '[]'::jsonb)
  into v_d5, v_d5_detail
  from public.campaign_agent_log
  where action ilike 'gtm_publish%' and success = true
    and (details->>'approved_at') is null
    and created_at > now() - interval '48 hours';

  -- D6: a compliance FAIL logged against main within the last 24h
  select coalesce(bool_or(true), false), coalesce(jsonb_agg(jsonb_build_object('dispatch_id', dispatch_id, 'evidence', evidence)), '[]'::jsonb)
  into v_d6, v_d6_detail
  from public.agent_ops_log
  where task ilike '%gtm%compliance%' and status = 'BLOCKED'
    and evidence ilike '%main%'
    and created_at > now() - interval '24 hours';

  -- D7: quota telemetry unreadable right now
  select (public.quota_gate_check('engineering')->>'reason') = 'NO_READING' into v_d7;
  v_d7_detail := public.quota_gate_check('engineering');

  if v_d1 then v_tripped_names := array_append(v_tripped_names, 'same_issue_revalidated_gt3_3h'); end if;
  if v_d2 then v_tripped_names := array_append(v_tripped_names, 'zero_merges_48h_open_queue'); end if;
  if v_d3 then v_tripped_names := array_append(v_tripped_names, 'spend_gt2x_7d_median'); end if;
  if v_d4 then v_tripped_names := array_append(v_tripped_names, '3_consecutive_fails_same_journey'); end if;
  if v_d5 then v_tripped_names := array_append(v_tripped_names, 'publish_attempted_approval_null'); end if;
  if v_d6 then v_tripped_names := array_append(v_tripped_names, 'compliance_fail_on_main'); end if;
  if v_d7 then v_tripped_names := array_append(v_tripped_names, 'quota_no_reading'); end if;

  v_result := jsonb_build_object(
    'tripped', array_length(v_tripped_names, 1) is not null,
    'tripped_detectors', to_jsonb(v_tripped_names),
    'checked_at', now(),
    'detail', jsonb_build_object(
      'same_issue_revalidated_gt3_3h', v_d1_detail,
      'zero_merges_48h_open_queue', v_d2_detail,
      'spend_gt2x_7d_median', v_d3_detail,
      '3_consecutive_fails_same_journey', v_d4_detail,
      'publish_attempted_approval_null', v_d5_detail,
      'compliance_fail_on_main', v_d6_detail,
      'quota_no_reading', v_d7_detail
    )
  );

  if array_length(v_tripped_names, 1) is not null then
    select exists(
      select 1 from public.spi_gates where gate_key = 'gtm_factory_halt' and verified_at is null
    ) into v_already_open;

    if not v_already_open then
      insert into public.spi_gates (gate_key, title, opened_at, proof)
      values (
        'gtm_factory_halt',
        'CMO Factory watchdog trip',
        now(),
        v_result::text
      )
      on conflict (gate_key) do update
        set opened_at = excluded.opened_at,
            proof = excluded.proof,
            verified_at = null
        where public.spi_gates.verified_at is not null; -- only reopen if the prior trip was already closed
    end if;

    insert into public.agent_ops_log (dispatch_id, task, status, evidence, severity)
    values ('gtm_watchdog', 'GTM_WATCHDOG_TRIP', 'BLOCKED', v_result::text, 'blocker');

    -- Best-effort control-issue comment via pg_net, if the extension is
    -- installed. Never raises -- absence of pg_net must not break the
    -- watchdog's own execution (DoD: "executes without error").
    begin
      -- Control issue #19780 ("CMO FACTORY — control"), created + pinned in
      -- this CP. No GH_TOKEN is available inside Postgres, so this call is
      -- almost certainly going to 401 against the GitHub API today -- it is
      -- intentionally best-effort (caught below) and NOT the primary
      -- notification path. The reliable path is the gtm-validate.yml /
      -- gtm-merge.yml workflow steps, which run with `gh` auth and check
      -- spi_gates.gtm_factory_halt themselves on every run (see
      -- .github/workflows/gtm-validate.yml). Wiring an authenticated
      -- comment-post from inside this function is explicitly flagged
      -- [NOT YET] in docs/spec/19777.md -- a CP1+ follow-up, not CP0 scope.
      perform net.http_post(
        url := 'https://api.github.com/repos/breverdbidder/cli-anything-biddeed/issues/19780/comments',
        headers := jsonb_build_object('Accept', 'application/vnd.github+json'),
        body := jsonb_build_object('body', 'gtm_watchdog() tripped: ' || array_to_string(v_tripped_names, ', '))
      );
    exception when others then
      insert into public.agent_ops_log (dispatch_id, task, status, evidence, severity)
      values ('gtm_watchdog', 'GTM_WATCHDOG_COMMENT_SKIPPED', 'SKIPPED', sqlerrm, 'warn');
    end;
  else
    insert into public.agent_ops_log (dispatch_id, task, status, evidence, severity)
    values ('gtm_watchdog', 'GTM_WATCHDOG_CLEAN', 'VERIFIED', v_result::text, 'info');
  end if;

  return v_result;
end;
$$;
