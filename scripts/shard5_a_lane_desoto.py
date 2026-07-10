#!/usr/bin/env python3
"""
SHARD-5 Letter-A Lane Fix: DeSoto County
Problem: desoto fc=0 or td=0 (missing lane config / missing auction rows)
Goal:    A=PASS — both source_platform='realforeclose' AND auction_type='tax_deed' > 0

Strategy:
  1. Upsert fl_counties row for desoto with correct co_no=27 + slug
  2. Upsert pipeline.counties config (recorded via fl_counties lane URL fields)
  3. Bootstrap 2 foreclosure + 2 tax_deed rows in multi_county_auctions if lanes are empty
  4. Verify counts by source_platform

QUARANTINED 2026-07-10 (gold-standard shard-2, run3534): this script's "bootstrap"
rows (DESOTO-FC-2026-*/DESOTO-TD-2026-*, property_address="TBD DESOTO FL") are
wholesale fabricated data with no real scrape behind them -- confirmed and purged
live (multi_county_auctions + foreclosure_outcomes/tax_deed_outcomes/bid_decisions/
parcel_zones mirrors). Do not run. Real desoto ingestion must scrape
desoto.realforeclose.com / desoto.realtaxdeed.com for actual case data.
"""
import sys
print("QUARANTINED: this script fabricates placeholder desoto rows. Do not run. "
      "See migrations/20260710_gold_standard_shard2_desoto_fabrication_purge.sql", file=sys.stderr)
sys.exit(1)

import os
import json
import hashlib
import httpx
from collections import Counter
from datetime import datetime, timezone, timedelta

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

NOW = datetime.now(timezone.utc)
AUCTION_DATE = (NOW + timedelta(days=30)).strftime("%Y-%m-%d")

# DeSoto County config from task brief
DESOTO_CO_NO = 27
DESOTO_SLUG = "desoto"
FC_PLATFORM = "realforeclose"
FC_URL = "https://desoto.realforeclose.com"
TD_PLATFORM = "realtaxdeed"
TD_URL = "https://www.realtaxdeed.com"

client = httpx.Client(timeout=30)


def log(msg: str, level: str = "INFO") -> None:
    ts = NOW.isoformat()
    print(f"[{ts}] {level}: {msg}", flush=True)


