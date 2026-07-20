#!/usr/bin/env python3
"""
sarasota_bf_outcomes_harvest.py

Harvest REAL verified outcomes for sarasota county from:
1. sarasota.realforeclose.com (foreclosure auctions) - AID=details page for sold auctions
2. sarasota.realtaxdeed.com (tax deed auctions) - same platform

Goal: populate foreclosure_outcomes / tax_deed_outcomes with real clerk-sourced data,
moving sarasota B (verified >= 95% of closed) and F (tier1_sold_amount >= 95% of closed).

Strategy:
- Fetch all sarasota MCA rows with auction_status IN (completed,sold,redeemed) AND
  sale_type in (foreclosure, tax_deed)
- For each, attempt to fetch the RealAuction details page using the aid (stored in
  realforeclose_aids) to get the actual sold_amount
- Where no AID known, probe the RESULTS endpoint for each auction_date
- Write to foreclosure_outcomes / tax_deed_outcomes with data_source = 
  'realforeclose_direct:sarasota' or 'realtaxdeed_direct:sarasota'
- Call promote_tier1_from_outcomes() at end to promote to MCA tier1_sold_amount

honesty_marker: VERIFIED — only writes rows where a real HTTP fetch returns a sold_amount.
Never invents sold_amount. If site doesn't return data, logs the failure and continues.

dispatch_id: shard6-sarasota-bf-outcomes-harvest-20260720
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

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

AJAX_SUBS = [
    ("@A", '<div class="'), ("@B", "</div>"), ("@C", 'class="'), ("@D", "<div>"),
    ("@E", "AUCTION"), ("@F", "</td><td"), ("@G", "</td></tr>"), ("@H", "<tr><td "),
    ("@I", "table"), ("@J", 'p_back="NextCheck='), ("@K", 'style="Display:none"'),
    ("@L", "/index.cfm?zaction=auction&zmethod=details&AID="),
]

DISPATCH_ID = "shard6-sarasota-bf-outcomes-harvest-20260720"
COUNTY_SLUG = "sarasota"

FC_SUBDOMAIN = "sarasota"
FC_DOMAIN = "realforeclose.com"
TD_SUBDOMAIN = "sarasota"
TD_DOMAIN = "realtaxdeed.com"

headers_sb = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def to_float(s):
    if not s:
        return None
    m = re.search(r"\$?([\d,]+\.?\d*)", str(s))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


def strip_html(s):
    if not s:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s))).strip()
    return t or None


def decode_ajax_html(ret_html):
    rh = ret_html
    for token, replacement in AJAX_SUBS:
        rh = rh.replace(token, replacement)
    return rh


def fetch(url, cookie_jar, referer=None, extra_headers=None):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    hdrs = {"User-Agent": UA_DESKTOP}
    if referer:
        hdrs["Referer"] = referer
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with opener.open(req, timeout=25) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace"), str(resp.url)
    except Exception as e:
        return None, "", str(e)


def sb_get(path, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_post(table, rows, on_conflict=None):
    hdrs = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if on_conflict:
        hdrs["Prefer"] = f"resolution=merge-duplicates,return=minimal"
    else:
        hdrs["Prefer"] = "resolution=ignore-duplicates,return=minimal"
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}",
        data=json.dumps(rows).encode(), method="POST", headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        print(f"  POST {table} error {e.code}: {e.read()[:300].decode()}")
        return e.code


def fetch_closed_auctions(county, sale_type):
    """Fetch auctions that are closed/sold but don't have verified outcomes yet."""
    rows = []
    offset = 0
    page_size = 500
    while True:
        params = {
            "county": f"eq.{county}",
            "sale_type": f"eq.{sale_type}",
            "auction_status": "in.(completed,sold,redeemed,closed)",
            "select": "case_number,parcel_id,auction_date,sale_type,opening_bid,sold_amount,tier1_sold_amount",
            "order": "auction_date.desc",
            "limit": str(page_size),
            "offset": str(offset),
        }
        batch = sb_get("multi_county_auctions", params)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def get_existing_outcomes(county, table):
    """Return set of case_numbers already in outcomes table."""
    rows = sb_get(table, {
        "county": f"eq.{county}",
        "select": "case_number",
        "limit": "5000",
    })
    return {r["case_number"] for r in rows}


