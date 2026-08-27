-- Nine-case FF Elementix-parity portfolio enrichment (issue #19531).
--
-- Finding fixed here (not in the issue text, but load-bearing for DoD 14/16/17):
-- winnerdata.ff_batches is a single shared table keyed only on batch_date,
-- used by TWO unrelated features that can legitimately collide on the same
-- calendar date:
--   1. "The Daily Winner FFs" seller-lead digest (winnerdata.leads / signal_events)
--   2. This nine-case third-party-auction portfolio FF batch (winnerdata.ff_batch_leads)
-- scripts/winnerdata_ff_send_approved.py's get_approved_batches() selects ANY
-- row with status='approved' and sends it using the seller-digest logic
-- (queries winnerdata.leads, which has nothing to do with ff_batch_leads),
-- then unconditionally calls mark_sent() even when 0 leads match. Its
-- schedule trigger (*/15 10-15 UTC) runs independently of the nine-case
-- enrichment-first gate the issue requires, so approving the nine-case batch
-- would let the backstop poll flip it to status='sent' before enrichment
-- ever completes -- violating "approval cannot dispatch client-send before
-- enrichment complete" and "only explicit final approval/send transitions to
-- sent". Fix: add an explicit batch_kind discriminator and gate both the
-- notifier trigger and the generic send script by it. Purely additive --
-- no existing column dropped or retyped, no PK change.

begin;

alter table winnerdata.ff_batches
  add column if not exists batch_kind text not null default 'seller_digest';

alter table winnerdata.ff_batches
  drop constraint if exists ff_batches_batch_kind_check;
alter table winnerdata.ff_batches
  add constraint ff_batches_batch_kind_check
  check (batch_kind in ('seller_digest','nine_case_portfolio'));

-- Backfill: the only live row today (2026-08-26) was built by
-- build_ff_portfolio_batch() and has 9 winnerdata.ff_batch_leads children --
-- it is the nine-case portfolio kind, not a seller-digest row.
update winnerdata.ff_batches b
set batch_kind = 'nine_case_portfolio'
where exists (select 1 from winnerdata.ff_batch_leads l where l.batch_date = b.batch_date)
  and b.batch_kind <> 'nine_case_portfolio';

-- build_ff_portfolio_batch always tags its own rows correctly, including on
-- the do-nothing/no-op branches used for idempotent re-runs.
create or replace function winnerdata.build_ff_portfolio_batch(p_batch_date date default (current_date - 1))
 returns jsonb
 language plpgsql
 security definer
 set search_path to 'public', 'winnerdata'
as $function$
declare
  v_total integer;
  v_matched integer;
  v_unmatched integer;
  v_existing_status text;
  v_hash text;
begin
  create temp table _ff_portfolio_candidates on commit drop as
  select
    a.id as auction_id, a.county, a.auction_date, a.property_address, a.case_number, a.sale_type,
    a.tier1_buyer_type, a.winning_bidder, a.tier1_sold_amount, a.market_value, a.assessed_value,
    a.parcel_id as auction_parcel_id, x.pin_clean,
    p.luse_code as dor_luse_code, p.luse_desc as dor_luse_desc, p.owner_name, p.owner_name2,
    p.owner_addr1, p.owner_addr2, p.owner_city, p.owner_state, p.owner_zip,
    p.site_addr, p.site_city, p.site_zip, p.num_buildings, p.year_built, p.sqft_heated,
    p.val_market, p.val_assessed, p.pa_link,
    case when a.tier1_sold_amount is not null and p.val_assessed > 0
      then round((a.tier1_sold_amount - p.val_assessed)::numeric / p.val_assessed * 100, 2) end as discount_to_assessed_pct,
    case when a.tier1_sold_amount is not null and p.val_market > 0
      then round((a.tier1_sold_amount - p.val_market)::numeric / p.val_market * 100, 2) end as discount_to_market_pct,
    coalesce(opc.property_count, 0) as portfolio_property_count,
    opc.portfolio_counties, opc.portfolio_assessed_value_total, opc.portfolio_market_value_total,
    null::text as resolved_principal_name,
    null::text as phone,
    null::text as email,
    null::text as business_website,
    jsonb_build_object(
      'auction_source','public.multi_county_auctions','auction_id',a.id,'auction_date',a.auction_date,
      'tier1_buyer_type',a.tier1_buyer_type,'winning_bidder',a.winning_bidder,
      'tier1_sold_amount',a.tier1_sold_amount,'market_value',a.market_value,'assessed_value',a.assessed_value,
      'auction_parcel_id',a.parcel_id,'crosswalk_pin_clean',x.pin_clean,
      'parcel_source','public.zw_parcels','parcel_pin_clean',p.pin_clean,
      'parcel_data_source',p.data_source,'parcel_updated_at',p.updated_at
    ) as source_snapshot
  from public.multi_county_auctions a
  left join winnerdata.ff_parcel_crosswalk x on x.auction_id=a.id
  left join public.zw_parcels p on p.pin_clean=x.pin_clean
  left join lateral (
    select count(*)::integer as property_count,
           array_agg(distinct op.county order by op.county) as portfolio_counties,
           sum(coalesce(op.jv,0)) as portfolio_assessed_value_total,
           null::numeric as portfolio_market_value_total
    from winnerdata.owner_portfolio op
    where upper(regexp_replace(coalesce(op.entity_name_raw,''),'[^A-Z0-9]','','g')) = upper(regexp_replace(coalesce(a.winning_bidder,''),'[^A-Z0-9]','','g'))
  ) opc on true
  where a.auction_date=p_batch_date and a.tier1_buyer_type='third_party'
    and nullif(btrim(a.winning_bidder),'') is not null;

  select count(*) into v_total from _ff_portfolio_candidates;
  select count(*) filter (where pin_clean is not null and owner_name is not null) into v_matched from _ff_portfolio_candidates;
  v_unmatched := v_total-v_matched;
  if v_total=0 then raise exception using errcode='no_data_found', message=format('No third-party FF candidates for %s',p_batch_date); end if;
  if v_unmatched>0 then raise exception using errcode='check_violation', message=format('FF portfolio batch %s blocked: %s of %s candidates lack validated parcel SSOT',p_batch_date,v_unmatched,v_total); end if;

  select status into v_existing_status from winnerdata.ff_batches where batch_date=p_batch_date for update;
  if v_existing_status in ('approved','sent') then
    return jsonb_build_object('ok',false,'reason','batch already '||v_existing_status,'batch_date',p_batch_date,'lead_count',v_total);
  end if;

  select md5(coalesce(string_agg(auction_id::text||':'||pin_clean,',' order by auction_id),'')) into v_hash from _ff_portfolio_candidates;
  insert into winnerdata.ff_batches(batch_date,status,lead_count,batch_kind,updated_at)
  values(p_batch_date,'pending_approval',v_total,'nine_case_portfolio',now())
  on conflict(batch_date) do update set lead_count=excluded.lead_count,batch_kind='nine_case_portfolio',updated_at=now()
  where winnerdata.ff_batches.status='pending_approval';

  delete from winnerdata.ff_batch_leads where batch_date=p_batch_date;
  insert into winnerdata.ff_batch_leads(
    batch_date,auction_id,county,auction_date,property_address,case_number,sale_type,tier1_buyer_type,winning_bidder,
    tier1_sold_amount,market_value,assessed_value,auction_parcel_id,pin_clean,dor_luse_code,dor_luse_desc,
    owner_name,owner_name2,owner_addr1,owner_addr2,owner_city,owner_state,owner_zip,site_addr,site_city,site_zip,
    num_buildings,year_built,sqft_heated,val_market,val_assessed,discount_to_assessed_pct,discount_to_market_pct,pa_link,resolved_entity_name,
    portfolio_property_count,portfolio_counties,portfolio_assessed_value_total,portfolio_market_value_total,
    evidence_ledger,source_snapshot,freshness_metadata,unresolved_field_count,qa_status
  )
  select p_batch_date,auction_id,county,auction_date,property_address,case_number,sale_type,tier1_buyer_type,winning_bidder,
    tier1_sold_amount,market_value,assessed_value,auction_parcel_id,pin_clean,dor_luse_code,dor_luse_desc,
    owner_name,owner_name2,owner_addr1,owner_addr2,owner_city,owner_state,owner_zip,site_addr,site_city,site_zip,
    num_buildings,year_built,sqft_heated,val_market,val_assessed,discount_to_assessed_pct,discount_to_market_pct,pa_link,winning_bidder,
    portfolio_property_count,portfolio_counties,portfolio_assessed_value_total,portfolio_market_value_total,
    jsonb_build_object('auction_buyer','authoritative Sold To','parcel_match','validated crosswalk','identity','not yet resolved','contact','not yet verified'),
    source_snapshot,jsonb_build_object('auction_date',auction_date,'parcel_updated_at',source_snapshot->'parcel_updated_at'),
    (case when owner_name is null then 1 else 0 end + case when resolved_principal_name is null then 1 else 0 end + case when phone is null then 1 else 0 end + case when email is null then 1 else 0 end + case when business_website is null then 1 else 0 end),
    'PARTIAL_ENRICHMENT'
  from _ff_portfolio_candidates;

  return jsonb_build_object('ok',true,'batch_date',p_batch_date,'status','pending_approval','third_party_auction_count',v_total,'matched_parcel_count',v_matched,'unmatched_parcel_count',v_unmatched,'source_snapshot_hash',v_hash);
end;
$function$;

-- Fail-closed enrichment dispatch, scoped to nine_case_portfolio only. A
-- seller_digest batch approval must behave exactly as it did before this
-- migration (no forced GH dispatch, no exception on transient GH API issues)
-- -- only the nine-case portfolio kind requires the enrichment gate.
create or replace function winnerdata.notify_ff_batch_approved()
 returns trigger
 language plpgsql
 security definer
 set search_path to 'public', 'winnerdata'
as $function$
declare
  v_dispatch jsonb;
begin
  if new.status = 'approved' and old.status is distinct from 'approved' then
    if new.batch_kind = 'nine_case_portfolio' then
      v_dispatch := public.fire_workflow_dispatch(
        'breverdbidder/cli-anything-biddeed',
        'winnerdata-nine-ff-enrichment.yml',
        'main',
        jsonb_build_object('batch_date', new.batch_date::text)
      );

      if coalesce(v_dispatch->>'status','') <> 'dispatched' then
        raise exception using
          errcode = 'external_routine_exception',
          message = format('Approval blocked: nine-case enrichment dispatch failed: %s', v_dispatch::text);
      end if;

      update winnerdata.ff_batches
         set enrichment_status = 'running',
             enrichment_started_at = now(),
             enrichment_error = null,
             updated_at = now()
       where batch_date = new.batch_date;
    end if;
  end if;
  return new;
end;
$function$;

-- Elementix-parity KPI columns required by issue #19531 that do not already
-- exist under any name. Per the issue: "reuse existing exact-name fields if
-- present, document mapping instead of duplicating" -- the mapping for
-- fields the issue names that already exist under a different name:
--   issue name                  -> existing column
--   parcel_market_value         -> val_market
--   parcel_assessed_value       -> val_assessed
--   dor_use_code                -> dor_luse_code
--   dor_use_description         -> dor_luse_desc
--   resolved_entity_type        -> identity_type
--   identity_confidence         -> identity_match_confidence
--   identity_rationale          -> identity_match_rationale
--   portfolio_total_market_value -> portfolio_market_value_total
--   portfolio_total_assessed_value -> portfolio_assessed_value_total
--   principal_address           -> principal_home_address
--   related_entities_json       -> related_entities
--   source_evidence_json        -> evidence_ledger
-- All columns below are genuinely new (no existing equivalent), additive,
-- nullable, no default-value backfill required for existing rows.

comment on column winnerdata.ff_batch_leads.val_market is 'Elementix-parity mapping: issue field name parcel_market_value';
comment on column winnerdata.ff_batch_leads.val_assessed is 'Elementix-parity mapping: issue field name parcel_assessed_value';
comment on column winnerdata.ff_batch_leads.dor_luse_code is 'Elementix-parity mapping: issue field name dor_use_code';
comment on column winnerdata.ff_batch_leads.dor_luse_desc is 'Elementix-parity mapping: issue field name dor_use_description';
comment on column winnerdata.ff_batch_leads.identity_type is 'Elementix-parity mapping: issue field name resolved_entity_type';
comment on column winnerdata.ff_batch_leads.identity_match_confidence is 'Elementix-parity mapping: issue field name identity_confidence';
comment on column winnerdata.ff_batch_leads.identity_match_rationale is 'Elementix-parity mapping: issue field name identity_rationale';
comment on column winnerdata.ff_batch_leads.portfolio_market_value_total is 'Elementix-parity mapping: issue field name portfolio_total_market_value';
comment on column winnerdata.ff_batch_leads.portfolio_assessed_value_total is 'Elementix-parity mapping: issue field name portfolio_total_assessed_value';
comment on column winnerdata.ff_batch_leads.principal_home_address is 'Elementix-parity mapping: issue field name principal_address';
comment on column winnerdata.ff_batch_leads.related_entities is 'Elementix-parity mapping: issue field name related_entities_json';
comment on column winnerdata.ff_batch_leads.evidence_ledger is 'Elementix-parity mapping: issue field name source_evidence_json';

-- AUCTION TRUTH additions
alter table winnerdata.ff_batch_leads add column if not exists auction_url text;
alter table winnerdata.ff_batch_leads add column if not exists source_url text;

-- PARCEL/DOR SSOT additions
alter table winnerdata.ff_batch_leads add column if not exists parcel_match_method text;
alter table winnerdata.ff_batch_leads add column if not exists parcel_match_confidence text;
alter table winnerdata.ff_batch_leads add column if not exists parcel_source text;
alter table winnerdata.ff_batch_leads add column if not exists parcel_source_updated_at timestamptz;

-- PORTFOLIO/INVESTOR KPI additions
alter table winnerdata.ff_batch_leads add column if not exists portfolio_county_count integer;
alter table winnerdata.ff_batch_leads add column if not exists portfolio_total_jv numeric;
alter table winnerdata.ff_batch_leads add column if not exists portfolio_total_buildings integer;
alter table winnerdata.ff_batch_leads add column if not exists portfolio_total_sqft_heated integer;
alter table winnerdata.ff_batch_leads add column if not exists portfolio_dor_mix_json jsonb not null default '{}'::jsonb;
alter table winnerdata.ff_batch_leads add column if not exists portfolio_acquisition_source_mix_json jsonb not null default '{}'::jsonb;
alter table winnerdata.ff_batch_leads add column if not exists portfolio_properties_json jsonb not null default '[]'::jsonb;
alter table winnerdata.ff_batch_leads add column if not exists umbrella_opportunity boolean;
alter table winnerdata.ff_batch_leads add column if not exists master_policy_opportunity boolean;
alter table winnerdata.ff_batch_leads add column if not exists commercial_bop_opportunity boolean;
alter table winnerdata.ff_batch_leads add column if not exists flood_opportunity text;

-- RELATIONSHIP GRAPH additions
alter table winnerdata.ff_batch_leads add column if not exists registered_agent_source text;
alter table winnerdata.ff_batch_leads add column if not exists registered_agent_confidence text;
alter table winnerdata.ff_batch_leads add column if not exists principal_address_type text;
alter table winnerdata.ff_batch_leads add column if not exists principal_address_source text;
alter table winnerdata.ff_batch_leads add column if not exists relationship_evidence_json jsonb not null default '{}'::jsonb;
alter table winnerdata.ff_batch_leads add column if not exists relationship_conflict_status text not null default 'no_conflict';

-- CONTACT/WEB VERIFICATION additions (business vs individual split; existing
-- generic phone/email/business_website columns are kept and still populated
-- for backward compat with the pre-#19531 single-seller renderer path).
alter table winnerdata.ff_batch_leads add column if not exists business_website_source text;
alter table winnerdata.ff_batch_leads add column if not exists business_email text;
alter table winnerdata.ff_batch_leads add column if not exists business_email_source text;
alter table winnerdata.ff_batch_leads add column if not exists business_phone text;
alter table winnerdata.ff_batch_leads add column if not exists business_phone_type text;
alter table winnerdata.ff_batch_leads add column if not exists business_phone_source text;
alter table winnerdata.ff_batch_leads add column if not exists individual_phone text;
alter table winnerdata.ff_batch_leads add column if not exists individual_phone_type text;
alter table winnerdata.ff_batch_leads add column if not exists individual_phone_source text;
alter table winnerdata.ff_batch_leads add column if not exists individual_email text;
alter table winnerdata.ff_batch_leads add column if not exists individual_email_source text;
alter table winnerdata.ff_batch_leads add column if not exists contact_match_status text;
alter table winnerdata.ff_batch_leads add column if not exists contact_confidence text;
alter table winnerdata.ff_batch_leads add column if not exists contact_expires_at timestamptz;
alter table winnerdata.ff_batch_leads add column if not exists is_dnc boolean;
alter table winnerdata.ff_batch_leads add column if not exists is_tcpa_litigator boolean;
alter table winnerdata.ff_batch_leads add column if not exists phone_email_evidence_json jsonb not null default '{}'::jsonb;

-- QA/PROVENANCE additions (row-level; distinct from winnerdata.ff_batches'
-- parent-level enrichment_status column, which tracks the batch as a whole).
alter table winnerdata.ff_batch_leads add column if not exists row_enrichment_status text not null default 'not_started'
  check (row_enrichment_status in ('not_started','running','complete','failed'));
alter table winnerdata.ff_batch_leads add column if not exists enrichment_provider_status_json jsonb not null default '{}'::jsonb;
alter table winnerdata.ff_batch_leads add column if not exists source_snapshot_hash text;
alter table winnerdata.ff_batch_leads add column if not exists field_provenance_json jsonb not null default '{}'::jsonb;
alter table winnerdata.ff_batch_leads add column if not exists freshness_checked_at timestamptz;
alter table winnerdata.ff_batch_leads add column if not exists qa_errors_json jsonb not null default '[]'::jsonb;

comment on column winnerdata.ff_batch_leads.row_enrichment_status is 'Elementix-parity mapping: issue QA/PROVENANCE field name enrichment_status (child-row scope; parent scope is winnerdata.ff_batches.enrichment_status)';

commit;
