-- WinnerData FF portfolio SSOT enrichment for Protection Partners.
-- Scope: nine third-party auction cases from 2026-08-26.
-- Buyer type remains authoritative from multi_county_auctions.tier1_buyer_type.
-- Contact/relationship fields are intentionally nullable until verified by approved sources.

begin;

create table if not exists winnerdata.ff_parcel_crosswalk (
  auction_id uuid primary key references public.multi_county_auctions(id),
  auction_parcel_id text not null,
  pin_clean text not null,
  match_method text not null check (match_method in ('validated_normalization','authoritative_crosswalk','manual_verified')),
  verified_at timestamptz not null default now(),
  verified_by text,
  notes text,
  unique (auction_id, auction_parcel_id)
);

create index if not exists ff_parcel_crosswalk_pin_idx on winnerdata.ff_parcel_crosswalk(pin_clean);

create table if not exists winnerdata.ff_batch_leads (
  batch_date date not null references winnerdata.ff_batches(batch_date) on delete cascade,
  auction_id uuid not null references public.multi_county_auctions(id),
  county text,
  auction_date date not null,
  property_address text,
  case_number text,
  sale_type text,
  tier1_buyer_type text not null check (tier1_buyer_type = 'third_party'),
  winning_bidder text not null,
  tier1_sold_amount numeric,
  market_value numeric,
  assessed_value numeric,
  auction_parcel_id text not null,
  pin_clean text not null,
  dor_luse_code text,
  dor_luse_desc text,
  owner_name text,
  owner_name2 text,
  owner_addr1 text,
  owner_addr2 text,
  owner_city text,
  owner_state text,
  owner_zip text,
  site_addr text,
  site_city text,
  site_zip text,
  num_buildings integer,
  year_built integer,
  sqft_heated integer,
  val_market integer,
  val_assessed integer,
  discount_to_assessed_pct numeric,
  discount_to_market_pct numeric,
  pa_link text,
  resolved_entity_name text,
  resolved_principal_name text,
  identity_type text,
  identity_match_method text,
  identity_match_confidence numeric,
  identity_match_rationale text,
  registered_agent_name text,
  registered_agent_address text,
  related_entities jsonb not null default '[]'::jsonb,
  principal_home_address text,
  portfolio_property_count integer,
  portfolio_counties text[],
  portfolio_assessed_value_total numeric,
  portfolio_market_value_total numeric,
  phone text,
  email text,
  linkedin_url text,
  business_website text,
  phone_validity text,
  email_deliverability text,
  contact_provider text,
  contact_verified_at timestamptz,
  dnc_state text,
  evidence_ledger jsonb not null default '{}'::jsonb,
  source_snapshot jsonb not null default '{}'::jsonb,
  freshness_metadata jsonb not null default '{}'::jsonb,
  unresolved_field_count integer not null default 0,
  qa_status text not null default 'PARTIAL_ENRICHMENT',
  created_at timestamptz not null default now(),
  primary key (batch_date, auction_id)
);

-- Extend an earlier, narrower child table idempotently if it already exists.

alter table winnerdata.ff_batch_leads add column if not exists dor_luse_code text;
alter table winnerdata.ff_batch_leads add column if not exists dor_luse_desc text;
alter table winnerdata.ff_batch_leads add column if not exists owner_name2 text;
alter table winnerdata.ff_batch_leads add column if not exists owner_addr2 text;
alter table winnerdata.ff_batch_leads add column if not exists site_addr text;
alter table winnerdata.ff_batch_leads add column if not exists site_city text;
alter table winnerdata.ff_batch_leads add column if not exists site_zip text;
alter table winnerdata.ff_batch_leads add column if not exists val_market integer;
alter table winnerdata.ff_batch_leads add column if not exists val_assessed integer;
alter table winnerdata.ff_batch_leads add column if not exists discount_to_assessed_pct numeric;
alter table winnerdata.ff_batch_leads add column if not exists discount_to_market_pct numeric;
alter table winnerdata.ff_batch_leads add column if not exists resolved_entity_name text;
alter table winnerdata.ff_batch_leads add column if not exists resolved_principal_name text;
alter table winnerdata.ff_batch_leads add column if not exists identity_type text;
alter table winnerdata.ff_batch_leads add column if not exists identity_match_method text;
alter table winnerdata.ff_batch_leads add column if not exists identity_match_confidence numeric;
alter table winnerdata.ff_batch_leads add column if not exists identity_match_rationale text;
alter table winnerdata.ff_batch_leads add column if not exists registered_agent_name text;
alter table winnerdata.ff_batch_leads add column if not exists registered_agent_address text;
alter table winnerdata.ff_batch_leads add column if not exists related_entities jsonb not null default '[]'::jsonb;
alter table winnerdata.ff_batch_leads add column if not exists principal_home_address text;
alter table winnerdata.ff_batch_leads add column if not exists portfolio_property_count integer;
alter table winnerdata.ff_batch_leads add column if not exists portfolio_counties text[];
alter table winnerdata.ff_batch_leads add column if not exists portfolio_assessed_value_total numeric;
alter table winnerdata.ff_batch_leads add column if not exists portfolio_market_value_total numeric;
alter table winnerdata.ff_batch_leads add column if not exists phone text;
alter table winnerdata.ff_batch_leads add column if not exists email text;
alter table winnerdata.ff_batch_leads add column if not exists linkedin_url text;
alter table winnerdata.ff_batch_leads add column if not exists business_website text;
alter table winnerdata.ff_batch_leads add column if not exists phone_validity text;
alter table winnerdata.ff_batch_leads add column if not exists email_deliverability text;
alter table winnerdata.ff_batch_leads add column if not exists contact_provider text;
alter table winnerdata.ff_batch_leads add column if not exists contact_verified_at timestamptz;
alter table winnerdata.ff_batch_leads add column if not exists dnc_state text;
alter table winnerdata.ff_batch_leads add column if not exists evidence_ledger jsonb not null default '{}'::jsonb;
alter table winnerdata.ff_batch_leads add column if not exists freshness_metadata jsonb not null default '{}'::jsonb;
alter table winnerdata.ff_batch_leads add column if not exists unresolved_field_count integer not null default 0;
alter table winnerdata.ff_batch_leads add column if not exists qa_status text not null default 'PARTIAL_ENRICHMENT';

