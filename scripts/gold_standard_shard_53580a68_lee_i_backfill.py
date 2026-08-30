#!/usr/bin/env python3
"""GOLD STANDARD lee I fix, 2026-08-30 session (dispatch 53580a68), continuation of
2026-08-29 session's 4-stage lee I work (gold_standard_shard5_lee_20260829_i_*.py,
which took I from 72.1%->89.3%/400 of 448 rows). Denominator has drifted since
yesterday (448 -> 449 tier1-eligible rows, one new auction).

LIVE BASELINE (re-measured today via pencil_dod_evaluate_county('lee')):
  I: card_complete=403 of 449 (89.8%), FAIL (gate 95% / ~427 rows)
  G: 97.0, PASS (unaffected baseline)

LIVE RE-DIAGNOSIS (replicating pencil_dod_evaluate_county's exact tier1-eligible
cohort + card_complete SQL: is_operational=true AND (data_source != 'propertyonion'
OR data_source IS NULL); card_complete = property_address present AND
COALESCE(latitude,po_latitude)/COALESCE(longitude,po_longitude) present AND
COALESCE(assessed_value,market_value) present AND parcel_id linked via
parcel_zones.zone_code in v_zoning_gold_standard_card):

  IMPORTANT METHODOLOGY NOTE: the naive `parcel_zones?zone_code=not.is.null&select=
  parcel_id` GET without a parcel_id filter silently truncates at PostgREST's
  default 1000-row page (parcel_zones has 764,725 total rows fleet-wide) -- an
  unscoped query returns essentially zero lee-relevant matches and would have
  produced a fabricated "426 zone-link-only" bucket. Corrected by scoping the
  parcel_zones query with parcel_id=in.(<our 436 lee parcel_ids>, chunked +
  URL-encoded) before computing the linked set. This discipline is preserved
  below for any future re-run of this diagnostic.

  10  no property_address AND no parcel_id at all (fully blank rows -- unresolvable,
      left alone, same class as yesterday's 11-row residual)
  2   parcel_id/address edge cases (unresolvable, confirmed dead ends, see below):
        24-CC-004249  "16300 PINE RIDGE RD LOT X18" -- mobile-home-park lot format,
          NO parcel_id, and ArcGIS SITENUMBER=16300 lookup returns no STRAP (same
          dead end yesterday's stage-4 script already tried and confirmed)
        25-CA-004116  parcel_id="TIMESHARE" (placeholder, not a real STRAP), no
          property_address at all -- unresolvable
  11  parcel_id present, missing assessed_value/market_value -- ALL 11 are Lehigh
      Acres / Alva addresses whose parcel_id block segment is a plain NUMERIC code
      (e.g. "07", "16", "03"). Per yesterday's stage-3 TRANSFORM DISCOVERY, the
      naive STRAP-strip transform (remove "-"/".") does NOT work for these: Lee
      County ArcGIS's STRAP block segment for these TRS blocks is a LETTER code
      (L1/L2/L3/L4), not the numeric code stored in our parcel_id, and there is no
      deterministic numeric->letter mapping. CONFIRMED live today: all 11 naive
      STRAP lookups returned zero ArcGIS features. Resolved via the same
      address-based fallback yesterday's stage-3/4 scripts used (SITENUMBER exact +
      SITESTREET match against property_address): 10 of 11 resolved to exactly one
      ArcGIS feature.
        - 9 of 10 have SITEADDR that echoes our stored property_address EXACTLY.
        - 1 of 10 (2026000286, "3404 20TH ST SW") has ONLY ONE ArcGIS candidate at
          SITENUMBER=3404 matching "20TH", but that candidate's SITEADDR reads
          "3404 20TH ST W" (directional suffix "W" vs our "SW") -- confirmed via a
          broader wildcard scan (SITENUMBER='3404' AND SITESTREET LIKE '%20TH%')
          that this is the ONLY candidate at that site number on that street (not
          an ambiguous multi-match), consistent with Lee County ArcGIS's known
          inconsistent directional-suffix formatting. Accepted as the same parcel,
          same confidence tier as yesterday's precedent matches.
        - 1 of 11 (24-CA-007460, parcel_id literally "Property Appraiser", a
          placeholder value) is unresolvable -- NOT attempted (not a real parcel_id
          to search by, and this is a duplicate-with-yesterday's-list placeholder
          case). Left as documented residual.
  21  zone-link-only gap (parcel_id/address/geo/value all present, but parcel_id
      not linked to a zone_code in parcel_zones). Live ArcGIS ZONING lookup for all
      21 STRAPs found:
        - 3 already-known dead ends from yesterday's session, NOT re-attempted:
            07-45-24-C2-05300.0100 (Cape Coral, ZONING=R1-D, NO existing
              zoning_districts row for (815, "R1-D") -- only plain "R1" exists)
            27-47-25-B2-00412.0020, 01-48-25-B2-00200.0790 (Bonita Springs,
              ZONING=MH-1, jurisdiction_id=914 code MH-1 confirmed yesterday to
              have ZERO zone_standards rows -- inserting drops G, already reverted
              twice this week)
        - 15 returned ZONING=None (condo/PUD sub-units -- Kelly Cove Dr, Kelly
          Greens Blvd, Kelly Sands Way, Ocean Walk Cir, Bay Beach Ln, Lakewood
          Trace Ct, Calabria Ct, Diamond Centre Ct, Bluewater Trace, and SW 3rd St
          condo units -- real structural source gap, confirmed condo/PUD parcels
          lack a unit-level ZONING attribute in this ArcGIS layer, same class as
          yesterday's 14-row condo residual)
        - 3 returned ZONING="" empty string (timeshare/PUD units on Kings Crown Dr,
          Dixie Beach Blvd, Tahiti Dr -- also a real structural gap)
        - 1 (13-43-22-C3-05462.0050, case 2026000277) returned ZONING="R1", block
          code "C3" places it in Cape Coral (jurisdiction_id=815, same convention
          confirmed for other C3-block parcels this week), and zoning_districts
          already has an exact row for (815, "R1") id=11226 -- SAFE to link, same
          low-risk residential-category pattern proven safe in yesterday's stage
          2b/3 batches (zero G-regression across ~75 residential-code inserts this
          week).

THIS SCRIPT covers:
  Stage A: 10 assessed_value backfills (address-matched ArcGIS ASSESSED field) --
    pure multi_county_auctions PATCH, zero G-regression risk (no zoning-table write).
  Stage B: 1 parcel_zones insert (13-43-22-C3-05462.0050 -> jurisdiction_id=815,
    zone_code=R1, existing district id=11226) -- G is re-checked live immediately
    after via pencil_dod_evaluate_county('lee') and the row is reverted if G drops,
    same guardrail as every prior lee I session this week.
  Stage C (discovered live AFTER running stage A/B, not in the original diagnosis):
    re-checking pencil_dod_evaluate_county('lee') after stage A showed I flat at
    403/449 despite 10 successful value patches -- live re-verification found all
    10 of those rows ALSO lack a parcel_zones link entirely (confirmed via
    parcel_id=in.(...) scoped query returning zero rows), i.e. they needed BOTH
    fixes, not just the value fix. Looked up ZONING for all 10 via the same
    ArcGIS STRAPs already resolved in stage A: all 10 are ZONING=RS-1 in
    jurisdiction_id=630 (Lee County Unincorporated), which already has an
    existing zoning_districts row (id=11108) -- same proven-safe low-risk
    residential pattern as stage B and every prior batch this week. Inserted as
    one batch, G re-checked live, reverted on any regression.

EXECUTION NOTE (2026-08-30): on a re-run of this script (Stage A rows had already
been patched, so it correctly no-op'd on the drift-check), the Stage B
`parcel_zones` POST with `Prefer: resolution=ignore-duplicates` inserted a SECOND
row for the same (parcel_id, jurisdiction_id, zone_code) tuple instead of
deduping -- the table has no unique constraint covering that tuple, so
ignore-duplicates silently did not prevent the duplicate. Harmless to I/G (the
completeness JOIN only checks row existence, not row count) but manually deleted
(id=874471) as data hygiene immediately after detection. Any future re-run of
this script's Stage B/C should check for an existing row before POSTing rather
than relying on ignore-duplicates.

Explicitly NOT attempted (documented residual, not fabricated):
  - 10 rows with no address/parcel_id at all
  - 24-CC-004249, 25-CA-004116 (confirmed dead ends)
  - 24-CA-007460 (placeholder parcel_id "Property Appraiser")
  - 07-45-24-C2-05300.0100 (R1-D, no matching zoning_districts row)
  - 27-47-25-B2-00412.0020, 01-48-25-B2-00200.0790 (Bonita Springs MH-1, zero
    zone_standards rows, confirmed dead end twice this week already)
  - 18 condo/PUD/timeshare zone-link rows with no real ZONING value from ArcGIS
"""
import os
import json
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# Stage A: assessed_value backfills. Source: live ArcGIS address-match lookup
# (SITENUMBER exact + SITESTREET match), SITEADDR cross-checked against our
# stored property_address (see docstring for the one directional-suffix
# exception, 2026000286, and its single-candidate justification).
VALUE_BACKFILL_ROWS = [
    {"id": "736c1a32-54b3-487a-8f97-89cf3dc9a471", "case": "2026000232",
     "parcel_id": "36-44-26-07-00058.0120", "strap": "364426L1070580120",
     "assessed_value": 7597},
    {"id": "d7f6921a-2698-4bb4-887b-aac91980a749", "case": "2026000172",
     "parcel_id": "16-44-27-02-00008.0230", "strap": "164427L3020080230",
     "assessed_value": 9414},
    {"id": "2127fd9d-0508-43b1-993e-726abe13020e", "case": "2026000080",
     "parcel_id": "03-44-27-01-0000C.0040", "strap": "034427L20100C0040",
     "assessed_value": 156895},
    {"id": "436e8b46-d6c4-41df-bffa-beabd1fbd487", "case": "2026000286",
     "parcel_id": "02-45-26-06-00051.0130", "strap": "234426L4080060030",
     "assessed_value": 226107},
    {"id": "d0d6653f-877f-41e2-a4ba-68328f2612e3", "case": "2026000224",
     "parcel_id": "06-44-27-02-00238.0010", "strap": "064427L2362380010",
     "assessed_value": 10050},
    {"id": "291dbc7c-c633-480d-833d-53ea4b0ec682", "case": "2026000131",
     "parcel_id": "05-44-27-03-00160.0060", "strap": "054427L3241600060",
     "assessed_value": 209183},
    {"id": "45e2868f-a990-4a59-a1a1-2dc4dfa0554c", "case": "2026000240",
     "parcel_id": "14-45-26-01-00003.0040", "strap": "144526L2010030040",
     "assessed_value": 283327},
    {"id": "41d60afd-738f-4b09-9bfb-3be70c9a17fc", "case": "2026000220",
     "parcel_id": "03-44-27-07-00025.0100", "strap": "034427L4050250100",
     "assessed_value": 6281},
    {"id": "4b0c56e8-77eb-43eb-8ba4-1b2574033d4a", "case": "2026000217",
     "parcel_id": "04-44-27-10-00069.0060", "strap": "044427L4150690060",
     "assessed_value": 10050},
    {"id": "c2d21c51-d95d-458b-bb91-1c853c749e2f", "case": "2026000216",
     "parcel_id": "04-44-27-10-00069.0050", "strap": "044427L4150690050",
     "assessed_value": 10050},
]

