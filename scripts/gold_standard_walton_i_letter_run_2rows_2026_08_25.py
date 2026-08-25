#!/usr/bin/env python3
"""Gold Standard walton letter I (property card completeness) — 2026-08-25
follow-up session targeting the two rows flagged as the highest-leverage
candidates by the dispatch prompt: 2026-0125TD and 25CA000531A.

RESULT: NO FIX APPLIED. Both target rows are confirmed genuine data ceilings
this session, via fresh independent live probes (not reused from memory).
Per Honesty Protocol / SHIP GATE this script performs ZERO writes. It exists
to record the evidence trail for this session so a future dispatch does not
re-attempt the same (now doubly-exhausted) leads.

============================================================================
BASELINE (verified live via pencil_dod_evaluate_county, 2026-08-25)
============================================================================
I: card_complete=144 of 153 (94.1%) — FAIL, need >=146/153 (95%). Gap = 2 rows
minimum. This exact 144/153 state was reached by the prior session
(scripts/gold_standard_walton_i_letter_run_85f2942e.py, dispatch 85f2942e,
2026-08-24), which fixed 10 rows (11 gap rows minus 1: 2026-0125TD held back
intentionally) and left 9 rows blocked: 2026-0125TD (address-less vacant
parcel) + 8 Bucket-B rows with no real parcel_id at all (25CA000531A among
them, plus 7 case numbers that all have data_source=calendar_sweep_mca_v3
bare-stub rows and no auction-detail-page data).

This session was dispatched specifically to re-attempt 2026-0125TD and
25CA000531A with a note that only 2 fixes total are needed.

============================================================================
ROW 1: 2026-0125TD (parcel 19-1N-17-04000-001-0110)
============================================================================
Missing field: property_address only (lat/lon/assessed_value already
present and correct — assessed_value=6323, source=walton_enerGov_arcgis_
gs_85f2942e). zoning-card join already satisfied: v_zoning_gold_standard_card
has this parcel_id with zone_code='General Agriculture' (verified live this
session).

Re-verified live this session, independently, via a DIFFERENT method than
the 2026-08-24 session's FL DOR PHY_ADDR1 check (spatial point-in-polygon,
not attribute join):
  1. Pulled the parcel's own polygon geometry from Walton EnerGov FeatureServer
     Layer 4 (Parcels), WHERE PARCELNO='19-1N-17-04000-001-0110'. Confirmed
     match: OWNER_NAME='VEGAS VISTAS LLC', APPRAISED_VALUE='6323' (matches
     our DB exactly), USE_CODE='0000', USE_DESC='VACANT', BLDG_VALUE='0',
     PA_TOT_ACRES='2.0000', LEGAL_1/2/3 = metes-and-bounds description (no
     platted subdivision/lot).
  2. Ran an intersects spatial query against EnerGov Layer 1 (Address Points)
     using this parcel's exact polygon geometry (not a radius/buffer —
     precise containment): 0 address points fall inside the parcel boundary.
  3. Cross-checked EnerGov Layer 9 ("EnerGov Address Parcel", the
     PARCELNO-to-FullAddr join layer) directly: FullAddr=null for this
     PARCELNO.
  4. A 500m radius search on Layer 1 around the parcel centroid returns 6
     nearby address points (all on Antioch Cemetery Rd, Ponce de Leon FL) —
     but NONE of them intersect this parcel's polygon, so none can be
     attributed to it without fabrication.

Three independent county/state authoritative sources (EnerGov attribute
join, EnerGov spatial point-in-polygon, and the 2026-08-24 session's FL DOR
Statewide Cadastral PHY_ADDR1 check, which was blank) now agree: this is a
genuinely address-less 2-acre vacant agricultural parcel. USE_DESC=VACANT,
BLDG_VALUE=0 confirms no structure exists to assign a situs address to.
This is a real data ceiling, not a scraper gap. BLANK > WRONG: left
untouched, no fabricated address.

============================================================================
ROW 2: 25CA000531A (parcel_id='TIMESHARE' placeholder)
============================================================================
sale_type=foreclosure. property_address already non-null ("Walton County
FL" — a county-level fallback placeholder, not a real situs address).
Missing: assessed_value; parcel_id is not a real STRAP.

Investigated this session whether a real parcel_id / assessed_value exists
for this timeshare-interest foreclosure:

  1. RealForeclose auction detail page (AID=1515605): re-confirmed HTTP 403
     via curl (matches 2026-08-24 finding) AND via a full headless-Chromium
     Playwright browser session (different mechanism than curl — rules out
     a TLS-fingerprint-specific block). Both return only the county splash
     page (title "RealForeclose- Walton County -Splash Page", ~16KB, no
     case data). This confirms the block is not curl-specific bot detection
     but a structural access gate on the case-detail route itself.
  2. Walton Clerk civil case index (civitekflorida.com/ocrs/county/66):
     re-confirmed JSF/PrimeFaces postback form (action=/ocrs/county/66/
     index.xhtml, ViewState-based) — no GET-queryable endpoint.
  3. waltonclerkfl.gov "record search" links resolve to
     orsearch.clerkofcourts.co.walton.fl.us (LandmarkWeb) — confirmed JS SPA,
     indexes recorded instruments (deeds/liens) by name/book-page, not civil
     case number to parcel_id.
  4. NEW this session: queried the FL DOR Statewide Cadastral (same endpoint
     used for Row 1) with a spatial intersects search around the row's
     stored lat/lon (30.6282, -86.1769, radius 300m). Result: exactly 1
     parcel found, PARCEL_ID='312N19180000010000', OWN_NAME='U S AIR FORCE
     BASE EGLIN', DOR_UC='081' (military). This proves the stored lat/lon
     is a generic/placeholder coordinate (it lands on Eglin AFB land, not
     any timeshare resort), corroborating that property_address="Walton
     County FL" is itself a county-level fallback geocode, not a real
     location — the calendar_sweep_mca_v3 ingestion never had real property
     data for this case to begin with.
  5. Structural/domain finding: Florida timeshare-interval foreclosures
     (mortgage on a fractional/weekly interest in a resort unit) are
     characteristically NOT assessed a discrete parcel_id or per-interest
     assessed_value in the county property appraiser's ad valorem tax roll.
     The underlying resort/condominium regime carries the real property
     parcel(s); individual timeshare weeks are personal-property-like
     interests, tracked by the resort HOA/management, not the county
     appraiser. No FL county GIS/CAMA system indexes per-week timeshare
     interests as separate parcels. This is consistent with parcel_id
     already being stored as the literal string 'TIMESHARE' (a deliberate
     scraper-side marker for "no real parcel exists for this sale type"),
     not a bug.

Conclusion: no real parcel_id or assessed_value is discoverable for this
row through any reachable source. Per BLANK > WRONG, left untouched.

============================================================================
FALLBACK POOL RE-CHECK (8 Bucket-B bare stubs, briefly re-probed for a new
lever since both primary targets are confirmed blocked)
============================================================================
19CA000472, 25CA000044, 25CA000142, 25CA000608, 26CA000030, 26CA000062: all
data_source='calendar_sweep_mca_v3', all sale_type=foreclosure, all
property_address/parcel_id/lat/lon/assessed_value NULL. All depend on the
same RealForeclose case-detail route confirmed structurally blocked above
(re-tested this session via both curl and headless Playwright — same splash
page, same 403 on direct JSON/preview endpoints). No new lever found. Not
pursued further this session (would require either RealAuction credential
access outside this pipeline's scope, or a manual clerk records request —
both out of scope for an automated dispatch).

============================================================================
CONCLUSION
============================================================================
I stays at 144/153 = 94.1% (FAIL) as a correct, evidence-backed data state.
Both rows named in this dispatch are genuine structural ceilings:
  - 2026-0125TD: address-less vacant land, reconfirmed via 3 independent
    sources (2 new methods this session: spatial point-in-polygon + Layer 9
    attribute join, on top of the prior session's FL DOR PHY_ADDR1 check).
  - 25CA000531A: timeshare-interest foreclosure with no discrete parcel in
    any Florida county CAMA/GIS system by domain characteristic, and the
    stored lat/lon is proven to be a fallback placeholder (lands on Eglin
    AFB, not a real property).

If I is ever to reach >=95% for walton, it requires either:
  (a) a future scraper that gains authenticated/allowed access to
      walton.realforeclose.com case-detail pages (currently 403 to both
      plain HTTP clients and headless browsers), unlocking the 8 Bucket-B
      rows, or
  (b) new upstream auction rows arriving that are naturally card-complete
      (raises the denominator's clean-row share without touching the 9
      known-blocked rows).

Usage:
  python3 scripts/gold_standard_walton_i_letter_run_2rows_2026_08_25.py
  (re-runs the live EnerGov spatial cross-check + FL DOR spatial check +
   RealForeclose reachability probes, then prints the before/after RPC eval;
   before == after by design, since zero writes are performed)
"""
from __future__ import annotations

