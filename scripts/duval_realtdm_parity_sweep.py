#!/usr/bin/env python3
"""Duval RealTDM public case-list sweep → duval_realtdm_raw staging table.

Scrapes duval.realtdm.com (or BASE_URL env override) with an extended date
range to capture historical cases needed for C/D parity.  Calls the
upsert_duval_realtdm_raw RPC, which populates the staging table used by
refresh_duval_parity_v1() to set parity_source='tier1_realtdm_duval'.

Usage:
    duval_realtdm_parity_sweep.py [MM/DD/YYYY start] [MM/DD/YYYY stop]
Defaults: 3 years back .. 1 year forward (catches all historical TD cases).

Env:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
    BASE_URL   — override RealTDM endpoint (default https://duval.realtdm.com)
    COUNTY_SLUG — override county slug (default duval)
"""
import sys, os, json, re, time, datetime as dt
import urllib.request, urllib.parse, http.cookiejar

BASE   = os.environ.get("BASE_URL", "https://duval.realtdm.com")
COUNTY = os.environ.get("COUNTY_SLUG", "duval")
UA     = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
assert SB_URL and SB_KEY, "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY env required"

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def req(url, data=None, retries=3):
    for a in range(retries):
        delay = 2.0 * (2 ** a if a else 1)
        time.sleep(delay)
        try:
            r = urllib.request.Request(
                url,
                data=data.encode() if isinstance(data, str) else data,
            )
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


def rpc(fn, payload):
    body = json.dumps({"p": payload}).encode()
    r = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=body, method="POST"
    )
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=120) as resp:
        return resp.status


DATE_RE = re.compile(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4})")
MONTHS  = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
)}


def iso(d):
    m = DATE_RE.search(d or "")
    if not m:
        return None
    return f"{m.group(3)}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}"


def parse_cards(html):
    out = []
    for blk in re.split(r'class="content-box contain', html)[1:]:
        cid    = re.search(r'data-caseID="(\d+)"', blk)
        case   = re.search(r'CASE #(\w+)', blk)
        status = re.search(r'opacity-75">([^<]+)<', blk)
        labels = dict(re.findall(
            r'data-label">([^<]+)</div>\s*<div class="data-value[^"]*">([^<]*)<', blk
        ))
        if not case:
            continue
        sb = (labels.get("Surplus Balance") or "").replace("$", "").replace(",", "").strip()
        out.append({
            "case_number":    case.group(1),
            "tdm_case_id":    cid.group(1) if cid else None,
            "case_status":    (status.group(1).strip() if status else None),
            "sale_date":      iso(labels.get("Sale Date")),
            "surplus_balance": sb if sb else None,
        })
    return out


def probe_endpoint():
    """Verify the RealTDM endpoint is reachable. Returns True on success."""
    try:
        html = req(BASE + "/public/cases/list")
        return bool(html and len(html) > 200)
    except Exception as e:
        sys.stderr.write(f"Endpoint probe failed: {e}\n")
        return False


if __name__ == "__main__":
    today = dt.date.today()
    # Wide range: 3 years back → 1 year forward to capture all historical cases
    default_start = (today - dt.timedelta(days=365 * 3)).strftime("%m/%d/%Y")
    default_stop  = (today + dt.timedelta(days=365)).strftime("%m/%d/%Y")

    start = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else default_start
    stop  = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else default_stop

    print(f"county={COUNTY} base={BASE} range={start}..{stop}")

    if not probe_endpoint():
        print(f"WARNING: {BASE} unreachable or returned empty. Exiting with 0 "
              "so downstream parity refresh still runs against realforeclose_aids.")
        sys.exit(0)

    req(BASE + "/public/cases/list")  # establish session cookie
    page, written, seen = 1, 0, set()

    while page <= 100:  # wider cap than generic sweep (more history)
        body = urllib.parse.urlencode({
            "filterPageNumber":    page,
            "filterFiltered":      1,
            "isPublic":            1,
            "sectionRouteCode":    "",
            "filtercasestatus":    "",
            "filterPartyName":     "",
            "filterCaseNumber":    "",
            "filterParcelNumber":  "",
            "filterAppNumber":     "",
            "filterCertNumber":    "",
            "filterPropAddress":   "",
            "filterSaleDateStart": start,
            "filterSaleDateStop":  stop,
            "filterBalanceType":   "",
            "filterCasesPerPage":  100,
        })
        cards = parse_cards(req(BASE + "/public/cases/list", data=body))
        new   = [c for c in cards if c["case_number"] not in seen]
        if not new:
            print(f"page {page}: empty — done")
            break
        seen.update(c["case_number"] for c in new)
        status = rpc("upsert_duval_realtdm_raw", new)
        written += len(new)
        print(f"page {page}: {len(new)} cases  (upsert HTTP {status})")
        page += 1

    print(f"done: {written} cases written to duval_realtdm_raw ({start}..{stop})")
