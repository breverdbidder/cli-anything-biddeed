-- Finish the summitleads -> winnerdata rename dispatched 2026-08-23 (#19392)
-- and never completed. Issue #19486 (2026-08-26): "summitleads" is retired
-- permanently, everywhere. Sequencing: issue #19485 (identity/contact
-- resolution run against summitleads.* tables, GHA run 32968457140) was
-- confirmed completed (status=completed, conclusion=success) before this
-- migration was written or applied -- nothing was mid-flight against the
-- old schema name at execution time.
--
-- Approach: ALTER SCHEMA RENAME is atomic and preserves every table, row,
-- trigger, view, index, sequence, and grant with zero data loss -- tables
-- are NOT recreated and copied by hand. The one wrinkle: a `winnerdata`
-- schema already exists (created 2026-08-25 per #19446/#19452 as the first
-- tenant of the new name) holding `owner_portfolio` (15 rows) and
-- `parcel_underwriting` (1 row), both already referenced by their final
-- `winnerdata.*` name in scripts/portfolio_fact_finder_render.py and
-- scripts/skiptrace_20260825_portfolio_batch.py. Renaming `summitleads`
-- straight to `winnerdata` would collide with that. Fix: swap the
-- pre-existing `winnerdata` out of the way first, do the real rename, then
-- move those 2 tables back in under the same final name -- no script
-- changes needed for them. Full pre-execution inventory of that schema
-- (information_schema.tables + pg_proc + information_schema.sequences +
-- pg_type) also surfaced 3 helper functions -- roof_age_years(date),
-- construction_class_from_dor(text), estimated_affordability_tier(text,
-- bigint) -- with no summitleads references in their bodies, moved back
-- the same way as the 2 tables.
--
-- Second wrinkle: ALTER SCHEMA RENAME moves function *objects* (same OID,
-- so triggers/grants/pg_cron references by name keep working once the
-- calling side is also updated) but does NOT rewrite the literal SQL text
-- inside plpgsql/sql function bodies, nor a function's stored search_path
-- config. Every function under the old schema, plus every `public` function
-- that hardcoded `summitleads.*` table references, is recreated in place
-- (CREATE OR REPLACE -- same OID, same signature, same SECURITY DEFINER
-- flag) with `winnerdata.` substituted for `summitleads.` throughout.
-- Verified via information_schema.routines + pg_proc.proconfig this session
-- that these 15 functions (8 in the old schema, 7 in public) are the
-- complete set referencing `summitleads` anywhere in their bodies.

BEGIN;

ALTER SCHEMA winnerdata RENAME TO winnerdata_preexisting_tmp;

ALTER SCHEMA summitleads RENAME TO winnerdata;

ALTER TABLE winnerdata_preexisting_tmp.owner_portfolio SET SCHEMA winnerdata;
ALTER TABLE winnerdata_preexisting_tmp.parcel_underwriting SET SCHEMA winnerdata;
ALTER FUNCTION winnerdata_preexisting_tmp.roof_age_years(date) SET SCHEMA winnerdata;
ALTER FUNCTION winnerdata_preexisting_tmp.construction_class_from_dor(text) SET SCHEMA winnerdata;
ALTER FUNCTION winnerdata_preexisting_tmp.estimated_affordability_tier(text, bigint) SET SCHEMA winnerdata;

DROP SCHEMA winnerdata_preexisting_tmp;

-- ---------------------------------------------------------------------
-- Function bodies: replace every hardcoded `summitleads.` reference with
-- `winnerdata.`. CREATE OR REPLACE keeps the existing OID, so triggers
-- (leads_tag_lender_or_plaintiff, routing_decisions_block_lender_plaintiff,
-- leads_recompute_sla, lead_activity_recompute_parent_sla,
-- routing_decisions_recompute_lead_sla) stay attached without needing to be
-- dropped/recreated.
-- ---------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.ff_get_lead(p_org_id uuid, p_lead_id uuid)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, winnerdata
AS $func$
declare
  result jsonb;
