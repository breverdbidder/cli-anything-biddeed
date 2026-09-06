#!/usr/bin/env python3
"""Fail-closed adapter for county Clerk public-sale pages.

The adapter intentionally refuses to infer records from prose. It accepts only
HTML tables or JSON-LD records containing a sale date plus a case/parcel
identity. Amounts are typed by sale type and retain source URL/provenance in
existing realforeclose_aids-compatible fields.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html as html_lib
import json
import os
import re
import sys
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path

from bs4 import BeautifulSoup

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
UA = "BidDeedCalendarBot/1.0 (+https://biddeed.ai; public-record-refresh)"
MONEY = re.compile(r"(?:\$\s*)?([0-9][0-9,]*(?:\.\d{1,2})?)")
DATE_PATTERNS = ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%B %d, %Y", "%b %d, %Y %I:%M %p", "%b %d, %Y")


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def parse_date(value: str) -> dt.date | None:
    value = clean(value)
    if "T" in value:
        value = value.split("T", 1)[0]
    for fmt in DATE_PATTERNS:
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", value)
    if match:
        month, day, year = map(int, match.groups())
        if year < 100:
            year += 2000
        try:
            return dt.date(year, month, day)
        except ValueError:
            return None
    return None


def parse_money(value: str | None) -> Decimal | None:
    if not value:
        return None
    match = MONEY.search(value.replace(" ", ""))
    if not match:
        return None
    try:
        return Decimal(match.group(1).replace(",", ""))
    except InvalidOperation:
        return None


def fetch(url: str) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/pdf"})
    with urllib.request.urlopen(request, timeout=35) as response:
        raw = response.read()
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "pdf" in content_type or url.lower().split("?")[0].endswith(".pdf"):
            converted = subprocess.run(["pdftotext", "-layout", "-", "-"], input=raw, capture_output=True, timeout=20, check=False)
            body = converted.stdout.decode("utf-8", errors="replace")
        else:
            body = raw.decode("utf-8", errors="replace")
        return str(response.status), body


def same_host_links(url: str, html: str, limit: int = 20) -> list[str]:
    base = urllib.parse.urlparse(url)
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    seen = {url}
    for tag in soup.find_all("a", href=True):
        candidate = urllib.parse.urljoin(url, tag["href"])
        parsed = urllib.parse.urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != base.netloc:
            continue
        if candidate in seen or candidate.lower().split("?")[0].endswith((".jpg", ".png", ".css", ".js")):
            continue
        seen.add(candidate)
        links.append(candidate)
        if len(links) >= limit:
            break
    return links


def parse_structured_rows(url: str, html: str, county: str, sale_type: str, start: dt.date, end: dt.date) -> tuple[list[dict], list[dict]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    evidence: list[dict] = []

    # Accept only explicit JSON-LD records with a date and identity; prose remains non-authoritative.
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.string or script.get_text())
        except (TypeError, json.JSONDecodeError):
            continue
        items = payload if isinstance(payload, list) else payload.get("itemListElement", []) if isinstance(payload, dict) else []
        for item in items:
            item = item.get("item", item) if isinstance(item, dict) else {}
            if not isinstance(item, dict):
                continue
            date_text = item.get("startDate") or item.get("date") or item.get("eventDate")
            sale_date = parse_date(str(date_text or ""))
            identity = item.get("identifier") or item.get("caseNumber") or item.get("parcelNumber") or item.get("url")
            if not sale_date or not identity or not (start <= sale_date <= end):
                continue
            amount = parse_money(str(item.get("price") or item.get("openingBid") or item.get("amount") or ""))
            aid = hashlib.sha256(f"{county}|{sale_type}|{identity}|{sale_date.isoformat()}".encode()).hexdigest()[:40]
            rows.append({"aid": aid, "county_slug": county, "auction_type": sale_type, "case_number": str(identity), "judgment_amount": float(amount) if amount is not None else None, "auction_starts_at": f"{sale_date.isoformat()}T00:00:00+00:00", "auction_starts_raw": str(date_text), "county_subdomain": "clerk-public-jsonld", "case_clerk_url": url, "source_response_id": None, "first_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "last_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "refresh_count": 1})
            evidence.append({"url": url, "sale_type": sale_type, "identity": str(identity), "sale_date": sale_date.isoformat(), "amount_present": amount is not None, "format": "json-ld"})

    page_text = clean(soup.get_text(" ", strip=True)).lower()
    if not rows and any(marker in page_text for marker in ("no properties currently", "no properties are currently", "no properties available for sale")):
        evidence.append({"url": url, "sale_type": sale_type, "authoritative_zero_candidate": True, "reason": "official page states no properties available"})

    for table in soup.find_all("table"):
        headers = [key(clean(x.get_text(" ", strip=True))) for x in table.find_all("th")]
        if not headers:
            first = table.find("tr")
            headers = [key(clean(x.get_text(" ", strip=True))) for x in (first.find_all(["td", "th"]) if first else [])]
        if not headers:
            continue
        for tr in table.find_all("tr")[1:]:
            cells = [clean(x.get_text(" ", strip=True)) for x in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            record = dict(zip(headers, cells))
            date_text = next((record.get(k) for k in ("auction_date", "sale_date", "date", "sale", "auction") if record.get(k)), None)
            sale_date = parse_date(date_text or "")
            if not sale_date or not (start <= sale_date <= end):
                continue
            identity = next((record.get(k) for k in ("case_number", "case", "case_no", "parcel_id", "parcel", "account", "folio") if record.get(k)), None)
            if not identity:
                continue
            amount_text = next((record.get(k) for k in ("judgment_amount", "final_judgment", "opening_bid", "minimum_bid", "amount", "sale_amount", "bid") if record.get(k)), None)
            amount = parse_money(amount_text)
            aid = hashlib.sha256(f"{county}|{sale_type}|{identity}|{sale_date.isoformat()}".encode()).hexdigest()[:40]
            rows.append({
                "aid": aid,
                "county_slug": county,
                "auction_type": sale_type,
                "case_number": identity,
                "judgment_amount": float(amount) if amount is not None else None,
                "auction_starts_at": f"{sale_date.isoformat()}T00:00:00+00:00",
                "auction_starts_raw": date_text,
                "county_subdomain": "clerk-public",
                "case_clerk_url": url,
                "source_response_id": None,
                "first_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "last_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "refresh_count": 1,
            })
            evidence.append({"url": url, "sale_type": sale_type, "identity": identity, "sale_date": sale_date.isoformat(), "amount_present": amount is not None})
    return rows, evidence


def parse_pdf_listing_rows(url: str, text: str, county: str, sale_type: str, start: dt.date, end: dt.date) -> tuple[list[dict], list[dict]]:
    """Parse dated official PDF listing lines with an explicit case identity.

    This accepts only lines beginning with a sale date and a case-number-like
    identity. It intentionally leaves amount fields null when the authority
    does not publish an amount in the schedule.
    """
    rows: list[dict] = []
    evidence: list[dict] = []
    for raw_line in text.splitlines():
        line = clean(raw_line)
        match = re.match(r"^(\d{1,2}/\d{1,2}/\d{2,4})\s+((?:\d{4}\s+)?[A-Z]{1,4}\s+\d{3,8})\b(?:\s+(.*))?$", line, flags=re.I)
        if not match:
            continue
        sale_date = parse_date(match.group(1))
        if not sale_date or not (start <= sale_date <= end):
            continue
        identity = clean(match.group(2))
        aid = hashlib.sha256(f"{county}|{sale_type}|{identity}|{sale_date.isoformat()}".encode()).hexdigest()[:40]
        rows.append({"aid": aid, "county_slug": county, "auction_type": sale_type, "case_number": identity, "judgment_amount": None, "auction_starts_at": f"{sale_date.isoformat()}T00:00:00+00:00", "auction_starts_raw": match.group(1), "county_subdomain": "clerk-public-pdf", "case_clerk_url": url, "source_response_id": None, "first_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "last_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "refresh_count": 1})
        evidence.append({"url": url, "sale_type": sale_type, "identity": identity, "sale_date": sale_date.isoformat(), "amount_present": False, "format": "pdf-line"})
    return rows, evidence


def parse_explicit_prose_rows(url: str, html: str, county: str, sale_type: str, start: dt.date, end: dt.date) -> tuple[list[dict], list[dict]]:
    """Parse only explicit labeled sale blocks, not arbitrary prose.

    This contract is intentionally narrow for Clerk pages such as Hamilton:
    DATE OF SALE + Case No. + optional Judgment amount. It refuses a row when
    either the sale date or case identity is absent.
    """
    text = clean(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))
    blocks = re.split(r"(?=DATE\s+OF\s+SALE\s*[–-])", text, flags=re.I)
    rows: list[dict] = []
    evidence: list[dict] = []
    for block in blocks:
        date_match = re.search(r"DATE\s+OF\s+SALE\s*[–-]\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", block, flags=re.I)
        case_match = re.search(r"Case\s+No\.?\s*[:#-]?\s*([A-Z0-9-]+)", block, flags=re.I)
        if not date_match or not case_match:
            continue
        sale_date = parse_date(date_match.group(1))
        if not sale_date or not (start <= sale_date <= end):
            continue
        identity = case_match.group(1).strip()
        amount_match = re.search(r"(?:Judgment\s+amount|Opening\s+bid)\s*[:$]?\s*([$0-9,]+(?:\.\d{1,2})?)", block, flags=re.I)
        amount = parse_money(amount_match.group(1) if amount_match else None)
        aid = hashlib.sha256(f"{county}|{sale_type}|{identity}|{sale_date.isoformat()}".encode()).hexdigest()[:40]
        rows.append({"aid": aid, "county_slug": county, "auction_type": sale_type, "case_number": identity, "judgment_amount": float(amount) if amount is not None else None, "auction_starts_at": f"{sale_date.isoformat()}T00:00:00+00:00", "auction_starts_raw": date_match.group(1), "county_subdomain": "clerk-public-prose", "case_clerk_url": url, "source_response_id": None, "first_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "last_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "refresh_count": 1})
        evidence.append({"url": url, "sale_type": sale_type, "identity": identity, "sale_date": sale_date.isoformat(), "amount_present": amount is not None, "format": "labeled-clerk-prose"})
    return rows, evidence


def parse_sarasota_calendar_rows(url: str, html: str, county: str, start: dt.date, end: dt.date) -> tuple[list[dict], list[dict]]:
    """Parse Sarasota's public RealTaxDeed calendar event blocks.

    The official calendar exposes a sale date, sale type, scheduled-count text,
    and time but no case/parcel identity. Each event is therefore represented
    by a deterministic source-event identity derived only from the official
    calendar date and sale type; amounts remain null and provenance retains the
    calendar URL. This avoids inventing case numbers or judgment amounts.
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    evidence: list[dict] = []
    for event in soup.select("div.CALBOX[dayid]"):
        dayid = clean(event.get("dayid"))
        sale_date = parse_date(dayid)
        text = clean(event.get_text(" ", strip=True))
        if not sale_date or not (start <= sale_date <= end) or "tax deed" not in text.lower():
            continue
        count_match = re.search(r"(\\d+)\\s*/\\s*(\\d+)\\s*TD", text, flags=re.I)
        scheduled_count = int(count_match.group(2)) if count_match else 1
        identity = f"CALENDAR-TD-{sale_date.isoformat()}"
        aid = hashlib.sha256(f"{county}|tax_deed|{identity}".encode()).hexdigest()[:40]
        rows.append({"aid": aid, "county_slug": county, "auction_type": "tax_deed", "case_number": identity, "judgment_amount": None, "auction_starts_at": f"{sale_date.isoformat()}T09:00:00+00:00", "auction_starts_raw": text, "county_subdomain": "sarasota-realtaxdeed-calendar", "case_clerk_url": url, "source_response_id": None, "first_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "last_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "refresh_count": 1})
        evidence.append({"url": url, "sale_type": "tax_deed", "identity": identity, "sale_date": sale_date.isoformat(), "scheduled_count": scheduled_count, "amount_present": False, "format": "sarasota-realtaxdeed-calendar"})
    return rows, evidence


