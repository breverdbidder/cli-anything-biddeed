#!/usr/bin/env python3
"""ESCAMBIA C/D residual fix, session 2026-08-28.

Baseline (VERIFIED live this session via pencil_dod_evaluate_county):
  escambia C=94.8% (matched_clean=473), D=95.0% (matched_any=474), auctions_total=499.
  25 non-PO rows with parity_status IS NULL, all data_source='calendar_sweep_mca_v3'
  (or data_source NULL for one row -- 2026 CC 002930):
    foreclosure: 09/02/2026 (2), 09/03/2026 (1), 09/08/2026 (2)
    tax_deed:    01/06/2027 (20)

These are all UPCOMING sales (none has occurred yet). 'matched_clean' for an
upcoming sale in this canon means: confirmed as a genuine, currently-scheduled
sale on the live Escambia RealAuction calendar
(escambia.realforeclose.com / escambia.realtaxdeed.com) -- NOT a sale outcome.

Method: harvest_date_paginated() (see scripts/shard8_charlotte_levy_monroe_
osceola_madison_cd_fix.py) against subdomain 'escambia' for platform_domain
'realforeclose.com' (the 3 foreclosure dates) and 'realtaxdeed.com' (the single
01/06/2027 tax-deed date). Exact case_number match only (normalize by
stripping non-alphanumerics, uppercasing -- same convention as every prior
escambia C/D session, e.g. gold_standard_shard1_escambia_cd_fix_2931b3a1.py).

RESULT this session: harvested 66 live items total (2+1+3 foreclosure +
60 tax-deed on 01/06/2027). 19 of the 25 gap rows matched exactly by
case_number and were PATCHed to parity_status='matched_clean'. 6 rows
(2024 TD 001893, 2024 TD 002005, 2024 TD 002006, 2024 TD 001993,
2024 TD 001975, 2024 TD 001870) did NOT appear in the live 01/06/2027
tax-deed list of 60 items -- genuine residual, left untouched
(BLANK > WRONG; no fabricated match).

Idempotent: only PATCHes rows with parity_status IS NULL (id=eq.<id>&
parity_status=is.null). Re-running finds these rows already matched_clean
and will patch 0 (all live-matched rows already covered).

Note: this session hit repeated PostgREST 500 "55P03 canceling statement due
to lock timeout" and one 503/timeout during multi-row batch PATCH attempts
(id=in.(...)), almost certainly from concurrent parallel gold-standard shard
sessions writing to the same multi_county_auctions table. Switched to
single-row PATCH (id=eq.<id>) with retry/backoff, which succeeded 19/19 with
zero failures once contention cleared.

RESULT (verified live via pencil_dod_evaluate_county('escambia') after patch):
  C: PASS, matched_clean=492 (98.6%)
  D: PASS, matched_any=493 (98.8%)

Usage: python3 scripts/gold_standard_escambia_cd_gap25_run20260828.py
"""
import os
import re
import json
import time
import importlib.util
import urllib.request
import urllib.error

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
PARITY_SOURCE = "tier1_realauction_escambia_shard1_run_20260828_cd_gap25"

FORECLOSURE_DATES = ["09/02/2026", "09/03/2026", "09/08/2026"]
TAXDEED_DATES = ["01/06/2027"]

TARGET_CASES = [
    "2024 TD 002484", "2024 TD 002483", "2024 TD 001817", "2024 TD 001893",
    "2024 TD 002005", "2024 TD 002006", "2024 TD 001993", "2024 TD 002372",
    "2024 TD 002347", "2024 TD 001841", "2024 TD 001782", "2024 TD 001807",
    "2024 TD 002465", "2024 TD 002527", "2024 TD 001975", "2024 TD 002491",
    "2024 TD 002341", "2024 TD 002525", "2024 TD 001870", "2025 CA 001769",
    "2026 CA 000155", "2026 CC 002930", "2026 CA 000047", "2025 CA 001880",
    "2025 CA 001976",
]


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch_one(row_id, body, retries=8):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}&parity_status=is.null",
        data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            last_err = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"PATCH failed for {row_id} after {retries} attempts: {last_err}")


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
    print(f"TOTAL live items harvested: {len(live_items)}")

    gap_rows_a = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&data_source=neq.propertyonion"
        f"&parity_status=is.null&select=id,case_number,sale_type,auction_date&limit=200")
    gap_rows_null = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&data_source=is.null"
        f"&parity_status=is.null&select=id,case_number,sale_type,auction_date&limit=200")
    by_id = {r["id"]: r for r in gap_rows_a}
    by_id.update({r["id"]: r for r in gap_rows_null})
    gap_rows = [r for r in by_id.values() if r["case_number"] in TARGET_CASES]
    print(f"gap rows (of the 25 target cases still parity_status IS NULL): {len(gap_rows)}")

    matches = [r for r in gap_rows if norm_case_number(r["case_number"]) in live_items]
    print(f"exact matches: {len(matches)}")

    if not matches:
        print("NO CANDIDATE MATCHES FOUND -- 0 rows to patch this run "
              "(genuine residual, not a silent failure).")

    patched = []
    for m in matches:
        resp = rest_patch_one(m["id"], {"parity_status": "matched_clean", "parity_source": PARITY_SOURCE})
        patched.extend(resp)
        print("  patched", m["id"], m["case_number"], len(resp))
        time.sleep(1)

    if len(patched) != len(matches):
        raise RuntimeError(
            f"FAIL-LOUD: expected to patch {len(matches)} rows but only "
            f"{len(patched)} PATCH responses returned -- partial/failed write, do not treat as success")

    residual = [r["case_number"] for r in gap_rows if norm_case_number(r["case_number"]) not in live_items]
    print(f"residual (genuine, undocumented as matched): {len(residual)}")
    for cn in residual:
        print("  RESIDUAL", cn)


if __name__ == "__main__":
    main()
