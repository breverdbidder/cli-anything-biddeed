# GOLD STANDARD shard (sarasota, nassau, bay, gulf) — 3rd firing session report
dispatch_id: `9f070f2b-162c-43a2-b7f1-bc7940c13f8f` · chat_session: `architect-20260718T160000` · 2026-07-18
mode: ULTRALOOP native (Workflow tool, 12 audit agents + 12 independent adversarial refuters, 24 total)

## This dispatch has now fired a THIRD time with an identical brief and chat_session

Two prior sessions today (16:37 UTC full ULTRALOOP fan-out, and a 16:37+ continuation) already worked this
shard's FAILING letters and shipped real fixes (bay I/G real ArcGIS backfill, a real ghost-success job
deletion in `shard5-daily-scraper.yml`). Live re-query at this session's start matched both prior reports
exactly — zero drift, nothing stale to redo. Root-caused **why** this keeps re-firing (see Part 0) instead of
blindly repeating exhausted research per the prior session's own explicit "do not re-attempt" list.

Since there was no new failing-letter lead to chase (three independent sessions have now hit the same
RealForeclose-403 / myfloridacounty.com CAPTCHA walls for gulf, and bay/nassau's remaining blockers need a
human methodology decision or credentials — see Part 2), this session instead did something **neither prior
session did**: audited the *provenance* of letters that were already reading PASS — including sarasota, which
the live scoreboard displays as `gold_standard=true` (10/10). That audit found the shard's real, high-value
work this session, described in Part 1.

## Part 0 — why this dispatch keeps firing (root-caused, not a bug)

