#!/usr/bin/env python3
"""SummitLeads Signal -> Skip-trace -> Quote-Draft -> Route -> Deliver spine.

Idempotent (all inserts guarded by NOT EXISTS). Runs against the live
summitleads schema via the Supabase Management API SQL endpoint (PostgREST
does not expose the summitleads schema). Degrades gracefully — and says so
in the run summary — when BRIGHTDATA_* / TRACERFY_API_KEY are absent.

Sprint 1b (Bright Data winner harvest) and the Tracerfy skip-trace lookup
are NOT implemented here: they require vendor SDKs / browser automation
this script does not carry. When those secrets are present this script
still only does the internal-data sprints (1, 2-degraded, 3, 4, 5); a
human/agent session should run the actual harvest + skip-trace separately
and this script will pick up the resulting rows on its next run.
"""
import json
import os
import sys
import urllib.request
from datetime import date

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"


def run_sql(query):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "summitleads-pipeline/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
    if isinstance(body, dict) and "message" in body:
        raise RuntimeError(body["message"])
    return body


SPRINT1 = """
insert into summitleads.signal_events (event_type, source, county, parcel_id, entity_name, event_payload, occurred_at)
select 'auction_close', 'biddeed', county, parcel_id, winning_bidder,
  jsonb_build_object(
    'case_number', case_number, 'sale_type', sale_type, 'sold_amount', sold_amount,
    'property_address', property_address, 'auction_id', id, 'winning_bidder_source', winning_bidder_source,
    'is_placeholder_identity', (winning_bidder is null or winning_bidder ilike '3rd party%')
  ),
  (auction_date::timestamptz)
from public.multi_county_auctions
where auction_date >= (current_date - interval '7 days') and auction_date <= current_date
  and sold_amount is not null
  and not exists (
    select 1 from summitleads.signal_events se
    where se.source='biddeed' and se.event_type='auction_close'
      and (se.event_payload->>'auction_id') = multi_county_auctions.id::text
  );
"""

# Sprint 2 (degraded): only signals with a real (non-placeholder) winning_bidder
# become leads. No Tracerfy/Sunbiz lookup is attempted here — contact info is
# left null and flagged, per SummitLeads compliance rails.
SPRINT2 = """
with se as (
  select signal_id, county, parcel_id, entity_name, event_payload, occurred_at
  from summitleads.signal_events
  where coalesce((event_payload->>'is_placeholder_identity')::boolean, true) = false
), org as (
  select org_id from summitleads.organizations where name = 'Protection Partners'
), classified as (
  select se.*, org.org_id,
    case when se.entity_name ilike '%properties%' or se.entity_name ilike '%construction%'
           or se.entity_name ilike '% llc%' or se.entity_name ilike '%llc' or se.entity_name ilike '%inc%'
         then 'business' else 'person' end as entity_type
  from se cross join org
)
insert into summitleads.leads (
  org_id, signal_id, product_line, temperature, outbound_lane,
  contact_name, contact_phone, contact_email, entity_name, parcel_id,
  closing_date, consent_status, consent_certificate, dnc_scrubbed_at,
  acquisition_cost_cents, ops_cost_cents
)
select
  org_id, signal_id, 'dwelling_landlord'::summitleads.product_line, 'hot'::summitleads.temperature,
  'compliant_outbound'::summitleads.outbound_lane, entity_name, null, null, entity_name, parcel_id,
  occurred_at::date, 'none'::summitleads.consent_status,
  jsonb_build_object(
    'entity_type', entity_type,
    'compliance_flag', case when entity_type = 'business' then 'NO_CONTACT_INFO_SUNBIZ_LOOKUP_PENDING' else 'DNC_UNSCRUBBED' end,
    'skip_trace_status', 'SKIP_TRACE_PENDING_TRACERFY_KEY_ABSENT',
    'contact_source', 'none_available_this_session'
  ),
  null, 0, 0
from classified
where not exists (select 1 from summitleads.leads l where l.signal_id = classified.signal_id);
"""

