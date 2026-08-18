#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-2 -- gadsden + martin + holmes
dispatch_id: 8000b258-5ab4-4abf-8208-ef4a2eea1444
chat_session: architect-20260818T080000

SCOPE (this file): re-run clerk_ssot diff_and_reconcile scoped to ONLY
gadsden (foreclosure + tax_deed) and holmes (foreclosure) -- reusing
run_parity.py's stage_rows/diff_and_reconcile verbatim, never calling its
main() so no other shard's counties are touched. This tests whether today's
35c162dd un-cancel-lock fix (shipped this morning for lake) also reactivates
any of gadsden's 8 CLERK_SSOT_CANCELLED rows, and gets a fresh live read on
holmes (last audited 2026-08-09, now past the 7-day certify-gate freshness
window).

martin has NO independently-parseable clerk calendar (run_parity.py's
NO_PUBLIC_CALENDAR list) -- not touched by this script.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/clerk_ssot" if False else os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clerk_ssot.run_parity import stage_rows, diff_and_reconcile  # noqa: E402
from clerk_ssot.parsers import gadsden, holmes  # noqa: E402

SCOPE = {
    "gadsden": {"foreclosure": gadsden.parse_foreclosure, "tax_deed": gadsden.parse_tax_deed},
    "holmes": {"foreclosure": holmes.parse_foreclosure},
}


def main():
    results = []
    failures = []
    for county_slug, sale_types in SCOPE.items():
        for sale_type, parser_fn in sale_types.items():
            try:
                rows = parser_fn()
            except Exception as e:
                failures.append({"county_slug": county_slug, "sale_type": sale_type, "error": str(e)})
                continue
            if not rows:
                failures.append({"county_slug": county_slug, "sale_type": sale_type, "error": "0 rows -- treated as FAILURE"})
                continue
            try:
                stage_rows(rows)
                result = diff_and_reconcile(county_slug, sale_type, rows)
                results.append(result)
                print(f"[{county_slug}/{sale_type}] rows={len(rows)} -> {json.dumps(result)}")
            except Exception as e:
                failures.append({"county_slug": county_slug, "sale_type": sale_type, "error": f"SQL/reconcile error: {e}"})

    print(json.dumps({"results": results, "failures": failures}, indent=2))
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
