#!/usr/bin/env python3
"""SHARD-7 continuation (dispatch 9fe2973e-44ea-441c-9770-92ff736483dd), lake G fix.

CONTEXT: prior session (run3679, see SHARD7_RUN3679_VOLUSIA_GADSDEN_SANTA_ROSA_LAKE_
SESSION_REPORT.md) replaced a FABRICATED zoning substrate for lake -- zoning_districts
id=10716 "Single Family Residential (Shard7 Synthetic)" backed by zone_standards id=3401
with hardcoded max_far=0.35/max_density_du_acre=4.0/parking_per_1000sf=2.0, all NULL
source_url/ordinance_section/confidence_score -- with 33 REAL parcel_zones rows sourced
from Lake County's live zoning GIS layer (gis.lakecountyfl.gov/InteractiveMap/MapServer/50),
carrying real diverse zone codes: A, CFD, PUD, R-3, R-6, R-7, RM. That correctly caused
Letter G to regress from a fabricated 100% to an honest 0% (density=23.3 far=0.0 pk1000=0.0),
because none of these 7 real zone codes had ANY zoning_districts/zone_standards rows.

ROOT CAUSE (confirmed live via v_zoning_gold_standard_kpi_v3 / v_zoning_district_
applicability / pencil_dod_evaluate_county source):
  - v_zoning_district_applicability defaults far_applicable=true / density_applicable=true
    / pk1000_applicable=true for ANY parcel_zones.zone_code with NO matching zoning_districts
    row at all (COALESCE(a.*_applicable, true) in the pj CTE inside pencil_dod_evaluate_
    county). That's why all 43 lake parcels currently score density/far/pk1000 as
    "applicable but missing" -- not because standards don't exist, but because no
    zoning_districts row exists yet for A/CFD/PUD/R-3/R-6/R-7/RM under jurisdiction 835.
  - Once a zoning_districts row exists, v_zoning_district_applicability's BASE view sets
    pk1000_applicable=false UNCONDITIONALLY (hardcoded) -- pk1000 falls out of scope
    entirely for every code the moment a district row exists, matching the pre-existing
    R-1/jurisdiction-828/838 precedent (confirmed live for jurisdiction 835's old R-1 row
    and jurisdiction 828's real santa_rosa rows from the prior session).
  - far_applicable defaults true ONLY for category in (commercial,industrial,mixed-use) AND
    name not containing 'pud'; for our 7 codes (agricultural/residential/special) it
    defaults FALSE unless zoning_districts.far_regulated is explicitly set true -- so we
    leave far_regulated NULL (mirrors the santa_rosa PUD precedent) EXCEPT for CFD, which
    Lake County's own Table 3.02.06 treats as a non-residential/FAR-only district (grouped
    with C1/C2/C3/CP/LM/HM/MP, density='-'). CFD needs BOTH far_regulated=true (it IS FAR-
    governed per the real table) AND density_regulated=false (it has NO residential density
    -- the '-' in the table is a structural N/A, not a data gap) so it doesn't get
    mis-counted as "density-applicable but incomplete".
  - density_applicable defaults true unless category in (commercial,industrial) OR
    density_regulated is explicitly false -- true by default for our 6 residential/
    agricultural codes, which is what we want (they ARE density-regulated, we just need
    the max_density_du_acre value itself).

REAL SOURCE: Lake County's own live Code of Ordinances, Appendix E Land Development
Regulations, Chapter III Zoning District Regulations, Section 3.02.06 "Density, Impervious
Surface, Floor Area, and Height Requirements" -- Table 3.02.06. Fetched live via Municode's
underlying content API (api.municode.com/CodesContent, jobId=487541 = "Supplement 150",
codified through Ordinance No. 2026-3, enacted January 20, 2026 -- confirmed via
api.municode.com/Jobs/latest/11115, productId=11115 "Code of Ordinances", clientId=11506
"Lake County" confirmed via api.municode.com/Clients/name). This is the exact live,
current, official table -- not a guess, not an LLM extraction from a PDF excerpt (the only
PDF excerpts findable via web search, e.g. tranzon.com's zoning summary, are OLDER
supplements that don't even include this section; verified live via the municode API
against the CURRENT jobId).

VALUES WRITTEN (verbatim from Table 3.02.06, current live supplement):
  A   (Agriculture):                    1 DU/5 AC = 0.2 du/acre,  FAR .10
  R-3 (Medium Residential District):    3 DU/AC,                  FAR .30
  R-6 (Urban Residential District):     6 DU/AC,                  FAR .40
  R-7 (Mixed Residential District):     8 DU/AC,                  FAR .40
  RM  (Mixed Home Residential):         8 DU/AC,                  FAR .50
  CFD (Community Facility District):    density '-' (N/A, non-residential), FAR 1.0

PUD DELIBERATELY SKIPPED (NOT fabricated): Table 3.02.06 has NO row for PUD at all --
confirmed live by fetching Chapter IV Special Districts, Section 4.03.00 "PUD Planned Unit
Development District", Subsection 4.03.04.A "Density": "The criteria for establishing the
residential Gross Density Shall: [be based on natural features, public facility adequacy,
Wekiva point system where applicable, up to 5.5 du/net acre special cases, etc.]" -- i.e.
Lake County's OWN ordinance text explicitly makes PUD density a per-development-agreement
determination, not a single county-wide number. Writing a single max_density_du_acre for
PUD here would be exactly the fabrication pattern this session was tasked to clean up.
A zoning_districts row IS created for PUD (category='Planned Development', far_regulated/
density_regulated left NULL) so the 9 PUD-zoned parcels get pulled OUT of "applicable but
missing" the same way R-1/AG-RR/PUD did for santa_rosa (their FAR/pk1000 stop being
falsely counted against the applicable set) -- but zone_standards.max_density_du_acre is
left genuinely absent, so PUD parcels correctly remain incomplete on the density metric.
This is an honest partial fix, not a full PASS engineered by omission.

Usage:
  python3 scripts/shard7c_lake_g_zoning_standards_fix.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COUNTY = "lake"
JURISDICTION_ID = 835  # Lake County -- matches the prior session's real GIS zoning fix
SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

DRY_RUN = "--dry-run" in sys.argv

SOURCE_URL = ("https://api.municode.com/CodesContent?jobId=487541&"
              "nodeId=APXELADERE_CHIIZODIRE_3.02.00BURE&productId=11115"
              " (Lake County Code of Ordinances, Appendix E LDR, Chapter III Zoning "
              "District Regulations, Table 3.02.06 -- codified through Ord. No. 2026-3, "
              "enacted 1-20-2026, live Supplement 150; human-readable viewer: "
              "https://library.municode.com/fl/lake_county/codes/code_of_ordinances"
              "?nodeId=APXELADERE_CHIIZODIRE_3.02.00BURE)")
ORDINANCE_SECTION = "Table 3.02.06 (Density, Impervious Surface, Floor Area, and Height Requirements)"

# code -> (name, category, max_density_du_acre or None, max_far or None,
#          far_regulated override or None, density_regulated override or None)
ZONE_SPECS = {
    "A":   ("Agriculture District",            "Agricultural", 0.2, 0.10, None, None),
    "R-3": ("Medium Residential District",      "Residential",  3.0, 0.30, None, None),
    "R-6": ("Urban Residential District",       "Residential",  6.0, 0.40, None, None),
    "R-7": ("Mixed Residential District",       "Residential",  8.0, 0.40, None, None),
    "RM":  ("Mixed Home Residential",           "Residential",  8.0, 0.50, None, None),
    # CFD: Table 3.02.06 lists density as "-" (structural N/A, non-residential) and
    # FAR=1.0 -- explicit far_regulated=True / density_regulated=False so the applicability
    # view treats it correctly (FAR-governed, NOT density-governed) rather than defaulting
    # density_applicable=true and counting it as an incomplete residential parcel.
    "CFD": ("Community Facility District",      "Special",      None, 1.0, True, False),
    # PUD: deliberately NO max_density_du_acre / max_far -- see module docstring. Still
    # gets a zoning_districts row (far_regulated/density_regulated left NULL, mirroring
    # the pre-existing santa_rosa PUD precedent) so it's correctly excluded from the
    # "no district row at all -> applicable-by-default" trap, without fabricating a number
    # the county's own ordinance says is determined per-development.
    "PUD": ("Planned Unit Development District", "Planned Development", None, None, None, None),
}


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


def rest_post(path, body, prefer="return=representation"):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json", "Prefer": prefer})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()) if prefer.startswith("return=representation") else None
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        log(f"POST {path} FAILED: {e.code} {body_err}", "VERIFIED")
        raise


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def ensure_zoning_district(code, name, category, far_regulated, density_regulated):
    existing = rest_get(
        f"zoning_districts?jurisdiction_id=eq.{JURISDICTION_ID}"
        f"&code=eq.{urllib.parse.quote(code)}")
    if existing:
        log(f"zoning_districts row already exists for {code} (id={existing[0]['id']})",
            "VERIFIED")
        return existing[0]["id"], False
    payload = {
        "jurisdiction_id": JURISDICTION_ID,
        "code": code,
        "name": name,
        "category": category,
    }
    if far_regulated is not None:
        payload["far_regulated"] = far_regulated
    if density_regulated is not None:
        payload["density_regulated"] = density_regulated
    if DRY_RUN:
        log(f"DRY-RUN would INSERT zoning_districts {payload}", "UNTESTED")
        return -1, True
    created = rest_post("zoning_districts", payload)
    did = created[0]["id"]
    log(f"Created zoning_districts id={did} code={code} category={category} "
        f"far_regulated={far_regulated} density_regulated={density_regulated}", "VERIFIED")
    return did, True


def ensure_zone_standards(zoning_district_id, code, max_density, max_far):
    if zoning_district_id == -1:
        return False
    existing = rest_get(f"zone_standards?zoning_district_id=eq.{zoning_district_id}")
    if existing:
        log(f"zone_standards row already exists for district id={zoning_district_id}",
            "VERIFIED")
        return False
    if max_density is None and max_far is None:
        log(f"  {code}: no county-wide dimensional number to write (see docstring) -- "
            f"zoning_districts row created, zone_standards intentionally left absent",
            "VERIFIED")
        return False
    payload = {
        "zoning_district_id": zoning_district_id,
        "source_url": SOURCE_URL,
        "ordinance_section": ORDINANCE_SECTION,
        "confidence_score": 1.0,
    }
    if max_density is not None:
        payload["max_density_du_acre"] = max_density
    if max_far is not None:
        payload["max_far"] = max_far
    if DRY_RUN:
        log(f"DRY-RUN would INSERT zone_standards {payload}", "UNTESTED")
        return True
    rest_post("zone_standards", payload, prefer="return=minimal")
    log(f"Created zone_standards for {code}: max_density_du_acre={max_density} "
        f"max_far={max_far} source=Table 3.02.06 (live municode API)", "VERIFIED")
    return True


def main():
    log("=== SHARD-7c LAKE G FIX: real Lake County LDR Table 3.02.06 zoning standards ===")

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE G: {baseline['G']}", "VERIFIED")
    log(f"BASELINE I: {baseline['I']}", "VERIFIED")

    districts_created = 0
    standards_created = 0

    for code, (name, category, max_density, max_far, far_reg, density_reg) in ZONE_SPECS.items():
        did, was_created = ensure_zoning_district(code, name, category, far_reg, density_reg)
        if was_created:
            districts_created += 1
        if ensure_zone_standards(did, code, max_density, max_far):
            standards_created += 1

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE -- no writes performed")
        print(f"Would create up to {len(ZONE_SPECS)} zoning_districts rows, "
              f"up to {sum(1 for v in ZONE_SPECS.values() if v[2] is not None or v[3] is not None)} "
              f"zone_standards rows")
        return

    after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER G: {after['G']}", "VERIFIED")
    log(f"AFTER I: {after['I']}", "VERIFIED")

    if baseline["I"]["pass"] != after["I"]["pass"] or baseline["I"]["metric"] != after["I"]["metric"]:
        log("NOTE: Letter I metric changed as a side effect (should be zero/near-zero -- "
            "this script only touches zoning_districts/zone_standards, not parcel_zones "
            "or multi_county_auctions).", "VERIFIED")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print("SELECT code, category, far_regulated, density_regulated FROM zoning_districts "
          "WHERE jurisdiction_id=835 AND code IN ('A','CFD','PUD','R-3','R-6','R-7','RM');")
    print("SELECT zd.code, s.max_density_du_acre, s.max_far, s.source_url FROM zone_standards s "
          "JOIN zoning_districts zd ON zd.id=s.zoning_district_id WHERE zd.jurisdiction_id=835 "
          "AND zd.code IN ('A','CFD','PUD','R-3','R-6','R-7','RM');")
    print(f"zoning_districts_created={districts_created} zone_standards_created={standards_created}")
    print(f"BEFORE G: {baseline['G']}")
    print(f"AFTER  G: {after['G']}")
    print(f"BEFORE I: {baseline['I']}")
    print(f"AFTER  I: {after['I']}")


if __name__ == "__main__":
    main()
