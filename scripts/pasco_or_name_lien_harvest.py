#!/usr/bin/env python3
"""PRE-AUCTION lien/title harvest for Pasco County tax-deed cases, sourcing
from Pasco Clerk & Comptroller's Official Records NAME search (classic ASP,
app.pascoclerk.com -- NOT AcclaimWeb, NOT Kendo-UI, NOT Laserfiche).

Platform discovery (this session, live-verified):
  - www.pascoclerk.com/232/Search-Official-Records links to
    app.pascoclerk.com/appdot-public-online-services-forms-or-search.asp
    (Server: Microsoft-IIS/10.0, X-Powered-By: ASP.NET, session cookie
    ASPSESSIONID* -- classic ASP, not AcclaimWeb/Kendo).
  - That page offers exactly THREE search modes: Book/Page, Instrument#,
    and Name. There is NO case-number search on Official Records.
  - Pasco's court-case docket search is a SEPARATE system: Civitek OCRS
    (civitekflorida.com/ocrs/county/51/, PrimeFaces/JSF, Cloudflare
    Turnstile present). Its "Case Search" tab wants Year + Court Type
    (dropdown: AP/CA/CC/CO/CT/DR/CF/GA/MM/MO/IN/CP/SC/TR) + Sequence# --
    there is NO "TD" (Tax Deed) court-type option in that dropdown. Tax
    deed sales in FL are administrative proceedings run by the Clerk under
    Ch. 197, not standard circuit-civil litigation, so they are not
    docketed in OCRS. Confirmed: the "512026XX000077TDAXXX" style case
    number the caller wants searched cannot be looked up directly on
    EITHER portal -- neither takes a raw UCN string, and OCRS has nothing
    to decode "TD" against.
  - The actual auction/bidding platform is RealAuction (pasco.realtaxdeed.com),
    which requires a login for the auction calendar / case-detail view (its
    home page reachable at HTTP 200 with a real browser UA, but every link
    beyond the splash page needs credentials -- no public case lookup).

Working path found instead: Pasco's Property Appraiser (search.pascopa.com,
official site, linked from pascopa.com) resolves parcel_id (already in our
DB in SEC-TWN-RNG-SUB-BLOCK-LOT format, e.g. "11-26-16-0010-01400-0020" ->
sec=11 twn=26 rng=16 sbb=0010 blk=01400 lot=0020) to the CURRENT RECORD
OWNER NAME. That owner name is then run through Official Records' Name
search, which returns every recorded document indexed under that name --
including the Clerk's own 2026 "NOTICE" filings (Notice of Application for
Tax Deed under Fla. Stat. 197.502, book/page dated 5/19/2026, and a second
Notice of Sale-adjacent filing dated 8/19/2026 naming every other
recorded/interested party on the property) and any LIEN docs recorded
against that owner whose Legal field matches our parcel's plat description.

Known, disclosed gap: this is a NAME search, not a case search, so it
inherits the site's own caveat ("owner names can return multiple matches")
-- common names (e.g. "PATTERSON PAUL") return unrelated people. This
script narrows by requiring the returned row's Legal field to contain the
parcel's own township-range prefix (e.g. "11-26-16") or plat name, and
prints a WARNING for any name search where that narrowing was needed
because the bare surname search was too broad. It does NOT catch every
possible lien (a lien recorded under a slightly different name spelling,
e.g. an LLC's old name, would be missed) -- that is a real limit, not a
silently swallowed one.

Owner names used (fetched live this session via search.pascopa.com, one
parcel lookup per case -- see PARCEL_OWNER map below). Two of the five
cases (77, 78) share one owner across adjoining lots in the same plat.

lien_type taxonomy note: the caller's requested 5-category taxonomy
(Mortgage / HOA-Association Lien / Mechanic's-Construction Lien / UCC
Filing / Tax Lien) does NOT include what Pasco's "LIEN" doctype actually
turned out to be for these owners: County code-enforcement liens (Party 1
= "PASCO COUNTY" / "BOARD OF COUNTY COMMISSIONERS", confirmed via
instrument-detail lookup on 2023144747). Force-fitting that into "Tax
Lien" would be factually wrong (a tax lien is unpaid ad valorem tax; a
code-enforcement lien is an unpaid code-violation fine) so this script
labels it honestly as "Code Enforcement/Municipal Lien" -- outside the
5-item list, disclosed here and in the run's own stdout, not silently
mapped to the nearest wrong bucket.

Hard rules (same throttle discipline as pre_auction_lien_harvest.py):
single session, ~2.5s between requests, exponential backoff, never rotate
IPs, never parallelize -- shared production court/clerk records site.

Idempotency: checks (case_number, book_page) for lien_results and
(case_number, rule_id) for title_defects before inserting, same as the
Duval reference harvester.

Usage: pasco_or_name_lien_harvest.py
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
"""
import os, re, sys, json, time
import urllib.request, urllib.parse, http.cookiejar

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
THROTTLE = 2.5
BASE = "https://app.pascoclerk.com"
SEARCH_PAGE = f"{BASE}/appdot-public-online-services-forms-or-search.asp"
NAME_RESULTS = f"{BASE}/appdot-public-sup-svcs-results-or-name-search.asp"
INSTR_DETAIL = f"{BASE}/appdot-public-sup-svcs-results-or-instr-detail.asp"

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
assert SB_URL and SB_KEY, "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY env required"

