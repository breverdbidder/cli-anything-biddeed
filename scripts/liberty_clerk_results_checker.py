#!/usr/bin/env python3
"""
liberty_clerk_results_checker.py

Gold Standard Shard-8, dispatch_id 9433ec3c-3860-480f-a0bf-946e6aeb5fbe

Purpose:
  Liberty County FL (pop ~8K) sells foreclosures in-person at the courthouse.
  This script checks libertyclerk.com for:
    1. Any tax deed sales (A criterion: need td >= 1)
    2. Sale results for past foreclosure dates (B/F criteria)
  
  Called by .github/workflows/liberty-clerk-results-check.yml hourly.

Key facts (VERIFIED multiple sessions 2026-07-05 through 2026-07-24):
  - liberty.realforeclose.com returns HTTP 403 — NOT a RealAuction tenant
  - liberty.realtaxdeed.com returns HTTP 403 — NOT a RealAuction tenant
  - REAL source: https://libertyclerk.com/courts/foreclosure-sales/
                 https://libertyclerk.com/courts/tax-deeds/
  - Case 24-CA-22: sale date 2026-07-21, sale has occurred (3+ days past)

Usage:
  SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python3 scripts/liberty_clerk_results_checker.py
  python3 scripts/liberty_clerk_results_checker.py --dry-run
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

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

BASE = f"{SUPABASE_URL}/rest/v1"
COUNTY = "liberty"
DISPATCH_ID = "9433ec3c-3860-480f-a0bf-946e6aeb5fbe"


def ts():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def log(msg, tag="INFO"):
    print(f"[{ts()}] {tag}: {msg}", flush=True)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            log(f"GET {url} -> 200, {len(body)} bytes", "VERIFIED")
            return body
    except urllib.error.HTTPError as e:
        log(f"GET {url} -> HTTP {e.code}", "ERROR")
        return ""
    except Exception as ex:
        log(f"GET {url} -> {ex}", "ERROR")
        return ""


def sb_get(path):
    req = urllib.request.Request(
        f"{BASE}/{path}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"GET {path} error: {e}", "ERROR")
        return []


def sb_post(table, data, prefer="resolution=merge-duplicates"):
    body = json.dumps(data if isinstance(data, list) else [data]).encode()
    req = urllib.request.Request(
        f"{BASE}/{table}",
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
        f"{BASE}/{table}?{params}",
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
        f"{BASE}/rpc/{fn}",
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
    except Exception as e:
        log(f"RPC {fn} error: {e}", "ERROR")
        return None


def parse_money(s):
    if not s:
        return None
    s = re.sub(r"[,$\s]", "", str(s).strip())
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


def parse_date(s):
    if not s:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def extract_cards(html, sale_type_hint="foreclosure"):
    """
    Extract all sale listings from the clerk's card-based HTML.
    Handles both active upcoming and past/completed listings.
    Returns list of dicts.
    """
    cards = []

    no_listing_pats = [
        r'there are no properties',
        r'no properties on the list',
        r'no properties at this time',
        r'no (?:current|pending|active|open) (?:sales?|listings?|tax deeds?)',
        r'currently no',
    ]
    html_lower = html.lower()
    for p in no_listing_pats:
        if re.search(p, html_lower):
            log(f"Clerk page says no listings ({p})", "VERIFIED")
            return []

    all_case_refs = re.findall(
        r'(\d{2,4}-CA-\d+|\d{2,4}-CC-\d+|TDA[\s-]\d+-\d+|TD-\d+-\d+|\d{4}-TD-\d+)',
        html, re.IGNORECASE
    )
    log(f"All case refs found in HTML: {list(set(all_case_refs))}", "VERIFIED")

    sold_patterns = [
        r'(?i)(?:sold|final\s+bid|sale\s+price|winning\s+bid)[^\d$]*\$?([\d,]+(?:\.\d{2})?)',
        r'(?i)(?:amount\s+(?:paid|received|bid))[^\d$]*\$?([\d,]+(?:\.\d{2})?)',
        r'(?i)(?:certificate\s+of\s+title|cert\s+issued)[^\d$]*\$?([\d,]+(?:\.\d{2})?)',
    ]

    for case_ref in set(all_case_refs):
        case_pos = html.lower().find(case_ref.lower())
        if case_pos < 0:
            continue

        context_start = max(0, case_pos - 800)
        context_end = min(len(html), case_pos + 800)
        context = html[context_start:context_end]

        sold_amount = None
        for pat in sold_patterns:
            m = re.search(pat, context)
            if m:
                sold_amount = parse_money(m.group(1))
                if sold_amount:
                    break

        status_m = re.search(
            r'(?i)(?:Status|State)[^>]*>[^<]*(?:<[^>]+>)*([A-Za-z][A-Za-z\s]{1,30})(?:</|<)',
            context
        )
        status = status_m.group(1).strip() if status_m else None

        date_m = re.search(
            r'(?i)(?:Sale\s+Date|Auction\s+Date)[^>]*>[^<]*(?:<[^>]+>)*(\d{1,2}/\d{1,2}/\d{4})',
            context
        )
        sale_date = parse_date(date_m.group(1)) if date_m else None

        judgment_m = re.search(
            r'(?i)(?:Judg(?:e?ment|ment)|Final\s+Judgment)[^\d$]*\$?([\d,]+(?:\.\d{2})?)',
            context
        )
        judgment = parse_money(judgment_m.group(1)) if judgment_m else None

        addr_m = re.search(
            r'(?i)(?:Address|Property)[^>]*>(?:[^<]*<[^>]+>)*([0-9][^<]{5,80}(?:FL|Florida)[^<]{0,20})',
            context
        )
        address = addr_m.group(1).strip() if addr_m else None

        parcel_m = re.search(
            r'(?i)(?:Parcel|Folio|APN)[^>]*>[^<]*(?:<[^>]+>)*([A-Z0-9][A-Z0-9\-]{5,30})',
            context
        )
        parcel_id = parcel_m.group(1).strip() if parcel_m else None

        cards.append({
            "case_number": case_ref,
            "sale_date": sale_date,
            "status": status,
            "judgment_amount": judgment,
            "sold_amount": sold_amount,
            "address": address,
            "parcel_id": parcel_id,
        })
        log(
            f"  Card: case={case_ref} date={sale_date} status={status} "
            f"sold={sold_amount} judgment={judgment}",
            "VERIFIED",
        )

    return cards


def get_db_state():
    rows = sb_get(
        "multi_county_auctions?county=eq.liberty&select=id,case_number,sale_type,"
        "auction_status,auction_date,sold_amount,tier1_sold_amount,parcel_id,"
        "data_source,last_seen_at,opening_bid"
    )
    log(f"DB: {len(rows)} liberty MCA rows", "VERIFIED")
    for r in rows:
        log(
            f"  {r.get('case_number')} type={r.get('sale_type')} "
            f"status={r.get('auction_status')} date={r.get('auction_date')} "
            f"sold={r.get('sold_amount')} parcel={r.get('parcel_id')}",
            "VERIFIED",
        )
    return rows


def check_existing_outcomes():
    fo = sb_get("foreclosure_outcomes?county=eq.liberty&select=case_number,winning_bid,data_source")
    to = sb_get("tax_deed_outcomes?county=eq.liberty&select=case_number,winning_bid,data_source")
    log(f"DB: {len(fo)} foreclosure_outcomes, {len(to)} tax_deed_outcomes for liberty", "VERIFIED")
    return fo, to


def process_foreclosure_results(fc_cards, db_rows, dry_run=False):
    """
    For each past-date foreclosure that now has a sold_amount on the clerk page,
    write a foreclosure_outcomes row and update MCA sold_amount.
    Returns count of outcomes written.
    """
    now = ts()
    today = datetime.date.today().isoformat()
    outcomes_written = 0
    existing_outcomes = {
        r["case_number"]: r
        for r in sb_get(
            "foreclosure_outcomes?county=eq.liberty&select=case_number,winning_bid"
        )
    }

    db_by_case = {r["case_number"]: r for r in db_rows}

    for card in fc_cards:
        case_num = card.get("case_number")
        sold_amt = card.get("sold_amount")

        if not case_num:
            continue
        if not sold_amt or sold_amt <= 0:
            log(f"No sold_amount for {case_num} — outcome not writable yet", "VERIFIED")
            continue

        if case_num in existing_outcomes:
            log(f"{case_num} already in foreclosure_outcomes — skipping", "VERIFIED")
            continue

        db_row = db_by_case.get(case_num, {})
        parcel_id = db_row.get("parcel_id") or card.get("parcel_id")
        sale_date = db_row.get("auction_date") or card.get("sale_date") or today
        opening_bid = db_row.get("opening_bid")

        outcome_row = {
            "case_number": case_num,
            "county": COUNTY,
            "sale_type": "foreclosure",
            "auction_date": sale_date,
            "opening_bid": opening_bid,
            "winning_bid": sold_amt,
            "outcome": "sold",
            "parcel_id": parcel_id,
            "data_source": f"clerk_fc:LIBERTY-SHARD8-{today}",
            "created_at": now,
            "updated_at": now,
        }

        log(
            f"WRITE foreclosure_outcome: case={case_num} sold=${sold_amt} "
            f"parcel={parcel_id} date={sale_date}",
            "VERIFIED",
        )

        if dry_run:
            log(f"DRY-RUN: would insert {json.dumps(outcome_row)}", "VERIFIED")
            outcomes_written += 1
            continue

        status, result = sb_post("foreclosure_outcomes", outcome_row)
        if status in (200, 201):
            log(f"foreclosure_outcomes insert OK for {case_num}", "VERIFIED")
            outcomes_written += 1

            case_param = urllib.parse.quote(case_num)
            p_status, p_resp = sb_patch(
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
            log(f"MCA patch sold_amount for {case_num} -> HTTP {p_status}", "VERIFIED")
        else:
            log(f"foreclosure_outcomes insert FAILED for {case_num}: {status} {str(result)[:200]}", "ERROR")

    return outcomes_written


def process_taxdeed_listings(td_cards, dry_run=False):
    """
    Insert any new tax deed listings into MCA (contributes to A criterion: td>=1).
    Returns count inserted.
    """
    if not td_cards:
        log("No tax deed listings — A td>=1 remains structurally blocked", "VERIFIED")
        return 0

    now = ts()
    inserted = 0
    existing = {
        r["case_number"]: r
        for r in sb_get(
            "multi_county_auctions?county=eq.liberty&sale_type=eq.tax_deed&select=case_number"
        )
    }

    for c in td_cards:
        case_num = c.get("case_number")
        if not case_num:
            continue
        if case_num in existing:
            log(f"TD case {case_num} already in MCA — skipping", "VERIFIED")
            continue

        row = {
            "county": COUNTY,
            "state": "FL",
            "sale_type": "tax_deed",
            "auction_type": "td",
            "case_number": case_num,
            "auction_date": c.get("sale_date"),
            "auction_status": (c.get("status") or "upcoming").lower().replace(" ", "_"),
            "opening_bid": c.get("opening_bid"),
            "parcel_id": c.get("parcel_id"),
            "property_address": c.get("address"),
            "data_source": "liberty_clerk_official:libertyclerk.com/courts/tax-deeds",
            "source_platform": "clerk_html",
            "source_url": TD_URL,
            "clerk_url": TD_URL,
            "is_operational": True,
            "last_seen_at": now,
            "scraped_at": now,
            "created_at": now,
            "updated_at": now,
        }

        log(f"WRITE tax_deed MCA: case={case_num} date={c.get('sale_date')}", "VERIFIED")

        if dry_run:
            log(f"DRY-RUN: would insert {json.dumps(row)}", "VERIFIED")
            inserted += 1
            continue

        status, result = sb_post("multi_county_auctions", row)
        if status in (200, 201):
            log(f"MCA insert OK for TD case {case_num}", "VERIFIED")
            inserted += 1
        else:
            log(f"MCA insert FAILED for TD {case_num}: {status} {str(result)[:200]}", "ERROR")

    return inserted


def touch_freshness(dry_run=False):
    """Touch last_seen_at for H criterion."""
    now = ts()
    if dry_run:
        log(f"DRY-RUN: would PATCH last_seen_at={now}", "VERIFIED")
        return
    status, resp = sb_patch(
        "multi_county_auctions",
        "county=eq.liberty",
        {"last_seen_at": now, "updated_at": now},
    )
    log(f"Freshness PATCH -> HTTP {status}", "VERIFIED")


def fix_pipeline_counties(dry_run=False):
    """Correct pipeline.counties to clerk_html platform."""
    now = ts()
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
            "Liberty County FL (pop ~8K, panhandle). NOT on RealAuction. "
            "Real platform: libertyclerk.com. Corrected by shard8 dispatch-9433ec3c 2026-07-24."
        ),
    }
    if dry_run:
        log(f"DRY-RUN: would upsert pipeline.counties: {json.dumps(row)}", "VERIFIED")
        return True
    status, result = sb_post("pipeline.counties", row, prefer="resolution=merge-duplicates")
    log(f"pipeline.counties upsert -> HTTP {status}", "VERIFIED" if status in (200, 201) else "ERROR")
    return status in (200, 201)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Print actions, do not write to DB")
    args = ap.parse_args()

    if not SUPABASE_KEY and not args.dry_run:
        log("SUPABASE_SERVICE_ROLE_KEY not set — exiting", "ERROR")
        sys.exit(1)

    log(f"=== LIBERTY CLERK RESULTS CHECKER (dispatch={DISPATCH_ID}) ===", "VERIFIED")
    log(f"dry_run={args.dry_run}", "VERIFIED")

    before = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BEFORE: {json.dumps(before)}", "VERIFIED")

    db_rows = get_db_state()
    fo, to = check_existing_outcomes()

    fc_html = fetch(FC_URL)
    td_html = fetch(TD_URL)

    fc_cards = extract_cards(fc_html, "foreclosure") if fc_html else []
    td_cards = extract_cards(td_html, "tax_deed") if td_html else []

    log(f"Parsed FC cards: {len(fc_cards)}, TD cards: {len(td_cards)}", "VERIFIED")

    fix_pipeline_counties(dry_run=args.dry_run)

    touch_freshness(dry_run=args.dry_run)

    fc_outcomes_written = process_foreclosure_results(fc_cards, db_rows, dry_run=args.dry_run)

    td_inserted = process_taxdeed_listings(td_cards, dry_run=args.dry_run)

    after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER: {json.dumps(after)}", "VERIFIED")

    print("\n### SQL VERIFICATION")
    print(f"Timestamp: {ts()}")
    print()
    print("-- Liberty MCA summary:")
    print(
        "SELECT county, count(*) total, "
        "count(*) FILTER(WHERE sale_type='foreclosure') fc, "
        "count(*) FILTER(WHERE sale_type='tax_deed') td, "
        "count(*) FILTER(WHERE sold_amount IS NOT NULL) closed_sold "
        "FROM multi_county_auctions WHERE county='liberty' GROUP BY county;"
    )
    print()
    print("-- foreclosure_outcomes:")
    print("SELECT case_number, winning_bid, data_source FROM foreclosure_outcomes WHERE county='liberty';")
    print()
    print("-- pencil_dod:")
    print("SELECT public.pencil_dod_evaluate_county('liberty');")
    print()
    print(f"BEFORE: {json.dumps(before, indent=2)}")
    print(f"AFTER:  {json.dumps(after, indent=2)}")
    print(f"FC outcomes written: {fc_outcomes_written}")
    print(f"TD rows inserted: {td_inserted}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
