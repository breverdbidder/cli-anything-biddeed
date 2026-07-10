# SHARD-9 Session Report — hardee, duval, putnam, okaloosa, lafayette

- dispatch_id: `97977765-5157-4919-b206-11f8e29045e3`
- chat_session: `architect-20260710T000000`
- run label: run3497 (matches loop run referenced in the brief)
- date: 2026-07-10
- ultraloop_mode: `native` (Workflow tool, per CLAUDE.md ULTRALOOP PROTOCOL — user opted in with "ultracode")

## Ship-to-main status

All changes committed and pushed directly to `main`. No side branches, no PRs. All DB
mutations applied LIVE via the Supabase Management API SQL endpoint (direct psql to the
pooler failed auth this session — `SUPABASE_DB_PASSWORD` appears stale, consistent with
notes left by prior sessions; the Management API + PostgREST were used for every read/write
and are the source of truth for every number below).

## What shipped

1. **`supabase/migrations/20260710_shard9_run3497_duval_putnam_parity_cancelled_spelling_fix.sql`**
   Root-cause fix to shared function `public.refresh_parity_tier1_outcomes(p_county)`: it
   required `outcome.outcome = 'cancelled'` (double-L exact string) to classify a
   case-number-matched cancelled auction as `matched_clean`, while `multi_county_auctions
   .auction_status` was already checked against both `'cancelled'` and `'canceled'`. Real
   agreements (mca says cancelled, outcome table says canceled — same fact) were being
   mislabeled `matched_divergent`, artificially suppressing C fleet-wide for every county
   this function has ever been run against. Fixed both the case-number-match CTE and the
   parcel-fallback CTE to accept both spellings. Re-ran for all 5 shard counties.

2. **`scripts/shard9_run3059_citrus_manatee_cd_parity.py`** (reused unmodified, proven
   pattern) run against putnam for the 17 `(sale_type, auction_date)` combinations that had
   `parity_status IS NULL` — exact case-number match against a live AJAX fetch of
   putnam.realforeclose.com / putnam.realtaxdeed.com (both confirmed real, provisioned
   RealAuction tenants this session, not the dead splash). 157 rows promoted.

3. **`supabase/migrations/20260710_shard9_run3497_hardee_clerk_realdata_okaloosa_bid4assets_altsource.sql`**
   — real alternate-source discovery, applied live:
   - Hardee: `pipeline.counties` corrected to `clerk_inperson` (hardeeclerk.com, real URLs);
     inserted ONE real, independently-verified foreclosure case (25000327CAAXMX, 1841 State
     Road 66 Zolfo Springs FL, judgment $408,906.52, sale 2026-07-22) fetched live from the
     clerk's own foreclosure-sales page. No tax-deed case was found this session — A remains
     FAIL by design (needs both fc>0 and td>0).
   - Okaloosa: `pipeline.counties.notes` records a real, county-endorsed alternate platform
     (Bid4Assets — `bid4assets.com/OkaloosaFL{,Tax}/listings`, confirmed live with real 2026
     sale dates) for next session. No auction rows inserted — per-case data on Bid4Assets
     loads via a backend AJAX call not visible in a plain fetch (no Firecrawl this session);
     inserting anything without that would risk fabrication.

