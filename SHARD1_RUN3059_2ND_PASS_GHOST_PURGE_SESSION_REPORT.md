# SHARD-1 run3059 — 2nd pass session report (brevard, gilchrist, sarasota, flagler, liberty)

dispatch_id: de295275-1e36-4809-a813-97bc4a6b897c
Session: architect-20260705T000000

**DUPLICATE DISPATCH NOTICE**: this is the same dispatch_id and chat_session as
`SHARD1_RUN3059_SESSION_REPORT.md` (already merged to main, commit `0527d536`), which reached the
same "honestly blocked" conclusion for sarasota/flagler/liberty independently. This pass differs
in one respect: it caught a real, additive finding the first pass missed — gilchrist's reported
60.0% C/D was itself a ghost-success (2 of its 3 "matched" rows had no outcome-table backing) —
and corrected it live. That correction is what this report documents; the sarasota/flagler/liberty
"no fix possible" conclusion is reconfirmed, not re-derived from scratch, and is consistent with
the first pass's report.

## Method

Used the Workflow tool (ultracode) per ULTRALOOP PROTOCOL: diagnosed 4 candidate C/D parity
fixes myself from live DB evidence (gilchrist, sarasota, flagler, liberty — brevard was already
10/10, untouched), then ran ONE workflow with 4 independent parallel adversarial refuter agents
(one per county), each given the proposed fix and told to try to BREAK it using fresh,
independent Supabase REST queries and file reads — not to trust the claim. All DB access via
Supabase REST (`$SUPABASE_URL/rest/v1`). Direct psql (pooler host, 5432/6543, and
`db.mocerqjnksmhcjzxrewo.supabase.co`) all fail password auth in this sandbox with the current
`SUPABASE_DB_PASSWORD`; `supabase db push --dry-run` confirms the same; no generic
`exec_sql`/`exec` RPC is live either. All writes this session were therefore table-level
PostgREST PATCH calls (row UPDATEs only, no DDL) — consistent with the same finding recorded in
`20260703_shard1_miami_dade_matcher_reinvoke_flagler_fabrication_revert.sql` two days earlier.

## BEFORE (fresh live query, start of session)

```
brevard:   10/10 (A-J all PASS)
gilchrist:  8/10  C=60.0(3/5) D=60.0(3/5) fail, rest PASS
sarasota:   8/10  C=81.3(165/203) D=81.3(165/203) fail, rest PASS
flagler:    6/10  B=null(0/0) C=0.0(0/134) D=0.0(0/134) F=null(0/0) fail, rest PASS
liberty:    3/10  A=0(fc=1,td=0) B=null(0/0) C=0.0(0/1) D=0.0(0/1) F=null(0/0)
                  G=null I=0.0(0/1) fail; E/H/J PASS
```

## Result: all 4 proposed C/D fixes REFUTED — zero forced promotions shipped, one genuine
## ghost-success found and corrected instead

The proposed fix pattern (common to all 4 counties): rows sourced directly from the official
county RealAuction/clerk platform, with confirmed zero PropertyOnion coverage for the county,
promoted to `parity_status='matched_clean'` via a new `tier1_<county>_direct` label — the same
mechanism used by prior Leon/st_johns fixes and the 2026-07-03 flagler fix. All 4 refuters
independently found this specific application unsafe and recommended DO_NOT_SHIP:

- **Structural**: every targeted row in every county is `auction_status='upcoming'` with
  `sold_amount IS NULL` and zero rows in `tax_deed_outcomes`/`foreclosure_outcomes`. The
  canonical, currently-shipped `refresh_parity_tier1_outcomes()` function structurally excludes
  `auction_status='upcoming'` from ever producing `matched_clean` — an auction that hasn't
  happened cannot have a verified outcome. Hand-promoting these rows would reproduce, one day
  later, the identical anti-pattern already caught and reverted for miami_dade (333 rows,
  `20260704_shard4_miami_dade_cd_systemic_ghost_success_revert.sql`) and leon (31 rows,
  `20260703_shard_leon_cd_ghost_success_honesty_fix.sql`).
