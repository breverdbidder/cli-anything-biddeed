# Gold Standard Shard-4: bradford / calhoun / union — dispatch 8389b490

Session: architect-20260813T080000. ULTRALOOP mode (native Workflow fan-out: 4 diagnose/fix agents + 4 adversarial refuters, all claims survived).

## Scoreboard before → after (live `pencil_dod_evaluate_county`)

| County | Before | After | Letters moved |
|---|---|---|---|
| bradford | 8/10 | 8/10 | none — B/F reconfirmed structurally blocked (9th session) |
| calhoun | 7/10 | **9/10** | D fixed (87.5→100), B fixed (null→100), F fixed (null→100) |
| union | 6/10 | 6/10 | none — C/D case genuinely pulled from clerk calendar; B/F already fresh from 2026-08-09 |

## calhoun — B, F: PASS (was FAIL)

Root cause: case `171 OF 2023` (tax deed, parcel `33-1N-08-0780-0001-0203`) was tier1-confirmed `sold` but had no dollar amount captured anywhere, so it never entered the `closed_sold` denominator — calhoun's B/F were mathematically unsatisfiable with 0/0.

Found an independent (non-PropertyOnion) clerk source: `calhounclerk.com` WP REST `taxdeedoverbids` feed, entry id=3553, parcel-matched exactly, `balance="2579.51"` (statutory surplus owed to former titleholder Bama Lee Cooper — **not** the auction winner, `winning_bidder` left NULL). No source (clerk CPT, media attachments, Beacon/Schneider appraiser — 403 to non-interactive access) states a winning bid directly.

Applied FL Stat 197.582 identity: `winning_bid = opening_bid + surplus = 6472.01 + 2579.51 = 9051.52`. Labeled **INFERRED**, not VERIFIED — both inputs are independently real, the relationship is statutory, but no single source states the total. Written to `tax_deed_outcomes` (`data_source='calhoun_clerk_taxdeedoverbids:derived_opening_plus_surplus_20260813'`) and `multi_county_auctions.sold_amount`/`tier1_sold_amount`.

Migration: `supabase/migrations/20260813_gold_standard_shard4_calhoun_bf_171of2023_sale_amount.sql`

## calhoun — D: PASS (was FAIL, regressed from a prior fix)

A 2026-08-11 session had already fixed this (case `546 OF 2024` → `CLERK_SSOT_CANCELLED`) but it silently regressed by 2026-08-12 because `scripts/clerk_ssot/run_parity.py`'s phantom-flagging branch had no guard against clobbering a manually-reconciled `CLERK_SSOT_CANCELLED` row — unlike its sibling clean-match branch, which already has that guard. Since the case is genuinely absent from calhoun's daily clerk feed, it would have re-regressed every cron run (`.github/workflows/clerk-ssot-parity.yml`, daily) forever.

Fix: one-line guard added (`AND parity_status IS DISTINCT FROM 'CLERK_SSOT_CANCELLED'`), mirroring the existing pattern. This is a **shared script covering ~27 counties** — refuter independently confirmed 101 `CLERK_SSOT_CANCELLED` rows across 10 counties are now protected by this fix, not just calhoun's.

Migration: `supabase/migrations/20260813_gold_standard_shard4_calhoun_d_phantom_guard_code_fix.sql`

C (matched_clean, 87.5%) remains correctly FAIL and unchanged — canon-blocked per the 2026-08-11 diagnosis (case 546 OF 2024 has no legitimate `matched_clean` value; only `matched_any` accepts `CLERK_SSOT_CANCELLED`).

## union — C, D: still FAIL (confirmed genuine, not a scraper bug)

Case `63-2025-CA-0053` (foreclosure, scheduled to sell **today** 2026-08-13) is flagged `PHANTOM_NOT_ON_CLERK`. Investigated whether this was a parser bug given the same-day sale date: live Playwright re-scrape of unionclerk.com found exactly one card on the page (`63-2024-CA-0047`), zero occurrences of the case number anywhere in the full rendered HTML, no pagination/date-window bug. Most consistent with a late cancellation/continuance in the days before sale. Left `PHANTOM_NOT_ON_CLERK` — forcing a match would be fabrication.

Migration (notes only, no data change): `supabase/migrations/20260813_gold_standard_shard4_union_cd_investigation.sql`

B/F not re-litigated — independently reconfirmed structurally blocked 2026-08-09 (`union_bf_adversarial_refuter_audit.sql`), still within the certification freshness window.

## bradford — B, F: still FAIL (9th consecutive reconfirm)

Case `25000457CAAXMX` (parcel `00273-0-01000`) sale date is 28 days past with zero clerk-published outcome. This session ran 3 narrowly-targeted case-specific checks (Bradford Property Appraiser/Schneider qPublic, bradfordclerk.com + subdomain guesses, bctelegraph.com legal notices including 2 new issues since the 7th session) beyond the 8 prior generic sweeps — all still Cloudflare/Turnstile-blocked or silent. No fabrication; fresh audit rows inserted to keep the 7-day certification-freshness window current.

Migration (reconnaissance log only): `supabase/migrations/20260813_gold_standard_bradford_bf_9th_reconfirm_case_specific_8389b490.sql`

## ULTRALOOP audit trail

12 `gold_standard_ultraloop_audit` rows inserted this session (dispatch `8389b490-c112-47cd-9fb8-c794250153c3`), all `survived=true`: calhoun B/F/C/D (4 fixer + verify pairs), union C/D + 2 meta-claims, bradford B/F. Every fix claim was independently re-derived by a refuter agent using different query paths/tools than the claimant — none were refuted.

## Close-out

```sql
SELECT public.pencil_dod_evaluate_county('bradford');  -- 8/10, B/F fail (structural)
SELECT public.pencil_dod_evaluate_county('calhoun');   -- 9/10, C fail (structural)
SELECT public.pencil_dod_evaluate_county('union');     -- 6/10, B/C/D/F fail (structural)
```

calhoun is now the closest of the three to certification — only C (87.5%, structurally capped) remains, and canon offers no legitimate path to move it further without a new auction diluting the denominator.