4. `pipeline.counties.notes` updated for all 5 counties with this session's exact findings
   (root causes, remaining gaps, what was and wasn't tried) so the next session does not
   re-derive the same investigation.

5. `gold_standard_ultraloop_audit`: 3 rows (`duval/C`, `putnam/C`, `putnam/D`), all
   `survived=true`, each backed by an independent adversarial refuter agent that re-ran the
   verification queries itself (not the agent that made the fix) — see Verification section.

## VERIFICATION PROTOCOL — before/after `pencil_dod_evaluate_county` (live, pasted verbatim)

### hardee

BEFORE (session start):
```json
{"A": {"pass": false, "detail": "fc=0 td=0", "metric": 0}, "B": {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null}, "C": {"pass": false, "detail": "matched_clean=0", "metric": null}, "D": {"pass": false, "detail": "matched_any=0", "metric": null}, "E": {"pass": false, "detail": "parcel_linked=0", "metric": null}, "F": {"pass": false, "detail": "tier1_sold=0 closed_sold=0", "metric": null}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": false, "metric": null}, "I": {"pass": false, "detail": "card_complete=0 of 0", "metric": null}, "J": {"pass": false, "detail": "deal_complete=0", "metric": null}, "county": "hardee", "auctions_total": 0}
```
(Note: this reflects the shard9 ghost-success purge that ran earlier the same day, per
`20260710_shard9_hardee_ghost_success_purge.sql` — 2 fabricated synthetic seed rows removed,
0 auctions honestly.)

AFTER (this session):
```json
{"A": {"pass": false, "detail": "fc=1 td=0", "metric": 0}, "B": {"pass": false, "metric": null}, "C": {"pass": false, "metric": 0.0}, "D": {"pass": false, "metric": 0.0}, "E": {"pass": false, "metric": 0.0}, "F": {"pass": false, "metric": null}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "detail": "hours since last_seen (SLA 48h)", "metric": 0.0}, "I": {"pass": false, "detail": "card_complete=0 of 1", "metric": 0.0}, "J": {"pass": false, "metric": 0.0}, "county": "hardee", "auctions_total": 1}
```
1/10 → 2/10 (A still FAIL by design — 1 real foreclosure case, 0 tax-deed cases found; H
flips PASS trivially since the row was just created — will need a real second data point to
stay honest at the next 48h check).

### duval

BEFORE:
```json
{"A": {"pass": true, "metric": 85}, "B": {"pass": true, "metric": 100.0}, "C": {"pass": false, "detail": "matched_clean=535", "metric": 86.3}, "D": {"pass": true, "metric": 97.6}, "E": {"pass": true, "metric": 100.0}, "F": {"pass": true, "metric": 100.0}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 3.1}, "I": {"pass": true, "metric": 96.1}, "J": {"pass": true, "metric": 99.0}, "county": "duval", "auctions_total": 620}
```
AFTER:
```json
{"A": {"pass": true, "metric": 85}, "B": {"pass": true, "metric": 100.0}, "C": {"pass": false, "detail": "matched_clean=569", "metric": 91.8}, "D": {"pass": true, "metric": 97.6}, "E": {"pass": true, "metric": 100.0}, "F": {"pass": true, "metric": 100.0}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 3.4}, "I": {"pass": true, "metric": 96.1}, "J": {"pass": true, "metric": 99.0}, "county": "duval", "auctions_total": 620}
```
8/10 → 8/10 (unchanged letter count — C moved 86.3%→91.8%, real gain, still short of the
95% threshold by 20 rows). **duval is one clean letter away from 9/10.**

### putnam

BEFORE:
```json
{"A": {"pass": true, "metric": 38}, "B": {"pass": true, "metric": 100.0}, "C": {"pass": false, "detail": "matched_clean=6", "metric": 2.5}, "D": {"pass": false, "detail": "matched_any=6", "metric": 2.5}, "E": {"pass": true, "metric": 95.8}, "F": {"pass": true, "metric": 100.0}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 2.9}, "I": {"pass": false, "detail": "card_complete=220 of 239", "metric": 92.1}, "J": {"pass": true, "metric": 98.7}, "county": "putnam", "auctions_total": 239}
```
AFTER:
```json
{"A": {"pass": true, "metric": 38}, "B": {"pass": true, "metric": 100.0}, "C": {"pass": false, "detail": "matched_clean=163", "metric": 68.2}, "D": {"pass": false, "detail": "matched_any=163", "metric": 68.2}, "E": {"pass": true, "metric": 95.8}, "F": {"pass": true, "metric": 100.0}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 3.2}, "I": {"pass": false, "detail": "card_complete=220 of 239", "metric": 92.1}, "J": {"pass": true, "metric": 98.7}, "county": "putnam", "auctions_total": 239}
```
7/10 → 7/10 (unchanged letter count — C/D jumped 2.5%→68.2%, the single biggest real
percentage-point gain this session, still short of 95%).

### okaloosa

BEFORE:
```json
{"A": {"pass": true, "metric": 1}, "B": {"pass": false, "metric": null}, "C": {"pass": false, "metric": 0.0}, "D": {"pass": false, "metric": 0.0}, "E": {"pass": false, "metric": 0.0}, "F": {"pass": false, "metric": null}, "G": {"pass": true, "metric": 100.0}, "H": {"pass": true, "metric": 12.1}, "I": {"pass": false, "detail": "card_complete=0 of 2", "metric": null}, "J": {"pass": true, "metric": 100.0}, "county": "okaloosa", "auctions_total": 2}
```
AFTER: **unchanged** (4/10 → 4/10) — no auction data written this session (see guardrail
note above re: Bid4Assets AJAX). Real, verified alternate platform documented for next
session instead of fabricating rows.

### lafayette

BEFORE / AFTER: **unchanged** (1/10 → 1/10, G only) — confirmed clean negative on a
historical archive search; no fabrication. `pipeline.counties.notes` records exactly what
was and wasn't checked so a future session with clerk-portal credentials (or a records
request) can pick this up without re-searching.

