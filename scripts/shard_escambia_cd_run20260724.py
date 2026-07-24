#!/usr/bin/env python3
"""ESCAMBIA C/D fix, gold-standard-shard C_D letter session, 2026-07-24.
dispatch_id: 1a7d03e0-6c1f-4240-822d-185fd0fe77dd

Baseline (VERIFIED live this session via pencil_dod_evaluate_county): escambia
C=D=77.7% (matched_clean=283 / auctions_total=364), 81 gap rows with
parity_status IS NULL: 1 foreclosure (2026-07-23, now past-due -- may have
posted a result since the shard14/run5361 session on 2026-07-20) and 80
tax_deed across 5 dates (2026-08-05 x18, 09-02 x21, 10-07 x14, 11-04 x10,
12-02 x19; some -08-05 rows are tier1_authoritative with data_source NULL,
apparently the same batch shard14/run5361 already promoted 11 rows from but
some remained unmatched, plus new rows appear to have been added to the
calendar sweep since).

Prior sessions (scripts/shard14_run5361_escambia_cd_fix.py, shard13, shard11)
established: (a) the same harvest_date_paginated() AJAX pattern against
escambia.realforeclose.com / escambia.realtaxdeed.com works reliably and
finds real live matches as auction dates get closer, (b) far-future tax_deed
dates historically show near-zero overlap because RealAuction's live TD
certificate list diverges from our calendar-sweep source (upstream
substitution/redemption before the sale posts), NOT a matcher bug -- do not
force-match, (c) exact case_number match only, no fuzzy/parcel arm (unsafe
per 2026-07-02 sentinel-guard migration).

This session re-probes all 6 currently-gapped dates (1 foreclosure + 5 tax
deed) now that time has passed and the calendar sweep has had more chances to
converge with RealAuction's live listings.

Also fixes a real bug found live this session in the prior scripts' gap-row
query pattern: `data_source=neq.propertyonion` via PostgREST silently drops
rows where data_source IS NULL (three-valued SQL logic), which excluded 16
of the 81 true gap rows (all `tier1_authoritative=true`) from ever being
checked by shard13/shard14. This script queries both arms explicitly and
unions by id to exactly match the evaluator's real filter
(`data_source <> 'propertyonion' OR tier1_authoritative=true`).

RESULT (VERIFIED live via pencil_dod_evaluate_county after promotion, this
session, 2026-07-24): 14 exact matches found and promoted matched_clean
(1 foreclosure 2025 CA 001574 on 07/23/2026 [past-due, now posted], 13 of
the 16 previously-unchecked tier1_authoritative/data_source-NULL tax_deed
rows on 08/05/2026). C/D: 77.7% -> 81.6% (matched_clean 283 -> 297 /
auctions_total=364). Re-ran the script again immediately after (idempotency
check): 0 new matches, 67 residual gap rows stable -- confirms genuine
residual, not a bug. Residual is 67 tax_deed rows across 08/05 (5), 09/02
(19), 10/07 (14), 11/04 (10), 12/02 (19) with zero exact case_number overlap
against the live, populated RealAuction TD calendar for those dates (60-61
items/date confirmed live) -- same root cause documented by shard13/shard14:
our calendar-sweep TD case numbers for those slots don't correspond to
what's currently listed, most likely due to upstream cert
substitution/redemption before the sale posts. GENUINELY BLOCKED, not
force-matched.

Usage: python3 scripts/shard_escambia_cd_run20260724.py
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
PARITY_SOURCE = "tier1_realauction_escambia_run20260724"

FORECLOSURE_DATES = ["07/23/2026"]
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

    # NOTE (found live this session): PostgREST's `data_source=neq.propertyonion`
    # excludes rows where data_source IS NULL (three-valued SQL logic -- NULL <>
    # 'x' is never true), silently dropping the tier1_authoritative=true /
    # data_source=NULL rows from the gap set. The evaluator's actual filter is
    # `data_source <> 'propertyonion' OR tier1_authoritative=true`, which DOES
    # include those NULL-data_source rows (since they carry tier1_authoritative=
    # true). Query both arms explicitly and union by id so nothing is missed.
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
