#!/usr/bin/env python3
"""Gold Standard shard-3 flagler (dispatch 8da53925) — C/D litmus harvest for
the 4 parity_status=NULL foreclosure rows flagged in the session's precomputed
gap data (cd_unmatched_any, all sale_type='foreclosure', auction_date Sep/Oct
2026 — i.e. genuinely upcoming, not-yet-sold auctions arriving via
calendar_sweep_mca_v3 after flagler's last certification pass).

C is already PASS (95.7%, matched_clean=156/163) at session start, so this is
NOT required to flip a failing letter — it is an opportunistic bonus fix per
job priority #3 (freshly-ingested unmatched_any rows). Reuses the exact same
proven flagler litmus lever as scripts/gold_standard_flagler_cd_8gap_litmus_fix.py
(RealForeclose AJAX calendar harvest_date(), imported verbatim from
scripts/shard2_run2450_ajax_realforeclose_harvest.py) — no new endpoint
discovery. PropertyOnion is never used as the litmus source (checked live:
zero propertyonion rows exist for any of these 4 case_numbers in this county,
so there is nothing to litmus-compare against there anyway).

Matching rule (same standard as the 8-gap precedent):
  - live realforeclose.com AJAX calendar returns a card for the case_number
    AND its own parcel_id field EXACT-matches (digit-normalized) our stored
    parcel_id -> parity_status='matched_clean', parity_source=
    'tier1:gold_standard_shard3_flagler_20260824_cd_4gap:realforeclose_ajax'
    (tier1% prefix required for the evaluator's matched_clean/matched_any FILTER).
  - case found but parcel mismatch, or case not found on the live calendar,
    or we have no parcel_id at all to compare (2026 CA 000203, 2025 CA 000600):
    left NULL — no fabrication, BLANK > WRONG.

DB writes via PostgREST only (direct pooler confirmed stale, per every prior
shard session).
"""
import json
import os
import re
import time
import urllib.error
import urllib.request
import importlib.util

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "ajax_harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_ajax_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ajax_mod)

RUN_LABEL = "tier1:gold_standard_shard3_flagler_20260824_cd_4gap:realforeclose_ajax"

ROWS = [
    {"id": "a4355f85-4328-4d08-9c87-8bb2c1352ca5", "case_number": "2025 CA 000305",
     "parcel_id": "07-11-31-7010-00130-0150", "auction_date": "2026-09-18"},
    {"id": "c1b495e8-a142-4f7c-aaad-7372948dfe2b", "case_number": "2026 CA 000203",
     "parcel_id": None, "auction_date": "2026-10-02"},
    {"id": "eef25b05-053e-4933-bf37-c619f67adbca", "case_number": "2024 CC 000997",
     "parcel_id": "07-11-31-5531-00000-0040", "auction_date": "2026-10-02"},
    {"id": "6307e8ab-d385-45fc-836d-f97f1a21eacf", "case_number": "2025 CA 000600",
     "parcel_id": None, "auction_date": "2026-10-02"},
]


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def norm_digits(s):
    return re.sub(r"\D", "", s or "")


def main():
    by_date = {}
    for row in ROWS:
        by_date.setdefault(row["auction_date"], []).append(row)

    results = []
    for ad, group in by_date.items():
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        try:
            items = _ajax_mod.harvest_date("flagler", "flagler", mmddyyyy, platform_domain="realforeclose.com")
        except Exception as e:
            print(f"  HARVEST FAIL flagler foreclosure {ad}: {e}")
            for row in group:
                results.append((row, "harvest_fail"))
            continue

        by_cn = {(it.get("case_number") or "").strip(): it for it in items}
        for row in group:
            cn = row["case_number"]
            if not row["parcel_id"]:
                print(f"  {cn}: no stored parcel_id -- cannot litmus-compare, skip (no fabrication)")
                results.append((row, "no_parcel_id"))
                continue
            item = by_cn.get(cn)
            if not item:
                print(f"  {cn}: NOT FOUND on live realforeclose AJAX calendar for {ad}")
                results.append((row, "not_found"))
                continue
            our_parcel = norm_digits(row["parcel_id"])
            their_parcel = norm_digits(item.get("parcel_id"))
            if not our_parcel or not their_parcel or our_parcel != their_parcel:
                print(f"  {cn}: parcel MISMATCH ours={row['parcel_id']!r} theirs={item.get('parcel_id')!r} -- NOT promoted")
                results.append((row, "parcel_mismatch"))
                continue
            try:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                           {"parity_status": "matched_clean", "parity_source": RUN_LABEL})
                print(f"  {cn}: parcel EXACT match -> matched_clean")
                results.append((row, "matched_clean"))
            except Exception as e:
                print(f"  PATCH FAIL {cn}: {e}")
                results.append((row, "patch_fail"))
        time.sleep(0.6)

    counts = {}
    for row, outcome in results:
        counts[outcome] = counts.get(outcome, 0) + 1
    print(f"\nTOTALS: {counts}")
    if len(results) != len(ROWS):
        raise RuntimeError(f"Expected {len(ROWS)} rows processed, got {len(results)} -- fail-loud")


if __name__ == "__main__":
    main()
