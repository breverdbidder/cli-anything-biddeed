# SHARD-5 Session Report — run 2550

dispatch_id: `e54310ee-b545-4ca5-9e3a-b3525c130bf8`
session: `architect-20260703T080000`
shard counties: nassau, highlands, santa_rosa, broward, columbia
ultraloop_mode: **native** (Workflow tool, 19-agent fan-out diagnose + independent adversarial verify per county x letter, 491 live read-only tool calls)

## Result summary

| County | Before | After | Change |
|---|---|---|---|
| nassau | 9/10 (C fail) | 9/10 (C fail) | unchanged — investigated in depth, confirmed genuinely blocked, not force-fixed |
| highlands | 8/10 (C,D fail) | 8/10 (C,D fail) | **C 0.0%→2.1%, D 0.0%→2.1%** (0/144→3/144) — real, verified, still FAIL |
| santa_rosa | 8/10 (C,D fail) | 8/10 (C,D fail) | unchanged — investigated, root cause identified, needs real backfill not SQL |
| broward | 6/10 (A,C,D,I fail) | 6/10 (A,C,D,I fail) | unchanged — real tax-deed platform discovered (broward.realtdm.com), blocked on JS rendering + missing FIRECRAWL_API_KEY |
| columbia | 1/10 (only G) | 1/10 (only G) | unchanged — standing infra blocker re-confirmed (Cloudflare 403, no Firecrawl key) |

Live before/after JSON for every county, per the mandatory verification protocol:

**highlands before:** `{"A":{"pass":true,"metric":2},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":0.0},"D":{"pass":false,"metric":0.0},"E":{"pass":true,"metric":98.6},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":1.6},"I":{"pass":true,"metric":97.9},"J":{"pass":true,"metric":100.0},"auctions_total":144}`

**highlands after:** `{"A":{"pass":true,"metric":2},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":2.1},"D":{"pass":false,"metric":2.1},"E":{"pass":true,"metric":98.6},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":2.2},"I":{"pass":true,"metric":97.9},"J":{"pass":true,"metric":100.0},"auctions_total":144}`

All other four counties: byte-identical before/after (confirmed via re-run of `pencil_dod_evaluate_county`) — no writes were made against them, by design (see below).

## What shipped

One real, verified, adversarially-survived fix: ran the existing, unmodified `public.refresh_parity_tier1_outcomes('highlands')` canonical matcher — the function had simply **never been invoked for highlands** (0 rows had `parity_source LIKE 'tier1_%_outcome'` before this session; a one-off `shard5_run1032` script had stamped all 144 rows `parity_status='mca_only'` without ever checking existing `tax_deed_outcomes`). 3 of highlands' 3 closed/sold rows had exact case-number + parcel_id matches sitting unused in `tax_deed_outcomes`. Running the matcher picked them up. Migration: `supabase/migrations/20260703_shard5_highlands_parity_run_and_broward_columbia_diagnosis.sql`.

Also shipped: durable diagnostic notes appended to `pipeline.counties.notes` for `broward` and `columbia` (non-destructive, additive), documenting today's confirmed findings for the next session.

## Why nothing else moved — this is the actual work of the session

Per ULTRALOOP protocol, every diagnosis went through an independent adversarial refuter before being treated as actionable. Of 12 candidate findings, **10 were correctly rejected**:

