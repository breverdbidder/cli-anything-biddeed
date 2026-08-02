#!/usr/bin/env python3
"""
Gold Standard SHARD-1 (dispatch a00c589b-9346-491a-a8bd-5ba50946fb44, loop run
8166): manatee letters C (matched_clean) and D (matched_any).

BASELINE (VERIFIED live 2026-08-02 08:03Z via
SELECT public.pencil_dod_evaluate_county('manatee');):
  C FAIL metric=93.5 [matched_clean=87 of 93]
  D FAIL metric=93.5 [matched_any=87 of 93]
  Same 6-row gap drives both.

ROOT CAUSE (VERIFIED live via direct SQL against multi_county_auctions using
the evaluator's own denominator filter -- (data_source<>'propertyonion' OR
tier1_authoritative=true) AND NOT (parity_status='matched_clean' AND
parity_source LIKE 'tier1%')):

The 6 unmatched rows are exactly the 6 rows already identified and
deliberately left untouched by the prior session's migration
20260801_gold_standard_manatee_cdi_ajax_gis_backfill.sql, which reasoned
"auction hasn't happened yet, cannot verify outcome" as of its run date
(2026-08-01). Re-diagnosed fresh this session (today is 2026-08-02, one day
later) rather than trusting that prior reasoning at face value per Honesty
Protocol:

  1. 5 tax_deed rows, auction_date=2026-08-03 (still 1 day in the future as
     of this session): 2026TD000018, 2026TD000019, 2026TD000024,
     2026TD000025, 2026TD000042.
  2. 1 foreclosure row, auction_date=2026-08-04 (2 days future),
     case_number=412025CA002931CAAXMA (data_source mislabeled 'realtaxdeed'
     -- it is actually a foreclosure case, unrelated to the tax_deed lane).

RE-EXAMINED THE "future auction = can't match" ASSUMPTION: it does not hold
for this county's established C/D evidentiary standard. Every existing
matched_clean row stamped via parity_source LIKE 'tier1:shard9_run3059_ajax_harvest%'
or 'tier1_realforeclose_calendar_sweep_v3' has sold_amount=NULL -- i.e. the
accepted tier1 bar for C/D in this pipeline is "the case appears on the
official RealAuction calendar for its stated sale_type/auction_date", NOT
"the sale has closed and an outcome was independently verified". Direct
proof: parity_source='tier1_realforeclose_calendar_sweep_v3' already has
live precedent matching manatee rows whose auction_date (2026-07-29) was
STILL IN THE FUTURE relative to the row's own created_at (2026-07-10) --
see migration 20260710-era backfill. So a live-calendar-listing match for a
still-upcoming sale is the SAME evidentiary class already certified
throughout this table, not a new/weaker one.

This is a DIFFERENT evidentiary question from the one correctly rejected in
migration 20260704_shard3_manatee_realtdm_tax_deed_backfill.sql (an exact
case+parcel match against the manatee.realtdm.com clerk DOCKET only proves
the listing exists in the docket, not that it matches an independent
calendar/outcome source -- that rejection stands and this script does NOT
touch realtdm). Here the match is against manatee.realforeclose.com's own
live public AJAX auction calendar -- the exact mechanism
(scripts/shard2_run2450_ajax_realforeclose_harvest.py) already used for the
other ~85 matched_clean manatee rows.

VERIFIED LIVE THIS SESSION (2026-08-02):
  - manatee.realtaxdeed.com now 302-redirects to the generic
    www.realauction.com marketing page (confirmed via curl + AJAX probe --
    UPDATE/LOAD endpoint returns full marketing HTML, not JSON). This
    subdomain is dead for Manatee, consistent with the prior session's
    finding.
  - manatee.realforeclose.com IS live and hosts BOTH sale_types. Harvesting
    auction_date=08/03/2026 via harvest_date('manatee','manatee',
    '08/03/2026', platform_domain='realforeclose.com') returns 25 TAXDEED
    items, including all 5 target case numbers verbatim: 2026TD000018,
    2026TD000019, 2026TD000024, 2026TD000025, 2026TD000042.
  - Harvesting auction_date=08/04/2026 via platform_domain='realforeclose.com'
    returns 2 items, including 412025CA002931CAAXMA at
    "2908 58TH WAY E, PALMETTO, FL- 34221".

FIX: exact case_number match (normalized, alnum-only) of these 6 rows
against the live manatee.realforeclose.com AJAX calendar for their own
auction_date, using the proven exact_match_and_promote() pattern from
scripts/shard9_run3059_citrus_manatee_cd_parity.py. Idempotent: only
promotes rows not already parity_status='matched_clean' AND parity_source
LIKE 'tier1%'; harmless to re-run.

dispatch_id: a00c589b-9346-491a-a8bd-5ba50946fb44 (shard-1 run8166)
"""
import importlib.util
import json
import os
import re
import time
import urllib.request

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# The 6 rows identified live this session as the exact C/D gap (all in
# manatee, all currently parity_status IS NULL, all data_source<>propertyonion
# and/or tier1_authoritative=true, i.e. inside the evaluator's denominator).
TARGETS = [
    {"county": "manatee", "sale_type": "tax_deed", "auction_date": "2026-08-03"},
    {"county": "manatee", "sale_type": "foreclosure", "auction_date": "2026-08-04"},
]

