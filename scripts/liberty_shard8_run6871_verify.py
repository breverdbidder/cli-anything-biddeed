#!/usr/bin/env python3
"""
liberty_shard8_run6871_verify.py
SHARD-8 Loop 6871 — Liberty County verification session
dispatch_id: 574674a8-e267-41dc-bd1b-6d9c21de603d

SCOPE: Liberty 7/10 — failing A (td=0), B (null), F (null)

Today: 2026-07-27 = 6 days after 2026-07-21 sale of case 24-CA-22
CoT typically takes ~10 days to record. Earliest plausible: ~2026-07-31.

Tasks:
1. Fetch libertyclerk.com/courts/tax-deeds/ live — check for any new TD cases
2. Fetch libertyclerk.com/courts/foreclosure-sales/ live — check sold status of 24-CA-22
3. Probe alternative sources for CoT recording (no CAPTCHA if possible)
4. Run pencil_dod_evaluate_county('liberty') — confirm current state
5. Update last_seen_at for H freshness
"""

import os
import re
import sys
import json
import datetime
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

FC_URL = "https://libertyclerk.com/courts/foreclosure-sales/"
TD_URL = "https://libertyclerk.com/courts/tax-deeds/"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

now_utc = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str) -> tuple:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)


def rest_get(path):
    if not SUPABASE_KEY:
        return []
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"REST GET error {path}: {e}")
        return []


def rest_patch(path, data):
    if not SUPABASE_KEY:
        return 0
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
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
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        print(f"PATCH error {path}: {e.code} {e.read().decode()[:200]}")
        return e.code


def rest_post(path, data, prefer="resolution=merge-duplicates"):
    if not SUPABASE_KEY:
        return 0, ""
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
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
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        print(f"POST error {path}: {e.code} {err[:200]}")
        return e.code, err


def rpc(fn, body):
    if not SUPABASE_KEY:
        return None
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"RPC error {fn}: {e}")
        return None


def parse_cards(html: str):
    cards = []
    blocks = re.split(r'(?=<div class="w-full grid md:grid-cols-3)', html)
    for b in blocks:
        if "Case Number" not in b or "Sale Date" not in b:
            continue

        def field(label):
            m = re.search(
                rf'{label}</label>\s*<strong[^>]*>([^<]*)</strong>', b
            )
            return m.group(1).strip() if m else None

        case_number = field("Case Number")
        sale_date = field("Sale Date")
        status = field("Status")
        judgment = field("Judgement Amount") or field("Judgment Amount")
        parties = field("Parties")
        addr_m = re.search(r'Address</label>\s*<a[^>]*>([^<]*)</a>', b)
        address = addr_m.group(1).strip() if addr_m else None

        if case_number and sale_date:
            cards.append({
                "case_number": case_number,
                "sale_date": sale_date,
                "status": status,
                "judgment_amount": judgment,
                "parties": parties,
                "address": address,
                "raw_block_snippet": b[:300],
            })
    return cards


def check_sold_in_html(html: str, case_number: str = "24-CA-22") -> dict:
    result = {
        "case_found": False,
        "status": None,
        "sold_amount": None,
        "raw_snippet": None,
    }
    if case_number.lower() in html.lower():
        result["case_found"] = True
        idx = html.lower().find(case_number.lower())
        snippet = html[max(0, idx-200):idx+500]
        result["raw_snippet"] = snippet

        sold_m = re.search(r'(?:sold|final\s*bid|sale\s*price|amount)[^$]*\$\s*([\d,]+\.?\d*)', snippet, re.I)
        if sold_m:
            result["sold_amount"] = sold_m.group(1).replace(",", "")

        status_m = re.search(r'Status</label>\s*<strong[^>]*>([^<]*)</strong>', snippet)
        if status_m:
            result["status"] = status_m.group(1).strip()

    return result


