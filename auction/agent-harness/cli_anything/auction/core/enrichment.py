"""Property enrichment via BCPAO API and AcclaimWeb.

For each RealForeclose case stub, this module:
  1. Queries AcclaimWeb to extract property address (best-effort)
  2. Queries BCPAO API to get just_value, sqft, year_built, bedrooms, bathrooms
  3. Returns enriched case dicts ready for ARV analysis

Both sources are public — no auth required.
SSL: verify=False required for both endpoints.
"""

import re
import time
import warnings
from html.parser import HTMLParser
from typing import Optional

import httpx


BCPAO_API = "https://www.bcpao.us/api/v1/search"
ACCLAIMWEB_BASE = "https://vaclmweb1.brevardclerk.us/AcclaimWeb"
RATE_LIMIT_SECS = 0.5  # seconds between BCPAO requests

_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/html, */*",
}


# ── AcclaimWeb case detail parser ─────────────────────────────────────


class _AcclaimDetailParser(HTMLParser):
    """Extract property address from AcclaimWeb civil case detail page."""

    def __init__(self):
        super().__init__()
        self.text_blocks: list[str] = []
        self.in_body = False
        self._current = ""

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.in_body = True

    def handle_endtag(self, tag):
        if tag in ("td", "th", "div", "span", "p", "li") and self._current.strip():
            self.text_blocks.append(self._current.strip())
            self._current = ""

    def handle_data(self, data):
        if self.in_body:
            self._current += data

    def find_address(self) -> str:
        """Heuristic: FL address pattern in extracted text blocks."""
        fl_pattern = re.compile(
            r"\d+\s+[\w\s]+(?:Ave|St|Dr|Blvd|Rd|Ln|Way|Ct|Pl|Cir|Terr?)\s*[,.]?\s*"
            r"[\w\s]+,\s*FL\s+\d{5}",
            re.IGNORECASE,
        )
        for block in self.text_blocks:
            m = fl_pattern.search(block)
            if m:
                return m.group(0).strip()
        return ""


def _fetch_acclaimweb_address(case_number: str, retries: int = 3) -> str:
    """Try to extract a FL property address from AcclaimWeb case detail."""
    # Brevard civil case number format: YYYY-CA-XXXXXX → normalize
    cn = case_number.strip().upper()
    url = f"{ACCLAIMWEB_BASE}/Details/CivilDetail"
    params = {"CaseNumber": cn}

    for attempt in range(retries):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                resp = httpx.get(
                    url,
                    params=params,
                    headers=_HTTP_HEADERS,
                    verify=False,
                    timeout=15,
                    follow_redirects=True,
                )
            if resp.status_code == 200:
                parser = _AcclaimDetailParser()
                parser.feed(resp.text)
                addr = parser.find_address()
                if addr:
                    return addr
            return ""
        except Exception:
            if attempt < retries - 1:
                time.sleep(1.5 ** attempt)
    return ""


# ── BCPAO API ─────────────────────────────────────────────────────────


def _query_bcpao_by_address(address: str) -> Optional[dict]:
    """Query BCPAO API by street address. Returns first result dict or None."""
    if not address:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            resp = httpx.get(
                BCPAO_API,
                params={"address": address},
                headers=_HTTP_HEADERS,
                verify=False,
                timeout=15,
            )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return _extract_bcpao_record(data)
    except Exception:
        return None


def _query_bcpao_by_account(parcel_id: str) -> Optional[dict]:
    """Query BCPAO API by parcel account number. Returns record dict or None."""
    if not parcel_id:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            resp = httpx.get(
                BCPAO_API,
                params={"acct": parcel_id},
                headers=_HTTP_HEADERS,
                verify=False,
                timeout=15,
            )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return _extract_bcpao_record(data)
    except Exception:
        return None


def _extract_bcpao_record(data: dict) -> Optional[dict]:
    """Normalize BCPAO API response to a flat property dict."""
    # BCPAO may return {"results": [...]} or {"PropertyList": [...]} or a list
    records = None
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = (
            data.get("results")
            or data.get("PropertyList")
            or data.get("propertyList")
            or data.get("data")
        )

    if not records:
        return None

    rec = records[0] if isinstance(records, list) and records else records
    if not isinstance(rec, dict):
        return None

    # Normalize field names — BCPAO API uses camelCase or snake_case
    def get(*keys):
        for k in keys:
            v = rec.get(k)
            if v is not None:
                return v
        return None

    just_value = get("justValue", "just_value", "JustValue", "assessedValue", "marketValue")
    if just_value is not None:
        try:
            just_value = float(str(just_value).replace(",", "").replace("$", ""))
        except (ValueError, TypeError):
            just_value = None

    return {
        "parcel_id": get("account", "Account", "parcelId", "parcel_id", "AccountNumber"),
        "address": get("address", "Address", "siteAddress", "site_address"),
        "just_value": just_value,
        "sqft": get("sqft", "livingArea", "LivingArea", "living_area", "area"),
        "year_built": get("yearBuilt", "year_built", "YearBuilt"),
        "bedrooms": get("bedrooms", "Bedrooms", "beds"),
        "bathrooms": get("bathrooms", "Bathrooms", "baths"),
        "photo_url": get("photoURL", "photo_url", "PhotoURL", "imageUrl"),
        "property_class": get("propertyClass", "property_class", "classCode"),
    }


# ── Public API ────────────────────────────────────────────────────────


def enrich_case(case: dict) -> dict:
    """Add BCPAO property data to a single case stub.

    Enrichment strategy:
    1. Use address from case if already present
    2. Otherwise fetch from AcclaimWeb by case number (best-effort)
    3. Query BCPAO by address → get just_value, sqft, year_built, etc.

    Returns the original case dict with bcpao_* fields added.
    """
    enriched = dict(case)
    address = case.get("address", "").strip()

    if not address:
        address = _fetch_acclaimweb_address(case.get("case_number", ""))
        if address:
            enriched["address"] = address

    if not address:
        enriched["bcpao_error"] = "no_address"
        return enriched

    time.sleep(RATE_LIMIT_SECS)
    bcpao = _query_bcpao_by_address(address)

    if bcpao:
        enriched["parcel_id"] = bcpao.get("parcel_id") or ""
        enriched["just_value"] = bcpao.get("just_value")
        enriched["sqft"] = bcpao.get("sqft")
        enriched["year_built"] = bcpao.get("year_built")
        enriched["bedrooms"] = bcpao.get("bedrooms")
        enriched["bathrooms"] = bcpao.get("bathrooms")
        enriched["photo_url"] = bcpao.get("photo_url") or ""
        enriched["bcpao_source"] = "api"
        # Override address with canonical BCPAO address if available
        if bcpao.get("address"):
            enriched["address"] = bcpao["address"]
    else:
        enriched["bcpao_error"] = "api_no_result"

    return enriched


def enrich_cases(cases: list[dict]) -> list[dict]:
    """Enrich a list of case stubs with BCPAO data.

    Rate-limited: 0.5s between requests (BCPAO allows ~2 req/sec).
    Enrichment failures are non-fatal — case returned as-is with bcpao_error field.
    """
    return [enrich_case(case) for case in cases]
