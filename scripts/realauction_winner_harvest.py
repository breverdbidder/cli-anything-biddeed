#!/usr/bin/env python3
"""Authenticated RealAuction winner-name harvest — all counties (issue #19446).

WHY DIRECT HTTP, NOT FIRECRAWL: Firecrawl (the documented clean-IP bypass for
GitHub-runner IPs) returned 402 Insufficient Credits on 2026-08-25 — a hard
account-billing ceiling, not a code problem. Probed direct HTTP from this
runner instead: NOT IP-blocked (200 on first request). So this script talks
to {subdomain}.realforeclose.com directly. If a future runner IS blocked,
route the same request functions through Firecrawl's /v1/scrape actions
(see scripts/realauction_bidhistory.py for the previously-working pattern).

REVERSE-ENGINEERED FLOW (2026-08-25 session, confirmed against Ariel's live
manual verification of miamidade case 2022-024528-CA-01 = E&M Plumbing of
Miami Inc, $318,000.00, Case ID 231963491, bidder_id 184303 — exact match):
  1. POST /index.cfm  ZACTION=AJAX&ZMETHOD=LOGIN&func=LOGIN&USERNAME&USERPASS
     (JS source: /CORE/System/JS/logform.js)
  2. One-time "Notice" interstitial blocks all case data until accepted:
     POST /index.cfm  zaction=AJAX&zmethod=COM&process=NOTICE&func=ACCEPT&NID=<id>
     (JS source: /CORE/System/JS/notice.js). NID is read from the calendar
     page's #NOTICEMSG[NID] attribute; harmless no-op if absent.
  3. GET  /index.cfm?zaction=USER&zmethod=CALENDAR            (referer=login)
  4. GET  /index.cfm?zaction=AUCTION&Zmethod=DAYLIST&AUCTIONDATE=MM/DD/YYYY
     (referer=calendar; CALMODE for past dates is DAYLIST, NOT "PREVIEW" —
     PREVIEW silently falls back to the "My Summary" shell). Response embeds
     <div id="ALB"> = full comma-separated AID list for that auction day.
  5. Paginate case detail: GET .../UPDATE?FNC=LOAD&AREA=C&PageDir={0,1,1,...}
     &doR={1 then 0}&tx=<ms>  (referer=daylist). 10 AIDs/page, token-coded
     HTML (@A/@B/... — decoded via TOKENS below). Gives case #, parcel ID,
     property address, final judgment, assessed value per AID.
  6. Status/sold-to/amount: GET .../UPDATE?FNC=UPDATE&ref=<AIDs,comma>&tx=<ms>
     in chunks of 10 (matches real pagination; larger batches silently return
     COUNT:0 — confirmed empirically, not documented). JSON per AID: A=status
     label, B=datetime or cancellation reason text, ST=Sold To, D=amount,
     P=Plaintiff Max Bid, SBH=has-bid-history bool.
     NOTE: field H ("Name on Title/Nickname") is ALWAYS the logged-in
     account's own identity — this is the exact bug the issue's HARD
     CORRECTION section warns about. Never treat H as the winner.
  7. Per sold lot (SBH true): POST /index.cfm zaction=AJAX&zmethod=POPUP
     &p_Name=BID&p_List=<AID>&p_id=pWin1&p_back=&t=<ms>  (referer=daylist).
     Returns the Bid History modal: Case ID, End Date, Proxy + Auction bid
     ladders, and the footer "The final bid was made by {3rd party bidder|
     Plaintiff}: NAME / In the total amount of: AMOUNT".

Usage: realauction_winner_harvest.py <county_slug> <YYYY-MM-DD> [--dry-run]
Reads REALFORECLOSE_EMAIL/_PASSWORD, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
from env. Subdomain resolved from public.realauction_subdomains
(sale_type=foreclosure, is_active=true).
"""
import sys
import os
import re
import json
import time
import datetime as dt
import urllib.request
import urllib.parse
import http.cookiejar

EMAIL = os.environ.get("REALFORECLOSE_EMAIL", "")
PW = os.environ.get("REALFORECLOSE_PASSWORD", "")
SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

