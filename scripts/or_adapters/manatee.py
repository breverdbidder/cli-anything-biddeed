#!/usr/bin/env python3
"""Manatee County Official Records adapter (MCCCC Public Records Hub) —
issue #20054 lane C, Part 2 ("free custom portals", smallest first). Same
output contract as landmark.py/pre_auction_lien_harvest.py: title_tier1_results
+ lien_results/title_defects via the shared classify_docs()/tier1_rows()/
write_tier1_results().

Platform reality, live-verified this session (2026-09-06):
  - records.manateeclerk.com is a plain ASP.NET MVC app (MCCCC "Tyler"-branded
    footer) with NO bot-management in front of it — a plain httpx GET/POST
    with the page's own anti-forgery token + session cookie works, no
    Playwright/browser needed (unlike every Landmark Web deployment).
  - Case Number search (/OfficialRecords/Search/CaseNumber ->
    /OfficialRecords/Search/DoSearch, POST) requires the CaseNumber in this
    site's OWN short form (4-digit year + 2-letter case type + the sequence
    digits as printed, e.g. "2018CA006069"), NOT the full UCN this repo
    stores in multi_county_auctions.case_number (e.g. "412018CA006069CAAXMA"
    or "2018CA006069AX"). _to_manatee_case_number() strips the leading
    2-digit circuit-court prefix (if present) and any trailing division
    suffix (AX, CAAXMA, ...) — live-verified against 4 real upcoming Manatee
    auctions this session, all returned real results (2-3 recorded
    instruments each) once transformed; the untransformed UCN always
    returned "We found 0 results".
  - Results render as a plain HTML <table id="results"> (no JSON API to
    intercept) — one <tr class="data-row"> per instrument, columns View
    (doc link)/Instrument/From/To/Type/Book/Page/Consideration/
    Description/Date/Pages. From/To are each an <ol><li> list of party
    names (a document can have multiple grantors/grantees) — joined with
    "; " into DirectName/IndirectName, same shape landmark.py's
    _normalize_row() produces for AcclaimWeb/Landmark's multi-name fields.
  - Consideration IS present here (unlike Landmark) — parsed as a plain
    dollar string, not guessed.

Usage: python scripts/or_adapters/manatee.py [--lookahead-days 14] [--limit 20] [--case-numbers 2018CA006069AX,...]
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
"""
import sys, os, re, time, argparse, datetime as dt
import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pre_auction_lien_harvest import (  # noqa: E402
    sb_get, sb_insert, classify_docs, already_exists, tier1_rows, write_tier1_results,
)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
BASE = "https://records.manateeclerk.com"
SEARCH_PAGE = f"{BASE}/OfficialRecords/Search/CaseNumber"
DO_SEARCH = f"{BASE}/OfficialRecords/Search/DoSearch"
THROTTLE = 2.0
COUNTY = "manatee"

_CASE_RE = re.compile(r"(\d{4})\s*-?\s*(CA|CC)\s*-?\s*(\d{4,8})")


def _to_manatee_case_number(raw):
    """Strip circuit-court prefix / division suffix down to this site's own
    short form -- see module docstring for live-verified examples."""
    m = _CASE_RE.search(raw.upper())
    if not m:
        return None
    year, ctype, seq = m.groups()
    return f"{year}{ctype}{seq}"


def _mmddyyyy_dash_to_yyyymmdd(s):
    if not s:
        return None
    m = re.match(r"^(\d{2})-(\d{2})-(\d{4})$", s.strip())
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    return f"{yyyy}/{mm}/{dd}"


