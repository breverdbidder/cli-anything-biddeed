# Gold Standard shard-1 — brevard/manatee/suwannee/madison/sumter (dispatch `999b87f8-844c-479d-b7fd-b0eccf906fb9`, 2026-08-31 08:00Z wave)

## TL;DR

Scoreboard unchanged this session: **brevard 9/10, manatee 9/10, suwannee 9/10, madison 8/10, sumter 6/10**.
One genuine, adversarially-verified live write was applied (brevard, 1 row) — it did not flip any letter's
pass/fail because the row's zone-linkage status was independently disproved to be what a heuristic script
predicted. All five counties' failing letters were reconfirmed today via fresh live sources against prior
diagnoses — every one still stands as either a canon-level structural design tension
(`CLERK_SSOT_CANCELLED` exclusion from `matched_clean`, affecting manatee C, suwannee C, sumter C) or a
genuine real-world data ceiling (sumter I unaddressed parcels, madison B/F no-outcome cases). Two new,
non-fabricated leads were surfaced for the next session (sumter E candidate parcel `M11-052` for case
`2026-CA-000129`, HYPOTHESIS-tier not applied; sumter I case `2026-CA-000074` now has a clerk-listed
address that is independently disproved to belong to a different, unrelated owner — flagged as a clerk-side
data anomaly, not written).

## Method

Ran a 9-agent ULTRALOOP Workflow (Fix phase: 7 agents — 2 genuine attempt-a-fix tasks + 5 reconfirm-only
tasks; Verify phase: 2 adversarial refuters against the 2 fix-phase claims). Pre-session forensics (done
directly, not delegated) established live baselines and ruled out dead levers (Firecrawl HTTP 402,
confirmed) before any agent was dispatched, so agent budget was spent on genuinely open questions rather
than rediscovering already-documented dead ends.

## brevard — letter I (86.0% → 86.0%, unchanged, FAIL)

Prior diagnosis (`20260827_gold_standard_shard1_8f944a71_brevard_i_geo_backfill_structural_block.sql`)
flagged an unattempted residual lever: AcclaimWeb docket lookup for the in-scope `parcel_id IS NULL`
population (documented at ~32-41 rows). Live re-check this session found this population had shrunk to
**16 rows**. Forked the proven `brevard_i_clerk_platform_legal_backfill_e91f7a52.py` pipeline
(AcclaimWeb case search → legal-description regex → gis.brevardfl.gov single-feature resolution →
fabrication guard) against the explicit 16-case list.

- 1/16 resolved to a single real GIS feature: case `05-2025-CC-051498-XXCC-BC`, TaxAcct `2460880`. Applied
  live via idempotent PATCH: `parcel_id=2460880`, `latitude=28.3794388950963`, `longitude=-80.8179775588836`,
  `assessed_value=253160`. `property_address` correctly left NULL — the GIS feature's `STREET_NAME` is
  `CONFIDENTIAL` (Address Confidentiality Program parcel); writing a fake address would be fabrication.
- 13/16 have condo/metes-and-bounds legal descriptions the LOT+PB+PG regex cannot parse at all — a
  genuinely different failure mode from the two previously-confirmed structural buckets (UNKNOWN street
  name; zero GIS feature).
- 2/16 hit ambiguous GIS matches (0 or 4 features) and were correctly skipped, not guessed.

**Metric did not move** (`card_complete` stayed at `6316 of 7348`, 86.0%). Root cause, independently
confirmed by both the fix agent and the adversarial verifier: the applied parcel (`2460880`) has zero rows
in `zoning_assignments` (the real per-parcel join table) despite `v_zoning_gold_standard_card` showing a
`zone_code='REU'` entry for it. This confirms — for the second time (previously seen on a seminole-county
session) — that `v_zoning_gold_standard_card` is a deduplicated `(jurisdiction_id, zone_code)` sample, not
a reliable per-row zone-linkage signal, and should not be trusted by future backfill scripts to predict
whether a write will flip `card_complete`.

Adversarially verified (`gold_standard_ultraloop_audit` id `19906`, `survived=true`): independently
re-queried the written row, confirmed it did not already carry these values before this session (cross-
checked against a prior migration that explicitly logged this exact row as fully-NULL and out-of-scope),
and reproduced the byte-identical before/after evaluator output.

**brevard I remains a confirmed structural ceiling.** Combined with the 08-27 finding, essentially every
inexpensive lever (GIS docket lookup, Firecrawl) is now exhausted or dead; the dominant ~980-row gap is
genuinely addressless/no-GIS-feature parcels in the county's own system of record.