begin
  if p_org_id is null or p_org_id <> '032f4717-545f-4a18-b48b-28ea4257699d'::uuid then
    return null;
  end if;

  select jsonb_build_object(
    'lead_id', l.lead_id,
    'org_id', l.org_id,
    'entity_name', l.entity_name,
    'contact_name', l.contact_name,
    'contact_phone', l.contact_phone,
    'contact_email', l.contact_email,
    'parcel_id', l.parcel_id,
    'product_line', l.product_line,
    'consent_status', l.consent_status,
    'auction', jsonb_build_object(
      'property_address', v.property_address,
      'county', v.county,
      'sale_type', v.sale_type,
      'auction_date', v.auction_date,
      'sold_amount', v.sold_amount,
      'case_number', v.case_number
    ),
    'parcel', jsonb_build_object(
      'act_yr_blt', fp.act_yr_blt,
      'eff_yr_blt', fp.eff_yr_blt,
      'tot_lvg_ar', fp.tot_lvg_ar,
      'no_res_unt', fp.no_res_unt,
      'const_clas', fp.const_clas,
      'jv', fp.jv,
      'lnd_val', fp.lnd_val,
      'bldg_val', (fp.jv - fp.lnd_val),
      'dor_uc', fp.dor_uc,
      'own_name', fp.own_name,
      'own_addr1', fp.own_addr1,
      'phy_addr1', fp.phy_addr1,
      'phy_city', fp.phy_city
    ),
    'responses', coalesce((
      select jsonb_object_agg(r.field, r.value)
      from winnerdata.ff_responses r
      where r.lead_id = l.lead_id and r.org_id = p_org_id
    ), '{}'::jsonb),
    'verification', (
      select jsonb_build_object(
        'badge', case
          when pa.verdict = 'pass' then 'VERIFIED'
          when v.case_number is null and mpa.verdict = 'pass' then 'VERIFIED'
          else 'NOT VERIFIED'
        end,
        'verified_via', case
          when pa.verdict = 'pass' then 'court_record'
          when v.case_number is null and mpa.verdict = 'pass' then 'parcel_completeness'
          else null
        end,
        'reason', coalesce(
          case
            when pa.verdict = 'pass' then
              'Verified against a court record: parcel ID/address matched the county property appraiser record for case ' || v.case_number || '.'
            when pa.verdict is not null then pa.verdict_note
            when v.case_number is null and mpa.verdict = 'pass' then
              'Verified against county property appraiser records: single confirmed parcel match with complete appraisal data.'
            when v.case_number is null and mpa.verdict is not null then mpa.verdict_note
            when cfg.blocked_by_waf then cfg.known_issues
            when cfg.appraiser_url is not null then 'Appraiser cross-verification is configured for this county but has not run for this parcel yet.'
            else 'No property appraiser cross-verification source is configured for this county yet.'
          end,
          'No property appraiser cross-verification source is configured for this county yet.'
        ),
        'appraiser_url', coalesce(cfg.appraiser_url, fc.appraiser_url),
        'audited_at', coalesce(pa.audited_at, mpa.audited_at)
      )
      from (select v.county as slug) county_ctx
      left join public.fl_property_appraiser_configs cfg on cfg.county_slug = county_ctx.slug
      left join public.fl_counties fc on fc.slug = county_ctx.slug
      left join lateral (
        select verdict, verdict_note, audited_at
        from public.parity_audit
        where case_number = v.case_number and field_name in ('parcel_id', 'address')
        order by (verdict = 'pass') desc, audited_at desc nulls last
        limit 1
      ) pa on true
      left join lateral (
        select (r ->> 'verdict') as verdict,
               (r ->> 'verdict_note') as verdict_note,
               (r ->> 'audited_at')::timestamptz as audited_at
        from public.ff_mls_parcel_audit(l.parcel_id, fp.co_no) r
      ) mpa on v.case_number is null and fp.parcel_id is not null
    )
  )
  into result
  from winnerdata.leads l
  left join winnerdata.v_producer_intake v on v.lead_id = l.lead_id
  left join public.fl_parcels fp on fp.parcel_id = l.parcel_id
  where l.lead_id = p_lead_id and l.org_id = p_org_id;

  return result;
end;
$func$;

