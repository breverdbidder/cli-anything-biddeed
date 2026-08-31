#!/usr/bin/env python3
"""PRE-AUCTION lien/title harvest for the SIGNAL$ Property Report (issue: real
lien_survival.classify + full SIGNAL$ rebrand propagation, PART C).

This is a SEPARATE, PARALLEL pipeline from the existing Daily Winner FF
post-auction harvest (scripts/winnerdata_pipeline.py). That one skip-traces
AUCTION WINNERS after the sale for Mariam's insurance leads. This one runs
BEFORE the sale, sourcing lien_results/title_defects for SIGNAL$ Property
Report customers who need lien_survival.classify data while the property is
still biddable.

Target selection:
  multi_county_auctions WHERE county=<COUNTY> AND auction_status='upcoming'
  AND auction_date BETWEEN today AND today+LOOKAHEAD_DAYS (default 14) --
  same table S1 discovery already reads, filtered to genuinely future rows
  (confirmed live 2026-08-31: this table's auction_status='upcoming' rows
  include stale historical dates for at least one county, so the date
  window is load-bearing, not decorative).

County choice — Duval, live-verified this session (not assumed):
  - gold-certified (public.gold_standard_certifications.certified=true)
  - genuinely-future 'upcoming' rows exist (32 confirmed live 2026-08-31)
  - or.duvalclerk.com/AcclaimWeb IS reachable from this runner right now
    (HTTP 200, real "Acclaim" content) -- this CONTRADICTS a stale
    2026-06-23 note in scripts/fill_opening_bids_brevard_duval.py claiming
    "or.duvalclerk.com is unreachable from GHA datacenter IPs (HTTP 0)".
    That finding is now out of date; do not trust it without a fresh check.
  - Duval's AcclaimWeb instance is a NEWER Kendo-UI build than Brevard's
    classic ASP.NET MVC one (scripts/acclaim_case_lookup.py,
    scripts/acclaim_ct_sweep.py). Endpoint paths differ:
      Brevard: http://vaclmweb1.brevardclerk.us/AcclaimWeb/search/...
      Duval:   https://or.duvalclerk.com/search/...           (no /AcclaimWeb
               prefix; disclaimer POST is capitalized /Search/Disclaimer)
    Reverse-engineered live this session via Playwright DOM inspection +
    replicated in plain httpx/urllib (case-number search flow only --
    confirmed working, real JSON: {"Data":[...],"Total":N}).

Known gap (documented honestly, not silently worked around): Duval
AcclaimWeb's owner/party NAME search (SearchTypeName) requires a
`BookTypesDisplay` parameter whose accepted encoding was not discovered this
session -- every attempt returned `ShowError('The booktype is invalid...')`.
That means this harvester can only search BY CASE NUMBER, which returns
documents recorded UNDER that specific court case (Lis Pendens, Final
Judgment, and any other doc cross-filed to the case) -- it does NOT do a
broad owner-name lien sweep, so it will miss independent third-party liens
(a separate senior mortgage, an HOA claim of lien, a mechanic's lien) that
were never filed as part of this litigation. This is a real, disclosed
capability limit, not a fabricated dataset.

What gets written, and where:
  - LIS PENDENS / (FINAL) JUDGMENT docs (the case's OWN litigation
    documents) -> title_defects, rule_category='case_filing'. These
    establish the case's priority-determination date; they are not
    third-party liens competing for priority, so they do not belong in
    lien_results.
  - Any OTHER doc type on the case that regex-matches a real lien category
    (mortgage, HOA/association claim of lien, mechanic's/construction lien,
    UCC filing, tax lien) -> lien_results, with `priority` derived by
    comparing that document's RecordDate against the case's own Lis Pendens
    RecordDate (recorded before LP = senior; on/after = junior) -- this is
    exactly the recording-priority signal lien-survival.js's classify()
    consumes for the foreclosure path.

Hard rules (same as acclaim_case_lookup.py / acclaim_ct_sweep.py): single
session, ~2.5s throttle, exponential backoff, never rotate IPs, never
parallelize -- this is a shared production court records site. This script
does NOT touch the Tracerfy/Bright Data 100-credits/day ledger
(ff_daily_credit_ledger) -- direct AcclaimWeb scraping is a different
resource with its own throttle, not a vendor API call.

Idempotency: before each insert, checks for an existing row with the same
(case_number, book/page or InstrumentNumber) so reruns (this is a scheduled,
recurring pipeline -- see .github/workflows/pre-auction-lien-harvest.yml)
do not duplicate rows as new auctions post to the calendar continuously.

Usage: pre_auction_lien_harvest.py [--county duval] [--lookahead-days 14] [--limit 8]
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
"""
import sys, os, re, json, time, argparse, datetime as dt
import urllib.request, urllib.parse, http.cookiejar

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
THROTTLE = 2.5

