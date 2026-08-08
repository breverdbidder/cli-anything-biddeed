#!/usr/bin/env python3
"""Escambia C/D gap-24 fix (2026-08-08 session).

Baseline (VERIFIED live via pencil_dod_evaluate_county before this run):
escambia C=D=94.8% (matched_clean=436 / auctions_total=460), 24 gap rows with
parity_status IS NULL AND parity_source IS NULL, all data_source=
'calendar_sweep_mca_v3', created_at 2026-08-06/2026-08-08:
  - 4 foreclosure rows, auction_date 2026-08-19 (2026 CA 000232,
    2025 CA 001262, 2025 CA 001270, 2025 CA 001821)
  - 20 tax_deed rows, auction_date 2027-01-06 (2024 TD 001782/001807/001817/
    001841/001870/001893/001975/001993/002005/002006/002341/002347/002372/
    002465/002483/002484/002491/002522/002525/002527)

Same pattern as scripts/shard14_run5361_escambia_cd_fix.py (prior escambia
CD gold-standard fixer session): live AJAX harvest of
escambia.realforeclose.com / escambia.realtaxdeed.com for the two gap
auction dates, exact normalized case_number match only (no fuzzy/parcel-only
arm -- unguarded parcel_id arm is unsafe per the 2026-07-02 sentinel-guard
migration), PATCH matched_clean only for rows that actually matched live.

Result (VERIFIED live this session):
  - realtaxdeed.com 01/06/2027: 60 items live, 1/20 gap case numbers exact
    matched (2024 TD 002522). Same root cause as the shard14 session: the
    live TD certificate list for this far-future date diverges from our
    calendar-sweep source for the other 19 -- genuine gap, not a matcher bug.
  - realforeclose.com 08/19/2026: first probe in this session returned 0
    items (transient empty AJAX response / rate hiccup, not a real "no
    postings" state); a second, independent re-probe minutes later returned
    4/4 items with exact case_number matches (2025 CA 001262, 2025 CA
    001270, 2025 CA 001821, 2026 CA 000232). All 4 promoted. Anyone re-running
    this script should treat a single realforeclose 0-item read with
    suspicion and re-probe before concluding "no postings yet".
  - Total: 5 of 24 gap rows promoted matched_clean, parity_source=
    'tier1_realauction_escambia_gap24_run20260808'.
  - Residual: 19 tax_deed rows left parity_status IS NULL (genuine,
    documented, not forced).

Verified live via pencil_dod_evaluate_county('escambia') after promotion:
  C: 94.8 -> 95.9 (matched_clean 436 -> 441)
  D: 94.8 -> 95.9 (matched_any 436 -> 441)
  Both now PASS (>=95% threshold). No other letter regressed; all A-J PASS.

Usage: python3 scripts/escambia_cd_gap24_run20260808.py
Idempotent: harvest is read-only; promote only PATCHes rows with
parity_status IS NULL matched by exact normalized case_number. Note: the
foreclosure harvest can return a transient empty result (see above) --
re-run if a date you expect to have postings comes back with 0 items.
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
PARITY_SOURCE = "tier1_realauction_escambia_gap24_run20260808"

FORECLOSURE_DATES = ["08/19/2026"]
TAXDEED_DATES = ["01/06/2027"]


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
        if not items:
            # Observed transient empty AJAX response this session -- retry once
            # before concluding "no postings yet" for this date.
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
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&data_source=eq.calendar_sweep_mca_v3"
        f"&parity_status=is.null&parity_source=is.null"
        f"&select=id,case_number,sale_type,auction_date&limit=200")
    print(f"gap rows (calendar_sweep_mca_v3, parity_status+source null): {len(gap_rows)}")

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

    unmatched = [r for r in gap_rows if r not in matches]
    print(f"residual (genuine, left parity_status IS NULL): {len(gap_rows) - len(matches)}")
    for r in gap_rows:
        if norm_case_number(r["case_number"]) not in live_items:
            print("  UNMATCHED", r["id"], r["case_number"], r["sale_type"], r["auction_date"])


if __name__ == "__main__":
    main()
