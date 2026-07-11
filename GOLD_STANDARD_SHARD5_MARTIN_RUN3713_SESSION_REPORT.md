# Gold Standard shard-5 (run3713) — martin

Session: 2026-07-11, dispatch_id `9528efeb-cb38-4b1b-9b7f-54bf36b3a98a`, chat_session
`architect-20260711T080000`.

## Dispatch overlap note

This dispatch (shard-5) assigned martin county at 7/10 (E/G/I failing). Before touching anything,
I verified live via `pencil_dod_evaluate_county('martin')` and found the county already at 8/10
(G passing) — a different shard (shard-12, commit `41d30fe1`) had already landed a fix for the
same county/letters earlier the same day. Per PARALLEL-FLEET RULES I rebased, confirmed no
conflicting in-flight work, and continued from the live state rather than duplicating shard-12's
fix.

## Method

ULTRALOOP protocol via the `Workflow` tool: fanned out 7 independent research agents (one per
zoning code still unresolved from shard-12's own residual-gap list — R-2A, A-2, R-4, B-2, HR-2,
PUD-WJ, Golden Gate Redevelopment District/Ord.1147), each followed by an independent adversarial
refuter that re-fetched sources from scratch rather than trusting the claim. All 7 findings +
verdicts logged to `gold_standard_ultraloop_audit` ids 5704–5710.

**Result: only 1 of 7 codes (PUD-WJ) produced a safely shippable, CONFIRMED value.** The other 6
remain genuinely unresolved — primary sources (Municode, elaws.us, cited PDFs) returned 403/timeout
on every attempt, same wall shard-12 hit. Per HONESTY PROTOCOL (BLANK > WRONG) and HARD GUARDRAILS
(never fabricate), no zone_standards rows were written for the unresolved 6.

**Correction to shard-12's record:** the refuter found R-2A is NOT "not found/not applicable" as a
future session might assume from an unqualified UNKNOWN tag — it's a real Category C district
(Sec. 3.405.1) almost certainly density-regulated, just with an unlocated numeric value. Similarly,
"R-4" as a literal district name does not exist in Table 3.12.1 (the real family is RM-3/RM-4/RM-5);
whether our live GIS's "R-4" zone_code is a data variant of RM-4 is unresolved. Flagged in the
migration for the next session.

## Scoreboard (pencil_dod_evaluate_county, before → after, live-verified)

| Letter | Before | After | Note |
|---|---|---|---|
| A | PASS 1 | PASS 1 | unchanged |
| B | PASS 100.0 | PASS 100.0 | unchanged |
| C | PASS 96.9 | PASS 96.9 | unchanged |
| D | PASS 96.9 | PASS 96.9 | unchanged |
| E | FAIL 90.6 (29/32) | FAIL 90.6 (29/32) | 2 fabricated parcel_ids corrected to real GIS-matched PCNs (no numerator change — both already counted non-null; correctness fix, not a metric fix) |
| F | PASS 100.0 | PASS 100.0 | unchanged |
| G | PASS 100.0 | PASS 100.0 | unchanged (PUD-WJ correctly excluded from denominator, same as PUD/PUD-R) |
| H | PASS 1.2–1.4 | PASS 0.0 | unchanged (freshness, fluctuates with scrape cadence) |
| I | **FAIL 40.6 (13/32)** | **FAIL 46.9 (15/32)** | +2 via PUD-WJ zoning link |
| J | PASS 100.0 | PASS 100.0 | unchanged |

**8/10 → 8/10** (no new letter flipped PASS, but I moved materially and the underlying data got
more honest). Full live JSON pasted below.