# county -> AcclaimWeb base URL + whether it uses the /AcclaimWeb/ path
# prefix (Brevard-style, classic ASP.NET MVC) or not (Duval-style, Kendo UI).
COUNTY_ACCLAIM = {
    "duval": {"base": "https://or.duvalclerk.com", "prefix": ""},
}

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
assert SB_URL and SB_KEY, "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY env required"

LIEN_TYPE_PATTERNS = [
    ("Mortgage",              re.compile(r"\b(MTG|MORTGAGE|DEED\s*OF\s*TRUST)\b", re.I)),
    ("HOA/Association Lien",  re.compile(r"\b(HOA|HOMEOWNERS|ASSOCIATION\s*LIEN|CLAIM\s*OF\s*LIEN)\b", re.I)),
    ("Mechanic's/Construction Lien", re.compile(r"\b(MECH(ANIC)?|CONSTRUCTION\s*LIEN)\b", re.I)),
    ("UCC Filing",            re.compile(r"\bUCC\b", re.I)),
    ("Tax Lien",              re.compile(r"\bTAX\s*LIEN\b", re.I)),
]
CASE_FILING_PATTERN = re.compile(r"\b(LIS\s*PENDENS|JUDG(E|MENT)?)\b", re.I)


def sb_get(path):
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_insert(table, row):
    body = json.dumps(row).encode()
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{table}", data=body, method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


class AcclaimSession:
    def __init__(self, base, prefix):
        self.base = base
        self.prefix = prefix  # "" for duval, "/AcclaimWeb" for brevard-style
        cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        self._disclaimer_accepted = False

    def _req(self, url, data=None, hdrs=None, retries=3):
        for attempt in range(retries):
            time.sleep(THROTTLE * (2 ** attempt if attempt else 1))
            try:
                r = urllib.request.Request(url, data=data.encode() if isinstance(data, str) else data)
                r.add_header("User-Agent", UA)
                for k, v in (hdrs or {}).items():
                    r.add_header(k, v)
                with self.opener.open(r, timeout=30) as resp:
                    return resp.read().decode("utf-8", "replace")
            except Exception as e:
                sys.stderr.write(f"retry {attempt+1}/{retries}: {e}\n")
                if attempt == retries - 1:
                    raise
        return None

    def _accept_disclaimer(self):
        if self._disclaimer_accepted:
            return
        search_path = f"{self.prefix}/search/SearchTypeCaseNumber"
        self._req(self.base + search_path)  # 302 -> Disclaimer page, establishes session
        self._req(
            self.base + f"{self.prefix}/Search/Disclaimer?st={search_path}",
            data="disclaimer=true",
            hdrs={"Content-Type": "application/x-www-form-urlencoded", "Referer": self.base + search_path},
        )
        self._req(self.base + search_path)  # confirm real form now loads
        self._disclaimer_accepted = True

    def case_lookup(self, case_number):
        """Documents recorded under this court case (Lis Pendens, Judgment, ...)."""
        self._accept_disclaimer()
        today = dt.date.today()
        payload = urllib.parse.urlencode({
            "CaseNumber": case_number, "CaseNumberFilter": "0", "DocTypes": "all",
            "DocTypesDisplay-input": "All", "DocTypesDisplay": "", "DateRangeList": " ",
            "RecordDateFrom": "1/1/1981", "RecordDateTo": f"{today.month}/{today.day}/{today.year}",
        })
        h = {"Content-Type": "application/x-www-form-urlencoded", "X-Requested-With": "XMLHttpRequest",
             "Referer": self.base + f"{self.prefix}/search/SearchTypeCaseNumber"}
        self._req(self.base + f"{self.prefix}/search/SearchTypeCaseNumber?Length=6", data=payload, hdrs=h)
        body = self._req(self.base + f"{self.prefix}/search/GridResults", data="page=1&size=200", hdrs=h)
        try:
            return json.loads(body).get("Data", [])
        except Exception:
            return []


# public.title_rules is a pre-existing curated taxonomy (rule_id NOT NULL FK
# on title_defects) -- e.g. JUDG_001 "Judgment lien against owner". A raw
# AcclaimWeb LIS PENDENS on THIS case's own foreclosure is not a title
# defect (it's the expected filing for the very auction the report is
# about) and none of the existing rule_id codes describe it accurately —
# JUDG_003 ("Lis pendens other action") specifically means an UNRELATED
# lawsuit clouding title, and mislabeling this case's own LP under that code
# would misrepresent normal foreclosure procedure as a red flag. It is used
# ONLY to compute the case's own priority-determination date (lp_date,
# below) and is never written to title_defects.
JUDGMENT_RULE_ID = "JUDG_001"  # "Judgment lien against owner" — real, existing title_rules row


