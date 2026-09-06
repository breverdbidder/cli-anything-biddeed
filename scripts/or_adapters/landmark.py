#!/usr/bin/env python3
"""Landmark Web (Pioneer Technology Group / Catalis Courts & Land Records)
Official Records adapter — lane B of the statewide Title Tiers 1-2 rollout
(issue #20050, pairs with #20049's AcclaimWeb family rollout + #20045's
Brevard wiring). Same output contract as pre_auction_lien_harvest.py's
AcclaimWeb path: title_tier1_results (full recorded-instrument list) +
lien_results/title_defects (Tier 2 input) via the SAME classify_docs() /
tier1_rows() / write_tier1_results() used by every other county.

Platform notes (live-verified this session, 2026-09-06):
  - Landmark Web deployments sit behind Cloudflare or Akamai bot-management
    in front of a classic ASP.NET MVC + jQuery/DataTables app. A plain
    httpx/urllib client gets 403'd on every disclaimer POST regardless of
    headers (confirmed against or.martinclerk.com); a real Chromium session
    that executes the site's own disclaimer/reCAPTCHA JS passes cleanly
    (confirmed against records2.baycoclerk.com — real case-number search,
    real results). Same reasoning as
    scripts/highlands_owner_name_lien_harvest.py's Playwright driver for
    AcclaimWeb's other bot-managed deployments — this is standard headless-
    browser automation of a public search form, not captcha-solving or any
    other evasion technique (no interactive challenge was ever presented to
    or solved by this script; Google reCAPTCHA's invisible v2 token is
    obtained by the page's own JS during normal navigation, same as any real
    visitor's browser does transparently).
  - Landmark Web's own generic index.js ships a "Case Number Search" code
    path (SubmitSearch('caseNumberSearchForm', 'CaseNumberSearch', ...)),
    but whether a given county's clerk actually ENABLES that tab is a
    per-deployment admin choice, not a fixed platform capability — verified
    live: Bay/Palm Beach/Citrus/Flagler expose "Case Number Search Search" in
    their nav; Martin/Okeechobee do not (Document/Name/BookPage/Consideration/
    RecordDate/InstrumentNumber/Legal only). COUNTY_LANDMARK's
    has_case_number_search flag records which, per county, live-verified.
  - Counties with has_case_number_search=False have NO working harvest path
    in this script yet — case_lookup() will raise for them. Landmark Web
    indexes by name/party/document-type, not court case number (it is a
    LAND recording index, not a court docket), so linking a case_number
    auction row to a specific name search requires an owner/defendant name
    from elsewhere (the same gap already disclosed for santa_rosa/brevard's
    name-search sweep in pre_auction_lien_harvest.py, and solved for
    Highlands only via an external property-appraiser lookup in
    scripts/highlands_owner_name_lien_harvest.py). Not attempted this
    session for Landmark counties — disclosed gap, not silently skipped.

Real verified response schema (records2.baycoclerk.com/Recording/Search/
GetSearchResults, case 25000982CA, 2026-09-06): a DataTables server-side
JSON {"draw","recordsTotal","recordsFiltered","data":[{...}]} where each row
is a dict of STRING-KEYED numeric columns (not named fields) —
_normalize_row() below maps that fixed column layout (verified against 3
real rows: LIS PENDENS / JUDGMENT / ORDER, real book/page/instrument
numbers) to the same field names classify_docs()/tier1_rows() already
expect from AcclaimWeb (DocTypeDescription, RecordDate, BookPage,
InstrumentNumber, DirectName, IndirectName, TransactionItemId).

Usage: python scripts/or_adapters/landmark.py --county bay [--lookahead-days 14] [--limit 8]
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
"""
import sys, os, re, time, argparse, datetime as dt
import html as html_lib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pre_auction_lien_harvest import (  # noqa: E402
    sb_get, sb_insert, classify_docs, already_exists, tier1_rows, write_tier1_results,
)

from playwright.sync_api import sync_playwright  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
THROTTLE = 3.0  # shared production recording sites, same floor as AcclaimSession + margin for the extra browser-render cost

