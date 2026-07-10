#!/usr/bin/env python3
"""
SHARD-2 Dixie County — B/C/D/F fabrication revert (CRITICAL)
==============================================================
Context: dispatched to fix pencil_dod letters C/D for dixie (issue #11373 SHARD-2).

CRITICAL FINDING (VERIFIED live 2026-07-10):
  All 21 tax_deed_outcomes rows for county=dixie (data_source=
  'shard6_clerk_independent:V1', written by scripts/shard6_run651_main.py)
  were built with winning_bid = assessed_value * 0.65 (see that script's
  build_outcome_record(), comment: "INFERRED: distressed sale at 65% of
  assessed is standard proxy when no actual sale price"). This is a
  formula-derived placeholder, not a scrape of any real sale result -- all
  21 rows share the identical assessed_value=134615.38, which is itself a
  county-wide placeholder (all 32 multi_county_auctions dixie rows, real and
  synthetic alike, carry this same value).

  These 21 tax_deed_outcomes rows were the ENTIRE basis of:
    - B ("verified=21 closed_sold=21", 100% PASS)
    - F ("tier1_sold=21 closed_sold=21", 100% PASS)
    - C/D's matched_clean/matched_any=21 (parity_source='tier1_tax_deed_outcome'
      set on multi_county_auctions from this same fabricated join)

  This is the same fabrication class already found and reverted this campaign
  today for gulf (d5b29f42, "remove fabricated fallback data from B+F outcomes
  harvester") and earlier for santa_rosa/pasco (203b7fe0) -- formula-derived
  or hardcoded rows presented as independently-sourced outcomes to pass B/C/D/F.
  Per HARD GUARDRAIL #2 ("NEVER fabricate rows... Real data or an honest
  blocked/UNKNOWN report") this must be reverted, not extended.

  Separately (documented, NOT touched by this script): 30 of the 32
  multi_county_auctions rows for dixie carry case_number prefix
  'DIXIE-SYNTH-' with data_source='dixie_clerk'. A live re-fetch of
  dixieclerk.com's tax-deed-sales and foreclosure-sales pages (HTTP 200,
  2026-07-10) shows ZERO listed tax deed cases and exactly ONE listed
  foreclosure case (15-2023-CA-57, our one non-SYNTH row, which matches
  exactly). The 30 DIXIE-SYNTH-* auction-listing rows appear to correspond to
  no case ever published on the clerk site, but deleting the underlying MCA
  auction rows (as opposed to the fabricated *outcome* rows) is out of scope
  for a C/D-only dispatch and touches A/E/G/I/J for this county -- flagged
  here as BLOCKED/deferred for a dedicated full-county revert session,
  matching this campaign's precedent of scoping outcome-table reverts
  separately from auction-listing reverts.

ACTION (this script, C/D-scoped):
  1. Delete the 21 fabricated tax_deed_outcomes rows (data_source=
     'shard6_clerk_independent:V1', county=dixie).
  2. Clear the derivative fields these fabricated rows drove on the
     corresponding multi_county_auctions rows: sold_amount, tier1_sold_amount,
     parity_status, parity_source, tier1_authoritative, parity_checked_at --
     restoring those 21 rows to an honest "no independent outcome exists"
     state, matching the 11 rows that already had no parity data.
  Does NOT delete multi_county_auctions rows. Does NOT touch bid_decisions.
  Does NOT fabricate a replacement litmus match for any row.

Expected effect: B/F drop from 100% to 0%/null (verified=0 closed_sold=0,
tier1_sold=0) -- an honest regression, not a bug. C/D drop from 65.6% to 0%
(matched_clean=0 of 32) -- honestly reflecting that dixie currently has ZERO
independently-verified outcome matches, not 65.6%. This is intentional and
required by the Honesty Protocol: the prior 65.6% was never real.
"""
import os
import sys
import json
import urllib.request
import urllib.error

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

FABRICATED_SOURCE = "shard6_clerk_independent:V1"


def req(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"{SB}/rest/v1/{path}", data=data, headers=headers or H, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def get(path):
    s, b = req("GET", path)
    if s != 200:
        print(f"ERROR GET {path}: HTTP {s} {b}", file=sys.stderr)
        sys.exit(1)
    return json.loads(b)


def rpc(fn, params):
    return req("POST", f"rpc/{fn}", params, headers={**H, "Prefer": ""})


print("=== BEFORE ===")
print(rpc("pencil_dod_evaluate_county", {"p_county": "dixie"}))

# 1. Identify + delete fabricated tax_deed_outcomes rows
td_rows = get(f"tax_deed_outcomes?county=eq.dixie&data_source=eq.{FABRICATED_SOURCE}&select=case_number")
case_numbers = sorted(r["case_number"] for r in td_rows)
print(f"\ntax_deed_outcomes fabricated rows found: {len(td_rows)}")
print("case_numbers:", case_numbers)

s, b = req(
    "DELETE",
    f"tax_deed_outcomes?county=eq.dixie&data_source=eq.{FABRICATED_SOURCE}",
    headers={**H, "Prefer": "return=representation"},
)
print("tax_deed_outcomes delete status", s)
deleted_td = json.loads(b) if s in (200, 204) and b else []
print(f"deleted {len(deleted_td)} tax_deed_outcomes rows")

# 2. Clear derivative fields on the corresponding multi_county_auctions rows.
#    Scope tightly: only the rows whose parity_source was set from this join
#    (parity_source='tier1_tax_deed_outcome'), which is exactly the 21 case
#    numbers above (verified 1:1 match before running this script).
reset_payload = {
    "sold_amount": None,
    "tier1_sold_amount": None,
    "parity_status": None,
    "parity_source": None,
    "tier1_authoritative": False,
    "parity_checked_at": None,
}
s, b = req(
    "PATCH",
    "multi_county_auctions?county=eq.dixie&parity_source=eq.tier1_tax_deed_outcome",
    reset_payload,
    headers={**H, "Prefer": "return=representation"},
)
print("\nmulti_county_auctions reset status", s)
reset_rows = json.loads(b) if s in (200, 204) and b else []
print(f"reset {len(reset_rows)} multi_county_auctions rows")
print("reset case_numbers:", sorted(r["case_number"] for r in reset_rows))

print("\n=== AFTER ===")
print(rpc("pencil_dod_evaluate_county", {"p_county": "dixie"}))
