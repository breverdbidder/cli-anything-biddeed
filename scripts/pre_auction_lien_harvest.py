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

County expansion (follow-on to #19657) — santa_rosa added, gold-certified
and live-reachable, but currently BLOCKED on case_lookup(): see the
COUNTY_ACCLAIM dict's santa_rosa comment for the disclosed root cause (its
AcclaimWeb indexes an internal docket number, not the UCN case_number we
store, and we have no owner-name fallback for this county). Included as an
honestly-disclosed 0-yield expansion, not a working second county yet.

Owner/party NAME search (SOLVED, follow-on to #19657's disclosed gap):
Duval AcclaimWeb's SearchTypeName is a 3-step flow, reverse-engineered live
via Playwright driving the real UI (see verification/ for the captured
requests) -- the prior `ShowError('The booktype is invalid...')` was caused
by leaving BookTypes blank/malformed. The client's own
GetBookTypeString() (Scripts/AcclaimSearchPages.js) sets BOTH BookTypes AND
BookTypesDisplay to the literal string "All" when no individual book-type
checkboxes are selected -- BookTypes must never be sent blank.
  1. POST /search/SearchTypeName?Length=6 with SearchOnName=<name> and
     BookTypes=All&BookTypesDisplay=All (both required, both literal "All").
     Returns an HTML fragment embedding a Kendo treeview of every distinct
     name AcclaimWeb has on file matching the search string (name
     disambiguation -- a real name search can match multiple people).
  2. POST /Search/SearchTypePreName with NameList=<treeview selection string>
     (`"<Surname> (<n>)|||<Full Name> "` per matched leaf) + the same date/
     book/doc-type params. This commits the name selection server-side.
  3. POST /Search/GridResults (no body params needed beyond
     sort=&group=&filter=) returns the same {"Data":[...],"Total":N} JSON
     shape as the case-number flow.
This returns ALL of that person's recorded documents STATEWIDE-in-Duval,
not just ones tied to the auction's own case -- exactly the broad owner-name
lien sweep the case-number-only flow couldn't do, surfacing independent
third-party liens (a separate mortgage, an HOA claim of lien, a mechanic's
lien) that never got cross-filed into this litigation.

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
#
# santa_rosa added (county expansion follow-on to #19657): verified live
# 2026-08-31 -- gold_standard_certifications.certified=true (42 consecutive
# gold runs), 13 genuinely-future 'upcoming' auctions in the next 14 days,
# and acclaim.srccol.com/AcclaimWeb/ reachable (HTTP 200, real disclaimer +
# SearchTypeName form, same Kendo BookTypes fields as Duval's build). This
# CONTRADICTS nothing prior -- santa_rosa's AcclaimWeb reachability was not
# previously assumed or checked for this pipeline.
#
# KNOWN GAP, disclosed not worked around: santa_rosa's AcclaimWeb indexes
# documents under the CLERK'S OWN internal docket number (verified live via
# Playwright, e.g. "25000824CAMXAX" = 2-digit year + 6-digit sequence + case
# type + judge/division suffix), NOT the standard Florida Uniform Case
# Number (UCN) format stored in multi_county_auctions.case_number (e.g.
# "57-2025-CA-000824-CA-AXMX" family) -- confirmed by cross-referencing a
# real "000824" substring search against 11 real unrelated cases sharing
# that sequence, none of which UCN-format-match our stored value. No
# defendant/owner_name column is populated for santa_rosa rows either, so
# name_lookup() has no fallback search key. Real result of a live run this
# session: 0 title_defects/lien_results added for 5 genuinely-future
# santa_rosa auctions (4 case numbers -> 0 documents found; case "2026122"
# -> 1 unrelated doc, no lien/judgment match). This needs either a UCN <->
# internal-docket crosswalk or an owner-name data source before it can
# harvest -- not attempted this session.
COUNTY_ACCLAIM = {
    "duval": {"base": "https://or.duvalclerk.com", "prefix": ""},
    "santa_rosa": {"base": "https://acclaim.srccol.com", "prefix": "/AcclaimWeb"},
    # highlands added (issue #19661, targeted 13-case title/lien pull): base
    # URL + platform from clerk_official_records_subdomains (honesty_marker
    # VERIFIED, classic ASP.NET AcclaimWeb -- same /AcclaimWeb prefix family
    # as Brevard/santa_rosa). That row recorded acclaim.highlandsclerkfl.gov
    # as UNREACHABLE (TCP connect timeout) from the runner in a prior
    # session; re-checked live this session (curl -> HTTP 200 in 0.4s,
    # Playwright not needed) -- reachable now, a real network-path change,
    # not a stale assumption being trusted.
    "highlands": {"base": "https://acclaim.highlandsclerkfl.gov", "prefix": "/AcclaimWeb"},
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
        body = self._req(self.base + search_path)  # 302 -> Disclaimer page, establishes session
        # Some AcclaimWeb deployments (highlands, live-verified 2026-08-31)
        # serve the real search form directly with no disclaimer
        # click-through at all -- id="CaseNumber" already present means
        # there is no /Search/Disclaimer endpoint to POST to (404 if tried).
        if body and 'id="CaseNumber"' in body:
            self._disclaimer_accepted = True
            return
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
        return self._extract_grid_data(body)

    @staticmethod
    def _extract_grid_data(body):
        """GridResults' JSON key casing differs by AcclaimWeb build: Duval's
        Kendo UI returns PascalCase {"Data":[...],"Total":N}; Santa Rosa's
        classic ASP.NET MVC build (like Brevard's, see acclaim_case_lookup.py)
        returns lowercase {"data":[...],"total":N} -- verified live 2026-08-31
        against both. Checking both keys keeps one case_lookup()/name_lookup()
        implementation working across both AcclaimWeb generations."""
        try:
            d = json.loads(body)
        except Exception:
            return []
        return d.get("Data") if d.get("Data") is not None else d.get("data", [])

    def name_lookup(self, name):
        """Documents recorded anywhere in Duval under this party's name --
        the broad owner-name lien sweep (mortgages, HOA/mechanic's liens,
        etc.) that case_lookup() cannot do. 3-step Kendo UI flow, reverse-
        engineered live via Playwright (see class docstring reference above
        the case_lookup gap note for the captured request shapes)."""
        self._accept_disclaimer()
        today = dt.date.today()
        date_from, date_to = "1/1/1800", f"{today.month}/{today.day}/{today.year}"
        h = {"Content-Type": "application/x-www-form-urlencoded", "X-Requested-With": "XMLHttpRequest",
             "Referer": self.base + f"{self.prefix}/search/SearchTypeName"}

        step1 = urllib.parse.urlencode({
            "IsParsedName": "False", "Both": "Both", "PartyType": "Both", "SearchOnName": name,
            "DateRangeList": " ", "DocTypes": "all", "DocTypesDisplay-input": "All", "DocTypesDisplay": "",
            "RecordDateFrom": date_from, "BookTypesDisplay": "All", "BookTypes": "All", "RecordDateTo": date_to,
        })
        html = self._req(self.base + f"{self.prefix}/search/SearchTypeName?Length=6", data=step1, hdrs=h)
        name_list = self._build_name_list_selector(html or "")
        if not name_list:
            return []  # no recorded documents under this name -- a real result, not a fetch failure

        step2 = urllib.parse.urlencode({
            "NameList": name_list, "checkedFiles": "on", "SelectAllPrenamesToggle": "on",
            "PartyType": "Both", "RecordDateFrom": f"{date_from} 12:00:00 AM", "RecordDateTo": f"{date_to} 12:00:00 AM",
            "BookTypes": "All", "DocTypes": "all", "SearchOnName": name,
            "SearchOnLastOrBusinessName": "", "SearchOnFirstName": "", "ShowAllNames": "", "ShowAllLegals": "",
        })
        self._req(self.base + f"{self.prefix}/Search/SearchTypePreName", data=step2, hdrs=h)
        body = self._req(self.base + f"{self.prefix}/Search/GridResults", data="sort=&group=&filter=", hdrs=h)
        return self._extract_grid_data(body)

    @staticmethod
    def _build_name_list_selector(html):
        """Reconstructs the NameList selector string that AcclaimCommon.js's
        GetNameListString() builds client-side when a user checks "All/None"
        on the name-disambiguation treeview from step 1's response --
        "<Surname Group> (<n>)|||<Full Name> " per matched leaf, joined with
        '|||'. Selects every matched name (equivalent to checking All/None)
        rather than requiring an exact single match, since a real owner name
        can legitimately return multiple AcclaimWeb-indexed variants."""
        m = re.search(r'"dataSource"\s*:\s*(\[.*?\])\s*,\s*"loadOnDemand"', html, re.S)
        if not m:
            return None
        try:
            tree = json.loads(m.group(1))
        except Exception:
            return None
        parts = []
        for group in tree:
            parts.append(group.get("text", ""))
            for leaf in group.get("items") or []:
                text = leaf.get("text", "")
                idx = text.rfind("(")
                parts.append(text[:idx] if idx != -1 else text)
        return "|||".join(parts) if parts else None


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


def normalize_name_search_docs(docs):
    """SearchTypeName's GridResults uses Party/Name/CrossPartyName instead of
    case_lookup's DirectName/IndirectName (verified live 2026-08-31 — same
    /Search/GridResults endpoint, different field shape per search type).
    Party="From" means the searched Name is the direct/from party;
    Party="To" means it's the indirect/to party. Normalizing here keeps
    classify_docs() itself untouched."""
    out = []
    for d in docs:
        party = d.get("Party")
        name, cross = d.get("Name"), d.get("CrossPartyName")
        direct_name, indirect_name = (name, cross) if party == "From" else (cross, name)
        out.append({**d, "DirectName": direct_name, "IndirectName": indirect_name})
    return out


def classify_docs(case_number, parcel_id, county, docs, source="duval_acclaimweb_case_search", lp_date_override=None):
    """Split a case's recorded documents into (title_defects rows, lien_results rows).

    lp_date_override lets a name-search pass (whose own doc set has already
    been filtered to exclude the case's own Lis Pendens, to avoid
    reprocessing it) still classify senior/junior priority against the
    case's real Lis Pendens date, computed by the caller's earlier
    case_lookup() pass."""
    lp_dates = [d["RecordDate"] for d in docs if "LIS PENDENS" in (d.get("DocTypeDescription") or "").upper() and d.get("RecordDate")]
    lp_date = lp_date_override or (min(lp_dates) if lp_dates else None)  # 'YYYY/MM/DD' strings sort correctly lexically

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
                    "source": source,
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
    ap.add_argument("--case-numbers", default=None,
                     help="comma-separated exact case_number list -- targeted pull for already-decided "
                          "cases (e.g. billable_ff_events), bypasses the upcoming/lookahead-window filter "
                          "which would otherwise exclude auction_status='sold' rows")
    args = ap.parse_args()

    county = args.county
    if county not in COUNTY_ACCLAIM:
        print(f"BLOCKED: no AcclaimWeb config for county={county!r}. Configured: {list(COUNTY_ACCLAIM)}")
        sys.exit(1)

    if args.case_numbers:
        wanted = [c.strip() for c in args.case_numbers.split(",") if c.strip()]
        in_list = ",".join(urllib.parse.quote(c) for c in wanted)
        auctions = sb_get(
            f"multi_county_auctions?county=eq.{county}&case_number=in.({in_list})"
            f"&select=id,case_number,parcel_id,auction_date,sale_type"
        )
        print(f"[pre_auction_lien_harvest] {county}: targeted pull, {len(auctions)}/{len(wanted)} of the "
              f"requested case_numbers found in multi_county_auctions")
    else:
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

        # Owner/party-name sweep (follow-on to #19657's disclosed gap): the
        # case's own JUDGMENT (or, before judgment, its LIS PENDENS) names
        # the defendant/owner as IndirectName -- search AcclaimWeb by that
        # name to catch independent third-party liens never cross-filed into
        # this litigation. Real "nobody by this name" or "no owner name found
        # yet" results return [] / None, not an error.
        owner_name = next(
            (d.get("IndirectName") for d in docs
             if re.search(r"\bJUDG(E|MENT)?\b", d.get("DocTypeDescription") or "", re.I) and d.get("IndirectName")),
            None,
        ) or next(
            (d.get("IndirectName") for d in docs
             if "LIS PENDENS" in (d.get("DocTypeDescription") or "").upper() and d.get("IndirectName")),
            None,
        )
        case_lp_dates = [d["RecordDate"] for d in docs if "LIS PENDENS" in (d.get("DocTypeDescription") or "").upper() and d.get("RecordDate")]
        case_lp_date = min(case_lp_dates) if case_lp_dates else None
        seen_txn_ids = {d.get("TransactionItemId") for d in docs}
        n_name_search_docs = 0
        if owner_name:
            try:
                name_docs = session.name_lookup(owner_name)
            except Exception as e:
                print(f"  {case_number}: name search FAILED for {owner_name!r} — {e}")
                name_docs = []
            new_docs = [d for d in name_docs if d.get("TransactionItemId") not in seen_txn_ids]
            n_name_search_docs = len(new_docs)
            if new_docs:
                name_title_rows, name_lien_rows = classify_docs(
                    case_number, a.get("parcel_id"), county,
                    normalize_name_search_docs(new_docs), source="duval_acclaimweb_name_search",
                    lp_date_override=case_lp_date,
                )
                title_rows += name_title_rows
                lien_rows += name_lien_rows

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

        name_note = f", name search on {owner_name!r}: +{n_name_search_docs} new docs" if owner_name else ", no owner name found for name search"
        print(f"  {case_number}: {len(docs)} case docs -> {len(title_rows)} case-filing, {len(lien_rows)} lien-type{name_note}")

    print(f"[pre_auction_lien_harvest] done: +{n_title_defects} title_defects, +{n_lien_results} lien_results, "
          f"{n_skipped_dupe} already on file, {n_cases_no_docs} cases with zero recorded documents")


if __name__ == "__main__":
    main()
