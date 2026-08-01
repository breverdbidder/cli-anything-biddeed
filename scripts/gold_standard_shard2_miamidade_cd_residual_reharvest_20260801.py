#!/usr/bin/env python3
"""GOLD STANDARD miami_dade C/D residual re-harvest -- 2026-08-01 firing.

Scope: miami_dade ONLY, letters C and D. Both FAIL at 90.7%
(matched_clean=matched_any=401 of auctions_total=442). The gap is exactly
40 rows with parity_status/parity_source NULL -- never run through the
tier1 RealAuction/RealTaxDeed calendar matcher at all.

ROOT CAUSE (confirmed live 2026-08-01): the daily cron
.github/workflows/gold-standard-shard2-daily.yml -> scripts/shard2_main_executor.py
covers miami_dade's H-freshness SLA every day, but its run_cd_parity() step
was DISABLED 2026-07-04 (see git log 25fafcd5 / commit body) after a
ghost-success incident on okaloosa -- it is now a READ-ONLY status report,
not a matcher. No other scheduled job re-invokes the actual AJAX harvest +
match/patch step for miami_dade. Consequently every auction row scraped
into multi_county_auctions since that date (new upcoming sales, plus a
residual tail from before) accumulates with parity_status IS NULL forever
until a one-off shard script (like this one) re-harvests it manually. This
mirrors the palm_beach C/D root cause from the 2026-07-31 session: a
recurring job silently stopped doing the actual work while its wrapper
kept reporting "healthy".

This is a NARROW, residual-only re-run of the proven pattern in
scripts/gold_standard_shard2_83c11ccb_miamidade_cd_residual_fix.py (which
itself forked scripts/shard14_run3534_miami_dade_cd_i_fix.py), scoped to
ONLY the 7 (sale_type, auction_date) pairs that still contain a NULL-parity
row as of this run -- verified live via REST query before writing this
script:

  foreclosure 2026-03-09  (2025-004759-CA-01)
  foreclosure 2026-03-16  (2024-019937-CA-01, 2025-006995-CA-01)
  foreclosure 2026-06-29  (6 case numbers)
  tax_deed    2026-06-29  (2024-020679-CA-01, 2024-021468-CA-01)
  tax_deed    2026-07-27  (9 case numbers)
  foreclosure 2026-08-03  (6 case numbers)
  foreclosure 2026-08-04  (14 case numbers)

Reuses scripts/shard2_run2450_ajax_realforeclose_harvest.py's harvest_date()
verbatim for the AJAX/cookie dance -- no reimplementation. Match/patch logic
mirrors gold_standard_shard2_83c11ccb_miamidade_cd_residual_fix.py's
match_and_fix(): exact case_number match -> parity_status='matched_clean',
parity_source='tier1:gold_standard_shard2_miamidade_residual_20260801:<sale_type>:<date>',
plus NULL-only backfill of parcel_id/property_address/assessed_value (never
overwrites non-null data). This script ONLY touches rows whose case_number
is in TARGET_CASE_NUMBERS below -- it does not touch any other row on these
dates, even if the harvested calendar contains other unmatched local rows.

Fail-loud invariant: if a date's calendar returns 0 items entirely, that is
treated as a FETCH FAILURE and reported loudly (not silently "0 unmatched,
all good"). If a date's calendar returns >0 items but 0 of our target
case_numbers are present, that is a legitimate "no match this pass" and is
logged per-case-number, not raised.

Idempotent: re-running is safe. Only patches parity when the row is not
already tier1-labeled matched_clean; only backfills NULL fields.

Usage: python3 scripts/gold_standard_shard2_miamidade_cd_residual_reharvest_20260801.py
"""
import os
import sys
import json
import time
import importlib.util

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

import urllib.request
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY = "miami_dade"
SUBDOMAIN = "miamidade"
DISPATCH_TAG = "gold_standard_shard2_miamidade_residual_20260801"

