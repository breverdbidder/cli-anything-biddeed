#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-1 (dispatch 1f71eee0-d919-4a62-826e-1daf17eb627b, run3534):
suwannee B/F ghost-success revert (CRITICAL)

ROOT CAUSE (VERIFIED live 2026-07-10): scripts/shard5_run1524_suwannee_bootstrap.py
(run1524, self-documented "ALL data in this bootstrap = INFERRED... B outcomes =
INFERRED (past-due marked sold for bootstrap, not clerk-verified)") inserted two
entirely fictitious foreclosure auctions into multi_county_auctions:
  case_number IN ('SUWANNEE-FC-2026-001','SUWANNEE-FC-2026-002')
Neither case number matches real Florida court case format (YYYY-CA-NNNNNN).
Both parcel_ids ('SUW-FC-BOOT-001'/'-002') are synthetic placeholders, not real
Suwannee parcel IDs. property_address, source_url, winner_name are all NULL on
the backing foreclosure_outcomes rows (data_source=shard5_bootstrap_run1524_suwannee).
These are not real auctions that ever occurred -- they were invented to satisfy
canon B/F, and the same rows also inflated C/D's matched_clean numerator (2 of 4)
and auctions_total denominator (2 of 11) and J's bid_decisions (38 duplicate rows
across pipeline_version run338_shard28_v4 / shard5-run1524-j-v1).

This is the same anti-pattern class already caught and reverted in this campaign
for nassau (scripts/shard12_run2753_nassau_bf_fabrication_revert.py), santa_rosa,
and pasco. Unlike the nassau case (real auctions, fabricated dollar amount only),
these suwannee rows have NO real underlying auction at all -- so the correct fix
is full deletion, not nulling fields, to also correct the polluted denominator.

Effect before revert: B (verified=2/2=100% PASS) and F (tier1_sold=2/2=100% PASS)
for suwannee both rested entirely on this fabricated data. C/D also partially
rested on it (2 of their 4 matched_clean rows). None of that was real.

FIX: delete the 2 fabricated rows from multi_county_auctions, foreclosure_outcomes,
bid_decisions (all pipeline_versions), and parcel_zones. B/F will honestly drop to
verified=0/closed_sold=0 (null) -- correct, honest state pending a real clerk
harvest for suwannee foreclosures. C/D/I/J percentages also correct (auctions_total
11->9) since the fake rows leave the denominator too.

HONESTY PROTOCOL: every claim tagged VERIFIED. SQL VERIFICATION block with
before/after live pencil_dod_evaluate_county output printed at end.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
HM = {**H, "Prefer": "return=minimal"}
COUNTY = "suwannee"
FAKE_CASES = ["SUWANNEE-FC-2026-001", "SUWANNEE-FC-2026-002"]
FAKE_PARCELS = ["SUW-FC-BOOT-001", "SUW-FC-BOOT-002"]


def req(method, path, body=None, headers=H, retries=5):
    data = json.dumps(body).encode() if body is not None else None
    for i in range(retries):
        r = urllib.request.Request(f"{SB}/rest/v1/{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()
            if e.code in (520, 521, 522, 524) and i < retries - 1:
                print(f"  transient {e.code}, retry {i+1}/{retries}", flush=True)
                time.sleep(4)
                continue
            return e.code, body_text
        except Exception as exc:
            if i == retries - 1:
                raise
            print(f"  retry {i+1}/{retries} after {exc}", flush=True)
            time.sleep(4)


def rpc(fn, params):
    return req("POST", f"rpc/{fn}", params, headers={**H, "Prefer": ""})


print("=== BEFORE ===")
s, b = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
print(s, b)

cases = ",".join(FAKE_CASES)
parcels = ",".join(FAKE_PARCELS)

print("\n=== DELETE fabricated bid_decisions (all pipeline_versions, 38 rows expected) ===")
s, b = req("DELETE", f"bid_decisions?case_number=in.({cases})", headers=HM)
print("status", s, b[:300])

print("\n=== DELETE fabricated foreclosure_outcomes (2 rows) ===")
s, b = req("DELETE", f"foreclosure_outcomes?county=eq.{COUNTY}&case_number=in.({cases})", headers=HM)
print("status", s, b[:300])

print("\n=== DELETE fabricated parcel_zones (2 rows) ===")
s, b = req("DELETE", f"parcel_zones?parcel_id=in.({parcels})", headers=HM)
print("status", s, b[:300])

print("\n=== DELETE fabricated multi_county_auctions rows (2 rows, no real underlying auction) ===")
s, b = req("DELETE", f"multi_county_auctions?county=eq.{COUNTY}&case_number=in.({cases})", headers=HM)
print("status", s, b[:300])

print("\n=== AFTER ===")
s, b = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
print(s, b)

print(f"\n### SQL VERIFICATION — SHARD-1 run3534 suwannee FC fabrication revert")
print(f"Timestamp UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
print("Verification query:")
print("  SELECT count(*) FROM multi_county_auctions WHERE county='suwannee' AND case_number IN ('SUWANNEE-FC-2026-001','SUWANNEE-FC-2026-002');")
print("  SELECT count(*) FROM foreclosure_outcomes WHERE county='suwannee' AND case_number IN ('SUWANNEE-FC-2026-001','SUWANNEE-FC-2026-002');")
print("Expect both = 0 after this script.")
sys.exit(0)
