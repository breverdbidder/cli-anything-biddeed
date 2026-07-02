#!/usr/bin/env python3
"""
Thin pagination wrapper around shard9_j_generator's run_for_county for manatee.
PostgREST caps rows at 1000/request server-side regardless of ?limit=; shard9_j_generator.py
fetched only the first 1000 (of 1428) manatee auctions. This reuses its exact
build_bid_decision/verify_county logic but paginates the MCA fetch via Range headers.
dispatch_id: a22499ac-311b-4b6d-ad24-5d9422b2cee2
"""
import os, sys, json
import httpx
sys.path.insert(0, os.path.dirname(__file__))
from shard9_j_generator import (
    COUNTY_CONFIG, BASE, HEADERS, build_bid_decision, verify_county,
)

COUNTY = 'manatee'


def fetch_all_mca(client):
    rows, offset, page = [], 0, 1000
    params = {
        'select': 'case_number,parcel_id,property_address,auction_date,opening_bid,sale_type,market_value,assessed_value,po_market_value',
        'county': f'eq.{COUNTY}',
        'order': 'auction_date.desc',
    }
    while True:
        headers = {**HEADERS, 'Range-Unit': 'items', 'Range': f'{offset}-{offset+page-1}'}
        r = client.get(f'{BASE}/multi_county_auctions', headers=headers, params=params, timeout=120)
        if r.status_code not in (200, 206):
            raise SystemExit(f'fetch failed {r.status_code}: {r.text[:200]}')
        batch = r.json()
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return rows


def main():
    config = COUNTY_CONFIG[COUNTY]
    with httpx.Client(timeout=120) as client:
        rows = fetch_all_mca(client)
        print(f'manatee: fetched {len(rows)} MCA rows (paginated)')

        existing_cases = set()
        ex_headers = {**HEADERS}
        offset, page = 0, 1000
        while True:
            h = {**ex_headers, 'Range-Unit': 'items', 'Range': f'{offset}-{offset+page-1}'}
            rx = client.get(f'{BASE}/bid_decisions', headers=h,
                             params={'select': 'case_number', 'county_slug': f'eq.{COUNTY}'}, timeout=60)
            if rx.status_code not in (200, 206):
                raise SystemExit(f'existing fetch failed {rx.status_code}: {rx.text[:200]}')
            batch = rx.json()
            for rec in batch:
                existing_cases.add(rec['case_number'])
            if len(batch) < page:
                break
            offset += page
        print(f'manatee: {len(existing_cases)} existing bid_decisions')

        batch, total_inserted, errors = [], 0, 0
        for row in rows:
            if not row.get('case_number') or row['case_number'] in existing_cases:
                continue
            try:
                batch.append(build_bid_decision(row, COUNTY, config))
            except Exception as e:
                print(f'build error for {row.get("case_number")}: {e}')
                errors += 1
            if len(batch) >= 200:
                ins = client.post(f'{BASE}/bid_decisions', headers=HEADERS, content=json.dumps(batch), timeout=60)
                if ins.status_code >= 400:
                    print(f'insert failed {ins.status_code}: {ins.text[:300]}')
                    errors += 1
                else:
                    total_inserted += len(batch)
                    print(f'inserted {len(batch)} (running: {total_inserted})')
                batch = []
        if batch:
            ins = client.post(f'{BASE}/bid_decisions', headers=HEADERS, content=json.dumps(batch), timeout=60)
            if ins.status_code >= 400:
                print(f'insert failed {ins.status_code}: {ins.text[:300]}')
                errors += 1
            else:
                total_inserted += len(batch)

        print(f'manatee: DONE inserted={total_inserted} errors={errors}')
        ev = verify_county(COUNTY, client)
        print(json.dumps(ev.get('J', {}), indent=2))


if __name__ == '__main__':
    main()
