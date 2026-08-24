#!/usr/bin/env python3
"""GOLD STANDARD shard-4, dispatch 7d59c973-434c-4b8c-a699-e820f9093c39, county=st_johns.

Fixes C (parity_clean) and D (parity_any).

ROOT CAUSE (confirmed live via PostgREST before writing):
  CA23-1974 and CA25-1600 both carry parity_status='matched_clean' but
  parity_source=NULL. They share tier1_source_run_id=153084 and
  tier1_verified_at=2026-08-24T08:15:00.383266+00:00 with CA25-1470, a third
  row from the exact same batch that DOES carry a parity_source value:
  'tier1_realforeclose_aids_st_johns'. That label is independently confirmed
  as the real, already-used precedent for this county's RealForeclose
  tier1-verification pipeline (9 existing st_johns rows already use it,
  including matched_clean rows CA22-1233, CA25-0128, CA25-0351, CA25-0475,
  CA25-1757, CA25-1779, CC25-0048, CC25-2919, plus CA25-1470 itself).

  This is a real re-label of an already-true verification state -- the
  underlying tier1 verification already ran (tier1_verified_at/
  tier1_source_run_id populated identically to the labeled sibling row);
  only the parity_source string was never written by that run.

  NOTE: diagnosis from the prior stage guessed the label
  'tier1_realforeclose_stjohns_calendar'. That guess is WRONG -- the actual
  evidenced sibling-row label for run_id=153084 is
  'tier1_realforeclose_aids_st_johns'. Using the guessed label would have
  been an unverified fabrication; using the real sibling-row label is not.

  CA25-1742 (parity_status='matched_divergent') ALSO shares the identical
  tier1_source_run_id=153084 / tier1_verified_at with CA23-1974/CA25-1600,
  confirming it went through the same same-day RealForeclose verification
  batch. Backfilling its parity_source the same way is equally evidenced
  (not a fabrication) and additionally lifts D's matched_any set.

TD26-0024, TD26-0034, TD26-0038 (PHANTOM_NOT_ON_CLERK) and TD26-0031
(CLERK_SSOT_CANCELLED) are NOT touched -- genuine parity anomalies, not a
labeling gap; relabeling them would be exactly the "ghost-success" pattern
this campaign bans.

Guardrail 2 (fail-loud): if the PATCH returns 0 rows for a case_number we
expected to update, raise -- do not swallow it.
"""
import os
import sys
import json
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "st_johns"
LABEL = "tier1_realforeclose_aids_st_johns"

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def patch(case_number, expected_parity_status):
    path = (
        f"/rest/v1/multi_county_auctions"
        f"?county=eq.{COUNTY}&case_number=eq.{case_number}"
        f"&parity_source=is.null"
    )
    req = urllib.request.Request(
        SUPABASE_URL + path,
        data=json.dumps({"parity_source": LABEL}).encode(),
        headers=HEADERS,
        method="PATCH",
    )
    resp = urllib.request.urlopen(req, timeout=30)
    body = json.loads(resp.read().decode())
    if len(body) != 1:
        raise RuntimeError(
            f"FAIL-LOUD: expected exactly 1 row updated for {case_number}, got {len(body)}"
        )
    row = body[0]
    if row["parity_status"] != expected_parity_status:
        raise RuntimeError(
            f"FAIL-LOUD: {case_number} parity_status drifted to "
            f"{row['parity_status']}, expected {expected_parity_status}"
        )
    return row


def main():
    targets = [
        ("CA23-1974", "matched_clean"),
        ("CA25-1600", "matched_clean"),
        ("CA25-1742", "matched_divergent"),
    ]
    written = []
    for case_number, expected_status in targets:
        row = patch(case_number, expected_status)
        written.append(row["case_number"])
        print(f"OK  {case_number}: parity_source -> {row['parity_source']} "
              f"(parity_status={row['parity_status']})")

    if len(written) != len(targets):
        raise RuntimeError(
            f"FAIL-LOUD: parsed {len(targets)} targets but only wrote {len(written)}"
        )

    print(f"\nTotal rows written: {len(written)} -> {written}")


if __name__ == "__main__":
    main()
