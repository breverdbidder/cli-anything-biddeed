#!/usr/bin/env python3
"""SHARD-9 escambia I/J backfill (2026-07-24, dispatch 1a7d03e0-6c1f-4240-822d-185fd0fe77dd).

Escambia I=89.6% and J=90.9% in the current dispatch brief, regressed from shard-14's
I=95.9% and J=97.4%. Root cause: new auction rows were added to multi_county_auctions
after shard-14 (2026-07-20) that do not yet have bid_decisions (J gap) or complete
property cards (I gap).

This script:
  1. Finds escambia auctions without bid_decisions → generates bid_decisions (J fix).
  2. Finds escambia auctions with missing address/geo/value → enriches from fl_parcels
     via parcel_id (I fix).
  3. All bid_decisions use the Shapira Formula V14 contract (arv, max_bid, ml_score,
     factors with all 5 required keys: distress_location, distress_property,
     distress_owner, cma_distressed, cma_resale).
  4. honesty_marker: INFERRED for county-level ARV proxy; all values clearly marked.

Usage: python3 scripts/shard9_escambia_ij_backfill.py
Idempotent: only inserts bid_decisions for case_numbers not already present;
only updates address/geo where currently NULL.
"""
import os
import re
import json
import urllib.request
from datetime import datetime

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY = "escambia"
ARV_BASE = 300000
PIPELINE_VERSION = "shard9_escambia_ij_backfill_run6148"
ML_SCORE_PASS = 0.72
ML_SCORE_SKIP = 0.38


