#!/usr/bin/env python3
"""Brevard AcclaimWeb CT sweep -> public.foreclosure_outcomes (+ pipeline staging).

Decoded 2026-06-11 (Summit session). Flow:
  GET  /AcclaimWeb/                                   -> session cookie
  POST /AcclaimWeb/search/Disclaimer  disclaimer=on   -> accept
  POST /AcclaimWeb/search/SearchTypeDocType?Length=6  -> criteria in session
       DocTypes=79 (CERTIFICATE OF TITLE), dates M/D/YYYY
  POST /AcclaimWeb/search/GridResults page=&size=     -> {"data":[...],"total":N}

Row fields: CaseNumber (real 05-YYYY-CA/CC format), Consideration (winning bid),
DirectName (grantor), IndirectName (grantee/winner), RecordDate (epoch ms),
InstrumentNumber, TransactionItemId, DocLegalDescription.

D1 note: CT carries RECORDING date, not sale date. data_source is suffixed
'_recdate' so it is never mistaken for a verified sale date (Honesty V3).

Hard rules: single session, ~2.5s throttle, exponential backoff, stop on
persistent block (never rotate IPs / never parallelize).

Usage: acclaim_ct_sweep.py [YYYY-MM] [YYYY-MM]
Defaults to previous month .. current month (forward top-up mode).

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (required).
"""
import sys, os, json, re, time, calendar, datetime as dt
import urllib.request, urllib.parse, http.cookiejar

BASE = "http://vaclmweb1.brevardclerk.us"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
THROTTLE = 2.5
DATA_SOURCE = "brevard_acclaim_ct_recdate"

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
assert SB_URL and SB_KEY, "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY env required"

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def req(url, data=None, hdrs=None, retries=4):
    for attempt in range(retries):
        time.sleep(THROTTLE * (2 ** attempt if attempt else 1))
        try:
            r = urllib.request.Request(url, data=data.encode() if isinstance(data, str) else data)
            r.add_header("User-Agent", UA)
            for k, v in (hdrs or {}).items():
                r.add_header(k, v)
            with op.open(r, timeout=60) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            sys.stderr.write(f"retry {attempt+1}/{retries}: {e}\n")
            if attempt == retries - 1:
                raise
    return None

def sb(path, payload, params="", profile=None):
    body = json.dumps(payload).encode()
    r = urllib.request.Request(f"{SB_URL}/rest/v1/{path}{params}", data=body, method="POST")
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    r.add_header("Content-Type", "application/json")
    r.add_header("Prefer", "resolution=merge-duplicates,return=minimal")
    if profile:
        r.add_header("Content-Profile", profile)
    with urllib.request.urlopen(r, timeout=120) as resp:
        return resp.status

def sb_pipeline(path, payload, params=""):
    """Best-effort write to pipeline schema (non-fatal if not exposed via PostgREST)."""
    try:
        return sb(path, payload, params, profile="pipeline")
    except Exception as e:
        print(f"pipeline write skipped ({path}): {e}", file=sys.stderr)
        return None

def session_init():
    req(BASE + "/AcclaimWeb/")
    req(BASE + "/AcclaimWeb/search/Disclaimer", data="disclaimer=on",
        hdrs={"Content-Type": "application/x-www-form-urlencoded",
              "Referer": BASE + "/AcclaimWeb/"})

def month_rows(y, m):
    last = calendar.monthrange(y, m)[1]
    payload = urllib.parse.urlencode({
        "DocTypes": "79",
        "DocTypesDisplay-input": "CERTIFICATE OF TITLE (CT)",
        "DocTypesDisplay": "CERTIFICATE OF TITLE (CT)",
        "DateRangeList": " ",
        "RecordDateFrom": f"{m}/1/{y}",
        "RecordDateTo": f"{m}/{last}/{y}",
    })
    h = {"Content-Type": "application/x-www-form-urlencoded",
         "X-Requested-With": "XMLHttpRequest",
         "Referer": BASE + "/AcclaimWeb/search/SearchTypeDocType"}
    body = req(BASE + "/AcclaimWeb/search/SearchTypeDocType?Length=6", data=payload, hdrs=h)
    if "Error.htm" in (body or ""):
        raise RuntimeError(f"criteria POST error {y}-{m:02d}")
    rows, page = [], 1
    while True:
        d = json.loads(req(BASE + "/AcclaimWeb/search/GridResults",
                           data=f"page={page}&size=200", hdrs=h))
        rows += d["data"]
        if len(rows) >= d["total"] or not d["data"]:
            return rows, d["total"]
        page += 1

