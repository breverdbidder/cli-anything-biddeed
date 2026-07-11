#!/usr/bin/env python3
"""
SHARD-11 Criterion J Generator — lafayette only (run3679, dispatch
17725211-9941-4675-87d5-14eacc6a6bcb)

Adapted directly from scripts/shard5_leon_j_generator.py (same evaluator
contract, same Shapira formula, same ml_score baseline). Scoped to
lafayette's single row (case_number 25000056CAAXMX) instead of a fixed
county list.

Evaluator contract (pencil_dod_evaluate_county Criterion J):
  - arv        : after-repair value
  - max_bid    : Shapira formula ARV*70% - repairs - $10K - MIN($25K, 15%*ARV)
  - ml_score   : Shapira V14 (0.65 baseline for non-Brevard counties)
  - factors    : JSONB with ALL 5 keys:
                 distress_location, distress_property, distress_owner,
                 cma_distressed, cma_resale

Real inputs used for lafayette's single case (VERIFIED live from
multi_county_auctions): assessed_value=market_value=70973,
judgment_amount=104964.67. No opening_bid available (upcoming auction,
not yet sold) -> cma_distressed falls back to arv*0.65 per the reference
script's build_factors() logic.
"""

import os
import sys
import json
import httpx
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

TARGET_COUNTIES = ["lafayette"]

# INFERRED: 0.65 baseline ml_score for counties without a trained Shapira model
# (identical baseline/rationale as shard5_leon_j_generator.py)
ML_SCORE_BASELINE = 0.65
REPAIRS_DEFAULT = 25_000.0
PIPELINE_RUN_ID = "shard11-lafayette-j-generator-v1"
PIPELINE_VERSION = "shard11-lafayette-j-generator-v1"


def shapira_max_bid(arv: float, repairs: float = REPAIRS_DEFAULT) -> float:
    """Shapira Formula: ARV*70% - repairs - $10K - MIN($25K, 15%*ARV). Floored at 0."""
    base = arv * 0.70 - repairs - 10_000.0
    deduction = min(25_000.0, arv * 0.15)
    result = base - deduction
    return max(0.0, round(result, 2))


def compute_arv(auction: dict) -> tuple:
    """
    Priority: assessed_value * 1.15 > market_value * 1.05 > opening_bid * 1.4 > 175000
    """
    assessed = auction.get("assessed_value")
    market = auction.get("market_value")
    opening_bid = auction.get("opening_bid") or auction.get("opening_bid_usd")

    if assessed and float(assessed) > 0:
        arv = round(float(assessed) * 1.15, 2)
        return arv, "assessed_value_factor"
    elif market and float(market) > 0:
        arv = round(float(market) * 1.05, 2)
        return arv, "market_value_factor"
    elif opening_bid and float(opening_bid) > 0:
        arv = round(float(opening_bid) * 1.4, 2)
        return arv, "minimum_bid_factor"
    else:
        return 175_000.0, "fallback_county_median"


def build_factors(county_slug: str, arv: float, opening_bid, sale_type: str = "") -> dict:
    """Build all 5 required factor keys for J evaluator."""
    distress_prop = "foreclosure"
    if sale_type and "tax" in sale_type.lower():
        distress_prop = "tax_deed"

    cma_distressed = float(opening_bid) if opening_bid else round(arv * 0.65, 2)

    return {
        "distress_location": f"{county_slug}_county_fl",
        "distress_property": distress_prop,
        "distress_owner": "county_auction_motivated",
        "cma_distressed": cma_distressed,
        "cma_resale": round(arv, 2),
    }


def fetch_auctions(county_slug: str) -> list:
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
    rows = []
    page_size = 500
    offset = 0

    while True:
        params = {
            "county": f"eq.{county_slug}",
            "select": (
                "case_number,parcel_id,assessed_value,market_value,"
                "opening_bid,opening_bid_usd,sale_type,property_address,"
                "auction_date,auction_status"
            ),
            "limit": str(page_size),
            "offset": str(offset),
            "order": "auction_date.desc.nullslast",
        }
        resp = httpx.get(url, headers=HEADERS, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"  ERROR fetching MCA offset {offset}: {resp.status_code} {resp.text[:200]}")
            break
        batch = resp.json()
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    return rows


def fetch_existing_decisions(county_slug: str) -> dict:
    url = f"{SUPABASE_URL}/rest/v1/bid_decisions"
    existing = {}
    page_size = 1000
    offset = 0

    while True:
        params = {
            "county_slug": f"eq.{county_slug}",
            "select": "id,case_number,arv,max_bid,ml_score,factors",
            "limit": str(page_size),
            "offset": str(offset),
            "order": "id.asc",
        }
        resp = httpx.get(url, headers=HEADERS, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"  ERROR fetching bid_decisions offset {offset}: {resp.status_code} {resp.text[:200]}")
            break
        batch = resp.json()
        if not batch:
            break
        for r in batch:
            cn = r["case_number"]
            if cn not in existing:
                existing[cn] = r
            else:
                if r["id"] > existing[cn]["id"]:
                    existing[cn] = r
        if len(batch) < page_size:
            break
        offset += page_size

    return existing


def row_passes_j(bd_row: dict) -> bool:
    required_keys = [
        "distress_location", "distress_property", "distress_owner",
        "cma_distressed", "cma_resale"
    ]
    if bd_row.get("arv") is None:
        return False
    if bd_row.get("max_bid") is None:
        return False
    if bd_row.get("ml_score") is None:
        return False
    factors = bd_row.get("factors") or {}
    if isinstance(factors, str):
        try:
            factors = json.loads(factors)
        except Exception:
            return False
    return all(k in factors for k in required_keys)


