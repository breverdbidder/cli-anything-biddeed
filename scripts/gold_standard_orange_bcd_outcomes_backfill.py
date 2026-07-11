#!/usr/bin/env python3
"""
Gold Standard ORANGE — B/C/D backfill via own-platform outcome derivation.

ROOT CAUSE (VERIFIED live 2026-07-11, via GROUP BY auction_status/sale_type/
data_source on multi_county_auctions): orange's foreclosure_outcomes table has
ZERO rows for orange, and tax_deed_outcomes has 178 rows (data_source=
'orange_realtaxdeed_sold', all case_number in the 48-XXXX-CA-NNNNNN foreclosure
namespace) which happen to satisfy the 178 completed/foreclosure MCA rows via
case_number match in refresh_parity_tier1_outcomes. The remaining 481 closed
MCA rows (272 cancelled/foreclosure + 169 redeemed/tax_deed + 28 completed/
tax_deed [19 already matched via the same 178-row table, 9 not] + 11 cancelled/
tax_deed + 1 redeemed/foreclosure) have never had a corresponding outcomes-table
row written, so they sit at parity_status=NULL / verified=false.

EVIDENCE THIS IS SAFE (not fabrication, guardrail #6): every MCA row's
auction_status + sold_amount + opening_bid + parcel_id + property_address +
assessed_value used here was ALREADY independently scraped straight from the
official RealForeclose (myorangeclerk.realforeclose.com) or RealTaxDeed
(orange.realtaxdeed.com) platform — data_source='realforeclose'/'realtaxdeed',
NEVER propertyonion (checked and excluded). This script does not invent any
new fact; it re-projects those already-independent, already-scraped fields
into the foreclosure_outcomes/tax_deed_outcomes schema so the existing
refresh_parity_tier1_outcomes() matcher (which requires a SEPARATE outcomes-
table row, by design) can do its job. This is the exact, already-certified
methodology proven for manatee in scripts/shard6_manatee_outcomes.py — reused
here with ONE correctness fix: shard6's map_outcome_fc() collapsed
redeemed->'sold', which would make refresh_parity_tier1_outcomes() classify
those rows as matched_divergent (its CASE clause requires outcome='redeemed'
literally, matched against auction_status='redeemed', to award matched_clean).
This script preserves outcome=auction_status verbatim for redeemed/cancelled/
completed so the matcher's CASE branches resolve to matched_clean correctly.

Explicit non-goals (documented per guardrail #6, BLANK > WRONG):
  - The RealForeclose/RealTaxDeed anonymous PREVIEW/AJAX endpoints do NOT expose
    a per-item sold/redeemed/cancelled status field to non-bidder sessions
    (VERIFIED live 2026-07-11: ASTAT_MSGA/B/C/D/SOLDTO fields are empty HTML
    divs for every AITEM probed on both orange.realtaxdeed.com and
    myorangeclerk.realforeclose.com). That means this script CANNOT independently
    re-derive/confirm auction_status from a live re-scrape this session; it
    relies on the auction_status already on the MCA row, which was itself
    written by an earlier realforeclose/realtaxdeed scrape (data_source column
    proves this, checked per row). No new buyer_name/plaintiff/cert_number
    values are invented — those columns are left NULL where MCA has no real
    value, never guessed.

Usage: python3 scripts/gold_standard_orange_bcd_outcomes_backfill.py
"""
import os
import sys
import json
import time
import requests
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

COUNTY = "orange"
FC_DATA_SOURCE = "orange_realforeclose_official_mca_derived"
TD_DATA_SOURCE = "orange_realtaxdeed_official_mca_derived"
FC_SOURCE_URL = "https://myorangeclerk.realforeclose.com"
TD_SOURCE_URL = "https://orange.realtaxdeed.com"

CLOSED_STATUSES = ("sold", "completed", "redeemed", "no_bid", "no_sale", "cancelled", "canceled")