## Adversarial verification (ULTRALOOP, independent refuters — not the fixer)

Ran via `Workflow` (background task `wn9x6k5bg`, run `wf_3bfd3d02-0f9`), 5 agents, 2 phases:

| Claim | Verdict | Confidence |
|---|---|---|
| duval C spelling-fix (86.3%→91.8%) | **SURVIVED** | CONFIRMED — refuter re-fetched the live function def, re-ran the RPC, and exhaustively cross-checked all 34 newly-clean `tier1_foreclosure_outcome` rows against `foreclosure_outcomes` by hand: 34/34 genuine, 0 mismatches |
| putnam C/D ajax-harvest (2.5%→68.2%) | **SURVIVED** | CONFIRMED — refuter independently re-fetched 8 sampled rows live from putnam.realforeclose.com/realtaxdeed.com across 6 date/platform combos; all 8 genuinely appear on the live calendar under their own row's auction_date |
| Okaloosa alt-source research | found_alternate_source=true | CONFIRMED — Bid4Assets live-fetched directly, real 2026 sale dates seen |
| Hardee alt-source research | found_alternate_source=true | CONFIRMED — hardeeclerk.com live-fetched directly, real active case seen |
| Lafayette archive research | found_alternate_source=false | UNKNOWN (honest — could not access without login; not a fabricated negative) |

3 audit rows written to `gold_standard_ultraloop_audit` (duval/C, putnam/C, putnam/D, all
`survived=true`) under this dispatch_id, satisfying the SQL certify-gate precondition for
those letters (though neither county reaches 10/10 this session, so no certify was
attempted).

## Deviation log

- Per the brief's fallback instruction ("run the full loop + certify ONLY in your close-out
  if no other session is mid-flight, otherwise skip loop and report per-county
  evaluations"): I had no way to confirm other shards were idle, so I **skipped**
  `gold_standard_loop()` / `gold_standard_certify()` and relied on
  `pencil_dod_evaluate_county` per county throughout, per protocol.
- Direct `psql` to the pooler failed password auth on every host/port combination tried
  (consistent with prior sessions' notes about a stale `SUPABASE_DB_PASSWORD`). All DB
  access this session went through the Supabase Management API (`database/query`, used for
  DDL/complex SQL) and PostgREST (used for row-level reads/patches) instead. No functional
  impact — just documenting the deviation from the "run SET statement_timeout=0" psql
  guidance, which doesn't apply to the Management API path.
- Did not build the Bid4Assets scraper for okaloosa or attempt the tier1_realforeclose_duval
  24-row stale-status reconciliation for duval C, or the 76-row putnam tax-deed calendar
  discrepancy, or putnam's I/E parcel backfill — all four are real, scoped, next-session
  leads documented in `pipeline.counties.notes`, not silently dropped.

## Priority hit list for the next shard-9 session (highest leverage first)

1. **duval C** (91.8%→95% needs +20 of the 620): investigate the 24 `tier1_realforeclose_duval`
   matched_divergent rows — real stale `auction_status='upcoming'` on auction_dates now
   months in the past, no outcome record yet. Needs a genuine post-auction RESULT fetch
   (not a PropertyOnion copy — several of these rows' PO-reported dates diverge by *years*
   from our auction_date, a red flag for case-number collision on PO's side, not staleness
   on ours). `duval_outcome_harvester.py` exists in-repo but needs `REALFORECLOSE_EMAIL`/
   `REALFORECLOSE_PASSWORD` env vars not present this session.
2. **putnam C/D** (68.2%→95% needs +64 of 239): 76 tax-deed rows across 3 dates show fewer
   live-calendar items than MCA has for the same date — real discrepancy to root-cause
   (duplicate/mis-dated MCA rows vs. items pulled off the real calendar since scrape).
3. **okaloosa A/B/C/D/E/F/I**: build a Bid4Assets scraper (`bid4assets.com/OkaloosaFL{,Tax}
   /listings`) — real, live, county-endorsed platform, URLs confirmed this session.
4. **hardee A** (needs a real tax-deed case; only 1 real foreclosure case found so far).
5. **lafayette**: needs either an authenticated OCRS session or a Clerk records request —
   not solvable via unauthenticated fetch.
