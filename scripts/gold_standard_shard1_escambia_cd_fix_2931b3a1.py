#!/usr/bin/env python3
"""ESCAMBIA C/D residual fix, Gold Standard shard-1 session, dispatch 2931b3a1.

Baseline (VERIFIED live this session via pencil_dod_evaluate_county):
escambia C=D=87.0% (matched_clean=347 / auctions_total=399), 52 gap rows with
parity_status IS NULL, all data_source='calendar_sweep_mca_v3':
  foreclosure: 08/11/2026 (2), 08/12/2026 (2)
  tax_deed:    09/02/2026 (8), 10/07/2026 (12), 11/04/2026 (10), 12/02/2026 (18)

Same recurring pattern documented in scripts/shard_escambia_cd_run20260724.py
and shard14_run5361_escambia_cd_fix.py: calendar-sweep keeps adding new future
auction rows faster than the tier1 RealAuction/RealTaxDeed harvest sweeps them.
This is the next incremental pass -- new dates only (08/11, 08/12 foreclosure
were not covered by any prior session; the tax_deed dates were previously
gapped and residual after 2026-07-24's pass, re-probed here since more time
has passed and RealAuction's live TD list may have converged further).

Exact case_number match only (no fuzzy/parcel arm -- unsafe per 2026-07-02
sentinel-guard migration). Idempotent: only PATCHes rows with
parity_status IS NULL.

Usage: python3 scripts/gold_standard_shard1_escambia_cd_fix_2931b3a1.py
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
PARITY_SOURCE = "tier1_realauction_escambia_shard1_2931b3a1"

FORECLOSURE_DATES = ["08/11/2026", "08/12/2026"]
TAXDEED_DATES = ["09/02/2026", "10/07/2026", "11/04/2026", "12/02/2026"]


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

    gap_rows_a = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&data_source=neq.propertyonion"
        f"&parity_status=is.null&select=id,case_number,sale_type,auction_date&limit=200")
    gap_rows_b = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&tier1_authoritative=eq.true"
        f"&parity_status=is.null&select=id,case_number,sale_type,auction_date&limit=200")
    gap_rows_by_id = {r["id"]: r for r in gap_rows_a}
    gap_rows_by_id.update({r["id"]: r for r in gap_rows_b})
    gap_rows = list(gap_rows_by_id.values())
    print(f"gap rows (non-PO OR tier1_authoritative, parity_status null): {len(gap_rows)}")

    matches = [r for r in gap_rows if norm_case_number(r["case_number"]) in live_items]
    print(f"exact matches: {len(matches)}")
    for m in matches:
        print("  ", m["id"], m["case_number"], m["sale_type"], m["auction_date"])

    if not matches:
        print("NO CANDIDATE MATCHES FOUND -- 0 rows to patch this run "
              "(genuine residual, not a silent failure: harvested "
              f"{len(live_items)} live items across {len(FORECLOSURE_DATES) + len(TAXDEED_DATES)} "
              "dates, zero overlapped by exact case_number with the current gap set).")

    if matches:
        ids = ",".join(str(m["id"]) for m in matches)
        resp = rest_patch(
            f"multi_county_auctions?id=in.({ids})",
            {"parity_status": "matched_clean", "parity_source": PARITY_SOURCE})
        print(f"patched: {len(resp)}")
        if len(resp) != len(matches):
            raise RuntimeError(
                f"FAIL-LOUD: expected to patch {len(matches)} rows but PATCH "
                f"returned {len(resp)} rows -- partial/failed write, do not treat as success")

    print(f"residual (genuine, undocumented as matched): {len(gap_rows) - len(matches)}")


if __name__ == "__main__":
    main()
