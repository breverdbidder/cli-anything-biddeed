#!/usr/bin/env python3
"""Generate property-spotlight posts (source_type='property_spotlight') for
social_content_queue -- one real closed deal per post, one post per
target_platform (linkedin_personal, telegram, reddit, bigger_pockets).

Issue: breverdbidder/cli-anything-biddeed#19088
Equity formula: breverdbidder/cli-anything-biddeed#19129 (AMEND #19128)
Additive only -- does not touch the county_snapshot generator (see
supabase/functions/social-content-generator/index.ts).

Source filter (see issue body for full spec + rationale):
  multi_county_auctions, tier1_authoritative=true, tier1_verified_at in the
  last 30 days, tier1_sale_status not REDEEMED/RESCHEDULED/withdrawn,
  effective sold amount > $1,000, sale_type='foreclosure' only (#19129 item 4
  -- outstanding_certs_total has zero coverage on sold tax_deed rows, so
  surviving-lien risk is unknown for tax deeds; foreclosure-only avoids
  presenting an equity claim we can't back), real parcel_id, deduped per
  (county, parcel_id), and (county, value_estimate) pairs that repeat 3+
  times dropped as placeholder valuations. Rows with no auction_url/
  realforeclose_url in the row are dropped -- the issue requires a source
  citation "already in the row"; this script never fabricates one.

Value estimate (#19129 item 1-2): first non-null of market_value,
po_market_value, po_avm_value, assessed_value (assessed_value only counts if
its own assessed_value_source clears the same inferred/fallback/proxy/arv/
bid_decisions/opening_bid_derived exclusions as before). value_source is
persisted per row (social_content_queue.value_source) so copy can say
"market value" vs "county assessed value" accurately -- never assessed_value
labeled as market value.

Equity filter (#19129 item 3): equity_dollars > 15% of effective_sold_amount
-- no negative or trivial-equity properties featured as wins.

HOA/condo-association lien exclusion (found during this session, not in the
original #19129 text, logged as a deviation): a chunk of extreme-equity rows
(one seen at 33,127%) trace to plaintiff = a condo/HOA association with a
small judgment_amount -- i.e. a junior-lien foreclosure where the first
mortgage is not extinguished by the sale. Presenting the full value_estimate
minus the token winning bid as "paper equity" would be misleading in the same
way #19129 item 4 already flagged for tax deeds (surviving senior claim,
different lien type). Excluded by plaintiff name pattern where identifiable;
rows with plaintiff=NULL and a judgment_amount small relative to
value_estimate carry the same unquantified risk but aren't filtered here --
no reliable lien-priority column exists to classify them. Flagged in the
session report, not solved -- this is a real data ceiling, see Findings.

Copy (#19129 item 5): always "Paper equity" / "estimated equity", never
"profit" -- excludes rehab, closing costs, holding costs.

Pacing: highest-paper-equity-dollar rows go out first, PACE_PER_DAY
properties per platform per day, via the scheduled_for column
(migration 20260815_social_content_queue_add_scheduled_for.sql).
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import date, timedelta

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ACCESS_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
PROJECT_REF = "mocerqjnksmhcjzxrewo"

PACE_PER_DAY = 3
PLATFORMS = ["linkedin_personal", "telegram", "reddit", "bigger_pockets"]

CLEAN_ROW_SQL = """
WITH base AS (
  SELECT *,
    COALESCE(tier1_sold_amount, sold_amount) AS effective_sold_amount,
    CASE
      WHEN assessed_value_source IS NOT NULL
        AND assessed_value_source NOT ILIKE '%inferred%'
        AND assessed_value_source NOT ILIKE '%fallback%'
        AND assessed_value_source NOT ILIKE '%proxy%'
        AND assessed_value_source NOT ILIKE '%arv%'
        AND assessed_value_source NOT ILIKE '%bid_decisions%'
        AND assessed_value_source <> 'opening_bid_derived'
        AND assessed_value > 0
      THEN assessed_value
      ELSE NULL
    END AS quality_assessed_value
  FROM public.multi_county_auctions
  WHERE tier1_authoritative = true
    AND tier1_verified_at >= now() - interval '30 days'
    AND tier1_sale_status IS NOT NULL
    AND tier1_sale_status NOT IN ('REDEEMED', 'RESCHEDULED')
    AND (property_address IS NULL OR property_address NOT ILIKE '%Withdrawn%')
    AND sale_type = 'foreclosure'
    AND COALESCE(tier1_sold_amount, sold_amount) > 1000
    AND parcel_id IS NOT NULL
    AND parcel_id <> 'Property Appraiser'
    AND (plaintiff IS NULL OR plaintiff !~* '(condominium|homeowners|community association|owners association| hoa )')
),
valued AS (
  SELECT *,
    COALESCE(market_value, po_market_value, po_avm_value, quality_assessed_value) AS value_estimate,
    CASE
      WHEN market_value IS NOT NULL THEN 'market_value'
      WHEN po_market_value IS NOT NULL THEN 'po_market_value'
      WHEN po_avm_value IS NOT NULL THEN 'po_avm_value'
      WHEN quality_assessed_value IS NOT NULL THEN 'assessed_value'
      ELSE NULL
    END AS value_source
  FROM base
),
priced AS (
  SELECT *,
    (value_estimate - effective_sold_amount) AS equity_dollars,
    ((value_estimate - effective_sold_amount) / NULLIF(effective_sold_amount, 0)) * 100 AS equity_pct
  FROM valued
  WHERE value_estimate IS NOT NULL
),
deduped_parcel AS (
  SELECT DISTINCT ON (county, parcel_id) *
  FROM priced
  ORDER BY county, parcel_id,
    (effective_sold_amount IS NOT NULL) DESC,
    created_at DESC
),
value_repeats AS (
  SELECT county, value_estimate, COUNT(*) AS cnt
  FROM deduped_parcel
  GROUP BY county, value_estimate
  HAVING COUNT(*) >= 3
),
clean AS (
  SELECT d.*
  FROM deduped_parcel d
  LEFT JOIN value_repeats vr
    ON vr.county = d.county AND vr.value_estimate = d.value_estimate
  WHERE vr.county IS NULL
    AND equity_dollars > 0.15 * effective_sold_amount
)
SELECT
  id, county, city, parcel_id, case_number, sale_type, tier1_sale_status,
  effective_sold_amount, value_estimate, value_source,
  auction_date, tier1_verified_at,
  COALESCE(auction_url, realforeclose_url) AS source_url,
  ROUND(equity_dollars::numeric, 2) AS equity_dollars,
  ROUND(equity_pct::numeric, 1) AS equity_pct
