#!/usr/bin/env python3
"""SHARD-10, run3645, county=alachua, letter E (parcel linkage).

Backfills parcel_id for 2 of the 7 alachua rows in multi_county_auctions that
were missing it (40/47=85.1%, need >=45/47=95%).

BACKGROUND: a prior diagnosis (scripts/shard14_run121fa7c3_alachua_e_i_diagnosis.py)
found RealForeclose's own "Parcel ID" field for all 7 cases decodes to the
placeholder "Property Appraiser" (or "MULTIPLE PARCEL"), and that qpublic.
schneidercorp.com (Alachua Property Appraiser search) returns HTTP 403 from
Cloudflare on every request, and isol.alachuaclerk.org's docid links appeared
JS-gated -- concluding no further progress was possible without fabrication.

THIS SESSION found a working path that diagnosis missed: Playwright (a JS-capable
headless browser, unavailable/untried in that prior session) against
isol.alachuaclerk.org's *Official Records* detail pages (not the JS-gated Court
Records case-docket portal, which remains genuinely captcha-blocked). The AITEM
HTML block emitted by the RealForeclose AJAX calendar (same harvester as
scripts/shard2_run2450_ajax_realforeclose_harvest.py) embeds, in the "Case #"
column, a link of the form:
    isol.alachuaclerk.org/RealEstate/SearchDetail.aspx?docid=<instrument_number>
for cases where the Clerk's office cross-referenced a recorded document
(JUDGMENT/ORDER) to the case at harvest time. This docid is NOT parsed by any
existing script (parse_aitem_blocks only extracts the case_number anchor TEXT,
discarding the href). Following that link with a JS-rendering browser (plain
urllib/curl was NOT sufficient -- SearchDetail.aspx redirects and lazy-loads its
tab content via client-side JS, confirmed live this session) surfaces:
  - Grantor/Grantee party names (real, recorded)
  - A "Legal Description" tab: subdivision plat name + lot number, or
    section/township/range

Of the 7 target cases, only 3 carried a non-empty docid in the RealForeclose
AJAX payload (verified live 2026-07-10): 003287 (docid 3683369, "MULTIPLE
PARCEL" per its own legal description spanning 3 lots -- SKIPPED, no single
parcel_id can be assigned without fabricating which of the multiple lots is
"the" parcel), 001356 (docid 3693575), and 001683 (docid 3696062). The other 4
(001928, 000399, 003110, 003156) have NO docid in the AJAX payload at all --
confirmed by inspecting the raw decoded AITEM HTML directly (href=
"...docid=&ms=0", empty) -- meaning the Clerk's system has not cross-referenced
any recorded document to those cases yet. No further real lead exists for those
4 this session (see BLOCKERS in the final report).

For the 2 resolvable cases, this script cross-references the real grantor/
grantee party names + legal description (extracted by hand this session via
Playwright against isol.alachuaclerk.org, reproduced below as literal fetched
values, NOT re-scraped live by this script to avoid re-driving Playwright/
captcha risk on every run -- the docid->attributes mapping is deterministic and
was verified moments before this script was written) against the Alachua County
Property Appraiser's public ArcGIS FeatureServer (PublicParcel/FeatureServer/0,
discovered by the prior diagnosis session) to resolve exactly one parcel_id per
case:

1. case 01 2024 CA 001683 (docid 3696062, JUDGMENT, grantee "PAUL JEREMY" /
   "PAUL VIRGINIA"): FeatureServer query
   `Owner_Mail_Name LIKE '%PAUL%JEREMY%'` returns exactly 2 rows; only one,
   parcel 02975-002-000 ("PAUL JEREMY & VIRGINIA", 10815 NW 199TH AVE, Alachua
   FL 32615-3902), matches BOTH first names on the judgment -- confirmed unique,
   no ambiguity.

2. case 01 2025 CA 001356 (docid 3693575, JUDGMENT, grantor "MAINSTREET
   COMMUNITY BANK OF FLORIDA", grantee "THE VUE AT CELEBRATION POINTE LLC",
   Legal Description: subdivision "THE VUE AT CELEBRATION POINTE REPLAT",
   Lot 91): the LLC itself owns 66 parcels in that plat (a bulk
   developer/inventory holder), so owner-name alone is ambiguous -- but this
   plat's parcel IDs encode the lot number as the numeric suffix
   (06820-010-090=lot90, -092=lot92, -093=lot93, ... confirmed by cross-checking
   10 known lot/parcel pairs), so lot 91 -> parcel 06820-010-091. That parcel is
   NOT in the LLC's current 66-row holding list (confirmed live query) --
   consistent with the LLC having already sold lot 91 to an individual owner,
   which is exactly the fact pattern of a mortgage/judgment foreclosure case
   (bank vs. the individual buyer, not the developer). FeatureServer confirms
   parcel 06820-010-091 = "BUSTAMANTE VICTOR & ISABEL", 3366 SW 50TH DR,
   Gainesville FL 32608.

Both parcel_ids verified absent from any other alachua row before writing
(no collision). Only property_address is also backfilled (from FULLADDR),
since that field was independently confirmed as a real site address on the
same ArcGIS record as the parcel_id (not fabricated/guessed).

Direct DB (psycopg2/pooler) NOT used -- confirmed dead this session. All writes
go through PostgREST.

Idempotent: only patches rows where parcel_id IS NULL (re-running after a
successful patch is a no-op, matched by empty result set).
"""
import json
import os
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# Verified live 2026-07-10 (see docstring for full provenance/evidence chain).
FIXES = [
    {
        "case_number": "01 2024 CA 001683",
        "parcel_id": "02975-002-000",
        "property_address": "10815 NW 199TH AVE, ALACHUA, FL 32615",
        "evidence": (
            "isol.alachuaclerk.org docid=3696062 (JUDGMENT, grantee PAUL JEREMY / "
            "PAUL VIRGINIA) -> ArcGIS PublicParcel FeatureServer unique match "
            "Owner_Mail_Name='PAUL JEREMY & VIRGINIA'"
        ),
    },
    {
        "case_number": "01 2025 CA 001356",
        "parcel_id": "06820-010-091",
        "property_address": "3366 SW 50TH DR, GAINESVILLE, FL 32608",
        "evidence": (
            "isol.alachuaclerk.org docid=3693575 (JUDGMENT, grantee THE VUE AT "
            "CELEBRATION POINTE LLC, Legal Description: THE VUE AT CELEBRATION "
            "POINTE REPLAT Lot 91) -> lot-number-encoded parcel suffix pattern "
            "(confirmed across 10 known lot/parcel pairs in the same plat) -> "
            "ArcGIS PublicParcel FeatureServer parcel 06820-010-091 = "
            "BUSTAMANTE VICTOR & ISABEL, 3366 SW 50TH DR"
        ),
    },
]


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def main():
    written = []
    for fix in FIXES:
        cn = fix["case_number"]
        cn_q = urllib.parse.quote(cn)
        rows = rest_get(
            f"multi_county_auctions?county=eq.alachua&case_number=eq.{cn_q}"
            f"&select=id,case_number,parcel_id,property_address")
        if not rows:
            print(f"NOT FOUND in DB: {cn}")
            continue
        row = rows[0]
        if row.get("parcel_id"):
            print(f"SKIP (already has parcel_id={row['parcel_id']}): {cn}")
            continue
        patch_body = {"parcel_id": fix["parcel_id"]}
        if not row.get("property_address") or row.get("property_address") == "ALACHUA COUNTY FL":
            patch_body["property_address"] = fix["property_address"]
        try:
            result = rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
        except Exception as e:
            print(f"PATCH FAILED for {cn} (id={row['id']}): {e}")
            raise
        if not result:
            print(f"FAIL-LOUD: PATCH for {cn} (id={row['id']}) returned 0 rows updated!")
            raise SystemExit(1)
        print(f"WROTE {cn} (id={row['id']}): parcel_id={fix['parcel_id']} "
              f"property_address={patch_body.get('property_address', '(unchanged)')}")
        print(f"    evidence: {fix['evidence']}")
        written.append((cn, fix["parcel_id"]))

    print(f"\nTOTAL WRITTEN: {len(written)} of {len(FIXES)} attempted")
    for cn, pid in written:
        print(f"  {cn} -> {pid}")


if __name__ == "__main__":
    main()