- **Flagler-specific**: 27 of 134 rows carry real `parity_po_id`/`po_market_value` (the
  "zero PropertyOnion coverage" premise was false); the exact `tier1_flagler_direct` label being
  restored was independently flagged as "a pure string relabel with no underlying
  independent-match logic" by a same-day fabrication-revert migration that ran *before* the fix
  being restored. Restoring it would not be "fixing a regression" — it would re-ship a
  known-suspect pattern.
- **Liberty-specific**: the county has a documented full-fabrication history (4 synthetic rows
  deleted, 11 prior audit rows had incorrectly `survived=true` on fabricated data before being
  caught in `20260702_shard1b_liberty_full_fabrication_deletion.sql`), making any further
  relabel-only promotion high-risk without a real outcome join.
- **Sarasota-specific**: this exact 81.3% gap was already independently diagnosed the day before
  (`20260704_shard14_duval_sarasota_holmes_union_ultraloop_run3025.sql`) as a genuine hard
  ceiling with no fixable gap today — the refuter reconfirmed zero drift.

No writes were made for sarasota, flagler, or liberty. All 4 refuted claims + evidence logged to
`gold_standard_ultraloop_audit` (`survived=false`) so no future session re-derives and re-attempts
the identical promotion without new evidence.

## Fix (SHIPPED): gilchrist C/D ghost-success purge, false 60.0% → honest 20.0%

While gathering evidence for the (ultimately refuted) gilchrist proposal, found that gilchrist's
*existing*, currently-reported 60.0% C/D was itself 2/3 ghost-success. Of the 3 rows counted as
`matched_clean`, only 1 (case `26-0005-TD`, `auction_status='completed'`,
`parity_source='tier1_tax_deed_outcome'`, `sold_amount=5050`) is genuinely outcome-backed. The
other 2 (`212025CA000035CAAXMX`, `212025CA000069CAAXMX`) carry
`parity_source='tier1_realforeclose_gilchrist'`, are `auction_status='upcoming'` with
`sold_amount IS NULL`, and have zero rows in either outcome table — the same signature the
canonical matcher itself would never produce and that was purged fleet-wide for miami_dade/leon.
Reverted via `supabase/migrations/20260705_shard1_gilchrist_ghost_success_purge_cd_refute_run3059.sql`
(nulled `parity_status`/`parity_source` on the 2 rows, guarded by id + source label + sold_amount
IS NULL + auction_status='upcoming' for idempotency).

```
BEFORE: C FAIL metric=60.0 [matched_clean=3 of 5]   D FAIL metric=60.0 [matched_any=3 of 5]
AFTER:  C FAIL metric=20.0 [matched_clean=1 of 5]   D FAIL metric=20.0 [matched_any=1 of 5]
```

C/D stay FAIL both before and after (no pass-count regression — gilchrist stays 8/10; both 60%
and 20% are below the 95% threshold), but the reported number is now honest. Logged to
`gold_standard_ultraloop_audit` as `survived=true`.

## Findings flagged, not remediated this session (out of scope / no safe fix available)

- **Sarasota HARD GUARDRAIL violation**: 1,111 of 1,314 `multi_county_auctions` rows for
  sarasota carry `data_source='propertyonion'` — a direct violation of "PropertyOnion = litmus
  ONLY, never ingest as a data source." The evaluator's 203-row denominator already excludes
  these (so the scoreboard is not corrupted), but this is dead contamination in production.
  Deleting 1,111 rows needs its own dedicated, reviewed session — not a side-effect of a parity
  fix.
- **Flagler B/F real path**: `flagler.realtaxdeed.com`/`flagler.realforeclose.com` now return
  HTTP 200 to a plain fetch (the 2026-07-03 "403 bot-blocked" finding is stale) but only serve
  the RealAuction login shell without authenticated credentials (none available in this
  environment) or the `FNC=UPDATE` diff endpoint. `flaglerclerk.com` (the county's own separate
  site) returns HTTP 403 (WAF/Cloudflare) to a plain fetch. A genuine fix needs either RealAuction
  credentials or a headless-render bypass (Playwright+chromium, per the working precedent in
  `scripts/shard9_union_clerk_realdata_ingest.py`) — not attempted this session (no browser
  binaries provisioned in this sandbox; real setup cost, deferred).
