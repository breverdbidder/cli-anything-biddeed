#!/usr/bin/env python3
"""GOLD STANDARD shard-1 (dispatch 32b4833c, loop run 7519) -- duval I fix.

CORRECTED v2 (same session, after adversarial refutation found two real bugs
in v1 -- see git history for the original commit message/context):

  BUG 1 (non-durable): pg_cron job `gold-calendar-parity-cycle` (every 5 min,
  jobid 204 -> public.gold_calendar_parity_cycle) re-dispatches a scrape for
  every duval auction_date >= current_date roughly every 40 minutes. The live
  RealAuction site displays parcel_id in dash format ("NNNNNN-NNNN"), and the
  scraper (.github/scripts/scrape_realauction_county.py) faithfully captures
  that verbatim -- correctly. So any row for an UPCOMING auction gets its
  parcel_id overwritten back to dash format on the next scrape cycle, silently
  reverting this fix. Only ~19 of 693 duval rows are "upcoming" at any time,
  but they're enough to swing I across the 95% threshold. This is NOT fixed
  by this script -- a durable fix needs to normalize format at the write
  chokepoint (biddeed.tier1_card_upsert / promote_upcoming_tier1_cards), out
  of scope for this session (shared by all 67 realauction counties, needs
  dedicated testing). Re-running this script is a mitigation, not a cure.

  BUG 2 (nondeterminism, more serious, FIXED in this version): v1 joined
  multi_county_auctions.parcel_id to v_zoning_gold_standard_card.parcel_id on
  digit-normalized equality with no uniqueness guard. ~171 of duval's zoning-
  card digit-keys have TWO real, differently-formatted parcel_id spellings
  (confirmed some carry genuinely different zone_code values -- these are not
  pure formatting noise, Duval RE-number dash/space variants can denote
  different real sub-parcels). v1's join could nondeterministically pick
  either spelling on each run, causing some rows to flip-flop between dash and
  space format across repeated runs instead of ever converging. v2 adds a
  `GROUP BY norm HAVING count(DISTINCT parcel_id) = 1` guard so only digit-keys
  with exactly one real spelling in the zoning card are ever touched --
  ambiguous keys are skipped entirely, never guessed at.

Usage: python3 scripts/gold_standard_shard1_duval_madison_run7519_duval_i_fix.py
Idempotent and safe to re-run periodically to counter BUG 1's erosion --
v2's uniqueness guard makes every run monotonic (only ever normalizes further
matches, never un-does a prior correct normalization).
"""
import json
import os
import urllib.request

MGMT_API = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

SQL = """
WITH zc_raw AS (
  SELECT DISTINCT parcel_id, regexp_replace(parcel_id,'[^0-9]','','g') AS norm
  FROM v_zoning_gold_standard_card
  WHERE lower(county) = norm_county_key('duval') AND zone_code IS NOT NULL
), zc_unique AS (
  SELECT norm, min(parcel_id) AS parcel_id
  FROM zc_raw
  GROUP BY norm
  HAVING count(DISTINCT parcel_id) = 1
), upd AS (
  SELECT mca.case_number, mca.parcel_id AS old_parcel_id, zu.parcel_id AS new_parcel_id
  FROM multi_county_auctions mca
  JOIN zc_unique zu ON zu.norm = regexp_replace(mca.parcel_id,'[^0-9]','','g')
  WHERE lower(mca.county)='duval'
    AND mca.parcel_id <> zu.parcel_id
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
    print(f"Normalized {len(rows)} duval parcel_id rows (collision-safe)")
    for r in rows[:10]:
        print(f"  {r['case_number']}: {r['old_parcel_id']} -> {r['new_parcel_id']}")
