#!/usr/bin/env python3
"""Gold Standard shard-5 (dispatch 56b3f5e3) — miami_dade letter J max_bid
correction, applied same session as scripts/gold_standard_shard5_56b3f5e3_miami_dade_j_generator_real.py.

ROOT CAUSE (caught live by an independent ULTRALOOP adversarial refuter, not
the fixer who wrote the generator): the generator's max_bid formula was

    base_bid = arv*0.70 - repairs - 10000
    max_bid  = max(base_bid, min(25000, arv*0.15), 1000)

which takes the MAX of base_bid and the profit-reserve floor instead of
SUBTRACTING the profit reserve from base_bid -- since base_bid almost always
exceeds the reserve floor for these ARVs, this silently never applied the
reserve subtraction at all, overstating max_bid by exactly
MIN(25000, 0.15*arv) on all 14 rows written this session ($22,273-$25,000
each). This inherited pattern also exists in the "canonical" template this
script forked from (scripts/gold_standard_shard1_a3eafa08_washington_j_generator_real.py)
-- fleet-wide fix is out of scope for this shard (dixie + miami_dade only
per PARALLEL-FLEET RULES); this file corrects only the 14 miami_dade rows
this session actually wrote.

Corrected formula (literal reading of CLAUDE.md's canonical deal_analysis
line: (ARV*70%)-Repairs-$10K-MIN($25K,15%*ARV)), using the same `repairs`
estimate methodology the original generator used (unchallenged by the
refuter): repairs = max(5000, min(40000, 0.08*arv)).

    max_bid = (arv*0.70) - repairs - 10000 - min(25000, 0.15*arv)

Independently re-verified by a second adversarial refuter agent after this
patch ran: all 14 rows matched the corrected formula to the cent, J stayed
PASS (99.3%, deal_complete=590 -- J only gates on max_bid IS NOT NULL, not
magnitude), no regression on any other letter.

This script is idempotent-unsafe by design (SELECT ... then subtract the
delta once) -- it must not be re-run against rows it has already corrected.
It ran once, live, during this session; kept here for audit reproducibility.
"""
import json
import os
import urllib.parse
import urllib.request

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HDR = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}

CASE_NUMBERS = [
    "2024-013103-CA-01", "2025-007384-CA-01", "2025-009474-CA-01", "2025-009775-CA-01",
    "2025-013585-CA-01", "2025-019697-CA-01", "2025-019702-CA-01", "2025-019889-CA-01",
    "2025-022229-CA-01", "2025-023462-CA-01", "2026-001351-CA-01", "2026-002345-CA-01",
    "2026-003141-CA-01", "2026-004941-CA-01",
]


def fetch_rows():
    in_list = ",".join(urllib.parse.quote(c, safe="") for c in CASE_NUMBERS)
    url = f"{SB_URL}/rest/v1/bid_decisions?select=id,case_number,arv,max_bid&case_number=in.({in_list})"
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def patch_max_bid(row_id, new_max_bid):
    url = f"{SB_URL}/rest/v1/bid_decisions?id=eq.{row_id}"
    body = json.dumps({"max_bid": new_max_bid}).encode()
    req = urllib.request.Request(
        url, data=body, method="PATCH",
        headers={**HDR, "Content-Type": "application/json", "Prefer": "return=minimal"},
    )
    with urllib.request.urlopen(req, timeout=20):
        pass


def main():
    rows = fetch_rows()
    print(f"[INFO] fetched {len(rows)}/{len(CASE_NUMBERS)} target rows")
    for r in rows:
        arv = r["arv"]
        old_max_bid = r["max_bid"]
        reserve = min(25000.0, 0.15 * arv)
        new_max_bid = round(old_max_bid - reserve, 2)
        patch_max_bid(r["id"], new_max_bid)
        print(f"[FIXED] {r['case_number']}: max_bid {old_max_bid} -> {new_max_bid} "
              f"(subtracted profit reserve {round(reserve, 2)})")


if __name__ == "__main__":
    main()
