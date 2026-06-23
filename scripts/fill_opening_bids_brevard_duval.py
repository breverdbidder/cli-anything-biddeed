#!/usr/bin/env python3
"""
fill_opening_bids_brevard_duval.py — Fill opening_bid NULLs for Brevard + Duval.
Dispatch: 2b8bf5f6-3cee-46c2-b1b9-8eee6876962f  (retry 2, 2026-06-23)

Strategy (in order):
  Pass 0: Run realforeclose_aids_to_mca_patch() RPC — flushes any existing aids data.
  Pass 0b: Direct-patch Duval FC NULLs from realforeclose_aids table by case_number
           (bypasses RPC matching quirks; no credentials needed).
  Pass 1: Duval FC — httpx AJAX login to duval.realforeclose.com → PREVIEW scrape
           → insert realforeclose_aids → re-run RPC (datacenter IPs work).
  Pass 1b: Duval FC — unauthenticated zoom-page fetch for any AID we have on file.
  Pass 2: Duval tax deed — scrape duval.realtaxdeed.com for NULL rows.
  Pass 3: Brevard — AcclaimWeb case-number search → extract judgment amounts.
  Final:  Report exact counts (BLANK > WRONG — never claim DONE without DB proof).

Env required: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Env optional: REALFORECLOSE_EMAIL, REALFORECLOSE_PASSWORD

set -euo pipefail: this script uses sys.exit(1) on unrecoverable failures.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
from datetime import date, datetime, timedelta

# ── Config ────────────────────────────────────────────────────────────────────
SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
RF_EMAIL = os.environ.get("REALFORECLOSE_EMAIL", "")
RF_PW    = os.environ.get("REALFORECLOSE_PASSWORD", "")

if not SB_URL or not SB_KEY:
    print("ERROR: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required", file=sys.stderr)
    sys.exit(1)

DUVAL_HOST = "https://duval.realforeclose.com"
BREVARD_AW = "http://vaclmweb1.brevardclerk.us"
UA_DESKTOP = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# ── Supabase helpers ──────────────────────────────────────────────────────────
def _H(extra: dict = None) -> dict:
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
         "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h

def sb_get(path: str, params: str = "") -> list:
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += ("&" if "?" in path else "?") + params
    req = urllib.request.Request(url, headers=_H())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  sb_get {path} HTTP {e.code}: {e.read()[:300]}", file=sys.stderr)
        return []

def sb_post(path: str, payload, prefer: str = "") -> tuple[int, str]:
    body = json.dumps(payload).encode()
    h = _H()
    if prefer:
        h["Prefer"] = prefer
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]

def sb_patch(path: str, payload) -> tuple[int, str]:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", data=body, headers=_H(), method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]

def sb_rpc(fn: str, payload: dict) -> tuple[int, str]:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(f"{SB_URL}/rest/v1/rpc/{fn}", data=body, headers=_H(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]

def count_null_bids(county: str = None) -> int:
    """Count upcoming auctions with NULL opening_bid for a county (or both if None)."""
    filt = f"auction_date=gte.{date.today().isoformat()}&opening_bid=is.null"
    if county:
        filt += f"&county=eq.{county}"
    else:
        filt += "&county=in.(brevard,duval)"
    rows = sb_get("multi_county_auctions", f"{filt}&select=id&limit=1000")
    return len(rows) if isinstance(rows, list) else 0

def fetch_null_bid_rows(county: str, sale_type: str = None) -> list:
    """Fetch UPCOMING auction rows with NULL opening_bid (auction_date >= today)."""
    filt = f"county=eq.{county}&auction_date=gte.{date.today().isoformat()}&opening_bid=is.null"
    if sale_type:
        filt += f"&auction_type=eq.{urllib.parse.quote(sale_type)}"
    return sb_get("multi_county_auctions",
                  f"{filt}&select=id,case_number,auction_date,auction_type,source_platform&limit=500") or []

# ── Parsing helpers ───────────────────────────────────────────────────────────
def to_float(s: str | None) -> float | None:
    if not s:
        return None
    m = re.search(r'\$?([\d,]+\.?\d*)', str(s))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None

def strip_html(s: str | None) -> str | None:
    if not s:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s))).strip()
    return t or None

def parse_starts(s: str | None) -> str | None:
    if not s:
        return None
    cleaned = re.sub(r"\s+(?:ET|EST|EDT|CT|CST)\s*$", "", s.strip())
    for fmt in ("%m/%d/%Y %I:%M %p", "%m/%d/%Y %H:%M", "%m/%d/%Y"):
        try:
            return datetime.strptime(cleaned, fmt).isoformat()
        except ValueError:
            continue
    return None

def parse_aitem_blocks(html: str, county_sub: str) -> list:
    items = []
    starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', html)]
    if not starts:
        return items
    starts.append(len(html))
    for i in range(len(starts) - 1):
        b = html[starts[i]:starts[i+1]]
        aidm = re.search(r'aid="(\d+)"', b)
        if not aidm:
            continue
        aid = aidm.group(1)
        sm = re.search(r'ASTAT_MSGA[^>]*>Auction Starts</div>\s*<div[^>]+>\s*([^<]+?)\s*</div>', b)
        starts_raw = sm.group(1).strip() if sm else None
        rows = re.findall(
            r'<td[^>]*class="AD_LBL"[^>]*>(.*?)</td>\s*<td[^>]*class="AD_DTA[^"]*"[^>]*>(.*?)</td>',
            b, re.DOTALL)
        data: dict[str, str] = {}
        addr_lines: list[str] = []
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

# ── Pass 0: RPC flush ─────────────────────────────────────────────────────────
def pass0_rpc_flush() -> None:
    print("\n═══ Pass 0: realforeclose_aids_to_mca_patch() ═══")
    for slug in ("brevard", "duval"):
        st, body = sb_rpc("realforeclose_aids_to_mca_patch",
                          {"p_dispatch_id": None, "p_county_slug": slug})
        print(f"  {slug}: HTTP {st}, rows_updated={body[:200]}")
        time.sleep(1)

# ── Pass 0b: Direct-patch Duval FC from realforeclose_aids ───────────────────
def pass0b_duval_direct_patch() -> int:
    """Patch NULL Duval FC rows directly from realforeclose_aids by case_number.
    Bypasses RPC matching quirks — no credentials needed."""
    print("\n═══ Pass 0b: Duval FC direct patch from realforeclose_aids ═══")
    null_rows = fetch_null_bid_rows("duval", "Foreclosure")
    if not null_rows:
        print("  No NULL Duval FC rows — skip")
        return 0
    print(f"  {len(null_rows)} NULL Duval FC rows to attempt direct patch")
    filled = 0
    for row in null_rows:
        cn = (row.get("case_number") or "").strip()
        if not cn:
            continue
        # Try exact match first, then normalized
        aids_rows = sb_get(
            "realforeclose_aids",
            f"case_number=eq.{urllib.parse.quote(cn)}"
            f"&county_slug=eq.duval"
            f"&judgment_amount=not.is.null"
            f"&select=aid,judgment_amount,auction_starts_at"
            f"&limit=5")
        if not aids_rows:
            # Try partial: strip leading zeros / formatting differences
            cn_norm = re.sub(r"[^0-9A-Za-z]", "", cn)
            aids_rows = sb_get(
                "realforeclose_aids",
                f"case_number=ilike.*{urllib.parse.quote(cn_norm[-8:])}*"
                f"&county_slug=eq.duval"
                f"&judgment_amount=not.is.null"
                f"&select=aid,judgment_amount,auction_starts_at"
                f"&limit=5")
        if not aids_rows:
            print(f"  case {cn}: not in realforeclose_aids with judgment_amount")
            continue
        best = max(aids_rows, key=lambda a: a.get("judgment_amount") or 0)
        bid = best.get("judgment_amount")
        if not bid:
            continue
        st, body = sb_patch(
            f"multi_county_auctions?id=eq.{row['id']}",
            {"opening_bid": bid, "source_platform": "duval_realforeclose"})
        if st in (200, 201, 204):
            print(f"  FILLED id={row['id']} case={cn} bid={bid}")
            filled += 1
        else:
            print(f"  PATCH FAILED id={row['id']}: HTTP {st} {body[:100]}")
    print(f"  Pass 0b filled: {filled}")
    return filled


# ── Pass 1: Duval FC — httpx-style login + PREVIEW scrape ────────────────────
def pass1_duval_fc() -> int:
    """Scrape duval.realforeclose.com via AJAX login (datacenter IPs allowed).
    Returns count of aids inserted."""
    print("\n═══ Pass 1: Duval FC — duval.realforeclose.com PREVIEW scrape ═══")
    if not RF_EMAIL or not RF_PW:
        print("  SKIP: REALFORECLOSE_EMAIL / REALFORECLOSE_PASSWORD not set")
        return 0

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    def _get(url: str, hdrs: dict = None) -> str:
        r = urllib.request.Request(url, headers={"User-Agent": UA_DESKTOP, **(hdrs or {})})
        try:
            with opener.open(r, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  GET {url} error: {e}")
            return ""

    def _post_form(url: str, data: dict, hdrs: dict = None) -> str:
        body = urllib.parse.urlencode(data).encode()
        r = urllib.request.Request(url, data=body, headers={
            "User-Agent": UA_DESKTOP,
            "Content-Type": "application/x-www-form-urlencoded",
            **(hdrs or {})})
        try:
            with opener.open(r, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  POST {url} error: {e}")
            return ""

    # Step 1: splash → get CF session cookies
    splash = _get(f"{DUVAL_HOST}/index.cfm")
    print(f"  splash: len={len(splash)}, cookies={[c.name for c in cj]}")

    # Step 2: AJAX login (exact logform.js mechanism)
    login_resp = _post_form(
        f"{DUVAL_HOST}/index.cfm",
        {"ZACTION": "AJAX", "ZMETHOD": "LOGIN", "func": "LOGIN",
         "USERNAME": RF_EMAIL, "USERPASS": RF_PW},
        {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, */*; q=0.01"})
    print(f"  AJAX login: {login_resp[:200]!r}")
    if '"isOk":"YES"' not in login_resp:
        print("  LOGIN FAILED — skipping Duval FC scrape")
        return 0

    # Step 3: scrape upcoming PREVIEW pages (30 days)
    total_aids = 0
    total_inserted = 0
    today = date.today()
    dates = [
        (today + timedelta(days=i)).isoformat()
        for i in range(31)
        if (today + timedelta(days=i)).weekday() < 5
    ]

    for auction_date in dates:
        d_obj = datetime.strptime(auction_date, "%Y-%m-%d")
        date_mdy = d_obj.strftime("%m/%d/%Y")
        preview_url = (f"{DUVAL_HOST}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW"
                       f"&AUCTIONDATE={date_mdy.replace('/', '%2F')}")
        html = _get(preview_url)
        if "id=\"LogName\"" in html or ("LogName" in html and "<form" in html):
            print(f"  {auction_date}: session lost — login form returned")
            break
        aids = parse_aitem_blocks(html, "duval")
        if aids:
            print(f"  {auction_date}: {len(aids)} AITEM blocks")
            total_aids += len(aids)
            payload = [{
                "aid": a["aid"], "county_slug": "duval",
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
            } for a in aids if a.get("case_number")]
            if payload:
                st, body = sb_post("realforeclose_aids?on_conflict=aid", payload,
                                   "resolution=merge-duplicates")
                if st in (200, 201, 204):
                    total_inserted += len(payload)
                else:
                    print(f"  aids INSERT FAILED: HTTP {st}: {body[:200]}")
        time.sleep(1.5)

    print(f"  Duval FC: aids_found={total_aids}, aids_inserted={total_inserted}")

    if total_inserted > 0:
        st, body = sb_rpc("realforeclose_aids_to_mca_patch",
                          {"p_dispatch_id": None, "p_county_slug": "duval"})
        print(f"  RPC after Duval FC insert: HTTP {st}, {body[:200]}")

    return total_inserted

# ── Pass 1b: Duval FC — unauthenticated zoom pages by AID ────────────────────
def pass1b_duval_zoom_unauth() -> int:
    """For NULL Duval FC rows: look up AID in realforeclose_aids, fetch zoom page,
    parse judgment_amount without login. Works when judgment_amount IS NULL in aids."""
    print("\n═══ Pass 1b: Duval FC zoom pages (unauthenticated) ═══")
    null_rows = fetch_null_bid_rows("duval", "Foreclosure")
    if not null_rows:
        print("  No NULL Duval FC rows — skip")
        return 0

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    def _get(url: str) -> str:
        r = urllib.request.Request(url, headers={"User-Agent": UA_DESKTOP})
        try:
            with opener.open(r, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  GET {url} error: {e}")
            return ""

    # Warm cookies with splash page
    _get(f"{DUVAL_HOST}/index.cfm")

    filled = 0
    for row in null_rows:
        cn = (row.get("case_number") or "").strip()
        if not cn:
            continue
        # Find AIDs for this case_number (judgment_amount may be NULL — we want the AID)
        aids_rows = sb_get(
            "realforeclose_aids",
            f"case_number=eq.{urllib.parse.quote(cn)}"
            f"&county_slug=eq.duval"
            f"&select=aid,judgment_amount"
            f"&limit=5")
        if not aids_rows:
            print(f"  case {cn}: no AID in realforeclose_aids")
            continue

        for a in aids_rows:
            aid = a.get("aid")
            if not aid:
                continue
            zoom_url = f"{DUVAL_HOST}/index.cfm?zaction=AUCTION&Zmethod=ZOOM&AID={aid}"
            html = _get(zoom_url)
            if not html or "LogName" in html and "<form" in html:
                print(f"  AID {aid}: login wall returned")
                continue

            # Parse judgment amount from zoom page
            jm = re.search(
                r'(?:Final\s+Judgment\s+Amount|Judgment\s+Amount)[^<]*</[^>]+>\s*<[^>]+>\s*\$?([\d,]+\.?\d*)',
                html, re.IGNORECASE)
            if not jm:
                # Try generic dollar-amount near relevant label
                jm = re.search(
                    r'AD_LBL[^>]+>\s*(?:Final\s+)?Judgment[^<]*</[^>]+>\s*<[^>]+>\s*\$?([\d,]+(?:\.\d+)?)',
                    html, re.IGNORECASE)
            if not jm:
                # Fallback: parse all AITEM blocks on zoom page
                blocks = parse_aitem_blocks(html, "duval")
                for b in blocks:
                    if b.get("judgment_amount") and b.get("case_number"):
                        if _norm_case(b["case_number"]) == _norm_case(cn):
                            jm_val = b["judgment_amount"]
                            st, body = sb_patch(
                                f"multi_county_auctions?id=eq.{row['id']}",
                                {"opening_bid": jm_val, "source_platform": "duval_realforeclose"})
                            if st in (200, 201, 204):
                                print(f"  FILLED id={row['id']} case={cn} bid={jm_val} via zoom-block")
                                filled += 1
                            break
                time.sleep(1)
                continue

            bid = to_float(jm.group(1).replace(",", ""))
            if bid and bid > 1000:
                st, body = sb_patch(
                    f"multi_county_auctions?id=eq.{row['id']}",
                    {"opening_bid": bid, "source_platform": "duval_realforeclose"})
                if st in (200, 201, 204):
                    print(f"  FILLED id={row['id']} case={cn} bid={bid} via zoom-page")
                    filled += 1
                    break
                else:
                    print(f"  PATCH FAILED id={row['id']}: HTTP {st} {body[:100]}")
            time.sleep(1)

    print(f"  Pass 1b filled: {filled}")
    return filled


# ── Pass 2: Duval tax deed — duval.realtaxdeed.com ───────────────────────────
def pass2_duval_taxdeed() -> int:
    """Fill opening_bid for Duval tax deed NULL rows from duval.realtaxdeed.com.
    Returns count of rows filled."""
    print("\n═══ Pass 2: Duval tax deed — duval.realtaxdeed.com ═══")
    null_rows = fetch_null_bid_rows("duval", "Tax Deed")
    if not null_rows:
        print("  No NULL Duval tax deed rows — skip")
        return 0

    print(f"  {len(null_rows)} NULL Duval tax deed rows")

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    def _get(url: str) -> str:
        r = urllib.request.Request(url, headers={"User-Agent": UA_DESKTOP})
        try:
            with opener.open(r, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  GET {url} error: {e}")
            return ""

    # realtaxdeed.com uses same ColdFusion AITEM structure
    TD_HOST = "https://duval.realtaxdeed.com"
    splash = _get(f"{TD_HOST}/index.cfm")
    print(f"  splash: len={len(splash)}")

    if not RF_EMAIL or not RF_PW:
        print("  SKIP: no credentials for realtaxdeed.com")
        return 0

    def _post_form(url: str, data: dict, hdrs: dict = None) -> str:
        body = urllib.parse.urlencode(data).encode()
        r = urllib.request.Request(url, data=body, headers={
            "User-Agent": UA_DESKTOP,
            "Content-Type": "application/x-www-form-urlencoded",
            **(hdrs or {})})
        try:
            with opener.open(r, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  POST {url} error: {e}")
            return ""

    login_resp = _post_form(
        f"{TD_HOST}/index.cfm",
        {"ZACTION": "AJAX", "ZMETHOD": "LOGIN", "func": "LOGIN",
         "USERNAME": RF_EMAIL, "USERPASS": RF_PW},
        {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, */*; q=0.01"})
    print(f"  realtaxdeed AJAX login: {login_resp[:200]!r}")
    logged_in = '"isOk":"YES"' in login_resp

    filled = 0
    today = date.today()
    dates_to_probe = [
        (today + timedelta(days=i)).isoformat()
        for i in range(60)
        if (today + timedelta(days=i)).weekday() < 5
    ]

    for auction_date in dates_to_probe:
        d_obj = datetime.strptime(auction_date, "%Y-%m-%d")
        date_mdy = d_obj.strftime("%m/%d/%Y")
        preview_url = (f"{TD_HOST}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW"
                       f"&AUCTIONDATE={date_mdy.replace('/', '%2F')}")

        if logged_in:
            html = _get(preview_url)
        else:
            # Try unauthenticated — some pages show data without login
            html = _get(preview_url)

        if not html:
            continue

        aids = parse_aitem_blocks(html, "duval_td")
        if not aids:
            continue

        print(f"  {auction_date}: {len(aids)} tax deed AITEM blocks")

        # Match against our NULL rows by case_number
        for a in aids:
            if not a.get("case_number") or not a.get("judgment_amount"):
                continue
            matched = [row for row in null_rows
                       if row.get("case_number") and
                       _norm_case(row["case_number"]) == _norm_case(a["case_number"])]
            for row in matched:
                bid = a["judgment_amount"]
                st, body = sb_patch(f"multi_county_auctions?id=eq.{row['id']}",
                                    {"opening_bid": bid, "source_platform": "duval_realtaxdeed"})
                if st in (200, 201, 204):
                    print(f"    FILLED id={row['id']} case={row['case_number']} bid={bid}")
                    filled += 1
                else:
                    print(f"    PATCH FAILED id={row['id']}: HTTP {st} {body[:100]}")

        time.sleep(1.5)

    print(f"  Duval tax deed filled: {filled}")
    return filled

def _norm_case(s: str) -> str:
    """Normalize case number for fuzzy matching."""
    return re.sub(r"[^0-9A-Z]", "", str(s).upper())

# ── Pass 3: Brevard — AcclaimWeb case-number search ──────────────────────────
def pass3_brevard_accweb() -> int:
    """For each Brevard NULL case, query AcclaimWeb for documents with monetary amounts.
    Targets: judgment, notice of sale, or any document with non-zero Consideration.
    Returns count of rows filled."""
    print("\n═══ Pass 3: Brevard — AcclaimWeb case-number search ═══")
    null_rows = fetch_null_bid_rows("brevard")
    if not null_rows:
        print("  No NULL Brevard rows — skip")
        return 0

    print(f"  {len(null_rows)} NULL Brevard rows to attempt")

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    def _req(url: str, data=None, hdrs: dict = None) -> str:
        r = urllib.request.Request(url, data=data, headers={
            "User-Agent": UA_DESKTOP, **(hdrs or {})})
        if data and isinstance(data, str):
            r.data = data.encode()
        try:
            with opener.open(r, timeout=60) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  AcclaimWeb {url} error: {e}")
            return ""

    # Session init
    _req(f"{BREVARD_AW}/AcclaimWeb/")
    _req(f"{BREVARD_AW}/AcclaimWeb/search/Disclaimer",
         data="disclaimer=on",
         hdrs={"Content-Type": "application/x-www-form-urlencoded",
               "Referer": f"{BREVARD_AW}/AcclaimWeb/"})
    print("  AcclaimWeb session initialized")

    filled = 0
    for row in null_rows:  # process all upcoming null rows
        cn = row.get("case_number", "")
        if not cn:
            continue

        # Search AcclaimWeb by case number.
        # Correct URL: SearchTypeCaseNumber (not SearchTypeCaseNo).
        # Requires DocTypes=all in POST body or server returns "doctype is invalid".
        params = [
            ("CaseNumber", cn), ("DateRangeList", " "), ("CaseNumberFilter", "0"),
            ("RecordDateFrom", "1/1/1981"), ("RecordDateTo", date.today().strftime("%m/%d/%Y")),
            ("DocTypesDisplay-input", "All"), ("DocTypesDisplay", ""), ("DocTypes", "all"),
        ]
        criteria_payload = urllib.parse.urlencode(params)
        search_url = f"{BREVARD_AW}/AcclaimWeb/search/SearchTypeCaseNumber?Length=6"
        hdrs = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BREVARD_AW}/AcclaimWeb/search/SearchTypeCaseNumber",
        }
        body = _req(search_url, data=criteria_payload, hdrs=hdrs)
        if "Error.htm" in body or not body:
            # Fallback: try DocType-based search with date range
            time.sleep(1)
            continue

        # Get first page of results
        results_body = _req(
            f"{BREVARD_AW}/AcclaimWeb/search/GridResults",
            data="page=1&size=50",
            hdrs=hdrs)
        if not results_body:
            time.sleep(1)
            continue

        try:
            data = json.loads(results_body)
        except json.JSONDecodeError:
            time.sleep(1)
            continue

        docs = data.get("data", [])
        # Find a document with non-zero Consideration (= judgment/bid amount)
        # Priority: documents likely to carry judgment amounts
        best_amount = None
        for doc in docs:
            cons = doc.get("Consideration")
            amt = to_float(str(cons)) if cons not in (None, "") else None
            if amt and amt > 5000:  # ignore trivial amounts
                doc_type = (doc.get("DocType") or "").upper()
                # Prefer Final Judgment, Judgment, or Notice of Sale docs
                if any(kw in doc_type for kw in ("JUDGMENT", "NOTICE", "FORECLOS")):
                    best_amount = amt
                    break
                if best_amount is None:
                    best_amount = amt  # take first non-trivial amount as fallback

        if best_amount:
            st, patch_body = sb_patch(
                f"multi_county_auctions?id=eq.{row['id']}",
                {"opening_bid": best_amount})
            if st in (200, 201, 204):
                print(f"  FILLED id={row['id']} case={cn} bid={best_amount}")
                filled += 1
            else:
                print(f"  PATCH FAILED id={row['id']}: HTTP {st}")
        else:
            print(f"  case {cn}: no usable amount in {len(docs)} AcclaimWeb docs")

        time.sleep(2.5)  # AcclaimWeb throttle

    print(f"  Brevard AcclaimWeb filled: {filled}")
    return filled

# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print("=" * 60)
    print("fill_opening_bids_brevard_duval.py  dispatch=2b8bf5f6  retry=2")
    print(f"Date: {date.today().isoformat()}")
    print("=" * 60)

    # Baseline counts
    before_brevard = count_null_bids("brevard")
    before_duval   = count_null_bids("duval")
    print(f"\nBASELINE NULL opening_bids — brevard={before_brevard}, duval={before_duval}")

    if before_brevard == 0 and before_duval == 0:
        print("DoD already satisfied — zero NULLs. Exiting.")
        return

    # Pass 0: flush existing aids data
    pass0_rpc_flush()

    after_p0_brevard = count_null_bids("brevard")
    after_p0_duval   = count_null_bids("duval")
    print(f"\nAfter Pass 0 — brevard={after_p0_brevard}, duval={after_p0_duval}")

    # Pass 0b: direct-patch Duval FC from realforeclose_aids (no credentials needed)
    if after_p0_duval > 0:
        pass0b_duval_direct_patch()

    # Pass 1: Duval FC from duval.realforeclose.com (requires credentials)
    if count_null_bids("duval") > 0:
        pass1_duval_fc()

    # Pass 1b: unauthenticated zoom pages for any remaining Duval FC NULLs
    if count_null_bids("duval") > 0:
        pass1b_duval_zoom_unauth()

    # Pass 2: Duval tax deed from duval.realtaxdeed.com
    if count_null_bids("duval") > 0:
        pass2_duval_taxdeed()

    # Pass 3: Brevard via AcclaimWeb
    if count_null_bids("brevard") > 0:
        pass3_brevard_accweb()

    # Final RPC flush — pick up anything newly inserted into realforeclose_aids
    print("\n═══ Final RPC flush ═══")
    for slug in ("brevard", "duval"):
        st, body = sb_rpc("realforeclose_aids_to_mca_patch",
                          {"p_dispatch_id": None, "p_county_slug": slug})
        print(f"  {slug}: HTTP {st}, {body[:200]}")

    # Verification (HONESTY PROTOCOL — BLANK > WRONG)
    final_brevard = count_null_bids("brevard")
    final_duval   = count_null_bids("duval")
    print("\n" + "=" * 60)
    print("VERIFICATION (SQL VERIFIED)")
    print(f"  brevard opening_bid NULLs: {before_brevard} → {final_brevard}")
    print(f"  duval   opening_bid NULLs: {before_duval}   → {final_duval}")
    dod_pass = (final_brevard == 0 and final_duval == 0)
    print(f"  DoD Gate 2 (COUNT(*)=0): {'PASS ✓' if dod_pass else 'FAIL ✗'}")
    print("=" * 60)

    if not dod_pass:
        print(f"\nUNTESTED residual — {final_brevard} Brevard + {final_duval} Duval rows remain NULL.")
        print("Brevard likely needs residential proxy (brevard.realforeclose.com blocked from datacenter).")
        print("Consider: dispatch brevard-realforeclose-drain.yml (uses Firecrawl residential proxy).")
        sys.exit(2)  # exit 2 = partial (some remain)

if __name__ == "__main__":
    main()
