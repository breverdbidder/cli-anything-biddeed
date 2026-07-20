"""Marion County Property Appraiser enrichment via pa.marion.fl.us PRC.aspx.

Additive companion to enrichment.py (BCPAO/Brevard) — does not import from
or modify that module. Marion has no JSON API; the "Property Record Card"
(PRC.aspx) is a server-rendered ASP.NET page keyed by the same parcel ID
RealForeclose's Parcel ID column already links to via
`pa.marion.fl.us/PRC.aspx?key=<parcel>&YR=<year>&mName=False&mSitus=False`.

No auth required. Public records.
"""

import re
import time
import urllib.request
from typing import Optional

MCPA_PRC_URL = "http://www.pa.marion.fl.us/PRC.aspx"
RATE_LIMIT_SECS = 1.0

_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
}

_CERT_VALUE_LABELS = (
    "Land Just Value", "Buildings", "Miscellaneous", "Total Just Value",
    "Total Assessed Value", "Exemptions", "Total Taxable", "School Taxable",
)
_BLDG_CHAR_LABELS = ("Improvement", "Effective Age", "Condition", "Quality Grade", "Inspected on")
_TRANSFER_LABELS = ("Book/Page", "Date", "Instrument", "Code", "Q/U", "V/I", "Price")
_BUILDING_ROW_LABELS = (
    "Type", "ID", "Exterior Walls", "Stories", "Year Built", "Finished Attic",
    "Bsmt Area", "Bsmt Finish", "Ground Floor Area", "Total Flr Area",
)


