# GOLD STANDARD shard-14 (bay) — dispatch e8926b0a-9997-471b-82f3-00a092c1eb19 — 2nd firing (ULTRALOOP refresh)

Session: architect-20260731T080000, re-fired. Assigned shard: bay only.

## Finding: this dispatch's work was already shipped before this firing started

Commit `8e1607ac` (08:32Z) already fixed C/D/I live on this exact dispatch_id — bay was
10/10 (`pencil_dod_evaluate_county`) before this session did anything. Re-verified
independently, twice, at session start: scoreboard confirmed `pass_count=10,
gold_standard=true` as of loop run 7658 (09:30Z). No county-data fix work remained.

## What this firing actually did: ULTRALOOP adversarial re-verification + audit-freshness refresh

The prior firing's own session report flagged an open risk: "the other 7 letters'
most recent survived=true rows... should be checked for staleness before
certification is claimed." Those rows (A,B,C,D,E,F,G,H,I,J) were all dated
2026-07-25 — 6 days old, about to age past the certify gate's 7-day window before
the second of two consecutive 10/10 daily 07:30Z runs could land. Ran a native
Workflow fan-out: 7 independent adversarial verifier agents (A,B,E,F,G,H,J — C/D/I
already had fresh 07-31 evidence from the 1st firing), each required to
independently re-derive its letter's metric from underlying tables via live REST
queries, not by re-trusting the RPC.

## Result: 5 letters SURVIVED, 2 letters REFUTED — bay is NOT actually clean 10/10

### Survived (fresh audit rows inserted: ids 11704-11708)
- **A** (64: fc=64/td=127) — independently re-tallied via REST count headers + full-row fetch, both product types fresh (last_seen today) and multi-source.
- **B** (100.0%, verified=44/closed=44) — confirmed zero double-count across tax_deed_outcomes/foreclosure_outcomes, zero promote-sourced leakage, exact 44/44 case_number set match. Ratio inside the 95-105% evaluator-v6 pass band (the anomaly class that blocked brevard/duval certification does not apply here — migration `20260702_shard3_pencil_dod_b_scope_fix.sql` structurally caps this numerator at the denominator).
- **E** (98.4%, 188/191) — 188 distinct, real-format parcel_ids, 3 genuine NULL gaps (23001239CA, 25000412CA, 26000161CA), fresh as of today.
- **F** (100.0%, 44/44) — same 44-case set as B, all non-promote sourced, real sold amounts.
- **G** (97.0%, density=98.8/far=97.6/pk1000=97.0) — independently recomputed from `v_zoning_gold_standard_kpi_v3`; confirmed the I-letter parcel_zones alias insert from the 1st firing did NOT create double-counting.

### REFUTED — two fresh false-positive findings, logged as survived=false (ids 11711, 11712)

**H (freshness, RPC reports PASS 0.1h):** `last_seen_at` is identical across all 191
bay rows (and identically mass-touched on a brevard comparison sample) — a
fleet-wide housekeeping bulk-update, not a per-record scrape event. The real
scraper-activity columns (`scrape_timestamp`/`created_at`) cap at
2026-07-29T21:13:51Z = **36.65 hours** old, not 0.1h. Still under the 48h SLA
today on the real timestamp, so H likely still resolves PASS on honest data — but
the RPC's specific reported metric is fabricated by an unrelated bulk touch and
cannot be cited as live-scrape proof. This is an evaluator-formula fragility
(`GREATEST(last_seen_at, scraped_at, scrape_timestamp, last_changed_at)` per
migration `20260626_shard1_pencil_dod_h_greatest_fix.sql`) that affects the fleet,
not a bay-specific data problem — flagged for architect review, not unilaterally
patched in this bay-only session.

