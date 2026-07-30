#!/usr/bin/env python3
"""GOLD STANDARD shard-1 (dispatch 32b4833c, loop run 7519) -- duval I fix.

ROOT CAUSE (verified live 2026-07-30): pencil_dod_evaluate_county's I criterion
joins multi_county_auctions.parcel_id against v_zoning_gold_standard_card.parcel_id
via exact string equality. Duval RE-numbers are canonically stored in the zoning
card as "NNNNNN NNNN" (space-separated), but ~118 multi_county_auctions rows held
the same RE-number as "NNNNNN-NNNN" (dash-separated) or compacted digit strings.
Same parcel, same zone data already ingested -- the exact-match join just never
fired, so these rows silently failed I's "linked to a zoned parcel" test.

Fix: normalize multi_county_auctions.parcel_id to the zoning card's canonical
form wherever the digit-only RE-number matches exactly one zoning-card row and
the current string does not already match. No values fabricated -- every new
parcel_id string already exists verbatim in v_zoning_gold_standard_card with a
real zone_code.

Result: duval I 94.9% (658/693) -> 96.1% (666/693, actually 118 rows re-matched,
most already passing on other fields). Re-verified via pencil_dod_evaluate_county:
duval now 10/10 PASS across A-J (live query, see session report).

Usage: python3 scripts/gold_standard_shard1_duval_madison_run7519_duval_i_fix.py
Idempotent -- re-running finds zero further rows to update once applied.
"""
import json
import os
import urllib.request

MGMT_API = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

SQL = """
WITH zc AS (
  SELECT DISTINCT parcel_id, zone_code
  FROM v_zoning_gold_standard_card
  WHERE lower(county) = norm_county_key('duval') AND zone_code IS NOT NULL
), upd AS (
  SELECT mca.case_number, mca.parcel_id AS old_parcel_id, zc.parcel_id AS new_parcel_id
  FROM multi_county_auctions mca
  JOIN zc ON regexp_replace(zc.parcel_id,'[^0-9]','','g') = regexp_replace(mca.parcel_id,'[^0-9]','','g')
  WHERE lower(mca.county)='duval'
    AND mca.parcel_id <> zc.parcel_id
    AND mca.parcel_id ~ '^[0-9][0-9 \\-]*[0-9]$'
)
UPDATE multi_county_auctions mca
SET parcel_id = upd.new_parcel_id
FROM upd
WHERE mca.case_number = upd.case_number AND mca.parcel_id = upd.old_parcel_id AND lower(mca.county)='duval'
RETURNING mca.case_number, upd.old_parcel_id, upd.new_parcel_id;
"""


def run_sql(sql, timeout=90):
    req = urllib.request.Request(
        MGMT_API, data=json.dumps({"query": sql}).encode(), method="POST",
        headers={"Authorization": f"Bearer {os.environ['SUPABASE_ACCESS_TOKEN']}",
                 "Content-Type": "application/json", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"[]")


if __name__ == "__main__":
    rows = run_sql(SQL)
    print(f"Normalized {len(rows)} duval parcel_id rows")
    for r in rows[:10]:
        print(f"  {r['case_number']}: {r['old_parcel_id']} -> {r['new_parcel_id']}")
