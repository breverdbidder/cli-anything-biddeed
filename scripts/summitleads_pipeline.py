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
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "property_appraiser"))
import tracerfy_client  # noqa: E402
import ff_credit_ledger  # noqa: E402
import dispatch as appraiser_dispatch  # noqa: E402

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_ANON_OR_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Retryable = not yet resolved either way, safe to attempt again next run
# (including a run that was skipped only because the daily credit cap was
# already hit). Terminal = attempted at least once; per Tracerfy's
# documented near-zero hit rate on pure-entity names with no person name on
# record, a terminal no-hit is a real ceiling, not retried forever.
TRACERFY_RETRYABLE_STATUSES = ("SKIP_TRACE_PENDING_TRACERFY_KEY_ABSENT", "SKIP_TRACE_SKIPPED_DAILY_CAP")


def _sql_str(v):
    if v is None:
        return "null"
    return "'" + str(v).replace("'", "''") + "'"


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
select distinct on (l.lead_id) l.lead_id, l.org_id, p.producer_id, l.product_line, 'calibration', now()
from summitleads.leads l
join summitleads.producers p on p.org_id = l.org_id and p.full_name = 'Mariam Shapira'
where exists (select 1 from summitleads.quote_drafts qd where qd.lead_id = l.lead_id)
  and not exists (select 1 from summitleads.routing_decisions rd where rd.lead_id = l.lead_id)
order by l.lead_id, p.created_at;
"""

BATCH_QUERY = """
select distinct on (l.lead_id)
       l.lead_id, l.entity_name, l.parcel_id, l.contact_phone, l.contact_email, l.dnc_scrubbed_at,
       l.consent_certificate, l.closing_date, l.temperature, l.product_line,
       qd.completeness_pct, qd.open_gaps, qd.assembled_at,
       se.county, se.occurred_at as signal_occurred_at,
       se.event_payload->>'case_number' as case_number,
       se.event_payload->>'sale_type' as sale_type,
       (se.event_payload->>'sold_amount')::numeric as sold_amount,
       se.event_payload->>'property_address' as property_address,
       mca.assessed_value, mca.market_value,
       p.full_name as producer_name
from summitleads.leads l
join summitleads.quote_drafts qd on qd.lead_id = l.lead_id
join summitleads.signal_events se on se.signal_id = l.signal_id
join summitleads.routing_decisions rd on rd.lead_id = l.lead_id
join summitleads.producers p on p.producer_id = rd.producer_id
left join public.multi_county_auctions mca on mca.parcel_id = l.parcel_id and mca.county = se.county
where not exists (
  select 1 from summitleads.lead_activity la where la.lead_id = l.lead_id and la.activity_type = 'delivered'
)
order by l.lead_id, mca.assessed_value desc nulls last;
"""

# Same shape as BATCH_QUERY but scoped to everything already delivered under
# this batch_date (not just leads new to this run). The rendered file must
# always reflect the full day's cumulative batch — a same-day re-run of this
# script must not clobber the file down to only this run's delta.
RENDERED_BATCH_QUERY_TMPL = """
select distinct on (l.lead_id)
       l.lead_id, l.entity_name, l.parcel_id, l.contact_phone, l.contact_email, l.dnc_scrubbed_at,
       l.consent_certificate, l.closing_date, l.temperature, l.product_line,
       qd.completeness_pct, qd.open_gaps, qd.assembled_at,
       se.county, se.occurred_at as signal_occurred_at,
       se.event_payload->>'case_number' as case_number,
       se.event_payload->>'sale_type' as sale_type,
       (se.event_payload->>'sold_amount')::numeric as sold_amount,
       se.event_payload->>'property_address' as property_address,
       mca.assessed_value, mca.market_value,
       p.full_name as producer_name
