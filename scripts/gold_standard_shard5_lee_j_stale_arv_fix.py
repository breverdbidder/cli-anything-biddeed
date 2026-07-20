#!/usr/bin/env python3
"""SHARD-5 (seminole/highlands/lee), dispatch 8acb0c40-fd3b-48a6-b357-fc15c79f973f.

Incident fix: the adversarial-verify workflow (ULTRALOOP refuter) caught a
real staleness bug in this session's own J-generator run
(scripts/gold_standard_shard5_lee_j_generator.py). Root cause: this
session ran the J-generator BEFORE the E/I ArcGIS backfill
(scripts/gold_standard_shard5_lee_ei_arcgis_backfill.py). The J-generator
correctly fell back to the county-median default ARV ($256,703, disclosed
in the script's own docstring) for rows that had no assessed_value/
market_value/opening_bid AT THE TIME IT RAN -- but the very next script
in this same session then populated real assessed_value for several of
those same rows via live ArcGIS lookups, leaving bid_decisions.arv stale
(not fabricated from nothing, but computed from data that a later step in
this same session made obsolete).

Verified live: 28 of the 65 rows inserted under pipeline_run_id
'SHARD5-8acb0c40-LEE-J-v1' have a bid_decisions.arv that disagrees with
what the exact same formula would produce from CURRENT
multi_county_auctions data (20 of the 28 are the big fallback-vs-real
mismatch the refuter flagged; 8 more are smaller deltas from the E/I
script's marginally-more-precise ArcGIS ASSESSED value overwriting an
existing-but-less-precise value).

This script recomputes and PATCHes those 28 rows in place (same case
numbers, same pipeline_run_id, no new rows) using the identical formula
as the original generator, against live current data. It does not touch
any other bid_decisions row.
"""
import json
import os
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
PIPELINE_RUN_ID = "SHARD5-8acb0c40-LEE-J-v1"

ML_SCORE = 0.55
LOCATION_SCORE = 0.42
CONFIDENCE_SCORE = 0.58


def headers():
    return {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def sb_get(path, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(url, headers=headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch(path, params, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}?{params}", data=body,
        headers={**headers(), "Prefer": "return=minimal"}, method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def calc(assessed, market, opening):
    assessed = assessed or 0
    market = market or 0
    opening = opening or 0
    arv = max(assessed, market) if max(assessed, market) > 0 else (opening * 1.4 if opening > 0 else 0)
    if arv <= 0:
        arv = 256703
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
        "cma_distressed": {"value": round(arv * 0.87, 2), "sources": ["assessed_value_proxy"]},
        "cma_resale": {"value": round(arv * 1.12, 2), "sources": ["market_value_proxy"]},
    }
    bid_ratio = max_bid / opening if opening > 0 else None
    if bid_ratio is not None:
        bid_ratio = min(bid_ratio, 9.99)
    return arv, repairs, max_bid, factors, bid_ratio


def main():
    rows = sb_get(
        "bid_decisions",
        f"pipeline_run_id=eq.{PIPELINE_RUN_ID}&select=case_number,arv",
    )
    case_numbers = [r["case_number"] for r in rows]
    print(f"Rows under {PIPELINE_RUN_ID}: {len(case_numbers)}", flush=True)

    in_clause = ",".join(case_numbers)
    auctions = sb_get(
        "multi_county_auctions",
        f"county=eq.lee&case_number=in.({in_clause})"
        "&select=case_number,opening_bid,assessed_value,market_value",
    )
    by_case = {a["case_number"]: a for a in auctions}

    fixed = 0
    unchanged = 0
    for r in rows:
        cn = r["case_number"]
        a = by_case.get(cn)
        if not a:
            continue
        arv, repairs, max_bid, factors, bid_ratio = calc(
            a.get("assessed_value"), a.get("market_value"), a.get("opening_bid")
        )
        old_arv = float(r["arv"])
        if abs(arv - old_arv) <= 1:
            unchanged += 1
            continue

        opening = a.get("opening_bid") or 0
        patch = {
            "arv": round(arv, 2),
            "repairs": round(repairs, 2),
            "final_judgment": round(opening, 2) if opening else None,
            "max_bid": round(max_bid, 2),
            "bid_judgment_ratio": round(bid_ratio, 4) if bid_ratio else None,
            "recommendation": "BID" if (opening > 0 and max_bid > opening) else "PASS",
            "factors": factors,
        }
        status, resp = sb_patch(
            "bid_decisions",
            f"pipeline_run_id=eq.{PIPELINE_RUN_ID}&case_number=eq.{urllib.parse.quote(cn)}",
            patch,
        )
        if status in (200, 204):
            fixed += 1
            print(f"  fixed {cn}: arv {old_arv} -> {arv}", flush=True)
        else:
            print(f"  FAILED {cn}: {status} {resp[:200]}", flush=True)

    print(f"\n=== DONE: fixed={fixed} unchanged={unchanged} ===", flush=True)


if __name__ == "__main__":
    main()
