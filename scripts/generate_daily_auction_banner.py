#!/usr/bin/env python3
"""Daily multi-county auction result banner + social post generator.

Picks one real completed FL auction per run, rotating across counties
(excludes counties featured in social_banner_history in the last 7 days),
renders a 1200x630 PNG banner via Playwright/Chromium, uploads it to the
'social-banners' Supabase Storage bucket, writes the post copy + banner URL
to social_content_queue (status='draft' -- never auto-published, see
supabase/migrations/20260815_daily_auction_banner.sql), and records the pick
in social_banner_history so the next run rotates to a different county.

Real data only. "We predicted X" language is only used when the property has
a real row in biddeed_report_predictions (rare) -- otherwise the post is
purely factual (sold price, county, property type, sale date).

Equity-claim safety (mirrors #19129, the fix applied to
generate_property_spotlight_content.py for the identical failure mode):
"% under value" claims are restricted to sale_type='foreclosure' rows with a
value_estimate = COALESCE(market_value, po_market_value, po_avm_value,
quality-filtered assessed_value), plaintiff not an HOA/condo association
(those are junior-lien foreclosures where the first mortgage can survive the
sale -- a "58/98% discount" claim on those is false, the buyer doesn't get
clean title for that price), and equity_dollars > 15% of sold_amount. If no
county has a clean equity-claim candidate, CANDIDATE_SQL_FALLBACK is used
instead: a plain factual sale post with no value comparison at all.

Additional guards found during this session, not present in #19129:

1. Rows where judgment_amount is far above effective_sold_amount (winning
   bid well under the judgment) are excluded from the equity-claim tier. A
   normal foreclosure's opening bid floors at the judgment amount, so a
   sold_amount under half of judgment_amount is either a data-capture error
   or an unverifiable junior/redemption scenario -- same unquantified-risk
   category as the HOA/condo carve-out, caught by inspecting a candidate row
   live (bay county, plaintiff field corrupted to the literal string
   "Max Bid:", judgment_amount $54,768 vs effective_sold_amount $1,100).

2. discount_pct is capped at 90% for the equity-claim tier. Ordering by
   biggest-discount-first repeatedly surfaced >98% "discount" rows this
   session even after guard #1 and the #19129 HOA/condo + assessed-value-
   quality filters -- e.g. a $1.1M market_value / $5,001 sold_amount
   Sarasota row with a legitimate-looking securitized-trust plaintiff and no
   judgment_amount to cross-check. Three consecutive top-ranked candidates
   this session (98.7%, 99.7%, 99.5%) were all judged implausible on manual
   inspection; a 90% ceiling is a blunt but evidence-grounded backstop given
   this repo's own property_spotlight fix (#19129) explicitly documents
   plaintiff=NULL/small-judgment rows as an unsolved, real data ceiling.
   Rows above the cap fall through to CANDIDATE_SQL_FALLBACK (no value
   claim) rather than being silently dropped.
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import date

from playwright.sync_api import sync_playwright

SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ACCESS_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
PROJECT_REF = "mocerqjnksmhcjzxrewo"

NAVY = "#0B1929"
ORANGE = "#F97316"
LOOKBACK_DAYS = 7
# GHA runners get Playwright's own bundled Chromium via
# `playwright install chromium` (no override needed). Local/sandbox dev
# environments without that download can point at a system browser instead.
CHROMIUM_PATH = os.environ.get("PLAYWRIGHT_CHROMIUM_PATH")

#  Mirrors the clean-row + equity-claim guardrails in
#  scripts/generate_property_spotlight_content.py (issue #19088, formula
#  fixed in #19129): naive "biggest discount" ranking over raw
#  sold_amount/assessed_value surfaces two distinct misleading-claim risks --
#  (a) data-entry artifacts (e.g. a $1,300 sold_amount against a $1.28M
#  market value), and (b) real but misleading rows: HOA/condo-association
#  junior-lien foreclosures where a small judgment lets the association win
#  for a token amount while the first mortgage survives the sale, making a
#  "% under value" claim false (the buyer doesn't get clean title for that
#  price). tier1_authoritative + recent verification + assessed_value_source
#  exclusions + repeated-value dedup + sale_type='foreclosure'-only +
#  plaintiff HOA/condo exclusion + equity_dollars > 15% of sold_amount filter
#  all of these out before a discount claim is made.
CANDIDATE_SQL_WITH_EQUITY = """
WITH recent_counties AS (
  SELECT DISTINCT county FROM public.social_banner_history
  WHERE posted_date >= CURRENT_DATE - interval '%(lookback)s days'
),
base AS (
  SELECT *,
    COALESCE(tier1_sold_amount, sold_amount) AS effective_sold_amount,
    CASE
      WHEN assessed_value_source IS NOT NULL
        AND assessed_value_source NOT ILIKE '%%inferred%%'
        AND assessed_value_source NOT ILIKE '%%fallback%%'
        AND assessed_value_source NOT ILIKE '%%proxy%%'
        AND assessed_value_source NOT ILIKE '%%arv%%'
        AND assessed_value_source NOT ILIKE '%%bid_decisions%%'
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
    AND (property_address IS NOT NULL AND property_address NOT ILIKE '%%Withdrawn%%')
    AND sale_type = 'foreclosure'
    AND COALESCE(tier1_sold_amount, sold_amount) > 1000
    AND parcel_id IS NOT NULL
    AND parcel_id <> 'Property Appraiser'
    AND (plaintiff IS NULL OR plaintiff !~* '(condominium|homeowners|community association|owners association| hoa )')
    AND (judgment_amount IS NULL OR COALESCE(tier1_sold_amount, sold_amount) >= 0.5 * judgment_amount)
    AND county IS NOT NULL
    AND county NOT IN (SELECT county FROM recent_counties)
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
    (value_estimate - effective_sold_amount) AS equity_dollars
  FROM valued
  WHERE value_estimate IS NOT NULL
),
deduped_parcel AS (
  SELECT DISTINCT ON (county, parcel_id) *
  FROM priced
  ORDER BY county, parcel_id, effective_sold_amount IS NOT NULL DESC, created_at DESC
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
  LEFT JOIN value_repeats vr ON vr.county = d.county AND vr.value_estimate = d.value_estimate
  WHERE vr.county IS NULL
    AND equity_dollars > 0.15 * effective_sold_amount
    AND equity_dollars <= 0.90 * d.value_estimate
)
SELECT
  id, county, city, property_address, parcel_id, case_number, sale_type,
  property_type, beds, baths, auction_date, effective_sold_amount,
  value_estimate AS effective_market_value, value_source,
  ROUND(((equity_dollars / value_estimate) * 100)::numeric, 1) AS discount_pct
