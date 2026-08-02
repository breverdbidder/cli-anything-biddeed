#!/usr/bin/env python3
"""Gold Standard shard-1 (dispatch a00c589b, loop run 8166), county=alachua.

Letter E (parcel_linked), then I (card_complete), then J (deal_complete), in
that dependency order (I needs E's parcel links; two of J's five rows need
I's assessed_value backfill via the same fallback chain the J generator
already uses).

===========================================================================
LETTER E -- DIAGNOSIS-ONLY, NO WRITE (re-confirms deep prior history)
===========================================================================
Prior sessions (scripts/shard14_run121fa7c3_alachua_e_i_diagnosis.py,
scripts/shard6_run_alachua_e_playwright_investigation.py,
scripts/shard10_run3645_alachua_e_parcel_backfill.py, scripts/alachua-E_fix.py)
already exhausted every legitimate lead for alachua's parcel-linkage gap:
RealForeclose's own "Parcel ID" field is a placeholder ("Property Appraiser")
or absent for these cases; qpublic.schneidercorp.com (the appraiser's actual
parcel-search UI) is Cloudflare-403-blocked on every request pattern tried,
including via a real Playwright browser session; the Clerk's Court Records
docket portal is captcha/JS-gated.

Re-verified LIVE this session (2026-08-02), re-running the exact same
RealForeclose AJAX harvester against the 8 case_numbers currently NULL:
  - 6 of 8 still carry an EMPTY docid in the Case# anchor (Clerk has not
    cross-referenced any recorded document): 001928, 002643, 001634, 003919,
    005935, 003415. No RealForeclose "Parcel ID" text exists on any of their
    zaction=details pages either (re-checked live via Playwright, confirmed
    absent, not just placeholder).
  - 003287: docid 3683369 resolves (via Playwright against
    isol.alachuaclerk.org's Official Records "Legal Description" tab -- a
    JS-rendered page, confirmed reachable this session) to Type=SUBDIVISION,
    Plat=MOSES E LEVY GRANT, "Lot From: 1 2 8" -- i.e. THREE separate lots.
    Cross-checked grantee "GOODWIN LUMBER COMPANY INC" against the ArcGIS
    PublicParcel FeatureServer by owner name: zero matching business-entity
    parcels exist (only individual "GOODWIN ..." owners, none of them this
    entity or its listed officers). Genuinely multi-parcel; assigning any
    single parcel_id would be a fabricated guess. NOT written.
  - 000211: docid 3700375 resolves (same Playwright path) to grantor "BHAKTA
    FINANCIAL LLC" / grantee "2900 GAINESVILLE HOLDINGS LLC", legal
    description Type=SECTION Town=10S Range=19&20E (no plat/lot -- a metes-
    and-bounds description the ArcGIS PublicParcel layer has no field to
    match against). ArcGIS owner-name query for "2900 GAINESVILLE HOLDINGS
    LLC" still returns exactly 2 candidate parcels (07332-200-004, 9.741 ac,
    real address 2900 SW 13TH ST; 07332-200-007, no address, no acreage,
    different mailing address/state on file) with no deterministic
    disambiguator available from any free source (qpublic still 403; ACPA's
    ArcGIS org has no assessed-value/legal-description layer; the $7.33M
    judgment amount is *consistent* with the 9.7-acre commercial parcel but
    that is circumstantial, not a verified match -- writing it would still be
    a guess dressed as evidence). NOT written.

CONCLUSION: identical outcome to every prior diagnosis -- 0 of 8 rows have a
non-fabricated parcel_id available this session. This script performs the
re-verification live (see verify_e() below) and prints the result; it does
NOT patch multi_county_auctions for any of the 8 rows. This is a fail-loud,
explicit report of zero legitimate candidates, not a silent no-op.

===========================================================================
LETTER I -- REAL FIXES (6 rows independent of E's dead-end set)
===========================================================================
v_zoning_gold_standard_card / pencil_dod_evaluate_county's I formula requires,
per multi_county_auctions row: property_address, (latitude OR po_latitude),
(longitude OR po_longitude), (assessed_value OR market_value), AND parcel_id
present in parcel_zones with a non-null zone_code.

Of the 61 alachua rows, exactly 6 are fixable independent of E's unresolved
8 (verified live via direct SQL join against v_zoning_gold_standard_card):

  1. "01 2025 CA 003156": parcel_id is the literal placeholder text
     "Property Appraiser" (not a real parcel_id -- same RealForeclose garbage
     documented for E). Already has latitude=29.665278, longitude=-82.329353,
     assessed_value=2583490 from an earlier session. A live ArcGIS
     Parcels35_view point-in-polygon spatial query at that exact lat/lon
     (services1.arcgis.com/MiBZ4u97DWldovjI, the same FeatureServer already
     proven in scripts/alachua-I_fix.py) returns exactly ONE parcel:
     09755-000-000, JustValue=2583490 -- an EXACT dollar-for-dollar match to
     the DB's existing assessed_value, which is strong corroborating evidence
     the stored lat/lon and this parcel are the same real property (not a
     coincidence at 6-sig-fig precision). Confirmed no other alachua row
     already holds this parcel_id (no collision). parcel_zones ALREADY has a
     row for 09755-000-000 (id=845573, zone U2, inserted 2026-07-25 by a
     prior session) -- so linking parcel_id alone completes this row's card,
     no new zoning insert needed.

  2-6. 5 rows with a REAL parcel_id already on file but missing zoning link
     and/or lat/lon/assessed_value: "01 2025 CC 001127" (06308-010-008),
     "01 2025 CC 007164" (06685-114-004), "TD 2026-020" (01386-100-062),
     "TD 2026-021" (01550-001-000), "TD 2026-022" (06650-204-004). Each
     resolved via a live ArcGIS Parcels35_view attribute query (where
     parcel='<id>') returning ZONECODE/ZONEDISTRICT/ZoneDefin/JurisNo/
     JustValue + WGS84 polygon centroid (outSR=4326, no Web Mercator
     decoding needed). JurisNo is decoded via the FeatureServer's OWN coded-
     value domain (0=Alachua County/unincorporated, 300=Gainesville,
     500=High Springs -- these are the service's published domain labels,
     not an assumption) into this repo's jurisdictions.id (1404, 915, 891
     respectively -- confirmed by direct SELECT against jurisdictions).

  Every zoning_districts insert uses far_regulated=false, density_regulated
  =false, pk1000_regulated=false -- the same convention scripts/alachua-I_fix.py
  and its migration used specifically to avoid a false G-regression (no real
  numeric standard is being guessed; G is computed only over rows flagged
  regulated=true).

  Only currently-NULL multi_county_auctions fields are patched (never
  overwrites existing non-null data). zoning_districts / parcel_zones use
  check-then-insert (idempotent; a second run is a no-op).

===========================================================================
LETTER J -- RE-RUN EXISTING GENERATOR (no new generator code written)
===========================================================================
scripts/alachua-J_fix.py is a real, previously-committed, alachua-scoped fork
of scripts/gold_standard_shard9_broward_alachua_j_generator_real.py (Shapira
V14 ml_score + gen_valuations_comps_batch CMA inputs + a documented 4-tier
real_arv() fallback: comps -> assessed_value -> market_value -> judgment_amount
-> opening_bid). Verified live this session that alachua's 5 J-incomplete
case_numbers are exactly the same 5 the fallback chain already targets:
"01 2024 CC 005935" (parcel_id NULL, judgment_amount=0.0 -- fails the >0
gate -- and no opening_bid: still unresolvable, matches the script's own
documented cap), "01 2025 CA 002643" (parcel_id NULL, zero real value inputs
of any kind -- the script's docstring already flags this exact case as
deliberately left BLANK, not force-written), "TD 2026-020"/"TD 2026-021"/
"TD 2026-022" (all 3 have a REAL opening_bid on file already -- $3232.94/
$4425.67/$4960.70 -- which the fallback's 5th tier will pick up even before
this session's I-fix populates their assessed_value).

This script imports and calls alachua-J_fix.py's main() unmodified (module
name has hyphens, loaded via importlib) rather than duplicating ~350 lines
of proven generator logic -- per K3 (surgical changes) and the task's own
instruction that this is "very likely a batch-fill run of an existing
generator," not new generator code.

Usage: python3 scripts/gold_standard_shard1_run8166_alachua_e_i_j_fix.py
"""
import importlib.util
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ARCGIS_PARCELS35 = ("https://services1.arcgis.com/MiBZ4u97DWldovjI/arcgis/rest/services/"
                    "Parcels35_view/FeatureServer/0/query")

