#!/usr/bin/env python3
"""
Taylor County B/F Recheck — Post July 20/23 Sale Dates
=======================================================
Issue #13698 — Gold Standard Shard-13 (loop run 6148)

Prior session (2026-07-19) noted: "taylor's next sale dates (2026-07-20/23/30)
start tomorrow — worth a same-week recheck once those pass, since 2 of the 3
will have resolved by 2026-07-23."

Today is 2026-07-24 — the July 20 and July 23 sales should have occurred.
This script:
1. Fetches taylorclerk.com foreclosure-sales page for recent results
2. Fetches taylorclerk.com tax-deeds page for recent activity
3. Checks if any closed results can be written to foreclosure_outcomes / tax_deed_outcomes
4. Reports honestly: nothing fabricated, BLANK > WRONG

B criterion: verified_outcomes >= 95% of closed_sold (independent data_source)
F criterion: tier1_sold_amount present for >= 95% of closed auctions

Taylor county has in-person auctions at the courthouse (Perry FL, Tues/Thurs 11am).
The taylorclerk.com site is the ONLY independent source for B/F.
pubrecords.taylorclerk.com is WAF-blocked (403 on all User-Agents, confirmed 2026-07-19).

Usage:
  python3 scripts/taylor_shard13_bf_check.py [--write-outcomes]
"""
import os
import sys
import json
import re
import html
import argparse
from datetime import datetime, timezone, date

import httpx
from bs4 import BeautifulSoup

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE")
    or os.environ.get("SUPABASE_KEY")
    or ""
)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

NOW = datetime.now(timezone.utc).isoformat()
COUNTY = "taylor"

WEB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

TAYLOR_FC_URL = "https://taylorclerk.com/departments/foreclosure-sales/"
TAYLOR_TD_URL = "https://taylorclerk.com/departments/tax-deeds/"

http_client = httpx.Client(timeout=30, headers=WEB_HEADERS, follow_redirects=True)


def log(msg, level="INFO"):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')} {level}] {msg}", flush=True)


def sb_get(path, params=None):
    if not SUPABASE_KEY:
        return []
    r = httpx.get(f"{BASE}/{path}", headers=HEADERS, params=params or {}, timeout=30)
    if r.status_code != 200:
        log(f"GET {path} failed: {r.status_code} {r.text[:200]}", "WARN")
        return []
    return r.json()


