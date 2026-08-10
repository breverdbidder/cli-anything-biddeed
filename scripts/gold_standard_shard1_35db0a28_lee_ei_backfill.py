#!/usr/bin/env python3
"""Gold Standard shard-1 (dispatch 35db0a28): Lee County E (parcel linkage) +
I (property card completeness) backfill via the Lee County ArcGIS
FeatureServer (proven live endpoint, reused from
scripts/gold_standard_shard5_lee_ei_arcgis_backfill.py and
scripts/gold_standard_shard12_lee_ei_backfill.py):

  https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/
  Lee_County_Parcels/FeatureServer/0/query

Live baseline this session (2026-08-10): E FAIL 94.7 (305/322), I FAIL 92.9
(299/322). 23-row gap: 17 rows with parcel_id IS NULL (E gap, all also
counted in I's gap), plus 6 rows with parcel_id present but not
zone-linked/geo/value-incomplete (I-only gap).

Resolved (2 rows):
  1. 18-CC-004510 (I-only gap): parcel_id='22432400000020000' already
     present. ArcGIS STRAP query returned ZONING='MH-2', a code with
     existing zoning_districts precedent under jurisdiction_id=630
     (unincorporated Lee). Inserted parcel_zones row + backfilled
     latitude/longitude/assessed_value (all real ArcGIS values, address on
     file was a mobile-home-park lot; the ArcGIS SITEADDR for the parent
     parcel differs, which is expected for MH lot-in-park cases -- STRAP
     match itself is exact and unambiguous).
  2. 25-CA-004959 (E gap, address on file: "2825 PALM BEACH BLVD, FORT
     MYERS, FL 33916"): exact SITEADDR match in ArcGIS -> STRAP
     '184425P10370000CE' (a Common Element parcel). Backfilled parcel_id +
     real lat/lng + the source's real assessed_value (0 -- genuinely $0
     taxable value for a CE parcel, not fabricated). ZONING was blank in
     ArcGIS for this STRAP, so no parcel_zones row was inserted (would
     require guessing a zone code) -- this row therefore still fails I's
     zone-link requirement and remains an I-only residual even though it
     resolved E.

Residual (21 rows, NOT fabricated):
  - 15 of the 17 E-gap rows have NO property_address and NO parcel_id:
    17-CA-003958, 25-CA-000630, 25-CA-001853, 25-CA-003243, 25-CA-003281,
    25-CA-003295, 25-CA-003836, 25-CA-004751, 25-CA-004836, 25-CA-005293,
    25-CA-006176, 25-CA-006956, 25-CA-007015, 25-CA-007139, 25-CC-010740.
    Attempted Lee's public RealForeclose calendar
    (lee.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR) and the
    per-date AUCTION/PREVIEW pages for known auction dates (8/13/2026,
    8/20/2026 etc) -- confirmed LIVE that the case-level grid is populated
    client-side and any DETAIL/SEARCH-by-case-number request redirects to
    the login "Splash Page" ("User Name or Password is Invalid" form) with
    zero case data exposed pre-auth. This is a genuine auth-gated dead end,
    not a CAPTCHA, but no case number/address/parcel path exists from
    public unauthenticated fetches. Not attempted: any login/stealth
    workaround (out of scope per hard policy boundary).
  - 24-CC-004249 (address "16300 PINE RIDGE RD LOT X18, FORT MYERS, FL
    33908"): no ArcGIS SITEADDR match for "16300 PINE RIDGE RD" or any
    nearby house-number range on Pine Ridge Rd (mobile-home lot address,
    same root cause class as 18-CC-004510 -- the park's platted address
    doesn't match the parent parcel's SITEADDR). No confident STRAP
    resolution; not guessed.
  - 24-CA-007460 (address "155/157 LUCILLE AVE, FORT MYERS, FL 33905"):
    no exact ArcGIS SITEADDR match for 155 or 157; existing parcel_id value
    'Property Appraiser' is itself a placeholder from an earlier ingest.
    Nearby LUCILLE AVE STRAPs exist (133, 144, 146, 166, 170, 173, 174,
    177, 178) but none at 155/157 -- resolving to any of these would be a
    guess. Left as residual.
  - 25-CA-003367 (parcel_id='MULTIPLE PARCEL') and 25-CA-004116
    (parcel_id='TIMESHARE'): no property_address on file, structurally not
    resolvable to a single STRAP via address search. Left as residual.
  - 24-CA-003913 (STRAP 25-46-22-T1-00600.0120) and 25-CA-004684 (STRAP
    34-46-22-T2-0080B.0140): both real Sanibel STRAPs, found live in the
    Lee County ArcGIS layer with real lat/lng/assessed values already on
    file, but ArcGIS's ZONING field is blank/None for both -- Sanibel
    maintains its own zoning system separate from unincorporated Lee's
    parcel layer. No zone code available from this source; inserting one
    would be fabrication. Left as residual (I-only).

Verified live via public.pencil_dod_evaluate_county_rows('lee'):
  BEFORE: E FAIL metric=94.7 parcel_linked=305 of 322 | I FAIL metric=92.9 card_complete=299 of 322
  AFTER:  E PASS  metric=95.0 parcel_linked=306 of 322 | I FAIL metric=93.2 card_complete=300 of 322
"""
import json
import os
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
LEE_ARCGIS = "https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/Lee_County_Parcels/FeatureServer/0/query"