# Stage B: single-row zone link, already-existing zoning_districts row, low-risk
# residential category (R1), matches proven-safe pattern from this week's prior
# batches.
ZONE_LINK_ROW = {
    "parcel_id": "13-43-22-C3-05462.0050", "jurisdiction_id": 815,
    "zone_code": "R1", "zone_name": "R1 Zone",
    "source": "lee_20260830_i_backfill_shard_53580a68_arcgis",
}

# Stage C: discovered live after running Stage A -- the 10 value-backfilled rows
# above ALSO lack a parcel_zones link. All resolve to RS-1 in jurisdiction_id=630
# (Lee County Unincorporated), which already has an existing zoning_districts row
# (id=11108). Same low-risk residential pattern as every prior batch this week.
STAGE_C_ZONE_LINK_ROWS = [
    {"parcel_id": "36-44-26-07-00058.0120", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "16-44-27-02-00008.0230", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "03-44-27-01-0000C.0040", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "02-45-26-06-00051.0130", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "06-44-27-02-00238.0010", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "05-44-27-03-00160.0060", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "14-45-26-01-00003.0040", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "03-44-27-07-00025.0100", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "04-44-27-10-00069.0060", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
    {"parcel_id": "04-44-27-10-00069.0050", "jurisdiction_id": 630, "zone_code": "RS-1",
     "zone_name": "Residential Single-Family Low Density"},
]


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
                                  headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_post(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json",
                 "Prefer": "resolution=ignore-duplicates,return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_delete(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", method="DELETE",
                                  headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                                           "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def evaluate():
    body = json.dumps({"p_county": "lee"}).encode()
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                                  data=body, method="POST",
                                  headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                                           "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    ev0 = evaluate()
    g_before = ev0["G"]["metric"]
    i_before = ev0["I"]["metric"]
    print(f"BASELINE: G={g_before} pass={ev0['G']['pass']}  I={i_before} ({ev0['I']['detail']})")

    # --- Stage A: value backfill (zero G-regression risk, no zoning write) ---
    value_fixed = 0
    for r in VALUE_BACKFILL_ROWS:
        # Re-verify live before writing -- never trust a value baked in from an
        # earlier diagnostic pass without a fresh re-check.
        current = rest_get(f"multi_county_auctions?id=eq.{r['id']}&select=assessed_value,market_value,parcel_id")
        if not current:
            print(f"  {r['case']}: ROW NOT FOUND (skip)")
            continue
        cur = current[0]
        if cur.get("assessed_value") is not None or cur.get("market_value") is not None:
            print(f"  {r['case']}: already has a value (drifted since diagnosis) -- skip")
            continue
        if cur.get("parcel_id") != r["parcel_id"]:
            print(f"  {r['case']}: parcel_id drifted since diagnosis ({cur.get('parcel_id')} != {r['parcel_id']}) -- skip")
            continue
        try:
            rest_patch(f"multi_county_auctions?id=eq.{r['id']}", {"assessed_value": r["assessed_value"]})
            value_fixed += 1
            print(f"  {r['case']} ({r['strap']}): PATCHED assessed_value={r['assessed_value']}")
        except Exception as e:
            print(f"  {r['case']}: PATCH FAILED {e}")

    ev1 = evaluate()
    print(f"\nAFTER STAGE A (value backfill): G={ev1['G']['metric']} (was {g_before})  "
          f"I={ev1['I']['metric']} ({ev1['I']['detail']})")

    # --- Stage B: single zone link, G-regression-checked ---
    zone_row = ZONE_LINK_ROW
    resp = rest_post("parcel_zones", [zone_row])
    inserted_ids = [r["id"] for r in resp] if isinstance(resp, list) else []
    n_inserted = len(inserted_ids)
    print(f"\nSTAGE B: parcel_zones insert (jur={zone_row['jurisdiction_id']} "
          f"code={zone_row['zone_code']} pid={zone_row['parcel_id']}): inserted={n_inserted}")

    ev2 = evaluate()
    g_after_zone = ev2["G"]["metric"]
    print(f"POST-ZONE-INSERT: G={g_after_zone} (was {ev1['G']['metric']})  I={ev2['I']['metric']} ({ev2['I']['detail']})")

    if n_inserted and g_after_zone < ev1["G"]["metric"]:
        print(f"G REGRESSION DETECTED ({ev1['G']['metric']} -> {g_after_zone}). Reverting zone-link insert.")
        id_list = ",".join(str(i) for i in inserted_ids)
        rest_delete(f"parcel_zones?id=in.({id_list})")
        ev2b = evaluate()
        print(f"post-revert: G={ev2b['G']['metric']} pass={ev2b['G']['pass']}  I={ev2b['I']['metric']}")
        zone_kept = False
    else:
        print("No G regression. Zone link kept.")
        zone_kept = n_inserted > 0

    ev3 = evaluate()
    g_before_c = ev3["G"]["metric"]
    i_before_c = ev3["I"]["metric"]
    print(f"\nPRE-STAGE-C: G={g_before_c}  I={i_before_c} ({ev3['I']['detail']})")

    # --- Stage C: 10-row zone-link batch (discovered live, see docstring) ---
    resp_c = rest_post("parcel_zones", STAGE_C_ZONE_LINK_ROWS)
    inserted_ids_c = [r["id"] for r in resp_c] if isinstance(resp_c, list) else []
    n_inserted_c = len(inserted_ids_c)
    print(f"\nSTAGE C: parcel_zones batch insert (jur=630 code=RS-1, 10 rows): inserted={n_inserted_c}")

    ev4 = evaluate()
    g_after_c = ev4["G"]["metric"]
    print(f"POST-STAGE-C: G={g_after_c} (was {g_before_c})  I={ev4['I']['metric']} ({ev4['I']['detail']})")

    stage_c_kept = n_inserted_c
    if inserted_ids_c and g_after_c < g_before_c:
        print(f"G REGRESSION DETECTED ({g_before_c} -> {g_after_c}). Reverting Stage C batch.")
        id_list = ",".join(str(i) for i in inserted_ids_c)
        rest_delete(f"parcel_zones?id=in.({id_list})")
        ev4b = evaluate()
        print(f"post-revert: G={ev4b['G']['metric']} pass={ev4b['G']['pass']}  I={ev4b['I']['metric']}")
        stage_c_kept = 0
    else:
        print("No G regression. Stage C batch kept.")

    ev_final = evaluate()
    print(f"\nFINAL: G={ev_final['G']['metric']} pass={ev_final['G']['pass']}  "
          f"I={ev_final['I']['metric']} pass={ev_final['I']['pass']} ({ev_final['I']['detail']})")
    print(f"\nSUMMARY: value_fixed={value_fixed}/10  zone_linked_stageB={'1' if zone_kept else '0'}/1  "
          f"zone_linked_stageC={stage_c_kept}/10")
    print("Residuals deliberately left alone: 10 no-addr/no-pid, 2 confirmed dead ends "
          "(24-CC-004249 mobile-home lot, 25-CA-004116 TIMESHARE), 1 placeholder parcel_id "
          "(24-CA-007460), 1 R1-D no-district (07-45-24-C2-05300.0100), 2 Bonita Springs "
          "MH-1 zero-zone_standards (27-47-25-B2-00412.0020, 01-48-25-B2-00200.0790), "
          "18 condo/PUD/timeshare rows with no ArcGIS ZONING value.")


if __name__ == "__main__":
    main()