def parse_status_sale_rows(url: str, html: str, county: str, sale_type: str, start: dt.date, end: dt.date) -> tuple[list[dict], list[dict]]:
    """Parse explicit Clerk blocks labeled Status, Sale Date, Case Number.

    Union County publishes future foreclosure records in this compact labeled
    format. The parser requires a scheduled status, a parseable sale date, a
    case number, and stays within the requested window.
    """
    text = clean(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))
    blocks = re.split(r"(?=Status\s+scheduled\b)", text, flags=re.I)
    rows: list[dict] = []
    evidence: list[dict] = []
    for block in blocks:
        if not re.match(r"Status\s+scheduled\b", block, flags=re.I):
            continue
        date_match = re.search(r"Sale\s+Date\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})", block, flags=re.I)
        case_match = re.search(r"Case\s+Number\s+([A-Z0-9-]+)", block, flags=re.I)
        if not date_match or not case_match:
            continue
        sale_date = parse_date(date_match.group(1))
        if not sale_date or not (start <= sale_date <= end):
            continue
        identity = case_match.group(1).strip()
        amount_match = re.search(r"Judgment\s+Amount\s+([$0-9,]+(?:\.\d{1,2})?)", block, flags=re.I)
        amount = parse_money(amount_match.group(1) if amount_match else None)
        aid = hashlib.sha256(f"{county}|{sale_type}|{identity}|{sale_date.isoformat()}".encode()).hexdigest()[:40]
        rows.append({"aid": aid, "county_slug": county, "auction_type": sale_type, "case_number": identity, "judgment_amount": float(amount) if amount is not None else None, "auction_starts_at": f"{sale_date.isoformat()}T00:00:00+00:00", "auction_starts_raw": date_match.group(1), "county_subdomain": "clerk-public-status", "case_clerk_url": url, "source_response_id": None, "first_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "last_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "refresh_count": 1})
        evidence.append({"url": url, "sale_type": sale_type, "identity": identity, "sale_date": sale_date.isoformat(), "amount_present": amount is not None, "format": "status-sale-block"})
    return rows, evidence


