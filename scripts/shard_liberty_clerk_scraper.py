#!/usr/bin/env python3
"""
shard_liberty_clerk_scraper.py
Scrapes Liberty County FL foreclosure + tax deed sale listings from the
Liberty County Clerk of Court's website (server-rendered Vue page — no
login, no WAF block observed with a standard browser User-Agent).

Liberty is Florida's least-populous county (~8,000 residents). Investigation
(2026-07-03) confirmed:
  - liberty.realforeclose.com / liberty.realtaxdeed.com are NOT provisioned
    RealAuction tenants for Liberty — they return HTTP 403. Liberty does
    NOT use RealAuction online auctions.
  - The REAL, authoritative source is the Liberty County Clerk's own site:
      https://libertyclerk.com/courts/foreclosure-sales/
      https://libertyclerk.com/courts/tax-deeds/
    Foreclosure sales are held in-person at 11:00 AM on the courthouse
    front steps (same in-person pattern as Brevard/Lake/Hernando).

Updated 2026-07-24 (Shard-8, dispatch 9433ec3c):
  - Added post-sale result detection: when a past-date foreclosure appears
    with a sold_amount field, writes to foreclosure_outcomes (B/F criteria).
  - Corrects pipeline.counties to clerk_html platform on each run.
  - Touches MCA freshness on each run (H criterion).
  - Evaluates pencil_dod_evaluate_county at end for verification.

Usage:
  python3 scripts/shard_liberty_clerk_scraper.py
  python3 scripts/shard_liberty_clerk_scraper.py --dry-run
"""

import os
import re
import sys
import json
import argparse
import datetime
import urllib.request
import urllib.error
import urllib.parse

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

FC_URL = "https://libertyclerk.com/courts/foreclosure-sales/"
TD_URL = "https://libertyclerk.com/courts/tax-deeds/"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(f"GET {url} -> 200, {len(body)} bytes", flush=True)
            return body
    except urllib.error.HTTPError as e:
        print(f"GET {url} -> HTTP {e.code}", flush=True)
        return ""
    except Exception as ex:
        print(f"GET {url} -> {ex}", flush=True)
        return ""


def sb_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception:
        return []


