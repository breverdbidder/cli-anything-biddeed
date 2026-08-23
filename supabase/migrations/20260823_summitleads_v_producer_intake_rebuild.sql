-- SummitLeads Sprint 7: rebuild v_producer_intake
--
-- Root cause (live-diagnosed 2026-08-23): the prior view mandated an INNER JOIN
-- through auction_buyer_sightings to get property/sale data. auction_buyer_profiles
-- covers ~more counties (including brevard) than auction_buyer_sightings (19
-- counties, no brevard) -- any buyer profile without a matching sighting row
-- produced zero rows for that lead, regardless of county.
--
-- The buyer-name match was also a substring LIKE ('%' || second_word || '%')
-- against 794 profiles, which both (a) false-positive-matches unrelated buyers
-- sharing a common word (PROPERTIES, INVESTMENTS, HOLDINGS, TRUST...) and
-- (b) fans out into a LATERAL ILIKE-prefix scan of fl_parcels (10.5M rows, no
-- functional/trigram-compatible index for this predicate) per matched row --
-- this is what caused live CREATE-time/SELECT-time queries against the view
-- to hang indefinitely (verified: 3 sessions stuck 7-12+ minutes in
-- pg_stat_activity against this exact view before being terminated).
--
-- Fix: two-path UNION.
--   1. direct_mca -- leads already carry BidDeed's own parcel_id (set at
--      Sprint 2 lead creation). Join straight to multi_county_auctions on
--      parcel_id (indexed equality) -- no sightings dependency, works for any
--      county including brevard the moment brevard leads exist.
--   2. via_profile -- fallback for leads with no parcel_id (e.g. the manual
--      chat-delivered batch), matched via exact buyer_name_normalized equality
--      (not substring LIKE) against auction_buyer_profiles + a sightings row.
-- fl_parcels enrichment is joined once at the end on exact parcel_id equality
-- (indexed) instead of a per-row ILIKE LATERAL scan. via_profile leads with no
-- resolvable parcel_id get honest nulls for construction fields rather than a
-- fuzzy address guess -- this matches what Sprint 3's quote_drafts already do
-- for the same leads (parcel_id required there too).
--
-- Verified live: 0 dependent views/functions (checked pg_depend before drop).
-- Before: query timeout (no result within 12+ min in 3 separate sessions).
-- After: 22 distinct leads resolved in 0.49s (37 total leads; 15 unresolved
-- because they have no parcel_id AND no matching buyer_name_normalized profile
-- -- an honest coverage gap, not a bug, tracked as a residual finding).

drop view if exists summitleads.v_producer_intake;

create view summitleads.v_producer_intake as
with direct_mca as (
  select distinct on (l.lead_id)
    l.lead_id, l.entity_name, l.contact_name, l.contact_phone, l.contact_email, l.parcel_id,
    mca.property_address, mca.county, mca.sale_type, mca.auction_date,
    mca.sold_amount::numeric(14,2) as sold_amount, mca.case_number
  from summitleads.leads l
  join public.multi_county_auctions mca on mca.parcel_id = l.parcel_id
  where l.parcel_id is not null
  order by l.lead_id, (mca.sold_amount is not null) desc, mca.auction_date desc
),
via_profile as (
  select distinct on (l.lead_id)
    l.lead_id, l.entity_name, l.contact_name, l.contact_phone, l.contact_email, l.parcel_id,
    s.property_address, s.county, s.sale_type, s.auction_date, s.sold_amount, s.case_number
  from summitleads.leads l
  join auction_buyer_profiles bp
    on regexp_replace(lower(bp.buyer_name_normalized), '[^a-z0-9 ]', '', 'g')
     = regexp_replace(lower(l.entity_name), '[^a-z0-9 ]', '', 'g')
  join auction_buyer_sightings s on s.buyer_profile_id = bp.id
  where l.parcel_id is null
  order by l.lead_id, s.auction_date desc
),
base as (
  select * from direct_mca
  union all
  select * from via_profile
)
select
  base.lead_id, base.entity_name, base.contact_name, base.contact_phone, base.contact_email,
  base.property_address, base.county, base.sale_type, base.auction_date, base.sold_amount, base.case_number,
  fp.parcel_id as appraiser_parcel, fp.act_yr_blt, fp.eff_yr_blt, fp.tot_lvg_ar, fp.no_buldng,
  fp.const_clas, fp.imp_qual, fp.jv as just_value, fp.lnd_val, fp.dor_uc, fp.zone_code,
  fp.own_addr1 as buyer_mailing_addr, fp.phy_city as property_city
from base
left join public.fl_parcels fp on fp.parcel_id = base.parcel_id;