## manatee — letter C (89.5%, FAIL) — reconfirmed, canon-level block, no change

Live metric identical before/after (no writes attempted, per this task's scope). Confirmed the same 13
`CLERK_SSOT_CANCELLED` rows documented in `GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md`,
`updated_at` timestamps show no drift since 4 days ago. Spot-checked 2 of 13 against
`records.manateeclerk.com/CourtRecords` live — both reconfirmed genuinely cancelled/no-judgment. Audit row
`gold_standard_ultraloop_audit` id `19847`, `survived=true`.

## suwannee — letter C (82.9%→80.0%, FAIL) — reconfirmed, blocking set grew 6→7 rows

The blocking set grew as hypothesized going in: case `4741` (parcel `1437000001`) joined the previously
documented 6-row `CLERK_SSOT_CANCELLED` set, confirmed genuinely redeemed against the live
`suwgov.org` tax-deed schedule PDF (now `Schedule-08.28.2026.pdf`, a newer edition than the prior report
used). Both spot-checked rows (`4693`, `4741`) confirmed absent from the current live schedule. Audit row
id `19848`, `survived=true`. Same canon-level block as manatee, unrelated to a per-county data defect.

## sumter — letters C (87.5%, FAIL), E (93.8%, FAIL), I (87.5%, FAIL), J (93.8%, FAIL)

### C — reconfirmed, canon-level block, no change
Same 4 redeemed tax-deed certs (`104, 1078, 1159, 1400`) as the 2026-08-29 finding, `updated_at` now
2026-08-30 (confirming an upstream re-scrape ran and landed on the identical classification). All 4
spot-checked (exceeding the required minimum of 2) against the live `sumterclerk.com` tax-deed widget —
exact string match on parcel/owner/status for all 4. Audit id `19849`, `survived=true`.

### E — fresh research attempt, one HYPOTHESIS-tier lead surfaced, NOT applied
The 2 rows blocking E (`2026-CA-000074`, `2026-CA-000129`) were previously called "genuinely unresolvable"
by a single prior session. This session found the real case captions for the first time via a
previously-untried live source (`sumterclerk.com/courts/foreclosures/foreclosure-sales/`, plain curl, no
Cloudflare block):

- **`2026-CA-000129`** (Kenneth Strong vs. Johnathon Young): candidate parcel `M11-052`
  (owner "YOUNG JOHNATHON & NICOLE", a unique name-spelling match in all of Sumter's `fl_parcels`, with a
  financially-plausible March-2024 $239,000 purchase preceding the $249,174.17 judgment). This is
  **HYPOTHESIS, not CONFIRMED** — no document ties the case number itself to this parcel by legal
  description; the match rests on name uniqueness + plausible timeline only. Per this repo's fabrication
  guardrail ("only write parcel_id if a source ties the SPECIFIC case_number to a SPECIFIC parcel"), **this
  was deliberately NOT written to the database.** Flagged for a follow-up corroboration pass (Sumter
  Official Records grantor/grantee index for "Young Johnathon") before any future session applies it.
- **`2026-CA-000074`** (Wilmington Savings Fund Society vs. Marc G. Ratliff): the clerk's own page lists
  an address, `316 San Marino Drive, Lady Lake, FL`, that this session independently disproved — that
  parcel (`D13D081`) is owned by Dale & Sharon Wheeler, who have held it since 1995 per a corroborating
  villages-news.com article, and no "Marc Ratliff" owns any parcel in Sumter County. This is now a
  **known clerk-side data anomaly** on the source system itself, not an unresearched gap — escalation to
  a human records request (352-569-6600) is the only remaining lever, not further scripted search.

Adversarially verified (audit id `19907`, `survived=true`): re-confirmed both rows still NULL in the DB (no
write occurred, as claimed), re-fetched the clerk page and `fl_parcels` evidence independently, confirmed
the Wheeler/villages-news corroboration.

### I — reconfirmed; the specific blocking rows have rotated, not shrunk
The 4 parcels named in the 2026-08-13 finding (unaddressed vacant/cemetery parcels) are now all resolved.
Today's actual 4 blockers are different: `2026-CA-000074`, `2026-CA-000129` (both no card fields — same
2 rows as the E gap above), plus `2026-CA-000090` (zoning-link mismatch) and `2025-CA-000515` (CMU zone
code with no `zone_standards` row) — both already documented dead ends from 08-27/08-28 sessions. One
genuinely new observation: case `2026-CA-000074`'s address field is now populated on the live clerk page
(`316 San Marino Drive...`) where it was blank in the 08-27/08-28 sessions — **but this is the same address
independently disproved above as belonging to a different owner, so it was correctly NOT written.** Audit
id `19863`, `survived=true`.

