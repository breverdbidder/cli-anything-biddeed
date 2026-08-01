#!/usr/bin/env python3
"""
sarasota_shard4_9f070f2b_parcel_geo_link.py

Task: sarasota county, letter I (card_complete threshold >=95%).
Baseline (VERIFIED live via pencil_dod_evaluate_county('sarasota'), 2026-08-01):
    I: card_complete=347 of 367 (94.6%), FAIL.

Method (same pattern as the prior sarasota SHARD-6/run5361 I geo/value-backfill
migration -- migrations/20260721_gold_standard_shard6_run5361_sarasota_i_geo_value_backfill.sql):
  1. Pull the exact 367-row scope used by pencil_dod_evaluate_county's letter-I
     gate: county='sarasota' AND (data_source <> 'propertyonion' OR
     tier1_authoritative=true) -- replicated from the live function body
     (supabase/migrations/20260718_gtm22_phase1_3_pencil_dod_snapshot_param_and_loop_rewire.sql).
  2. Pull v_zoning_gold_standard_card for sarasota (zone_code IS NOT NULL) as the
     zoning crosswalk (parcel_id OR tax_account match).
  3. Replicate card_complete in Python: property_address present AND
     lat/lng present (COALESCE(latitude, po_latitude)) AND
     (assessed_value OR market_value) present AND parcel_id IN crosswalk.
  4. For rows failing ONLY on parcel_id/lat-lng/value (i.e. NOT already blocked
     by a missing zoning-crosswalk match), query the Sarasota County Property
     Appraiser's own hosted ArcGIS FeatureServer
     (https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/FeatureServer/0,
     field `account`) by exact fulladdress prefix match, and only apply an
     UPDATE when the match is unambiguous (exactly 1 feature returned) and the
     resulting parcel_id/tax_account is ALSO present in the zoning crosswalk
     (i.e. the update would actually flip card_complete for that row -- no
     point writing a parcel_id that still leaves the row incomplete).

FINDING (VERIFIED live this session, 2026-08-01): of the 20 rows failing
card_complete, ALL 20 are blocked by the zoning-crosswalk join, not by
missing address/parcel_id/lat-lng/value alone:
  - 12 rows have NO property_address in our DB at all ("Address Not
    Available, Sarasota County, FL" or NULL) -- cannot be searched against
    the PA site without fabricating an address. Out of scope (address
    discovery via court docket, not parcel/geo linking).
  - 8 rows have a real address. Of these, 6 ALREADY have a parcel_id, but
    that parcel_id/tax_account does not exist ANYWHERE in
    v_zoning_gold_standard_card for sarasota (confirmed via live REST query,
    zero rows returned for all 6 IDs) -- this is a letter-G zoning-coverage
    gap, not a geo/parcel_id backfill problem, and per the prior SHARD-6
    session's explicit finding is out of scope for this task (no DDL, no
    fabricating zone links).
  - The remaining 2 addressable rows (parcel_id currently NULL) were looked
    up live against the Sarasota PA ArcGIS FeatureServer and got exactly 1
    unambiguous match each:
      eb52428d-a0bc-42e9-83c4-6d0366d551a2  "3223 N LOCKWOOD RIDGE RD LOT 9,
        SARASOTA, 34234" -> account 0030030004 ("3223 N LOCKWOOD RIDGE RD
        SARASOTA FL, 34234")
      39258d45-a169-455a-a5aa-fa3c8d4185c9  "6792 HIGDON RD, NORTH PORT,
        34287" -> account 0998251619 ("6792 HIGDON RD NORTH PORT FL, 34287")
    BUT: neither 0030030004 nor 0998251619 exists in
    v_zoning_gold_standard_card either (confirmed live, zero rows). Filling
    parcel_id for these 2 rows was simulated against the exact card_complete
    predicate and does NOT change the metric (347/367 before and after).
    Writing these 2 parcel_ids would be a real, verifiable improvement to
    data completeness (so this script DOES apply them -- COALESCE-safe,
    non-destructive), but it will NOT move letter I past the 95% threshold
    on its own. Flagged explicitly, not silently swallowed.

Net: this session's parcel/geo-link lever for sarasota I is exhausted at
347/367. The remaining 20-row gap requires either (a) zoning-crosswalk
coverage expansion for the 8 identified parcel_ids (letter G work, needs
parcel_zones/zoning_districts data, out of scope here), or (b) court-docket
address discovery for the 12 no-address rows (different pipeline). Reported
as still-blocked with reasons, per BLANK > WRONG.

Usage:
    python3 scripts/sarasota_shard4_9f070f2b_parcel_geo_link.py [--apply]

Without --apply, runs in report-only (dry-run) mode: prints the live
row list, the PA lookups, and the simulated card_complete before/after.
With --apply, PATCHes the 2 unambiguous-match rows' parcel_id (COALESCE-safe:
only ever fills a NULL parcel_id, never overwrites an existing value) via
PostgREST. Does not touch lat/lng or values (no PA geometry field verified
in this session for those 2 rows; the finding above shows it would not move
the DoD metric regardless).
"""
import json
import os
import sys
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

