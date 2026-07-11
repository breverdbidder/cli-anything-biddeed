#!/usr/bin/env python3
"""Marion County J backfill -- run3713 continuation, after the I (address/geo/value)
and C/D (tier1 parity) agents in this same session finished their passes.

Re-queries live canon (552 rows) + live bid_decisions fresh (does NOT reuse any
stale residual list) and inserts qualifying bid_decisions rows for every
case_number still missing one.

HONESTY-BUG FIX APPLIED (see supabase/migrations/20260711091500_shard6_marion_j_honesty_bug_fix.sql
and c50fab81 for the bug this corrects): the ORIGINAL marion_j_backfill_run3713.py
used arv = max(real_value, county_median * 0.4), which silently discarded the real
per-parcel value in favor of an inflated median-derived floor for any parcel whose
real value fell below it, while still tagging honesty_marker='VERIFIED'. This
script does NOT repeat that pattern:
  - If a row has a real market_value or assessed_value from multi_county_auctions,
    that value is used DIRECTLY as ARV with NO max()-against-a-derived-floor.
    honesty_marker = VERIFIED.
  - Only if a row has NO real value (market_value and assessed_value both NULL)
    does a floor apply, and it is an ABSOLUTE floor ($25,000), never a
    median-derived one. honesty_marker = INFERRED, noted as floor-applied.
  - For those floor rows, if a real opening_bid exists (tax-deed minimum bid --
    itself a real sourced number, just not a market-value estimate), a
    heuristic projection (opening_bid * 1.4) is computed and used ONLY if it
    exceeds the $25,000 floor; otherwise the flat floor is used. Either way this
    branch is tagged INFERRED, never VERIFIED, because it is not a real
    market/assessed value.

dispatch_id: fb80bb9c-7d7d-469f-b3c0-493b5e4f9b3f
Session: architect-20260711T080000, loop run 3713 (continuation)
"""
import os
import json
import urllib.request
import urllib.parse

SB_URL = os.environ["SUPABASE_URL"]
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
BASE = f"{SB_URL}/rest/v1"

TIERED_REPAIRS = [(100000, 30000), (200000, 25000), (400000, 20000), (float("inf"), 15000)]
ABSOLUTE_FLOOR = 25000.0
REQUIRED_KEYS = {"distress_location", "distress_property", "distress_owner", "cma_distressed", "cma_resale"}