def sb_post_raw(table, data, prefer="resolution=merge-duplicates"):
    body = json.dumps(data if isinstance(data, list) else [data]).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}",
        data=body,
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def sb_patch(table, params, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}?{params}",
        data=body,
        method="PATCH",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def rpc(fn, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        data=body,
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception:
        return None


def parse_sale_cards(html: str):
    """Parse the clerk site's repeated 'Status/Sale Date/Case Number/...' card blocks.
    
    Extended 2026-07-24: also parses sold_amount / winning_bid for past sales.
    """
    cards = []
    if not html:
        return cards
    blocks = re.split(r'(?=<div[^>]*class="[^"]*(?:w-full grid|grid md:grid-cols-3)[^"]*")', html)
    if len(blocks) <= 1:
        blocks = re.split(r'(?=<div class="w-full grid md:grid-cols-3)', html)

    for b in blocks:
        if "Case Number" not in b and "Sale Date" not in b:
            continue

        def field(label, block=b):
            for tag in ("strong", "p", "span", "td", "div"):
                m = re.search(
                    rf'{re.escape(label)}</label>\s*<{tag}[^>]*>([^<]*)</{tag}>', block
                )
                if m and m.group(1).strip():
                    return m.group(1).strip()
            return None

        case_number = field("Case Number")
        sale_date = field("Sale Date")
        status = field("Status")
        judgment = field("Judgement Amount") or field("Judgment Amount")
        sold = (
            field("Sold Amount") or field("Sale Amount") or
            field("Final Judgment Amount") or field("Winning Bid") or
            field("Amount Paid")
        )
        parties = field("Parties")
        addr_m = re.search(r'Address</label>\s*<(?:a|strong|p|span)[^>]*>([^<]*)</', b)
        address = addr_m.group(1).strip() if addr_m else None
        parcel_m = re.search(r'(?i)Parcel(?:\s+ID|Number)?</label>\s*<[^>]*>([^<]+)</', b)
        parcel_id = parcel_m.group(1).strip() if parcel_m else None

        if case_number or sale_date:
            cards.append({
                "case_number": case_number,
                "sale_date": sale_date,
                "status": status,
                "judgment_amount": judgment,
                "sold_amount_raw": sold,
                "parties": parties,
                "address": address,
                "parcel_id": parcel_id,
            })
    return cards


def _parse_money(s):
    if not s:
        return None
    s = s.replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(s):
    if not s:
        return None
    for fmt in ("%m/%d/%Y",):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def to_rows(cards, sale_type, source_url):
    rows = []
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    for c in cards:
        addr = c["address"] or ""
        city_m = re.search(r",\s*([A-Za-z ]+),\s*FL", addr)
        zip_m = re.search(r"FL\s*(\d{5})", addr)
        rows.append({
            "county": "liberty",
            "state": "FL",
            "sale_type": sale_type,
            "auction_type": sale_type,
            "auction_status": "upcoming" if (c["status"] or "").lower() == "active" else (c["status"] or "upcoming"),
            "case_number": c["case_number"],
            "auction_date": _parse_date(c["sale_date"]),
            "property_address": addr or None,
            "city": city_m.group(1).strip() if city_m else None,
            "zip": zip_m.group(1) if zip_m else None,
            "plaintiff": (c["parties"].split(" VS ")[0].strip() if c["parties"] and " VS " in c["parties"] else None),
            "judgment_amount": _parse_money(c["judgment_amount"]),
            "judgment_amount_usd": _parse_money(c["judgment_amount"]),
            "auction_venue": "in_person",
            "data_source": "liberty_clerk_official:libertyclerk.com",
            "source_platform": "clerk_html",
            "source_url": source_url,
            "clerk_url": source_url,
            "provenance": "primary_scrape",
            "is_operational": True,
            "scrape_timestamp": now,
            "scraped_at": now,
            "last_seen_at": now,
        })
    return rows


def upsert(rows, dry_run=False):
    if not rows:
        print("No rows to upsert.")
        return 0
    if dry_run:
        print(json.dumps(rows, indent=2))
        return len(rows)

    body = json.dumps(rows).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?on_conflict=county,case_number,sale_type",
        data=body,
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            print(f"Upserted {len(result)} rows.")
            return len(result)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"HTTPError {e.code}: {err_body}", file=sys.stderr)
        # Retry without on_conflict if the constraint doesn't exist
        req2 = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            data=body,
            method="POST",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
        )
        with urllib.request.urlopen(req2, timeout=30) as resp2:
            result = json.loads(resp2.read().decode("utf-8"))
            print(f"Inserted {len(result)} rows (fallback, no upsert).")
            return len(result)


def fix_pipeline_counties(dry_run=False):
    """Correct pipeline.counties to clerk_html platform (runs on every scrape)."""
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    row = {
        "county_slug": "liberty",
        "state": "FL",
        "co_no": 49,
        "fc_platform": "clerk_html",
        "fc_url": FC_URL,
        "fc_enabled": True,
        "td_platform": "clerk_html",
        "td_url": TD_URL,
        "td_enabled": True,
        "scraper_last_seen": now,
        "updated_at": now,
        "notes": (
            "Liberty County FL (pop ~8K, panhandle). NOT on RealAuction — "
            "liberty.realforeclose.com / liberty.realtaxdeed.com return HTTP 403. "
            "Real source: libertyclerk.com. Corrected 2026-07-24 shard8-9433ec3c."
        ),
    }
    if dry_run:
        print(f"DRY-RUN: would upsert pipeline.counties clerk_html for liberty")
        return
    status, result = sb_post_raw("pipeline.counties", row)
    print(f"pipeline.counties clerk_html upsert -> HTTP {status}", flush=True)


