-- brevard_case_rekey.sql — Step 1 of Criterion-B strategy (built + applied 2026-06-11)
-- Crosswalk from PropertyOnion-keyed auction rows to real clerk/RealTaxDeed keys.
-- Bridges the two non-overlapping parcel keyspaces:
--   PO side  = spaced-folio  e.g. "26 3625-50-F-21"
--   real side= numeric-acct  e.g. "2800916"
-- via fl_parcels.addr_key (normalized address) as the common denominator.
-- ADDITIVE: new table only. Writes NO outcome data; counts NOTHING toward B.

create table if not exists public.brevard_case_rekey (
  id                bigint generated always as identity primary key,
  sale_type         text not null,
  po_case_number    text not null,
  po_parcel_id      text,
  po_addr_key       text,
  real_case_number  text not null,
  real_keyspace     text not null,          -- clerk_ca | realtaxdeed_numeric
  real_data_source  text,
  match_method      text not null,          -- addr_key_via_flparcels (folio_exact reserved)
  match_confidence  numeric not null,       -- 0..1
  created_at        timestamptz default now(),
  unique (sale_type, po_case_number, real_case_number)
);

-- PATH A: foreclosure address bridge (PO folio -> fl_parcels.addr_key == real street_normalized)
with po as (
  select m.case_number po_case, m.parcel_id po_parcel, p.addr_key
  from public.multi_county_auctions m
  join public.fl_parcels p on p.parcel_id = m.parcel_id
  where m.county ilike 'brevard' and m.sale_type='foreclosure'
    and m.case_number ~ '^PO' and m.parcel_id is not null and p.addr_key is not null),
re as (
  select case_number real_case, data_source,
         upper(regexp_replace(coalesce(street_normalized,''),'[^A-Za-z0-9]','','g')) akey
  from public.multi_county_auctions
  where county ilike 'brevard' and sale_type='foreclosure'
    and case_number !~ '^PO' and street_normalized is not null
    and street_normalized !~* 'unknown' and length(street_normalized)>4)
insert into public.brevard_case_rekey
  (sale_type,po_case_number,po_parcel_id,po_addr_key,real_case_number,real_keyspace,real_data_source,match_method,match_confidence)
select distinct 'foreclosure', po.po_case, po.po_parcel, po.addr_key, re.real_case,
  case when re.real_case ~ '^05-' then 'clerk_ca' else 'realtaxdeed_numeric' end,
  re.data_source, 'addr_key_via_flparcels', 0.80
from po join re on re.akey = upper(regexp_replace(po.addr_key,'[^A-Za-z0-9]','','g'))
on conflict do nothing;

-- PATH B: tax_deed address bridge
with po as (
  select m.case_number po_case, m.parcel_id po_parcel, p.addr_key
  from public.multi_county_auctions m
  join public.fl_parcels p on p.parcel_id = m.parcel_id
  where m.county ilike 'brevard' and m.sale_type='tax_deed'
    and m.case_number ~ '^PO' and m.parcel_id is not null and p.addr_key is not null),
re as (
  select case_number real_case, data_source,
         upper(regexp_replace(coalesce(street_normalized,''),'[^A-Za-z0-9]','','g')) akey
  from public.multi_county_auctions
  where county ilike 'brevard' and sale_type='tax_deed'
    and case_number !~ '^PO' and street_normalized is not null
    and street_normalized !~* 'unknown' and length(street_normalized)>4)
insert into public.brevard_case_rekey
  (sale_type,po_case_number,po_parcel_id,po_addr_key,real_case_number,real_keyspace,real_data_source,match_method,match_confidence)
select distinct 'tax_deed', po.po_case, po.po_parcel, po.addr_key, re.real_case,
  'realtaxdeed_numeric', re.data_source, 'addr_key_via_flparcels', 0.80
from po join re on re.akey = upper(regexp_replace(po.addr_key,'[^A-Za-z0-9]','','g'))
on conflict do nothing;
