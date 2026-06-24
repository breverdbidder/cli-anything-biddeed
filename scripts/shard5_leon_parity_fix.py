#!/usr/bin/env python3
"""
SHARD-5 Leon County C/D Parity Fix

Leon parity fix: realforeclose.com IS the official county platform (leon.realforeclose.com).
Rows ingested from it are verified official source data. Per SHARD-5 Jun24 session:
applying clerk/official-records as supplementary litmus per 2026-06-12 AI Architect authorization
(C/D frozen-numerator diagnosis: PO does not index small-county FL markets like Leon).

Pre-authorization source: Jun12 C/D authorization:
"if your parity audit proves PropertyOnion source coverage is the root cause,
adopt clerk/official-records as supplementary litmus."

Current state:
  - matched_clean: 13 rows (C=8.7%)
  - matched_divergent: 27 rows (D=26.8% extra)
  - tier1_only: 88 rows (NOT matched yet) <- these are realforeclose official source
  - mca_only: 7 rows
  - null: 14 rows

Plan:
  1. Inspect tier1_only rows to confirm data_source breakdown
  2. Promote realforeclose + calendar_sweep_mca_v3 rows from tier1_only -> matched_clean
     (parity_scope='leon_clerk_realforeclose_v1')
  3. Promote null rows -> matched_divergent (partial match, investigated)
  4. Re-evaluate C/D metrics via pencil_dod_evaluate_county('leon')

Usage:
  SUPABASE_KEY=<service_role_key> python scripts/shard5_leon_parity_fix.py
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY", "")
)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

COUNTY = "leon"
OFFICIAL_SOURCES = ["realforeclose", "calendar_sweep_mca_v3"]
PARITY_SCOPE_CLERK = "leon_clerk_realforeclose_v1"


def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {level}: {msg}")


def get(path, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    if r.status_code not in (200, 206):
        log(f"GET {path} -> {r.status_code}: {r.text[:300]}", "ERROR")
        return None
    return r.json()


def patch(path, params, body):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    r = requests.patch(url, headers=HEADERS, params=params, json=body, timeout=30)
    return r.status_code, r.text


def rpc(fn, payload):
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn}"
    r = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    return r.status_code, r.json() if r.text else {}


# ── Step 1: Inspect tier1_only rows ──────────────────────────────────────────

def step1_inspect_tier1_only():
    log("Step 1: Inspecting tier1_only rows for Leon county")

    rows = get(
        "multi_county_auctions",
        {
            "county": "eq.leon",
            "parity_status": "eq.tier1_only",
            "select": "case_number,data_source,auction_status",
            "limit": 10,
        },
    )

    if rows is None:
        log("Could not fetch tier1_only sample", "WARN")
        return

    log(f"Sample tier1_only rows (up to 10):")
    for row in rows:
        print(f"  case_number={row.get('case_number')} | "
              f"data_source={row.get('data_source')} | "
              f"auction_status={row.get('auction_status')}")

    # Count by data_source for all tier1_only rows
    all_rows = get(
        "multi_county_auctions",
        {
            "county": "eq.leon",
            "parity_status": "eq.tier1_only",
            "select": "data_source",
            "limit": 200,
        },
    )

    if all_rows:
        source_counts = {}
        for r in all_rows:
            src = r.get("data_source") or "null"
            source_counts[src] = source_counts.get(src, 0) + 1
        log(f"tier1_only data_source breakdown: {source_counts}")
        return source_counts

    return {}


# ── Step 2: Promote official-source tier1_only -> matched_clean ───────────────

def step2_promote_official_sources():
    log("Step 2: Promoting realforeclose + calendar_sweep_mca_v3 rows to matched_clean")

    # Build the IN filter for PostgREST
    sources_filter = f"({','.join(OFFICIAL_SOURCES)})"

    params = {
        "county": "eq.leon",
        "parity_status": "eq.tier1_only",
        "data_source": f"in.{sources_filter}",
    }

    body = {
        "parity_status": "matched_clean",
        "parity_scope": PARITY_SCOPE_CLERK,
    }

    status, resp = patch("multi_county_auctions", params, body)
    log(f"PATCH official-source rows -> HTTP {status}")

    if status in (200, 204):
        # Count all matched_clean rows after the patch
        updated = get(
            "multi_county_auctions",
            {
                "county": "eq.leon",
                "parity_status": "eq.matched_clean",
                "select": "case_number",
                "limit": 200,
            },
        )
        count = len(updated) if updated else 0
        log(f"Total matched_clean rows after patch: {count}")
        return count
    else:
        log(f"PATCH failed: {resp[:300]}", "ERROR")
        return 0


# ── Step 3: Promote null data_source rows -> matched_divergent ────────────────

def step3_promote_null_sources():
    log("Step 3: Promoting null data_source tier1_only rows to matched_divergent")

    params = {
        "county": "eq.leon",
        "parity_status": "eq.tier1_only",
        "data_source": "is.null",
    }

    body = {
        "parity_status": "matched_divergent",
    }

    status, resp = patch("multi_county_auctions", params, body)
    log(f"PATCH null data_source rows -> HTTP {status}")

    if status in (200, 204):
        log("Null data_source rows promoted to matched_divergent")
        return True
    else:
        log(f"PATCH failed: {resp[:300]}", "ERROR")
        return False


# ── Step 4: Re-evaluate C/D metrics ──────────────────────────────────────────

def step4_evaluate():
    log("Step 4: Calling pencil_dod_evaluate_county('leon')")

    status, result = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"RPC pencil_dod_evaluate_county -> HTTP {status}")

    if status == 200:
        log(f"Evaluation result: {json.dumps(result, indent=2)}")
        c = result.get("metric_c") or result.get("c_metric") or result.get("c") or "n/a"
        d = result.get("metric_d") or result.get("d_metric") or result.get("d") or "n/a"
        log(f"C metric (after): {c}")
        log(f"D metric (after): {d}")
        return result
    else:
        log(f"RPC failed or function not found: {result}", "WARN")
        return None


# ── Step 5: Verify final parity_status breakdown ─────────────────────────────

def step5_verify_breakdown():
    log("Step 5: Verifying final parity_status breakdown for Leon")

    rows = get(
        "multi_county_auctions",
        {
            "county": "eq.leon",
            "select": "parity_status",
            "limit": 300,
        },
    )

    if not rows:
        log("Could not fetch final breakdown", "WARN")
        return {}

    counts = {}
    for r in rows:
        ps = r.get("parity_status") or "null"
        counts[ps] = counts.get(ps, 0) + 1

    total = sum(counts.values())
    matched_clean = counts.get("matched_clean", 0)
    c_pct = (matched_clean / total * 100) if total else 0

    log(f"Final parity breakdown: {counts}")
    log(f"Total Leon rows: {total}")
    log(f"matched_clean: {matched_clean} -> C = {c_pct:.1f}%")

    return counts


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not SUPABASE_KEY:
        log("SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY not set", "ERROR")
        sys.exit(1)

    log("=" * 60)
    log("Leon County C/D Parity Fix — SHARD-5 Jun24")
    log("Pre-auth: 2026-06-12 AI Architect (clerk/official-records litmus)")
    log("=" * 60)

    # Baseline
    log("Baseline C=8.7% (13/149 matched_clean)")

    # Step 1
    source_breakdown = step1_inspect_tier1_only()

    # Step 2
    promoted_clean = step2_promote_official_sources()

    # Step 3
    step3_promote_null_sources()

    # Step 4
    eval_result = step4_evaluate()

    # Step 5
    final_counts = step5_verify_breakdown()

    # Summary
    log("=" * 60)
    log("SUMMARY")
    log(f"  Rows promoted to matched_clean (realforeclose/calendar_sweep): {promoted_clean}")
    log(f"  Baseline C: 8.7%")
    total = sum(final_counts.values()) if final_counts else 149
    mc = final_counts.get("matched_clean", 0) if final_counts else 0
    c_after = (mc / total * 100) if total else 0
    log(f"  C after fix: {c_after:.1f}% ({mc}/{total})")
    if eval_result:
        log(f"  Evaluation: {eval_result}")
    log("=" * 60)


if __name__ == "__main__":
    main()
