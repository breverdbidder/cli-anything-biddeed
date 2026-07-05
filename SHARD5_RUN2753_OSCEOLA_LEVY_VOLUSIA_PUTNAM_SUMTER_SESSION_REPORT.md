# SHARD-5 Session Report — run 2753

dispatch_id: `e815c313-9d14-4a45-b961-f4979680beea`
session: `architect-20260703T160000`
shard counties: osceola, levy, volusia, putnam, sumter
ultraloop_mode: **native** (Workflow tool, 2-agent adversarial verify fan-out before any write, plus one dedicated web-research agent for the sumter E gap; ~40 additional live read-only SQL queries run directly against the Supabase Management API by the main session)

## Honesty checkpoint — the dispatch brief's numbers were stale

The brief's per-county tables (loop run 2753) do **not** match live state. Live `pencil_dod_evaluate_county` calls at session start showed:

| County | Brief said | Live at session start |
|---|---|---|
| osceola | 10/10 | **5/10** — B, C, D, F, I fail |
| levy | 8/10 (C,D fail 0%) | 8/10 (C 87.5%, D 87.5%) |
| volusia | 8/10 (C 91.4%, D 92.4%) | 8/10 (C 71.0%, D 71.8%) — worse, denominator grew 290→373 |
| putnam | 6/10 | 7/10 (E now passes, was 95.0%→96.2%) |
| sumter | 1/10 | 2/10 (A now passes: fc=4 td=7) |

Root cause for osceola: `supabase/migrations/20260704_shard9_osceola_ghost_success_revert.sql` (previous session, 2026-07-04) found osceola's reported 10/10 was **entirely fabricated** — a single static lat/long/$145K placeholder copied across all 132 rows, 3 synthetic foreclosure rows, and a 108-row `tax_deed_outcomes` batch with `winning_bid = 1.5x opening_bid` on every row and zero `source_url`/`winner_name`. That session correctly reverted it. The dispatch brief for this run still carries the pre-revert numbers. Treat every stale-brief number in this campaign as unverified until re-queried live — this is now the second shard-5 run in a row where the brief lagged real state (see run 2550's report).

## Result summary

| County | Before (session start) | After | Change |
|---|---|---|---|
| osceola | 5/10 (B,C,D,F,I fail) | 5/10 (unchanged) | investigated in depth; genuinely blocked, not force-fixed |
| levy | 8/10 (C,D fail) | 8/10 (unchanged) | C/D gap is 4 future-dated auctions (2026-07-07 through 2026-08-10) with no outcome yet to match — structurally correct, not a bug |
| volusia | 8/10 (C,D fail) | 8/10 (unchanged) | C/D gap is 105 rows, 103 of which are genuinely upcoming/unsold; the 1 candidate "real match" a refuter found was itself backed by a fabricated placeholder batch (see below) — correctly NOT applied |
| putnam | 7/10 (C,D,I fail) | 7/10 (unchanged metric; data-integrity fixed) | **shipped**: reverted a 217-row ghost-success (`parity_source='clerk_official_court_format'`), 0 metric movement by design (evaluator already excluded these), but removes a false "verified" stamp from the base table |
| sumter | 2/10 (only A,G,H pass) | 2/10 (unchanged) | E gap (1 row missing parcel_id) researched via live web/browser automation against Sumter's qPublic property search — blocked by Cloudflare bot-detection, no parcel ID found, correctly NOT guessed |

Live before/after JSON, mandatory verification protocol:

**osceola:** `{"A":{"pass":true,"metric":5},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":85.8},"D":{"pass":false,"metric":85.8},"E":{"pass":true,"metric":96.3},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":14.2},"I":{"pass":false,"metric":0},"J":{"pass":true,"metric":96.3},"auctions_total":134}` — identical before and after.

**levy:** `{"A":{"pass":true,"metric":3},"B":{"pass":true,"metric":100},"C":{"pass":false,"metric":87.5},"D":{"pass":false,"metric":87.5},"E":{"pass":true,"metric":100},"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":23},"I":{"pass":true,"metric":100},"J":{"pass":true,"metric":100},"auctions_total":32}` — identical before and after.

**volusia:** `{"A":{"pass":true,"metric":94},"B":{"pass":true,"metric":100},"C":{"pass":false,"metric":71},"D":{"pass":false,"metric":71.8},"E":{"pass":true,"metric":100},"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":14.2},"I":{"pass":true,"metric":98.4},"J":{"pass":true,"metric":100},"auctions_total":373}` — identical before and after.

**putnam before:** `{"A":{"pass":true,"metric":37},"B":{"pass":true,"metric":100},"C":{"pass":false,"metric":2.5},"D":{"pass":false,"metric":2.5},"E":{"pass":true,"metric":96.2},"F":{"pass":true,"metric":100},"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":13},"I":{"pass":false,"metric":92.4},"J":{"pass":true,"metric":99.2},"auctions_total":238}`
**putnam after:** identical JSON, by design — see below for what actually changed (base-table integrity, not the evaluator-visible metric).

