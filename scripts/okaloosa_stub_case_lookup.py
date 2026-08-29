#!/usr/bin/env python3
"""One-off: recover parcel_id/address/judgment/assessed for 6 Okaloosa stub
rows (Gold Standard shard9 dispatch f8de10ec, E/C/D/I fix).

Reuses the proven login + FNC=LOAD/FNC=UPDATE pairing from
scripts/realauction_winner_harvest.py (2026-08-25 reverse-engineered flow).
Read-only: prints matched case data as JSON, does not write to Supabase.

Usage: okaloosa_stub_case_lookup.py <platform:realforeclose|realtaxdeed> <MM/DD/YYYY> <case1,case2,...>
"""
import sys
import os
import re
import json
import time
import urllib.request
import urllib.parse
import http.cookiejar

EMAIL = os.environ.get("REALFORECLOSE_EMAIL", "")
PW = os.environ.get("REALFORECLOSE_PASSWORD", "")
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
    for _ in range(10):
        cal_html = sess.get(cal_url, referer=home)
        m = re.search(r'id="NOTICEMSG"[^>]*NID="(\d+)"', cal_html)
        if not m:
            break
        nid = m.group(1)
        sess.post(home, {"zaction": "AJAX", "zmethod": "COM", "process": "NOTICE",
                          "func": "ACCEPT", "NID": nid}, referer=cal_url)
    return True, cal_url


def get_daylist(sess, cal_url, date_mdY):
    url = sess.host + f"/index.cfm?zaction=AUCTION&Zmethod=DAYLIST&AUCTIONDATE={date_mdY}"
    html = sess.get(url, referer=cal_url)
    m = re.search(r'id="ALB"[^>]*>([\d,]*)<', html)
    aids = [a for a in (m.group(1) if m else "").split(",") if a]
    return url, aids, html


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


def load_all(sess, daylist_url, n_pages_hint=40):
    cases, status = {}, {}
    pagedir = 0
    prev_rlist = None
    for i in range(n_pages_hint + 2):
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
        time.sleep(1.0)

        tx2 = int(time.time() * 1000)
        upd_url = sess.host + f"/index.cfm?zaction=AUCTION&ZMETHOD=UPDATE&FNC=UPDATE&ref={rlist}&tx={tx2}"
        ubody = sess.get(upd_url, referer=daylist_url)
        um = re.search(r'\{"PC".*\}\s*$', ubody, re.S)
        if um:
            uj = json.loads(um.group(0))
            for item in uj.get("ADATA", {}).get("AITEM", []):
                status[item["AID"]] = item
        pagedir = 1
        time.sleep(1.2)
    return cases, status


def main():
    if len(sys.argv) < 4:
        print("Usage: okaloosa_stub_case_lookup.py <realforeclose|realtaxdeed> <MM/DD/YYYY> <case1,case2,...>", file=sys.stderr)
        sys.exit(2)
    platform = sys.argv[1]
    date_mdY = sys.argv[2]
    wanted = set(sys.argv[3].split(","))
    assert EMAIL and PW, "missing REALFORECLOSE_EMAIL/_PASSWORD"

    host = f"https://okaloosa.{platform}.com"
    sess = Session(host)
    ok, cal_url_or_err = login(sess)
    if not ok:
        print(json.dumps({"status": "LOGIN_FAILED", "detail": cal_url_or_err}))
        sys.exit(1)
    cal_url = cal_url_or_err

    daylist_url, aids, daylist_html = get_daylist(sess, cal_url, date_mdY)
    print(json.dumps({"status": "DAYLIST_OK", "date": date_mdY, "n_aids": len(aids)}), file=sys.stderr)
    if not aids:
        print(json.dumps({"status": "NO_LOTS", "date": date_mdY}))
        return

    n_pages_hint = (len(aids) // 10) + 1
    cases, status = load_all(sess, daylist_url, n_pages_hint)

    matched = {}
    for aid, c in cases.items():
        cn = c["case_number"]
        for w in wanted:
            if w in cn or cn in w:
                matched[w] = {**c, "aid": aid, "status": status.get(aid)}

    print(json.dumps({
        "status": "DONE",
        "date": date_mdY,
        "n_aids": len(aids),
        "n_cases_loaded": len(cases),
        "matched": matched,
        "unmatched_wanted": sorted(wanted - set(matched.keys())),
    }, indent=2))


if __name__ == "__main__":
    main()