# case_number -> (parcel_id, owner name search string, township-range prefix
# used to narrow common-surname results). owner names + T-R prefixes were
# resolved live this session via search.pascopa.com parcel lookups.
CASES = [
    {"case_number": "512026XX000077TDAXXX", "parcel_id": "11-26-16-0010-01400-0020",
     "owner_search": "LITTLE ROAD PARTNERSHIP", "legal_prefix": "11-26-16", "sibling_rank": 0},
    {"case_number": "512026XX000078TDAXXX", "parcel_id": "11-26-16-0010-01400-0031",
     "owner_search": "LITTLE ROAD PARTNERSHIP", "legal_prefix": "11-26-16", "sibling_rank": 1},
    {"case_number": "512026XX000082TDAXXX", "parcel_id": "32-25-22-0000-00500-0000",
     "owner_search": "RICE WILLIS", "legal_prefix": "32-25-22", "sibling_rank": 0},
    {"case_number": "512026XX000100TDAXXX", "parcel_id": "10-25-21-0050-00000-0430",
     "owner_search": "HUANG ZHAOBING", "legal_prefix": ["10-25-21", "CLINTON AVENUE HEIGHTS"], "sibling_rank": 0},
    {"case_number": "512026XX000105TDAXXX", "parcel_id": "09-25-18-0020-00E00-0020",
     "owner_search": "PATTERSON PAUL M", "legal_prefix": ["09-25-18", "JULIUS PK", "JULIUS PARK"], "sibling_rank": 0},
]
# Cases sharing the same owner_search (77 & 78, both LITTLE ROAD PARTNERSHIP,
# adjoining lots in the same 11-26-16 section) cannot be disambiguated from
# the Official Records index alone for blank-Legal clerk NOTICE rows -- both
# would otherwise resolve identically and get the SAME notice instruments
# written to BOTH cases (a real duplication bug hit and fixed this session).
# `sibling_rank` orders same-owner cases by case_number; for blank-legal
# notice rows that come in same-day *pairs* (5/19/2026 batch: 2 instruments;
# 8/19/2026 batch: 2 instruments), rank 0 gets the first instrument of each
# pair and rank 1 gets the second, in book/page order. This is a disclosed
# ASSUMPTION (documented as INFERRED, not VERIFIED) based on Pasco filing
# adjoining-parcel notices as consecutive same-day instruments -- not proven
# by opening the actual document image.
SIBLING_OWNER_COUNT = {}
for _c in CASES:
    SIBLING_OWNER_COUNT[_c["owner_search"]] = SIBLING_OWNER_COUNT.get(_c["owner_search"], 0) + 1

