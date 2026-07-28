#!/usr/bin/env python3
"""
Calhoun Clerk Foreclosure/Tax-Deed Harvest (2026-07-10, updated 2026-07-24 SHARD-10)
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

Both taxdeeds/foreclosures endpoints show only `scheduled`/`cancelled` and never
flip to a closed/sold status themselves -- the clerk's site does not appear to
update case status after a sale. 2026-07-28 addition: the tax-deed-surplus feed
(`/wp-json/wp/v2/taxdeedoverbids`) is now cross-referenced by cert against our
tracked tax_deed rows (`mark_closed_from_overbids`) -- a surplus/overbid entry
only exists under FL Stat 197.582 once a sale has actually closed above the
statutory minimum, so a match proves closure. Its `balance` field remains the
unclaimed surplus owed to the prior owner, not the winning bid, so it is still
never written to `sold_amount`/`tier1_sold_amount`; a match only flips
`auction_status`/`tier1_sale_status`/`tier1_authoritative` (same convention as
the gulf county tax-deed-surplus fix). An unrecognized status on the primary
feeds is still logged loudly rather than guessed at.

Env (required): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success (>=1 row upserted), 1 = fatal error, 2 = no new rows found
"""
import datetime
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
    "tax_deed_overbid": "https://www.calhounclerk.com/wp-json/wp/v2/taxdeedoverbids",
}

KNOWN_STATUSES = {"scheduled", "cancelled"}


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
    # e.g. "Aug 20, 2026 11:00 am" -> "2026-08-20"
    dt = datetime.datetime.strptime(raw.strip(), "%b %d, %Y %I:%M %p")
    return dt.date().isoformat()


def normalize_status(raw: str) -> str:
    status = (raw or "").strip().lower()
    if status not in KNOWN_STATUSES:
        print(f"NOTE: unrecognized calhoun clerk status {raw!r} -- writing as-is, "
              f"verify manually whether this represents a closed sale", file=sys.stderr)
    return "upcoming" if status == "scheduled" else status


def build_foreclosure_rows(posts: list[dict]) -> list[dict]:
    rows = []
    for p in posts:
        acf = p.get("acf") or {}
        if not acf.get("case_number") or not acf.get("sale_date"):
            continue
        rows.append({
            "county": "calhoun",
            "case_number": acf["case_number"],
            "sale_type": "foreclosure",
            "auction_type": "foreclosure",
            "auction_date": parse_sale_date(acf["sale_date"]),
            "property_address": (acf.get("address") or "").strip() or None,
            "parcel_id": acf.get("parcel") or None,
            "judgment_amount": float(acf["amount"]) if acf.get("amount") not in (None, "") else None,
            "auction_status": normalize_status(acf.get("status")),
            "state": "FL",
            "source_platform": "calhoun_clerk_scrape",
            "data_source": "calhoun_clerk_scrape",
            "source_url": p.get("link") or API["foreclosure"],
        })
    return rows


def build_taxdeed_rows(posts: list[dict]) -> list[dict]:
    rows = []
    for p in posts:
        acf = p.get("acf") or {}
        if not acf.get("cert") or not acf.get("sale_date"):
            continue
        rows.append({
            "county": "calhoun",
            "case_number": acf["cert"],
            "sale_type": "tax_deed",
            "auction_type": "tax_deed",
            "auction_date": parse_sale_date(acf["sale_date"]),
            "parcel_id": acf.get("parcel") or None,
            "opening_bid": float(acf["opening_bid"]) if acf.get("opening_bid") not in (None, "") else None,
            "auction_status": normalize_status(acf.get("status")),
            "state": "FL",
            "source_platform": "calhoun_clerk_scrape",
            "data_source": "calhoun_clerk_scrape",
            "source_url": p.get("link") or API["tax_deed"],
        })
    return rows


def upsert(supa_url: str, headers: dict, rows: list[dict]) -> None:
    resp = requests.post(
        f"{supa_url}/rest/v1/multi_county_auctions?on_conflict=county,case_number,sale_type",
        headers=headers, json=rows, timeout=30,
    )
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"upsert failed {resp.status_code} {resp.text[:300]}")


def mark_closed_from_overbids(supa_url: str, headers: dict) -> int:
    """Cross-reference the tax-deed-surplus/overbid feed against our tracked tax_deed rows.

    A surplus/overbid record only exists under FL Stat 197.582 once a sale has actually
    closed with a winning bid above the statutory minimum, so a match proves the sale
    closed even though the feed's `balance` field is the unclaimed surplus owed to the
    prior owner, not the winning bid -- it is NEVER written to sold_amount/tier1_sold_amount
    (two prior sessions on this county already rejected deriving winning_bid = opening_bid +
    balance as fabrication). This only flips status fields, same convention as the gulf
    county tax-deed-surplus fix (migrations/20260725_gold_standard_shard1_..._a9f1f24f.sql).
    """
    overbids = fetch_posts(API["tax_deed_overbid"])
    certs = {(p.get("acf") or {}).get("cert", "").strip().upper() for p in overbids}
    certs.discard("")

    resp = requests.get(
        f"{supa_url}/rest/v1/multi_county_auctions",
        headers=headers,
        params={
            "county": "eq.calhoun",
            "sale_type": "eq.tax_deed",
            "select": "id,case_number,auction_status",
        },
        timeout=30,
    )
    resp.raise_for_status()
    rows = resp.json()

    matched_ids = [
        r["id"] for r in rows
        if r["case_number"].strip().upper() in certs and r["auction_status"] != "completed"
    ]
    if not matched_ids:
        return 0

    patch = requests.patch(
        f"{supa_url}/rest/v1/multi_county_auctions",
        headers=headers,
        params={"id": f"in.({','.join(matched_ids)})"},
        json={
            "auction_status": "completed",
            "tier1_sale_status": "sold",
            "tier1_authoritative": True,
            "tier1_verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        timeout=30,
    )
    if not (200 <= patch.status_code < 300):
        raise RuntimeError(f"overbid status patch failed {patch.status_code} {patch.text[:300]}")
    return len(matched_ids)


def main() -> int:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    supa_key = _req("SUPABASE_SERVICE_ROLE_KEY")
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

    if fc_rows:
        upsert(supa_url, headers, fc_rows)
    if td_rows:
        upsert(supa_url, headers, td_rows)

    closed = mark_closed_from_overbids(supa_url, headers)
    if closed:
        print(f">>> tax_deed_overbid: {closed} tracked row(s) flipped to auction_status=completed "
              f"(surplus/overbid feed proves the sale closed; sold_amount left NULL -- not publicly available)")

    total = len(fc_rows) + len(td_rows)
    if not total and not closed:
        print("NOTE: zero cards parsed from either endpoint and no new overbid matches -- "
              "calhoun genuinely has no listed inventory changes")
        return 2

    print(f"\nSUCCESS: upserted {total} calhoun row(s), flipped {closed} to completed: "
          f"{[r['case_number'] for r in fc_rows + td_rows]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