PA_FEATURESERVER = (
    "https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/"
    "FeatureServer/0/query"
)


def rest_get(path, extra_headers=None):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={**HEADERS, **(extra_headers or {})},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def rest_patch(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=data,
        method="PATCH",
        headers={**HEADERS, "Prefer": "return=representation"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def pa_lookup_by_address(addr_prefix, limit=5):
    where = f"fulladdress LIKE '{addr_prefix}%'"
    params = {
        "where": where,
        "outFields": "account,fulladdress,assd,just,zoning",
        "returnGeometry": "false",
        "f": "json",
        "resultRecordCount": str(limit),
    }
    url = PA_FEATURESERVER + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp).get("features", [])


def card_complete(r, zc_ids):
    if not r.get("property_address"):
        return False
    lat = r.get("latitude") if r.get("latitude") is not None else r.get("po_latitude")
    lng = r.get("longitude") if r.get("longitude") is not None else r.get("po_longitude")
    if lat is None or lng is None:
        return False
    if r.get("assessed_value") is None and r.get("market_value") is None:
        return False
    pid = r.get("parcel_id")
    if not pid or pid not in zc_ids:
        return False
    return True


def main():
    apply_mode = "--apply" in sys.argv

    # Exact 367-row scope used by pencil_dod_evaluate_county's letter-I gate.
    rows = rest_get(
        "multi_county_auctions"
        "?select=id,case_number,property_address,parcel_id,latitude,longitude,"
        "po_latitude,po_longitude,market_value,assessed_value,data_source,"
        "tier1_authoritative"
        "&county=eq.sarasota"
        "&or=(data_source.is.null,data_source.neq.propertyonion,"
        "tier1_authoritative.eq.true)"
        "&limit=400",
        extra_headers={"Range": "0-399"},
    )
    print(f"Scoped rows (auctions_total): {len(rows)}")

    zc = rest_get(
        "v_zoning_gold_standard_card"
        "?select=parcel_id,tax_account&county=eq.sarasota&zone_code=not.is.null"
        "&limit=400",
        extra_headers={"Range": "0-399"},
    )
    zc_ids = set()
    for z in zc:
        if z.get("parcel_id"):
            zc_ids.add(z["parcel_id"])
        if z.get("tax_account"):
            zc_ids.add(z["tax_account"])
    print(f"Zoning crosswalk (zone_code IS NOT NULL) rows: {len(zc)}")

    before_complete = sum(1 for r in rows if card_complete(r, zc_ids))
    print(f"card_complete BEFORE: {before_complete} of {len(rows)}")

    incomplete = [r for r in rows if not card_complete(r, zc_ids)]
    print(f"Incomplete rows: {len(incomplete)}")

    no_address = [
        r for r in incomplete
        if not r.get("property_address")
        or "Address Not Available" in r["property_address"]
    ]
    print(f"  - no usable address (out of scope, needs docket lookup): {len(no_address)}")

    addressable = [r for r in incomplete if r not in no_address]
    print(f"  - has real address: {len(addressable)}")

    already_has_parcel_not_in_zc = [
        r for r in addressable if r.get("parcel_id") and r["parcel_id"] not in zc_ids
    ]
    print(
        "    - already has parcel_id, but parcel_id absent from zoning "
        f"crosswalk (letter-G gap, out of scope): {len(already_has_parcel_not_in_zc)}"
    )
    for r in already_has_parcel_not_in_zc:
        print(f"        {r['id']} {r['case_number']} parcel_id={r['parcel_id']}")

    needs_parcel = [r for r in addressable if not r.get("parcel_id")]
    print(f"    - missing parcel_id entirely, has address to search: {len(needs_parcel)}")

    applied = []
    still_blocked = []

    for r in needs_parcel:
        addr = r["property_address"]
        # Use the street-number + street-name token (before first comma) as the
        # search prefix, matching the PA site's own address format.
        street = addr.split(",")[0].strip()
        # Strip trailing unit/lot descriptors the PA site won't have verbatim.
        for cut in [" LOT ", " UNIT ", " #", " BLD"]:
            if cut in street.upper():
                idx = street.upper().index(cut)
                street = street[:idx].strip()
        try:
            feats = pa_lookup_by_address(street)
        except Exception as e:
            print(f"  PA lookup FAILED for {r['id']} ({street!r}): {e}")
            still_blocked.append((r, f"PA lookup error: {e}"))
            continue

        if len(feats) != 1:
            print(f"  PA lookup AMBIGUOUS/NO-MATCH for {r['id']} ({street!r}): {len(feats)} results")
            still_blocked.append((r, f"{len(feats)} PA matches (not unambiguous)"))
            continue

        attrs = feats[0]["attributes"]
        account = attrs["account"]
        print(
            f"  MATCH {r['id']}: {street!r} -> account={account} "
            f"({attrs.get('fulladdress')})"
        )

        if account in zc_ids:
            applied.append((r, account))
        else:
            still_blocked.append(
                (r, f"matched account {account} but NOT in zoning crosswalk "
                    "(would not flip card_complete)")
            )
            # Still record as a real, verified data-completeness improvement
            # even though it won't move the DoD metric this session.
            applied.append((r, account))

    print()
    print(f"Applying parcel_id for {len(applied)} unambiguous-match row(s) "
          f"({'LIVE' if apply_mode else 'DRY-RUN'})")
    for r, account in applied:
        if apply_mode:
            result = rest_patch(
                f"multi_county_auctions?id=eq.{r['id']}&parcel_id=is.null",
                {"parcel_id": account},
            )
            print(f"    PATCHED {r['id']} parcel_id={account} -> {result}")
        else:
            print(f"    WOULD PATCH {r['id']} parcel_id={account}")

    # Simulate the metric after applying.
    sim_rows = []
    applied_ids = {r["id"]: account for r, account in applied}
    for r in rows:
        rr = dict(r)
        if rr["id"] in applied_ids:
            rr["parcel_id"] = applied_ids[rr["id"]]
        sim_rows.append(rr)
    after_complete = sum(1 for r in sim_rows if card_complete(r, zc_ids))
    print()
    print(f"card_complete SIMULATED AFTER: {after_complete} of {len(rows)}")

    print()
    print("Still blocked (with reasons):")
    for r, reason in still_blocked:
        print(f"  {r['id']} {r['case_number']}: {reason}")
    for r in no_address:
        print(f"  {r['id']} {r['case_number']}: no usable address in DB")
    for r in already_has_parcel_not_in_zc:
        print(
            f"  {r['id']} {r['case_number']}: parcel_id={r['parcel_id']} "
            "not in zoning crosswalk (letter-G gap)"
        )


if __name__ == "__main__":
    main()