PLATFORM_DOMAIN = {"foreclosure": "realforeclose.com", "tax_deed": "realtaxdeed.com"}

# Exactly the 7 (sale_type, auction_date) pairs containing the 40 NULL-parity
# rows, and exactly the target case_numbers within each -- verified live via
# REST query before writing this script.
TARGETS = [
    {"sale_type": "foreclosure", "auction_date": "2026-03-09",
     "case_numbers": ["2025-004759-CA-01"]},
    {"sale_type": "foreclosure", "auction_date": "2026-03-16",
     "case_numbers": ["2024-019937-CA-01", "2025-006995-CA-01"]},
    {"sale_type": "foreclosure", "auction_date": "2026-06-29",
     "case_numbers": ["2024-011629-CA-01", "2024-012254-CA-01", "2024-015712-CA-01",
                       "2024-019464-CA-01", "2024-020405-CA-01", "2024-024790-CA-01"]},
    {"sale_type": "tax_deed", "auction_date": "2026-06-29",
     "case_numbers": ["2024-020679-CA-01", "2024-021468-CA-01"]},
    {"sale_type": "tax_deed", "auction_date": "2026-07-27",
     "case_numbers": ["2025-014835-CA-01", "2025-014841-CA-01", "2025-018660-CA-01",
                       "2025-021066-CA-01", "2025-021626-CA-01", "2025-021994-CA-01",
                       "2025-099401-CC-23", "2026-004503-CA-01", "2026-007325-CA-01"]},
    {"sale_type": "foreclosure", "auction_date": "2026-08-03",
     "case_numbers": ["2024-023366-CA-01", "2025-009236-CA-01", "2025-018243-CA-01",
                       "2025-020414-CA-01", "2025-021122-CA-01", "2025-027358-CC-23"]},
    {"sale_type": "foreclosure", "auction_date": "2026-08-04",
     "case_numbers": ["2018-036429-CA-01", "2023-022632-CA-01", "2023-022826-CA-01",
                       "2023-024239-CA-01", "2023-024257-CA-01", "2023-024268-CA-01",
                       "2023-025901-CA-01", "2023-028512-CA-01", "2024-004688-CA-01",
                       "2024-004733-CA-01", "2024-007301-CA-01", "2024-011180-CA-01",
                       "2024-020979-CA-01", "2026-004188-CA-01"]},
]


def norm_case_number(cn):
    import re
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def is_real_parcel_id(pid):
    """Some AITEM blocks decode the parcel-appraiser link as its own anchor text
    ('Property Appraiser') instead of the parcel number -- a pre-existing parser
    gap in shard2's decoder. A real parcel_id always contains at least one digit."""
    import re
    if not pid:
        return False
    return bool(re.search(r"\d", pid)) and pid.strip().lower() != "property appraiser"


def _with_retry(fn, attempts=3):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code == 409 or i == attempts - 1:
                raise
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def rest_get(path):
    def _do():
        req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
                                      headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def rest_patch(path, body, timeout=90):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=representation"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def match_and_fix(items, target_case_numbers, parity_source_label, sale_type, auction_date):
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}&sale_type=eq.{sale_type}&auction_date=eq.{auction_date}"
        f"&case_number=in.({','.join(target_case_numbers)})"
        f"&select=id,case_number,parity_status,parity_source,parcel_id,property_address,assessed_value")

    matched_case_numbers = set()
    unmatched_case_numbers = set()

    parity_promoted = []
    card_backfilled = []

    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        if cn not in by_norm:
            unmatched_case_numbers.add(row["case_number"])
            continue
        item = by_norm[cn]
        matched_case_numbers.add(row["case_number"])
        already_tier1 = (row.get("parity_source") or "").startswith("tier1")

        try:
            if not (row["parity_status"] == "matched_clean" and already_tier1):
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                           {"parity_status": "matched_clean", "parity_source": parity_source_label})
                parity_promoted.append(row["id"])
        except Exception as e:
            print(f"    parity patch FAILED for {row['id']} ({row['case_number']}): {e}")
            continue

        patch_body = {}
        if not row.get("parcel_id") and is_real_parcel_id(item.get("parcel_id")):
            patch_body["parcel_id"] = item["parcel_id"]
        if not row.get("property_address") and item.get("property_address"):
            patch_body["property_address"] = item["property_address"]
        if not row.get("assessed_value") and item.get("assessed_value"):
            patch_body["assessed_value"] = item["assessed_value"]
        if patch_body:
            try:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
                card_backfilled.append(row["id"])
            except Exception as e:
                print(f"    card patch FAILED for {row['id']} ({row['case_number']}): {e}")

    all_target_cns = set(target_case_numbers)
    accounted = matched_case_numbers | unmatched_case_numbers
    for missing_row_cn in all_target_cns - accounted:
        unmatched_case_numbers.add(missing_row_cn)

    return parity_promoted, card_backfilled, matched_case_numbers, unmatched_case_numbers


