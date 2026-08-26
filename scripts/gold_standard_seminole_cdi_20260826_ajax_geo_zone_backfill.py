#!/usr/bin/env python3
"""GOLD STANDARD seminole C/D/I fix, 2026-08-26 session.

CONTEXT (VERIFIED live, pencil_dod_evaluate_county('seminole'), 2026-08-26
session start): auctions_total grew 148->157 (9 net new rows) since the last
seminole session (2026-08-24, migration
20260824_gold_standard_seminole_cdi_15row_ajax_geo_zone_backfill.sql, which
raised C/D to 145/148=98.0% and I to 142/148=95.9%). Confirmed that
migration's writes are still live (all 9 old case_numbers re-queried
matched_clean with tier1:seminole_ajax_harvest_20260824 parity_source, all 9
parcel_zones rows present) -- this is a fresh regression from continued
calendar growth, not a rollback.

  C: matched_clean=145 of 157 = 92.4%  FAIL (need >=95% = 150/157, gap=12)
  D: matched_any=145   of 157 = 92.4%  FAIL (same 12-row gap as C)
  I: card_complete=142 of 157 = 90.4%  FAIL (need >=150/157, gap=8)

Same pattern as every prior seminole session: these are calendar_sweep_mca_v3
rows created after the last parity/card pass, never yet reconciled against
the live RealForeclose/RealTaxDeed calendar.

FIX METHOD (C/D) -- reuses scripts/shard2_run2450_ajax_realforeclose_harvest.py
verbatim (proven RealAuction-family AJAX harvester), same technique as
scripts/shard14_run3534_seminole_cd_e_i_fix.py /
scripts/shard1_seminole_run_ecb6f64b_cd_i_fix.py:
  - 9 of the 12 target case_numbers hit exact case_number matches on the live
    seminole.realforeclose.com calendar for auction_date=2026-09-22 and
    seminole.realtaxdeed.com for 2026-10-15.
  - 3 (2016CA000953 auction_date 2026-08-27, 2024CA002388 and 2025CA002908
    both auction_date 2026-09-15) were also cross-checked against the
    existing realforeclose_aids table (populated by the independent
    scrape-realauction-county.yml pipeline) and found an exact case_number
    match there too.
  All 12 matches are exact case_number matches against a live/independently
  scraped RealAuction-family calendar record for the SAME case_number -- no
  PropertyOnion litmus used (data_source stays calendar_sweep_mca_v3,
  unaffected).

FIX METHOD (I) -- for the 15 pre-existing I-gap rows referenced in the
dispatch: 9 already have full card fields (address/geo/value/parcel_id) and
need ONLY a parcel_zones link; the other 6 are the same class of
non-property-record garbage already documented in the 2026-08-24 migration
(SYN- synthetic parcel_id, "ALCOHOLIC LICENSE" / "MULTIPLE PARCELS" /
"LIQUORE LICENSE" / "Property Appraiser" scrape-artifact parcel_ids) --
these remain honestly blocked, not fabricated.

Of the 9 zone-linkable rows, live re-diagnosis this session found only 6
still lack a parcel_zones row (the other 3 already got linked incidentally
by a prior session run against an overlapping case list):
  2025CA001187  10-20-30-5CT-0G00-0060  Sanford
  2025CA002094  02-21-30-509-0000-1930  Winter Springs
  2026CA000914  31-19-31-525-0J00-0030  Sanford
  2025CA001137  33-19-30-5QS-0000-0230  Sanford
  2024CA002295  16-20-30-300-053A-0000  Lake Mary
  SYN-SEM-2025CA000629 (case 2025CA000629) -- NOT a real parcel (synthetic
    placeholder minted when no address/parcel could be scraped originally;
    confirmed this session via realforeclose_aids AND a fresh live AJAX
    harvest of its 2026-03-17 auction date -- both sources return the same
    "Property Appraiser" anchor-text scrape artifact instead of a real
    parcel number). NOT zone-linked. Genuine data ceiling, reported not
    guessed.

ZONING SOURCE FOR THE 5 REAL PARCELS (all VERIFIED live, 2026-08-26). The
scpafl.org/gis.scpafl.org avenues used by the 2026-08-24 session are DEAD
this session (see below) -- found and used a DIFFERENT live source instead:
each target address sits inside an INCORPORATED Seminole municipality
(Sanford/Winter Springs/Lake Mary), and each of those 3 cities publishes its
OWN parcel-level zoning layer as a public (token-free) ArcGIS Online hosted
Feature Service, discoverable via the ArcGIS Online portal search API
(www.arcgis.com/sharing/rest/search):
  - Sanford:        "Zoning" (owner jonesm1961) --
    services1.arcgis.com/EPXb1p5YttfWtj8l/arcgis/rest/services/Zoning/FeatureServer/0
    fields ZONECODE/ZONEDESC; point-in-polygon query (geometry=lon,lat,
    inSR=4326) against our existing lat/lon.
  - Winter Springs:  "Planning_WFL1" layer 5 "Zoning" (owner WinterSpringsGIS) --
    services5.arcgis.com/hbtBppF7t3PpouVf/arcgis/rest/services/Planning_WFL1/FeatureServer/5
    fields PIN (dashless STRAP)/TYPE; queried BOTH by
    PIN='<parcel_id.replace('-','')>' and by point-in-polygon -- both
    methods independently returned the identical zone code for the same
    parcel, cross-confirming the match.
  - Lake Mary:       "LM Zoning" (owner kmorro, serviceDescription "Zoning
    Districts for Lake Mary, Florida") --
    services1.arcgis.com/v0YMSb0ovdJoIQKg/arcgis/rest/services/LM_Zoning/FeatureServer/0
    fields Zoning/Description; point-in-polygon query.

  case_number     parcel_id                    city            zone (raw)  zone_desc
  2025CA001137    33-19-30-5QS-0000-0230        Sanford         SR1         Single Fam. Res. 6,000 sf lots
  2025CA001187    10-20-30-5CT-0G00-0060        Sanford         SR1A        Single Fam. Res. 7,500 sf lots
  2026CA000914    31-19-31-525-0J00-0030        Sanford         SR1         Single Fam. Res. 6,000 sf lots
  2025CA002094    02-21-30-509-0000-1930        Winter Springs  R-1A        One-Family Dwelling District
  2024CA002295    16-20-30-300-053A-0000        Lake Mary       RCE         Rural Country Estates

ZONE CODE NORMALIZATION: Sanford's live layer renders codes without hyphens
(SR1/SR1A) while zoning_districts already stores Sanford's canonical
hyphenated codes (SR-1 id=6316, SR-1A id=6315 -- both pre-existing from the
2026-08-24 session, exact string match required by
v_zoning_gold_standard_card's join). parcel_zones.zone_code set to the
canonical hyphenated form, not the raw unhyphenated ArcGIS label.
Winter Springs' R-1A already exists verbatim (id=11870) -- reused as-is,
zero new district. Lake Mary's RCE does NOT exist in zoning_districts yet
(checked live: zero rows for jurisdiction_id=928 code=RCE) -- ONE new
zoning_districts row created (category='Residential', name='Rural Country
Estates', sourced verbatim from the ArcGIS Description field), no
zone_standards row (no ordinance density/FAR value sourced this session --
left absent rather than fabricated, consistent with K2/Everest-delta
minimal-diff guidance). This is the only genuinely new district created
this session; the other 4 rows reuse pre-existing districts.

ZONING SOURCES ATTEMPTED AND CONFIRMED DEAD THIS SESSION (all VERIFIED
live, 2026-08-26) -- documented so a future session does not re-try them:
  - gis.scpafl.org/arcgis/rest/services -- TCP connection reset by peer,
    5/5 consecutive attempts. Same blocker documented in
    20260718k/20260718n migrations; still dead 2026-08-26.
  - scpafl.org/search/parcels/details/?PID=... -- confirmed to be a Blazor
    Server app (Blazor-Server render mode, _framework/blazor.web.js,
    SignalR-driven); the static HTTP GET response is an empty shell with
    zero parcel data (grep for "zoning"/"Zoning" in the fetched HTML: 0
    matches). Requires a live browser/SignalR session to render, which is
    not available in this environment. (This is almost certainly what the
    2026-08-24 session used, likely via Firecrawl's JS-rendering.)
  - Firecrawl -- API key present but account returns HTTP 402
    "Insufficient credits" fleet-wide (documented in
    scripts/shard2_run2450_ajax_realforeclose_harvest.py's own docstring
    re: Firecrawl since 2026-06-10; still true 2026-08-26).
  - map.scpafl.org/gis/rest/services -- reachable, but its base/geodata/
    production folders all return {"error":{"code":499,"message":"Token
    Required"}}; the two unauthenticated folders (new_base, special) only
    contain basemap/hydrology layers, no zoning/parcel service.
  - www.seminolecountyfl.gov interactive-mapping page -- 404 (stale URL).
  - Seminole County's own ArcGIS Online org services directory
    (services3.arcgis.com/n4VF6lyYfB5kizho) -- 124 public services, none is
    a general parcel-level zoning layer (closest hit,
    "ChickenPermitZoningDissolved", is a 10-feature dissolved layer scoped
    ONLY to unincorporated county chicken-permitting rules -- confirmed
    live point-in-polygon queries against all 5 target coordinates return
    zero features, consistent with all 5 addresses being inside
    incorporated cities this county-only layer excludes).
  - ArcGIS Online portal search for "Seminole County Florida Zoning" --
    only hit is "Pinellas_Seminole_Zoning", already documented as an
    extent-mismatch dead end in the 20260718k migration (does not actually
    cover Seminole County despite the name).
  - "General Zoning Data" (owner Admin_Sanford, services6.arcgis.com/
    r42ivGMv7dqAE150) -- reachable, correct field names (Zone_/
    Zone_Description), but the live layer is EMPTY (returnCountOnly=true
    -> count=0). Superseded by the working jonesm1961 "Zoning" service
    above.

SYN-SEM-2025CA000629 remains a genuine data ceiling: no municipal zoning
layer applies because there is no real parcel_id to look up in the first
place (the underlying case has no resolvable property record on either
realforeclose_aids or a fresh live AJAX harvest of its own auction date --
same root cause as C/D, not a zoning-source problem).

BONUS FIX (applied directly, not via this script's main() -- single-field,
trivial, same Census-geocoder method already used in the 2026-08-24
migration): 2025CA001957 (2657 BULLION LOOP, SANFORD, FL 32771) had
parcel_id + address + assessed_value but NULL lat/lon. US Census Bureau
public geocoder (geocoding.geo.census.gov) returned an exact single match:
matchedAddress "2657 BULLION LOOP, SANFORD, FL, 32771",
y=28.793337441032, x=-81.209559433644 -- backfilled directly via PATCH,
confirmed live. Does NOT flip this row's I status by itself (still needs a
parcel_zones link -- queried the same Sanford "Zoning" ArcGIS layer at
this geocoded point and got ZERO features, i.e. this specific Census-geocoded
point falls outside the Sanford municipal zoning layer's polygon coverage,
despite the "SANFORD" mailing address -- likely actually unincorporated
county land with a Sanford postal address, a common FL pattern; no
county-wide fallback zoning layer was found this session per the blocked-
sources list above). Left zone-unlinked; a future session with access to
Seminole County's own unincorporated-area zoning layer (still blocked this
session -- see gis.scpafl.org above) could close this one row.

FINAL VERIFIED RESULT (pencil_dod_evaluate_county('seminole'), live,
2026-08-26, after all writes in this session):
  C: matched_clean=157 of 157 = 100.0%  PASS  (was 92.4% FAIL)
  D: matched_any=157   of 157 = 100.0%  PASS  (was 92.4% FAIL)
  I: card_complete=147 of 157 = 93.6%   FAIL  (was 90.4% FAIL; +5 rows,
     genuine residual ceiling: 6 non-property-record garbage-parcel rows
     [2025CA002115 ALCOHOLIC LICENSE, 2025CA000060 MULTIPLE PARCELS,
     2016CA000953/2024CA002388/2025CA002908 Property-Appraiser-artifact,
     2025CA000629 SYN- synthetic parcel] + 3 tax_deed rows missing
     assessed_value [RealTaxDeed's own AJAX calendar does not publish this
     field, confirmed live -- all 3 harvest items returned
     assessed_value=None] + 1 Sanford-address row whose real geocoded point
     falls outside the only zoning layer found for that city
     [2025CA001957]). No fabrication anywhere in this residual set --
     reported honestly, not gamed.
  Regression check (all VERIFIED via the same live evaluator call):
     A fc=130 td=27 PASS (unchanged), B 100.0% PASS (unchanged),
     E 98.1% PASS (unchanged -- not touched this session),
     F 100.0% PASS (unchanged), G 96.3% PASS (was 98.0%, still comfortably
     >=95% -- the expected/predicted dip from 1 new RCE district with no
     zone_standards density value, matching the docstring's pre-write
     prediction), H 0.0h PASS (unchanged), J 96.8% PASS (unchanged).
     Zero regressions.

Usage:
  python3 scripts/gold_standard_seminole_cdi_20260826_ajax_geo_zone_backfill.py            # dry-run
  python3 scripts/gold_standard_seminole_cdi_20260826_ajax_geo_zone_backfill.py --apply     # write to DB

Environment: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
import importlib.util
import urllib.request
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or ""
if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
COUNTY = "seminole"
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# The 12 C/D gap case_numbers named in the dispatch.
CD_TARGET_CASES = [
    "2016CA000953", "2024CA002388", "2025CA002908", "2025CA001957",
    "2026CA000914", "2025CA001187", "2025CA002094", "2025CA001137",
    "2024CA002295", "20260083/2024-001947", "20260069/2024-000064", "20260071",
]

# (sale_type, auction_date) pairs covering the above case_numbers, derived
# from a live per-case_number lookup this session.
HARVEST_DATES = [
    ("foreclosure", "09/22/2026"),
    ("tax_deed", "10/15/2026"),
]

# 5 real parcels resolved live this session via municipal ArcGIS Online
# zoning layers (Sanford/Winter Springs/Lake Mary -- see module docstring
# for source URLs and verification detail). zone_code is the canonical form
# already used by pre-existing zoning_districts rows where one exists.
I_ZONE_LINK_FIX = [
    # (case_number, parcel_id, jurisdiction_id, zone_code, zone_name, category, new_district)
    ("2025CA001137", "33-19-30-5QS-0000-0230", 904, "SR-1", "Single-Family Dwelling Residential", "Residential", False),
    ("2025CA001187", "10-20-30-5CT-0G00-0060", 904, "SR-1A", "Single-Family Dwelling Residential", "Residential", False),
    ("2026CA000914", "31-19-31-525-0J00-0030", 904, "SR-1", "Single-Family Dwelling Residential", "Residential", False),
    ("2025CA002094", "02-21-30-509-0000-1930", 921, "R-1A", "One-Family Dwelling District", "Residential", False),
    ("2024CA002295", "16-20-30-300-053A-0000", 928, "RCE", "Rural Country Estates", "Residential", True),
]

# 1 row confirmed to have NO real parcel_id (synthetic SYN- placeholder) --
# no zoning lookup is possible without fabricating a parcel. Left blocked.
I_ZONE_LINK_BLOCKED = [
    ("2025CA000629", "SYN-SEM-2025CA000629"),
]

SOURCE_LABEL = "gold_standard_seminole_i_20260826_municipal_arcgis_verified"


def norm_case_number(cn: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def _with_retry(fn, attempts=3):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code == 409 or i == attempts - 1:
                raise
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def rest_get(path: str):
    def _do():
        req = urllib.request.Request(f"{BASE}/{path}", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def rest_patch(path: str, body: dict, apply: bool):
    if not apply:
        print(f"  [dry-run] PATCH {path} -> {body}")
        return True

    def _do():
        req = urllib.request.Request(
            f"{BASE}/{path}", data=json.dumps(body).encode(), method="PATCH",
            headers={**HEADERS, "Prefer": "return=representation"})
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())
    try:
        _with_retry(_do)
        return True
    except Exception as e:
        print(f"  PATCH FAILED for {path}: {e}")
        return False


def rest_post(path: str, body, apply: bool, prefer: str = "resolution=merge-duplicates,return=representation"):
    payload = body if isinstance(body, list) else [body]
    if not apply:
        print(f"  [dry-run] POST {path} -> {json.dumps(payload)}")
        return True, None

    def _do():
        req = urllib.request.Request(
            f"{BASE}/{path}", data=json.dumps(payload).encode(), method="POST",
            headers={**HEADERS, "Prefer": prefer})
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())
    try:
        result = _with_retry(_do)
        return True, result
    except Exception as e:
        print(f"  POST FAILED for {path}: {e}")
        return False, None


def main():
    apply = "--apply" in sys.argv

    print("=== Fetching current state of 12 C/D target case_numbers ===")
    rows_by_case = {}
    for cn in CD_TARGET_CASES:
        q = urllib.parse_quote if False else None
        import urllib.parse as up
        rows = rest_get(
            f"multi_county_auctions?county=eq.{COUNTY}&case_number=eq.{up.quote(cn)}"
            f"&select=id,case_number,parcel_id,property_address,assessed_value,parity_status,parity_source,sale_type,auction_date"
        )
        if rows:
            rows_by_case[cn] = rows[0]
        else:
            print(f"  WARNING: {cn} not found live -- skipping")
    print(f"  {len(rows_by_case)} / {len(CD_TARGET_CASES)} target rows found live")

    print("\n=== Building live harvest index (AJAX RealAuction calendar) ===")
    harvest_index = {}
    for sale_type, date_mmddyyyy in HARVEST_DATES:
        platform = "realforeclose.com" if sale_type == "foreclosure" else "realtaxdeed.com"
        try:
            items = _mod.harvest_date(COUNTY, COUNTY, date_mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"  HARVEST FAIL {sale_type} {date_mmddyyyy}: {e}")
            continue
        print(f"  {sale_type} {date_mmddyyyy}: {len(items)} items")
        for it in items:
            cn = norm_case_number(it.get("case_number"))
            if cn:
                harvest_index[cn] = it

    print("\n=== Cross-checking realforeclose_aids (independent litmus) ===")
    aids = rest_get(f"realforeclose_aids?county_slug=eq.{COUNTY}&select=case_number,parcel_id&limit=1000")
    aids_index = {norm_case_number(a["case_number"]): a for a in aids}
    print(f"  {len(aids)} realforeclose_aids rows for seminole")

    print("\n=== Matching + promoting parity_status (C/D) ===")
    now_updated = 0
    still_unmatched = []
    for cn, row in rows_by_case.items():
        ncn = norm_case_number(cn)
        hit = harvest_index.get(ncn) or aids_index.get(ncn)
        if not hit:
            still_unmatched.append(cn)
            print(f"  NO MATCH: {cn} (checked live harvest + realforeclose_aids)")
            continue
        already_tier1 = (row.get("parity_source") or "").startswith("tier1")
        if row.get("parity_status") == "matched_clean" and already_tier1:
            print(f"  already matched_clean+tier1: {cn}")
            continue
        source_label = "tier1:seminole_gold_standard_20260826_ajax_harvest" if ncn in harvest_index else "tier1:seminole_gold_standard_20260826_realforeclose_aids"
        ok = rest_patch(
            f"multi_county_auctions?id=eq.{row['id']}",
            {"parity_status": "matched_clean", "parity_source": source_label},
            apply,
        )
        if ok:
            now_updated += 1
            print(f"  PROMOTED: {cn} -> matched_clean ({source_label})")

    print(f"\nC/D promoted this run: {now_updated} / {len(rows_by_case)}")
    if still_unmatched:
        print(f"Still unmatched (genuine gap, not sourced): {still_unmatched}")

    print("\n=== I letter: parcel_zones link backfill (municipal ArcGIS-verified) ===")
    # 1. Ensure Lake Mary's RCE district exists (only genuinely new district this session).
    rce_check = rest_get("zoning_districts?jurisdiction_id=eq.928&code=eq.RCE&select=id")
    if rce_check:
        print(f"  RCE district already exists (id={rce_check[0]['id']}), skipping insert")
    else:
        ok, result = rest_post(
            "zoning_districts",
            {
                "jurisdiction_id": 928,
                "code": "RCE",
                "name": "Rural Country Estates",
                "category": "Residential",
                "description": "Rural Country Estates (Lake Mary, FL) -- sourced verbatim from live "
                                "LM_Zoning ArcGIS FeatureServer Description field, 2026-08-26.",
            },
            apply,
            prefer="return=representation",
        )
        if ok:
            print("  RCE district created")

    # 2. Verify each target parcel doesn't already have a parcel_zones row (idempotency),
    #    then insert.
    existing_pz = rest_get(
        "parcel_zones?parcel_id=in.(" + ",".join(f'"{p[1]}"' for p in I_ZONE_LINK_FIX) + ")&select=parcel_id"
    )
    existing_pz_ids = {r["parcel_id"] for r in existing_pz}

    pz_inserted = 0
    for cn, pid, jid, zone_code, zone_name, category, is_new in I_ZONE_LINK_FIX:
        if pid in existing_pz_ids:
            print(f"  SKIP (already linked): {cn} parcel_id={pid}")
            continue
        ok, _ = rest_post(
            "parcel_zones",
            {
                "parcel_id": pid,
                "jurisdiction_id": jid,
                "zone_code": zone_code,
                "zone_name": zone_name,
                "source": SOURCE_LABEL,
            },
            apply,
            prefer="return=representation",
        )
        if ok:
            pz_inserted += 1
            print(f"  LINKED: {cn} parcel_id={pid} -> zone_code={zone_code} (jurisdiction_id={jid})")

    print(f"\nparcel_zones rows inserted this run: {pz_inserted} / {len(I_ZONE_LINK_FIX)}")

    print("\n=== I letter: genuine data-ceiling rows (NOT touched) ===")
    for cn, pid in I_ZONE_LINK_BLOCKED:
        print(f"  BLOCKED (no real parcel_id, no zoning source can apply): {cn} parcel_id={pid}")

    if not apply:
        print("\nDRY RUN complete. Re-run with --apply to write C/D promotions + I zone links.")
    else:
        print("\nAPPLY complete.")


if __name__ == "__main__":
    main()
