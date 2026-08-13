#!/usr/bin/env python3
"""GOLD STANDARD gadsden E/I -- resolve the 6-row parcel_id gap via CourtScribe
real-address discovery + fl_parcels(co_no=30) unique matching.

CONTEXT (verified live 2026-08-13): gadsden E=parcel_linked 59/65 (90.8%),
I=card_complete 59/65 (90.8%) -- 6 rows share the exact same 6 case_numbers,
all lacking parcel_id (I is structurally capped by E per pencil_dod_evaluate_county
construction: a card can't be complete without a linked parcel).

Prior sessions (scripts/shard7_run3679b_gadsden_e_plat_disambiguation_fix.py,
scripts/gold_standard_shard4_gadsden_dispatch_cefc3fb1_e_backfill.py,
GOLD_STANDARD_SHARD11_GADSDEN_DISPATCH_52bf028c_E_COURTSCRIBE_SESSION_REPORT.md)
established: (1) co_no=30 is confirmed for gadsden fl_parcels, (2) the clerk's
static sale sheet (Foreclosures_files/sheet001.htm) often carries only a bare
legal description (Lot/Block/Section text) with no street address, but (3) the
CourtScribe API (gadsdenclerk.com/CourtScribePublicInquiry/CourtScribe/*) --
discovered in a prior session for exactly this reason -- often has a REAL
street address in its case-index record even when the sale sheet doesn't.

This session queried CourtScribe SearchClerk for all 6 gap case_numbers and
found real street addresses for all 6 (including the 2 rows -- 25000952CA,
26000063CA -- that had NO address/owner at all in our multi_county_auctions
row). Cross-referenced each address/owner against fl_parcels(co_no=30):

  25000755CA "75 Cascade Falls Way, Havana" -> EXACT unique phy_addr1 match,
    parcel_id 2-26-3N-2W-1540-0000A-0230. own_name on that parcel is literally
    "75 CASCADE FALLS WAY HAVANA LA" -- self-confirming.
  25000900CA "80 Mary Brown Road, Quincy" -> EXACT unique phy_addr1 match,
    parcel_id 2-34-3N-3W-3330-00000-0020 (HILLS SHAMEIKA).
  25000952CA "70 Sugarmill Court, Havana" (address+owner were NULL in our
    row until CourtScribe lookup) -> EXACT unique phy_addr1 match ("70
    SUGARMILL CT"), parcel_id 2-33-3N-2W-0258-0000A-0370, own_name "DERICO
    SHIQUITA" -- matches CourtScribe defendant "SHAQUITA DERICO" (same
    person, transliteration variant) -- self-confirming.
  26000062CA "230 Buckskin Circle, Midway" -> EXACT unique phy_addr1 match,
    parcel_id 4-12-1N-3W-1510-0000A-0380, own_name "BAILEY KATRINA" --
    matches CourtScribe defendant "KATRINA L BAILEY" exactly -- self-confirming.
  26000143CA HUAPILLA MARIBEL (mailing addr only on CourtScribe, "135 Smith
    Cir, Tallahassee") -> unique own_name exact match (only "HUAPILLA
    MARIBEL" -- not a partial/surname match -- among 27+ other Huapilla-
    surname parcels), parcel_id 3-09-2N-5W-0000-00110-0200, situs "TOLAR-
    WHITE RD, GRETNA", own_addr1 "135 SMITH CIR LOT 4" matches CourtScribe
    mailing address exactly.
  26000063CA MDB INVESTMENTS "FL" LLC -> CourtScribe's case record alone was
    ambiguous (MDB owns exactly 2 gadsden parcels: Glory Rd and 1539 Rustling
    Pines Blvd, both sharing the same 1539 Rustling Pines Blvd mailing
    address). Disambiguated via the actual Final Judgment of Foreclosure PDF
    (CourtScribe GetDocumentPDF DocketID=12743551, filed 08/10/2026): the
    judgment's metes-and-bounds legal description explicitly references
    "the Westerly right of way line ... known as Glory Road, also being
    known as County Road #379-A" and "Section 8, Township 3 North, Range 4
    West" -- this is unambiguously the Glory Rd parcel (own_addr1 1359/1539
    Rustling Pines Blvd is the OWNER's mailing address for both parcels, not
    the foreclosed property's situs), parcel_id 2-09-3N-4W-0000-00330-0000.

All 6 writes use REAL fl_parcels(co_no=30) data: parcel_id, phy_addr1+phy_city
as property_address, jv as assessed_value, centroid_lat/centroid_lng as
lat/long. No fabrication. Does not touch zoning_districts/zone_standards/
parcel_zones -- G is unaffected by this script.

Usage: python3 scripts/gold_standard_gadsden_ei_courtscribe_backfill.py [--dry-run]
"""
from __future__ import annotations
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

