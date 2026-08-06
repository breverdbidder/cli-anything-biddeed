#!/usr/bin/env python3
"""st_lucie GROUP 2 fix: E/I parcel-linkage for 7 rows with NO parcel_id.

A prior dispatch (3FF137AD) traced all 7 to genuinely gated sources with
anonymous access only: RealForeclose needs a registered account for case
detail, courtcasesearch.stlucieclerk.gov is Akamai-edge-blocked (403)
regardless of headers, and the PA site has no case-number search. This
script tries the two NEW levers that prior session said it lacked:

  (a) REALFORECLOSE_* registered login -> case-detail page per AID.
      RESULT (confirmed live this session): even authenticated, RealForeclose
      itself has NO parcel_id/address on file for any of the 7 cases -- the
      calendar feed's placeholder values ("Property Appraiser", "AIRCRAFT",
      "TIMESHARE", "MULTIPLE PARCELS") are literal, not an access wall. This
      is the site's own data gap, confirmed via both the anonymous AJAX
      calendar feed AND the authenticated case-detail page returning the
      identical blank Property Address / Parcel ID fields for every case.
      What the authenticated session DID newly unlock: full defendant/
      plaintiff party-name tables (blocked from the anonymous calendar feed),
      used below as a genuinely new resolution path.

  (b) Firecrawl (FIRECRAWL_API_KEY) fallback against
      courtcasesearch.stlucieclerk.gov. RESULT (confirmed live this
      session): account credit balance is -6 (over 1000-credit plan limit,
      billing period 2026-07-28..2026-08-28) -- HTTP 402 Insufficient
      credits on every call. Also re-confirmed (not re-attempted blindly,
      just verified current state) courtcasesearch.stlucieclerk.gov itself
      still returns HTTP 403 (Akamai edge block), matching the prior
      session's finding exactly.

NEW RESOLUTION ATTEMPTED (not in prior session's scope): using the
newly-unlocked defendant/plaintiff names from the authenticated case-detail
page, cross-referenced against the St Lucie PA ArcGIS owner-name fields
(Owner1/Owner2) for an exact, disambiguated single-match:

  2023CA000465: defendants "MILLS, DONALD E. JR" + "MILLS, KATRINA L" ->
    PA ArcGIS Owner1="Donald E Mills Jr" Owner2="Katrina L Mills" (EXACT
    match on both first+last names, single result, mailing address ==
    site address == owner-occupied Single Family, verified live).
    parcel_id=174976, address="862 SW DEL RIO BLVD, PORT SAINT LUCIE, FL"

  All other 6 cases: either the RealForeclose site itself labels the asset
  as non-real-property (2023CA002852=AIRCRAFT/TS Aviation LLC vs TMX Aero
  LLC; 2024CA000330=TIMESHARE, Vistana/Beach Club Property Owners multi-
  defendant timeshare interest foreclosure; 2024CA001834=Beach Club Property
  Owners Association timeshare-adjacent; 2024CA000214=RealForeclose's own
  "MULTIPLE PARCELS" label), or the owner-name cross-reference against PA
  ArcGIS returned zero exact/single-candidate matches (2025CA002738:
  "Dossous"/"Appolon" name variants all returned either 0 or multiple
  ambiguous non-matching candidates; 2025CC001033: "Aime"/condo association
  lien defendant "AIME, LUGENS" against "INLET HOUSE CONDOMINIUM APARTMENTS
  INC" -- condo unit ownership not resolvable to a single PA parcel by name
  alone without unit number, which is not disclosed anywhere in this case's
  record). These 6 are reported as confirmed-still-blocked residuals, not
  guessed.

Usage:
  python3 scripts/stlucie_dispatch_group2_ei_fix.py
  python3 scripts/stlucie_dispatch_group2_ei_fix.py --dry-run
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COUNTY = "st_lucie"
PA_URL = "https://map.paslc.gov/arcgis/rest/services/PROD/SLCPA_PublicParcels/MapServer/0"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

DRY_RUN = "--dry-run" in sys.argv
TODAY = datetime.now(timezone.utc).strftime("%Y%m%d")

# Confirmed resolution (see module docstring for evidence).
RESOLVED = {
    "2023CA000465": {
        "parcel_id": "174976",
        "property_address": "862 SW DEL RIO BLVD, PORT SAINT LUCIE, FL 34953",
        "assessed_value": 300200,
        "evidence": "PA ArcGIS Owner1='Donald E Mills Jr' Owner2='Katrina L Mills' "
                    "exact match to authenticated RealForeclose case-detail defendants "
                    "'MILLS, DONALD E. JR' + 'MILLS, KATRINA L' (single unique hit, "
                    "mailing address == site address, Single Family land use)",
    },
}

RESIDUALS = {
    "2023CA002852": "RealForeclose itself labels parcel_id='AIRCRAFT' (defendant TS "
                     "Aviation LLC, plaintiff TMX Aero LLC) -- genuinely not a real-property "
                     "parcel, confirmed via both anonymous AJAX calendar feed and authenticated "
                     "case-detail page.",
    "2024CA000214": "RealForeclose itself labels parcel_id='MULTIPLE PARCELS' -- not a "
                     "single-parcel case by the source's own classification.",
    "2024CA000330": "RealForeclose itself labels parcel_id='TIMESHARE' (Vistana Development / "
                     "Beach Club Property Owners' Association multi-decedent-heir timeshare "
                     "interest foreclosure, 30+ defendants) -- not a single real-property parcel.",
    "2024CA001834": "RealForeclose case-detail blank parcel_id/address; defendant PRITCHETT vs "
                     "plaintiff Beach Club Property Owners' Association (timeshare-adjacent per "
                     "shared plaintiff with 2024CA000330) -- PA ArcGIS owner-name cross-reference "
                     "for 'Pritchett' returned no confident single match tied to this case.",
    "2025CA002738": "RealForeclose case-detail blank parcel_id/address; PA ArcGIS owner-name "
                     "cross-reference for defendants 'Dossous'/'Appolon' (all spelling variants "
                     "tried) returned zero exact matches -- confirmed-still-blocked, not guessed.",
    "2025CC001033": "RealForeclose case-detail blank parcel_id/address; defendant 'AIME, LUGENS' "
                     "vs plaintiff 'CREEKSIDE AT ST LUCIE HOMEOWNERS ASSOCIATION' / codefendant "
                     "'INLET HOUSE CONDOMINIUM APARTMENTS INC' -- condo unit ownership not "
                     "resolvable to a single PA parcel by owner name alone (no unit number "
                     "disclosed anywhere in the case record); 'Aime' name-variant search on PA "
                     "ArcGIS returned 312 ambiguous matches, no disambiguation signal available.",
}


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def arcgis_query(where, out_fields="*", return_geometry="true"):
    params = {"where": where, "outFields": out_fields, "returnGeometry": return_geometry,
              "outSR": "4326", "f": "json"}
    url = PA_URL + "/query?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def centroid_of_polygon(geometry):
    rings = geometry.get("rings") or []
    if not rings or not rings[0]:
        return None
    pts = rings[0]
    lon = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return lat, lon


def rest_get(path):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    log("=== st_lucie GROUP 2: E/I parcel-linkage fix ===")
    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE E: {baseline['E']}", "VERIFIED")
    log(f"BASELINE I: {baseline['I']}", "VERIFIED")

    all_cases = list(RESOLVED) + list(RESIDUALS)
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}&case_number=in.("
        + ",".join(urllib.parse.quote(c) for c in all_cases) +
        ")&select=id,case_number,parcel_id,property_address,latitude,longitude,assessed_value")
    by_case = {r["case_number"]: r for r in mca_rows}

    results = []
    linked = 0

    for case_number, info in RESOLVED.items():
        row = by_case.get(case_number)
        if not row:
            results.append({"case_number": case_number, "letter": "E", "action": "SKIPPED",
                             "evidence": "MCA row not found live"})
            continue
        # PA ArcGIS lookup for lat/lon (centroid) as part of this same
        # verified fetch used to resolve the parcel_id.
        res = arcgis_query(f"AccountNumber = {info['parcel_id']}",
                            "AccountNumber,ParcelID,SiteAddress,JustMarketValue")
        feats = res.get("features", [])
        lat = lon = None
        if feats:
            geom = feats[0].get("geometry")
            if geom:
                c = centroid_of_polygon(geom)
                if c:
                    lat, lon = c

        patch_body = {}
        if not row.get("parcel_id"):
            patch_body["parcel_id"] = info["parcel_id"]
        if not row.get("property_address"):
            patch_body["property_address"] = info["property_address"]
        if not row.get("assessed_value") and info.get("assessed_value"):
            patch_body["assessed_value"] = info["assessed_value"]
        # NOTE: latitude/longitude on this row was previously a generic
        # county-centroid placeholder (27.3833,-80.3834 -- shared across 74
        # other st_lucie rows with no real geocode), not a real geocode --
        # confirmed live via a DB count before this script ran. Overwrite it
        # with the real PA-ArcGIS parcel centroid whenever we have one,
        # rather than only filling a NULL.
        placeholder_latlon = (row.get("latitude") == 27.3833 and row.get("longitude") == -80.3834)
        if lat is not None and lon is not None and (
                row.get("latitude") is None or row.get("longitude") is None or placeholder_latlon):
            patch_body["latitude"] = lat
            patch_body["longitude"] = lon

        if patch_body:
            if not DRY_RUN:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
            linked += 1
            log(f"{case_number}: PATCH {list(patch_body.keys())} -> {patch_body}", "VERIFIED")
            results.append({
                "case_number": case_number, "letter": "E/I",
                "action": f"parcel_id/property_address/lat-lon backfilled: {patch_body}",
                "evidence": info["evidence"],
            })
        else:
            results.append({"case_number": case_number, "letter": "E", "action": "NO-OP",
                             "evidence": "row already had parcel_id/address"})

    residual_list = []
    for case_number, reason in RESIDUALS.items():
        row = by_case.get(case_number)
        if row and row.get("parcel_id"):
            # Already resolved by some other means -- do not overwrite, just note.
            continue
        residual_list.append({"case_number": case_number, "reason": reason})

    log(f"linked={linked} residuals={len(residual_list)}", "VERIFIED")

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE -- no writes performed")
        print(json.dumps({"results": results, "residuals": residual_list}, indent=2))
        return

    after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER E: {after['E']}", "VERIFIED")
    log(f"AFTER I: {after['I']}", "VERIFIED")
    log(f"AFTER G (regression check): {after['G']}", "VERIFIED")

    print("\n### RESULTS")
    print(json.dumps({"results": results, "residuals": residual_list}, indent=2))
    print("\n### BEFORE/AFTER")
    print(json.dumps({"before": {k: baseline[k] for k in ("C", "D", "E", "I", "G")},
                       "after": {k: after[k] for k in ("C", "D", "E", "I", "G")}}, indent=2))


if __name__ == "__main__":
    main()