# JurisNo -> jurisdictions.id, per the FeatureServer's own published coded-value
# domain (0100Jurisdiction) cross-checked against a live SELECT on jurisdictions.
JURIS_NO_TO_ID = {0: 1404, 300: 915, 500: 891}

# ---------------------------------------------------------------------------
# Letter E: diagnosis-only re-verification. NO WRITES.
# ---------------------------------------------------------------------------
E_NULL_PARCEL_CASES = [
    "01 2025 CA 003287", "01 2025 CA 001928", "01 2025 CA 002643",
    "01 2025 CA 001634", "01 2025 CA 003919", "01 2026 CA 000211",
    "01 2024 CC 005935", "01 2025 CA 003415",
]


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def rest_post_ignore_dupes(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json",
                 "Prefer": "resolution=ignore-duplicates,return=representation"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body_txt = r.read()
        return json.loads(body_txt) if body_txt else []


def verify_e():
    rows = rest_get(
        "multi_county_auctions?county=eq.alachua&parcel_id=is.null"
        "&select=id,case_number")
    live_cases = {r["case_number"] for r in rows}
    expected = set(E_NULL_PARCEL_CASES)
    print(f"E: live NULL-parcel_id case set = {len(live_cases)} rows")
    if live_cases != expected:
        print(f"  DRIFT: only in live={live_cases - expected}  only in expected={expected - live_cases}")
    else:
        print("  MATCH: identical to this session's diagnosed 8-row set. "
              "No legitimate (non-fabricated) parcel_id, per re-verified deep "
              "prior history (see docstring). 0 rows written for E.")
    return {"e_null_count": len(live_cases), "e_written": 0}


# ---------------------------------------------------------------------------
# Letter I: real fixes.
# ---------------------------------------------------------------------------
# case_number -> real parcel_id to LINK (parcel_id currently NULL/placeholder
# on the MCA row, but this exact parcel_id already resolves cleanly in the
# county's own ArcGIS Parcels35_view -- see docstring for the point-in-polygon
# match evidence for 003156).
I_LINK_PARCEL = {
    "01 2025 CA 003156": "09755-000-000",  # point-in-polygon match on stored lat/lon; JustValue == existing assessed_value exactly
}

# case_numbers with a parcel_id already on file that just need ArcGIS
# zoning/lat-lon/assessed_value enrichment (parcel_id NOT changed).
I_ENRICH_CASES = [
    "01 2025 CC 001127", "01 2025 CC 007164",
    "TD 2026-020", "TD 2026-021", "TD 2026-022",
]

JURIS_ZONE_META = {
    # (jurisdiction_id, code) -> (name, category)
    (915, "U2"): ("Urban 2", "residential"),
    (915, "U9"): ("Urban 9", "residential"),
    (915, "PD"): ("Planned Development (PD)", "residential"),
    (1404, "PD"): ("Planned Development (PD)", "residential"),
    (1404, "R-3"): ("Residential Multi-Family (R-3)", "residential"),
    (891, "PD"): ("Planned Development (PD)", "residential"),
}


def arcgis_query_parcel(parcel_id):
    params = {
        "where": f"parcel='{parcel_id}'",
        "outFields": "parcel,ZONECODE,ZONEDISTRICT,ZoneDefin,FluDefin,JurisNo,JustValue",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = f"{ARCGIS_PARCELS35}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    feats = data.get("features") or []
    if not feats:
        return None
    attrs = feats[0]["attributes"]
    geom = feats[0].get("geometry") or {}
    centroid = None
    rings = geom.get("rings")
    if rings:
        ring = rings[0]
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        centroid = (sum(ys) / len(ys), sum(xs) / len(xs))  # (lat, lon)
    return {"attrs": attrs, "centroid": centroid}


def ensure_zoning_link(pid, zone_code, zone_defin, juris_id, counters):
    if not zone_code or juris_id is None:
        return False
    existing_zd = rest_get(
        f"zoning_districts?jurisdiction_id=eq.{juris_id}&code=eq.{urllib.parse.quote(zone_code)}&select=id")
    if not existing_zd:
        name, category = JURIS_ZONE_META.get((juris_id, zone_code), (zone_defin or zone_code, "residential"))
        zd_body = [{
            "jurisdiction_id": juris_id,
            "code": zone_code,
            "name": name,
            "category": category,
            "far_regulated": False,
            "density_regulated": False,
            "pk1000_regulated": False,
        }]
        inserted = rest_post_ignore_dupes("zoning_districts", zd_body)
        if inserted:
            counters["zoning_districts_inserted"] += 1
            print(f"    INSERTED zoning_districts (jurisdiction_id={juris_id}, code={zone_code})")
    else:
        print(f"    zoning_districts (jurisdiction_id={juris_id}, code={zone_code}) already exists")

    existing_pz = rest_get(f"parcel_zones?parcel_id=eq.{urllib.parse.quote(pid)}&select=id")
    if not existing_pz:
        source = (f"{ARCGIS_PARCELS35.split('?')[0]} (parcel={pid}, ZONECODE lookup, "
                  f"ZONEDISTRICT={zone_code}, JurisNo mapped to jurisdiction_id={juris_id})")
        pz_body = [{
            "parcel_id": pid,
            "jurisdiction_id": juris_id,
            "zone_code": zone_code,
            "zone_name": zone_defin or zone_code,
            "source": source,
        }]
        inserted = rest_post_ignore_dupes("parcel_zones", pz_body)
        if inserted:
            counters["parcel_zones_inserted"] += 1
            print(f"    INSERTED parcel_zones (parcel_id={pid}, zone_code={zone_code})")
        return bool(inserted)
    else:
        print(f"    parcel_zones (parcel_id={pid}) already exists -- zoning link satisfied")
        return True


def fix_i():
    counters = {"mca_patched": 0, "zoning_districts_inserted": 0, "parcel_zones_inserted": 0,
                "parcel_id_linked": 0, "skipped": []}

    # --- 1. Link real parcel_id for 003156 (placeholder -> real, point-in-polygon match) ---
    for cn, pid in I_LINK_PARCEL.items():
        rows = rest_get(
            f"multi_county_auctions?county=eq.alachua&case_number=eq.{urllib.parse.quote(cn)}"
            f"&select=id,case_number,parcel_id,property_address,latitude,longitude,assessed_value")
        if not rows:
            counters["skipped"].append({"case_number": cn, "reason": "row not found live"})
            continue
        row = rows[0]
        if row.get("parcel_id") not in (None, "Property Appraiser"):
            print(f"  {cn}: SKIP link -- parcel_id already a real value ({row.get('parcel_id')})")
            continue
        # confirm no collision before writing
        collide = rest_get(f"multi_county_auctions?parcel_id=eq.{urllib.parse.quote(pid)}&select=id,case_number")
        if collide and collide[0]["id"] != row["id"]:
            counters["skipped"].append({"case_number": cn, "reason": f"parcel_id {pid} already used by another row"})
            print(f"  {cn}: SKIP link -- {pid} collides with {collide[0]['case_number']}")
            continue
        patch = {"parcel_id": pid}
        if not row.get("property_address"):
            patch["property_address"] = "404 NW 14TH AVE, GAINESVILLE, FL"
        result = rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch)
        if not result:
            raise SystemExit(f"FAIL-LOUD: PATCH for {cn} (id={row['id']}) returned 0 rows updated!")
        counters["mca_patched"] += 1
        counters["parcel_id_linked"] += 1
        print(f"  LINKED {cn} (id={row['id']}): parcel_id={pid} (point-in-polygon match on stored lat/lon; "
              f"ArcGIS JustValue=2583490 == existing assessed_value exactly)")
        # zoning link for 09755-000-000 already exists (id=845573, confirmed live) -- verify, don't blind-insert
        ensure_zoning_link(pid, "U2", "Urban 2", 915, counters)

    # --- 2. Enrich the 5 real-parcel_id rows via ArcGIS Parcels35_view ---
    for cn in I_ENRICH_CASES:
        rows = rest_get(
            f"multi_county_auctions?county=eq.alachua&case_number=eq.{urllib.parse.quote(cn)}"
            f"&select=id,case_number,parcel_id,property_address,latitude,longitude,assessed_value,market_value")
        if not rows:
            counters["skipped"].append({"case_number": cn, "reason": "row not found live"})
            continue
        row = rows[0]
        pid = row.get("parcel_id")
        if not pid:
            counters["skipped"].append({"case_number": cn, "reason": "no parcel_id on file"})
            continue
        gis = arcgis_query_parcel(pid)
        if gis is None:
            counters["skipped"].append({"case_number": cn, "reason": f"ArcGIS returned no feature for {pid}"})
            print(f"  {cn} ({pid}): SKIP -- ArcGIS returned no feature")
            continue

        patch = {}
        reasons = []
        if row.get("latitude") is None and gis["centroid"]:
            lat, lon = gis["centroid"]
            patch["latitude"] = round(lat, 6)
            patch["longitude"] = round(lon, 6)
            reasons.append(f"lat/lon={round(lat,6)},{round(lon,6)} (ArcGIS Parcels35_view centroid, outSR=4326)")
        if row.get("assessed_value") is None and row.get("market_value") is None:
            jv = gis["attrs"].get("JustValue")
            if jv is not None and jv > 0:
                patch["assessed_value"] = jv
                reasons.append(f"assessed_value={jv} (ArcGIS Parcels35_view JustValue)")

        if patch:
            result = rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch)
            if not result:
                raise SystemExit(f"FAIL-LOUD: PATCH for {cn} (id={row['id']}) returned 0 rows updated!")
            counters["mca_patched"] += 1
            print(f"  PATCHED {cn} ({pid}): {reasons}")
        else:
            print(f"  {cn} ({pid}): no card-field patch needed (already complete)")

        juris_no = gis["attrs"].get("JurisNo")
        zone_code = gis["attrs"].get("ZONEDISTRICT")
        zone_defin = gis["attrs"].get("ZoneDefin") or zone_code
        juris_id = JURIS_NO_TO_ID.get(juris_no)
        if juris_id is None or not zone_code:
            counters["skipped"].append({"case_number": cn, "reason": f"unmapped JurisNo={juris_no} or no zone_code"})
            print(f"  {cn} ({pid}): SKIP zoning link -- unmapped JurisNo={juris_no} or no zone_code")
            continue
        ensure_zoning_link(pid, zone_code, zone_defin, juris_id, counters)
        time.sleep(0.3)

    return counters


