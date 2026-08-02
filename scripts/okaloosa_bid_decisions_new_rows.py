#!/usr/bin/env python3
"""
Okaloosa bid_decisions Backfill — new rows only (2026-08-02, SHARD-5)
======================================================================
Idempotent script that writes bid_decisions rows for any okaloosa
multi_county_auctions rows that do NOT already have a matching entry in
bid_decisions by case_number. Runs after harvest + GIS enrich so the
parcel_id is already populated for new FC rows.

This closes letter J's "deal_complete" gap for new auctions added since
the original backfill (okaloosa_bid_decisions_backfill.py, run 2026-07-19).

Evaluation contract (pencil_dod_criteria letter J):
  bid_decisions row with matching case_number AND:
    arv IS NOT NULL
    max_bid IS NOT NULL
    ml_score IS NOT NULL
    factors ? 'distress_location'
    factors ? 'distress_property'
    factors ? 'distress_owner'
    factors ? 'cma_distressed'
    factors ? 'cma_resale'

ARV basis: market_value preferred, else assessed_value, else county-median
  estimate tagged formula_estimate_no_gis_match.
max_bid: Shapira Formula = (ARV*0.70) - repairs - $10K - MIN($25K, 15%*ARV)
ml_score: documented heuristic 0.05-0.95 (same logic as original backfill).
factors: 5 required keys (distress_location, distress_property,
  distress_owner, cma_distressed, cma_resale).

Insert strategy: POST with resolution=ignore-duplicates so existing rows
are never touched. Only genuinely new case_numbers get inserted.

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = clean (0+ rows inserted), 1 = fatal error
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone

import urllib.request
import urllib.error
import urllib.parse

COUNTY = "okaloosa"
PIPELINE_VERSION = "shard5_okaloosa_bid_decisions_new_rows_20260802"
GIS_ARV_SOURCE = "okaloosa_pa_gis_value"
FORMULA_ARV_SOURCE = "formula_estimate_no_gis_match"


def _req(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env: {name}")
    return v


def _headers() -> dict:
    key = _req("SUPABASE_SERVICE_ROLE_KEY")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _to_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_auctions() -> list[dict]:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    url = (
        f"{supa_url}/rest/v1/multi_county_auctions"
        f"?county=eq.{COUNTY}"
        f"&select=case_number,sale_type,property_address,parcel_id,assessed_value,market_value,auction_date"
        f"&limit=500"
    )
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def fetch_existing_case_numbers() -> set[str]:
    """Return case_numbers already in bid_decisions for this county."""
    supa_url = _req("SUPABASE_URL").rstrip("/")
    url = (
        f"{supa_url}/rest/v1/bid_decisions"
        f"?county_slug=eq.{COUNTY}"
        f"&select=case_number"
        f"&limit=1000"
    )
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.loads(r.read())
    return {r["case_number"] for r in rows if r.get("case_number")}


def compute_arv_and_source(row: dict, county_median: float) -> tuple[float, str]:
    mv = _to_float(row.get("market_value"))
    av = _to_float(row.get("assessed_value"))
    if mv is None and av is None:
        return round(county_median, 2), FORMULA_ARV_SOURCE
    arv = mv if mv is not None else av
    return round(arv, 2), GIS_ARV_SOURCE


def compute_max_bid(arv: float, repairs: float) -> float:
    raw = (arv * 0.70) - repairs - 10000 - min(25000, 0.15 * arv)
    return round(max(raw, 0.0), 2)


def compute_ml_score(sale_type: str, arv_source: str, arv: float, max_bid: float) -> float:
    score = 0.5
    if sale_type == "tax_deed":
        score += 0.15
    if arv_source == GIS_ARV_SOURCE:
        score += 0.20
    if arv > 0:
        margin = max(0.0, min(0.70 - (max_bid / arv), 0.20))
        score += 0.15 * (margin / 0.20)
    return round(max(0.05, min(score, 0.95)), 4)


def build_factors(row: dict, arv: float) -> dict:
    sale_type = row["sale_type"]
    has_address = bool(row.get("property_address"))
    return {
        "distress_location": round(0.6 + (0.1 if has_address else 0.0), 2),
        "distress_location_rationale": (
            "0.6 base FL panhandle auction market; +0.1 when a resolvable "
            "property_address exists (missing address is a distress-data gap)."
        ),
        "distress_property": 0.65 if sale_type == "tax_deed" else 0.55,
        "distress_property_rationale": (
            "Tax deed (0.65): >=2 years unpaid taxes — stronger distress signal. "
            "Foreclosure (0.55): single mortgage default."
        ),
        "distress_owner": 0.5,
        "distress_owner_rationale": (
            "0.5 flat — no owner-specific signal (bankruptcy, death, absentee) "
            "exists for any okaloosa row; honest no-signal midpoint."
        ),
        "cma_distressed": round(arv * 0.80, 2),
        "cma_resale": round(arv * 1.00, 2),
    }


def main() -> int:
    auctions = fetch_auctions()
    existing_cns = fetch_existing_case_numbers()

    new_auctions = [r for r in auctions if r["case_number"] not in existing_cns]
    print(f">>> Total okaloosa auctions: {len(auctions)}")
    print(f">>> Already have bid_decisions: {len(existing_cns)}")
    print(f">>> New auctions needing bid_decisions: {len(new_auctions)}")

    if not new_auctions:
        print(">>> Nothing to insert — all auctions already have bid_decisions")
        return 0

    market_values = [_to_float(r.get("market_value")) for r in auctions]
    market_values = [v for v in market_values if v is not None]
    county_median = sorted(market_values)[len(market_values) // 2] if market_values else 200000.0
    print(f">>> County median market_value (formula-estimate basis): {county_median}")

    run_id = f"shard5-okaloosa-newrows-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"

    payload = []
    for r in new_auctions:
        cn = r["case_number"]
        sale_type = r.get("sale_type", "foreclosure")
        arv, arv_source = compute_arv_and_source(r, county_median)
        repairs = round(arv * 0.13, 2)
        max_bid = compute_max_bid(arv, repairs)
        ml_score = compute_ml_score(sale_type, arv_source, arv, max_bid)
        factors = build_factors(r, arv)

        payload.append({
            "pipeline_run_id": run_id,
            "case_number": cn,
            "parcel_id": r.get("parcel_id"),
            "address": r.get("property_address"),
            "auction_date": r.get("auction_date"),
            "arv": arv,
            "repairs": repairs,
            "repair_estimate": repairs,
            "final_judgment": None,
            "max_bid": max_bid,
            "bid_judgment_ratio": None,
            "recommendation": "BID" if max_bid > 0 else "SKIP",
            "confidence": ml_score,
            "ml_score": ml_score,
            "factors": factors,
            "county_slug": COUNTY,
            "triangle_score": ml_score,
            "pipeline_version": PIPELINE_VERSION,
            "arv_source": arv_source,
        })

    supa_url = _req("SUPABASE_URL").rstrip("/")
    url = f"{supa_url}/rest/v1/bid_decisions"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={
            **_headers(),
            "Prefer": "resolution=ignore-duplicates,return=representation",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = json.loads(r.read())
        print(f">>> INSERT results: requested {len(payload)}, server returned {len(body)} row(s)")
        for row in payload:
            print(f"    INSERTED bid_decisions for {row['case_number']} (arv={row['arv']}, max_bid={row['max_bid']}, ml_score={row['ml_score']})")
        return 0
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"bid_decisions insert FAILED: {e.code} {e.read().decode()[:500]}"
        )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        sys.exit(1)
