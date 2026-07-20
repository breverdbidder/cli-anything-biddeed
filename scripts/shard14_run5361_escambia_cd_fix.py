#!/usr/bin/env python3
"""SHARD-14 escambia C/D fix (2026-07-20 gold-standard fixer session, run 5361).
dispatch_id: a7bdb48f-8748-4a1c-8539-d996dcda9e73

Baseline (VERIFIED live this session via pencil_dod_evaluate_county): escambia
C=D=76.2% (matched_clean=259 / auctions_total=340), 81 gap rows with
parity_status IS NULL -- 73 tax_deed (5 far-future dates: 2026-08-05/09-02/10-07/
11-04/12-02) and 8 foreclosure (2026-07-28/07-29, all newly listed since the
shard13 session which only saw 1 foreclosure gap row on 07-23).

Prior session context (commit history, scripts/shard13_escambia_cd_fix.py):
shard13 probed the same 5 tax_deed dates and found ZERO live overlap -- a
genuine gap, not a matcher bug, because those dates were too far out for the
county to have posted listings yet. This session re-probed the same 5 dates
(now 16 days to ~4.5 months closer to the sale date) plus the 2 new foreclosure
dates, using the shared harvest_date_paginated() + exact-case_number-only
matching from scripts/shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py.

Result (VERIFIED via live escambia.realforeclose.com / escambia.realtaxdeed.com
AJAX harvest + exact case_number match against multi_county_auctions):
  - foreclosure 07/28/2026 + 07/29/2026: 8/8 gap case numbers matched live
    (2025 CA 001053, 001226, 001927, 002045, 001091, 001381, 001796,
    2026 CA 000001). All 8 promoted.
  - tax_deed 5 dates: now 60-61 items live per date (calendar has populated
    since shard13's probe), but only 3/73 gap case numbers exact-matched
    (2024 TD 001944, 2024 TD 003128, 2024 TD 005029). All 3 promoted.
  - Total: 11 rows promoted matched_clean, parity_source=
    'tier1_realauction_escambia_shard14_run5361'.

Residual (HONEST, not forced): 70 of the 73 tax_deed gap rows have zero
overlap by exact case_number against the live, now-populated RealAuction
calendar for their auction date. This means our calendar-sweep-sourced TD
case numbers for those slots do not correspond to what RealAuction is
currently listing for the same date -- most likely our calendar sweep source
and RealAuction's TD certificate list diverge upstream (different TD cert
numbers get pulled/substituted/redeemed before the sale posts). No fuzzy or
parcel-only match was attempted (unguarded parcel_id arm is unsafe per the
2026-07-02 sentinel-guard migration) -- left parity_status IS NULL, documented
as a genuine residual for next session.

Verified live via pencil_dod_evaluate_county('escambia') after promotion:
  C: 76.2 -> 79.4 (matched_clean 259 -> 270)
  D: 76.2 -> 79.4 (matched_any 259 -> 270)
  No other letter regressed (E/F/H/I/J unchanged; A/B/H were already PASS).

Usage: python3 scripts/shard14_run5361_escambia_cd_fix.py
Idempotent: harvest is read-only; promote only PATCHes rows with
parity_status IS NULL matched by exact normalized case_number.
"""
import os
import re
import json
import importlib.util
import urllib.request

_here = os.path.dirname(os.path.abspath(__file__))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_here, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fixmod = _load("shard8_fix", "shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY_SLUG = "escambia"
PARITY_SOURCE = "tier1_realauction_escambia_shard14_run5361"

FORECLOSURE_DATES = ["07/28/2026", "07/29/2026"]
TAXDEED_DATES = ["08/05/2026", "09/02/2026", "10/07/2026", "11/04/2026", "12/02/2026"]


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def main():
    live_items = {}
    for d in FORECLOSURE_DATES:
        items = fixmod.harvest_date_paginated(COUNTY_SLUG, COUNTY_SLUG, d, "realforeclose.com")
        print(f"realforeclose {d}: {len(items)} items")
        for it in items:
            cn = norm_case_number(it.get("case_number"))
            if cn:
                live_items[cn] = it
    for d in TAXDEED_DATES:
        items = fixmod.harvest_date_paginated(COUNTY_SLUG, COUNTY_SLUG, d, "realtaxdeed.com")
        print(f"realtaxdeed {d}: {len(items)} items")
        for it in items:
            cn = norm_case_number(it.get("case_number"))
            if cn:
                live_items[cn] = it

    gap_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&data_source=neq.propertyonion"
        f"&parity_status=is.null&select=id,case_number,sale_type,auction_date&limit=200")
    print(f"gap rows (non-PO, parity_status null): {len(gap_rows)}")

    matches = [r for r in gap_rows if norm_case_number(r["case_number"]) in live_items]
    print(f"exact matches: {len(matches)}")
    for m in matches:
        print("  ", m["id"], m["case_number"], m["sale_type"], m["auction_date"])

    if matches:
        ids = ",".join(str(m["id"]) for m in matches)
        resp = rest_patch(
            f"multi_county_auctions?id=in.({ids})",
            {"parity_status": "matched_clean", "parity_source": PARITY_SOURCE})
        print(f"patched: {len(resp)}")

    print(f"residual (genuine, undocumented as matched): {len(gap_rows) - len(matches)}")


if __name__ == "__main__":
    main()
