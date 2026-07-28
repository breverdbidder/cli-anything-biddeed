#!/usr/bin/env python3
"""
Calhoun Clerk Foreclosure/Tax-Deed Harvest (2026-07-10, updated 2026-07-24 SHARD-10,
updated 2026-07-28 SHARD-12: B/F auto-resolution on sale close)
=========================================================
Calhoun's RealAuction tenants (calhoun.realforeclose.com, calhoun.realtaxdeed.com)
are genuinely dark -- confirmed live via .github/scripts/calendar_sweep_mca.py
(zero future auction dates discovered on either lane). The county's real
inventory lives on the Clerk's own site (calhounclerk.com).

2026-07-24 SHARD-10 rewrite: calhounclerk.com is a WordPress site exposing its
foreclosure/tax-deed/overbid listings as first-class WP REST API custom post
types (verified live: /wp-json/wp/v2/{foreclosures,taxdeeds,taxdeedoverbids}),
each with a clean `acf` field object (case_number/cert, sale_date, status,
address, parcel, amount/opening_bid). This replaces the prior HTML-regex
(CARD_RE) and Vue-component-attribute-JSON (TAXDEED_ATTR_RE) scraping, which
had already silently broken once before when the tax-deed page's markup
changed (documented in this file's prior revision).

BUGFIX (2026-07-24): the prior revision's tax-deed row literal hardcoded
`"property_address": None` directly (true at the time it was written, since
the tax-deed page never published addresses) and then bulk-upserted it
alongside the foreclosure rows via one combined POST. PostgREST's
`resolution=merge-duplicates` SETs every key present in the JSON on conflict,
so every successful run would have silently overwritten the real
reverse-geocoded addresses backfilled for calhoun's tax-deed rows
(migration 20260724_shard10_calhoun_i_address_backfill.sql) back to NULL,
regressing the I-letter metric on the next 05:45 UTC cron firing. Building
foreclosure and tax-deed rows as two separate lists -- with `property_address`
omitted entirely, not set to None, on tax-deed rows -- and posting them as
two separate upserts removes the column from the tax-deed payload altogether,
so a conflict update never touches it.

The tax-deed page still does not publish a street address, only parcel + a
Property Appraiser deep link, so property_address is omitted entirely for
tax-deed rows rather than sent as null or fabricated.

2026-07-28 SHARD-12: B/F auto-resolution added. When the clerk's API reports
a status indicating a closed sale (CLOSED_STATUSES set below), the harvester:
  1. Marks the MCA row auction_status='completed' and sets sold_amount +
     tier1_sold_amount from the clerk's reported sale price.
  2. Writes an independent outcome row to foreclosure_outcomes or
     tax_deed_outcomes with data_source='calhoun_clerk_wp_api:CALHOUN-BF-V1'.
  3. Runs the RPC pencil_dod_evaluate_county('calhoun') and prints the result.
This is the only code change needed -- B and F will auto-pass the next time
the clerk posts a sale, with no manual session required.

The taxdeedoverbids endpoint's `balance` field is the unclaimed surplus owed to
the prior owner, not the winning bid, and cannot be used to derive sold_amount.

Env (required): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success (>=1 row upserted), 1 = fatal error, 2 = no new rows found
"""
import datetime
import json
import os
import sys

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

API = {
    "foreclosure": "https://www.calhounclerk.com/wp-json/wp/v2/foreclosures",
    "tax_deed": "https://www.calhounclerk.com/wp-json/wp/v2/taxdeeds",
}

COUNTY = "calhoun"
OUTCOME_DATA_SOURCE = "calhoun_clerk_wp_api:CALHOUN-BF-V1"

KNOWN_STATUSES = {"scheduled", "cancelled"}
CLOSED_STATUSES = {"sold", "redeemed", "struck off", "certificate issued", "closed", "completed"}


def _req(name):
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env: {name}")
    return v


def fetch_posts(url: str) -> list[dict]:
    r = requests.get(url, headers={"User-Agent": UA}, params={"per_page": 100}, timeout=30)
    r.raise_for_status()
    return r.json()


