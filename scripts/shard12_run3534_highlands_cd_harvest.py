#!/usr/bin/env python3
"""Highlands C/D row-level parity harvest (SHARD-12 run 3534, 2026-07-10).

Highlands sits at C=10.1%% D=10.1%% because only auction_date=2026-07-01 (14 rows) was
ever row-level harvested against the live RealTaxDeed/RealForeclose calendar (by a prior
shard4 session). The other 6 auction dates (163 rows: 5 tax_deed dates + 2 foreclosure
dates) have never been checked against the live platform, so parity_status stays NULL or
mca_only. This is a pure C/D fix — the rows already carry property_address/assessed_value
from the calendar_sweep_mca_v3 ingest; they just lack the tier1 parity confirmation.

Reuses harvest_date()/parse_aitem_blocks() VERBATIM from
scripts/shard2_run2450_ajax_realforeclose_harvest.py (same proven AJAX mechanism) per the
SEARCH-FIRST MANDATE — no reimplementation.

case_number matching: highlands uses bare numeric case numbers in our table (e.g.
"25000534"). The RealTaxDeed "Case #" field on the AJAX item may or may not carry the same
exact string — this script matches on exact string equality only (BLANK > WRONG: no fuzzy
matching that could produce a false parity_status='matched_clean').
"""
import sys
import os
import json
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from shard2_run2450_ajax_realforeclose_harvest import harvest_date  # noqa: E402

SUPABASE_ACCESS_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
MGMT_API = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
UA = "Mozilla/5.0 (X11; Linux x86_64) curl-gha-sql-runner"


def run_sql(sql):
    req = urllib.request.Request(
        MGMT_API, data=json.dumps({"query": sql}).encode(), method="POST",
        headers={"Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
                 "Content-Type": "application/json", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read() or b"[]")


def esc(s):
    return str(s).replace("'", "''")


TARGETS = [
    ("highlands", "realtaxdeed.com", ["07/22/2026", "07/29/2026", "08/05/2026", "08/12/2026", "08/19/2026"]),
    ("highlands", "realforeclose.com", ["08/02/2026", "08/17/2026"]),
]

PARITY_SOURCE = "tier1:highlands_run3534_ajax_harvest_gsc_shard12"


def main():
    total_parsed = 0
    total_matched = 0
    total_addr_backfilled = 0
    unmatched_case_numbers = []

    for subdomain, platform, dates in TARGETS:
        for d in dates:
            items = harvest_date(subdomain, "highlands", d, platform_domain=platform)
            total_parsed += len(items)
            print(f"highlands {platform} {d}: parsed={len(items)}")
            for it in items:
                cn = it.get("case_number")
                if not cn:
                    continue
                cn_e = esc(cn)
                rows = run_sql(
                    f"SELECT case_number, property_address, assessed_value FROM multi_county_auctions "
                    f"WHERE county='highlands' AND case_number='{cn_e}';"
                )
                if not rows:
                    unmatched_case_numbers.append(cn)
                    continue
                row = rows[0]
                sets = ["parity_status='matched_clean'", f"parity_source='{PARITY_SOURCE}'"]
                if row.get("property_address") is None and it.get("property_address"):
                    sets.append(f"property_address='{esc(it['property_address'])}'")
                if row.get("assessed_value") is None and it.get("assessed_value") is not None:
                    sets.append(f"assessed_value={it['assessed_value']}")
                    total_addr_backfilled += 1
                run_sql(
                    f"UPDATE multi_county_auctions SET {', '.join(sets)} "
                    f"WHERE county='highlands' AND case_number='{cn_e}';"
                )
                total_matched += 1
            time.sleep(0.3)

    print(f"TOTAL parsed={total_parsed} matched_and_updated={total_matched} "
          f"fields_backfilled={total_addr_backfilled} unmatched={len(unmatched_case_numbers)}")
    if total_parsed > 0 and total_matched == 0:
        raise RuntimeError(f"Silent failure: {total_parsed} items parsed but 0 matched to multi_county_auctions")
    print("UNMATCHED (present on platform, no case_number match in our table):",
          unmatched_case_numbers[:30])


if __name__ == "__main__":
    main()
