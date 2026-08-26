-- SummitLeads: re-point the lender/plaintiff guard at tier1_buyer_type.
--
-- Defect (flagged on issue #19490 during the 2026-08-25 winner-name harvest):
-- summitleads.tag_lender_or_plaintiff() (20260826_summitleads_lender_plaintiff_guard.sql)
-- keys entirely off a regex on entity_name. That is a proxy, not the source
-- of truth -- the RealAuction portal's own "Sold To" field (persisted as
-- multi_county_auctions.tier1_buyer_type by scripts/realauction_winner_harvest.py)
-- is authoritative. The regex both over- and under-fires: on the 2026-08-24
-- batch four *plaintiff* wins (74th Court Holding, Romeo Echo, Conkreta
-- Financial, WFK & Associates) reached Mariam's call sheet because their
-- entity names matched no lender/bank pattern, while an entity_name
-- containing "trust" can be a legitimate individual buyer (custodial IRA)
-- wrongly flagged. This migration makes tier1_buyer_type authoritative in
-- both directions when it is known, and demotes the entity_name regex to a
-- secondary, explicitly-labeled fallback used only while an auction's
-- tier1_buyer_type has not yet been harvested.

create or replace function summitleads.tag_lender_or_plaintiff()
returns trigger
language plpgsql
as $$
declare
  v_tier1_buyer_type text;
begin
  select mca.tier1_buyer_type
    into v_tier1_buyer_type
  from summitleads.signal_events se
  join public.multi_county_auctions mca on mca.id::text = se.event_payload ->> 'auction_id'
  where se.signal_id = new.signal_id;

  if v_tier1_buyer_type = 'plaintiff' then
    -- Authoritative: the auction portal's Sold To field says plaintiff/lender
    -- took the property back via credit bid, regardless of what the name looks like.
    new.is_lender_or_plaintiff := true;
    new.consent_certificate := coalesce(new.consent_certificate, '{}'::jsonb) ||
      jsonb_build_object('compliance_flag', 'LENDER_TOOK_BACK_PROPERTY_NOT_BUYER_LEAD',
                          'compliance_source', 'tier1_buyer_type');
  elsif v_tier1_buyer_type = 'third_party' then
    -- Authoritative: the portal confirms a genuine third-party buyer.
    -- Never let the name regex override this, even if the name matches
    -- (e.g. a legitimate buyer entity with "trust" in its name).
    new.is_lender_or_plaintiff := false;
  elsif new.entity_name ~* '(mortgage|bank|n\.a\.|national association|savings fund|loan servicing|trust\y|fannie mae|freddie mac|\yhud\y|department of housing|association)' then
    -- tier1_buyer_type not yet harvested for this auction. Fall back to the
    -- name-pattern heuristic so a pre-harvest lead can't slip through
    -- unflagged, but mark it as an unconfirmed secondary signal, not the
    -- authoritative compliance flag.
    new.is_lender_or_plaintiff := true;
    new.consent_certificate := coalesce(new.consent_certificate, '{}'::jsonb) ||
      jsonb_build_object('compliance_flag', 'LENDER_TOOK_BACK_PROPERTY_NOT_BUYER_LEAD_UNCONFIRMED',
                          'compliance_source', 'entity_name_regex_fallback');
  end if;
  return new;
end;
$$;

-- Retroactive correction for existing rows, both directions:

-- 1. Flag leads whose auction is authoritatively plaintiff but weren't
--    caught by the old regex-only trigger.
update summitleads.leads l
set is_lender_or_plaintiff = true,
    consent_certificate = coalesce(l.consent_certificate, '{}'::jsonb) ||
      jsonb_build_object('compliance_flag', 'LENDER_TOOK_BACK_PROPERTY_NOT_BUYER_LEAD',
                          'compliance_source', 'tier1_buyer_type')
from summitleads.signal_events se
join public.multi_county_auctions mca on mca.id::text = se.event_payload ->> 'auction_id'
where se.signal_id = l.signal_id
  and mca.tier1_buyer_type = 'plaintiff'
  and l.is_lender_or_plaintiff = false;

-- 2. Unflag leads whose auction is authoritatively third_party but were
--    incorrectly flagged by the old regex (name false positive).
update summitleads.leads l
set is_lender_or_plaintiff = false
from summitleads.signal_events se
join public.multi_county_auctions mca on mca.id::text = se.event_payload ->> 'auction_id'
where se.signal_id = l.signal_id
  and mca.tier1_buyer_type = 'third_party'
  and l.is_lender_or_plaintiff = true;