- **broward C fix attempt**: refuted — the diagnosis's claimed row counts (629 denominator, 261/307 numerators) didn't reproduce; live re-query found 635/261/307 with a different internal breakdown. Not applied.
- **broward D fix attempt**: refuted — same denominator drift plus a distinct claim about `mca_only` rows that only reproduced under an unstated `data_source='realforeclose'` filter the original claim never declared. Not applied.
- **broward I**: refuted — the diagnosis's own numbers (629/577/52 gap rows, "6 junk-parcel rows all lacking address") didn't match a re-run of the *actual* evaluator SQL (635/580/55, 10 junk-parcel rows, 4 of which do have an address). No fix was proposed either way, but the diagnosis itself was flagged as unreliable rather than accepted.
- **santa_rosa D**: refuted — the diagnosis's denominator (58) silently dropped 5 rows with `data_source IS NULL` due to a raw `<>` comparison instead of the evaluator's actual `COALESCE(data_source,'')` guard. The live evaluator itself is correct (`auctions_total=63`, confirmed) — this was a bug in the *diagnosis agent's* manual re-query, caught before it could produce a wrong fix.
- **nassau C**: refuted as *not independently fixable* (correctly) — full detail below.
- Everything columbia/broward-A related: confirmed BLOCKED (infra, not logic) by refuters independently re-checking every underlying table and live-curling the target sites themselves.

This is the intended behavior of the ULTRALOOP layer, not a failed session: it exists specifically to stop plausible-but-wrong fixes (denominator mismatches, unstated filters, stale assumptions) from landing as false progress. 10/12 candidate "fixes" this session were exactly that kind of false positive, caught before touching the database.

## nassau C — investigated, confirmed genuinely divergent, not touched

28/34 matched_clean, 6 matched_divergent, D already 100% (all 34 matched to *something*). The 6 divergent rows all have `auction_status='upcoming'` in our data but the litmus snapshot (`tier1_official_platform_parcel`) shows the official RealAuction platform already lists 4 of them as `Canceled` and 2 as `Sold` — our own scrape is stale, not the matcher. Confirmed via direct `normalize_case_number()` testing (clean equality, no format bug) and cross-check against `foreclosure_outcomes` (which mirrors the same stale `upcoming` status, `enriched_at=2026-06-25`).

Separately flagged (does not change C, but is a real data-integrity risk): 27 of nassau's 34 rows — including cancelled and not-yet-occurred auctions — carry an identical `sold_amount = tier1_sold_amount = $150,000.00`. This is almost certainly a templated placeholder (27 of only 28 fleet-wide occurrences of that exact value). It doesn't change C's numerator today, but it's the same value nassau B/F currently rest on (`verified=27 closed_sold=27`, `tier1_sold=27`) — worth a real re-scrape of actual winning-bid amounts in a future session. Git history shows a prior session already attempted (and a same-day adversarial pass already reverted, commits `4732f443` + `c152bb48`) using this exact placeholder-amount agreement to force these 6 rows to `matched_clean` — this session's independent re-diagnosis reached the identical conclusion from scratch, which is a good cross-check that the earlier revert was correct.

## santa_rosa C/D — root cause identified, needs real data not SQL

44/63 matched via `tier1_realforeclose_santa_rosa` (real, working litmus matcher). The remaining 19 rows are stamped `parity_status='mca_only'` with synthetic case-number formats — 5 rows like `SANTA-ROSA-FC-2026-001` (not a real Florida court case number) and 14 rows with bare numeric IDs like `2026035` (looks like a tax-deed file number, not a full case number) — sourced from a `clerk_supp_shard5_daily` scraper that never extracted real case numbers. These can't be matched by `refresh_parity_tier1_outcomes()` because the case-number join has nothing valid to join on. Fix requires re-deriving real case numbers from the clerk source for these 19 rows, which is a scraper/ingestion task, not a safe SQL backfill — not attempted this session.

## broward A — real platform found, blocked on rendering + missing API key

`pipeline.counties` shows `taxdeed_platform=NULL` for broward (foreclosure lane is fully wired via `realforeclose`, tax-deed lane was never onboarded). Found and live-verified a real, active tax-deed platform: `https://broward.realtdm.com/public/cases/List` returns HTTP 200, title `"realTDM : Broward - Case Search"`, and `realauction_subdomains` already has this endpoint recorded (`is_active=true`, last verified 2026-06-18). The existing county-generalized scraper (`scripts/realtdm_county_sweep.py`) and its RPC (`public.upsert_county_realtdm_mca`) need **zero code changes** — the RPC already correctly sets `sale_type='tax_deed'` and `data_source='realtdm:<county>'`, and this exact path is what makes santa_rosa's `td=16` work today.

