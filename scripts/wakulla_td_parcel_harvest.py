#!/usr/bin/env python3
"""
Wakulla Tax Deed Parcel Harvest (2026-07-10)
=============================================
Wakulla does not use RealForeclose/RealTaxDeed (wakulla.realtdm.com is a locked
TEST tenant with zero public cases -- confirmed by scripts/shard_wakulla_realtdm_exhaustive_probe.py).
The county's real live source is the Clerk of Court's own website
(wakullaclerk.org). The tax_deed_sales.php calendar lists case numbers only,
but each case links to a "Notice of Application for Tax Deed" PDF that
contains the Parcel #, legal description, owner name, and opening/redemption
bid amounts -- this is what criterion E (parcel linkage) needs.

Foreclosure cases (foreclosures.php) do not carry a parcel number on that page
and are NOT covered by this script -- they still need a different source
(courthouse docket / property appraiser owner-name lookup) to link parcels.

Env (required): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success (>=1 row updated), 1 = fatal error, 2 = zero new links found
"""
import os
import re
import sys
import urllib.parse
import urllib.request

import pypdf
import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

TD_URL = "https://wakullaclerk.org/official_records/tax_deed_sales.php"

# Parcel formats observed: "00-00-043-010-08943-000" (platted lots) and
# "26-4s-02w-022-02204-000" / "08-3s-01w-208-04334-028" (section-township-range).
PARCEL_RE = re.compile(r"\b(\d{2}-\d{2}-\d{3}-\d{3}-\d{5}-\d{3}|\d{2}-\d[A-Za-z]-\d{2}[A-Za-z]-\d{3}-\d{5}-\d{3})\b")


def _req(name):
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env: {name}")
    return v


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def extract_pdf_fields(pdf_bytes: bytes, tmp_path: str) -> dict:
    with open(tmp_path, "wb") as f:
        f.write(pdf_bytes)
    text = pypdf.PdfReader(tmp_path).pages[0].extract_text()

    parcel_m = PARCEL_RE.search(text)
    owner_m = re.search(
        r"\n([A-Z][A-Za-z ,.&'\-]{4,60})\n(?:REDEMPTION AMOUNT|July|August|September|[A-Z][a-z]+ \d{1,2}, 2026)",
        text,
    )
    legal_m = re.search(r"((?:[A-Z0-9][\w \-.'/,]{3,60}\n){1,4}OR \d+ P \d+)", text)
    owner = owner_m.group(1).strip() if owner_m else None
    if owner and "Clerk of the Circuit Court" in owner:
        owner = None
    return {
        "parcel_id": parcel_m.group(1) if parcel_m else None,
        "owner_name": owner,
        "legal_description": legal_m.group(1).replace("\n", " ").strip() if legal_m else None,
    }


def main() -> int:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    supa_key = _req("SUPABASE_SERVICE_ROLE_KEY")
    headers = {
        "apikey": supa_key,
        "Authorization": f"Bearer {supa_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    html = fetch(TD_URL).decode("utf-8", "ignore")
    pairs = re.findall(r'href=\s*"([^"]+\.pdf[^"]*)"[^>]*>\s*(2026-TXD-\d+)\s*</a>', html)
    print(f">>> wakulla_td_parcel_harvest | {len(pairs)} PDF links discovered on {TD_URL}")

    # Only bother with cases wakulla currently has in scope (avoids writing rows
    # for future tax deed cycles the calendar sweep hasn't ingested yet).
    existing = requests.get(
        f"{supa_url}/rest/v1/multi_county_auctions"
        "?county=eq.wakulla&sale_type=eq.tax_deed&parcel_id=is.null&select=case_number",
        headers=headers, timeout=20,
    ).json()
    missing_cases = {r["case_number"] for r in existing}
    if not missing_cases:
        print("NOTE: no wakulla tax_deed rows are missing parcel_id -- nothing to do")
        return 2
    print(f"    {len(missing_cases)} wakulla rows currently missing parcel_id: {sorted(missing_cases)}")

    updated = 0
    for href, case in pairs:
        if case not in missing_cases:
            continue
        path = href.split("?")[0]
        ts = href.split("?", 1)[1] if "?" in href else ""
        url = "https://wakullaclerk.org/" + urllib.parse.quote(path) + (("?" + ts) if ts else "")
        try:
            pdf_bytes = fetch(url)
            fields = extract_pdf_fields(pdf_bytes, f"/tmp/{case}.pdf")
        except Exception as e:
            print(f"  ! {case}: fetch/parse failed: {e}", file=sys.stderr)
            continue

        if not fields["parcel_id"]:
            print(f"  ! {case}: PDF parsed but no parcel # found (format not recognized yet)")
            continue

        patch = {k: v for k, v in fields.items() if v is not None}
        patch["source_url"] = url
        r = requests.patch(
            f"{supa_url}/rest/v1/multi_county_auctions?county=eq.wakulla&case_number=eq.{case}",
            headers=headers, json=patch, timeout=20,
        )
        if 200 <= r.status_code < 300:
            n = len(r.json()) if r.text else 0
            if n:
                updated += 1
                print(f"  + {case}: parcel_id={fields['parcel_id']}")
        else:
            print(f"  ! {case}: PATCH failed {r.status_code} {r.text[:200]}", file=sys.stderr)

    print(f"\nSUCCESS: updated {updated} wakulla tax_deed row(s) with parcel_id" if updated
          else "\nNOTE: zero rows updated this run")
    return 0 if updated else 2


if __name__ == "__main__":
    sys.exit(main())
