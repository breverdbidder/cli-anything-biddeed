#!/usr/bin/env python3
"""
HomeHarvest (Realtor.com) closed-sales + rental comps ingestion.

Interim/bootstrap data source (Ariel, Aug 16 2026) until revenue supports a
licensed API (RentCast or similar). Scheduled batch ingestion ONLY -- never
called live on a user request. Writes to Supabase; biddeed.ai and zonewise.ai
read only from Supabase, never from HomeHarvest directly.

Compliance guardrails (Realtor.com ToS prohibits automated access):
  - Weekly cron only (see .github/workflows/homeharvest-ingest.yml), never per-request.
  - Sequential pagination (parallel=False) with a delay between calls -- no aggressive parallelism.
  - Every row labeled source='homeharvest_realtor_com', honesty_marker='INFERRED'
    (scraped, not licensed data). Never labeled MLS/Zillow/Redfin.
  - Florida only. Brevard first, then the Gold Standard certified county list.

Usage:
  python scripts/homeharvest_ingest.py --counties Brevard --dry-run
  python scripts/homeharvest_ingest.py --counties Brevard,Orange,Duval
  python scripts/homeharvest_ingest.py --batch --batch-size 6   # rotating weekly batch (cron default)
"""
import argparse
import hashlib
import os
import sys
import time
import warnings
from datetime import datetime, timezone

import httpx
import pandas as pd

warnings.filterwarnings("ignore")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

SOURCE = "homeharvest_realtor_com"
HONESTY_MARKER = "INFERRED"  # scraped, not licensed data (RentCast-swap is the licensed path)

# Gold Standard certified FL counties as of 2026-08-16 (v_certified_counties),
# Brevard listed first per guardrail. This is the pipeline's target scope --
# NOT all 67 FL counties. Weekly cron rotates through this list in batches
# (see --batch) rather than hitting all of them in a single run.
# (search_name, county_slug) -- slug matches the lowercase/underscore convention
# used everywhere else in this schema (multi_county_auctions.county,
# v_certified_counties.county_slug, shapira_formula_params.county), so the S5
# report engine can join sale_listings/rental_listings by county without a
# separate normalization step.
FL_PRIORITY_COUNTIES = [
    ("Brevard", "brevard"), ("Alachua", "alachua"), ("Baker", "baker"), ("Bay", "bay"),
    ("Bradford", "bradford"), ("Broward", "broward"), ("Citrus", "citrus"), ("Clay", "clay"),
    ("Collier", "collier"), ("Columbia", "columbia"), ("Escambia", "escambia"),
    ("Flagler", "flagler"), ("Gilchrist", "gilchrist"), ("Hardee", "hardee"),
    ("Hendry", "hendry"), ("Hernando", "hernando"), ("Highlands", "highlands"),
    ("Hillsborough", "hillsborough"), ("Jackson", "jackson"), ("Lake", "lake"),
    ("Lee", "lee"), ("Leon", "leon"), ("Marion", "marion"), ("Martin", "martin"),
    ("Miami-Dade", "miami_dade"), ("Nassau", "nassau"), ("Okeechobee", "okeechobee"),
    ("Palm Beach", "palm_beach"), ("Pasco", "pasco"), ("Polk", "polk"),
    ("Putnam", "putnam"), ("Santa Rosa", "santa_rosa"), ("Seminole", "seminole"),
    ("St. Johns", "st_johns"), ("St. Lucie", "st_lucie"), ("Suwannee", "suwannee"),
    ("Walton", "walton"),
]

REQUEST_DELAY_SECONDS = 3  # conservative pacing between county/listing_type calls
PER_COUNTY_LIMIT = 1000    # bounded per run -- weekly refresh, not full history
PAST_DAYS = 14             # weekly cadence with overlap margin

client = httpx.Client(timeout=60)


def telegram(msg):
    print(msg)
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]})
        except Exception:
            pass


def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }


def row_id(*parts):
    key = "|".join(str(p) for p in parts if p not in (None, ""))
    return "hh_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def to_float(v):
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def to_int(v):
    f = to_float(v)
    return int(f) if f is not None else None


