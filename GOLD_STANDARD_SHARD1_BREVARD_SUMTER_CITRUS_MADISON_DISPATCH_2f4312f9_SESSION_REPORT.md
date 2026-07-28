# Gold Standard Shard-1: brevard, sumter, citrus, madison — session report

dispatch_id: 2f4312f9-1601-4103-8c7e-0eeb036ac834
chat_session: architect-20260728T160000
loop run: 7076

## Headline finding: brevard was NOT an honest 10/10 as briefed

The brief listed brevard and sumter as already 10/10. Live re-verification confirmed
that at session start, but a fan-out ULTRALOOP audit-refresh workflow (15 measure +
adversarial-refute agent pairs, run via the Workflow tool, `ultraloop_mode=native`)
caught **three ghost-successes in brevard** that the brief's numbers didn't disclose:

1. **Letter E** (parcel linkage): 94 rows had `parcel_id` values like `SYN-aa8c03f9eaeb`
   — synthetic placeholders, not real BCPAO parcel numbers — counted as "linked".
2. **Letter I** (property card complete): 2,122 rows had `property_address` set to a
   literal placeholder (`0 UNKNOWN`, `UNKNOWN`, `UNKNOWN FL`, etc., 8 variants) —
   satisfying the evaluator's `IS NOT NULL` check without a real address.
3. **Letter J** (deal thesis): `bid_decisions.factors` pass the evaluator's key-existence
   check, but the underlying values are a **mechanical placeholder fill**, not real
   Shapira-formula/CMA output — proven fleet-wide (same exact tuple recurs in sumter,
   alachua, bay).

Per HONESTY PROTOCOL (BLANK/FAIL > WRONG PASS) and the same precedent set by the
2026-07-27 citrus E ghost-linkage purge (commit c96d7fce), I purged what could be
purged and let the metrics land honestly, even though this moves brevard away from
certification rather than toward it.

## What was fixed live

- **brevard E**: nulled 94 `SYN-%` placeholder `parcel_id` values. Honest re-verify:
  97.7% (7047/7215) — still a genuine PASS, just not the falsely-clean 99.0% claimed.
- **brevard I**: nulled 2,122 `UNKNOWN`-pattern placeholder `property_address` values.
  Honest re-verify: **67.4% (4865/7215) — a genuine FAIL** (evaluator had been
  reporting a false PASS at 96.1%).
- **madison**: corrected case `25-79-CA`'s stale `auction_date` (was 2026-07-14, clerk's
  live page now shows it rescheduled to 2026-09-08 — verified directly, not fabricated).
- **citrus + madison**: `pipeline.counties.notes` updated with today's re-verified
  findings (below) so tomorrow's session doesn't repeat the same investigation.

## What was NOT fixed (and why)

- **brevard/sumter J**: the ghost-success is fleet-wide (also present in alachua, bay)
  and structural — the evaluator's `factors ? key` check has zero value-variance
  validation, and there's no real per-property data underneath the placeholder to
  restore. Rebuilding the Shapira/two-arm-CMA generator is out of this shard's
  authority (4 auction-data counties, not the deal-thesis pipeline). **Escalating to
  AI Architect**: J should not be trusted as evidence of real deal intelligence
  fleet-wide until the generator is rebuilt or the evaluator adds a distinctness check.
- **brevard G**: refuter found `parcel_zones` has 363,876 rows for brevard but only
  340,446 distinct `parcel_id`s (~23,430 stale duplicates from an unpurged prior
  re-ingestion batch, `created_at` 2026-01-23 vs corrected 2026-03-04). This does
  **not** change G's reported density/FAR/pk1000 percentages (those reproduced
  exactly), so G's PASS itself isn't false — but the headline parcel count is
  inflated. Flagged as a residual for the zoning-ingest owner, not fixed here.
- **citrus E/I**: still genuinely FAIL (180/191 = 94.2%, need 182). Re-verified the
  2026-07-27 architect-triage diagnosis stands: 2 multi-parcel cases (schema-limited),
  5 pending-judgment cases (future auction dates 08/20–09/03), 4 CAPTCHA/paywall-gated.
  Firecrawl confirmed still exhausted today (`remaining_credits=-4`). **New finding**:
  citrusclerk.org is migrating its foreclosure platform from RealForeclose to
  Bid4Assets, with all foreclosure sales paused 2026-07-13 through 2026-08-17 — this
  is why case `2025 CA 000999 A` (calendared 07-23, now past) never resolved. INFERRED
  from news coverage, not yet cross-checked against the clerk docket directly.
- **madison A/B/F**: still genuinely FAIL. A is fail-by-design (fc=5, td=0 — tax-deed
  page lists zero properties). B/F fail because closed_sold=0. Investigated the 2
  past-due cases: `25-79-CA` was rescheduled (not sold, see above). `21-36-CA` has
  disappeared from the clerk's calendar entirely with no results/archive page anywhere
  on the site. Exhausted alternates: `myfloridacounty.com/orisearch/40` needs a party
  name we don't have; Civitek OCRS (`civitekflorida.com/ocrs/county/40/`) is JS-gated
  and `browser-use` CLI isn't installed in this runner; `madisonpa.com`/qpublic are
  bot-blocked (403). Two independent WebSearch summaries hallucinated conflicting
  dollar amounts for `21-36-CA` across separate queries — both were caught and
  discarded, not reported. B/F remain a genuine external blocker.

## SQL VERIFICATION