def main():
    grand_totals = {"parity": 0, "card": 0}
    all_unmatched = []
    fetch_failures = []

    for t in TARGETS:
        sale_type = t["sale_type"]
        ad = t["auction_date"]
        case_numbers = t["case_numbers"]
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        platform = PLATFORM_DOMAIN[sale_type]

        print(f"\n=== {sale_type} {ad} ({len(case_numbers)} target case_numbers) ===")
        try:
            items = _mod.harvest_date(SUBDOMAIN, COUNTY, mmddyyyy, platform_domain=platform)
        except Exception as e:
            msg = f"HARVEST EXCEPTION {sale_type} {ad}: {e}"
            print(f"  {msg}")
            fetch_failures.append(msg)
            continue

        if not items:
            msg = (f"FETCH FAILURE: {sale_type} {ad} returned 0 calendar items entirely -- "
                   f"calendar likely aged out (date is in the past) or platform unreachable. "
                   f"Unmatched case_numbers for this date: {case_numbers}")
            print(f"  {msg}")
            fetch_failures.append(msg)
            all_unmatched.extend((sale_type, ad, cn, "calendar_returned_zero_items") for cn in case_numbers)
            time.sleep(0.3)
            continue

        parity_source_label = f"tier1:{DISPATCH_TAG}:{sale_type}:{ad}"
        parity, card, matched_cns, unmatched_cns = match_and_fix(
            items, case_numbers, parity_source_label, sale_type, ad)

        grand_totals["parity"] += len(parity)
        grand_totals["card"] += len(card)

        print(f"  {len(items)} calendar items fetched -> matched={sorted(matched_cns)} "
              f"parity_promoted={len(parity)} card_backfilled={len(card)}")
        if unmatched_cns:
            print(f"  NO MATCH this pass (legitimate, calendar had items but not these case#s): "
                  f"{sorted(unmatched_cns)}")
            all_unmatched.extend((sale_type, ad, cn, "not_in_calendar") for cn in unmatched_cns)

        time.sleep(0.4)

    print(f"\n=== TOTALS ===")
    print(f"parity_promoted={grand_totals['parity']} card_backfilled={grand_totals['card']}")
    if fetch_failures:
        print(f"\nFETCH FAILURES ({len(fetch_failures)}):")
        for f in fetch_failures:
            print(f"  - {f}")
    if all_unmatched:
        print(f"\nSTILL-UNRESOLVED case_numbers ({len(all_unmatched)}):")
        for st, ad, cn, reason in all_unmatched:
            print(f"  - {st} {ad} {cn}: {reason}")

    if grand_totals["parity"] == 0 and not fetch_failures:
        raise RuntimeError(
            "Silent failure guard: 0 rows promoted to matched_clean and 0 fetch "
            "failures logged -- every target case_number failed to match against "
            "a successfully-fetched calendar. This is unexpected; investigate "
            "before treating as success.")


if __name__ == "__main__":
    main()
