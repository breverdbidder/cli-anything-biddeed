-- Issue #19434: Winner Data seller FF template consolidation on Template B.
--
-- Requirement 2 verification finding: summitleads.v_producer_intake (which
-- ff_get_lead's verification subquery reads `county` from, to resolve
-- appraiser_url) only ever produces a row for a lead via two paths, both
-- auction-shaped:
--   direct_mca   -- lead.parcel_id matches a multi_county_auctions row
--   via_profile  -- lead.parcel_id is null, name-matched to an auction buyer
-- An MLS-sourced seller lead (active/pending listing, never auctioned) has
-- a parcel_id but will never appear in multi_county_auctions, so it falls
-- through both CTEs and gets ZERO rows in this view. ff_get_lead's
-- `left join v_producer_intake v` then leaves v.county null, so the
-- verification subquery's county_ctx.slug is null, cfg/fc joins are null,
-- and appraiser_url is null -- confirmed live-verified 2026-08-24 (this
-- session) for both of #19392's two seller pilot leads (Labelle/Latulip),
-- neither of which produced any v_producer_intake row.
--
-- Fix (additive-only, per CC_META_PROMPT 3.4): a third CTE, via_parcel_only,
-- for leads that have a parcel_id but no multi_county_auctions match.
-- Resolves county via fl_parcels.co_no -> fl_counties.co_no -> slug, which
-- is source-independent of auction data. auction/sale fields are left null
-- (honest -- there is no sale to report for an MLS-sourced lead) rather than
-- fabricated. direct_mca and via_profile are untouched, so the 22
-- historical/production auction-track leads are unaffected -- their rows
-- still come from those two branches exactly as before.
--
-- Residual, honestly reported (not fixed here, out of scope): the VERIFIED
-- badge itself (not the link) still can never be true for an MLS-sourced
-- lead, because public.parity_audit -- the only source of a 'pass' verdict
-- -- is keyed by case_number, and MLS-sourced leads have no court case.
-- That is a real ceiling of the current cross-verification design, not a
-- bug this migration can fix without inventing a new MLS-specific audit
-- source (a real future project, not implied by this issue).

create or replace view summitleads.v_producer_intake as
with direct_mca as (
  select distinct on (l.lead_id)
    l.lead_id, l.entity_name, l.contact_name, l.contact_phone, l.contact_email,
    l.parcel_id, mca.property_address, mca.county, mca.sale_type, mca.auction_date,
    mca.sold_amount::numeric(14,2) as sold_amount, mca.case_number
  from summitleads.leads l
  join multi_county_auctions mca on mca.parcel_id = l.parcel_id
  where l.parcel_id is not null
  order by l.lead_id, (mca.sold_amount is not null) desc, mca.auction_date desc
), via_profile as (
  select distinct on (l.lead_id)
    l.lead_id, l.entity_name, l.contact_name, l.contact_phone, l.contact_email,
    l.parcel_id, s.property_address, s.county, s.sale_type, s.auction_date,
    s.sold_amount, s.case_number
  from summitleads.leads l
  join auction_buyer_profiles bp
    on regexp_replace(lower(bp.buyer_name_normalized), '[^a-z0-9 ]', '', 'g')
     = regexp_replace(lower(l.entity_name), '[^a-z0-9 ]', '', 'g')
  join auction_buyer_sightings s on s.buyer_profile_id = bp.id
  where l.parcel_id is null
  order by l.lead_id, s.auction_date desc
), via_parcel_only as (
  select distinct on (l.lead_id)
    l.lead_id, l.entity_name, l.contact_name, l.contact_phone, l.contact_email,
    l.parcel_id,
    null::text as property_address,
    fc.slug as county,
    null::text as sale_type,
    null::date as auction_date,
    null::numeric(14,2) as sold_amount,
    null::text as case_number
  from summitleads.leads l
  join fl_parcels fp on fp.parcel_id = l.parcel_id
  left join fl_counties fc on fc.co_no = fp.co_no
  where l.parcel_id is not null
    and not exists (select 1 from multi_county_auctions mca where mca.parcel_id = l.parcel_id)
), base as (
  select * from direct_mca
  union all
  select * from via_profile
  union all
  select * from via_parcel_only
)
select
  base.lead_id, base.entity_name, base.contact_name, base.contact_phone, base.contact_email,
  base.property_address, base.county, base.sale_type, base.auction_date, base.sold_amount, base.case_number,
  fp.parcel_id as appraiser_parcel, fp.act_yr_blt, fp.eff_yr_blt, fp.tot_lvg_ar, fp.no_buldng,
  fp.const_clas, fp.imp_qual, fp.jv as just_value, fp.lnd_val, fp.dor_uc, fp.zone_code,
  fp.own_addr1 as buyer_mailing_addr, fp.phy_city as property_city
from base
left join fl_parcels fp on fp.parcel_id = base.parcel_id;
