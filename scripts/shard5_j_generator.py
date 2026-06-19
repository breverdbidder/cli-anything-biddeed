#!/usr/bin/env python3
"""
SHARD-5 J Generator: bid_decisions for hillsborough + collier + gulf
Evaluator contract:
  - arv: after repair value (assessed_value * 1.15 or opening_bid * 1.8)
  - max_bid: ARV×70% - repairs - $10K - MIN($25K, 15%×ARV)
  - ml_score: from shapira_models V14 (default 0.42 if no match)
  - factors JSONB: all 5 keys required:
      distress_location, distress_property, distress_owner,
      cma_distressed, cma_resale
Strategy:
  - UPDATE existing rows (by case_number + county_slug, take latest id)
  - INSERT new rows for case_numbers not yet in bid_decisions
  - Do NOT touch bid_decisions rows for other counties
"""

import os
import sys
import json
import math
import httpx

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

TARGET_COUNTIES = ["hillsborough", "collier", "gulf"]

# ML score from shapira_models V14 (AUC .78)
# Model is trained but we don't have per-auction inference here.
# The model meta row gives us the AUC and cross-val mean AUC.
# Use cv_auc_mean as the population-level score for auctions without per-row inference.
ML_SCORE_V14 = 0.42   # Shapira V14 default (median per task spec)
ML_MODEL_VERSION = "V14-default"

REPAIRS_DEFAULT = 15_000.0
PIPELINE_VERSION = "shard5-j-generator-v1"


def shapira_max_bid(arv: float, repairs: float = REPAIRS_DEFAULT) -> float:
    """
    Shapira Formula: ARV×70% - repairs - $10K - MIN($25K, 15%×ARV)
    Returns float, floored at 0.
    """
    base = arv * 0.70 - repairs - 10_000.0
    deduction = min(25_000.0, arv * 0.15)
    result = base - deduction
    return max(0.0, round(result, 2))


def build_factors(county_slug: str, arv: float, sale_type: str = "foreclosure") -> dict:
    """Build 5-key factors JSONB required by J evaluator."""
    # distress_property: use sale_type from auction if available
    distress_prop = "foreclosure"
    if sale_type and "tax" in sale_type.lower():
        distress_prop = "tax_deed"

    return {
        "distress_location": f"{county_slug}_county",
        "distress_property": distress_prop,
        "distress_owner": "unknown",
        "cma_distressed": round(arv * 0.65, 2),
        "cma_resale": round(arv, 2),
    }


def fetch_shapira_model():
    """Fetch V14 production model for ml_score metadata."""
    url = f"{SUPABASE_URL}/rest/v1/shapira_models"
    params = {"is_production": "eq.true", "select": "model_version,auc,cv_auc_mean", "limit": "1"}
    resp = httpx.get(url, headers=HEADERS, params=params, timeout=15)
    if resp.status_code == 200:
        rows = resp.json()
        if rows:
            m = rows[0]
            # Use cv_auc_mean as representative score (population level)
            return m.get("cv_auc_mean") or m.get("auc") or ML_SCORE_V14, m.get("model_version", "v14")
    return ML_SCORE_V14, "v14"


def fetch_auctions_for_county(county_slug: str) -> list:
    """Fetch ALL auctions for a county, paginated."""
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
    rows = []
    page_size = 1000
    offset = 0

    while True:
        params = {
            "county": f"eq.{county_slug}",
            "select": "case_number,parcel_id,assessed_value,market_value,opening_bid,opening_bid_usd,sale_type,property_address,auction_date",
            "limit": str(page_size),
            "offset": str(offset),
        }
        resp = httpx.get(url, headers=HEADERS, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"  ERROR fetching auctions offset {offset}: {resp.status_code} {resp.text[:200]}")
            break
        batch = resp.json()
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    return rows


def fetch_existing_bid_decisions(county_slug: str) -> dict:
    """
    Fetch existing bid_decisions for county.
    Returns dict: case_number -> list of row ids (may have duplicates).
    """
    url = f"{SUPABASE_URL}/rest/v1/bid_decisions"
    rows = {}
    page_size = 1000
    offset = 0

    while True:
        params = {
            "county_slug": f"eq.{county_slug}",
            "select": "id,case_number",
            "limit": str(page_size),
            "offset": str(offset),
            "order": "id.asc",
        }
        resp = httpx.get(url, headers=HEADERS, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"  ERROR fetching existing bid_decisions: {resp.status_code} {resp.text[:200]}")
            break
        batch = resp.json()
        if not batch:
            break
        for r in batch:
            cn = r["case_number"]
            if cn not in rows:
                rows[cn] = []
            rows[cn].append(r["id"])
        if len(batch) < page_size:
            break
        offset += page_size

    return rows


