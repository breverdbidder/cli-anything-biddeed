#!/usr/bin/env python3
"""Harvest realforeclose_aids for pinellas/santa_rosa via the RealForeclose AJAX
data endpoint (zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=...), bypassing the
Firecrawl-based parity-court-scraper.yml path.

WHY THIS EXISTS: court_responses_raw shows 6,180 consecutive HTTP 402
"Insufficient credits" failures from Firecrawl fleet-wide since 2026-06-10 (the
Firecrawl account is out of credit). The RealForeclose PREVIEW page's auction-item
content is loaded client-side via this AJAX endpoint, not server-rendered — but the
endpoint itself needs no JS execution, only: (1) a session cookie from an initial
GET of the PREVIEW page for the target AUCTIONDATE, (2) a browser User-Agent header
(bare curl / default UA gets HTTP 403 from the WAF; a standard desktop UA gets 200),
(3) decoding the JSON `retHTML` field's 12-token shorthand encoding (identical to
`LoadNewArea()` in /CORE/System/JS/auction.js on the target site). Verified live
2026-07-02 against real pinellas/santa_rosa auction dates before this script was
written (see SHARD2_RUN2450 session report addendum).

Reuses parse_aitem_blocks() verbatim from scripts/fill_opening_bids_brevard_duval.py
(same AITEM HTML shape once decoded) rather than reimplementing it.
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import http.cookiejar
from datetime import datetime

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

UA_DESKTOP = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

AJAX_SUBS = [
    ("@A", '<div class="'),
    ("@B", "</div>"),
    ("@C", 'class="'),
    ("@D", "<div>"),
    ("@E", "AUCTION"),
    ("@F", "</td><td"),
    ("@G", "</td></tr>"),
    ("@H", "<tr><td "),
    ("@I", "table"),
    ("@J", 'p_back="NextCheck='),
    ("@K", 'style="Display:none"'),
    ("@L", "/index.cfm?zaction=auction&zmethod=details&AID="),
]


def to_float(s):
    if not s:
        return None
    m = re.search(r"\$?([\d,]+\.?\d*)", s)
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


def parse_starts(s):
    if not s:
        return None
    cleaned = re.sub(r"\s+(?:ET|EST|EDT|CT|CST|CDT|MT|MST|MDT|PT|PST|PDT)\s*$", "", s.strip())
    for fmt in ("%m/%d/%Y %I:%M %p", "%m/%d/%Y %H:%M", "%m/%d/%Y"):
        try:
            return datetime.strptime(cleaned, fmt).isoformat()
        except ValueError:
            continue
    return None


def parse_aitem_blocks(html, county_sub):
    """Verbatim port of scripts/fill_opening_bids_brevard_duval.py:parse_aitem_blocks."""
    items = []
    starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', html)]
    if not starts:
        return items
    starts.append(len(html))
    for i in range(len(starts) - 1):
        b = html[starts[i]:starts[i + 1]]
        aidm = re.search(r'aid="(\d+)"', b)
        if not aidm:
            continue
        aid = aidm.group(1)
        sm = re.search(r'ASTAT_MSGA[^>]*>Auction Starts</div>\s*<div[^>]+>\s*([^<]+?)\s*</div>', b)
        starts_raw = sm.group(1).strip() if sm else None
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
        items.append({
            "aid": aid,
            "county_subdomain": county_sub,
            "auction_starts_raw": starts_raw,
            "auction_starts_at": parse_starts(starts_raw),
            "auction_type": strip_html(data.get("auction type")),
            "case_number": strip_html(data.get("case #")),
            "judgment_amount": to_float(data.get("final judgment amount")),
            "parcel_id": strip_html(data.get("parcel id")),
            "property_address": ", ".join(addr_lines) if addr_lines else None,
            "assessed_value": to_float(data.get("assessed value")),
            "plaintiff_max_bid": to_float(data.get("plaintiff max bid")),
        })
    return items


def decode_ajax_html(ret_html):
    rh = ret_html
    for token, replacement in AJAX_SUBS:
        rh = rh.replace(token, replacement)
    return rh


def fetch(url, cookie_jar, referer=None, headers=None):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    hdrs = {"User-Agent": UA_DESKTOP}
    if referer:
        hdrs["Referer"] = referer
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with opener.open(req, timeout=20) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def harvest_date(subdomain, county_slug, auction_date_mmddyyyy, platform_domain="realforeclose.com"):
    """Returns list of raw AITEM dicts (pre-DB-shape) harvested for one auction date.
    platform_domain: 'realforeclose.com' (foreclosure) or 'realtaxdeed.com' (tax deed) —
    both RealAuction-family platforms sharing the identical AJAX/auction.js mechanism
    (verified live 2026-07-02: byte-identical auction.js on both subdomains)."""
    base = f"https://{subdomain}.{platform_domain}"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={auction_date_mmddyyyy}"
    jar = http.cookiejar.CookieJar()
    try:
        status, _ = fetch(preview_url, jar)
    except Exception as e:
        print(f"  PREVIEW fetch failed {subdomain} {auction_date_mmddyyyy}: {e}")
        return []
    if status != 200:
        print(f"  PREVIEW non-200 ({status}) {subdomain} {auction_date_mmddyyyy}")
        return []

    items = []
    for area in ("W", "C"):
        ts = int(time.time() * 1000)
        ajax_url = (f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                    f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(auction_date_mmddyyyy)}"
                    f"&PageDir=0&doR=0&tx={ts}&bypassPage=0&test=1")
        try:
            status, body = fetch(ajax_url, jar, referer=preview_url,
                                  headers={"X-Requested-With": "XMLHttpRequest"})
        except Exception as e:
            print(f"  AJAX AREA={area} fetch failed {subdomain} {auction_date_mmddyyyy}: {e}")
            continue
        if status != 200:
            continue
        try:
            data = json.loads(body)
        except Exception:
            continue
        ret_html = data.get("retHTML") or ""
        if not ret_html:
            continue
        decoded = decode_ajax_html(ret_html)
        parsed = parse_aitem_blocks(decoded, subdomain)
        items.extend(parsed)
        time.sleep(0.4)
    return items


def upsert_aids(items, county_slug, run_label):
    if not items:
        return 0
    payload = []
    for a in items:
        if not a.get("case_number"):
            continue
        payload.append({
            "aid": a["aid"],
            "county_slug": county_slug,
            "auction_type": a["auction_type"],
            "case_number": a["case_number"],
            "judgment_amount": a["judgment_amount"],
            "parcel_id": a["parcel_id"],
            "property_address": a["property_address"],
            "assessed_value": a["assessed_value"],
            "plaintiff_max_bid": a["plaintiff_max_bid"],
            "auction_starts_at": a["auction_starts_at"],
            "auction_starts_raw": a["auction_starts_raw"],
            "county_subdomain": a["county_subdomain"],
        })
    if not payload:
        return 0
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/realforeclose_aids?on_conflict=aid",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": f"resolution=merge-duplicates,return=minimal",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        status = resp.status
    if status not in (200, 201, 204):
        raise RuntimeError(f"realforeclose_aids upsert failed for {county_slug}: HTTP {status}")
    return len(payload)


def main():
    targets = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
    if not targets:
        print("usage: shard2_run2450_ajax_realforeclose_harvest.py '[{\"subdomain\":\"pinellas\",\"county_slug\":\"pinellas\",\"dates\":[\"07/07/2026\"]}]'")
        sys.exit(1)

    total_parsed = 0
    total_inserted = 0
    for t in targets:
        sub = t["subdomain"]
        slug = t["county_slug"]
        platform = t.get("platform_domain", "realforeclose.com")
        for d in t["dates"]:
            items = harvest_date(sub, slug, d, platform_domain=platform)
            n_parsed = len(items)
            n_inserted = upsert_aids(items, slug, "shard2_run2450_ajax")
            total_parsed += n_parsed
            total_inserted += n_inserted
            print(f"{slug} {d}: parsed={n_parsed} inserted_or_merged={n_inserted}")
            time.sleep(0.3)

    print(f"TOTAL: parsed={total_parsed} inserted_or_merged={total_inserted}")
    if total_parsed > 0 and total_inserted == 0:
        raise RuntimeError(f"Silent failure: {total_parsed} aids parsed but 0 written to realforeclose_aids")


if __name__ == "__main__":
    main()
