#!/usr/bin/env python3
"""SHARD-14 (liberty), dispatch 121fa7c3-6131-474f-b6c8-928efe26d2f5.

Platform research + diagnosis for Liberty County (FL's least-populous county,
~8,000 residents). Documents WHY A/B/F/G/I cannot pass right now, with live
evidence, rather than fabricating rows to force a pass.

=== A (fc>0 AND td>0) — GENUINE DATA SCARCITY, NOT A BUG ===

Liberty County is NOT on the RealAuction/RealTaxDeed platform:
  - https://liberty.realtaxdeed.com   -> HTTP 403 (bare curl)
  - https://liberty.realforeclose.com -> HTTP 403 (bare curl)
  These 403s are NOT the "needs cookie-jar session" pattern seen on other
  RealAuction subdomains (see shard2_run2450_ajax_realforeclose_harvest.py) --
  Liberty simply does not have a RealAuction tenant. Liberty runs its own
  clerk website instead:
    https://libertyclerk.com/courts/tax-deeds/        (tax deed sales)
    https://libertyclerk.com/courts/foreclosure-sales/ (foreclosure sales,
        already the data_source for our existing row: 'liberty_clerk_official:
        libertyclerk.com')
    https://libertyclerk.com/courts/property-sales/    (index page, no listings)

  Fetched https://libertyclerk.com/courts/tax-deeds/ live this session
  (HTTP 200, 94020 bytes, raw HTML grepped -- not just a WebFetch summary):
    the page contains the literal string "no properties on the list of tax
    deeds at this time" (VERIFIED via `grep -i -o` on the raw response body,
    see /tmp/liberty_taxdeed.html fetched this session).

  Conclusion: Liberty County currently has ZERO pending tax deed sales. This
  is plausible and expected for an ~8,000-population county with very few
  parcels moving through the 22-month tax-certificate-to-deed pipeline at
  any given time. A cannot pass (needs foreclosure>0 AND tax_deed>0 in the
  same population) without inventing a tax_deed row that does not exist.
  Per HARD GUARDRAIL #5 (never fabricate a case/parcel), no such row is
  written. This is reported as a genuine residual gap, to be revisited by
  re-scraping https://libertyclerk.com/courts/tax-deeds/ periodically (a tax
  deed sale could be scheduled at any time) -- NOT by this session.

=== B / F (verified_outcomes / tier1_sold ratios) — DOWNSTREAM OF A ===

closed_sold=0 because the only auction row (case 24-CA-22, foreclosure,
auction_date 2026-07-21) has not yet occurred (sold_amount IS NULL, future
sale date). B and F are ratios over closed_sold; with closed_sold=0 they are
mathematically undefined (null), matching the RPC output. There is no closed
sale to verify or backfill. Nothing to do here until the 2026-07-21 auction
actually occurs and a sold_amount is captured by the routine post-auction
scrape -- out of scope for this session (future event, not a data gap).

=== G (zoning KPI density/far/pk1000) — GENUINE DATA-LOADING GAP ===

Live queries this session (all via PostgREST, zero rows found):
  - zoning_districts?jurisdiction_id=eq.893 (jurisdictions row for "Bristol",
    Liberty's only seeded jurisdiction, id=893) -> []
  - parcel_zones?parcel_id=eq.0261S6W00725000 -> []
  - v_zoning_gold_standard_card?county=eq.liberty -> []
  - v_zoning_gold_standard_kpi_v3 has no 'liberty' row at all (spot-checked
    the view; only counties with loaded zoning data appear, e.g. 'levy').

jurisdictions row for Bristol (id=893) shows phase_3 through phase_20 marked
"complete" in the tracking table, but the actual zoning_districts/
zone_standards/parcel_zones tables have ZERO rows for jurisdiction_id=893.
This is a pipeline gap between the phase-tracking metadata and the real
Municode/GIS scrape -- Liberty's zoning ordinance (library.municode.com/fl/
bristol) was never actually scraped into zoning_districts. Fixing this
requires the Phase 4 Municode + Firecrawl + LLM extraction pipeline
(zoning_districts -> zone_standards -> permitted_uses) described in this
repo's county-expansion CLAUDE.md section, which is out of scope for a
gold-standard auction-parity shard session. Reported as residual.

=== I (card_complete) — SAME ROOT CAUSE AS G, NOT A DIFFERENT BUG ===

Live query this session confirmed the single Liberty auction row (case
24-CA-22) ALREADY carries every non-zoning card field:
  property_address = "20892 NE Burlington rd., Hosford, FL 32334"
  latitude/longitude = 30.3600103 / -84.8051394
  assessed_value = 90150, market_value = 104221
  parcel_id = "0261S6W00725000"
The I formula additionally requires a matching zone_code row in
v_zoning_gold_standard_card keyed by parcel_id -- which returns zero rows
for this parcel (see G section above: no zoning data loaded for Liberty at
all). There is nothing left to backfill on the auction-row side; I is
blocked exclusively by the same zoning-data-loading gap as G.

=== WRITES PERFORMED THIS SESSION ===

None to multi_county_auctions. Diagnosis-only: every field the I/A/B/F
formulas need on the auction-row side was already populated by a prior
session (data_source='liberty_clerk_official:libertyclerk.com'). No NULL
field was found to backfill, no proven-wrong value was found to correct, and
no real tax_deed auction exists to ingest. Writing a fabricated tax_deed row
or a fabricated zone_code would violate HARD GUARDRAILS #2 and #5.

Usage: python3 scripts/shard14_run3534_liberty_platform_fix.py
  (diagnostic/report-only script -- performs live read-only verification
  queries and prints them; makes zero writes given the findings above)
"""
import os
import json
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rpc(fn, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    print("=== fl_counties liberty ===")
    print(json.dumps(rest_get("fl_counties?slug=eq.liberty&select=*"), indent=2))

    print("\n=== multi_county_auctions liberty (card fields) ===")
    print(json.dumps(rest_get(
        "multi_county_auctions?county=eq.liberty&select=case_number,sale_type,"
        "property_address,latitude,longitude,assessed_value,market_value,"
        "parcel_id,sold_amount,auction_date,data_source"), indent=2))

    print("\n=== jurisdictions liberty (Bristol) ===")
    print(json.dumps(rest_get(
        "jurisdictions?county=ilike.*liberty*&select=id,name,county,municode_url"),
        indent=2))

    print("\n=== zoning_districts for jurisdiction_id=893 (Bristol) ===")
    print(json.dumps(rest_get("zoning_districts?jurisdiction_id=eq.893&select=*"),
                      indent=2))

    print("\n=== parcel_zones for the one liberty parcel ===")
    print(json.dumps(rest_get(
        "parcel_zones?parcel_id=eq.0261S6W00725000&select=*"), indent=2))

    print("\n=== v_zoning_gold_standard_card county=liberty ===")
    print(json.dumps(rest_get(
        "v_zoning_gold_standard_card?county=eq.liberty&select=*"), indent=2))

    print("\n=== live pencil_dod_evaluate_county('liberty') ===")
    print(json.dumps(rpc("pencil_dod_evaluate_county", {"p_county": "liberty"}),
                      indent=2))

    print("\nCONCLUSION: no writes performed. See module docstring for full")
    print("evidence chain on why A/B/F/G/I are genuine residual gaps this")
    print("session cannot close without fabricating data (forbidden by")
    print("HARD GUARDRAILS #2 and #5).")


if __name__ == "__main__":
    main()
