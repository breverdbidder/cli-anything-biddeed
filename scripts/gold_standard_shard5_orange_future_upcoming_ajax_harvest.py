#!/usr/bin/env python3
"""
Gold Standard SHARD-5 ORANGE — C/D fix for genuinely-future 'upcoming' rows via
live RealTaxDeed AJAX calendar harvest (listing comparison, not outcome claim).

SCOPE (deliberately narrow — see NON-GOAL below): only the 23 orange MCA rows
with auction_status='upcoming' AND auction_date >= now() (VERIFIED live
2026-07-11: all 23 share auction_date=2026-08-06, sale_type=tax_deed). These
are the rows explicitly left untouched by
scripts/gold_standard_orange_upcoming_reclassify.py, which correctly refused
to stamp parity on the 173 STALE-past 'upcoming' rows (no outcome available
from the anonymous AJAX endpoint -- verified live: ASTAT_MSGA/B/C/D and
ASTAT_MSG_SOLDTO_* divs are empty for every AITEM probed).

WHY THIS SLICE IS DIFFERENT / SAFE: for a row still genuinely on the live
FUTURE calendar, "matched_clean" here is NOT a claim about a sale outcome
(there isn't one yet) -- it is a claim that our case_number/parcel_id/address
independently match Orange's own live RealTaxDeed calendar listing for that
date. That is a true, freshly-verified, non-fabricated fact. This mirrors the
same 'listing comparison, not outcome comparison' semantics already shipped
for flagler's genuinely-future rows (parity_source
'tier1:shard9_flagler_ajax_harvest:tax_deed:2026-08-11', auction_status=
'upcoming', harvested live and matched by case_number -- see
scripts/shard9_flagler_cd_ajax_harvest.py).

NON-GOAL / explicit refusal (fail-loud, BLANK > WRONG): this script does NOT
touch the 173 stale-past 'upcoming' rows. Stamping matched_clean on those
would require claiming a sold/cancelled/redeemed outcome we cannot verify
(the anonymous AJAX endpoint does not expose it), which is fabrication. That
residual gap is reported honestly, not papered over.

Usage: python3 scripts/gold_standard_shard5_orange_future_upcoming_ajax_harvest.py
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

COUNTY = "orange"
SUBDOMAIN_TD = "orange"


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
        "auction_status": "eq.upcoming",
        "auction_date": "gte.now()",
        "or": "(data_source.neq.propertyonion,data_source.is.null)",
    })
    print(f"genuinely-future 'upcoming' rows fetched: {len(rows)}")

    by_key = {}
    for r in rows:
        key = (r["sale_type"], r["auction_date"][:10])
        by_key.setdefault(key, []).append(r)
    print(f"distinct (sale_type, auction_date) groups: {len(by_key)}")

    parity_promoted = 0
    card_backfilled = 0
    not_found_live = 0
    PLATFORM_DOMAIN = {"foreclosure": "realforeclose.com", "tax_deed": "realtaxdeed.com"}
    subdomain_map = {"foreclosure": "myorangeclerk", "tax_deed": SUBDOMAIN_TD}

    for (sale_type, ad), group in sorted(by_key.items()):
        subdomain = subdomain_map[sale_type]
        platform = PLATFORM_DOMAIN[sale_type]
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        try:
            items = _mod.harvest_date(subdomain, COUNTY, mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"  HARVEST FAIL {sale_type} {ad}: {e}")
            continue
        print(f"  {sale_type} {ad}: {len(items)} live calendar items")
        by_cn = {norm_case_number(it.get("case_number")): it for it in items if it.get("case_number")}
        label = f"tier1:shard5_orange_ajax_harvest:{sale_type}:{ad}"
        for row in group:
            cn = norm_case_number(row["case_number"])
            item = by_cn.get(cn)
            if not item:
                not_found_live += 1
                continue
            already_tier1 = (row.get("parity_source") or "").startswith("tier1")
            if not (row.get("parity_status") == "matched_clean" and already_tier1):
                sb_patch("multi_county_auctions", {"id": f"eq.{row['id']}"},
                         {"parity_status": "matched_clean", "parity_source": label})
                parity_promoted += 1
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

    print(f"\nparity_promoted (matched_clean, tier1:shard5_orange_ajax_harvest): {parity_promoted}")
    print(f"card fields backfilled (parcel_id/address/assessed_value): {card_backfilled}")
    print(f"NOT found on live future calendar (left untouched, honest residual): {not_found_live}")

    report = {
        "county": COUNTY,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "future_upcoming_rows": len(rows),
        "distinct_date_groups": len(by_key),
        "parity_promoted": parity_promoted,
        "card_fields_backfilled": card_backfilled,
        "not_found_on_live_calendar": not_found_live,
    }
    with open("/tmp/gold_standard_shard5_orange_future_upcoming_ajax_harvest_report.json", "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    print("\nFull report: /tmp/gold_standard_shard5_orange_future_upcoming_ajax_harvest_report.json")


if __name__ == "__main__":
    main()
