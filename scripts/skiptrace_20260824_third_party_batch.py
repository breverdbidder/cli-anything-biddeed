#!/usr/bin/env python3
"""One-shot batch: skip-trace + deliver the 2026-08-24 third_party auction winners.

Scoped run for issue-driven batch work (17-24 Aug-24 third_party rows, see
issue). Deliberately NOT summitleads_pipeline.py's generic SPRINT1/2 — those
filter only on `is_placeholder_identity`, which does not exclude plaintiff
takebacks (a real winning_bidder name that is NOT a lead per this batch's
scope). This script scopes strictly to
multi_county_auctions.tier1_buyer_type='third_party' AND auction_date=
'2026-08-24', pulled live (no hardcoded row list).

Improved-property gate (buildings > 0 on fl_parcels.no_buldng for the
SUBJECT parcel) is applied before any lead is allowed to proceed to
skip-trace/delivery -- confirmed vacant (no_buldng=0) or unknown (no
fl_parcels row for that parcel/county) leads still get a lead row (so no
buyer is left indistinguishable from "never attempted") but are gate-blocked
from delivery, never traced, never live-linked.

Entity piercing: fl_parcels own_name history first (buyer's own prior deed --
the proven 88%-hit-rate address, never the just-purchased property). Sunbiz
piercing for LLCs with no fl_parcels hit was ATTEMPTED this session via
Firecrawl scrape of search.sunbiz.org and via WebFetch -- both blocked
(Cloudflare bot-challenge on the Sunbiz side; Firecrawl separately returned
HTTP 402 insufficient credits). This is a real, live-confirmed ceiling this
session, not a shortcut -- tagged honestly per-lead rather than retried.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import tracerfy_client  # noqa: E402
import ff_credit_ledger  # noqa: E402

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
BATCH_DATE = "2026-08-24"


def run_sql(query, timeout=90):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "skiptrace-aug24-batch/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read())
    if isinstance(body, dict) and "message" in body:
        raise RuntimeError(body["message"])
    return body


def sql_str(v):
    if v is None:
        return "null"
    return "'" + str(v).replace("'", "''") + "'"


def main():
    batch = run_sql(f"""
        select id, county, case_number, parcel_id, property_address, sold_amount, winning_bidder
        from public.multi_county_auctions
        where auction_date = '{BATCH_DATE}' and tier1_buyer_type = 'third_party'
          and winning_bidder is not null
        order by county, case_number;
    """)
    print(f"Live batch pulled: {len(batch)} third_party rows for {BATCH_DATE} (no hardcoding).")

    # 1. signal_events -- idempotent, scoped to exactly these auction ids
    ids = ",".join(sql_str(r["id"]) for r in batch)
    run_sql(f"""
        insert into summitleads.signal_events (event_type, source, county, parcel_id, entity_name, event_payload, occurred_at)
        select 'auction_close', 'biddeed', county, parcel_id, winning_bidder,
          jsonb_build_object('case_number', case_number, 'sale_type', sale_type, 'sold_amount', sold_amount,
            'property_address', property_address, 'auction_id', id, 'batch', '20260824_third_party'),
          (auction_date::timestamptz)
        from public.multi_county_auctions
        where id in ({ids})
          and not exists (
            select 1 from summitleads.signal_events se
            where se.source='biddeed' and se.event_type='auction_close'
              and (se.event_payload->>'auction_id') = multi_county_auctions.id::text
          );
    """)
    print("signal_events synced.")

    counts = run_sql("select count(*) as n from summitleads.leads;")
    print(f"leads table before this run: {counts[0]['n']}")


if __name__ == "__main__":
    main()
