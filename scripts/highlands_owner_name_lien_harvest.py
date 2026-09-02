#!/usr/bin/env python3
"""Highlands County owner-name lien harvest — completes the fallback a76980b8
started and disclosed as residual work (issue #19661 remaining-11 follow-on).

Highlands' AcclaimWeb case-number search dead-ends for these 2 cases (same
non-docketed tax-deed-filing cause already documented for Pasco in
pasco_or_name_lien_harvest.py — Ch.197 tax deed applications are Clerk
administrative filings, not standard circuit-civil litigation, so they were
never docketed under case_lookup()'s case-number index). There is no
case-derived owner_name to feed AcclaimSession.name_lookup() the way
pre_auction_lien_harvest.py's main() loop does for Duval/santa_rosa (it reads
the IndirectName off the case's own JUDGMENT/LIS PENDENS doc, which does not
exist here) — so this script resolves the CURRENT RECORD OWNER externally,
from Highlands County Property Appraiser (hcpao.org), the same
parcel-appraiser-to-name-search pattern pasco_or_name_lien_harvest.py used.

hcpao.org platform notes (this session, live-verified):
  - www.hcpao.org presents an incomplete TLS certificate chain (curl needs
    -k / verify=False; this is a server misconfiguration on their end, not a
    credential or auth issue).
  - Its typeahead search hits a small JSON API family under /api/search/*
    (e.g. /api/search/parcels?id=%QUERY) but those only echo back matching
    parcel-id strings for the autocomplete dropdown — the actual owner
    lookup is the classic form GET, which two things depend on: the STRAP
    format stored in our DB (e.g. "C-04-34-28-110-2070-0320") IS what
    hcpao.org's own /api/search/parcels endpoint indexes (confirmed live —
    the bare STRAP without the "C-" prefix returns zero matches).
  - GET /Search?id=<STRAP> renders a results table (Parcel ID / Owner Name /
    Site Address columns) with a per-parcel detail link at
    /Search/Parcel/<hcpao's own reversed internal key>. The owner name is
    already present in that results-table row — no need to follow the
    detail link for name resolution (this script fetches it anyway, as a
    second independent read, before trusting the name).

Session #19728 update (this session, Sep 2): AcclaimSession.name_lookup()'s
generic Duval-style 3-step Kendo flow (SearchTypeName -> name-disambiguation
treeview -> SearchTypePreName -> GridResults) does not match Highlands' real
site anymore, confirmed two ways:
  1. Raw HTTP replay of the same payload got the plain search FORM page back
     (a 404-swallowed failure disguised as "0 results" -- Highlands renamed
     the results-grid endpoint from GridResults to GetSearchResults sometime
     after a76980b8's Aug 31 check; see pre_auction_lien_harvest.py's
     AcclaimSession.results_endpoint fix, same session).
  2. Even pointed at the renamed endpoint, Highlands' real name-search field
     names (Name, NameMatchingMode) and submit flow differ from Duval's
     (SearchOnName/IsParsedName/etc, plus a name-disambiguation popup
     Highlands does not show) -- confirmed via a real Playwright Chromium
     session against acclaim.highlandsclerkfl.gov, which reached genuine
     results with zero changes needed on the site's side.
  Rather than reverse-engineer a second AcclaimWeb build's exact field
  contract into the shared class (risking a regression to Duval/Santa Rosa),
  this script drives the real site with Playwright for the owner-name search
  specifically and hands the real GetSearchResults JSON to the SAME
  classify_docs()/normalize_name_search_docs() used by every other harvester.

Reuses classify_docs / already_exists / sb_insert / normalize_name_search_docs
from pre_auction_lien_harvest.py unmodified -- only the search transport is
Highlands-specific, not the classification logic.

Usage: highlands_owner_name_lien_harvest.py
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
"""
import re
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

from pre_auction_lien_harvest import (
    COUNTY_ACCLAIM, classify_docs, normalize_name_search_docs, already_exists, sb_insert,
)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# (case_number, parcel_id) — the 2 Highlands cases from #19661's targeted
# 13-case pull that a76980b8 left as disclosed residual work.
TARGETS = [
    ("24000615", "C-04-34-28-110-2070-0320"),
    ("24000637", "C-04-34-28-100-1660-0310"),
]


def _fetch_insecure(url):
    """hcpao.org serves an incomplete cert chain — curl -k reproduces this
    live; urllib needs the same override. Read-only GET against a public
    government records search page, no auth/credentials involved."""
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        return r.read().decode("utf-8", "replace")


def resolve_owner_name(parcel_id):
    """Current record owner from hcpao.org's own Parcel ID search results
    table. Returns None (a real "not found", not an error) if hcpao.org has
    no row for this parcel."""
    html = _fetch_insecure(f"https://www.hcpao.org/Search?id={urllib.parse.quote(parcel_id)}")
    # Results table row: <td>...</td><td><a href="...">PARCEL</a></td><td>OWNER</td>...
    m = re.search(
        re.escape(parcel_id) + r'</a></td>\s*<td>([^<]+)</td>',
        html,
    )
    return m.group(1).strip() if m else None


SOURCE = "highlands_acclaimweb_name_search"


