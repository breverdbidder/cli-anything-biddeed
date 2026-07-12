#!/usr/bin/env python3
"""Residual C/D gap reharvest for miami_dade (SHARD-12, run3786 dispatch
19fbd0ec-ad81-487d-9007-a82601d91d04). 18 rows / 12 distinct case_numbers still
carry parity_status IS NULL / parity_source IS NULL after the prior
shard_run_miamidade_residual27_reharvest pass (which resolved 7 of the original
19 gap cases). Reuses harvest_date() from
scripts/shard2_run2450_ajax_realforeclose_harvest.py verbatim -- same pattern as
the prior residual reharvest -- to re-sweep the live RealForeclose/RealTaxDeed
PREVIEW calendar across a window of dates around each row's claimed
auction_date, on both platforms.

This script only PRINTS/WRITES findings to /tmp -- it does not write to the DB.
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

# The 12 distinct case_numbers still carrying parity_status IS NULL as of
# 2026-07-12 (18 rows total -- 6 of these appear twice, once per sale_type).
CASES = {
    "2024-011629-CA-01": ["2026-06-29"],
    "2024-012254-CA-01": ["2026-06-29"],
    "2024-015712-CA-01": ["2026-06-29"],
    "2024-019464-CA-01": ["2026-06-29"],
    "2024-019937-CA-01": ["2026-03-16"],
    "2024-020405-CA-01": ["2026-06-29"],
    "2024-020679-CA-01": ["2026-06-29"],
    "2024-021468-CA-01": ["2026-06-29"],
    "2024-022327-CA-01": ["2026-03-02"],
    "2024-024790-CA-01": ["2026-06-29"],
    "2025-004759-CA-01": ["2026-03-09"],
    "2025-006995-CA-01": ["2026-03-16"],
}


def norm(cn):
    import re
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def build_window(claim_dates, weeks_back=12, weeks_fwd=2):
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

    with open("/tmp/miamidade_shard12_residual_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nWrote /tmp/miamidade_shard12_residual_results.json")


if __name__ == "__main__":
    main()