import json
import math
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COUNTY = "walton"
SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

ENERG0V_BASE = "https://services1.arcgis.com/TaXHPwWfIMuzJ7Ov/arcgis/rest/services/EnerGov/FeatureServer"
FL_DOR_CADASTRAL = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query"
WALTON_CO_NO = 76

ROW1_PARCEL = "19-1N-17-04000-001-0110"
ROW1_CASE = "2026-0125TD"
ROW2_CASE = "25CA000531A"
ROW2_LAT, ROW2_LON = 30.6282, -86.1769
ROW2_AID = 1515605


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def rest_get(path):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def arcgis_query(base_url, params):
    url = base_url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def lonlat_to_webmercator(lon, lat):
    x = lon * 20037508.34 / 180
    y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180)
    y = y * 20037508.34 / 180
    return x, y


def check_row1_address():
    log(f"=== ROW 1: {ROW1_CASE} (parcel {ROW1_PARCEL}) ===")

    # zoning-card join check
    zc = rest_get(
        f"v_zoning_gold_standard_card?county=eq.walton&parcel_id=eq."
        f"{urllib.parse.quote(ROW1_PARCEL)}&select=parcel_id,zone_code")
    log(f"v_zoning_gold_standard_card join: {zc}", "VERIFIED")

    # EnerGov parcel attribute lookup
    d = arcgis_query(f"{ENERG0V_BASE}/4/query", {
        "where": f"PARCELNO='{ROW1_PARCEL}'",
        "outFields": "*", "returnGeometry": "true", "f": "json"})
    feats = d.get("features", [])
    if not feats:
        log("EnerGov Layer 4 (Parcels): NO MATCH", "VERIFIED")
        return False
    attrs = feats[0]["attributes"]
    geom = feats[0]["geometry"]
    log(f"EnerGov Layer 4 match: OWNER={attrs.get('OWNER_NAME')} "
        f"USE_DESC={attrs.get('USE_DESC')} APPRAISED_VALUE={attrs.get('APPRAISED_VALUE')} "
        f"BLDG_VALUE={attrs.get('BLDG_VALUE')} ACRES={attrs.get('PA_TOT_ACRES')}", "VERIFIED")

    # Layer 9 (EnerGov Address Parcel) attribute join
    d9 = arcgis_query(f"{ENERG0V_BASE}/9/query", {
        "where": f"PARCELNO='{ROW1_PARCEL}'",
        "outFields": "FullAddr,ShortAddress", "f": "json"})
    f9 = d9.get("features", [])
    full_addr = f9[0]["attributes"].get("FullAddr") if f9 else None
    log(f"EnerGov Layer 9 (Address Parcel join) FullAddr: {full_addr!r}", "VERIFIED")

    # spatial point-in-polygon against Layer 1 (Address Points) using exact parcel geometry
    geom_str = json.dumps({"rings": geom["rings"], "spatialReference": {"wkid": 102100}})
    d1 = arcgis_query(f"{ENERG0V_BASE}/1/query", {
        "geometry": geom_str, "geometryType": "esriGeometryPolygon",
        "inSR": "102100", "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*", "f": "json"})
    pts_inside = d1.get("features", [])
    log(f"EnerGov Layer 1 spatial point-in-polygon (exact parcel boundary): "
        f"{len(pts_inside)} address points intersect", "VERIFIED")

    if full_addr is None and len(pts_inside) == 0:
        log("CONCLUSION: genuinely no situs address for this parcel "
            "(vacant land, 2 independent live checks this session both "
            "negative, matches prior session's FL DOR PHY_ADDR1 blank "
            "finding). No fix applied.", "VERIFIED")
        return False
    else:
        log(f"UNEXPECTED: an address WAS found this session (full_addr={full_addr!r}, "
            f"pts_inside={len(pts_inside)}) — would need review before writing, "
            f"not auto-applied by this script.", "VERIFIED")
        return False


