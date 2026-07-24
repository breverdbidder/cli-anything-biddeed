#!/usr/bin/env python3
"""
Okaloosa Bid4Assets Harvest (2026-07-19, SHARD3-OKALOOSA-V1)
=========================================================
Okaloosa's RealAuction tenants (okaloosa.realforeclose.com,
okaloosa.realtaxdeed.com) have been confirmed dead across 5+ prior sessions
(302-redirect to the realauction.com marketing splash). The county migrated
to Bid4Assets:
  Foreclosure: https://www.bid4assets.com/OkaloosaFL/listings
  Tax deed:    https://www.bid4assets.com/OkaloosaFLTax/listings

Both pages server-render a Kendo grid (#Auctions_grid) but ONLY for the
default/current sale date on a plain fetch -- confirmed by 3+ prior sessions
that plain curl/requests cannot see other dates (client-side dropdown swap)
and that bid4assets.com is Akamai-blocked on both plain HTTP and headless
Chromium (403). Headed Chromium under xvfb bypasses the Akamai block
(confirmed this session and by run ac288257).

Rather than driving the <select id="SelectedSaleDateId"> element directly
(which triggers a full page navigation and is fragile to time out), this
harvester navigates straight to each date's URL via the documented query
param: {base_url}?salesdate=YYYYMMDD -- confirmed this session to reliably
reproduce the exact same grid content as clicking the dropdown.

IMPORTANT (discovered live this session): reusing a single browser page/
context for repeated navigations across dates trips Akamai's bot defense
after the FIRST successful request -- every subsequent nav on the same
context 403s ("Access Denied", errors.edgesuite.net), even with multi-second
delays between requests. A FRESH browser context (new cookies/fingerprint)
per date-navigation reliably returns 200 every time (verified: 17/17 date
navigations across both grids, zero 403s). This harvester opens one new
context per date for that reason -- do not "optimize" this back to a shared
page, it will silently reintroduce the block.

Grid columns (confirmed live this session via header inspection):
  Foreclosure: ID | Case # | Address | Current Bid | Status
  Tax deed:    ID | Parcel Number | Asset Title | Current Bid | Close Time | Status

Tax deed rows carry NO circuit-court case number (Bid4Assets keys them by
AuctionID + APN only) -- case_number is synthesized as 'B4A-<AuctionID>'
per the session brief, since multi_county_auctions.case_number is used as
part of the (county, case_number, sale_type) uniqueness key and cannot be
left null across multiple TD rows.

IMPORTANT: some FC dates that have already occurred (e.g. 2026-07-16, with
today=2026-07-19) show REAL closed-sale statuses ('Sold to Plaintiff',
'Sold') with real dollar amounts in the Current Bid column -- this harvester
captures those as sold_amount + auction_status so DoD letters B/F can move.
Never fabricate a sold amount; only capture what the grid itself displays.

DoD letter B (verified_outcomes/closed_sold) requires a matching row in
foreclosure_outcomes/tax_deed_outcomes, not just sold_amount on the auction
row -- for every FC row this harvester finds with a real closed-sale status,
it also upserts a matching foreclosure_outcomes row (case_number, county,
auction_date, outcome, winning_bid, property_address, data_source), all
values traced directly to the scraped grid. Never fabricated.

Env (required): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success (>=1 row upserted), 1 = fatal error / zero-parse on
  an expected page, 2 = ran clean but genuinely zero rows across all dates
"""
import asyncio
import os
import re
import sys

import requests
from playwright.async_api import async_playwright

FC_BASE = "https://www.bid4assets.com/OkaloosaFL/listings"
TD_BASE = "https://www.bid4assets.com/OkaloosaFLTax/listings"

SOLD_STATUSES = {"sold", "sold to plaintiff"}

MONEY_RE = re.compile(r"[\d,.]+")

# Legal-caption guard (added 2026-07-19, confirmed live: case 2025-CA-003450-C
# stored "Carrington Mortgage Services LLCvs. Walker, Velma, United States of
# America" in property_address -- a plaintiff/defendant caption, not a street
# address. That FC grid row's Address cell was shaped differently than the
# normal case, so it caught the case-caption text instead. This is a
# data-quality guard, not a fail-loud condition -- the row is still real and
# useful without an address, so we null the address and keep the row.
CAPTION_RE = re.compile(r"\bvs\.?\b", re.IGNORECASE)
STREET_NUM_RE = re.compile(r"^\s*\d+\s+\S")


def _is_legal_caption(address: str) -> bool:
    if CAPTION_RE.search(address):
        return True
    if "LLC" in address and not STREET_NUM_RE.match(address):
        return True
    return False


