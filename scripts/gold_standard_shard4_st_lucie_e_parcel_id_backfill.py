#!/usr/bin/env python3
"""Gold Standard shard-4 st_lucie letter E (parcel linkage) fix.

Dispatch 7d59c973-434c-4b8c-a699-e820f9093c39.

ROOT CAUSE: scripts/clerk_ssot/parsers/st_lucie.py::parse_tax_deed() extracts
only cells[0,1,2,5,6,8] from the live acclaimweb.stlucieclerk.gov #dgResults
table and silently drops cells[3] (Issue Year) and cells[4] (Parcel ID) even
though the table's own header row documents the schema as "Applicant | Case
Number | Certificate Number | Issue Year | Parcel ID | Sale Date | Current
Status | Opening Bid | Property Owners". 14 tax_deed rows for the 2026-11-09
auction batch were inserted with parcel_id=NULL as a result, while their 14
sibling rows from the identical harvest (e.g. 26-150, 26-153...) have
parcel_id populated correctly (that harvest used a different/more complete
extraction against the same clerk page).

This script performs a ONE-TIME BACKFILL of the already-live, already-real
Parcel ID values for those 14 rows, sourced from a live GET+POST round trip
against the same acclaimweb.stlucieclerk.gov/TributeWeb/ #dgResults table
this county's parser already scrapes (same source, same table -- this is not
a new/different data source, just correctly reading a column the parser was
silently dropping).

Separately (not in this script), scripts/clerk_ssot/parsers/st_lucie.py is
patched to extract cells[4] going forward so this class of gap does not
recur on the next harvest run.

Fail-loud: if fewer than 14 of the 14 target case numbers are found live, or
if any PATCH does not return the expected updated row, raise -- never
silently skip.
"""
import os
import re
import sys
from datetime import date, timedelta

import httpx
from bs4 import BeautifulSoup

TD_URL = "https://acclaimweb.stlucieclerk.gov/TributeWeb/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Referer": TD_URL,
}
CASE_RE = re.compile(r"^\d{2}-\d{3,5}$")

TARGET_CASES = {
    "26-178", "26-180", "26-181", "26-182", "26-184", "26-185", "26-186",
    "26-187", "26-189", "26-190", "26-193", "26-195", "26-197", "26-212",
}

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
REST = f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
PG_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def _collect_form_fields(soup: BeautifulSoup) -> dict:
    data = {}
    for inp in soup.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        if inp.get("type") == "checkbox" and not inp.get("checked"):
            continue
        data[name] = inp.get("value", "")
    for sel in soup.find_all("select"):
        name = sel.get("name")
        if not name:
            continue
        selected = sel.find("option", selected=True)
        chosen = selected or sel.find("option")
        data[name] = chosen.get("value", "") if chosen else ""
    return data


def fetch_live_parcel_ids() -> dict:
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        resp = client.get(TD_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        data = _collect_form_fields(soup)
        if "__VIEWSTATE" not in data:
            raise RuntimeError("st_lucie tax_deed: no __VIEWSTATE on GET — page structure changed")

        today = date.today()
        data["GrpSaleDate"] = "radDateRange"
        data["txtFrom"] = (today - timedelta(days=120)).strftime("%m/%d/%Y")
        data["txtTo"] = (today + timedelta(days=180)).strftime("%m/%d/%Y")
        data["ddStatus"] = "0"
        data["txtPageSize"] = "500"

        resp2 = client.post(TD_URL, data=data, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"})
        resp2.raise_for_status()

    soup2 = BeautifulSoup(resp2.text, "lxml")
    table = soup2.find("table", id="dgResults")
    if table is None:
        raise RuntimeError("st_lucie tax_deed: no #dgResults table in search response — page structure changed")

    found = {}
    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 9 or not CASE_RE.match(cells[1]):
            continue
        case_number = cells[1]
        if case_number in TARGET_CASES:
            parcel_id = cells[4]
            status = cells[6]
            if not parcel_id:
                raise RuntimeError(f"st_lucie E backfill: case {case_number} has blank Parcel ID cell live — cannot backfill")
            found[case_number] = {"parcel_id": parcel_id, "status": status}
    return found


def main():
    live = fetch_live_parcel_ids()
    missing = TARGET_CASES - set(live.keys())
    if missing:
        raise RuntimeError(f"st_lucie E backfill: {len(missing)} target case(s) not found live: {sorted(missing)}")

    print(f"Fetched {len(live)} of {len(TARGET_CASES)} target case parcel IDs live from acclaimweb.stlucieclerk.gov")

    rows_written = 0
    with httpx.Client(timeout=30) as client:
        for case_number, info in sorted(live.items()):
            parcel_id = info["parcel_id"]
            resp = client.patch(
                REST,
                params={"county": "eq.st_lucie", "case_number": f"eq.{case_number}"},
                headers=PG_HEADERS,
                json={"parcel_id": parcel_id},
            )
            resp.raise_for_status()
            body = resp.json()
            if len(body) != 1:
                raise RuntimeError(f"st_lucie E backfill: PATCH for {case_number} returned {len(body)} rows, expected 1")
            if body[0].get("parcel_id") != parcel_id:
                raise RuntimeError(f"st_lucie E backfill: PATCH for {case_number} did not persist parcel_id={parcel_id}")
            rows_written += 1
            print(f"  {case_number} -> parcel_id={parcel_id} ({info['status']}) OK")

    print(f"\nTotal rows written: {rows_written} / {len(TARGET_CASES)}")
    if rows_written != len(TARGET_CASES):
        raise RuntimeError(f"st_lucie E backfill: expected {len(TARGET_CASES)} rows written, got {rows_written}")


if __name__ == "__main__":
    main()