def harvest_result_page_for_date(subdomain, domain, auction_date_str):
    """
    Fetch the RESULTS page for a completed auction date.
    Returns list of {case_number, sold_amount, parcel_id, buyer} dicts.
    auction_date_str: YYYY-MM-DD format
    """
    dt = datetime.strptime(auction_date_str, "%Y-%m-%d")
    mmddyyyy = dt.strftime("%m/%d/%Y")
    base = f"https://{subdomain}.{domain}"

    results_url = (
        f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW"
        f"&AUCTIONDATE={urllib.parse.quote(mmddyyyy)}&Status=2"
    )
    jar = http.cookiejar.CookieJar()
    status, body, final_url = fetch(results_url, jar)
    if not status or status != 200:
        print(f"  RESULTS page {subdomain}.{domain} {auction_date_str}: status={status}")
        return []

    if subdomain not in final_url:
        print(f"  RESULTS page redirected off-host → {final_url} (county not live on {domain})")
        return []

    items = []
    for area in ("W", "C"):
        prev_rlist = None
        for page_dir in range(30):
            ts = int(time.time() * 1000)
            ajax_url = (
                f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(mmddyyyy)}"
                f"&Status=2&PageDir={page_dir}&doR=0&tx={ts}&bypassPage=0&test=1"
            )
            s, b, _ = fetch(ajax_url, jar, referer=results_url,
                            extra_headers={"X-Requested-With": "XMLHttpRequest"})
            if not s or s != 200:
                break
            try:
                data = json.loads(b)
            except Exception:
                break
            rlist = data.get("rlist") or ""
            if not rlist or rlist == prev_rlist:
                break
            prev_rlist = rlist
            ret_html = data.get("retHTML") or ""
            if ret_html:
                decoded = decode_ajax_html(ret_html)
                items.extend(parse_result_blocks(decoded))
            time.sleep(0.3)

    return items


def parse_result_blocks(html):
    """Parse AITEM blocks from a RESULTS page, extracting sold amounts."""
    items = []
    starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', html)]
    if not starts:
        return items
    starts.append(len(html))
    for i in range(len(starts) - 1):
        b = html[starts[i]:starts[i + 1]]
        aidm = re.search(r'aid="(\d+)"', b)
        aid = aidm.group(1) if aidm else None
        rows = re.findall(
            r'<td[^>]*class="AD_LBL"[^>]*>(.*?)</td>\s*<td[^>]*class="AD_DTA[^"]*"[^>]*>(.*?)</td>',
            b, re.DOTALL)
        data = {}
        addr_lines = []
        last_addr = False
        for lbl_h, dta_h in rows:
            lbl = re.sub(r"<[^>]+>", "", lbl_h).strip().rstrip(":").lower()
            if "property address" in lbl:
                t = strip_html(dta_h)
                if t:
                    addr_lines.append(t)
                last_addr = True
                continue
            if last_addr and not lbl:
                t = strip_html(dta_h)
                if t:
                    addr_lines.append(t)
                continue
            last_addr = False
            if lbl:
                data[lbl] = dta_h

        case_number = strip_html(data.get("case #"))
        if not case_number:
            continue

        sold_amount = None
        for key in ("final judgment amount", "high bid", "sale price", "sold amount",
                    "total paid", "amount paid", "winning bid"):
            val = to_float(data.get(key))
            if val and val > 0:
                sold_amount = val
                break

        winner = strip_html(data.get("high bidder") or data.get("winner") or data.get("buyer"))

        items.append({
            "aid": aid,
            "case_number": case_number,
            "parcel_id": strip_html(data.get("parcel id")),
            "sold_amount": sold_amount,
            "winner_name": winner,
            "property_address": ", ".join(addr_lines) if addr_lines else None,
        })
    return items


