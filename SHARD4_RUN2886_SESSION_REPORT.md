# SHARD-4 run2886 — desoto, hillsborough, wakulla, miami_dade, sumter

dispatch_id: 428137af-dc82-4531-900a-2e54917fcbf0
chat_session: architect-20260704T080000
ultraloop_mode: **native** (Workflow tool — 1 adversarial refuter for the hillsborough I claim + 1 bounded sumter B investigator, run in parallel)

## Headline

One real, verified, adversarially-survived gain this session: **hillsborough I FAIL(95.0%)→PASS(96.3%)**, with a self-caused G regression (100.0%→0.0%) caught and fixed in the same session before it could ship. Everything else in this shard was either already fixed by a concurrent SHARD-4 session earlier the same day (desoto, wakulla, miami_dade — confirmed via `git log`, not re-done), or genuinely blocked and honestly re-confirmed as blocked (sumter, hillsborough C/D).

## Pre-session discovery: two of five counties were already touched today by a concurrent session

Before doing any work, live `pencil_dod_evaluate_county` queries showed desoto C/D and miami_dade C/D at values that didn't match this dispatch's brief (which claimed desoto 10/10 and miami_dade 6/10 with C/D=94.9%). `git log` showed two commits landed on `main` at 2026-07-04T08:10:55Z and earlier the same day — `1f9bcd52` ("SHARD-4 (desoto/wakulla): ghost-success revert") and `b8729ead` ("SHARD-4 (miami_dade): C/D systemic ghost-success revert") — from a concurrent instance also dispatched on this exact shard. Live numbers matched those commits' "after" state exactly. Per PARALLEL-FLEET RULES and to avoid duplicate/conflicting work, this session did **not** re-touch desoto, wakulla, or miami_dade's already-reverted data, and instead verified stability and moved to the two genuinely open fronts: hillsborough and sumter. A separate concurrent SHARD-8/SHARD-9 session earlier today (`2c67503f`, `bf5cd982`, `eb82a5a3`) had already root-caused hillsborough C/D as accrual-blocked and attempted (and failed) sumter E twice — that work was read and not repeated.

## hillsborough — 7/10 → 8/10 (real, adversarially verified gain)

### Before
```json
{"A":true,"B":100.0,"C":77.4(FAIL),"D":77.4(FAIL),"E":97.8,"F":100.0,"G":100.0,"H":0.0,"I":95.0(FAIL,870/916),"J":97.3}
```

### I letter — root cause and fix
Confirmed the same root cause an earlier SHARD-8 session diagnosed but did not fix: 46 of 916 auction rows fail the property-card-complete check (address+geo+value+zoned-parcel), split as 20 rows with NULL `parcel_id` and 26 rows with a `parcel_id` present but absent from `parcel_zones`.