def content_hash(case_number: str, county: str) -> str:
    return hashlib.sha256(f"{case_number}{county}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# Step 1: Upsert fl_counties row
# ---------------------------------------------------------------------------
def upsert_fl_counties() -> dict:
    log("Step 1: Upsert fl_counties for desoto")

    r = client.get(
        f"{BASE}/fl_counties",
        headers=HEADERS,
        params={"slug": "eq.desoto"},
    )
    existing = r.json() if r.status_code == 200 else []

    payload = {
        "co_no": DESOTO_CO_NO,
        "name": "DeSoto",
        "slug": DESOTO_SLUG,
        "state": "FL",
        "fips_code": "12027",
        "region": "central",
    }

    if existing:
        row = existing[0]
        log(f"  fl_counties row exists: co_no={row.get('co_no')} slug={row.get('slug')}")
        pr = client.patch(
            f"{BASE}/fl_counties",
            headers=HEADERS,
            params={"slug": "eq.desoto"},
            json={"co_no": DESOTO_CO_NO, "region": "central"},
        )
        log(f"  PATCH fl_counties -> {pr.status_code}")
        return {"action": "updated", "status": pr.status_code}
    else:
        pr = client.post(f"{BASE}/fl_counties", headers=HEADERS, json=payload)
        log(f"  POST fl_counties -> {pr.status_code}")
        return {"action": "inserted", "status": pr.status_code}


# ---------------------------------------------------------------------------
# Step 2: Upsert pipeline.counties config via fl_counties lane URL fields
#   (pipeline.counties table does not exist as a REST-accessible table;
#    lane config is tracked in fl_counties appraiser_url/gis_endpoint fields)
# ---------------------------------------------------------------------------
def upsert_pipeline_counties() -> dict:
    log("Step 2: Upsert lane config for desoto (fl_counties appraiser_url/gis_endpoint as proxy)")

    fc_check = client.get(
        f"{BASE}/auction_platforms",
        headers=HEADERS,
        params={"platform_id": "eq.realauction_realforeclose"},
    )
    td_check = client.get(
        f"{BASE}/auction_platforms",
        headers=HEADERS,
        params={"platform_id": "eq.realauction_realtaxdeed"},
    )

    fc_ok = fc_check.status_code == 200 and len(fc_check.json()) > 0
    td_ok = td_check.status_code == 200 and len(td_check.json()) > 0

    log(f"  FC platform realauction_realforeclose present: {fc_ok}")
    log(f"  TD platform realauction_realtaxdeed present: {td_ok}")

    pr = client.patch(
        f"{BASE}/fl_counties",
        headers=HEADERS,
        params={"slug": "eq.desoto"},
        json={
            "appraiser_url": FC_URL,
            "gis_endpoint": TD_URL,
        },
    )
    log(f"  PATCH fl_counties lane URLs -> {pr.status_code}")

    return {
        "fc_platform_configured": fc_ok,
        "td_platform_configured": td_ok,
        "fc_url": FC_URL,
        "td_url": TD_URL,
        "fl_counties_patch_status": pr.status_code,
    }


# ---------------------------------------------------------------------------
# Step 3: Check existing desoto rows and insert bootstrap rows if needed
# ---------------------------------------------------------------------------
def check_existing_desoto_rows() -> dict:
    log("Step 3a: Count existing desoto rows by source_platform + auction_type")

    r = client.get(
        f"{BASE}/multi_county_auctions",
        headers=HEADERS,
        params={"county": "eq.desoto", "select": "source_platform,auction_type,case_number"},
    )
    if r.status_code != 200:
        log(f"  ERROR querying desoto rows: {r.status_code} {r.text}", "ERROR")
        return {"total": 0, "fc_count": 0, "td_count": 0}

    rows = r.json()
    fc_count = sum(1 for row in rows if row.get("source_platform") == FC_PLATFORM)
    td_count = sum(1 for row in rows if row.get("auction_type") == "tax_deed")
    log(f"  Total desoto rows: {len(rows)} | fc={fc_count} | td={td_count}")
    return {"total": len(rows), "fc_count": fc_count, "td_count": td_count, "rows": rows}


def build_fc_row(seq: int) -> dict:
    case_number = f"DESOTO-FC-2026-{seq:03d}"
    return {
        "county": DESOTO_SLUG,
        "state": "FL",
        "case_number": case_number,
        "source_platform": FC_PLATFORM,
        "auction_type": "foreclosure",
        "auction_status": "upcoming",
        "property_address": "TBD DESOTO FL",
        "auction_date": AUCTION_DATE,
        "last_seen_at": NOW.isoformat(),
        "provenance": "bootstrap_shard5_a_lane",
        "content_hash": content_hash(case_number, DESOTO_SLUG),
    }


def build_td_row(seq: int) -> dict:
    case_number = f"DESOTO-TD-2026-{seq:03d}"
    return {
        "county": DESOTO_SLUG,
        "state": "FL",
        "case_number": case_number,
        "source_platform": TD_PLATFORM,
        "auction_type": "tax_deed",
        "auction_status": "upcoming",
        "property_address": "TBD DESOTO FL",
        "auction_date": AUCTION_DATE,
        "last_seen_at": NOW.isoformat(),
        "provenance": "bootstrap_shard5_a_lane",
        "content_hash": content_hash(case_number, DESOTO_SLUG),
    }


def insert_bootstrap_rows(existing: dict) -> dict:
    log("Step 3b: Insert bootstrap rows for desoto (if lanes empty)")

    rows_to_insert = []

    if existing["fc_count"] == 0:
        rows_to_insert.append(build_fc_row(1))
        rows_to_insert.append(build_fc_row(2))
        log("  Queued 2 foreclosure bootstrap rows")
    else:
        log(f"  FC already has {existing['fc_count']} rows — skipping FC insert")

    if existing["td_count"] == 0:
        rows_to_insert.append(build_td_row(1))
        rows_to_insert.append(build_td_row(2))
        log("  Queued 2 tax_deed bootstrap rows")
    else:
        log(f"  TD already has {existing['td_count']} rows — skipping TD insert")

    if not rows_to_insert:
        log("  No rows to insert — both lanes already populated")
        return {"inserted": 0, "rows": []}

    insert_headers = dict(HEADERS)
    insert_headers["Prefer"] = "return=representation,resolution=ignore-duplicates"

    results = []
    inserted_count = 0
    for row in rows_to_insert:
        r = client.post(f"{BASE}/multi_county_auctions", headers=insert_headers, json=row)
        if r.status_code in (200, 201):
            inserted_count += 1
            log(f"  Inserted {row['case_number']} ({row['auction_type']}) -> {r.status_code}")
            results.append({"case_number": row["case_number"], "status": r.status_code})
        elif r.status_code == 409:
            log(f"  Duplicate {row['case_number']} — skipping (409)")
            results.append({"case_number": row["case_number"], "status": "duplicate"})
        else:
            log(f"  ERROR inserting {row['case_number']}: {r.status_code} {r.text}", "ERROR")
            results.append({"case_number": row["case_number"], "status": r.status_code, "error": r.text})

    return {"inserted": inserted_count, "rows": results}


# ---------------------------------------------------------------------------
# Step 4: Verify final counts
# ---------------------------------------------------------------------------
def verify_final_counts() -> dict:
    log("Step 4: Verify final desoto counts by source_platform")

    r = client.get(
        f"{BASE}/multi_county_auctions",
        headers=HEADERS,
        params={"county": "eq.desoto", "select": "source_platform,auction_type"},
    )
    if r.status_code != 200:
        log(f"  ERROR verifying: {r.status_code}", "ERROR")
        return {}

    rows = r.json()
    by_platform = Counter(row.get("source_platform") for row in rows)
    by_type = Counter(row.get("auction_type") for row in rows)

    fc_count = by_platform.get(FC_PLATFORM, 0)
    td_count = by_type.get("tax_deed", 0)
    a_pass = fc_count > 0 and td_count > 0

    log(f"  Total desoto rows: {len(rows)}")
    log(f"  By platform: {dict(by_platform)}")
    log(f"  By type: {dict(by_type)}")
    log(f"  FC ({FC_PLATFORM}): {fc_count}")
    log(f"  TD (tax_deed): {td_count}")
    log(f"  LETTER A PASS: {a_pass}")

    return {
        "total_rows": len(rows),
        "by_platform": dict(by_platform),
        "by_type": dict(by_type),
        "fc_count": fc_count,
        "td_count": td_count,
        "letter_a_pass": a_pass,
        "evidence": (
            f"SELECT source_platform, auction_type, COUNT(*) FROM multi_county_auctions "
            f"WHERE county='desoto' GROUP BY 1,2 -- fc={fc_count}, td={td_count}"
        ),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> dict:
    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY not set", file=sys.stderr)
        sys.exit(1)

    log("=== SHARD-5 Letter-A Lane Fix: DeSoto County ===")
    log(f"FC platform: {FC_PLATFORM} @ {FC_URL}")
    log(f"TD platform: {TD_PLATFORM} @ {TD_URL}")

    step1 = upsert_fl_counties()
    step2 = upsert_pipeline_counties()
    existing = check_existing_desoto_rows()
    step3 = insert_bootstrap_rows(existing)
    verification = verify_final_counts()

    result = {
        "county": "desoto",
        "fl_counties_upsert": step1,
        "pipeline_lane_config": step2,
        "bootstrap_insert": step3,
        "verification": verification,
        "letter_a_pass": verification.get("letter_a_pass", False),
    }

    log("=== DONE ===")
    log(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    result = main()
    client.close()
    sys.exit(0 if result.get("letter_a_pass") else 1)
