#!/usr/bin/env python3
"""
SHARD-2 run5361: Apply migrations and run pencil_dod_evaluate_county verification.
dispatch_id: 670c6f74-aaf1-475a-afd2-6d27133f9301

Counties: hendry (10/10), okeechobee (9/10), bay (7/10), gulf (4/10)
"""
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

REF = "mocerqjnksmhcjzxrewo"
SB = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
MGMT_API = f"https://api.supabase.com/v1/projects/{REF}/database/query"

HEADERS_REST = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
}


def run_sql(sql: str, label: str = "") -> list:
    if not ACCESS_TOKEN:
        print(f"  WARN: No ACCESS_TOKEN — cannot run SQL ({label})")
        return []
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        MGMT_API,
        data=body,
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
            print(f"  SQL [{label}] status=200 rows={len(result) if isinstance(result, list) else 1}")
            return result if isinstance(result, list) else [result]
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        print(f"  SQL ERROR [{label}] {e.code}: {body}")
        return []


def evaluate_county(county: str) -> dict:
    if not KEY:
        return {}
    body = json.dumps({"p_county": county}).encode()
    req = urllib.request.Request(
        f"{SB}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=body,
        headers={**HEADERS_REST, "Prefer": ""},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  EVAL ERROR for {county}: {e.code} {e.read().decode()[:200]}")
        return {}


def apply_migration_file(path: Path) -> bool:
    print(f"\n=== Applying {path.name} ===")
    sql = path.read_text()
    result = run_sql(sql, label=path.name)
    if result is None:
        return False
    print(f"  Applied: {path.name}")
    return True


def main() -> int:
    print("=" * 70)
    print("SHARD-2 run5361 — Migration application + verification")
    print("dispatch_id: 670c6f74-aaf1-475a-afd2-6d27133f9301")
    print("=" * 70)

    if not ACCESS_TOKEN and not KEY:
        print("ERROR: Need SUPABASE_ACCESS_TOKEN or SUPABASE_SERVICE_ROLE_KEY")
        return 1

    migrations_dir = Path(__file__).parent.parent / "migrations"

    # Step 1: Baseline
    print("\n[1/4] BASELINE evaluations...")
    counties = ["hendry", "okeechobee", "bay", "gulf"]
    baseline = {}
    for c in counties:
        ev = evaluate_county(c)
        baseline[c] = ev
        score = sum(1 for l in "ABCDEFGHIJ" if ev.get(l, {}).get("pass"))
        print(f"  {c}: {score}/10  I={ev.get('I',{}).get('metric')}  B={ev.get('B',{}).get('metric')}")

    # Step 2: Apply okeechobee/bay migration
    print("\n[2/4] Applying bay + okeechobee I fix migration...")
    m1 = migrations_dir / "20260720_gold_standard_shard2_run5361_bay_okeechobee_i_fix.sql"
    if m1.exists():
        apply_migration_file(m1)
    else:
        print(f"  Migration not found: {m1}")

    # Step 3: Apply gulf audit migration
    print("\n[3/4] Applying gulf C/D/E audit migration...")
    m2 = migrations_dir / "20260720_gold_standard_shard2_run5361_gulf_c_d_e_audit.sql"
    if m2.exists():
        apply_migration_file(m2)
    else:
        print(f"  Migration not found: {m2}")

    # Step 4: Final evaluations
    print("\n[4/4] FINAL evaluations...")
    after = {}
    for c in counties:
        ev = evaluate_county(c)
        after[c] = ev

    # Summary
    print("\n" + "=" * 70)
    print("SESSION SUMMARY — shard2 run5361")
    print("=" * 70)
    print("\n### SQL VERIFICATION")
    for c in counties:
        bev = baseline.get(c, {})
        aev = after.get(c, {})
        b_score = sum(1 for l in "ABCDEFGHIJ" if bev.get(l, {}).get("pass"))
        a_score = sum(1 for l in "ABCDEFGHIJ" if aev.get(l, {}).get("pass"))
        print(f"\n  {c.upper()}: {b_score}/10 → {a_score}/10")
        print(f"    BEFORE: {json.dumps(bev)}")
        print(f"    AFTER:  {json.dumps(aev)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