- **Liberty A (fc=1 td=0)**: live re-fetch of `https://libertyclerk.com/courts/tax-deeds/`
  confirms the page's own text states "There are no properties on the list of tax deeds at this
  time" — a genuine, verified data ceiling (not a scraper defect; `scripts/shard_liberty_clerk_scraper.py`
  correctly parses both pages).
- **Liberty/all-shard-counties-except-brevard G/I**: fleet-wide zoning-ingestion gap
  (`fl_counties.total_parcels=0`/`gis_endpoint=NULL` for liberty) — out of scope for a
  single-county session, per the 06-10 diagnosis already on file.

## AFTER (fresh live query, end of session)

```
brevard:   10/10 (unchanged, re-verified only, never touched)
gilchrist:  8/10  C=20.0(1/5) D=20.0(1/5) fail, rest PASS   [was 60.0/60.0 — false, now honest]
sarasota:   8/10  C=81.3(165/203) D=81.3(165/203) fail, rest PASS   [unchanged, correctly untouched]
flagler:    6/10  B=null(0/0) C=0.0(0/134) D=0.0(0/134) F=null(0/0) fail, rest PASS   [unchanged]
liberty:    3/10  A=0(fc=1,td=0) B=null(0/0) C=0.0(0/1) D=0.0(0/1) F=null(0/0)
                  G=null I=0.0(0/1) fail; E/H/J PASS   [unchanged]
```

### SQL VERIFICATION

```sql
SELECT parity_status, parity_source, sold_amount, auction_status
FROM multi_county_auctions
WHERE county = 'gilchrist'
ORDER BY case_number;
```
Result (2026-07-05T00:35Z, live): 1 row `matched_clean`/`tier1_tax_deed_outcome`/`sold_amount=5050`/
`completed`; 2 rows `mca_only`/`tier1_clerk_supp_shard5_run651`/NULL/`upcoming`; 2 rows
`NULL`/`NULL`/NULL/`upcoming` (the 2 just-reverted rows — matches
`pencil_dod_evaluate_county('gilchrist')` C=20.0%/D=20.0% exactly).

Timestamp UTC: 2026-07-05T00:35Z

## Loop closure — plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| gilchrist C/D | Promote 2 mca_only rows to matched_clean | REFUTED; instead purged 2 existing ghost-success matched_clean rows | Reversed direction — honesty correction, not a promotion |
| sarasota C/D | Promote 37/38 unmatched rows to matched_clean | REFUTED, no action | Full deviation — proposal abandoned |
| flagler B/C/D/F | Restore July 3 tier1_flagler_direct promotion | REFUTED, no action; root cause (regression bug) documented instead | Full deviation — proposal abandoned |
| liberty C/D | Promote 1 row to matched_clean | REFUTED, no action | Full deviation — proposal abandoned |
| brevard | Re-verify only (already 10/10 per fleet directive not to touch passing counties) | Re-verified, unchanged | None |

## Verification evidence

- `pencil_dod_evaluate_county` run live for all 5 counties at session start and session end
  (both pasted above).
- 4 refuter agents each independently re-ran the underlying counts, PropertyOnion-coverage
  checks, and outcome-table joins via fresh REST queries (not reused from the proposal text) —
  full evidence in workflow run `wf_bd9f5ddb-241`.
- 5 rows written to `gold_standard_ultraloop_audit` (dispatch_id
  `de295275-1e36-4809-a813-97bc4a6b897c`): 1 `survived=true` (gilchrist purge), 4
  `survived=false` (the four refuted promotions).
- Zero drift confirmed for brevard, sarasota, flagler, liberty (before/after identical except
  the one gilchrist correction).
