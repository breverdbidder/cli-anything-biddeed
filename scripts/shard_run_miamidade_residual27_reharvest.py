#!/usr/bin/env python3
"""One-off residual-gap reharvest for miami_dade C/D (27-row gap flagged this
session). Reuses harvest_date() from scripts/shard2_run2450_ajax_realforeclose_harvest.py
verbatim (same pattern as scripts/shard14_run3534_miami_dade_cd_i_fix.py) to
re-sweep the live RealForeclose/RealTaxDeed PREVIEW calendar across a window
of dates around each row's claimed auction_date, on both platforms
(realforeclose.com for foreclosure, realtaxdeed.com for tax_deed) -- a case
number's true platform is itself unknown a priori for the 27 gap rows, so
both are tried.

For each of the 16 distinct case_numbers involved, this script:
  1. Builds a candidate date list: every Monday within +/- 10 weeks of each
     of that case's claimed auction_date(s) (RealAuction/RealTaxDeed sales in
     FL run on a weekly cadence, historically Mondays for Miami-Dade).
  2. Fetches harvest_date() for each candidate date on both platforms.
  3. Looks for an exact (normalized) case_number match anywhere in the
     harvested set.
  4. Prints a per-case classification: FOUND_REAL (with real date+platform),
     or NOT_FOUND (checked N dates x 2 platforms, nothing).

This script only PRINTS findings -- it does not write to the DB. DB writes
(if any FOUND_REAL results appear) are done separately, one deliberate PATCH
per case, each citing the exact date/platform this script found it under.
"""
import os
import sys
import json
import time
import importlib.util
from datetime import datetime, timedelta

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SUBDOMAIN = "miamidade"
PLATFORMS = ["realforeclose.com", "realtaxdeed.com"]

CASES = {
    "2024-011629-CA-01": ["2026-06-29"],
    "2024-012254-CA-01": ["2026-06-29"],
    "2024-015712-CA-01": ["2026-06-29"],
    "2024-018474-CA-01": ["2026-04-06"],
    "2024-019464-CA-01": ["2026-06-29"],
    "2024-019937-CA-01": ["2026-03-16"],
    "2024-020257-CA-01": ["2026-05-18"],
    "2024-020405-CA-01": ["2026-06-29"],
    "2024-020679-CA-01": ["2026-06-29"],
    "2024-020875-CA-01": ["2026-03-02"],
    "2024-021468-CA-01": ["2026-06-29"],
    "2024-021491-CA-01": ["2026-04-06"],
    "2024-022327-CA-01": ["2026-03-02"],
    "2024-024790-CA-01": ["2026-06-29"],
    "2025-004759-CA-01": ["2026-03-09"],
    "2025-004963-CA-01": ["2026-03-16"],
    "2025-006995-CA-01": ["2026-03-16"],
    "2025A01003": ["2026-03-19"],
    "2026A00132": ["2026-05-14"],
}


def norm(cn):
    import re
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def build_window(claim_dates, weeks_back=10, weeks_fwd=10):
    out = set()
    for cd in claim_dates:
        base = datetime.strptime(cd, "%Y-%m-%d")
        for w in range(-weeks_back, weeks_fwd + 1):
            d = base + timedelta(weeks=w)
            out.add(d)
    return sorted(out)


def main():
    all_claim_dates = sorted({d for ds in CASES.values() for d in ds})
    window = build_window(all_claim_dates)
    print(f"Sweeping {len(window)} candidate dates x {len(PLATFORMS)} platforms "
          f"= {len(window)*len(PLATFORMS)} fetches", file=sys.stderr)

    # cache: (platform, mmddyyyy) -> items
    cache = {}
    for d in window:
        mmddyyyy = d.strftime("%m/%d/%Y")
        for platform in PLATFORMS:
            key = (platform, mmddyyyy)
            try:
                items = _mod.harvest_date(SUBDOMAIN, "miami_dade", mmddyyyy, platform_domain=platform)
            except Exception as e:
                print(f"  ERROR {platform} {mmddyyyy}: {e}", file=sys.stderr)
                items = []
            cache[key] = items
            found_cns = {norm(i.get("case_number")) for i in items if i.get("case_number")}
            print(f"  {platform} {mmddyyyy}: {len(items)} items, "
                  f"{len(found_cns)} distinct case_numbers", file=sys.stderr)
            time.sleep(0.3)

    results = {}
    for cn, claim_dates in CASES.items():
        target = norm(cn)
        hits = []
        for (platform, mmddyyyy), items in cache.items():
            for it in items:
                if norm(it.get("case_number")) == target:
                    hits.append({
                        "platform": platform,
                        "date_mmddyyyy": mmddyyyy,
                        "item": it,
                    })
        results[cn] = hits
        if hits:
            print(f"FOUND {cn}: {len(hits)} hit(s)")
            for h in hits:
                print(f"   -> {h['platform']} {h['date_mmddyyyy']} "
                      f"case={h['item'].get('case_number')!r} "
                      f"addr={h['item'].get('property_address')!r}")
        else:
            print(f"NOT_FOUND {cn} (checked {len(window)} dates x {len(PLATFORMS)} platforms, "
                  f"claim_dates={claim_dates})")

    with open("/tmp/miamidade_residual27_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nWrote /tmp/miamidade_residual27_results.json")


if __name__ == "__main__":
    main()
