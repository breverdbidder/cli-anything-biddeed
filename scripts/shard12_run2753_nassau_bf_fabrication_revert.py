#!/usr/bin/env python3
"""
SHARD-12 (dispatch a50b350f, run2753 shard): nassau B/F fabrication revert (CRITICAL)

ROOT CAUSE (VERIFIED live 2026-07-04, independently confirmed by an adversarial
ULTRALOOP refuter agent against a fresh live query): supabase/migrations/
20260625_shard4_run581_gold_standard.sql line 46-53 explicitly defaults nassau's
sold_amount/tier1_sold_amount to a hardcoded 150000 constant ("-- nassau: use
opening_bid or default 150000 (no amount data at all)") when no real sale amount
was ever scraped. That constant was later also written into tax_deed_outcomes (5
rows) and foreclosure_outcomes (22 rows) under data_source values that *sound*
authoritative (nassau_realtaxdeed_official, nassau_realforeclose_official,
nassau_mca_official) but all carry the identical winning_bid=150000.0 regardless
of case, judgment_amount ($9K-$549K range), auction_status (upcoming/cancelled),
or auction_date (including dates in 2026-08, i.e. auctions that have not happened
yet as of today 2026-07-04). A cancelled or not-yet-occurred auction cannot have
a real sale price. This is the same anti-pattern class already reverted for
santa_rosa (scripts/shard14_run2753c_santa_rosa_ghost_revert.py) and pasco
(commit d92b5a33) earlier in this campaign.

Effect before revert: B (verified=27/27=100% PASS) and F (tier1_sold=27/27=100%
PASS) for nassau both rested entirely on this fabricated data. Neither criterion
is real.

FIX: null out sold_amount/tier1_sold_amount/tier1_verified_at/tier1_authoritative
on the 27 affected multi_county_auctions rows, and delete the 27 fabricated
outcome rows (5 tax_deed_outcomes + 22 foreclosure_outcomes) that carry the
identical placeholder winning_bid=150000.0. B/F will honestly drop to
verified=0/closed_sold=0 (null) -- this is the correct, honest state pending a
real tier1 harvest for nassau.

HONESTY PROTOCOL: every claim tagged VERIFIED. SHIP GATE: SQL VERIFICATION block
printed at end with before/after live pencil_dod_evaluate_county output.
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
COUNTY = "nassau"

TD_CASES = [
    "26TD000004AXYX", "26TD000005AXYX", "26TD000006AXYX",
    "26TD000007AXYX", "26TD000008AXYX",
]
FC_CASES = [
    "452025CA000054CAAXYX", "452023CA000402CAAXYX", "452025CA000102CAAXYX",
    "452025CA000106CAAXYX", "452023CA000419CAAXYX", "452023CA000360CAAXYX",
    "452022CA000061CAAXYX", "452025CA000382CAAXYX", "452024CA000012CAAXYX",
    "452024CA000420CAAXYX", "452025CC000239CCAXYX", "452023CA000464CAAXYX",
    "452024CC000464CCAXYX", "452024CA000350CAAXYX", "452023CA000536CAAXYX",
    "452020CA000024CAAXYX", "452025CA000304CAAXYX", "452025CA000193CAAXYX",
    "452025CA000390CAAXYX", "452026CA000050CAAXYX", "452025CA000166CAAXYX",
    "452025CA000334CAAXYX",
]
ALL_CASES = TD_CASES + FC_CASES  # 27 total, matches live 27/34 fabricated rows


def req(method, path, body=None, headers=H, retries=5):
    data = json.dumps(body).encode() if body is not None else None
    for i in range(retries):
        r = urllib.request.Request(f"{SB}/rest/v1/{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()
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

print("\n=== DELETE fabricated tax_deed_outcomes (5 rows, winning_bid=150000) ===")
cases = ",".join(TD_CASES)
s, b = req("DELETE", f"tax_deed_outcomes?county=eq.{COUNTY}&case_number=in.({cases})&winning_bid=eq.150000", headers=HM)
print("status", s, b[:300])

print("\n=== DELETE fabricated foreclosure_outcomes (22 rows, winning_bid=150000) ===")
cases = ",".join(FC_CASES)
s, b = req("DELETE", f"foreclosure_outcomes?county=eq.{COUNTY}&case_number=in.({cases})&winning_bid=eq.150000", headers=HM)
print("status", s, b[:300])

print("\n=== PATCH multi_county_auctions: null out fabricated sold_amount/tier1 fields ===")
now = datetime.now(timezone.utc).isoformat()
cases = ",".join(ALL_CASES)
patch_body = {
    "sold_amount": None,
    "tier1_sold_amount": None,
    "tier1_verified_at": None,
    "tier1_authoritative": False,
    "tier1_source_run_id": None,
    # IMPORTANT: do NOT overwrite parity_source with a non-'tier1%'-prefixed value here.
    # The live pencil_dod_evaluate_county (confirmed via Management API pg_get_functiondef,
    # NOT the stale copy in supabase/migrations/20260702_shard3_pencil_dod_f_scope_fix.sql)
    # requires `parity_status='matched_clean' AND parity_source LIKE 'tier1%%'` for C, and
    # the matched_divergent equivalent for D. A first version of this script set parity_source
    # to a non-tier1-prefixed revert tag and it silently dropped nassau C from 82.4%->20.6%
    # and D from 100%->20.6% as an unrelated side effect (caught immediately by re-running the
    # evaluator after this patch -- see the follow-up correction below). Leaving parity_source
    # untouched here avoids repeating that mistake.
}
s, b = req(
    "PATCH",
    f"multi_county_auctions?county=eq.{COUNTY}&case_number=in.({cases})&sold_amount=eq.150000",
    patch_body,
    headers=HM,
)
print("status", s, b[:300])

# NOTE (post-hoc, added after the live incident described above): the first live run of this
# script DID include a parity_source overwrite and broke C/D as described. It was corrected
# live in the same session via:
#   UPDATE multi_county_auctions SET parity_source =
#     'tier1_bf_fabrication_revert_shard12_20260704_original_source_not_recoverable'
#   WHERE county='nassau' AND parity_source =
#     'reverted_fabricated_150000_placeholder_shard12_20260704';
# The exact original per-row parity_source values (tier1_official_platform_open_auction_parcel /
# tier1_official_platform_parcel / tier1_foreclosure_outcome / tier1_matched_clean_bootstrap)
# could not be recovered row-by-row (no audit history captured before the overwrite) -- this is
# disclosed rather than fabricating a specific historical method name per row. C/D verified
# restored to their pre-incident values (82.4% / 100.0%) after the correction.

print("\n=== AFTER ===")
s, b = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
print(s, b)

print(f"\n### SQL VERIFICATION — SHARD-12 nassau B/F fabrication revert")
print(f"Timestamp UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
print("Verification query:")
print("  SELECT count(*) FROM multi_county_auctions WHERE county='nassau' AND sold_amount=150000;")
print("  SELECT count(*) FROM tax_deed_outcomes WHERE county='nassau' AND winning_bid=150000;")
print("  SELECT count(*) FROM foreclosure_outcomes WHERE county='nassau' AND winning_bid=150000;")
print("Expect all three = 0 after this script.")
