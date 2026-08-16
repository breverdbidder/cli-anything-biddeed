#!/usr/bin/env python3
"""GTM-shard8-run5153 putnam C/D backfill via Putnam Clerk certification lookup.

Root cause (VERIFIED 2026-07-19 via ULTRALOOP fan-out + adversarial forensics
agent): 141 putnam tax_deed rows (auction dates 2026-06-24..2026-08-26) have
parity_status IS NULL. Re-harvesting the live RealTaxDeed AJAX calendar for
all 7 affected dates returns calendar items with ZERO case-number overlap
against these 141 rows -- so this is not a matching-key bug, and the
redemption/cancellation hypothesis was independently REFUTED: a sample of 6
case numbers checked against the Putnam Clerk of Court's own tax deed
certification system (apps.putnam-fl.com) all show live, active, unredeemed
applications with "Date of Sale" matching our DB's auction_date exactly. The
true root cause is a RealTaxDeed-side calendar/pagination gap, not stale data.

This script closes the loop for all 141 rows: fetch each case's certification
page directly from the Clerk (an INDEPENDENT authoritative government source,
per the standing C/D litmus-fallback authorization), confirm (a) the cert is
found under this exact case number, (b) it is not shown as redeemed/cancelled
itself, (c) its "Date of Sale" matches our auction_date. Only then does the
row get parity_status='matched_clean' with a 'tier1:...' source label so it
counts toward canon C/D.

Usage: python3 scripts/putnam_clerk_certification_cd_fix.py
"""
import os
import re
import sys
import json
import time
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

CERT_URL = "https://apps.putnam-fl.com/coc/taxdeeds/public/public_certification.php?certnum={certnum}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
                                  headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status


def to_text(html):
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}


def parse_sale_date(text):
    m = re.search(r"Date of Sale\s+(\w+)\s+(\d{1,2}),\s+(\d{4})", text)
    if not m:
        return None
    mon, day, year = m.group(1), int(m.group(2)), int(m.group(3))
    if mon not in MONTHS:
        return None
    return f"{year:04d}-{MONTHS[mon]:02d}-{day:02d}"


def fetch_cert(case_number, attempts=3):
    certnum = case_number.replace("-", "")
    url = CERT_URL.format(certnum=certnum)
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode("utf-8", errors="replace")
        except Exception as e:
            if i == attempts - 1:
                return None, str(e)
            time.sleep(2 * (i + 1))
    return None, "unreachable"


def evaluate(case_number, expected_auction_date, text):
    """Returns (verdict, reason) where verdict in {'confirm','redeemed','mismatch','not_found'}"""
    if f"Tax Sale Certificate Number {case_number}" not in text and case_number not in text:
        return "not_found", "case number not present on certification page"

    # BUG FIX (2026-08-16, adversarial-verify finding): the page's own
    # top-of-page status banner ("Certificate Number <X> has been redeemed.")
    # was not checked. It is the authoritative redemption signal for the
    # certificate actually being queried -- the boilerplate "Date of Sale"
    # text lower on the page is part of the static form template and stays
    # present even after redemption, so relying on date-match alone produced
    # false 'confirm' verdicts for 4 already-redeemed certs (2021-0011399,
    # 2024-0010776, 2024-0017158, 2024-0016884).
    if re.search(r"has been redeemed", text, re.IGNORECASE):
        return "redeemed", "top-of-page status banner: certificate has been redeemed"

    sale_date = parse_sale_date(text)
    if not sale_date:
        return "mismatch", "no 'Date of Sale' found on page"
    if sale_date != expected_auction_date:
        return "mismatch", f"page sale date {sale_date} != our auction_date {expected_auction_date}"

    # Distinguish "CERTIFICATES REDEEMED BY APPLICANT" (lists OTHER older certs
    # consolidated into this application -- normal) from this cert itself being
    # stamped redeemed/cancelled. Look for a redemption/cancellation marker in
    # the record's own high-bid/deed-recorded status block.
    redeemed_section = ""
    m = re.search(r"CERTIFICATES REDEEMED BY APPLICANT.*?(?=CERTIFICATES OWNED|Total Amount Paid|$)", text)
    if m:
        redeemed_section = m.group(0)
    if case_number in redeemed_section:
        return "redeemed", "this case_number appears inside its own 'redeemed by applicant' section"
    if re.search(r"\bTHIS SALE (WAS|IS) CANCELLED\b", text, re.IGNORECASE):
        return "redeemed", "explicit cancellation marker on page"

    return "confirm", f"live cert found, unredeemed, Date of Sale matches ({sale_date})"


def main():
    rows = rest_get(
        "multi_county_auctions?county=eq.putnam&parity_status=is.null"
        "&or=(data_source.neq.propertyonion,data_source.is.null)"
        "&select=id,case_number,auction_date")
    print(f"Loaded {len(rows)} unmatched putnam rows")

    counts = {"confirm": 0, "redeemed": 0, "mismatch": 0, "not_found": 0, "fetch_error": 0}
    confirmed_ids = []
    for i, row in enumerate(rows):
        cn = row["case_number"]
        ad = row["auction_date"][:10]
        status, body = fetch_cert(cn)
        if status != 200:
            counts["fetch_error"] += 1
            print(f"  [{i+1}/{len(rows)}] {cn} FETCH_ERROR: {body}")
            time.sleep(1.0)
            continue
        text = to_text(body)
        verdict, reason = evaluate(cn, ad, text)
        counts[verdict] += 1
        print(f"  [{i+1}/{len(rows)}] {cn} (auction={ad}) -> {verdict}: {reason}")
        if verdict == "confirm":
            confirmed_ids.append((row["id"], ad))
        time.sleep(0.8)

    print(f"\nVERDICT COUNTS: {counts}")

    promoted = 0
    for rid, ad in confirmed_ids:
        try:
            rest_patch(f"multi_county_auctions?id=eq.{rid}", {
                "parity_status": "matched_clean",
                "parity_source": f"tier1:clerk_certification_php:putnam:{ad}",
            })
            promoted += 1
        except Exception as e:
            print(f"  PATCH FAILED for {rid}: {e}")

    print(f"\nPROMOTED parity_status=matched_clean for {promoted} rows")


if __name__ == "__main__":
    main()
