#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-3: gulf, hamilton, union
Session: 2026-08-03T08:00Z
Dispatch: 03abc256-a5ba-4078-b41f-b7f730a50901

Objectives:
- gulf: I=85.7% -> 95%+ (fix 2 incomplete property cards)
- hamilton: C/D=61.9% (investigate new data), I=95.2% (fix 1 remaining card)
- union: B/F=null (check if 2026-08-13 auction closed)

Run: python3 shard3_gulf_hamilton_union_session.py
"""
from __future__ import annotations
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
SUPABASE_REF = "mocerqjnksmhcjzxrewo"

BASE = f"{SUPABASE_URL}/rest/v1"
MGMT_URL = f"https://api.supabase.com/v1/projects/{SUPABASE_REF}/database/query"

HEADERS_REST = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}
HEADERS_MGMT = {
    "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str, tag: str = "INFO") -> None:
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def sb_get(path: str) -> List[Dict]:
    url = f"{BASE}/{path}"
    req = urllib.request.Request(url, headers=HEADERS_REST)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"GET {path} HTTP {e.code}: {e.read()[:300]}", "ERROR")
        return []
    except Exception as e:
        log(f"GET {path} failed: {e}", "ERROR")
        return []


def sb_rpc(fn: str, body: Dict) -> Dict:
    req = urllib.request.Request(
        f"{BASE}/rpc/{fn}",
        data=json.dumps(body).encode(),
        headers=HEADERS_REST,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"RPC {fn} HTTP {e.code}: {e.read()[:300]}", "ERROR")
        return {}
    except Exception as e:
        log(f"RPC {fn} failed: {e}", "ERROR")
        return {}


def sb_patch(table: str, filters: str, data: Dict) -> Tuple[int, str]:
    url = f"{BASE}/{table}?{filters}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={**HEADERS_REST, "Prefer": "return=minimal"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def mgmt_sql(query: str) -> Dict:
    if not SUPABASE_ACCESS_TOKEN:
        log("No SUPABASE_ACCESS_TOKEN -- using RPC fallback", "WARN")
        return {}
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        headers=HEADERS_MGMT,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"MGMT SQL HTTP {e.code}: {e.read()[:500]}", "ERROR")
        return {}
    except Exception as e:
        log(f"MGMT SQL failed: {e}", "ERROR")
        return {}


def run_baseline_evaluations():
    """Run pencil_dod_evaluate_county for all 3 counties."""
    log("=" * 70)
    log("STEP 1: BASELINE EVALUATIONS")
    log("=" * 70)
    results = {}
    for county in ["gulf", "hamilton", "union"]:
        ev = sb_rpc("pencil_dod_evaluate_county", {"p_county": county})
        results[county] = ev
        passing = sum(1 for k, v in ev.items()
                      if k not in ("auctions_total",) and isinstance(v, dict) and v.get("pass"))
        total = sum(1 for k, v in ev.items()
                    if k not in ("auctions_total",) and isinstance(v, dict))
        log(f"{county}: {passing}/{total} | {json.dumps(ev)}", "BASELINE")
    return results


def check_union_auction_status():
    """
    Check if union's upcoming auctions have closed.
    From prior report: 63-2025-CA-0053 due 2026-08-13, 63-2024-CA-0047 due 2026-10-15.
    Today is 2026-08-03 -- 2026-08-13 is still 10 days away.
    But check actual status in MCA.
    """
    log("=" * 70)
    log("STEP 2: UNION AUCTION STATUS CHECK")
    log("=" * 70)

    rows = sb_get(
        "multi_county_auctions?county=eq.union"
        "&select=case_number,auction_date,status,parity_status,verified_outcome,winning_bid"
        "&order=auction_date.asc"
    )
    log(f"Union auctions total: {len(rows)}")
    for r in rows:
        log(f"  {r.get('case_number')} | date={r.get('auction_date')} | "
            f"status={r.get('status')} | parity={r.get('parity_status')} | "
            f"verified={r.get('verified_outcome')} | bid={r.get('winning_bid')}")

    # Check foreclosure_outcomes and tax_deed_outcomes for union
    fo = sb_get("foreclosure_outcomes?county=eq.union&select=case_number,winning_bid,data_source&limit=10")
    td = sb_get("tax_deed_outcomes?county=eq.union&select=case_number,winning_bid,data_source&limit=10")
    log(f"Union foreclosure_outcomes: {len(fo)} rows")
    log(f"Union tax_deed_outcomes: {len(td)} rows")
    for r in fo + td:
        log(f"  {r}")
    return rows


def investigate_gulf_i_gap():
    """
    Gulf I = 85.7% (12/14). Need to find the 2 incomplete cards.
    Prior report identified:
    - 05762000R and 05004050R: in Port St Joe, need zoning georeferencing (blocker)
    - 03426604R and 00469000R: genuinely addressless (BORROW PIT etc)
    - 232019CA000060CAAXMX, 232024CA000072CAAXMX, 232024CC000157CCAXMX: no parcel_id

    Since I is now 12/14 (not 7/14), the prior session must have fixed some of these.
    Need to find which 2 are still incomplete.
    """
    log("=" * 70)
    log("STEP 3: GULF I GAP DIAGNOSIS")
    log("=" * 70)

    # Get all gulf auctions with card completeness details
    rows = sb_get(
        "multi_county_auctions?county=eq.gulf"
        "&select=case_number,parcel_id,property_address,latitude,po_latitude,"
        "assessed_value,market_value,status"
    )
    log(f"Gulf total auctions: {len(rows)}")

    # Check parcel_zones for gulf parcel_ids
    parcel_ids = [r.get("parcel_id") for r in rows if r.get("parcel_id")]
    log(f"Gulf parcel_ids: {parcel_ids}")

    # Identify incomplete cards manually
    incomplete = []
    for r in rows:
        issues = []
        if not r.get("property_address"):
            issues.append("no_address")
        if r.get("latitude") is None and r.get("po_latitude") is None:
            issues.append("no_geo")
        if r.get("assessed_value") is None and r.get("market_value") is None:
            issues.append("no_value")
        # parcel_id in parcel_zones is checked by the evaluator but we can't run
        # the CTE directly here - we'll check parcel_zones coverage separately
        if issues or not r.get("parcel_id"):
            incomplete.append((r.get("case_number"), r.get("parcel_id"), issues))
            log(f"  INCOMPLETE {r.get('case_number')} | parcel={r.get('parcel_id')} | issues={issues}")

    log(f"Rows missing address/geo/value: {len(incomplete)}")

    # Check parcel_zones coverage for gulf parcels
    if parcel_ids:
        pz_rows = sb_get(
            f"parcel_zones?parcel_id=in.({',' .join(parcel_ids[:20])})"
            f"&select=parcel_id,zone_code&limit=50"
        )
        zoned_parcel_ids = {r["parcel_id"] for r in pz_rows}
        log(f"Gulf parcels in parcel_zones: {len(zoned_parcel_ids)} of {len(parcel_ids)}")
        for pid in parcel_ids:
            if pid not in zoned_parcel_ids:
                log(f"  NOT ZONED: {pid}")
    return incomplete


def investigate_hamilton_i_gap():
    """
    Hamilton I = 95.2% (20/21). Need to find the 1 remaining incomplete card.
    From prior session: Groups B/C (6 parcels) were unzoned.
    Since I improved from 71.4% to 95.2%, most were fixed. 1 remains.
    """
    log("=" * 70)
    log("STEP 4: HAMILTON I GAP DIAGNOSIS")
    log("=" * 70)

    rows = sb_get(
        "multi_county_auctions?county=eq.hamilton"
        "&select=case_number,parcel_id,property_address,latitude,po_latitude,"
        "assessed_value,market_value"
    )
    log(f"Hamilton total auctions: {len(rows)}")

    incomplete = []
    for r in rows:
        issues = []
        if not r.get("property_address"):
            issues.append("no_address")
        if r.get("latitude") is None and r.get("po_latitude") is None:
            issues.append("no_geo")
        if r.get("assessed_value") is None and r.get("market_value") is None:
            issues.append("no_value")
        if not r.get("parcel_id"):
            issues.append("no_parcel_id")
        if issues:
            incomplete.append((r.get("case_number"), r.get("parcel_id"), issues))
            log(f"  INCOMPLETE {r.get('case_number')} | parcel={r.get('parcel_id')} | issues={issues}")

    log(f"Hamilton rows missing address/geo/value: {len(incomplete)}")

    # Check parcel_zones for hamilton parcel_ids
    parcel_ids = [r.get("parcel_id") for r in rows if r.get("parcel_id")]
    if parcel_ids:
        pz_rows = sb_get(
            f"parcel_zones?parcel_id=in.({',' .join(parcel_ids[:30])})"
            f"&select=parcel_id,zone_code&limit=50"
        )
        zoned_parcel_ids = {r["parcel_id"] for r in pz_rows}
        log(f"Hamilton parcels in parcel_zones: {len(zoned_parcel_ids)} of {len(parcel_ids)}")
        for pid in parcel_ids:
            if pid not in zoned_parcel_ids:
                log(f"  NOT ZONED: {pid}")

    return incomplete


def investigate_hamilton_cd_gap():
    """
    Hamilton C/D = 61.9% (13/21). Check if any new data is available.
    Prior session found 8 rows genuinely unresolvable.
    Check if 2025-CA-66 (date discrepancy case) has been resolved.
    """
    log("=" * 70)
    log("STEP 5: HAMILTON C/D GAP CHECK")
    log("=" * 70)

    rows = sb_get(
        "multi_county_auctions?county=eq.hamilton"
        "&select=case_number,auction_date,parity_status,parity_source,status"
        "&order=case_number.asc"
    )
    log(f"Hamilton total: {len(rows)}")
    not_matched = []
    for r in rows:
        if r.get("parity_status") != "matched_clean":
            not_matched.append(r)
            log(f"  NOT MATCHED: {r.get('case_number')} | date={r.get('auction_date')} | "
                f"status={r.get('parity_status')} | src={r.get('parity_source')}")
    log(f"Unmatched rows: {len(not_matched)}")
    return not_matched


def log_ultraloop_audit(county: str, letter: str, claim: str,
                        refuter_evidence: Dict, survived: bool,
                        dispatch_id: str = "03abc256-a5ba-4078-b41f-b7f730a50901"):
    """Log to gold_standard_ultraloop_audit."""
    row = {
        "dispatch_id": dispatch_id,
        "ultraloop_mode": "fallback",
        "county_slug": county,
        "letter": letter,
        "claim": claim,
        "refuter_evidence": refuter_evidence,
        "survived": survived,
    }
    url = f"{BASE}/gold_standard_ultraloop_audit"
    req = urllib.request.Request(
        url,
        data=json.dumps(row).encode(),
        headers={**HEADERS_REST, "Prefer": "return=representation"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
            log(f"Logged ultraloop audit: county={county} letter={letter} survived={survived} id={result[0].get('id') if result else '?'}")
            return result[0].get("id") if result else None
    except urllib.error.HTTPError as e:
        log(f"Failed to log ultraloop audit: HTTP {e.code}: {e.read()[:300]}", "ERROR")
        return None


def update_campaign_checkpoint(dispatch_id: str, criteria_passed: Dict, exit_reason: str):
    """Update gold_standard_campaign with session progress."""
    log(f"Updating gold_standard_campaign checkpoint: exit_reason={exit_reason}")
    rows = sb_get(
        f"summit_chat_dispatch?id=eq.{dispatch_id}&select=id,state"
    )
    if not rows:
        log(f"dispatch_id {dispatch_id} not found in summit_chat_dispatch", "WARN")
        return

    sql = f"""
