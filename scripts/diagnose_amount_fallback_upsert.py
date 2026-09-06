#!/usr/bin/env python3
"""Diagnose the auction_amount_fallbacks REST upsert without leaking secrets.

Usage:
  SUPABASE_URL=https://... SUPABASE_SERVICE_ROLE_KEY=... \
    python3 biddeed_supabase_fallback_400_diagnostic.py payload.json

The payload file must contain a JSON array of fallback evidence rows. The script
performs local validation, sends one bounded POST, and prints a redacted response.
It does not print the API key or full payload.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation

REQUIRED = {
    "source_record_key",
    "county_slug",
    "sale_type",
    "auction_date",
    "amount_type",
    "amount_currency",
    "source_authority",
    "source_url",
    "null_reason",
    "provenance",
}
ALLOWED_SALE_TYPES = {"tax_deed", "foreclosure"}


def fail(message: str) -> None:
    print(f"LOCAL_VALIDATION_ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def validate(rows: object) -> list[dict]:
    if not isinstance(rows, list) or not rows:
        fail("payload must be a non-empty JSON array")
    seen: set[tuple[str, str, str]] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            fail(f"row {index} is not an object")
        missing = sorted(REQUIRED - set(row))
        if missing:
            fail(f"row {index} missing fields: {', '.join(missing)}")
        key = str(row.get("source_record_key") or "").strip()
        county = str(row.get("county_slug") or "").strip().lower()
        sale_type = str(row.get("sale_type") or "").strip().lower()
        amount_type = str(row.get("amount_type") or "").strip()
        if not key or not county or not amount_type:
            fail(f"row {index} has an empty source_record_key, county_slug, or amount_type")
        if sale_type not in ALLOWED_SALE_TYPES:
            fail(f"row {index} has unsupported sale_type={sale_type!r}")
        conflict_key = (key, amount_type, str(row.get("source_authority") or ""))
        if conflict_key in seen:
            fail(f"duplicate conflict key in payload at row {index}: {conflict_key}")
        seen.add(conflict_key)
        amount = row.get("amount")
        if amount is not None:
            try:
                Decimal(str(amount))
            except (InvalidOperation, ValueError):
                fail(f"row {index} has a non-numeric amount")
        if amount is None and not row.get("null_reason"):
            fail(f"row {index} has null amount without null_reason")
        if amount is not None and row.get("null_reason") not in (None, ""):
            fail(f"row {index} has both amount and null_reason")
        if not isinstance(row.get("provenance"), dict):
            fail(f"row {index} provenance must be a JSON object")
    return rows


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} payload.json", file=sys.stderr)
        return 2
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required", file=sys.stderr)
        return 2
    try:
        rows = validate(json.loads(open(sys.argv[1], encoding="utf-8").read()))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"PAYLOAD_READ_ERROR: {exc}", file=sys.stderr)
        return 2

    params = urllib.parse.urlencode({
        "on_conflict": "source_record_key,amount_type,source_authority",
    })
    url = f"{base}/rest/v1/auction_amount_fallbacks?{params}"
    body = json.dumps(rows, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )
    print(json.dumps({"rows": len(rows), "bytes": len(body), "endpoint": "/rest/v1/auction_amount_fallbacks", "dry_run": False}))
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            print(json.dumps({"http_status": response.status, "response_body": response_body[:2000]}))
            return 0 if response.status in (200, 201, 204) else 1
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        print(json.dumps({"http_status": exc.code, "reason": exc.reason, "response_body": response_body[:4000]}))
        return 1
    except urllib.error.URLError as exc:
        print(json.dumps({"transport_error": str(exc.reason)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