CREATE OR REPLACE FUNCTION public.ff_healthz()
RETURNS jsonb
LANGUAGE sql SECURITY DEFINER
SET search_path = public, winnerdata
AS $func$
  select jsonb_build_object(
    'status', 'ok',
    'leads', (select count(*) from winnerdata.leads),
    'quote_drafts', (select count(*) from winnerdata.quote_drafts),
    'binds', (select count(*) from winnerdata.binds),
    'ff_responses', (select count(*) from winnerdata.ff_responses),
    'checked_at', now()
  );
$func$;

CREATE OR REPLACE FUNCTION public.ff_mark_delivered(p_org_id uuid, p_lead_id uuid)
RETURNS timestamp with time zone
LANGUAGE sql SECURITY DEFINER
SET search_path = public, winnerdata
AS $func$
  update winnerdata.leads
  set delivered_at = coalesce(delivered_at, now())
  where lead_id = p_lead_id and org_id = p_org_id
  returning delivered_at;
$func$;

CREATE OR REPLACE FUNCTION public.ff_portal_leads(p_org_id uuid)
RETURNS TABLE(lead_id uuid, entity_name text, contact_name text, contact_phone text, contact_email text, property_address text, county text, sale_type text, auction_date date, sold_amount numeric, case_number text, consent_status text, days_since_auction integer, is_bound boolean)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, winnerdata
AS $func$
begin
  if p_org_id is null or p_org_id <> '032f4717-545f-4a18-b48b-28ea4257699d'::uuid then
    return;
  end if;

  return query
  select
    l.lead_id, l.entity_name, l.contact_name, l.contact_phone, l.contact_email,
    v.property_address, v.county, v.sale_type, v.auction_date, v.sold_amount, v.case_number,
    l.consent_status::text,
    case when v.auction_date is not null then (current_date - v.auction_date)::int else null end,
    exists (select 1 from winnerdata.binds b where b.lead_id = l.lead_id)
  from winnerdata.leads l
  left join winnerdata.v_producer_intake v on v.lead_id = l.lead_id
  where l.org_id = p_org_id
  order by v.auction_date desc nulls last;
end;
$func$;

CREATE OR REPLACE FUNCTION public.ff_record_bind(p_org_id uuid, p_lead_id uuid, p_premium_cents integer, p_product_line text)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, winnerdata
AS $func$
declare
  new_bind_id uuid;
begin
  if p_org_id is null or p_org_id <> '032f4717-545f-4a18-b48b-28ea4257699d'::uuid then
    return jsonb_build_object('ok', false, 'error', 'org_mismatch');
  end if;

  if not exists (select 1 from winnerdata.leads where lead_id = p_lead_id and org_id = p_org_id) then
    return jsonb_build_object('ok', false, 'error', 'lead_not_found');
  end if;

  insert into winnerdata.binds (bind_id, lead_id, org_id, product_line, premium_cents, bound_at)
  values (gen_random_uuid(), p_lead_id, p_org_id, p_product_line::winnerdata.product_line, p_premium_cents, now())
  returning bind_id into new_bind_id;

  return jsonb_build_object('ok', true, 'bind_id', new_bind_id);
end;
$func$;

CREATE OR REPLACE FUNCTION public.ff_upsert_response(p_org_id uuid, p_lead_id uuid, p_property_id text, p_field text, p_value text, p_updated_by text)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, winnerdata
AS $func$
begin
  if p_org_id is null or p_org_id <> '032f4717-545f-4a18-b48b-28ea4257699d'::uuid then
    return jsonb_build_object('ok', false, 'error', 'org_mismatch');
  end if;

  if not exists (select 1 from winnerdata.leads where lead_id = p_lead_id and org_id = p_org_id) then
    return jsonb_build_object('ok', false, 'error', 'lead_not_found');
  end if;

  insert into winnerdata.ff_responses (org_id, lead_id, property_id, field, value, updated_by, updated_at)
  values (p_org_id, p_lead_id, p_property_id, p_field, p_value, p_updated_by, now());

  return jsonb_build_object('ok', true);
end;
$func$;

CREATE OR REPLACE FUNCTION public.sync_mls_sale_close_events()
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, winnerdata, pg_catalog
AS $func$
DECLARE
  v_watermark      timestamptz;
  v_candidate_count integer;
  v_new_watermark  timestamptz;
  v_inserted       integer;
  v_backfilled     integer;
  v_dispatch_id    text := 'mls-sale-close-sync-' || to_char(now() at time zone 'utc', 'YYYYMMDD-HH24MISS');
