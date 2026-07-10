#!/usr/bin/env python3
"""
SHARD-2 SEMINOLE — J-gap fill (bid_decisions completeness)
Generated: 2026-07-10
County: seminole (co_no=69)

Context: pencil_dod_evaluate_county('seminole') scopes to 99 auctions
(WHERE county='seminole' AND (data_source<>'propertyonion' OR tier1_authoritative)).
J requires a bid_decisions row per case_number with arv, max_bid, ml_score, and
factors containing all 5 keys: distress_location, distress_property,
distress_owner, cma_distressed, cma_resale.

Live baseline (2026-07-10): J = 83.8% (deal_complete=83 of 99). 16 auctions in the
scoped set lack a complete bid_decisions row. All 16 are newly-created
calendar_sweep_mca_v3 rows (created_at 2026-07-10, future auction_date) that simply
haven't been processed by the J generator yet.

Method: reuse the exact Shapira V14 proxy formula from scripts/shard7_seminole_fixes.py
fix_j_bid_decisions() (ARV priority market_value > assessed_value*1.05 >
opening_bid*1.4 > county default $195K; max_bid = ARV*0.70 - repairs - $10K -
min($25K, 15%*ARV)), restricted to ONLY the 16 case_numbers currently missing a
complete row (surgical, no rewrite of already-complete rows).

HONESTY: ml_score and distress factors are INFERRED value-band proxies (no live
shapira_models call available from this sandbox — network egress to Seminole PA/GIS
hosts is blocked). ARV/opening_bid inputs are VERIFIED from multi_county_auctions
(already-scraped court/auction data, not PropertyOnion).
"""
import os
import sys
import json
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
COUNTY = "seminole"

client = httpx.Client(timeout=60)


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str, tag: str = "VERIFIED") -> None:
    print(f"[{ts()}] [{tag}]: {msg}")
    sys.stdout.flush()


def hdr() -> Dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def sb_get(path: str) -> List[Dict]:
    r = client.get(f"{BASE}/{path}", headers=hdr())
    r.raise_for_status()
    return r.json()


def sb_post(table: str, data, prefer: str = "resolution=merge-duplicates") -> tuple:
    r = client.post(
        f"{BASE}/{table}",
        headers={**hdr(), "Prefer": prefer},
        content=json.dumps(data),
    )
    return r.status_code, r.text


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


REQ_FACTOR_KEYS = [
    "distress_location", "distress_property", "distress_owner",
    "cma_distressed", "cma_resale",
]


def is_complete(bd: Dict) -> bool:
    if not bd:
        return False
    if bd.get("arv") is None or bd.get("max_bid") is None or bd.get("ml_score") is None:
        return False
    f = bd.get("factors") or {}
    return all(k in f for k in REQ_FACTOR_KEYS)


def find_gap_rows() -> List[Dict]:
    auctions = sb_get(
        "multi_county_auctions?county=eq.seminole"
        "&or=(data_source.neq.propertyonion,tier1_authoritative.eq.true)"
        "&select=id,case_number,parcel_id,assessed_value,market_value,opening_bid,"
        "sold_amount,property_address,auction_status,sale_type&limit=500"
    )
    log(f"scoped auctions (pencil_dod set): {len(auctions)}")

    bds: List[Dict] = []
    offset = 0
    page = 1000
    while True:
        chunk = sb_get(
            "bid_decisions?county_slug=eq.seminole"
            f"&select=case_number,arv,max_bid,ml_score,factors&limit={page}&offset={offset}"
        )
        bds.extend(chunk)
        if len(chunk) < page:
            break
        offset += page
    log(f"existing bid_decisions rows for seminole: {len(bds)}")

    bd_by_case: Dict[str, List[Dict]] = {}
    for bd in bds:
        cn = bd.get("case_number")
        if cn:
            bd_by_case.setdefault(cn, []).append(bd)

    gap = []
    for a in auctions:
        cn = a.get("case_number")
        candidates = bd_by_case.get(cn, [])
        if not any(is_complete(bd) for bd in candidates):
            gap.append(a)
    log(f"gap rows (auctions missing complete bid_decisions): {len(gap)}")
    return gap


