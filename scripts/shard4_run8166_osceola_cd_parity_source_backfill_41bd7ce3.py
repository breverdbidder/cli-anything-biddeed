#!/usr/bin/env python3
"""
shard4_run8166_osceola_cd_parity_source_backfill_41bd7ce3.py

Gold Standard shard-4 (dispatch 41bd7ce3, loop run 8166) -- osceola criteria C/D.

CONTEXT (fresh live check, 2026-08-23):
  osceola C = 89.3% (matched_clean=134 of 150), D = 89.3% (matched_any=134
  of 150). Both need >=95% i.e. >=143/150.

  Live diagnosis (this session): exactly 16 population rows (data_source
  IS NULL, tier1_authoritative=true -- NOT PropertyOnion) have
  parity_status='matched_clean' but parity_source IS NULL. The evaluator's
  C/D conditions require parity_source LIKE 'tier1%%' when parity_status=
  'matched_clean' -- these 16 rows fail that LIKE check purely because the
  label field was never written.

  ROUND 1 finding that BLOCKED a mechanical fix (this session, live-verified,
  not assumed): the FIRST hypothesis -- "there's one single conventional
  parity_source value for all osceola tax_deed tier1_authoritative rows,
  just backfill it" -- is FALSE. A full live query (not a truncated sample)
  shows FOUR different parity_source values in use across the 128 already-
  labeled osceola tax_deed/tier1_authoritative rows:
    tier1_realforeclose_aids_osceola        94 rows (2026-05-05 to 06-18)
    tier1:shard9_run3059_osceola_ajax_harvest  21 rows (2026-05-20 to 06-13)
    tier1_realforeclose_aids_osceola_ext     5 rows (2026-05-21 to 06-25)
    tier1_osceola_clerk_taxdeed_browserview   8 rows (2026-05-21 to 06-12)
  These four date ranges overlap heavily (no clean date-based rule) and
  none of them extend anywhere near the 16 gap rows' created_at/last_
  changed_at timestamp (2026-08-18T05:42-05:43Z, all 16 within ~1 second
  of each other -- a distinct single batch, further distinguished by
  auction_status='redeemed' on auction_date='2026-08-18', a status/shape
  none of the 4 known source pipelines produced in their sample rows).

  No script in this repo (grepped for "redeemed" + osceola/matched_clean,
  and for "2026-08-18") documents what pipeline produced this batch. With
  4 non-overlapping-in-character candidate labels and zero direct evidence
  tying the 16 gap rows to any one of them, assigning ANY of the 4 (or
  inventing a 5th) would be guessing a value to force C/D to pass -- exactly
  the fabrication pattern this campaign's guardrails prohibit (see e.g.
  scripts/shard4_run5153_osceola_i_enrichment.py's own docstring on the
  2026-07-19/07-31 Osceola PD-fallback ghost-success revert for the SAME
  county). tier1_authoritative=true and parity_status='matched_clean' are
  left AS-IS (not reverted -- no evidence they are wrong, only that their
  source label is missing and unrecoverable this session).

  DECISION: BLANK > WRONG. This script is now REPORT-ONLY. It reconfirms
  the finding live and does NOT patch parity_source. osceola C/D remain
  FAIL, documented as a genuine structural/provenance gap for a future
  session with either (a) access to the actual harvest job's logs/run-id
  that produced the 2026-08-18 redeemed batch, or (b) a live re-verification
  path (e.g. re-querying the county tax collector for these specific 16
  case numbers) that can independently confirm the match rather than just
  relabeling an unexplained existing flag.

VERIFIED (this session, live query, FULL not truncated):
  SELECT parity_source, count(*) FROM multi_county_auctions
    WHERE county='osceola' AND tier1_authoritative=true AND sale_type='tax_deed'
    AND parity_source IS NOT NULL GROUP BY parity_source;
  -> 4 distinct values, see table above. NOT a single convention.

FAIL-LOUD: if the live convention-check ever DOES resolve to a single
unambiguous value in a future run, the script still requires an explicit
code change (removal of the guard below) before it will patch -- it will
not auto-patch even a clean single-value result without a human/session
re-affirming the evidence, since the entire point of this run was that a
too-hasty assumption of "one convention" was FALSE.

Usage:
    python3 scripts/shard4_run8166_osceola_cd_parity_source_backfill_41bd7ce3.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COUNTY = "osceola"
DRY_RUN = "--dry-run" in sys.argv
CONVENTION_SOURCE = "tier1_realforeclose_aids_osceola"

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

SB_HDR = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def _retry(fn, retries=3):
    last = None
    for i in range(retries):
        try:
            return fn()
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            wait = 2 ** i
            log(f"retry {i+1}/{retries} in {wait}s: {exc}", "UNTESTED")
            time.sleep(wait)
    raise RuntimeError(f"All {retries} retries exhausted: {last}")


def sb_get(path):
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/{path}",
            headers={k: v for k, v in SB_HDR.items() if k not in ("Prefer", "Content-Type")},
        )
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read())
    return _retry(_do)


def sb_patch(path, body):
    if DRY_RUN:
        log(f"DRY-RUN PATCH {path}: {body}", "UNTESTED")
        return 1
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/{path}",
            data=json.dumps(body).encode(),
            headers=SB_HDR,
            method="PATCH",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    result = _retry(_do)
    return len(result) if isinstance(result, list) else 0


def sb_rpc(fn, params):
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/rpc/{fn}",
            data=json.dumps(params).encode(),
            headers={k: v for k, v in SB_HDR.items() if k != "Prefer"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _retry(_do)


def main():
    log("=== SHARD-4 RUN-8166 OSCEOLA C/D PARITY_SOURCE BACKFILL (dispatch 41bd7ce3) ===")
    baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE C: {baseline.get('C')} | D: {baseline.get('D')} | I: {baseline.get('I')}", "VERIFIED")

    # Re-verify the convention live (do not trust the docstring's cached number).
    convention_rows = sb_get(
        "multi_county_auctions?select=parity_source"
        "&county=eq.osceola&tier1_authoritative=eq.true&sale_type=eq.tax_deed"
        "&parity_source=not.is.null"
    )
    from collections import Counter
    counts = Counter(r["parity_source"] for r in convention_rows)
    log(f"Live convention check: {dict(counts)}", "VERIFIED")
    if len(counts) == 1:
        log(
            f"NOTE: convention is now a single value ({next(iter(counts))!r}) -- "
            "this differs from the multi-value finding this script's docstring "
            "documents. A future session should re-diagnose before assuming "
            "this script's REPORT-ONLY conclusion still applies.",
            "VERIFIED",
        )
    else:
        log(
            f"CONFIRMED: {len(counts)} distinct parity_source values in use "
            "for osceola tax_deed tier1_authoritative rows -- no single "
            "convention exists, backfilling would be a guess.",
            "VERIFIED",
        )

    gap_rows = sb_get(
        "multi_county_auctions?select=id,case_number,parcel_id,sale_type,tier1_authoritative,data_source"
        "&county=eq.osceola&parity_status=eq.matched_clean&parity_source=is.null"
        "&tier1_authoritative=eq.true"
    )
    log(f"Found {len(gap_rows)} matched_clean/parity_source-null/tier1_authoritative rows", "VERIFIED")

    log(
        "REPORT-ONLY: convention check above proves >1 candidate label exists "
        "with zero evidence tying these 16 rows to any specific one -- "
        "refusing to guess (BLANK > WRONG). See docstring for full reasoning.",
        "VERIFIED",
    )
    for row in gap_rows:
        log(
            f"UNFIXED (genuine gap, not patched): {row['case_number']} "
            f"({row['parcel_id']}) -- matched_clean/tier1_authoritative=true but "
            f"parity_source unrecoverable this session",
            "VERIFIED",
        )

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print("-- Re-run to confirm (unchanged, zero writes this session):")
    print("SELECT public.pencil_dod_evaluate_county('osceola');")
    print(f"BEFORE: C={baseline.get('C')} D={baseline.get('D')} I={baseline.get('I')}")
    print(f"C/D left FAIL: {len(gap_rows)} rows have an unrecoverable parity_source provenance gap this session.")
    print("rows_patched=0 (report-only, see docstring)")


if __name__ == "__main__":
    main()
