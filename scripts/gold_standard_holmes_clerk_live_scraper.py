#!/usr/bin/env python3
"""
Holmes County Clerk Live Scraper — Gold Standard Pipeline
=========================================================
Scrapes holmesclerk.com tax-deed and foreclosure notice pages,
upserts new cases to multi_county_auctions, and updates parity_status
for cases found on the live page.

Platform: holmesclerk.com (custom WordPress, no RealAuction).
  TD:  https://holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/
  FC:  https://holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/
  LAT: https://holmesclerk.com/courts/foreclosures-tax-deeds/lands-available-for-taxes/

Notes (confirmed across 4+ sessions, 2026-07-10 through 2026-07-21):
  - holmesclerk.com is a FORWARD-LOOKING notice board. Cases that have
    rolled off (sold or resolved) are REMOVED — no disposition/sold-amount
    data is published anywhere on the site.
  - holmes.realforeclose.com and holmes.realtaxdeed.com: 302-redirect to
    vendor marketing site (unprovisioned accounts). DO NOT use.
  - myfloridacounty.com/orisearch/30: CAPTCHA-gated official-records
    search (cannot be used without browser automation).
  - B/F remain structurally blocked until Firecrawl credits are restored
    or a browser-automation avenue becomes available.

Env:
  SUPABASE_URL (required)
  SUPABASE_SERVICE_ROLE_KEY (required)

Exit codes:
  0 — success (at least 1 card parsed OR all pre-existing)
  1 — fatal error
  2 — FAIL-LOUD: zero cards parsed from either page
"""
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

PAGES = {
    "foreclosure": "https://holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/",
    "tax_deed":    "https://holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/",
    "lat":         "https://holmesclerk.com/courts/foreclosures-tax-deeds/lands-available-for-taxes/",
}

MONTHS = {
    "JANUARY": "01", "FEBRUARY": "02", "MARCH": "03", "APRIL": "04",
    "MAY": "05", "JUNE": "06", "JULY": "07", "AUGUST": "08",
    "SEPTEMBER": "09", "OCTOBER": "10", "NOVEMBER": "11", "DECEMBER": "12",
}

TD_CARD_RE = re.compile(
    r"(TD#[\d\-]+)\s*"
    r"([A-Z][A-Z ,.'&\-]*?)\s*"
    r"PARCEL\s+ID:\s*([\w.\-]+)\s*"
    r"OPENING\s+BID:\s*\$([\w,.TBD*]*)\s*"
    r"SALE\s+DATE:\s*([\d/]+)",
    re.IGNORECASE,
)

FC_CARD_RE = re.compile(
    r"SALE\s+DATE:\s*([A-Z]+ \d{1,2},?\s*\d{4})\s*"
    r"(?:FINAL\s+JUDGMENT\s+AMOUNT:\s*\$([\d,]+(?:\.\d{2})?))?.*?"
    r"PARCEL\s+ID:\s*([\w.\-]+)\s*"
    r"(?:PROPERTY\s+ADDRESS:\s*([^\n$]{5,200?}))?",
    re.DOTALL | re.IGNORECASE,
)


def _req_env(name):
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env: {name}")
    return v


def _fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8", errors="replace")
    stripped = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.S)
    stripped = re.sub(r"<style[^>]*>.*?</style>", "", stripped, flags=re.S)
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    stripped = html.unescape(stripped)
    return re.sub(r"\s+", " ", stripped)


def _parse_td_date(s):
    parts = s.strip().split("/")
    if len(parts) == 3:
        mm, dd, yyyy = parts
        return f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}"
    return None


def _parse_fc_date(s):
    s = s.strip().replace(",", "")
    parts = s.split()
    if len(parts) == 3:
        month_word, dd, yyyy = parts
        mo = MONTHS.get(month_word.upper())
        if mo:
            return f"{yyyy}-{mo}-{int(dd):02d}"
    return None