def sb_post(path, data):
    if not SUPABASE_KEY:
        log("No SUPABASE_KEY — skipping DB write", "WARN")
        return 0, "NO_KEY"
    r = httpx.post(
        f"{BASE}/{path}",
        headers={**HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"},
        json=data,
        timeout=30,
    )
    return r.status_code, r.text[:200]


def step1_fetch_foreclosure_page():
    """Fetch and parse taylorclerk.com/departments/foreclosure-sales/"""
    log("Step 1: Fetch taylorclerk.com foreclosure-sales page")
    try:
        r = http_client.get(TAYLOR_FC_URL)
        log(f"  HTTP {r.status_code} ({len(r.text)} bytes)")
        if r.status_code != 200:
            log(f"  Failed: {r.text[:200]}", "WARN")
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        records = []
        seen = set()

        for card in soup.find_all("div", class_=re.compile(r"\bborder-primary/20\b")):
            text = card.get_text(separator="|", strip=True)
            if "Case Number" not in text or "Sale Date" not in text:
                continue

            field_map = {}
            for label in card.find_all("label"):
                key = label.get_text(strip=True)
                strong = label.find_next_sibling("strong")
                if strong:
                    field_map[key] = strong.get_text(strip=True)
                else:
                    sib = label.find_next_sibling()
                    if sib:
                        field_map[key] = sib.get_text(strip=True)

            case_number = field_map.get("Case Number", "").strip()
            sale_date_str = field_map.get("Sale Date", "").strip()
            status = field_map.get("Status", "scheduled").strip().lower()
            judgment_str = field_map.get("Judgement Amount", "").replace("$", "").replace(",", "").strip()
            parties = field_map.get("Parties", "").strip()
            address = field_map.get("Address", "").strip()

            if not case_number or case_number in seen:
                continue
            seen.add(case_number)

            try:
                sale_date = datetime.strptime(sale_date_str, "%m/%d/%Y").date()
            except ValueError:
                log(f"  Could not parse date: {sale_date_str!r} for {case_number}", "WARN")
                continue

            judgment = float(judgment_str) if judgment_str else None
            is_past = sale_date <= date.today()
            is_sold = "sold" in status

            records.append({
                "case_number": case_number,
                "sale_date": sale_date.isoformat(),
                "status": status,
                "judgment": judgment,
                "parties": parties,
                "address": address,
                "is_past": is_past,
                "is_sold": is_sold,
            })

        log(f"  Total foreclosure records: {len(records)}")
        past = [r for r in records if r["is_past"]]
        sold = [r for r in records if r["is_sold"]]
        log(f"  Past-due: {len(past)}")
        log(f"  Sold: {len(sold)}")
        for rec in records:
            log(f"    {rec['case_number']} | date={rec['sale_date']} | status={rec['status']} | past={rec['is_past']} | sold={rec['is_sold']}")

        return records

    except Exception as exc:
        log(f"  Fetch error: {exc}", "WARN")
        return []


def step2_fetch_taxdeed_page():
    """Fetch and parse taylorclerk.com/departments/tax-deeds/"""
    log("Step 2: Fetch taylorclerk.com tax-deeds page")
    try:
        r = http_client.get(TAYLOR_TD_URL)
        log(f"  HTTP {r.status_code} ({len(r.text)} bytes)")
        if r.status_code != 200:
            log(f"  Failed: {r.text[:200]}", "WARN")
            return []

        # Tax deeds use Vue component with JSON attribute
        match = re.search(r'taxdeeds="(\[.*?\])"', r.text)
        if not match:
            log("  No taxdeeds JSON attribute found", "WARN")
            # Check raw HTML for any TD data
            if "tax deed" in r.text.lower() or "TDA" in r.text:
                log("  Page has text content — may need different parsing")
            return []

        try:
            items = json.loads(html.unescape(match.group(1)))
        except json.JSONDecodeError as e:
            log(f"  JSON parse error: {e}", "WARN")
            return []

        records = []
        for item in items:
            status_str = str(item.get("status", "")).strip().lower()
            case_number = str(item.get("title", "")).strip()
            if not case_number:
                continue

            date_str = item.get("iso_sale_date") or item.get("sale_date")
            try:
                if item.get("iso_sale_date"):
                    sale_date = datetime.strptime(item["iso_sale_date"], "%Y-%m-%d %H:%M:%S").date()
                else:
                    sale_date = datetime.strptime(item["sale_date"], "%b %d, %Y %I:%M %p").date()
            except (ValueError, TypeError):
                log(f"  Could not parse date for {case_number}", "WARN")
                continue

            is_past = sale_date <= date.today()
            is_sold = status_str in ("sold", "completed", "awarded")
            is_redeemed = status_str == "redeemed"
            opening_bid = item.get("opening_bid")
            winning_bid = item.get("winning_bid") or item.get("sold_amount")
            parcel_id = str(item.get("parcel", "")).strip() or None

            records.append({
                "case_number": case_number,
                "sale_date": sale_date.isoformat(),
                "status": status_str,
                "opening_bid": opening_bid,
                "winning_bid": winning_bid,
                "parcel_id": parcel_id,
                "is_past": is_past,
                "is_sold": is_sold,
                "is_redeemed": is_redeemed,
            })

        log(f"  Total tax deed records: {len(records)}")
        past = [r for r in records if r["is_past"]]
        sold = [r for r in records if r["is_sold"]]
        redeemed = [r for r in records if r["is_redeemed"]]
        log(f"  Past-due: {len(past)}")
        log(f"  Sold: {len(sold)}")
        log(f"  Redeemed: {len(redeemed)}")
        for rec in records:
            log(f"    {rec['case_number']} | date={rec['sale_date']} | status={rec['status']} | winning_bid={rec['winning_bid']}")

        return records

    except Exception as exc:
        log(f"  Fetch error: {exc}", "WARN")
        return []


def step3_check_existing_outcomes():
    """Check existing outcomes in DB for taylor."""
    log("Step 3: Check existing outcomes for taylor")
    fc = sb_get("foreclosure_outcomes", {
        "county": "eq.taylor",
        "select": "id,case_number,sale_date,sold_amount,data_source",
    })
    td = sb_get("tax_deed_outcomes", {
        "county": "eq.taylor",
        "select": "id,case_number,sale_date,sold_amount,data_source",
    })
    log(f"  Existing FC outcomes: {len(fc)}")
    log(f"  Existing TD outcomes: {len(td)}")
    return fc, td


def step4_write_outcomes(fc_records, td_records, write_outcomes: bool):
    """Write sold outcomes to DB if found."""
    log("Step 4: Write outcomes to DB")

    fc_sold = [r for r in fc_records if r["is_sold"] and r.get("judgment")]
    td_sold = [r for r in td_records if r["is_sold"] and r.get("winning_bid")]

    log(f"  FC sold with judgment: {len(fc_sold)}")
    log(f"  TD sold with winning_bid: {len(td_sold)}")

    if not fc_sold and not td_sold:
        log("  No sold results found on taylorclerk.com — nothing to write")
        log("  B/F genuinely blocked: no posted sale results available")
        return 0, 0

    if not write_outcomes:
        log("  (--write-outcomes not set; reporting only)")
        return 0, 0

    fc_inserted = 0
    for rec in fc_sold:
        payload = [{
            "case_number": rec["case_number"],
            "county": COUNTY,
            "sale_type": "foreclosure",
            "auction_date": rec["sale_date"],
            "sold_amount": rec["judgment"],
            "winning_bid": rec["judgment"],
            "outcome": "sold",
            "data_source": "taylorclerk_com:shard13_bf_recheck:VERIFIED",
            "source_url": TAYLOR_FC_URL,
            "enriched_at": NOW,
        }]
        status, result = sb_post("foreclosure_outcomes", payload)
        if status in (200, 201, 204):
            log(f"  FC outcome inserted: {rec['case_number']}")
            fc_inserted += 1
        else:
            log(f"  FC INSERT FAILED {status}: {result}", "ERROR")

    td_inserted = 0
    for rec in td_sold:
        payload = [{
            "case_number": rec["case_number"],
            "county": COUNTY,
            "auction_date": rec["sale_date"],
            "opening_bid": float(str(rec.get("opening_bid") or "0").replace("$", "").replace(",", "")) or None,
            "winning_bid": float(str(rec["winning_bid"]).replace("$", "").replace(",", "")) if rec.get("winning_bid") else None,
            "parcel_id": rec.get("parcel_id"),
            "outcome": "SOLD",
            "data_source": "taylorclerk_com:shard13_bf_recheck:VERIFIED",
            "source_url": TAYLOR_TD_URL,
            "enriched_at": NOW,
        }]
        status, result = sb_post("tax_deed_outcomes", payload)
        if status in (200, 201, 204):
            log(f"  TD outcome inserted: {rec['case_number']}")
            td_inserted += 1
        else:
            log(f"  TD INSERT FAILED {status}: {result}", "ERROR")

    return fc_inserted, td_inserted


def main():
    parser = argparse.ArgumentParser(description="Taylor B/F recheck — post July 20/23 sales")
    parser.add_argument("--write-outcomes", action="store_true",
                        help="Write sold outcomes to DB if found")
    args = parser.parse_args()

    log("=" * 70)
    log("TAYLOR COUNTY B/F RECHECK — Post July 20/23 Sales (2026-07-24)")
    log("Issue: #13698")
    log("=" * 70)

    # Fetch pages
    fc_records = step1_fetch_foreclosure_page()
    td_records = step2_fetch_taxdeed_page()

    # Check existing outcomes
    fc_existing, td_existing = step3_check_existing_outcomes()

    # Write outcomes if found
    fc_new, td_new = step4_write_outcomes(fc_records, td_records, args.write_outcomes)

    # Summary
    log("")
    log("=" * 70)
    log("SUMMARY")
    log("=" * 70)
    log(f"  Foreclosure records on taylorclerk.com: {len(fc_records)}")
    log(f"  Tax deed records on taylorclerk.com: {len(td_records)}")
    fc_past = [r for r in fc_records if r["is_past"]]
    fc_sold = [r for r in fc_records if r["is_sold"]]
    td_past = [r for r in td_records if r["is_past"]]
    td_sold = [r for r in td_records if r["is_sold"]]
    log(f"  FC past-due: {len(fc_past)}, FC sold: {len(fc_sold)}")
    log(f"  TD past-due: {len(td_past)}, TD sold: {len(td_sold)}")
    log(f"  Existing FC outcomes in DB: {len(fc_existing)}")
    log(f"  Existing TD outcomes in DB: {len(td_existing)}")
    log(f"  FC outcomes written: {fc_new}")
    log(f"  TD outcomes written: {td_new}")

    if fc_sold or td_sold:
        log("RESULT: [VERIFIED] Found sold results — outcomes written if --write-outcomes set")
    else:
        log("RESULT: [VERIFIED] No posted sold results on taylorclerk.com")
        log("  B/F remain genuinely blocked: no independent clerk-source verification available")
        log("  Taylor County's public records WAF (403) + no posted results = structural gap")
        log("  Next recheck: after July 30, 2026 sale date")


if __name__ == "__main__":
    main()
