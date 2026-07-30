#!/usr/bin/env python3
"""Backfill parcel_zones.tax_account for brevard from Brevard's own GIS parcel layer.

Root cause (diagnosed live 2026-07-30, dispatch 09f985fc 3rd firing): parcel_zones
already holds real zone_code data for brevard (363,877 rows, 25,089 with
tax_account NULL), keyed by BCPAO-format parcel_id (e.g. "29 3702-00-297"). But
multi_county_auctions.parcel_id for many brevard rows stores the numeric tax
account (e.g. "2965080") instead. The gold-standard I evaluator joins on EITHER
parcel_id OR tax_account, so a null tax_account silently drops the join for any
auction row keyed by tax account -- even though the zoning data already exists.

Fix: pull PARCEL_ID -> TaxAcct pairs from Brevard's public GIS layer
(gis.brevardfl.gov, no auth, no Cloudflare gate -- distinct from the
Cloudflare-blocked bcpao.us) and backfill the existing null tax_account column.
No new zoning data is invented; this is a pure linkage repair.

Usage: python3 scripts/brevard_parcel_zones_taxaccount_backfill.py
Env: SUPABASE_ACCESS_TOKEN (Management API SQL execution).
"""
import os, sys, json, time, urllib.request, urllib.parse
import httpx

REF = "mocerqjnksmhcjzxrewo"
TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
GIS_BASE = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5/query"

def mgmt_sql(query):
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    r = httpx.post(f"https://api.supabase.com/v1/projects/{REF}/database/query",
                    headers=h, json={"query": query}, timeout=120)
    r.raise_for_status()
    return r.json()

def gis_page(offset, page_size=1000):
    params = {
        "where": "TaxAcct IS NOT NULL AND PARCEL_ID IS NOT NULL",
        "outFields": "PARCEL_ID,TaxAcct",
        "returnGeometry": "false",
        "orderByFields": "OBJECTID",
        "resultOffset": str(offset),
        "resultRecordCount": str(page_size),
        "f": "json",
    }
    url = GIS_BASE + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode())

def fetch_gis_map():
    """Paginate the full GIS layer -> dict PARCEL_ID -> TaxAcct."""
    m = {}
    offset = 0
    while True:
        d = gis_page(offset)
        feats = d.get("features", [])
        if not feats:
            break
        for f in feats:
            a = f["attributes"]
            pid = (a.get("PARCEL_ID") or "").strip()
            acct = a.get("TaxAcct")
            if pid and acct is not None:
                m[pid] = str(acct)
        offset += len(feats)
        if len(feats) < 1000:
            break
        if offset % 20000 == 0:
            print(f"  ...fetched {offset} GIS records", file=sys.stderr)
        time.sleep(0.3)
    return m

def sql_literal(s):
    return "'" + s.replace("'", "''") + "'"

if __name__ == "__main__":
    print("Fetching brevard parcel_zones rows with NULL tax_account...")
    r = mgmt_sql("""
        SELECT parcel_id FROM parcel_zones
        WHERE jurisdiction_id IN (SELECT id FROM jurisdictions WHERE lower(county_name)='brevard' OR lower(county)='brevard')
          AND tax_account IS NULL
    """)
    null_rows = r if isinstance(r, list) else r.get("result", [])
    null_parcel_ids = [row["parcel_id"] for row in null_rows]
    print(f"  {len(null_parcel_ids)} rows need backfill")

    print("Fetching full PARCEL_ID -> TaxAcct map from Brevard GIS (paginated, ~354 pages)...")
    gis_map = fetch_gis_map()
    print(f"  {len(gis_map)} GIS records with both fields populated")

    pairs = [(pid, gis_map[pid]) for pid in null_parcel_ids if pid in gis_map]
    print(f"  {len(pairs)} of {len(null_parcel_ids)} null rows have a GIS match")

    if not pairs:
        print("Nothing to update.")
        sys.exit(0)

    BATCH = 500
    updated_total = 0
    for i in range(0, len(pairs), BATCH):
        chunk = pairs[i:i+BATCH]
        values = ",".join(f"({sql_literal(pid)},{sql_literal(acct)})" for pid, acct in chunk)
        q = f"""
        WITH v(parcel_id, tax_account) AS (VALUES {values})
        UPDATE parcel_zones pz
        SET tax_account = v.tax_account
        FROM v
        WHERE pz.parcel_id = v.parcel_id
          AND pz.tax_account IS NULL
          AND pz.jurisdiction_id IN (SELECT id FROM jurisdictions WHERE lower(county_name)='brevard' OR lower(county)='brevard')
        """
        resp = mgmt_sql(q)
        updated_total += len(chunk)
        print(f"  batch {i//BATCH+1}: {len(chunk)} rows submitted (cumulative {updated_total})")
        time.sleep(0.2)

    print(f"Done. Submitted updates for {updated_total} parcel_zones rows.")
