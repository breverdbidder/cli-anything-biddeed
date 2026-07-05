# SHARD-4 run3059 — washington, highlands, volusia, okaloosa, columbia

dispatch_id: `7b631590-6fdc-4e43-acef-8082c3c778d1`

## Environment note (read before comparing to prior sessions)

This runner had no direct Postgres connection (`SUPABASE_DB_PASSWORD` did not authenticate against either pooler host/region) and no `FIRECRAWL_API_KEY`. All live DB reads/writes this session went through the **Supabase Management API** (`https://api.supabase.com/v1/projects/{ref}/database/query`, authenticated with `SUPABASE_ACCESS_TOKEN`) rather than the `rpc/exec_sql`/`rpc/exec` PostgREST functions referenced in some older scripts in this repo — those functions do not exist in the live schema (confirmed 404). `pencil_dod_evaluate_county` reads were done via the real PostgREST RPC (`p_county` param, not `county_slug_arg`).

## washington — 10/10, re-verified unchanged, no action

```json
{"A":true(12),"B":100.0,"C":100.0,"D":100.0,"E":100.0,"F":100.0,"G":100.0,"H":0.1,"I":96.8,"J":96.8}
```
Spot-checked for the ghost-data pattern found in okaloosa (below): 0 of 31 rows have a `SYN-%` parcel_id or `INFERRED` in `property_address`. Clean, genuinely real data. Not touched.

## okaloosa — GHOST-SUCCESS PURGED: honest 6/10(fake) → 1/10 (real)

**Before** (as dispatched):
```json
{"A":true(1),"B":null(FAIL),"C":0.0(FAIL),"D":0.0(FAIL),"E":100.0,"F":null(FAIL),"G":100.0,"H":3.0,"I":100.0,"J":100.0}
```
### Root cause found
Both `multi_county_auctions` rows for okaloosa (its entire dataset) were fabricated:
- `parcel_id='SYN-OKA-FC-001'`, `property_address='Okaloosa County FC (address INFERRED SYN-OKA-FC-001), Fort Walton Beach, FL 32547'`
- `parcel_id='SYN-OKA-TD-001'`, same pattern for tax_deed

51 associated `bid_decisions` rows (`case_number` IN `OKALOOSA-FC-PAST-001`, `OKALOOSA-FC-PAST-002`, `OKALOOSA-TD-PAST-001`, x17 duplicates each) referenced these same fake case numbers — one row's `factors.cma_resale` literally read `"bootstrap INFERRED from assessed_value"`. All created 2026-06-25/26 by `pipeline_version='run338_shard28_v4'` — a prior ghost-success bootstrap session, matching the exact pattern this campaign has caught before (gilchrist, charlotte, wakulla, desoto, miami_dade).

Corroborating evidence: `pipeline.scrape_runs` shows **281 failed / 0 succeeded, all-time** for okaloosa, every failure `RuntimeError: Zero cards extracted for okaloosa ... Refusing to mark success.` The fail-loud scraper has never inserted a real row for this county — the 2 rows in production could only have been synthetic.

### Fix
Deleted both `multi_county_auctions` rows and all 51 associated `bid_decisions` rows via direct SQL against the live DB.

### After
```json
{"A":false(0),"B":null(FAIL),"C":null(FAIL),"D":null(FAIL),"E":null(FAIL),"F":null(FAIL),"G":100.0,"H":null(FAIL),"I":null(FAIL),"J":null(FAIL)}
```
Score: **1/10** (G only — a fleet-wide view artifact, not okaloosa-specific data).

### Adversarial verification (ULTRALOOP)
Independent Workflow refuter re-queried live: confirmed zero remaining references to the deleted ids/case_numbers anywhere (checked all 4 FK-linked tables — `auction_enrichment_queue`, `auction_schedule_history`, `court_case_metadata`, `po_mca_matches` — plus every other table with a `case_number`/`parcel_id` column), confirmed the 281/0 scrape_runs track record, confirmed table-scale sanity (`multi_county_auctions`=79,982, `bid_decisions`=98,341 fleet-wide — a surgical delete, not a mass-deletion incident). **Verdict: SURVIVED** (refuted=false).

### Live endpoint re-check (this session, curl)
`okaloosa.realforeclose.com` and `okaloosa.realtaxdeed.com` both now 302-redirect to the generic `realauction.com` marketing splash — the same "unprovisioned tenant" pattern already diagnosed for columbia — despite `realauction_subdomains` showing both verified live as of 2026-05-24. `okaloosa.realtdm.com/public/cases/List` does return content (HTTP 200) but is explicitly titled **"realTDM : TEST"** / **"Test Clerk"** — a sandbox tenant, not real Okaloosa data. Did not scrape it. No `FIRECRAWL_API_KEY` in this runner env to attempt an escalated fetch of the two dead subdomains. Documented in `pipeline.counties.notes` for the next session.

## highlands — 8/10, C/D root-caused; genuine 15-row actionable gap found via refutation

```json
{"A":true(2),"B":100.0,"C":2.1(FAIL),"D":2.1(FAIL),"E":98.6,"F":100.0,"G":100.0,"H":12.7,"I":97.9,"J":100.0}
```
No writes made — root-cause diagnosis only, per the honesty-protocol ban on fabricating outcome matches.

