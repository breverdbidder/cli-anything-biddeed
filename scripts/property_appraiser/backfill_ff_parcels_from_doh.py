#!/usr/bin/env python3
"""Winner Data FF -- Gap 5 (2026-08-26 P0): wire the FL DOH statewide parcels
layer into fl_parcels as the SSOT ingest path for currently-referenced FF
parcels, per supabase/migrations/20260826f_winnerdata_ff_portfolio_assessed_
dor_source.sql's documented decision (ingest job, not per-request live query
-- see that migration's header comment for the full rationale).

Scope: only the (county, parcel_id) pairs actually referenced today by
winnerdata.leads (single-property path) or winnerdata.owner_portfolio
(multi-property path) -- NOT a statewide fl_parcels refresh (10.5M rows,
out of scope for this gap). Re-run any time to pick up newly-added leads;
already-synced rows just get their dor_synced_at refreshed.

For each candidate: query gis.floridahealth.gov's statewide layer via
doh_statewide.query_parcel(). On a match, UPDATE fl_parcels' DOR NAL fields
(jv/av_sd/lnd_val/dor_uc/own_name/phy_addr1) from the DOH response and stamp
dor_source='doh_statewide', dor_synced_at=now(); INSERT the row first if
fl_parcels has none for (co_no, parcel_id) yet. No match -- e.g. parcel_id
format doesn't resolve on the statewide layer, or the county isn't one of
the 67 layers -- is logged and skipped, never fabricated.

Writes go through the Supabase Management API (POST /database/query) with
SUPABASE_ACCESS_TOKEN, the same fallback this repo's other apply_*.py
scripts use -- direct psql/pooler auth is a known, already-documented
platform limitation in this environment (see workers/winnerdata-ff/src/
index.js's DB ACCESS note), not something this script works around
differently.

Usage:
  python3 scripts/property_appraiser/backfill_ff_parcels_from_doh.py
  python3 scripts/property_appraiser/backfill_ff_parcels_from_doh.py --dry-run
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from doh_statewide import query_parcel  # noqa: E402

REF = "mocerqjnksmhcjzxrewo"
DRY_RUN = "--dry-run" in sys.argv
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def mgmt_sql(sql: str, timeout: int = 120, retries: int = 4):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=json.dumps({"query": sql}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": UA},
        method="POST",
    )
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, json.loads(r.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(3 * attempt)
    raise last_err


def sql_str(v) -> str:
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def load_candidates() -> list[dict]:
    sql = """
    with lead_parcels as (
      select v.county, l.parcel_id, fc.co_no
      from winnerdata.leads l
      left join winnerdata.v_producer_intake v on v.lead_id = l.lead_id
      left join public.fl_counties fc on fc.slug = v.county
      where l.parcel_id is not null and v.county is not null
    ),
    portfolio_parcels as (
      select op.county, op.parcel_id, op.co_no
      from winnerdata.owner_portfolio op
    )
    select distinct county, parcel_id, co_no
    from (select * from lead_parcels union select * from portfolio_parcels) u
    where co_no is not null and parcel_id is not null
    order by county, parcel_id;
    """
    status, result = mgmt_sql(sql)
    if status != 201:
        raise RuntimeError(f"candidate query failed: {status} {result}")
    return result


def upsert_parcel(co_no: int, parcel_id: str, attrs: dict) -> None:
    jv = attrs.get("JV")
    av_sd = attrs.get("AV_SD")
    lnd_val = attrs.get("LND_VAL")
    dor_uc = attrs.get("DOR_UC")
    own_name = attrs.get("OWN_NAME")
    phy_addr1 = attrs.get("PHY_ADDR1")
    no_buldng = attrs.get("NO_BULDNG")

    sql = f"""
    insert into public.fl_parcels (co_no, parcel_id, jv, av_sd, lnd_val, dor_uc, own_name, phy_addr1, no_buldng, dor_source, dor_synced_at, updated_at)
    values ({co_no}, {sql_str(parcel_id)}, {jv or 'NULL'}, {av_sd or 'NULL'}, {lnd_val or 'NULL'}, {sql_str(dor_uc)}, {sql_str(own_name)}, {sql_str(phy_addr1)}, {no_buldng or 'NULL'}, 'doh_statewide', now(), now())
    on conflict (co_no, parcel_id) do update set
      jv = coalesce(excluded.jv, public.fl_parcels.jv),
      av_sd = coalesce(excluded.av_sd, public.fl_parcels.av_sd),
      lnd_val = coalesce(excluded.lnd_val, public.fl_parcels.lnd_val),
      dor_uc = coalesce(excluded.dor_uc, public.fl_parcels.dor_uc),
      own_name = coalesce(excluded.own_name, public.fl_parcels.own_name),
      phy_addr1 = coalesce(excluded.phy_addr1, public.fl_parcels.phy_addr1),
      no_buldng = coalesce(excluded.no_buldng, public.fl_parcels.no_buldng),
      dor_source = 'doh_statewide',
      dor_synced_at = now();
    """
    status, result = mgmt_sql(sql)
    if status not in (200, 201):
        raise RuntimeError(f"upsert failed for {co_no}/{parcel_id}: {status} {result}")


def main():
    candidates = load_candidates()
    print(f"[backfill_ff_parcels_from_doh] {len(candidates)} distinct (county, parcel_id) candidates")

    if DRY_RUN:
        print("[DRY RUN] not calling DOH or writing -- candidate list only")
        for c in candidates[:20]:
            print(f"  {c['county']} / {c['parcel_id']} (co_no={c['co_no']})")
        return

    matched = 0
    unmatched = []
    errors = []
    for c in candidates:
        county, parcel_id, co_no = c["county"], c["parcel_id"], c["co_no"]
        try:
            attrs = query_parcel(county, parcel_id)
        except Exception as exc:
            errors.append((county, parcel_id, str(exc)))
            print(f"  [ERROR] {county}/{parcel_id}: {exc}")
            continue
        if attrs is None:
            unmatched.append((county, parcel_id))
            print(f"  [NO MATCH] {county}/{parcel_id}")
            continue
        try:
            upsert_parcel(co_no, parcel_id, attrs)
        except Exception as exc:
            errors.append((county, parcel_id, str(exc)))
            print(f"  [WRITE ERROR] {county}/{parcel_id}: {exc}")
            continue
        matched += 1
        print(f"  [OK] {county}/{parcel_id}: JV={attrs.get('JV')} AV_SD={attrs.get('AV_SD')} (matched_format={attrs.get('matched_format')!r})")

    print(f"\n[backfill_ff_parcels_from_doh] matched={matched} unmatched={len(unmatched)} errors={len(errors)} of {len(candidates)} candidates")
    if unmatched:
        print(f"  unmatched (no resolvable format on DOH statewide layer): {unmatched[:15]}{'...' if len(unmatched) > 15 else ''}")
    if errors:
        print(f"  errors: {errors[:10]}{'...' if len(errors) > 10 else ''}")


if __name__ == "__main__":
    main()
