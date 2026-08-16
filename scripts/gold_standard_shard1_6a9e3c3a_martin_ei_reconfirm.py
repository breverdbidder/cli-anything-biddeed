#!/usr/bin/env python3
"""Gold Standard shard-1, dispatch 6a9e3c3a, martin county E/I reconfirmation session.

GOAL (as given): county=martin, letters E (parcel linkage >=95%) and I (card
complete >=95%). Currently both at 93.0% (40/43).

FINDING: STRUCTURALLY BLOCKED. Zero writes.

STEP 1 — Live DB query (PostgREST) confirmed the current 3 failing E/I rows
are EXACTLY the 3 previously-identified structural blockers. auctions_total
grew from 41 (prior session, dispatch 32ef2b2a) to 43 (this session) — 2 new
auctions ingested — but neither of the 2 new rows failed E/I; all NULL fields
land on the same 3 case_numbers as before:

  23001555CCAXMX  — personal-property lien (Tropical Acres HOA)
  25001634CCAXMX  — timeshare lien (Plantation Beach Club Condo Assoc)
  25001632CCAXMX  — timeshare lien (Plantation Beach Club Condo Assoc)

STEP 2 — External re-verification (this session, 2026-08-16):
  a) martin.realforeclose.com auction detail pages (AID=1490119, 1491114,
     1494243 from stored source_url) require an authenticated Realauction
     login to view case-level parcel/legal-description detail — the public
     page is a login splash screen only, no PCN exposed. Confirmed via raw
     curl (HTTP 200, but body = login/splash page, no case content).
  b) Martin County Clerk case-number search (court.martinclerk.com) requires
     interactive CAPTCHA verification — not programmatically queryable.
  c) Martin County Clerk Official Records search (or.martinclerk.com/
     LandmarkWeb) is a JS SPA requiring interactive party/document-type
     search — no direct case-number URL endpoint found.
  d) Martin County Property Appraiser (pamartinfl.gov, formerly pa.martin.
     fl.us) real-property search requires interactive owner/PCN/address
     query against an app endpoint — plaintiff names here (HOA names) are
     not property owners, so a direct PCN lookup by plaintiff isn't
     meaningful.
  e) Open web search corroborates the DB's existing case_classification
     labels with independent evidence:
       - "Plantation Beach Club" (cases 25001634CCAXMX, 25001632CCAXMX) is
         a 30-unit Hilton Grand Vacations TIMESHARE resort on Hutchinson
         Island, Martin County — confirms case_classification_label=
         'timeshare' in the DB. Timeshare owners hold a fractional-interest
         estate, not a fee-simple parcel with a normal county PCN.
       - "Tropical Acres" (case 23001555CCAXMX) matches "Tropical Acres
         Mobile Home Pk," Jensen Beach, FL (Martin County) — a mobile home
         park. Under FL law, a mobile home on such a park is commonly
         titled as PERSONAL PROPERTY (HSMV title), not real property —
         confirms case_classification_label='personal_property' in the DB.

CONCLUSION: No new/real parcel_id, address, geo, or assessed_value exists
for any of these 3 liens. They are liens against non-real-property
(mobile-home-as-chattel) or fractional timeshare interests, which
structurally do not have a fee-simple PCN/address/geo the way a normal
foreclosure parcel does. 93.0% (40/43) is the honest ceiling for martin
E and I. No writes performed — inventing parcel/address/geo data for these
3 rows would violate NEVER-LIE / HONESTY PROTOCOL.

Uses PostgREST (not psycopg2) — consistent with all prior martin sessions.
"""
import json
import os
import sys
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

DISPATCH_ID = "6a9e3c3a"

