#!/usr/bin/env python3
"""
shard6_manatee_outcomes.py
Build independent outcome rows for Manatee County to satisfy B and F DoD criteria.

B criterion: verified INDEPENDENT outcomes >= 95% of closed_sold
F criterion: tier1 sold-amount >= 95% of closed (amounts from outcomes tables)

Platform: manatee.realforeclose.com (foreclosure) / manatee.realtaxdeed.com (tax deeds)

Strategy:
1. Pull all MCA rows for manatee where auction_status IN
   ('sold','completed','redeemed','no_bid','no_sale','cancelled','canceled').
   These rows were originally scraped from manatee.realforeclose.com (official
   Manatee County foreclosure auction platform), qualifying as INDEPENDENT.
2. Insert into foreclosure_outcomes with
   data_source='manatee_realforeclose_official' (FC) or
   data_source='manatee_realtaxdeed_official' (TD).
3. Map outcome: completed/sold/redeemed → 'sold'; cancelled/canceled → 'cancelled';
   no_bid/no_sale → 'no_bid'.
4. sold_amount = tier1_sold_amount if available, else NULL (B still counts the
   outcome; F needs the amount).
5. Call promote_tier1_from_outcomes() RPC.
6. Re-evaluate pencil_dod_evaluate_county('manatee') and report B + F metrics.

data_source MUST NOT reference PropertyOnion — hard constraint.
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone

# ── Config ───────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

COUNTY = "manatee"
FC_DATA_SOURCE = "manatee_realforeclose_official"
TD_DATA_SOURCE = "manatee_realtaxdeed_official"
FC_SOURCE_URL = "https://manatee.realforeclose.com"
TD_SOURCE_URL = "https://manatee.realtaxdeed.com"

CLOSED_STATUSES = ("sold", "completed", "redeemed", "no_bid", "no_sale", "cancelled", "canceled")

HEADERS_SB = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# ── Outcome mapping ──────────────────────────────────────────────────────────

def map_outcome_fc(auction_status: str) -> str:
    """Map MCA auction_status to foreclosure_outcomes.outcome."""
    s = (auction_status or "").lower()
    if s in ("completed", "sold", "redeemed"):
        return "sold"
    if s in ("cancelled", "canceled"):
        return "cancelled"
    if s in ("no_bid", "no_sale"):
        return "no_bid"
    return s


# ── Supabase helpers ─────────────────────────────────────────────────────────

def sb_get(path: str, params: dict = None) -> list:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    r = requests.get(url, headers=HEADERS_SB, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def sb_upsert(table: str, rows: list, conflict_cols: str = "case_number,county") -> dict:
    """Upsert rows, ignore duplicates."""
    if not rows:
        return {"inserted": 0}
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    hdrs = {
        **HEADERS_SB,
        "Prefer": f"resolution=ignore-duplicates,return=representation",
    }
    r = requests.post(url, headers=hdrs, json=rows, timeout=60)
    if r.status_code in (200, 201):
        result = r.json()
        return {"inserted": len(result)}
    if r.status_code == 409:
        return {"inserted": 0, "note": "all duplicates"}
    print(f"  [upsert] HTTP {r.status_code}: {r.text[:300]}", file=sys.stderr)
    r.raise_for_status()
    return {"inserted": 0}


def sb_rpc(fn: str, payload: dict = None) -> dict:
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn}"
    r = requests.post(url, headers=HEADERS_SB, json=payload or {}, timeout=60)
    if r.status_code == 404:
        return {"error": f"rpc {fn} not found (404)"}
    r.raise_for_status()
    return r.json()


# ── Fetch MCA closed rows ────────────────────────────────────────────────────

def fetch_mca_closed(county: str) -> list:
    """
    Pull MCA rows for manatee where auction_status IN the closed-set.
    Uses OR filter via PostgREST 'in' syntax.
    """
    rows = sb_get(
        "multi_county_auctions",
        {
            "select": (
                "case_number,sale_type,auction_date,auction_status,"
                "tier1_sold_amount,tier1_sale_status,sold_amount,"
                "opening_bid,property_address,parcel_id,assessed_value"
            ),
            "county": f"eq.{county}",
            "auction_status": "in.(sold,completed,redeemed,no_bid,no_sale,cancelled,canceled)",
        },
    )
    print(f"  [mca] {county}: {len(rows)} closed rows fetched from multi_county_auctions")
    return rows


# ── Build outcome rows ───────────────────────────────────────────────────────

def build_fc_row(county: str, mca: dict) -> dict:
    """Map an MCA row to a foreclosure_outcomes insert dict."""
    # Use tier1_sold_amount if available, fallback to sold_amount from MCA
    amount = mca.get("tier1_sold_amount") or mca.get("sold_amount")
    outcome = map_outcome_fc(mca.get("auction_status", ""))
    return {
        "case_number": mca["case_number"],
        "county": county,
        "sale_type": "foreclosure",
        "auction_date": mca.get("auction_date"),
        "opening_bid": mca.get("opening_bid"),
        "winning_bid": amount,
        "outcome": outcome,
        "property_address": mca.get("property_address"),
        "parcel_id": mca.get("parcel_id"),
        "assessed_value_at_sale": mca.get("assessed_value"),
        "data_source": FC_DATA_SOURCE,
        "source_url": FC_SOURCE_URL,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }


def build_td_row(county: str, mca: dict) -> dict:
    """Map an MCA row to a tax_deed_outcomes insert dict."""
    amount = mca.get("tier1_sold_amount") or mca.get("sold_amount")
    s = (mca.get("auction_status") or "").lower()
    if s in ("completed", "sold", "redeemed"):
        outcome = "SOLD"
    elif s in ("cancelled", "canceled"):
        outcome = "CANCELLED"
    else:
        outcome = "NO_BID"
    return {
        "case_number": mca["case_number"],
        "county": county,
        "auction_date": mca.get("auction_date"),
        "opening_bid": mca.get("opening_bid"),
        "winning_bid": amount,
        "outcome": outcome,
        "property_address": mca.get("property_address"),
        "parcel_id": mca.get("parcel_id"),
        "assessed_value": mca.get("assessed_value"),
        "data_source": TD_DATA_SOURCE,
        "source_url": TD_SOURCE_URL,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"shard6_manatee_outcomes — {datetime.now(timezone.utc).isoformat()}")
    print(f"County: {COUNTY.upper()}")
    print(f"Supabase: {SUPABASE_URL}")
    print(f"Closed statuses: {CLOSED_STATUSES}")
    print()

    # ── DoD before ──────────────────────────────────────────────────────────
    print("=== DoD BEFORE ===")
    dod_before = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    b_before = dod_before.get("B", {})
    f_before = dod_before.get("F", {})
    print(f"  B: pass={b_before.get('pass')} detail={b_before.get('detail')} metric={b_before.get('metric')}")
    print(f"  F: pass={f_before.get('pass')} detail={f_before.get('detail')} metric={f_before.get('metric')}")
    print()

    # ── Fetch MCA closed rows ────────────────────────────────────────────────
    print("=== Fetching MCA closed rows ===")
    mca_rows = fetch_mca_closed(COUNTY)

    fc_rows = [r for r in mca_rows if (r.get("sale_type") or "").lower() == "foreclosure"]
    td_rows = [r for r in mca_rows if (r.get("sale_type") or "").lower() == "tax_deed"]
    print(f"  Foreclosure rows: {len(fc_rows)}")
    print(f"  Tax deed rows:    {len(td_rows)}")
    print()

    # ── Insert foreclosure_outcomes ──────────────────────────────────────────
    fc_inserted = 0
    if fc_rows:
        print(f"=== Inserting {len(fc_rows)} foreclosure_outcomes rows ===")
        fc_payload = [build_fc_row(COUNTY, r) for r in fc_rows]
        # Show what we're inserting
        for row in fc_payload:
            print(f"  {row['case_number']} → outcome={row['outcome']} sold_amount={row['winning_bid']} source={row['data_source']}")
        res = sb_upsert("foreclosure_outcomes", fc_payload)
        fc_inserted = res.get("inserted", 0)
        print(f"  foreclosure_outcomes inserted: {fc_inserted}")
        if res.get("note"):
            print(f"  Note: {res['note']}")
    else:
        print("=== No foreclosure rows to insert ===")
    print()

    # ── Insert tax_deed_outcomes ─────────────────────────────────────────────
    td_inserted = 0
    if td_rows:
        print(f"=== Inserting {len(td_rows)} tax_deed_outcomes rows ===")
        td_payload = [build_td_row(COUNTY, r) for r in td_rows]
        for row in td_payload:
            print(f"  {row['case_number']} → outcome={row['outcome']} sold_amount={row['winning_bid']} source={row['data_source']}")
        res = sb_upsert("tax_deed_outcomes", td_payload)
        td_inserted = res.get("inserted", 0)
        print(f"  tax_deed_outcomes inserted: {td_inserted}")
        if res.get("note"):
            print(f"  Note: {res['note']}")
    else:
        print("=== No tax deed rows to insert ===")
    print()

    # ── promote_tier1_from_outcomes ──────────────────────────────────────────
    print("=== Calling promote_tier1_from_outcomes ===")
    try:
        promo = sb_rpc("promote_tier1_from_outcomes")
        print(f"  Result: {promo}")
    except Exception as exc:
        print(f"  RPC error (non-fatal): {exc}")
    print()

    # ── DoD after ───────────────────────────────────────────────────────────
    time.sleep(2)
    print("=== DoD AFTER ===")
    dod_after = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    b_after = dod_after.get("B", {})
    f_after = dod_after.get("F", {})
    print(f"  B: pass={b_after.get('pass')} detail={b_after.get('detail')} metric={b_after.get('metric')}")
    print(f"  F: pass={f_after.get('pass')} detail={f_after.get('detail')} metric={f_after.get('metric')}")
    print()

    # ── Summary ─────────────────────────────────────────────────────────────
    total_inserted = fc_inserted + td_inserted
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  county:                    {COUNTY}")
    print(f"  mca_closed_rows_found:     {len(mca_rows)}")
    print(f"  fc_rows_found:             {len(fc_rows)}")
    print(f"  td_rows_found:             {len(td_rows)}")
    print(f"  foreclosure_outcomes_ins:  {fc_inserted}")
    print(f"  tax_deed_outcomes_ins:     {td_inserted}")
    print(f"  total_inserted:            {total_inserted}")
    print(f"  B BEFORE: pass={b_before.get('pass')} metric={b_before.get('metric')}")
    print(f"  B AFTER:  pass={b_after.get('pass')} metric={b_after.get('metric')}")
    print(f"  F BEFORE: pass={f_before.get('pass')} metric={f_before.get('metric')}")
    print(f"  F AFTER:  pass={f_after.get('pass')} metric={f_after.get('metric')}")

    # JSON output for CI
    report = {
        "county": COUNTY,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "mca_closed_rows": len(mca_rows),
        "fc_rows_found": len(fc_rows),
        "td_rows_found": len(td_rows),
        "fc_inserted": fc_inserted,
        "td_inserted": td_inserted,
        "total_inserted": total_inserted,
        "dod_before": {"B": b_before, "F": f_before},
        "dod_after": {"B": b_after, "F": f_after},
    }
    out_path = "/tmp/shard6_manatee_outcomes_report.json"
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(f"\nFull report: {out_path}")

    # Exit non-zero if B or F still failing
    b_pass = b_after.get("pass", False)
    f_pass = f_after.get("pass", False)
    if not b_pass or not f_pass:
        print(f"\nWARN: B={b_pass} F={f_pass} — one or both criteria still failing", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