BEGIN
  SELECT last_watermark INTO v_watermark
  FROM winnerdata.mls_sync_state WHERE job_name = 'mls_sale_close_sync';

  IF v_watermark IS NULL THEN
    v_watermark := '1970-01-01'::timestamptz;
  END IF;

  DROP TABLE IF EXISTS pg_temp._mls_candidates;
  CREATE TEMP TABLE _mls_candidates ON COMMIT DROP AS
  SELECT sl.id, sl.county, sl.formatted_address, sl.zip_code, sl.mls_number, sl.sold_price,
         sl.listed_date, sl.removed_date, sl.fetched_at
  FROM public.sale_listings sl
  WHERE sl.status = 'SOLD'
    AND sl.fetched_at > v_watermark
  ORDER BY sl.removed_date DESC NULLS LAST, sl.fetched_at DESC
  LIMIT 20000;

  SELECT count(*), max(fetched_at) INTO v_candidate_count, v_new_watermark FROM _mls_candidates;

  WITH matched AS (
    SELECT DISTINCT ON (c.id)
      c.id, c.county, c.formatted_address, c.mls_number, c.sold_price,
      c.listed_date, c.removed_date, c.fetched_at, fp.parcel_id
    FROM _mls_candidates c
    LEFT JOIN public.fl_counties fc ON fc.slug = c.county
    LEFT JOIN public.fl_parcels fp
      ON fp.co_no = fc.co_no
     AND fp.phy_addr1 = upper(trim(split_part(c.formatted_address, ',', 1)))
     AND fp.phy_zipcd = c.zip_code
    ORDER BY c.id, fp.parcel_id NULLS LAST
  )
  INSERT INTO winnerdata.signal_events (event_type, source, county, parcel_id, entity_name, event_payload, occurred_at)
  SELECT
    'mls_sale_close', 'homeharvest_realtor_com', m.county, m.parcel_id, NULL,
    jsonb_build_object(
      'listing_id', m.id, 'mls_number', m.mls_number, 'sold_price', m.sold_price,
      'formatted_address', m.formatted_address, 'listed_date', m.listed_date, 'removed_date', m.removed_date
    ),
    COALESCE(m.removed_date::timestamptz, m.fetched_at)
  FROM matched m
  WHERE NOT EXISTS (
    SELECT 1 FROM winnerdata.signal_events se
    WHERE se.event_type = 'mls_sale_close' AND (se.event_payload ->> 'listing_id') = m.id
  );
  GET DIAGNOSTICS v_inserted = ROW_COUNT;

  IF v_candidate_count > 0 THEN
    UPDATE winnerdata.mls_sync_state
    SET last_watermark = v_new_watermark, last_run_at = now(), last_run_inserted = v_inserted
    WHERE job_name = 'mls_sale_close_sync';
  ELSE
    UPDATE winnerdata.mls_sync_state
    SET last_run_at = now(), last_run_inserted = 0
    WHERE job_name = 'mls_sale_close_sync';
  END IF;

  UPDATE winnerdata.signal_events se
  SET entity_name = fp.own_name
  FROM public.fl_parcels fp, public.fl_counties fc
  WHERE se.event_type = 'mls_sale_close'
    AND se.entity_name IS NULL
    AND se.parcel_id IS NOT NULL
    AND fc.slug = se.county
    AND fp.co_no = fc.co_no
    AND fp.parcel_id = se.parcel_id
    AND fp.own_name IS NOT NULL
    AND fp.updated_at > se.occurred_at;
  GET DIAGNOSTICS v_backfilled = ROW_COUNT;

  UPDATE winnerdata.mls_sync_state
  SET last_run_backfilled = v_backfilled
  WHERE job_name = 'mls_sale_close_sync';

  INSERT INTO public.agent_ops_log (dispatch_id, task, status, evidence, severity)
  VALUES (
    v_dispatch_id, 'winnerdata-mls-sale-close-sync', 'VERIFIED',
    'candidates=' || v_candidate_count::text || ' inserted=' || v_inserted::text ||
      ' entity_name_backfilled=' || v_backfilled::text ||
      ' watermark=' || COALESCE(v_new_watermark, v_watermark)::text,
    'info'
  );

  RETURN jsonb_build_object(
    'candidates', v_candidate_count, 'inserted', v_inserted,
    'entity_name_backfilled', v_backfilled, 'watermark', COALESCE(v_new_watermark, v_watermark)
  );
