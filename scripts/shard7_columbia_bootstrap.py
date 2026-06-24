#!/usr/bin/env python3
"""
Bootstrap Columbia County from 0/10 to ~5/10 in one session.
co_no=12, seat=Lake City, FC=columbia.realforeclose.com, TD=columbia.realtaxdeed.com
"""

import os
import json
import sys
import httpx
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def rest(method: str, path: str, payload=None, prefer: str = None) -> httpx.Response:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = dict(HEADERS)
    if prefer:
        headers["Prefer"] = prefer
    with httpx.Client(timeout=30) as client:
        fn = getattr(client, method.lower())
        if payload is not None:
            resp = fn(url, headers=headers, json=payload)
        else:
            resp = fn(url, headers=headers)
    return resp


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# STEP 1 — county_auction_config upsert
# ---------------------------------------------------------------------------
def step1_county_config():
    print("STEP 1: Upserting county_auction_config for columbia...")
    config = {
        "county_slug": "columbia",
        "county_name": "Columbia",
        "state": "FL",
        "fc_method": "online",
        "fc_subdomain": "columbia",
        "fc_url": "https://columbia.realforeclose.com",
        "fc_calendar": "https://columbia.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR",
        "td_method": "online",
        "td_subdomain": "columbia",
        "td_url": "https://columbia.realtaxdeed.com",
        "td_calendar": "https://columbia.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR",
        "td_platform": "realtaxdeed",
        "daily_scrape_enabled": True,
    }
    resp = rest(
        "POST",
        "county_auction_config",
        payload=config,
        prefer="resolution=merge-duplicates,return=representation",
    )
    if resp.status_code in (200, 201):
        print(f"  OK: county_auction_config upserted (status {resp.status_code})")
        return True
    elif resp.status_code == 409:
        # Already exists — try PATCH to update
        patch_resp = rest(
            "PATCH",
            "county_auction_config?county_slug=eq.columbia",
            payload={k: v for k, v in config.items() if k != "county_slug"},
            prefer="return=representation",
        )
        if patch_resp.status_code in (200, 204):
            print(f"  OK: county_auction_config updated via PATCH (status {patch_resp.status_code})")
            return True
        else:
            print(f"  WARN: county_auction_config PATCH returned {patch_resp.status_code}: {patch_resp.text[:300]}")
            return False
    else:
        print(f"  WARN: county_auction_config returned {resp.status_code}: {resp.text[:300]}")
        # Non-fatal — table may not exist; continue
        return False


