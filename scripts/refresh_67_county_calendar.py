#!/usr/bin/env python3
"""Refresh the next 60 days of Florida auction calendars for every configured county.

This orchestrator does not invent rows. It reads the pipeline county registry,
invokes the existing paginated RealForeclose/RealTaxDeed adapter for approved
public source hosts, and records unsupported or unconfigured counties as gaps.
It is intended for a GitHub Actions daily run with Supabase service-role access.
"""
from __future__ import annotations

import argparse
import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
ROOT = Path(__file__).resolve().parents[1]
HARVESTER = ROOT / "scripts" / "realforeclose_aids_paginated_harvest.py"
ALLOWED_HOST_SUFFIXES = ("realforeclose.com", "realtaxdeed.com")


def get_counties() -> list[dict]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    params = urllib.parse.urlencode(
        {
            "select": "county_slug,county_name,fc_url,td_url",
            "order": "county_slug.asc",
        }
    )
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/county_auction_config?{params}")
    req.add_header("apikey", SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    with urllib.request.urlopen(req, timeout=60) as response:
        rows = json.loads(response.read().decode("utf-8"))
    if len(rows) != 67:
        raise RuntimeError(f"county registry returned {len(rows)} rows; expected 67")
    return rows


def source_parts(url: str | None, county_slug: str) -> tuple[str, str] | None:
    if not url:
        return None
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    suffix = next((s for s in ALLOWED_HOST_SUFFIXES if host.endswith(s)), None)
    if not suffix:
        return None
    subdomain = host[: -(len(suffix) + 1)].split(".")[0]
    if not subdomain:
        subdomain = county_slug
    return subdomain, suffix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days-ahead", type=int, default=60)
    parser.add_argument("--start-date", default=dt.date.today().isoformat())
    parser.add_argument("--county", action="append", help="limit to a county slug; repeatable")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    start = dt.date.fromisoformat(args.start_date)
    dates = [(start + dt.timedelta(days=i)).strftime("%m/%d/%Y") for i in range(args.days_ahead + 1)]
    wanted = {c.lower() for c in args.county} if args.county else None
    counties = get_counties()
    report = {"started_at": dt.datetime.now(dt.timezone.utc).isoformat(), "days_ahead": args.days_ahead, "workers": args.workers, "processed": [], "gaps": [], "errors": []}
    tasks: list[tuple[str, str, str, str]] = []
    for county in counties:
        slug = str(county["county_slug"]).lower()
        if wanted and slug not in wanted:
            continue
        sources = []
        for sale_type, key in (("foreclosure", "fc_url"), ("tax_deed", "td_url")):
            parts = source_parts(county.get(key), slug)
            if parts:
                sources.append((sale_type, parts))
        if not sources:
            report["gaps"].append({"county": slug, "reason": "no_supported_public_adapter"})
            continue
        for sale_type, (subdomain, platform) in sources:
            tasks.append((slug, sale_type, subdomain, platform))

    def run_task(task: tuple[str, str, str, str]) -> dict:
        slug, sale_type, subdomain, platform = task
        cmd = [sys.executable, str(HARVESTER), subdomain, platform, slug, *dates]
        completed = subprocess.run(cmd, cwd=ROOT, env=os.environ.copy(), text=True, capture_output=True, timeout=900)
        tail = (completed.stdout + completed.stderr)[-2000:]
        # Existing rows are valid on a daily idempotent refresh. The legacy adapter
        # returns exit 1 when it parsed rows but found nothing new to merge.
        if completed.returncode == 1 and "Silent failure: parsed>0 inserted=0" in tail:
            return {"county": slug, "sale_type": sale_type, "platform": platform, "returncode": 0, "state": "no_change_existing_rows", "tail": tail}
        return {"county": slug, "sale_type": sale_type, "platform": platform, "returncode": completed.returncode, "state": "updated" if completed.returncode == 0 else "adapter_error", "tail": tail}

    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 8))) as pool:
        futures = [pool.submit(run_task, task) for task in tasks]
        for future in as_completed(futures):
            try:
                entry = future.result()
                if entry["returncode"] == 0:
                    report["processed"].append(entry)
                else:
                    report["errors"].append(entry)
            except Exception as exc:
                report["errors"].append({"error": str(exc)})
                if not args.continue_on_error:
                    raise

    report["finished_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    print(json.dumps(report, indent=2))
    return 0 if not report["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
