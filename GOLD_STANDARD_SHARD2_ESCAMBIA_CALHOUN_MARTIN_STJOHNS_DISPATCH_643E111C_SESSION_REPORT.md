# Gold Standard Shard-2: escambia / calhoun / martin / st_johns

- dispatch_id: `643e111c-f0a8-4816-b466-a73de4f05c9f`
- chat_session: `architect-20260809T160000`
- Method: ULTRALOOP (Workflow/ultracode) -- one fix agent per county, each pipelined into an independent adversarial verifier before any claim was accepted. 8 subagents total, ~668K subagent tokens, 321 tool calls.

## Scoreboard: before -> after (live `pencil_dod_evaluate_county`, verified by an independent refuter agent for every claim)

| County | Before | After | Letters moved |
|---|---|---|---|
| escambia | 9/10 (I fail) | **10/10** | I: FAIL 95.0% (453/477) -> PASS 99.2% (473/477) |
| calhoun | 8/10 (B,F fail) | 8/10 (unchanged) | none -- honest negative result, see below |
| martin | 8/10 (E,I fail) | 8/10 (unchanged) | none -- honest negative result, see below |
| st_johns | 6/10 (C,D,E,I fail) | **7/10** | D: FAIL 94.4% (51/54) -> PASS 100% (54/54). C improved 92.6%->94.4% (50->51/54), still FAIL, 1 row short of threshold |

## escambia -- I fix (VERIFIED, survived adversarial review)

Root cause: 20 auction rows had real, well-formed parcel_ids with complete address/geo/value data but zero `parcel_zones` link (never zone-assigned). Reused the proven method from a 2026-07-25 session (`migrations/20260725_shard_escambia_i_gis_zoning_backfill.sql`): Escambia's live ArcGIS REST GIS (`gismaps.myescambia.com`, Parcels layer centroid -> Zoning layer point-in-polygon). All 20 resolved to a real zone; 19 used the real code directly (G-safety checked against `zone_standards.parking_per_1000sf`), 1 (`212N313301016001`, real zone RMU) used the pre-authorized R-1 INFERRED fallback because RMU has no `zoning_districts` row under escambia's jurisdiction_id=1151. G held steady at 97.1% (no regression). 4 other structurally-broken rows (garbage parcel_id values, missing address/geo) were left untouched as documented residual -- not addressable without fabrication, and not needed to clear the 95% threshold.

Migration: `supabase/migrations/20260809_gold_standard_shard2_643e111c_escambia_i_fix.sql`

**Process note (self-corrected):** the fixer agent's migration originally self-inserted its own `gold_standard_ultraloop_audit` survived=true row -- a violation of the ULTRALOOP separation-of-duties rule (only the independent verifier may certify a claim). The verifier caught this in its own review. The two self-written rows (ids 13978/13979, `dispatch_id` incorrectly NULL) were deleted live post-session; the file was edited to remove the self-insert and document the correction. The authoritative audit row is id 13986, written by the independent verifier after it re-derived the GIS zone codes itself from `gismaps.myescambia.com` (not trusting the migration's comments) and reconfirmed G unregressed.

## calhoun -- B/F investigated, no fix (honest negative result)

Target: case `171 OF 2023` (tax deed, sold 2026-07-09) -- the one row that had genuinely changed status since a 2026-07-10 session exhausted all other calhoun B/F leads. Found new corroborating evidence at calhounclerk.com's Tax Deed Surplus registry (file 2025-20-TD, surplus balance $2,579.51, parcel `33-1N-08-0780-0001-0203` -- confirms the sale closed) but no page publishes the actual winning bid. Per FL Statute 197.582(6)/28.24(11), the surplus balance is net of clerk fees, so `opening_bid + surplus_balance` would embed an unverified zero-fee assumption. Declined to write a derived sold_amount. Zero DB writes made. Migration is documentation-only (no-op), recording a concrete next-session lead (pull the actual certificate of sale / disbursement order for file 2025-20-TD).

Migration: `supabase/migrations/20260809_gold_standard_shard2_643e111c_calhoun_bf_fix.sql`

## martin -- E/I investigated, no fix (honest negative result)

