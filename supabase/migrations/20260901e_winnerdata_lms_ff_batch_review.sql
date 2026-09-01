-- FF Batch Review + Approval screen (winnerdataai.com LMS), 2026-09-01.
--
-- Ariel reviewed a corrected 28-lead FF batch (batch_date 2026-08-29) pasted
-- into chat and asked to review/approve/reject/request-improvements on each
-- FF from the LMS itself instead of chat. This is purely a NEW REVIEW
-- SURFACE on top of the existing approval gate
-- (20260827_winnerdata_ff_batches_approval_gate.sql) -- the standing
-- no-send rule is unchanged: public.ff_approve_batch() still requires an
-- explicit human action, this migration just adds where that action can be
-- triggered from (LMS UI) plus a new per-lead granularity layer underneath
-- it. Nothing here auto-sends or auto-approves anything.
--
-- Design: one new table, keyed on (batch_date, case_number) rather than
-- lead_id/auction_id, because case_number is the only join key that exists
-- on BOTH ff_batches child shapes -- winnerdata.seller_digest_leads
-- (batch_kind='seller_digest', keyed on lead_id) and winnerdata.ff_batch_leads
-- (batch_kind='nine_case_portfolio', keyed on auction_id). Reusing the exact
-- case_number join already proven live in
-- scripts/winnerdata_ff_digest_lib.py's get_batch_leads() rather than
-- inventing a new key.
--
-- Conservative default (Ariel's item 5, "unreviewed lead does not get
-- sent"): scripts/winnerdata_ff_send_approved.py is updated in the same
-- change (not this file -- see that script) to only send leads with
-- decision='approved' here. That is enforced at the send step, not by a DB
-- constraint, because the send step already recomputes its lead list live
-- (see that script's own docstring) and this is one more live-recomputed
-- filter alongside it.

begin;

-- ============================================================
-- 1. Per-lead review table.
-- ============================================================

create table if not exists winnerdata.ff_batch_lead_review (
  batch_date date not null references winnerdata.ff_batches(batch_date) on delete cascade,
  case_number text not null,
  decision text not null check (decision in ('approved', 'rejected', 'improvement_requested')),
  note text,
  reviewer text not null,
  reviewed_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (batch_date, case_number)
);

comment on table winnerdata.ff_batch_lead_review is
  'Per-lead approve/reject/request-improvement decisions from the winnerdataai.com '
  'LMS FF Batch Review screen (2026-09-01). Keyed on (batch_date, case_number) so '
  'it joins to both ff_batches child shapes (seller_digest_leads and '
  'ff_batch_leads). A lead with no row here is "unreviewed" -- '
  'scripts/winnerdata_ff_send_approved.py treats unreviewed the same as '
  'rejected (excluded from send) per Ariel''s explicit conservative default.';

create index if not exists ff_batch_lead_review_date_idx
  on winnerdata.ff_batch_lead_review (batch_date);

grant select on winnerdata.ff_batch_lead_review to lms_agent_ro;

-- ============================================================
-- 2. Extend ff_digest_log's status vocabulary for the new send-time block
--    condition (all qualifying leads unreviewed/rejected -- distinct from
--    "no qualifying leads at all", which stays 'no_leads_sent').
-- ============================================================

alter table winnerdata.ff_digest_log drop constraint ff_digest_log_status_check;
alter table winnerdata.ff_digest_log
  add constraint ff_digest_log_status_check
  check (status in (
    'sent', 'no_leads_sent', 'blocked_no_email', 'blocked_sandbox_recipient',
    'blocked_unreviewed_leads', 'error'
  ));

comment on column winnerdata.ff_digest_log.status is
  'blocked_unreviewed_leads (2026-09-01): the batch had qualifying leads but '
  'none were marked decision=''approved'' in winnerdata.ff_batch_lead_review at '
  'send time -- distinct from no_leads_sent (zero qualifying leads existed at '
  'all). Batch stays ''approved'' for retry once leads are reviewed.';

-- ============================================================
-- 3. READ RPC -- batch list with per-batch review rollup.
-- ============================================================

create or replace function public.lms_ff_batches_list()
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
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
    'improvement_count', coalesce(r.improvement_count, 0)
  ) order by b.batch_date desc), '[]'::jsonb)
  into v_result
  from winnerdata.ff_batches b
  left join (
    select
      batch_date,
      count(*) as reviewed_count,
      count(*) filter (where decision = 'approved') as approved_count,
      count(*) filter (where decision = 'rejected') as rejected_count,
      count(*) filter (where decision = 'improvement_requested') as improvement_count
    from winnerdata.ff_batch_lead_review
    group by batch_date
  ) r on r.batch_date = b.batch_date;

  return jsonb_build_object('ok', true, 'batches', v_result);
end;
$$;

-- ============================================================
-- 4. READ RPC -- batch detail (leads + current review decision per lead).
--    Branches on batch_kind since the two ff_batches child shapes have
--    different lead source tables and neither is a superset of the other.
-- ============================================================

create or replace function public.lms_ff_batch_detail(p_batch_date date)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_batch winnerdata.ff_batches%rowtype;
  v_leads jsonb;
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
        rv.reviewer as reviewed_by, rv.reviewed_at
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
        rv.reviewer as reviewed_by, rv.reviewed_at
      from winnerdata.ff_batch_leads fbl
      left join winnerdata.ff_batch_lead_review rv
        on rv.batch_date = fbl.batch_date and rv.case_number = fbl.case_number
      where fbl.batch_date = p_batch_date
    ) t;
  end if;

  return jsonb_build_object(
    'ok', true,
    'batch', jsonb_build_object(
      'batch_date', v_batch.batch_date, 'status', v_batch.status, 'batch_kind', v_batch.batch_kind,
      'lead_count', v_batch.lead_count, 'enrichment_status', v_batch.enrichment_status,
      'created_at', v_batch.created_at, 'approved_at', v_batch.approved_at, 'sent_at', v_batch.sent_at
    ),
    'leads', v_leads
  );
