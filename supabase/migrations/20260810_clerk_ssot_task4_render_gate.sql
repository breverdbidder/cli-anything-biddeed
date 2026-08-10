-- CLERK-SSOT Task 4.2/4.3 — fail-closed render gate + parity badge.
--
-- Before this migration, fire_daily_upcoming_lots_digest() had zero references
-- to clerk_parity_results/parity_status/auction_status != 'CANCELLED' -- a
-- clerk-confirmed-cancelled lot could still render in the digest and on
-- property cards. This adds:
--   1. public.v_property_card_verified -- gate view: auction_status <>
--      'CANCELLED' AND parity_status IN ('CLERK_VERIFIED','PARITY_OK') AND a
--      fresh (<48h) PARITY-status clerk_parity_results row for that
--      county/sale_type. Also carries match_pct/checked_at for the badge.
--   2. fire_daily_upcoming_lots_digest() rebuilt to only emit lots that pass
--      the same gate, and to log fail-closed suppressions to public.insights
--      (anomaly_type='clerk_parity') per county when it drops rows.
--
-- Companion fix (scripts/clerk_ssot/run_parity.py, same session): previously
-- only newly-reconciled rows got parity_status set (CLERK_VERIFIED /
-- CLERK_SSOT_CANCELLED) -- an already-matching row stayed parity_status=NULL
-- forever, which meant this gate would have suppressed everything. The
-- runner now also marks clean per-sweep matches PARITY_OK.

CREATE OR REPLACE VIEW public.v_property_card_verified AS
SELECT
  mca.*,
  cpr.match_pct   AS clerk_parity_match_pct,
  cpr.checked_at  AS clerk_parity_checked_at
FROM public.multi_county_auctions mca
JOIN LATERAL (
  SELECT cpr2.match_pct, cpr2.checked_at
  FROM public.clerk_parity_results cpr2
  WHERE cpr2.county_slug = lower(mca.county)
    AND cpr2.sale_type = mca.sale_type
    AND cpr2.status = 'PARITY'
    AND cpr2.checked_at > now() - interval '48 hours'
  ORDER BY cpr2.checked_at DESC
  LIMIT 1
) cpr ON true
WHERE mca.auction_status <> 'CANCELLED'
  AND mca.parity_status IN ('CLERK_VERIFIED','PARITY_OK');

GRANT SELECT ON public.v_property_card_verified TO anon, authenticated, service_role;

CREATE OR REPLACE FUNCTION public.fire_daily_upcoming_lots_digest(p_dry_run boolean DEFAULT false)
 RETURNS TABLE(notifications_enqueued integer, total_hot_lots integer, body_preview text)
 LANGUAGE plpgsql
AS $function$
declare
  v_c record;
  v_route record;
  v_section text; v_cnt integer;
  v_body text := ''; v_subject text;
  v_total integer := 0; v_enq integer := 0;
  v_subj_counts text := '';
  v_suppressed_cnt integer;
  v_suppressed_cases text[];