**sumter:** `{"A":{"pass":true,"metric":4},"B":{"pass":false,"metric":null},"C":{"pass":false,"metric":0},"D":{"pass":false,"metric":0},"E":{"pass":false,"metric":90.9},"F":{"pass":false,"metric":null},"G":{"pass":true,"metric":100},"H":{"pass":true,"metric":13.1},"I":{"pass":false,"metric":0},"J":{"pass":false,"metric":0},"auctions_total":11}` — identical before and after.

## What shipped

**Putnam C/D ghost-success revert** — `supabase/migrations/20260705_shard5_run2753_putnam_cd_ghost_success_revert.sql`, applied live via Supabase Management API SQL.

Diagnosis: putnam had 217 `multi_county_auctions` rows stamped `parity_status='matched_clean'`, `parity_source='clerk_official_court_format'`, `parity_confidence=0.85` (214 rows) or `0.80` (3 rows). Root migration `migrations/20260619_shard2_putnam_cd_parity.sql` set this purely by excluding `PO-`/`PO_`-prefixed case numbers — **no join, no cross-check against any outcome table.**

Per ULTRALOOP protocol, ran this claim through an independent adversarial-verify Workflow (`wf_67ae8f8a-f30`) before touching anything. The refuter ran its own live queries and returned **SURVIVES**: confirmed all 217 rows have `sold_amount IS NULL`, confirmed 0 of 217 have any backing in `tax_deed_outcomes`/`foreclosure_outcomes` by case_number, confirmed the proposed `WHERE` clause is scoped correctly and cannot touch the 6 genuinely tier1-backed putnam rows. One correction from the refuter: the "217 rows" claim conflated a 3-row detail (confidence 0.80 vs 0.85) that didn't change the verdict.

Applied the revert. Metric unchanged by design — `pencil_dod_evaluate_county`'s C/D filter already requires `parity_source LIKE 'tier1%'`, so this fabricated batch was never counted toward the live score. This was a base-table data-integrity fix (removing a false "verified" stamp before it can be picked up by any future join, dashboard, or certification path that doesn't share the evaluator's tier1 filter), not a metric-moving fix. Logged to `honesty_violations` (severity CRITICAL) and `gold_standard_ultraloop_audit` (both C and D, `survived=false` on the original inflated claim).

## What was investigated and correctly NOT shipped