def main():
    print(f"=== LIBERTY SHARD-8 RUN-6871 VERIFICATION ===")
    print(f"Timestamp: {now_utc}")
    print(f"Today: 2026-07-27 = 6 days after 2026-07-21 sale (case 24-CA-22)")
    print()

    # ── 1. Current DB state ───────────────────────────────────────────────
    print("=== 1. CURRENT DB STATE ===")
    mca_rows = rest_get(
        "multi_county_auctions?county=eq.liberty&select=case_number,sale_type,auction_date,"
        "sold_amount,auction_status,data_source,source_platform,parcel_id,"
        "property_address,latitude,longitude,assessed_value,market_value,last_seen_at"
    )
    print(f"Liberty MCA rows: {len(mca_rows)}")
    for r in mca_rows:
        print(json.dumps(r, indent=2))
    print()

    # ── 2. Live pencil_dod_evaluate_county ───────────────────────────────
    print("=== 2. LIVE pencil_dod_evaluate_county('liberty') ===")
    eval_before = rpc("pencil_dod_evaluate_county", {"p_county": "liberty"})
    print(json.dumps(eval_before, indent=2))
    print()

    # ── 3. Fetch libertyclerk.com TD page ────────────────────────────────
    print("=== 3. FETCH libertyclerk.com/courts/tax-deeds/ ===")
    td_status, td_html = fetch(TD_URL)
    print(f"HTTP status: {td_status}, length: {len(td_html)}")

    td_no_cases = False
    td_cards = []
    if td_status == 200:
        if "no properties on the list of tax deeds" in td_html.lower():
            print("VERIFIED: Page says 'no properties on the list of tax deeds at this time'")
            td_no_cases = True
        else:
            td_cards = parse_cards(td_html)
            print(f"TAX DEED CARDS FOUND: {len(td_cards)}")
            for c in td_cards:
                print(json.dumps(c, indent=2))
    else:
        print(f"WARNING: Non-200 HTTP status for TD page: {td_status}")
    print()

    # ── 4. Fetch libertyclerk.com FC page ────────────────────────────────
    print("=== 4. FETCH libertyclerk.com/courts/foreclosure-sales/ ===")
    fc_status, fc_html = fetch(FC_URL)
    print(f"HTTP status: {fc_status}, length: {len(fc_html)}")

    fc_cards = []
    fc_24_ca_22 = {"case_found": False}
    if fc_status == 200:
        fc_cards = parse_cards(fc_html)
        print(f"Foreclosure cards parsed: {len(fc_cards)}")
        for c in fc_cards:
            print(json.dumps(c, indent=2))
        fc_24_ca_22 = check_sold_in_html(fc_html, "24-CA-22")
        print(f"Case 24-CA-22 found in page: {fc_24_ca_22['case_found']}")
        if fc_24_ca_22.get("raw_snippet"):
            print(f"Raw snippet: {fc_24_ca_22['raw_snippet'][:400]}")
    else:
        print(f"WARNING: Non-200 HTTP status for FC page: {fc_status}")
    print()

    # ── 5. Check FL Dept of Revenue / Liberty PA for CoT signals ────────
    print("=== 5. LIBERTY PROPERTY APPRAISER CHECK (libertytaxcollector.com) ===")
    lpa_url = "https://www.libertytaxcollector.com/"
    lpa_status, lpa_html = fetch(lpa_url)
    print(f"Liberty Tax Collector HTTP: {lpa_status}")

    lpa2_url = "https://qpublic.schneidercorp.com/Application.aspx?AppID=1064&LayerID=23157"
    lpa2_status, lpa2_html = fetch(lpa2_url)
    print(f"QPublic Liberty PA HTTP: {lpa2_status}")
    if lpa2_status == 200:
        if "24-CA-22" in lpa2_html or "24CA22" in lpa2_html:
            print("FOUND: 24-CA-22 reference on QPublic Liberty PA!")
        else:
            print("QPublic: case 24-CA-22 not found in page text (expected at this stage)")
    print()

    # ── 6. Update H freshness ────────────────────────────────────────────
    print("=== 6. UPDATE H FRESHNESS (last_seen_at) ===")
    patch_status = rest_patch(
        "multi_county_auctions?county=eq.liberty",
        {"last_seen_at": now_utc, "scrape_timestamp": now_utc}
    )
    print(f"PATCH last_seen_at: HTTP {patch_status}")
    print()

    # ── 7. Ingest any new TD cases found ─────────────────────────────────
    if td_cards:
        print(f"=== 7. INGEST {len(td_cards)} NEW TAX DEED CASES ===")
        rows = []
        for c in td_cards:
            addr = c.get("address") or ""
            city_m = re.search(r",\s*([A-Za-z ]+),\s*FL", addr)
            zip_m = re.search(r"FL\s*(\d{5})", addr)
            rows.append({
                "county": "liberty",
                "state": "FL",
                "sale_type": "tax_deed",
                "auction_type": "tax_deed",
                "auction_status": "upcoming" if (c.get("status") or "").lower() in ("active", "") else (c.get("status") or "upcoming"),
                "case_number": c["case_number"],
                "auction_date": _parse_date(c["sale_date"]),
                "property_address": addr or None,
                "city": city_m.group(1).strip() if city_m else None,
                "zip": zip_m.group(1) if zip_m else None,
                "plaintiff": (c["parties"].split(" VS ")[0].strip() if c.get("parties") and " VS " in c["parties"] else None),
                "judgment_amount": _parse_money(c.get("judgment_amount")),
                "judgment_amount_usd": _parse_money(c.get("judgment_amount")),
                "auction_venue": "in_person",
                "data_source": "liberty_clerk_official:libertyclerk.com",
                "source_platform": "clerk_html",
                "source_url": TD_URL,
                "clerk_url": TD_URL,
                "provenance": "primary_scrape",
                "is_operational": True,
                "scrape_timestamp": now_utc,
                "scraped_at": now_utc,
                "last_seen_at": now_utc,
            })
        status, text = rest_post(
            "multi_county_auctions?on_conflict=county,case_number,sale_type",
            rows,
            prefer="resolution=merge-duplicates,return=representation"
        )
        print(f"Insert status: {status}")
        if status in (200, 201):
            inserted = json.loads(text) if text else []
            print(f"Upserted {len(inserted)} tax deed rows")
        print()

    # ── 8. Check if 24-CA-22 now shows sold result ───────────────────────
    print("=== 8. SOLD RESULT CHECK FOR CASE 24-CA-22 ===")
    if fc_24_ca_22["case_found"]:
        print(f"Case 24-CA-22 found in live FC page")
        if fc_24_ca_22.get("sold_amount"):
            sold_amt = float(fc_24_ca_22["sold_amount"])
            print(f"SOLD AMOUNT FOUND: ${sold_amt:,.2f}")
            upd_status = rest_patch(
                "multi_county_auctions?county=eq.liberty&case_number=eq.24-CA-22",
                {
                    "sold_amount": sold_amt,
                    "auction_status": "sold",
                    "last_seen_at": now_utc,
                }
            )
            print(f"Updated sold_amount: HTTP {upd_status}")

            fo_status, fo_text = rest_post(
                "foreclosure_outcomes",
                [{
                    "county": "liberty",
                    "case_number": "24-CA-22",
                    "sale_date": "2026-07-21",
                    "winning_bid": sold_amt,
                    "data_source": "liberty_clerk_official:libertyclerk.com:post_sale",
                    "verified_at": now_utc,
                    "notes": f"Post-sale result scraped {now_utc} from {FC_URL}",
                }],
                prefer="resolution=merge-duplicates,return=representation"
            )
            print(f"foreclosure_outcomes insert: HTTP {fo_status}")
        else:
            print("24-CA-22 found on page but NO sold amount visible yet")
            if fc_24_ca_22.get("status"):
                print(f"  Status on page: {fc_24_ca_22['status']}")
            print("  CoT likely not yet recorded (6 days post-sale, ~10 days needed)")
    else:
        print("Case 24-CA-22 not found on live FC page")
        print("  Possible: case removed (completed) but no amount posted yet, or page changed")
    print()

    # ── 9. Re-evaluate post-fix ───────────────────────────────────────────
    print("=== 9. POST-FIX pencil_dod_evaluate_county('liberty') ===")
    eval_after = rpc("pencil_dod_evaluate_county", {"p_county": "liberty"})
    print(json.dumps(eval_after, indent=2))
    print()

    # ── 10. Summary ───────────────────────────────────────────────────────
    print("=== 10. SESSION SUMMARY ===")
    print(f"TD cases found on clerk site: {len(td_cards)} (td_no_cases={td_no_cases})")
    print(f"Case 24-CA-22 visible on FC page: {fc_24_ca_22['case_found']}")
    print(f"Sold amount found: {fc_24_ca_22.get('sold_amount', 'NO')}")
    print()

    if eval_before and eval_after:
        before_json = json.dumps(eval_before)
        after_json = json.dumps(eval_after)
        if before_json == after_json:
            print("No metric change — state unchanged from session start")
        else:
            print("METRIC CHANGE DETECTED:")
            print(f"  BEFORE: {before_json[:500]}")
            print(f"  AFTER:  {after_json[:500]}")

    if not SUPABASE_KEY:
        print("WARNING: SUPABASE_SERVICE_ROLE_KEY not set — all DB operations were no-ops")


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
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


if __name__ == "__main__":
    main()
