-- Unforgeable approval provenance for "The Daily Winner FFs" (issue #19745).
--
-- Incident (Ariel, Sep 2 2026): on 2026-09-01T15:38:05Z an automated session
-- approved batch 2026-08-29 by writing approved_by='ariel' via a
-- service-role call to public.ff_approve_batch(), then sent it to
-- Ms@protectionpartners.net 6 seconds later -- before the LMS Batch Review
-- screen (c9e406bd) even existed. winnerdata.ff_batches.approved_by is
-- free-text set by a SECURITY DEFINER function grantable to service_role --
-- it records an *intent* but proves nothing about who/what actually issued
-- the call, because service_role is the same blanket credential every
-- backend script/automation/Cowork task shares.
--
-- Fix: a second, independent table (winnerdata.ff_batch_approvals) that can
-- ONLY be written when the calling request carries a real Supabase Auth JWT
-- for an allow-listed admin -- auth.uid()/auth.email() reflect the ACTUAL
-- caller's JWT regardless of whether the writing function is SECURITY
-- DEFINER or INVOKER (they read the per-request `request.jwt.claims` GUC
-- PostgREST sets, not the function owner), so this holds even though
-- public.ff_batch_approve_authenticated() below is DEFINER (kept DEFINER so
-- it needs no new grants scattered across the locked-down winnerdata schema
-- -- see workers/winnerdata-lms/src/index.js docstring for why that schema
-- is intentionally not PostgREST-exposed). A service_role or anon call has
-- no `sub` claim, so auth.uid() is null and both the RPC's own check and the
-- BEFORE INSERT trigger below reject it -- the trigger fires unconditionally
-- on the actual DML regardless of RLS bypass/table ownership, so it is the
-- true backstop even against a hypothetical future direct-table exposure.
--
-- winnerdata.ff_batches.status/approved_at/approved_by (and the existing
-- public.ff_approve_batch() service_role RPC) are UNCHANGED -- they still
-- exist for the original Cowork-task flow this table was built for. What
-- changes is that they are no longer *sufficient*: the send path
-- (scripts/winnerdata_ff_send_approved.py, same change set) now hard-refuses
-- to send unless a matching ff_batch_approvals row also exists.

begin;

-- ============================================================
-- 1. Admin allowlist. Single live admin today (Ariel); a table, not a
--    hardcoded email in the trigger, so a future co-admin is a one-row
--    INSERT, not a migration.
-- ============================================================

create table if not exists winnerdata.lms_admins (
  email text primary key,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

comment on table winnerdata.lms_admins is
  'Allow-list of emails permitted to approve an FF batch through the '
  'authenticated LMS path (see winnerdata.ff_batch_approvals). Checked by '
  'both the enforce_ff_batch_approval_authenticated() trigger and '
  'public.ff_batch_approve_authenticated().';

-- Only ever read internally by the trigger function and the SECURITY
-- DEFINER RPC above, both of which run as the table owner (postgres) and so
-- bypass RLS regardless -- no role needs a direct grant. RLS enabled/forced
-- anyway per M2 (every new table ships with RLS, no anon/authenticated
-- policy); no policies means default-deny for every other role.
alter table winnerdata.lms_admins enable row level security;
alter table winnerdata.lms_admins force row level security;

-- ariel+lms-admin@everestcapitalusa.com is a DEDICATED Supabase Auth
-- identity provisioned for this flow (this session, via the Admin API) --
-- deliberately NOT the pre-existing auth.users row for
-- ariel@everestcapitalusa.com (created 2026-08-28, used by an unrelated
-- beta-investor-portal login), so wiring this gate carries zero blast radius
-- on that other live login. Plus-addressed under Ariel's own real domain so
-- provenance is still unambiguously "Ariel", not a generic service account.
insert into winnerdata.lms_admins (email)
values ('ariel+lms-admin@everestcapitalusa.com')
on conflict (email) do nothing;

-- ============================================================
-- 2. Approval provenance table. Immutable audit log -- no update/delete
--    policy, so once written a row can never be edited, only superseded by
--    a fresh approval (new row) if the batch snapshot changes.
-- ============================================================

create table if not exists winnerdata.ff_batch_approvals (
  id bigint generated always as identity primary key,
  batch_date date not null references winnerdata.ff_batches(batch_date) on delete cascade,
  batch_kind text not null,
  lead_count_snapshot integer not null,
  snapshot_hash text not null,
  approved_by_user_id uuid not null references auth.users(id),
  approved_by_email text not null,
  approved_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

comment on table winnerdata.ff_batch_approvals is
  'Unforgeable approval provenance (issue #19745). One row per real click of '
  'Approve in the LMS by an authenticated, allow-listed admin -- '
  'approved_by_user_id/approved_by_email come from auth.uid()/auth.email() '
  'of the actual request, never from client-supplied input. snapshot_hash = '
  'sha256(batch_date|batch_kind|lead_count) at approval time; the send path '
  'recomputes this from the batch''s CURRENT state and refuses to send on a '
  'mismatch (batch changed since approval -> re-approval required).';

create index if not exists ff_batch_approvals_batch_date_idx
  on winnerdata.ff_batch_approvals (batch_date, approved_at desc);

alter table winnerdata.ff_batch_approvals enable row level security;
alter table winnerdata.ff_batch_approvals force row level security;

-- Defense-in-depth alongside the trigger below: even if this table were ever
-- granted directly to `authenticated` (it is not, today -- all writes go
-- through the SECURITY DEFINER RPC), a direct INSERT could still only claim
-- the caller's own auth.uid(), never someone else's.
create policy ff_batch_approvals_insert_self
  on winnerdata.ff_batch_approvals
  for insert
  to authenticated
  with check (approved_by_user_id = auth.uid());

-- No update/delete policy for any role -> default deny, immutable log.
-- No select policy for `authenticated` -> reads go through service_role
-- (bypasses RLS) via the existing lms_ff_batches_list/lms_ff_batch_detail
-- RPC pattern, same as every other winnerdata table this Worker reads.

-- ============================================================
-- 3. BEFORE INSERT trigger -- the real, unconditional backstop. Triggers
--    fire for every INSERT regardless of RLS bypass, table ownership, or
--    whether the inserting function is SECURITY DEFINER/INVOKER, so this is
--    what actually makes a service-role or anon-forged row impossible, not
--    just the RLS policy above (RLS alone does not stop service_role, which
--    has BYPASSRLS).
-- ============================================================

create or replace function winnerdata.enforce_ff_batch_approval_authenticated()
returns trigger
language plpgsql
as $$
declare
  v_email text;
begin
  if auth.uid() is null then
    raise exception 'ff_batch_approvals insert rejected: no authenticated Supabase Auth JWT on this request (auth.uid() is null) -- service_role and anon callers cannot create an approval record'
      using errcode = '42501';
  end if;

  if new.approved_by_user_id is distinct from auth.uid() then
    raise exception 'ff_batch_approvals insert rejected: approved_by_user_id must equal the calling session''s auth.uid()'
      using errcode = '42501';
  end if;

  v_email := auth.email();
  if v_email is null or new.approved_by_email is distinct from v_email then
    raise exception 'ff_batch_approvals insert rejected: approved_by_email must equal the calling session''s authenticated email'
      using errcode = '42501';
  end if;

  if not exists (
    select 1 from winnerdata.lms_admins a where a.email = v_email and a.active
  ) then
    raise exception 'ff_batch_approvals insert rejected: % is not an active LMS admin', v_email
      using errcode = '42501';
  end if;

  return new;
end;
$$;

drop trigger if exists ff_batch_approvals_enforce_authenticated on winnerdata.ff_batch_approvals;
create trigger ff_batch_approvals_enforce_authenticated
  before insert on winnerdata.ff_batch_approvals
  for each row
  execute function winnerdata.enforce_ff_batch_approval_authenticated();

-- ============================================================
-- 4. winnerdata.ff_batches gets a provenance column so every batch's
--    approval trail is queryable in one place without a join.
-- ============================================================

alter table winnerdata.ff_batches
  add column if not exists approval_provenance text;

alter table winnerdata.ff_batches
  drop constraint if exists ff_batches_approval_provenance_check;
alter table winnerdata.ff_batches
  add constraint ff_batches_approval_provenance_check
  check (approval_provenance is null or approval_provenance in (
    'authenticated_lms_click', 'unverified-legacy'
  ));

comment on column winnerdata.ff_batches.approval_provenance is
  'authenticated_lms_click: this batch''s approval has a matching, '
  'hash-verified winnerdata.ff_batch_approvals row (issue #19745). '
  'unverified-legacy: approved_at predates the LMS authenticated-approval '
  'gate (or c9e406bd''s Batch Review screen) -- retro-audit annotation only, '
  'per issue #19745 item 3 the underlying approved_by/approved_at values are '
  'NOT rewritten. null: never approved.';

-- ============================================================
-- 5. The authenticated approval RPC. Callable by `authenticated` only (the
--    LMS Worker calls this with the admin's real Supabase Auth access
--    token, minted server-side via a password grant -- see
--    workers/winnerdata-lms/src/index.js -- never with the service_role
--    key). SECURITY DEFINER purely so it can read/write the locked-down
--    winnerdata schema without new blanket grants; the auth.uid()/
--    auth.email() checks below are what actually gate it, and those reflect
--    the real caller's JWT regardless of DEFINER/INVOKER (see file header).
-- ============================================================

create or replace function public.ff_batch_approve_authenticated(p_batch_date date)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata, extensions
as $$
declare
  v_uid uuid := auth.uid();
  v_email text := auth.email();
  v_batch winnerdata.ff_batches%rowtype;
  v_hash text;
  v_approve_result jsonb;
  v_total integer;
  v_approved integer;
begin
  if v_uid is null or v_email is null then
    return jsonb_build_object(
      'ok', false, 'reason', 'not_authenticated',
      'detail', 'This action requires a real Supabase Auth session (auth.uid()/auth.email() were null on this request) -- service_role and anon callers cannot approve a batch.'
    );
  end if;

  if not exists (select 1 from winnerdata.lms_admins a where a.email = v_email and a.active) then
    return jsonb_build_object('ok', false, 'reason', 'not_an_admin', 'email', v_email);
  end if;

  if p_batch_date is null then
    return jsonb_build_object('ok', false, 'reason', 'missing_batch_date');
  end if;

  select * into v_batch from winnerdata.ff_batches where batch_date = p_batch_date;
  if not found then
    return jsonb_build_object('ok', false, 'reason', 'batch_not_found', 'batch_date', p_batch_date);
  end if;

  if v_batch.status <> 'pending_approval' then
    return jsonb_build_object('ok', false, 'reason', 'batch_already ' || v_batch.status, 'batch_date', p_batch_date, 'status', v_batch.status);
  end if;

  v_hash := encode(
    extensions.digest(p_batch_date::text || '|' || v_batch.batch_kind || '|' || v_batch.lead_count::text, 'sha256'),
    'hex'
  );

  insert into winnerdata.ff_batch_approvals
    (batch_date, batch_kind, lead_count_snapshot, snapshot_hash, approved_by_user_id, approved_by_email, approved_at)
  values
    (p_batch_date, v_batch.batch_kind, v_batch.lead_count, v_hash, v_uid, v_email, now());

  v_approve_result := public.ff_approve_batch(p_batch_date);

  update winnerdata.ff_batches
  set approval_provenance = 'authenticated_lms_click'
  where batch_date = p_batch_date;

  -- Per-lead eligibility snapshot for the audit log -- same branch-on-kind
  -- logic as public.lms_ff_approve_batch() (20260901e), duplicated rather
  -- than called because that function calls ff_approve_batch() itself and
  -- would otherwise flip status a second time / double-log.
  if v_batch.batch_kind = 'seller_digest' then
    select count(*) into v_total from winnerdata.seller_digest_leads where batch_date = p_batch_date;
  else
    select count(*) into v_total from winnerdata.ff_batch_leads where batch_date = p_batch_date;
  end if;

  select count(*) into v_approved
  from winnerdata.ff_batch_lead_review
  where batch_date = p_batch_date and decision = 'approved';

  insert into winnerdata.lms_audit_log (org_id, actor, action, target_table, target_id, detail)
  values (
    '032f4717-545f-4a18-b48b-28ea4257699d'::uuid, v_email, 'ff_batch_approve_authenticated',
    'winnerdata.ff_batch_approvals', p_batch_date::text,
    jsonb_build_object(
      'approved_by_user_id', v_uid, 'snapshot_hash', v_hash,
      'total_leads', v_total, 'approved_for_send', v_approved,
      'excluded_unreviewed_or_rejected', greatest(v_total - v_approved, 0)
    )
  );

  return v_approve_result || jsonb_build_object(
    'approval_provenance', 'authenticated_lms_click',
    'approved_by_user_id', v_uid,
    'approved_by_email', v_email,
    'snapshot_hash', v_hash,
    'total_leads', v_total, 'approved_for_send', v_approved,
    'excluded_unreviewed_or_rejected', greatest(v_total - v_approved, 0)
  );
end;
$$;

revoke all on function public.ff_batch_approve_authenticated(date) from public;
grant execute on function public.ff_batch_approve_authenticated(date) to authenticated;

-- ============================================================
-- 6. Send-path status vocabulary (issue #19745 item 2 -- see
--    scripts/winnerdata_ff_send_approved.py, same change set).
-- ============================================================

alter table winnerdata.ff_digest_log drop constraint ff_digest_log_status_check;
alter table winnerdata.ff_digest_log
  add constraint ff_digest_log_status_check
  check (status in (
    'sent', 'no_leads_sent', 'blocked_no_email', 'blocked_sandbox_recipient',
    'blocked_unreviewed_leads', 'blocked_unverified_approval', 'error'
  ));

comment on column winnerdata.ff_digest_log.status is
  'blocked_unverified_approval (2026-09-02, issue #19745): the batch was '
  'status=''approved'' but no winnerdata.ff_batch_approvals row exists whose '
  'snapshot_hash matches the batch''s current (batch_date, batch_kind, '
  'lead_count) -- either it was never approved through the authenticated LMS '
  'path, or the batch changed after approval. Hard error, never a silent '
  'skip. blocked_unreviewed_leads: distinct pre-existing condition (batch has '
  'a verified approval but no lead is decision=''approved'').';

-- ============================================================
-- 7. Retro-audit (issue #19745 item 3). Annotate, never rewrite: any batch
--    with approved_at set that predates the LMS Batch Review screen
--    (c9e406bd, merged 2026-09-01T16:53:18Z) or has no matching
--    ff_batch_approvals row is legacy-unverified. The 2026-08-29 row's
--    approved_by text was already corrected in a prior session (#19659
--    closeout) -- not touched again here.
-- ============================================================

update winnerdata.ff_batches
set approval_provenance = 'unverified-legacy'
where approved_at is not null
  and approval_provenance is null
  and (
    approved_at < '2026-09-01T16:53:18Z'::timestamptz
    or not exists (
      select 1 from winnerdata.ff_batch_approvals a where a.batch_date = ff_batches.batch_date
    )
  );

commit;
