#!/usr/bin/env python3
"""Record certified fallback evidence for future auction rows.

This script never converts assessed or market value into an opening bid or
judgment amount. It records Property Appraiser values as typed fallback
metrics and records an explicit null reason when no certified amount exists.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def get_rows(start: str, end: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        query = urllib.parse.urlencode([
            ("select", "id,county,auction_date,sale_type,case_number,parcel_id,opening_bid,opening_bid_usd,judgment_amount,judgment_amount_usd,bcpao_data,bcpao_url,clerk_url,source_url,source_platform,source_county,scrape_timestamp"),
            ("auction_date", f"gte.{start}"),
            ("auction_date", f"lte.{end}"),
            ("limit", "1000"),
            ("offset", str(offset)),
            ("order", "auction_date.asc"),
        ])
        request = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/multi_county_auctions?{query}", headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
        with urllib.request.urlopen(request, timeout=45) as response:
            batch = json.loads(response.read().decode())
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += len(batch)
    return rows


def appraiser_values(row: dict) -> dict[str, float]:
    raw = row.get("bcpao_data") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    values = {}
    for target, keys in {
        "assessed_value": ("assessed_value", "assessedValue", "assessed", "taxable_value"),
        "market_value": ("market_value", "marketValue", "just_value", "market"),
    }.items():
        for key in keys:
            value = raw.get(key) if isinstance(raw, dict) else None
            try:
                if value not in (None, ""):
                    values[target] = float(str(value).replace(",", "").replace("$", ""))
                    break
            except ValueError:
                pass
    return values


def build_evidence(rows: list[dict], run_id: str) -> list[dict]:
    evidence = []
    for row in rows:
        sale_type = str(row.get("sale_type") or "unknown").lower()
        if "tax" in sale_type:
            normalized_sale = "tax_deed"
        elif "forecl" in sale_type:
            normalized_sale = "foreclosure"
        else:
            continue
        primary_amount = row.get("opening_bid_usd") or row.get("opening_bid") or row.get("judgment_amount_usd") or row.get("judgment_amount")
        key = str(row.get("id") or row.get("case_number") or row.get("parcel_id") or "")
        values = appraiser_values(row)
        base = {
            "source_record_key": key,
            "county_slug": str(row.get("county") or row.get("source_county") or "").lower().strip(),
            "sale_type": normalized_sale,
            "auction_date": row.get("auction_date"),
            "parcel_id": row.get("parcel_id"),
            "case_number": row.get("case_number"),
            "source_captured_at": row.get("scrape_timestamp"),
            "source_run_id": run_id,
            "provenance": {"source_platform": row.get("source_platform"), "source_url": row.get("source_url"), "source_record_id": key, "primary_amount_present": primary_amount is not None},
        }
        if primary_amount is not None:
            continue
        source_url = row.get("bcpao_url") or row.get("clerk_url") or row.get("source_url")
        if not source_url:
            continue
        if values:
            for amount_type, amount in values.items():
                evidence.append({**base, "amount_type": amount_type, "amount": amount, "amount_currency": "USD", "source_authority": "Property Appraiser", "source_url": source_url, "null_reason": None})
        else:
            evidence.append({**base, "amount_type": "no_certified_amount", "amount": None, "source_authority": "Property Appraiser", "source_url": source_url, "null_reason": "property_appraiser_value_unavailable"})
    return evidence


def upsert(evidence: list[dict]) -> int:
    if not evidence:
        return 0
    # Prevent PostgreSQL's ON CONFLICT statement from affecting the same target
    # row twice when duplicate source records occur in one harvested window.
    deduped: dict[tuple[str, str, str], dict] = {}
    for row in evidence:
        conflict_key = (
            str(row.get("source_record_key") or ""),
            str(row.get("amount_type") or ""),
            str(row.get("source_authority") or ""),
        )
        deduped[conflict_key] = row
    payload = list(deduped.values())
    request = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/auction_amount_fallbacks?on_conflict=source_record_key,amount_type,source_authority",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            if response.status not in (200, 201, 204):
                raise RuntimeError(f"fallback upsert failed HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:4000]
        raise RuntimeError(f"fallback upsert failed HTTP {exc.code}: {body}") from exc
    return len(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--days-ahead", type=int, default=14)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    start = dt.date.fromisoformat(args.start_date)
    end = start + dt.timedelta(days=args.days_ahead)
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    rows = get_rows(start.isoformat(), end.isoformat())
    run_id = f"amount-fallback-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    evidence = build_evidence(rows, run_id)
    inserted = upsert(evidence) if args.apply else 0
    print(json.dumps({"run_id": run_id, "window": [start.isoformat(), end.isoformat()], "source_rows": len(rows), "fallback_evidence": len(evidence), "inserted": inserted, "apply": args.apply, "amounts_are_not_auction_bid_substitutes": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
