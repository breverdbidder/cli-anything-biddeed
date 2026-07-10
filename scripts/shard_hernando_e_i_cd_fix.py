#!/usr/bin/env python3
"""
Hernando E/I/C/D fix (2026-07-10), dispatch_id 11df373c-d3d3-4778-b489-2c32d7af5545.

Part 1 -- Letter E (parcel_linked) + I (card_complete) for tax_deed rows:
  4 tax_deed rows have parcel_id IS NULL (2024-077TD, 2026-018TD, 2026-023TD,
  2026-024TD). Hernando County Property Appraiser publishes a live public ArcGIS
  FeatureServer (discovered this session via hernandocountypa-florida.us ->
  centralgis.hernandocountypa-florida.us -> ArcGIS Hub item 50dac409cf664b98aa845d01c9283288):

    https://services2.arcgis.com/x5zvhhxfUuRDntRe/arcgis/rest/services/Parcels/FeatureServer/0

  Field PARCEL_NUMBER is in the identical spaced format our DB already stores
  (e.g. "R22 222 19 2650 0010 0120"). We resolve each row's parcel via a
  point-in-polygon spatial query against the row's existing (already-populated)
  latitude/longitude -- this is unambiguous (exactly one parcel polygon contains
  any given point), unlike house-number+street-name text matching which produced
  a false positive for 224 W FORT DADE AVE (matched "224 Preston Hollow Dr" and
  "224 Callaway Ave" in Spring Hill before the point-in-polygon query correctly
  resolved to the Brooksville parcel). Verified live 2026-07-10: all 4 rows
  resolve to exactly one polygon each.

  Bonus: verified live that all 4 resolved parcel_ids ALSO already exist in
  v_zoning_gold_standard_card with a non-null zone_code for hernando -- so this
  same parcel_id write closes letter I (card_complete) for these 4 rows too
  (property_address + lat/lon + market_value were already present; parcel_id
  was the only missing card_complete predicate).

Part 2 -- Letter C/D (parity) for foreclosure mca_only rows:
  3 foreclosure rows (22000840CA, 25000578CA, 25001007CA) sit at
  parity_status='mca_only' for the 2026-07-28 auction date. Hernando's
  foreclosure lane is NOT a RealAuction AJAX platform (unlike most other FL
  counties in this pipeline) -- it is a weekly PDF sale list published at
  hernandoclerk.com. The 28-JULY-2026.pdf is a SCANNED IMAGE (CCITT-encoded,
  zero embedded text layer -- verified with PyMuPDF: page.get_text() returns
  empty string), which is why the existing shard3_hernando_fc_scraper.py's
  regex-over-extracted-text approach silently produces nothing for this
  document. This script OCRs the rendered page image with tesseract (installed
  this session: `apt-get install tesseract-ocr`) and does an EXACT case-number
  match against the 3 target rows before promoting -- no fuzzy matching.

  Verified live 2026-07-10: OCR text contains all 3 target case numbers with
  addresses that exactly match our existing property_address values
  (22000840CA -> 6187 GAINSBORO AVE SPRING HILL FL 34609;
   25000578CA -> 6466 TAPESTRY CIR SPRING HILL FL 34606;
   25001007CA -> 6882 REDBAY DR BROOKSVILLE FL 34602).

  parity_source uses the same 'tier1:' prefix convention already established
  for this county's prior successful promotions (tier1:hernando_clerk_pdf_reharvest:...)
  so it satisfies the evaluator's `parity_source LIKE 'tier1%'` requirement.

Letters B/F (verified outcomes / tier1 sold) are OUT OF SCOPE for this script --
diagnosed this session as genuinely undefined right now: all 23 hernando rows
have auction_status='upcoming' with future auction_date (2026-06-30 through
2026-07-28) and sold_amount IS NULL. No closed hernando auctions currently
exist in the DB to verify against. See session report residual_gaps.

Usage: python3 scripts/shard_hernando_e_i_cd_fix.py
Idempotent: E/I patches only touch rows where parcel_id IS NULL; C/D promote
only patches rows where parity_status != 'matched_clean'.
"""
import os
import re
import sys
import json
import time
import tempfile
import urllib.request
import urllib.parse
import http.cookiejar

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

PARCELS_FEATURESERVER = (
    "https://services2.arcgis.com/x5zvhhxfUuRDntRe/arcgis/rest/services/"
    "Parcels/FeatureServer/0/query"
)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

FC_PDF_URL = (
    "https://hernandoclerk.com/wp-content/uploads/_Documents/Foreclosures/"
    "Foreclosure%20Sale%20Lists/2026/07-July/28%20JULY.pdf"
)
CD_TARGET_CASES = {"22000840CA", "25000578CA", "25001007CA"}
PARITY_SOURCE_LABEL = "tier1:hernando_clerk_pdf_ocr:foreclosure:2026-07-28"