def get_all(path, params):
    out, offset, page = [], 0, 1000
    params = dict(params)
    params.setdefault("order", "id")
    while True:
        q = urllib.parse.urlencode(params)
        req = urllib.request.Request(
            f"{BASE}/{path}?{q}",
            headers={**HEADERS, "Range-Unit": "items", "Range": f"{offset}-{offset + page - 1}"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            chunk = json.loads(resp.read().decode())
        out.extend(chunk)
        if len(chunk) < page:
            break
        offset += page
    return out


def post(path, payload, prefer="return=minimal"):
    h = dict(HEADERS)
    h["Prefer"] = prefer
    req = urllib.request.Request(f"{BASE}/{path}", data=json.dumps(payload).encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.status, resp.read().decode()


def tiered_repair(arv):
    for threshold, repair in TIERED_REPAIRS:
        if arv < threshold:
            return repair
    return 15000


def shapira_max_bid(arv, repairs):
    return (arv * 0.70) - repairs - 10000 - min(25000, 0.15 * arv)


def build(row):
    mkt = row.get("market_value") or row.get("assessed_value")
    opening = float(row.get("opening_bid") or 0)

    if mkt:
        # REAL value used DIRECTLY. No max() against a derived floor.
        arv = float(mkt)
        verified = True
        note = "per-parcel real assessed_value/market_value from multi_county_auctions, used directly (no floor applied)"
    else:
        projected = opening * 1.4 if opening > 1000 else 0.0
        arv = max(projected, ABSOLUTE_FLOOR)
        verified = False
        if projected >= ABSOLUTE_FLOOR:
            note = f"no real assessed/market value on file; opening_bid ${opening:,.2f} x1.4 heuristic projection (exceeds $25k floor) -- NOT a real market value"
        else:
            note = f"no real assessed/market value on file; opening_bid ${opening:,.2f} heuristic projection below $25k absolute floor -- floor applied, NOT a real market value"

    repairs = tiered_repair(arv)
    max_bid = shapira_max_bid(arv, repairs)
    ml_score = 0.72 if max_bid > 1000 else 0.40
    opening_f = opening if opening > 0 else arv * 0.5
    ratio = min(9.9999, max(-9.9999, max_bid / opening_f))

    factors = {
        "distress_location": {"score": 6.0, "note": "marion county FL — Ocala metro/rural mix", "honesty_marker": "INFERRED"},
        "distress_property": {"score": 5.0, "note": f'{row.get("sale_type", "tax_deed")} distress', "honesty_marker": "INFERRED"},
        "distress_owner": {"score": 6.5, "note": "judicial/tax-deed action filed", "honesty_marker": "INFERRED"},
        "cma_distressed": {"value": round(arv * 0.85, 2), "note": "distressed comp arm", "honesty_marker": "INFERRED"},
        "cma_resale": {
            "value": round(arv, 2),
            "note": note,
            "honesty_marker": "VERIFIED" if verified else "INFERRED",
        },
        "model": "shapira_v14",
    }
    assert REQUIRED_KEYS.issubset(factors.keys())

    return {
        "case_number": row["case_number"],
        "county_slug": "marion",
        "parcel_id": row.get("parcel_id") or None,
        "address": row.get("property_address"),
        "auction_date": row.get("auction_date"),
        "arv": round(arv, 2),
        "repairs": round(repairs, 2),
        "max_bid": round(max(max_bid, 0), 2),
        "bid_judgment_ratio": round(ratio, 4),
        "ml_score": ml_score,
        "factors": factors,
        "recommendation": "BID" if max_bid > 1000 else "SKIP",
        "confidence": 0.5,
        "arv_source": "assessed_value_marion_j_backfill_direct" if verified else "opening_bid_heuristic_or_absolute_floor_marion_j_backfill",
        "pipeline_version": "marion_j_backfill_run3713_continuation",
    }, verified


def main():
    canon = get_all(
        "multi_county_auctions",
        {
            "select": "case_number,parcel_id,property_address,auction_date,opening_bid,judgment_amount,"
            "sale_type,market_value,assessed_value,data_source,tier1_authoritative,county",
            "county": "ilike.marion",
        },
    )
    canon = [
        r for r in canon
        if (r.get("data_source") or "") != "propertyonion" or (r.get("tier1_authoritative") or False)
    ]
    print(f"canon count: {len(canon)}")
    if len(canon) != 552:
        print(f"WARNING: canon count {len(canon)} != expected 552 -- proceeding on live data anyway")

    bd = get_all("bid_decisions", {"select": "case_number,arv,max_bid,ml_score,factors", "county_slug": "ilike.marion"})
    print(f"existing bid_decisions rows (any casing): {len(bd)}")

    def qualifies(r):
        if r.get("arv") is None or r.get("max_bid") is None or r.get("ml_score") is None:
            return False
        factors = r.get("factors")
        if not isinstance(factors, dict):
            return False
        return REQUIRED_KEYS.issubset(factors.keys())

    qualifying_cases = {r["case_number"] for r in bd if qualifies(r) and r.get("case_number")}
    print(f"qualifying distinct case_numbers: {len(qualifying_cases)}")

    residual = [r for r in canon if r.get("case_number") not in qualifying_cases]
    print(f"residual case_numbers needing a qualifying bid_decisions row: {len(residual)}")

    seen = set()
    targets = []
    for r in residual:
        cn = r.get("case_number")
        if not cn or cn in seen:
            continue
        seen.add(cn)
        targets.append(r)
    print(f"deduped targets: {len(targets)}")

    built = [build(r) for r in targets]
    batch = [b for b, _ in built]
    n_verified = sum(1 for _, v in built if v)
    n_floored = sum(1 for _, v in built if not v)
    print(f"verified (real value used directly): {n_verified}")
    print(f"floored/inferred (no real value, absolute floor or opening_bid heuristic): {n_floored}")

    if len(batch) == 0:
        print("no candidates -- nothing to insert")
        return

    total = 0
    for i in range(0, len(batch), 100):
        chunk = batch[i : i + 100]
        status, body = post("bid_decisions", chunk)
        print(f"chunk {i // 100}: status={status} n={len(chunk)}")
        if status >= 400:
            raise RuntimeError(f"insert failed status={status} body={body[:500]}")
        total += len(chunk)

    if total == 0 and len(batch) > 0:
        raise RuntimeError(f"FAIL-LOUD: had {len(batch)} candidate rows but wrote 0 -- investigate, do not silently no-op")

    print(f"TOTAL inserted: {total}")


if __name__ == "__main__":
    main()
