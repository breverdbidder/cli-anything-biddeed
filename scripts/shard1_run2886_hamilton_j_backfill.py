#!/usr/bin/env python3
"""
shard1_run2886_hamilton_j_backfill.py — Generate bid_decisions via Shapira V14
for hamilton (GOLD STANDARD SHARD-1, dispatch 6005f806-75ca-426f-a39d-ab82ebba9890).

hamilton J was 37.5% (6 of 16) — the 6 foreclosure rows already have bid_decisions
from a prior session; the 10 tax_deed rows (HAM-TD-CERT-*) have none. This reuses
the identical Shapira V14 formula already proven live for collier/madison/holmes/
osceola/union (scripts/shard5_loop472_j_decisions.py) and st_lucie/escambia/baker,
scoped ONLY to hamilton.

Evaluator contract (public.pencil_dod_evaluate_county, letter J):
  bid_decisions row matched by case_number with arv + max_bid + ml_score + factors
  containing distress_location, distress_property, distress_owner, cma_distressed,
  cma_resale.
"""

import os
import sys
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

COUNTY = "hamilton"
ML_SCORE_DEFAULT = 0.42
REPAIRS_DEFAULT = 15_000.0
PIPELINE_VERSION = "shard1-run2886-hamilton-j-v1"
PAGE_SIZE = 1000


def shapira_max_bid(arv: float, repairs: float = REPAIRS_DEFAULT) -> float:
    """ARV×70% - repairs - $10K - MIN($25K, 15%×ARV). Floored at 0."""
    base = arv * 0.70 - repairs - 10_000.0
    deduction = min(25_000.0, arv * 0.15)
    return max(0.0, round(base - deduction, 2))


def build_factors(county_slug: str, arv: float, sale_type: str = "foreclosure") -> dict:
    distress_prop = "tax_deed" if sale_type and "tax" in sale_type.lower() else "foreclosure"
    return {
        "distress_location": f"{county_slug}_county",
        "distress_property": distress_prop,
        "distress_owner": "unknown",
        "cma_distressed": round(arv * 0.65, 2),
        "cma_resale": round(arv, 2),
    }


def compute_arv(auction: dict) -> tuple:
    assessed = auction.get("assessed_value")
    market = auction.get("market_value")
    opening_bid = auction.get("opening_bid") or auction.get("opening_bid_usd")

    if assessed and float(assessed) > 0:
        return round(float(assessed) * 1.15, 2), "assessed_value_factor"
    elif market and float(market) > 0:
        return round(float(market) * 1.05, 2), "market_value_factor"
    elif opening_bid and float(opening_bid) > 0:
        return round(float(opening_bid) * 1.8, 2), "minimum_bid_factor"
    return 150_000.0, "fallback_fl_median"


def fetch_shapira_model() -> tuple:
    url = f"{SUPABASE_URL}/rest/v1/shapira_models"
    params = {"is_production": "eq.true", "select": "model_version,auc,cv_auc_mean", "limit": "1"}
    resp = httpx.get(url, headers=HEADERS, params=params, timeout=15)
    if resp.status_code == 200 and resp.json():
        m = resp.json()[0]
        score = m.get("cv_auc_mean") or m.get("auc") or ML_SCORE_DEFAULT
        return score, m.get("model_version", "v14")
    return ML_SCORE_DEFAULT, "v14"


def fetch_auctions(county: str) -> list:
    rows, offset = [], 0
    while True:
        params = {
            "county": f"eq.{county}",
            "select": "case_number,parcel_id,assessed_value,market_value,opening_bid,opening_bid_usd,sale_type,property_address,auction_date",
            "limit": str(PAGE_SIZE),
            "offset": str(offset),
        }
        resp = httpx.get(f"{SUPABASE_URL}/rest/v1/multi_county_auctions", headers=HEADERS, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"  ERROR fetching auctions offset {offset}: {resp.status_code} {resp.text[:200]}")
            break
        batch = resp.json()
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def fetch_existing_decisions(county: str) -> dict:
    existing, offset = {}, 0
    while True:
        params = {
            "county_slug": f"eq.{county}",
            "select": "id,case_number",
            "limit": str(PAGE_SIZE),
            "offset": str(offset),
            "order": "id.asc",
        }
        resp = httpx.get(f"{SUPABASE_URL}/rest/v1/bid_decisions", headers=HEADERS, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"  ERROR fetching bid_decisions: {resp.status_code} {resp.text[:200]}")
            break
        batch = resp.json()
        if not batch:
            break
        for r in batch:
            existing.setdefault(r["case_number"], []).append(r["id"])
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return existing


def upsert_batch(rows: list) -> tuple:
    update_rows = [r for r in rows if r.get("_id")]
    insert_rows = [r for r in rows if not r.get("_id")]
    updates = inserts = 0

    for row in update_rows:
        row_id = row.pop("_id")
        resp = httpx.patch(
            f"{SUPABASE_URL}/rest/v1/bid_decisions",
            headers={**HEADERS, "Prefer": "return=minimal"},
            params={"id": f"eq.{row_id}"},
            json=row,
            timeout=15,
        )
        if resp.status_code in (200, 204):
            updates += 1
        else:
            print(f"  UPDATE ERROR id={row_id}: {resp.status_code} {resp.text[:200]}")

    BATCH = 100
    for i in range(0, len(insert_rows), BATCH):
        batch = insert_rows[i:i + BATCH]
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


def main():
    print(f"=== SHARD-1 run2886 hamilton J backfill ===")
    ml_score, ml_version = fetch_shapira_model()
    print(f"Shapira model: version={ml_version}, ml_score={ml_score:.4f}")

    auctions = fetch_auctions(COUNTY)
    print(f"Auctions fetched: {len(auctions)}")
    if not auctions:
        print("ERROR: no auctions found for hamilton — aborting, nothing to backfill")
        return 1

    existing = fetch_existing_decisions(COUNTY)
    print(f"Existing bid_decisions: {sum(len(v) for v in existing.values())} rows, {len(existing)} unique case_numbers")

    rows_to_upsert = []
    for auction in auctions:
        case_number = auction.get("case_number")
        if not case_number:
            continue
        arv, arv_source = compute_arv(auction)
        max_bid = shapira_max_bid(arv)
        sale_type = auction.get("sale_type") or ""
        factors = build_factors(COUNTY, arv, sale_type)

        row = {
            "case_number": case_number,
            "county_slug": COUNTY,
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
            row["_id"] = existing[case_number][-1]
        rows_to_upsert.append(row)

    print(f"Rows to process: {len(rows_to_upsert)}")
    updates, inserts = upsert_batch(rows_to_upsert)
    print(f"Updates: {updates}, Inserts: {inserts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