from summitleads.leads l
join summitleads.quote_drafts qd on qd.lead_id = l.lead_id
join summitleads.signal_events se on se.signal_id = l.signal_id
join summitleads.routing_decisions rd on rd.lead_id = l.lead_id
join summitleads.producers p on p.producer_id = rd.producer_id
left join public.multi_county_auctions mca on mca.parcel_id = l.parcel_id and mca.county = se.county
where exists (
  select 1 from summitleads.lead_activity la
  where la.lead_id = l.lead_id and la.activity_type = 'delivered' and (la.payload->>'batch_date') = '{batch_date}'
)
order by l.lead_id, mca.assessed_value desc nulls last;
"""


BRIGHTDATA_PLACEHOLDER_COUNTIES_QUERY = """
select distinct county from summitleads.signal_events
where event_type = 'auction_close' and source = 'biddeed'
  and coalesce((event_payload->>'is_placeholder_identity')::boolean, false) = true
  and occurred_at >= (current_date - interval '1 day');
"""


def sprint1b_brightdata_harvest():
    """Bright Data winner harvest for placeholder-identity ('3rd Party
    Bidder') winners from the last day, across whichever of the 67 counties
    actually have one -- never a hardcoded 'certified counties' list. One
    combined-ledger unit spent per county attempt (a scraper run touches many
    pages within that county); see ff_credit_ledger.py header for why this is
    call-count-based, not a reconciled Tracerfy/BrightData dollar figure."""
    if not os.environ.get("BRIGHTDATA_BROWSER_WSS") or not os.environ.get("REALFORECLOSE_EMAIL") or not os.environ.get("REALFORECLOSE_PASSWORD"):
        print("Sprint 1b BLOCKED: BRIGHTDATA_BROWSER_WSS/REALFORECLOSE_EMAIL/REALFORECLOSE_PASSWORD "
              "absent -- skipping winner harvest, running on existing winning_bidder data only.")
        return

    counties = [r["county"] for r in run_sql(BRIGHTDATA_PLACEHOLDER_COUNTIES_QUERY) if r.get("county")]
    if not counties:
        print("Sprint 1b: no placeholder-identity winners in the last day across any county -- nothing to harvest.")
        return

    run_counties, skipped_counties = [], []
    for county in counties:
        ledger = ff_credit_ledger.spend("brightdata", 1)
        if not ledger.get("granted"):
            skipped_counties.append((county, ledger.get("error") or "daily combined credit cap reached"))
            continue
        run_counties.append(county)

    if skipped_counties:
        print(f"Sprint 1b: {len(skipped_counties)} county attempt(s) skipped on the daily credit cap: {skipped_counties}")
    if not run_counties:
        print("Sprint 1b: all candidate counties skipped (cap already hit before this run started).")
        return

    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "brightdata_auction_harvester.py"),
         "--counties", ",".join(run_counties)],
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        print(f"Sprint 1b: brightdata_auction_harvester.py exited {result.returncode} for counties {run_counties} "
              "-- see its own FATAL-on-login-failure logging above. Continuing pipeline on existing data.")
    else:
        print(f"Sprint 1b done: harvested {run_counties}.")


class MailingAddressLookupError(Exception):
    """Raised on a transport/query failure (e.g. timeout) -- NOT the same as
    a successful zero-row result. Conflating the two would mislabel a
    transient failure as the terminal 'this buyer has no fl_parcels history'
    ceiling, permanently losing the lookup (see idx_fl_parcels_ownname_trgm
    migration header for the live timeout this caught)."""


def lookup_mailing_address(entity_name):
    """Buyer's own prior-deed mailing address (fl_parcels.own_addr1) -- the
    proven 88%-hit-rate method (see tracerfy_client.py module docstring).
    Returns None if the query succeeded but this buyer genuinely has no
    fl_parcels history to trace against (a real ceiling for pure LLC/trust
    names never seen as an owner before, not a bug). Raises
    MailingAddressLookupError on a transport/query failure so the caller
    can leave the lead retryable instead of terminal."""
    if not entity_name:
        return None
    pattern = urllib.parse.quote(f"*{entity_name.strip()}*")
    url = f"{SUPABASE_URL}/rest/v1/fl_parcels?select=own_addr1,own_city,own_state,own_zipcd&own_name=ilike.{pattern}&own_addr1=not.is.null&limit=1"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_ANON_OR_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_ANON_OR_SERVICE_KEY}",
    })
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            rows = json.loads(resp.read())
    except Exception as e:
        raise MailingAddressLookupError(str(e)) from e
    return rows[0] if rows else None


TRACERFY_CANDIDATES_QUERY = f"""
select l.lead_id, l.entity_name
from summitleads.leads l
where l.contact_phone is null and l.contact_email is null
  and coalesce(l.consent_certificate->>'skip_trace_status', '') in (
    {", ".join(_sql_str(s) for s in TRACERFY_RETRYABLE_STATUSES)}
  );
"""


def sprint2b_tracerfy_skiptrace():
    """Real Tracerfy enhanced-trace calls for leads still in a retryable
    skip-trace state, ledger-gated, never re-attempting a lead that already
    reached a terminal outcome (hit, confirmed no-hit, or no mailing address
    to trace against) on a prior run."""
    if not os.environ.get("TRACERFY_API_KEY"):
        print("Sprint 2b BLOCKED: TRACERFY_API_KEY absent -- leads stay in degraded/pending skip-trace state.")
        return

    candidates = run_sql(TRACERFY_CANDIDATES_QUERY)
    if not candidates:
        print("Sprint 2b: no leads pending skip-trace.")
        return

    hits = no_hits = no_address = cap_skipped = lookup_errors = 0
    for lead in candidates:
        try:
            addr = lookup_mailing_address(lead["entity_name"])
        except MailingAddressLookupError as e:
            # Leave skip_trace_status untouched (stays in a retryable state)
            # -- a transport/query failure is not proof this buyer has no
            # fl_parcels history, and must not be permanently mislabeled as
            # the terminal no-address ceiling.
            print(f"  lookup_mailing_address({lead['entity_name']!r}) failed, leaving retryable: {e}")
            lookup_errors += 1
            continue
        if not addr:
            run_sql(f"""
                update summitleads.leads set consent_certificate = consent_certificate ||
                  jsonb_build_object('skip_trace_status', 'TRACED_NO_MAILING_ADDRESS')
                where lead_id = {_sql_str(lead['lead_id'])};
            """)
            no_address += 1
            continue

        ledger = ff_credit_ledger.spend("tracerfy", 1)
        if not ledger.get("granted"):
            run_sql(f"""
                update summitleads.leads set consent_certificate = consent_certificate ||
                  jsonb_build_object('skip_trace_status', 'SKIP_TRACE_SKIPPED_DAILY_CAP')
                where lead_id = {_sql_str(lead['lead_id'])};
            """)
            cap_skipped += 1
            continue

        result = tracerfy_client.trace_lead(
            lead["entity_name"], addr.get("own_addr1"), addr.get("own_city"), addr.get("own_state"), addr.get("own_zipcd"),
        )
        if result.get("phone") or result.get("email"):
            run_sql(f"""
                update summitleads.leads set
                  contact_phone = {_sql_str(result.get('phone'))},
                  contact_email = {_sql_str(result.get('email'))},
                  contact_name = {_sql_str(result.get('full_name') or lead['entity_name'])},
                  consent_certificate = consent_certificate ||
                    jsonb_build_object('skip_trace_status', 'TRACED_HIT', 'skip_trace_parse_status', {_sql_str(result.get('parse_status'))})
                where lead_id = {_sql_str(lead['lead_id'])};
            """)
            hits += 1
        else:
            run_sql(f"""
                update summitleads.leads set consent_certificate = consent_certificate ||
                  jsonb_build_object('skip_trace_status', 'TRACED_NO_HIT', 'skip_trace_parse_status', {_sql_str(result.get('parse_status'))})
                where lead_id = {_sql_str(lead['lead_id'])};
            """)
            no_hits += 1

    print(f"Sprint 2b done: {hits} hit(s), {no_hits} confirmed no-hit, {no_address} with no fl_parcels "
          f"mailing address to trace against, {cap_skipped} skipped on daily credit cap, "
          f"{lookup_errors} left retryable after a lookup error.")


APPRAISER_VERIFY_CANDIDATES_QUERY = """
select l.lead_id, se.event_payload->>'case_number' as case_number, se.county,
       l.parcel_id, se.event_payload->>'property_address' as address, fp.own_name as owner
from summitleads.leads l
join summitleads.signal_events se on se.signal_id = l.signal_id
left join public.fl_parcels fp on fp.parcel_id = l.parcel_id
where l.parcel_id is not null
  and se.county in ('manatee', 'lee', 'broward', 'palm_beach', 'marion');
"""


def sprint3b_appraiser_verify():
    """Property appraiser cross-verification for the 5 counties with a live
    scraper (see scripts/property_appraiser/dispatch.py). Every other county
    gets its NOT VERIFIED badge + reason straight from public.ff_get_lead's
    fl_property_appraiser_configs/fl_counties fallback -- no placeholder row
    needed here."""
    leads = run_sql(APPRAISER_VERIFY_CANDIDATES_QUERY)
    if not leads:
        print("Sprint 3b: no leads in a property-appraiser-scraper-supported county.")
        return
    stats = appraiser_dispatch.verify_leads(leads)
    print(f"Sprint 3b done: {stats}")


def sprint5_deliver(batch_date):
    new_rows = run_sql(BATCH_QUERY)
    if not new_rows:
        print("Sprint 5: no newly-undelivered leads this run.")
    else:
        lead_ids = ",".join(f"'{r['lead_id']}'" for r in new_rows)
        run_sql(f"""
            insert into summitleads.lead_activity (lead_id, org_id, producer_id, activity_type, channel, payload, occurred_at)
            select l.lead_id, l.org_id, rd.producer_id, 'delivered', 'call_sheet',
              jsonb_build_object('batch_date', '{batch_date}'), now()
            from summitleads.leads l
            join summitleads.routing_decisions rd on rd.lead_id = l.lead_id
            where l.lead_id in ({lead_ids})
              and not exists (select 1 from summitleads.lead_activity la where la.lead_id = l.lead_id and la.activity_type='delivered');
        """)
        print(f"Sprint 5: marked {len(new_rows)} newly-delivered lead(s) for batch_date={batch_date}.")

    # Always re-render from the FULL cumulative batch_date set, not just this run's delta,
    # so a same-day re-run never clobbers previously-delivered leads out of the committed file.
    rows = run_sql(RENDERED_BATCH_QUERY_TMPL.format(batch_date=batch_date))
    if not rows:
        print(f"Sprint 5: nothing delivered for batch_date={batch_date} — no file written.")
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
    print(f"Sprint 5: rendered {len(rows)} cumulative lead(s) to {out_dir}")


def main():
    batch_date = os.environ.get("SUMMITLEADS_BATCH_DATE", date.today().isoformat())

    run_sql(SPRINT1)
    print("Sprint 1 done: signal_events synced from last-7-day completed FL auctions, all 67 counties.")
    sprint1b_brightdata_harvest()
    run_sql(SPRINT2)
    print("Sprint 2 done: leads created for non-placeholder-identity signals.")
    sprint2b_tracerfy_skiptrace()
    sprint3b_appraiser_verify()
    run_sql(SPRINT3)
    print("Sprint 3 done: quote_drafts assembled for un-drafted leads.")
    run_sql(SPRINT4)
    print("Sprint 4 done: producers seeded, leads routed (routing_reason=calibration).")
    sprint5_deliver(batch_date)

    counts = run_sql("""
        select
          (select count(*) from summitleads.signal_events) as signal_events,
          (select count(*) from summitleads.leads) as leads,
          (select count(*) from summitleads.leads where contact_phone is not null or contact_email is not null) as leads_with_contact,
          (select count(*) from summitleads.quote_drafts) as quote_drafts,
          (select count(*) from summitleads.lead_activity where activity_type='delivered') as delivered,
          (select count(*) from public.parity_audit where verdict='pass' and field_name='parcel_id') as appraiser_verified_parcels,
          (select total_calls from public.ff_daily_credit_ledger where usage_date = current_date) as credit_units_spent_today;
    """)
    print("Sprint 6 QA — live counts:", json.dumps(counts[0]))


if __name__ == "__main__":
    main()