# county -> {base, virtual_dir, has_case_number_search}. virtual_dir is the
# IIS application path segment (varies per deployment — "LandmarkWeb" for
# most, "Recording" for Bay). has_case_number_search is live-verified per
# county (see module docstring) — do not assume True for an un-checked
# county; case_lookup() will fail loudly (missing nav link) rather than
# silently returning wrong data if a county doesn't expose this tab.
COUNTY_LANDMARK = {
    "bay":        {"base": "https://records2.baycoclerk.com", "virtual_dir": "Recording",   "has_case_number_search": True},
    "martin":     {"base": "https://or.martinclerk.com",       "virtual_dir": "LandmarkWeb", "has_case_number_search": False},
    # palm_beach/flagler: Landmark Web mounted at the domain ROOT, not under
    # /LandmarkWeb (live-verified 2026-09-06 — /LandmarkWeb/Home/Index 404s,
    # /Home/Index is the real path here; per-deployment IIS config, not a
    # fixed platform convention).
    "palm_beach": {"base": "https://erec.mypalmbeachclerk.com","virtual_dir": "",            "has_case_number_search": True},
    "citrus":     {"base": "https://search.citrusclerk.org",   "virtual_dir": "LandmarkWeb", "has_case_number_search": True},
    "flagler":    {"base": "https://records.flaglerclerk.gov", "virtual_dir": "",            "has_case_number_search": True},
    "okeechobee": {"base": "https://pioneer.okeechobeelandmark.com", "virtual_dir": "LandmarkWebLive", "has_case_number_search": False},
    "st_johns":   {"base": "https://apps.stjohnsclerk.com",     "virtual_dir": "Landmark",    "has_case_number_search": None},  # unverified this session
    "lee":        {"base": "https://or.leeclerk.org",           "virtual_dir": "LandMarkWeb", "has_case_number_search": None},  # unverified this session -- DB flagged is_active=False, needs live re-check
}

_NOBREAK = re.compile(r"^nobreak_")
_HIDDEN = re.compile(r"^hidden_")
_NAME_SEP = re.compile(r"<div class='nameSeperator'></div>|<div class=\"nameSeperator\"></div>")


def _clean(val):
    if val is None:
        return None
    s = str(val)
    s = _NOBREAK.sub("", s)
    s = html_lib.unescape(s)
    return s.strip().strip("\r\n").strip() or None


def _mmddyyyy_to_yyyymmdd(s):
    """Landmark Web's GetSearchResults returns 'MM/DD/YYYY' — classify_docs()
    compares RecordDate strings lexically against the case's Lis Pendens
    date (assumes 'YYYY/MM/DD' sorts correctly, same as AcclaimWeb's native
    shape) and tier1_rows() does a naive '/' -> '-' swap expecting that same
    ordering. Converting here keeps both shared functions untouched, same
    pattern as pre_auction_lien_harvest.py's normalize_brevard_docs()."""
    if not s:
        return None
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s.strip())
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    return f"{yyyy}/{int(mm):02d}/{int(dd):02d}"


def _normalize_row(row):
    """Maps Bay's verified DataTables column layout (0-indexed string keys)
    to the field names classify_docs()/tier1_rows() expect. Column mapping
    verified live against 3 real Bay County instruments (LIS PENDENS,
    JUDGMENT, ORDER) — see module docstring."""
    direct = _clean(row.get("5"))
    indirect_raw = row.get("6") or ""
    indirect_parts = [html_lib.unescape(p).strip() for p in _NAME_SEP.split(indirect_raw) if p and p.strip()]
    indirect = "; ".join(indirect_parts) if indirect_parts else None
    doc_id = None
    hidden25 = row.get("25") or ""
    m = _HIDDEN.match(hidden25)
    if m:
        doc_id = hidden25[len(m.group(0)):] or None
    book = _clean(row.get("10"))
    page = _clean(row.get("11"))
    book_page = f"{book}/{page}" if book and page else (book or page)
    return {
        "DocTypeDescription": _clean(row.get("8")),
        "RecordDate": _mmddyyyy_to_yyyymmdd(_clean(row.get("7"))),
        "BookPage": book_page,
        "InstrumentNumber": _clean(row.get("12")),
        "DirectName": direct,
        "IndirectName": indirect,
        "TransactionItemId": doc_id,
        "Consideration": None,  # not present in this result set -- disclosed limitation, not guessed
    }