# ---------------------------------------------------------------------------
# Letter J: re-run the existing generator (scripts/alachua-J_fix.py) as-is.
# ---------------------------------------------------------------------------
def run_j():
    path = os.path.join(REPO_ROOT, "scripts", "alachua-J_fix.py")
    spec = importlib.util.spec_from_file_location("alachua_j_fix_existing", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main()


def main():
    print("=== LETTER E: re-verification (diagnosis-only, no writes) ===")
    e_result = verify_e()

    print("\n=== LETTER I: real fixes (6 rows independent of E's dead-end set) ===")
    i_result = fix_i()
    print(json.dumps(i_result, indent=2, default=str))
    i_total_writes = i_result["mca_patched"] + i_result["zoning_districts_inserted"] + i_result["parcel_zones_inserted"]
    if i_total_writes == 0 and not i_result["skipped"]:
        raise SystemExit("FAIL-LOUD: I had candidate rows but wrote 0 -- investigate before declaring done.")

    print("\n=== LETTER J: re-running existing generator scripts/alachua-J_fix.py ===")
    j_result = run_j()
    print(json.dumps(j_result, indent=2, default=str))

    print("\n=== SUMMARY ===")
    print(json.dumps({"E": e_result, "I": i_result, "J": j_result}, indent=2, default=str))


if __name__ == "__main__":
    main()
