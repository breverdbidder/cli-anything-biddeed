#!/usr/bin/env python3
"""GOLD STANDARD shard-3 miami_dade C/D residual re-harvest -- dispatch
0c873526-996a-4f5d-9123-99836d1d585f, 2026-08-23.

Scope: miami_dade ONLY, letters C and D. Both FAIL live at 93.4%
(matched_clean=matched_any=526 of auctions_total=563). Population is the
evaluator's exact filter -- (data_source IS NULL OR data_source <>
'propertyonion' OR tier1_authoritative=true) -- confirmed live via PostgREST
to return exactly 563 rows, matching pencil_dod_evaluate_county's
auctions_total. Within that population, 37 rows have parity_status not
'matched_clean'/'matched_any' with a tier1% parity_source. Need >=535
(95% of 563) to pass; currently 526; gap to close = 9.

ROOT CAUSE (same recurring structural issue documented in
scripts/gold_standard_shard2_okmd_9c6b9b03_miamidade_cd_reharvest.py, dated
2026-08-08): the daily cron's run_cd_parity() step has been DISABLED since
2026-07-04 (ghost-success blanket-flip regression on okaloosa -- see
scripts/shard2_main_executor.py). Every auction row scraped since the last
manual re-harvest accumulates with parity_status NULL/stale forever. This is
a FRESH residual re-derived live immediately before writing this script (37
distinct case_numbers across 5 (sale_type, auction_date) pairs), NOT reused
from any prior target list.

Reuses scripts/shard2_run2450_ajax_realforeclose_harvest.py's harvest_date()
verbatim (imported via importlib, no reimplementation) for the AJAX/cookie
dance against the live RealForeclose (foreclosure) / RealTaxDeed (tax_deed)
calendars. Match/patch logic identical to the 2026-08-08 script: exact
normalized case_number match -> parity_status='matched_clean',
parity_source='tier1:miamidade_gsd3_0c873526:<sale_type>:<date>' (only if
not already tier1-labeled matched_clean), plus NULL-only backfill of
parcel_id/property_address/assessed_value (never overwrites non-null data).

Fail-loud invariant: a date's calendar returning 0 items entirely is a FETCH
FAILURE, logged loudly. Four of our five target dates (2026-08-10,
2026-08-17, 2026-08-18, 2026-08-19) are already in the past relative to
today (2026-08-23) -- RealForeclose/RealTaxDeed calendars commonly age out
once the sale date has passed, so fetch failures on those dates are EXPECTED
per the documented pattern, not a bug. 2026-08-24 (tomorrow) is the one
still-live date and is the primary target. A date with items but none
matching target case_numbers is a legitimate no-match, logged per-case, not
raised. If ALL targets end with 0 promotions AND 0 fetch failures, raise
loudly.

Idempotent: safe to re-run. Only patches parity when not already
tier1-labeled matched_clean; only backfills NULL card fields.
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
DISPATCH_TAG = "miamidade_gsd3_0c873526"

PLATFORM_DOMAIN = {"foreclosure": "realforeclose.com", "tax_deed": "realtaxdeed.com"}

# Exactly the 5 (sale_type, auction_date) pairs containing the 37 non-tier1
# rows within the evaluator's exact 563-row population, and exactly the
# target case_numbers within each -- verified live via PostgREST query
# immediately before writing this script (2026-08-23).
TARGETS = [
    {"sale_type": "foreclosure", "auction_date": "2026-08-10",
     "case_numbers": ["2025-014301-CA-01", "2025-010500-CA-01", "2025-013100-CA-01",
                       "2025-010211-CA-01", "2025-007971-CA-01", "2025-009306-CA-01"]},
    {"sale_type": "foreclosure", "auction_date": "2026-08-24",
     "case_numbers": ["2024-018502-CA-01", "2025-023730-CA-01", "2025-024683-CA-01",
                       "2025-008800-CA-01", "2024-019582-CA-01", "2025-020717-CA-01",
                       "2025-015248-CA-01", "2024-009650-CA-01", "2024-021360-CA-01",
                       "2025-003933-CA-01", "2026-021475-CC-23", "2026-002023-CA-01",
                       "2025-004896-CA-01", "2024-017015-CA-01", "2025-005539-CA-01",
                       "2024-020977-CA-01", "2025-002524-CA-01", "2025-025518-CA-01"]},
    {"sale_type": "tax_deed", "auction_date": "2026-08-17",
     "case_numbers": ["2025-008973-CA-01", "2025-013299-CA-01", "2025-013969-CA-01",
                       "2025-019896-CA-01", "2025-002992-CA-01", "2025-013301-CA-01",
                       "2025-004629-CA-01", "2025-018389-CA-01", "2025-018229-CA-01"]},
    {"sale_type": "tax_deed", "auction_date": "2026-08-18",
     "case_numbers": ["2025-002515-CA-01", "2025-003400-CA-01"]},
    {"sale_type": "tax_deed", "auction_date": "2026-08-19",
     "case_numbers": ["2024-021457-CA-01", "2025-013889-CA-01"]},
]


def norm_case_number(cn):
    import re
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def is_real_parcel_id(pid):
    """Some AITEM blocks decode the parcel-appraiser link as its own anchor text
    ('Property Appraiser') instead of the parcel number -- a pre-existing parser
    gap. A real parcel_id always contains at least one digit."""
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
    all_matched_by_date = {}

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
            all_unmatched.extend((sale_type, ad, cn, "harvest_exception") for cn in case_numbers)
            continue

        if not items:
            msg = (f"FETCH FAILURE: {sale_type} {ad} returned 0 calendar items entirely -- "
                   f"calendar likely aged out (date relative to 2026-08-23) or platform "
                   f"unreachable. Unmatched case_numbers for this date: {case_numbers}")
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
        all_matched_by_date[(sale_type, ad)] = sorted(matched_cns)

        print(f"  {len(items)} calendar items fetched -> matched={sorted(matched_cns)} "
              f"parity_promoted={len(parity)} card_backfilled={len(card)}")
        if unmatched_cns:
            print(f"  NO MATCH this pass (legitimate, calendar had items but not these case#s): "
                  f"{sorted(unmatched_cns)}")
            all_unmatched.extend((sale_type, ad, cn, "not_in_calendar") for cn in unmatched_cns)

        time.sleep(0.4)

    print(f"\n=== TOTALS ===")
    print(f"parity_promoted={grand_totals['parity']} card_backfilled={grand_totals['card']}")
    print(f"\nMATCHED BY DATE:")
    for (st, ad), cns in all_matched_by_date.items():
        print(f"  {st} {ad}: {cns}")
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