def _sb_get(base_url, key, table, params):
    url = f"{base_url}/rest/v1/{table}?{params}"
    req = urllib.request.Request(url, headers={
        "apikey": key,
        "Authorization": f"Bearer {key}",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _sb_post(base_url, key, table, rows):
    body = json.dumps(rows).encode()
    req = urllib.request.Request(
        f"{base_url}/rest/v1/{table}",
        data=body,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=ignore-duplicates,return=minimal",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _sb_patch(base_url, key, table, params, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{base_url}/rest/v1/{table}?{params}",
        data=body,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def parse_td_cards(text):
    cards = []
    for m in TD_CARD_RE.finditer(text):
        td_num = m.group(1).strip()
        defendant = m.group(2).strip().rstrip(" ,")
        parcel_id = m.group(3).strip()
        opening_raw = m.group(4).strip().replace(",", "")
        sale_date_raw = m.group(5).strip()

        sale_date = _parse_td_date(sale_date_raw)
        if not sale_date:
            print(f"  SKIP: could not parse TD date {sale_date_raw!r}", file=sys.stderr)
            continue

        opening_bid = None
        if opening_raw and opening_raw not in ("TBD", "*", ""):
            clean = re.sub(r"[*]", "", opening_raw)
            try:
                opening_bid = float(clean) if clean else None
            except ValueError:
                pass

        today = date.today().isoformat()
        cards.append({
            "county":           "holmes",
            "state":            "FL",
            "auction_type":     "tax_deed",
            "sale_type":        "tax_deed",
            "case_number":      td_num,
            "parcel_id":        parcel_id,
            "plaintiff":        defendant,
            "opening_bid":      opening_bid,
            "auction_date":     sale_date,
            "auction_status":   "upcoming" if sale_date >= today else "completed",
            "data_source":      "holmes_clerk",
            "source_platform":  "holmes_clerk",
            "clerk_url":        PAGES["tax_deed"],
        })
    return cards


def parse_fc_cards(text):
    cards = []
    for m in FC_CARD_RE.finditer(text):
        sale_date_raw = m.group(1).strip()
        judgment_raw  = m.group(2) or ""
        parcel_id     = m.group(3).strip()
        address_raw   = m.group(4) or ""

        sale_date = _parse_fc_date(sale_date_raw)
        if not sale_date:
            print(f"  SKIP: could not parse FC date {sale_date_raw!r}", file=sys.stderr)
            continue

        judgment = None
        if judgment_raw:
            try:
                judgment = float(judgment_raw.replace(",", ""))
            except ValueError:
                pass

        address = re.sub(r"\s+(Foreclosures|Tax Deeds|CONTACT).*", "",
                         address_raw.strip(), flags=re.IGNORECASE).strip()

        today = date.today().isoformat()
        cards.append({
            "county":           "holmes",
            "state":            "FL",
            "auction_type":     "foreclosure",
            "sale_type":        "foreclosure",
            "parcel_id":        parcel_id,
            "property_address": address or None,
            "judgment_amount":  judgment,
            "auction_date":     sale_date,
            "auction_status":   "upcoming" if sale_date >= today else "completed",
            "data_source":      "holmes_clerk",
            "source_platform":  "holmes_clerk",
            "clerk_url":        PAGES["foreclosure"],
        })
    return cards


def main():
    supa_url = _req_env("SUPABASE_URL").rstrip("/")
    supa_key = _req_env("SUPABASE_SERVICE_ROLE_KEY")
    now_ts   = datetime.now(timezone.utc).isoformat()
    today    = date.today().isoformat()

    td_text = _fetch_text(PAGES["tax_deed"])
    td_cards = parse_td_cards(td_text)
    print(f"TD page: {len(td_cards)} case(s) parsed", flush=True)

    fc_text = _fetch_text(PAGES["foreclosure"])
    fc_cards = parse_fc_cards(fc_text)
    print(f"FC page: {len(fc_cards)} case(s) parsed", flush=True)

    lat_text = _fetch_text(PAGES["lat"])
    has_lat = "NO LOLA FILES" not in lat_text.upper() and len(lat_text) > 200
    print(f"LAT page: {'has content' if has_lat else 'empty (NO LOLA FILES)'}", flush=True)

    all_cards = td_cards + fc_cards
    if not all_cards:
        print("FAIL-LOUD: zero cards parsed from either live page — refusing silent no-op",
              file=sys.stderr)
        return 2

    db_rows = _sb_get(supa_url, supa_key, "multi_county_auctions",
                      "county=eq.holmes&select=id,case_number,auction_type,auction_date,"
                      "parcel_id,property_address,parity_status&limit=100")
    print(f"DB: {len(db_rows)} existing holmes row(s)", flush=True)

    existing_by_case = {(r["case_number"] or "").upper(): r for r in db_rows}
    existing_by_parcel_date = {
        (r["parcel_id"], r["auction_date"]): r for r in db_rows
        if r.get("parcel_id") and r.get("auction_date")
    }

    inserted = 0
    parity_updated = 0
    freshness_updated = 0

    for card in all_cards:
        case_key = (card.get("case_number") or "").upper()
        parcel_key = (card.get("parcel_id", ""), card.get("auction_date", ""))

        existing = existing_by_case.get(case_key) or existing_by_parcel_date.get(parcel_key)

        if existing:
            row_id = existing["id"]
            patch_data = {"last_seen_at": now_ts}
            if existing.get("parity_status") != "matched_clean":
                patch_data["parity_status"] = "matched_clean"
                patch_data["parity_source"] = "tier1:holmes_clerk_live_shard8_c04799e6"
                parity_updated += 1
            s, _ = _sb_patch(supa_url, supa_key, "multi_county_auctions",
                              f"id=eq.{row_id}", patch_data)
            if s not in (200, 201, 204):
                print(f"  WARN: patch failed for id={row_id}: HTTP {s}", file=sys.stderr)
            else:
                freshness_updated += 1
        else:
            payload = {k: v for k, v in card.items() if v is not None}
            payload["last_seen_at"] = now_ts
            payload["scraped_at"]   = now_ts
            payload["parity_status"]  = "matched_clean"
            payload["parity_source"]  = "tier1:holmes_clerk_live_shard8_c04799e6"
            s, resp = _sb_post(supa_url, supa_key, "multi_county_auctions", [payload])
            if s in (200, 201):
                inserted += 1
                print(f"  INSERTED: {card.get('case_number', card.get('parcel_id'))} "
                      f"@ {card.get('auction_date')}", flush=True)
            else:
                print(f"  WARN: insert failed HTTP {s}: {resp[:200]}", file=sys.stderr)

    s_live = set((c.get("case_number") or "").upper() for c in td_cards if c.get("case_number"))
    rolled_off = [
        r["case_number"] for r in db_rows
        if (r.get("case_number") or "").upper() not in s_live
        and r.get("auction_type") == "tax_deed"
        and r.get("case_number", "").startswith("TD#")
        and r.get("auction_status") in ("upcoming", None)
    ]
    if rolled_off:
        print(f"\nRolled-off TD cases (no longer on live page, no disposition data available):",
              flush=True)
        for cn in rolled_off:
            print(f"  {cn}", flush=True)

    print(f"\nSUMMARY: inserted={inserted} parity_updated={parity_updated} "
          f"freshness_updated={freshness_updated} rolled_off={len(rolled_off)}", flush=True)
    print("B/F NOTE: holmesclerk.com has no disposition/sold-amount page — "
          "no outcome rows written (correct behavior, not a scraper gap).", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
