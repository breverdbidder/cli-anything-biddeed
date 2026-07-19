#!/usr/bin/env python3
"""
Okaloosa bid_decisions Backfill (2026-07-19, SHARD3-OKALOOSA-J-continuation)
==============================================================================
Writes one bid_decisions row per okaloosa multi_county_auctions case_number
(all 40) so Gold Standard letter J's per-county deal-triangle completeness
check finds a qualifying row for every auction. None of the existing 52
'PO_*' bid_decisions rows for okaloosa match any of the 40 real
case_numbers, so this is a pure backfill, not an update.

ARV / arv_source provenance (NEVER-LIE -- estimate vs real must never look
identical in provenance):
  - 38 of 40 rows now carry a real assessed_value/market_value, either from
    this session's live okaloosa county GIS ArcGIS lookup (36 rows,
    arv_source='okaloosa_pa_gis_value') or pre-existing on the row before
    this session (2 rows: 2024-CA-000470 / 2024-TDD-000089, same
    arv_source since the value itself came from a real appraiser source
    per the DB, not fabricated by this script).
  - 2 rows (2025-CA-002043-F: address had 0 GIS matches; 2025-CA-003450-C:
    corrupted address, out of scope for this session) have NO real value
    data anywhere on the row. For these ONLY, ARV is a disclosed formula
    estimate = the median market_value across okaloosa's 38 real-valued
    rows ($207,735 as of this run), tagged
    arv_source='formula_estimate_no_gis_match' so it can never be confused
    with a verified value downstream.
  ARV basis used = market_value (total appraised value) when present, else
  assessed_value, else the disclosed county-median estimate. market_value
  is preferred over assessed_value as the ARV proxy because Florida's
  assessed value is capped/lagged by Save Our Homes and non-homestead
  assessment caps and is routinely below true market value, whereas
  TOTALAPPR (market_value here) is the appraiser's actual market estimate
  -- a closer real-world proxy for ARV.

repairs / repair_estimate: 13% of arv (midpoint of the 12-15% range in the
task brief), a documented flat assumption, not case-specific (no condition
data exists for any of these 40 properties).

max_bid (Shapira Formula): (ARV*0.70) - repairs - $10,000 -
  MIN($25,000, 15%*ARV), clamped to >0.

ml_score (0-1): documented heuristic, NOT a constant --
  base 0.5
  + 0.15 if sale_type == 'tax_deed' (TD sales carry a real, GIS-verified
    APN in 100% of in-scope rows here, i.e. stronger title-chain data
    coverage than FC rows in this dataset)
  + 0.20 if arv_source == 'okaloosa_pa_gis_value' (real appraiser data,
    not a formula estimate)
  + up to 0.15 scaled by how far max_bid/arv sits below the Shapira 70%
    ARV ceiling (bigger margin of safety = higher confidence), i.e.
    0.15 * clamp((0.70 - max_bid/arv), 0, 0.20) / 0.20
  clamped to [0.05, 0.95] (never exactly 0 or 1 -- this is a heuristic,
  not a certainty).

factors jsonb (5 required keys):
  distress_location (0-1): 0.6 base, +0.1 if property_address present
    (rationale: an unresolved/missing address is itself a distress-data
    gap, not a location-quality signal, so its ABSENCE lowers confidence
    in this factor rather than the location itself).
  distress_property (0-1): 0.55 base for foreclosure, 0.65 for tax_deed
    (rationale: FL tax deed sales by definition follow >=2 years of
    unpaid property taxes, a stronger property-distress signal than a
    single mortgage default underlying most FC cases).
  distress_owner (0-1): flat 0.5 (rationale: no owner-specific data --
    bankruptcy, death, absentee-owner flags -- exists anywhere in this
    dataset for any of the 40 rows, so this is an honest "no signal"
    midpoint, not a derived score).
  cma_distressed (dollar): arv * 0.80 (20% distressed-sale discount off
    ARV -- standard investor comp assumption for an auction-acquired,
    as-is property).
  cma_resale (dollar): arv * 1.00 (ARV itself is already defined as the
    stabilized after-repair resale comp basis).

Write pattern: REST POST batch insert with Prefer: return=representation.
Exact success/fail counts are reported, never swallowed.

Env (required): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success (40/40 written), 1 = fatal error or partial failure
"""
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import httpx

PIPELINE_VERSION = "shard3_okaloosa_c366ee22_continuation"
GIS_ARV_SOURCE = "okaloosa_pa_gis_value"
FORMULA_ARV_SOURCE = "formula_estimate_no_gis_match"

NO_VALUE_CASE_NUMBERS = {"2025-CA-002043-F", "2025-CA-003450-C"}


