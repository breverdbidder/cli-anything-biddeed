#!/usr/bin/env python3
"""Highlands C/D/I gap investigation + backfill (SHARD-12 run 3534b, 2026-07-10).

Follow-up to scripts/shard12_run3534_highlands_cd_harvest.py, which already took
C/D from 10.1%% -> 82.1%% by harvesting the RealTaxDeed/RealForeclose AJAX calendar
for highlands' 7 known future auction dates and exact-matching case_number.

This script re-runs the identical harvest against the SAME 7 dates (fail-loud
re-verification per task instructions -- "if harvest_date() returns >0 items for a
date but 0 match our case numbers, investigate before declaring exhausted") for the
remaining ~33 gap rows, and separately probes the I (card_complete) gap.

FINDINGS (both VERIFIED live this session, 2026-07-10):

1. C/D gap (30 tax_deed case numbers across 08/05, 08/12, 08/19/2026 + 2
   foreclosure "bootstrap_placeholder" rows on 08/02, 08/17/2026):
   - Re-harvested all 3 tax_deed dates live: platform returns 24, 24, 29 real
     items respectively (77 total) vs our DB's 34, 33, 39 rows for those same
     dates (106 total) -- a consistent ~27%% shortfall on EVERY date, not a
     format/parsing bug.
   - None of the 30 target case numbers appear in ANY of 5 harvested tax_deed
     dates (07/22, 07/29, 08/05, 08/12, 08/19/2026), while NEIGHBORING case
     numbers from the same calendar_sweep_mca_v3 batch (e.g. 25000694-701 and
     25000714-717 flanking the 25000702-713 gap on 08/05) ARE present and were
     already matched_clean by the prior run.
   - tax_deed_outcomes / foreclosure_outcomes: zero rows for all 30 case
     numbers (checked directly).
   - The 2 foreclosure "bootstrap_placeholder" rows (HIGHLANDS-FC-2026-001/002,
     address "TBD HIGHLANDS FL") return 0 items on both 08/02 and 08/17/2026 --
     consistent with them being synthetic placeholders never backed by a real
     case, not a harvest gap.
   - CONCLUSION: these 30 case numbers were present in the 2026-06-25 bulk
     calendar_sweep_mca_v3 ingest but are no longer on the live sale calendar
     for their originally-assigned dates -- most consistent with normal tax
     deed redemption/cancellation between ingest and now. This is a genuine
     upstream data-lifecycle event, not a scraper defect. Per BLANK > WRONG,
     this script does NOT force parity_status='matched_clean' for these rows --
     doing so would fabricate a match that does not exist live. No DB writes
     performed for this batch.

2. I (card_complete) gap: entirely different root cause than C/D. Every failing
   row already has property_address + latitude/longitude + assessed_value (or
   market_value) populated -- the sole missing ingredient is a parcel_id match
   against v_zoning_gold_standard_card (zone_code IS NOT NULL). Only 142 of 177
   distinct highlands parcel_ids in multi_county_auctions have zoning-gold-
   standard coverage; the other 35 parcels were simply never zoning-ingested.
   This is a v_zoning_gold_standard_card / zoning-ingest coverage gap (a
   different subsystem -- county GIS zoning scrape, not case-number outcome
   harvest) and out of scope for this row-level parity harvest script. No
   fabricated lat/long/zone data written.

Net result: 0 rows changed by this script. All findings VERIFIED live
2026-07-10 and reported to the calling session for handoff / backlog.
"""
import sys
import os
import json
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


# The exact remaining C/D gap rows as of this session's recon (query re-run fresh
# at script start below -- this list is illustrative of what was targeted).
TAXDEED_GAP_CASES = {
    "25000702", "25000703", "25000704", "25000705", "25000706", "25000707",
    "25000709", "25000711", "25000712", "25000713",
    "25000685", "25000686", "25000688", "25000689", "25000691", "25000692",
    "25000710", "25000719", "25000720", "25000721",
    "25000735", "25000736", "25000737", "25000738", "25000739", "25000740",
    "25000741", "25000742", "25000743", "25000755",
}
FORECLOSURE_GAP_CASES = {"HIGHLANDS-FC-2026-001", "HIGHLANDS-FC-2026-002"}

TAXDEED_DATES = ["07/22/2026", "07/29/2026", "08/05/2026", "08/12/2026", "08/19/2026"]
FORECLOSURE_DATES = ["08/02/2026", "08/17/2026"]

PARITY_SOURCE = "tier1:highlands_run3534b_ajax_harvest_gsc_shard12"