def sb_get(path, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(url, headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch(path, params, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}?{params}", data=body,
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def sb_post(path, data, prefer="return=minimal"):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=body,
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}",
                 "Content-Type": "application/json", "Prefer": prefer},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def query_arcgis_by_strap(strap):
    params = urllib.parse.urlencode({
        "where": f"STRAP = '{strap}'",
        "outFields": "STRAP,ZONING,LATITUDE,LONGITUDE,ASSESSED,JUST,SITEADDR,SITECITY",
        "f": "json", "resultRecordCount": 5,
    })
    req = urllib.request.Request(f"{LEE_ARCGIS}?{params}", headers={"User-Agent": "BidDeed-SHARD1-35db0a28"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    feats = data.get("features", [])
    return feats[0]["attributes"] if feats else None


def query_arcgis_by_address(siteaddr):
    params = urllib.parse.urlencode({
        "where": f"SITEADDR = '{siteaddr.upper()}'",
        "outFields": "STRAP,ZONING,LATITUDE,LONGITUDE,ASSESSED,JUST,SITEADDR,SITECITY",
        "f": "json", "resultRecordCount": 5,
    })
    req = urllib.request.Request(f"{LEE_ARCGIS}?{params}", headers={"User-Agent": "BidDeed-SHARD1-35db0a28"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    feats = data.get("features", [])
    return feats[0]["attributes"] if feats else None


def main():
    # ---- Fix 1: 18-CC-004510 (I-only gap, real STRAP already on file) ----
    strap = "22432400000020000"
    attrs = query_arcgis_by_strap(strap)
    print(f"18-CC-004510 STRAP {strap} -> {attrs}")
    if attrs and attrs.get("ZONING") == "MH-2":
        status, _ = sb_patch(
            "multi_county_auctions", "case_number=eq.18-CC-004510",
            {"latitude": attrs["LATITUDE"], "longitude": attrs["LONGITUDE"],
             "assessed_value": attrs["ASSESSED"]},
        )
        print("geo/value patch status:", status)
        # jurisdiction_id=630 (unincorporated Lee) has MH-2 in zoning_districts
        # -- verified via SELECT before insert, see script docstring.
        status2, resp2 = sb_post("parcel_zones", [{
            "parcel_id": strap, "jurisdiction_id": 630,
            "zone_code": "MH-2", "zone_name": "MH-2",
            "source": "shard1_35db0a28_lee_arcgis",
        }], prefer="resolution=ignore-duplicates,return=minimal")
        print("parcel_zones insert status:", status2, resp2[:200])

    # ---- Fix 2: 25-CA-004959 (E gap, has address) ----
    addr = "2825 PALM BEACH BLVD"
    attrs2 = query_arcgis_by_address(addr)
    print(f"25-CA-004959 addr '{addr}' -> {attrs2}")
    if attrs2 and attrs2.get("STRAP"):
        patch = {"parcel_id": attrs2["STRAP"]}
        if attrs2.get("LATITUDE") is not None:
            patch["latitude"] = attrs2["LATITUDE"]
            patch["longitude"] = attrs2.get("LONGITUDE")
        if attrs2.get("ASSESSED") is not None:
            patch["assessed_value"] = attrs2["ASSESSED"]
        status, _ = sb_patch("multi_county_auctions", "case_number=eq.25-CA-004959", patch)
        print("25-CA-004959 patch status:", status, patch)
        # ZONING was blank for this STRAP -- no parcel_zones insert (would
        # be fabrication). Row remains an I-only residual.

    print("\nRun SELECT * FROM public.pencil_dod_evaluate_county_rows('lee') to verify.")


if __name__ == "__main__":
    main()
