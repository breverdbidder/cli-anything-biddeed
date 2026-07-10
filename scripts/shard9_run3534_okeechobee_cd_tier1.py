#!/usr/bin/env python3
"""GOLD STANDARD SHARD-9 run3534 -- okeechobee letters C/D.

Does NOT reimplement the AJAX harvest -- reuses
scripts/shard2_run2450_ajax_realforeclose_harvest.py verbatim (SEARCH-FIRST: same
RealAuction-family platform, same proven mechanism already used for
pinellas/santa_rosa/alachua/gilchrist/putnam/manatee). This file only pins down the exact
target list (subdomains + dates) used for the okeechobee run, so the harvest is
reproducible.

Usage:
    python3 scripts/shard2_run2450_ajax_realforeclose_harvest.py \
        "$(python3 scripts/shard9_run3534_okeechobee_cd_tier1.py --targets)"

Then apply supabase/migrations/20260710_shard9_run3534_okeechobee_cd_ghost_fix_and_tier1.sql
(or the equivalent UPDATEs) to join the harvested public.realforeclose_aids rows back
into public.multi_county_auctions honestly.
"""
import json
import sys

# okeechobee foreclosure auction dates on file in multi_county_auctions as of 2026-07-10,
# plus the single tax_deed date on file. okeechobee.realforeclose.com /
# okeechobee.realtaxdeed.com confirmed live + active in realauction_subdomains
# (parity_verdict='verified' for foreclosure).
FORECLOSURE_DATES = [
    "2026-03-11", "2026-03-18", "2026-04-08", "2026-05-06", "2026-05-20",
    "2026-06-17", "2026-07-01", "2026-07-08", "2026-07-22", "2026-08-06",
    "2026-08-19", "2026-08-26", "2026-09-17",
]
TAX_DEED_DATES = ["2026-04-09"]


def _mmddyyyy(iso_date: str) -> str:
    y, m, d = iso_date.split("-")
    return f"{m}/{d}/{y}"


def build_targets():
    return [
        {
            "subdomain": "okeechobee",
            "county_slug": "okeechobee",
            "platform_domain": "realforeclose.com",
            "dates": [_mmddyyyy(d) for d in FORECLOSURE_DATES],
        },
        {
            "subdomain": "okeechobee",
            "county_slug": "okeechobee",
            "platform_domain": "realtaxdeed.com",
            "dates": [_mmddyyyy(d) for d in TAX_DEED_DATES],
        },
    ]


if __name__ == "__main__":
    if "--targets" in sys.argv:
        print(json.dumps(build_targets()))
    else:
        print(__doc__)

# ---------------------------------------------------------------------------
# RESULT (live, run 2026-07-10):
#   okeechobee harvest: 58 real AITEM records parsed and upserted into
#   public.realforeclose_aids (county_slug='okeechobee'); tax_deed date 04/09/2026
#   returned 0 items (endpoint reachable, genuinely no AJAX items posted for that date --
#   not an error; every foreclosure date returned real data, confirming the mechanism
#   works on this tenant).
#
#   pencil_dod_evaluate_county('okeechobee'):
#     before      : C matched_clean=52/54 (96.3%, ghost-inflated by 6 mislabeled PO rows)
#     after fix   : C matched_clean=46/54 (85.2%) FAIL, D matched_any=46/54 (85.2%) FAIL
#     after tier1 : C matched_clean=54/54 (100.0%) PASS, D matched_any=54/54 (100.0%) PASS
# ---------------------------------------------------------------------------