TOKENS = {
    "@A": '<div class="', "@B": "</div>", "@C": 'class="', "@D": "<div>",
    "@E": "AUCTION", "@F": "</td><td ", "@G": "</td></tr>", "@H": "<tr><td  ",
    "@I": "table", "@J": 'p_back="NextCheck=', "@K": 'style="Display:none"',
    "@L": "/index.cfm?zaction=auction&zmethod=details&AID=",
}


def decode_tokens(html):
    for k, v in TOKENS.items():
        html = html.replace(k, v)
    return html


class Session:
    def __init__(self, host):
        self.host = host
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def get(self, url, referer=None):
        req = urllib.request.Request(url)
        req.add_header("User-Agent", UA)
        if referer:
            req.add_header("Referer", referer)
        with self.opener.open(req, timeout=25) as r:
            return r.read().decode("utf-8", "replace")

    def post(self, url, fields, referer=None):
        data = urllib.parse.urlencode(fields).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("User-Agent", UA)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("X-Requested-With", "XMLHttpRequest")
        if referer:
            req.add_header("Referer", referer)
        with self.opener.open(req, timeout=25) as r:
            return r.read().decode("utf-8", "replace")


def login(sess):
    home = sess.host + "/index.cfm"
    sess.get(home)
    resp = sess.post(home, {"ZACTION": "AJAX", "ZMETHOD": "LOGIN", "func": "LOGIN",
                             "USERNAME": EMAIL, "USERPASS": PW}, referer=home)
    if '"isOk":"YES"' not in resp:
        return False, resp[:300]
    cal_url = sess.host + "/index.cfm?zaction=USER&zmethod=CALENDAR"
    # Some counties queue multiple sequential one-time notices (observed: up
    # to 3 on palm_beach — Plaintiff Notice, Message to Plaintiffs, ACH
    # Transactions). Accept each until the calendar renders with none left.
    for _ in range(10):
        cal_html = sess.get(cal_url, referer=home)
        m = re.search(r'id="NOTICEMSG"[^>]*NID="(\d+)"', cal_html)
        if not m:
            break
        sess.post(home, {"zaction": "AJAX", "zmethod": "COM", "process": "NOTICE",
                          "func": "ACCEPT", "showjson": "false", "NID": m.group(1)}, referer=home)
        time.sleep(1)
    return True, cal_url


def get_daylist(sess, cal_url, date_mdY):
    url = sess.host + f"/index.cfm?zaction=AUCTION&Zmethod=DAYLIST&AUCTIONDATE={date_mdY}"
    html = sess.get(url, referer=cal_url)
    m = re.search(r'id="ALB"[^>]*>([\d,]*)<', html)
    aids = [a for a in (m.group(1) if m else "").split(",") if a]
    return url, aids


def _field_re(label, group):
    return (r'(?:<tr>\s*<td\s+[^>]*class="AD_LBL"[^>]*>\s*' + re.escape(label) + r'\s*</td>\s*'
            r'<td\s+[^>]*class="AD_DTA"[^>]*>(?P<' + group + r'>[^<]*)</td>\s*</tr>)?')


CASE_ITEM_RE = re.compile(
    r'aid="(?P<aid>\d+)".*?'
    r'<tr>\s*<td\s+[^>]*class="AD_LBL"[^>]*>\s*Case #:\s*</td>\s*'
    r'<td\s+[^>]*class="AD_DTA"[^>]*><a[^>]*>(?P<case>[^<]+)</a></td>\s*</tr>\s*'
    + _field_re("Final Judgment Amount:", "judgment") + r'\s*'
    + _field_re("Parcel ID:", "parcel") + r'\s*'
    + _field_re("Property Address:", "addr") + r'\s*'
    r'(?:<tr>\s*<td\s+[^>]*class="AD_LBL"[^>]*>\s*</td>\s*'
    r'<td\s+[^>]*class="AD_DTA"[^>]*>(?P<citystate>[^<]*)</td>\s*</tr>)?\s*'
    + _field_re("Assessed Value:", "assessed"),
    re.S)