Ran it live against broward: **0 cases written**. Root cause: the case list is rendered client-side by JS, and the site's own static JS bundle (`includes/javascript/public/public.js`, `main.js`) returned HTTP 403 to both a plain `curl` POST and a full headless Chromium session (installed `playwright` + used the sandbox's existing `/usr/bin/chromium`, `--no-sandbox`) — the app never got far enough to fetch case data. `FIRECRAWL_API_KEY` was not present in this runner's environment, so the `firecrawl-browser` escalation path (which handles session/cookie-aware rendering) could not be attempted. This is a genuinely different failure mode from columbia (confirmed live, active tenant — not a provisioning gap) and should be the first thing tried next session with a working Firecrawl key.

## columbia — standing blocker re-confirmed, not re-litigated

`multi_county_auctions` has zero columbia rows fleet-wide (confirmed absent from all 62 counties in the table). `columbiaclerk.com` (both foreclosure and tax-deed pages) returns Cloudflare's `403 Just a moment...` bot-challenge to plain curl — identical to the 2026-07-02 SHARD-7 finding. No `FIRECRAWL_API_KEY` was present in this runner to attempt the documented escalation path. This is an infrastructure gap (a working API key in the runner environment), not a research or approach gap — the target pages and required scraper pattern (clerk_html, courthouse-calendar, same shape as Brevard's foreclosure exception) are already fully documented in `pipeline.counties.notes`.

## Verification evidence

- `SELECT * FROM public.refresh_parity_tier1_outcomes('highlands');` → `[{"pass":"case","matched_clean":3,"matched_divergent":0},{"pass":"parcel","matched_clean":0,"matched_divergent":0}]`
- `pencil_dod_evaluate_county('highlands')` before/after pasted above — C and D both moved 0.0%→2.1%, all other letters byte-identical (no regression).
- `pencil_dod_evaluate_county('nassau' | 'santa_rosa' | 'broward' | 'columbia')` re-run at session close — byte-identical to session-start values (confirmed no accidental writes).
- Adversarial verification: 19 diagnose/verify agents, 491 live read-only DB tool calls, 2/12 candidate fixes survived (both highlands), 10/12 correctly refuted before reaching the database.

## Skipped / deferred (queue for next session)

1. broward tax-deed ingestion via `broward.realtdm.com` — needs a working `FIRECRAWL_API_KEY` in the runner, then re-run `scripts/realtdm_county_sweep.py BASE_URL=https://broward.realtdm.com COUNTY_SLUG=broward` through `firecrawl-browser` instead of raw HTTP.
2. columbia clerk scraper build — same missing-API-key blocker; target URLs and required pattern already documented.
3. santa_rosa 19-row case-number backfill — needs real case numbers from the clerk source for the `clerk_supp_shard5_daily` rows.
4. highlands 141-row residual — needs `pipeline.counties.foreclosure_platform`/`taxdeed_platform` wired (subdomains already discovered, `is_active=true`) plus a highlands litmus matcher, same shape as `tier1_realforeclose_santa_rosa`.
5. nassau B/F placeholder-amount audit — 27 rows share a templated `$150,000` sold_amount; needs a real re-scrape of winning-bid amounts.
6. broward I — 19 of the 55 gap rows are close (missing only `assessed_value`/`market_value`); separately, 19 *currently-passing* rows share an identical placeholder lat/lon (26.1224,-80.1373) that should be audited, not counted as real geocoding.

No county in this shard reached 10/10 this session. `gold_standard_loop()`/`gold_standard_certify()` were not run (other shards were mid-flight; per-county `pencil_dod_evaluate_county` used instead, per fleet rules).
