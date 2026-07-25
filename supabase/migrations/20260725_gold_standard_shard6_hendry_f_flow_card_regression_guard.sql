-- Gold Standard shard-6 hendry (dispatch 2ccb180a, loop run 6354,
-- 2026-07-25T08:00Z session): F durable root-cause fix.
--
-- PRIOR ATTEMPTS (2 sessions, migration 20260724_gold_standard_shard11_
-- hendry_f_status_sync_i_zone_correction.sql): both applied a one-time
-- per-row UPDATE + re-ran promote_tier1_from_outcomes() for case 25-100.
-- Both reverted within minutes -- documented as "genuinely BLOCKED, not a
-- bug in our pipeline" because the county's own calendar page still lists
-- the case as upcoming for a later date while a separate results-report
-- page shows it already sold. That diagnosis stopped one function short of
-- the actual root cause.
--
-- ROOT CAUSE (VERIFIED live this session, not assumed):
--   pipeline.tier1_card_raw id=20600 (hendry, case_number_text='25-100',
--   scraped_at=2026-07-25T05:47:10Z) carries auction_status_canon='LISTED',
--   sold_amount_num=NULL, auction_date=2026-07-30 -- the stale calendar
--   card described in the prior migration's notes.
--   biddeed.flow_card_to_mca(p_card_id), invoked by
--   public.promote_upcoming_tier1_cards() (cron, runs for auction_date >=
--   current_date -- 2026-07-30 qualifies), applies THIS card to
--   multi_county_auctions UNCONDITIONALLY on every run:
--     tier1_sale_status=c.auction_status_canon, tier1_sold_amount=c.sold_amount_num,
--     auction_status=coalesce(v_mca_status,auction_status), auction_date=coalesce(c.auction_date,auction_date)
--   -- i.e. every re-scrape of the stale calendar page nulls
--   tier1_sold_amount right back out over the genuine, independently-
--   verified $7,100 sale (tax_deed_outcomes: data_source=
--   'tier1:realtaxdeed_results_report:hendry', outcome='sold',
--   auction_date=2026-07-16 -- a REAL results-report page, not
--   fabricated). Confirmed live before this fix: multi_county_auctions
--   row for 25-100 had sold_amount=7100.00 (from outcomes, a column
--   flow_card_to_mca never touches) but tier1_sold_amount=NULL,
--   tier1_sale_status='LISTED', auction_status='upcoming',
--   auction_date='2026-07-30' -- exactly the flap signature.
--
-- FIX (durable, fleet-wide, shared-code -- biddeed.flow_card_to_mca is the
-- single choke point every RealAuction/RealTaxDeed county scraper funnels
-- through via promote_upcoming_tier1_cards): when updating an EXISTING
-- multi_county_auctions row, if that row already carries a non-null
-- sold_amount (i.e. an independent outcome already verified it sold) AND
-- the incoming card is non-terminal (auction_status_canon maps to
-- 'upcoming') with no sold_amount_num of its own, skip overwriting the
-- tier1_sale_status / tier1_sold_amount / auction_status / auction_date
-- fields -- only the coalesce-safe descriptive fields (address, opening
-- bid, assessed value) still refresh. This is the same class of fix
-- already validated and shipped for calendar_sweep_mca.py (terminal-state
-- skip) -- applied here at the actual root-cause function instead of one
-- of its many callers. Never blocks a genuine new SOLD detection (that
-- path is untouched); only prevents a lower-authority "still listed" card
-- from regressing an already-verified sale.
--
-- Applied live via Supabase Management API SQL execution this session (no
-- direct psql/pooler auth available from this runner, consistent with
-- prior sessions' notes) -- recorded here per the established convention
-- in this migrations directory.

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
    if v_existing_sold_amount is not null and v_mca_status = 'upcoming' and c.sold_amount_num is null then
      -- Regression guard (2026-07-25, hendry F root cause): a lower-authority
      -- "still listed" card must never null out an already-verified sale.
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

-- One-time recovery: promote_tier1_from_outcomes() is safe/idempotent and
-- only sets tier1_sold_amount from an already-present, non-propertyonion,
-- non-promote-tagged outcome row where sold_amount is already set. This
-- repairs the current NULL left by the last flow_card_to_mca overwrite;
-- the guard above prevents it from being nulled out again.
SELECT public.promote_tier1_from_outcomes();