LIEN_TYPE_PATTERNS = [
    ("Mortgage",              re.compile(r"\b(MTG|MORTGAGE|DEED\s*OF\s*TRUST)\b", re.I)),
    ("HOA/Association Lien",  re.compile(r"\b(HOA|HOMEOWNERS|ASSOCIATION\s*LIEN|CLAIM\s*OF\s*LIEN)\b", re.I)),
    ("Mechanic's/Construction Lien", re.compile(r"\b(MECH(ANIC)?|CONSTRUCTION\s*LIEN)\b", re.I)),
    ("UCC Filing",            re.compile(r"\bUCC\b", re.I)),
    ("Tax Lien",              re.compile(r"\bTAX\s*LIEN\b", re.I)),
]
JUDGMENT_RE = re.compile(r"\bJUDG(E|MENT)?\b", re.I)
NOTICE_RE = re.compile(r"\bNOTICE\b", re.I)
JUDGMENT_RULE_ID = "JUDG_001"  # existing title_rules row, category=JUDGMENT

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def http_req(url, data=None, hdrs=None, retries=4):
    for attempt in range(retries):
        time.sleep(THROTTLE * (2 ** attempt if attempt else 1))
        try:
            body = data.encode() if isinstance(data, str) else data
            r = urllib.request.Request(url, data=body)
            r.add_header("User-Agent", UA)
            for k, v in (hdrs or {}).items():
                r.add_header(k, v)
            with opener.open(r, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            sys.stderr.write(f"retry {attempt+1}/{retries}: {e}\n")
            if attempt == retries - 1:
                raise
    return None


def name_search(name):
    http_req(SEARCH_PAGE)  # establish ASPSESSIONID cookie
    payload = urllib.parse.urlencode({
        "name": name, "fromdate": "", "todate": "",
        "docset": "ALL", "namedir": "A", "Submit": "Search by Name",
    })
    hdrs = {"Content-Type": "application/x-www-form-urlencoded",
            "Referer": SEARCH_PAGE}
    return http_req(NAME_RESULTS, data=payload, hdrs=hdrs)


ROW_RE = re.compile(
    r'<tr><td >([^<]*)</td><td >([^<]*)</td><td >.*?</td>'
    r'<td ><A HREF="[^"]*">(\d+)</A></td><td >([^<]*)</td><td >[^<]*</td>'
    r'<td >([^<]*)</td><td >([^<]*)</td><td >([^<]*)</td><td >([^<]*)</td></tr>',
    re.S,
)


def parse_rows(html):
    rows = []
    html = html or ""
    # Scope to the actual RESULTS table -- the page also renders a
    # "Search Criteria Used" summary table with a similarly-shaped single
    # <tr> above it; slicing past "Searched for:" (which only appears once
    # the results table's own header follows) avoids matching that row.
    marker = html.find("Searched for:")
    if marker != -1:
        html = html[marker:]
    for m in ROW_RE.finditer(html):
        name, cross, instr, date, book, page, doctype, legal = m.groups()
        rows.append({
            "name": name.strip(), "cross_party": cross.strip(),
            "instrument": instr.strip(), "date": date.strip(),
            "book": book.strip(), "page": page.strip(),
            "doctype": doctype.strip(), "legal": legal.strip(),
        })
    return rows


def instrument_detail(instrument):
    http_req(SEARCH_PAGE)
    body = http_req(f"{INSTR_DETAIL}?mdqs=1&tbqs={instrument}",
                     hdrs={"Referer": NAME_RESULTS})
    return body or ""


def parse_parties(detail_html):
    parties = re.findall(r"([A-Z0-9 &/'.\-]+?)\s*</td>\s*<td[^>]*>\s*Party\s*(\d)",
                          detail_html)
    return [(p[0].strip(), p[1]) for p in parties]


def matches_parcel(row, legal_prefix):
    prefixes = legal_prefix if isinstance(legal_prefix, list) else [legal_prefix]
    legal = (row["legal"] or "").upper()
    if legal:
        return any(p.upper() in legal for p in prefixes)
    # Some NOTICE rows (the Clerk's own Ch.197 tax-deed filings) carry no
    # Legal field on the summary row -- confirmed live this session
    # (2026156460/68/72, all blank Legal). Do not silently drop these; the
    # caller must resolve them via instrument_detail() and party matching
    # instead of this legal-prefix shortcut.
    return None


def to_iso_date(mdy):
    try:
        m, d, y = mdy.split("/")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except Exception:
        return None


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


def already_exists(table, case_number, key_field, key_value):
    if not key_value:
        return False
    rows = sb_get(f"{table}?case_number=eq.{urllib.parse.quote(case_number)}"
                  f"&{key_field}=eq.{urllib.parse.quote(str(key_value))}&select=id&limit=1")
    return bool(rows)


def pick_sibling_rows(blank_legal_notice_rows, sibling_rank, sibling_count):
    """When N sibling cases share one owner_search, blank-Legal clerk NOTICE
    rows resolve identically for all of them (real bug hit + fixed this
    session -- see CASES comment). Group same-day rows into batches of
    `sibling_count`, sorted by (date, book, page), and keep only the row at
    position `sibling_rank` within each batch. If a batch's size does not
    divide evenly by sibling_count, ALL rows in that leftover batch are kept
    (ambiguous -> disclosed via duplication rather than silently dropped)."""
    if sibling_count <= 1:
        return blank_legal_notice_rows, False
    by_date = {}
    for r in blank_legal_notice_rows:
        by_date.setdefault(r["date"], []).append(r)
    kept, ambiguous = [], False
    for date, group in by_date.items():
        group.sort(key=lambda r: (r["book"], r["page"]))
        if len(group) % sibling_count == 0 and len(group) >= sibling_count:
            step = len(group) // sibling_count
            kept.extend(group[sibling_rank * step:(sibling_rank + 1) * step])
        else:
            kept.extend(group)  # can't cleanly split -- keep all, flag ambiguous
            ambiguous = True
    return kept, ambiguous


def classify(case_number, parcel_id, rows, legal_prefix, owner_search, sibling_rank=0, sibling_count=1):
    title_rows, lien_rows = [], []
    blank_legal_notices = []
    resolved_rows = []

    for row in rows:
        doctype = row["doctype"]
        is_clerk_notice = NOTICE_RE.search(doctype) and row["cross_party"].upper().startswith("ALVAREZ SOWLES")
        match = matches_parcel(row, legal_prefix)

        if match is None and is_clerk_notice:
            # Blank-Legal clerk NOTICE row (confirmed live: the Ch.197
            # tax-deed application/sale notice rows often carry no Legal on
            # the summary table) -- resolve via instrument_detail's real
            # party list instead of the legal-prefix shortcut.
            detail = instrument_detail(row["instrument"])
            parties = parse_parties(detail)
            names_upper = [p.upper() for p, _t in parties]
            if not any(owner_search.upper() in n or n in owner_search.upper() for n in names_upper):
                continue  # confirmed via detail lookup: not this owner/parcel
            row = dict(row, _detail=detail)
            blank_legal_notices.append(row)
            continue
        elif match is None:
            continue  # blank-legal non-notice row -- cannot confirm parcel, skip rather than guess
        elif not match:
            continue  # unrelated same-name person / different parcel

        resolved_rows.append(row)

    kept_notices, ambiguous = pick_sibling_rows(blank_legal_notices, sibling_rank, sibling_count)
    if ambiguous:
        print(f"  WARNING [{case_number}]: sibling-case notice batch did not split evenly "
              f"({sibling_count} sibling cases share owner {owner_search!r}) -- kept all rows, "
              f"cross-case duplication is possible and NOT independently verified")
    resolved_rows.extend(kept_notices)

    for row in resolved_rows:
        doctype = row["doctype"]
        is_clerk_notice = NOTICE_RE.search(doctype) and row["cross_party"].upper().startswith("ALVAREZ SOWLES")
        book_page = f"{row['book']}/{row['page']}"
        rec_date = to_iso_date(row["date"])

        if is_clerk_notice:
            # Clerk's own Notice of Application for Tax Deed / sale-adjacent
            # notice under Ch. 197 -- this case's OWN administrative filing,
            # not a third-party lien. Treated like the reference script's
            # Lis Pendens/Judgment "case filing" bucket.
            detail = row.get("_detail") or instrument_detail(row["instrument"])
            parties = parse_parties(detail)
            affected = [p for p, t in parties if t == "2"] or [row["name"]]
            sibling_note = (
                f" [sibling_disambiguation: INFERRED from same-day book/page ordering, "
                f"{sibling_count} sibling cases share owner {owner_search!r} -- not verified "
                f"against the actual document image]" if sibling_count > 1 else ""
            )
            title_rows.append({
                "case_number": case_number,
                "parcel_id": parcel_id,
                "county": "pasco",
                "rule_id": JUDGMENT_RULE_ID,
                "rule_category": "JUDGMENT",
                "rule_name": f"Notice of Application for Tax Deed ({doctype})",
                "severity": "high",
                "defect_description": (
                    f"{doctype} recorded {row['date']}, book/page {book_page}, "
                    f"instrument {row['instrument']}, legal {row['legal']!r} "
                    f"(Pasco Official Records name search on {row['name']!r} -- "
                    f"this case's own Ch.197 tax deed application/notice, listing "
                    f"interested parties: {', '.join(affected)}){sibling_note}"
                ),
                "affected_parties": affected,
                "auto_detected": True,
            })
            continue

        if JUDGMENT_RE.search(doctype):
            title_rows.append({
                "case_number": case_number,
                "parcel_id": parcel_id,
                "county": "pasco",
                "rule_id": JUDGMENT_RULE_ID,
                "rule_category": "JUDGMENT",
                "rule_name": doctype,
                "severity": "high",
                "defect_description": (
                    f"{doctype} recorded {row['date']}, book/page {book_page}, "
                    f"instrument {row['instrument']}, {row['name']} v {row['cross_party']}, "
                    f"legal {row['legal']!r} (Pasco Official Records name search)"
                ),
                "affected_parties": [p for p in (row["name"], row["cross_party"]) if p],
                "auto_detected": True,
            })
            continue

        matched_type = None
        for lien_type, pattern in LIEN_TYPE_PATTERNS:
            if pattern.search(doctype):
                matched_type = lien_type
                break
        if matched_type is None and doctype.upper() == "LIEN":
            # Real recorded LIEN doctype, but creditor is a government body
            # (confirmed via instrument-detail: Party1 = PASCO COUNTY /
            # BOARD OF COUNTY COMMISSIONERS) -- a code-enforcement lien, not
            # one of the caller's 5 taxonomy categories. Labeled honestly
            # rather than force-fit into "Tax Lien".
            matched_type = "Code Enforcement/Municipal Lien"

        if matched_type:
            lien_rows.append({
                "case_number": case_number,
                "parcel_id": parcel_id,
                "lien_type": matched_type,
                "creditor": row["cross_party"] or None,
                "recording_date": rec_date,
                "book_page": book_page,
                "priority": None,  # tax-deed sale: no foreclosed-lien priority comparison
                "source": "pasco_or_name_search",
                "raw_data": row,
            })
    return title_rows, lien_rows


def main():
    n_title = n_lien = n_dupe = 0
    for c in CASES:
        case_number, parcel_id = c["case_number"], c["parcel_id"]
        owner = c["owner_search"]
        print(f"[{case_number}] parcel={parcel_id} owner_search={owner!r}")
        html = name_search(owner)
        rows = parse_rows(html)
        if not rows:
            print(f"  0 name-search results for {owner!r}")
            continue
        matched = [r for r in rows if matches_parcel(r, c["legal_prefix"]) is True]
        unresolved = [r for r in rows if matches_parcel(r, c["legal_prefix"]) is None]
        print(f"  {len(rows)} total records for {owner!r}, {len(matched)} match legal prefix "
              f"{c['legal_prefix']!r}, {len(unresolved)} blank-legal rows need instrument-detail resolution")
        if len(rows) > 15 and len(matched) < len(rows):
            print(f"  WARNING: broad surname search ({len(rows)} rows) narrowed by legal-prefix filter -- "
                  f"may still miss liens recorded under a different name variant")

        sibling_count = SIBLING_OWNER_COUNT.get(owner, 1)
        title_rows, lien_rows = classify(case_number, parcel_id, rows, c["legal_prefix"], owner,
                                          sibling_rank=c["sibling_rank"], sibling_count=sibling_count)
        for row in title_rows:
            # multiple NOTICE rows can share rule_id -- dedupe on book_page via defect_description search instead
            existing = sb_get(
                f"title_defects?case_number=eq.{urllib.parse.quote(case_number)}"
                f"&rule_id=eq.{row['rule_id']}&select=id,defect_description")
            book_page_tag = re.search(r"book/page (\S+)", row["defect_description"]).group(1)
            if any(book_page_tag in (e.get("defect_description") or "") for e in existing):
                n_dupe += 1
                continue
            try:
                sb_insert("title_defects", row)
                n_title += 1
                print(f"  +title_defects: {row['rule_name']} book/page={book_page_tag}")
            except Exception as e:
                print(f"  title_defects insert failed: {e}")
        for row in lien_rows:
            if already_exists("lien_results", case_number, "book_page", row["book_page"]):
                n_dupe += 1
                continue
            try:
                sb_insert("lien_results", row)
                n_lien += 1
                print(f"  +lien_results: {row['lien_type']} creditor={row['creditor']} book_page={row['book_page']}")
            except Exception as e:
                print(f"  lien_results insert failed: {e}")

    print(f"\n[pasco_or_name_lien_harvest] done: +{n_title} title_defects, +{n_lien} lien_results, "
          f"{n_dupe} already on file")


if __name__ == "__main__":
    main()