UPDATE public.gold_standard_campaign
SET
  criteria_passed = '{json.dumps(criteria_passed)}'::jsonb,
  criteria_total = 10,
  exit_reason = '{exit_reason}',
  session_end_at = now()
WHERE dispatch_id = '{dispatch_id}';
"""
    result = mgmt_sql(sql)
    log(f"Campaign update result: {json.dumps(result)}")


def run_session_close_evaluations():
    """Final evaluations before session close."""
    log("=" * 70)
    log("FINAL EVALUATIONS")
    log("=" * 70)
    results = {}
    for county in ["gulf", "hamilton", "union"]:
        ev = sb_rpc("pencil_dod_evaluate_county", {"p_county": county})
        results[county] = ev
        passing = sum(1 for k, v in ev.items()
                      if k not in ("auctions_total",) and isinstance(v, dict) and v.get("pass"))
        total = sum(1 for k, v in ev.items()
                    if k not in ("auctions_total",) and isinstance(v, dict))
        log(f"{county}: {passing}/{total} AFTER | {json.dumps(ev)}", "FINAL")
    return results


def main():
    log("=== SHARD-3 gulf/hamilton/union SESSION START ===")
    log(f"SUPABASE_URL: {SUPABASE_URL}")
    log(f"SUPABASE_KEY set: {bool(SUPABASE_KEY)}")
    log(f"SUPABASE_ACCESS_TOKEN set: {bool(SUPABASE_ACCESS_TOKEN)}")

    # Step 1: Baseline evaluations
    baseline = run_baseline_evaluations()

    # Step 2: Check union auction status (may have closed 2026-08-13)
    union_auctions = check_union_auction_status()

    # Step 3: Gulf I gap diagnosis
    gulf_incomplete = investigate_gulf_i_gap()

    # Step 4: Hamilton I gap diagnosis
    ham_i_incomplete = investigate_hamilton_i_gap()

    # Step 5: Hamilton C/D gap check
    ham_cd_unmatched = investigate_hamilton_cd_gap()

    log("=" * 70)
    log("SESSION DIAGNOSTIC SUMMARY")
    log("=" * 70)
    log(f"Union auctions: {len(union_auctions)} (checking if any closed since 2026-08-13)")
    log(f"Gulf I incomplete rows: {len(gulf_incomplete)}")
    log(f"Hamilton I incomplete rows: {len(ham_i_incomplete)}")
    log(f"Hamilton C/D unmatched rows: {len(ham_cd_unmatched)}")

    return baseline


if __name__ == "__main__":
    main()