FROM clean
ORDER BY (equity_dollars / value_estimate) DESC, auction_date DESC
LIMIT 1
""" % {"lookback": LOOKBACK_DAYS}

# Fallback when no county has a clean equity-claim candidate: a plain,
# factual "recent sale" post per the issue spec -- no discount language,
# just address/county/sold amount/property type. Same source-quality and
# rotation filters, minus the equity/plaintiff restrictions since no value
# comparison is being claimed.
CANDIDATE_SQL_FALLBACK = """
WITH recent_counties AS (
  SELECT DISTINCT county FROM public.social_banner_history
  WHERE posted_date >= CURRENT_DATE - interval '%(lookback)s days'
)
SELECT
  id, county, city, property_address, parcel_id, case_number, sale_type,
  property_type, beds, baths, auction_date,
  COALESCE(tier1_sold_amount, sold_amount) AS effective_sold_amount,
  NULL::numeric AS effective_market_value, NULL::text AS value_source,
  NULL::numeric AS discount_pct
FROM public.multi_county_auctions
WHERE tier1_authoritative = true
  AND tier1_verified_at >= now() - interval '30 days'
  AND tier1_sale_status IS NOT NULL
  AND tier1_sale_status NOT IN ('REDEEMED', 'RESCHEDULED')
  AND (property_address IS NOT NULL AND property_address NOT ILIKE '%%Withdrawn%%')
  AND COALESCE(tier1_sold_amount, sold_amount) > 1000
  AND county IS NOT NULL
  AND county NOT IN (SELECT county FROM recent_counties)