def check_row2_timeshare():
    log(f"=== ROW 2: {ROW2_CASE} (parcel_id='TIMESHARE' placeholder) ===")

    # RealForeclose reachability probe (curl-equivalent via urllib)
    url = f"https://walton.realforeclose.com/index.cfm?zaction=auction&zmethod=details&AID={ROW2_AID}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"})
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode(errors="replace")
            log(f"RealForeclose AID={ROW2_AID} HTTP {r.status}, "
                f"title-check: {'Splash Page' in body}", "VERIFIED")
    except Exception as e:
        log(f"RealForeclose AID={ROW2_AID} request error: {e}", "VERIFIED")

    # FL DOR spatial check on the row's stored lat/lon to test placeholder-coordinate theory
    x, y = lonlat_to_webmercator(ROW2_LON, ROW2_LAT)
    d = arcgis_query(FL_DOR_CADASTRAL, {
        "geometry": f"{x},{y}", "geometryType": "esriGeometryPoint",
        "inSR": "102100", "distance": "300", "units": "esriSRUnit_Meter",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "PARCEL_ID,PHY_ADDR1,OWN_NAME,DOR_UC,JV,CO_NO",
        "where": f"CO_NO={WALTON_CO_NO}", "f": "json"})
    feats = d.get("features", [])
    log(f"FL DOR spatial check near stored lat/lon ({ROW2_LAT},{ROW2_LON}), "
        f"300m radius: {len(feats)} parcel(s) found", "VERIFIED")
    for f in feats:
        log(f"  -> {f['attributes']}", "VERIFIED")
    if feats and "EGLIN" in str(feats[0]["attributes"].get("OWN_NAME", "")).upper():
        log("CONFIRMS stored lat/lon is a placeholder/fallback coordinate "
            "(lands on Eglin AFB military land, not a timeshare resort) — "
            "calendar_sweep_mca_v3 never captured real property data for "
            "this case. No real parcel_id/assessed_value discoverable. "
            "No fix applied.", "VERIFIED")
    return False


def main():
    log("=== walton I 2-row targeted re-check (2026-08-25 follow-up) ===")
    before = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BEFORE I: {before['I']}", "VERIFIED")

    row1_fixable = check_row1_address()
    row2_fixable = check_row2_timeshare()

    if not row1_fixable and not row2_fixable:
        log("Both target rows confirmed genuine data ceilings this session. "
            "Zero writes performed (correct per BLANK > WRONG).", "VERIFIED")

    after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER I: {after['I']}", "VERIFIED")

    print("\n### BEFORE/AFTER (expected identical -- zero writes performed)")
    print(json.dumps({"before": {"I": before["I"]}, "after": {"I": after["I"]}}, indent=2))


if __name__ == "__main__":
    main()
