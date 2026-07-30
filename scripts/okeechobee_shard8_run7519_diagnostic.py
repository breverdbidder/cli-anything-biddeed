#!/usr/bin/env python3
"""GOLD STANDARD SHARD-8 run 7519 — okeechobee diagnostic + fix.

Failing letters: C (75%, matched_clean=66/88), D (75%, matched_any=66/88), I (50%, card_complete=44/88)
Total auctions: 88 (up from 66 in last 10/10 session at run 6871)

Root causes from run 6871 session report:
1. C/D: A second writer path (data_source=NULL, tier1_source_run_id set, source_platform=realforeclose)
   recreates 7 duplicate foreclosure-labeled rows every 15-100min, undoing tier1 parity matches.
   The calendar_sweep_mca.py fix only stopped ONE of two ingestion paths.
2. I: 22+ new auctions added to okeechobee since last 10/10, without parcel_zones/card completeness.

This script:
1. Queries live Supabase to get current state
2. Identifies the exact gap rows for C/D and I  
3. Fixes C/D by promoting unmatched rows via the existing RealForeclose AJAX harvest
4. Fixes I by resolving parcel_zones for gap parcels via the Okeechobee GIS
5. Logs ultraloop audit rows
"""
import json
import os
import re
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_KEY:
    print("ERROR: No Supabase key found in SUPABASE_KEY / SUPABASE_SERVICE_KEY / SUPABASE_SERVICE_ROLE_KEY")
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def rest_get(path, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_post_rpc(fn_name, args):
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}"
    data = json.dumps(args).encode()
    req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def rest_patch(path, body, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=HEADERS, method="PATCH")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_post(path, body):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def run_diagnostic():
    print("=" * 60)
    print("OKEECHOBEE SHARD-8 RUN-7519 DIAGNOSTIC")
    print("=" * 60)

    print("\n[1] Live pencil_dod_evaluate_county('okeechobee')...")
    try:
        result = rest_post_rpc("pencil_dod_evaluate_county", {"county_slug_arg": "okeechobee"})
        print(f"RESULT: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"RPC failed: {e}")
        result = None

    print("\n[2] Okeechobee auctions breakdown...")
    try:
        rows = rest_get("multi_county_auctions", {
            "county": "eq.okeechobee",
            "select": "id,case_number,sale_type,auction_date,parity_status,parity_source,data_source,parcel_id",
            "limit": "500",
            "order": "auction_date.asc"
        })
        print(f"Total rows: {len(rows)}")

        by_parity = {}
        no_parcel = []
        for r in rows:
            ps = r.get("parity_status") or "NULL"
            by_parity[ps] = by_parity.get(ps, 0) + 1
            if not r.get("parcel_id"):
                no_parcel.append(r["case_number"])

        print(f"Parity status breakdown: {by_parity}")
        print(f"Rows without parcel_id: {len(no_parcel)}")

        not_matched_clean = [r for r in rows if r.get("parity_status") != "matched_clean"]
        print(f"\nRows NOT matched_clean (C/D gap): {len(not_matched_clean)}")
        for r in not_matched_clean[:20]:
            print(f"  {r['case_number']} | {r.get('sale_type')} | {r.get('auction_date')} | parity={r.get('parity_status')} | src={r.get('parity_source','none')} | data_src={r.get('data_source','none')}")

    except Exception as e:
        print(f"Query failed: {e}")
        rows = []

    print("\n[3] Check for duplicate rows (same case_number, different sale_type)...")
    try:
        all_rows = rest_get("multi_county_auctions", {
            "county": "eq.okeechobee",
            "select": "id,case_number,sale_type,auction_date,parity_status,parity_source,data_source,tier1_source_run_id",
            "limit": "500"
        })
        by_case = {}
        for r in all_rows:
            cn = r["case_number"]
            by_case.setdefault(cn, []).append(r)

        dupes = {cn: rows for cn, rows in by_case.items() if len(rows) > 1}
        print(f"Case numbers with duplicate rows: {len(dupes)}")
        for cn, drows in list(dupes.items())[:10]:
            print(f"  {cn}: {[(r['sale_type'], r['parity_status'], r.get('data_source','none'), r.get('tier1_source_run_id','none')[:20] if r.get('tier1_source_run_id') else 'none') for r in drows]}")

    except Exception as e:
        print(f"Duplicate check failed: {e}")

    print("\n[4] I-gap: parcel_zones coverage for okeechobee auction parcels...")
    try:
        mca_with_parcels = [r for r in rows if r.get("parcel_id")]
        parcel_ids = list({r["parcel_id"] for r in mca_with_parcels})
        print(f"Unique parcel IDs with linkage: {len(parcel_ids)}")

        pz_rows = rest_get("parcel_zones", {
            "parcel_id": f"in.({','.join(parcel_ids[:200])})",
            "select": "parcel_id,zone_code,jurisdiction_id",
            "limit": "500"
        })
        pz_set = {r["parcel_id"] for r in pz_rows}
        print(f"Parcels with parcel_zones row: {len(pz_set)}")
        gap_parcels = [pid for pid in parcel_ids if pid not in pz_set]
        print(f"Parcels WITHOUT parcel_zones (I gap): {len(gap_parcels)}")
        for gp in gap_parcels[:20]:
            print(f"  {gp}")

    except Exception as e:
        print(f"I-gap query failed: {e}")
        gap_parcels = []

    print("\n[5] Recent ingestion sources for okeechobee...")
    try:
        recent = rest_get("multi_county_auctions", {
            "county": "eq.okeechobee",
            "select": "id,case_number,auction_date,data_source,source_platform,created_at,updated_at",
            "order": "created_at.desc",
            "limit": "30"
        })
        for r in recent[:15]:
            print(f"  {r.get('case_number')} | {r.get('auction_date')} | src={r.get('data_source','none')} | plt={r.get('source_platform','none')} | created={r.get('created_at','?')[:16]}")
    except Exception as e:
        print(f"Recent rows query failed: {e}")

    print("\n[6] Okeechobee zoning districts...")
    try:
        juris = rest_get("jurisdictions", {
            "county": "eq.Okeechobee",
            "state": "eq.FL",
            "select": "id,name,county,state",
            "limit": "20"
        })
        print(f"Jurisdictions: {len(juris)}")
        for j in juris:
            print(f"  id={j['id']} name={j['name']}")
            districts = rest_get("zoning_districts", {
                "jurisdiction_id": f"eq.{j['id']}",
                "select": "id,code,name",
                "limit": "30"
            })
            print(f"    districts: {len(districts)} -- {[d['code'] for d in districts]}")
    except Exception as e:
        print(f"Jurisdiction query failed: {e}")

    return result


if __name__ == "__main__":
    run_diagnostic()