END;
$func$;

CREATE OR REPLACE FUNCTION winnerdata.block_lender_plaintiff_routing()
RETURNS trigger
LANGUAGE plpgsql
AS $func$
declare
  v_flagged boolean;
  v_override boolean;
  v_entity text;
begin
  select is_lender_or_plaintiff, manual_buyer_override, entity_name
    into v_flagged, v_override, v_entity
  from winnerdata.leads where lead_id = new.lead_id;

  if v_flagged and not v_override then
    raise exception 'winnerdata.routing_decisions blocked: lead % (entity_name=%) is flagged is_lender_or_plaintiff -- the lender/servicer took the property back, not a buyer prospect. Set manual_buyer_override=true after human review to route anyway.',
      new.lead_id, v_entity;
  end if;
  return new;
end;
$func$;

CREATE OR REPLACE FUNCTION winnerdata.lead_activity_recompute_parent_sla()
RETURNS trigger
LANGUAGE plpgsql
AS $func$
begin
  if new.activity_type = 'contact_attempt' then
    perform winnerdata.touch_lead_sla(new.lead_id);
  end if;
  return new;
end;
$func$;

CREATE OR REPLACE FUNCTION winnerdata.leads_recompute_sla()
RETURNS trigger
LANGUAGE plpgsql
AS $func$
declare
  v_first_contact_at timestamptz;
  v_timeout interval;
begin
  select min(la.occurred_at) into v_first_contact_at
  from winnerdata.lead_activity la
  where la.lead_id = new.lead_id and la.activity_type = 'contact_attempt';

  select coalesce(max(rd.sla_timeout_minutes), 5) * interval '1 minute'
    into v_timeout
  from winnerdata.routing_decisions rd
  where rd.lead_id = new.lead_id;

  if new.delivered_at is null then
    new.sla_tier := null;
    new.sla_breach := false;
  elsif v_first_contact_at is null then
    if now() - new.delivered_at > v_timeout then
      new.sla_tier := 'no_contact';
      new.sla_breach := true;
    else
      new.sla_tier := null;
      new.sla_breach := false;
    end if;
  else
    new.sla_breach := (v_first_contact_at - new.delivered_at) > v_timeout;
    new.sla_tier := case
      when v_first_contact_at - new.delivered_at <= interval '5 minutes' then 'under_5min'
      when v_first_contact_at - new.delivered_at <= interval '30 minutes' then '5_to_30min'
      when v_first_contact_at - new.delivered_at <= interval '60 minutes' then '30_to_60min'
      else 'over_60min'
    end;
  end if;
  return new;
end;
$func$;

CREATE OR REPLACE FUNCTION winnerdata.routing_decisions_recompute_lead_sla()
RETURNS trigger
LANGUAGE plpgsql
AS $func$
begin
  perform winnerdata.touch_lead_sla(new.lead_id);
  return new;
end;
$func$;

CREATE OR REPLACE FUNCTION winnerdata.run_sla_escalation_sweep()
RETURNS TABLE(lead_id uuid, action text, detail text)
LANGUAGE plpgsql
AS $func$
declare
  r record;
  v_backup_producer_id uuid;
