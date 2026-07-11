#!/usr/bin/env python3
"""
Gold Standard shard-1 (run3713): Collier County tax-deed harvester.

Collier's RealAuction lanes (collier.realforeclose.com / collier.realtaxdeed.com) are
confirmed dead at the ELB/vhost level (every path/query redirects off-host to the vendor
marketing site) -- re-verified live this session, matching SHARD13_RUN3645's prior
"deprovisioned vendor account" finding.

Collier tax deed sales ARE published, however, by the Clerk of the Circuit Court via a
public (anonymous, no login) Laserfiche WebLink repository:
  https://www.collierclerk.com/tax-deed-sales/search-upcoming-sales-list/
    -> iframe -> https://app.collierclerk.com/LFOfficialRecords/Browse.aspx?dbid=0&startid=1600&repo=OFFICIALRECORDSPROD
    -> \Tax Deeds Public\Sales Lists & Lands Available\{2024,2025,2026} SALES\*.pdf

Each PDF is a "Tax Deeds Sales List" as of a given date, with one row per parcel:
  Sale Date | TDA# | Cert# | Title Holder | Property ID# | Legal Description | Min. Bid | Status or Sold Amt
Status is either REDEEMED (no sale -- owner paid off before auction), ACTIVE (future,
not yet sold), or a dollar amount (an ACTUAL completed sale -- may equal or exceed Min. Bid).

Collier foreclosure sales use a SEPARATE, non-Laserfiche mechanism (Blazor Server SignalR
app at cor.collierclerk.com/coraccess/, no REST surface reachable without full browser JS)
-- confirmed NOT_VIABLE this session, out of scope here. This harvester covers tax_deed only.

data_source='collier_clerk_laserfiche' -- an INDEPENDENT clerk-of-court source, never
RealAuction, never PropertyOnion. No fabrication: rows failing validation are skipped and
counted, never inserted with guessed fields.
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone

import pdfplumber

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
REPO = "OFFICIALRECORDSPROD"
ROOT_FOLDER_ID = 1600  # "Sales Lists & Lands Available"
COOKIE_JAR = "/tmp/collier_lf_cookies.txt"

SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"


def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout, r.stderr


def bootstrap_session():
    code, out, err = sh(
        f'curl -sS -m 20 -L -c {COOKIE_JAR} -b {COOKIE_JAR} -A "{UA}" '
        f'"https://app.collierclerk.com/LFOfficialRecords/Browse.aspx?dbid=0&startid={ROOT_FOLDER_ID}&repo={REPO}" '
        f'-o /tmp/collier_lf_browse.html -w "%{{http_code}}"'
    )
    if out.strip() != "200":
        raise RuntimeError(f"FAIL-LOUD: Laserfiche session bootstrap returned HTTP {out.strip()}, not 200")


def get_folder_listing(folder_id):
    payload = json.dumps({
        "repoName": REPO, "folderId": folder_id, "getNewListing": True,
        "start": 0, "end": 500, "sortColumn": "Name", "sortAscending": False,
    })
    code, out, err = sh(
        f"curl -sS -m 20 -c {COOKIE_JAR} -b {COOKIE_JAR} -A \"{UA}\" "
        f"-X POST \"https://app.collierclerk.com/LFOfficialRecords/FolderListingService.aspx/GetFolderListing2\" "
        f"-H \"Content-Type: application/json\" -d '{payload}'"
    )
    d = json.loads(out)
    return d["data"]["results"]


def download_pdf(entry_id, dest):
    code, out, err = sh(
        f'curl -sS -m 30 -c {COOKIE_JAR} -b {COOKIE_JAR} -A "{UA}" '
        f'"https://app.collierclerk.com/LFOfficialRecords/ElectronicFile.aspx?docid={entry_id}&dbid=0&repo={REPO}" '
        f'-o {dest} -w "%{{http_code}}"'
    )
    if out.strip() != "200":
        raise RuntimeError(f"FAIL-LOUD: ElectronicFile.aspx docid={entry_id} returned HTTP {out.strip()}")


ROW_RE = re.compile(
    r"(\d{1,2}/\d{1,2}/\d{4})\s+"      # 1 sale date
    r"(\d{4,6})\s+"                     # 2 TDA#
    r"(\d{4}/\d{1,6})\s*"                # 3 cert# (sometimes glued directly to title holder, no space)
    r"(.*?)\s+"                         # 4 title holder (lazy)
    r"(\d{6,12})\s+"                    # 5 property id# (first long digit run)
    r"(.*?)\s+"                         # 6 legal description (lazy)
    r"\$\s*([\d,\s]+\.\d{2})\s+"        # 7 min bid (tolerate stray OCR spaces in digits)
    r"(REDEEMED|CANCELLED|CANCELED|ACTIVE|\$\s*[\d,\s]+\.\d{2})"  # 8 status
)


def _money(s):
    return float(re.sub(r"[,\s$]", "", s))


def parse_pdf(path, sale_folder_label):
    rows = []
    skipped = 0
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    for line in text.split("\n"):
        m = ROW_RE.search(line)
        if not m:
            continue
        try:
            sale_date_raw, tda, cert, holder, prop_id, legal, min_bid_raw, status_raw = m.groups()
            sale_date = datetime.strptime(sale_date_raw, "%m/%d/%Y").date().isoformat()
            min_bid = _money(min_bid_raw)
            status_raw = status_raw.strip()
            if status_raw.upper() in ("REDEEMED",):
                auction_status, sold_amount = "redeemed", None
            elif status_raw.upper() in ("CANCELLED", "CANCELED"):
                auction_status, sold_amount = "cancelled", None
            elif status_raw.upper() == "ACTIVE":
                auction_status, sold_amount = "upcoming", None
            elif status_raw.startswith("$"):
                sold_amount = _money(status_raw)
                auction_status = "sold"
            else:
                skipped += 1
                continue
            rows.append({
                "auction_date": sale_date,
                "case_number": tda,
                "cert_number": cert,
                "owner_name": holder.strip(),
                "parcel_id": prop_id,
                "legal_description": legal.strip(),
                "opening_bid": round(min_bid, 2),
                "auction_status": auction_status,
                "sold_amount": round(sold_amount, 2) if sold_amount is not None else None,
                "source_doc": sale_folder_label,
            })
        except (ValueError, TypeError):
            skipped += 1
            continue
    return rows, skipped


def main():
    bootstrap_session()
    year_folders = [r for r in get_folder_listing(ROOT_FOLDER_ID) if r.get("extension") is None or r.get("extension") == ""]
    year_folders = [r for r in year_folders if "SALES" in (r.get("name") or "").upper()]
    print(f"Year folders found: {[(r['name'], r['entryId']) for r in year_folders]}", file=sys.stderr)

    all_rows = []
    total_skipped = 0
    doc_count = 0
    for yf in year_folders:
        docs = get_folder_listing(yf["entryId"])
        for d in docs:
            doc_count += 1
            entry_id = d["entryId"]
            name = d["name"]
            dest = f"/tmp/collier_lf_doc_{entry_id}.pdf"
            download_pdf(entry_id, dest)
            rows, skipped = parse_pdf(dest, name)
            print(f"  {name} (entryId={entry_id}): {len(rows)} parsed, {skipped} skipped", file=sys.stderr)
            all_rows.extend(rows)
            total_skipped += skipped

    print(f"\nTOTAL: {doc_count} documents, {len(all_rows)} rows parsed, {total_skipped} rows skipped (unparseable)", file=sys.stderr)

    if doc_count > 0 and len(all_rows) == 0:
        raise RuntimeError("FAIL-LOUD: parsed 0 rows from >0 documents -- parser regressed, not a data issue")

    with open("/tmp/collier_taxdeed_rows.json", "w") as f:
        json.dump(all_rows, f, indent=2)
    print(f"\nWrote {len(all_rows)} rows to /tmp/collier_taxdeed_rows.json", file=sys.stderr)


if __name__ == "__main__":
    main()