SPRINT3 = """
with lead_src as (
  select l.lead_id, l.org_id, l.product_line, l.parcel_id, l.entity_name, se.occurred_at, se.county
  from summitleads.leads l
  join summitleads.signal_events se on se.signal_id = l.signal_id
  where not exists (select 1 from summitleads.quote_drafts qd where qd.lead_id = l.lead_id)
), enriched as (
  select ls.*, a.property_address, a.city, a.zip, a.assessed_value, a.market_value, a.lot_size,
         a.year_built, a.beds, a.baths, a.sqft, a.sale_type
  from lead_src ls
  left join public.multi_county_auctions a on a.parcel_id = ls.parcel_id and a.county = ls.county
), scored as (
  select enriched.*,
    ( (entity_name is not null)::int + (property_address is not null)::int +
      (county is not null)::int + (coalesce(city,'') <> '' or property_address is not null)::int +
      (assessed_value is not null)::int + (year_built is not null)::int +
      (sqft is not null)::int + (beds is not null and baths is not null)::int +
      (lot_size is not null)::int + (false)::int
    )::numeric / 10 * 100 as completeness_pct
  from enriched
)
insert into summitleads.quote_drafts (lead_id, org_id, product_line, payload, completeness_pct, open_gaps, assembled_at)
select
  lead_id, org_id, product_line,
  jsonb_build_object(
    'applicant', jsonb_build_object('name', entity_name, 'entity_type_source', 'name_pattern_heuristic'),
    'location', jsonb_build_object('address', property_address, 'city', city, 'county', county, 'zip', zip, 'state', 'FL'),
    'construction', jsonb_build_object('year_built', year_built, 'sqft', sqft, 'beds', beds, 'baths', baths, 'zonewise_coverage', false),
    'protection', jsonb_build_object('note', 'no fire/protection-class data available this session'),
    'vacancy_flags', jsonb_build_object('occupancy_status', 'unknown', 'note', 'no occupancy source available'),
    'valuation', jsonb_build_object('assessed_value', assessed_value, 'market_value', market_value, 'lot_size_acres', lot_size, 'sale_type', sale_type),
    'effective_date', current_date,
    'meta', jsonb_build_object('signal_occurred_at', occurred_at, 'ttbq_seconds', extract(epoch from (now() - occurred_at)))
  ),
  completeness_pct,
  (array_remove(array[
    case when year_built is null then 'year_built' end,
    case when sqft is null then 'square_footage' end,
    case when beds is null or baths is null then 'bed_bath_count' end,
    case when true then 'occupancy_status' end,
    case when true then 'construction_type' end,
    case when true then 'roof_type' end,
    case when true then 'protection_class' end
  ], null))::text[],
  now()
from scored;
"""

SPRINT4 = """
insert into summitleads.producers (org_id, full_name, email, active_lines, license_states, active)
select org_id, 'Mariam Shapira', null, array['dwelling_landlord','builders_risk','commercial_bop']::summitleads.product_line[], array['FL'], true
from summitleads.organizations where name = 'Protection Partners'
and not exists (select 1 from summitleads.producers p join summitleads.organizations o on o.org_id=p.org_id where o.name='Protection Partners' and p.full_name='Mariam Shapira');

insert into summitleads.routing_decisions (lead_id, org_id, producer_id, product_line, routing_reason, routed_at)
select l.lead_id, l.org_id, p.producer_id, l.product_line, 'calibration', now()
from summitleads.leads l
join summitleads.producers p on p.org_id = l.org_id and p.full_name = 'Mariam Shapira'
where not exists (select 1 from summitleads.routing_decisions rd where rd.lead_id = l.lead_id);
"""

BATCH_QUERY = """
select l.lead_id, l.entity_name, l.parcel_id, l.consent_certificate, l.closing_date, l.temperature,
       l.product_line, qd.completeness_pct, qd.open_gaps, qd.payload, se.event_payload, p.full_name as producer_name
from summitleads.leads l
join summitleads.quote_drafts qd on qd.lead_id = l.lead_id
join summitleads.signal_events se on se.signal_id = l.signal_id
join summitleads.routing_decisions rd on rd.lead_id = l.lead_id
join summitleads.producers p on p.producer_id = rd.producer_id
where not exists (
  select 1 from summitleads.lead_activity la where la.lead_id = l.lead_id and la.activity_type = 'delivered'
)
order by l.entity_name;
"""