FROM clean
WHERE COALESCE(auction_url, realforeclose_url) IS NOT NULL
ORDER BY equity_dollars DESC
"""


def mgmt_sql(query: str):
    payload = json.dumps({"query": query})
    result = subprocess.run(
        [
            "curl", "-s", "-X", "POST",
            f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
            "-H", f"Authorization: Bearer {ACCESS_TOKEN}",
            "-H", "Content-Type: application/json",
            "-H", "User-Agent: cli-anything-biddeed-cc/1.0",
            "--data", payload,
        ],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    if isinstance(data, dict) and "message" in data:
        raise RuntimeError(f"SQL error: {data['message']}")
    return data


def money(n):
    return f"${float(n):,.0f}"


def county_label(county: str) -> str:
    return county.replace("_", " ").title()


def sale_type_label(sale_type: str) -> str:
    return "Tax Deed" if sale_type == "tax_deed" else "Foreclosure"


def location_label(row) -> str:
    city = (row.get("city") or "").strip()
    county = county_label(row["county"])
    return f"{city}, {county} County, FL" if city else f"{county} County, FL"


VALUE_SOURCE_LABEL = {
    "market_value": "market value",
    "po_market_value": "market value estimate",
    "po_avm_value": "AVM market estimate",
    "assessed_value": "county assessed value",
}


def value_label(row) -> str:
    return VALUE_SOURCE_LABEL.get(row["value_source"], "estimated value")


def equity_line(row) -> str:
    eq = float(row["equity_dollars"])
    pct = row.get("equity_pct")
    label = value_label(row)
    if eq >= 0:
        pct_str = f" ({float(pct):.0f}% under {label})" if pct is not None else ""
        return f"Paper equity: {money(eq)}{pct_str}"
    pct_str = f" ({abs(float(pct)):.0f}% over {label})" if pct is not None else ""
    return f"Sold above {label} by {money(abs(eq))}{pct_str} -- not every lot is a discount, which is exactly why you screen before bidding"


DISCLAIMER = "Informational only -- not legal, financial, or investment advice. Verify independently before bidding."


def build_linkedin_telegram(row) -> str:
    return "\n".join([
        f"Closed {sale_type_label(row['sale_type'])} deal -- {location_label(row)}:",
        "",
        f"Sold: {money(row['effective_sold_amount'])}",
        f"{value_label(row).capitalize()}: {money(row['value_estimate'])}",
        equity_line(row),
        f"Sale date: {row['auction_date']}",
        "",
        f"Source (verify yourself): {row['source_url']}",
        "",
        "Real closed auction data from BidDeed.AI's pipeline -- one property, one verified outcome.",
        "",
        DISCLAIMER,
    ])


def build_reddit(row) -> str:
    return "\n".join([
        f"{sale_type_label(row['sale_type'])} sale closed in {location_label(row)}:",
        "",
        f"- Sold: {money(row['effective_sold_amount'])}",
        f"- {value_label(row).capitalize()}: {money(row['value_estimate'])}",
        f"- {equity_line(row)}",
        f"- Sale date: {row['auction_date']}",
        f"- Source (public auction record, check it yourself): {row['source_url']}",
        "",
        "Sharing because real closed-deal numbers are harder to find than upcoming-lot lists. "
        "Pulled this from a FL auction data pipeline I work on (BidDeed.AI) -- happy to answer "
        "questions about how the assessed-value comparison works or FL auction mechanics generally. "
        "Not trying to pitch anything here.",
        "",
        DISCLAIMER,
    ])


def build_bigger_pockets(row) -> str:
    return "\n".join([
        f"Market update -- {location_label(row)} {sale_type_label(row['sale_type']).lower()} auction result:",
        "",
        f"A property in {location_label(row)} closed at {money(row['effective_sold_amount'])} against a "
        f"{value_label(row)} of {money(row['value_estimate'])} ({equity_line(row).lower()}), sale date {row['auction_date']}.",
        "",
        f"Public record source: {row['source_url']}",
        "",
        "Tracking these as part of BidDeed.AI/Everest Capital's FL auction pipeline (67-county coverage). "
        "Posting real closed outcomes, not upcoming-lot hype -- figured this board would find the comp useful.",
        "",
        DISCLAIMER,
    ])


BUILDERS = {
    "linkedin_personal": build_linkedin_telegram,
    "telegram": build_linkedin_telegram,
    "reddit": build_reddit,
    "bigger_pockets": build_bigger_pockets,
}


def content_hash(platform: str, county: str, parcel_id: str) -> str:
    key = f"property_spotlight|{platform}|{county}|{parcel_id}"
    return hashlib.sha256(key.encode()).hexdigest()


def main():
    dry_run = "--dry-run" in sys.argv

    rows = mgmt_sql(CLEAN_ROW_SQL)
    print(f"Clean, citable rows: {len(rows)} across {len(set(r['county'] for r in rows))} counties", file=sys.stderr)

    today = date.today()
    inserts = []
    skipped_existing = 0

    for i, row in enumerate(rows):
        day_offset = i // PACE_PER_DAY
        scheduled_for = (today + timedelta(days=day_offset)).isoformat()
        for platform in PLATFORMS:
            h = content_hash(platform, row["county"], row["parcel_id"])
            content_text = BUILDERS[platform](row)
            inserts.append({
                "content_hash": h,
                "target_platform": platform,
                "source_type": "property_spotlight",
                "source_ref": f"{row['county']}:{row['parcel_id']}",
                "content_text": content_text,
                "status": "pending",
                "scheduled_for": scheduled_for,
                "value_source": row["value_source"],
                "_equity_dollars": float(row["equity_dollars"]),
                "_day_offset": day_offset,
            })

    print(f"Prepared {len(inserts)} candidate rows ({len(rows)} properties x {len(PLATFORMS)} platforms)", file=sys.stderr)

    if dry_run:
        by_day = {}
        by_value_source = {}
        for ins in inserts:
            by_day.setdefault(ins["_day_offset"], 0)
            by_day[ins["_day_offset"]] += 1
            by_value_source.setdefault(ins["value_source"], 0)
            by_value_source[ins["value_source"]] += 1
        print(json.dumps({
            "total_candidates": len(inserts),
            "by_day_offset": by_day,
            "by_value_source": by_value_source,
            "sale_types": sorted(set(r["sale_type"] for r in rows)),
        }, indent=2))
        return

    # Insert in batches via PostgREST, checking existing content_hash first
    # (belt-and-suspenders dedup -- content_hash also has implicit dedup via
    # this check since the table has no unique constraint on content_hash).
    hashes = [ins["content_hash"] for ins in inserts]
    existing_hashes = set()
    batch_size = 200
    for i in range(0, len(hashes), batch_size):
        batch = hashes[i:i + batch_size]
        in_list = ",".join(batch)
        result = subprocess.run(
            [
                "curl", "-s",
                f"{SUPABASE_URL}/rest/v1/social_content_queue?select=content_hash&content_hash=in.({in_list})",
                "-H", f"apikey: {SERVICE_ROLE_KEY}",
                "-H", f"Authorization: Bearer {SERVICE_ROLE_KEY}",
            ],
            capture_output=True, text=True, check=True,
        )
        for r in json.loads(result.stdout):
            existing_hashes.add(r["content_hash"])

    to_insert = [ins for ins in inserts if ins["content_hash"] not in existing_hashes]
    skipped_existing = len(inserts) - len(to_insert)
    print(f"Already queued (skipped): {skipped_existing}", file=sys.stderr)
    print(f"New rows to insert: {len(to_insert)}", file=sys.stderr)

    clean_rows = []
    for ins in to_insert:
        clean_rows.append({k: v for k, v in ins.items() if not k.startswith("_")})

    inserted = 0
    for i in range(0, len(clean_rows), batch_size):
        batch = clean_rows[i:i + batch_size]
        payload = json.dumps(batch)
        with open("/tmp/_spotlight_batch.json", "w") as f:
            f.write(payload)
        result = subprocess.run(
            [
                "curl", "-s", "-w", "\n%{http_code}",
                f"{SUPABASE_URL}/rest/v1/social_content_queue",
                "-H", f"apikey: {SERVICE_ROLE_KEY}",
                "-H", f"Authorization: Bearer {SERVICE_ROLE_KEY}",
                "-H", "Content-Type: application/json",
                "-H", "Prefer: return=minimal",
                "--data", f"@/tmp/_spotlight_batch.json",
            ],
            capture_output=True, text=True, check=True,
        )
        lines = result.stdout.strip().split("\n")
        http_code = lines[-1]
        if http_code != "201":
            print(f"INSERT BATCH FAILED (HTTP {http_code}): {result.stdout}", file=sys.stderr)
            sys.exit(1)
        inserted += len(batch)

    print(f"Inserted {inserted} rows", file=sys.stderr)
    os.remove("/tmp/_spotlight_batch.json") if os.path.exists("/tmp/_spotlight_batch.json") else None


if __name__ == "__main__":
    main()
