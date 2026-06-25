#!/usr/bin/env python3
"""
shard5_loop472_j_decisions.py — Generate bid_decisions via Shapira V14
for loop-472 shard-5 counties: collier, madison, holmes, osceola, union.

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

TARGET_COUNTIES = ["collier", "madison", "holmes", "osceola", "union"]

ML_SCORE_DEFAULT = 0.42
ML_MODEL_VERSION = "V14-default"
REPAIRS_DEFAULT = 15_000.0
PIPELINE_VERSION = "shard5-loop472-j-v1"
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
    rows = []
    offset = 0
    while True:
        params = {
            "county": f"eq.{county}",
            "select": "case_number,parcel_id,assessed_value,market_value,opening_bid,opening_bid_usd,sale_type,property_address,auction_date",
            "limit": str(PAGE_SIZE),
            "offset": str(offset),
        }
        resp = httpx.get(f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                         headers=HEADERS, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"  ERROR fetching auctions [{county}] offset {offset}: {resp.status_code} {resp.text[:200]}")
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
    existing = {}
    offset = 0
    while True:
        params = {
            "county_slug": f"eq.{county}",
            "select": "id,case_number",
            "limit": str(PAGE_SIZE),
            "offset": str(offset),
            "order": "id.asc",
        }
        resp = httpx.get(f"{SUPABASE_URL}/rest/v1/bid_decisions",
                         headers=HEADERS, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"  ERROR fetching bid_decisions [{county}]: {resp.status_code} {resp.text[:200]}")
            break
        batch = resp.json()
        if not batch:
            break
        for r in batch:
            cn = r["case_number"]
            existing.setdefault(cn, []).append(r["id"])
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


def process_county(county: str, ml_score: float, ml_version: str) -> dict:
    print(f"\n=== {county.upper()} ===")
    auctions = fetch_auctions(county)
    print(f"  Auctions fetched: {len(auctions)}")
    if not auctions:
        return {"county": county, "auctions": 0, "updates": 0, "inserts": 0}

    existing = fetch_existing_decisions(county)
    print(f"  Existing bid_decisions: {sum(len(v) for v in existing.values())} rows, "
          f"{len(existing)} unique case_numbers")

    rows_to_upsert = []
    for auction in auctions:
        case_number = auction.get("case_number")
        if not case_number:
            continue

        arv, arv_source = compute_arv(auction)
        max_bid = shapira_max_bid(arv)
        sale_type = auction.get("sale_type") or ""
        factors = build_factors(county, arv, sale_type)

        row = {
            "case_number": case_number,
            "county_slug": county,
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

    print(f"  Rows to process: {len(rows_to_upsert)}")
    updates, inserts = upsert_batch(rows_to_upsert)
    print(f"  Updates: {updates}, Inserts: {inserts}")

    return {"county": county, "auctions": len(auctions), "updates": updates, "inserts": inserts}


def verify_counts() -> dict:
    results = {}
    for county in TARGET_COUNTIES:
        resp = httpx.get(
            f"{SUPABASE_URL}/rest/v1/bid_decisions",
            headers={**HEADERS, "Prefer": "count=exact"},
            params={"county_slug": f"eq.{county}", "select": "id", "limit": "1"},
            timeout=15,
        )
        cr = resp.headers.get("content-range", "*/0")
        total = int(cr.split("/")[-1]) if "/" in cr and cr.split("/")[-1] != "*" else 0

        resp_ml = httpx.get(
            f"{SUPABASE_URL}/rest/v1/bid_decisions",
            headers={**HEADERS, "Prefer": "count=exact"},
            params={"county_slug": f"eq.{county}", "ml_score": "not.is.null", "select": "id", "limit": "1"},
            timeout=15,
        )
        cr_ml = resp_ml.headers.get("content-range", "*/0")
        ml_count = int(cr_ml.split("/")[-1]) if "/" in cr_ml and cr_ml.split("/")[-1] != "*" else 0

        resp_f = httpx.get(
            f"{SUPABASE_URL}/rest/v1/bid_decisions",
            headers={**HEADERS, "Prefer": "count=exact"},
            params={"county_slug": f"eq.{county}", "factors": "not.is.null", "select": "id", "limit": "1"},
            timeout=15,
        )
        cr_f = resp_f.headers.get("content-range", "*/0")
        factors_count = int(cr_f.split("/")[-1]) if "/" in cr_f and cr_f.split("/")[-1] != "*" else 0

        results[county] = {"total": total, "with_ml_score": ml_count, "with_factors": factors_count}
    return results


def main():
    print("SHARD-5 Loop-472 J Decisions: collier/madison/holmes/osceola/union")
    print("=" * 64)

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

    print(f"\nTotal bid_decisions written: {total_written}")

    print("\n=== SUMMARY ===")
    for s in stats:
        print(f"  {s['county']}: auctions={s['auctions']}, updates={s['updates']}, inserts={s['inserts']}")

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
        print(f"  {county}: {status} (total={total}, ml_score_pct={ml/max(total,1)*100:.1f}%, "
              f"factors_pct={fac/max(total,1)*100:.1f}%)")

    print(f"\nAll counties J-valid: {'YES' if all_valid else 'NO'}")
    return 0 if all_valid else 1


if __name__ == "__main__":
    sys.exit(main())
