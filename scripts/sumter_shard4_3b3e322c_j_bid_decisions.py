#!/usr/bin/env python3
"""
sumter_shard4_3b3e322c_j_bid_decisions.py

Gold Standard shard-4 (dispatch 3b3e322c): sumter J fix -- bid_decisions rows
for the 5 case numbers newly parcel_id-linked this session (see companion
scripts/sumter_shard4_3b3e322c_e_mca_enrichment.py and migration
supabase/migrations/20260827_sumter_shard4_3b3e322c_ei_7row_zoning_link.sql).

METHODOLOGY (identical two-arm real-CMA pattern already shipped and PASSING
for sumter's other 24 rows -- see
scripts/gold_standard_shard3_b57474e3_sumter_eij_10row_enrich.py's docstring
for the full rationale, NOT rebuilt from scratch here):
  For each of the 5 parcels, pulled REAL sold comps from fl_parcels (co_no=70,
  same zip + DOR use code, sale_yr1>=2022, sale_prc1>1000), deduplicated by
  exact sale_prc1 (FL DOR repeats the same bulk-deed price across every parcel
  in a multi-parcel sale -- confirmed again live this session: raw_n up to
  1000 collapsing to 160-301 unique prices). ARV = p75 of deduplicated comps,
  cma_distressed = p25, cma_resale = p75. All 5 parcels are DOR_UC=001
  (single-family residential, improved) with n>=160 comps each -- comfortably
  above the n>=3 real-comps threshold, no assessed-value-proxy fallback
  needed for any of the 5.

  Judgment amounts sourced from the SAME sumterclerk.com foreclosure-sales
  page used for the address enrichment (live 2026-08-27), matched by
  case_number.

WRITES PERFORMED: 5 POST rows to bid_decisions (arv, repairs, max_bid,
ml_score, factors with the 5 required keys, confidence, recommendation).

SCOPE: ONLY the 5 case numbers already confirmed parcel-linked this session.
2026-CA-000074, 2026-CA-000090, 2026-CA-000129 are NOT touched here -- they
have no confirmed parcel_id this session (see companion script's docstring),
and generating a J row for them would require inventing an ARV/comps input
with no real parcel to anchor it to. Per BLANK > WRONG, not done.
"""
import json
import os
import re
import sys

import requests

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

# case_number -> parcel/dor_uc/zip/value/owner/judgment, VERIFIED live 2026-08-27
J_ROWS = {
    "2026-CA-000099": {
        "parcel": "D03J031", "dor_uc": "001", "zip": "32162", "jv": 255970, "av_sd": 255970,
        "lnd": 3948, "own": "CARTLEDGE MARY ANN", "sale_type": "foreclosure",
        "judgment": 386107.53, "address": "1920 PEACHTREE AVE", "auction_date": "2026-09-17",
    },
    "2025-CA-000475": {
        "parcel": "D29C059", "dor_uc": "001", "zip": "34785", "jv": 200300, "av_sd": 164510,
        "lnd": 21826, "own": "WILKINSON LARRY LEE & NATASHA", "sale_type": "foreclosure",
        "judgment": 77976.60, "address": "4578 CR 116", "auction_date": "2026-10-01",
    },
    "2025-CA-000394": {
        "parcel": "G03C159", "dor_uc": "001", "zip": "32162", "jv": 304070, "av_sd": 203690,
        "lnd": 5460, "own": "BRAY WILLIAM HOMER JR (TTEE)", "sale_type": "foreclosure",
        "judgment": 455570.90, "address": "2768 PERSIMMON LOOP", "auction_date": "2026-10-01",
    },
    "2025-CA-000294": {
        "parcel": "D13K044", "dor_uc": "001", "zip": "32159", "jv": 253320, "av_sd": 253320,
        "lnd": 4136, "own": "TERRAMOCCIA SHERRY A & VELIO", "sale_type": "foreclosure",
        "judgment": 303774.94, "address": "624 NUEVO LEON LN", "auction_date": "2026-10-15",
    },
    "2025-CA-000515": {
        "parcel": "G04N163", "dor_uc": "001", "zip": "34785", "jv": 186750, "av_sd": 186380,
        "lnd": 2032, "own": "BOULET BRICE HENRY", "sale_type": "foreclosure",
        "judgment": 236118.49, "address": "5364 PINECONE CT", "auction_date": "2026-10-15",
    },
}


def percentile(vals, p):
    if not vals:
        return None
    vals = sorted(float(v) for v in vals if v is not None)
    n = len(vals)
    idx = (n - 1) * p / 100
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return vals[lo] + frac * (vals[hi] - vals[lo])


def get_comps_dedup(zip_, dor_uc, lnd_sqfoot=None):
    params = {
        "co_no": "eq.70",
        "phy_zipcd": f"eq.{zip_}",
        "dor_uc": f"eq.{dor_uc}",
        "sale_yr1": "gte.2022",
        "sale_prc1": "gt.1000",
        "select": "sale_prc1,lnd_sqfoot",
        "limit": 1000,
    }
    if lnd_sqfoot:
        lo = int(lnd_sqfoot * 0.4)
        hi = int(lnd_sqfoot * 2.5)
        params["lnd_sqfoot"] = f"gte.{lo}"
        params["and"] = f"(lnd_sqfoot.lte.{hi})"
    r = requests.get(f"{SB}/rest/v1/fl_parcels", headers=H, params=params, timeout=30)
    r.raise_for_status()
    rows = r.json()
    seen, dedup = set(), []
    for row in rows:
        p = row.get("sale_prc1")
        if p and p not in seen:
            seen.add(p)
            dedup.append(p)
    return dedup, len(rows)


