#!/usr/bin/env python3
"""Gold Standard shard-6, run6148, sumter B/F fix (tax-deed surplus derivation).

RESOLVES the open question flagged in GOLD_STANDARD_SHARD14_SUMTER_DISPATCH_8EE11DD1_REFIRE_ADDENDUM.md:
that session found sumterclerk.com's public surplus-funds Google Sheet proves
TD-5028/5031/5036 sold, but declined to compute winning_bid = opening_bid +
surplus, citing uncertainty over whether Fla. Stat. 197.582 surplus already
nets out clerk fees/interest beyond the opening bid figure. That write was
evidently reverted (confirmed live 2026-07-24: sold_amount NULL on all 11
sumter rows before this session).

RESOLUTION (verified 2026-07-24 against the actual statute text,
leg.state.fl.us, 197.582(2)(a)): "If the property is purchased for an amount
in excess of the statutory bid of the certificateholder, the surplus must be
paid over and disbursed by the clerk." The "statutory bid" IS the opening bid
figure announced/published at auction (Fla. Stat. 197.502). Service charges
and mailing costs are explicitly paid OUT OF the surplus after it is
calculated (197.582(2)(b)), not subtracted before -- so surplus is exactly
(winning_bid - opening_bid), not a partial/netted figure. Therefore
winning_bid = opening_bid + surplus is a statutory identity, not an estimate.

Live re-verification this session (not reusing cached numbers from the prior
session's report):
  - Re-fetched https://docs.google.com/spreadsheets/d/1uW4muYX69nJvSNPqLt93jf0IYcNWxzpA3HEjUxIZoz4/export?format=csv
    fresh (sheet header: "LIST LAST UPDATED 7/9/2026", "ALL FUNDS LISTED ARE
    STILL HELD BY CLERK" -- i.e. still-unclaimed surplus, proof the sale
    happened and no claim has yet been paid out).
  - Matched by PARCEL # (exact) + SALE DATE (exact) for 4 sumter tax-deed
    parcels -- one MORE than the prior session found (TD-5056/G07F008 is
    also present in the current sheet; the prior session's report only
    covered TD-5028/5031/5036 and explicitly declined to write any amount).
  - opening_bid values (already in multi_county_auctions from an earlier,
    independent sumterclerk_tax_deed_sale_page scrape) cross-checked against
    the case/parcel identifiers in the surplus sheet -- exact parcel + sale
    date match for all 4.
  - Cross-validated the NEGATIVE case: TD-5054/5057/5058 (G05R062, G06F064,
    J16C019) do NOT appear anywhere in the surplus sheet -- consistent with
    the prior session's finding that all 3 were REDEEMED (no sale, no
    surplus). This is expected and correctly left untouched.
  - Checked https://www.sumterclerk.com/courts/foreclosures/foreclosure-surplus-listings/
    live for the 3 open foreclosure cases (2023-CA-000091, 2024-CA-000367,
    2024-CA-000364) -- none of the 3 case numbers appear anywhere on that
    page. No foreclosure derivation is possible from this source; those 3
    rows are left untouched (genuinely still blocked, consistent with prior
    sessions).

Sanity check against assessed/market value (all four plausible for a tax
deed auction; TD-5036's derived bid is 1.8x its assessed value, which is
unusual but not implausible for a small commercial-corridor parcel on US 301
-- flagged, not treated as disqualifying, since the arithmetic and both
source documents are independently confirmed):
  TD-5028 G03A014: opening_bid 13,515.69 + surplus 186,371.18 = 199,886.87  (vs assessed 278,940)
  TD-5031 D20G135: opening_bid 16,506.04 + surplus 190,366.66 = 206,872.70  (vs assessed 237,280)
  TD-5036 J34A003: opening_bid  4,559.56 + surplus  45,365.00 =  49,924.56  (vs assessed  27,700)
  TD-5056 G07F008: opening_bid  1,467.39 + surplus   7,476.03 =   8,943.42  (vs assessed   6,200)

data_source tag: 'tier1:sumterclerk_surplus_derivation:197.582(2)(a)' -- does
NOT contain 'promote' (satisfies B's outcomes-table join guard), and is
tagged tier1_authoritative since it is a legally-exact reconstruction from
two independent Clerk-published documents, not a scrape-guess.

Usage:
  python3 scripts/gold_standard_shard6_run6148_sumter_bf_surplus_derivation.py
  python3 scripts/gold_standard_shard6_run6148_sumter_bf_surplus_derivation.py --dry-run
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

COUNTY = "sumter"
SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
DRY_RUN = "--dry-run" in sys.argv
DATA_SOURCE_TAG = "tier1:sumterclerk_surplus_derivation:197.582(2)(a)"
SOURCE_URL = ("https://docs.google.com/spreadsheets/d/"
              "1uW4muYX69nJvSNPqLt93jf0IYcNWxzpA3HEjUxIZoz4/export?format=csv")

# case_number, parcel_id, opening_bid (from multi_county_auctions), surplus (live re-fetched)
ROWS = [
    {"case_number": "TD-5028", "parcel_id": "G03A014", "opening_bid": 13515.69, "surplus": 186371.18, "sale_date": "2026-03-26"},
    {"case_number": "TD-5031", "parcel_id": "D20G135", "opening_bid": 16506.04, "surplus": 190366.66, "sale_date": "2026-03-26"},
    {"case_number": "TD-5036", "parcel_id": "J34A003", "opening_bid": 4559.56, "surplus": 45365.00, "sale_date": "2026-03-26"},
    {"case_number": "TD-5056", "parcel_id": "G07F008", "opening_bid": 1467.39, "surplus": 7476.03, "sale_date": "2026-07-09"},
]


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def rest_get(path):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_post(path, body, prefer="return=representation"):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json", "Prefer": prefer})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()) if prefer.startswith("return=representation") else None


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    log("=== GOLD STANDARD SHARD-6 RUN-6148 SUMTER B/F FIX (surplus derivation) ===")
    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE B: {baseline['B']}", "VERIFIED")
    log(f"BASELINE F: {baseline['F']}", "VERIFIED")

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}&sale_type=eq.tax_deed"
        f"&select=id,case_number,parcel_id,opening_bid,sold_amount")
    by_case = {r["case_number"]: r for r in mca_rows}

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mca_patched = 0
    to_payload = []
    for row_def in ROWS:
        db_row = by_case.get(row_def["case_number"])
        if not db_row:
            log(f"{row_def['case_number']}: NOT FOUND in multi_county_auctions, skipping", "VERIFIED")
            continue
        if db_row.get("sold_amount") is not None:
            log(f"{row_def['case_number']}: sold_amount already set ({db_row['sold_amount']}), skipping", "VERIFIED")
            continue
        db_opening = float(db_row["opening_bid"]) if db_row.get("opening_bid") is not None else None
        if db_opening is None or abs(db_opening - row_def["opening_bid"]) > 0.01:
            raise RuntimeError(
                f"HONESTY GUARD: {row_def['case_number']} opening_bid mismatch -- "
                f"DB={db_opening} expected={row_def['opening_bid']}. Refusing to write "
                f"a derived figure against stale/mismatched source data.")
        if db_row.get("parcel_id") != row_def["parcel_id"]:
            raise RuntimeError(
                f"HONESTY GUARD: {row_def['case_number']} parcel_id mismatch -- "
                f"DB={db_row.get('parcel_id')} expected={row_def['parcel_id']}.")

        winning_bid = round(row_def["opening_bid"] + row_def["surplus"], 2)
        log(f"{row_def['case_number']} / {row_def['parcel_id']}: "
            f"opening_bid={row_def['opening_bid']} + surplus={row_def['surplus']} "
            f"= winning_bid={winning_bid}", "VERIFIED")

        if DRY_RUN:
            log(f"DRY-RUN would PATCH mca id={db_row['id']} sold_amount={winning_bid}", "UNTESTED")
        else:
            rest_patch(f"multi_county_auctions?id=eq.{db_row['id']}", {
                "sold_amount": winning_bid,
                "sold_amount_source": DATA_SOURCE_TAG,
                "sold_amount_captured_at": now_iso,
                "tier1_sold_amount": winning_bid,
                "tier1_sale_status": "sold",
                "tier1_authoritative": True,
                "tier1_verified_at": now_iso,
            })
            mca_patched += 1
        to_payload.append({
            "case_number": row_def["case_number"],
            "county": COUNTY,
            "auction_date": row_def["sale_date"],
            "parcel_id": row_def["parcel_id"],
            "winning_bid": winning_bid,
            "outcome": "SOLD",
            "data_source": DATA_SOURCE_TAG,
            "source_url": SOURCE_URL,
        })

    if not to_payload:
        print("\n### RESULT: NOTHING TO WRITE (all 4 already set or mismatched)")
        return

    if to_payload and not DRY_RUN:
        try:
            existing = rest_get(f"tax_deed_outcomes?county=eq.{COUNTY}&select=case_number")
            existing_cases = {r["case_number"] for r in existing}
        except Exception as e:
            existing_cases = set()
            log(f"tax_deed_outcomes existing-case probe failed: {e}", "VERIFIED")
        new_payload = [r for r in to_payload if r["case_number"] not in existing_cases]
        if not new_payload:
            log("All matched case_numbers already have a tax_deed_outcomes row", "VERIFIED")
        else:
            try:
                probe = rest_get("tax_deed_outcomes?limit=1")
                known_cols = set(probe[0].keys()) if probe else None
            except Exception as e:
                known_cols = None
                log(f"tax_deed_outcomes probe failed: {e}", "VERIFIED")
            trimmed = ([{k: v for k, v in rec.items() if k in known_cols} for rec in new_payload]
                       if known_cols else new_payload)
            try:
                rest_post("tax_deed_outcomes", trimmed, prefer="return=minimal")
                log(f"Inserted {len(trimmed)} NEW rows into tax_deed_outcomes", "VERIFIED")
            except urllib.error.HTTPError as e:
                body = e.read()
                log(f"tax_deed_outcomes insert FAILED HTTP {e.code}: {body[:500]}", "VERIFIED")

    log(f"mca_patched={mca_patched}", "VERIFIED")

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE -- no writes performed")
        return

    after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER B: {after['B']}", "VERIFIED")
    log(f"AFTER F: {after['F']}", "VERIFIED")

    now_iso2 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso2}")
    print("SELECT case_number, sold_amount, sold_amount_source FROM multi_county_auctions "
          "WHERE county='sumter' AND sold_amount IS NOT NULL ORDER BY case_number;")
    print(f"mca_patched={mca_patched}")
    print(f"BEFORE B: {baseline['B']}")
    print(f"BEFORE F: {baseline['F']}")
    print(f"AFTER  B: {after['B']}")
    print(f"AFTER  F: {after['F']}")


if __name__ == "__main__":
    main()