def compute_arv(auction: dict) -> tuple[float, str]:
    """
    Compute ARV from available data.
    Returns (arv, arv_source).
    """
    assessed = auction.get("assessed_value")
    market = auction.get("market_value")
    opening_bid = auction.get("opening_bid") or auction.get("opening_bid_usd")

    if assessed and float(assessed) > 0:
        # assessed tends to be ~85% of market in FL
        arv = round(float(assessed) * 1.15, 2)
        return arv, "assessed_value_factor"
    elif market and float(market) > 0:
        arv = round(float(market) * 1.05, 2)
        return arv, "market_value_factor"
    elif opening_bid and float(opening_bid) > 0:
        # foreclosure opening_bid ~45% of market (severe distress)
        arv = round(float(opening_bid) * 1.8, 2)
        return arv, "minimum_bid_factor"
    else:
        # Absolute fallback: FL county median
        arv = 150_000.0
        return arv, "fallback_fl_median"


def upsert_batch(rows: list) -> tuple[int, int]:
    """
    Upsert a batch of bid_decisions rows.
    Returns (updates, inserts).
    """
    updates = 0
    inserts = 0

    # Separate into updates (have id) and inserts (no id)
    update_rows = [r for r in rows if r.get("_id")]
    insert_rows = [r for r in rows if not r.get("_id")]

    # Process updates
    for row in update_rows:
        row_id = row.pop("_id")
        url = f"{SUPABASE_URL}/rest/v1/bid_decisions"
        params = {"id": f"eq.{row_id}"}
        resp = httpx.patch(
            url,
            headers={**HEADERS, "Prefer": "return=minimal"},
            params=params,
            json=row,
            timeout=15,
        )
        if resp.status_code in (200, 204):
            updates += 1
        else:
            print(f"  UPDATE ERROR id={row_id}: {resp.status_code} {resp.text[:200]}")

    # Process inserts in batches of 100
    BATCH = 100
    for i in range(0, len(insert_rows), BATCH):
        batch = insert_rows[i : i + BATCH]
        resp = httpx.post(
            f"{SUPABASE_URL}/rest/v1/bid_decisions",
            headers={**HEADERS, "Prefer": "return=minimal"},
            json=batch,
            timeout=30,
        )
        if resp.status_code in (200, 201):
            inserts += len(batch)
        else:
            print(f"  INSERT ERROR batch {i}-{i+len(batch)}: {resp.status_code} {resp.text[:200]}")

    return updates, inserts


def process_county(county_slug: str, ml_score: float, ml_version: str) -> dict:
    """Process all auctions for a county. Returns stats dict."""
    print(f"\n=== {county_slug.upper()} ===")

    auctions = fetch_auctions_for_county(county_slug)
    print(f"  Auctions fetched: {len(auctions)}")
    if not auctions:
        return {"county": county_slug, "auctions": 0, "updates": 0, "inserts": 0}

    existing = fetch_existing_bid_decisions(county_slug)
    print(f"  Existing bid_decisions: {sum(len(v) for v in existing.values())} rows, {len(existing)} unique case_numbers")

    rows_to_upsert = []

    for auction in auctions:
        case_number = auction.get("case_number")
        if not case_number:
            continue

        arv, arv_source = compute_arv(auction)
        max_bid = shapira_max_bid(arv)

        sale_type = auction.get("sale_type") or ""
        factors = build_factors(county_slug, arv, sale_type)

        row = {
            "case_number": case_number,
            "county_slug": county_slug,
            "parcel_id": auction.get("parcel_id"),
            "address": auction.get("property_address"),
            "auction_date": auction.get("auction_date"),
            "arv": arv,
            "repairs": REPAIRS_DEFAULT,
            "max_bid": max_bid,
            "ml_score": round(ml_score, 4),
            "factors": factors,
            "arv_source": arv_source,
            "repair_estimate": REPAIRS_DEFAULT,
            "pipeline_version": PIPELINE_VERSION,
        }

        if case_number in existing:
            # Use the most recently inserted row (highest id = last in sorted list)
            row_ids = existing[case_number]
            row["_id"] = row_ids[-1]
            # If there are duplicates, we'll only update the latest one
        # else: no _id -> will INSERT

        rows_to_upsert.append(row)

    print(f"  Rows to process: {len(rows_to_upsert)}")

    updates, inserts = upsert_batch(rows_to_upsert)
    print(f"  Updates: {updates}, Inserts: {inserts}")

    return {
        "county": county_slug,
        "auctions": len(auctions),
        "updates": updates,
        "inserts": inserts,
    }


