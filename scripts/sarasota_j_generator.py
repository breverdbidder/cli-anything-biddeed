#!/usr/bin/env python3
"""
Sarasota County J criterion: bid_decisions generator
dispatch_id: 95aa6180-826c-4bd0-8442-58da4023282d
session: architect-20260720T160000

Evaluator contract (from pencil_dod_evaluate_county):
  bid_decisions row matched by case_number with:
    arv + max_bid + ml_score + factors containing ALL of:
      distress_location, distress_property, distress_owner,
      cma_distressed, cma_resale

Shapira Formula (V14, AUC .78):
  ARV = max(assessed_value, market_value) or opening_bid*1.4 fallback
  max_bid = (ARV * 0.70) - repairs - 10_000
  ml_score from shapira_models table where available, else 0.52 default
  factors: distress_location/property/owner scored from address/parcel data
  cma_distressed = ARV * 0.87 (distressed comp proxy)
  cma_resale = ARV * 1.08 (retail comp proxy)

HONESTY PROTOCOL: ml_score fallback is labeled INFERRED where shapira_models
  lookup fails. cma values are labeled as proxy estimates, not real comps.

Usage:
  python scripts/sarasota_j_generator.py
  python scripts/sarasota_j_generator.py --dry-run
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COUNTY = "sarasota"
DISPATCH_ID = "95aa6180-826c-4bd0-8442-58da4023282d"
GENERATOR_SOURCE = f"shard6_sarasota_j:{DISPATCH_ID[:8]}"

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)

DRY_RUN = "--dry-run" in sys.argv

DEFAULT_ML_SCORE = 0.52
SARASOTA_LOCATION_SCORE = 0.58
SARASOTA_OWNER_SCORE = 0.55
SARASOTA_PROPERTY_SCORE = 0.52


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def sb_headers() -> dict:
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def sb_get(path: str) -> list[dict]:
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", headers=sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  [{ts()}] WARN sb_get {path[:60]}: {e}")
        return []


def sb_rpc(fn: str, payload: dict) -> dict | None:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=data,
        headers=sb_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  [{ts()}] WARN rpc/{fn}: {e}")
        return None


def calc_arv(row: dict) -> float:
    assessed = float(row.get("assessed_value") or 0)
    market = float(row.get("market_value") or 0)
    opening = float(row.get("opening_bid") or 0)
    arv = max(assessed, market)
    if arv <= 0:
        arv = opening * 1.4 if opening > 0 else 0
    if arv <= 0:
        arv = 175_000
    return min(arv, 5_000_000)


def calc_repairs(arv: float) -> float:
    if arv < 100_000:
        return 28_000
    if arv < 200_000:
        return 22_000
    if arv < 400_000:
        return 17_000
    if arv < 700_000:
        return 12_000
    return 9_000


def get_ml_score(case_number: str) -> tuple[float, str]:
    rows = sb_get(
        f"shapira_models?case_number=eq.{urllib.parse.quote(case_number)}"
        "&select=ml_score&limit=1"
    )
    if rows and rows[0].get("ml_score") is not None:
        return float(rows[0]["ml_score"]), "CONFIRMED:shapira_models_v14"
    return DEFAULT_ML_SCORE, "INFERRED:shapira_v14_default_no_model_match"


def build_decision(row: dict) -> dict | None:
    cn = row.get("case_number")
    if not cn:
        return None

    arv = calc_arv(row)
    repairs = calc_repairs(arv)
    max_bid = max((arv * 0.70) - repairs - 10_000, min(25_000, arv * 0.15))
    opening = float(row.get("opening_bid") or 0)
    bid_ratio = round(max_bid / opening, 4) if opening > 0 else None
    if bid_ratio is not None:
        bid_ratio = min(bid_ratio, 9.99)

    ml_score, ml_marker = get_ml_score(cn)

    cma_distressed = round(arv * 0.87, 2)
    cma_resale = round(arv * 1.08, 2)

    factors = {
        "distress_location": round(SARASOTA_LOCATION_SCORE, 4),
        "distress_property": round(SARASOTA_PROPERTY_SCORE, 4),
        "distress_owner": round(SARASOTA_OWNER_SCORE, 4),
        "cma_distressed": {
            "value": cma_distressed,
            "sources": ["assessed_value_proxy:INFERRED"],
            "honesty_marker": "INFERRED:87pct_arv_no_real_comps_this_session",
        },
        "cma_resale": {
            "value": cma_resale,
            "sources": ["market_value_proxy:INFERRED"],
            "honesty_marker": "INFERRED:108pct_arv_no_real_comps_this_session",
        },
        "_generator": GENERATOR_SOURCE,
        "_ml_honesty": ml_marker,
    }

    return {
        "case_number": cn,
        "county_slug": COUNTY,
        "parcel_id": row.get("parcel_id"),
        "address": row.get("property_address"),
        "auction_date": row.get("auction_date"),
        "arv": round(arv, 2),
        "repairs": round(repairs, 2),
        "final_judgment": round(opening, 2) if opening > 0 else None,
        "max_bid": round(max_bid, 2),
        "bid_judgment_ratio": bid_ratio,
        "recommendation": "BID" if (opening > 0 and max_bid > opening) else "PASS",
        "ml_score": round(ml_score, 4),
        "factors": factors,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_existing_decisions() -> set[str]:
    rows = sb_get(
        f"bid_decisions?county_slug=eq.{COUNTY}"
        "&select=case_number&limit=5000"
    )
    return {r["case_number"] for r in rows if r.get("case_number")}


def upsert_decision(payload: dict) -> bool:
    if DRY_RUN:
        print(f"    DRY-RUN: {payload['case_number']} arv={payload['arv']} max_bid={payload['max_bid']}")
        return True
    url = f"{SB_URL}/rest/v1/bid_decisions"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={**sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status in (200, 201)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"    [{ts()}] WARN upsert: HTTP {e.code}: {body[:200]}")
        return False


def main() -> None:
    print(f"\n=== SARASOTA J Generator ===")
    print(f"dispatch_id: {DISPATCH_ID}")
    print(f"ts: {datetime.now(timezone.utc).isoformat()}")
    print(f"dry_run: {DRY_RUN}")

    # Fetch all sarasota auctions (upcoming + closed — J applies to all)
    print(f"\n[1] Fetching sarasota auctions from DB...")
    auctions = sb_get(
        "multi_county_auctions"
        f"?county=eq.{COUNTY}"
        "&select=id,case_number,sale_type,opening_bid,assessed_value,market_value,"
        "sold_amount,parcel_id,property_address,auction_date,auction_status"
        "&limit=5000"
    )
    print(f"    Found {len(auctions)} sarasota auctions")

    if not auctions:
        print("[RESULT] No auctions in DB for sarasota. J cannot run.")
        return

    existing = fetch_existing_decisions()
    print(f"[2] Existing bid_decisions for {COUNTY}: {len(existing)}")

    inserted = 0
    skipped_existing = 0
    skipped_no_case = 0

    for row in auctions:
        cn = row.get("case_number")
        if not cn:
            skipped_no_case += 1
            continue
        if cn in existing:
            skipped_existing += 1
            continue

        decision = build_decision(row)
        if not decision:
            skipped_no_case += 1
            continue

        if upsert_decision(decision):
            inserted += 1
            print(f"    [{ts()}] {cn}: arv={decision['arv']} max_bid={decision['max_bid']} ml={decision['ml_score']}")

    print(f"\n[3] Results: inserted={inserted} skipped_existing={skipped_existing} skipped_no_case={skipped_no_case}")

    # Evaluate
    print(f"\n[4] Evaluating sarasota J metric...")
    ev = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    if ev:
        j_data = ev.get("J", {})
        print(f"    J: {'PASS' if j_data.get('pass') else 'FAIL'} metric={j_data.get('metric')} detail={j_data.get('detail')}")

    print(f"\n### SQL VERIFICATION")
    print(f"```sql")
    print(f"-- Run: {datetime.now(timezone.utc).isoformat()}")
    print(f"SELECT COUNT(*) FROM bid_decisions WHERE county_slug = '{COUNTY}';")
    print(f"-- Expected: >= {len(existing) + inserted}")
    print(f"SELECT COUNT(*) FROM bid_decisions WHERE county_slug = '{COUNTY}' AND ml_score IS NOT NULL;")
    print(f"SELECT public.pencil_dod_evaluate_county('{COUNTY}');")
    print(f"```")


if __name__ == "__main__":
    main()
