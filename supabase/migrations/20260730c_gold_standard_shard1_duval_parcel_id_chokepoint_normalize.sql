-- Gold Standard shard-1 duval/madison (dispatch 32b4833c, 3rd firing, chat_session
-- architect-20260730T160000) -- durable fix for the recurring duval I regression.
--
-- ROOT CAUSE (diagnosed by the 2nd firing on this dispatch, re-confirmed live this
-- firing): pg_cron job `gold-calendar-parity-cycle` (jobid 204, ~every 40min per
-- date) re-scrapes every upcoming duval auction. RealAuction serves Duval parcel_id
-- in dash format ("020031-1690"); v_zoning_gold_standard_card uses space format
-- ("020031 1690") for the same real parcel. Every re-scrape writes through
-- biddeed.flow_card_to_mca(), which previously did `parcel_id=coalesce(v_pid,parcel_id)`
-- with no format normalization -- silently reverting any offline fix within ~40min
-- for the ~19 rows that are "upcoming" at any time. Two prior firings on this
-- dispatch each independently re-diagnosed and mitigated this via an OFFLINE
-- re-normalization script (scripts/gold_standard_shard1_duval_madison_run7519_duval_i_fix.py,
-- v2, collision-safe) -- this migration is the source-level fix so the mitigation
-- script stops being necessary.
--
-- NOT YET APPLIED LIVE this firing: Supabase Management API returns Cloudflare
-- WAF block (HTTP 403, code 1010) and direct psql auth fails (SASL) from this
-- sandbox -- same infra blocker flagged by both prior firings on this dispatch.
-- PostgREST has no DDL execution surface, so this DDL change could not be pushed
-- live this session; only the data-level mitigation (re-running the equivalent
-- normalization via REST PATCH calls) was applied live. Whoever has working
-- `supabase db push` / psql access should apply this migration, then the
-- mitigation script becomes a no-op safety net rather than a required re-run.
--
-- SCOPE: additive only, gated on `c.county_slug = 'duval'` and a strict
-- "digits-dash-digits, no space" pattern match -- zero behavior change for any
-- other of the 67 realauction counties. Collision-safe: mirrors the offline v2
-- script's guard exactly (only normalizes when the digit-key has exactly one
-- distinct real spelling in the zoning card with zone_code set); Duval has ~30
-- known digit-keys where dash-form and space-form resolve to genuinely different
-- zone_code values (mostly generic 'PUD' vs a specific 'PUD-LDR'/'PUD-MDR'/etc.
-- subcategory -- confirmed live 2026-07-30, left untouched by design, never guessed).

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

  -- Duval RE-number format normalization (2026-07-30, shard-1 dispatch 32b4833c,
  -- durable version of the offline parcel_id-format sweep -- see comment above).
  -- Collision-safe: only rewrites when exactly one real space-format spelling
  -- exists for the digit-key in the zoning card; ambiguous digit-keys (genuinely
  -- different real parcels/zones) are left as scraped, never guessed at.
  if c.county_slug = 'duval' and v_pid ~ '^[0-9]+-[0-9]+$' then
    v_pid := coalesce((
      select min(zc.parcel_id)
      from v_zoning_gold_standard_card zc
      where lower(zc.county) = norm_county_key('duval')
        and zc.zone_code is not null
        and regexp_replace(zc.parcel_id,'[^0-9]','','g') = regexp_replace(v_pid,'[^0-9]','','g')
      having count(distinct zc.parcel_id) = 1
    ), v_pid);
  end if;

  -- FL clerk "<year>TD<digits>" is an unambiguous statewide Tax Deed docket number,
  -- authoritative regardless of source_platform (2026-07-30, okeechobee C/D root
  -- cause: a combined foreclosure+tax-deed calendar tags everything with one platform).
  v_sale_type := case
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
