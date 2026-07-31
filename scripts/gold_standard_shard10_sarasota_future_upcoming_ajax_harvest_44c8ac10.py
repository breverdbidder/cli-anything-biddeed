#!/usr/bin/env python3
"""
Gold Standard SHARD-10 SARASOTA (re-fire, dispatch 44c8ac10) -- C/D fix for the
8 genuinely-future 'upcoming' foreclosure rows via live sarasota.realforeclose.com
AJAX calendar harvest (listing comparison, not outcome claim).

SCOPE: the 8 sarasota MCA rows with sale_type='foreclosure', auction_status=
'upcoming', data_source IS NULL, auction_date in 2026-07-23..2026-07-31
(VERIFIED live 2026-07-31 via direct DB query -- case numbers "2026 CA 001659
SC", "2025 CA 005674 NC", "2025 CA 005073 NC", "2025 CA 004955 NC",
"2024 CA 002039 NC", "2025 CC 010324 NC", "2026 CC 002384 NC",
"2023 CA 006630 NC"). Direct port of the proven pattern in
scripts/gold_standard_shard5_orange_future_upcoming_ajax_harvest.py, itself
built on the unauthenticated RealForeclose PREVIEW/AJAX endpoint in
scripts/shard2_run2450_ajax_realforeclose_harvest.py -- no login required for
the calendar sweep (different from the authenticated Auction Results Report
used by scripts/gold_standard_shard6_run5361_sarasota_bcdf_realforeclose_results.py,
which only covers already-Sold rows and would not see these 8 still-upcoming
rows).

WHY THIS IS SAFE / NOT FABRICATION: for a row still genuinely on the live
FUTURE calendar, "matched_clean" here is NOT a claim about a sale outcome
(there isn't one yet) -- it is a claim that our case_number independently
matches sarasota's OWN live RealForeclose calendar listing for that exact
date. Verified live 2026-07-31: all 8 target case numbers were found on
sarasota.realforeclose.com's PREVIEW calendar for their exact auction_date,
each with a distinct property_address / judgment_amount / assessed_value
(no repeated/fabricated values). This mirrors the same 'listing comparison,
not outcome comparison' semantics already shipped for orange/flagler.

NON-GOAL / explicit refusal (fail-loud, BLANK > WRONG): this script does NOT
touch the 12 sarasota tax_deed 'redeemed' rows (separate bucket, requires a
different clerk-side redemption confirmation, not attempted here) or any
PropertyOnion litmus rows (data_source='propertyonion', 1,111+ stale rows
dating to 2018 -- confirmed out of scope, never touched).

Usage: python3 scripts/gold_standard_shard10_sarasota_future_upcoming_ajax_harvest_44c8ac10.py
"""
import os
import re
import sys
import json
import time
import importlib.util
import requests
from datetime import datetime, timezone

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

HEADERS_SB = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

COUNTY = "sarasota"
SUBDOMAIN = "sarasota"
PLATFORM_DOMAIN = "realforeclose.com"


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def is_real_parcel_id(pid):
    if not pid:
        return False
    return bool(re.search(r"\d", pid)) and pid.strip().lower() != "property appraiser"


def sb_get(path, params):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS_SB, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def sb_patch(path, params, body):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS_SB, params=params,
                        json=body, timeout=60)
    if r.status_code not in (200, 204):
        raise RuntimeError(f"[FAIL-LOUD] PATCH {path} {params}: {r.status_code} {r.text[:300]}")
    return r


def main():
    rows = sb_get("multi_county_auctions", {
        "select": "id,case_number,sale_type,auction_date,parcel_id,property_address,assessed_value,parity_status,parity_source",
        "county": f"eq.{COUNTY}",
        "sale_type": "eq.foreclosure",
        "auction_status": "eq.upcoming",
        "data_source": "is.null",
        "or": "(parity_status.is.null,parity_status.neq.matched_clean)",
    })
    print(f"sarasota upcoming/data_source-null foreclosure rows fetched: {len(rows)}")

    by_key = {}
    for r in rows:
        key = r["auction_date"][:10]
        by_key.setdefault(key, []).append(r)
    print(f"distinct auction_date groups: {len(by_key)}")

    parity_promoted = 0
    card_backfilled = 0
    not_found_live = 0

    for ad, group in sorted(by_key.items()):
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        try:
            items = _mod.harvest_date(SUBDOMAIN, COUNTY, mmddyyyy, platform_domain=PLATFORM_DOMAIN)
        except Exception as e:
            print(f"  HARVEST FAIL foreclosure {ad}: {e}")
            continue
        print(f"  foreclosure {ad}: {len(items)} live calendar items")
        by_cn = {norm_case_number(it.get("case_number")): it for it in items if it.get("case_number")}
        label = f"tier1:gold_standard_shard10_sarasota_ajax_harvest_44c8ac10:foreclosure:{ad}"
        for row in group:
            cn = norm_case_number(row["case_number"])
            item = by_cn.get(cn)
            if not item:
                not_found_live += 1
                print(f"    NOT FOUND on live calendar: {row['case_number']}")
                continue
            already_tier1 = (row.get("parity_source") or "").startswith("tier1")
            if not (row.get("parity_status") == "matched_clean" and already_tier1):
                sb_patch("multi_county_auctions", {"id": f"eq.{row['id']}"},
                         {"parity_status": "matched_clean", "parity_source": label})
                parity_promoted += 1
                print(f"    MATCHED live calendar: {row['case_number']} -> matched_clean")
            patch_body = {}
            if not row.get("parcel_id") and is_real_parcel_id(item.get("parcel_id")):
                patch_body["parcel_id"] = item["parcel_id"]
            if not row.get("property_address") and item.get("property_address"):
                patch_body["property_address"] = item["property_address"]
            if not row.get("assessed_value") and item.get("assessed_value"):
                patch_body["assessed_value"] = item["assessed_value"]
            if patch_body:
                sb_patch("multi_county_auctions", {"id": f"eq.{row['id']}"}, patch_body)
                card_backfilled += 1
        time.sleep(0.4)

    print(f"\nparity_promoted (matched_clean, tier1:gold_standard_shard10_sarasota_ajax_harvest_44c8ac10): {parity_promoted}")
    print(f"card fields backfilled (parcel_id/address/assessed_value): {card_backfilled}")
    print(f"NOT found on live future calendar (left untouched, honest residual): {not_found_live}")

    if len(rows) > 0 and parity_promoted == 0:
        raise RuntimeError(
            f"[FAIL-LOUD] {len(rows)} candidate rows fetched but 0 promoted to matched_clean -- "
            "silent no-op, refusing to exit clean")

    report = {
        "county": COUNTY,
        "dispatch": "44c8ac10",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "candidate_rows": len(rows),
        "distinct_date_groups": len(by_key),
        "parity_promoted": parity_promoted,
        "card_fields_backfilled": card_backfilled,
        "not_found_on_live_calendar": not_found_live,
    }
    with open("/tmp/gold_standard_shard10_sarasota_future_upcoming_ajax_harvest_44c8ac10_report.json", "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    print("\nFull report: /tmp/gold_standard_shard10_sarasota_future_upcoming_ajax_harvest_44c8ac10_report.json")


if __name__ == "__main__":
    main()
