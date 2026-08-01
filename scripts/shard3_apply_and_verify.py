#!/usr/bin/env python3
"""Apply shard3-6cace789 migrations and capture before/after evaluations."""
import os, sys, json, time
import urllib.request
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ACCESS_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"

COUNTIES = ["seminole", "hamilton", "union", "flagler", "lake"]

MIGRATIONS = [
    "migrations/20260801_shard3_6cace789_flagler_g_regression_fix.sql",
    "migrations/20260801b_shard3_6cace789_seminole_i_inline_fix.sql",
    "migrations/20260801c_shard3_6cace789_flagler_cd_i_fix.sql",
    "migrations/20260801d_shard3_6cace789_ultraloop_and_closeout.sql",
]


def evaluate(county):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=json.dumps({"county_slug_arg": county}).encode(),
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def run_mgmt_sql(sql):
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": sql}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main():
    print("=" * 60)
    print("SHARD3-6cace789 APPLY & VERIFY")
    print("=" * 60)

    # BEFORE state
    print("\n--- BEFORE STATE ---")
    before = {}
    for c in COUNTIES:
        try:
            before[c] = evaluate(c)
            print(f"BEFORE {c}: {json.dumps(before[c])}")
        except Exception as e:
            print(f"BEFORE {c}: ERROR {e}")
            before[c] = {"error": str(e)}

    # Apply migrations
    print("\n--- APPLYING MIGRATIONS ---")
    migration_results = {}
    for mf in MIGRATIONS:
        if not os.path.exists(mf):
            print(f"MISSING: {mf}")
            migration_results[mf] = {"status": "missing"}
            continue
        with open(mf) as f:
            sql = f.read()
        print(f"\nApplying {mf} ({len(sql)} chars)...")
        status, body = run_mgmt_sql(sql)
        print(f"  Status: {status}")
        print(f"  Response: {body[:500]}")
        migration_results[mf] = {"status": status, "response": body[:500]}
        if status not in (200, 201):
            print(f"  WARNING: Non-200 status on {mf}")
        time.sleep(2)

    # AFTER state
    print("\n--- AFTER STATE ---")
    after = {}
    for c in COUNTIES:
        try:
            after[c] = evaluate(c)
            print(f"AFTER {c}: {json.dumps(after[c])}")
        except Exception as e:
            print(f"AFTER {c}: ERROR {e}")
            after[c] = {"error": str(e)}

    # Summary
    print("\n--- SCORE MOVEMENT SUMMARY ---")
    for c in COUNTIES:
        b = before.get(c, {})
        a = after.get(c, {})
        if "error" in b or "error" in a:
            print(f"{c}: ERROR in evaluation")
            continue
        b_pass = sum(1 for k, v in b.items() if isinstance(v, dict) and v.get("pass"))
        a_pass = sum(1 for k, v in a.items() if isinstance(v, dict) and v.get("pass"))
        b_fail = [k for k, v in b.items() if isinstance(v, dict) and not v.get("pass")]
        a_fail = [k for k, v in a.items() if isinstance(v, dict) and not v.get("pass")]
        delta = a_pass - b_pass
        symbol = "+" if delta > 0 else ("=" if delta == 0 else "")
        print(f"{c}: {b_pass}/10 -> {a_pass}/10 ({symbol}{delta})")
        if b_fail:
            print(f"  was failing: {', '.join(sorted(b_fail))}")
        if a_fail:
            print(f"  still failing: {', '.join(sorted(a_fail))}")

    results = {
        "before": before,
        "migrations": migration_results,
        "after": after,
    }
    with open("/tmp/shard3_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nFull results saved to /tmp/shard3_results.json")
    return results


if __name__ == "__main__":
    main()