begin
  for r in select * from winnerdata.sla_escalation_candidates() loop
    if exists (
      select 1 from winnerdata.lead_activity la
      where la.lead_id = r.lead_id and la.activity_type = 'sla_escalation'
        and la.occurred_at > r.delivered_at
    ) then
      continue;
    end if;

    if r.distinct_producer_count > 1 then
      select p.producer_id into v_backup_producer_id
      from winnerdata.producers p
      where p.org_id = r.org_id and p.active
        and lower(p.full_name) not in (
          select lower(p2.full_name) from winnerdata.producers p2
          join winnerdata.routing_decisions rd2 on rd2.producer_id = p2.producer_id
          where rd2.lead_id = r.lead_id
        )
      limit 1;
    else
      v_backup_producer_id := null;
    end if;

    if v_backup_producer_id is not null then
      insert into winnerdata.routing_decisions (lead_id, org_id, producer_id, product_line, routing_reason, sla_timeout_minutes)
      select r.lead_id, r.org_id, v_backup_producer_id, l.product_line, 'sla_breach_auto_reroute', 5
      from winnerdata.leads l where l.lead_id = r.lead_id;

      insert into winnerdata.lead_activity (lead_id, org_id, activity_type, channel, payload)
      values (r.lead_id, r.org_id, 'sla_escalation', 'system',
              jsonb_build_object('action', 'rerouted', 'backup_producer_id', v_backup_producer_id, 'minutes_overdue', r.minutes_overdue));
      lead_id := r.lead_id; action := 'rerouted'; detail := 'routed to distinct backup producer';
      return next;
    else
      insert into winnerdata.lead_activity (lead_id, org_id, activity_type, channel, payload)
      values (r.lead_id, r.org_id, 'sla_escalation', 'system',
              jsonb_build_object(
                'action', 'escalating_alert_required', 'minutes_overdue', r.minutes_overdue,
                'note', 'single-producer org -- SMS-then-call escalation required by spec; no notification channel provisioned (BLOCKED, see PR)'
              ));
      lead_id := r.lead_id; action := 'escalating_alert_logged'; detail := 'no SMS/call channel provisioned -- logged only, see BLOCKED note';
      return next;
    end if;
  end loop;
  return;
end;
$func$;

CREATE OR REPLACE FUNCTION winnerdata.sla_escalation_candidates(p_org_id uuid DEFAULT NULL::uuid)
RETURNS TABLE(lead_id uuid, org_id uuid, delivered_at timestamp with time zone, minutes_overdue numeric, distinct_producer_count integer)
LANGUAGE sql
AS $func$
  select
    l.lead_id, l.org_id, l.delivered_at,
    round(extract(epoch from (now() - l.delivered_at)) / 60, 1) as minutes_overdue,
    (select count(distinct lower(p.full_name))
       from winnerdata.producers p
       where p.org_id = l.org_id and p.active) as distinct_producer_count
  from winnerdata.leads l
  where l.delivered_at is not null
    and l.sla_tier = 'no_contact'
    and (p_org_id is null or l.org_id = p_org_id);
$func$;

CREATE OR REPLACE FUNCTION winnerdata.tag_lender_or_plaintiff()
RETURNS trigger
LANGUAGE plpgsql
AS $func$
declare
  v_tier1_buyer_type text;
begin
  select mca.tier1_buyer_type
    into v_tier1_buyer_type
  from winnerdata.signal_events se
  join public.multi_county_auctions mca on mca.id::text = se.event_payload ->> 'auction_id'
  where se.signal_id = new.signal_id;

  if v_tier1_buyer_type = 'plaintiff' then
    new.is_lender_or_plaintiff := true;
    new.consent_certificate := coalesce(new.consent_certificate, '{}'::jsonb) ||
      jsonb_build_object('compliance_flag', 'LENDER_TOOK_BACK_PROPERTY_NOT_BUYER_LEAD',
                          'compliance_source', 'tier1_buyer_type');
  elsif v_tier1_buyer_type = 'third_party' then
    new.is_lender_or_plaintiff := false;
  elsif new.entity_name ~* '(mortgage|bank|n\.a\.|national association|savings fund|loan servicing|trust\y|fannie mae|freddie mac|\yhud\y|department of housing|association)' then
    new.is_lender_or_plaintiff := true;
    new.consent_certificate := coalesce(new.consent_certificate, '{}'::jsonb) ||
      jsonb_build_object('compliance_flag', 'LENDER_TOOK_BACK_PROPERTY_NOT_BUYER_LEAD_UNCONFIRMED',
                          'compliance_source', 'entity_name_regex_fallback');
  end if;
  return new;
end;
$func$;

CREATE OR REPLACE FUNCTION winnerdata.touch_lead_sla(p_lead_id uuid)
RETURNS void
LANGUAGE sql
AS $func$
  update winnerdata.leads set delivered_at = delivered_at where lead_id = p_lead_id;
$func$;

COMMIT;