def sprint5_deliver(batch_date):
    rows = run_sql(BATCH_QUERY)
    if not rows:
        print("Sprint 5: no undelivered leads — nothing to batch today.")
        return
    out_dir = f"summitleads/batches/{batch_date}"
    os.makedirs(out_dir, exist_ok=True)
    # markdown rendering intentionally kept inline (mirrors scripts/summitleads_render_batch.py)
    import subprocess
    with open("/tmp/batch_data.json", "w") as f:
        json.dump(rows, f)
    subprocess.run(
        [sys.executable, "scripts/summitleads_render_batch.py"],
        check=True,
        env={**os.environ, "BATCH_DATE_OVERRIDE": batch_date},
    )
    lead_ids = ",".join(f"'{r['lead_id']}'" for r in rows)
    run_sql(f"""
        insert into summitleads.lead_activity (lead_id, org_id, producer_id, activity_type, channel, payload, occurred_at)
        select l.lead_id, l.org_id, rd.producer_id, 'delivered', 'call_sheet',
          jsonb_build_object('batch_date', '{batch_date}'), now()
        from summitleads.leads l
        join summitleads.routing_decisions rd on rd.lead_id = l.lead_id
        where l.lead_id in ({lead_ids})
          and not exists (select 1 from summitleads.lead_activity la where la.lead_id = l.lead_id and la.activity_type='delivered');
    """)
    print(f"Sprint 5: delivered {len(rows)} lead(s) to {out_dir}")


def main():
    batch_date = os.environ.get("SUMMITLEADS_BATCH_DATE", date.today().isoformat())

    if not os.environ.get("BRIGHTDATA_API_KEY") or not os.environ.get("BRIGHTDATA_BROWSER_WSS"):
        print("Sprint 1b BLOCKED: BRIGHTDATA_API_KEY/BRIGHTDATA_BROWSER_WSS absent — "
              "skipping winner harvest, running on existing winning_bidder data only.")
    else:
        print("Sprint 1b SCOPE GAP: BRIGHTDATA_* secrets are present, but no Bright Data "
              "Scraping Browser client exists in this repo yet (no connect_over_cdp usage "
              "anywhere; county_outcome_harvester.py is plain urllib, not a browser). "
              "Secrets landing did not unblock this — the harvester still needs to be "
              "written and verified against a live county site before it can run. "
              "Running on existing winning_bidder data only.")
    if not os.environ.get("TRACERFY_API_KEY"):
        print("Sprint 2 degraded: TRACERFY_API_KEY absent — no phone/email skip-trace, "
              "leads created with contact info gaps flagged per compliance rails.")
    else:
        print("Sprint 2 SCOPE GAP: TRACERFY_API_KEY is present, but no Tracerfy API client "
              "exists in this repo yet and its endpoint/auth contract is undocumented here. "
              "Guessing at the API shape risks burning paid lookups or mishandling PII, so "
              "this session leaves skip-trace degraded rather than faking a call. Leads "
              "created with contact info gaps flagged per compliance rails.")

    run_sql(SPRINT1)
    print("Sprint 1 done: signal_events synced from last-7-day completed FL auctions.")
    run_sql(SPRINT2)
    print("Sprint 2 done: leads created for non-placeholder-identity signals.")
    run_sql(SPRINT3)
    print("Sprint 3 done: quote_drafts assembled for un-drafted leads.")
    run_sql(SPRINT4)
    print("Sprint 4 done: producers seeded, leads routed (routing_reason=calibration).")
    sprint5_deliver(batch_date)

    counts = run_sql("""
        select
          (select count(*) from summitleads.signal_events) as signal_events,
          (select count(*) from summitleads.leads) as leads,
          (select count(*) from summitleads.quote_drafts) as quote_drafts,
          (select count(*) from summitleads.lead_activity where activity_type='delivered') as delivered;
    """)
    print("Sprint 6 QA — live counts:", json.dumps(counts[0]))


if __name__ == "__main__":
    main()
