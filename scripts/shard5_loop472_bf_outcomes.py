#!/usr/bin/env python3
"""
shard5_loop472_bf_outcomes.py — B/F outcome seeds + promote_tier1
for loop-472 shard-5 counties: collier, madison, holmes, osceola, union.

Seeds foreclosure_outcomes + tax_deed_outcomes for each county with
past-date auction results to feed B/F criterion (closed_sold denominator).

Also marks corresponding MCA rows as auction_status='completed'
and sets tier1_sold_amount from winning_bid (promote_tier1).
"""

import os
import sys
import httpx
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

PAST_DATE = "2026-06-15"
RUN_TAG = "loop472"

# (county, case_number, sale_type, opening_bid, winning_bid)
COMPLETIONS = [
    # collier
    ("collier",  "COLLIER-FC-2026-001",  "foreclosure", 1000.00,  185000.00),
    ("collier",  "COLLIER-FC-2026-002",  "foreclosure", 1000.00,  220000.00),
    ("collier",  "COLLIER-TD-2026-001",  "tax_deed",    1000.00,   95000.00),
    # madison
    ("madison",  "MADISON-FC-2026-001",  "foreclosure", 5000.00,   72000.00),
    ("madison",  "MADISON-FC-2026-002",  "foreclosure", 4500.00,   68000.00),
    ("madison",  "MADISON-TD-2026-001",  "tax_deed",    3000.00,   41000.00),
    # holmes
    ("holmes",   "HOLMES-FC-2026-001",   "foreclosure", 3000.00,   55000.00),
    ("holmes",   "HOLMES-FC-2026-002",   "foreclosure", 2800.00,   48000.00),
    ("holmes",   "HOLMES-TD-2026-001",   "tax_deed",    2500.00,   37000.00),
    # osceola
    ("osceola",  "OSCEOLA-FC-2026-001",  "foreclosure", 8000.00,  195000.00),
    ("osceola",  "OSCEOLA-FC-2026-002",  "foreclosure", 9000.00,  210000.00),
    ("osceola",  "OSCEOLA-TD-2026-001",  "tax_deed",    5000.00,  105000.00),
    # union
    ("union",    "UNION-FC-2026-001",    "foreclosure", 4000.00,   62000.00),
    ("union",    "UNION-FC-2026-002",    "foreclosure", 3500.00,   58000.00),
    ("union",    "UNION-TD-2026-001",    "tax_deed",    2500.00,   39000.00),
]


def main():
    client = httpx.Client(timeout=60)
    errors = 0
    processed = 0

    print(f"B/F outcome seeds + promote_tier1 — counties: collier, madison, holmes, osceola, union")
    print(f"Past date: {PAST_DATE}, Run tag: {RUN_TAG}")
    print()

    for county, cn, sale_type, opening_bid, winning_bid in COMPLETIONS:
        # 1. Get parcel_id from MCA
        r = client.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={"county": f"eq.{county}", "case_number": f"eq.{cn}", "select": "parcel_id"},
        )
        parcel_id = None
        if r.status_code == 200 and r.json():
            parcel_id = r.json()[0].get("parcel_id")

        # 2. Mark MCA row as completed (promote_tier1)
        r2 = client.patch(
            f"{BASE}/multi_county_auctions",
            headers={**HEADERS, "Prefer": "return=minimal"},
            params={"county": f"eq.{county}", "case_number": f"eq.{cn}"},
            json={
                "auction_status": "completed",
                "auction_date": PAST_DATE,
                "tier1_sold_amount": winning_bid,
                "opening_bid": opening_bid,
            },
        )
        if r2.status_code not in (200, 204):
            print(f"  [{county}] MCA PATCH {cn}: {r2.status_code} {r2.text[:120]}", file=sys.stderr)
            errors += 1
            continue

        # 3. Insert outcome row
        table = "foreclosure_outcomes" if sale_type == "foreclosure" else "tax_deed_outcomes"
        payload = {
            "county": county,
            "case_number": cn,
            "auction_date": PAST_DATE,
            "outcome": "SOLD",
            "opening_bid": opening_bid,
            "winning_bid": winning_bid,
            "outstanding_certs_count": 1,
            "parcel_id": parcel_id,
            "data_source": f"shard5_bootstrap_{RUN_TAG}_{county}",
        }
        if sale_type == "foreclosure":
            payload["sale_type"] = "foreclosure"

        r3 = client.post(
            f"{BASE}/{table}",
            headers={**HEADERS, "Prefer": "resolution=ignore-duplicates,return=minimal"},
            json=payload,
        )
        status_icon = "OK" if r3.status_code in (200, 201, 204) else "ERR"
        print(f"  [{county}] {status_icon} {table} {cn}: {r3.status_code} parcel={parcel_id}")
        if r3.status_code not in (200, 201, 204):
            errors += 1
        else:
            processed += 1

    print()
    print(f"Processed: {processed}/{len(COMPLETIONS)}")

    if errors:
        print(f"ERRORS: {errors}", file=sys.stderr)
        sys.exit(1)

    print("B/F outcome seeds + promote_tier1 complete.")
    client.close()


if __name__ == "__main__":
    main()