Of 144 evaluator-scope rows, 141 are unmatched. My first-pass claim was "structurally unfixable until real auctions close" — the ULTRALOOP refuter **partially refuted** this: 126/141 rows are genuinely future-dated (`auction_status='upcoming'`, `auction_date` in the future) and are correctly unfixable today. But **15/141 rows have `auction_date=2026-07-01`** — already 4 days past `current_date` — with zero linked outcome, despite 3 sibling cases from the identical date and source (`calendar_sweep_mca_v3`) already resolving cleanly to `matched_clean`/`sold`. That's a real outcome-scraper completeness gap for one already-closed auction date, not a "wait for time" situation. Logged the refined finding for the next session: backfill Highlands Clerk tax-deed outcomes for case numbers `25000610/620/622/623/628/631/634/637/641/644/650/661/663/666/667`.

## volusia — 8/10, C/D root-caused; confirmed genuinely blocked on live-scrape access

```json
{"A":true(94),"B":100.0,"C":71.0(FAIL),"D":71.8(FAIL),"E":100.0,"F":100.0,"G":100.0,"H":12.7,"I":98.4,"J":100.0}
```
No writes made. Of 373 evaluator-scope rows: 84 are `upcoming` (structural, unfixable), 21 are `auction_status='concluded'` with `parity_status IS NULL` and genuinely zero matching row in `tax_deed_outcomes`(280 volusia rows)/`foreclosure_outcomes`(249 volusia rows) — tested via exact match, alphanumeric-normalized match, leading-zero-stripped match, and bidirectional substring match, all zero. ULTRALOOP refuter independently reran all 4 strategies plus a manual fuzzy pass: **confirmed, not refuted** (refuted=false) — no real match was missed, this genuinely needs a live clerk/RealAuction outcome scrape (no Firecrawl credential this session). Even fully resolved, ceiling is 77.5% (289/373) — still short of 95% because of the 84 upcoming rows.

## columbia — 1/10, standing blocker re-confirmed, not re-attempted

```json
{"A":false(0),"B":null,"C":null,"D":null,"E":null,"F":null,"G":100.0,"H":null,"I":null,"J":null}
```
Re-curled `columbiaclerk.com/upcoming-foreclosure-sales/` this session: still HTTP 403 (Cloudflare "Just a moment" challenge), and `FIRECRAWL_API_KEY` is still absent from this runner env — the same standing infrastructure blocker three prior sessions (2026-07-02 SHARD-7, 2026-07-03 SHARD5-RUN2550) already confirmed. Did not re-attempt RealAuction dispatch (confirmed correctly unprovisioned by those same sessions). No new capability available this session to route around it; not re-attempted a 4th time with an identical tool set. No writes made.

## Cross-shard finding (NOT acted on — outside this shard's scope)

While checking for the okaloosa ghost-data pattern fleet-wide, found synthetic (`SYN-%parcel_id` / `INFERRED` marker) rows still present in counties outside this shard: **brevard (94 rows), seminole (5 rows), hardee (2 rows)**. Per PARALLEL-FLEET RULES this shard does not own those counties and did not touch them — flagging here for the owning shard/architect since brevard in particular is a flagship campaign target and 94 ghost rows there would be inflating its certified metrics the same way okaloosa's 2 rows did.

## Verification evidence

- `gold_standard_ultraloop_audit`: 13 new rows this session, `dispatch_id='7b631590-6fdc-4e43-acef-8082c3c778d1'`, `ultraloop_mode='native'` — okaloosa letters A/B/C/D/E/F/H/I/J (survived=true), highlands C/D (survived=true, refined claim), volusia C/D (survived=true).
- Okaloosa purge applied live via Supabase Management API SQL execution (not just committed — executed against `mocerqjnksmhcjzxrewo`, then re-verified via `pencil_dod_evaluate_county`).
- `pipeline.counties.notes` updated for okaloosa, highlands, volusia with this session's findings so the next session doesn't re-derive them.
- Did not run `public.gold_standard_loop()` or `gold_standard_certify()` — per PARALLEL-FLEET RULES (other shards may be mid-flight); per-county `pencil_dod_evaluate_county` evaluations only, pasted above, both before and after.
- No cron jobs 109/111/115 or scoring jobs touched. No other shard's counties touched (verified: only `okaloosa` rows in `multi_county_auctions`/`bid_decisions` were written; `pipeline.counties.notes` writes limited to this shard's 3 counties).

## Deviation log

- Planned to attempt a real C/D fix for highlands/volusia via SQL reconciliation. Deviated to diagnosis-only after confirming (and having a refuter independently confirm) that the remaining gap in both counties is either genuinely future-dated auctions or requires a live outcome scrape this sandbox cannot perform (no Firecrawl/browser credential) — fabricating a match would have been banned ghost-success. Logged concrete, bounded next-session actions instead (highlands: 15-case backfill; volusia: 21-case backfill).
- Did not attempt columbia onboarding — identical Cloudflare/Firecrawl blocker as three prior sessions, no new tooling available to route around it this session.
- Did not touch the cross-shard brevard/seminole/hardee ghost-data finding — out of this shard's assigned scope.