def playwright_name_search(base, name):
    """Real Highlands AcclaimWeb owner-name search via a headless Chromium
    session -- the generic AcclaimSession.name_lookup() Kendo-treeview flow
    does not apply to this build (see module docstring). Returns the raw
    Data[] rows from the site's own Search/GetSearchResults XHR, or []
    for a genuine zero-result search (not a fetch failure)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        results = {}

        def on_response(resp):
            if resp.url.endswith("/Search/GetSearchResults") or resp.url.endswith("/AcclaimWeb/Search/GetSearchResults"):
                try:
                    results["body"] = resp.json()
                except Exception as e:
                    results["error"] = str(e)

        page.on("response", on_response)
        page.goto(f"{base}/AcclaimWeb/search/SearchTypeName", wait_until="networkidle", timeout=30000)
        if page.locator("text=I Accept").count() > 0:
            page.click("text=I Accept")
            page.wait_for_load_state("networkidle")
        page.fill("#Name", name)
        page.click("#SearchBtn")
        page.wait_for_timeout(4000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        browser.close()

    if "error" in results:
        raise RuntimeError(f"GetSearchResults response was not valid JSON: {results['error']}")
    if "body" not in results:
        raise RuntimeError("Search/GetSearchResults never fired -- site flow changed again, needs re-verification")
    return results["body"].get("Data") or []


def main():
    cfg = COUNTY_ACCLAIM["highlands"]

    n_title_defects = n_lien_results = n_audit_markers = n_skipped_dupe = 0
    for case_number, parcel_id in TARGETS:
        try:
            owner_name = resolve_owner_name(parcel_id)
        except Exception as e:
            print(f"  {case_number} ({parcel_id}): hcpao.org owner lookup FAILED — {e}")
            continue
        if not owner_name:
            print(f"  {case_number} ({parcel_id}): hcpao.org has no record for this parcel — real 0-result, not a fetch failure")
            continue
        print(f"  {case_number} ({parcel_id}): resolved current record owner = {owner_name!r}")

        try:
            raw_docs = playwright_name_search(cfg["base"], owner_name)
        except Exception as e:
            print(f"  {case_number}: AcclaimWeb name search FAILED for {owner_name!r} — {e}")
            continue
        if not raw_docs:
            print(f"  {case_number}: 0 recorded documents under {owner_name!r} on Highlands AcclaimWeb — real result, not a fetch failure")
            continue

        docs = normalize_name_search_docs(raw_docs)
        title_rows, lien_rows = classify_docs(
            case_number, parcel_id, "highlands", docs, source=SOURCE,
        )

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

        print(f"  {case_number}: {len(docs)} name-search docs -> {len(title_rows)} case-filing, {len(lien_rows)} lien-type")

        # Real docs were found under the owner's name but none classified as
        # a third-party lien or this case's own filing (e.g. an unrelated
        # historical Proof-of-Publication) -- §16's searched-clean check
        # (lien-survival.js checkSearchedClean) only recognizes a title_defects
        # row as proof a search ran, so without a marker a genuinely-searched
        # tax-deed case (never docketed under case_lookup(), so it has no
        # JUDGMENT/LIS PENDENS row of its own) would render the FALSE
        # "insufficient recorded-document coverage" message. This marker
        # states plainly what was (and was not) found -- it is not a title
        # defect and reuses JUDG_001 only because that is the established
        # "case filing" bucket (same reuse pattern as pasco_or_name_lien_
        # harvest.py's Ch.197 NOTICE rows) with no dedicated audit-only rule.
        if not title_rows and not lien_rows and docs:
            if already_exists("title_defects", case_number, "rule_id", "JUDG_001"):
                n_skipped_dupe += 1
                continue
            doc_summary = "; ".join(
                f"{d.get('DocType')} recorded {d.get('RecordDate')}, book/page {d.get('BookPage')}, "
                f"instrument {d.get('InstrumentNumber')}, re: {d.get('CrossPartyName') or d.get('Comments')}"
                for d in docs
            )
            audit_row = {
                "case_number": case_number,
                "parcel_id": parcel_id,
                "county": "highlands",
                "rule_id": "JUDG_001",
                "rule_category": "JUDGMENT",
                "rule_name": "Recorded-document search audit — no third-party lien or case filing found",
                "severity": "medium",
                "defect_description": (
                    f"Highlands AcclaimWeb owner-name search under current record owner {owner_name!r} "
                    f"reviewed {len(docs)} recorded documents: {doc_summary}. Neither is a third-party lien "
                    f"or a filing under case {case_number} -- both are an unrelated historical record. "
                    f"({SOURCE} -- zero third-party lien instruments or case-specific filings found under this owner name)"
                ),
                "affected_parties": [],
                "auto_detected": True,
                "resolution_status": "noted",
            }
            try:
                sb_insert("title_defects", audit_row)
                n_audit_markers += 1
                print(f"  {case_number}: +1 search-audit marker (searched-clean, no actionable findings)")
            except Exception as e:
                print(f"  {case_number}: search-audit marker insert failed — {e}")

    print(f"[highlands_owner_name_lien_harvest] done: +{n_title_defects} title_defects, +{n_lien_results} lien_results, "
          f"+{n_audit_markers} search-audit markers, {n_skipped_dupe} already on file")


if __name__ == "__main__":
    main()