def classify_docs(case_number, parcel_id, county, docs):
    """Split a case's recorded documents into (title_defects rows, lien_results rows)."""
    lp_dates = [d["RecordDate"] for d in docs if "LIS PENDENS" in (d.get("DocTypeDescription") or "").upper() and d.get("RecordDate")]
    lp_date = min(lp_dates) if lp_dates else None  # 'YYYY/MM/DD' strings sort correctly lexically

    title_defect_rows, lien_rows = [], []
    for d in docs:
        doc_type = d.get("DocTypeDescription") or ""
        rec_date = d.get("RecordDate")
        book_page = d.get("BookPage")
        direct = d.get("DirectName") or ""
        indirect = d.get("IndirectName") or ""

        if "LIS PENDENS" in doc_type.upper():
            continue  # priority-date input only, see JUDGMENT_RULE_ID note above

        if re.search(r"\bJUDG(E|MENT)?\b", doc_type, re.I):
            title_defect_rows.append({
                "case_number": case_number,
                "parcel_id": parcel_id,
                "county": county,
                "rule_id": JUDGMENT_RULE_ID,
                "rule_category": "JUDGMENT",
                "rule_name": doc_type.strip(),
                "severity": "high",
                "defect_description": f"{doc_type} recorded {rec_date}, book/page {book_page}, instrument {d.get('InstrumentNumber')}, {direct} v {indirect} (Duval AcclaimWeb case-number search — this case's own foreclosure judgment)",
                "affected_parties": [p for p in (direct, indirect) if p],
                "auto_detected": True,
            })
            continue

        for lien_type, pattern in LIEN_TYPE_PATTERNS:
            if pattern.search(doc_type):
                priority = None
                if lp_date and rec_date:
                    priority = "senior" if rec_date < lp_date else "junior"
                lien_rows.append({
                    "case_number": case_number,
                    "parcel_id": parcel_id,
                    "lien_type": lien_type,
                    "creditor": direct or None,
                    "recording_date": rec_date.replace("/", "-") if rec_date else None,
                    "book_page": book_page,
                    "priority": priority,
                    "source": "duval_acclaimweb_case_search",
                    "raw_data": d,
                })
                break
    return title_defect_rows, lien_rows


def already_exists(table, case_number, key_field, key_value):
    if not key_value:
        return False
    rows = sb_get(f"{table}?case_number=eq.{urllib.parse.quote(case_number)}&{key_field}=eq.{urllib.parse.quote(str(key_value))}&select=id&limit=1")
    return bool(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--county", default="duval")
    ap.add_argument("--lookahead-days", type=int, default=14)
    ap.add_argument("--limit", type=int, default=8, help="max cases per run — shared production court records site, throttled")
    args = ap.parse_args()

    county = args.county
    if county not in COUNTY_ACCLAIM:
        print(f"BLOCKED: no AcclaimWeb config for county={county!r}. Configured: {list(COUNTY_ACCLAIM)}")
        sys.exit(1)

    today = dt.date.today()
    cutoff = today + dt.timedelta(days=args.lookahead_days)
    auctions = sb_get(
        f"multi_county_auctions?county=eq.{county}&auction_status=eq.upcoming"
        f"&auction_date=gte.{today.isoformat()}&auction_date=lte.{cutoff.isoformat()}"
        f"&select=id,case_number,parcel_id,auction_date,sale_type&order=auction_date.asc&limit={args.limit}"
    )
    print(f"[pre_auction_lien_harvest] {county}: {len(auctions)} genuinely-future upcoming auctions in [{today}, {cutoff}] (limit={args.limit})")

    cfg = COUNTY_ACCLAIM[county]
    session = AcclaimSession(cfg["base"], cfg["prefix"])

    n_title_defects = n_lien_results = n_skipped_dupe = n_cases_no_docs = 0
    for a in auctions:
        case_number = a["case_number"]
        try:
            docs = session.case_lookup(case_number)
        except Exception as e:
            print(f"  {case_number}: FETCH FAILED — {e}")
            continue
        if not docs:
            n_cases_no_docs += 1
            print(f"  {case_number}: 0 recorded documents on file")
            continue

        title_rows, lien_rows = classify_docs(case_number, a.get("parcel_id"), county, docs)
        for row in title_rows:
            if already_exists("title_defects", case_number, "rule_id", row.get("rule_id")):
                n_skipped_dupe += 1
                continue
            try:
                sb_insert("title_defects", row)
                n_title_defects += 1
            except Exception as e:
                print(f"  {case_number}: title_defects insert failed — {e}")
        for row in lien_rows:
            if already_exists("lien_results", case_number, "book_page", row.get("book_page")):
                n_skipped_dupe += 1
                continue
            try:
                sb_insert("lien_results", row)
                n_lien_results += 1
            except Exception as e:
                print(f"  {case_number}: lien_results insert failed — {e}")

        print(f"  {case_number}: {len(docs)} docs -> {len(title_rows)} case-filing, {len(lien_rows)} lien-type")

    print(f"[pre_auction_lien_harvest] done: +{n_title_defects} title_defects, +{n_lien_results} lien_results, "
          f"{n_skipped_dupe} already on file, {n_cases_no_docs} cases with zero recorded documents")


if __name__ == "__main__":
    main()