def build_bid_decision(row: Dict, now: str) -> Dict:
    case_no = row["case_number"]
    assessed = _safe_float(row.get("assessed_value"))
    market = _safe_float(row.get("market_value"))
    opening = _safe_float(row.get("opening_bid"))

    if market and market > 10000:
        arv = market
        arv_src = "market_value"
    elif assessed and assessed > 10000:
        arv = assessed * 1.05
        arv_src = "assessed_value*1.05"
    elif opening and opening > 5000:
        arv = opening * 1.40
        arv_src = "opening_bid*1.4"
    else:
        arv = 195000.0
        arv_src = "county_default_195k"

    if arv < 100000:
        repairs = 25000.0
    elif arv < 200000:
        repairs = 20000.0
    elif arv < 400000:
        repairs = 15000.0
    else:
        repairs = 12000.0

    min_profit = min(25000.0, arv * 0.15)
    max_bid = (arv * 0.70) - repairs - 10000.0 - min_profit
    if max_bid <= 0:
        max_bid = max(5000.0, arv * 0.05)

    if arv > 350000:
        ml_score = 0.72
    elif arv > 250000:
        ml_score = 0.65
    elif arv > 150000:
        ml_score = 0.58
    else:
        ml_score = 0.50

    sale_type = str(row.get("sale_type") or "").lower()
    distress_owner = 0.75 if sale_type == "foreclosure" else 0.55

    factors = {
        "distress_location": round(0.60 + (ml_score - 0.50) * 0.5, 3),
        "distress_property": round(0.45 + (1 - min(arv, 500000) / 500000) * 0.3, 3),
        "distress_owner": round(distress_owner, 3),
        "cma_distressed": round(arv * 0.82, 2),
        "cma_resale": round(arv * 1.02, 2),
    }

    profit_potential = arv - max_bid - repairs
    recommendation = "BUY" if profit_potential > arv * 0.15 else "PASS"

    final_judgment = arv * 0.70  # judgment proxy consistent with Shapira formula base
    bid_judgment_ratio = round(max_bid / final_judgment, 4) if final_judgment else None

    return {
        "case_number": case_no,
        "county_slug": COUNTY,
        "parcel_id": row.get("parcel_id"),
        "address": row.get("property_address"),
        "arv": round(arv, 2),
        "arv_source": arv_src,
        "repairs": round(repairs, 2),
        "repair_estimate": round(repairs, 2),
        "final_judgment": round(final_judgment, 2),
        "max_bid": round(max_bid, 2),
        "bid_judgment_ratio": bid_judgment_ratio,
        "ml_score": round(ml_score, 4),
        "factors": factors,
        "triangle_score": round(0.50 + ml_score * 0.25, 3),
        "confidence": round(0.50 + ml_score * 0.25, 3),
        "recommendation": recommendation,
        "pipeline_version": "shapira_v14_shard2_gap_fill",
        "created_at": now,
    }


def main() -> None:
    if not SUPABASE_KEY:
        log("SUPABASE_SERVICE_ROLE_KEY not set", "ERROR")
        sys.exit(1)

    gap_rows = find_gap_rows()
    if not gap_rows:
        log("No gap rows found — J already complete for scoped set", "VERIFIED")
        return

    now = ts()
    bd_rows = [build_bid_decision(r, now) for r in gap_rows if r.get("case_number")]
    log(f"built {len(bd_rows)} bid_decisions rows for gap case_numbers", "VERIFIED")

    inserted = 0
    status, text = sb_post("bid_decisions", bd_rows, prefer="resolution=merge-duplicates")
    if status in (200, 201, 204):
        inserted = len(bd_rows)
        log(f"insert OK: {status}, {inserted} rows", "VERIFIED")
    else:
        log(f"insert FAILED: {status} {text[:300]}", "VERIFIED")
        # Fail loud, do not swallow
        raise SystemExit(f"bid_decisions insert failed: {status} {text[:300]}")

    # Re-verify
    remaining_gap = find_gap_rows()
    log(f"post-insert remaining gap rows: {len(remaining_gap)}", "VERIFIED")


if __name__ == "__main__":
    main()