end;
$$;

-- ============================================================
-- 5. WRITE RPC -- per-lead decision. Audit-logged, same pattern as
--    lms_flag_lead / lms_update_producer_note.
-- ============================================================

create or replace function public.lms_ff_batch_lead_review(
  p_batch_date date, p_case_number text, p_decision text, p_actor text, p_note text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
begin
  if p_batch_date is null or p_case_number is null or trim(p_case_number) = ''
     or p_decision is null or p_actor is null then
    return jsonb_build_object('ok', false, 'reason', 'missing_params');
  end if;

  if p_decision not in ('approved', 'rejected', 'improvement_requested') then
    return jsonb_build_object('ok', false, 'reason', 'invalid_decision');
  end if;

  if not exists (select 1 from winnerdata.ff_batches where batch_date = p_batch_date) then
    return jsonb_build_object('ok', false, 'reason', 'batch_not_found');
  end if;

  insert into winnerdata.ff_batch_lead_review (batch_date, case_number, decision, note, reviewer, reviewed_at, updated_at)
  values (p_batch_date, p_case_number, p_decision, p_note, p_actor, now(), now())
  on conflict (batch_date, case_number)
  do update set decision = excluded.decision, note = excluded.note, reviewer = excluded.reviewer,
                reviewed_at = now(), updated_at = now();

  -- Single live tenant (Protection Partners) -- same constant as
  -- workers/winnerdata-ff/src/index.js ORG_ID and
  -- scripts/winnerdata_ff_digest_lib.py PROTECTION_PARTNERS_ORG_ID.
  insert into winnerdata.lms_audit_log (org_id, actor, action, target_table, target_id, detail)
  values (
    '032f4717-545f-4a18-b48b-28ea4257699d'::uuid, p_actor, 'ff_batch_lead_review',
    'winnerdata.ff_batch_lead_review', p_batch_date::text || ':' || p_case_number,
    jsonb_build_object('decision', p_decision, 'note', p_note)
  );

  return jsonb_build_object('ok', true, 'batch_date', p_batch_date, 'case_number', p_case_number, 'decision', p_decision);
end;
$$;

-- ============================================================
-- 6. WRITE RPC -- batch-level approve. Thin wrapper around the EXISTING
--    public.ff_approve_batch(date) (same function the chat-based flow
--    calls -- unchanged, not duplicated), adds LMS audit logging and
--    returns the per-lead send-eligibility summary so the UI can show
--    Ariel exactly what will/won't be sent under the conservative
--    unreviewed-excluded default.
-- ============================================================

create or replace function public.lms_ff_approve_batch(p_batch_date date, p_actor text)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
declare
  v_batch_kind text;
  v_approve_result jsonb;
  v_total integer;
  v_approved integer;
begin
  if p_batch_date is null or p_actor is null then
    return jsonb_build_object('ok', false, 'reason', 'missing_params');
  end if;

  select batch_kind into v_batch_kind from winnerdata.ff_batches where batch_date = p_batch_date;
  if v_batch_kind is null then
    return jsonb_build_object('ok', false, 'reason', 'batch_not_found');
  end if;

  if v_batch_kind = 'seller_digest' then
    select count(*) into v_total from winnerdata.seller_digest_leads where batch_date = p_batch_date;
  else
    select count(*) into v_total from winnerdata.ff_batch_leads where batch_date = p_batch_date;
  end if;

  select count(*) into v_approved
  from winnerdata.ff_batch_lead_review
  where batch_date = p_batch_date and decision = 'approved';

  v_approve_result := public.ff_approve_batch(p_batch_date);

  if (v_approve_result ->> 'ok')::boolean then
    insert into winnerdata.lms_audit_log (org_id, actor, action, target_table, target_id, detail)
    values (
      '032f4717-545f-4a18-b48b-28ea4257699d'::uuid, p_actor, 'ff_batch_approve',
      'winnerdata.ff_batches', p_batch_date::text,
      jsonb_build_object('total_leads', v_total, 'approved_for_send', v_approved,
                          'excluded_unreviewed_or_rejected', greatest(v_total - v_approved, 0))
    );
  end if;

  return v_approve_result || jsonb_build_object(
    'total_leads', v_total, 'approved_for_send', v_approved,
    'excluded_unreviewed_or_rejected', greatest(v_total - v_approved, 0)
  );
end;
$$;

-- ============================================================
-- 7. Grants -- same posture as 20260901c_winnerdata_lms_revoke_anon_execute.sql:
--    service_role only (the Worker's real access boundary), never anon.
-- ============================================================

revoke all on function public.lms_ff_batches_list() from public;
revoke all on function public.lms_ff_batch_detail(date) from public;
revoke all on function public.lms_ff_batch_lead_review(date, text, text, text, text) from public;
revoke all on function public.lms_ff_approve_batch(date, text) from public;

grant execute on function public.lms_ff_batches_list() to service_role;
grant execute on function public.lms_ff_batch_detail(date) to service_role;
grant execute on function public.lms_ff_batch_lead_review(date, text, text, text, text) to service_role;
grant execute on function public.lms_ff_approve_batch(date, text) to service_role;

commit;