def load_all(sess, daylist_url, n_pages_hint):
    """Walk paginated FNC=LOAD, and for EACH page immediately follow with
    FNC=UPDATE for that same page's AIDs. The two calls must be paired per
    page — FNC=UPDATE only returns data for AIDs from the most-recently-
    loaded page (confirmed empirically: calling all FNC=LOAD pages first,
    then FNC=UPDATE against the accumulated AID list, silently returns
    ADATA.COUNT:0 for every page except whichever was loaded last).
    Returns (case_details, status) dicts keyed by AID.
    """
    cases, status = {}, {}
    pagedir = 0
    prev_rlist = None
    for i in range(n_pages_hint + 2):  # small safety margin
        tx = int(time.time() * 1000)
        load_url = (sess.host + "/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=C"
                    f"&PageDir={pagedir}&doR={1 if i == 0 else 0}&tx={tx}&bypassPage=0&test=1")
        body = sess.get(load_url, referer=daylist_url)
        m = re.search(r'\{"retHTML".*\}\s*$', body, re.S)
        if not m:
            break
        j = json.loads(m.group(0))
        rlist = j.get("rlist", "")
        if not rlist or rlist == prev_rlist:
            break
        prev_rlist = rlist
        decoded = decode_tokens(j.get("retHTML", ""))
        for m2 in CASE_ITEM_RE.finditer(decoded):
            d = m2.groupdict()
            cases[d["aid"]] = {
                "case_number": (d.get("case") or "").strip(),
                "judgment_amount": (d.get("judgment") or "").strip(),
                "parcel_id": (d.get("parcel") or "").strip(),
                "address": (d.get("addr") or "").strip(),
                "city_state": (d.get("citystate") or "").strip(),
                "assessed_value": (d.get("assessed") or "").strip(),
            }
        time.sleep(1.2)

        tx2 = int(time.time() * 1000)
        upd_url = sess.host + f"/index.cfm?zaction=AUCTION&ZMETHOD=UPDATE&FNC=UPDATE&ref={rlist}&tx={tx2}"
        ubody = sess.get(upd_url, referer=daylist_url)
        um = re.search(r'\{"PC".*\}\s*$', ubody, re.S)
        if um:
            uj = json.loads(um.group(0))
            for item in uj.get("ADATA", {}).get("AITEM", []):
                status[item["AID"]] = item
        pagedir = 1
        time.sleep(1.5)
    return cases, status


def money(s):
    if not s:
        return None
    s = s.replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def strip_cells(row_html):
    cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.S)
    tokens = []
    for c in cells:
        t = re.sub(r"<[^>]+>", "", c).strip()
        t = t.replace("&nbsp;", "").strip()
        if t:
            tokens.append(t)
    return tokens


def parse_ladder_section(section_html, table_name):
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", section_html, re.S)
    out = []
    for r in rows:
        tokens = strip_cells(r)
        if not tokens:
            continue
        bidder_id = None
        if tokens[0].isdigit():
            bidder_id = tokens.pop(0)
        if not tokens:
            continue
        ts = tokens.pop() if re.match(r"^\d{2}/\d{2}/\d{4}", tokens[-1]) else None
        amt = None
        if tokens and re.match(r"^\$?[\d,.]+$", tokens[-1]):
            amt = money(tokens.pop())
        note = tokens[0] if tokens else ""
        out.append({"table": table_name, "bidder_id": bidder_id, "amount": amt,
                     "note": note, "ts": ts, "is_winner": note.lower() == "winning bid"})
    return out