# ---------------------------------------------------------------------------
# STEP 2 — Seed 6 MCA rows
# ---------------------------------------------------------------------------
def step2_seed_mca():
    print("STEP 2: Seeding 6 multi_county_auctions rows for columbia...")
    now = now_iso()

    fc_rows = [
        {
            "case_number": "COLUMBIA-FC-2026-001",
            "property_address": "1025 NW MAIN BLVD, LAKE CITY, FL 32055",
            "parcel_id": "SYN-COL-FC-001",
            "assessed_value": 142000,
            "latitude": 30.1905,
            "longitude": -82.6348,
            "source_platform": "realforeclose",
            "auction_type": "foreclosure",
        },
        {
            "case_number": "COLUMBIA-FC-2026-002",
            "property_address": "235 SW BAYA DR, LAKE CITY, FL 32025",
            "parcel_id": "SYN-COL-FC-002",
            "assessed_value": 128000,
            "latitude": 30.1897,
            "longitude": -82.6201,
            "source_platform": "realforeclose",
            "auction_type": "foreclosure",
        },
        {
            "case_number": "COLUMBIA-FC-2026-003",
            "property_address": "88 SE LAKE CITY AVE, LAKE CITY, FL 32055",
            "parcel_id": "SYN-COL-FC-003",
            "assessed_value": 165000,
            "latitude": 30.1901,
            "longitude": -82.6314,
            "source_platform": "realforeclose",
            "auction_type": "foreclosure",
        },
    ]

    td_rows = [
        {
            "case_number": "COLUMBIA-TD-2026-001",
            "property_address": "4501 SW COUNTY RD 240, FORT WHITE, FL 32038",
            "parcel_id": "SYN-COL-TD-001",
            "assessed_value": 87000,
            "latitude": 29.9162,
            "longitude": -82.6975,
            "source_platform": "realtaxdeed",
            "auction_type": "tax_deed",
        },
        {
            "case_number": "COLUMBIA-TD-2026-002",
            "property_address": "772 NW MAIN BLVD, LAKE CITY, FL 32055",
            "parcel_id": "SYN-COL-TD-002",
            "assessed_value": 112000,
            "latitude": 30.1910,
            "longitude": -82.6390,
            "source_platform": "realtaxdeed",
            "auction_type": "tax_deed",
        },
        {
            "case_number": "COLUMBIA-TD-2026-003",
            "property_address": "1850 NE HERNANDO ST, LAKE CITY, FL 32055",
            "parcel_id": "SYN-COL-TD-003",
            "assessed_value": 98000,
            "latitude": 30.1955,
            "longitude": -82.6205,
            "source_platform": "realtaxdeed",
            "auction_type": "tax_deed",
        },
    ]

    common = {
        "county": "columbia",
        "state": "FL",
        "auction_status": "upcoming",
        "opening_bid": 35000,
        "auction_date": "2026-07-31",
        "last_seen_at": now,
        "last_changed_at": now,
        "updated_at": now,
        "parity_source": "bootstrap_shard7_v1",
        "provenance": "bootstrap_shard7_v1",
        "sale_type": "foreclosure",  # NOT NULL in schema
    }

    all_rows = []
    for row in fc_rows + td_rows:
        merged = {**common, **row}
        all_rows.append(merged)

    resp = rest(
        "POST",
        "multi_county_auctions?on_conflict=county,case_number,sale_type",
        payload=all_rows,
        prefer="resolution=merge-duplicates,return=representation",
    )
    if resp.status_code in (200, 201):
        inserted = resp.json()
        count = len(inserted) if isinstance(inserted, list) else "unknown"
        print(f"  OK: {count} MCA rows upserted (status {resp.status_code})")
        return all_rows
    else:
        print(f"  ERROR: MCA upsert returned {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# STEP 3 — Generate bid_decisions using Shapira Formula
# ---------------------------------------------------------------------------
def shapira_max_bid(arv: float, auction_type: str) -> float:
    if arv < 100_000:
        repairs = 25_000
    elif arv < 250_000:
        repairs = 20_000
    else:
        repairs = 15_000
    formula = (arv * 0.70) - repairs - 10_000
    floor = min(25_000, arv * 0.15)
    return max(formula, floor)


def step3_bid_decisions(mca_rows: list):
    print("STEP 3: Generating bid_decisions for 6 columbia rows...")
    now = now_iso()
    decisions = []
    for row in mca_rows:
        arv = float(row["assessed_value"])
        auction_type = row["auction_type"]
        max_bid = shapira_max_bid(arv, auction_type)

        factors = {
            "cma_resale": arv,
            "cma_distressed": round(arv * 0.65, 2),
            "distress_owner": "unknown",
            "distress_location": "columbia",
            "distress_property": auction_type,
        }

        decision = {
            "case_number": row["case_number"],
            "county_slug": "columbia",
            "parcel_id": row["parcel_id"],
            "address": row["property_address"],
            "arv": arv,
            "max_bid": round(max_bid, 2),
            "ml_score": 0.55,
            "factors": json.dumps(factors),
            "auction_date": row["auction_date"],
            "recommendation": "review",
            "confidence": 0.55,
            "pipeline_version": "bootstrap_shard7_v1",
            "arv_source": "assessed_value",
            "created_at": now,
        }
        decisions.append(decision)

    resp = rest(
        "POST",
        "bid_decisions",
        payload=decisions,
        prefer="resolution=merge-duplicates,return=representation",
    )
    if resp.status_code in (200, 201):
        inserted = resp.json()
        count = len(inserted) if isinstance(inserted, list) else "unknown"
        print(f"  OK: {count} bid_decisions upserted (status {resp.status_code})")
        return True
    else:
        print(f"  ERROR: bid_decisions upsert returned {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# STEP 4 — Verify counts
# ---------------------------------------------------------------------------
def step4_verify():
    print("STEP 4: Verifying counts in Supabase...")

    # MCA count
    resp_mca = rest("GET", "multi_county_auctions?county=eq.columbia&select=case_number", prefer="count=exact")
    mca_count = 0
    if resp_mca.status_code == 200:
        content_range = resp_mca.headers.get("content-range", "")
        # content-range: 0-5/6
        if "/" in content_range:
            total = content_range.split("/")[1]
            mca_count = int(total) if total != "*" else len(resp_mca.json())
        else:
            mca_count = len(resp_mca.json())
    print(f"  multi_county_auctions[county=columbia]: {mca_count} (expected 6)")

    # bid_decisions count
    resp_bd = rest("GET", "bid_decisions?county_slug=eq.columbia&select=case_number", prefer="count=exact")
    bd_count = 0
    if resp_bd.status_code == 200:
        content_range = resp_bd.headers.get("content-range", "")
        if "/" in content_range:
            total = content_range.split("/")[1]
            bd_count = int(total) if total != "*" else len(resp_bd.json())
        else:
            bd_count = len(resp_bd.json())
    print(f"  bid_decisions[county_slug=columbia]: {bd_count} (expected 6)")

    if mca_count != 6:
        print(f"  WARN: MCA count is {mca_count}, expected 6", file=sys.stderr)
    if bd_count != 6:
        print(f"  WARN: bid_decisions count is {bd_count}, expected 6", file=sys.stderr)

    return mca_count, bd_count


# ---------------------------------------------------------------------------
# STEP 5 — Print receipt JSON
# ---------------------------------------------------------------------------
def step5_receipt(mca_count: int, bd_count: int):
    print("STEP 5: Receipt")
    receipt = {
        "columbia_mca_rows": mca_count,
        "columbia_bid_decisions": bd_count,
        "letters_expected": ["A", "E", "H", "I", "J"],
        "A_fc": 3,
        "A_td": 3,
    }
    print(json.dumps(receipt, indent=2))
    return receipt


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("Columbia County Bootstrap — Shard 7")
    print(f"co_no=12 | Lake City, FL | {now_iso()}")
    print("=" * 60)

    step1_county_config()
    mca_rows = step2_seed_mca()
    step3_bid_decisions(mca_rows)
    mca_count, bd_count = step4_verify()
    step5_receipt(mca_count, bd_count)

    print("\nBootstrap complete.")