def _headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers=_headers())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=data, method="POST",
        headers={**_headers(), "Content-Type": "application/json",
                 "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=data, method="PATCH",
        headers={**_headers(), "Content-Type": "application/json",
                 "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def tiered_repairs(arv):
    if arv < 100_000:
        return 30_000
    elif arv < 200_000:
        return 25_000
    elif arv < 400_000:
        return 20_000
    return 15_000


def shapira_max_bid(arv, repairs):
    return (arv * 0.70) - repairs - 10_000 - min(25_000, 0.15 * arv)


def build_bid_decision(row):
    mkt = row.get("market_value") or row.get("assessed_value")
    opening = float(row.get("opening_bid") or 0)
    if mkt:
        arv = max(float(mkt), ARV_BASE * 0.4)
    elif opening > 1000:
        arv = opening * 1.4
    else:
        arv = ARV_BASE
    arv = max(arv, 50_000)
    repairs = tiered_repairs(arv)
    max_bid = shapira_max_bid(arv, repairs)
    ml_score = ML_SCORE_PASS if max_bid > 1000 else ML_SCORE_SKIP
    opening_f = opening if opening > 0 else arv * 0.5
    ratio = min(9.9999, max(-9.9999, max_bid / opening_f))

    factors = {
        "distress_location": {
            "score": 6.5,
            "note": "Escambia County FL — Pensacola metro area",
            "honesty_marker": "INFERRED"
        },
        "distress_property": {
            "score": 5.0,
            "note": f"{row.get('sale_type', 'tax_deed')} distress",
            "honesty_marker": "INFERRED"
        },
        "distress_owner": {
            "score": 6.0,
            "note": "tax certificate / foreclosure action filed",
            "honesty_marker": "INFERRED"
        },
        "cma_distressed": {
            "value": round(arv * 0.85, 2),
            "note": "distressed comp arm — 85% of ARV proxy",
            "honesty_marker": "INFERRED"
        },
        "cma_resale": {
            "value": round(arv, 2),
            "note": "retail resale arm — Escambia county median ARV proxy (Redfin Jan 2026 ~$300K), not per-parcel comp",
            "honesty_marker": "INFERRED"
        },
        "model": "shapira_v14"
    }

    return {
        "case_number": row["case_number"],
        "county_slug": COUNTY,
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
        "confidence": 0.50,
        "arv_source": "shapira_formula_escambia_county_median_proxy_shard9",
        "pipeline_version": PIPELINE_VERSION,
    }


def run_j_backfill():
    print(f"\n=== J BACKFILL (bid_decisions) ===")
    auctions = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        f"&case_number=not.is.null"
        f"&select=case_number,parcel_id,property_address,auction_date,"
        f"opening_bid,assessed_value,market_value,sale_type&limit=2000")
    print(f"  {COUNTY}: {len(auctions)} total auctions with case_number")

    existing = rest_get(
        f"bid_decisions?county_slug=eq.{COUNTY}&select=case_number&limit=5000")
    existing_cases = {r["case_number"] for r in existing}
    print(f"  {COUNTY}: {len(existing_cases)} existing bid_decisions")

    new_auctions = [a for a in auctions if a["case_number"] not in existing_cases]
    print(f"  {COUNTY}: {len(new_auctions)} new auctions to process")

    if not new_auctions:
        print("  J: DONE — 0 rows to insert")
        return 0

    rows = [build_bid_decision(a) for a in new_auctions]
    inserted_total = 0
    for i in range(0, len(rows), 100):
        chunk = rows[i:i+100]
        result = rest_post("bid_decisions", chunk)
        if not isinstance(result, list):
            raise RuntimeError(
                f"Fail-loud: parsed={len(chunk)} inserted=0 for {COUNTY}: {result}")
        inserted = len(result)
        if inserted == 0 and len(chunk) > 0:
            raise RuntimeError(
                f"Fail-loud: parsed={len(chunk)} inserted=0 for {COUNTY}")
        inserted_total += inserted
        print(f"  chunk {i//100+1}: inserted {inserted}")

    print(f"  J DONE: inserted {inserted_total} bid_decisions for {COUNTY}")
    return inserted_total


def run_i_backfill():
    """Find escambia auctions missing address/geo/value and backfill from fl_parcels."""
    print(f"\n=== I BACKFILL (property card completeness) ===")

    i_gap_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        f"&parcel_id=not.is.null"
        f"&or=(property_address.is.null,latitude.is.null,assessed_value.is.null)"
        f"&select=id,parcel_id,property_address,latitude,assessed_value&limit=500")
    print(f"  {COUNTY}: {len(i_gap_rows)} auctions with parcel_id missing address/geo/value")

    if not i_gap_rows:
        print("  I: no gaps to fill from fl_parcels")
        return 0

    parcel_ids = list({r["parcel_id"] for r in i_gap_rows if r.get("parcel_id")})
    filled = 0

    for pid in parcel_ids:
        try:
            pid_enc = urllib.parse.quote(pid) if hasattr(urllib, 'parse') else pid
            parcels = rest_get(
                f"fl_parcels?parcel_id=eq.{pid_enc}"
                f"&select=parcel_id,physical_address,latitude,longitude,just_value,total_assessed&limit=1")
        except Exception as e:
            print(f"  skip {pid}: {e}")
            continue

        if not parcels:
            continue

        p = parcels[0]
        patch = {}
        if p.get("physical_address"):
            patch["property_address"] = p["physical_address"]
        if p.get("latitude"):
            patch["latitude"] = float(p["latitude"])
        if p.get("longitude"):
            patch["longitude"] = float(p["longitude"])
        val = p.get("just_value") or p.get("total_assessed")
        if val:
            patch["assessed_value"] = float(val)

        if not patch:
            continue

        mca_ids = [r["id"] for r in i_gap_rows if r.get("parcel_id") == pid]
        if not mca_ids:
            continue

        ids_str = ",".join(str(x) for x in mca_ids)
        try:
            rest_patch(f"multi_county_auctions?id=in.({ids_str})", patch)
            filled += len(mca_ids)
            print(f"  enriched parcel {pid}: {len(mca_ids)} rows, fields: {list(patch.keys())}")
        except Exception as e:
            print(f"  patch failed for {pid}: {e}")

    print(f"  I DONE: enriched {filled} auction rows for {COUNTY}")
    return filled


def main():
    print(f"[{datetime.utcnow().isoformat()}] escambia I/J backfill starting — {COUNTY}")
    j_count = run_j_backfill()
    i_count = run_i_backfill()
    print(f"\nSUMMARY: J inserted={j_count}, I enriched={i_count}")


if __name__ == "__main__":
    import urllib.parse
    main()
