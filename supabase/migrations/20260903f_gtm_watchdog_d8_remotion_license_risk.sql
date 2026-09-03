-- CMO FACTORY CP3b(v2) (issue #19787) -- adds D8 remotion_license_risk to
-- public.gtm_watchdog(). This is the license tripwire required BEFORE
-- Remotion is used anywhere (zonewise-superpowers unblock, docs/gtm/VIDEO_STACK.md).
--
-- D8 cannot compute git-author counts or grep customer-facing surfaces
-- itself -- Postgres has no git/filesystem access. Same pattern as D5/D6:
-- the CI check (.github/workflows/gtm-validate.yml, new
-- "License tripwire: remotion_license_risk" step) does the actual git-log /
-- grep work and writes one row per run to agent_ops_log with
-- dispatch_id='remotion_license_risk', task in:
--   'remotion_license_risk_authors'   -- (a) >3 distinct human authors, 90d,
--                                          zonewise-superpowers + any repo
--                                          importing remotion -- ADVISORY-FAIL
--   'remotion_license_risk_player'    -- (b) @remotion/player / <Player> import
--                                          in a customer-facing surface -- HARD FAIL
--   'remotion_license_risk_usercode'  -- (c) a code path accepting user-supplied
--                                          Remotion project/code for rendering -- HARD FAIL
-- status='BLOCKED' means that run's check tripped; status='VERIFIED' means
-- clean. D8 reads the most recent row per task within the last 24h (CI runs
-- on every gtm-validate.yml dispatch, so 24h comfortably covers one miss).
--
-- Ariel ruling (Sep 3 2026, unified_context key license_v2_ruling_remotion_sep3):
-- Remotion Free License covers individuals + for-profit orgs up to 3 people,
-- and automations built by a Free-License-eligible org do not need to
-- purchase Renders. Everest Capital of Brevard LLC is a one-person operator
-- -> $0, unlimited automated commercial renders, no account needed. This
-- tripwire exists so that fact never silently goes stale: if headcount on
-- the Remotion projects crosses 3, or Remotion Player leaks into a
-- customer-facing app, or user code gets accepted for rendering (any of
-- which would flip Everest into the paid/Automators tier or a
-- redistribution violation), D8 trips before the risk compounds.

begin;

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
  v_d8 boolean := false; v_d8_detail jsonb := '{}'::jsonb;
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

  -- D8: Remotion license-risk tripwire. Reads the most recent
  -- gtm-validate.yml CI check result per sub-condition (a/b/c) within 24h.
  -- Absence of any row for a sub-condition is NOT treated as a trip (fails
  -- open on missing telemetry here, matching D7's own explicit NO_READING
  -- carve-out rather than manufacturing a false positive) but IS surfaced in
  -- the detail so a missing check is visible, not silent.
  with latest as (
    select distinct on (task) task, status, evidence, created_at
    from public.agent_ops_log
    where dispatch_id = 'remotion_license_risk'
      and task in ('remotion_license_risk_authors', 'remotion_license_risk_player', 'remotion_license_risk_usercode')
      and created_at > now() - interval '24 hours'
    order by task, created_at desc
  )
  select
    coalesce(bool_or(status = 'BLOCKED'), false),
    jsonb_build_object(
      'authors_check', (select jsonb_build_object('status', status, 'evidence', evidence, 'checked_at', created_at) from latest where task = 'remotion_license_risk_authors'),
      'player_check', (select jsonb_build_object('status', status, 'evidence', evidence, 'checked_at', created_at) from latest where task = 'remotion_license_risk_player'),
      'usercode_check', (select jsonb_build_object('status', status, 'evidence', evidence, 'checked_at', created_at) from latest where task = 'remotion_license_risk_usercode'),
      'missing_checks', (
        select coalesce(jsonb_agg(t), '[]'::jsonb) from (
          select unnest(array['remotion_license_risk_authors','remotion_license_risk_player','remotion_license_risk_usercode']) as t
        ) x where t not in (select task from latest)
      )
    )
  into v_d8, v_d8_detail
  from latest;

  if v_d1 then v_tripped_names := array_append(v_tripped_names, 'same_issue_revalidated_gt3_3h'); end if;
  if v_d2 then v_tripped_names := array_append(v_tripped_names, 'zero_merges_48h_open_queue'); end if;
  if v_d3 then v_tripped_names := array_append(v_tripped_names, 'spend_gt2x_7d_median'); end if;
  if v_d4 then v_tripped_names := array_append(v_tripped_names, '3_consecutive_fails_same_journey'); end if;
  if v_d5 then v_tripped_names := array_append(v_tripped_names, 'publish_attempted_approval_null'); end if;
  if v_d6 then v_tripped_names := array_append(v_tripped_names, 'compliance_fail_on_main'); end if;
  if v_d7 then v_tripped_names := array_append(v_tripped_names, 'quota_no_reading'); end if;
  if v_d8 then v_tripped_names := array_append(v_tripped_names, 'remotion_license_risk'); end if;

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
      'quota_no_reading', v_d7_detail,
      'remotion_license_risk', v_d8_detail
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

    -- D8-specific gate: also opened under its own gate_key so it can be
    -- resolved independently of the general gtm_factory_halt gate (a
    -- Remotion headcount/Player-leak finding is a different owner/fix than
    -- a GTM factory stall).
    if v_d8 then
      insert into public.spi_gates (gate_key, title, opened_at, proof)
      values ('remotion_license_risk', 'Remotion License V2 tripwire fired', now(), v_d8_detail::text)
      on conflict (gate_key) do update
        set opened_at = excluded.opened_at,
            proof = excluded.proof,
            verified_at = null
        where public.spi_gates.verified_at is not null;
    end if;

    insert into public.agent_ops_log (dispatch_id, task, status, evidence, severity)
    values ('gtm_watchdog', 'GTM_WATCHDOG_TRIP', 'BLOCKED', v_result::text, 'blocker');

    -- Best-effort control-issue comment via pg_net. No GH_TOKEN is available
    -- inside Postgres, so this call is expected to 401 today -- caught below,
    -- never breaks the watchdog's own execution. Reliable notification path
    -- is gtm-validate.yml / gtm-merge.yml checking spi_gates.gtm_factory_halt
    -- themselves (authenticated `gh`). See docs/spec/19777.md for the
    -- explicit [NOT YET] flag on authenticated in-DB comment-posting.
    begin
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

revoke all on function public.gtm_watchdog() from public;
grant execute on function public.gtm_watchdog() to postgres, service_role;

commit;
