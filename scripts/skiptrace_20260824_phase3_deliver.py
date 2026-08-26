#!/usr/bin/env python3
"""Phase 3: quote-draft + route + deliver the 19 gate-passed leads from the
2026-08-24 third_party batch; log a gate_blocked activity (no delivery, no
live link) for the 5 that failed the improved-property gate.
"""
import json
import os
import urllib.request

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"


def run_sql(query, timeout=90):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "skiptrace-aug24-batch-phase3/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read())
    if isinstance(body, dict) and "message" in body:
        raise RuntimeError(body["message"])
    return body


def s(v):
    if v is None:
        return "null"
    return "'" + str(v).replace("'", "''") + "'"


def main():
    leads = run_sql("""
        select l.lead_id, l.org_id, l.entity_name, l.parcel_id, l.consent_certificate->>'improved_gate' as gate,
               l.consent_certificate->>'gate_note' as gate_note
        from winnerdata.leads l
        join winnerdata.signal_events se on se.signal_id = l.signal_id
        where (se.event_payload->>'batch') = '20260824_third_party';
    """)
    print(f"{len(leads)} leads in this batch.")

    blocked = [r for r in leads if r["gate"] != "pass"]
    passed = [r for r in leads if r["gate"] == "pass"]

    for r in blocked:
        run_sql(f"""
            insert into winnerdata.lead_activity (lead_id, org_id, producer_id, activity_type, channel, payload, occurred_at)
            select {s(r['lead_id'])}, {s(r['org_id'])}, null, 'gate_blocked', 'call_sheet',
              jsonb_build_object('reason', 'improved_property_gate_' || {s(r['gate'])}, 'detail', {s(r['gate_note'])}),
              now()
            where not exists (
              select 1 from winnerdata.lead_activity la
              where la.lead_id = {s(r['lead_id'])} and la.activity_type = 'gate_blocked'
            );
        """)
    print(f"Logged gate_blocked for {len(blocked)} leads (not delivered, no live link).")

    # quote_drafts for the 19 gate-passed leads (same completeness scoring shape as winnerdata_pipeline.py SPRINT3)
    run_sql("""
        with lead_src as (
          select l.lead_id, l.org_id, l.product_line, l.parcel_id, l.entity_name, se.occurred_at, se.county
          from winnerdata.leads l
          join winnerdata.signal_events se on se.signal_id = l.signal_id
          where (se.event_payload->>'batch') = '20260824_third_party'
            and (l.consent_certificate->>'improved_gate') = 'pass'
            and not exists (select 1 from winnerdata.quote_drafts qd where qd.lead_id = l.lead_id)
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
              (lot_size is not null)::int
            )::numeric / 9 * 100 as completeness_pct
          from enriched
        )
        insert into winnerdata.quote_drafts (lead_id, org_id, product_line, payload, completeness_pct, open_gaps, assembled_at)
        select
          lead_id, org_id, product_line,
          jsonb_build_object(
            'applicant', jsonb_build_object('name', entity_name, 'entity_type_source', 'name_pattern_heuristic'),
            'location', jsonb_build_object('address', property_address, 'city', city, 'county', county, 'zip', zip, 'state', 'FL'),
            'construction', jsonb_build_object('year_built', year_built, 'sqft', sqft, 'beds', beds, 'baths', baths),
            'valuation', jsonb_build_object('assessed_value', assessed_value, 'market_value', market_value, 'lot_size_acres', lot_size, 'sale_type', sale_type),
            'effective_date', current_date,
            'meta', jsonb_build_object('signal_occurred_at', occurred_at, 'batch', '20260824_third_party')
          ),
          completeness_pct,
          (array_remove(array[
            case when year_built is null then 'year_built' end,
            case when sqft is null then 'square_footage' end,
            case when beds is null or baths is null then 'bed_bath_count' end
          ], null))::text[],
          now()
        from scored;
    """)
    print("quote_drafts assembled for gate-passed leads.")

    run_sql("""
        insert into winnerdata.producers (org_id, full_name, email, active_lines, license_states, active)
        select org_id, 'Mariam Shapira', null, array['dwelling_landlord','builders_risk','commercial_bop']::winnerdata.product_line[], array['FL'], true
        from winnerdata.organizations where name = 'Protection Partners'
        and not exists (select 1 from winnerdata.producers p join winnerdata.organizations o on o.org_id=p.org_id where o.name='Protection Partners' and p.full_name='Mariam Shapira');
    """)
    run_sql("""
        insert into winnerdata.routing_decisions (lead_id, org_id, producer_id, product_line, routing_reason, routed_at)
        select distinct on (l.lead_id) l.lead_id, l.org_id, p.producer_id, l.product_line, 'calibration', now()
        from winnerdata.leads l
        join winnerdata.signal_events se on se.signal_id = l.signal_id
        join winnerdata.producers p on p.org_id = l.org_id and p.full_name = 'Mariam Shapira'
        where (se.event_payload->>'batch') = '20260824_third_party'
          and (l.consent_certificate->>'improved_gate') = 'pass'
          and exists (select 1 from winnerdata.quote_drafts qd where qd.lead_id = l.lead_id)
          and not exists (select 1 from winnerdata.routing_decisions rd where rd.lead_id = l.lead_id)
        order by l.lead_id, p.created_at;
    """)
    print("Routed to Mariam Shapira (Protection Partners producer).")

    run_sql(f"""
        insert into winnerdata.lead_activity (lead_id, org_id, producer_id, activity_type, channel, payload, occurred_at)
        select l.lead_id, l.org_id, rd.producer_id, 'delivered', 'call_sheet',
          jsonb_build_object('batch_date', '2026-08-24', 'batch', '20260824_third_party'), now()
        from winnerdata.leads l
        join winnerdata.signal_events se on se.signal_id = l.signal_id
        join winnerdata.routing_decisions rd on rd.lead_id = l.lead_id
        where (se.event_payload->>'batch') = '20260824_third_party'
          and (l.consent_certificate->>'improved_gate') = 'pass'
          and not exists (select 1 from winnerdata.lead_activity la where la.lead_id = l.lead_id and la.activity_type='delivered');
    """)
    print("Marked delivered.")

    final = run_sql("""
        select l.lead_id, l.entity_name, l.contact_phone, l.consent_certificate->>'improved_gate' as gate,
               l.consent_certificate->>'skip_trace_status' as skip_trace_status,
               (exists(select 1 from winnerdata.lead_activity la where la.lead_id=l.lead_id and la.activity_type='delivered')) as delivered
        from winnerdata.leads l
        join winnerdata.signal_events se on se.signal_id = l.signal_id
        where (se.event_payload->>'batch') = '20260824_third_party'
        order by l.entity_name;
    """)
    print(json.dumps(final, indent=2))


if __name__ == "__main__":
    main()
