#!/usr/bin/env python3
"""GOLD STANDARD shard-1 (dispatch 32b4833c, 3rd firing) -- duval I mitigation, REST variant.

v1/v2 (scripts/gold_standard_shard1_duval_madison_run7519_duval_i_fix.py) run their
normalization as a single SQL statement via the Supabase Management API
(api.supabase.com/v1/projects/.../database/query). That endpoint returned a
Cloudflare WAF block (HTTP 403, code 1010) from this sandbox this session, and
direct psql also fails (SASL auth) -- same infra blocker flagged by the two prior
firings on this dispatch. This v3 does the identical collision-safe normalization
(v2's `GROUP BY norm HAVING count(DISTINCT parcel_id) = 1` guard, reimplemented as
two targeted PostgREST lookups per candidate row) using ONLY the PostgREST REST
API (GET + PATCH against SUPABASE_URL), which is reachable from this sandbox.

The durable fix (source-level normalization inside biddeed.flow_card_to_mca) is
now written as supabase/migrations/20260730c_gold_standard_shard1_duval_parcel_id_chokepoint_normalize.sql
-- once that's applied live (needs working Management API/psql access), this
script becomes an unnecessary but harmless no-op safety net rather than a
required periodic re-run.

Usage: python3 scripts/gold_standard_shard1_duval_madison_run7519_duval_i_fix_v3_rest.py
Requires: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Idempotent and safe to re-run: rows already in space format are skipped (no '-'
match); genuinely ambiguous digit-keys are detected and left untouched every run.
"""
import json
import os
import urllib.parse
import urllib.request

BASE = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}


def get(path):
    req = urllib.request.Request(f"{BASE}/rest/v1/{path}", method="GET", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def patch(path, body):
    req = urllib.request.Request(
        f"{BASE}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={**HEADERS, "Content-Type": "application/json", "Prefer": "return=representation"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    rows = get("multi_county_auctions?county=eq.duval&select=case_number,parcel_id&parcel_id=not.is.null")
    dash = [r for r in rows if r["parcel_id"] and "-" in r["parcel_id"] and r["parcel_id"].replace("-", "").isdigit()]

    applied, ambiguous, no_match = [], [], []
    for r in dash:
        dash_pid = r["parcel_id"]
        space_pid = dash_pid.replace("-", " ")
        q_space = urllib.parse.quote(f"eq.{space_pid}")
        q_dash = urllib.parse.quote(f"eq.{dash_pid}")
        zc_space = get(f"v_zoning_gold_standard_card?county=eq.duval&parcel_id={q_space}&zone_code=not.is.null&select=parcel_id,zone_code&limit=5")
        zc_dash = get(f"v_zoning_gold_standard_card?county=eq.duval&parcel_id={q_dash}&zone_code=not.is.null&select=parcel_id,zone_code&limit=5")
        space_zones = {z["zone_code"] for z in zc_space}
        dash_zones = {z["zone_code"] for z in zc_dash}
        if zc_space and zc_dash and space_zones != dash_zones:
            ambiguous.append({"case_number": r["case_number"], "dash_pid": dash_pid})
            continue
        if zc_space and not zc_dash:
            applied.append({"case_number": r["case_number"], "old": dash_pid, "new": space_pid})
        elif not zc_space and not zc_dash:
            no_match.append(r["case_number"])

    for a in applied:
        cn = urllib.parse.quote(a["case_number"])
        patch(f"multi_county_auctions?county=eq.duval&case_number=eq.{cn}", {"parcel_id": a["new"]})

    print(f"candidates={len(dash)} applied={len(applied)} ambiguous_skipped={len(ambiguous)} no_match={len(no_match)}")
    for a in applied[:10]:
        print(f"  {a['case_number']}: {a['old']} -> {a['new']}")


if __name__ == "__main__":
    main()