STRUCTURAL_BLOCKERS = {
    "23001555CCAXMX": "personal-property lien (Tropical Acres HOA — mobile home titled as chattel, Jensen Beach FL)",
    "25001634CCAXMX": "timeshare lien (Plantation Beach Club Condo Assoc — Hilton Grand Vacations timeshare, Hutchinson Island)",
    "25001632CCAXMX": "timeshare lien (Plantation Beach Club Condo Assoc — Hilton Grand Vacations timeshare, Hutchinson Island)",
}


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rpc_call(fn_name, params=None, timeout=120):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}",
        data=json.dumps(params or {}).encode(),
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def diagnose():
    print("=== STEP 1: Live query — martin rows failing E/I criteria ===")
    rows = rest_get(
        "multi_county_auctions?county=eq.martin"
        "&or=(property_address.is.null,parcel_id.is.null,latitude.is.null,assessed_value.is.null)"
        "&select=id,case_number,auction_date,sale_type,property_address,parcel_id,"
        "assessed_value,latitude,longitude,case_classification_code,"
        "case_classification_label,plaintiff,updated_at"
        "&order=auction_date.asc"
    )
    total = rest_get("multi_county_auctions?county=eq.martin&select=id")
    print(f"  auctions_total (live): {len(total)}")
    print(f"  Rows failing E/I: {len(rows)}")
    new_gaps = []
    for r in rows:
        cn = r.get("case_number", "?")
        known = cn in STRUCTURAL_BLOCKERS
        tag = STRUCTURAL_BLOCKERS.get(cn, "NEW/UNKNOWN — requires investigation")
        print(f"    {cn} | plaintiff={r.get('plaintiff')!r} | "
              f"classification={r.get('case_classification_code')}/{r.get('case_classification_label')} | {tag}")
        if not known:
            new_gaps.append(r)
    return rows, len(total), new_gaps


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        sys.exit(1)

    print(f"Gold Standard shard-1 martin E/I reconfirm, dispatch {DISPATCH_ID}")
    print(f"Supabase project: {SUPABASE_URL}\n")

    print("=== BEFORE: pencil_dod_evaluate_county('martin') ===")
    before = rpc_call("pencil_dod_evaluate_county", {"p_county": "martin"})
    print(json.dumps(before, indent=2))

    rows, total, new_gaps = diagnose()

    print(f"\n=== ANALYSIS ===")
    print(f"  Rows failing E/I: {len(rows)}")
    print(f"  Known structural blockers matched: {len(rows) - len(new_gaps)}")
    print(f"  NEW gaps requiring investigation: {len(new_gaps)}")

    if new_gaps:
        print("  ACTION: would attempt real-data fix for new gaps (NONE FOUND this session)")
    else:
        print("  ACTION: zero writes — all 3 failing rows are confirmed structural "
              "blockers (personal-property / timeshare liens), externally "
              "re-verified this session via web search corroboration of the "
              "existing case_classification labels. realforeclose.com case "
              "detail requires login; Clerk case search requires CAPTCHA; "
              "Property Appraiser search isn't meaningful against HOA "
              "plaintiff names. No real parcel/PCN found or invented.")

    print("\n=== AFTER: pencil_dod_evaluate_county('martin') (no writes made, re-run for freshness proof) ===")
    after = rpc_call("pencil_dod_evaluate_county", {"p_county": "martin"})
    print(json.dumps(after, indent=2))

    e_before = before.get("E", {}) if isinstance(before, dict) else {}
    i_before = before.get("I", {}) if isinstance(before, dict) else {}
    e_after = after.get("E", {}) if isinstance(after, dict) else {}
    i_after = after.get("I", {}) if isinstance(after, dict) else {}

    print("\n=== SESSION SUMMARY ===")
    print(f"  E before: {e_before.get('metric')}%  E after: {e_after.get('metric')}%")
    print(f"  I before: {i_before.get('metric')}%  I after: {i_after.get('metric')}%")
    print(f"  rows_examined: {len(rows)}")
    print(f"  rows_updated: 0")
    print(f"  structural_blockers_confirmed: {list(STRUCTURAL_BLOCKERS.keys())}")
    print(f"  new_gap_found: {bool(new_gaps)}")
    print(f"  honesty_tag: VERIFIED (structural ceiling, zero writes, external "
          f"corroboration via web search of case_classification labels already in DB)")

    return {
        "before": before,
        "after": after,
        "rows_examined": len(rows),
        "rows_updated": 0,
        "structural_blockers_confirmed": list(STRUCTURAL_BLOCKERS.keys()),
        "new_gap_found": bool(new_gaps),
    }


if __name__ == "__main__":
    main()
