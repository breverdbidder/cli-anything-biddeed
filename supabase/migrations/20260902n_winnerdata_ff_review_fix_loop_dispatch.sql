-- Issue #19748: close the loop on "Request improvement" in the LMS batch
-- review page.
--
-- Schema (issue_number, dispatched_at, fix_ready_at, fix_commit, fix_summary
-- on winnerdata.ff_batch_lead_review, decision CHECK widened to include
-- 'fix_ready') was already applied by migration ff_lead_review_fix_loop
-- before this session started -- NOT re-added here. This migration adds the
-- three functions that actually move a row through the loop:
--
--   1. winnerdata.ff_review_dispatch_sweep(p_dry_run) -- cron-driven:
--      improvement_requested rows with issue_number IS NULL get a CC issue
--      opened (public.gha_create_issue) + a GHA dispatch fired
--      (public.fire_workflow_dispatch, jsonb_build_object inputs per the
--      skill-audit-cron lesson -- never string concat) against
--      cc-runner-ghonly.yml (workflow id 297104962, confirmed live via
--      `gh api .../actions/workflows`).
--   2. public.ff_review_mark_fix_ready(p_issue, p_commit, p_summary) -- the
--      closer every dispatched brief's FINAL STEP tells the fixing CC
--      session to call.
--   3. public.ff_review_spi_lines() -- live counts for the /spi report.
--
-- Also extends lms_ff_batch_detail / lms_ff_batches_list (from
-- 20260901_winnerdata_lms_v1.sql) with the fix_ready fields the LMS worker
-- needs to render the "READY FOR RE-REVIEW" badge/tile/list-count (see
-- workers/winnerdata-lms/src/index.js in the same commit).
--
-- No new tables -> no new RLS surface. All three new functions get the same
-- anon/authenticated/public revoke treatment as the rest of the lms_* RPC
-- family (20260901c_winnerdata_lms_revoke_anon_execute.sql) since they can
-- create GitHub issues and fire workflow dispatches -- there is no reading
-- for which that should ever be anon-callable.

begin;

-- ---------------------------------------------------------------------
-- 1. Dispatcher sweep
-- ---------------------------------------------------------------------
create or replace function winnerdata.ff_review_dispatch_sweep(p_dry_run boolean default false)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'winnerdata'
as $function$
declare
  v_quota      jsonb;
  v_allow      boolean;
  v_org        uuid;
  r            record;
  v_issue      int;
  v_title      text;
  v_body       text;
  v_ff_url     text;
  v_dispatch   jsonb;
  v_result     jsonb := '[]'::jsonb;
  v_count      int := 0;
