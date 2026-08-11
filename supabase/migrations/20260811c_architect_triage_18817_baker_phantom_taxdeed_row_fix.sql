-- Architect triage #18817 (dispatch 14cbae1a, baker gold-standard cert blocked)
--
-- ROOT CAUSE (VERIFIED via pg_get_functiondef + live data, 2026-08-11):
-- biddeed.flow_card_to_mca() derives sale_type purely from source_platform
-- ('realtaxdeed' -> tax_deed) whenever the case_number isn't in the unambiguous
-- '^[0-9]{4}TD[0-9]+$' tax-deed-docket format. Baker's realtaxdeed.com feed
-- re-lists the SAME court case numbers (standard FL '..CAAXMX' foreclosure
-- format) that already exist in multi_county_auctions as sale_type='foreclosure'.
-- Because the match queries in flow_card_to_mca filter on sale_type=v_sale_type,
-- neither match branch finds the existing foreclosure row, so a phantom
-- sale_type='tax_deed' sibling row is INSERTed with mostly-NULL scraped fields.
-- This happened twice for baker within one day (022025CA000148CAAXMX at
-- 2026-08-11T16:30Z, 022025CA000002CAAXMX at 2026-08-11T21:01Z), inflating
-- auctions_total and permanently capping C/D/E/I/J below their true value on
-- every gold-standard evaluation — the exact effect that made the prior
-- session's genuine C/D/E/I fixes (63.6->80.0) regress back down once the
-- next phantom row landed. Confirmed via FK check: zero references to either
-- phantom row across auction_enrichment_queue/auction_schedule_history/
-- court_case_metadata/po_mca_matches/shapira_outcome_scorecard.
--
-- FIX: once a (county, case_number) pair has an existing row, its sale_type
-- wins over any later platform-derived guess -- mirrors the existing
-- TD-docket-format precedent ("case_number format/identity is authoritative
-- over source_platform tag") already established in this function's 2026-07-30
-- okeechobee fix, just applied in the other direction.

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
  v_existing_sale_type text;
  v_action text := 'noop';
  v_pid text;
begin
  select * into c from pipeline.tier1_card_raw where id = p_card_id;
  if not found or c.case_number_text is null or c.auction_date is null then return 'skip_no_case'; end if;

  -- Real parcel IDs always contain a digit; a link-label placeholder (e.g. "Property
  -- Appraiser") never does. Treat non-digit text as no parcel data, not as a value.
  v_pid := CASE WHEN c.parcel_id_text ~ '[0-9]' THEN c.parcel_id_text ELSE NULL END;

  -- Case-number identity wins over platform tag: if this exact (county, case_number)
  -- already has a row, reuse its sale_type so a re-list on a different domain
  -- (e.g. baker.realtaxdeed.com re-listing a court foreclosure case) reconciles
  -- into the same row instead of spawning a mostly-NULL phantom sibling.
  select sale_type into v_existing_sale_type from public.multi_county_auctions
   where lower(county)=lower(c.county_slug) and case_number=c.case_number_text limit 1;

  -- FL clerk "<year>TD<digits>" is an unambiguous statewide Tax Deed docket number,
  -- authoritative regardless of source_platform (2026-07-30, okeechobee C/D root
  -- cause: a combined foreclosure+tax-deed calendar tags everything with one platform).
  v_sale_type := case
    when v_existing_sale_type is not null then v_existing_sale_type
    when c.case_number_text ~ '^[0-9]{4}TD[0-9]+$' then 'tax_deed'
    when c.source_platform = 'realtaxdeed' then 'tax_deed'
    else 'foreclosure'
  end;
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

-- Data correction: purge the two known phantom tax_deed sibling rows for baker
-- that this bug already produced. FK-safety verified live: zero references in
-- auction_enrichment_queue, auction_schedule_history, court_case_metadata,
-- po_mca_matches, shapira_outcome_scorecard for either id.
DELETE FROM public.multi_county_auctions
WHERE id IN (
  '673fc02f-a336-4eea-a2c4-2b201866ea51', -- case 022025CA000148CAAXMX phantom tax_deed dup
  '769c36d5-e055-4642-b0e5-820acf13c5b6'  -- case 022025CA000002CAAXMX phantom tax_deed dup
);
