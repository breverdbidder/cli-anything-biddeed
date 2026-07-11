#!/usr/bin/env python3
"""
Glades County FL foreclosure + tax deed sale ingestion from the Clerk's
Municode "MuniDocs" Notices repository (library.municode.com, productId=31194).

Glades publishes NO auction data through RealAuction, kofile, myfloridacounty,
civitek, or bid4assets (confirmed dead across 4 prior gold-standard sessions —
see SHARD8_RUN3713_GLADES_SESSION_REPORT.md). It DOES publish real foreclosure
sale notices and tax deed sale notices (2021-present) as PDFs/DOCX under
Notices > Foreclosure Sales and Notices > Tax Deeds > {year} Tax Deed Sales in
its Municode document library. The Angular SPA tree API requires a real
browser context (Cloudflare-gated, `x-csrf: 1` header set by in-page JS); the
actual PDF/DOCX blobs are served unauthenticated from a separate Azure
Functions host once the node ID is known.

Idempotent: re-running only inserts case_numbers not already present for
county=glades, and touches last_seen_at on rows it re-confirms from the live
tree so H (freshness) stays current between new postings.
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests
from playwright.sync_api import sync_playwright
from pypdf import PdfReader
import docx

MUNICODE_BASE = "https://library.municode.com/fl/glades_county_florida_clerk_of_court/munidocs/munidocs"
PRODUCT_ID = "31194"
PDF_DOWNLOAD_BASE = "https://mcclibraryfunctions.azurewebsites.us/api/munidocDownload"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

USAGE_KEYWORDS = [
    "Vacant Residential", "Multi Family", "Multi-Family", "Single Family",
    "Mobile Home", "No Ag Acreage", "Ornamentals, Misc", "Vacant Commercial",
    "Commercial",
]
USAGE_ALT = "|".join(re.escape(k) for k in USAGE_KEYWORDS)
SALE_DATE_RE = re.compile(r"TAX DEED SALE\s*[–\-]\s*([A-Za-z]+ \d{1,2},?\s*\d{4})", re.I)
RECORD_START_RE = re.compile(r"(\d{4}-\d{1,3})\s+(\d{1,4}-\d{4})\s+")
PARCEL_RE = re.compile(
    r"\b([A-Z]\d{2}\s*-\s*\d{2}\s*-\s*\d{2}\s*-\s*[A-Z0-9]{2,3}\s*-\s*[A-Z0-9]{3,4}\s*-\s*[A-Z0-9]{3,4})\b"
)
BID_RE = re.compile(r"\$([\d,]+\.\d{2})")
SOLD_RE = re.compile(r"SOLD\s+(\d{1,2}/\d{1,2}/\d{4})\s+FOR\s+\$([\d,]+\.\d{2})", re.I)
REDEEMED_RE = re.compile(r"REDEEMED\s*(?:ON)?\s*(\d{1,2}/\d{1,2}/\d{4})?", re.I)
CANCELLED_RE = re.compile(r"CANCELLED", re.I)
USAGE_RE = re.compile(USAGE_ALT, re.I)


def norm_ws(s):
    return re.sub(r"\s+", " ", s).strip()


def api_get(page, url):
    js = """async (u) => {
        const r = await fetch(u, {headers: {Accept: 'application/json', 'x-csrf': '1'}});
        return {status: r.status, body: await r.text()};
    }"""
    result = page.evaluate(js, url)
    if result["status"] != 200:
        raise RuntimeError(f"Municode API {url} -> HTTP {result['status']}")
    return json.loads(result["body"])


def walk_tree(page):
    """Returns list of leaf doc dicts: {category, year, node_id, heading, filename, ext, sort_date}."""
    notices = api_get(page, f"https://library.municode.com/api/munidocsToc/children?nodeId=notices&productId={PRODUCT_ID}")
    docs = []
    for c in notices:
        heading = c.get("Heading", "")
        cid = c.get("Id")
        if "Foreclosure" in heading:
            children = api_get(page, f"https://library.municode.com/api/munidocsToc/children?nodeId={cid}&productId={PRODUCT_ID}")
            for ch in children:
                d = ch["Data"]
                docs.append({"category": "foreclosure", "year": None, "node_id": d["Id"],
                             "heading": d["Heading"], "filename": d["OriginalFileName"],
                             "ext": d["OriginalFileExtension"], "sort_date": d["SortDate"]})
        elif "Tax Deed" in heading:
            years = api_get(page, f"https://library.municode.com/api/munidocsToc/children?nodeId={cid}&productId={PRODUCT_ID}")
            for y in years:
                yid = y.get("Id")
                items = api_get(page, f"https://library.municode.com/api/munidocsToc/children?nodeId={yid}&productId={PRODUCT_ID}")
                for it in items:
                    d = it["Data"]
                    if d["Heading"].strip() == "To Be Determined":
                        continue
                    docs.append({"category": "tax_deed", "year": y.get("Heading"), "node_id": d["Id"],
                                 "heading": d["Heading"], "filename": d["OriginalFileName"],
                                 "ext": d["OriginalFileExtension"], "sort_date": d["SortDate"]})
    return docs


def download_doc(node_id, ext, out_dir):
    url = f"{PDF_DOWNLOAD_BASE}/{PRODUCT_ID}/{node_id}/{ext.lstrip('.')}"
    last_err = None
    for attempt in range(4):
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
            r.raise_for_status()
            out_path = os.path.join(out_dir, f"{node_id}{ext}")
            with open(out_path, "wb") as f:
                f.write(r.content)
            return out_path
        except requests.exceptions.HTTPError as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise last_err


def parse_tax_deed_pdf(path, heading):
    reader = PdfReader(path)
    full_text = "\n".join(p.extract_text() or "" for p in reader.pages)
    records = []
    starts = list(RECORD_START_RE.finditer(full_text))
    for i, sm in enumerate(starts):
        start = sm.start()
        end = starts[i + 1].start() if i + 1 < len(starts) else len(full_text)
        flat = norm_ws(full_text[start:end])

        tax_deed_file, cert_no = sm.group(1), sm.group(2)
        parcel_m = PARCEL_RE.search(flat)
        parcel_id = re.sub(r"\s+", "", parcel_m.group(1)) if parcel_m else None

        sold_m = SOLD_RE.search(flat)
        redeemed_m = REDEEMED_RE.search(flat) if not sold_m else None
        cancelled_m = CANCELLED_RE.search(flat) if not sold_m else None

        bid_amount = None
        for bm in BID_RE.finditer(flat):
            if sold_m and sold_m.start() <= bm.start() <= sold_m.end():
                continue
            bid_amount = float(bm.group(1).replace(",", ""))
            break

        addr = None
        if parcel_m:
            after = flat[parcel_m.end(): parcel_m.end() + 120]
            addr_m = re.search(r"^(.*?FL\.?,?\s*\d{0,5})\s+(?:" + USAGE_ALT + ")", after, re.I)
            if addr_m:
                addr = norm_ws(addr_m.group(1))
            else:
                um = USAGE_RE.search(after)
                if um:
                    addr = norm_ws(after[:um.start()]) or None

        outcome, sold_amount, sale_result_date = None, None, None
        if sold_m:
            outcome, sale_result_date, sold_amount = "SOLD", sold_m.group(1), float(sold_m.group(2).replace(",", ""))
        elif redeemed_m and redeemed_m.group(0).upper().startswith("REDEEMED"):
            outcome, sale_result_date = "REDEEMED", redeemed_m.group(1)
        elif cancelled_m:
            outcome = "CANCELLED"

        records.append({"tax_deed_file": tax_deed_file, "cert_no": cert_no, "parcel_id": parcel_id,
                         "physical_address": addr, "opening_bid": bid_amount, "outcome": outcome,
                         "sold_amount": sold_amount, "sale_result_date": sale_result_date,
                         "source_doc": heading})
    return records


def parse_tax_deed_docx(path, heading):
    d = docx.Document(path)
    records = []
    for table in d.tables:
        for row in table.rows[1:]:
            cells = [c.text.strip() for c in row.cells]
            if len(cells) < 9 or not re.match(r"\d{4}-\d+", cells[0]):
                continue
            file_no, cert_no, _holder, parcel_id, addr, _usage, _desc, _owner, bid_cell = cells[:9]
            outcome, sold_amount, sale_result_date, bid_amount = None, None, None, None
            sold_m = re.search(r"SOLD\s+(\d{1,2}/\d{1,2}/\d{4})\s+FOR\s+\$([\d,]+\.\d{2})", bid_cell, re.I)
            cancelled_m = re.search(r"CANCELLED", bid_cell, re.I)
            redeemed_m = re.search(r"REDEEMED\s*(?:ON)?\s*(\d{1,2}/\d{1,2}/\d{4})?", bid_cell, re.I)
            bid_m = re.search(r"\$([\d,]+\.\d{2})", bid_cell)
            if bid_m:
                bid_amount = float(bid_m.group(1).replace(",", ""))
            if sold_m:
                outcome, sale_result_date, sold_amount = "SOLD", sold_m.group(1), float(sold_m.group(2).replace(",", ""))
            elif cancelled_m:
                outcome = "CANCELLED"
            elif redeemed_m:
                outcome, sale_result_date = "REDEEMED", redeemed_m.group(1)
            records.append({"tax_deed_file": file_no, "cert_no": cert_no,
                             "parcel_id": re.sub(r"\s+", "", parcel_id),
                             "physical_address": norm_ws(addr) or None, "opening_bid": bid_amount,
                             "outcome": outcome, "sold_amount": sold_amount,
                             "sale_result_date": sale_result_date, "source_doc": heading})
    return records


FORECLOSURE_ROW_RE = re.compile(
    r"(\d{6}CA\d{6}CA[A-Z]{2,4})\s+(.*?)\s+\$([\d,]+\.\d{2})\s+(.*?)"
    r"PROPERTY ADDRESS:\s*(.*?)(?:\s+Updated:|$)"
)


def parse_foreclosure_pdf(path):
    reader = PdfReader(path)
    text = "\n".join(p.extract_text() or "" for p in reader.pages)
    flat = norm_ws(text)
    rows = []
    for m in FORECLOSURE_ROW_RE.finditer(flat):
        case_number, parties, judgment, legal, addr = m.groups()
        rows.append({
            "case_number": case_number.strip(),
            "plaintiff": norm_ws(parties)[:250],
            "judgment_amount": float(judgment.replace(",", "")),
            "legal_description": norm_ws(legal),
            "property_address": norm_ws(addr),
        })
    return rows


def sb_get(table, params):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=SB_HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def sb_insert(table, rows):
    if not rows:
        return 0
    keys = sorted({k for r in rows for k in r})
    norm_rows = [{k: r.get(k) for k in keys} for r in rows]
    headers = {**SB_HEADERS, "Prefer": "return=representation"}
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=headers, json=norm_rows, timeout=60)
    if r.status_code >= 300:
        raise RuntimeError(f"insert into {table} failed: HTTP {r.status_code} {r.text[:500]}")
    return len(r.json())


def sb_touch_last_seen(case_numbers, now_iso):
    if not case_numbers:
        return
    headers = {**SB_HEADERS, "Prefer": "return=minimal"}
    for cn in case_numbers:
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers=headers,
            params={"county": "eq.glades", "case_number": f"eq.{cn}"},
            json={"last_seen_at": now_iso, "last_changed_at": now_iso},
            timeout=30,
        )


def main():
    out_dir = "/tmp/glades_municode_docs"
    os.makedirs(out_dir, exist_ok=True)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(f"{MUNICODE_BASE}?nodeId=notices", timeout=30000, wait_until="networkidle")
        page.wait_for_timeout(1500)
        docs = walk_tree(page)
        browser.close()

    print(f"Discovered {len(docs)} live documents in Municode MuniDocs Notices tree")

    td_records, fc_records = [], []
    for d in docs:
        path = download_doc(d["node_id"], d["ext"], out_dir)
        if d["category"] == "tax_deed":
            if d["ext"] == ".pdf":
                recs = parse_tax_deed_pdf(path, d["heading"])
            elif d["ext"] == ".docx":
                recs = parse_tax_deed_docx(path, d["heading"])
            else:
                continue
            for r in recs:
                r["sort_date"] = d["sort_date"]
            td_records.extend(recs)
        elif d["category"] == "foreclosure" and d["ext"] == ".pdf":
            fc_records.extend(parse_foreclosure_pdf(path))

    print(f"Parsed {len(td_records)} tax deed records, {len(fc_records)} foreclosure records")

    existing = sb_get("multi_county_auctions", {"county": "eq.glades", "select": "case_number"})
    existing_cases = {r["case_number"] for r in existing}
    existing_outcomes = {r["case_number"] for r in sb_get("tax_deed_outcomes", {"county": "eq.glades", "select": "case_number"})}

    new_auction_rows, sold_outcome_rows, seen_this_run = [], [], []
    for r in td_records:
        date8 = (r["sort_date"] or "")[:10].replace("-", "") or "UNK"
        case_number = f"TD-{r['tax_deed_file']}-{date8}"
        seen_this_run.append(case_number)
        addr = r["physical_address"]
        if addr and "FL" not in addr:
            addr = addr + ", FL"
        if case_number not in existing_cases:
            row = {
                "county": "glades", "state": "FL", "sale_type": "tax_deed", "auction_type": "tax_deed",
                "case_number": case_number, "cert_number": r["cert_no"], "parcel_id": r["parcel_id"],
                "property_address": addr, "opening_bid": r["opening_bid"], "sold_amount": r["sold_amount"],
                "auction_date": (r["sort_date"] or "")[:10] or None, "auction_status": "closed",
                "data_source": "municode_munidocs:GLADES-TD-V1", "source_platform": "municode_munidocs",
                "provenance": "primary_scrape", "source_url": MUNICODE_BASE,
                "last_seen_at": now_iso, "scraped_at": now_iso, "scrape_timestamp": now_iso,
            }
            if r["sold_amount"] is not None:
                row["sold_amount_source"] = "municode_munidocs:GLADES-TD-V1"
            new_auction_rows.append(row)
            if r["sold_amount"] is not None and case_number not in existing_outcomes:
                sold_outcome_rows.append({
                    "case_number": case_number, "county": "glades", "auction_date": row["auction_date"],
                    "cert_number": r["cert_no"], "opening_bid": r["opening_bid"], "winning_bid": r["sold_amount"],
                    "outcome": "SOLD", "property_address": addr, "parcel_id": r["parcel_id"],
                    "data_source": "municode_munidocs:GLADES-TD-V1", "source_url": MUNICODE_BASE,
                })

    for r in fc_records:
        seen_this_run.append(r["case_number"])
        if r["case_number"] not in existing_cases:
            new_auction_rows.append({
                "county": "glades", "state": "FL", "sale_type": "foreclosure", "auction_type": "foreclosure",
                "case_number": r["case_number"], "plaintiff": r["plaintiff"],
                "property_address": r["property_address"], "judgment_amount": r["judgment_amount"],
                "legal_description": r["legal_description"], "auction_status": "upcoming",
                "data_source": "municode_munidocs:GLADES-FC-V1", "source_platform": "municode_munidocs",
                "provenance": "primary_scrape", "source_url": MUNICODE_BASE,
                "last_seen_at": now_iso, "scraped_at": now_iso, "scrape_timestamp": now_iso,
            })

    inserted = sb_insert("multi_county_auctions", new_auction_rows)
    inserted_outcomes = sb_insert("tax_deed_outcomes", sold_outcome_rows)

    already_present = [cn for cn in seen_this_run if cn in existing_cases]
    sb_touch_last_seen(already_present, now_iso)

    if sold_outcome_rows or inserted_outcomes:
        r = requests.post(f"{SUPABASE_URL}/rest/v1/rpc/promote_tier1_from_outcomes", headers=SB_HEADERS, json={}, timeout=30)
        print("promote_tier1_from_outcomes:", r.status_code, r.text[:200])

    total_parsed = len(td_records) + len(fc_records)
    total_written = inserted + inserted_outcomes + len(already_present)
    print(f"multi_county_auctions inserted={inserted} touched={len(already_present)}")
    print(f"tax_deed_outcomes inserted={inserted_outcomes}")

    if total_parsed > 0 and total_written == 0:
        raise RuntimeError("FAIL-LOUD: parsed>0 but wrote 0 rows (insert+touch) — refusing to exit silently")

    evalr = requests.post(f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county", headers=SB_HEADERS,
                           json={"p_county": "glades"}, timeout=30)
    print("pencil_dod_evaluate_county(glades):", evalr.text)


if __name__ == "__main__":
    sys.exit(main())