def to_date(v):
    if v is None or pd.isna(v):
        return None
    try:
        return pd.to_datetime(v).date().isoformat()
    except Exception:
        return None


def bathrooms(full_baths, half_baths):
    f = to_float(full_baths) or 0
    h = to_float(half_baths) or 0
    total = f + 0.5 * h
    return total if total else None


def fetch_county(search_name, listing_type):
    """Sequential, non-parallel, rate-limited pull from HomeHarvest for one FL county."""
    from homeharvest import scrape_property

    location = f"{search_name} County, FL"
    df = scrape_property(
        location=location,
        listing_type=listing_type,
        past_days=PAST_DAYS,
        limit=PER_COUNTY_LIMIT,
        return_type="pandas",
        parallel=False,  # guardrail: no aggressive parallel scraping
    )
    return df


def map_sale_row(r, county):
    return {
        "id": row_id(SOURCE, "sale", r.get("mls_id") or r.get("property_url") or r.get("full_street_line")),
        "formatted_address": r.get("formatted_address"),
        "city": r.get("city"),
        "state": r.get("state"),
        "zip_code": r.get("zip_code"),
        "county": county,
        "latitude": to_float(r.get("latitude")),
        "longitude": to_float(r.get("longitude")),
        "property_type": r.get("style"),
        "bedrooms": to_float(r.get("beds")),
        "bathrooms": bathrooms(r.get("full_baths"), r.get("half_baths")),
        "square_footage": to_int(r.get("sqft")),
        "lot_size": to_int(r.get("lot_sqft")),
        "year_built": to_int(r.get("year_built")),
        "status": r.get("status"),
        "list_price": to_float(r.get("list_price")),
        "sold_price": to_float(r.get("sold_price")),
        "last_sold_price": to_float(r.get("last_sold_price")),
        "listed_date": to_date(r.get("list_date")),
        "days_on_market": to_int(r.get("days_on_mls")),
        "mls_name": r.get("mls"),
        "mls_number": r.get("mls_id"),
        "listing_agent_jsonb": {
            "name": r.get("agent_name"), "email": r.get("agent_email"), "phones": r.get("agent_phones"),
        } if r.get("agent_name") else None,
        "listing_office_jsonb": {
            "name": r.get("office_name"), "phones": r.get("office_phones"),
        } if r.get("office_name") else None,
        "source": SOURCE,
        "honesty_marker": HONESTY_MARKER,
    }


def rent_price_of(r):
    v = to_float(r.get("list_price"))
    if v is not None:
        return v
    lo, hi = to_float(r.get("list_price_min")), to_float(r.get("list_price_max"))
    if lo is not None and hi is not None:
        return (lo + hi) / 2
    return lo if lo is not None else hi


def map_rental_row(r, county):
    return {
        "id": row_id(SOURCE, "rental", r.get("mls_id") or r.get("property_url") or r.get("full_street_line")),
        "formatted_address": r.get("formatted_address"),
        "address_line_1": r.get("full_street_line"),
        "city": r.get("city"),
        "state": r.get("state"),
        "zip_code": r.get("zip_code"),
        "county": county,
        "county_fips": r.get("fips_code"),
        "latitude": to_float(r.get("latitude")),
        "longitude": to_float(r.get("longitude")),
        "property_type": r.get("style"),
        "bedrooms": to_float(r.get("beds")),
        "bathrooms": bathrooms(r.get("full_baths"), r.get("half_baths")),
        "square_footage": to_int(r.get("sqft")),
        "lot_size": to_int(r.get("lot_sqft")),
        "year_built": to_int(r.get("year_built")),
        "hoa_fee": to_float(r.get("hoa_fee")),
        "status": r.get("status"),
        "rent_price": rent_price_of(r),
        "listing_type": "for_rent",
        "listed_date": to_date(r.get("list_date")),
        "last_seen_date": datetime.now(timezone.utc).isoformat(),
        "days_on_market": to_int(r.get("days_on_mls")),
        "mls_name": r.get("mls"),
        "mls_number": r.get("mls_id"),
        "listing_agent_name": r.get("agent_name"),
        "listing_agent_phone": (r.get("agent_phones") or [{}])[0].get("number") if isinstance(r.get("agent_phones"), list) and r.get("agent_phones") else None,
        "listing_agent_email": r.get("agent_email"),
        "listing_office_name": r.get("office_name"),
        "listing_office_phone": (r.get("office_phones") or [{}])[0].get("number") if isinstance(r.get("office_phones"), list) and r.get("office_phones") else None,
        "source": SOURCE,
        "honesty_marker": HONESTY_MARKER,
    }


