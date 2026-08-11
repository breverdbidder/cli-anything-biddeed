# Gold Standard shard-5 baker — dispatch 14cbae1a-b1e3-4744-99c7-ffe69766ca29

Session: 2026-08-11, loop run 10589 baseline. Ultracode workflow (native mode) used for
fan-out research + adversarial verify per the ULTRALOOP PROTOCOL.

## Method

Baker had already been worked by 7+ prior sessions on the same stuck case numbers
(022025CA000117CAAXMX, 022025CA000124CAAXMX, 022025CC000132CCAXMX) and a zoning gap
(parcel 073S21000000000100). Re-scraping the same two RealAuction subdomains again would
have been wasted budget, so this session ran a `Workflow` fan-out of 4 independent research
agents (one per stuck item, each explicitly instructed to try genuinely different sources —
Clerk docket search, bakerpa.com cross-reference, legal-notice aggregators, ArcGIS GIS) and
then an adversarial verifier agent per finding whose only job was to try to refute it via an
independent re-fetch. Results below only include claims that survived refutation.

## Findings that survived adversarial verification (applied live)

1. **022025CA000124CAAXMX** — found via `bakercountypress.com` legal notices (a source none
   of the 6 prior sessions had checked). NOTICE OF SALE PURSUANT TO CHAPTER 45, Case No.
   25000124CAMXAX (Baker Clerk's abbreviated serialization of the same 02/2025/CA/000124
   tokens), Carrington Mortgage Services LLC vs. Estate of Norman Danny Thrift et al., sale
   8/27/2026 11:00am at baker.realforeclose.com — exact match to our auction_date/URL.
   Cross-referenced against bakerpa.com: parcel **052S22000000000020**, owner "THRIFT NORMAN
   DANNY SR" (exact defendant match), Site Address "5438 CR 23D Glen St Mary, FL", Total Just
   Value $135,204, Assessed Value $53,079. Lat/long from Baker County GIS ArcGIS FeatureServer
   centroid. Refuter independently re-fetched the notice and re-queried the ArcGIS layer —
   not refuted.
2. **Zoning gap, parcel 073S21000000000100** (case 022025CA000002CAAXMX, resolved for
   parcel/address/value in a 2026-08-10 session but explicitly left the zoning link open) —
   Baker County GIS ArcGIS FeatureServer (`parcels_web2/FeatureServer/0`) query for this
   PARCELNO returns Zoning="AG 7.5", matching owner (HOLMES) and 13.21-acre size. Not refuted.
3. **Zoning gap, parcel 052S22000000000020** (the case124 parcel newly linked this session) —
   same ArcGIS layer, Zoning="AG 7.5", Deed_Acrea=1.5. Applied same session, verified live via
   `v_zoning_gold_standard_card` immediately after.
4. **J**: generated a `bid_decisions` row for case 022025CA000124CAAXMX via the Shapira v14
   formula on the verified ARV ($135,204 Total Just Value): max_bid=$39,362.20.

## Findings that did NOT survive / were correctly left untouched

- **022025CA000117CAAXMX** — 7th independent session to reach the same conclusion:
  genuinely source-exhausted. Clerk OCRS is gated by a mandatory Cloudflare Turnstile
  checkbox (confirmed via Playwright screenshot of the reset-on-submit behavior);
  bakerclerk.com and Trellis.law both 403; PropertyOnion's Baker listing search found zero
  match among its 106 visible listings (6 more paywalled, unverifiable). No data fabricated.
- **022025CC000132CCAXMX** — re-assessed legitimacy against the 8th Judicial Circuit's own
  AO 9.02 case-type-assignment PDF: "CC" (County Court) *is* a valid Baker foreclosure case
  type for $5,001–$15,000 claims, so the case-type code alone doesn't disqualify it. But it
  remains the only Baker row with a CC-suffixed case number AND the only row with
  `judgment_amount=$0.00`, and matches this county's own twice-already-fixed
  calendar_sweep_mca_v3 mislabeled-duplicate signature. This is circumstantial-pattern
  evidence (**INFERRED**), not a positive docket confirmation — every independent
  court-record source was blocked (OCRS login wall, bakerclerk.com 403, UniCourt WAF,
  Trellis.law 403, RealAuction login wall, PropertyOnion JS-only page). Per BLANK > WRONG,
  left untouched rather than guess-deleted.