create index if not exists ff_batch_leads_date_idx on winnerdata.ff_batch_leads(batch_date);
create index if not exists ff_batch_leads_pin_idx on winnerdata.ff_batch_leads(pin_clean);

-- Nine mappings confirmed by deterministic normalized lookup against zw_parcels.pin_clean.
insert into winnerdata.ff_parcel_crosswalk (auction_id, auction_parcel_id, pin_clean, match_method, verified_by, notes) values
('6a048e5f-f933-4141-ac22-b3c5dc0a9594','36582-124-000','36582124000','validated_normalization','winnerdata-ai','Removed parcel separators; exact pin_clean match'),
('e506e2f4-0002-4f75-bf30-2fd767901124','16-05-24-005955-119-00','16052400595511900','validated_normalization','winnerdata-ai','Removed parcel separators; exact pin_clean match'),
('7528bd9a-6c00-43ff-957d-049747bf272c','252S312400070001','252S312400070001','validated_normalization','winnerdata-ai','Exact pin_clean match'),
('497c3248-5448-48cc-ae69-5dadee7d3c84','C-04-34-28-110-2070-0320','C04342811020700320','validated_normalization','winnerdata-ai','Removed parcel separators; exact pin_clean match'),
('3e0fb036-5159-45b7-af75-566640f152a2','C-04-34-28-110-1900-0240','C04342811019000240','validated_normalization','winnerdata-ai','Removed parcel separators; exact pin_clean match'),
('5a66b5b5-4f1a-47ee-9dde-9312a3a709ea','C-04-34-28-100-1660-0310','C04342810016600310','validated_normalization','winnerdata-ai','Removed parcel separators; exact pin_clean match'),
('d1f58dab-bc56-4a3e-9e22-9f68bfff5096','C-22-37-30-191-1830-0150','C22373019118300150','validated_normalization','winnerdata-ai','Removed parcel separators; exact pin_clean match'),
('1c821f29-4e4c-4cc8-8ba6-545dffa6b7ec','C-22-37-30-191-1960-0200','C22373019119600200','validated_normalization','winnerdata-ai','Removed parcel separators; exact pin_clean match'),
('68dabeec-2930-414c-9d3f-0bbfa6f798be','C-22-37-30-080-0690-0160','C22373008006900160','validated_normalization','winnerdata-ai','Removed parcel separators; exact pin_clean match')
on conflict (auction_id) do update set auction_parcel_id=excluded.auction_parcel_id, pin_clean=excluded.pin_clean, match_method=excluded.match_method, verified_at=now(), verified_by=excluded.verified_by, notes=excluded.notes;

create or replace function winnerdata.build_ff_portfolio_batch(p_batch_date date default (current_date - 1))
returns jsonb
language plpgsql
security definer
set search_path = public, winnerdata
as $$
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
  insert into winnerdata.ff_batches(batch_date,status,lead_count,updated_at)
  values(p_batch_date,'pending_approval',v_total,now())
  on conflict(batch_date) do update set lead_count=excluded.lead_count,updated_at=now()
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
$$;

revoke all on function winnerdata.build_ff_portfolio_batch(date) from public;
grant execute on function winnerdata.build_ff_portfolio_batch(date) to service_role;

commit;