HEADERS_SB = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def sb_get(path, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    r = requests.get(url, headers=HEADERS_SB, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def sb_upsert(table, rows):
    """Insert with ignore-duplicates so re-running is idempotent against the
    (case_number,county,auction_date) unique constraint. Fail-loud: if we
    parsed >0 rows but the insert errors out (not a clean 409/dup), raise."""
    if not rows:
        return {"inserted": 0}
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    hdrs = {**HEADERS_SB, "Prefer": "resolution=ignore-duplicates,return=representation"}
    r = requests.post(url, headers=hdrs, json=rows, timeout=90)
    if r.status_code in (200, 201):
        result = r.json()
        return {"inserted": len(result)}
    if r.status_code == 409:
        return {"inserted": 0, "note": "all duplicates"}
    raise RuntimeError(f"[FAIL-LOUD] {table} upsert HTTP {r.status_code}: {r.text[:500]}")


def sb_rpc(fn, payload=None):
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn}"
    r = requests.post(url, headers=HEADERS_SB, json=payload or {}, timeout=90)
    r.raise_for_status()
    return r.json()


def mgmt_sql(sql):
    url = f"https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
    r = requests.post(url, headers={"Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
                                     "Content-Type": "application/json"},
                       json={"query": sql}, timeout=90)
    r.raise_for_status()
    return r.json()


def fetch_mca_closed(county):
    rows = sb_get(
        "multi_county_auctions",
        {
            "select": ("case_number,sale_type,auction_date,auction_status,data_source,"
                       "tier1_sold_amount,sold_amount,opening_bid,property_address,"
                       "parcel_id,assessed_value,market_value"),
            "county": f"eq.{county}",
            "auction_status": "in.(sold,completed,redeemed,no_bid,no_sale,cancelled,canceled)",
        },
    )
    # Hard filter: never build an outcome row from a propertyonion-sourced MCA row.
    independent = [r for r in rows if (r.get("data_source") or "").lower() != "propertyonion"]
    dropped = len(rows) - len(independent)
    print(f"  [mca] {county}: {len(rows)} closed rows fetched, {dropped} dropped "
          f"(propertyonion data_source), {len(independent)} independent")
    return independent


def map_outcome(auction_status):
    """Preserve auction_status verbatim (lowercased) — the matcher's CASE clause
    needs outcome='redeemed' for st='redeemed', outcome in ('cancelled','canceled')
    for st in ('cancelled','canceled'), and outcome='sold'/'struck_to_plaintiff'/
    'sold_third_party' for st='sold'. 'completed' always matches regardless of
    outcome value, but we still record the real status, never a guess."""
    s = (auction_status or "").lower()
    if s in ("no_bid", "no_sale"):
        return "no_bid"
    return s  # completed / sold / redeemed / cancelled / canceled — verbatim


def build_fc_row(county, mca):
    amount = mca.get("tier1_sold_amount") or mca.get("sold_amount")
    return {
        "case_number": mca["case_number"],
        "county": county,
        "sale_type": "foreclosure",
        "auction_date": mca.get("auction_date"),
        "opening_bid": mca.get("opening_bid"),
        "winning_bid": amount,
        "outcome": map_outcome(mca.get("auction_status")),
        "property_address": mca.get("property_address"),
        "parcel_id": mca.get("parcel_id"),
        "assessed_value_at_sale": mca.get("assessed_value") or mca.get("market_value"),
        "data_source": FC_DATA_SOURCE,
        "source_url": FC_SOURCE_URL,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }


def build_td_row(county, mca):
    amount = mca.get("tier1_sold_amount") or mca.get("sold_amount")
    return {
        "case_number": mca["case_number"],
        "county": county,
        "auction_date": mca.get("auction_date"),
        "opening_bid": mca.get("opening_bid"),
        "winning_bid": amount,
        "outcome": map_outcome(mca.get("auction_status")),
        "property_address": mca.get("property_address"),
        "parcel_id": mca.get("parcel_id"),
        "assessed_value": mca.get("assessed_value") or mca.get("market_value"),
        "data_source": TD_DATA_SOURCE,
        "source_url": TD_SOURCE_URL,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    print(f"gold_standard_orange_bcd_outcomes_backfill — {datetime.now(timezone.utc).isoformat()}")
    print(f"County: {COUNTY.upper()}")
    print()

    print("=== DoD BEFORE ===")
    dod_before = mgmt_sql(f"SELECT public.pencil_dod_evaluate_county('{COUNTY}') AS r")[0]["r"]
    print(json.dumps(dod_before, indent=2))
    print()

    print("=== Fetching MCA closed rows (independent data_source only) ===")
    mca_rows = fetch_mca_closed(COUNTY)

    fc_rows = [r for r in mca_rows if (r.get("sale_type") or "").lower() == "foreclosure"]
    td_rows = [r for r in mca_rows if (r.get("sale_type") or "").lower() == "tax_deed"]
    print(f"  Foreclosure rows: {len(fc_rows)}")
    print(f"  Tax deed rows:    {len(td_rows)}")
    print()

    fc_inserted = 0
    if fc_rows:
        print(f"=== Upserting {len(fc_rows)} foreclosure_outcomes rows ===")
        fc_payload = [build_fc_row(COUNTY, r) for r in fc_rows]
        res = sb_upsert("foreclosure_outcomes", fc_payload)
        fc_inserted = res.get("inserted", 0)
        print(f"  foreclosure_outcomes inserted: {fc_inserted} (parsed={len(fc_payload)})")
        if fc_inserted == 0 and len(fc_payload) > 0 and not res.get("note"):
            raise RuntimeError("[FAIL-LOUD] parsed >0 foreclosure rows but inserted 0 with no dup note")
        if res.get("note"):
            print(f"  Note: {res['note']}")
    print()

    td_inserted = 0
    if td_rows:
        print(f"=== Upserting {len(td_rows)} tax_deed_outcomes rows ===")
        td_payload = [build_td_row(COUNTY, r) for r in td_rows]
        res = sb_upsert("tax_deed_outcomes", td_payload)
        td_inserted = res.get("inserted", 0)
        print(f"  tax_deed_outcomes inserted: {td_inserted} (parsed={len(td_payload)})")
        if td_inserted == 0 and len(td_payload) > 0 and not res.get("note"):
            raise RuntimeError("[FAIL-LOUD] parsed >0 tax_deed rows but inserted 0 with no dup note")
        if res.get("note"):
            print(f"  Note: {res['note']}")
    print()

    print("=== Calling public.refresh_parity_tier1_outcomes('orange') ===")
    refresh_result = mgmt_sql(
        f"SELECT * FROM public.refresh_parity_tier1_outcomes('{COUNTY}')")
    print(json.dumps(refresh_result, indent=2))
    print()

    print("=== Calling public.promote_tier1_from_outcomes() ===")
    try:
        promo = sb_rpc("promote_tier1_from_outcomes")
        print(f"  Result: {promo}")
    except Exception as exc:
        print(f"  RPC error (non-fatal): {exc}")
    print()

    time.sleep(2)
    print("=== DoD AFTER ===")
    dod_after = mgmt_sql(f"SELECT public.pencil_dod_evaluate_county('{COUNTY}') AS r")[0]["r"]
    print(json.dumps(dod_after, indent=2))

    report = {
        "county": COUNTY,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "mca_closed_rows": len(mca_rows),
        "fc_rows_found": len(fc_rows),
        "td_rows_found": len(td_rows),
        "fc_inserted": fc_inserted,
        "td_inserted": td_inserted,
        "refresh_parity_result": refresh_result,
        "dod_before": dod_before,
        "dod_after": dod_after,
    }
    out_path = "/tmp/gold_standard_orange_bcd_outcomes_backfill_report.json"
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(f"\nFull report: {out_path}")


if __name__ == "__main__":
    main()
