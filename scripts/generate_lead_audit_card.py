#!/usr/bin/env python3
"""Personalized lead-audit card template -- two data-bound variants on one
shared renderer (issue: personalized lead-audit card, outreach + social).

Reuses the render/upload/insert pipeline shipped in
scripts/generate_daily_auction_banner.py (#19128/#19129/#19130): same
Playwright HTML->PNG render, same 'social-banners' storage bucket (new
'lead-cards/' key prefix), same social_content_queue insert shape, same
navy/orange brand tokens.

Variant A (personalized, per-lead, email-attachment asset):
  For lead_profiles rows with source='auction_llc_expansion' AND
  bidder_activity_tier='INVESTOR_LLC', joins to multi_county_auctions on
  winning_bidder (case/whitespace-insensitive) + county to compute: auctions
  won, total sold_amount deployed, and count of upcoming auctions
  (auction_date within 30 days, sold_amount IS NULL) in the lead's county.
  Leads with zero auctions-won matches are excluded by the query itself
  (HAVING COUNT > 0) -- nothing fabricated, nothing padded.

  CORRECTION (issue #19174 -> #19174-followup, fixed on 2026-08-17):
  `bidder_activity_tier` is now a real, persisted column on lead_profiles
  (added and backfilled this session -- see supabase/migrations for the
  ALTER/UPDATE), not a one-off query. It is computed once via regex against
  `name` in this priority order: HOA_CONDO_ASSOCIATION, then
  RESORT_TIMESHARE_MAJOR, then INSTITUTIONAL_LENDER, then INVESTOR_LLC (all
  other `, LLC`/`, INC.`/`INCORPORATED` names), else OTHER. Live counts for
  source='auction_llc_expansion' (n=288): INVESTOR_LLC=185,
  INSTITUTIONAL_LENDER=48, HOA_CONDO_ASSOCIATION=44,
  RESORT_TIMESHARE_MAJOR=7, OTHER=4. The 185 figure referenced in the
  original #19174 brief was correct; the bug was that the filter was never
  applied because the column never existed until now.

  FINDING (still true post-fix, a fit-for-purpose note not a fabrication
  issue): institutional loan servicers/plaintiffs (e.g. "LAKEVIEW LOAN
  SERVICING, LLC", "FREEDOM MORTGAGE CORPORATION") that credit-bid their own
  foreclosure back are now correctly excluded by the INSTITUTIONAL_LENDER
  tier (checked before INVESTOR_LLC in the CASE, so "...SERVICING, LLC"
  matches lender first despite the trailing "LLC"). One known regex gap
  remains: "THE FALLS OF INVERRARY CONDOMINIUMS, INC." classifies as
  INVESTOR_LLC because the HOA regex requires the literal substring
  "CONDOMINIUM ASSOCIATION", not "CONDOMINIUMS" alone -- this is the
  brief's exact specified regex, reproduced as given, not a bug introduced
  here. Flagged for a human look at the regex, not silently patched.

  DATA-QUALITY FIX (found live, not in the brief): some multi_county_auctions
  rows have winning_bidder already populated for a FUTURE auction_date with
  sold_amount still NULL (e.g. a lee county row dated 2026-08-20, three days
  after this session ran on 2026-08-17). That is a pre-populated plaintiff/
  anticipated-bidder placeholder, not a completed win, and counting it would
  overstate "auctions won." The join requires mca.auction_date <= CURRENT_DATE
  so only sales that have actually occurred are counted. Where a matched,
  already-occurred sale still lacks both sold_amount and tier1_sold_amount
  (a real data-capture gap, observed on 2 of the 288-population rows), "Total
  Deployed" renders as "N/A" rather than "$0" -- $0 would falsely claim zero
  spend on a lead who did win an auction; NULL means the dollar figure was
  never captured, not that it was zero.

Variant B (generic, per-county, social-ready draft):
  Reuses the county-rotation pattern from generate_daily_auction_banner.py
  (excludes counties featured in social_banner_history in the last 7 days)
  but swaps personalized stats for real county-level aggregates: completed
  auctions tracked (sold_amount IS NOT NULL) and upcoming auctions
  (auction_date within 30 days, sold_amount IS NULL).

Both variants insert into social_content_queue with status='draft' (never
picked up by social-publish-worker, which only queries status='pending' --
see 20260815_daily_auction_banner.sql). target_platform is set to the
closest existing enum value ('linkedin_personal' -- the only allowed value
this table's CHECK constraint offers is a genuine intended future channel
for both); source_type is the actual discriminator: 'lead_audit_card_a'
(email-attachment, never for direct social post -- see non-goals) vs
'lead_audit_card_b' (social-ready draft).
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
CHROMIUM_PATH = os.environ.get("PLAYWRIGHT_CHROMIUM_PATH")

VARIANT_A_SAMPLE_SQL = """
-- Reuses public.lead_auction_activity (supabase/migrations/20260817d_lead_auction_activity_view.sql)
-- for the auctions_won/total_deployed computation instead of re-joining
-- multi_county_auctions here -- single source of truth shared with
-- email/SMS/countdown-cron personalization surfaces (#19176 join-fix task).
WITH matched AS (
  SELECT laa.lead_id, laa.name, laa.county, laa.auctions_won, laa.total_deployed
  FROM public.lead_auction_activity laa
  JOIN public.lead_profiles lp ON lp.id = laa.lead_id
  WHERE lp.source = 'auction_llc_expansion'
    AND lp.bidder_activity_tier = 'INVESTOR_LLC'
    AND laa.auctions_won > 0
    AND NOT EXISTS (
      SELECT 1 FROM public.social_content_queue scq
      WHERE scq.source_type = 'lead_audit_card_a'
        AND scq.source_ref = 'lead_profiles:' || lp.id::text
    )
),
upcoming AS (
  SELECT county, COUNT(*) AS upcoming_count
  FROM public.multi_county_auctions
  WHERE auction_date BETWEEN CURRENT_DATE AND CURRENT_DATE + interval '30 days'
    AND sold_amount IS NULL
    AND (property_address IS NOT NULL AND property_address NOT ILIKE '%%Withdrawn%%')
  GROUP BY county
)
SELECT m.lead_id, m.name, m.county, m.auctions_won, m.total_deployed,
       COALESCE(u.upcoming_count, 0) AS upcoming_auctions
FROM matched m
LEFT JOIN upcoming u ON u.county = m.county
ORDER BY m.auctions_won DESC, m.lead_id
LIMIT %(limit)s
"""

VARIANT_A_POPULATION_SQL = """
SELECT source, investor_type, bidder_activity_tier, count(*) AS n
FROM public.lead_profiles
WHERE source = 'auction_llc_expansion'
GROUP BY 1, 2, 3
ORDER BY n DESC
"""

VARIANT_B_COUNTY_SQL = """
WITH recent_counties AS (
  SELECT DISTINCT county FROM public.social_banner_history
  WHERE posted_date >= CURRENT_DATE - interval '%(lookback)s days'
),
agg AS (
  SELECT county,
    COUNT(*) FILTER (WHERE sold_amount IS NOT NULL OR tier1_sold_amount IS NOT NULL) AS completed_auctions,
    COUNT(*) FILTER (
      WHERE sold_amount IS NULL
        AND auction_date BETWEEN CURRENT_DATE AND CURRENT_DATE + interval '30 days'
    ) AS upcoming_auctions
  FROM public.multi_county_auctions
  WHERE county IS NOT NULL
    AND (property_address IS NOT NULL AND property_address NOT ILIKE '%%Withdrawn%%')
  GROUP BY county
)
SELECT county, completed_auctions, upcoming_auctions
FROM agg
WHERE completed_auctions > 0
  AND county NOT IN (SELECT county FROM recent_counties)
ORDER BY completed_auctions DESC
LIMIT 1
""" % {"lookback": LOOKBACK_DAYS}


def mgmt_sql(query: str, params: dict = None):
    if params:
        query = query % params
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


def rest_insert(table: str, rows: list):
    payload = json.dumps(rows)
    tmp_path = f"/tmp/_{table}_insert.json"
    with open(tmp_path, "w") as f:
        f.write(payload)
    result = subprocess.run(
        [
            "curl", "-s", "-w", "\n%{http_code}",
            f"{SUPABASE_URL}/rest/v1/{table}",
            "-H", f"apikey: {SERVICE_ROLE_KEY}",
            "-H", f"Authorization: Bearer {SERVICE_ROLE_KEY}",
            "-H", "Content-Type: application/json",
            "-H", "Prefer: return=representation",
            "--data", f"@{tmp_path}",
        ],
        capture_output=True, text=True, check=True,
    )
    os.remove(tmp_path)
    lines = result.stdout.strip().split("\n")
    http_code = lines[-1]
    body = "\n".join(lines[:-1])
    if http_code != "201":
        raise RuntimeError(f"INSERT into {table} failed (HTTP {http_code}): {body}")
    return json.loads(body)


def upload_card(local_path: str, storage_key: str) -> str:
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
        raise RuntimeError(f"Card upload failed (HTTP {http_code}): {result.stdout}")
    return f"{SUPABASE_URL}/storage/v1/object/public/social-banners/{storage_key}"


def money(n):
    return f"${float(n):,.0f}"


def county_label(county: str) -> str:
    return county.replace("_", " ").title()


def county_slug(county: str) -> str:
    return county.replace("_", "-").lower()


def render_card_html(kicker: str, headline: str, stats: list, cta_county: str) -> str:
    """Shared frame -- same brand tokens/layout family as the daily banner.
    `stats` is a list of (label, value) pairs, up to 3."""
    stat_blocks = "".join(
        f'<div class="stat"><div class="stat-value">{v}</div>'
        f'<div class="stat-label">{l}</div></div>'
        for l, v in stats
    )
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
  .kicker {{ display:inline-block; background:rgba(249,115,22,0.15); color:{ORANGE};
    border:1px solid {ORANGE}; border-radius:6px; padding:6px 16px; font-size:20px;
    font-weight:700; letter-spacing:0.5px; margin-bottom:20px; }}
  .headline {{ font-size:40px; font-weight:800; line-height:1.15; max-width:1000px; }}
  .stats-row {{ display:flex; gap:56px; margin-top:36px; }}
  .stat-value {{ font-size:52px; font-weight:900; color:{ORANGE}; }}
  .stat-label {{ font-size:18px; color:#94a3b8; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; margin-top:6px; }}
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
      <div class="kicker">{kicker}</div>
      <div class="headline">{headline}</div>
      <div class="stats-row">{stat_blocks}</div>
    </div>
    <div class="cta">See {cta_county}'s auctions free -> <span class="accent">biddeed.ai/{county_slug(cta_county)}</span></div>
  </div>
</body>
</html>"""


def render_card_png(html: str, out_path: str):
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


def content_hash(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def run_variant_a(limit: int, dry_run: bool):
    population = mgmt_sql(VARIANT_A_POPULATION_SQL)
    print(f"Population check -- source='auction_llc_expansion': {json.dumps(population)}", file=sys.stderr)

    rows = mgmt_sql(VARIANT_A_SAMPLE_SQL, {"limit": limit})
    print(f"Matched leads with auctions_won > 0 (sample size requested={limit}): {len(rows)}", file=sys.stderr)
    if not rows:
        print("DATA CEILING: zero leads in source='auction_llc_expansion' have any "
              "winning_bidder match in multi_county_auctions. Nothing to generate.", file=sys.stderr)
        return []

    today = date.today().isoformat()
    generated = []
    for row in rows:
        name = row["name"]
        county = row["county"]
        auctions_won = row["auctions_won"]
        total_deployed = row.get("total_deployed")
        upcoming = row["upcoming_auctions"]

        deployed_display = money(total_deployed) if total_deployed else "N/A"
        stats = [
            ("Auctions Won", str(auctions_won)),
            ("Total Deployed", deployed_display),
            ("Upcoming (30d)", str(upcoming)),
        ]
        html = render_card_html(
            kicker=f"{county_label(county)} COUNTY, FL",
            headline=f"{name}'S AUCTION ACTIVITY",
            stats=stats,
            cta_county=county_label(county),
        )
        post_text = (
            f"{name} -- {county_label(county)} County auction activity\n\n"
            f"Auctions won: {auctions_won}\n"
            f"Total deployed: {deployed_display}\n"
            f"Upcoming auctions in {county_label(county)} County (next 30 days): {upcoming}\n\n"
            f"See {county_label(county)}'s auctions free -> biddeed.ai/{county_slug(county)}\n\n"
            "Informational only -- not legal, financial, or investment advice."
        )

        print(f"  [A] {name} / {county} / won={auctions_won} deployed={total_deployed} upcoming={upcoming}", file=sys.stderr)

        if dry_run:
            generated.append({"lead_id": row["lead_id"], "name": name, "county": county,
                               "auctions_won": auctions_won, "total_deployed": total_deployed,
                               "upcoming_auctions": upcoming, "post_text": post_text})
            continue

        png_path = f"/tmp/lead_card_{row['lead_id']}.png"
        render_card_png(html, png_path)
        storage_key = f"lead-cards/{today}/A_{row['lead_id']}.png"
        media_url = upload_card(png_path, storage_key)
        os.remove(png_path)

        h = content_hash("lead_audit_card_a", row["lead_id"], today)
        queue_row = {
            "content_hash": h,
            "target_platform": "linkedin_personal",
            "source_type": "lead_audit_card_a",
            "source_ref": f"lead_profiles:{row['lead_id']}",
            "content_text": post_text,
            "media_url": media_url,
            "status": "draft",
            "scheduled_for": today,
        }
        inserted = rest_insert("social_content_queue", [queue_row])
        print(f"    -> social_content_queue row {inserted[0]['id']} / media {media_url}", file=sys.stderr)
        generated.append({"lead_id": row["lead_id"], "queue_id": inserted[0]["id"], "media_url": media_url,
                           "name": name, "county": county, "auctions_won": auctions_won,
                           "total_deployed": total_deployed, "upcoming_auctions": upcoming})

    return generated


def run_variant_b(dry_run: bool):
    rows = mgmt_sql(VARIANT_B_COUNTY_SQL)
    if not rows:
        print("DATA CEILING: no county outside the 7-day rotation window has any "
              "completed auctions. Nothing to generate.", file=sys.stderr)
        return None

    row = rows[0]
    county = row["county"]
    completed = row["completed_auctions"]
    upcoming = row["upcoming_auctions"]
    today = date.today().isoformat()

    stats = [
        ("Auctions Tracked", str(completed)),
        ("Upcoming (30d)", str(upcoming)),
    ]
    html = render_card_html(
        kicker=f"{county_label(county)} COUNTY, FL",
        headline=f"{county_label(county).upper()} COUNTY AUCTION ACTIVITY",
        stats=stats,
        cta_county=county_label(county),
    )
    post_text = (
        f"{county_label(county)} County, FL -- auction activity\n\n"
        f"Completed auctions tracked: {completed}\n"
        f"Upcoming auctions (next 30 days): {upcoming}\n\n"
        f"See {county_label(county)}'s auctions free -> biddeed.ai/{county_slug(county)}\n\n"
        "Informational only -- not legal, financial, or investment advice."
    )
    print(f"  [B] {county} / completed={completed} upcoming={upcoming}", file=sys.stderr)

    if dry_run:
        return {"county": county, "completed_auctions": completed, "upcoming_auctions": upcoming, "post_text": post_text}

    png_path = f"/tmp/lead_card_B_{county}.png"
    render_card_png(html, png_path)
    storage_key = f"lead-cards/{today}/B_{county}.png"
    media_url = upload_card(png_path, storage_key)
    os.remove(png_path)

    h = content_hash("lead_audit_card_b", county, today)
    queue_row = {
        "content_hash": h,
        "target_platform": "linkedin_personal",
        "source_type": "lead_audit_card_b",
        "source_ref": f"county:{county}",
        "content_text": post_text,
        "media_url": media_url,
        "status": "draft",
        "scheduled_for": today,
    }
    inserted = rest_insert("social_content_queue", [queue_row])
    print(f"    -> social_content_queue row {inserted[0]['id']} / media {media_url}", file=sys.stderr)

    history_row = {"county": county, "property_id": f"lead_audit_card_b:{today}", "posted_date": today}
    rest_insert("social_banner_history", [history_row])

    return {"county": county, "queue_id": inserted[0]["id"], "media_url": media_url,
            "completed_auctions": completed, "upcoming_auctions": upcoming}


def main():
    variant = None
    dry_run = "--dry-run" in sys.argv
    limit = 10
    for i, arg in enumerate(sys.argv):
        if arg == "--variant" and i + 1 < len(sys.argv):
            variant = sys.argv[i + 1]
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    if variant == "a":
        result = run_variant_a(limit, dry_run)
    elif variant == "b":
        result = run_variant_b(dry_run)
    else:
        print("Usage: generate_lead_audit_card.py --variant a|b [--limit N] [--dry-run]", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, default=str, indent=2))


if __name__ == "__main__":
    main()