def patch_row(row_id: int, payload: dict) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/bid_decisions"
    params = {"id": f"eq.{row_id}"}
    resp = httpx.patch(
        url,
        headers={**HEADERS, "Prefer": "return=minimal"},
        params=params,
        json=payload,
        timeout=15,
    )
    return resp.status_code in (200, 204)


def insert_batch(rows: list) -> int:
    inserted = 0
    batch_size = 50

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        resp = httpx.post(
            f"{SUPABASE_URL}/rest/v1/bid_decisions",
            headers={**HEADERS, "Prefer": "resolution=ignore-duplicates,return=minimal"},
            json=batch,
            timeout=30,
        )
        if resp.status_code in (200, 201):
            inserted += len(batch)
        else:
            print(f"  INSERT ERROR batch {i}-{i+len(batch)}: {resp.status_code} {resp.text[:300]}")

    return inserted


def get_j_metric(county_slug: str) -> dict:
    resp = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        headers=HEADERS,
        json={"p_county": county_slug},
        timeout=30,
    )
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, dict):
            return data.get("J", {})
    return {}


def process_county(county_slug: str) -> dict:
    print(f"\n{'='*60}")
    print(f"COUNTY: {county_slug.upper()}")
    print(f"{'='*60}")

    j_before = get_j_metric(county_slug)
    j_metric_before = j_before.get("metric")
    j_pass_before = j_before.get("pass", False)
    print(f"  J BEFORE: metric={j_metric_before}%, pass={j_pass_before}")

    auctions = fetch_auctions(county_slug)
    print(f"  MCA rows: {len(auctions)}")

    existing = fetch_existing_decisions(county_slug)
    print(f"  Existing bid_decisions: {len(existing)} unique case_numbers")

    inserts_needed = []
    patches_done = 0
    patches_failed = 0
    skipped_complete = 0

    for auction in auctions:
        case_number = auction.get("case_number")
        if not case_number:
            continue

        arv, arv_source = compute_arv(auction)
        repairs = REPAIRS_DEFAULT
        max_bid = shapira_max_bid(arv, repairs)
        ml_score = ML_SCORE_BASELINE
        opening_bid = auction.get("opening_bid") or auction.get("opening_bid_usd")
        sale_type = auction.get("sale_type") or ""
        factors = build_factors(county_slug, arv, opening_bid, sale_type)
        recommendation = "BID" if max_bid > 5000 else "SKIP"

        if case_number in existing:
            bd = existing[case_number]
            if row_passes_j(bd):
                skipped_complete += 1
                continue
            payload = {
                "arv": arv,
                "repairs": repairs,
                "repair_estimate": repairs,
                "max_bid": max_bid,
                "ml_score": ml_score,
                "factors": factors,
                "arv_source": arv_source,
                "recommendation": recommendation,
                "pipeline_run_id": PIPELINE_RUN_ID,
                "pipeline_version": PIPELINE_VERSION,
            }
            if auction.get("auction_date"):
                payload["auction_date"] = auction["auction_date"]
            if patch_row(bd["id"], payload):
                patches_done += 1
            else:
                patches_failed += 1
        else:
            row = {
                "case_number": case_number,
                "county_slug": county_slug,
                "parcel_id": auction.get("parcel_id"),
                "address": auction.get("property_address"),
                "auction_date": auction.get("auction_date"),
                "arv": arv,
                "repairs": repairs,
                "repair_estimate": repairs,
                "max_bid": max_bid,
                "ml_score": ml_score,
                "factors": factors,
                "arv_source": arv_source,
                "recommendation": recommendation,
                "pipeline_run_id": PIPELINE_RUN_ID,
                "pipeline_version": PIPELINE_VERSION,
            }
            inserts_needed.append(row)

    inserted = insert_batch(inserts_needed) if inserts_needed else 0

    print(f"  Skipped (already J-complete): {skipped_complete}")
    print(f"  Patched (filled gaps): {patches_done} (failed: {patches_failed})")
    print(f"  Inserted (new rows): {inserted}")

    j_after = get_j_metric(county_slug)
    j_metric_after = j_after.get("metric")
    j_pass_after = j_after.get("pass", False)
    print(f"  J AFTER:  metric={j_metric_after}%, pass={j_pass_after}")

    return {
        "county": county_slug,
        "mca_total": len(auctions),
        "existing_bd": len(existing),
        "skipped": skipped_complete,
        "patched": patches_done,
        "inserted": inserted,
        "j_before": j_metric_before,
        "j_after": j_metric_after,
        "j_pass": j_pass_after,
    }


def main():
    print("SHARD-11 Criterion J Generator — lafayette")
    print(f"Run timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Target counties: {TARGET_COUNTIES}")
    print(f"ML score baseline: {ML_SCORE_BASELINE} (INFERRED: Shapira V14, non-Brevard counties)")

    results = []
    for county in TARGET_COUNTIES:
        result = process_county(county)
        results.append(result)

    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    all_pass = True
    for r in results:
        j_b = f"{r['j_before']}%" if r['j_before'] is not None else "null"
        j_a = f"{r['j_after']}%" if r['j_after'] is not None else "null"
        pass_str = "PASS" if r['j_pass'] else "FAIL"
        if not r['j_pass']:
            all_pass = False
        print(f"{r['county']}: MCA={r['mca_total']} BD={r['existing_bd']} "
              f"skip={r['skipped']} patch={r['patched']} insert={r['inserted']} "
              f"J_before={j_b} J_after={j_a} {pass_str}")

    print(f"\nAll counties J=PASS: {'YES' if all_pass else 'NO'}")
    print(f"\nSQL VERIFICATION:")
    for r in results:
        print(f"  SELECT COUNT(*) FROM bid_decisions WHERE county_slug='{r['county']}';  -- expect >={r['mca_total']}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
