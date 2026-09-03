#!/usr/bin/env python3
"""Tax-deed reel-candidate backfill from public.clerk_ssot_sale_rows (issue
#19794, CMO Factory CP3c-D).

CONTEXT: winnerdata.biddeed_reels' tax-deed candidate source
(biddeed_reels_pipeline.get_third_party_wins -> public.auction_buyer_sightings)
is a thin, largely NON-overlapping slice of the county footprint that
public.clerk_ssot_sale_rows already covers for calendar parity (11,396
tax_deed rows across 17 counties as of 2026-09-03; only 'highlands' overlaps
auction_buyer_sightings' own county set at all). This script adds
clerk_ssot_sale_rows as a SECOND candidate source, feeding the same
process_row() pipeline as the daily job -- it does not change how a
candidate is rendered, only where extra candidates come from.

SCHEMA FINDING (do not assume parity with multi_county_auctions): live-
verified 2026-09-03, clerk_ssot_sale_rows carries ONLY id, county_slug,
sale_type, case_number, sale_date, cancelled, raw_comment, case_title,
source_url, parsed_at, created_at -- no sold_amount, no parcel_id, no
property_address column exists. sale_date itself is null for 10,114 of
11,396 rows (89%); the per-county raw_comment free text is the only place
a cert/bid/parcel reference sometimes lives, and its FORMAT is entirely
different per county (confirmed: nassau "STATUS | cert N | bid $X" where
$X is the certificate's opening/redemption bid, NOT a closing sale price;
highlands "STATUS | parcel C-.." with no dollar figure at all; st_lucie/
levy/st_johns/walton/gadsden/hardee/gulf/hamilton/desoto/suwannee each use
yet another format; case_title embeds full plaintiff/defendant names for
several counties -- NEVER read case_title into anything user-facing, only
case_number). None of this is usable as a reel's price field directly.

The only place real, structured sold_amount/parcel_id/property_address/
assessed_value exists for these case numbers is public.multi_county_auctions,
so a clerk_ssot_sale_rows row only becomes a candidate once it JOINS to an
multi_county_auctions row on (case_number, county) -- confirmed live: only
723 of 7,923 non-cancelled clerk_ssot tax_deed rows join at all (9.1%),
concentrated away from the two counties that hold 94.7% of clerk_ssot's own
volume (highlands 7.6% join rate, nassau 2.1%) -- i.e. this is a genuine
data-completeness gap for those two counties, not purely a wiring gap, even
though wiring the join is still the correct and necessary fix for the ~9%
that DOES join, and for the smaller counties that join at 90-100%.

QUALIFYING FILTER (all required -- see docs/spec/19794.md for full evidence):
  - clerk_ssot_sale_rows.cancelled = false
  - clerk_ssot's own raw_comment does not match a negative-outcome marker
    (REDEEMED/CANCELLED/APPLICANT/DEFAULTED/PENDING/SCHEDULED/"FOR SALE") --
    a redeemed cert or a still-scheduled auction is not a sale regardless of
    what any other field says
  - multi_county_auctions.sale_result = 'SOLD_THIRD_PARTY' OR
    tier1_sale_status = 'SOLD' (tier1 is this schema's own verified-outcome
    override tier, already used elsewhere for stale-base-field cases;
    live-confirmed some real tier1_sold_amount values differ from and
    supersede opening_bid, i.e. this is a genuine re-verified closing price,
    not opening_bid relabeled)
  - a real price exists: sold_amount > 0 OR tier1_sold_amount > 0 --
    opening_bid/base_bid/po_opening_bid are NEVER used as sold_amount (they
    are the certificate's minimum required bid, not what the property
    actually closed for)
  - parcel_id is present (no parcel identifier upstream = cannot even
    attempt the imagery join below)

DATA-QUALITY ASSERTION (issue #19794 step 5 -- encode Ariel's absolute-
auction correction as code, not just prose): Florida tax-deed sales have no
plaintiff/lender able to credit-bid and reclaim the property the way a
foreclosure bank can, so a genuinely third-party-sold tax_deed row (per the
filter above) does NOT need foreclosure's winning_bidder-ambiguity check --
this script never calls or requires that check for a tax_deed candidate.
It DOES still require the sale_result/tier1_sale_status "did a sale to a
third party actually happen" gate above, because 'SOLD_PLAINTIFF' and
'SOLD APPLICANT' outcomes are real and do occur (the certificate applicant
receiving the property when nobody outbids the minimum) -- that is a
distinct concept from foreclosure's winning_bidder ambiguity, not the same
check re-applied, and is exactly what the raw_comment/sale_result filters
above exclude.

Negative tests this script must not violate:
  (a) a row whose property_address fails the parcel-outline join
      (lib.match_parcel) is never inserted -- checked after the SQL
      qualifying filter, before any Maps/TTS/vision spend
  (b) a case is never sourced twice -- the SQL UNIONs against
      auction_buyer_sightings' own (case_number, county) set before this
      script ever sees a row, and biddeed_reels' own (case_number, county)
      unique constraint is the second guard
  (c) no winning_bidder/foreclosure-style ambiguity check is applied here

Run:
  python scripts/biddeed_reels_clerk_ssot_taxdeed_backfill.py [--days 14]
    [--limit N] [--force] [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import biddeed_reels_lib as lib
import biddeed_reels_pipeline as pipeline

NEGATIVE_STATUS_RE = r"(REDEEM|CANCEL|APPLICANT|DEFAULT|PENDING|SCHEDULED|FOR SALE)"


def get_clerk_ssot_tax_deed_candidates(days: int) -> list[dict]:
    """Returns qualifying clerk_ssot_sale_rows tax_deed rows already joined
    to their multi_county_auctions price/parcel fields, deduped against
    auction_buyer_sightings by (case_number, county), for the last `days`
    days (by clerk sale_date, falling back to multi_county_auctions'
    auction_date/sale_date when clerk's own sale_date is null -- true for
    the large majority of rows, see module docstring)."""
    sql = f"""
        with clerk_qualifying as (
            select c.case_number, c.county_slug as county, c.sale_type,
                   coalesce(c.sale_date, m.auction_date, m.sale_date) as auction_date,
                   m.property_address,
                   case when coalesce(m.sold_amount, 0) > 0 then m.sold_amount else m.tier1_sold_amount end as sold_amount
            from public.clerk_ssot_sale_rows c
            join public.multi_county_auctions m
                on m.case_number = c.case_number and m.county = c.county_slug
            where c.sale_type = 'tax_deed'
              and c.cancelled = false
              and coalesce(c.raw_comment, '') !~* '{NEGATIVE_STATUS_RE}'
              and (m.sale_result = 'SOLD_THIRD_PARTY' or upper(coalesce(m.tier1_sale_status, '')) = 'SOLD')
              and (coalesce(m.sold_amount, 0) > 0 or coalesce(m.tier1_sold_amount, 0) > 0)
              and m.parcel_id is not null
        ),
        already_sourced as (
            select case_number, county from public.auction_buyer_sightings
            where buyer_type = 'third_party' and sale_type = 'tax_deed'
        )
        select cq.case_number, cq.county, cq.sale_type, cq.auction_date::text as auction_date,
               cq.property_address, cq.sold_amount
        from clerk_qualifying cq
        left join already_sourced a on a.case_number = cq.case_number and a.county = cq.county
        where a.case_number is null
          and cq.auction_date >= current_date - interval '{int(days)} days'
          and cq.auction_date <= current_date
        order by cq.auction_date desc;
    """
    return lib.run_sql(sql)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14, help="lookback window in days (default 14)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="cap rows actually rendered (cost control)")
    ap.add_argument("--audit-only", action="store_true",
                     help="run the parcel-join check across every candidate, ignoring --limit; render nothing")
    args = ap.parse_args()

    candidates = get_clerk_ssot_tax_deed_candidates(args.days)
    print(f"{len(candidates)} clerk_ssot-sourced tax_deed candidate(s) in the last {args.days} day(s) "
          f"(post-dedup against auction_buyer_sightings, pre-parcel-join-check).")

    # The parcel-outline check (lib.match_parcel) is a real address ILIKE
    # query against zw_parcels (10.5M rows) and costs ~15-30s per candidate
    # regardless of --limit. --limit is applied to the CANDIDATE list before
    # this check, not after, so a cost/time-bounded render run doesn't pay
    # that cost for rows it was never going to render this run. Use
    # --audit-only to run the check across every candidate instead (no
    # render, no API spend) when the goal is the join-failure-rate report.
    audit_pool = candidates if args.audit_only else candidates[: args.limit] if args.limit else candidates

    parcel_ok, parcel_fail = [], []
    for i, c in enumerate(audit_pool):
        parcel = lib.match_parcel(c["property_address"], c["county"])
        if parcel and parcel.get("centroid_lat") is not None:
            parcel_ok.append(c)
        else:
            parcel_fail.append(c)
        if (i + 1) % 10 == 0:
            print(f"  ...parcel-join checked {i+1}/{len(audit_pool)} (pass={len(parcel_ok)} fail={len(parcel_fail)})",
                  flush=True)

    print(f"parcel-outline join checked for {len(audit_pool)}/{len(candidates)} candidate(s): "
          f"{len(parcel_ok)} pass, {len(parcel_fail)} fail (fail = negative test (a), never inserted).")
    if parcel_fail:
        print("=== PARCEL JOIN FAILURES (excluded) ===")
        for c in parcel_fail:
            print(f"  {c['county']} / {c['case_number']}: {c['property_address']!r}")

    to_render = [] if args.audit_only else parcel_ok

    def resolve_key(env_name, vault_names):
        v = os.environ.get(env_name, "")
        if v or args.dry_run:
            return v
        for name in vault_names:
            try:
                return lib.get_vault_secret(name)
            except Exception:
                continue
        return ""

    keys = {
        "google_maps": resolve_key("GOOGLE_MAPS_API_KEY", ["google_maps_api_key"]),
        "elevenlabs": resolve_key("ELEVENLABS_API_KEY", ["elevenlabs_api_key", "elevenlabs_production"]),
        "openrouter": resolve_key("OPENROUTER_API_KEY", ["openrouter_api_key"]),
        "router": resolve_key("ROUTER_PROXY_KEY", ["router_proxy_key"]),
    }
    missing = [k for k, v in keys.items() if not v and not args.dry_run]
    if missing and to_render:
        print(f"ERROR: missing required keys (env + vault both empty) for: {missing}", file=sys.stderr)
        sys.exit(1)

    results = []
    for c in to_render:
        sighting = {
            "case_number": c["case_number"], "county": c["county"], "sale_type": c["sale_type"],
            "auction_date": c["auction_date"], "property_address": c["property_address"],
            "sold_amount": c["sold_amount"],
        }
        print(f"Processing {sighting['case_number']} / {sighting['county']} "
              f"(source=clerk_ssot_sale_rows) ...")
        r = pipeline.process_row(sighting, args.force, args.dry_run, keys)
        print(f"  -> {r['status']}" + (f" ({r['error']})" if r.get("error") else ""))
        results.append(r)

    n_ok = sum(1 for r in results if r["status"] == "pending_approval")
    n_err = sum(1 for r in results if r["status"] == "error")
    n_skip = sum(1 for r in results if r["status"] == "skipped_has_video")
    print("\n=== SUMMARY ===")
    print(f"days={args.days} candidates_pre_parcel_check={len(candidates)} parcel_join_pass={len(parcel_ok)} "
          f"parcel_join_fail={len(parcel_fail)} rendered_this_run={len(to_render)} "
          f"pending_approval={n_ok} error={n_err} skipped_has_video={n_skip}")


if __name__ == "__main__":
    main()