def dedupe_by_id(rows):
    seen = {}
    for row in rows:
        seen[row["id"]] = row  # last-write-wins within batch
    return list(seen.values())


def upsert(table, rows):
    rows = dedupe_by_id(rows)
    if not rows:
        return 0
    resp = client.post(
        f"{SUPABASE_URL}/rest/v1/{table}?on_conflict=id",
        headers=sb_headers(),
        json=rows,
    )
    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(f"upsert {table} failed: {resp.status_code} {resp.text[:500]}")
    return len(rows)


def slugify_county(name):
    return name.strip().lower().replace(".", "").replace("-", " ").replace(" ", "_")


def run(counties, dry_run):
    """counties: list of (search_name, county_slug) tuples."""
    totals = {"sold": 0, "for_rent": 0}
    for search_name, slug in counties:
        for listing_type in ("sold", "for_rent"):
            try:
                df = fetch_county(search_name, listing_type)
            except Exception as e:
                telegram(f"[homeharvest_ingest] {search_name} {listing_type} FAILED: {e}")
                continue

            n = len(df) if df is not None else 0
            telegram(f"[homeharvest_ingest] {search_name} {listing_type}: fetched {n} rows")
            if n == 0:
                time.sleep(REQUEST_DELAY_SECONDS)
                continue

            records = df.to_dict("records")
            if listing_type == "sold":
                rows = [map_sale_row(r, slug) for r in records]
                table = "sale_listings"
            else:
                rows = [map_rental_row(r, slug) for r in records]
                table = "rental_listings"

            if dry_run:
                telegram(f"[homeharvest_ingest] DRY RUN -- would upsert {len(rows)} rows into {table} (sample: {rows[0]})")
            else:
                written = upsert(table, rows)
                totals[listing_type] += written
                telegram(f"[homeharvest_ingest] {search_name} {listing_type}: upserted {written} rows into {table}")

            time.sleep(REQUEST_DELAY_SECONDS)

    telegram(f"[homeharvest_ingest] DONE. sold={totals['sold']} for_rent={totals['for_rent']} dry_run={dry_run}")
    return totals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--counties", help="Comma-separated FL county names (e.g. Brevard,Orange)")
    ap.add_argument("--batch", action="store_true", help="Rotate through FL_PRIORITY_COUNTIES by ISO week")
    ap.add_argument("--batch-size", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not SUPABASE_KEY and not args.dry_run:
        print("FATAL: SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY not set", file=sys.stderr)
        sys.exit(1)

    if args.counties:
        names = [c.strip() for c in args.counties.split(",") if c.strip()]
        counties = [(n, slugify_county(n)) for n in names]
    elif args.batch:
        week = datetime.now(timezone.utc).isocalendar().week
        n_batches = max(1, -(-len(FL_PRIORITY_COUNTIES) // args.batch_size))
        batch_idx = week % n_batches
        start = batch_idx * args.batch_size
        counties = FL_PRIORITY_COUNTIES[start:start + args.batch_size]
        if not any(slug == "brevard" for _, slug in counties):
            counties = [("Brevard", "brevard")] + counties  # flagship county every run
    else:
        counties = [("Brevard", "brevard")]

    telegram(f"[homeharvest_ingest] starting run: counties={counties} dry_run={args.dry_run}")
    run(counties, args.dry_run)


if __name__ == "__main__":
    main()