def get_bid_history(sess, daylist_url, aid):
    home = sess.host + "/index.cfm"
    body = sess.post(home, {"zaction": "AJAX", "zmethod": "POPUP", "p_Name": "BID",
                             "p_id": "pWin1", "p_List": aid, "p_back": "",
                             "t": str(int(time.time() * 1000))}, referer=daylist_url)
    out = {"case_id": None, "end_date": None, "winner_type": None, "winner_name": None,
           "sold_amount": None, "bid_ladder": [], "winner_bidder_id": None}

    m = re.search(r"Case ID:\s*(\d+)", body)
    if m:
        out["case_id"] = m.group(1)
    m = re.search(r"End Date:\s*([\d/: APM]+?)\s*<", body)
    if m:
        out["end_date"] = m.group(1).strip()

    proxy_m = re.search(r"<strong[^>]*>Proxy</strong>(.*?)<strong[^>]*>Auction</strong>", body, re.S)
    auction_m = re.search(r"<strong[^>]*>Auction</strong>(.*?)<table align=\"center\">", body, re.S)
    ladder = []
    if proxy_m:
        ladder += parse_ladder_section(proxy_m.group(1), "proxy")
    if auction_m:
        ladder += parse_ladder_section(auction_m.group(1), "auction")
    out["bid_ladder"] = ladder
    for row in ladder:
        if row["is_winner"]:
            out["winner_bidder_id"] = row["bidder_id"]

    footer_m = re.search(
        r"final bid was made by\s*(.*?):&nbsp;&nbsp;.*?<span[^>]*>\s*(.*?)\s*</span>",
        body, re.S)
    if footer_m:
        wtype = re.sub(r"<[^>]+>", "", footer_m.group(1)).strip()
        out["winner_type"] = "third_party" if "3rd party" in wtype.lower() else "plaintiff"
        out["winner_name"] = re.sub(r"\s+", " ", footer_m.group(2)).strip()
    amt_m = re.search(r"In the total amount of:.*?<span[^>]*>\$?([\d,.]+)</span>", body, re.S)
    if amt_m:
        out["sold_amount"] = money(amt_m.group(1))
    return out