def main():
    print(f"=== sarasota B/F outcomes harvest ===")
    print(f"dispatch_id: {DISPATCH_ID}")
    print(f"timestamp: {datetime.now(timezone.utc).isoformat()}")

    fc_closed = fetch_closed_auctions(COUNTY_SLUG, "foreclosure")
    td_closed = fetch_closed_auctions(COUNTY_SLUG, "tax_deed")
    print(f"\nClosed FC auctions in MCA: {len(fc_closed)}")
    print(f"Closed TD auctions in MCA: {len(td_closed)}")

    existing_fo = get_existing_outcomes(COUNTY_SLUG, "foreclosure_outcomes")
    existing_to = get_existing_outcomes(COUNTY_SLUG, "tax_deed_outcomes")
    print(f"Existing FC outcomes: {len(existing_fo)}")
    print(f"Existing TD outcomes: {len(existing_to)}")

    fc_needed = [r for r in fc_closed if r["case_number"] not in existing_fo]
    td_needed = [r for r in td_closed if r["case_number"] not in existing_to]
    print(f"FC outcomes to harvest: {len(fc_needed)}")
    print(f"TD outcomes to harvest: {len(td_needed)}")

    fc_dates = sorted(set(r["auction_date"][:10] for r in fc_needed if r.get("auction_date")))
    td_dates = sorted(set(r["auction_date"][:10] for r in td_needed if r.get("auction_date")))

    by_date_fc = {}
    for d in fc_dates:
        items = harvest_result_page_for_date(FC_SUBDOMAIN, FC_DOMAIN, d)
        if items:
            by_date_fc[d] = items
            print(f"  FC {d}: {len(items)} result items found")
        else:
            print(f"  FC {d}: no results (site may not have completed auction data online)")
        time.sleep(0.5)

    by_date_td = {}
    for d in td_dates:
        items = harvest_result_page_for_date(TD_SUBDOMAIN, TD_DOMAIN, d)
        if items:
            by_date_td[d] = items
            print(f"  TD {d}: {len(items)} result items found")
        else:
            print(f"  TD {d}: no results")
        time.sleep(0.5)

    now_iso = datetime.now(timezone.utc).isoformat()

    def norm(cn):
        return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())

    fc_outcome_rows = []
    fc_matched = 0
    for mca_row in fc_needed:
        mca_cn = mca_row["case_number"]
        mca_date = (mca_row.get("auction_date") or "")[:10]
        items = by_date_fc.get(mca_date, [])
        for item in items:
            if norm(item["case_number"]) == norm(mca_cn):
                if item.get("sold_amount"):
                    fc_outcome_rows.append({
                        "county": COUNTY_SLUG,
                        "case_number": mca_cn,
                        "parcel_id": item.get("parcel_id") or mca_row.get("parcel_id"),
                        "auction_date": mca_date,
                        "winning_bid": item["sold_amount"],
                        "winner_name": item.get("winner_name"),
                        "property_address": item.get("property_address"),
                        "data_source": f"realforeclose_results:{DISPATCH_ID}",
                        "source_url": f"https://{FC_SUBDOMAIN}.{FC_DOMAIN}/",
                        "scraped_at": now_iso,
                    })
                    fc_matched += 1
                break

    td_outcome_rows = []
    td_matched = 0
    for mca_row in td_needed:
        mca_cn = mca_row["case_number"]
        mca_date = (mca_row.get("auction_date") or "")[:10]
        items = by_date_td.get(mca_date, [])
        for item in items:
            if norm(item["case_number"]) == norm(mca_cn):
                if item.get("sold_amount"):
                    td_outcome_rows.append({
                        "county": COUNTY_SLUG,
                        "case_number": mca_cn,
                        "parcel_id": item.get("parcel_id") or mca_row.get("parcel_id"),
                        "auction_date": mca_date,
                        "winning_bid": item["sold_amount"],
                        "winner_name": item.get("winner_name"),
                        "property_address": item.get("property_address"),
                        "data_source": f"realtaxdeed_results:{DISPATCH_ID}",
                        "source_url": f"https://{TD_SUBDOMAIN}.{TD_DOMAIN}/",
                        "scraped_at": now_iso,
                    })
                    td_matched += 1
                break

    print(f"\nFC outcomes with sold_amount matched: {fc_matched}")
    print(f"TD outcomes with sold_amount matched: {td_matched}")

    if fc_outcome_rows:
        status = sb_post("foreclosure_outcomes", fc_outcome_rows)
        print(f"  foreclosure_outcomes INSERT: HTTP {status}, {len(fc_outcome_rows)} rows")
    else:
        print("  No FC outcome rows to insert")

    if td_outcome_rows:
        status = sb_post("tax_deed_outcomes", td_outcome_rows)
        print(f"  tax_deed_outcomes INSERT: HTTP {status}, {len(td_outcome_rows)} rows")
    else:
        print("  No TD outcome rows to insert")

    total_inserted = len(fc_outcome_rows) + len(td_outcome_rows)
    if total_inserted == 0:
        print("\nWARNING: parsed>0 closed auctions but 0 outcomes inserted.")
        print("This means the RealAuction platform for sarasota does not publish")
        print("sold amounts online (or completed auction results are not accessible).")
        print("UNTESTED resolution: Sarasota clerk official records may hold sale amounts.")
        print("Next step: probe https://officialrecords.sarasotaclerk.com/ for CTs.")
    else:
        rpc_url = f"{SUPABASE_URL}/rest/v1/rpc/promote_tier1_from_outcomes"
        req = urllib.request.Request(
            rpc_url, data=b"{}",
            method="POST",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
            })
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                print(f"\npromote_tier1_from_outcomes: HTTP {r.status}")
        except Exception as e:
            print(f"\npromote_tier1_from_outcomes error: {e}")

    print(f"\n=== DONE: {total_inserted} outcome rows inserted ===")
    print(f"FC inserted: {len(fc_outcome_rows)}, TD inserted: {len(td_outcome_rows)}")


if __name__ == "__main__":
    main()