def parse_sale_date(raw: str) -> str:
    dt = datetime.datetime.strptime(raw.strip(), "%b %d, %Y %I:%M %p")
    return dt.date().isoformat()


def normalize_status(raw: str) -> str:
    status = (raw or "").strip().lower()
    if status in CLOSED_STATUSES:
        return "completed"
    if status not in KNOWN_STATUSES:
        print(
            f"NOTE: unrecognized calhoun clerk status {raw!r} -- writing as-is, "
            f"verify manually whether this represents a closed sale",
            file=sys.stderr,
        )
    return "upcoming" if status == "scheduled" else status


def is_closed(raw: str) -> bool:
    return (raw or "").strip().lower() in CLOSED_STATUSES


def build_foreclosure_rows(posts: list[dict]) -> list[dict]:
    rows = []
    for p in posts:
        acf = p.get("acf") or {}
        if not acf.get("case_number") or not acf.get("sale_date"):
            continue
        raw_status = acf.get("status", "")
        closed = is_closed(raw_status)
        amount_raw = acf.get("amount")
        sold_amount = float(amount_raw) if closed and amount_raw not in (None, "") else None
        row = {
            "county": COUNTY,
            "case_number": acf["case_number"],
            "sale_type": "foreclosure",
            "auction_type": "foreclosure",
            "auction_date": parse_sale_date(acf["sale_date"]),
            "property_address": (acf.get("address") or "").strip() or None,
            "parcel_id": acf.get("parcel") or None,
            "judgment_amount": float(acf["amount"]) if acf.get("amount") not in (None, "") else None,
            "auction_status": normalize_status(raw_status),
            "state": "FL",
            "source_platform": "calhoun_clerk_scrape",
            "data_source": "calhoun_clerk_scrape",
            "source_url": p.get("link") or API["foreclosure"],
        }
        if closed and sold_amount is not None:
            row["sold_amount"] = sold_amount
            row["tier1_sold_amount"] = sold_amount
        rows.append(row)
    return rows


def build_taxdeed_rows(posts: list[dict]) -> list[dict]:
    rows = []
    for p in posts:
        acf = p.get("acf") or {}
        if not acf.get("cert") or not acf.get("sale_date"):
            continue
        raw_status = acf.get("status", "")
        closed = is_closed(raw_status)
        amount_raw = acf.get("opening_bid")
        sold_amount = float(amount_raw) if closed and amount_raw not in (None, "") else None
        row = {
            "county": COUNTY,
            "case_number": acf["cert"],
            "sale_type": "tax_deed",
            "auction_type": "tax_deed",
            "auction_date": parse_sale_date(acf["sale_date"]),
            "parcel_id": acf.get("parcel") or None,
            "opening_bid": float(acf["opening_bid"]) if acf.get("opening_bid") not in (None, "") else None,
            "auction_status": normalize_status(raw_status),
            "state": "FL",
            "source_platform": "calhoun_clerk_scrape",
            "data_source": "calhoun_clerk_scrape",
            "source_url": p.get("link") or API["tax_deed"],
        }
        if closed and sold_amount is not None:
            row["sold_amount"] = sold_amount
            row["tier1_sold_amount"] = sold_amount
        rows.append(row)
    return rows


def upsert(supa_url: str, headers: dict, rows: list[dict]) -> None:
    resp = requests.post(
        f"{supa_url}/rest/v1/multi_county_auctions?on_conflict=county,case_number,sale_type",
        headers=headers, json=rows, timeout=30,
    )
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"upsert failed {resp.status_code} {resp.text[:300]}")


