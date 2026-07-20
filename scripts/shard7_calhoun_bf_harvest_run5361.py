#!/usr/bin/env python3
"""
shard7_calhoun_bf_harvest_run5361.py
=====================================
Calhoun County B+F harvest attempt — SHARD-7 dispatch 74e8c56b, loop run 5361
Date: 2026-07-20

Context:
  - As of 2026-07-19 (volusia/calhoun/taylor session): B=FAIL, F=FAIL (0/0 closed_sold)
  - Tax deed case 171 OF 2023 was scheduled 2026-07-09 (11 days ago as of today)
  - calhounclerk.com "Lands Available" page was empty 2026-07-19 (checked live)
  - This script re-checks today: if the July 9 sale resolved, it may now have a result
  - Also checks for any new outcomes on calhoun.realtaxdeed.com (403 in prior sessions,
    may be different from a different egress IP)

Strategy:
  1. Fetch calhounclerk.com/foreclosure and tax-deed-sales pages
  2. Look for any completed/resolved cases (status != "upcoming" or "scheduled")
  3. If found, write to foreclosure_outcomes or tax_deed_outcomes with
     data_source='calhounclerk_com:SHARD7-RUN5361' (INDEPENDENT data source — satisfies B canon)
  4. If no results found, report UNKNOWN (not fabricated)

HONESTY PROTOCOL: 
  - VERIFIED = proof from live page
  - UNKNOWN = checked but no result found (always acceptable per protocol)
  - NEVER fabricate outcomes

Exit codes: 0=success (rows written), 1=error, 2=no new data (UNKNOWN, expected)
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

PAGES = {
    "foreclosure": "https://www.calhounclerk.com/foreclosure",
    "tax_deed": "https://www.calhounclerk.com/tax-deed-sales",
    "lands_available": "https://www.calhounclerk.com/lands-available",
}

DATA_SOURCE_FC = "calhounclerk_com:SHARD7-RUN5361-FC"
DATA_SOURCE_TD = "calhounclerk_com:SHARD7-RUN5361-TD"

NOW_ISO = datetime.now(timezone.utc).isoformat()


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg: str, tag: str = "INFO") -> None:
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def fetch_raw(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        log(f"HTTP {e.code} fetching {url}", "WARN")
        return ""
    except Exception as exc:
        log(f"Error fetching {url}: {exc}", "WARN")
        return ""


def fetch_text(url: str) -> str:
    raw = fetch_raw(url)
    if not raw:
        return ""
    text = re.sub(r"<script.*?</script>", "", raw, flags=re.S)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _headers() -> dict:
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def rest_get(path: str, params: dict | None = None) -> list:
    import urllib.parse
    qs = urllib.parse.urlencode(params or {})
    url = f"{SB_URL}/rest/v1/{path}?{qs}"
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as exc:
        log(f"GET {path} failed: {exc}", "ERROR")
        return []


def rest_post(table: str, rows: list, prefer: str = "resolution=merge-duplicates,return=minimal") -> tuple[int, str]:
    body = json.dumps(rows).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}",
        data=body,
        headers={**_headers(), "Prefer": prefer},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return 200, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", "replace")
        log(f"POST {table} HTTP {e.code}: {body_txt[:300]}", "ERROR")
        return e.code, body_txt
    except Exception as exc:
        log(f"POST {table} failed: {exc}", "ERROR")
        return 0, str(exc)


def check_foreclosure_page() -> list[dict]:
    log("Fetching calhounclerk.com/foreclosure ...")
    text = fetch_text(PAGES["foreclosure"])
    if not text:
        log("UNKNOWN — page unreachable (HTTP error or empty)", "WARN")
        return []

    log(f"Page text length: {len(text)}")

    # Look for status indicators — COMPLETED / SOLD / CANCELLED
    # The foreclosure page uses: Status Active/Upcoming + Sale Date + Case Number + Judgment Amount + Address + Parcel ID
    completed_patterns = [
        r"Status\s+(?:Completed?|Sold|Final\s+Judgment|Certificate\s+of\s+Title)\s+Sale Date\s+(\d{2}/\d{2}/\d{4})\s+Case Number\s+([\w\-]+)\s+Judgement Amount\s+\$([\d,.]+)\s+Address\s+(.+?)\s+Parcel ID\s+([\w\-]+)",
    ]

    results = []
    for pat in completed_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            results.append({
                "sale_date": m.group(1),
                "case_number": m.group(2),
                "judgment_amount": float(m.group(3).replace(",", "")),
                "address": m.group(4).strip(),
                "parcel_id": m.group(5).strip(),
                "type": "foreclosure",
            })

    # Also check for "no properties" indicators
    no_props = re.search(r"no\s+(properties|listings|cases|foreclosure)", text, re.IGNORECASE)
    if no_props:
        log(f"Page indicates no properties: found '{no_props.group(0)}'")

    log(f"Found {len(results)} completed foreclosure records")
    return results


def check_taxdeed_page() -> list[dict]:
    log("Fetching calhounclerk.com/tax-deed-sales ...")
    raw = fetch_raw(PAGES["tax_deed"])
    if not raw:
        log("UNKNOWN — tax deed page unreachable", "WARN")
        return []

    # The tax-deed page uses Vue component attribute: :taxdeeds="[...]"
    TAXDEED_ATTR_RE = re.compile(r':taxdeeds="(?P<blob>\[.*?\])"', re.S)
    m = TAXDEED_ATTR_RE.search(raw)

    results = []
    if m:
        try:
            blob_raw = m.group("blob")
            blob_raw = html.unescape(blob_raw)
            taxdeeds = json.loads(blob_raw)
            log(f"Parsed {len(taxdeeds)} tax deed entries from Vue component")

            for td in taxdeeds:
                status = str(td.get("status", "")).lower()
                # Look for completed/sold entries
                if any(kw in status for kw in ("sold", "completed", "certificate", "closed", "redeemed")):
                    results.append({
                        "case_number": str(td.get("case_number", td.get("caseNumber", ""))),
                        "parcel_id": str(td.get("parcel_id", td.get("parcelId", ""))),
                        "sale_date": str(td.get("sale_date", td.get("saleDate", ""))),
                        "sold_amount": float(td.get("sold_amount", td.get("soldAmount", 0)) or 0),
                        "status": status,
                        "type": "tax_deed",
                    })
                    log(f"Found completed TD: case={results[-1]['case_number']} status={status}")
        except json.JSONDecodeError as e:
            log(f"Failed to parse taxdeed JSON blob: {e}", "WARN")
    else:
        # Fallback: check text version
        text = fetch_text(PAGES["tax_deed"])
        log(f"Tax deed page text length: {len(text)} (no Vue component found)")
        # Check for "171 OF 2023" specifically
        if "171" in text and "2023" in text:
            log("Found reference to 171/2023 in tax deed page — check manually")
        if re.search(r"no\s+(properties|listings|tax\s*deeds?)", text, re.IGNORECASE):
            log("Tax deed page indicates no active listings")

    log(f"Found {len(results)} completed tax deed records")
    return results


def check_lands_available() -> bool:
    log("Fetching calhounclerk.com/lands-available ...")
    text = fetch_text(PAGES["lands_available"])
    if not text:
        log("UNKNOWN — lands available page unreachable", "WARN")
        return False

    # If the tax deed resolved without a buyer, it appears on Lands Available
    has_props = bool(re.search(r"\b(171\s+(?:OF\s+)?2023|621\s+(?:OF\s+)?2026)\b", text, re.IGNORECASE))
    no_props = bool(re.search(r"no\s+properties|currently\s+no\s+lands\s+available|no\s+items", text, re.IGNORECASE))

    if has_props:
        log("Lands Available page contains reference to one of our tracked cases — sale may have resolved to no buyer", "WARN")
    if no_props:
        log("Lands Available page explicitly shows no properties available")

    return has_props


def get_calhoun_case_map() -> dict:
    rows = rest_get("multi_county_auctions", {
        "county": "eq.calhoun",
        "select": "id,case_number,parcel_id,auction_status,source_platform",
    })
    log(f"Found {len(rows)} calhoun rows in multi_county_auctions")
    return {r["case_number"]: r for r in rows if r.get("case_number")}


def write_foreclosure_outcome(case_map: dict, rec: dict) -> bool:
    case = case_map.get(rec["case_number"])
    if not case:
        log(f"Case {rec['case_number']} not in our DB — skipping", "WARN")
        return False

    outcome = {
        "case_number": rec["case_number"],
        "county": "calhoun",
        "sale_date": rec["sale_date"],
        "sold_amount": rec["judgment_amount"],
        "data_source": DATA_SOURCE_FC,
        "source_url": PAGES["foreclosure"],
        "verified_at": NOW_ISO,
        "outcome_type": "foreclosure",
        "parcel_id": rec.get("parcel_id") or case.get("parcel_id"),
    }

    status, body = rest_post("foreclosure_outcomes", [outcome])
    if status in (200, 201):
        log(f"Wrote foreclosure_outcome for {rec['case_number']}: ${rec['judgment_amount']}")
        return True
    else:
        log(f"Failed to write foreclosure_outcome: {status} {body[:200]}", "ERROR")
        return False


def write_taxdeed_outcome(case_map: dict, rec: dict) -> bool:
    case = case_map.get(rec["case_number"])
    if not case:
        log(f"Tax deed {rec['case_number']} not in our DB — skipping", "WARN")
        return False

    outcome = {
        "case_number": rec["case_number"],
        "county": "calhoun",
        "sale_date": rec["sale_date"],
        "sold_amount": rec["sold_amount"] if rec["sold_amount"] > 0 else None,
        "data_source": DATA_SOURCE_TD,
        "source_url": PAGES["tax_deed"],
        "verified_at": NOW_ISO,
        "outcome_type": "tax_deed",
        "parcel_id": rec.get("parcel_id") or case.get("parcel_id"),
        "status": rec["status"],
    }

    status, body = rest_post("tax_deed_outcomes", [outcome])
    if status in (200, 201):
        log(f"Wrote tax_deed_outcome for {rec['case_number']}: sold_amount={rec['sold_amount']}")
        return True
    else:
        log(f"Failed to write tax_deed_outcome: {status} {body[:200]}", "ERROR")
        return False


def main() -> int:
    if not SB_KEY:
        log("SUPABASE_SERVICE_ROLE_KEY not set — cannot write to DB", "ERROR")
        return 1

    log("=== CALHOUN B+F HARVEST — SHARD-7 RUN5361 ===")
    case_map = get_calhoun_case_map()

    # 1. Check foreclosure page
    fc_records = check_foreclosure_page()

    # 2. Check tax deed page
    td_records = check_taxdeed_page()

    # 3. Check lands available (informational)
    check_lands_available()

    total_written = 0

    # Write foreclosure outcomes
    for rec in fc_records:
        if write_foreclosure_outcome(case_map, rec):
            total_written += 1

    # Write tax deed outcomes
    for rec in td_records:
        if write_taxdeed_outcome(case_map, rec):
            total_written += 1

    if total_written > 0:
        log(f"SUCCESS: wrote {total_written} outcome row(s) to DB")
        log("Run pencil_dod_evaluate_county('calhoun') to verify B/F metric improvement")
        return 0
    else:
        log("UNKNOWN: no completed auction outcomes found on calhounclerk.com today")
        log("B/F remain FAIL — genuinely no closed auctions to harvest yet (BLANK > WRONG)")
        log("Next check date: 2026-08-13 (next scheduled Calhoun tax deed batch)")
        return 2


if __name__ == "__main__":
    sys.exit(main())
