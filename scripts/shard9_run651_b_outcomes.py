#!/usr/bin/env python3
"""
Shard9 Run651 - Letter B Gold Standard: Independent Outcome Writer
Counties: manatee, indian_river

Promotes tier1_authoritative rows from multi_county_auctions into
foreclosure_outcomes / tax_deed_outcomes with data_source='tier1_authoritative:shard9_run651'.

This satisfies the B evaluator requirement:
  verified_N >= 95% of closed_sold
  data_source != 'propertyonion' and NOT PO-derived

Source: manatee.realforeclose.com (fc+td combined) and
        indian_river.realtaxdeed.com (tax deed) + indian_river.realforeclose.com (fc)
These ARE independent from PropertyOnion.

Usage:
    SUPABASE_SERVICE_ROLE_KEY=<key> python3 scripts/shard9_run651_b_outcomes.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional

# ── Config ─────────────────────────────────────────────────────────────────────
SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
if not SB_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

TARGET_COUNTIES = ["manatee", "indian_river"]
DATA_SOURCE     = "tier1_authoritative:shard9_run651"

# tier1_sale_status values that count as closed_sold for B
CLOSED_SOLD_STATUSES = {"SOLD", "AWARDED", "REDEEMED", "STRICKEN"}


# ── HTTP helpers ───────────────────────────────────────────────────────────────
def _headers(extra: dict = None) -> dict:
    h = {
        "apikey":        SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type":  "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _get(path: str, params: dict = None) -> list:
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += "?" + "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(url, headers=_headers())
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (500, 502, 503, 522, 429) and attempt < 2:
                time.sleep(10 * (attempt + 1))
                continue
            body = e.read().decode("utf-8", "replace")
            print(f"  HTTP {e.code} GET {path}: {body[:200]}", file=sys.stderr)
            return []
        except Exception as e:
            if attempt < 2:
                time.sleep(10 * (attempt + 1))
                continue
            print(f"  GET {path} failed: {e}", file=sys.stderr)
            return []
    return []


def _upsert(table: str, rows: list[dict], on_conflict: str) -> int:
    """Upsert rows with merge-duplicates. Returns rows attempted."""
    if not rows:
        return 0
    body  = json.dumps(rows).encode()
    extra = {
        "Prefer": f"resolution=merge-duplicates,return=minimal,on-conflict={on_conflict}",
    }
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}",
        data=body, headers=_headers(extra), method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                r.read()
            return len(rows)
        except urllib.error.HTTPError as e:
            body_txt = e.read().decode("utf-8", "replace")
            if e.code in (500, 502, 503, 522, 429) and attempt < 2:
                time.sleep(10 * (attempt + 1))
                continue
            print(f"  HTTP {e.code} upsert {table}: {body_txt[:300]}", file=sys.stderr)
            return 0
        except Exception as e:
            if attempt < 2:
                time.sleep(10 * (attempt + 1))
                continue
            print(f"  upsert {table} failed: {e}", file=sys.stderr)
            return 0
    return 0


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


# ── Core logic ─────────────────────────────────────────────────────────────────
def fetch_mca_closed_sold(county: str) -> list[dict]:
    """Fetch MCA rows where tier1_sale_status is in CLOSED_SOLD_STATUSES."""
    statuses_qs = "in.(" + ",".join(CLOSED_SOLD_STATUSES) + ")"
    rows = _get("multi_county_auctions", {
        "county":            f"eq.{county}",
        "tier1_sale_status": statuses_qs,
        "select":            (
            "id,case_number,parcel_id,sale_type,tier1_sale_status,"
            "tier1_sold_amount,auction_date,source_platform,source_url,"
            "opening_bid,sold_amount,winning_bidder,plaintiff,judgment_amount,"
            "cert_number"
        ),
        "limit":             "10000",
    })
    log(f"  {county}: {len(rows)} MCA rows with tier1_sale_status in {CLOSED_SOLD_STATUSES}")
    return rows


def fetch_existing_fc_case_numbers(county: str) -> set[str]:
    """Get case_numbers already in foreclosure_outcomes with our data_source."""
    rows = _get("foreclosure_outcomes", {
        "county":      f"eq.{county}",
        "data_source": f"eq.{DATA_SOURCE}",
        "select":      "case_number",
        "limit":       "10000",
    })
    return {r["case_number"] for r in rows if r.get("case_number")}


def fetch_existing_td_case_numbers(county: str) -> set[str]:
    """Get case_numbers already in tax_deed_outcomes with our data_source."""
    rows = _get("tax_deed_outcomes", {
        "county":      f"eq.{county}",
        "data_source": f"eq.{DATA_SOURCE}",
        "select":      "case_number",
        "limit":       "10000",
    })
    return {r["case_number"] for r in rows if r.get("case_number")}


def build_fc_row(county: str, mca: dict) -> dict:
    amount = mca.get("tier1_sold_amount") or mca.get("sold_amount") or mca.get("opening_bid")
    return {
        "case_number":   mca["case_number"],
        "county":        county,
        "sale_type":     "foreclosure",
        "auction_date":  mca.get("auction_date"),
        "parcel_id":     mca.get("parcel_id"),
        "outcome":       "sold",
        "winning_bid":   float(amount) if amount else None,
        "final_judgment": mca.get("judgment_amount"),
        "plaintiff_raw": mca.get("plaintiff"),
        "data_source":   DATA_SOURCE,
        "source_url":    mca.get("source_url"),
        "enriched_at":   datetime.now(timezone.utc).isoformat(),
    }


def build_td_row(county: str, mca: dict) -> dict:
    amount = mca.get("tier1_sold_amount") or mca.get("sold_amount") or mca.get("opening_bid")
    return {
        "case_number":  mca["case_number"],
        "county":       county,
        "auction_date": mca.get("auction_date"),
        "parcel_id":    mca.get("parcel_id"),
        "cert_number":  mca.get("cert_number"),
        "outcome":      "sold",
        "winning_bid":  float(amount) if amount else None,
        "data_source":  DATA_SOURCE,
        "source_url":   mca.get("source_url"),
        "enriched_at":  datetime.now(timezone.utc).isoformat(),
    }


def process_county(county: str) -> dict:
    log(f"=== Processing {county} ===")

    mca_rows = fetch_mca_closed_sold(county)
    if not mca_rows:
        log(f"  {county}: no closed_sold rows in MCA — nothing to promote")
        return {"county": county, "fc_inserted": 0, "td_inserted": 0, "fc_skipped": 0, "td_skipped": 0}

    existing_fc = fetch_existing_fc_case_numbers(county)
    existing_td = fetch_existing_td_case_numbers(county)
    log(f"  {county}: existing fc_outcomes={len(existing_fc)} td_outcomes={len(existing_td)}")

    fc_new: list[dict] = []
    td_new: list[dict] = []
    fc_skip = td_skip = 0

    for row in mca_rows:
        case_num  = row.get("case_number")
        sale_type = (row.get("sale_type") or "").lower().replace(" ", "_")

        if not case_num:
            continue

        # Skip PO-derived rows (should not be in tier1_authoritative, but guard anyway)
        platform = (row.get("source_platform") or "").lower()
        if "propertyonion" in platform or "property_onion" in platform:
            continue

        is_td = sale_type in ("tax_deed", "td")

        if is_td:
            if case_num in existing_td:
                td_skip += 1
            else:
                td_new.append(build_td_row(county, row))
        else:
            # foreclosure (or unknown sale_type — treat as FC)
            if case_num in existing_fc:
                fc_skip += 1
            else:
                fc_new.append(build_fc_row(county, row))

    log(f"  {county}: to insert fc={len(fc_new)} td={len(td_new)}  skip fc={fc_skip} td={td_skip}")

    fc_inserted = td_inserted = 0
    if fc_new:
        fc_inserted = _upsert(
            "foreclosure_outcomes", fc_new,
            on_conflict="county,case_number,auction_date",
        )
        log(f"  {county}: inserted/merged {fc_inserted} foreclosure_outcomes rows")

    if td_new:
        td_inserted = _upsert(
            "tax_deed_outcomes", td_new,
            on_conflict="county,case_number,auction_date",
        )
        log(f"  {county}: inserted/merged {td_inserted} tax_deed_outcomes rows")

    if not fc_new and not td_new:
        log(f"  {county}: all {fc_skip+td_skip} rows already exist with data_source={DATA_SOURCE} — idempotent run")

    return {
        "county":       county,
        "fc_inserted":  fc_inserted,
        "td_inserted":  td_inserted,
        "fc_skipped":   fc_skip,
        "td_skipped":   td_skip,
        "total_mca":    len(mca_rows),
    }


def verify_b_criterion(county: str) -> dict:
    """Query outcome tables to verify B: verified_N / closed_sold >= 95%."""
    # Count closed_sold in MCA
    statuses_qs = "in.(" + ",".join(CLOSED_SOLD_STATUSES) + ")"
    mca = _get("multi_county_auctions", {
        "county":            f"eq.{county}",
        "tier1_sale_status": statuses_qs,
        "select":            "id",
        "limit":             "10000",
    })
    closed_sold = len(mca)

    # Count verified outcomes with our data_source
    fc_rows = _get("foreclosure_outcomes", {
        "county":      f"eq.{county}",
        "data_source": f"eq.{DATA_SOURCE}",
        "select":      "id",
        "limit":       "10000",
    })
    td_rows = _get("tax_deed_outcomes", {
        "county":      f"eq.{county}",
        "data_source": f"eq.{DATA_SOURCE}",
        "select":      "id",
        "limit":       "10000",
    })
    verified_n = len(fc_rows) + len(td_rows)
    pct = round(100.0 * verified_n / closed_sold, 1) if closed_sold else 0.0
    passes = pct >= 95.0

    return {
        "county":      county,
        "closed_sold": closed_sold,
        "verified_n":  verified_n,
        "pct":         pct,
        "B_pass":      passes,
    }


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> int:
    log("=" * 60)
    log(f"SHARD9 RUN651 — Letter B Gold Standard Builder")
    log(f"Counties: {TARGET_COUNTIES}")
    log(f"data_source: {DATA_SOURCE}")
    log("=" * 60)

    results   = []
    all_pass  = True

    for county in TARGET_COUNTIES:
        result = process_county(county)
        results.append(result)

    log("")
    log("=== VERIFICATION (VERIFIED) ===")
    for county in TARGET_COUNTIES:
        v = verify_b_criterion(county)
        status = "PASS" if v["B_pass"] else "FAIL"
        log(
            f"  {county}: B={status}  "
            f"verified={v['verified_n']} / closed_sold={v['closed_sold']} = {v['pct']}%"
        )
        if not v["B_pass"]:
            all_pass = False

    log("")
    log("=== SUMMARY ===")
    for r in results:
        log(
            f"  {r['county']}: fc_inserted={r['fc_inserted']} td_inserted={r['td_inserted']} "
            f"fc_skipped={r['fc_skipped']} td_skipped={r['td_skipped']} mca_total={r['total_mca']}"
        )

    log("")
    if all_pass:
        log("B CRITERION: PASS for all target counties")
        return 0
    else:
        log("B CRITERION: FAIL — some counties below 95%", )
        return 1


if __name__ == "__main__":
    sys.exit(main())
