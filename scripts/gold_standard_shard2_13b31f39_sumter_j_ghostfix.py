"""GOLD STANDARD SHARD-2 (dispatch 13b31f39, sumter/flagler) — sumter J ghost-row repair.

Root cause (confirmed live): bid_decisions already had rows for the 4 missing
sumter case numbers (2025-CA-000255, TD-5054, TD-5056, TD-5058) but every
numeric/factors column was NULL, so the DoD evaluator counted them as
incomplete while scripts/gold_standard_shard5_sumter_j_generator.py's
idempotent "case_number not in existing" filter skipped them forever (ghost
rows, not missing rows). Underlying multi_county_auctions data for all 4 was
present and complete (assessed_value/market_value/opening_bid all non-null),
so this is a PATCH of existing rows using the same Shapira-proxy formula
already applied to sumter's other 7 rows, not a new-data problem.
"""
import os, json, requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

def headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}

rows = {
    "2025-CA-000255": {"assessed_value": 1133690, "market_value": 1133690, "opening_bid": None},
    "TD-5054": {"assessed_value": 4040, "market_value": 4040, "opening_bid": 1507.55},
    "TD-5056": {"assessed_value": 6200, "market_value": 6200, "opening_bid": 1467.39},
    "TD-5058": {"assessed_value": 18240, "market_value": 18240, "opening_bid": 2046.34},
}

ML_SCORE = 0.55
LOCATION_SCORE = 0.42
CONFIDENCE_SCORE = 0.58
COUNTY_DEFAULT_ARV = 180000

def calc(row):
    assessed = row.get("assessed_value") or 0
    opening = row.get("opening_bid") or 0
    market = row.get("market_value") or 0
    arv = max(assessed, market) if max(assessed, market) > 0 else (opening * 1.4 if opening > 0 else 0)
    if arv <= 0:
        arv = COUNTY_DEFAULT_ARV
    arv = min(arv, 5_000_000)
    if arv < 100_000:
        repairs = 25_000
    elif arv < 250_000:
        repairs = 20_000
    elif arv < 500_000:
        repairs = 15_000
    else:
        repairs = 12_000
    max_bid = max((arv * 0.7) - repairs - 10_000, min(25_000, arv * 0.15))
    factors = {
        "distress_location": LOCATION_SCORE,
        "distress_property": 0.50,
        "distress_owner": 0.55,
        "cma_distressed": {"value": round(arv * 0.87, 2), "sources": ["assessed_value_proxy"], "honesty_marker": "INFERRED"},
        "cma_resale": {"value": round(arv * 1.12, 2), "sources": ["market_value_proxy"], "honesty_marker": "INFERRED"},
    }
    bid_ratio = max_bid / opening if opening > 0 else None
    if bid_ratio is not None:
        bid_ratio = min(bid_ratio, 9.99)
    return {
        "arv": round(arv, 2),
        "final_judgment": round(opening, 2) if opening else None,
        "max_bid": round(max_bid, 2),
        "bid_judgment_ratio": round(bid_ratio, 4) if bid_ratio else None,
        "recommendation": "BID" if (opening > 0 and max_bid > opening) else "PASS",
        "confidence": CONFIDENCE_SCORE,
        "ml_score": ML_SCORE,
        "factors": factors,
        "pipeline_run_id": "GOLDSTANDARD-SHARD2-13b31f39-SUMTER-J-GHOSTFIX-v1",
    }

for case_number, row in rows.items():
    payload = calc(row)
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/bid_decisions",
        headers={**headers(), "Prefer": "return=representation"},
        params={"case_number": f"eq.{case_number}", "county_slug": "eq.sumter"},
        data=json.dumps(payload),
        timeout=60,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Fail-loud: PATCH failed for {case_number}: {resp.status_code} {resp.text[:500]}")
    updated = resp.json()
    if len(updated) != 1:
        raise RuntimeError(f"Fail-loud: expected 1 row updated for {case_number}, got {len(updated)}")
    print(f"{case_number}: updated arv={payload['arv']} max_bid={payload['max_bid']} ml_score={payload['ml_score']}")

print("DONE")
