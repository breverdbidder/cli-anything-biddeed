#!/usr/bin/env python3
"""SHARD-10, county=alachua, criterion E (parcel linkage) -- docid harvest.

For each of 13 target case numbers, find the isol.alachuaclerk.org
SearchDetail.aspx?docid=NNNNNNN href embedded in the RealForeclose (or
RealTaxDeed) AJAX calendar payload's "Case #" column for that case's
auction date.

Reuses parse_aitem_blocks() and AJAX_SUBS verbatim from
scripts/shard2_run2450_ajax_realforeclose_harvest.py (per task instructions),
and additionally regexes the docid href out of the raw decoded HTML block
per AITEM (discarded by the existing parse_aitem_blocks, which only keeps
the case_number anchor TEXT).

Live network fetch against alachua.realforeclose.com / alachua.realtaxdeed.com.
No DB writes -- this is a read-only reconnaissance script. Prints a JSON
object matching the requested output contract.
"""
import json
import re
import sys
import time
import urllib.request
import urllib.parse
import http.cookiejar
from datetime import datetime

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


def strip_html(s):
    if not s:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s))).strip()
    return t or None


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
    """Verbatim port of scripts/shard2_run2450_ajax_realforeclose_harvest.py:parse_aitem_blocks
    (itself a verbatim port of scripts/fill_opening_bids_brevard_duval.py)."""
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
            "case_number_raw_html": data.get("case #"),
            "raw_block": b,
            "judgment_amount": to_float(data.get("final judgment amount")),
            "parcel_id": strip_html(data.get("parcel id")),
            "property_address": ", ".join(addr_lines) if addr_lines else None,
            "assessed_value": to_float(data.get("assessed value")),
            "plaintiff_max_bid": to_float(data.get("plaintiff max bid")),
        })
    return items


def extract_docid(item):
    """Regex the isol.alachuaclerk.org SearchDetail.aspx?docid=NNNNNNN href out of
    the raw decoded HTML for this AITEM block, scoped to the Case # column."""
    # Prefer scoping to the case# raw html cell if it contains the anchor.
    haystack = item.get("case_number_raw_html") or ""
    m = re.search(r'docid=(\d+)', haystack)
    if m:
        return m.group(1), haystack
    # Fall back to searching the whole AITEM block (case# anchor might be split
    # across cells/attrs differently than expected).
    block = item.get("raw_block") or ""
    m = re.search(r'docid=(\d+)', block)
    if m:
        # snippet around the match for audit
        s, e = max(0, m.start() - 80), min(len(block), m.end() + 40)
        return m.group(1), block[s:e]
    # Explicit empty-docid marker per shard10_run3645 docstring: docid=&ms=0
    if re.search(r'docid=&', haystack) or re.search(r'docid=&', block):
        return None, haystack or "(docid=&ms=0 empty marker found in block)"
    return None, haystack or None


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


def harvest_date(subdomain, auction_date_mmddyyyy, platform_domain):
    base = f"https://{subdomain}.{platform_domain}"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={auction_date_mmddyyyy}"
    jar = http.cookiejar.CookieJar()
    try:
        status, _ = fetch(preview_url, jar)
    except Exception as e:
        return [], f"PREVIEW fetch failed: {e}"
    if status != 200:
        return [], f"PREVIEW non-200: {status}"

    items = []
    for area in ("W", "C"):
        prev_rlist = None
        for page_dir in range(20):
            ts = int(time.time() * 1000)
            ajax_url = (f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                        f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(auction_date_mmddyyyy)}"
                        f"&PageDir={page_dir}&doR=0&tx={ts}&bypassPage=0&test=1")
            try:
                status, body = fetch(ajax_url, jar, referer=preview_url,
                                      headers={"X-Requested-With": "XMLHttpRequest"})
            except Exception as e:
                return items, f"AJAX AREA={area} PageDir={page_dir} fetch failed: {e}"
            if status != 200:
                return items, f"AJAX non-200: {status} (AREA={area} PageDir={page_dir})"
            try:
                data = json.loads(body)
            except Exception:
                return items, f"AJAX non-JSON body (AREA={area} PageDir={page_dir}): {body[:200]!r}"
            rlist = data.get("rlist") or ""
            if not rlist or rlist == prev_rlist:
                break
            prev_rlist = rlist
            ret_html = data.get("retHTML") or ""
            if ret_html:
                decoded = decode_ajax_html(ret_html)
                items.extend(parse_aitem_blocks(decoded, subdomain))
            time.sleep(0.4)
    return items, None


def norm_case(cn):
    return re.sub(r"\s+", " ", cn.strip().upper())


def main():
    cases = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
    if not cases:
        print("usage: script.py '[{\"case_number\":...,\"auction_date\":\"YYYY-MM-DD\"}]'", file=sys.stderr)
        sys.exit(1)

    result = {}
    remaining = {norm_case(c["case_number"]): c for c in cases}
    by_date = {}
    for c in cases:
        by_date.setdefault(c["auction_date"], []).append(c)

    errors = {}
    for platform_domain, url_field in (("realforeclose.com", "foreclosure"),):
        for auction_date, group in sorted(by_date.items()):
            y, m, d = auction_date.split("-")
            mmddyyyy = f"{m}/{d}/{y}"
            items, err = harvest_date("alachua", mmddyyyy, platform_domain)
            if err:
                errors[f"{platform_domain}:{auction_date}"] = err
                print(f"ERROR alachua {platform_domain} {mmddyyyy}: {err}", file=sys.stderr)
            print(f"alachua {platform_domain} {mmddyyyy}: {len(items)} AITEM blocks parsed", file=sys.stderr)
            for it in items:
                cn = it.get("case_number")
                if not cn:
                    continue
                ncn = norm_case(cn)
                if ncn in remaining:
                    docid, snippet = extract_docid(it)
                    result[remaining[ncn]["case_number"]] = {
                        "found_on_calendar": True,
                        "docid": docid,
                        "raw_case_column_html_snippet": (snippet or "")[:400],
                        "_matched_auction_date_requested": remaining[ncn]["auction_date"],
                        "_platform": platform_domain,
                        "_aid": it.get("aid"),
                    }
                    del remaining[ncn]
            time.sleep(0.3)

    # Anything left unfound on realforeclose for its expected date -- report NOT_FOUND.
    for ncn, c in remaining.items():
        result[c["case_number"]] = {
            "found_on_calendar": False,
            "docid": None,
            "raw_case_column_html_snippet": None,
            "_note": "NOT_FOUND_ON_CALENDAR (realforeclose, expected date checked)",
        }

    print(json.dumps(result, indent=2))
    if errors:
        print("\nERRORS ENCOUNTERED:", file=sys.stderr)
        print(json.dumps(errors, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
