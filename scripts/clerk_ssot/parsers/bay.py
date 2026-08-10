"""Bay clerk foreclosure sales parser. Family D (PDF calendar, but a 2-column
layout that pypdf extracts as alternating *pages* rather than alternating
lines): each "left column" page holds N case numbers/dates/judgment amounts,
and the very next page holds those same N case styles (plaintiff - vs -
defendant), in matching document order. Detected live 2026-08-10: 9 case-
number pages (0,2,4,...,16) paired 1:1 with 9 case-style pages (1,3,5,...,17)
in apps.baycoclerk.com/Downloads/ForeclosureSales.pdf, 33 cases total.

tax_deed is NOT implemented here: bay.realtaxdeed.com is the only calendar
(guardrailed RealTaxDeed platform) and the county's own
records2.baycoclerk.com/TaxDeed/ search page has zero rows in static HTML --
its grid is populated by a legacy ASP.NET jQuery-tabs AJAX call
(Home/UpdateTab...) that requires session/viewstate, not a static list.
"""
import re

import httpx
from pypdf import PdfReader
from io import BytesIO

FC_URL = "https://apps.baycoclerk.com/Downloads/ForeclosureSales.pdf"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

CASE_RE = re.compile(r"\d{8}(?:CA|CC)")
VS_RE = re.compile(r"-\s*\nvs\s*-\s*\n", re.S)
SEP_RE = re.compile(r"\n\s{2,}\n")
DATETIME_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s*[AP]M")
BOILERPLATE_RE = re.compile(r"CIRCUIT CIVIL FORECLOSURE SALES.*?WILL BE LISTED", re.S)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _clean_page(text: str) -> str:
    body = BOILERPLATE_RE.sub("", text)
    body = DATETIME_RE.sub("", body)
    body = re.sub(r"^Case (Number|Style)", "", body.strip())
    return body


def _extract_cases(text: str) -> list[dict]:
    """Case-number page: 'CASENO [SALE WILL BE HELD ONLINE @ url] [ORDER
    CANCELLING SALE] MM-DD-YYYY $AMOUNT' repeated."""
    body = _clean_page(text)
    matches = list(CASE_RE.finditer(body))
    out = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[start:end]
        date_m = re.search(r"(\d{2})-(\d{2})-(\d{4})", block)
        out.append({
            "case_number": m.group(0),
            "sale_date": f"{date_m.group(3)}-{date_m.group(1)}-{date_m.group(2)}" if date_m else None,
            "cancelled": "CANCEL" in block.upper(),
        })
    return out


def _extract_titles(text: str) -> list[tuple[str, str]]:
    """Case-style page: 'PLAINTIFF - vs - DEFENDANT' repeated, each entity
    block delimited by a blank-ish '\\n  \\n' separator on both sides."""
    body = _clean_page(text)
    parts = VS_RE.split(body)
    if len(parts) < 2:
        return []

    names = []
    first = re.sub(r"^\n\s{2,}\n", "", parts[0])
    names.append(_norm(SEP_RE.split(first)[0]))
    for mid in parts[1:-1]:
        sub = SEP_RE.split(mid)
        names.append(_norm(sub[0]))  # defendant
        names.append(_norm(sub[1]) if len(sub) > 1 else "")  # next plaintiff
    names.append(_norm(parts[-1]))  # last defendant

    return [(names[i], names[i + 1]) for i in range(0, len(names) - 1, 2)]


def parse_foreclosure() -> list[dict]:
    resp = httpx.get(FC_URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    reader = PdfReader(BytesIO(resp.content))
    page_texts = [page.extract_text() for page in reader.pages]
    if not any(page_texts):
        raise RuntimeError("bay foreclosure: PDF has no extractable text — likely a scanned image")

    rows = []
    pending_cases: list[dict] | None = None
    for text in page_texts:
        n_cases = len(CASE_RE.findall(text))
        n_vs = len(VS_RE.findall(text))
        if n_cases > n_vs and n_cases > 0:
            pending_cases = _extract_cases(text)
        elif n_vs > 0 and pending_cases is not None:
            titles = _extract_titles(text)
            for case, (plaintiff, defendant) in zip(pending_cases, titles):
                rows.append({
                    "county_slug": "bay",
                    "sale_type": "foreclosure",
                    "case_number": case["case_number"],
                    "sale_date": case["sale_date"],
                    "cancelled": case["cancelled"],
                    "raw_comment": "CANCELLED" if case["cancelled"] else "",
                    "case_title": f"{plaintiff} VS {defendant}",
                    "source_url": FC_URL,
                })
            pending_cases = None

    if not rows:
        raise RuntimeError("bay foreclosure: parsed 0 rows from a 200 response — treat as FAILURE, not an empty calendar")
    return rows


if __name__ == "__main__":
    import json
    data = parse_foreclosure()
    cancelled = sum(1 for r in data if r["cancelled"])
    print(f"parsed {len(data)} rows, {cancelled} cancelled")
    print(json.dumps(data[:2], indent=2))
