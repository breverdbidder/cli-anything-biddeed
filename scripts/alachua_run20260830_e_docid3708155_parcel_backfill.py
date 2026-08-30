#!/usr/bin/env python3
"""Alachua letter E (parcel_linked) fix -- 2026-08-30 session.

CONTEXT: pencil_dod_evaluate_county('alachua') E = FAIL, 82/91 = 90.1%
(need ~87/91 = 95.6% to pass). 9 rows have parcel_id IS NULL within the
canonical filter (data_source<>'propertyonion' OR tier1_authoritative=true).

This is the Nth session to work these exact 9 rows -- see
scripts/shard10_run3645_alachua_e_parcel_backfill.py,
scripts/shard14_run121fa7c3_alachua_e_i_diagnosis.py, scripts/alachua-E_fix.py,
and scripts/alachua_run20260830_cd_0924_sweep.py for prior exhaustive attempts.
8 of the 9 rows were re-confirmed genuine dead ends this session (re-harvested
live via scripts/shard10_run_alachua_docid_harvest.py):
  - 01 2025 CA 003287: docid 3683369 -> Clerk record confirms Document Type
    ORDER, Legal Description SUBDIVISION "MOSES E LEVY GRANT" Lot From "1 2 8"
    (three lots) -- genuinely multi-parcel, cannot assign one parcel_id.
  - 01 2025 CA 001928, 002643, 003919, 002760, 003080, 000658, 001045: all
    carry an EMPTY docid (docid=&ms=0) in the RealForeclose AJAX Case# anchor
    -- the Clerk has not cross-referenced any recorded document to these
    cases yet. RealForeclose's own "Parcel ID" field is the literal
    placeholder "Property Appraiser" for all of these. No owner name or
    address exists anywhere in our DB or on the public calendar to
    cross-reference against the Alachua ArcGIS PublicParcel layer.

NEW LEAD FOUND THIS SESSION: 01 2026 CA 000169 (docid 3708155) -- this case
did NOT have a docid in the prior (2026-08-02 era) diagnosis session; the
Clerk has since cross-referenced a JUDGMENT (filed 08/18/2026, Book 5287
Page 1360) to this case. Unlike the prior E fixes (which needed an
ArcGIS owner-name lookup with lot-suffix disambiguation), this record's own
"Legal Description" tab carries a PARCEL-type entry with an explicit,
unambiguous Parcel Id field:

    isol.alachuaclerk.org/RealEstate/SearchDetail.aspx?docid=3708155
    -> Document Type: JUDGMENT
    -> Grantor: GROOMS GEOFFREY PIERCE / GROOMS SUSAN HARDEE
    -> Grantee (#1 of 5): OUTLAW ASHLEY
    -> Legal Description tab, "PARCEL" block -> Parcel Id: 06178-005-000

Cross-referenced against Alachua County Property Appraiser's public ArcGIS
FeatureServer (PublicParcel/FeatureServer/0):
    query Name='06178-005-000' -> Owner_Mail_Name="OUTLAW ASHLEY",
    FULLADDR="2305 NW 46TH TER", StatedArea=0.3229 acres.
Owner_Mail_Name on the parcel record exactly matches Grantee #1 on the
JUDGMENT (the party record shows a subsequent owner chain consistent with
a mortgage foreclosure judgment against the property's then-current owner).
No other alachua row already carries parcel_id=06178-005-000 (checked live,
zero collisions).

Access notes for future sessions: isol.alachuaclerk.org's SearchDetail.aspx
appears to intermittently serve real (non-JS-gated) HTML to a plain
curl/urllib client with a browser UA + persistent cookie jar + `curl -L`
redirect-following (case-insensitive docid/docId param, 301 -> 302 -> 200
redirect chain) -- this contradicts several PRIOR sessions' finding that the
page is unconditionally JS-required/redirect-looping. It is unclear whether
this is a site-side change or intermittent behavior; do not assume it will
work on every docid without re-verifying live.

Idempotent: only patches the row if parcel_id IS NULL (re-run is a no-op).
"""
import json
import os
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

FIX = {
    "case_number": "01 2026 CA 000169",
    "parcel_id": "06178-005-000",
    "property_address": "2305 NW 46TH TER, GAINESVILLE, FL",
    "evidence": (
        "isol.alachuaclerk.org docid=3708155 (JUDGMENT, Book 5287 Page 1360, "
        "filed 08/18/2026) Legal Description tab PARCEL block -> "
        "Parcel Id 06178-005-000 (explicit, no disambiguation needed) -> "
        "ArcGIS PublicParcel FeatureServer Owner_Mail_Name='OUTLAW ASHLEY' "
        "matches Grantee #1 on the judgment"
    ),
}

# The 8 rows re-confirmed as genuine dead ends this session (no write).
RESIDUAL_UNRESOLVED = {
    "01 2025 CA 003287": "docid 3683369 resolves to a 3-lot SUBDIVISION legal "
        "description (MOSES E LEVY GRANT, Lot From '1 2 8') -- genuinely "
        "multi-parcel, cannot assign single parcel_id without fabrication.",
    "01 2025 CA 001928": "empty docid (docid=&ms=0) in live RealForeclose AJAX -- "
        "Clerk has not cross-referenced a recorded document to this case.",
    "01 2025 CA 002643": "empty docid, same as above.",
    "01 2025 CA 003919": "empty docid, same as above.",
    "01 2025 CA 002760": "empty docid, same as above.",
    "01 2025 CA 003080": "empty docid, same as above.",
    "01 2026 CA 000658": "empty docid, same as above.",
    "01 2026 CA 001045": "empty docid, same as above.",
}


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
    cn = FIX["case_number"]
    cn_q = urllib.parse.quote(cn)
    rows = rest_get(
        f"multi_county_auctions?county=eq.alachua&case_number=eq.{cn_q}"
        f"&select=id,case_number,parcel_id,property_address")
    if not rows:
        print(f"NOT FOUND in DB: {cn}")
        return
    row = rows[0]
    if row.get("parcel_id"):
        print(f"SKIP (already has parcel_id={row['parcel_id']}): {cn}")
    else:
        patch_body = {"parcel_id": FIX["parcel_id"], "property_address": FIX["property_address"]}
        result = rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
        if not result:
            print(f"FAIL-LOUD: PATCH for {cn} (id={row['id']}) returned 0 rows updated!")
            raise SystemExit(1)
        print(f"WROTE {cn} (id={row['id']}): parcel_id={FIX['parcel_id']} "
              f"property_address={patch_body['property_address']}")
        print(f"    evidence: {FIX['evidence']}")

    print(f"\nRESIDUAL UNRESOLVED (no write, genuine dead end, re-verified live this session): "
          f"{len(RESIDUAL_UNRESOLVED)}")
    for k, v in RESIDUAL_UNRESOLVED.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