def transform(r):
    ms = int(re.search(r"-?\d+", r["RecordDate"]).group())
    rec_date = dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date().isoformat()
    cg = (r.get("CompressedDirectName") or "").upper()
    ce = (r.get("CompressedIndirectName") or "").upper()
    pl = bool(cg and ce and (cg == ce or cg in ce or ce in cg))
    cons = r.get("Consideration")
    return {
        "case_number": (r.get("CaseNumber") or f"INSTR-{r.get('InstrumentNumber')}").strip(),
        "county": "brevard", "sale_type": "foreclosure",
        "auction_date": rec_date,
        "outcome": "struck_to_plaintiff" if pl else "sold",
        "winner_type": "plaintiff" if pl else "third_party",
        "winner_name": (r.get("IndirectName") or "").strip() or None,
        "winning_bid": float(cons) if cons not in (None, "") else None,
        "plaintiff_raw": (r.get("DirectName") or "").strip() or None,
        "data_source": DATA_SOURCE,
        "source_url": f"{BASE}/AcclaimWeb/Details/?docId={r.get('TransactionItemId')}&insNm={r.get('InstrumentNumber')}",
        "enriched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }, {
        "instrument": str(r.get("InstrumentNumber") or ""),
        "rec": {"case_number": (r.get("CaseNumber") or "").strip(),
                "legal": (r.get("DocLegalDescription") or "")[:500],
                "rec_date": rec_date,
                "winner": (r.get("IndirectName") or "").strip(),
                "grantor": (r.get("DirectName") or "").strip(),
                "consideration": cons},
    }

def months_between(a, b):
    y, m = a
    while (y, m) <= b:
        yield y, m
        m += 1
        if m > 12:
            y, m = y + 1, 1

if __name__ == "__main__":
    today = dt.date.today()
    prev = (today.replace(day=1) - dt.timedelta(days=1))
    start = sys.argv[1] if len(sys.argv) > 2 and sys.argv[1] else f"{prev.year}-{prev.month:02d}"
    end = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else f"{today.year}-{today.month:02d}"
    sy, sm = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    session_init()
    failures = 0
    for y, m in months_between((sy, sm), (ey, em)):
        month = f"{y}-{m:02d}-01"
        try:
            rows, total = month_rows(y, m)
            pub, raw, seen = [], [], set()
            for r in rows:
                p, s = transform(r)
                k = (p["case_number"], p["auction_date"])
                if k in seen or not s["instrument"]:
                    continue
                seen.add(k)
                s["month_start"] = month
                pub.append(p)
                raw.append(s)
            if pub:
                sb("foreclosure_outcomes", pub,
                   "?on_conflict=case_number,county,auction_date")
                sb_pipeline("brevard_fc_acclaim_raw", raw, "?on_conflict=instrument")
            sb_pipeline("brevard_fc_acclaim_progress",
               [{"month_start": month, "status": "done", "rows_found": total,
                 "rows_written": len(pub),
                 "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                 "note": "gha scrape-brevard-acclaim-ct"}],
               "?on_conflict=month_start")
            print(f"{month}: total={total} written={len(pub)}")
        except Exception as e:
            failures += 1
            print(f"{month}: ERROR {e}", file=sys.stderr)
            try:
                sb_pipeline("brevard_fc_acclaim_progress",
                   [{"month_start": month, "status": "error", "note": str(e)[:300]}],
                   "?on_conflict=month_start")
            except Exception:
                pass
    sys.exit(1 if failures else 0)