def parse_lafayette_taxdeed_cards(url: str, html: str, county: str, start: dt.date, end: dt.date) -> tuple[list[dict], list[dict]]:
    """Parse Lafayette's official scheduled tax-deed cards.

    The Clerk publishes repeated labeled cards rather than an HTML table. A
    certificate number or parcel ID is used as the public-record identity;
    the page does not publish a judgment amount, so that field remains null.
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    evidence: list[dict] = []
    tag = soup.find("tax-deed-sales")
    raw_payload = tag.get(":taxdeeds") if tag else None
    if raw_payload:
        try:
            payload = json.loads(html_lib.unescape(raw_payload))
        except json.JSONDecodeError:
            payload = []
        for item in payload if isinstance(payload, list) else []:
            if str(item.get("status", "")).lower() != "scheduled":
                continue
            sale_date = parse_date(str(item.get("sale_date", "")))
            identity = clean(str(item.get("cert") or item.get("parcel") or ""))
            if not sale_date or not identity or not (start <= sale_date <= end):
                continue
            aid = hashlib.sha256(f"{county}|tax_deed|{identity}|{sale_date.isoformat()}".encode()).hexdigest()[:40]
            rows.append({"aid": aid, "county_slug": county, "auction_type": "tax_deed", "case_number": identity, "judgment_amount": None, "auction_starts_at": f"{sale_date.isoformat()}T00:00:00+00:00", "auction_starts_raw": str(item.get("sale_date")), "county_subdomain": "lafayette-clerk-vue", "case_clerk_url": str(item.get("link") or url), "source_response_id": str(item.get("ID")) if str(item.get("ID", "")).isdigit() else None, "first_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "last_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "refresh_count": 1})
            evidence.append({"url": url, "sale_type": "tax_deed", "identity": identity, "sale_date": sale_date.isoformat(), "parcel_id": item.get("parcel"), "certificate": item.get("cert"), "amount_present": False, "format": "lafayette-vue-taxdeeds"})
        if rows:
            return rows, evidence
    text = clean(soup.get_text(" ", strip=True))
    blocks = re.split(r"(?=Status\s+scheduled\b)", text, flags=re.I)
    for block in blocks:
        if not re.match(r"Status\s+scheduled\b", block, flags=re.I):
            continue
        date_match = re.search(r"Sale\s+Date\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})", block, flags=re.I)
        cert_match = re.search(r"Cert\s*#\s*([A-Z0-9-]+)", block, flags=re.I)
        parcel_match = re.search(r"Parcel\s+ID\s+([A-Z0-9-]+)", block, flags=re.I)
        if not date_match or not (cert_match or parcel_match):
            continue
        sale_date = parse_date(date_match.group(1))
        if not sale_date or not (start <= sale_date <= end):
            continue
        identity = clean((cert_match.group(1) if cert_match else parcel_match.group(1)))
        aid = hashlib.sha256(f"{county}|tax_deed|{identity}|{sale_date.isoformat()}".encode()).hexdigest()[:40]
        rows.append({"aid": aid, "county_slug": county, "auction_type": "tax_deed", "case_number": identity, "judgment_amount": None, "auction_starts_at": f"{sale_date.isoformat()}T00:00:00+00:00", "auction_starts_raw": date_match.group(1), "county_subdomain": "lafayette-clerk-cards", "case_clerk_url": url, "source_response_id": parcel_match.group(1) if parcel_match else identity, "first_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "last_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "refresh_count": 1})
        evidence.append({"url": url, "sale_type": "tax_deed", "identity": identity, "sale_date": sale_date.isoformat(), "parcel_id": parcel_match.group(1) if parcel_match else None, "certificate": cert_match.group(1) if cert_match else None, "amount_present": False, "format": "lafayette-scheduled-card"})
    return rows, evidence


def parse_charlotte_taxdeed_rows(county: str, start: dt.date, end: dt.date) -> tuple[list[dict], list[dict], str]:
    """Fetch Charlotte's official public tax-deed search JSON contract.

    The portal requires a same-origin antiforgery token and accepts a bounded
    sale-date query. BaseBid is retained only as source evidence; it is not
    promoted to judgment_amount because it is a tax-deed bid field.
    """
    page_url = "https://taxdeeds.charlotteclerk.com/TaxDeed/Search"
    endpoint = "https://taxdeeds.charlotteclerk.com/TaxDeed/GetTaxDeedView"
    jar = urllib.request.HTTPCookieProcessor()
    opener = urllib.request.build_opener(jar)
    headers = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/json"}
    page_request = urllib.request.Request(page_url, headers=headers)
    with opener.open(page_request, timeout=35) as response:
        page_html = response.read().decode("utf-8", errors="replace")
    token_match = re.search(r'name=["\\\']__RequestVerificationToken["\\\'][^>]*value=["\\\']([^"\\\']+)', page_html, flags=re.I)
    if not token_match:
        token_match = re.search(r'value=["\\\']([^"\\\']+)["\\\'][^>]*name=["\\\']__RequestVerificationToken["\\\']', page_html, flags=re.I)
    if not token_match:
        raise RuntimeError("Charlotte TaxDeed Search antiforgery token not found")
    today = dt.date.today().isoformat()
    form = {
        "__RequestVerificationToken": token_match.group(1),
        "inSearchBy": "BySaleDate",
        "inFromSaleDate": start.strftime("%m/%d/%Y"),
        "inToSaleDate": end.strftime("%m/%d/%Y"),
        "inCertificate": "", "inCaseNumber": "", "inParcelId": "", "inApplicant": "",
        "inFromSaleDateApplicant": "01/01/1977", "inToSaleDateApplicant": today,
        "inOwner": "", "inFromSaleDateOwner": "01/01/1977", "inToSaleDateOwner": today,
        "inStatus": "", "inFromSaleDateStatus": "01/01/1977", "inToSaleDateStatus": today,
    }
    request = urllib.request.Request(endpoint, data=urllib.parse.urlencode(form).encode(), method="POST", headers={**headers, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest"})
    with opener.open(request, timeout=35) as response:
        status = str(response.status)
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    source_rows = payload.get("Data", payload if isinstance(payload, list) else [])
    rows: list[dict] = []
    evidence: list[dict] = []
    for item in source_rows:
        sale_date = parse_date(str(item.get("SaleDate") or ""))
        identity = clean(str(item.get("CaseNumber") or item.get("ParcelId") or ""))
        if not sale_date or not identity or not (start <= sale_date <= end):
            continue
        aid = hashlib.sha256(f"{county}|tax_deed|{identity}|{sale_date.isoformat()}".encode()).hexdigest()[:40]
        rows.append({"aid": aid, "county_slug": county, "auction_type": "tax_deed", "case_number": identity, "judgment_amount": None, "auction_starts_at": f"{sale_date.isoformat()}T00:00:00+00:00", "auction_starts_raw": str(item.get("SaleDate")), "county_subdomain": "charlotte-taxdeed-search", "case_clerk_url": page_url, "source_response_id": str(item.get("CaseId") or ""), "first_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "last_seen_at": dt.datetime.now(dt.timezone.utc).isoformat(), "refresh_count": 1})
        evidence.append({"url": page_url, "sale_type": "tax_deed", "identity": identity, "sale_date": sale_date.isoformat(), "amount_present": False, "base_bid": item.get("BaseBid"), "status": item.get("Status"), "format": "charlotte-taxdeed-json"})
    return rows, evidence, status


def upsert(rows: list[dict]) -> int:
    if not rows:
        return 0
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for --apply")
    request = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/realforeclose_aids?on_conflict=aid",
        data=json.dumps(rows).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status not in (200, 201, 204):
                body = response.read().decode("utf-8", errors="replace")[:800]
                raise RuntimeError(f"upsert failed with HTTP {response.status}: {body}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"upsert failed with HTTP {exc.code}: {body}") from exc
    return len(rows)


def promote_mca(county: str) -> dict:
    request = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/realforeclose_aids_to_mca_insert",
        data=json.dumps({"p_county_slug": county}).encode(),
        method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
    )
    last_error = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8", errors="replace")
                if response.status not in (200, 201, 204):
                    raise RuntimeError(f"MCA promotion HTTP {response.status}: {body[:500]}")
                return {"status": "success", "response": body[:500]}
        except Exception as exc:
            last_error = str(exc)
            if attempt == 0:
                import time
                time.sleep(2)
    return {"status": "error", "error": last_error}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--county", required=True)
    parser.add_argument("--sale-type", choices=("foreclosure", "tax_deed"), required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--days-ahead", type=int, default=14)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--crawl", action="store_true", help="follow same-host links; disabled by default for bounded daily runs")
    parser.add_argument("--extra-url", action="append", default=[], help="explicit official linked document/page to inspect")
    args = parser.parse_args()
    start = dt.date.fromisoformat(args.start_date)
    end = start + dt.timedelta(days=args.days_ahead)
    if args.county.lower() == "lafayette" and args.sale_type == "tax_deed":
        status, html = fetch(args.url)
        rows, evidence = parse_lafayette_taxdeed_cards(args.url, html, args.county.lower(), start, end)
    elif args.county.lower() == "sarasota" and args.sale_type == "tax_deed":
        status, html = fetch(args.url)
        rows, evidence = parse_sarasota_calendar_rows(args.url, html, args.county.lower(), start, end)
    elif args.county.lower() == "charlotte" and args.sale_type == "tax_deed":
        try:
            rows, evidence, status = parse_charlotte_taxdeed_rows(args.county.lower(), start, end)
            html = ""
        except Exception as exc:
            rows, evidence, status, html = [], [{"url": "https://taxdeeds.charlotteclerk.com/TaxDeed/Search", "error": str(exc), "format": "charlotte-taxdeed-json"}], "error", ""
    else:
        status, html = fetch(args.url)
        rows, evidence = parse_structured_rows(args.url, html, args.county.lower(), args.sale_type, start, end)
    if args.county.lower() in {"lafayette", "sarasota"} and args.sale_type == "tax_deed":
        pdf_rows, pdf_evidence = [], []
        prose_rows, prose_evidence = [], []
        status_rows, status_evidence = [], []
    else:
        pdf_rows, pdf_evidence = parse_pdf_listing_rows(args.url, html, args.county.lower(), args.sale_type, start, end)
        prose_rows, prose_evidence = parse_explicit_prose_rows(args.url, html, args.county.lower(), args.sale_type, start, end)
        status_rows, status_evidence = parse_status_sale_rows(args.url, html, args.county.lower(), args.sale_type, start, end)
    rows.extend(pdf_rows)
    rows.extend(prose_rows)
    rows.extend(status_rows)
    evidence.extend(pdf_evidence)
    evidence.extend(prose_evidence)
    evidence.extend(status_evidence)
    extra_links = list(dict.fromkeys(args.extra_url))
    for link in extra_links:
        try:
            nested_status, nested_html = fetch(link)
            nested_rows, nested_evidence = parse_structured_rows(link, nested_html, args.county.lower(), args.sale_type, start, end)
            nested_pdf_rows, nested_pdf_evidence = parse_pdf_listing_rows(link, nested_html, args.county.lower(), args.sale_type, start, end)
            nested_prose_rows, nested_prose_evidence = parse_explicit_prose_rows(link, nested_html, args.county.lower(), args.sale_type, start, end)
            nested_status_rows, nested_status_evidence = parse_status_sale_rows(link, nested_html, args.county.lower(), args.sale_type, start, end)
            rows.extend(nested_rows)
            rows.extend(nested_pdf_rows)
            rows.extend(nested_prose_rows)
            rows.extend(nested_status_rows)
            evidence.extend(nested_evidence)
            evidence.extend(nested_pdf_evidence)
            evidence.extend(nested_prose_evidence)
            evidence.extend(nested_status_evidence)
        except Exception as exc:
            evidence.append({"url": link, "error": str(exc)})
    if args.crawl:
        for link in same_host_links(args.url, html):
            try:
                nested_status, nested_html = fetch(link)
                nested_rows, nested_evidence = parse_structured_rows(link, nested_html, args.county.lower(), args.sale_type, start, end)
                rows.extend(nested_rows)
                evidence.extend(nested_evidence)
            except Exception as exc:
                evidence.append({"url": link, "error": str(exc)})
    unique = {r["aid"]: r for r in rows}
    inserted = upsert(list(unique.values())) if args.apply else 0
    promotion = promote_mca(args.county.lower()) if args.apply and inserted else {"status": "not_requested"}
    print(json.dumps({"county": args.county, "sale_type": args.sale_type, "source_url": args.url, "http_status": status, "window": [start.isoformat(), end.isoformat()], "parsed": len(unique), "inserted": inserted, "apply": args.apply, "mca_promotion": promotion, "evidence": evidence}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