For 12 of the 26 (the ones physically inside unincorporated Hillsborough County — `MUNI='U'` on the county's own parcel layer; the other 13 are inside Tampa/Plant City/Temple Terrace, which run independent zoning authorities not covered by this GIS layer and were left unfixed):

1. Queried the live, public, unauthenticated Hillsborough County ArcGIS FeatureServer `HC_Parcels` by each row's existing `parcel_id` (used as-is — as STRAP for 22-char values, as FOLIO for 10-digit values, no id-format guessing/crosswalk) to fetch the real parcel record: address, municipality, assessed value, and polygon geometry.
2. Verified the fetched `SITE_ADDR`/`SITE_CITY` matched the stored `property_address` on every row before using it.
3. Computed each parcel's true polygon centroid and queried the live public `DSD_Viewer_Zoning_Regulatory` Zoning FeatureServer with a point-in-polygon intersection to get the real zone code covering that exact parcel today.
4. Inserted 12 `parcel_zones` rows (real, distinct zone codes: RSC-6 ×4, AS-1 ×4, PD ×2, CI ×1 — not a single repeated/decorative value) and backfilled `latitude`/`longitude`/`assessed_value` on the 6 of those rows that were also missing them, from the same authoritative parcel record.

Result: `card_complete` 870→882 of 916, **I: 95.0% FAIL → 96.3% PASS**.

### Self-caused G regression — caught and fixed same session
Adding those 12 `parcel_zones` rows with no matching `zoning_districts` row caused `v_zoning_gold_standard_kpi_v3`'s applicability CTE to default `far_applicable`/`pk1000_applicable` to `TRUE` (via `COALESCE(a.far_applicable, true)`) for all 12 — since none had a real FAR/parking standard, this cratered **G from PASS 100.0 to FAIL 0.0** live, mid-session. Fixed by inserting 4 `zoning_districts` rows using the verbatim `CATEGORY` string the same live ArcGIS layer returns for each code (not normalized or guessed) — this restores `far_applicable=false` / `pk1000_applicable=false` for all 4 (pk1000 is hardcoded false in the applicability view whenever a real district row exists), returning FAR/parking's applicable-parcel counts to 0 fleet-wide for hillsborough (same as before this migration), so `LEAST()` again ignores those two NULL sub-metrics. **G: PASS 98.7%** (density-driven; density itself dipped from an artifactual 100.0 to a genuine 98.7% because the 12 new parcels don't yet have a `max_density_du_acre` value — still well above the 95% threshold). FAR and parking-per-1000 remain structurally unevaluated for hillsborough (0 parcels ever marked applicable); this migration does not change that pre-existing fact.

### Adversarial verification (ULTRALOOP)
An independent Workflow refuter re-fetched 4 of the 12 parcels fresh from both live ArcGIS FeatureServers, independently recomputed centroids, and confirmed exact address/zone-code matches; reconciled 870+12=882 via a fresh COUNT query; confirmed no other county or `gold_standard_*`/`pencil_dod_*` table was touched. **Verdict: SURVIVED.**

The refuter also flagged two narrative issues, both checked and resolved:
- The first draft of this migration's comment described the applicability-defaulting mechanism as living in the wrong view (`v_zoning_district_applicability` instead of `v_zoning_gold_standard_kpi_v3`'s CTE) — corrected in the shipped migration comment.
- The refuter believed the 6-row lat/lng/assessed_value backfill hadn't actually executed this session, based on a stale `updated_at` timestamp (2026-07-03, pre-dating this session). Checked directly: the 6 rows' current `latitude`/`longitude`/`assessed_value` are exact matches to this session's computed values, and `multi_county_auctions` has no trigger that bumps `updated_at` on a plain `UPDATE` — the refuter's inference was a false positive, not a real problem. Logged both the refutation attempt and this counter-verification to `gold_standard_ultraloop_audit`.

### After
```json
{"A":true,"B":100.0,"C":77.4(FAIL),"D":77.4(FAIL),"E":97.8,"F":100.0,"G":98.7,"H":0.0,"I":96.3(PASS,882/916),"J":97.3}
```

### C/D — re-confirmed genuinely accrual-blocked, not touched
Re-verified live: of 916 total auctions, `redeemed=273 + cancelled=249 + completed=187 = 709` exactly equals `matched_clean`. Every already-closed hillsborough auction is already matched via genuine tier1 outcome sourcing; the entire 207-row gap to 95% is auctions with `auction_status='upcoming'` that have not sold yet. This matches the earlier SHARD-8 session's diagnosis exactly (same 709/916 split, no drift) — structurally impossible to fix today, not a matching bug. Not re-attempted.

## sumter — 3/10, unchanged (one bounded real attempt, correctly blocked)

```json
{"A":true,"B":null(FAIL),"C":0.0(FAIL),"D":0.0(FAIL),"E":90.9(FAIL),"F":null(FAIL),"G":100.0,"H":1.0,"I":0.0(FAIL),"J":0.0(FAIL)}
```

Root cause (matches two earlier sessions' diagnosis today, re-confirmed): `tax_deed_outcomes`/`foreclosure_outcomes` have zero rows for sumter — no independent outcomes source has ever landed data for this county. E's 90.9% (10/11 linked) and the qPublic-403 / FL-GIO-timeout blockers on the 4th E-linkage row were not re-attempted (two dead ends already logged today, per instructions not to repeat them).

This session made one new, different, bounded attempt at letter B specifically (verified sale outcomes, not E):
- **Found a real, verified data source**: Sumter Clerk's own published Tax Deed Sales Surplus Funds list (Google Sheets export, linked from `sumterclerk.com/surplus-funds-list`) contains exact-match rows for all 3 target tax-deed parcels (G03A014, D20G135, J34A003), confirmed via 3 independent fetch passes.
- **Correctly did not use it**: "surplus" is the excess left over *after* the winning bid pays taxes/fees/costs — it is not the sale/winning-bid amount itself, and the fee/cost stack needed to back out `sold_amount` from surplus is not known. Per BLANK > WRONG, no `sold_amount` was guessed or written.
- The two foreclosure case numbers (2024-CA-000364/367) remain blocked on a new, distinct, and specific reason: Sumter's public court-records search (Civitek OCRS, and separately `myfloridacounty.com/orisearch/60`) both require an actual JS/form-submission interaction (button click, dropdown selection, form POST) that a static-fetch tool cannot execute — not a 403, not a bad guess, a genuine tool-capability gap. Logged so the next session tries `firecrawl-browser`/`browser-use` instead of repeating a plain fetch against these same three portals.
- No database writes made for sumter this session.

## desoto, wakulla, miami_dade — verified stable, not touched (already resolved or genuinely blocked by a concurrent session today)

```json
// desoto (unchanged all session, confirmed twice)
{"A":true,"B":100.0,"C":33.3(FAIL),"D":33.3(FAIL),"E":100.0,"F":100.0,"G":100.0,"H":2.9,"I":100.0,"J":100.0}
// wakulla (unchanged all session, confirmed twice) -- honest 0 auctions after today's earlier ghost-success purge
{"A":false,"B":null(FAIL),"C":null(FAIL),"D":null(FAIL),"E":null(FAIL),"F":null(FAIL),"G":100.0,"H":null(FAIL),"I":null(FAIL),"J":null(FAIL)}
// miami_dade (unchanged all session, confirmed twice)
{"A":true,"B":100.0,"C":1.4(FAIL),"D":1.4(FAIL),"E":94.9(FAIL),"F":100.0,"G":99.3,"H":1.2,"I":94.1(FAIL),"J":100.0}
```

desoto's C/D (100%→33.3%) and miami_dade's C/D (94.9%→1.4%) collapses were both ghost-success reverts shipped by a concurrent SHARD-4 session earlier today (`1f9bcd52`, `b8729ead`) — genuine corrections, re-verified stable, not re-touched. Wakulla's `pipeline.counties` row has `foreclosure_platform=NULL`/`taxdeed_platform=NULL`/`pipeline_status='pending'` (never actually wired), but `public.realauction_subdomains` shows `wakulla.realforeclose.com` and `wakulla.realtaxdeed.com` both live (HTTP 200 on prior probe) — investigated wiring a real scrape this session, but found (a) `pipeline.counties` is not actually consumed by any live scraper — confirmed via code search, it's a non-REST-accessible ledger with zero readers, dispatch is actually driven by `realauction_subdomains` + hardcoded county lists in `.github/workflows/shard5-daily-*.yml` — and (b) this sandbox has no Firecrawl API key and plain `curl`/WebFetch get HTTP 403 from both RealAuction subdomains (anti-bot), so no real scrape could be executed and verified this session. Honestly reported as blocked rather than forced; wakulla's foreclosure row shows `parity_verdict: "no docket either side (us+PO zero all-time)"` from a prior probe, suggesting genuinely low/no online foreclosure volume for this small county regardless.

## Scoreboard (live, this session's end)

| county | before | after | letters passing |
|---|---|---|---|
| desoto | 8/10 | 8/10 | A,B,E,F,G,H,I,J |
| hillsborough | 7/10 | **8/10** | A,B,E,F,G,H,I,J |
| wakulla | 1/10 | 1/10 | G only |
| miami_dade | 6/10 | 6/10 | A,B,F,G,H,J |
| sumter | 3/10 | 3/10 | A,G,H |

## Verification evidence

- `gold_standard_ultraloop_audit`: 2 new rows this session (`county_slug='hillsborough'`, letters `I` and `G`, both `survived=true`, `dispatch_id='428137af-dc82-4531-900a-2e54917fcbf0'`).
- Migration: `supabase/migrations/20260704_shard4_hillsborough_i_zoning_backfill.sql`, applied live via Supabase Management API SQL execution (not just committed — executed against the live `mocerqjnksmhcjzxrewo` project, then re-verified via `pencil_dod_evaluate_county`).
- Did not run `public.gold_standard_loop()` or `gold_standard_certify()` — other shards were mid-flight per PARALLEL-FLEET RULES; per-county `pencil_dod_evaluate_county` evaluations only, pasted above.
- No cron jobs 109/111/115 or scoring jobs touched. No other shard's counties or rows touched (verified via `git log` before starting and spot-checked orange/clay evaluators post-change, both unaffected).

## Deviation log

- Planned to also attempt wiring wakulla's A-letter (zero auctions) this session; deviated to a bounded investigation only after confirming the assumed dispatch mechanism (`pipeline.counties`) doesn't exist in the live scrape path, and no Firecrawl credential is available in this sandbox to route around the RealAuction anti-bot block. No data was written for wakulla. Logged as a genuine, tooling-level blocker for the next session (needs either a Firecrawl-credentialed environment or `firecrawl-browser`/`browser-use`).
- Did not attempt further sumter letters (C/D/F/I/J) — all are downstream of B/E, which remain genuinely blocked; no independent work available there this session per canon's dependency chain.
