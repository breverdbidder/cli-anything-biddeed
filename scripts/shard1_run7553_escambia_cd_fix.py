#!/usr/bin/env python3
"""SHARD-1 escambia C/D fix, gold-standard loop run 7553, 2026-07-31.
dispatch_id: 2931b3a1-9b07-4419-adba-fe711f1d0a56

Baseline (from loop run 7553 brief): escambia C=D=87.0%
(matched_clean=347 / auctions_total=399), ~52 unmatched rows.

Prior session history:
- shard14 run5361 (2026-07-20): 259→274 promoted (8 foreclosure 07/28+07/29,
  3 tier1_authoritative tax_deed 08/05). 70 tax_deed residual.
- shard_cd run20260724: 274→297 promoted (1 foreclosure 07/23, 13 tier1_auth
  08/05 rows that prior scripts missed due to NULL data_source bug). Fixed the
  NULL data_source gap-query bug -- this script uses the same two-arm union.
- shard9 1a7d03e0 (2026-07-24 2nd firing): 297→321 promoted (24 new matches
  on 08/05+09/02 tax-deed dates). Residual 74 rows.
- Loop run 7553 baseline: 347 matched_clean / 399 total = 87%.

Since the prior session (2026-07-24), auctions_total grew 395→399 (4 new rows),
which means 4 more rows need to be checked. Also need to check new foreclosure
dates: 2026-07-31 (today), 2026-08-04, and any others that have appeared since
the last probe.

Probe strategy (VERIFIED pattern from prior sessions):
- Foreclosure: realforeclose.com -- check all dates not yet exhaustively covered
- Tax deed: realtaxdeed.com -- re-probe same 5 dates (new certs appear as
  auction approaches); also probe any new dates in gap rows

Root cause of residual (CONFIRMED): our calendar-sweep TD cert numbers for the
5 far-future dates (08/05-12/02/2026) diverge from what RealAuction currently
lists. This is NOT a matcher bug -- the live calendar has 60+ items per date
but zero exact case_number overlap. Do not force-match.

Idempotent: only patches rows with parity_status IS NULL matched by exact
normalized case_number. Zero rows patched = genuine residual, not silent failure.
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
PARITY_SOURCE = "tier1_realauction_escambia_shard1_run7553"

FORECLOSURE_DATES = [
    "07/31/2026",
    "08/04/2026",
    "08/05/2026",
    "08/11/2026",
    "08/18/2026",
    "08/25/2026",
]
TAXDEED_DATES = [
    "08/05/2026",
    "09/02/2026",
    "10/07/2026",
    "11/04/2026",
    "12/02/2026",
]


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


def rpc_evaluate():
    """Run pencil_dod_evaluate_county for escambia and return the result."""
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=json.dumps({"p_county": COUNTY_SLUG}).encode(),
        method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    print(f"=== ESCAMBIA C/D FIX — run7553, {COUNTY_SLUG} ===")

    before = None
    try:
        before = rpc_evaluate()
        print(f"BEFORE: {json.dumps(before)}")
    except Exception as e:
        print(f"  evaluate BEFORE failed (non-fatal): {e}")

    live_items = {}
    for d in FORECLOSURE_DATES:
        try:
            items = fixmod.harvest_date_paginated(COUNTY_SLUG, COUNTY_SLUG, d, "realforeclose.com")
            print(f"  realforeclose {d}: {len(items)} items")
            for it in items:
                cn = norm_case_number(it.get("case_number"))
                if cn:
                    live_items[cn] = it
        except Exception as e:
            print(f"  realforeclose {d}: ERROR {e}")
        time.sleep(0.4)

    for d in TAXDEED_DATES:
        try:
            items = fixmod.harvest_date_paginated(COUNTY_SLUG, COUNTY_SLUG, d, "realtaxdeed.com")
            print(f"  realtaxdeed {d}: {len(items)} items")
            for it in items:
                cn = norm_case_number(it.get("case_number"))
                if cn:
                    live_items[cn] = it
        except Exception as e:
            print(f"  realtaxdeed {d}: ERROR {e}")
        time.sleep(0.4)

    print(f"Total live items collected: {len(live_items)}")

    # Two-arm query to avoid NULL data_source exclusion bug (VERIFIED fix from
    # shard_cd_run20260724: PostgREST `data_source.neq.propertyonion` silently
    # drops rows where data_source IS NULL; must union both arms explicitly).
    gap_rows_a = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&data_source=neq.propertyonion"
        f"&parity_status=is.null&select=id,case_number,sale_type,auction_date&limit=500")
    gap_rows_b = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&tier1_authoritative=eq.true"
        f"&parity_status=is.null&select=id,case_number,sale_type,auction_date&limit=500")
    gap_rows_by_id = {r["id"]: r for r in gap_rows_a}
    gap_rows_by_id.update({r["id"]: r for r in gap_rows_b})
    gap_rows = list(gap_rows_by_id.values())
    print(f"Gap rows (non-PO OR tier1_authoritative, parity_status null): {len(gap_rows)}")

    matches = [r for r in gap_rows if norm_case_number(r.get("case_number", "")) in live_items]
    print(f"Exact matches: {len(matches)}")
    for m in matches:
        print(f"  id={m['id']} case={m['case_number']} type={m['sale_type']} date={m['auction_date']}")

    if not matches:
        print("NO CANDIDATE MATCHES FOUND -- 0 rows to patch this run "
              f"(genuine residual: {len(live_items)} live items harvested, "
              f"zero overlapped by exact case_number with current gap set of {len(gap_rows)} rows).")
    else:
        ids = ",".join(str(m["id"]) for m in matches)
        resp = rest_patch(
            f"multi_county_auctions?id=in.({ids})",
            {"parity_status": "matched_clean", "parity_source": PARITY_SOURCE})
        print(f"Patched: {len(resp)} rows")
        if len(resp) != len(matches):
            raise RuntimeError(
                f"FAIL-LOUD: expected to patch {len(matches)} rows but PATCH "
                f"returned {len(resp)} rows -- partial/failed write, do not treat as success")

    print(f"Residual (genuine, not matched): {len(gap_rows) - len(matches)}")

    after = None
    try:
        after = rpc_evaluate()
        print(f"AFTER: {json.dumps(after)}")
    except Exception as e:
        print(f"  evaluate AFTER failed (non-fatal): {e}")

    if before and after:
        c_before = next((x for x in (before if isinstance(before, list) else [before]) if x.get("letter") == "C"), before.get("C") if isinstance(before, dict) else None)
        c_after = next((x for x in (after if isinstance(after, list) else [after]) if x.get("letter") == "C"), after.get("C") if isinstance(after, dict) else None)
        print(f"\nC metric: {c_before} → {c_after}")

    return len(matches)


if __name__ == "__main__":
    main()
