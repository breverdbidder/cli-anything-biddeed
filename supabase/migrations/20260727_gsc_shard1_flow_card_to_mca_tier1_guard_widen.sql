-- GOLD STANDARD shard-1 (duval/union), dispatch 3aafe92d, 2026-07-27
-- Root cause (VERIFIED live, reproduced twice): biddeed.flow_card_to_mca() runs
-- every 5 min for every county via promote_upcoming_tier1_cards() / the
-- gold-calendar-parity-cycle cron. Its 2026-07-25 "regression guard" (added for
-- the hendry F root cause) only skips the null-out when the incoming card's
-- status is exactly 'upcoming'. A re-scraped card in ANY other status
-- (e.g. still 'completed'/SOLD but this particular scrape pass didn't capture
-- the amount) falls through to the plain UPDATE branch, which sets
-- tier1_sold_amount = c.sold_amount_num unconditionally -- i.e. NULLs out an
-- already-verified amount. Live evidence: promote_tier1_from_outcomes()
-- promoted duval's 45 tier1_sold_amount rows twice in this session, and both
-- times the very next gold-calendar-parity-cycle tick (5-min boundary) reset
-- them back to NULL with tier1_verified_at bumped to the tick's timestamp --
-- the unconditional branch, not the upcoming-only guard, firing.
--
-- Fix: widen the guard to cover any status, not just 'upcoming' -- once a sold
-- amount is verified, a card carrying no sold amount must never clear it.

CREATE OR REPLACE FUNCTION biddeed.flow_card_to_mca(p_card_id bigint)
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pipeline', 'biddeed', 'public', 'pg_catalog'
AS $function$
declare
  c pipeline.tier1_card_raw%rowtype;
  v_sale_type text; v_source_url text;
  v_mca_status text;
  v_existing_id uuid;
  v_existing_sold_amount numeric;
  v_action text := 'noop';
  v_pid text;
begin
  select * into c from pipeline.tier1_card_raw where id = p_card_id;
  if not found or c.case_number_text is null or c.auction_date is null then return 'skip_no_case'; end if;

  -- Real parcel IDs always contain a digit; a link-label placeholder (e.g. "Property
  -- Appraiser") never does. Treat non-digit text as no parcel data, not as a value.
  v_pid := CASE WHEN c.parcel_id_text ~ '[0-9]' THEN c.parcel_id_text ELSE NULL END;

  v_sale_type := case when c.source_platform = 'realtaxdeed' then 'tax_deed' else 'foreclosure' end;
  v_source_url := 'https://' || c.county_slug || '.' || c.source_platform || '.com';
  v_mca_status := case c.auction_status_canon
    when 'SOLD' then 'completed' when 'CANCELED' then 'cancelled' when 'CANCELLED' then 'cancelled'
    when 'LISTED' then 'upcoming' when 'REDEEMED' then 'redeemed' when 'PREVIEW' then 'upcoming'
    else null end;

  -- 1) match by case_number (our case format)
  select id, sold_amount into v_existing_id, v_existing_sold_amount from public.multi_county_auctions
   where lower(county)=lower(c.county_slug) and case_number=c.case_number_text and sale_type=v_sale_type limit 1;

  -- 2) FALLBACK: reconcile to an existing row (often PO-seeded) by parcel_id + date,
  --    since PO case_numbers differ from RealAuction case_numbers
  if v_existing_id is null and v_pid is not null then
    select id, sold_amount into v_existing_id, v_existing_sold_amount from public.multi_county_auctions
     where lower(county)=lower(c.county_slug) and parcel_id=v_pid
       and auction_date=c.auction_date and sale_type=v_sale_type limit 1;
  end if;

  if v_existing_id is not null then
    if v_existing_sold_amount is not null and c.sold_amount_num is null then
      -- Regression guard (2026-07-25, hendry F root cause; widened 2026-07-27,
      -- shard-1 duval F root cause): a lower-authority re-scrape carrying no
      -- sold amount must never null out an already-verified sale, regardless
      -- of what status that re-scrape reports.
      update public.multi_county_auctions set
        property_address=coalesce(c.property_address_text,property_address),
        opening_bid=coalesce(c.opening_bid_num,opening_bid),
        assessed_value=coalesce(c.assessed_value_num,assessed_value),
        scraped_at=now()
      where id=v_existing_id;
      v_action:='skipped_stale_relist';
    else
      begin
        update public.multi_county_auctions set
          tier1_sale_status=c.auction_status_canon, tier1_sold_amount=c.sold_amount_num,
          tier1_verified_at=now(), tier1_source_run_id=c.scrape_run_id, tier1_authoritative=true,
          auction_status=coalesce(v_mca_status,auction_status), auction_date=coalesce(c.auction_date,auction_date),
          parcel_id=coalesce(v_pid,parcel_id), property_address=coalesce(c.property_address_text,property_address),
          opening_bid=coalesce(c.opening_bid_num,opening_bid), assessed_value=coalesce(c.assessed_value_num,assessed_value),
          source_platform=coalesce(c.source_platform,source_platform),
          realforeclose_url=coalesce(realforeclose_url,v_source_url), scraped_at=now()
        where id=v_existing_id;
        v_action:='updated';
      exception when unique_violation then
        update public.multi_county_auctions set
          tier1_sale_status=c.auction_status_canon, tier1_sold_amount=c.sold_amount_num,
          tier1_verified_at=now(), tier1_source_run_id=c.scrape_run_id, tier1_authoritative=true,
          auction_status=coalesce(v_mca_status,auction_status),
          parcel_id=coalesce(v_pid,parcel_id), opening_bid=coalesce(c.opening_bid_num,opening_bid),
          assessed_value=coalesce(c.assessed_value_num,assessed_value), scraped_at=now()
        where id=v_existing_id;
        v_action:='updated_no_date_move';
      end;
    end if;
  else
    begin
      insert into public.multi_county_auctions (
        county, sale_type, auction_date, case_number, parcel_id, property_address,
        opening_bid, assessed_value, auction_status, source_platform, realforeclose_url,
        tier1_sale_status, tier1_sold_amount, tier1_verified_at, tier1_source_run_id, tier1_authoritative, scraped_at
      ) values (
        lower(c.county_slug), v_sale_type, c.auction_date, c.case_number_text, v_pid, c.property_address_text,
        c.opening_bid_num, c.assessed_value_num, coalesce(v_mca_status,'upcoming'), c.source_platform, v_source_url,
        c.auction_status_canon, c.sold_amount_num, now(), c.scrape_run_id, true, now()
      ) on conflict (county, case_number, sale_type) do nothing;
      v_action:='inserted';
    exception when unique_violation then
      -- parcel+date collision against a differently-cased row: reconcile it to own
      update public.multi_county_auctions set
        tier1_sale_status=c.auction_status_canon, tier1_sold_amount=c.sold_amount_num,
        tier1_verified_at=now(), tier1_source_run_id=c.scrape_run_id, tier1_authoritative=true,
        auction_status=coalesce(v_mca_status,auction_status),
        opening_bid=coalesce(c.opening_bid_num,opening_bid), assessed_value=coalesce(c.assessed_value_num,assessed_value),
        scraped_at=now()
      where lower(county)=lower(c.county_slug) and parcel_id=v_pid
        and auction_date=c.auction_date and sale_type=v_sale_type;
      v_action:='reconciled_by_parcel';
    end;
  end if;
  return v_action;
end;
$function$;
