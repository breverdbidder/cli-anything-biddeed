#!/usr/bin/env python3
"""Generalized county RealTDM public case-list sweep -> upsert_county_realtdm_mca RPC.

Supports any county hosted on the RealTDM platform (holmes, walton, santa_rosa, st_johns, etc.)
Decoded 2026-06-11 (Summit session). Public portal, no auth, not IP-blocked:
  POST https://<county>.realtdm.com/public/cases/list
  fields: filterPageNumber, filterFiltered=1, isPublic=1,
          filterSaleDateStart/Stop (MM/DD/YYYY), filterCasesPerPage (server caps ~20)
Cards: data-caseID, CASE #NNNNNN, status line, App Number, Parcel Number(=tax account),
       Sale Date, Surplus Balance, Date Created.

Captures per-case status + SURPLUS BALANCES (surplus-funds intel).
Usage: realtdm_county_sweep.py [MM/DD/YYYY start] [MM/DD/YYYY stop]
Defaults: 45 days back .. 60 days forward.
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, BASE_URL, COUNTY_SLUG.
"""
import sys, os, json, re, time, datetime as dt
import urllib.request, urllib.parse, http.cookiejar

BASE = os.environ.get("BASE_URL", "https://brevard.realtdm.com")
COUNTY = os.environ.get("COUNTY_SLUG", "brevard")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
assert SB_URL and SB_KEY, "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY env required"

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def req(url, data=None, retries=3):
    for a in range(retries):
        time.sleep(2.0 * (2 ** a if a else 1))
        try:
            r = urllib.request.Request(url, data=data.encode() if isinstance(data, str) else data)
            r.add_header("User-Agent", UA)
            if data:
                r.add_header("Content-Type", "application/x-www-form-urlencoded")
                r.add_header("Referer", BASE + "/public/cases/list")
            with op.open(r, timeout=60) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            sys.stderr.write(f"retry {a+1}: {e}\n")
            if a == retries - 1:
                raise

def rpc(fn, county, payload_list):
    body = json.dumps({"p_county": county, "p": payload_list}).encode()
    r = urllib.request.Request(f"{SB_URL}/rest/v1/rpc/{fn}", data=body, method="POST")
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=120) as resp:
        return resp.status

DATE_RE = re.compile(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4})")
MONTHS = {m: i+1 for i, m in enumerate(
    ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])}

def iso(d):
    m = DATE_RE.search(d or "")
    if not m:
        return None
    return f"{m.group(3)}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}"

def parse_cards(html):
    out = []
    # each card: content-box ... data-caseID="N" ... CASE #X ... status ... labeled rows
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

if __name__ == "__main__":
    today = dt.date.today()
    start = sys.argv[1] if len(sys.argv) > 2 and sys.argv[1] else \
        (today - dt.timedelta(days=45)).strftime("%m/%d/%Y")
    stop = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else \
        (today + dt.timedelta(days=60)).strftime("%m/%d/%Y")
    print(f"county={COUNTY} base={BASE} range={start}..{stop}")
    req(BASE + "/public/cases/list")  # session
    page, written, seen = 1, 0, set()
    while page <= 60:
        body = urllib.parse.urlencode({
            "filterPageNumber": page, "filterFiltered": 1, "isPublic": 1,
            "sectionRouteCode": "", "filtercasestatus": "", "filterPartyName": "",
            "filterCaseNumber": "", "filterParcelNumber": "", "filterAppNumber": "",
            "filterCertNumber": "", "filterPropAddress": "",
            "filterSaleDateStart": start, "filterSaleDateStop": stop,
            "filterBalanceType": "", "filterCasesPerPage": 100,
        })
        cards = parse_cards(req(BASE + "/public/cases/list", data=body))
        new = [c for c in cards if c["case_number"] not in seen]
        if not new:
            break
        seen.update(c["case_number"] for c in new)
        rpc("upsert_county_realtdm_mca", COUNTY, new)
        written += len(new)
        print(f"page {page}: {len(new)} cases")
        page += 1
    print(f"done: {written} cases ({start}..{stop})")