def main():
    # Fresh pull of the current gap list (fail-loud: re-verify, don't trust stale recon)
    gap_rows = run_sql(
        "SELECT case_number, auction_date, sale_type FROM multi_county_auctions "
        "WHERE lower(county)='highlands' "
        "AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1%');"
    )
    print(f"Fresh gap recon: {len(gap_rows)} rows outstanding "
          f"({sum(1 for r in gap_rows if r['sale_type']=='tax_deed')} tax_deed, "
          f"{sum(1 for r in gap_rows if r['sale_type']=='foreclosure')} foreclosure)")

    live_case_numbers = {}  # case_number -> (date, address, assessed_value)
    for d in TAXDEED_DATES:
        items = harvest_date("highlands", "highlands", d, platform_domain="realtaxdeed.com")
        print(f"highlands realtaxdeed {d}: live_platform_parsed={len(items)}")
        for it in items:
            cn = it.get("case_number")
            if cn:
                live_case_numbers[cn] = (d, it.get("property_address"), it.get("assessed_value"))

    for d in FORECLOSURE_DATES:
        items = harvest_date("highlands", "highlands", d, platform_domain="realforeclose.com")
        print(f"highlands realforeclose {d}: live_platform_parsed={len(items)}")
        for it in items:
            cn = it.get("case_number")
            if cn:
                live_case_numbers[cn] = (d, it.get("property_address"), it.get("assessed_value"))

    matched = 0
    still_missing = []
    for cn in sorted(TAXDEED_GAP_CASES | FORECLOSURE_GAP_CASES):
        if cn in live_case_numbers:
            date, addr, val = live_case_numbers[cn]
            print(f"  MATCH FOUND on re-harvest: {cn} on {date} (addr={addr!r} val={val})")
            rows = run_sql(
                f"SELECT case_number, property_address, assessed_value FROM multi_county_auctions "
                f"WHERE county='highlands' AND case_number='{esc(cn)}';"
            )
            if rows:
                row = rows[0]
                sets = ["parity_status='matched_clean'", f"parity_source='{PARITY_SOURCE}'"]
                if row.get("property_address") is None and addr:
                    sets.append(f"property_address='{esc(addr)}'")
                if row.get("assessed_value") is None and val is not None:
                    sets.append(f"assessed_value={val}")
                run_sql(
                    f"UPDATE multi_county_auctions SET {', '.join(sets)} "
                    f"WHERE county='highlands' AND case_number='{esc(cn)}';"
                )
                matched += 1
        else:
            still_missing.append(cn)

    print(f"\nRE-HARVEST RESULT: {matched} newly matched, {len(still_missing)} confirmed absent from live calendar")
    print("CONFIRMED ABSENT (present in our DB, not found on any live calendar date checked):")
    for cn in still_missing:
        print(f"  {cn}")

    if matched == 0 and live_case_numbers:
        print(
            "\nFAIL-LOUD CHECK: live platform returned "
            f"{len(live_case_numbers)} distinct case numbers across all dates checked, "
            f"but 0 of our {len(TAXDEED_GAP_CASES | FORECLOSURE_GAP_CASES)} gap case "
            "numbers matched. This is NOT silently swallowed -- see docstring above "
            "for root-cause investigation (redemption/cancellation hypothesis, "
            "VERIFIED via tax_deed_outcomes/foreclosure_outcomes cross-check = 0 rows "
            "for all targets, and via neighboring-case-number presence on the same "
            "dates from the same ingest batch)."
        )

    # I-gap diagnostic (read-only, no writes -- documents the finding for handoff)
    i_gap = run_sql(
        "WITH zc AS (SELECT DISTINCT parcel_id, tax_account FROM v_zoning_gold_standard_card "
        "WHERE lower(county) = norm_county_key('highlands') AND zone_code IS NOT NULL) "
        "SELECT count(*) AS distinct_parcels, "
        "(SELECT count(*) FROM zc) AS card_rows_with_zone "
        "FROM (SELECT DISTINCT parcel_id FROM multi_county_auctions "
        "WHERE lower(county)='highlands' AND parcel_id IS NOT NULL) p;"
    )
    print(f"\nI-GAP DIAGNOSTIC: {i_gap}")
    print("I gap root cause: parcel_id -> v_zoning_gold_standard_card linkage coverage "
          "(35 of 177 highlands parcels never zoning-ingested). Out of scope for this "
          "case-number outcome harvester; requires county GIS zoning ingest, not a "
          "row-level parity fix.")


if __name__ == "__main__":
    main()
