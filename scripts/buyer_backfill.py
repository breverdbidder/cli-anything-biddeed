#!/usr/bin/env python3
"""
Buyer Backfill — Name On Title + Plaintiff from RealForeclose Detail Pages
Runs via GitHub Actions (buyer-backfill.yml) with real secrets.
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SINCE_DATE, UNTIL_DATE, TARGET_COUNTY
     REALFORECLOSE_EMAIL, REALFORECLOSE_PASSWORD (optional — for authenticated sessions)
"""
import json, os, re, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone, date

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or
          os.environ.get("SUPABASE_KEY") or "")
if not SB_URL or not SB_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required", file=sys.stderr)
    sys.exit(1)

SINCE     = os.environ.get("SINCE_DATE", "2026-07-01")
UNTIL     = os.environ.get("UNTIL_DATE", "") or date.today().isoformat()
COUNTY    = os.environ.get("TARGET_COUNTY", "").lower().strip()
RF_EMAIL  = os.environ.get("REALFORECLOSE_EMAIL", "")
RF_PW     = os.environ.get("REALFORECLOSE_PASSWORD", "")
THROTTLE  = 2.5
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36"

SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

RF_SUBDOMAINS = {
    "alachua": "alachua.realforeclose.com",
    "bay": "bay.realforeclose.com",
    "brevard": "brevard.realforeclose.com",
    "broward": "broward.realforeclose.com",
    "charlotte": "charlotte.realforeclose.com",
    "clay": "clay.realforeclose.com",
    "collier": "collier.realtaxdeed.com",
    "duval": "duval.realforeclose.com",
    "escambia": "escambia.realforeclose.com",
    "flagler": "flagler.realforeclose.com",
    "hendry": "hendry.realforeclose.com",
    "highlands": "highlands.realforeclose.com",
    "hillsborough": "hillsborough.realforeclose.com",
    "indian_river": "indian-river.realforeclose.com",
    "jackson": "jackson.realforeclose.com",
    "lake": "lake.realforeclose.com",
    "lee": "lee.realtaxdeed.com",
    "leon": "leon.realforeclose.com",
    "manatee": "manatee.realforeclose.com",
    "marion": "marion.realforeclose.com",
    "miami_dade": "miamidade.realtaxdeed.com",
    "nassau": "nassau.realforeclose.com",
    "okaloosa": "okaloosa.realforeclose.com",
    "orange": "orange.realtaxdeed.com",
    "palm_beach": "palmbeach.realforeclose.com",
    "pasco": "pasco.realforeclose.com",
    "pinellas": "pinellas.realforeclose.com",
    "polk": "polk.realforeclose.com",
    "putnam": "putnam.realforeclose.com",
    "sarasota": "sarasota.realforeclose.com",
    "seminole": "seminole.realforeclose.com",
    "st_lucie": "stlucie.realforeclose.com",
    "volusia": "volusia.realforeclose.com",
    "walton": "walton.realforeclose.com",
    "washington": "washington.realtaxdeed.com",
    "calhoun": "calhoun.realtaxdeed.com",
    "dixie": "dixie.realforeclose.com",
    "franklin": "franklin.realforeclose.com",
    "gadsden": "gadsden.realforeclose.com",
    "hernando": "hernando.realforeclose.com",
    "indian_river": "indian-river.realforeclose.com",
    "martin": "martin.realforeclose.com",
    "monroe": "monroe.realforeclose.com",
    "osceola": "osceola.realforeclose.com",
    "putnam": "putnam.realforeclose.com",
    "santa_rosa": "santarosa.realforeclose.com",
    "st_johns": "stjohns.realforeclose.com",
    "sumter": "sumter.realforeclose.com",
    "wakulla": "wakulla.realtaxdeed.com",
}

def sb_get(path):
    safe_path = urllib.parse.quote(path, safe="/?&=.,()")
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{safe_path}",
        headers={**SB_HEADERS, "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  SB GET error: {e}", file=sys.stderr)
        return []

def sb_patch(row_id, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}",
        data=body, method="PATCH", headers=SB_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except Exception as e:
        print(f"  SB PATCH error: {e}", file=sys.stderr)
        return 0

import http.cookiejar as _hcj
_cj     = _hcj.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cj))

def rf_login(subdomain):
    if not RF_EMAIL or not RF_PW:
        return False
    try:
        data = urllib.parse.urlencode({"LogName": RF_EMAIL, "LogPass": RF_PW, "LogButton": "Login"}).encode()
        req  = urllib.request.Request(
            f"https://{subdomain}/index.cfm",
            data=data,
            headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
                     "Referer": f"https://{subdomain}/"})
        with _opener.open(req, timeout=20) as r:
            html = r.read().decode("utf-8", "replace")
            return "logout" in html.lower()
    except:
        return False

_logged_in = set()