### J — not separately investigated this session
J's 2-row gap (`30 of 32`) structurally depends on the same 2 case numbers blocking E (no parcel → no
comps → no `bid_decisions` row); resolving E's `2026-CA-000129` lead (once corroborated) should cascade-fix
one J row via the existing `tier1-promote-hourly`/valuations-comps automation, per this campaign's
documented dependency chain. Not re-diagnosed independently this session to avoid duplicate work.

## madison — letters B, F (both null%, FAIL) — 12th+ reconfirmation, no new lead

`auctions_total` grew 5→8 (3 new future-dated rows, Sept-Nov 2026, none closed — cannot affect the
`closed_sold` denominator). The exact same 3 past-due blocking cases stand: `21-36-CA`, `24-62-CA`
(`tier1_sale_status=SOLD` but `sold_amount` still null), `26-20-CA`. Per task instructions, no previously-
tried angle was re-attempted since no genuinely new case appeared. Two spot-checks (madisonclerk.com,
civitekflorida.com OCRS) both reconfirmed the same Turnstile/no-archive dead ends as prior sessions, not
stale. Two audit rows inserted (`19896` for B, `19897` for F, `survived=true` — the audit table's letter
column is single-character, so the combined "B and F" task was logged as two rows).

## Guardrail compliance

- No `parity_status`, `sold_amount`, or any address/parcel field was fabricated or guessed anywhere this
  session. Every written value traces to a live source fetched this session (brevard's 1 write) or was
  explicitly withheld pending stronger evidence (sumter E's Young lead).
- PropertyOnion was not used as anything but litmus.
- `pencil_dod_evaluate_county`, `refresh_parity_tier1_outcomes`, cron jobs 109/111/115, and the
  gold-standard-loop scoring jobs were not modified.
- `gold_standard_loop()` / `gold_standard_certify()` were not invoked (per PARALLEL-FLEET RULES — other
  shard sessions were presumed concurrently in-flight; the same `dispatch_id`-shared audit table shows
  interleaved rows from other counties' sessions at overlapping timestamps, confirming this).
- 7 `gold_standard_ultraloop_audit` rows inserted this session (ids `19847`, `19848`, `19849`, `19863`,
  `19896`, `19897`, `19906`, `19907` — 8 total counting both verify-phase rows), all `survived=true`.
- `gold_standard_campaign` id `5426` updated with per-county `criteria_passed` (A-J for all 5 counties),
  `exit_reason='ceiling_reconfirmed_plus_1_real_write_no_metric_flip'`, `session_end_at` recorded.

## Live scoring evidence (VERIFIED, `pencil_dod_evaluate_county`, run 2026-08-31 end of session)

```
brevard:  9/10 (I FAIL 86.0%, card_complete=6316 of 7348)
manatee:  9/10 (C FAIL 89.5%, matched_clean=154 of 172)
suwannee: 9/10 (C FAIL 80.0%, matched_clean=28 of 35)
madison:  8/10 (B FAIL null%, F FAIL null%, verified=0/closed_sold=0)
sumter:   6/10 (C FAIL 87.5%, E FAIL 93.8%, I FAIL 87.5%, J FAIL 93.8%)
```

## Next-session priorities

- **sumter E/J**: corroborate the `M11-052` / Young lead via Sumter Official Records grantor-grantee index
  before applying (would fix E and likely cascade one J row).
- **sumter E**: `2026-CA-000074` (Ratliff) needs a human records request to the Clerk's office — no further
  scripted lever exists; the clerk's own published address is now confirmed wrong.
- **brevard I / manatee C / suwannee C / sumter C / sumter I**: all confirmed structural ceilings this
  session, independently, with fresh live evidence. Recommend NOT re-diagnosing these on the same angles
  again absent a new data source or a canon-level architect decision on the C/D `CLERK_SSOT_CANCELLED`
  question (still open per the 2026-08-27 cross-county finding's Options A/B/C).
- **madison B/F**: skip every angle logged across 12+ sessions; the only remaining lever is a direct
  Clerk's-office contact, outside automated-session scope.