def repairs_tier(arv):
    if arv < 100_000:
        return 25_000
    elif arv < 250_000:
        return 20_000
    elif arv < 500_000:
        return 15_000
    return 12_000


def shapira_max_bid(arv, repairs):
    profit_floor = min(25000.0, 0.15 * arv)
    return max(0.0, (arv * 0.70) - repairs - profit_floor)


def compute_j_row(case, r):
    is_vacant = r["dor_uc"] in ("000", "076")
    prices, raw_n = get_comps_dedup(r["zip"], r["dor_uc"], lnd_sqfoot=r["lnd"] if is_vacant else None)
    n = len(prices)

    if n >= 3:
        p75, p25 = percentile(prices, 75), percentile(prices, 25)
        arv, cma_distressed, cma_resale = round(p75, 2), round(p25, 2), round(p75, 2)
        method = "fl_parcels_comps_p75_sizebound0.4-2.5x_dedup_bulk" if is_vacant else "fl_parcels_comps_p75_zip_dor_uc_dedup_bulk"
        arv_source = f"{method}_n{n}"
        note_common = f"{n} real deduplicated sold comps (fl_parcels, co_no=70, same zip+DOR use code" + \
            (", land sqft within 0.4x-2.5x tolerance" if is_vacant else "") + \
            ", sold since 2022, bulk/subdivision-deed duplicate prices collapsed)"
        honesty = "INFERRED"
    else:
        arv = max(r["jv"], r["av_sd"])
        cma_distressed, cma_resale = round(arv * 0.87, 2), round(arv * 1.12, 2)
        arv_source = f"assessed_value_proxy_n{n}_comps_insufficient"
        note_common = "assessed_value proxy (no qualifying comps found for this use code/zip)"
        honesty = "INFERRED_NO_COMPS"

    repairs = repairs_tier(arv)
    max_bid = round(shapira_max_bid(arv, repairs), 2)

    owner = r["own"].upper()
    is_estate = bool(re.search(r"\b(ESTATE|TRUST|HEIRS?|DECEASED|DECD)\b", owner))
    is_entity = bool(re.search(r"\b(LLC|INC|CORP|LP|HOLDING|PROPERTIES|REALTY|TRUSTEES)\b", owner))
    is_multi_owner = "&" in owner or " AND " in owner
    if is_estate:
        distress_owner = 0.62
    elif is_entity:
        distress_owner = 0.30
    elif is_multi_owner:
        distress_owner = 0.48
    else:
        distress_owner = 0.50

    distress_property = 0.55 if is_vacant else 0.40

    debt = r.get("judgment") or r.get("opening_bid") or 0
    av = max(r["jv"], r["av_sd"]) or 1
    debt_ratio = debt / av
    if debt_ratio > 2.0:
        distress_location = 0.55
    elif debt_ratio > 1.0:
        distress_location = 0.42
    elif debt_ratio > 0.3:
        distress_location = 0.30
    else:
        distress_location = 0.20

    spread = (cma_resale - cma_distressed) / cma_resale if cma_resale else 0.3
    ml_score = round(min(0.95, max(0.15, (distress_owner + distress_property + distress_location) / 3 * (1 - spread * 0.3) + 0.15)), 4)
    confidence = round(0.5 + (n / 500) * 0.3, 4) if n >= 3 else 0.35

    opening_bid = r.get("opening_bid")
    bid_ratio = round(min(max_bid / opening_bid, 9.99), 4) if opening_bid else None
    recommendation = "BID" if (opening_bid and max_bid > opening_bid) else ("REVIEW" if not opening_bid else "PASS")

    return {
        "case_number": case,
        "county_slug": "sumter",
        "parcel_id": r["parcel"],
        "address": r.get("address"),
        "auction_date": r.get("auction_date"),
        "arv": round(arv, 2),
        "repairs": repairs,
        "final_judgment": round(debt, 2) if debt else None,
        "max_bid": max_bid,
        "bid_judgment_ratio": bid_ratio,
        "recommendation": recommendation,
        "confidence": confidence,
        "ml_score": ml_score,
        "factors": {
            "distress_location": distress_location,
            "distress_property": distress_property,
            "distress_owner": distress_owner,
            "cma_distressed": {"value": cma_distressed, "note": f"p25 percentile of {note_common}", "honesty_marker": honesty},
            "cma_resale": {"value": cma_resale, "note": f"p75 percentile of {note_common}", "honesty_marker": honesty},
        },
        "arv_source": arv_source,
        "pipeline_run_id": "GOLDSTANDARD-SHARD4-3b3e322c-SUMTER-J-v1",
        "pipeline_version": "sumter_shard4_3b3e322c_j_bid_decisions_v1",
    }


def insert_bid_decisions():
    rows = [compute_j_row(case, r) for case, r in J_ROWS.items()]
    resp = requests.post(f"{SB}/rest/v1/bid_decisions", headers=H, data=json.dumps(rows), timeout=60)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Fail-loud: parsed={len(rows)} inserted=0: {resp.status_code} {resp.text[:1000]}")
    inserted = resp.json()
    if len(inserted) != len(rows):
        raise RuntimeError(f"Fail-loud: parsed={len(rows)} inserted={len(inserted)}")
    for r in inserted:
        print(f"J OK {r['case_number']}: arv={r['arv']} max_bid={r['max_bid']} ml_score={r['ml_score']}")
    print(f"bid_decisions: {len(inserted)}/{len(rows)} rows inserted.")


if __name__ == "__main__":
    insert_bid_decisions()
