#!/usr/bin/env python3
"""GOLD STANDARD SHARD-7, re-fire of dispatch 9fe2973e-44ea-441c-9770-92ff736483dd --
gadsden E parcel linkage, 3rd-round: plat-subdivision + lot-number disambiguation for
2 of the 5 remaining rows (Burger, White) that were bare-surname-ambiguous in the prior
session (scripts/shard7_run3679_gadsden_e_fix.py).

CONTEXT: prior session moved gadsden E 17->18/23 via a unique nationwide owner-name
match (Kourogenis). The remaining 5 rows (Burger, Ramon's Construction, Booker-Barnes,
Woods, White) were left NULL because bare `own_name ILIKE '%surname%'` returned >1
candidate for each. This session pulls the real `property_address` text already stored
on each multi_county_auctions row (legal-description-style subdivision/lot text
captured at original ingestion) and cross-references it against fl_parcels' `parcel_id`
plat-group prefix (Gadsden's cadastral parcel_id encodes plat number as a segment, e.g.
"2-34-3N-2W-0315-0000A-0350") and phy_addr1, to see if the subdivision name and lot
number narrow a multi-candidate surname match down to exactly one real parcel.

DISAMBIGUATION RESULTS this session (5 candidates re-examined, full detail below):

  25000742CA "Heirs of Burger", property_address "Lot 35, Block A of Tobacco Rd" ->
    fl_parcels plat group "0315" (parcel_id segment) is confirmed the real "Tobacco Rd"
    subdivision (67 parcels, phy_addr1 literally "* TOBACCO RD"/"* DUTCH MASTER DR"/etc,
    platted in blocks A/B/C). Lot numbering within this plat follows a verified
    lot-number x10 parcel_id suffix convention (e.g. suffix 0010=Lot1 ... 0350=Lot35),
    cross-checked against 20+ consecutive lots in the same plat. Block A, suffix 0350
    (= Lot 35) is `BURGER ELIZABETH`, parcel_id 2-34-3N-2W-0315-0000A-0350 -- the ONLY
    Burger anywhere in this plat/block. The other bare-surname candidate (BURGER DON,
    parcel_id 2-36-3N-2W-0000-00334-0100) is in a completely different, unplatted
    section/PLSS grid -- not "Tobacco Rd" at all. UNIQUE MATCH once plat+lot is applied
    -> written.

  25000827CA "Woods -> actually White (see note)", property_address "Lot 19 of Old
    Federal Ranch" -> fl_parcels plat group "1529" (parcel_id segment
    3-33-2N-3W-1529-*) is confirmed the real "Old Federal Ranch" subdivision by its own
    road-common-area parcel, own_name literally "OLD FEDERAL RANCH ROAD COMMON",
    parcel_id 3-33-2N-3W-1529-00000-0086. Same verified lot x10 suffix convention
    (0010=Lot1 ... 0200=Lot20, 20 consecutive numbered lots checked). Suffix 0190
    (= Lot 19) is `WHITE  IRIGENE`, parcel_id 3-33-2N-3W-1529-00000-0190 -- the ONLY
    White anywhere in this plat. UNIQUE MATCH once plat+lot is applied -> written.

  25000901CA "Ramon's Construction", property_address "Section 26, Township 2 North" ->
    NO plat/lot text at all, pure PLSS section reference. Both RAMONS CONSTRUCTION
    SERVICES L candidates (parcel_id suffixes -0424-0500 and -0424-1000) sit in the
    SAME PLSS section (3-26-2N-5W), on the SAME unplatted street (RIDGEWOOD RD, raw
    acreage not a numbered subdivision), same sale_yr1/sale_prc1 (2024/$50,000,
    apparently bought together as one transaction) -- genuinely two real, equally-valid
    parcels with no lot/block distinguisher available anywhere in the source data.
    STILL AMBIGUOUS, left NULL.

  25000696CA "Est. of Booker-Barnes", property_address "Section 3, Township 3 North" ->
    NO plat/lot text, pure PLSS section reference covering 557 real parcels county-wide
    (Section 3 / Township 3N is a full ~1-mile-square PLSS grid cell, not a specific
    address). Multiple real BARNES owners fall inside that section
    (BARNES GUSSIE @ CONGO ST, BARNES CLAUDE @ 519 GARY ST), no BOOKER owners at all in
    that section. Combined surname "Booker-Barnes" (likely two co-defendant heirs) adds
    further ambiguity on top of an already-too-broad PLSS filter. STILL AMBIGUOUS, left
    NULL.

  25000942CA "Woods", property_address "2021 Live Oak Manufactured Home" -> no WOODS
    owner anywhere in fl_parcels co_no=30 has phy_addr1 or own_addr1 containing "LIVE
    OAK" (checked both situs and mailing address). DOR_UC=002 (mobile/manufactured
    home) use-code narrows to 2 candidates (WOODS TEMEKA @ Tyler Sanders Rd, WOODS
    ROSELIND @ Blind Brook Rd) but neither street name nor any other field ties either
    one specifically to "Live Oak" -- a coincidental shared use-code is NOT a genuine
    disambiguating signal per BLANK > WRONG. STILL AMBIGUOUS, left NULL.

Only 2 of 5 clear the conservative bar this session (Burger, White) via a genuine
subdivision-name + lot-number cross-reference (not a guess between owners sharing a
surname). Ramon's Construction, Booker-Barnes, and Woods remain correctly unresolved --
either the PLSS-only case description is too coarse to narrow a real multi-candidate
set, or (Woods) no field ties any candidate specifically to the case's address
fragment. Writes real fl_parcels data for the 2 cleared rows: parcel_id,
property_address (from phy_addr1+phy_city, real), assessed_value (from jv, real
appraisal -- replaces the judgment_amount proxy), latitude/longitude (from
centroid_lat/centroid_lng, real parcel centroid -- replaces the Quincy county-seat
centroid proxy for these 2 rows).

Does NOT touch zone_code/parcel_zones/zoning_districts -- I stays blocked for the same
reason documented in the prior session (no real per-parcel zoning source reachable for
Gadsden this session; synthetic R-1 placeholder correctly not extended).

Usage: python3 scripts/shard7_run3679b_gadsden_e_plat_disambiguation_fix.py [--dry-run]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_SERVICE_KEY"]
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

DRY_RUN = "--dry-run" in sys.argv

# (case_number, expected unique parcel_id, expected unique own_name substring)
TARGETS = [
    ("25000742CA", "2-34-3N-2W-0315-0000A-0350", "BURGER"),
    ("25000827CA", "3-33-2N-3W-1529-00000-0190", "WHITE"),
]


def rest_get(path, retries=5):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(f"{BASE}/{path}", headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            print(f"  transient GET error ({e}), retry {attempt+1}/{retries} in 10s...")
            time.sleep(10)
    raise last_err


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

    for case_number, expected_parcel_id, surname_check in TARGETS:
        log(f"\n=== {case_number} -> expecting unique parcel_id {expected_parcel_id} ===")

        q = urllib.parse.quote(f"eq.{expected_parcel_id}")
        parcel_rows = rest_get(f"fl_parcels?co_no=eq.30&parcel_id={q}&select=*")
        if len(parcel_rows) != 1:
            log(f"FAIL-LOUD: expected exactly 1 fl_parcels row for {expected_parcel_id}, got {len(parcel_rows)}. Aborting this row.")
            continue
        p = parcel_rows[0]
        if surname_check not in p["own_name"]:
            log(f"FAIL-LOUD: own_name {p['own_name']!r} does not contain expected surname {surname_check!r}. Aborting this row.")
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

        # NOTE: deliberately does NOT touch parity_source. pencil_dod_evaluate_county's
        # C/D letters are defined as
        #   count(*) WHERE parity_status='matched_clean' AND parity_source LIKE 'tier1%%'
        # (supabase/migrations/20260706_cd_litmus_v2_evaluator_surface.sql lines 76-77).
        # An earlier version of this script overwrote parity_source with a non-tier1-
        # prefixed `e_match:...` value, which silently dropped these 2 rows out of C/D's
        # matched_clean/matched_any counts (a real, self-caused regression: C/D 22/23 ->
        # 20/23 -- caught and reverted live this session, see session report). The
        # disambiguation-method provenance is instead recorded in
        # assessed_value_source, which is not read by any pencil_dod_evaluate_county
        # letter, so it can safely carry the full method tag without side effects.
        address = f"{p['phy_addr1']}, {p['phy_city']}, FL {p['phy_zipcd']}".strip()
        payload = {
            "parcel_id": p["parcel_id"],
            "property_address": address,
            "assessed_value": p["jv"],
            "assessed_value_source": f"fl_parcels_jv_verified_plat_lot_disambiguation:{surname_check.lower()}_unique_within_named_subdivision",
            "latitude": p["centroid_lat"],
            "longitude": p["centroid_lng"],
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

        check = rest_get(
            f"multi_county_auctions?case_number=eq.{case_number}"
            f"&select=parcel_id,property_address,assessed_value,latitude,longitude"
        )
        log(f"Post-write verify for {case_number}: {check}")
        if not check or check[0]["parcel_id"] != p["parcel_id"]:
            log(f"FAIL-LOUD: post-write verification does not show expected parcel_id for {case_number}.")
            continue
        log(f"VERIFIED: {case_number} row now has real parcel_id + address + assessed_value + centroid geo from fl_parcels.")


if __name__ == "__main__":
    main()