## Separate finding — actively recurring duplicate-row bug (escalated, not root-caused)

The sale_type='tax_deed', all-NULL duplicate row for case 022025CA000148CAAXMX (previously
documented recurring twice on 2026-08-10) recurred **four more times** during this single
session (~16:15, ~16:30 pre-existing, ~16:15, ~16:25 — roughly every 10–25 minutes, far
faster than the previously-assumed daily cadence). Deleted live each time (FK-safety
re-verified against auction_enrichment_queue / auction_schedule_history /
court_case_metadata / po_mca_matches / shapira_outcome_scorecard — zero references every
time). New evidence this session: the phantom row's `tier1_source_run_id` is a **stable**
value (55009) across recurrences with fresh `tier1_verified_at`/`scraped_at` timestamps each
time, while the genuine sibling row gets a different, incrementing run id (90855) — this
points at a tier1-verification/promotion process re-touching a stale batch identity, **not**
a fresh calendar_sweep_mca_v3 scrape as previously hypothesized. Could not confirm the exact
job: no matching `calendar-sweep-dark-counties.yml` run or `gha_dispatch_log` row exists in
the time window, and this session's DB pooler credentials
(`aws-0-us-west-2.pooler.supabase.com`, `postgres.<project_ref>` user) failed password auth,
so `cron.job` could not be listed directly.

**Next session: get the `cron.job` listing via Supabase dashboard or Management API (not the
stale pooler password) and look for an hourly/frequent tier1-promotion job touching baker —
do not re-guess a calendar_sweep_mca.py fix, the evidence now points elsewhere.**

## SQL VERIFICATION

Before (session start, `pencil_dod_evaluate_county('baker')`, loop_run_id=10589):
```
auctions_total=11
C=FAIL(63.6, matched_clean=7)  D=FAIL(63.6, matched_any=7)  E=FAIL(63.6, parcel_linked=7)
I=FAIL(54.5, card_complete=6 of 11)  J=FAIL(90.9, deal_complete=10 of 11)
```

After (immediately after this session's final delete of the recurring phantom row, live):
```
auctions_total=10   (denominator-honesty corrected: 10 genuine distinct baker cases)
C=FAIL(80.0, matched_clean=8)  D=FAIL(80.0, matched_any=8)  E=FAIL(80.0, parcel_linked=8)
I=FAIL(80.0, card_complete=8 of 10)  J=FAIL(90.0, deal_complete=9 of 10)
```

C/D/E/I moved +16.4 to +25.4 points each. Still 4/10 pass overall (A/B/F/G/H unchanged +
already passing). J's apparent -0.9 is the same denominator-honesty correction, not a
regression — the phantom row's case_number already had a bid_decisions match via
case-number lookup, so it was double-counted as complete while also inflating the
denominator. Residual gap on C/D/E/I/J is now exactly 2 case numbers (117, 132), both
confirmed genuinely source-exhausted this session with fresh, non-duplicative evidence.

Given the row count keeps fluctuating from the still-unresolved recurring-duplicate bug,
re-run `SELECT public.pencil_dod_evaluate_county('baker');` before trusting any snapshot.

## Close-out

- `gold_standard_campaign` (dispatch_id=14cbae1a-b1e3-4744-99c7-ffe69766ca29) updated:
  criteria_passed={A,B,F,G,H:true; C,D,E,I,J:false}, exit_reason='timeout'.
- 6 rows written to `gold_standard_ultraloop_audit` (5 survived=true, 1 survived=false for
  the two source-exhausted cases).
- Migration `supabase/migrations/20260811b_gold_standard_shard5_14cbae1a_baker_cdeij_fix.sql`
  is an idempotent mirror of every live write this session.

## Next-session priorities

1. Diagnose the recurring phantom-duplicate root cause via `cron.job` listing (dashboard/
   Management API — pooler psql auth is currently broken with the CLAUDE.md-documented
   password). This is now firing every 10–25 minutes and will keep suppressing C/D/E/I's
   denominator until fixed.
2. 022025CC000132CCAXMX: obtain a positive docket confirmation (paid lookup service if
   necessary, per ARM-2 budget authorization) before deciding enrich vs. exclude.
3. 022025CA000117CAAXMX: only remaining lever is defeating the OCRS Cloudflare Turnstile,
   which is out of scope for an automated session — flag to Ariel as a manual-lookup
   candidate if this case must close before its 2026-10-15 auction date.