```sql
-- BEFORE (session start, matches brief)
-- brevard: A-J all pass=true (apparent 10/10)
-- sumter:  A-J all pass=true (apparent 10/10)
-- citrus:  E fail 94.2 (180/191), I fail 94.2 (180/191), rest pass
-- madison: A fail (fc=5 td=0), B fail (null), F fail (null), rest pass

-- AFTER (2026-07-28, live)
SELECT public.pencil_dod_evaluate_county('brevard');
-- A PASS 906 | B PASS 98.6 | C PASS 95.6 | D PASS 95.6 | E PASS 97.7 (7047/7215, ghost-purged)
-- F PASS 98.9 | G PASS 98.0 | H PASS 0 | I **FAIL 67.4** (4865/7215, ghost-purged) | J PASS 99.3 (mechanical, escalated)

SELECT public.pencil_dod_evaluate_county('sumter');
-- A-J unchanged, all PASS (J flagged as mechanical placeholder, escalated, not reverted -- no real data to restore)

SELECT public.pencil_dod_evaluate_county('citrus');
-- unchanged: E FAIL 94.2 (180/191), I FAIL 94.2 (180/191), rest PASS

SELECT public.pencil_dod_evaluate_county('madison');
-- unchanged: A FAIL 0, B FAIL null, F FAIL null, rest PASS
```

Timestamp: 2026-07-28 ~18:05 UTC.

## ULTRALOOP audit evidence

15 rows inserted into `gold_standard_ultraloop_audit` (dispatch_id
`2f4312f9-1601-4103-8c7e-0eeb036ac834`, `ultraloop_mode='native'`):

| county | letter | survived | note |
|---|---|---|---|
| brevard | A,B,C,D,F,H | true | independently reproduced, clean |
| brevard | E | true | ghost-purged, honest 97.7% still passes |
| brevard | G | false | refuted — parcel-count duplicate-row anomaly (density/FAR/pk1000 % unaffected) |
| brevard | I | false | ghost-purged, honest 67.4% is a genuine FAIL |
| brevard | J | false | fleet-wide mechanical placeholder, escalated |
| sumter | A,C,D,H | true | independently reproduced, clean |
| sumter | J | false | same fleet-wide mechanical placeholder, escalated |

This intentionally does NOT clear brevard/sumter for certification — the honest
picture is brevard 8/10 (E,G-residual aside, I and J genuinely open) and sumter 9/10
(J genuinely open). The `adversarial_survival_X_of_10` gate is doing its job here.

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Verify brief's starting numbers | Yes | Yes | brevard/sumter matched brief at face value; ULTRALOOP found the brief's own numbers rested partly on ghost data |
| Fix citrus E/I | Attempted | Blocked | Genuine external blocker re-confirmed (Firecrawl exhausted, CAPTCHA, unentered judgments); new bid4assets-migration context found and documented |
| Fix madison A/B/F | Attempted | Blocked | Genuine external blocker (no clerk results archive, JS-gated official records, bot-blocked appraiser); 1 stale auction_date corrected |
| ULTRALOOP audit refresh (brevard+sumter) | Yes | Yes, expanded | Found 3 real ghost-successes instead of rubber-stamping; purged 2, escalated 1 |
| Commit + push to main | Yes | Yes | Direct to main per Ship-to-Main mandate |

## Deviation log

- The brief characterized brevard and sumter as clean 10/10s. That was true of the
  live evaluator output at face value, but not true once ULTRALOOP adversarially
  checked the *substance* behind each PASS. This is exactly the failure mode the
  ULTRALOOP protocol exists to catch (per the brief's own B>100% anomaly precedent),
  and it caught two more instances of it (I, J) that hadn't been flagged before now.
- `browser-use` CLI is documented in `.claude/skills/browser-use/SKILL.md` but is not
  installed on this GHA runner (`command not found`). This blocked one of the two
  remaining madison B/F leads (Civitek OCRS public-tier access). Flagging for
  infra/next session.
- Firecrawl account (`api.firecrawl.dev`) still shows `remaining_credits=-4` on a
  billing period that hasn't refreshed since 2026-03/04 — needs a plan renewal,
  repo-wide blocker, not citrus-specific.

## Residual / next-session priorities

1. **AI Architect escalation (top priority)**: J's evaluator contract is fleet-wide
   exploitable by placeholder fills with zero value-variance check. Any county's J=PASS
   should be treated as unverified until either the generator is rebuilt with real
   Shapira/CMA output or the evaluator adds a distinctness/authenticity check.
2. brevard I is now honestly FAILING (67.4%) — needs real address enrichment for the
   ~2,122 rows that were placeholder, likely via the same BCPAO ArcGIS pipeline used
   for parcel linkage.
3. brevard G: zoning-ingest owner should dedupe the ~23,430 stale `parcel_zones` rows
   from the pre-2026-03-04 re-ingestion batch.
4. citrus: verify the RealForeclose→Bid4Assets migration directly against the clerk
   docket once Firecrawl credits are restored, then update `foreclosure_platform`/
   `foreclosure_url` to bid4assets after the first live auction (2026-08-17).
5. madison: `21-36-CA`'s disposition remains unknown. Either install `browser-use`
   (or another JS-capable tool) to reach Civitek OCRS's public tier, or escalate the
   phone-call option (Madison Clerk, 850-973-1500) to Ariel.
6. `seminole` has 1 row with the same `SYN-%` ghost parcel_id pattern found in brevard
   — out of this shard's scope, flagging for whichever shard owns seminole.
