#!/usr/bin/env python3
"""
Gold Standard ORANGE — reclassify stale 'upcoming' rows via live RealAuction re-harvest.

ROOT CAUSE (VERIFIED live 2026-07-11): 196 orange MCA rows sit at
auction_status='upcoming' with parity_status=NULL. Of these, 173 have an
auction_date already in the PAST relative to today (2026-07-11) — meaning the
scraper never came back to re-check what actually happened to them (sold /
cancelled / redeemed), and they are frozen on a stale 'upcoming' label. Per the
campaign brief's explicit warning, these must NOT be blind-stamped as tier1
evidence just because a calendar entry exists (unlike the manatee
calendar_sweep_mca_v3 precedent, which was for rows still genuinely on the
live/future calendar) — a stale 'upcoming' row for a PAST date needs its real
current status looked up.

This script re-harvests the live RealForeclose/RealTaxDeed AJAX calendar
(AREA=C, i.e. "completed"/past auctions, using the proven
scripts/shard2_run2450_ajax_realforeclose_harvest.py:harvest_date mechanism)
for each distinct (sale_type, auction_date) among these 173 stale rows, and:
  - if the case_number is still present on the live completed-auctions list for
    that date, we now know real parcel_id/property_address/assessed_value
    (useful for E/I card completeness) but the AJAX endpoint does NOT expose an
    anonymous sold/cancelled/redeemed status (VERIFIED live 2026-07-11 — see
    gold_standard_orange_bcd_outcomes_backfill.py docstring for the ASTAT-empty
    finding), so we CANNOT determine a real outcome this way either.
  - This script therefore does NOT stamp parity_status for these rows. It only
    opportunistically backfills real parcel_id/property_address/assessed_value
    where the live re-harvest confirms them and the MCA row is missing them
    (card-completeness assist for I), and reports exactly how many stale
    'upcoming' rows it could/could not re-confirm on the live calendar.
  - The 23 genuinely-future 'upcoming' rows (auction_date >= now()) are left
    untouched — those are correctly labeled and are real future calendar
    entries, consistent with the manatee precedent, but stamping parity on a
    FUTURE unresolved auction would be a false claim of a determinate outcome
    that hasn't happened yet, so they are correctly excluded from C/D matching
    by refresh_parity_tier1_outcomes()'s own auction_status IN (...) filter
    (which does not include 'upcoming') — nothing to do here, by design.

NEVER-LIE: this script does not fabricate a sold/cancelled/redeemed outcome for
any of the 173 stale rows. If the residual gap in C/D remains after this
script (it will), that is the honest, reported residual for this session —
BLANK > WRONG.

Usage: python3 scripts/gold_standard_orange_upcoming_reclassify.py
"""
import os
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

PLATFORM_DOMAIN = {"foreclosure": "realforeclose.com", "tax_deed": "realtaxdeed.com"}
COUNTY = "orange"
SUBDOMAIN_FC = "myorangeclerk"
SUBDOMAIN_TD = "orange"


def norm_case_number(cn):
    import re
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


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
        "select": "id,case_number,sale_type,auction_date,parcel_id,property_address,assessed_value,data_source",
        "county": f"eq.{COUNTY}",
        "auction_status": "eq.upcoming",
        "auction_date": "lt.now()",
        "or": "(data_source.neq.propertyonion,data_source.is.null)",
    })
    print(f"stale 'upcoming' (auction_date < now()) rows fetched: {len(rows)}")

    by_key = {}
    for r in rows:
        key = (r["sale_type"], r["auction_date"][:10])
        by_key.setdefault(key, []).append(r)

    print(f"distinct (sale_type, auction_date) to re-harvest: {len(by_key)}")

    reconfirmed = 0
    not_found_live = 0
    card_backfilled = 0
    subdomain_map = {"foreclosure": SUBDOMAIN_FC, "tax_deed": SUBDOMAIN_TD}

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
        by_cn = {norm_case_number(it.get("case_number")): it for it in items if it.get("case_number")}
        for row in group:
            cn = norm_case_number(row["case_number"])
            item = by_cn.get(cn)
            if not item:
                not_found_live += 1
                continue
            reconfirmed += 1
            patch_body = {}
            if not row.get("parcel_id") and item.get("parcel_id"):
                patch_body["parcel_id"] = item["parcel_id"]
            if not row.get("property_address") and item.get("property_address"):
                patch_body["property_address"] = item["property_address"]
            if not row.get("assessed_value") and item.get("assessed_value"):
                patch_body["assessed_value"] = item["assessed_value"]
            if patch_body:
                sb_patch("multi_county_auctions", {"id": f"eq.{row['id']}"}, patch_body)
                card_backfilled += 1
        time.sleep(0.4)

    print(f"\nre-confirmed on live calendar (case_number still present): {reconfirmed}")
    print(f"NOT found on live calendar for their date (site no longer lists them "
          f"-- ambiguous, no anonymous status field to resolve; left untouched, "
          f"NOT stamped): {not_found_live}")
    print(f"card fields backfilled (parcel_id/address/assessed_value): {card_backfilled}")
    print("\nNo parity_status was stamped for any of these rows in this script -- "
          "the live AJAX endpoint does not expose an anonymous sold/cancelled/"
          "redeemed field (see docstring). This is an honest residual, not a fix.")

    report = {
        "county": COUNTY,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "stale_upcoming_rows": len(rows),
        "distinct_date_groups": len(by_key),
        "reconfirmed_on_live_calendar": reconfirmed,
        "not_found_on_live_calendar": not_found_live,
        "card_fields_backfilled": card_backfilled,
    }
    with open("/tmp/gold_standard_orange_upcoming_reclassify_report.json", "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    print("\nFull report: /tmp/gold_standard_orange_upcoming_reclassify_report.json")


if __name__ == "__main__":
    main()