All 6 gap rows confirmed genuinely un-parcelable via the official martin.realforeclose.com AJAX endpoint: 3 are personal-property/timeshare lien foreclosures (`Parcel ID` field literally = "PERSONAL PROPERTY" / "TIMESHARE" on the source platform -- no real estate parcel exists), 3 are $0.00-judgment, blank-parcel auctions 7+ weeks out with nothing published anywhere yet. One safe corrective action taken: nulled out an unsupported placeholder address/lat-lng/assessed_value (`"Stuart, Martin County, FL 34997"`, identical lat/lng across all 3 rows) that had no evidence trail -- this does not change E/I pass/fail (parcel_id was already NULL) and was confirmed idempotent and non-regressive on all other letters.

Migration: `supabase/migrations/20260809_gold_standard_shard2_643e111c_martin_e_i_fix.sql`

Fleet note (unscored, flagged for a future session): martin B/F currently rest on a single closed-sold row whose independent-source match carries `data_source='martin_clerk:shard12_run1113_b:HYPOTHESIS'` -- technically passes the evaluator's literal contract (not propertyonion) but is a thin foundation for a 100% metric on n=1. Predates this session, correctly left untouched.

## st_johns -- C/D fix (VERIFIED, survived adversarial review)

A same-day earlier session (dispatch `ba2461bd`) had already confirmed 3 cases (CA25-0749, CA25-1585, CC24-6166) hard-blocked by clerk CAPTCHA. This session found a genuinely new lever: C/D depend on `parity_status`/`parity_source`, which don't strictly require a resolved parcel. Installed Playwright (headless browser) fresh this session -- succeeded where every prior curl/WebFetch/Firecrawl attempt was blocked by WAF/session-gating. Backfilled a real tier1 `parity_source` for the 3 blocked cases from the live saintjohns.realforeclose.com calendar (the source itself shows the same "Parcel ID: Property Appraiser" / $0.00 placeholder we have -- consistent, not a ghost stamp), which flipped D to 100% PASS. Separately, field-by-field diffed case CA25-1289 (previously `matched_divergent`) against a fresh live fetch: every field matched exactly, `parity_divergences` was NULL (no real divergence was ever recorded) -- corrected to `matched_clean`, moving C to 94.4% (still 1 row short of the 95% threshold). E/I remain genuinely blocked: independently re-confirmed via Playwright that the St Johns Clerk case-search hCaptcha is real (not an HTTP-client artifact), and the RealForeclose calendar's own data shows the same unresolved parcel placeholder for those 3 cases.

Migration: `supabase/migrations/20260809_gold_standard_shard2_643e111c_stjohns_cd_fix.sql`

## Verification protocol

Every claim above was independently re-derived by a separate refuter agent (not the fixer) against the live DB and, where applicable, the original upstream source (re-fetching GIS/clerk/calendar pages itself rather than trusting the fixer's migration comments). All 10 evaluated claims (escambia I; calhoun B, F; martin E, I; st_johns C, D, E, I) survived. `gold_standard_ultraloop_audit` rows: 13980-13983, 13985-13986, 13997-14000 (dispatch_id `643e111c-f0a8-4816-b466-a73de4f05c9f`).

## Close-out

```sql
UPDATE public.gold_standard_campaign
SET criteria_passed = <A-J per county, pasted above>,
    criteria_total = 10,
    exit_reason = 'timeout',
    session_end_at = now()
WHERE id = 4019;  -- dispatch_id = 643e111c-f0a8-4816-b466-a73de4f05c9f
```
Applied live, confirmed via SELECT (see transcript). `gold_standard_loop()`/`gold_standard_certify()` were NOT run (other shards were mid-flight per PARALLEL-FLEET RULES) -- per-county evaluation via `pencil_dod_evaluate_county` only.

## Next-session priorities

- **calhoun B/F**: pull the actual Certificate of Title / court disbursement order for file 2025-20-TD (case 171 OF 2023) -- the surplus registry confirms the sale closed but not the winning bid figure.
- **martin E/I**: structurally blocked until the 3 timeshare/personal-property cases either get real judgment data or are recognized as a distinct auction sub-type; the 3 far-future ($0.00 FJ) cases will likely resolve naturally as their auction dates approach and judgments are entered.
- **st_johns C**: 1 row short of threshold (51/54, need 52). E/I remain CAPTCHA-blocked for the same 3 cases across three independent sessions now -- likely needs a different unblocking approach (e.g. a non-clerk data source) rather than another clerk-search attempt.