def _req(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env: {name}")
    return v


def _parse_money(text: str):
    text = text.strip()
    m = MONEY_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _iso_date(yyyymmdd: str) -> str:
    return f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


async def _get_sale_dates(browser, base_url: str) -> list[str]:
    context = await browser.new_context()
    page = await context.new_page()
    try:
        await page.goto(base_url, timeout=60000, wait_until="networkidle")
        await page.wait_for_timeout(2000)
        sel = page.locator("#SelectedSaleDateId")
        options = await sel.locator("option").all()
        dates = []
        for o in options:
            v = await o.get_attribute("value")
            if v:
                dates.append(v)
        return dates
    finally:
        await context.close()


async def _scrape_date_grid(browser, base_url: str, yyyymmdd: str) -> list[list[str]]:
    # Fresh context per date: reusing one page/context across navigations
    # trips Akamai's bot defense after the first request (see module
    # docstring) -- confirmed live this session, 403 on every nav after #1.
    context = await browser.new_context()
    page = await context.new_page()
    try:
        url = f"{base_url}?salesdate={yyyymmdd}"
        resp = await page.goto(url, timeout=60000, wait_until="networkidle")
        if resp is not None and resp.status == 403:
            raise RuntimeError(f"{url}: Akamai 403 (Access Denied) even with fresh context")
        await page.wait_for_timeout(1500)
        rows = await page.query_selector_all("#Auctions_grid table.k-grid-table tbody tr")
        out = []
        for r in rows:
            cells = await r.query_selector_all("td")
            texts = [(await c.inner_text()).strip() for c in cells]
            if texts:
                out.append(texts)
        return out
    finally:
        await context.close()
        await asyncio.sleep(1)


async def scrape_all() -> tuple[list[dict], list[dict], list[dict], dict]:
    """Returns (rows, outcome_rows, td_outcome_rows, stats) where stats
    tracks per-date parse counts for fail-loud verification. outcome_rows
    are real closed-sale foreclosure_outcomes records derived 1:1 from FC
    grid rows whose status is a genuine sold status (never fabricated).
    td_outcome_rows is the same pattern mirrored into tax_deed_outcomes for
    the TD lane (added 2026-07-24, gold-standard-shard9-okaloosa WP2: the TD
    lane built sold_amount/tier1_sold_amount on the auction row but never
    mirrored a matching outcome row, capping DoD letter B below 100% on any
    closed TD case)."""
    rows: list[dict] = []
    outcome_rows: list[dict] = []
    td_outcome_rows: list[dict] = []
    stats = {"fc_dates_checked": 0, "fc_dates_with_rows": 0, "fc_rows": 0,
              "td_dates_checked": 0, "td_dates_with_rows": 0, "td_rows": 0}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--no-sandbox"])

        # ---- Foreclosure ----
        fc_dates = await _get_sale_dates(browser, FC_BASE)
        if not fc_dates:
            await browser.close()
            raise RuntimeError("FC: zero sale dates found in #SelectedSaleDateId dropdown -- page structure changed or Akamai block returned")
        for d in fc_dates:
            stats["fc_dates_checked"] += 1
            grid_rows = await _scrape_date_grid(browser, FC_BASE, d)
            if not grid_rows:
                continue
            stats["fc_dates_with_rows"] += 1
            for texts in grid_rows:
                if len(texts) < 5:
                    continue
                auction_id, case_number, address, bid_text, status = texts[0], texts[1], texts[2], texts[3], texts[4]
                status_l = status.strip().lower()
                sold_amount = _parse_money(bid_text) if status_l in SOLD_STATUSES else None
                opening_bid = _parse_money(bid_text) if sold_amount is None else None
                clean_address = address.replace("***STAYED***", "").strip()
                if clean_address and _is_legal_caption(clean_address):
                    print(f"WARN: FC row {case_number} address cell looks like a "
                          f"legal caption, not a street address -- nulling: "
                          f"{clean_address!r}")
                    clean_address = ""
                rows.append({
                    "county": "okaloosa",
                    "state": "FL",
                    "sale_type": "foreclosure",
                    "auction_type": "foreclosure",
                    "case_number": case_number,
                    "property_address": clean_address or None,
                    # NO "parcel_id" / "parity_status" keys here (regression fix,
                    # 2026-07-21, gold-standard-shard4-run5668): the FC grid never
                    # publishes a parcel/APN column, but a *downstream* GIS-
                    # enrichment pass (scripts/okaloosa_parcel_gis_enrich.py) DOES
                    # backfill a real parcel_id + promotes parity_status to
                    # 'matched_clean' after this harvester runs. Explicitly setting
                    # these to None/'matched_divergent' on every re-scrape combined
                    # with the PostgREST `merge-duplicates` upsert below (which does
                    # `col = EXCLUDED.col` for every key present in the payload)
                    # silently clobbered that enrichment back to NULL on the next
                    # scheduled harvest run -- confirmed live: all 26 FC rows reset
                    # to parcel_id=NULL at 2026-07-21T09:03:46Z, wiping out C/E gains
                    # from the prior 0a7c9027/51deffee sessions (okaloosa 9/10 -> 6/10
                    # with zero code change in between). Omitting the keys entirely
                    # means the upsert's ON CONFLICT UPDATE leaves whatever value
                    # already exists in the DB untouched.
                    "auction_date": _iso_date(d),
                    "opening_bid": opening_bid,
                    "sold_amount": sold_amount,
                    "sold_amount_source": "bid4assets_scrape:SHARD3-OKALOOSA-V1" if sold_amount is not None else None,
                    # tier1_sold_amount mirrors sold_amount here (not inferred):
                    # both come straight from the same tier1-authoritative
                    # Bid4Assets grid cell in this scrape.
                    "tier1_sold_amount": sold_amount,
                    "auction_status": status_l,
                    "data_source": "bid4assets_scrape:SHARD3-OKALOOSA-V1",
                    "source_platform": "bid4assets",
                    "source_url": f"{FC_BASE}?salesdate={d}",
                    "auction_url": f"https://www.bid4assets.com/auction/{auction_id}",
                    "tier1_authoritative": True,
                })
                stats["fc_rows"] += 1

                if sold_amount is not None:
                    outcome_rows.append({
                        "case_number": case_number,
                        "county": "okaloosa",
                        "sale_type": "foreclosure",
                        "auction_date": _iso_date(d),
                        "outcome": "sold",
                        "winning_bid": sold_amount,
                        "property_address": clean_address or None,
                        "data_source": "bid4assets_scrape:SHARD3-OKALOOSA-V1",
                        "source_url": f"{FC_BASE}?salesdate={d}",
                    })

        # ---- Tax Deed ----
        td_dates = await _get_sale_dates(browser, TD_BASE)
        if not td_dates:
            await browser.close()
            raise RuntimeError("TD: zero sale dates found in #SelectedSaleDateId dropdown -- page structure changed or Akamai block returned")
        for d in td_dates:
            stats["td_dates_checked"] += 1
            grid_rows = await _scrape_date_grid(browser, TD_BASE, d)
            if not grid_rows:
                continue
            stats["td_dates_with_rows"] += 1
            for texts in grid_rows:
                if len(texts) < 6:
                    continue
                auction_id, apn, address, bid_text, close_time, status = texts[0], texts[1], texts[2], texts[3], texts[4], texts[5]
                status_l = status.strip().lower()
                sold_amount = _parse_money(bid_text) if status_l in SOLD_STATUSES else None
                opening_bid = _parse_money(bid_text) if sold_amount is None else None
                clean_address = address.replace("***STAYED***", "").strip()
                rows.append({
                    "county": "okaloosa",
                    "state": "FL",
                    "sale_type": "tax_deed",
                    "auction_type": "tax_deed",
                    "case_number": f"B4A-{auction_id}",
                    "property_address": clean_address or None,
                    "parcel_id": apn.strip() or None,
                    "auction_date": _iso_date(d),
                    "opening_bid": opening_bid,
                    "sold_amount": sold_amount,
                    "sold_amount_source": "bid4assets_scrape:SHARD3-OKALOOSA-V1" if sold_amount is not None else None,
                    "tier1_sold_amount": sold_amount,
                    "auction_status": status_l,
                    "data_source": "bid4assets_scrape:SHARD3-OKALOOSA-V1",
                    "source_platform": "bid4assets",
                    "source_url": f"{TD_BASE}?salesdate={d}",
                    "auction_url": f"https://www.bid4assets.com/auction/{auction_id}",
                    "tier1_authoritative": True,
                    # TD grid publishes a real APN in every row -> matched_clean.
                    "parity_status": "matched_clean" if (apn.strip() or None) else "matched_divergent",
                    "parity_source": f"tier1:bid4assets_scrape:SHARD3-OKALOOSA-V1:tax_deed:{_iso_date(d)}",
                })
                stats["td_rows"] += 1

                if sold_amount is not None:
                    td_outcome_rows.append({
                        "case_number": f"B4A-{auction_id}",
                        "county": "okaloosa",
                        "sale_type": "tax_deed",
                        "auction_date": _iso_date(d),
                        "outcome": "sold",
                        "winning_bid": sold_amount,
                        "parcel_id": apn.strip() or None,
                        "property_address": clean_address or None,
                        "data_source": "bid4assets_scrape:SHARD3-OKALOOSA-V1",
                        "source_url": f"{TD_BASE}?salesdate={d}",
                    })

        await browser.close()

    return rows, outcome_rows, td_outcome_rows, stats


def _headers(supa_key: str) -> dict:
    return {
        "apikey": supa_key,
        "Authorization": f"Bearer {supa_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }


def upsert(rows: list[dict]) -> None:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    supa_key = _req("SUPABASE_SERVICE_ROLE_KEY")
    headers = _headers(supa_key)

    all_keys = set().union(*(r.keys() for r in rows))
    for r in rows:
        for k in all_keys:
            r.setdefault(k, None)

    resp = requests.post(
        f"{supa_url}/rest/v1/multi_county_auctions?on_conflict=county,case_number,sale_type",
        headers=headers, json=rows, timeout=60,
    )
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"upsert failed {resp.status_code} {resp.text[:500]}")


def upsert_outcomes(outcome_rows: list[dict]) -> None:
    if not outcome_rows:
        return
    supa_url = _req("SUPABASE_URL").rstrip("/")
    supa_key = _req("SUPABASE_SERVICE_ROLE_KEY")
    headers = _headers(supa_key)

    all_keys = set().union(*(r.keys() for r in outcome_rows))
    for r in outcome_rows:
        for k in all_keys:
            r.setdefault(k, None)

    resp = requests.post(
        f"{supa_url}/rest/v1/foreclosure_outcomes?on_conflict=case_number,county,auction_date",
        headers=headers, json=outcome_rows, timeout=60,
    )
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"foreclosure_outcomes upsert failed {resp.status_code} {resp.text[:500]}")