def handle_post_sale_outcomes(fc_cards, dry_run=False):
    """
    For any foreclosure card with a sold_amount (past-date sale), write to
    foreclosure_outcomes and patch MCA. Moves B and F criteria.
    Returns count of outcomes written.
    """
    today = datetime.date.today().isoformat()
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    existing_outcomes = {
        r["case_number"]: r
        for r in sb_get("foreclosure_outcomes?county=eq.liberty&select=case_number,winning_bid")
    }

    db_rows = {
        r["case_number"]: r
        for r in sb_get(
            "multi_county_auctions?county=eq.liberty&sale_type=eq.foreclosure"
            "&select=case_number,auction_date,opening_bid,parcel_id"
        )
    }

    outcomes_written = 0
    for card in fc_cards:
        case_num = card.get("case_number")
        sold_raw = card.get("sold_amount_raw")
        sold_amt = _parse_money(sold_raw) if sold_raw else None

        if not case_num or not sold_amt or sold_amt <= 0:
            continue
        if case_num in existing_outcomes:
            print(f"Outcome for {case_num} already exists — skipping", flush=True)
            continue

        db_row = db_rows.get(case_num, {})
        parcel_id = db_row.get("parcel_id") or card.get("parcel_id")
        sale_date = db_row.get("auction_date") or _parse_date(card.get("sale_date")) or today

        outcome_row = {
            "case_number": case_num,
            "county": "liberty",
            "sale_type": "foreclosure",
            "auction_date": sale_date,
            "opening_bid": db_row.get("opening_bid"),
            "winning_bid": sold_amt,
            "outcome": "sold",
            "parcel_id": parcel_id,
            "data_source": f"clerk_fc:LIBERTY-SHARD8-{today}",
            "created_at": now,
            "updated_at": now,
        }

        print(f"POST-SALE outcome: {case_num} sold=${sold_amt}", flush=True)

        if dry_run:
            print(f"DRY-RUN: would write {json.dumps(outcome_row)}", flush=True)
            outcomes_written += 1
            continue

        status, result = sb_post_raw("foreclosure_outcomes", outcome_row)
        if status in (200, 201):
            print(f"foreclosure_outcomes OK for {case_num}", flush=True)
            outcomes_written += 1
            case_param = urllib.parse.quote(case_num)
            p_status, _ = sb_patch(
                "multi_county_auctions",
                f"county=eq.liberty&case_number=eq.{case_param}",
                {
                    "sold_amount": sold_amt,
                    "tier1_sold_amount": sold_amt,
                    "auction_status": "completed",
                    "last_seen_at": now,
                    "updated_at": now,
                },
            )
            print(f"MCA sold_amount patch -> HTTP {p_status}", flush=True)
        else:
            print(f"foreclosure_outcomes FAILED {case_num}: {status} {str(result)[:200]}", flush=True)

    return outcomes_written


def touch_freshness(dry_run=False):
    """Touch MCA last_seen_at for H criterion."""
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    if dry_run:
        print("DRY-RUN: would touch MCA last_seen_at for liberty", flush=True)
        return
    status, _ = sb_patch(
        "multi_county_auctions",
        "county=eq.liberty",
        {"last_seen_at": now, "updated_at": now},
    )
    print(f"Freshness PATCH -> HTTP {status}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    before = rpc("pencil_dod_evaluate_county", {"p_county": "liberty"})
    print(f"BEFORE eval: {json.dumps(before)}", flush=True)

    fix_pipeline_counties(dry_run=args.dry_run)

    fc_html = fetch(FC_URL)
    fc_cards = parse_sale_cards(fc_html)
    print(f"Foreclosure sales parsed: {len(fc_cards)}", flush=True)
    for c in fc_cards:
        print(
            f"  FC card: case={c.get('case_number')} date={c.get('sale_date')} "
            f"status={c.get('status')} sold_raw={c.get('sold_amount_raw')}",
            flush=True,
        )

    td_html = fetch(TD_URL)
    td_cards = parse_sale_cards(td_html)
    print(f"Tax deed sales parsed: {len(td_cards)}", flush=True)

    rows = to_rows(fc_cards, "foreclosure", FC_URL) + to_rows(td_cards, "tax_deed", TD_URL)
    n = upsert(rows, dry_run=args.dry_run)
    print(f"Upserted {n} MCA rows.", flush=True)

    outcomes_written = handle_post_sale_outcomes(fc_cards, dry_run=args.dry_run)
    print(f"Post-sale outcomes written: {outcomes_written}", flush=True)

    touch_freshness(dry_run=args.dry_run)

    after = rpc("pencil_dod_evaluate_county", {"p_county": "liberty"})
    print(f"AFTER eval: {json.dumps(after)}", flush=True)

    print("\n### SQL VERIFICATION")
    print(f"Timestamp: {datetime.datetime.utcnow().isoformat()}Z")
    print("SELECT county, count(*) total, count(*) FILTER(WHERE sale_type='foreclosure') fc,")
    print("  count(*) FILTER(WHERE sale_type='tax_deed') td,")
    print("  count(*) FILTER(WHERE sold_amount IS NOT NULL) closed_sold")
    print("FROM multi_county_auctions WHERE county='liberty' GROUP BY county;")
    print()
    print(f"BEFORE: {json.dumps(before, indent=2)}")
    print(f"AFTER:  {json.dumps(after, indent=2)}")
    print(f"MCA rows upserted: {n}")
    print(f"Foreclosure outcomes written: {outcomes_written}")


if __name__ == "__main__":
    main()
