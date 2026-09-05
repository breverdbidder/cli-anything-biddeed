-- LMS reel/variant approve/reject screen (issue #20029, GTM-0 launch-night
-- readiness). Mirrors the unforgeable-approval pattern built for FF batches
-- in 20260902i_winnerdata_ff_batch_approvals_gate.sql: winnerdata.
-- reel_variant_review is Ariel's ground truth (docs/intent/20029.md
-- guardrail #2 -- this session must never write to it directly), so the
-- only write path is a SECURITY DEFINER RPC gated on a real Supabase Auth
-- JWT for an allow-listed admin (winnerdata.lms_admins, same table the FF
-- gate already created -- reused, not duplicated).
--
-- Read path (public.lms_reel_variants_list) is service_role-only, same
-- shape as public.lms_ff_batches_list -- the Worker's plain rpc() helper
-- calls it with SUPABASE_SERVICE_KEY, exactly like every other read in
-- workers/winnerdata-lms/src/index.js.

begin;

-- ============================================================
-- 1. BEFORE INSERT trigger -- the real, unconditional backstop (same
--    reasoning as winnerdata.enforce_ff_batch_approval_authenticated: a
--    trigger fires regardless of RLS bypass or DEFINER/INVOKER, so it is
--    what actually makes a service-role-forged review row impossible).
-- ============================================================

create or replace function winnerdata.enforce_reel_variant_review_authenticated()
returns trigger
language plpgsql
as $$
declare
  v_email text;
begin
  if auth.uid() is null then
    raise exception 'reel_variant_review insert rejected: no authenticated Supabase Auth JWT on this request (auth.uid() is null) -- service_role and anon callers cannot write a review decision'
      using errcode = '42501';
  end if;

  v_email := auth.email();
  if v_email is null or new.decided_by is distinct from v_email then
    raise exception 'reel_variant_review insert rejected: decided_by must equal the calling session''s authenticated email'
      using errcode = '42501';
  end if;

  if not exists (
    select 1 from winnerdata.lms_admins a where a.email = v_email and a.active
  ) then
    raise exception 'reel_variant_review insert rejected: % is not an active LMS admin', v_email
      using errcode = '42501';
  end if;

  return new;
end;
$$;

drop trigger if exists reel_variant_review_enforce_authenticated on winnerdata.reel_variant_review;
create trigger reel_variant_review_enforce_authenticated
  before insert on winnerdata.reel_variant_review
  for each row
  execute function winnerdata.enforce_reel_variant_review_authenticated();

-- Defense-in-depth RLS policy, same posture as ff_batch_approvals_insert_self
-- -- even if this table were ever granted directly to `authenticated`
-- (it is not; all writes go through the RPC below), a direct INSERT could
-- still only claim the caller's own auth.email().
alter table winnerdata.reel_variant_review force row level security;

drop policy if exists reel_variant_review_insert_self on winnerdata.reel_variant_review;
create policy reel_variant_review_insert_self
  on winnerdata.reel_variant_review
  for insert
  to authenticated
  with check (decided_by = auth.email());

-- ============================================================
-- 2. Read RPC -- service_role only, same grant shape as
--    public.lms_ff_batches_list. Returns every variant that still needs a
--    decision plus enough reel/QA context for the review screen (thumbnail
--    via video_url, hook title, county/sale type, QA verdict), and the
--    latest decision if one already exists (so "approved"/"rejected" rows
--    still show correctly instead of disappearing).
-- ============================================================

create or replace function public.lms_reel_variants_list()
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata, extensions
as $$
declare
  v_variants jsonb;
begin
  select coalesce(jsonb_agg(row_to_json(v) order by v.auction_date, v.county, v.sale_type, v.variant_key), '[]'::jsonb)
  into v_variants
  from (
    select
      rv.id as variant_id,
      rv.reel_id,
      rv.variant_key,
      rv.title,
      rv.archetype,
      rv.video_url,
      rv.short_code,
      rv.short_url,
      rv.qr_url,
      rv.qa_pass,
      rv.qa_scores,
      rv.is_draft,
      rv.lang,
      rv.status as variant_status,
      br.county,
      br.sale_type,
      br.phase,
      br.auction_date,
      br.status as reel_status,
      br.page_http_status,
      rev.decision,
      rev.note,
      rev.decided_by,
      rev.decided_at
    from winnerdata.reel_variants rv
    join winnerdata.biddeed_reels br on br.id = rv.reel_id
    left join lateral (
      select r.decision, r.note, r.decided_by, r.decided_at
      from winnerdata.reel_variant_review r
      where r.variant_id = rv.id
      order by r.decided_at desc
      limit 1
    ) rev on true
    where rv.lang = 'en'
  ) v;

  return jsonb_build_object('ok', true, 'variants', v_variants);