def fetch_page(url, subdomain=None):
    if subdomain and subdomain not in _logged_in and RF_EMAIL:
        if rf_login(subdomain):
            _logged_in.add(subdomain)
            print(f"  🔑 Authenticated to {subdomain}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            time.sleep(THROTTLE if attempt == 0 else THROTTLE * 2)
            with _opener.open(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if attempt == 2:
                print(f"  ✗ fetch failed: {e}")
    return None

def extract_winner_plaintiff(html):
    result = {"winning_bidder": None, "plaintiff": None, "tier1_buyer_type": None}
    if not html:
        return result

    # winning_bidder — multiple patterns
    for pat in [
        r'Name\s+On\s+Title[^<]*</td>\s*<td[^>]*>\s*([^<]{2,80})',
        r'<td[^>]*>\s*Name\s+On\s+Title\s*</td>\s*<td[^>]*>\s*([^<]{2,80})',
        r'Name\s+On\s+Title.*?<span[^>]*ASTAT[^>]*>\s*([^<]{2,80})',
        r'(?:Winner|Successful\s+Bidder)[^<]*</td>\s*<td[^>]*>\s*([^<]{2,80})',
        r'High\s+Bidder[^<]*</td>\s*<td[^>]*>\s*([^<]{2,80})',
    ]:
        m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
        if m:
            val = m.group(1).strip().rstrip('</ ').strip()
            if val and 2 < len(val) < 100 and val.lower() not in ('n/a','pending','none',''):
                result["winning_bidder"] = val
                break

    # plaintiff
    for pat in [
        r'<td[^>]*>\s*Plaintiff\s*</td>\s*<td[^>]*>\s*([^<]{5,200}?)\s*</td>',
        r'Plaintiff[^<]{0,30}</td>\s*<td[^>]*>\s*([^<]{5,200})',
        r'<td[^>]*>Plaintiff</td>.*?<td[^>]*>([^<]{5,200})',
    ]:
        m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
        if m:
            val = m.group(1).strip().replace("&amp;","&").replace("&#39;","'")
            val = re.sub(r'\s+', ' ', val)
            if val and 3 < len(val) < 200:
                result["plaintiff"] = val
                break

    # buyer_type
    w = (result["winning_bidder"] or "").lower().strip()
    p = (result["plaintiff"] or "").lower().strip()
    if w and p:
        result["tier1_buyer_type"] = (
            "plaintiff" if (w[:20] == p[:20] or w in p or p[:30] in w)
            else "third_party"
        )
    elif w:
        result["tier1_buyer_type"] = "third_party"

    return result

def build_detail_url(row):
    src = row.get("source_url") or ""
    if ("AID=" in src and "realforeclose" in src) or "realtaxdeed" in src or "realtaxlien" in src:
        domain = src.replace("https://", "").replace("http://", "").split("/")[0]
        return src, domain

    county    = (row.get("county") or "").lower()
    case      = (row.get("case_number") or "").strip()
    subdomain = RF_SUBDOMAINS.get(county)

    if subdomain and case:
        case_enc = urllib.parse.quote(case)
        return (f"https://{subdomain}/index.cfm?zaction=AUCTION&Zmethod=DETAIL&CASENUM={case_enc}",
                subdomain)

    rf_url = row.get("realforeclose_url") or ""
    if rf_url and case:
        domain = rf_url.rstrip("/").replace("https://","").split("/")[0]
        case_enc = urllib.parse.quote(case)
        return (f"https://{domain}/index.cfm?zaction=AUCTION&Zmethod=DETAIL&CASENUM={case_enc}",
                domain)

    return None, None

def main():
    print("=" * 65)
    print(f"BUYER BACKFILL  {SINCE} → {UNTIL}" + (f"  county={COUNTY}" if COUNTY else "  all counties"))
    print("=" * 65)

    # Build query
    filters = [
        f"auction_date=gte.{SINCE}",
        f"auction_date=lte.{UNTIL}",
        "or=(tier1_sale_status.eq.SOLD,auction_status.in.(completed,sold))",
        "or=(winning_bidder.is.null,winning_bidder.in.(3rd Party Bidder,Cert Holder,Unknown))",
        "select=id,case_number,county,sale_type,property_address,auction_date,tier1_sold_amount,source_url,realforeclose_url",
        "limit=500",
        "order=county.asc,auction_date.desc",
    ]
    if COUNTY:
        filters.insert(2, f"county=eq.{COUNTY}")

    rows = sb_get("multi_county_auctions?" + "&".join(filters))
    print(f"Rows to process: {len(rows)}\n")

    stats = {"fetched":0, "winner":0, "plaintiff":0, "third_party":0,
             "no_url":0, "no_data":0, "patched":0}

    for i, row in enumerate(rows):
        county   = row.get("county","?")
        case     = row.get("case_number","?")
        addr     = row.get("property_address","?")[:50]
        sold     = row.get("tier1_sold_amount","?")

        url, subdomain = build_detail_url(row)
        if not url:
            print(f"[{i+1:3d}] {county:15s} NO URL — {case}")
            stats["no_url"] += 1
            continue

        print(f"[{i+1:3d}] {county:15s} ${sold:>10} | {addr}")

        html = fetch_page(url, subdomain)
        stats["fetched"] += 1

        ext = extract_winner_plaintiff(html)
        w   = ext["winning_bidder"]
        p   = ext["plaintiff"]
        bt  = ext["tier1_buyer_type"]

        if not w and not p:
            print(f"       ✗ no data extracted")
            stats["no_data"] += 1
            continue

        patch = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if w:
            patch["winning_bidder"] = w
            stats["winner"] += 1
        if p:
            patch["plaintiff"] = p
            stats["plaintiff"] += 1
        if bt:
            patch["tier1_buyer_type"] = bt
            if bt == "third_party":
                stats["third_party"] += 1

        status = sb_patch(row["id"], patch)
        if status:
            stats["patched"] += 1

        print(f"       ✅ winner={w or '—'}  type={bt or '—'}")
        if p:
            print(f"          plaintiff={p[:60]}")

    print("\n" + "=" * 65)
    print("SUMMARY")
    for k,v in stats.items():
        print(f"  {k:20s}: {v}")
    print(f"\n  🎯 3rd-party buyers found: {stats['third_party']}")
    print(f"  📬 Lead funnel additions:  {stats['third_party']} new buyer profiles (via DB trigger)")

if __name__ == "__main__":
    main()
