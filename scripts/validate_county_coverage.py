#!/usr/bin/env python3
"""Validate the 67-county future-auction publication gate.

This is read-only. It uses the active county_auction_config registry as the
67-county denominator and public.multi_county_auctions as the publication
layer. County normalization deliberately lowercases before stripping
punctuation so values such as ``Osceola`` are not truncated to ``sceola``.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def fetch(table: str, query: dict[str, str], *, page_size: int = 1000) -> list[dict]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    retryable = {500, 502, 503, 504, 520, 521, 522, 523, 524, 525}
    all_rows: list[dict] = []
    offset = 0
    while True:
        page_query = dict(query)
        page_query["limit"] = str(page_size)
        page_query["offset"] = str(offset)
        url = f"{SUPABASE_URL}/rest/v1/{table}?{urllib.parse.urlencode(page_query)}"
        last_error: Exception | None = None
        for attempt, delay in enumerate((0, 5, 15, 45), start=1):
            if delay:
                time.sleep(delay)
            req = urllib.request.Request(url, headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
            try:
                with urllib.request.urlopen(req, timeout=60) as response:
                    page = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in retryable or attempt == 4:
                    raise
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == 4:
                    raise
        else:
            raise RuntimeError(f"Supabase coverage query failed after retries: {last_error}")
        if not isinstance(page, list):
            raise RuntimeError(f"Unexpected Supabase response for {table}: {type(page).__name__}")
        all_rows.extend(page)
        if len(page) < page_size:
            return all_rows
        offset += page_size


def main() -> int:
    today = dt.date.today().isoformat()
    repo_root = Path(__file__).resolve().parents[1]
    overrides_path = repo_root / "config" / "county_source_overrides.json"
    assertions_path = repo_root / "config" / "county_authoritative_assertions.json"
    overrides = json.loads(overrides_path.read_text(encoding="utf-8")) if overrides_path.exists() else {}
    assertions = json.loads(assertions_path.read_text(encoding="utf-8")) if assertions_path.exists() else {"assertions": []}
    required_types: dict[str, set[str]] = {}
    for slug, entry in overrides.get("counties", {}).items():
        required_types[key(slug)] = {str(source.get("sale_type")) for source in entry.get("sources", []) if source.get("sale_type")}
    zero_types: dict[str, set[str]] = {}
    for assertion in assertions.get("assertions", []):
        if assertion.get("assertion_type") in {"authoritative_zero", "authoritative_empty_schedule"}:
            zero_types.setdefault(key(assertion.get("county_slug")), set()).add(str(assertion.get("sale_type")))
    registry = fetch("county_auction_config", {
        "select": "county_name,county_slug",
        "is_active": "eq.true",
        "limit": "100",
    })
    rows = fetch("multi_county_auctions", {
        "select": "county,auction_date,judgment_amount",
        "auction_date": f"gte.{today}",
    })
    by_county: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = by_county.setdefault(key(row.get("county")), {"future_rows": 0, "amount_rows": 0})
        bucket["future_rows"] += 1
        if row.get("judgment_amount") is not None:
            bucket["amount_rows"] += 1
    coverage = []
    for county in registry:
        slug = str(county.get("county_slug") or "")
        bucket = by_county.get(key(slug), {"future_rows": 0, "amount_rows": 0})
        asserted_zero_types = sorted(zero_types.get(key(slug), set()))
        required = required_types.get(key(slug), set())
        has_authoritative_no_sale_evidence = bool(required) and required.issubset(set(asserted_zero_types))
        has_empty_schedule_evidence = any(
            assertion.get("assertion_type") == "authoritative_empty_schedule"
            and key(assertion.get("county_slug")) == key(slug)
            for assertion in assertions.get("assertions", [])
        )
        coverage.append({
            "county": county.get("county_name"),
            "slug": slug,
            **bucket,
            "authoritative_zero_sale_types": asserted_zero_types,
            "qualified": bucket["future_rows"] > 0 or has_authoritative_no_sale_evidence,
            "qualification_reason": "future_rows" if bucket["future_rows"] > 0 else ("authoritative_zero_all_configured_sale_types" if has_authoritative_no_sale_evidence and not has_empty_schedule_evidence else ("authoritative_empty_schedule_all_configured_sale_types" if has_authoritative_no_sale_evidence else "unresolved")),
        })
    covered = [item for item in coverage if item["future_rows"] > 0]
    qualified = [item for item in coverage if item["qualified"]]
    total_rows = sum(item["future_rows"] for item in coverage)
    amount_rows = sum(item["amount_rows"] for item in coverage)
    report = {
        "as_of": dt.datetime.now(dt.timezone.utc).isoformat(),
        "supabase_host": urllib.parse.urlparse(SUPABASE_URL).hostname,
        "today": today,
        "registry_count": len(coverage),
        "counties_with_future_rows": len(covered),
        "counties_without_future_rows": len(coverage) - len(covered),
        "counties_qualified": len(qualified),
        "counties_unqualified": len(coverage) - len(qualified),
        "qualified_64_of_67": len(qualified) >= 64,
        "future_rows": total_rows,
        "future_rows_with_amount": amount_rows,
        "amount_completeness_pct": round(100.0 * amount_rows / total_rows, 2) if total_rows else 0.0,
        "future_rows_64_of_67": len(covered) >= 64,
        "milestone_64_of_67": len(qualified) >= 64,
        "missing_future_row_counties": [item for item in coverage if item["future_rows"] == 0],
        "missing_counties": [item for item in coverage if not item["qualified"]],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["registry_count"] == 67 else 2


if __name__ == "__main__":
    raise SystemExit(main())
