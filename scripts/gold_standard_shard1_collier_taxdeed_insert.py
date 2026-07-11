#!/usr/bin/env python3
"""
Insert the real, parsed Collier tax-deed rows (from
gold_standard_shard1_collier_taxdeed_laserfiche_harvest.py, /tmp/collier_taxdeed_rows.json)
into multi_county_auctions, plus tax_deed_outcomes for completed (sold) sales, both tagged
data_source='collier_clerk_laserfiche' -- an INDEPENDENT clerk-of-court source (never
RealAuction, never PropertyOnion).

Idempotent: queries existing collier case_numbers + their auction_status first.
  - New case_numbers -> inserted fresh.
  - Existing case_numbers whose status has since resolved (upcoming -> sold/redeemed/
    cancelled, e.g. a future sale that has now occurred) -> updated in place, plus a
    tax_deed_outcomes row added if newly sold.
  - Existing, unchanged case_numbers -> last_seen_at bumped only (we re-verified them
    against the live source this run; no other field changes).
Safe to run on every scheduled cron invocation.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
NOW = datetime.now(timezone.utc).isoformat()


def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"curl failed: {r.stderr}")
    return r.stdout


def rest_get(path):
    out = sh(
        f'curl -sS -m 30 "{SUPABASE_URL}/rest/v1/{path}" '
        f'-H "apikey: {KEY}" -H "Authorization: Bearer {KEY}"'
    )
    return json.loads(out)


def rest_post(table, rows, prefer="return=minimal"):
    if not rows:
        return
    payload_path = f"/tmp/_insert_{table}.json"
    with open(payload_path, "w") as f:
        json.dump(rows, f)
    out = sh(
        f'curl -sS -m 60 -X POST "{SUPABASE_URL}/rest/v1/{table}" '
        f'-H "apikey: {KEY}" -H "Authorization: Bearer {KEY}" '
        f'-H "Content-Type: application/json" -H "Prefer: {prefer}" '
        f'--data @{payload_path} -w "\\nHTTP:%{{http_code}}"'
    )
    if "HTTP:20" not in out.splitlines()[-1]:
        raise RuntimeError(f"FAIL-LOUD: insert into {table} failed: {out}")


def rest_patch(table, filter_qs, body):
    payload_path = f"/tmp/_patch_{table}.json"
    with open(payload_path, "w") as f:
        json.dump(body, f)
    out = sh(
        f'curl -sS -m 30 -X PATCH "{SUPABASE_URL}/rest/v1/{table}?{filter_qs}" '
        f'-H "apikey: {KEY}" -H "Authorization: Bearer {KEY}" '
        f'-H "Content-Type: application/json" -H "Prefer: return=minimal" '
        f'--data @{payload_path} -w "\\nHTTP:%{{http_code}}"'
    )
    if "HTTP:20" not in out.splitlines()[-1]:
        raise RuntimeError(f"FAIL-LOUD: patch on {table} ({filter_qs}) failed: {out}")


def main():
    rows = json.load(open("/tmp/collier_taxdeed_rows.json"))
    print(f"Loaded {len(rows)} parsed Collier tax-deed rows", file=sys.stderr)

    existing = rest_get("multi_county_auctions?county=eq.collier&select=case_number,auction_status")
    existing_status = {r["case_number"]: r["auction_status"] for r in existing}
    print(f"{len(existing_status)} collier case_numbers already in DB", file=sys.stderr)

    new_parsed = [r for r in rows if r["case_number"] not in existing_status]
    transition_parsed = [
        r for r in rows
        if r["case_number"] in existing_status
        and existing_status[r["case_number"]] == "upcoming"
        and r["auction_status"] != "upcoming"
    ]
    unchanged_case_numbers = [
        r["case_number"] for r in rows
        if r["case_number"] in existing_status
        and r["case_number"] not in {t["case_number"] for t in transition_parsed}
    ]
    print(f"{len(new_parsed)} new, {len(transition_parsed)} status-transitioned, "
          f"{len(unchanged_case_numbers)} unchanged (freshness-only bump)", file=sys.stderr)

    mca_rows = []
    outcome_rows = []
    for r in new_parsed:
        mca_rows.append({
            "county": "collier",
            "state": "FL",
            "sale_type": "tax_deed",
            "auction_type": "tax_deed",
            "auction_date": r["auction_date"],
            "case_number": r["case_number"],
            "cert_number": r["cert_number"],
            "owner_name": r["owner_name"],
            "parcel_id": r["parcel_id"],
            "legal_description": r["legal_description"],
            "opening_bid": r["opening_bid"],
            "opening_bid_usd": r["opening_bid"],
            "sold_amount": r["sold_amount"],
            "auction_status": r["auction_status"],
            "data_source": "collier_clerk_laserfiche",
            "source_platform": "collier_clerk_laserfiche",
            "provenance": "primary_scrape",
            "source_url": "https://app.collierclerk.com/LFOfficialRecords/Browse.aspx?dbid=0&startid=1600&repo=OFFICIALRECORDSPROD",
            "scrape_timestamp": NOW,
            "scraped_at": NOW,
            "last_seen_at": NOW,
            "created_at": NOW,
            "tier1_authoritative": r["sold_amount"] is not None,
            "tier1_sold_amount": r["sold_amount"],
            "tier1_sale_status": r["auction_status"].upper() if r["sold_amount"] is not None else None,
            "tier1_verified_at": NOW if r["sold_amount"] is not None else None,
            "tier1_source_run_id": None,
        })
        if r["sold_amount"] is not None:
            outcome_rows.append({
                "case_number": r["case_number"],
                "county": "collier",
                "auction_date": r["auction_date"],
                "cert_number": r["cert_number"],
                "opening_bid": r["opening_bid"],
                "winning_bid": r["sold_amount"],
                "outcome": "SOLD",
                "parcel_id": r["parcel_id"],
                "data_source": "collier_clerk_laserfiche",
                "source_url": "https://app.collierclerk.com/LFOfficialRecords/Browse.aspx?dbid=0&startid=1600&repo=OFFICIALRECORDSPROD",
                "enriched_at": NOW,
                "created_at": NOW,
            })

    print(f"Inserting {len(mca_rows)} multi_county_auctions rows...", file=sys.stderr)
    for i in range(0, len(mca_rows), 50):
        rest_post("multi_county_auctions", mca_rows[i:i + 50])
    print("multi_county_auctions insert OK", file=sys.stderr)

    print(f"Inserting {len(outcome_rows)} tax_deed_outcomes rows (independent, real sold amounts)...", file=sys.stderr)
    for i in range(0, len(outcome_rows), 50):
        rest_post("tax_deed_outcomes", outcome_rows[i:i + 50])
    print("tax_deed_outcomes insert OK", file=sys.stderr)

    for r in transition_parsed:
        rest_patch(
            "multi_county_auctions",
            f"county=eq.collier&case_number=eq.{r['case_number']}",
            {
                "auction_status": r["auction_status"],
                "sold_amount": r["sold_amount"],
                "tier1_authoritative": r["sold_amount"] is not None,
                "tier1_sold_amount": r["sold_amount"],
                "tier1_sale_status": r["auction_status"].upper() if r["sold_amount"] is not None else None,
                "tier1_verified_at": NOW if r["sold_amount"] is not None else None,
                "last_seen_at": NOW,
            },
        )
        if r["sold_amount"] is not None:
            existing_outcome = rest_get(
                f"tax_deed_outcomes?county=eq.collier&case_number=eq.{r['case_number']}&select=case_number"
            )
            if not existing_outcome:
                rest_post("tax_deed_outcomes", [{
                    "case_number": r["case_number"],
                    "county": "collier",
                    "auction_date": r["auction_date"],
                    "cert_number": r["cert_number"],
                    "opening_bid": r["opening_bid"],
                    "winning_bid": r["sold_amount"],
                    "outcome": "SOLD",
                    "parcel_id": r["parcel_id"],
                    "data_source": "collier_clerk_laserfiche",
                    "source_url": "https://app.collierclerk.com/LFOfficialRecords/Browse.aspx?dbid=0&startid=1600&repo=OFFICIALRECORDSPROD",
                    "enriched_at": NOW,
                    "created_at": NOW,
                }])
    if transition_parsed:
        print(f"Transitioned {len(transition_parsed)} rows to their resolved status", file=sys.stderr)

    for i in range(0, len(unchanged_case_numbers), 50):
        batch = unchanged_case_numbers[i:i + 50]
        cn_list = ",".join(batch)
        rest_patch(
            "multi_county_auctions",
            f"county=eq.collier&case_number=in.({cn_list})",
            {"last_seen_at": NOW},
        )
    if unchanged_case_numbers:
        print(f"Freshness-bumped {len(unchanged_case_numbers)} unchanged rows", file=sys.stderr)

    print(f"\nDONE: {len(mca_rows)} new multi_county_auctions rows, {len(outcome_rows)} new tax_deed_outcomes rows, "
          f"{len(transition_parsed)} status transitions, {len(unchanged_case_numbers)} freshness bumps for collier.", file=sys.stderr)


if __name__ == "__main__":
    main()