**J (Shapira deal thesis, RPC reports PASS 100.0%, deal_complete=191):
CONFIRMED GHOST-SUCCESS.** The RPC only checks non-null + key-presence on
`bid_decisions.factors`, which 191/191 pass technically. Direct row inspection
found 55 of 191 (28.8%) unique bay case_numbers share a **byte-for-byte identical
boilerplate** factors payload (arv=$50,000, max_bid=$0, ml_score=0.38, generic
distress/CMA notes) stamped across genuinely distinct tax_deed properties whose
real `assessed_value` ranges $2,247–$115,894. Broader dedup: 84/191 (44%) share a
factors signature with ≥1 other row; `distress_location`/`distress_property`/
`distress_owner` have only 8/7/6 distinct values across 203 checked rows —
category-level constants, not per-property analysis. **Additional bug found:**
`case_number` is not unique across counties (e.g. `2026-0077TD` collides across
Bay/Jacksonville/Freeport rows), an ambiguous join key that risks cross-county
contamination in this and any other case_number-joined criterion fleet-wide. This
matches the known, separately-tracked fleet-wide J ghost-fill investigation — not
fixed in this bay-only session (out of scope: shared generator, not bay data).

## Certify-gate integrity action taken

The certify gate (`migrations/20260720_architect_triage_12866_certify_tiebreak_fix.sql`)
takes the **most recent** `gold_standard_ultraloop_audit` row per (county, letter)
within a 7-day window (`DISTINCT ON (county_slug, letter) ... ORDER BY created_at
DESC`). The 2026-07-25 survived=true rows for H and J were still inside that
window and, left alone, would have been picked up by any future certify run as
valid evidence — silently masking today's confirmed ghost-success on J. Inserted
fresh `survived=false` rows for both (ids 11711, 11712) with full refuter evidence
so the certify gate sees the correct, current finding instead of stale evidence.

**Net effect: bay is genuinely audit-current on 8/10 letters (A,B,C,D,E,F,G,I) and
correctly BLOCKED from certify eligibility on H and J as of this session**, despite
`gold_standard_scoreboard` still showing `pass_count=10` (the scoreboard reflects
the raw evaluator metric, not adversarial audit status — this is expected,
by-design divergence between the two, not a contradiction).

## No county-data fixes attempted this firing

This session found no genuine bay-data gap to fix — the 1st firing's C/D/I fix
already closed the only real gaps. The J ghost-fill and H evaluator-formula
issues are both shared/fleet-wide concerns (generator logic, scoring formula) that
a single-county shard session should flag, not unilaterally patch, per
PARALLEL-FLEET RULES and the existing dedicated fleet-wide J ghost-fill
investigation track.

## Recommended next steps (for architect / next J-focused session)
1. Investigate the J boilerplate generator fleet-wide — the 55-row identical
   tax_deed signature strongly suggests a template fallback path is firing
   instead of the real Shapira/CMA pipeline for a specific case subtype.
   `pasco-f-audit-and-j-scope` skill already exists for exactly this.
2. Fix the `case_number` cross-county ambiguity — any RPC or view joining
   `bid_decisions` (or similar) by `case_number` alone without a `county` filter
   is at risk of silent cross-county contamination fleet-wide, not just for J.
3. Review whether the H evaluator's `GREATEST()` freshness formula should exclude
   or weight down non-scrape bulk-touch columns, since a housekeeping job can
   currently make any county's H metric report near-zero regardless of real
   scrape recency.

## Verification protocol
```
SELECT public.pencil_dod_evaluate_county('bay');  -- raw evaluator: 10/10 (unchanged)
SELECT * FROM gold_standard_ultraloop_audit WHERE county_slug='bay'
  AND created_at > now() - interval '1 day' ORDER BY letter;  -- fresh audit: 8 survived, 2 refuted (H, J)
```
`gold_standard_loop()`/`gold_standard_certify()` intentionally not run this session
(PARALLEL-FLEET RULES, other shards may be mid-flight).

## Cost
1 Workflow (7 verifier agents + 1 synthesis agent, 8 agents total, ~640s), 2 direct
SQL inserts (H/J refutation rows) by the orchestrating session. No schema changes,
no scripts written, no paid API spend.