class ManateeSession:
    def __init__(self):
        self.client = httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=20)

    def close(self):
        self.client.close()

    def case_lookup(self, case_number):
        mcn = _to_manatee_case_number(case_number)
        if not mcn:
            raise RuntimeError(f"could not derive a Manatee-format case number from {case_number!r}")
        r = self.client.get(SEARCH_PAGE)
        token_m = re.search(r'__RequestVerificationToken" type="hidden" value="([^"]+)"', r.text)
        if not token_m:
            raise RuntimeError("anti-forgery token not found on search page -- site markup may have changed")
        data = {
            "SearchInputs.CaseNumber": mcn,
            "__RequestVerificationToken": token_m.group(1),
            "SearchInputs.Page": "1", "SearchInputs.PageSize": "50",
            "SearchInputs.SearchType": "CaseNumber",
        }
        r2 = self.client.post(DO_SEARCH, data=data)
        if r2.status_code != 200:
            raise RuntimeError(f"DoSearch returned HTTP {r2.status_code}")
        if "We found 0 results" in r2.text:
            return []
        soup = BeautifulSoup(r2.text, "html.parser")
        table = soup.find("table", id="results")
        if not table:
            raise RuntimeError("no #results table and no '0 results' message -- site flow may have changed")
        rows = []
        for tr in table.find_all("tr", class_="data-row"):
            cells = tr.find_all("td")
            if len(cells) < 11:
                continue
            direct = "; ".join(li.get_text(strip=True) for li in cells[2].find_all("li")) or None
            indirect = "; ".join(li.get_text(strip=True) for li in cells[3].find_all("li")) or None
            rows.append({
                "DocTypeDescription": cells[4].get_text(strip=True) or None,
                "RecordDate": _mmddyyyy_dash_to_yyyymmdd(cells[9].get_text(strip=True)),
                "BookPage": (f"{cells[5].get_text(strip=True)}/{cells[6].get_text(strip=True)}"
                             if cells[5].get_text(strip=True) or cells[6].get_text(strip=True) else None),
                "InstrumentNumber": cells[1].get_text(strip=True) or None,
                "DirectName": direct,
                "IndirectName": indirect,
                "TransactionItemId": None,  # this portal keys images by instrument number, not a separate item id
                "Consideration": cells[7].get_text(strip=True) or None,
            })
        return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lookahead-days", type=int, default=14)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--case-numbers", default=None)
    args = ap.parse_args()

    if args.case_numbers:
        wanted = [c.strip() for c in args.case_numbers.split(",") if c.strip()]
        in_list = ",".join(f'"{c}"' for c in wanted)
        auctions = sb_get(
            f"multi_county_auctions?county=eq.{COUNTY}&case_number=in.({in_list})"
            f"&select=id,case_number,parcel_id,auction_date,sale_type"
        )
        print(f"[manatee] targeted pull, {len(auctions)}/{len(wanted)} of the requested case_numbers found")
    else:
        today = dt.date.today()
        cutoff = today + dt.timedelta(days=args.lookahead_days)
        auctions = sb_get(
            f"multi_county_auctions?county=eq.{COUNTY}&auction_status=eq.upcoming"
            f"&auction_date=gte.{today.isoformat()}&auction_date=lte.{cutoff.isoformat()}"
            f"&select=id,case_number,parcel_id,auction_date,sale_type&order=auction_date.asc&limit={args.limit}"
        )
        print(f"[manatee] {len(auctions)} genuinely-future upcoming auctions in [{today}, {cutoff}] (limit={args.limit})")

    session = ManateeSession()
    n_title_defects = n_lien_results = n_skipped_dupe = n_cases_no_docs = n_fetch_failed = 0
    n_tier1_written = n_tier1_skipped = 0
    source = "manatee_mcccc_case_search"
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
                            "mca_id": a["id"], "case_number": case_number, "county": COUNTY,
                            "parcel_id": a.get("parcel_id"), "instrument_type": "NO_DOCUMENTS_FOUND",
                            "status": "searched_clean — 0 recorded documents found for this case number in this search",
                            "source": source, "raw_data": {"case_lookup_result": "empty"},
                        })
                    except Exception as e:
                        print(f"  {case_number}: no-docs tier1 marker insert failed — {e}")
                continue

            title_rows, lien_rows = classify_docs(case_number, a.get("parcel_id"), COUNTY, docs, source=source)
            t1w, t1s, t1f = write_tier1_results(tier1_rows(a["id"], case_number, COUNTY, a.get("parcel_id"), docs, source))
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
        session.close()

    print(f"[manatee] done: +{n_title_defects} title_defects, +{n_lien_results} lien_results, "
          f"+{n_tier1_written} title_tier1_results ({n_tier1_skipped} already on file), "
          f"{n_skipped_dupe} already on file, {n_cases_no_docs} cases with zero recorded documents, "
          f"{n_fetch_failed} fetch failures")


if __name__ == "__main__":
    main()