CO_NO = 30
DRY_RUN = "--dry-run" in sys.argv

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# (case_number, expected unique parcel_id, expected own_name substring, method note)
TARGETS = [
    ("25000755CA", "2-26-3N-2W-1540-0000A-0230", "75 CASCADE FALLS WAY",
     "courtscribe_address:75_cascade_falls_way_havana"),
    ("25000900CA", "2-34-3N-3W-3330-00000-0020", "HILLS",
     "courtscribe_address:80_mary_brown_rd_quincy"),
    ("25000952CA", "2-33-3N-2W-0258-0000A-0370", "DERICO",
     "courtscribe_address_and_owner:70_sugarmill_ct_havana_derico_shiquita"),
    ("26000062CA", "4-12-1N-3W-1510-0000A-0380", "BAILEY",
     "courtscribe_address_and_owner:230_buckskin_cir_midway_bailey_katrina"),
    ("26000143CA", "3-09-2N-5W-0000-00110-0200", "HUAPILLA",
     "courtscribe_owner_unique_exact_match:huapilla_maribel_own_addr_confirmed"),
    ("26000063CA", "2-09-3N-4W-0000-00330-0000", "MDB",
     "final_judgment_pdf_legal_description:glory_rd_sec8_t3n_r4w_disambiguates_from_rustling_pines_parcel"),
]


def rest_get(path):
    req = urllib.request.Request(f"{BASE}/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def rest_patch(table, filters, data):
    url = f"{BASE}/{table}?{filters}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={**HEADERS, "Prefer": "return=representation"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main():
    log = print
    linked = 0

    for case_number, expected_parcel_id, owner_check, method in TARGETS:
        log(f"\n=== {case_number} -> expecting unique parcel_id {expected_parcel_id} ===")

        q = urllib.parse.quote(f"eq.{expected_parcel_id}")
        parcel_rows = rest_get(f"fl_parcels?co_no=eq.{CO_NO}&parcel_id={q}&select=*")
        if len(parcel_rows) != 1:
            log(f"FAIL-LOUD: expected exactly 1 fl_parcels row for {expected_parcel_id}, got {len(parcel_rows)}. Aborting this row.")
            continue
        p = parcel_rows[0]
        if owner_check not in (p["own_name"] or "").upper() and owner_check not in (p.get("phy_addr1") or "").upper():
            log(f"FAIL-LOUD: neither own_name {p['own_name']!r} nor phy_addr1 {p.get('phy_addr1')!r} contains expected token {owner_check!r}. Aborting this row.")
            continue

        auc_rows = rest_get(
            f"multi_county_auctions?case_number=eq.{case_number}&county=eq.gadsden"
            f"&select=id,parcel_id,property_address,assessed_value"
        )
        if len(auc_rows) != 1:
            log(f"FAIL-LOUD: expected exactly 1 auction row for {case_number}, got {len(auc_rows)}. Aborting this row.")
            continue
        auc = auc_rows[0]
        if auc["parcel_id"] is not None:
            log(f"NOTE: {case_number} already has parcel_id={auc['parcel_id']!r}, nothing to do.")
            continue

        address = f"{p['phy_addr1']}, {p['phy_city']}, FL {p.get('phy_zipcd') or ''}".strip()
        payload = {
            "parcel_id": p["parcel_id"],
            "property_address": address,
            "owner_name": p["own_name"],
            "assessed_value": p["jv"],
            "assessed_value_source": f"fl_parcels_jv_verified:{method}",
            "latitude": p.get("centroid_lat"),
            "longitude": p.get("centroid_lng"),
        }
        log(f"About to PATCH multi_county_auctions id={auc['id']} case={case_number} with: {json.dumps(payload, indent=2)}")

        if DRY_RUN:
            log("DRY RUN -- no write performed.")
            continue

        status, body = rest_patch(
            "multi_county_auctions",
            f"id=eq.{auc['id']}",
            payload,
        )
        log(f"PATCH result: HTTP {status}")
        if status not in (200, 204):
            log(f"FAIL-LOUD: write did not succeed cleanly for {case_number}. Body: {body}")
            continue
        if status == 200 and (not body or len(body) == 0):
            log(f"FAIL-LOUD: HTTP 200 but 0 rows returned for {case_number} -- write silently matched nothing.")
            continue
        log(f"Wrote row for {case_number}: {body if status == 200 else '(return=minimal, but status ok)'}")

        # NOTE: must scope by county=gadsden too -- case_number is not globally
        # unique across counties (e.g. 25000755CA also exists as an unrelated
        # charlotte-county row with its own distinct parcel_id/format; a bare
        # case_number filter here previously produced a false FAIL-LOUD after
        # a real, correct write to the gadsden row).
        check = rest_get(
            f"multi_county_auctions?case_number=eq.{case_number}&county=eq.gadsden"
            f"&select=parcel_id,property_address,assessed_value,latitude,longitude"
        )
        log(f"Post-write verify for {case_number}: {check}")
        if not check or check[0]["parcel_id"] != p["parcel_id"]:
            log(f"FAIL-LOUD: post-write verification does not show expected parcel_id for {case_number}.")
            continue
        log(f"VERIFIED: {case_number} row now has real parcel_id + address + assessed_value + centroid geo from fl_parcels.")
        linked += 1

    log(f"\n=== SUMMARY: {linked}/{len(TARGETS)} rows linked ===")


if __name__ == "__main__":
    main()