- **Volusia C/D "real match" candidate** — proposed linking 2 rows with apparent real outcome-table backing. The adversarial refuter (same Workflow run) found only **1** genuine case-number match existed (not 2 — the claim's count was wrong), and that single match was backed by `tax_deed_outcomes`/`foreclosure_outcomes` rows tagged `data_source IN ('volusia_realtaxdeed_sold','volusia_realforeclose_sold')` — a fabricated placeholder batch: 51 of 84 and 43 of 177 rows in those two sources carry `winning_bid='0.00'` with `outcome='sold'`, zero `source_url` on any row ever, and future auction dates already marked sold. **Not applied.** This is the ULTRALOOP protocol working as designed — a plausible-looking fix that would have been a second ghost-success was caught before it shipped.

  **Follow-up flag for next session** (not in scope to fix here, logging per boundaries protocol): I separately confirmed volusia's currently-*passing* B/F (100%, 175 verified/closed) do **not** rest on this contaminated `_sold` batch — every one of the 175 counted rows also has an independent match via the legitimate `_official` sibling source (`volusia_realtaxdeed_official` / `volusia_realforeclose_official`, 0 zero-bid rows, varied real bid amounts). B/F are genuinely backed. But the 94-row `_sold` contaminated batch itself is still live in the base tables and should be reverted or investigated by whichever session owns volusia's outcome-ingestion pipeline, since it is a ghost-success signature (identical to the osceola/putnam fabrication class already found and purged repeatedly in this campaign) sitting unaddressed.

- **Osceola C/D 85.8% gap (19 of 134 rows)** — broke the gap down: 13 rows never had any parity check run (`parity_status`/`parity_source` both NULL); 6 rows have `parity_status='matched_clean'` but `parity_source IS NULL` (stamped by something that didn't tag its source, dated 2026-07-04 06:03:09, immediately after the ghost-success revert — likely a side effect of that migration's bulk timestamp update, not a real match: osceola's `tax_deed_outcomes`/`foreclosure_outcomes` are confirmed 0 rows county-wide, so none of these 6 can have real backing). Ran the canonical `public.refresh_parity_tier1_outcomes('osceola')` matcher (the same safe, join-only function that fixed highlands' C/D in run 2550) — returned 0/0 on both the case-number and parcel passes, confirming there is nothing to match against until osceola's B/F outcome data gets real scraping. Not force-fixed.

- **Osceola I=0% (card_complete=0 of 134)** — root cause: **zero** of the 134 rows have latitude/longitude (real or PropertyOnion-fallback), even though 129 have real street addresses and 129 have real 12-digit parcel folio numbers (e.g. `262630061300`, `4180 HIGH PLAINS LN, KISSIMMEE, FL- 34744`, `assessed_value=309103.0` — genuine county-appraiser-sourced data, not placeholder). This is a legitimate geocoding gap. Attempted a real fix via the FL GIO Statewide Cadastral FeatureServer (the established ZoneWise pattern): exact `PARCEL_ID` equality queries against `services9.arcgis.com/.../Florida_Statewide_Cadastral/FeatureServer/0` returned zero features for osceola's parcel_id format, and broader `LIKE` queries timed out (this FeatureServer is documented elsewhere in the repo as slow/timeout-prone on broad queries). Did not have time to resolve the field-format mismatch safely this session — flagging as a concrete, scoped, real next-session task rather than attempting a rushed geocode that could introduce bad coordinates.

- **Sumter E gap (1 row, case 2025-CA-000255, owner "Wildwood Phase One LLC")** — dispatched a dedicated web-research agent to find the real parcel ID via the Sumter County Property Appraiser (qPublic/Schneider Corp). Confirmed blocked: direct fetch returns HTTP 403, and a live Playwright browser-automation attempt against qPublic's own search form was explicitly blocked by Cloudflare WAF ("Sorry, you have been blocked"). No parcel ID was guessed. Per HONESTY PROTOCOL (BLANK > WRONG), this is correctly reported as unresolved rather than fabricated.

- **Levy C/D 87.5% gap (4 of 32 rows)** — all 4 are future-dated auctions (2026-07-07, 2026-07-14, 2026-07-21, 2026-08-10). There is no outcome to match yet; this is a structural ceiling, not a bug. Ran the canonical matcher (0/0, confirming no hidden backlog). Will self-resolve as these dates pass and real scrapes capture outcomes.

## Live guardrail-violation finding (flagging, not fixing — outside this shard's scope)

Osceola currently has **516 live `multi_county_auctions` rows with `data_source='propertyonion'`** — the exact same count (516) that `supabase/migrations/20260702_shard12_osceola_propertyonion_contamination_cleanup.sql` documented deleting three days ago. Either that delete never actually landed in production, or a recurring ingestion job has re-inserted the identical volume since. This is a HARD GUARDRAIL violation ("PropertyOnion = litmus ONLY. Never ingest as a data source") that is evidently *recurring*, not a one-time incident. These rows do not affect any current pencil_dod metric (the evaluator excludes `data_source='propertyonion'` fleet-wide), so it was left untouched rather than re-deleted blind — re-deleting without finding the recurring ingestion source would just mask the real bug again. Flagging for whichever session owns the osceola/Duval-style PropertyOnion ingestion pipeline to find and stop the source.

## Verification protocol executed

- `pencil_dod_evaluate_county` run live before and after for all 5 counties (pasted above).
- `public.refresh_parity_tier1_outcomes(<county>)` run live for all 5 counties as a confirmatory, safe, idempotent, non-fabricating diagnostic (results: osceola 0/0, levy 0/0, volusia 265/3 unchanged, putnam 6/0 unchanged, sumter 0/0) — rules out "matcher bug" as an explanation for every remaining C/D gap in this shard except where already independently confirmed.
- Two ULTRALOOP adversarial-verify rows logged to `gold_standard_ultraloop_audit` for putnam C and D (`survived=false` on the refuted ghost-success claim being investigated, i.e. correctly flagging the original fabrication).
- One `honesty_violations` row logged (CRITICAL) for the putnam ghost-success finding.
- Did **not** run `gold_standard_loop()` or `gold_standard_certify()` per PARALLEL-FLEET RULES (other shards' sessions may be mid-flight); reported per-county `pencil_dod_evaluate_county` only, as instructed.

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Re-verify live state for all 5 counties | yes | done | brief numbers were stale for 4 of 5 counties (see checkpoint above) |
| Fix putnam C/D | attempt real backfill | shipped data-integrity revert of a ghost-success; real C/D backfill still needs external clerk/tax-deed scraping (only 9 real outcome rows exist for 238 auctions) | scope narrowed after diagnosis showed the "217 matched" state was fake, not a quick-win |
| Fix osceola B/F/I | attempt | correctly identified all three as needing real external scraping/geocoding no tool in this sandbox could complete safely this session; not forced | deferred, documented |
| Fix levy/volusia C/D | attempt | confirmed structurally blocked (upcoming auctions, no outcome yet); 1 near-miss volusia fix caught and rejected by adversarial verify | deferred, documented |
| Fix sumter E | attempt | researched via live web agent, blocked by Cloudflare, not force-guessed | deferred, documented |

No county reached 10/10 this session. Given the demonstrated fabrication risk already found twice in osceola and once in putnam within this exact campaign, the honest outcome for this shard is: one verified data-integrity fix shipped, five real remaining gaps precisely diagnosed and correctly left unforced, and one live recurring guardrail violation surfaced for the next session.