`public.cc_redispatch_guard` (issue #12748, this exact task) has `dod_sql`:
```sql
SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications
               WHERE county_slug = ANY('{sarasota,nassau,bay,gulf}'::text[]) AND certified)
```
i.e. it only marks itself delivered once **all four counties** are certified simultaneously. `attempts=3,
max_attempts=3` — this is the last engineer attempt; `cc_redispatch_tick()`'s own source shows that once this
tick finds `dod_sql` still false, it will flip `status='blocked'` and auto-dispatch **one** architect TRIAGE
session (Tier 2) with instructions to post a `BLOCKED: ... Recommend: ... Approve?` comment for anything
needing human input. This is working as designed, not stuck — see Part 2 for the pre-emptive triage content
so that auto-dispatched session doesn't have to re-derive it.

## Part 1 — ghost-success provenance audit (the real work this session)

Fanned 12 audit agents (one per county+letter already reading PASS) + 12 independent adversarial refuters
(each re-ran the SAME queries from scratch against live production, or tried to break the claim) via the
Workflow tool. **10 of 11 completed audits were confirmed GHOST_SUCCESS** — every claim independently
reproduced byte-for-byte by a refuter working from nothing but the auditor's stated evidence. Only bay/E
survived as genuinely LEGITIMATE (7/7 live point-in-polygon re-checks against `gis.baycountyfl.gov`'s real
ArcGIS service matched DB `zone_code` exactly). Full evidence for all 11 (queries run, files read, exact row
counts) logged to `public.gold_standard_ultraloop_audit` (13 rows: 11 original + 2 post-purge re-confirmations
for nassau/gulf G — see below).

**Bonus finding, unprompted:** `gold_standard_certifications` (the actual cert-of-record table) already shows
`certified=false` for all 4 shard counties — sarasota's was `revoked_at=2026-07-12`, ten days before this
audit. The live `gold_standard_scoreboard` VIEW (what the dispatch brief's "10/10" and both prior sessions'
"CERTIFIED" language came from) was never wired to reflect that revocation, and — worse — the fabricated data
underneath was never cleaned up in the ten days since revocation. This migration fixes the data; the
scoreboard/certifications wiring gap is a separate scoring-infrastructure question flagged in Part 2, not
touched here (out of a single engineer session's authority per HARD GUARDRAILS).

Purged live via `migrations/20260718_gold_standard_shard5_sarasota_nassau_bay_gulf_ghost_success_purge.sql`
(applied via Supabase Management API, committed to main). Every deletion cites the exact fabrication signature
found (single-microsecond bulk-insert timestamps, self-labeled `source_url`/`source` strings containing
"synthetic"/"bootstrap"/"beta"/"proxy"/"default", byte-identical circular copies between an "independent"
outcomes table and the auction's own already-scraped field, or hardcoded deterministic formulas standing in
for a real ML model / CMA comps).

### Status Board (BEFORE → AFTER, live `pencil_dod_evaluate_county`)

| County | Letter | Before | After | What was purged |
|---|---|---|---|---|
| sarasota (scoped, snapshot 2026-06-24) | B | PASS 100.0 (89/89) | **FAIL 12.4** (11/89) | 165 circular outcomes rows (`sarasota_realforeclose_official`/`sarasota_realtaxdeed_official`) — bulk-inserted 2026-06-23, `winning_bid` byte-identical to the auction's own `sold_amount`, zero enrichment fields |
| sarasota | C | PASS 97.9 | **FAIL 9.6** | parity_status/parity_source on the same 165 rows was derived from the fabricated outcomes; honest side-effect regression |
| sarasota | D | PASS 97.9 | **FAIL 9.6** | same as C |
| sarasota | E | PASS 100.0 | FAIL→**PASS 95.2** (still passes, honestly) | 10 rows with literal scraped-UI-label junk (`'Property Appraiser'`/`'TIMESHARE'`/`'MULTIPLE PARCEL'`) nulled out of `parcel_id` |
| sarasota | F | PASS 100.0 | **FAIL 12.4** | same 165-row outcomes purge (F was circularly tied to B via `promote_tier1_from_outcomes()`, gated only on B already being populated) |
| sarasota | G | PASS 100.0 | **FAIL (null)** | `zoning_districts` id=10679, self-labeled `'Single Family Residential (Beta Synthetic)'`, `source_url=NULL`, plus its `zone_standards` row and 196 `parcel_zones` rows (100% of the county's zoning coverage — all in ONE of Sarasota's 3 jurisdictions, Venice/North Port had zero coverage regardless) |
| sarasota | I | PASS 100.0 (scoped)/FAIL 58.7 (live, already) | **FAIL 0.0** | direct consequence of the G+E purges (card completeness requires a zoned parcel) |
| sarasota | J | PASS 100.0 | **FAIL 0.0** | all 204 `bid_decisions` rows — `ml_score` a deterministic ARV/assessed-value formula (not a model), `cma_resale`/`cma_distressed` fixed multipliers with **zero variance** across 203 rows, both generator scripts self-comment `INFERRED — no real ML model available` |
| sarasota | pass_count | **10/10 (scoreboard said `gold_standard=true`; certifications table already said `certified=false`)** | **3/10 (A, E, H)** | — |
| nassau | G | PASS 100.0 (34 parcels, 79.4% synthetic) | PASS 100.0 (**7 parcels, 100% real**) | 27 `shard4_run581_v2/nassau_synthetic` rows (one bulk timestamp, one corrupted `parcel_id='Property Appraiser'` sentinel) + unsourced R-1 `zone_standards`/`zoning_districts` (id=7716). Remaining 7 rows independently confirmed real (zoneomics.com, Nassau 2030 Comp Plan, maps.ncpafl.com) |
| nassau | I | PASS 97.1 | **FAIL 20.6** (7/34) | direct consequence of the G purge — card completeness no longer counts parcels whose "zoning" was synthetic |
| nassau | E | PASS 100.0 (flagged, not purged) | unchanged (100.0) | see note below — insufficient evidence to justify nulling real MCA rows |
| nassau | pass_count | 8/10 | **7/10** | — |
| bay | B | PASS 100.0 (6/6) | **FAIL (null)** | 6 outcomes rows (`shard3_bay_B_fix:2026-06-26`) where 4/6 `sold_amount` values were invented via `COALESCE(opening_bid, assessed_value*0.7)` with `opening_bid` actually NULL (verified: `392719*0.7=274903.30` exact match, etc.), the other 2 synced FROM the same script's outcomes insert |
| bay | F | PASS 100.0 | **FAIL (null)** | same 6-row purge (F circularly tied to the same fabricated `sold_amount`) |
| bay | E | PASS 98.4 | unchanged (98.4, **confirmed LEGITIMATE**) | no action — 7/7 live point-in-polygon re-check against real `gis.baycountyfl.gov` ArcGIS matched DB zone_code exactly |
| bay | pass_count | 6/10 | **4/10** | — |
| gulf | G | PASS 100.0 (22 "parcels", 68% bootstrap) | PASS 100.0 (**7 parcels, 100% real**) | 15 Port St. Joe rows (4 cosmetically-distinct source tags all resolving to ONE `zone_standards` row self-labeled `source_url='shard5_bootstrap_gulf'`) + that row + its `zoning_districts` row (id=10669). Remaining 7 Wewahitchka rows independently confirmed real (cityofwewahitchka.com LDR PDF citation, confidence 0.90) |
| gulf | I | FAIL 64.3 (9/14) | **FAIL 35.7** (5/14) | direct consequence of the G purge |
| gulf | pass_count | 3/10 | **3/10 (unchanged — G stays honestly PASS)** | — |

**Net honest scoreboard, this session:** sarasota 10→**3**/10, nassau 8→**7**/10, bay 6→**4**/10, gulf 3→**3**/10
(unchanged letter count, but its G is now real). Every one of these is a *regression* in the raw PASS count —
exactly the outcome the campaign's own stated philosophy calls for ("honest FAIL > fabricated PASS"), and
matches the precedent of prior ghost-success purges in this repo's history (gadsden, jackson, levy, polk,
putnam, dixie, suwannee — this campaign has hit this exact failure mode repeatedly).

**nassau E was flagged but NOT purged**: unlike sarasota's `parcel_id` junk (literal scraped-label strings),
nassau's 34 `parcel_id` values are all non-empty and mostly plausible-format (2 have unusual-but-not-obviously-
fake formatting). The evaluator's E criterion is a pure `IS NOT NULL` check with no join to `parcel_zones` —
so purging the G-side synthetic zoning data (already done) doesn't move E's raw metric, and there wasn't
strong enough evidence of fabrication *in the MCA column itself* to justify nulling real auction rows. Flagged
as a metric-design weakness (E doesn't actually verify a real GIS link), not fixed by deleting data.

All 13 audit findings (11 original + 2 post-purge re-confirmations for nassau/gulf G, which were already
independently verified as legitimate before the purge and simply had their fabricated siblings removed) are
logged in `public.gold_standard_ultraloop_audit` for the CERTIFY GATE's evidence requirement.

## Part 2 — BLOCKED items requiring Ariel's decision (attempt 3/3 — this is the last engineer pass before auto-TRIAGE escalation)

Per the redispatch guard's own TRIAGE protocol ("If the fix requires human action... post a comment in EXACTLY
this format... then stop"), surfacing both remaining human-decision blockers now so the auto-dispatched
architect TRIAGE session (which will fire once this attempt completes, per Part 0) doesn't have to re-derive
them:

**BLOCKED: bay G's `pk1000` (parking) sub-metric, 27.3%, the sole remaining G blocker for bay.** Tried: real
ArcGIS + Municode/zoneomics research across 3 sessions confirmed Panama City's Chapter 108 parking code is
regulated **per specific use-type** (1/200sf–1/1000sf, varies retail/medical/industrial), not as a single
per-district scalar — writing one number per district would misrepresent the ordinance. Recommend: pick one
of (a) per-district modal/most-common use-type value, (b) most-restrictive-bound proxy, (c) most-permissive-
bound proxy. This is a scoring-methodology precedent that will apply fleet-wide to every county with use-type-
based parking codes, not just bay — should not be decided unilaterally by an engineer session. Approve one?

**BLOCKED: gulf B/F/H (verified outcomes, tier1 sold-amount, freshness) — structurally blocked across 3
independent sessions (2026-07-11 curl/WebFetch, 2026-07-18 16:37 Playwright, this session's re-confirmation).**
Tried: `gulf.realforeclose.com` and `gulf.realtaxdeed.com` both 403 (same RealAuction platform family as the
already-403'd foreclosure lane — confirmed via `pipeline.counties`, so there is no untried RealAuction-family
lane left). `myfloridacounty.com`'s Official Records search (the one real, working lead) is gated behind a
Cloudflare Turnstile CAPTCHA. Recommend: (a) a licensed CAPTCHA-solving integration for myfloridacounty.com
(new cost/tooling decision), or (b) a manual/paid records request to the Gulf Clerk's office. No further
automated curl/WebFetch/Playwright attempt against these same 3 sources is likely to move this — do not
re-dispatch engineer attempts at this without a genuinely new lead. Approve one, or deprioritize gulf B/F/H
given it's a 14-auction county?

## Next-session priorities

1. **If Ariel approves a bay G pk1000 methodology**: apply it, this is the highest-value remaining bay lever.
2. **Reconcile `gold_standard_scoreboard` vs `gold_standard_certifications`**: the scoreboard view currently
   has no mechanism to reflect a certification revocation — flag to whoever owns the scoring pipeline
   (`gold_standard_loop()`/`gold_standard_certify()`, both under HARD GUARDRAIL #4, not touched this session).
3. **Sweep other shards for the same fabrication signatures** found here: `promote_tier1_from_outcomes()`
   (circular B/F) is invoked by name in 7+ migration files across many counties beyond this shard; the
   `_synthetic`/`_bootstrap`/`beta`/`_default` zoning-district placeholder pattern was found in 17 different
   counties' `zoning_districts` table during this audit (Broward, Escambia, Pinellas, Orange, etc. — not just
   this shard's 4); the `shard12_main_executor.py`/`shard8_run757_gold_standard.py` J-generator pattern
   targets okaloosa/putnam/hendry/union/pasco in addition to sarasota. None of these were touched (out of
   shard scope) — flagged for their owning shards, same as this campaign's own precedent for cross-shard
   fabrication flags.
4. Do NOT re-attempt gulf B/F/H or Callaway FAR research without a genuinely new lead (both exhausted across
   3+ sessions now).
5. Do NOT re-audit nassau E's MCA rows without new evidence of literal junk values in the `parcel_id` column
   itself (checked this session, found insufficient to justify a purge).

---
dispatch_id: 9f070f2b-162c-43a2-b7f1-bc7940c13f8f (3rd firing)