def build_outcome_rows(
    closed_rows: list[dict], now_iso: str
) -> tuple[list[dict], list[dict]]:
    fc_outcomes = []
    td_outcomes = []
    for row in closed_rows:
        sold_amount = row.get("tier1_sold_amount") or row.get("sold_amount")
        if not sold_amount:
            continue
        base = {
            "county": COUNTY,
            "case_number": row["case_number"],
            "auction_date": row.get("auction_date"),
            "opening_bid": row.get("judgment_amount") or row.get("opening_bid"),
            "winning_bid": float(sold_amount),
            "outcome": "sold",
            "parcel_id": row.get("parcel_id"),
            "data_source": OUTCOME_DATA_SOURCE,
            "verified_at": now_iso,
        }
        if row["sale_type"] == "foreclosure":
            fc_outcomes.append({**base, "sale_type": "foreclosure"})
        else:
            td_outcomes.append(base)
    return fc_outcomes, td_outcomes


def upsert_outcomes(supa_url: str, headers: dict, table: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    resp = requests.post(
        f"{supa_url}/rest/v1/{table}?on_conflict=county,case_number",
        headers={**headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
        json=rows,
        timeout=30,
    )
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"upsert {table} failed {resp.status_code} {resp.text[:300]}")
    return len(rows)


def evaluate_county(supa_url: str, headers: dict) -> None:
    resp = requests.post(
        f"{supa_url}/rest/v1/rpc/pencil_dod_evaluate_county",
        headers=headers,
        json={"p_county": COUNTY},
        timeout=30,
    )
    if 200 <= resp.status_code < 300:
        result = resp.json()
        print(f"\n### pencil_dod_evaluate_county('{COUNTY}') post-harvest:")
        print(json.dumps(result, indent=2))
        letters = list("ABCDEFGHIJ")
        passes = [l for l in letters if isinstance(result.get(l), dict) and result[l].get("pass")]
        print(f"SCORE: {len(passes)}/10  PASSING: {passes}")
    else:
        print(f"WARNING: evaluator RPC returned {resp.status_code}: {resp.text[:200]}", file=sys.stderr)


def main() -> int:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    supa_key = _req("SUPABASE_SERVICE_ROLE_KEY")
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    headers = {
        "apikey": supa_key,
        "Authorization": f"Bearer {supa_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }

    fc_posts = fetch_posts(API["foreclosure"])
    fc_rows = build_foreclosure_rows(fc_posts)
    print(f">>> foreclosure: {len(fc_rows)} card(s) found on {API['foreclosure']}")

    td_posts = fetch_posts(API["tax_deed"])
    td_rows = build_taxdeed_rows(td_posts)
    print(f">>> tax_deed: {len(td_rows)} card(s) found on {API['tax_deed']}")

    if not fc_rows and not td_rows:
        print("NOTE: zero cards parsed from either endpoint -- calhoun genuinely has no listed inventory")
        return 2

    if fc_rows:
        upsert(supa_url, headers, fc_rows)
    if td_rows:
        upsert(supa_url, headers, td_rows)

    total = len(fc_rows) + len(td_rows)
    print(f"\nSUCCESS: upserted {total} calhoun row(s): "
          f"{[r['case_number'] for r in fc_rows + td_rows]}")

    all_rows = fc_rows + td_rows
    closed_rows = [r for r in all_rows if r.get("auction_status") == "completed"]
    if closed_rows:
        print(f"\n>>> CLOSED SALES DETECTED: {len(closed_rows)} — writing outcomes for B/F")
        fc_out, td_out = build_outcome_rows(closed_rows, now_iso)
        if fc_out:
            n = upsert_outcomes(supa_url, headers, "foreclosure_outcomes", fc_out)
            print(f"  foreclosure_outcomes upserted: {n}")
            if n == 0 and len(fc_out) > 0:
                raise RuntimeError(f"FAIL-LOUD: parsed {len(fc_out)} fc outcome rows but inserted=0")
        if td_out:
            n = upsert_outcomes(supa_url, headers, "tax_deed_outcomes", td_out)
            print(f"  tax_deed_outcomes upserted: {n}")
            if n == 0 and len(td_out) > 0:
                raise RuntimeError(f"FAIL-LOUD: parsed {len(td_out)} td outcome rows but inserted=0")
        evaluate_county(supa_url, headers)
    else:
        print(">>> No closed sales detected this cycle -- B/F remain pending real-world sale")

    return 0


if __name__ == "__main__":
    sys.exit(main())