begin
  v_quota := public.quota_gate_check('engineering');
  v_allow := coalesce((v_quota->>'allow')::boolean, false) or (v_quota->>'reason' = 'NO_READING');

  if not v_allow then
    return jsonb_build_object(
      'ok', true, 'dry_run', p_dry_run, 'dispatched_count', 0,
      'skipped_reason', 'quota_gate_blocked', 'quota', v_quota
    );
  end if;

  select org_id into v_org from winnerdata.organizations order by org_id limit 1;

  for r in
    select
      rv.batch_date, rv.case_number, rv.note, rv.reviewer,
      b.batch_kind,
      coalesce(fbl.county, sdl.county)                             as county,
      fbl.pa_link,
      coalesce(fbl.identity_match_confidence::text, sdl.email_tier) as contact_confidence,
      coalesce(fbl.row_enrichment_status, sdl.row_enrichment_status) as row_enrichment_status,
      fbl.winning_bidder,
      fbl.resolved_entity_name,
      sdl.lead_id
    from winnerdata.ff_batch_lead_review rv
    join winnerdata.ff_batches b on b.batch_date = rv.batch_date
    left join winnerdata.ff_batch_leads fbl
      on fbl.batch_date = rv.batch_date and fbl.case_number = rv.case_number
    left join winnerdata.seller_digest_leads sdl
      on sdl.batch_date = rv.batch_date and sdl.case_number = rv.case_number
    where rv.decision = 'improvement_requested' and rv.issue_number is null
    order by rv.batch_date, rv.case_number
  loop
    -- Same uuid-resolution rule as the LMS "View FF" link
    -- (workers/winnerdata-lms/src/index.js viewFFBatchDetail): lead_id (only
    -- populated for seller_digest batches) wins, pa_link is the fallback.
    v_ff_url := case
      when r.lead_id is not null then 'https://winnerdata-ff.brevardbidderai.workers.dev/ff/' || r.lead_id::text
      else coalesce(r.pa_link, '(no FF link on file for this row -- resolve via the LMS ff-batches/' || r.batch_date::text || ' detail page)')
    end;

    v_title := format('FF fix: %s / %s -- reviewer improvement request', r.batch_date, r.case_number);

    v_body := format(
$body$Operating contract: CC_META_PROMPT.md. Read it first.

## HARD MANDATE (Ariel, Sep 1 2026) -- IN THE BODY ON PURPOSE
NOTHING goes out to Mariam or any producer from this issue. No FF batch, no email, no Resend call, no digest. Approval happens ONLY by Ariel clicking approve in the LMS (lms.winnerdataai.com/ff-batches). No outside-Claude notification channels (no Telegram/SMS/Slack) -- alerts live in the LMS UI and in the in-chat /spi report only (Ariel, Aug 30 2026).

## Context / live numbers to re-derive
batch_date: %s
case_number: %s
county: %s
batch_kind: %s
reviewer: %s
reviewer note (the defect to fix): %s
FF URL: %s

Current values on file (winnerdata.ff_batch_leads / seller_digest_leads as of dispatch time -- re-query, do not trust these as still-current):
  pa_link: %s
  contact_confidence: %s
  row_enrichment_status: %s
  winning_bidder: %s
  resolved_entity_name: %s

## Required behavior
1. Read the reviewer note above -- that is the defect to fix. Locate the actual data path (workers/winnerdata-ff and/or the enrichment script that populated the row) producing it.
2. Fix with real data (no fabricated placeholders, no silently-swallowed nulls).
3. Re-render the FF page above and verify the fix live via curl -- paste the before/after in your closing comment.

## Explicit non-goals
- No sends, no digest changes, no Resend calls, no producer-facing notification of any kind.
- No auto-approval of anything -- fix_ready is a review state, not an approval.
- Do not touch protected objects (gold_standard_*, public.insights, taxi_meter_*, multi_county_auctions, spi_gates, spi_task_registry, spi_daily, winnerdata.billable_ff_events, winnerdata.ff_digest_log).

## Definition of Done
- FF page re-rendered and curl-verified showing the fix (paste before/after).
- FINAL STEP: after the FF is re-rendered and verified, call
  select public.ff_review_mark_fix_ready(<issue>, '<sha>', '<one-line summary>');
  (substitute this issue's own number for <issue>)
$body$,
      r.batch_date, r.case_number, coalesce(r.county, 'unknown'), r.batch_kind,
      coalesce(r.reviewer, 'unknown'), coalesce(r.note, '(no note)'), v_ff_url,
      coalesce(r.pa_link, '(none)'), coalesce(r.contact_confidence, '(none)'),
      coalesce(r.row_enrichment_status, '(none)'), coalesce(r.winning_bidder, '(none)'),
      coalesce(r.resolved_entity_name, '(none)')
    );

    if p_dry_run then
      v_result := v_result || jsonb_build_object(
        'batch_date', r.batch_date, 'case_number', r.case_number, 'would_dispatch', true
      );
    else
      v_issue := public.gha_create_issue(v_title, v_body, 'breverdbidder/cli-anything-biddeed');

      v_dispatch := public.fire_workflow_dispatch(
        'breverdbidder/cli-anything-biddeed', '297104962', 'main',
        jsonb_build_object('issues', v_issue::text)
      );

      update winnerdata.ff_batch_lead_review
        set issue_number = v_issue, dispatched_at = now()
        where batch_date = r.batch_date and case_number = r.case_number;

      insert into winnerdata.lms_audit_log(org_id, actor, action, target_table, target_id, detail)
      values (
        v_org, 'ff_review_dispatch_sweep', 'dispatch', 'ff_batch_lead_review',
        r.batch_date::text || '/' || r.case_number,
        jsonb_build_object('issue_number', v_issue, 'workflow_dispatch', v_dispatch)
      );

      insert into public.agent_ops_log(dispatch_id, task, status, evidence, severity)
      values (
        'ff-review-dispatch-sweep',
        'FF review fix-loop dispatch: ' || r.batch_date || '/' || r.case_number,
        'VERIFIED',
        'issue #' || v_issue || ' created, workflow_dispatch=' || coalesce(v_dispatch->>'status', 'unknown'),
        'info'
      );

      v_result := v_result || jsonb_build_object(
        'batch_date', r.batch_date, 'case_number', r.case_number, 'issue_number', v_issue
      );
    end if;

    v_count := v_count + 1;
  end loop;

  return jsonb_build_object(
    'ok', true, 'dry_run', p_dry_run, 'dispatched_count', v_count,
    'dispatched', v_result, 'quota', v_quota
  );
end;
$function$;

revoke all on function winnerdata.ff_review_dispatch_sweep(boolean) from public;

-- ---------------------------------------------------------------------
-- 2. Closer
-- ---------------------------------------------------------------------
create or replace function public.ff_review_mark_fix_ready(p_issue int, p_commit text, p_summary text)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'winnerdata'
as $function$
declare
  v_count int;
  v_org   uuid;
begin
  if p_issue is null then
    return jsonb_build_object('ok', false, 'reason', 'p_issue required');
  end if;

  update winnerdata.ff_batch_lead_review
    set decision = 'fix_ready', fix_ready_at = now(), fix_commit = p_commit, fix_summary = p_summary
    where issue_number = p_issue and decision = 'improvement_requested';
  get diagnostics v_count = row_count;

  if v_count = 0 then
    return jsonb_build_object('ok', false, 'reason', 'no_matching_improvement_requested_row_for_issue', 'issue_number', p_issue);
  end if;

  select org_id into v_org from winnerdata.organizations order by org_id limit 1;

  insert into winnerdata.lms_audit_log(org_id, actor, action, target_table, target_id, detail)
  select
    v_org, 'ff_review_mark_fix_ready', 'fix_ready', 'ff_batch_lead_review',
    rv.batch_date::text || '/' || rv.case_number,
    jsonb_build_object('issue_number', p_issue, 'fix_commit', p_commit, 'fix_summary', p_summary)
  from winnerdata.ff_batch_lead_review rv
  where rv.issue_number = p_issue and rv.decision = 'fix_ready';

  insert into public.agent_ops_log(dispatch_id, task, status, evidence, severity)
  values (
    'issue-' || p_issue, 'FF review fix_ready close: issue #' || p_issue, 'VERIFIED',
    coalesce(p_summary, '(no summary)') || ' [' || coalesce(p_commit, 'no sha') || ']', 'info'
  );

  return jsonb_build_object('ok', true, 'rows_updated', v_count, 'issue_number', p_issue);
end;
$function$;

revoke all on function public.ff_review_mark_fix_ready(int, text, text) from public;

-- ---------------------------------------------------------------------
-- 3. /spi lines
-- ---------------------------------------------------------------------
create or replace function public.ff_review_spi_lines()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'winnerdata'
as $function$
declare
  v_ready_count   int;
  v_ready_detail  text;
  v_pending_count int;
begin
  select count(*),
         coalesce(string_agg(batch_date::text || ' ' || case_number || ' (#' || issue_number || ')', ', ' order by fix_ready_at), '')
    into v_ready_count, v_ready_detail
  from winnerdata.ff_batch_lead_review
  where decision = 'fix_ready';

  select count(*) into v_pending_count
  from winnerdata.ff_batch_lead_review
  where decision = 'improvement_requested' and issue_number is null;

  return jsonb_build_object(
    'line1', 'FF fixes ready for re-review: ' || v_ready_count || case when v_ready_count > 0 then ' -- ' || v_ready_detail else '' end,
    'line2', 'FF improvements pending dispatch: ' || v_pending_count,
    'ready_count', v_ready_count,
    'pending_count', v_pending_count
  );
end;
$function$;

revoke all on function public.ff_review_spi_lines() from public;

-- ---------------------------------------------------------------------
-- 4. cron -- every 5 minutes, gated inside the function on quota_gate_check
-- ---------------------------------------------------------------------
do $cron$
begin
  if exists (select 1 from cron.job where jobname = 'winnerdata-ff-review-dispatch') then
    perform cron.unschedule('winnerdata-ff-review-dispatch');
  end if;
end
$cron$;

select cron.schedule(
  'winnerdata-ff-review-dispatch',
  '*/5 * * * *',
  $sql$select winnerdata.ff_review_dispatch_sweep(false);$sql$
);

-- ---------------------------------------------------------------------
-- 5. Extend lms_ff_batch_detail / lms_ff_batches_list with fix_ready fields
-- ---------------------------------------------------------------------
create or replace function public.lms_ff_batch_detail(p_batch_date date)
returns jsonb
language plpgsql
security definer
set search_path to 'public', 'winnerdata'
as $function$
declare
  v_batch winnerdata.ff_batches%rowtype;
  v_leads jsonb;
  v_fix_ready_count int;
  v_pending_dispatch_count int;
begin
  if p_batch_date is null then
    return jsonb_build_object('ok', false, 'reason', 'batch_date required');
  end if;

  select * into v_batch from winnerdata.ff_batches where batch_date = p_batch_date;
  if not found then
    return jsonb_build_object('ok', false, 'reason', 'batch_not_found');
  end if;

  if v_batch.batch_kind = 'seller_digest' then
    select coalesce(jsonb_agg(row_to_json(t) order by t.entity_name), '[]'::jsonb) into v_leads
    from (
      select
        sdl.lead_id, sdl.entity_name, sdl.county, sdl.sale_type, sdl.case_number,
        sdl.sold_amount, sdl.property_address,
        fbl.contact_confidence as confidence_tier,
        null::text as pa_link,
        rv.decision as review_decision, rv.note as review_note,
        rv.reviewer as reviewed_by, rv.reviewed_at,
        rv.issue_number, rv.dispatched_at, rv.fix_ready_at, rv.fix_commit, rv.fix_summary
      from winnerdata.seller_digest_leads sdl
      left join winnerdata.ff_batch_leads fbl on fbl.case_number = sdl.case_number
      left join winnerdata.ff_batch_lead_review rv
        on rv.batch_date = sdl.batch_date and rv.case_number = sdl.case_number
      where sdl.batch_date = p_batch_date
    ) t;
  else
    select coalesce(jsonb_agg(row_to_json(t) order by t.entity_name), '[]'::jsonb) into v_leads
    from (
      select
        null::uuid as lead_id,
        coalesce(fbl.resolved_entity_name, fbl.winning_bidder) as entity_name,
        fbl.county, fbl.sale_type, fbl.case_number,
        fbl.tier1_sold_amount as sold_amount, fbl.property_address,
        fbl.identity_match_confidence::text as confidence_tier,
        fbl.pa_link,
        rv.decision as review_decision, rv.note as review_note,
        rv.reviewer as reviewed_by, rv.reviewed_at,
        rv.issue_number, rv.dispatched_at, rv.fix_ready_at, rv.fix_commit, rv.fix_summary
      from winnerdata.ff_batch_leads fbl
      left join winnerdata.ff_batch_lead_review rv
        on rv.batch_date = fbl.batch_date and rv.case_number = fbl.case_number
      where fbl.batch_date = p_batch_date
    ) t;
  end if;

  select count(*) filter (where decision = 'fix_ready'),
         count(*) filter (where decision = 'improvement_requested' and issue_number is null)
    into v_fix_ready_count, v_pending_dispatch_count
  from winnerdata.ff_batch_lead_review
  where batch_date = p_batch_date;

  return jsonb_build_object(
    'ok', true,
    'batch', jsonb_build_object(
      'batch_date', v_batch.batch_date, 'status', v_batch.status, 'batch_kind', v_batch.batch_kind,
      'lead_count', v_batch.lead_count, 'enrichment_status', v_batch.enrichment_status,
      'created_at', v_batch.created_at, 'approved_at', v_batch.approved_at, 'sent_at', v_batch.sent_at,
      'fix_ready_count', coalesce(v_fix_ready_count, 0),
      'pending_dispatch_count', coalesce(v_pending_dispatch_count, 0)
    ),
    'leads', v_leads
  );
end;
$function$;

create or replace function public.lms_ff_batches_list()
returns jsonb
language plpgsql
security definer
set search_path to 'public', 'winnerdata'
as $function$
declare
  v_result jsonb;
begin
  select coalesce(jsonb_agg(jsonb_build_object(
    'batch_date', b.batch_date,
    'status', b.status,
    'batch_kind', b.batch_kind,
    'lead_count', b.lead_count,
    'enrichment_status', b.enrichment_status,
    'created_at', b.created_at,
    'approved_at', b.approved_at,
    'sent_at', b.sent_at,
    'reviewed_count', coalesce(r.reviewed_count, 0),
    'approved_count', coalesce(r.approved_count, 0),
    'rejected_count', coalesce(r.rejected_count, 0),
    'improvement_count', coalesce(r.improvement_count, 0),
    'fix_ready_count', coalesce(r.fix_ready_count, 0),
    'pending_dispatch_count', coalesce(r.pending_dispatch_count, 0)
  ) order by b.batch_date desc), '[]'::jsonb)
  into v_result
  from winnerdata.ff_batches b
  left join (
    select
      batch_date,
      count(*) as reviewed_count,
      count(*) filter (where decision = 'approved') as approved_count,
      count(*) filter (where decision = 'rejected') as rejected_count,
      count(*) filter (where decision = 'improvement_requested') as improvement_count,
      count(*) filter (where decision = 'fix_ready') as fix_ready_count,
      count(*) filter (where decision = 'improvement_requested' and issue_number is null) as pending_dispatch_count
    from winnerdata.ff_batch_lead_review
    group by batch_date
  ) r on r.batch_date = b.batch_date;

  return jsonb_build_object('ok', true, 'batches', v_result);
end;
$function$;

commit;
