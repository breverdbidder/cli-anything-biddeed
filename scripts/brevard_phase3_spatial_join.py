#!/usr/bin/env python3
"""Chunked spatial join + replace for Brevard (co_no=15) zoning_assignments.
Processes zw_parcels in id-range chunks to stay under the Management API's
server-side statement timeout. Usage:
  python3 scripts/brevard_phase3_spatial_join.py <src_jurisdiction> <target_jurisdiction> <zone_source> [chunk_size]
Example:
  python3 scripts/brevard_phase3_spatial_join.py "Brevard County" brevard_county "gis:BREVARD COUNTY" 20000
"""
import sys, os, time, httpx

REF = "mocerqjnksmhcjzxrewo"
TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
MGMT = f"https://api.supabase.com/v1/projects/{REF}/database/query"


def run_sql(query: str, retries=4):
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    last_err = None
    for attempt in range(retries):
        try:
            r = httpx.post(MGMT, headers=h, json={"query": query}, timeout=280)
        except httpx.TransportError as e:
            last_err = RuntimeError(f"transport error: {e}")
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code in (502, 503, 504, 524):
            last_err = RuntimeError(f"SQL failed {r.status_code} (transient gateway)")
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code >= 300:
            raise RuntimeError(f"SQL failed {r.status_code}: {r.text[:2000]}")
        return r.json()
    raise last_err


def apply_chunk(src_j, tgt_j, zone_source, lo, hi):
    q = f"""
with j as (
  select distinct on (p.pin) p.pin as parcel_id, z.zone_code
  from zw_parcels p
  join zw_zoning_src z
    on z.co_no=15 and z.jurisdiction='{src_j}'
   and st_intersects(z.geom, p.geom)
  where p.co_no=15 and p.geom is not null and p.id between {lo} and {hi}
  order by p.pin, z.id
),
elig as (
  select j.parcel_id, j.zone_code
  from j
  join zoning_assignments za on za.co_no=15 and za.parcel_id=j.parcel_id
  where za.zone_source is null or za.zone_source ilike '%dor_uc%' or za.zone_source ilike '%crosswalk%'
),
del as (
  delete from zoning_assignments z using elig
  where z.co_no=15 and z.parcel_id=elig.parcel_id
  returning 1
),
ins as (
  insert into zoning_assignments
    (parcel_id, co_no, county, zone_code, jurisdiction, zone_source, zone_confidence, zone_updated_at)
  select elig.parcel_id, 15, 'brevard', elig.zone_code, '{tgt_j}',
         '{zone_source}', 'high', now()
  from elig
  returning 1
)
select (select count(*) from del) as removed, (select count(*) from ins) as inserted;
"""
    return run_sql(q)


def main():
    src_j, tgt_j, zone_source = sys.argv[1:4]
    chunk_size = int(sys.argv[4]) if len(sys.argv) > 4 else 20000

    if len(sys.argv) > 6:
        lo0, hi0 = int(sys.argv[5]), int(sys.argv[6])
    else:
        bounds = run_sql(
            "select min(id) as lo, max(id) as hi from zw_parcels where co_no=15 and geom is not null"
        )[0]
        lo0, hi0 = bounds["lo"], bounds["hi"]
    if lo0 is None:
        print("No parcels found.")
        return

    total_removed = 0
    total_inserted = 0
    lo = lo0
    while lo <= hi0:
        hi = min(lo + chunk_size - 1, hi0)
        cs = chunk_size
        while True:
            try:
                res = apply_chunk(src_j, tgt_j, zone_source, lo, lo + cs - 1)
                break
            except RuntimeError as e:
                if "statement timeout" in str(e) and cs > 1000:
                    cs = cs // 2
                    print(f"  timeout, shrinking chunk to {cs}", flush=True)
                    continue
                raise
        removed = res[0]["removed"]
        inserted = res[0]["inserted"]
        total_removed += removed
        total_inserted += inserted
        print(
            f"range=[{lo},{lo+cs-1}] removed={removed} inserted={inserted} "
            f"cum_removed={total_removed} cum_inserted={total_inserted}",
            flush=True,
        )
        lo = lo + cs

    print(f"DONE src={src_j} tgt={tgt_j} total_removed={total_removed} total_inserted={total_inserted}")


if __name__ == "__main__":
    main()