end;
$$;

revoke all on function public.lms_reel_variants_list() from public;
grant execute on function public.lms_reel_variants_list() to service_role;

-- ============================================================
-- 3. Write RPC -- authenticated only, one variant per call. Same shape as
--    public.ff_batch_approve_authenticated: mints nothing itself (the
--    Worker mints the admin JWT via mintAdminAccessToken()), just enforces
--    the gate and inserts.
-- ============================================================

create or replace function public.reel_variant_review_authenticated(
  p_variant_id uuid,
  p_decision text,
  p_note text default null
)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata, extensions
as $$
declare
  v_uid uuid := auth.uid();
  v_email text := auth.email();
begin
  if v_uid is null or v_email is null then
    return jsonb_build_object(
      'ok', false, 'reason', 'not_authenticated',
      'detail', 'This action requires a real Supabase Auth session -- service_role and anon callers cannot review a variant.'
    );
  end if;

  if not exists (select 1 from winnerdata.lms_admins a where a.email = v_email and a.active) then
    return jsonb_build_object('ok', false, 'reason', 'not_an_admin', 'email', v_email);
  end if;

  if p_decision not in ('approved', 'rejected', 'improvement_requested') then
    return jsonb_build_object('ok', false, 'reason', 'invalid_decision', 'decision', p_decision);
  end if;

  if not exists (select 1 from winnerdata.reel_variants where id = p_variant_id) then
    return jsonb_build_object('ok', false, 'reason', 'variant_not_found', 'variant_id', p_variant_id);
  end if;

  insert into winnerdata.reel_variant_review (variant_id, decision, note, decided_by, decided_at)
  values (p_variant_id, p_decision, p_note, v_email, now());

  return jsonb_build_object('ok', true, 'variant_id', p_variant_id, 'decision', p_decision, 'decided_by', v_email);
end;
$$;

revoke all on function public.reel_variant_review_authenticated(uuid, text, text) from public;
grant execute on function public.reel_variant_review_authenticated(uuid, text, text) to authenticated;

-- ============================================================
-- 4. Batch-approve RPC -- "batch approve for a day's slots" (issue body
--    deliverable 2). Approves every variant_id in the array in one call, so
--    the LMS screen's day-batch button is one request, not N.
-- ============================================================

create or replace function public.reel_variant_batch_approve_authenticated(
  p_variant_ids uuid[]
)
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata, extensions
as $$
declare
  v_uid uuid := auth.uid();
  v_email text := auth.email();
  v_id uuid;
  v_approved uuid[] := '{}';
  v_skipped uuid[] := '{}';
begin
  if v_uid is null or v_email is null then
    return jsonb_build_object('ok', false, 'reason', 'not_authenticated');
  end if;

  if not exists (select 1 from winnerdata.lms_admins a where a.email = v_email and a.active) then
    return jsonb_build_object('ok', false, 'reason', 'not_an_admin', 'email', v_email);
  end if;

  foreach v_id in array coalesce(p_variant_ids, '{}') loop
    if exists (select 1 from winnerdata.reel_variants where id = v_id) then
      insert into winnerdata.reel_variant_review (variant_id, decision, note, decided_by, decided_at)
      values (v_id, 'approved', 'batch approve', v_email, now());
      v_approved := v_approved || v_id;
    else
      v_skipped := v_skipped || v_id;
    end if;
  end loop;

  return jsonb_build_object('ok', true, 'approved', v_approved, 'skipped', v_skipped, 'decided_by', v_email);
end;
$$;

revoke all on function public.reel_variant_batch_approve_authenticated(uuid[]) from public;
grant execute on function public.reel_variant_batch_approve_authenticated(uuid[]) to authenticated;

commit;