def _req(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env: {name}")
    return v


def fetch_auctions() -> list[dict]:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    supa_key = _req("SUPABASE_SERVICE_ROLE_KEY")
    headers = {"apikey": supa_key, "Authorization": f"Bearer {supa_key}"}
    resp = httpx.get(
        f"{supa_url}/rest/v1/multi_county_auctions",
        params={
            "county": "eq.okaloosa",
            "select": "case_number,sale_type,property_address,parcel_id,assessed_value,market_value,auction_date",
        },
        headers=headers, timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _to_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def compute_arv_and_source(row: dict, county_median_market_value: float) -> tuple[float, str]:
    cn = row["case_number"]
    mv = _to_float(row.get("market_value"))
    av = _to_float(row.get("assessed_value"))
    if cn in NO_VALUE_CASE_NUMBERS or (mv is None and av is None):
        return round(county_median_market_value, 2), FORMULA_ARV_SOURCE
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
        margin = 0.70 - (max_bid / arv)  # bigger gap below the 70% ceiling = safer
        margin = max(0.0, min(margin, 0.20))
        score += 0.15 * (margin / 0.20)
    return round(max(0.05, min(score, 0.95)), 4)


def build_factors(row: dict, arv: float) -> dict:
    sale_type = row["sale_type"]
    has_address = bool(row.get("property_address"))
    distress_location = round(0.6 + (0.1 if has_address else 0.0), 2)
    distress_property = 0.65 if sale_type == "tax_deed" else 0.55
    distress_owner = 0.5
    return {
        "distress_location": distress_location,
        "distress_location_rationale": (
            "0.6 base FL panhandle auction market; +0.1 when a resolvable "
            "property_address exists on the source row (an unresolved/missing "
            "address is itself a distress-data gap, not a location signal)."
        ),
        "distress_property": distress_property,
        "distress_property_rationale": (
            "Tax deed (0.65): >=2 years unpaid property taxes is a stronger, "
            "codified distress signal. Foreclosure (0.55): single mortgage "
            "default, no additional property-condition data available."
        ),
        "distress_owner": distress_owner,
        "distress_owner_rationale": (
            "0.5 flat -- no owner-specific signal (bankruptcy, death, absentee "
            "flag) exists in this dataset for any okaloosa row; honest no-signal "
            "midpoint, not a derived score."
        ),
        "cma_distressed": round(arv * 0.80, 2),
        "cma_resale": round(arv * 1.00, 2),
    }


def main() -> int:
    rows = fetch_auctions()
    if len(rows) != 40:
        print(f"WARNING: expected 40 okaloosa rows, found {len(rows)}", file=sys.stderr)

    market_values = [_to_float(r.get("market_value")) for r in rows]
    market_values = [v for v in market_values if v is not None]
    county_median = sorted(market_values)[len(market_values) // 2] if market_values else 200000.0
    print(f">>> County median market_value (formula-estimate basis): {county_median}")

    run_id = f"gtm22j-okaloosa-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"

    payload = []
    for r in rows:
        cn = r["case_number"]
        sale_type = r["sale_type"]
        arv, arv_source = compute_arv_and_source(r, county_median)
        repairs = round(arv * 0.13, 2)
        max_bid = compute_max_bid(arv, repairs)
        ml_score = compute_ml_score(sale_type, arv_source, arv, max_bid)
        factors = build_factors(r, arv)
        bid_judgment_ratio = None  # no final_judgment data exists for any okaloosa row

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
            "bid_judgment_ratio": bid_judgment_ratio,
            "recommendation": "BID" if max_bid > 0 else "SKIP",
            "confidence": ml_score,
            "ml_score": ml_score,
            "factors": factors,
            "county_slug": "okaloosa",
            "triangle_score": ml_score,
            "pipeline_version": PIPELINE_VERSION,
            "arv_source": arv_source,
        })

    supa_url = _req("SUPABASE_URL").rstrip("/")
    supa_key = _req("SUPABASE_SERVICE_ROLE_KEY")
    headers = {
        "apikey": supa_key,
        "Authorization": f"Bearer {supa_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    resp = httpx.post(
        f"{supa_url}/rest/v1/bid_decisions",
        headers=headers, json=payload, timeout=60,
    )
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"bid_decisions insert FAILED: {resp.status_code} {resp.text[:1000]}")
    body = resp.json()
    print(f">>> INSERT results: requested {len(payload)}, server returned {len(body)} row(s)")
    if len(body) != len(payload):
        raise RuntimeError(
            f"FAIL LOUD: sent {len(payload)} rows but only {len(body)} were returned/inserted -- "
            f"partial failure, not reporting success."
        )
    print("SUCCESS: all rows inserted")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