def fetch_prc_html(parcel_key: str, year: Optional[int] = None) -> Optional[str]:
    """Fetch the raw PRC.aspx HTML for a parcel key. Returns None on failure."""
    if not parcel_key:
        return None
    params = f"key={parcel_key}"
    if year:
        params += f"&YR={year}"
    params += "&mName=False&mSitus=False"
    req = urllib.request.Request(f"{MCPA_PRC_URL}?{params}", headers=_HTTP_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                return None
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _segments(html: str) -> list[str]:
    """Strip scripts/styles/tags to a flat list of non-empty visible text segments."""
    text = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    plain = re.sub(r"<[^>]+>", "|", text)
    plain = re.sub(r"\|+", "|", plain)
    plain = plain.replace("&nbsp;", " ").replace("&amp;", "&")
    return [s.strip() for s in plain.split("|") if s.strip()]


def _find(segs: list[str], label: str) -> Optional[int]:
    for i, s in enumerate(segs):
        if s == label:
            return i
    return None


def _value_after(segs: list[str], label: str) -> Optional[str]:
    i = _find(segs, label)
    return segs[i + 1] if i is not None and i + 1 < len(segs) else None


def _label_block(segs: list[str], start_idx: int, candidates: tuple) -> list[str]:
    """Collect a contiguous run of segments (from start_idx) that are all in `candidates`."""
    out = []
    i = start_idx
    while i < len(segs) and segs[i] in candidates:
        out.append(segs[i])
        i += 1
    return out


def _to_float(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    neg = s.strip().startswith("(") and s.strip().endswith(")")
    clean = re.sub(r"[^\d.]", "", s)
    if not clean:
        return None
    try:
        v = float(clean)
        return -v if neg else v
    except ValueError:
        return None


def parse_prc(html: str) -> dict:
    """Parse a PRC.aspx page into a normalized enrichment dict.

    Every key defaults to None if not found — callers write None as NULL,
    never a fabricated 0/empty string for a missing field.
    """
    segs = _segments(html)
    out = {
        "owner_name": None, "property_address": None, "lot_size": None,
        "market_value": None, "assessed_value": None, "homestead_status": None,
        "legal_description": None, "property_type": None,
        "bedrooms": None, "bathrooms": None, "year_built": None,
        "living_area_sqft": None, "prior_sale_date": None, "prior_sale_price": None,
        "photo_url": None,
    }

    # Owner name + mailing address: segments between "Property Information" and
    # "Taxes / Assessments:". First segment may be a "More Names" link — skip it.
    pi = _find(segs, "Property Information")
    ta = _find(segs, "Taxes / Assessments:")
    if pi is not None and ta is not None and ta > pi:
        block = [s for s in segs[pi + 1:ta] if s != "More Names"]
        if block:
            out["owner_name"] = block[0]

    # Situs address
    for s in segs:
        if s.startswith("Situs:"):
            out["property_address"] = s[len("Situs:"):].strip()
            break

    # Lot size (acres)
    for s in segs:
        if s.startswith("Acres:"):
            out["lot_size"] = _to_float(s[len("Acres:"):])
            break

    # Certified value block: Land Just Value / Buildings / Misc / Total Just Value /
    # Total Assessed Value / Exemptions / Total Taxable [/ School Taxable]
    ljv = _find(segs, "Land Just Value")
    if ljv is not None:
        labels = _label_block(segs, ljv, _CERT_VALUE_LABELS)
        n = len(labels)
        values = segs[ljv + n: ljv + 2 * n]
        if len(values) == n:
            valmap = dict(zip(labels, values))
            out["market_value"] = _to_float(valmap.get("Total Just Value"))
            out["assessed_value"] = _to_float(valmap.get("Total Assessed Value"))
            exemptions = _to_float(valmap.get("Exemptions"))
            out["homestead_status"] = "homestead" if exemptions and exemptions != 0 else "non-homestead"

    # Legal description
    pd = _find(segs, "Property Description")
    ld = _find(segs, "Land Data - Warning: Verify Zoning")
    if pd is not None and ld is not None and ld > pd:
        block = segs[pd + 1: ld]
        # Drop a trailing "Parent Parcel:" label + its value if present
        if len(block) >= 2 and block[-2] == "Parent Parcel:":
            block = block[:-2]
        out["legal_description"] = " ".join(block).strip() or None

    # Building characteristics: Improvement description = property type
    imp = _find(segs, "Improvement")
    if imp is not None:
        labels = _label_block(segs, imp, _BLDG_CHAR_LABELS)
        n = len(labels)
        values = segs[imp + n: imp + 2 * n]
        if len(values) == n and labels and labels[0] == "Improvement":
            out["property_type"] = values[0]

    # Year built (first occurrence — top-level building summary)
    yb = _value_after(segs, "Year Built")
    if yb and yb.isdigit():
        out["year_built"] = int(yb)

    # Living area — main building's "Total Flr Area" column, from the first
    # building-characteristics row (Type/ID/.../Ground Floor Area/Total Flr Area).
    # "Type" alone also appears in the unrelated Land Data table, so anchor on
    # "Type" immediately followed by "ID" to find the real header row.
    for i in range(len(segs) - 1):
        if segs[i] == "Type" and segs[i + 1] == "ID":
            labels = _label_block(segs, i, _BUILDING_ROW_LABELS)
            n = len(labels)
            values = segs[i + n: i + 2 * n]
            if len(values) == n and labels[-1] == "Total Flr Area":
                v = _to_float(values[-1])
                out["living_area_sqft"] = int(v) if v is not None else None
            break

    # Bedrooms / bathrooms (4-fixture + 3-fixture full baths; 2-fixture = half bath)
    beds = _value_after(segs, "Bedrooms:")
    if beds and beds.lstrip("-").isdigit():
        out["bedrooms"] = int(beds)
    b4 = _to_float(_value_after(segs, "4 Fixture Baths:")) or 0
    b3 = _to_float(_value_after(segs, "3 Fixture Baths:")) or 0
    b2 = _to_float(_value_after(segs, "2 Fixture Baths:")) or 0
    if any(v is not None for v in (
        _value_after(segs, "4 Fixture Baths:"),
        _value_after(segs, "3 Fixture Baths:"),
        _value_after(segs, "2 Fixture Baths:"),
    )):
        out["bathrooms"] = b4 + b3 + 0.5 * b2

    # Most recent transfer (Property Transfer History is sorted newest-first)
    bp = _find(segs, "Book/Page")
    if bp is not None:
        labels = _label_block(segs, bp, _TRANSFER_LABELS)
        n = len(labels)
        row = segs[bp + n: bp + 2 * n]
        if len(row) == n:
            rowmap = dict(zip(labels, row))
            date_raw = rowmap.get("Date")  # MM/YYYY — no day published
            if date_raw and re.match(r"^\d{2}/\d{4}$", date_raw):
                mm, yyyy = date_raw.split("/")
                out["prior_sale_date"] = f"{yyyy}-{mm}-01"
            out["prior_sale_price"] = _to_float(rowmap.get("Price"))

    # No parcel photo is published on PRC.aspx (verified: only office branding
    # images / UI icons present in the raw HTML) — photo_url stays None.

    return out


def enrich_parcel(parcel_key: str, year: Optional[int] = None) -> dict:
    """Fetch + parse a single Marion parcel. Rate-limited by caller between calls."""
    html = fetch_prc_html(parcel_key, year=year)
    if not html:
        return {"error": "fetch_failed"}
    return parse_prc(html)


def enrich_parcels(parcel_keys: list[str], year: Optional[int] = None) -> dict[str, dict]:
    """Enrich multiple parcels, rate-limited RATE_LIMIT_SECS apart."""
    results = {}
    for i, key in enumerate(parcel_keys):
        if i > 0:
            time.sleep(RATE_LIMIT_SECS)
        results[key] = enrich_parcel(key, year=year)
    return results