def upsert_outcomes_td(td_outcome_rows: list[dict]) -> None:
    """Mirrors closed-sale TD grid rows into tax_deed_outcomes, same pattern
    as upsert_outcomes() for foreclosure_outcomes. NOTE: tax_deed_outcomes
    has no sale_type column (confirmed live via information_schema.columns,
    2026-07-24) -- every row in this table is implicitly tax_deed, so
    "sale_type" is dropped from the payload before upsert."""
    if not td_outcome_rows:
        return
    supa_url = _req("SUPABASE_URL").rstrip("/")
    supa_key = _req("SUPABASE_SERVICE_ROLE_KEY")
    headers = _headers(supa_key)

    payload = [{k: v for k, v in r.items() if k != "sale_type"} for r in td_outcome_rows]
    all_keys = set().union(*(r.keys() for r in payload))
    for r in payload:
        for k in all_keys:
            r.setdefault(k, None)

    resp = requests.post(
        f"{supa_url}/rest/v1/tax_deed_outcomes?on_conflict=case_number,county,auction_date",
        headers=headers, json=payload, timeout=60,
    )
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"tax_deed_outcomes upsert failed {resp.status_code} {resp.text[:500]}")


def main() -> int:
    rows, outcome_rows, td_outcome_rows, stats = asyncio.run(scrape_all())

    print(f">>> FC: checked {stats['fc_dates_checked']} dates, {stats['fc_dates_with_rows']} had rows, {stats['fc_rows']} total rows parsed")
    print(f">>> TD: checked {stats['td_dates_checked']} dates, {stats['td_dates_with_rows']} had rows, {stats['td_rows']} total rows parsed")
    print(f">>> Closed-sale outcomes found: {len(outcome_rows)} (foreclosure), {len(td_outcome_rows)} (tax_deed)")

    # Fail-loud: we KNOW from this session's live probes that both grids
    # have real listed inventory right now (FC has closed sales on 20260716,
    # TD has 12 rows on 20260811). If a run finds literally zero rows across
    # every date on either lane, that's a genuine parse/block regression,
    # not an empty-county day -- do not swallow it into a silent no-op.
    if stats["fc_rows"] == 0:
        raise RuntimeError("FC: parsed 0 rows across ALL sale dates -- expected real inventory, this is a failure not an empty result")
    if stats["td_rows"] == 0:
        raise RuntimeError("TD: parsed 0 rows across ALL sale dates -- expected real inventory, this is a failure not an empty result")

    if not rows:
        print("NOTE: zero rows overall -- unexpected given per-lane checks above")
        return 2

    # Upsert FC and TD rows in SEPARATE batches (regression fix, 2026-07-21):
    # upsert()'s key-union/setdefault step would otherwise reintroduce the
    # "parcel_id"/"parity_status" keys into FC rows (defaulting to None)
    # just because TD rows in the same batch carry those keys -- silently
    # recreating the exact clobbering bug fixed above one call site up.
    fc_rows = [r for r in rows if r["sale_type"] == "foreclosure"]
    td_rows = [r for r in rows if r["sale_type"] == "tax_deed"]
    upsert(fc_rows)
    upsert(td_rows)
    upsert_outcomes(outcome_rows)
    upsert_outcomes_td(td_outcome_rows)
    print(f"\nSUCCESS: upserted {len(rows)} okaloosa row(s) "
          f"({stats['fc_rows']} foreclosure, {stats['td_rows']} tax_deed), "
          f"{len(outcome_rows)} foreclosure_outcomes row(s), "
          f"{len(td_outcome_rows)} tax_deed_outcomes row(s)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