ORDER BY auction_date DESC
LIMIT 1
""" % {"lookback": LOOKBACK_DAYS}


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


def rest_get(path: str):
    result = subprocess.run(
        [
            "curl", "-s", f"{SUPABASE_URL}/rest/v1/{path}",
            "-H", f"apikey: {SERVICE_ROLE_KEY}",
            "-H", f"Authorization: Bearer {SERVICE_ROLE_KEY}",
        ],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def rest_insert(table: str, rows: list):
    payload = json.dumps(rows)
    with open(f"/tmp/_{table}_insert.json", "w") as f:
        f.write(payload)
    result = subprocess.run(
        [
            "curl", "-s", "-w", "\n%{http_code}",
            f"{SUPABASE_URL}/rest/v1/{table}",
            "-H", f"apikey: {SERVICE_ROLE_KEY}",
            "-H", f"Authorization: Bearer {SERVICE_ROLE_KEY}",
            "-H", "Content-Type: application/json",
            "-H", "Prefer: return=representation",
            "--data", f"@/tmp/_{table}_insert.json",
        ],
        capture_output=True, text=True, check=True,
    )
    os.remove(f"/tmp/_{table}_insert.json")
    lines = result.stdout.strip().split("\n")
    http_code = lines[-1]
    body = "\n".join(lines[:-1])
    if http_code != "201":
        raise RuntimeError(f"INSERT into {table} failed (HTTP {http_code}): {body}")
    return json.loads(body)


def money(n):
    return f"${float(n):,.0f}"


def county_label(county: str) -> str:
    return county.replace("_", " ").title()


def sale_type_label(sale_type):
    return "Tax Deed" if sale_type == "tax_deed" else "Foreclosure"


def location_label(row) -> str:
    city = (row.get("city") or "").strip()
    county = county_label(row["county"])
    return f"{city}, {county} County, FL" if city else f"{county} County, FL"


VALUE_LABELS = {
    "market_value": "Market value",
    "po_market_value": "Market value",
    "po_avm_value": "Estimated market value",
    "assessed_value": "County assessed value",
}


def value_label(row) -> str:
    return VALUE_LABELS.get(row.get("value_source"), "Estimated value")


def fetch_prediction(county: str, parcel_id):
    if not parcel_id:
        return None
    rows = rest_get(
        f"biddeed_report_predictions?select=predicted_ceiling,outcome_status"
        f"&county=eq.{county}&parcel_id=eq.{parcel_id}&predicted_ceiling=not.is.null&limit=1"
    )
    return rows[0] if rows else None


def build_post_copy(row, prediction) -> str:
    lines = [
        f"Closed {sale_type_label(row['sale_type'])} sale -- {location_label(row)}",
        "",
        f"Sold: {money(row['effective_sold_amount'])}",
    ]
    if row.get("effective_market_value"):
        lines.append(f"{value_label(row)}: {money(row['effective_market_value'])}")
    if row.get("discount_pct") is not None:
        lines.append(f"Paper equity: {row['discount_pct']}% under {value_label(row).lower()}")
    lines.append(f"Sale date: {row['auction_date']}")
    if row.get("property_type"):
        lines.append(f"Property type: {row['property_type']}")
    if prediction and prediction.get("predicted_ceiling") and prediction.get("outcome_status") not in (None, "PENDING"):
        lines.append("")
        lines.append(f"BidDeed.AI's model ceiling for this parcel was {money(prediction['predicted_ceiling'])} -- outcome: {prediction['outcome_status']}.")
    lines += [
        "",
        "See your county's auctions free -> biddeed.ai",
        "",
        "Informational only -- not legal, financial, or investment advice. Verify independently before bidding.",
    ]
    return "\n".join(lines)


def render_banner_html(row) -> str:
    address = (row.get("property_address") or "").strip()
    county = county_label(row["county"])
    sold = money(row["effective_sold_amount"])
    discount_badge = ""
    if row.get("discount_pct") is not None and float(row["discount_pct"]) > 0:
        discount_badge = f'<div class="badge">{row["discount_pct"]}% UNDER {value_label(row).upper()}</div>'
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap" rel="stylesheet">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; font-family:'Inter',sans-serif; }}
  body {{ width:1200px; height:630px; background:{NAVY};
    background-image: radial-gradient(circle at 85% 15%, rgba(249,115,22,0.18), transparent 45%);
    color:#fff; position:relative; overflow:hidden; }}
  .wrap {{ padding:64px 72px; height:100%; display:flex; flex-direction:column; justify-content:space-between; }}
  .brand {{ font-size:26px; font-weight:900; letter-spacing:1px; }}
  .brand .accent {{ color:{ORANGE}; }}
  .county-tag {{ display:inline-block; background:rgba(249,115,22,0.15); color:{ORANGE};
    border:1px solid {ORANGE}; border-radius:6px; padding:6px 16px; font-size:20px;
    font-weight:700; letter-spacing:0.5px; margin-bottom:20px; }}
  .address {{ font-size:44px; font-weight:800; line-height:1.15; max-width:980px; }}
  .sold-row {{ display:flex; align-items:baseline; gap:24px; margin-top:28px; }}
  .sold-label {{ font-size:22px; color:#94a3b8; font-weight:600; text-transform:uppercase; letter-spacing:1px; }}
  .sold-amount {{ font-size:72px; font-weight:900; color:{ORANGE}; }}
  .badge {{ display:inline-block; margin-top:16px; background:{ORANGE}; color:{NAVY};
    font-size:22px; font-weight:800; padding:8px 20px; border-radius:6px; }}
  .cta {{ font-size:24px; font-weight:700; }}
  .cta .accent {{ color:{ORANGE}; }}
  .divider {{ height:4px; width:100%; background:linear-gradient(90deg,{ORANGE} 0%, transparent 100%); margin:20px 0; }}
</style>
</head>
<body>
  <div class="wrap">
    <div>
      <div class="brand">BidDeed<span class="accent">.AI</span></div>
      <div class="divider"></div>
      <div class="county-tag">{county} COUNTY, FL &middot; {sale_type_label(row['sale_type']).upper()}</div>
      <div class="address">{address}</div>
      <div class="sold-row">
        <span class="sold-label">Sold</span>
        <span class="sold-amount">{sold}</span>
      </div>
      {discount_badge}
    </div>
    <div class="cta">See your county's auctions free -> <span class="accent">biddeed.ai</span></div>
  </div>
</body>
</html>"""


