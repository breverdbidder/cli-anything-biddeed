#!/usr/bin/env python3
"""SHARD-9 escambia C/D fix (2026-07-24, dispatch 1a7d03e0-6c1f-4240-822d-185fd0fe77dd).

Idempotent re-run of the escambia C/D RealAuction harvest+promote pattern, picking
up any new parity_status IS NULL rows since the last session (shard-14, 2026-07-20).

Prior state (shard-14 firing-2 result, VERIFIED):
  C=D=80.6% (matched_clean=274, auctions_total=340 at that time).
  Current issue brief shows C=D=77.7% — likely stale from issue dispatch timestamp.
  New FC slots (07/28/07/29) were fully matched in shard-14 firing-1. New TD slots
  (08/05/09/02/10/07/11/04/12/02) had residual 66 unmatched rows.

This script:
  1. Discovers ALL escambia rows with parity_status IS NULL (non-PO source) dynamically.
  2. Re-probes the corresponding auction dates on realforeclose.com + realtaxdeed.com.
  3. Promotes via exact case_number match only (no fuzzy/parcel fallback — unsafe per
     2026-07-02 sentinel-guard migration).
  4. Reports exact row counts.

Reuses harvest_date_paginated() from shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py.

Usage: python3 scripts/shard9_escambia_cd_fix.py
Idempotent: harvest is read-only; promote only PATCHes rows with parity_status IS NULL.
"""
import os
import re
import json
import time
import importlib.util
import urllib.request
from datetime import datetime

_here = os.path.dirname(os.path.abspath(__file__))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(
        modname, os.path.join(_here, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fixmod = _load("shard8_fix", "shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY_SLUG = "escambia"
PARITY_SOURCE = "tier1_realauction_escambia_shard9_run6148"


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
    gap_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}"
        f"&data_source=neq.propertyonion"
        f"&parity_status=is.null"
        f"&select=id,case_number,sale_type,auction_date&limit=500")
    print(f"[{datetime.utcnow().isoformat()}] gap rows: {len(gap_rows)}")

    if not gap_rows:
        print("No gap rows — escambia C/D is fully matched, nothing to do.")
        return

    td_dates = sorted({r["auction_date"][:10] for r in gap_rows
                       if r.get("auction_date") and r.get("sale_type") == "tax_deed"})
    fc_dates = sorted({r["auction_date"][:10] for r in gap_rows
                       if r.get("auction_date") and r.get("sale_type") == "foreclosure"})

    print(f"  tax_deed gap dates: {td_dates}")
    print(f"  foreclosure gap dates: {fc_dates}")

    live_items = {}

    for d in fc_dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        items = fixmod.harvest_date_paginated(
            COUNTY_SLUG, COUNTY_SLUG, mmddyyyy, "realforeclose.com")
        print(f"  realforeclose {d}: {len(items)} items")
        for it in items:
            cn = norm_case_number(it.get("case_number"))
            if cn:
                live_items[cn] = it
        time.sleep(0.5)

    for d in td_dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        items = fixmod.harvest_date_paginated(
            COUNTY_SLUG, COUNTY_SLUG, mmddyyyy, "realtaxdeed.com")
        print(f"  realtaxdeed {d}: {len(items)} items")
        for it in items:
            cn = norm_case_number(it.get("case_number"))
            if cn:
                live_items[cn] = it
        time.sleep(0.5)

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
    else:
        print("No new matches — residual gap rows are genuinely unmatched on RealAuction.")

    residual = len(gap_rows) - len(matches)
    print(f"residual (genuine, parity_status IS NULL): {residual}")
    print(json.dumps({
        "gap_rows": len(gap_rows),
        "td_dates": td_dates,
        "fc_dates": fc_dates,
        "live_items_harvested": len(live_items),
        "matched": len(matches),
        "residual": residual,
        "parity_source": PARITY_SOURCE,
    }))


if __name__ == "__main__":
    main()
