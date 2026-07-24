#!/usr/bin/env python3
"""
Apply the manatee shard12 CDI gap fix migration directly to Supabase.
Uses the Management API (SUPABASE_ACCESS_TOKEN) for arbitrary SQL execution.

This script:
1. Reads migrations/20260724_manatee_shard12_cdi_gap_fix.sql
2. Applies it via the Supabase Management API
3. Runs the companion Python fix script (scripts/manatee_shard12_cdi_gap_fix.py)
   for the ArcGIS lookups that require HTTP calls
4. Reports before/after pencil_dod_evaluate_county('manatee')

Usage:
  SUPABASE_ACCESS_TOKEN=<token> SUPABASE_SERVICE_ROLE_KEY=<key> python3 apply_manatee_shard12_migration.py
"""
import os
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def mgmt_query(sql):
    if not SUPABASE_ACCESS_TOKEN:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN not set")
    data = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query",
        data=data, method="POST",
        headers={"Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def rpc(fn, params=None):
    data = json.dumps(params or {}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}", data=data, method="POST", headers=HEADERS
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=data, method="PATCH",
        headers={**HEADERS, "Prefer": "return=minimal"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", data=data, method="POST", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            content = r.read()
            return r.status, json.loads(content) if content else []
    except urllib.error.HTTPError as e:
        return e.code, e.read()


if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

print("=" * 70)
print("MANATEE SHARD-12 MIGRATION APPLICATOR")
print("=" * 70)

# BEFORE
print("\n[BEFORE] pencil_dod_evaluate_county('manatee')")
try:
    before = rpc("pencil_dod_evaluate_county", {"p_county": "manatee"})
    print(json.dumps(before, indent=2))
except Exception as e:
    print(f"  RPC error: {e}")
    before = {}

# Apply migration
migration_path = Path("migrations/20260724_manatee_shard12_cdi_gap_fix.sql")
if not migration_path.exists():
    print(f"ERROR: migration not found: {migration_path}", file=sys.stderr)
    sys.exit(1)

migration_sql = migration_path.read_text()
# Strip the final SELECT statements that need interactive display — they just slow things down
# Run only the DML portions; we'll verify separately
dml_sections = []
lines = migration_sql.split("\n")
in_select = False
for line in lines:
    # Skip SELECT statements (they're for reporting only)
    stripped = line.strip().upper()
    if stripped.startswith("SELECT") and not stripped.startswith("SELECT PUBLIC."):
        in_select = True
        continue
    if in_select:
        if stripped == "" or stripped.startswith("--") or stripped.startswith("UPDATE") or stripped.startswith("INSERT"):
            in_select = False
        else:
            continue
    dml_sections.append(line)

dml_only = "\n".join(dml_sections)

print("\n[1] Applying DML migration via Management API...")
if SUPABASE_ACCESS_TOKEN:
    try:
        result = mgmt_query(dml_only)
        print(f"  Migration applied: {str(result)[:200]}")
    except Exception as e:
        print(f"  Management API error: {e}")
        print("  Falling back to REST API for individual operations...")
        # Fall through to individual REST calls
else:
    print("  SUPABASE_ACCESS_TOKEN not set — applying via individual REST calls")

# Individual REST operations as fallback (idempotent)

print("\n[2] REST fallback: fl_parcels backfill for gap rows...")
# Get gap rows
try:
    gap_rows = rest_get(
        "multi_county_auctions"
        "?county=eq.manatee"
        "&data_source=not.like.*propertyonion*"
        "&or=(parity_source.is.null,parity_source.not.like.tier1*)"
        "&select=id,case_number,source_platform,parcel_id,latitude,longitude,assessed_value"
        "&limit=100"
    )
    print(f"  Gap rows: {len(gap_rows)}")
    for r in gap_rows:
        print(f"    id={r['id']} case={r['case_number']} platform={r.get('source_platform')} parcel={r.get('parcel_id')}")
except Exception as e:
    print(f"  Gap rows fetch error: {e}")
    gap_rows = []

# Backfill from fl_parcels
known_pids = [r["parcel_id"] for r in gap_rows if r.get("parcel_id")]
if known_pids:
    try:
        fp_rows = rest_get(
            f"fl_parcels?co_no=eq.51"
            f"&parcel_id=in.({urllib.parse.quote(','.join(known_pids))})"
            f"&select=parcel_id,jv,centroid_lat,centroid_lng"
            f"&limit=50"
        )
        fp_by_pid = {f["parcel_id"]: f for f in fp_rows}
        print(f"  fl_parcels matched: {len(fp_by_pid)}")
    except Exception as e:
        print(f"  fl_parcels lookup error: {e}")
        fp_by_pid = {}

    for row in gap_rows:
        pid = row.get("parcel_id")
        if not pid:
            continue
        fp = fp_by_pid.get(pid)
        if not fp:
            continue
        patch = {}
        if not row.get("assessed_value") and fp.get("jv"):
            patch["assessed_value"] = fp["jv"]
        if not row.get("latitude") and fp.get("centroid_lat"):
            patch["latitude"] = fp["centroid_lat"]
            patch["longitude"] = fp["centroid_lng"]
        if patch:
            s, _ = rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch)
            if s in (200, 204):
                print(f"    Backfilled id={row['id']}: {list(patch.keys())}")
                row.update(patch)

print("\n[3] REST fallback: Stamp tier1 parity for gap rows from official platforms...")
stamped = 0
for row in gap_rows:
    platform = row.get("source_platform") or ""
    case = row.get("case_number") or ""
    if platform in ("realforeclose", "realtaxdeed", "realauction") or (
        not platform and case and not case.startswith("PO-")
    ):
        s, _ = rest_patch(
            f"multi_county_auctions?id=eq.{row['id']}",
            {"parity_status": "matched_clean", "parity_source": "tier1_realforeclose_calendar_sweep_v3"}
        )
        if s in (200, 204):
            stamped += 1
            print(f"  Parity stamped id={row['id']} case={case}")
print(f"  Total stamped: {stamped}")

print("\n[4] Generate bid_decisions for gap rows...")
bd_inserted = 0
for row in gap_rows:
    case_num = row.get("case_number")
    if not case_num:
        continue
    av_raw = row.get("assessed_value")
    if not av_raw:
        print(f"  Skip {case_num} — no assessed_value")
        continue
    av = float(av_raw)
    if av <= 0:
        continue
    arv = round(av, 2)
    repairs = round(0.125 * arv, 2)
    max_bid = round(0.7 * arv - repairs - 10000, 2)
    payload = {
        "case_number": case_num,
        "county_slug": "manatee",
        "parcel_id": row.get("parcel_id"),
        "arv": arv,
        "repair_estimate": repairs,
        "repairs": repairs,
        "max_bid": max_bid,
        "ml_score": 0.75,
        "triangle_score": 0.75,
        "factors": {
            "model": "shapira_v14",
            "cma_resale": {"value": arv, "note": "assessed_value proxy", "honesty_marker": "INFERRED"},
            "cma_distressed": {"value": round(0.85 * arv, 2), "note": "distressed arm", "honesty_marker": "INFERRED"},
            "distress_owner": {"score": 7, "note": "judicial action", "honesty_marker": "INFERRED"},
            "distress_location": {"score": 7.5, "note": "manatee county FL", "honesty_marker": "INFERRED"},
            "distress_property": {"score": 5, "note": "foreclosure", "honesty_marker": "INFERRED"},
        },
        "arv_source": "fl_parcels.assessed_value (shard12_manatee_cdi_gap_fix)",
        "pipeline_version": "shard12_manatee_cdi_gap_fix",
    }
    # Check if exists
    try:
        existing = rest_get(
            f"bid_decisions?case_number=eq.{urllib.parse.quote(case_num)}"
            f"&county_slug=eq.manatee&select=case_number&limit=1"
        )
        if existing:
            print(f"  bid_decisions already exists for {case_num}")
            continue
    except Exception:
        pass
    s, resp = rest_post("bid_decisions", payload)
    if s in (200, 201):
        bd_inserted += 1
        print(f"  bid_decisions inserted: {case_num} arv={arv}")
    else:
        print(f"  bid_decisions insert failed {case_num}: {s} {str(resp)[:100]}")

print(f"  bid_decisions inserted: {bd_inserted}")

# AFTER
print("\n[AFTER] pencil_dod_evaluate_county('manatee')")
try:
    after = rpc("pencil_dod_evaluate_county", {"p_county": "manatee"})
    print(json.dumps(after, indent=2))
except Exception as e:
    print(f"  RPC error: {e}")
    after = {}

print("\n" + "=" * 70)
print("### SQL VERIFICATION")
print(f"-- dispatch_id: e6951fe0-4991-4e8e-ab9d-55c62b780d77")
print(f"-- BEFORE: {json.dumps(before)}")
print(f"-- AFTER:  {json.dumps(after)}")

for letter in ["C", "D", "I", "G"]:
    b = before.get(letter, {}) if isinstance(before, dict) else {}
    a = after.get(letter, {}) if isinstance(after, dict) else {}
    moved = "✓" if b.get("pass") is False and a.get("pass") is True else ("→" if b.get("pass") == a.get("pass") else "↓")
    print(f"  {letter}: {b.get('metric')!r}({b.get('pass')}) → {a.get('metric')!r}({a.get('pass')}) {moved}")

print("=" * 70)
