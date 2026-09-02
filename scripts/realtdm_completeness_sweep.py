#!/usr/bin/env python3
"""Issue #19720 Phase 3 — RealTDM completeness sweep, one county at a time.

RealTDM ({county}.realtdm.com/public/cases/list) is a PUBLIC, unauthenticated
case-search portal (confirmed live 2026-09-02, no login form, no IP block from
this runner) -- unlike realforeclose.com/realtaxdeed.com it needs no
REALFORECLOSE_EMAIL/_PASSWORD. It is the tax-deed FILE system: scheduled sale,
case_status (ACTIVE - SOLD BIDDER / COMPLETED - REDEEMED / etc), surplus.

Writes one public.harvest_runs row per county via upsert_county_realtdm_mca's
caller (this script), sequential, with backoff between counties per the
intent's throttle-safe mandate even though this platform has no known lockout.

Usage: python3 scripts/realtdm_completeness_sweep.py [county_slug ...]
  (no args = sweep the DEFAULT_COUNTIES list below)
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
from __future__ import annotations
import sys, os, json, re, time, datetime as dt
import urllib.request, urllib.parse, http.cookiejar

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# county_slug -> realtdm subdomain, per public.realauction_subdomains sale_type='tdm'
SUBDOMAINS = {
    "brevard": "brevard", "highlands": "highlands", "sarasota": "sarasota",
    "washington": "washington", "polk": "polk", "seminole": "seminole",
    "miami_dade": "miamidade", "hillsborough": "hillsborough", "lee": "lee",
    "marion": "marion", "palm_beach": "palmbeach", "pasco": "pasco",
}
DEFAULT_COUNTIES = list(SUBDOMAINS.keys())

DATE_RE = re.compile(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4})")
MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def iso(d):
    m = DATE_RE.search(d or "")
    return f"{m.group(3)}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}" if m else None


def parse_cards(html):
    out = []
    for blk in re.split(r'class="content-box contain', html)[1:]:
        cid = re.search(r'data-caseID="(\d+)"', blk)
        case = re.search(r'CASE #([^<]+)<', blk)
        status = re.search(r'opacity-75">([^<]+)<', blk)
        labels = dict(re.findall(
            r'data-label">([^<]+)</div>\s*<div class="data-value[^"]*">([^<]*)<', blk))
        if not case:
            continue
        sb = (labels.get("Surplus Balance") or "").replace("$", "").replace(",", "").strip()
        out.append({
            "case_number": case.group(1).strip(),
            "tdm_case_id": cid.group(1) if cid else None,
            "account_number": (labels.get("Parcel Number") or "").strip() or None,
            "app_number": (labels.get("App Number") or "").strip() or None,
            "case_status": (status.group(1).strip() if status else None),
            "sale_date": iso(labels.get("Sale Date")),
            "surplus_balance": sb if sb else None,
            "date_created": iso(labels.get("Date Created")),
        })
    return out


def rpc(fn, payload):
    r = urllib.request.Request(f"{SB_URL}/rest/v1/rpc/{fn}",
                                data=json.dumps(payload).encode(), method="POST")
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=120) as resp:
        return resp.status


def insert_harvest_run(county, platform, mechanism, started_at, finished_at,
                        login_ok, scheduled, with_result, rows_written, error):
    body = {
        "mechanism": mechanism, "provider": "scripts/realtdm_completeness_sweep.py",
        "county": county, "platform": platform, "started_at": started_at,
        "finished_at": finished_at, "login_ok": login_ok, "scheduled": scheduled,
        "with_result": with_result, "rows_written": rows_written, "error": error,
    }
    r = urllib.request.Request(f"{SB_URL}/rest/v1/harvest_runs",
                                data=json.dumps(body).encode(), method="POST")
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    r.add_header("Content-Type", "application/json")
    r.add_header("Prefer", "return=minimal")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return resp.status


def sweep_county(county):
    sub = SUBDOMAINS[county]
    base = f"https://{sub}.realtdm.com"
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    def req(url, data=None):
        r = urllib.request.Request(url, data=data.encode() if isinstance(data, str) else data)
        r.add_header("User-Agent", UA)
        if data:
            r.add_header("Content-Type", "application/x-www-form-urlencoded")
            r.add_header("Referer", base + "/public/cases/list")
        with op.open(r, timeout=45) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")

    login_ok, cards, written, err = False, [], 0, None
    try:
        s, _ = req(base + "/public/cases/list")
        login_ok = (s == 200)
        today = dt.date.today()
        start = (today - dt.timedelta(days=45)).strftime("%m/%d/%Y")
        stop = (today + dt.timedelta(days=60)).strftime("%m/%d/%Y")
        page, seen = 1, set()
        while page <= 60:
            body = urllib.parse.urlencode({
                "filterPageNumber": page, "filterFiltered": 1, "isPublic": 1,
                "sectionRouteCode": "", "filtercasestatus": "", "filterPartyName": "",
                "filterCaseNumber": "", "filterParcelNumber": "", "filterAppNumber": "",
                "filterCertNumber": "", "filterPropAddress": "",
                "filterSaleDateStart": start, "filterSaleDateStop": stop,
                "filterBalanceType": "", "filterCasesPerPage": 100,
            })
            _, html = req(base + "/public/cases/list", data=body)
            page_cards = parse_cards(html)
            new = [c for c in page_cards if c["case_number"] not in seen]
            if not new:
                break
            seen.update(c["case_number"] for c in new)
            cards.extend(new)
            page += 1
            time.sleep(1.5)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"

    if login_ok and cards and not err:
        try:
            rpc("upsert_county_realtdm_mca", {"p_county": county, "p": cards})
            written = len(cards)
        except Exception as e:
            err = f"rpc failed: {type(e).__name__}: {e}"

    with_result = sum(1 for c in cards if c["case_status"] and
                       ("REDEEM" in c["case_status"] or "SOLD" in c["case_status"]
                        or "CANCEL" in c["case_status"]))
    finished = dt.datetime.now(dt.timezone.utc).isoformat()
    insert_harvest_run(
        county=county, platform="realtdm", mechanism="realtdm_public_portal",
        started_at=started, finished_at=finished, login_ok=login_ok,
        scheduled=len(cards), with_result=with_result, rows_written=written, error=err,
    )
    status = "FATAL" if not login_ok else ("ERROR" if err else "OK")
    print(f"{county}: {status} cards={len(cards)} written={written} err={err}")
    return status == "OK"


if __name__ == "__main__":
    counties = sys.argv[1:] or DEFAULT_COUNTIES
    ok, failed = 0, 0
    for c in counties:
        if c not in SUBDOMAINS:
            print(f"{c}: SKIP (no known realtdm subdomain)")
            continue
        if sweep_county(c):
            ok += 1
        else:
            failed += 1
        time.sleep(3)
    print(f"done: {ok} ok, {failed} failed/fatal, {len(counties)} attempted")
