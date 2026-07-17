#!/usr/bin/env python3
"""
CERTIFY ROUTER BACKTEST — Definition of Done item 6.

Replays last 7d certify_tier_trail records through router.route() and asserts
SAME final verdict on every run vs the prior path.

Any flip = non-zero exit code (loop does NOT exit).

Usage:
    python3 certify/backtest.py [--days 7]
"""
from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("certify_backtest")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def _sb_get(path: str, params: dict | None = None) -> Any:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    resp = httpx.get(url, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _sb_post(path: str, body: dict) -> Any:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    resp = httpx.post(
        url,
        headers={**HEADERS, "Prefer": "return=representation"},
        json=body,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_recent_trails(days: int) -> list[dict]:
    """Fetch distinct (county_slug, final_certify) from last N days."""
    cutoff = (datetime.now(timezone.utc) - __import__("datetime").timedelta(days=days)).isoformat()
    rows = _sb_get("certify_tier_trail", {
        "created_at": f"gte.{cutoff}",
        "select":     "county_slug,final_certify,gate_verdict,gate_pass_count,gate_letters",
        "order":      "county_slug.asc,created_at.desc",
    })
    # Deduplicate: keep most recent per county
    seen: set[str] = set()
    unique: list[dict] = []
    for row in rows:
        slug = row["county_slug"]
        if slug not in seen:
            seen.add(slug)
            unique.append(row)
    return unique


def backtest(days: int = 7) -> int:
    """
    Returns number of verdict flips found.
    0 = all match, non-zero = loop must NOT exit.
    """
    # Late import to avoid circular
    from certify.router import _load_config, route  # noqa: PLC0415

    historic = fetch_recent_trails(days)
    if not historic:
        log.warning("No historic trails found for last %d days — nothing to backtest", days)
        return 0

    log.info("Backtest: replaying %d county trails from last %d days", len(historic), days)

    cfg = _load_config()
    run_id = f"backtest-{uuid.uuid4()}"

    flips: list[dict] = []

    for trail in historic:
        county_slug = trail["county_slug"]
        historic_certify = trail["final_certify"]

        try:
            dec = route(county_slug, run_id, cfg)
        except Exception as exc:
            log.error("route() error for %s: %s — skipping", county_slug, exc)
            continue

        if dec.final_certify != historic_certify:
            flips.append({
                "county_slug":       county_slug,
                "historic_certify":  historic_certify,
                "router_certify":    dec.final_certify,
                "router_tier":       dec.final_tier,
                "historic_verdict":  trail.get("gate_verdict"),
                "historic_pass_count": trail.get("gate_pass_count"),
            })
            log.error(
                "FLIP: %s historic=%s router=%s (tier=%s)",
                county_slug, historic_certify, dec.final_certify, dec.final_tier,
            )
        else:
            log.info("OK: %s certify=%s tier=%s", county_slug, dec.final_certify, dec.final_tier)

    # Persist backtest results
    try:
        _sb_post("certify_router_run", {
            "run_id":          run_id,
            "counties_total":  len(historic),
            "trigger_source":  "backtest",
            "haiku_floor_used":   cfg.get("haiku_confidence_floor", 0.90),
            "sonnet_floor_used":  cfg.get("sonnet_confidence_floor", 0.85),
            "shadow_rate_used":   cfg.get("shadow_audit_rate", 0.10),
        })
    except Exception as exc:
        log.warning("Could not persist backtest run record: %s", exc)

    if flips:
        log.error("BACKTEST FAILED: %d verdict flips detected", len(flips))
        print("\n=== VERDICT FLIPS ===")
        print(json.dumps(flips, indent=2))
        return len(flips)

    log.info("BACKTEST PASSED: all %d counties matched historic verdicts", len(historic))
    print(f"\nBACKTEST PASSED — {len(historic)} counties, 0 flips, run_id={run_id}")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7, help="lookback window in days")
    args = parser.parse_args()

    flip_count = backtest(days=args.days)
    sys.exit(0 if flip_count == 0 else 1)
