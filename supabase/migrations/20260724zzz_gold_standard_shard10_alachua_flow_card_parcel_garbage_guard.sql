-- Root cause of the alachua E/I/J "ghost placeholder regeneration" mystery
-- (flagged unresolved by two prior firings of dispatch a36233a1): the RealAuction
-- multi-county scraper (.github/scripts/scrape_realauction_county.py) captured the
-- "Property Appraiser" site-nav link's anchor text as parcel_id_text when a county
-- listing has no linked parcel. That garbage lands in pipeline.tier1_card_raw via
-- biddeed.tier1_card_upsert, and every 5 minutes the gold-calendar-parity-cycle
-- pg_cron job (-> promote_upcoming_tier1_cards -> biddeed.flow_card_to_mca)
-- unconditionally overwrites multi_county_auctions.parcel_id with it via
-- coalesce(c.parcel_id_text, parcel_id) -- clobbering real, previously-fixed data.
--
-- The scraper itself is fixed separately (source no longer emits non-digit
-- parcel_id_text). This migration adds a defense-in-depth guard in
-- flow_card_to_mca so any garbage already in pipeline.tier1_card_raw (this county
-- or others) can never again overwrite a real parcel_id -- a non-digit
-- parcel_id_text is treated as absent, same contract as a NULL.

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
  select id into v_existing_id from public.multi_county_auctions
   where lower(county)=lower(c.county_slug) and case_number=c.case_number_text and sale_type=v_sale_type limit 1;

  -- 2) FALLBACK: reconcile to an existing row (often PO-seeded) by parcel_id + date,
  --    since PO case_numbers differ from RealAuction case_numbers
  if v_existing_id is null and v_pid is not null then
    select id into v_existing_id from public.multi_county_auctions
     where lower(county)=lower(c.county_slug) and parcel_id=v_pid
       and auction_date=c.auction_date and sale_type=v_sale_type limit 1;
  end if;

  if v_existing_id is not null then
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

-- Clean the 6 already-poisoned alachua tier1_card_raw rows so the cron's next tick
-- can't re-clobber multi_county_auctions even before this guard existed. Scoped to
-- alachua only (this session's shard) -- other counties' identical rows are a known
-- fleet-wide instance of the same bug, flagged for their owning shards, not touched here.
UPDATE pipeline.tier1_card_raw
   SET parcel_id_text = NULL
 WHERE county_slug = 'alachua'
   AND parcel_id_text IS NOT NULL
   AND parcel_id_text !~ '[0-9]';