def rest_get(path):
    req = urllib.request.Request(f"{BASE}/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{BASE}/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={**HEADERS, "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rpc(name, body):
    req = urllib.request.Request(
        f"{BASE}/rpc/{name}", data=json.dumps(body).encode(), method="POST",
        headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


# ---------------------------------------------------------------------------
# Part 1: Letter E/I -- parcel_id backfill via point-in-polygon ArcGIS query
# ---------------------------------------------------------------------------

def query_parcel_by_point(lon, lat):
    params = {
        "geometry": json.dumps({"x": lon, "y": lat}),
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "PARCEL_NUMBER,SITUS_ADDRESS,SITUS_CITY",
        "f": "json",
    }
    url = PARCELS_FEATURESERVER + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    feats = d.get("features", [])
    if len(feats) != 1:
        return None
    return feats[0]["attributes"]


def fix_e_i():
    rows = rest_get(
        "multi_county_auctions?county=eq.hernando&auction_type=eq.tax_deed"
        "&parcel_id=is.null&select=id,case_number,property_address,latitude,longitude"
    )
    print(f"[E/I] {len(rows)} tax_deed rows with parcel_id IS NULL")
    fixed = []
    for row in rows:
        lat, lon = row.get("latitude"), row.get("longitude")
        if lat is None or lon is None:
            print(f"  SKIP {row['case_number']}: no lat/lon to query against")
            continue
        attrs = query_parcel_by_point(lon, lat)
        if not attrs or not attrs.get("PARCEL_NUMBER"):
            print(f"  NO MATCH {row['case_number']} at ({lat},{lon})")
            continue
        parcel_id = attrs["PARCEL_NUMBER"]
        print(f"  MATCH {row['case_number']} -> {parcel_id} "
              f"({attrs.get('SITUS_ADDRESS')}, {attrs.get('SITUS_CITY')})")
        rest_patch(f"multi_county_auctions?id=eq.{row['id']}", {"parcel_id": parcel_id})
        fixed.append((row["case_number"], parcel_id))
    if rows and not fixed:
        raise SystemExit("FAIL-LOUD: parsed >0 E-gap rows but fixed 0 -- not silently swallowing")
    print(f"[E/I] parcel_id backfilled for {len(fixed)} rows: {fixed}")
    return fixed


# ---------------------------------------------------------------------------
# Part 2: Letter C/D -- OCR the scanned foreclosure PDF, exact-match, promote
# ---------------------------------------------------------------------------

CASE_NUM_RE = re.compile(r"\b(\d{8}CA)\b")


def ocr_pdf_text(pdf_bytes):
    import fitz  # PyMuPDF
    import subprocess
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_bytes)
        pdf_path = f.name
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        native_text = page.get_text()
        if native_text.strip():
            doc.close()
            return native_text
        pix = page.get_pixmap(dpi=300)
        png_path = pdf_path.replace(".pdf", ".png")
        pix.save(png_path)
        doc.close()
        result = subprocess.run(
            ["tesseract", png_path, "stdout", "--psm", "6"],
            capture_output=True, text=True, timeout=60)
        os.unlink(png_path)
        if result.returncode != 0:
            raise RuntimeError(f"tesseract failed: {result.stderr[:300]}")
        return result.stdout
    finally:
        os.unlink(pdf_path)


def fix_c_d():
    req = urllib.request.Request(FC_PDF_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        pdf_bytes = r.read()
    text = ocr_pdf_text(pdf_bytes)
    found_cases = set(CASE_NUM_RE.findall(text))
    print(f"[C/D] OCR extracted {len(found_cases)} case numbers from 28-JULY-2026.pdf")

    matches = found_cases & CD_TARGET_CASES
    print(f"[C/D] target mca_only cases found on PDF: {matches}")
    if not matches:
        raise SystemExit("FAIL-LOUD: OCR produced text but 0 of 3 target case numbers matched")

    mca_rows = rest_get(
        "multi_county_auctions?county=eq.hernando&sale_type=eq.foreclosure"
        "&select=id,case_number,parity_status"
        "&or=(data_source.neq.propertyonion,data_source.is.null)"
    )
    ids_to_promote = [
        r["id"] for r in mca_rows
        if r["case_number"] in matches and r["parity_status"] != "matched_clean"
    ]
    if not ids_to_promote:
        print("[C/D] all matched rows already matched_clean -- nothing to promote")
        return matches
    id_filter = ",".join(ids_to_promote)
    rest_patch(
        f"multi_county_auctions?id=in.({id_filter})",
        {"parity_status": "matched_clean", "parity_source": PARITY_SOURCE_LABEL},
    )
    print(f"[C/D] promoted {len(ids_to_promote)} rows to matched_clean "
          f"(parity_source={PARITY_SOURCE_LABEL})")
    return matches


if __name__ == "__main__":
    print("=== Hernando E/I parcel backfill ===")
    fix_e_i()
    print()
    print("=== Hernando C/D OCR promotion ===")
    fix_c_d()
    print()
    print("=== pencil_dod_evaluate_county('hernando') AFTER ===")
    result = rpc("pencil_dod_evaluate_county", {"p_county": "hernando"})
    print(json.dumps(result, indent=2))