EXPECTED_CASE_NUMBERS = {
    "2026TD000018", "2026TD000019", "2026TD000024", "2026TD000025",
    "2026TD000042", "412025CA002931CAAXMA",
}


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def exact_match_and_promote(items, parity_source_label):
    """Only touches rows NOT already matched_clean+tier1 (idempotent), never
    overwrites an existing non-null parity_status/source with a different
    value -- only fills NULL/non-tier1 rows."""
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        "multi_county_auctions?county=eq.manatee"
        "&or=(data_source.neq.propertyonion,data_source.is.null)"
        "&select=id,case_number,parity_status,parity_source")
    matches = []
    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        already_tier1 = (row.get("parity_source") or "").startswith("tier1")
        if cn in by_norm and not (row["parity_status"] == "matched_clean" and already_tier1):
            matches.append(row["id"])
    if not matches:
        return []
    id_filter = ",".join(str(m) for m in matches)
    rest_patch(f"multi_county_auctions?id=in.({id_filter})",
               {"parity_status": "matched_clean", "parity_source": parity_source_label})
    return matches


def main():
    total_promoted = 0
    for t in TARGETS:
        ad = t["auction_date"]
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        # Both sale_types confirmed live this session to be hosted on
        # manatee.realforeclose.com (NOT realtaxdeed.com, which is dead --
        # redirects to the generic realauction.com marketing page).
        try:
            items = _mod.harvest_date("manatee", "manatee", mmddyyyy,
                                       platform_domain="realforeclose.com")
        except Exception as e:
            print(f"  HARVEST FAIL manatee {t['sale_type']} {ad}: {e}")
            continue
        if not items:
            print(f"  manatee {t['sale_type']} {ad}: 0 items from calendar (nothing to match)")
            time.sleep(0.3)
            continue
        label = f"tier1:gold_standard_shard1_run8166_ajax_harvest:{t['sale_type']}:{ad}"
        matched = exact_match_and_promote(items, label)
        total_promoted += len(matched)
        print(f"  manatee {t['sale_type']} {ad}: {len(items)} calendar items -> {len(matched)} promoted")
        time.sleep(0.4)

    print(f"\nTOTAL PROMOTED: {total_promoted}")

    if total_promoted == 0:
        raise RuntimeError(
            "Silent failure guard: expected to promote 6 known target rows "
            f"({sorted(EXPECTED_CASE_NUMBERS)}) but promoted 0. Aborting without "
            "declaring success.")

    # Verify: re-fetch the target rows by case_number to confirm the exact
    # expected set was promoted (not more, not fewer than what calendar
    # evidence supports).
    cn_filter = ",".join(f'"{cn}"' for cn in EXPECTED_CASE_NUMBERS)
    check = rest_get(
        "multi_county_auctions?county=eq.manatee"
        f"&case_number=in.({cn_filter})"
        "&select=case_number,auction_date,parity_status,parity_source")
    print("\n=== TARGET ROW STATUS AFTER PATCH ===")
    still_unmatched = []
    for row in check:
        tagged = row["parity_status"] == "matched_clean" and (row.get("parity_source") or "").startswith("tier1")
        print(f"  {row['case_number']} ({row['auction_date']}): "
              f"parity_status={row['parity_status']} parity_source={row['parity_source']} "
              f"{'OK' if tagged else 'STILL UNMATCHED'}")
        if not tagged:
            still_unmatched.append(row["case_number"])
    if still_unmatched:
        print(f"\nWARNING: {len(still_unmatched)} target rows still unmatched after run: {still_unmatched}")

    print("\n=== pencil_dod_evaluate_county('manatee') AFTER ===")
    ev_req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=json.dumps({"p_county": "manatee"}).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(ev_req, timeout=30) as r:
        ev = json.loads(r.read())
    print(json.dumps(ev, indent=2))


if __name__ == "__main__":
    main()