begin
  for v_c in
    select c.slug,
           (c.co_no + 10)::integer as fdor_co_no,
           coalesce(g.gold_standard,false) as is_gold
    from public.fl_counties c
    left join public.gold_standard_scoreboard g on g.county_slug = c.slug
    where coalesce(g.gold_standard,false) or c.slug in ('duval','polk','marion','brevard')
    order by coalesce(g.gold_standard,false) desc, c.slug
  loop
    with src as (
      select e.*, mca.parcel_id as raw_parcel_id,
        case
          when e.property_address is null or btrim(e.property_address)=''
            or upper(btrim(e.property_address)) like '%UNKNOWN%'
          then 'Parcel ' || mca.parcel_id
          else substring(e.property_address from 1 for 32)
        end as disp_addr,
        case when coalesce(e.assessed,0)=0 then 'assessed pending'
             else '$' || to_char(e.assessed,'FM999,999,990') end as money_tok,
        coalesce(e.price_tier, case
          when e.assessed is null or e.assessed=0 then '—'
          when e.assessed < 5000 then 'tier_1_<5k'
          when e.assessed < 25000 then 'tier_2_5-25k'
          when e.assessed < 75000 then 'tier_3_25-75k'
          when e.assessed < 200000 then 'tier_4_75-200k'
          else 'tier_5_>200k' end) as tier_tok,
        coalesce(nullif(btrim(mca.bcpao_url),''), nullif(btrim(mca.clerk_url),''),
                 public.appraiser_link(v_c.slug, mca.parcel_id)) as appraiser_href,
        coalesce(
          (select coalesce(r.final_url, r.base_url, 'https://'||r.fqdn)
             from public.realauction_subdomains r
             where r.county_slug = v_c.slug
               and r.sale_type = case
                     when e.case_type = 'TAX_DEED' then 'tax_deed'
                     when e.case_type in ('FORECLOSURE','COUNTY_FC') then 'foreclosure'
                     else 'foreclosure' end
               and coalesce(r.is_canonical,true) and coalesce(r.is_active,true)
             limit 1),
          nullif(btrim(e.realforeclose_url),''), nullif(btrim(mca.auction_url),''),
          nullif(btrim(mca.source_url),'')) as bid_href,
        mca.case_number as gate_case_number,
        (
          mca.auction_status is distinct from 'CANCELLED'
          and mca.parity_status in ('CLERK_VERIFIED','PARITY_OK')
          and exists (
            select 1 from public.clerk_parity_results cpr
            where cpr.county_slug = lower(mca.county)
              and cpr.sale_type = mca.sale_type
              and cpr.status = 'PARITY'
              and cpr.checked_at > now() - interval '48 hours'
          )
        ) as passes_parity_gate
      from public.v_county_upcoming_enriched(v_c.slug, v_c.fdor_co_no) e
      join public.multi_county_auctions mca on mca.id = e.auction_id
      where (mca.parcel_id is null or mca.parcel_id not like 'SYN-%')
        and ( mca.parcel_id is not null
              or (e.property_address is not null and btrim(e.property_address)<>''
                  and upper(btrim(e.property_address)) not like '%UNKNOWN%') )
    ),
    gated as (
      select * from src where passes_parity_gate
    ),
    lines as (
      select row_number() over (
               order by (auction_date - current_date),
                        (avg_roi is not null) desc,
                        zip_score desc nulls last, assessed desc nulls last) as ln,
        ( case when avg_roi is not null then
            format(E'%s • %s • %s • %s • ROI %sx • %s anch%s%s',
              to_char(auction_date,'MM/DD'), disp_addr, money_tok, tier_tok,
              coalesce(to_char(avg_roi,'FM999.9'),'?'), coalesce(anchors_in_zip,0),
              case when montpelier_active then E' ★MONTP' else '' end,
              case when enrichment_status='queued' then ' [pend]' else '' end)
          else
            format(E'%s • %s • %s • %s%s',
              to_char(auction_date,'MM/DD'), disp_addr, money_tok, tier_tok,
              case when enrichment_status='queued' then ' [pend]' else '' end)
          end )
          || coalesce(E'\n  ↳ appraiser: ' || appraiser_href, '')
          || coalesce(E'\n  🔨 bid: ' || bid_href, '')
        as line
      from gated
    ),
    agg as (
      select
        (select count(*) from lines) as cnt,
        (select string_agg(line, E'\n' order by ln) from lines where ln <= 30) as section,
        (select count(*) filter (where not passes_parity_gate) from src) as suppressed_cnt,
        (select array_agg(gate_case_number) filter (where not passes_parity_gate) from src) as suppressed_cases
    )
    select cnt, section, suppressed_cnt, suppressed_cases
      into v_cnt, v_section, v_suppressed_cnt, v_suppressed_cases from agg;

    if coalesce(v_cnt,0) > 30 then
      v_section := coalesce(v_section,'') || format(E'\n  … +%s more', v_cnt - 30);
    end if;

    v_total := v_total + coalesce(v_cnt,0);
    v_subj_counts := v_subj_counts
      || case when v_subj_counts='' then '' else ' ' end
      || upper(substring(v_c.slug from 1 for 3)) || ':' || coalesce(v_cnt,0);

    v_body := v_body || format(E'*%s (%s)%s*\n%s\n\n',
      upper(replace(v_c.slug,'_',' ')), coalesce(v_cnt,0),
      case when v_c.is_gold then ' 🏆' else '' end,
      coalesce(v_section,'(none)'));

    if not p_dry_run and coalesce(v_suppressed_cnt,0) > 0 then
      insert into public.insights (county, sale_type, anomaly_type, description, properties_affected)
      values (
        v_c.slug, 'both', 'clerk_parity',
        format('fire_daily_upcoming_lots_digest suppressed %s lot(s) for %s: fail-closed on missing/stale/unverified clerk parity (Task 4.2 gate)', v_suppressed_cnt, v_c.slug),
        jsonb_build_object('suppressed_count', v_suppressed_cnt, 'case_numbers', to_jsonb(v_suppressed_cases[1:20]))
      );
    end if;
  end loop;

  v_subject := format('📋 FL upcoming lots — %s lots 30d (%s)', v_total, v_subj_counts);
  v_body := format(E'*%s*\n\n', v_subject) || v_body
    || E'🏆=Gold Standard certified county. "Parcel N"=real account, address pending. ↳ appraiser + 🔨 bid link on every lot (RealAuction parity). ROI/anch shown where flip-history exists. ★MONTP=Montpelier-active.';

  if not p_dry_run then
    for v_route in
      select * from public.flip_alert_routing
      where active = true and alert_type = 'DAILY_UPCOMING_DIGEST'
    loop
      insert into public.flip_alert_notifications (alert_id, channel, recipient, subject, body, notif_type)
      values (null, v_route.channel, v_route.recipient, v_subject, v_body, 'DIGEST');
      v_enq := v_enq + 1;
    end loop;
  end if;

  notifications_enqueued := v_enq;
  total_hot_lots := v_total;
  body_preview := v_body;
  return next;
end;
$function$;