Before (live `pencil_dod_evaluate_county('martin')`, 2026-07-11 ~09:45Z, confirmed matches
shard-12's committed after-state exactly):
```json
{"A":{"pass":true,"metric":1,"detail":"fc=31 td=1"},"B":{"pass":true,"metric":100.0,"detail":"verified=1 closed_sold=1"},
"C":{"pass":true,"metric":96.9,"detail":"matched_clean=31"},"D":{"pass":true,"metric":96.9,"detail":"matched_any=31"},
"E":{"pass":false,"metric":90.6,"detail":"parcel_linked=29"},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=1 closed_sold=1"},
"G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},"H":{"pass":true,"metric":1.2,"detail":"hours since last_seen (SLA 48h)"},
"I":{"pass":false,"metric":40.6,"detail":"card_complete=13 of 32"},"J":{"pass":true,"metric":100.0,"detail":"deal_complete=32 (triangle + two-arm CMA + ml_score + max_bid)"},
"county":"martin","V2_LITMUS":null,"auctions_total":32}
```

After (live `pencil_dod_evaluate_county('martin')`, 2026-07-11 10:29Z):
```json
{"A":{"pass":true,"metric":1,"detail":"fc=31 td=1"},"B":{"pass":true,"metric":100.0,"detail":"verified=1 closed_sold=1"},
"C":{"pass":true,"metric":96.9,"detail":"matched_clean=31"},"D":{"pass":true,"metric":96.9,"detail":"matched_any=31"},
"E":{"pass":false,"metric":90.6,"detail":"parcel_linked=29"},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=1 closed_sold=1"},
"G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},"H":{"pass":true,"metric":0.0,"detail":"hours since last_seen (SLA 48h)"},
"I":{"pass":false,"metric":46.9,"detail":"card_complete=15 of 32"},"J":{"pass":true,"metric":100.0,"detail":"deal_complete=32 (triangle + two-arm CMA + ml_score + max_bid)"},
"county":"martin","V2_LITMUS":null,"auctions_total":32}
```

## What shipped

1. **PUD-WJ zoning district** (new `zoning_districts` row, jurisdiction 1331) — West Jensen PUD,
   CONFIRMED via a live 2024 Martin County staff report (W038-108) pdftotext-verified plus a Dec
   2023 Residential Capacity Analysis. `density_regulated=false`/`far_regulated=false` — same
   negotiated-per-development-order mechanism already established for PUD/PUD-R.
2. **2 fabricated `parcel_id` values corrected** to real, GIS-address-matched PCNs:
   - `2024-001-TD-MARTIN`: `27-38-41-008-000-01020-1` (does not exist in the county parcel layer)
     → `18-37-41-004-003-00020-0` (real, address-matched via SITUS_HOUSE_/SITUS_STREET query).
   - `24000350CAAXMX`: `04-38-41-019-010-00010-5` (does not exist) → `52-38-41-005-000-00580-8`
     (real, address-matched).
3. **2 new `parcel_zones` links** for the corrected parcels (PUD-WJ and R-2B respectively).
4. **7 rows logged to `gold_standard_ultraloop_audit`** (ids 5704–5710) — 2 survived=false
   (R-2A, R-4 findings that were refuted), 5 survived=true (including the 4 that stayed honestly
   UNKNOWN and 1 shipped).

Migration: `supabase/migrations/20260711j_gold_standard_martin_shard5_run3713_pud_wj_and_fabrication_purge.sql`

## Residual gaps (unchanged from shard-12, re-confirmed, next-session priorities)

- 6 municipality-passthrough parcels (Stuart ×5, Indiantown ×1) — need each municipality's own
  zoning ordinance, separate jurisdiction from Martin County LDR.
- R-2A, A-2, R-4, B-2, HR-2, Golden Gate Redevelopment District — all real, GIS-matched zone
  codes with no usable numeric density/FAR value located after two independent sessions'
  research attempts (Municode 403, elaws.us timeout/503, cited PDFs 403 — a consistent access
  wall, not an oversight). A-2 has a candidate value (0.2 du/acre) but it conflicts with a
  separately-cited FLU cap (0.05 du/acre) and was deliberately not inserted pending resolution.
- 2 `NO_PARCEL_MATCH` folios (distinct from the 2 fixed this session) + 2 out-of-county-mailing
  parcels (`SITUS_CITY=JUPITER`, actually unincorporated Martin per `TAX_DISTRICT_DESC=DISTRICT
  THREE MSTU` — these ARE genuinely in-county, contra a possible prior assumption, and resolve to
  real zone code `HR-2`, also unresolved per above) + 3 personal-property/timeshare liens with no
  assessable parcel at all: structural ceiling, same as before.
- Given these ceilings, martin's I metric cannot exceed roughly 22/32 (68.75%) even with every
  Martin-County-LDR code resolved, and cannot reach the 95% PASS threshold without the Stuart/
  Indiantown municipal zoning work. E is similarly capped at 90.6% (29/32) by the 3 non-real-
  property liens, structurally below the 95% threshold regardless of further linkage work.

## Verification protocol executed

- `SELECT public.pencil_dod_evaluate_county('martin')` run before and after (pasted above).
- No `gold_standard_loop()`/`gold_standard_certify()` run this session (not at 10/10; other shards
  may be mid-flight per parallel-fleet rules).
- `git pull --rebase` before push; no conflicts with concurrent shard work.
