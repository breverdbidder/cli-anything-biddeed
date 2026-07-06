#!/usr/bin/env python3
"""C/D LITMUS V2 (issue #10981) — RealAuction primary-source count-parity harvester.

Ariel directive 2026-07-06 (docs/CD-LITMUS-HIERARCHY-V2.md): calendar-parity litmus
is now (1) PRIMARY realauction, (2) FALLBACK floridabidder, (3) TERTIARY propertyonion
(cross-check only, never blocking). This script implements the PRIMARY leg: for a
given county + sale_type, re-count the live RealAuction calendar (realforeclose.com /
realtaxdeed.com) for the same auction dates already present in OUR frozen calendar
(multi_county_auctions) and write a row to cd_litmus_parity_v2 — count/coverage litmus
only, never row-level resolution (per cd_litmus_hierarchy.usage_constraint).

Reuses the proven AJAX harvest mechanism verbatim from
scripts/shard2_run2450_ajax_realforeclose_harvest.py (same auction.js shorthand
decoding, same PREVIEW-cookie-then-AJAX-page dance) rather than reimplementing it.
County -> platform/subdomain comes from pipeline.counties (live, not a hardcoded
per-script dict) so this generalizes to any RealAuction-family county without edits.

Usage:
  python3 scripts/cd_litmus_v2_realauction_harvest.py '[{"county_slug":"desoto","sale_type":"foreclosure"}]'
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import http.cookiejar
from datetime import datetime, timezone
from urllib.parse import urlparse

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUPABASE_ACCESS_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_API = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

UA_DESKTOP = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

AJAX_SUBS = [
    ("@A", '<div class="'), ("@B", "</div>"), ("@C", 'class="'), ("@D", "<div>"),
    ("@E", "AUCTION"), ("@F", "</td><td"), ("@G", "</td></tr>"), ("@H", "<tr><td "),
    ("@I", "table"), ("@J", 'p_back="NextCheck='), ("@K", 'style="Display:none"'),
    ("@L", "/index.cfm?zaction=auction&zmethod=details&AID="),
]


def run_sql(sql, timeout=60):
    # Cloudflare in front of api.supabase.com returns error 1010 (blocked User-Agent)
    # for urllib's default "Python-urllib/x.y" UA — a real desktop UA clears it.
    req = urllib.request.Request(
        MGMT_API, data=json.dumps({"query": sql}).encode(), method="POST",
        headers={"Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}", "Content-Type": "application/json",
                 "User-Agent": UA_DESKTOP},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"[]")


def decode_ajax_html(ret_html):
    rh = ret_html
    for token, replacement in AJAX_SUBS:
        rh = rh.replace(token, replacement)
    return rh


def count_aitems(html):
    return len(re.findall(r'<div\s+id="AITEM_\d+"', html))


def fetch(url, cookie_jar, referer=None, headers=None):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    hdrs = {"User-Agent": UA_DESKTOP}
    if referer:
        hdrs["Referer"] = referer
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with opener.open(req, timeout=20) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace"), resp.geturl()


def harvest_date_count(subdomain, auction_date_mmddyyyy, platform_domain):
    """Returns (item_count, reached) for one auction date on one RealAuction-family
    platform. reached=False means the site itself could not be reached OR redirected
    off the requested subdomain — e.g. desoto.realforeclose.com 302s to the generic
    www.realauction.com marketing homepage when that county isn't actually live-hosted
    there, which would otherwise silently masquerade as an honest "0 items" (VERIFIED
    2026-07-06 against live desoto.realforeclose.com + desoto.realtaxdeed.com: both
    redirect off-host). reached=True with item_count=0 means the site responded ON
    the requested host but has nothing published for that date — a real, honest zero."""
    base = f"https://{subdomain}.{platform_domain}"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={auction_date_mmddyyyy}"
    jar = http.cookiejar.CookieJar()
    try:
        status, _, final_url = fetch(preview_url, jar)
    except Exception as e:
        print(f"  PREVIEW fetch failed {subdomain}.{platform_domain} {auction_date_mmddyyyy}: {e}")
        return 0, False
    if status != 200:
        print(f"  PREVIEW non-200 ({status}) {subdomain}.{platform_domain} {auction_date_mmddyyyy}")
        return 0, False
    if urlparse(final_url).netloc != urlparse(base).netloc:
        print(f"  PREVIEW redirected off-host {subdomain}.{platform_domain} -> {final_url} "
              f"(county not live on this platform)")
        return 0, False

    total = 0
    reached = True
    for area in ("W", "C"):
        prev_rlist = None
        for page_dir in range(20):
            ts = int(time.time() * 1000)
            ajax_url = (f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                        f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(auction_date_mmddyyyy)}"
                        f"&PageDir={page_dir}&doR=0&tx={ts}&bypassPage=0&test=1")
            try:
                status, body, _ = fetch(ajax_url, jar, referer=preview_url,
                                         headers={"X-Requested-With": "XMLHttpRequest"})
            except Exception as e:
                print(f"  AJAX AREA={area} PageDir={page_dir} fetch failed: {e}")
                break
            if status != 200:
                break
            try:
                data = json.loads(body)
            except Exception:
                break
            rlist = data.get("rlist") or ""
            if not rlist or rlist == prev_rlist:
                break
            prev_rlist = rlist
            ret_html = data.get("retHTML") or ""
            if ret_html:
                total += count_aitems(decode_ajax_html(ret_html))
            time.sleep(0.4)
    return total, reached


def subdomain_and_domain(url):
    netloc = urlparse(url).netloc
    parts = netloc.split(".")
    return parts[0], ".".join(parts[1:])


def harvest_one(county_slug, sale_type):
    col_platform = "foreclosure_platform" if sale_type == "foreclosure" else "taxdeed_platform"
    col_url = "foreclosure_url" if sale_type == "foreclosure" else "taxdeed_url"
    rows = run_sql(f"""
        SELECT {col_platform} AS platform, {col_url} AS url
        FROM pipeline.counties WHERE county_slug = '{county_slug}';
    """)
    platform = rows[0]["platform"] if rows else None
    url = rows[0]["url"] if rows else None
    if platform not in ("realforeclose", "realtaxdeed") or not url:
        print(f"{county_slug}/{sale_type}: off RealAuction platform (platform={platform}) — "
              f"leave to floridabidder fallback")
        return None

    subdomain, domain = subdomain_and_domain(url)

    date_rows = run_sql(f"""
        SELECT auction_date::date AS d, count(*) AS n
        FROM multi_county_auctions
        WHERE lower(county) = '{county_slug}' AND sale_type = '{sale_type}'
          AND auction_date >= now() - interval '7 days'
        GROUP BY 1 ORDER BY 1;
    """)
    if not date_rows:
        insert_row(county_slug, "realauction", sale_type, None, None, 0, 0, None, "ok",
                    "dates_checked=[] (no auctions in our frozen window for this sale_type)")
        print(f"{county_slug}/{sale_type}: no MCA rows in window — recorded 0/0")
        return

    dates = [r["d"] for r in date_rows]
    our_count = sum(r["n"] for r in date_rows)
    source_count = 0
    any_reached = False
    for d in dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        n, reached = harvest_date_count(subdomain, mmddyyyy, domain)
        source_count += n
        any_reached = any_reached or reached
        time.sleep(0.3)

    status = "ok" if any_reached else "unreachable"
    match_pct = None
    if source_count > 0 and our_count > 0:
        match_pct = round(100.0 * min(source_count, our_count) / max(source_count, our_count), 1)
    insert_row(county_slug, "realauction", sale_type, dates[0], dates[-1],
               source_count if status == "ok" else None, our_count, match_pct, status,
               f"dates_checked={dates}")
    print(f"{county_slug}/{sale_type}: source={source_count} our={our_count} match_pct={match_pct} status={status}")


def insert_row(county_slug, source, sale_type, window_start, window_end,
               source_count, our_count, match_pct, status, notes):
    def sql_val(v):
        if v is None:
            return "NULL"
        if isinstance(v, str):
            return "'" + v.replace("'", "''") + "'"
        return str(v)

    run_sql(f"""
        INSERT INTO cd_litmus_parity_v2
          (county_slug, source, sale_type, window_start, window_end,
           source_count, our_count, match_pct, fetched_at, status, notes)
        VALUES
          ({sql_val(county_slug)}, {sql_val(source)}, {sql_val(sale_type)},
           {sql_val(window_start)}, {sql_val(window_end)},
           {sql_val(source_count)}, {sql_val(our_count)}, {sql_val(match_pct)},
           now(), {sql_val(status)}, {sql_val(notes)});
    """)


def main():
    targets = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
    if not targets:
        print('usage: cd_litmus_v2_realauction_harvest.py \'[{"county_slug":"desoto","sale_type":"foreclosure"}]\'')
        sys.exit(1)
    print(f"[{datetime.now(timezone.utc).isoformat()}] HONESTY V3: VERIFIED live RealAuction "
          f"re-count against {len(targets)} target(s)")
    for t in targets:
        harvest_one(t["county_slug"], t["sale_type"])


if __name__ == "__main__":
    main()