def render_banner_png(row, out_path: str):
    html = render_banner_html(row)
    launch_kwargs = {"args": ["--no-sandbox"]}
    if CHROMIUM_PATH:
        launch_kwargs["executable_path"] = CHROMIUM_PATH
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        try:
            page = browser.new_page(viewport={"width": 1200, "height": 630})
            page.set_content(html, wait_until="networkidle")
            page.screenshot(path=out_path)
        finally:
            browser.close()


def upload_banner(local_path: str, storage_key: str) -> str:
    result = subprocess.run(
        [
            "curl", "-s", "-w", "\n%{http_code}",
            f"{SUPABASE_URL}/storage/v1/object/social-banners/{storage_key}",
            "-H", f"apikey: {SERVICE_ROLE_KEY}",
            "-H", f"Authorization: Bearer {SERVICE_ROLE_KEY}",
            "-H", "Content-Type: image/png",
            "-H", "x-upsert: true",
            "--data-binary", f"@{local_path}",
        ],
        capture_output=True, text=True, check=True,
    )
    lines = result.stdout.strip().split("\n")
    http_code = lines[-1]
    if http_code not in ("200", "201"):
        raise RuntimeError(f"Banner upload failed (HTTP {http_code}): {result.stdout}")
    return f"{SUPABASE_URL}/storage/v1/object/public/social-banners/{storage_key}"


def content_hash(county: str, property_id: str, posted_date: str) -> str:
    key = f"auction_banner|{county}|{property_id}|{posted_date}"
    return hashlib.sha256(key.encode()).hexdigest()


def main():
    dry_run = "--dry-run" in sys.argv

    rows = mgmt_sql(CANDIDATE_SQL_WITH_EQUITY)
    if not rows:
        print("No clean equity-claim candidate this run -- falling back to a plain factual sale post.", file=sys.stderr)
        rows = mgmt_sql(CANDIDATE_SQL_FALLBACK)
    if not rows:
        print("DATA CEILING: no candidate auction rows outside the 7-day county rotation window. "
              "Nothing to generate this run.", file=sys.stderr)
        sys.exit(0)

    row = rows[0]
    today = date.today().isoformat()
    print(f"Selected: {row['county']} / {row['property_address']} / sold {money(row['effective_sold_amount'])}", file=sys.stderr)

    prediction = fetch_prediction(row["county"], row.get("parcel_id"))
    post_text = build_post_copy(row, prediction)

    if dry_run:
        print(post_text)
        return

    property_id = row.get("parcel_id") or row["id"]
    png_path = f"/tmp/banner_{row['county']}_{today}.png"
    render_banner_png(row, png_path)
    storage_key = f"{today}/{row['county']}_{property_id}.png".replace(" ", "_")
    media_url = upload_banner(png_path, storage_key)
    print(f"Banner uploaded: {media_url}", file=sys.stderr)

    h = content_hash(row["county"], str(property_id), today)
    queue_row = {
        "content_hash": h,
        "target_platform": "linkedin_personal",
        "source_type": "auction_banner",
        "source_ref": f"{row['county']}:{property_id}",
        "content_text": post_text,
        "media_url": media_url,
        "status": "draft",
        "scheduled_for": today,
    }
    inserted = rest_insert("social_content_queue", [queue_row])
    print(f"social_content_queue row: {inserted[0]['id']}", file=sys.stderr)

    history_row = {"county": row["county"], "property_id": str(property_id), "posted_date": today}
    rest_insert("social_banner_history", [history_row])
    print(f"social_banner_history recorded: {row['county']} / {today}", file=sys.stderr)

    os.remove(png_path)


if __name__ == "__main__":
    main()