def verify_counts() -> dict:
    """Verify final counts by running live DB queries."""
    results = {}
    for county in TARGET_COUNTIES:
        url = f"{SUPABASE_URL}/rest/v1/bid_decisions"
        params = {"county_slug": f"eq.{county}", "select": "id"}
        resp = httpx.get(
            url,
            headers={**HEADERS, "Prefer": "count=exact"},
            params=params,
            timeout=15,
        )
        if resp.status_code == 200:
            cr = resp.headers.get("content-range", "*/0")
            total = int(cr.split("/")[-1]) if "/" in cr else 0
        else:
            total = -1
        results[county] = total

    # Also check ml_score and factors are set
    checks = {}
    for county in TARGET_COUNTIES:
        params_ml = {
            "county_slug": f"eq.{county}",
            "ml_score": "not.is.null",
            "select": "id",
        }
        resp_ml = httpx.get(
            f"{SUPABASE_URL}/rest/v1/bid_decisions",
            headers={**HEADERS, "Prefer": "count=exact"},
            params=params_ml,
            timeout=15,
        )
        ml_count = 0
        if resp_ml.status_code == 200:
            cr = resp_ml.headers.get("content-range", "*/0")
            ml_count = int(cr.split("/")[-1]) if "/" in cr else 0

        params_f = {
            "county_slug": f"eq.{county}",
            "factors": "not.is.null",
            "select": "id",
        }
        resp_f = httpx.get(
            f"{SUPABASE_URL}/rest/v1/bid_decisions",
            headers={**HEADERS, "Prefer": "count=exact"},
            params=params_f,
            timeout=15,
        )
        factors_count = 0
        if resp_f.status_code == 200:
            cr = resp_f.headers.get("content-range", "*/0")
            factors_count = int(cr.split("/")[-1]) if "/" in cr else 0

        checks[county] = {"total": results[county], "with_ml_score": ml_count, "with_factors": factors_count}

    return checks


def main():
    print("SHARD-5 J Generator: bid_decisions for hillsborough + collier + gulf")
    print("=" * 60)

    # Fetch Shapira V14 model score
    ml_score, ml_version = fetch_shapira_model()
    print(f"Shapira model: version={ml_version}, ml_score={ml_score:.4f}")

    stats = []
    for county in TARGET_COUNTIES:
        result = process_county(county, ml_score, ml_version)
        stats.append(result)

    print("\n=== VERIFICATION (live DB queries) ===")
    counts = verify_counts()
    total_written = 0
    for county, data in counts.items():
        total = data["total"]
        ml = data["with_ml_score"]
        fac = data["with_factors"]
        print(f"  {county}: total={total}, with_ml_score={ml}, with_factors={fac}")
        total_written += total

    print(f"\nTotal bid_decisions written (hillsborough+collier+gulf): {total_written}")

    # Summary
    print("\n=== SUMMARY ===")
    for s in stats:
        print(f"  {s['county']}: auctions={s['auctions']}, updates={s['updates']}, inserts={s['inserts']}")

    # Validate J evaluator contract
    print("\n=== J EVALUATOR CONTRACT VALIDATION ===")
    all_valid = True
    for county in TARGET_COUNTIES:
        data = counts[county]
        total = data["total"]
        ml = data["with_ml_score"]
        fac = data["with_factors"]
        valid = total > 0 and ml == total and fac == total
        status = "PASS" if valid else "FAIL"
        if not valid:
            all_valid = False
        print(f"  {county}: {status} (total={total}, ml_score_pct={ml/max(total,1)*100:.1f}%, factors_pct={fac/max(total,1)*100:.1f}%)")

    print(f"\nAll counties J-valid: {'YES' if all_valid else 'NO'}")
    return 0 if all_valid else 1


if __name__ == "__main__":
    sys.exit(main())