class LandmarkSession:
    """Drives a real Chromium session via Playwright for the reasons in the
    module docstring. One browser session per script run (reused across
    cases in the same county, like AcclaimSession) — only the disclaimer
    accept is per-section, not per-case."""

    def __init__(self, base, virtual_dir):
        self.base = base.rstrip("/")
        self.vdir = virtual_dir.strip("/")
        self._pw = None
        self.browser = None
        self.page = None
        self._disclaimer_section = None

    def start(self):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=True)
        ctx = self.browser.new_context(user_agent=UA)
        ctx.route("**/*.{png,jpg,jpeg,gif,woff,woff2,ttf}", lambda route: route.abort())
        self.page = ctx.new_page()

    def stop(self):
        try:
            if self.browser:
                self.browser.close()
        finally:
            if self._pw:
                self._pw.stop()

    def _home_url(self):
        return f"{self.base}/{self.vdir}/Home/Index" if self.vdir else f"{self.base}/Home/Index"

    def _accept_disclaimer(self, section):
        if self._disclaimer_section == section:
            return
        page = self.page
        page.goto(self._home_url(), timeout=30000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        nav = page.locator(f"a[onclick*=\"LaunchDisclaimer('{section}')\"]")
        if nav.count() == 0:
            raise RuntimeError(
                f"no '{section}' nav link on {self.base}/{self.vdir} -- this county's "
                "Landmark Web deployment does not expose this search type (live-checked, not assumed)"
            )
        # some deployments' fixed navbar intercepts pointer events on the
        # in-flow nav link (verified live: citrus) -- invoking the same
        # onclick handler directly is equivalent to a real click for this
        # inline JS function, no different than the browser's own dispatch.
        nav.first.evaluate("el => el.onclick ? el.onclick() : el.click()")
        time.sleep(2)
        if page.is_visible("#idAcceptYes"):
            page.click("#idAcceptYes")
            time.sleep(3)
        self._disclaimer_section = section

    def case_lookup(self, case_number):
        """Case Number Search — only where the clerk enabled this tab (see
        COUNTY_LANDMARK's has_case_number_search). Returns normalized
        instrument dicts. A real zero-result search returns []."""
        self._accept_disclaimer("searchCriteriaCaseNumber")
        page = self.page
        page.wait_for_selector("#caseNumber", timeout=10000)
        page.fill("#caseNumber", "")
        page.fill("#caseNumber", case_number)
        time.sleep(0.5)

        captured = {}

        def on_response(resp):
            if resp.url.endswith("/Search/GetSearchResults") and resp.request.method == "POST":
                try:
                    captured["body"] = resp.json()
                except Exception as e:
                    captured["error"] = str(e)

        page.on("response", on_response)
        page.click("#submit-CaseNumber")
        deadline = time.time() + 25
        while "body" not in captured and "error" not in captured and time.time() < deadline:
            page.wait_for_timeout(400)
        page.remove_listener("response", on_response)

        if "error" in captured:
            raise RuntimeError(f"GetSearchResults returned non-JSON: {captured['error']}")
        if "body" not in captured:
            raise RuntimeError("Search/GetSearchResults never fired within 25s -- site flow may have changed, needs re-verification")
        rows = captured["body"].get("data") or []
        return [_normalize_row(r) for r in rows]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--county", required=True, choices=sorted(COUNTY_LANDMARK))
    ap.add_argument("--lookahead-days", type=int, default=14)
    ap.add_argument("--limit", type=int, default=8, help="max cases per run -- shared production recording site, throttled")
    ap.add_argument("--case-numbers", default=None, help="comma-separated exact case_number list, bypasses the upcoming/lookahead-window filter")
    args = ap.parse_args()

    county = args.county
    cfg = COUNTY_LANDMARK[county]
    if not cfg["has_case_number_search"]:
        print(f"BLOCKED: {county} Landmark Web deployment does not expose Case Number Search "
              f"(live-verified) and no owner-name source is wired for this county yet. "
              f"0 cases attempted -- disclosed gap, not a silent skip.")
        sys.exit(1)
    if cfg["has_case_number_search"] is None:
        print(f"BLOCKED: {county} has_case_number_search is unverified this session -- refusing "
              f"to guess. Run a live check before harvesting.")
        sys.exit(1)

    if args.case_numbers:
        wanted = [c.strip() for c in args.case_numbers.split(",") if c.strip()]
        in_list = ",".join(f'"{c}"' for c in wanted)
        auctions = sb_get(
            f"multi_county_auctions?county=eq.{county}&case_number=in.({in_list})"
            f"&select=id,case_number,parcel_id,auction_date,sale_type"
        )
        print(f"[landmark] {county}: targeted pull, {len(auctions)}/{len(wanted)} of the requested case_numbers found")
    else:
        today = dt.date.today()
        cutoff = today + dt.timedelta(days=args.lookahead_days)
        auctions = sb_get(
            f"multi_county_auctions?county=eq.{county}&auction_status=eq.upcoming"
            f"&auction_date=gte.{today.isoformat()}&auction_date=lte.{cutoff.isoformat()}"
            f"&select=id,case_number,parcel_id,auction_date,sale_type&order=auction_date.asc&limit={args.limit}"
        )
        print(f"[landmark] {county}: {len(auctions)} genuinely-future upcoming auctions in [{today}, {cutoff}] (limit={args.limit})")

    session = LandmarkSession(cfg["base"], cfg["virtual_dir"])
    session.start()

    n_title_defects = n_lien_results = n_skipped_dupe = n_cases_no_docs = n_fetch_failed = 0
    n_tier1_written = n_tier1_skipped = 0
    source = f"{county}_landmarkweb_case_search"
    try:
        for i, a in enumerate(auctions):
            case_number = a["case_number"]
            if i > 0:
                time.sleep(THROTTLE)
            try:
                docs = session.case_lookup(case_number)
            except Exception as e:
                print(f"  {case_number}: FETCH FAILED — {e}")
                n_fetch_failed += 1
                continue

            if not docs:
                n_cases_no_docs += 1
                print(f"  {case_number}: 0 recorded documents on file")
                if not sb_get(f"title_tier1_results?mca_id=eq.{a['id']}&select=id&limit=1"):
                    try:
                        sb_insert("title_tier1_results", {
                            "mca_id": a["id"], "case_number": case_number, "county": county,
                            "parcel_id": a.get("parcel_id"), "instrument_type": "NO_DOCUMENTS_FOUND",
                            "status": "searched_clean — 0 recorded documents found for this case number in this search",
                            "source": source, "raw_data": {"case_lookup_result": "empty"},
                        })
                    except Exception as e:
                        print(f"  {case_number}: no-docs tier1 marker insert failed — {e}")
                continue

            title_rows, lien_rows = classify_docs(case_number, a.get("parcel_id"), county, docs, source=source)

            t1w, t1s, t1f = write_tier1_results(tier1_rows(a["id"], case_number, county, a.get("parcel_id"), docs, source))
            n_tier1_written += t1w
            n_tier1_skipped += t1s

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

            print(f"  {case_number}: {len(docs)} case docs -> {len(title_rows)} case-filing, "
                  f"{len(lien_rows)} lien-type, {t1w} tier1 instruments (+{t1s} already on file)")
    finally:
        session.stop()

    print(f"[landmark] done: county={county} +{n_title_defects} title_defects, +{n_lien_results} lien_results, "
          f"+{n_tier1_written} title_tier1_results ({n_tier1_skipped} already on file), "
          f"{n_skipped_dupe} already on file, {n_cases_no_docs} cases with zero recorded documents, "
          f"{n_fetch_failed} fetch failures")


if __name__ == "__main__":
    main()