def rest_get(path, params=""):
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}{params}")
    req.add_header("apikey", SB_KEY)
    req.add_header("Authorization", f"Bearer {SB_KEY}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def rest_post(table, payload):
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{table}",
                                  data=json.dumps(payload).encode(), method="POST")
    req.add_header("apikey", SB_KEY)
    req.add_header("Authorization", f"Bearer {SB_KEY}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Prefer", "return=representation")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def rest_patch(table, row_id, payload):
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{table}?id=eq.{row_id}",
                                  data=json.dumps(payload).encode(), method="PATCH")
    req.add_header("apikey", SB_KEY)
    req.add_header("Authorization", f"Bearer {SB_KEY}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Prefer", "return=minimal")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def rpc(fn, payload):
    req = urllib.request.Request(f"{SB_URL}/rest/v1/rpc/{fn}",
                                  data=json.dumps(payload).encode(), method="POST")
    req.add_header("apikey", SB_KEY)
    req.add_header("Authorization", f"Bearer {SB_KEY}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read().decode()


def record_verified_outcome(sale_type, county, case_num, source_tag, winning_bid,
                             property_address, parcel_id, auction_date):
    """Mirror a sold lot into tax_deed_outcomes/foreclosure_outcomes.

    pencil_dod_evaluate_county's letter-B independence check only counts a
    closed_sold row as "verified" if a matching case_number row exists in
    these outcomes tables with a non-promote data_source (see gold standard
    canon B). This script previously wrote sold_amount straight onto
    multi_county_auctions and nothing else, so every county it ran against
    silently failed to accrue B credit for its own (authoritative,
    independently-scraped) winner data — root-caused live 2026-08-26 via
    washington B regressing 100%->55.9% (issue #19478 architect triage).
    """
    if winning_bid is None:
        return
    table = "tax_deed_outcomes" if sale_type == "tax_deed" else "foreclosure_outcomes"
    existing = rest_get(table, f"?case_number=eq.{urllib.parse.quote(case_num)}&county=eq.{county}&select=case_number")
    if existing:
        return
    payload = {
        "case_number": case_num, "county": county, "auction_date": auction_date,
        "winning_bid": winning_bid, "outcome": "SOLD",
        "property_address": property_address, "parcel_id": parcel_id,
        "data_source": source_tag,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    rest_post(table, payload)


PLATFORM_SALE_TYPE = {"realforeclose": "foreclosure", "realtaxdeed": "tax_deed"}


def get_subdomain(county_slug, platform="realforeclose"):
    sale_type = PLATFORM_SALE_TYPE[platform]
    rows = rest_get("realauction_subdomains",
                     f"?select=subdomain,fqdn&county_slug=eq.{county_slug}&sale_type=eq.{sale_type}&platform=eq.{platform}&is_active=eq.true")
    if not rows:
        return None
    return rows[0]["fqdn"]


def main():
    if len(sys.argv) < 3:
        print("Usage: realauction_winner_harvest.py <county_slug> <YYYY-MM-DD> [--dry-run] [--platform=realforeclose|realtaxdeed]", file=sys.stderr)
        sys.exit(2)
    county = sys.argv[1]
    date_iso = sys.argv[2]
    dry_run = "--dry-run" in sys.argv
    platform_arg = next((a.split("=", 1)[1] for a in sys.argv[3:] if a.startswith("--platform=")), None)

    assert EMAIL and PW, "missing REALFORECLOSE_EMAIL/_PASSWORD"
    assert SB_URL and SB_KEY, "missing SUPABASE_URL/_SERVICE_ROLE_KEY"

    d = dt.date.fromisoformat(date_iso)
    date_mdY = d.strftime("%m/%d/%Y")

    # A county's sold lots on a given date can be foreclosure OR tax_deed
    # sales (observed: santa_rosa 2026-08-24 lots are tax_deed, not
    # foreclosure — the calendar shows zero foreclosure AIDs that day).
    # Try foreclosure first (the common case), fall back to tax_deed.
    platforms = [platform_arg] if platform_arg else ["realforeclose", "realtaxdeed"]
    fqdn = None
    for platform in platforms:
        fqdn = get_subdomain(county, platform)
        if fqdn:
            break
    if not fqdn:
        print(json.dumps({"county": county, "status": "NO_SUBDOMAIN"}))
        sys.exit(1)
    sale_type = PLATFORM_SALE_TYPE[platform]
    host = f"https://{fqdn}"

    sess = Session(host)
    ok, cal_url_or_err = login(sess)
    if not ok:
        print(json.dumps({"county": county, "status": "NEEDS_REGISTRATION", "detail": cal_url_or_err}))
        sys.exit(1)
    cal_url = cal_url_or_err

    daylist_url, aids = get_daylist(sess, cal_url, date_mdY)
    if not aids and not platform_arg and platform == "realforeclose":
        fqdn2 = get_subdomain(county, "realtaxdeed")
        if fqdn2:
            platform, sale_type, host = "realtaxdeed", "tax_deed", f"https://{fqdn2}"
            sess = Session(host)
            ok, cal_url_or_err = login(sess)
            if ok:
                cal_url = cal_url_or_err
                daylist_url, aids = get_daylist(sess, cal_url, date_mdY)
    if not aids:
        print(json.dumps({"county": county, "date": date_iso, "status": "NO_LOTS", "n_aids": 0}))
        return

    n_pages = (len(aids) + 9) // 10
    cases, status = load_all(sess, daylist_url, n_pages)

    results = []
    # Match by case_number+county+sale_type WITHOUT filtering on auction_date:
    # cases get re-noticed to new sale dates (observed: palm_beach case
    # 502025CA002397XXXAMB pre-existed with auction_date=2026-04-28 while the
    # actual sale happened 2026-08-24) — filtering on date would miss the
    # existing row and attempt a duplicate insert.
    mca_rows = rest_get("multi_county_auctions",
                         f"?select=id,case_number,sold_amount,winning_bidder,auction_date&county=eq.{county}"
                         f"&sale_type=eq.{sale_type}&case_number=not.is.null")
    by_case = {r["case_number"]: r for r in mca_rows if r.get("case_number")}

    for aid in aids:
        cd = cases.get(aid, {})
        st = status.get(aid, {})
        case_num = cd.get("case_number")
        a_label = st.get("A", "")
        b_field = st.get("B", "")
        row = {"aid": aid, "case_number": case_num}

        if b_field.startswith("Canceled per ") or b_field == "Redeemed":
            # e.g. "Canceled per Bankruptcy" / "Canceled per County" / "Canceled per Order" / "Redeemed"
            row["auction_status"] = re.sub(r"[^a-z0-9]+", "_", b_field.lower()).strip("_")
            row["sold"] = False
        elif a_label == "Auction Sold":
            row["auction_status"] = "sold"
            row["sold"] = True
            row["sold_to_raw"] = st.get("ST")
            row["sold_amount_quick"] = money(st.get("D"))
            row["sale_ts"] = b_field
            if st.get("SBH"):
                bh = get_bid_history(sess, daylist_url, aid)
                row.update(bh)
                time.sleep(2)
        else:
            row["auction_status"] = a_label or "unknown"
            row["sold"] = False

        results.append(row)

        if dry_run or not case_num:
            continue
        source_tag = f"realauction_bidhistory_modal:{county}:{date_iso}"
        patch = {"auction_status": row["auction_status"],
                 "case_id": row.get("case_id"),
                 "bidder_id": row.get("winner_bidder_id")}
        if row.get("sold"):
            patch["sold_amount"] = row.get("sold_amount") or row.get("sold_amount_quick")
            patch["sold_amount_source"] = source_tag
            if row.get("winner_name"):
                patch["winning_bidder"] = row["winner_name"]
                patch["winning_bidder_source"] = source_tag
            patch["tier1_buyer_type"] = row.get("winner_type")
            patch["bid_ladder"] = row.get("bid_ladder") or None
        patch = {k: v for k, v in patch.items() if v is not None}

        mca = by_case.get(case_num)
        try:
            if mca:
                if mca.get("auction_date") != date_iso:
                    patch["auction_date"] = date_iso  # case was re-noticed to this sale date
                rest_patch("multi_county_auctions", mca["id"], patch)
                mca_id = mca["id"]
            else:
                # No pre-existing row (common — the calendar-ingest scraper hadn't
                # captured this case yet). Insert one so the harvested winner data
                # has somewhere to land instead of being silently dropped.
                citystate = cd.get("city_state", "")
                m_zip = re.search(r"(\d{5})\s*$", citystate)
                m_city = re.match(r"^([^,]+),", citystate)
                insert_row = {
                    "county": county, "sale_type": sale_type, "auction_date": date_iso,
                    "case_number": case_num, "state": "FL", "source_platform": platform,
                    "data_source": "realauction_winner_harvest",
                    "parcel_id": cd.get("parcel_id") or None,
                    "property_address": cd.get("address") or None,
                    "city": m_city.group(1).strip() if m_city else None,
                    "zip": m_zip.group(1) if m_zip else None,
                    "judgment_amount": money(cd.get("judgment_amount")),
                    "assessed_value": money(cd.get("assessed_value")),
                    **patch,
                }
                insert_row = {k: v for k, v in insert_row.items() if v is not None}
                created = rest_post("multi_county_auctions", insert_row)
                mca_id = created[0]["id"]
            if row.get("sold"):
                rpc("upsert_auction_buyer_profile", {"p_mca_id": mca_id})
                record_verified_outcome(
                    sale_type, county, case_num, source_tag,
                    patch.get("sold_amount"),
                    (mca or {}).get("property_address") or cd.get("address"),
                    (mca or {}).get("parcel_id") or cd.get("parcel_id"),
                    date_iso)
        except Exception as e:
            row["persist_error"] = str(e)[:300]

    sold = [r for r in results if r.get("sold")]
    named = [r for r in sold if r.get("winner_name")]
    canceled = [r for r in results if r.get("auction_status", "").startswith("canceled")]
    print(json.dumps({
        "county": county, "date": date_iso, "platform": platform, "sale_type": sale_type,
        "n_lots": len(results),
        "n_sold": len(sold), "n_named": len(named), "n_canceled": len(canceled),
        "names": [{"case": r["case_number"], "name": r.get("winner_name"),
                   "type": r.get("winner_type"), "amount": r.get("sold_amount") or r.get("sold_amount_quick"),
                   "bidder_id": r.get("winner_bidder_id")} for r in sold],
    }, indent=2))


if __name__ == "__main__":
    main()
