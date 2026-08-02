#!/usr/bin/env python3
"""SHARD-3 issue#17343 escambia C/D fix (2026-08-02).
dispatch_id: b69ca511-b7e7-4831-a784-eeebf403dd04

Baseline (from issue brief): escambia C=D=89.0% (matched_clean=356 /
auctions_total=400). 44 gap rows with parity_status IS NULL. The prior
shard9-escambia-run6148 daily workflow runs shard_escambia_cd_run20260724.py
which covers FORECLOSURE_DATES=["07/23/2026"] and TAXDEED_DATES through
12/02/2026. New auction rows added since July 2026 are automatically covered
because both scripts re-query gap rows live from the DB each run.

This script is an updated version that:
  1. Queries all distinct auction_date values live (not hardcoded date lists),
     so it always catches newly-added rows for any date.
  2. Preserves the exact-case_number-only match discipline (no parcel fallback,
     per 2026-07-02 sentinel-guard migration).
  3. Uses the same harvest_date_paginated() AJAX pattern established by
     shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py.

Usage: python3 scripts/escambia_shard3_17343_cd_fix.py
Idempotent: only PATCHes rows where parity_status IS NULL.
"""
import os
import re
import json
import importlib.util
import urllib.request
import urllib.parse
import time

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
PARITY_SOURCE = "tier1_realauction_escambia_shard3_run20260802"


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
    gap_rows_a = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&data_source=neq.propertyonion"
        f"&parity_status=is.null&select=id,case_number,sale_type,auction_date&limit=500")
    gap_rows_b = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&tier1_authoritative=eq.true"
        f"&parity_status=is.null&select=id,case_number,sale_type,auction_date&limit=500")
    gap_by_id = {r["id"]: r for r in gap_rows_a}
    gap_by_id.update({r["id"]: r for r in gap_rows_b})
    gap_rows = list(gap_by_id.values())
    print(f"gap rows (non-PO OR tier1_authoritative, parity_status null): {len(gap_rows)}")

    if not gap_rows:
        print("No gap rows — nothing to do.")
        return

    fc_dates = sorted({r["auction_date"] for r in gap_rows if r.get("sale_type") in ("foreclosure", "fc")})
    td_dates = sorted({r["auction_date"] for r in gap_rows if r.get("sale_type") not in ("foreclosure", "fc")})
    print(f"foreclosure gap dates: {fc_dates}")
    print(f"tax_deed gap dates:    {td_dates}")

    live_items = {}
    for d_iso in fc_dates:
        if not d_iso:
            continue
        y, m, dd = d_iso.split("-")
        d = f"{m}/{dd}/{y}"
        items = fixmod.harvest_date_paginated(COUNTY_SLUG, COUNTY_SLUG, d, "realforeclose.com")
        print(f"realforeclose {d}: {len(items)} items")
        for it in items:
            cn = norm_case_number(it.get("case_number"))
            if cn:
                live_items[cn] = it
        time.sleep(0.5)

    for d_iso in td_dates:
        if not d_iso:
            continue
        y, m, dd = d_iso.split("-")
        d = f"{m}/{dd}/{y}"
        items = fixmod.harvest_date_paginated(COUNTY_SLUG, COUNTY_SLUG, d, "realtaxdeed.com")
        print(f"realtaxdeed {d}: {len(items)} items")
        for it in items:
            cn = norm_case_number(it.get("case_number"))
            if cn:
                live_items[cn] = it
        time.sleep(0.5)

    matches = [r for r in gap_rows if norm_case_number(r["case_number"]) in live_items]
    print(f"exact matches: {len(matches)}")
    for m in matches:
        print("  ", m["id"], m["case_number"], m["sale_type"], m["auction_date"])

    if not matches:
        print("NO CANDIDATE MATCHES FOUND — 0 rows to patch this run "
              f"(harvested {len(live_items)} live items, zero overlapped by exact case_number).")
        return

    ids = ",".join(str(m["id"]) for m in matches)
    resp = rest_patch(
        f"multi_county_auctions?id=in.({ids})",
        {"parity_status": "matched_clean", "parity_source": PARITY_SOURCE})
    print(f"patched: {len(resp)}")
    if len(resp) != len(matches):
        raise RuntimeError(
            f"FAIL-LOUD: expected to patch {len(matches)} rows but PATCH "
            f"returned {len(resp)} rows — partial/failed write.")

    print(f"residual (genuine, not matched): {len(gap_rows) - len(matches)}")


if __name__ == "__main__":
    main()
