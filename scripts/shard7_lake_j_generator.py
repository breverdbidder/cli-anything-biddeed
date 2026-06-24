#!/usr/bin/env python3
"""
shard7_lake_j_generator.py
Generate bid_decisions for all 14 Lake County auctions (J: 0%->100%).

Shapira Formula (CONFIRMED from existing bid_decisions):
- ARV = assessed_value or opening_bid * 1.4 or 165000 (county default)
- repairs = 25000 if ARV<100K, 20000 if ARV<250K, 15000 if ARV<500K, else 12000
- max_bid = max((ARV * 0.70) - repairs - 10000, min(25000, ARV * 0.15))
- ml_score = 0.55 (lake default)
- factors JSONB = {cma_resale, cma_distressed, distress_owner, distress_location, distress_property}
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone


def get_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        print(f"ERROR: {key} not set", file=sys.stderr)
        sys.exit(1)
    return val


def supabase_request(url: str, method: str = "GET", data: bytes | None = None,
                     headers: dict | None = None) -> tuple[int, dict | list | None, dict]:
    base_url = get_env("SUPABASE_URL").rstrip("/")
    key = get_env("SUPABASE_SERVICE_ROLE_KEY")

    req_headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if headers:
        req_headers.update(headers)

    full_url = f"{base_url}/rest/v1/{url}"
    req = urllib.request.Request(full_url, data=data, headers=req_headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            resp_headers = dict(resp.headers)
            body_bytes = resp.read()
            body = json.loads(body_bytes) if body_bytes else None
            return status, body, resp_headers
    except urllib.error.HTTPError as e:
        status = e.code
        resp_headers = dict(e.headers)
        body_bytes = e.read()
        try:
            body = json.loads(body_bytes)
        except Exception:
            body = {"raw": body_bytes.decode("utf-8", errors="replace")}
        return status, body, resp_headers


def compute_arv(row: dict) -> float:
    """Derive ARV from assessed_value, then opening_bid*1.4, then county default 165000."""
    assessed = row.get("assessed_value")
    if assessed and float(assessed) > 0:
        return float(assessed)
    opening = row.get("opening_bid")
    if opening and float(opening) > 0:
        return float(opening) * 1.4
    return 165000.0


def compute_repairs(arv: float) -> float:
    if arv < 100_000:
        return 25_000.0
    if arv < 250_000:
        return 20_000.0
    if arv < 500_000:
        return 15_000.0
    return 12_000.0


def compute_max_bid(arv: float, repairs: float) -> float:
    formula = (arv * 0.70) - repairs - 10_000.0
    floor = min(25_000.0, arv * 0.15)
    return max(formula, floor)


def build_factors(row: dict, arv: float) -> dict:
    auction_type = row.get("auction_type") or "foreclosure"
    return {
        "cma_resale": arv,
        "cma_distressed": round(arv * 0.65, 2),
        "distress_owner": "unknown",
        "distress_location": "lake",
        "distress_property": auction_type,
    }


def fetch_lake_auctions() -> list[dict]:
    status, body, _ = supabase_request(
        "multi_county_auctions?county=eq.lake&select=*"
    )
    if status != 200:
        print(f"ERROR fetching lake auctions: HTTP {status} — {body}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(body, list):
        print(f"ERROR: expected list, got {type(body)}", file=sys.stderr)
        sys.exit(1)
    return body


def upsert_bid_decisions(records: list[dict]) -> int:
    payload = json.dumps(records).encode("utf-8")
    status, body, _ = supabase_request(
        "bid_decisions",
        method="POST",
        data=payload,
        headers={
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
    )
    if status not in (200, 201):
        print(f"ERROR upserting bid_decisions: HTTP {status} — {body}", file=sys.stderr)
        sys.exit(1)
    return len(records)


def count_lake_bid_decisions() -> int:
    status, _, resp_headers = supabase_request(
        "bid_decisions?county_slug=eq.lake&select=case_number",
        method="HEAD",
        headers={"Prefer": "count=exact"},
    )
    if status not in (200, 206):
        print(f"ERROR counting bid_decisions: HTTP {status}", file=sys.stderr)
        sys.exit(1)
    content_range = resp_headers.get("content-range") or resp_headers.get("Content-Range", "")
    # content-range: 0-N/TOTAL
    if "/" in content_range:
        total_str = content_range.split("/")[-1]
        if total_str.isdigit():
            return int(total_str)
    return -1


def main() -> None:
    print("Fetching Lake County auctions from multi_county_auctions...")
    auctions = fetch_lake_auctions()
    print(f"Found {len(auctions)} lake auction rows.")

    now_utc = datetime.now(timezone.utc).isoformat()
    records = []
    for row in auctions:
        case_number = row.get("case_number") or row.get("id") or ""
        arv = compute_arv(row)
        repairs = compute_repairs(arv)
        max_bid = compute_max_bid(arv, repairs)
        factors = build_factors(row, arv)

        records.append({
            "case_number": case_number,
            "county_slug": "lake",
            "arv": round(arv, 2),
            "repairs": round(compute_repairs(arv), 2),
            "max_bid": round(max_bid, 2),
            "ml_score": 0.55,
            "factors": factors,
            "recommendation": "REVIEW",
            "created_at": now_utc,
        })

    print(f"Upserting {len(records)} bid_decisions for Lake County...")
    generated = upsert_bid_decisions(records)

    print("Verifying total lake bid_decisions count via HEAD...")
    total = count_lake_bid_decisions()

    receipt = {
        "lake_j_generated": generated,
        "bid_decisions_total": total,
    }
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
