#!/usr/bin/env python3
"""GOLD STANDARD SHARD-7, dispatch loop run 3679 -- gadsden E parcel linkage,
2nd-round owner-name match for the residual 6 legal-description-only rows.

CONTEXT (verify-then-extend, not re-guess): a prior session
(20260704_shard11_gadsden_e_parcel_linkage.sql) already linked 10 of 16
gadsden foreclosure rows by exact street-address match against fl_parcels
WHERE co_no=30 (Gadsden's real parcel data -- CONFIRMED co_no=20 actually
holds Clay County data, a systemic +10 co_no shift documented in that
migration). The remaining 6 rows carry NO street address, only PLSS
legal descriptions ("Section 26, Township 2 North", "4 Parcels", etc.) --
structurally unmatchable by address.

THIS SESSION: tries owner-name matching instead, using the real defendant
surnames captured verbatim in scripts/shard8_gadsden_bootstrap.py at
original ingestion (2026-07-02) -- the live gadsdenclerk.com sheet has since
drifted (2 of the 6 case numbers, 25000942CA/25000827CA, are no longer on
the current sheet at all; the other 4 are still there and independently
re-confirmed against the raw HTML this session, see session evidence).

MATCHING RULE (conservative, BLANK > WRONG -- same pattern as
scripts/shard14_lake_e_ownername_match.py):
  Query fl_parcels WHERE co_no=30 AND own_name ILIKE '%<surname>%'.
  Accept ONLY if exactly one candidate survives. Ambiguous (>1) or zero
  hits -> leave parcel_id NULL, do not guess between multiple owners
  sharing a surname or between multiple parcels owned by the same entity.

RESULTS this session (6 candidates tried, full detail in code comments):
  25000545CA "Est. of Kourogenis"       -> KOUROGENIS ANASTASIA, 1 hit
                                           NATIONWIDE (not just co_no=30) ->
                                           UNIQUE MATCH, written.
  25000742CA "Heirs of Burger"          -> BURGER (2 hits: Elizabeth, Don)
                                           -> AMBIGUOUS, skipped.
  25000901CA "Ramon's Construction"     -> RAMONS CONSTRUCTION SERVICES L
                                           (2 hits, same entity, 2 adjacent
                                           parcels on Ridgewood Rd) ->
                                           AMBIGUOUS (can't tell which
                                           parcel is THIS foreclosure without
                                           more info), skipped.
  25000696CA "Est. of Booker-Barnes"    -> BOOKER (7 hits) / BARNES (10 hits)
                                           -> AMBIGUOUS, skipped.
  25000942CA "Woods"                    -> WOODS (10 hits) -> AMBIGUOUS,
                                           skipped. (Also: case no longer on
                                           live Clerk sheet to re-verify.)
  25000827CA "White"                    -> WHITE (10 hits) -> AMBIGUOUS,
                                           skipped. (Also: case no longer on
                                           live Clerk sheet to re-verify.)

Only 1 of 6 clears the conservative bar. Writes real fl_parcels data for
that 1 row: parcel_id, property_address (from phy_addr1+phy_city, real),
assessed_value (from jv, real appraisal -- replaces the judgment_amount
proxy), latitude/longitude (from centroid_lat/centroid_lng, real parcel
centroid -- replaces the Quincy county-seat centroid proxy for this row).
assessed_value_source and parity_source explicitly tag the provenance.

Does NOT touch zone_code/parcel_zones/zoning_districts -- see session
report for why I stays blocked (this county's zoning_districts R-1 entry
is an explicit HYPOTHESIS/synthetic placeholder from the original bootstrap,
and no real per-parcel zoning source is reachable this session -- all of
gadsdencountyfl.gov, qpublic.net return 403 in this sandbox; extending the
synthetic R-1 label to more parcels would compound fabrication, not fix it).

Usage: python3 scripts/shard7_run3679_gadsden_e_fix.py [--dry-run]
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

    # Verify the unique Kourogenis match, live, right now.
    q = urllib.parse.quote("*KOUROGENIS*")
    parcel_rows = rest_get(f"fl_parcels?own_name=ilike.{q}&select=*")
    if len(parcel_rows) != 1:
        log(f"FAIL-LOUD: expected exactly 1 KOUROGENIS match, got {len(parcel_rows)}. Aborting, no write.")
        sys.exit(1)
    p = parcel_rows[0]
    if p["co_no"] != 30:
        log(f"FAIL-LOUD: matched parcel co_no={p['co_no']}, expected 30 (Gadsden real data). Aborting.")
        sys.exit(1)

    auc_rows = rest_get("multi_county_auctions?case_number=eq.25000545CA&county=eq.gadsden&select=id,parcel_id,property_address,assessed_value")
    if len(auc_rows) != 1:
        log(f"FAIL-LOUD: expected exactly 1 auction row for 25000545CA, got {len(auc_rows)}. Aborting.")
        sys.exit(1)
    auc = auc_rows[0]
    if auc["parcel_id"] is not None:
        log(f"NOTE: 25000545CA already has parcel_id={auc['parcel_id']!r}, nothing to do. Exiting.")
        return

    address = f"{p['phy_addr1']}, {p['phy_city']}, FL {p['phy_zipcd']}".strip()
    payload = {
        "parcel_id": p["parcel_id"],
        "property_address": address,
        "assessed_value": p["jv"],
        "assessed_value_source": "fl_parcels_jv_verified_ownername_match",
        "latitude": p["centroid_lat"],
        "longitude": p["centroid_lng"],
        "parity_source": "e_match:fl_parcels_ownername_v1:kourogenis_unique_nationwide",
    }
    log(f"About to PATCH multi_county_auctions id={auc['id']} case=25000545CA with: {json.dumps(payload, indent=2)}")

    if DRY_RUN:
        log("DRY RUN -- no write performed.")
        return

    status, body = rest_patch(
        "multi_county_auctions",
        f"id=eq.{auc['id']}",
        payload,
    )
    log(f"PATCH result: HTTP {status}")
    if status not in (200, 204):
        log(f"FAIL-LOUD: write did not succeed cleanly. Body: {body}")
        sys.exit(1)
    if status == 200 and (not body or len(body) == 0):
        log("FAIL-LOUD: HTTP 200 but 0 rows returned -- write silently matched nothing. Aborting.")
        sys.exit(1)
    log(f"Wrote row: {body if status == 200 else '(return=minimal, but status ok)'}")

    # Re-fetch to confirm persisted.
    check = rest_get(f"multi_county_auctions?case_number=eq.25000545CA&select=parcel_id,property_address,assessed_value,latitude,longitude")
    log(f"Post-write verify: {check}")
    if not check or check[0]["parcel_id"] != p["parcel_id"]:
        log("FAIL-LOUD: post-write verification does not show expected parcel_id. Aborting claim of success.")
        sys.exit(1)
    log("VERIFIED: row now has real parcel_id + address + assessed_value + centroid geo from fl_parcels.")


if __name__ == "__main__":
    main()
