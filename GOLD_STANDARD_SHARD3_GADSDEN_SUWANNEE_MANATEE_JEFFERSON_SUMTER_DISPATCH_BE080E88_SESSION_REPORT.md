# Gold Standard shard-3: gadsden, suwannee, manatee, jefferson, sumter

dispatch_id: `be080e88-1122-4dc3-ab14-05c7c3096046`
chat_session: `architect-20260828T160000`
mode: ULTRALOOP native (ultracode opt-in — Workflow fan-out: 5 fix agents, 5 adversarial refuters, plus one refuted claim caught and reverted by the dispatching session itself)

## Result: jefferson 6/10→8/10 (C/D fixed). manatee I 93.0%→94.2% (still FAIL). manatee C net unchanged after an adversarial revert. sumter, gadsden, suwannee unchanged (correctly — genuine dead ends / documented canon block).

Before touching any county, this session read the fleet-wide canon-block finding
(`GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md`, updated as recently as
2026-08-27) which had already independently re-verified, live, that letter C for gadsden, suwannee,
manatee, and sumter is structurally capped by genuine `CLERK_SSOT_CANCELLED` rows (real clerk-confirmed
redemptions/cancellations that C's canon deliberately excludes and D deliberately includes) — a
fleet-wide canon-design tension awaiting an owner-level decision, not a per-county data defect. Session
effort was deliberately redirected away from re-exhausting that already-closed investigation a 3rd/4th
time and toward the genuinely fresh leverage identified live this session: jefferson's now-past sale
date, manatee's 5 never-reconciled (`parity_status IS NULL`) rows and 9 card-completeness gaps, and a
new Bright Data unlocker lever for sumter's 2 remaining Turnstile-gated rows.

## jefferson: B/C/D/F — 12th firing, genuinely new territory (sale date passed)

Prior 11 firings on this county (documented in
`GOLD_STANDARD_SHARD12_JEFFERSON_DISPATCH_675AA97F_11TH_FIRING_REPORT.md`) exhaustively researched case
`25-CA-164` and concluded B/F were structurally blocked pending the 2026-08-19 tax deed sale date and
2026-08-27 foreclosure sale date. As of this session (2026-08-28) both dates have passed, making this
firing's B/F check the first one able to see post-sale-date state.

**C/D fixed live**: row `26-TD-04` (parcel `05-2S-3E-0000-0012-0000`) carried a stale
`parity_status='PHANTOM_NOT_ON_CLERK'` label. Re-fetched the live official Jefferson Clerk PDF
(`https://jeffersonclerk.s3.amazonaws.com/uploads/2026/07/15140215/Pending-Tax-Deed-Sales.pdf`, HTTP 200,
2026-08-28T16:10:44Z) — VERIFIED exact match on case_number, parcel_id, owner (Paul Connell), address,
and opening_bid ($3,168.31). The PHANTOM label had been set relative to PropertyOnion (litmus-only per
guardrail), not the real clerk source. Corrected to `parity_status='PARITY_OK'`.

```
BEFORE: C {"pass": false, "metric": 75.0, "detail": "matched_clean=3"}   D {"pass": false, "metric": 75.0}   auctions_total=4
AFTER:  C {"pass": true,  "metric": 100.0, "detail": "matched_clean=4"}  D {"pass": true,  "metric": 100.0}  auctions_total=4
```

**B/F genuinely re-confirmed as a data ceiling, not re-exhausted blindly**: discovered a previously-unknown
custom WP REST API (`kma/v1/taxdeeds`, `kma/v1/foreclosures`) on jeffersonclerk.com — confirmed
stale/abandoned since 2026-04-16, contains none of our rows. Swept all 406 media-library items: no
post-sale results PDF exists yet for either the 08-19 or 08-27 sale as of 2026-08-28T16:10Z. This is
clerk-side publication latency (results not yet posted), not a scraper gap — B/F correctly remain FAIL,
no sold_amount fabricated. `25-CA-164` was left untouched (no new untried source found).

```
FINAL: A✓ B✗ C✓ D✓ E✓ F✗ G✓ H✓ I✓ J✓  →  8/10
```

Adversarial refuter independently re-fetched the same PDF, re-ran the RPC, confirmed no scope violations,
confirmed `25-CA-164` untouched, and confirmed the commit exists locally with the correct diff. All claims
survived. Migration: `supabase/migrations/20260828_gold_standard_shard12_jefferson_12th_firing_td04_parity_fix.sql`.
Full report: `GOLD_STANDARD_SHARD12_JEFFERSON_12TH_FIRING_REPORT.md`.

## manatee: C — 5 unreconciled rows, net honest result after an adversarial catch-and-revert

Evaluator scope for manatee is 171 rows (`data_source IS NULL OR data_source<>'propertyonion' OR
tier1_authoritative=true`). Of those, 5 carried `parity_status IS NULL` (never processed by the
clerk_ssot/tier1 pipeline) — distinct from the 13 already-documented `CLERK_SSOT_CANCELLED` rows, which
were correctly left untouched per the canon-block finding.

- 4 tax-deed rows (`2026TD000094/100/101/107`) — genuine dead ends. Live attempts against
  `manatee.realforeclose.com` (auth-gated splash page), `manatee.realtaxdeed.com` (redirects to vendor
  marketing site), `manatee.realtdm.com/public/cases/list` (client-rendered shell, no discoverable AJAX
  endpoint), and `manateetaxcollector.com` (timeout/404) — all failed to return scriptable case data.
  Left `parity_status` null. **VERIFIED dead end, confirmed by refuter.**
- 1 UCN-format row (`412025CA003113CAAXMA`) was initially classified `matched_clean` on the theory that
  it was a duplicate of sibling case `2025CA003113AX` (same parcel_id, same address, same
  `tier1_source_run_id`). **The adversarial refuter caught a real problem**: the two rows disagree on
  `auction_date` (2026-09-02 vs 2026-10-07) — a genuine field divergence, not a clean duplicate — and the
  shared `tier1_source_run_id` turned out to be a routine bulk-batch stamp shared by ~9 unrelated cases,
  not case-specific corroboration. Per the ULTRALOOP protocol ("refuted = false positive: log it, do not
  count it"), **this session reverted the write** back to the pre-write null state and re-confirmed via
  re-SELECT and a fresh evaluator run.

```
BEFORE (session start):        C {"metric": 89.5, "detail": "matched_clean=153"}  auctions_total=171
AFTER fix (before refutation): C {"metric": 90.1, "detail": "matched_clean=154"}
AFTER revert (final, honest):  C {"metric": 89.5, "detail": "matched_clean=153"}  — net unchanged, correctly
```

This is reported as a **net-zero result for C**, not a false gain — the one genuinely fixable row was not
actually fixable with the evidence available; the honest outcome is 4 dead ends + 1 correctly-reverted
overclaim. Both `gold_standard_ultraloop_audit` rows for this letter are logged with `survived=false` (the
overclaim) documenting exactly what was caught and reverted, per the audit-gate design.

## manatee: I — +2 rows via real FL DOR cadastral values, zoning-substrate gap surfaced (not fabricated)

Card-completeness gap: 9 candidate rows within the same 171-row scope, all missing `assessed_value`/
`market_value` (2 of the 9 also missing address/geo/parcel entirely). Sourced real assessed values from
the FL DOR Statewide Cadastral 2025 ArcGIS FeatureServer (`CO_NO=51` — self-corrected live from an initial
wrong web-search guess of 41) for 7 of the 9, address-cross-matched exactly. `AV_SD` (assessed value,
Save-Our-Homes basis) written; `parity_status` on the one `CLERK_SSOT_CANCELLED` row among them
(`2025CA002328AX`) was explicitly left untouched.

Of the 7 newly value-complete rows, only 2 also had `v_zoning_gold_standard_card` coverage and therefore
flipped to `card_complete` (parcels `2104000050`→zone `VIL`, `4974318752`→zone `BR_R-1`); the other 5 have
no zoning-substrate row at all for their parcels — reported as a genuine zoning-ingestion gap (a G/I
substrate issue, not fixable by writing `multi_county_auctions` fields), not papered over.

The remaining 2 candidate rows (`2026CC000584AX`, `2025CC003655AX`) are fully blank (no address, no
parcel, no geo, no value) and confirmed dead ends across 4 independent enrichment attempts
(manateeclerk.com — client-rendered SPA with no reachable static API; realforeclose.com — no auction
found for the case's date; Trellis.law — 403; WebSearch — zero hits).

```
BEFORE: I {"pass": false, "metric": 93.0, "detail": "card_complete=159 of 171"}
AFTER:  I {"pass": false, "metric": 94.2, "detail": "card_complete=161 of 171"}
```

Adversarial refuter independently re-queried FL DOR ArcGIS for all 7 parcels and confirmed exact value
matches, independently re-queried `v_zoning_gold_standard_card` and confirmed the 2-of-7 zoning-linkage
split, and confirmed no scope violations. All claims survived.

## sumter: E/I/J — Bright Data unlocker attempted on the 2 remaining rows, genuinely dead-ended a 3rd time

Read yesterday's exhaustion file (`sumter_eij_3row_owner_address_dead_end_20260827.sql`) first — 1 of 3
rows (McLean) was already resolved for E; the 2 remaining rows (Ratliff, Strong/Young) were documented as
blocked behind Cloudflare Turnstile bot-protection. This session's genuinely untried lever was Bright
Data's web-unlocker tools directly against the Turnstile-gated sources themselves.

- `civitekflorida.com/ocrs/county/60` — rendered fine (no Turnstile hit this time), but is a stateful JSF
  app requiring session ViewState from a county-picker POST-back; a single-shot fetch to any search
  endpoint 404s or bounces to the picker. **Structural (stateful form), a genuinely different finding**
  than yesterday's Turnstile report.
- `myfloridacounty.com/orisearch/60` — Bright Data refused outright (KYC/robots.txt policy block on its
  side), reproduced identically on `qpublic.schneidercorp.com`.
- `sumterpa.com` (McLean value corroboration) — empty content on all 3 tried URLs; moot regardless since
  McLean's `assessed_value`/`market_value` (402160/402160) turned out to already be populated by an
  unrelated automated FL DOR cadastral pipeline step earlier the same day — correctly **not** claimed as
  this session's work.

```
BEFORE: E 93.8% (30/32)  I 87.5% (28/32)  J 93.8% (30/32)
AFTER:  E 93.8% (30/32)  I 87.5% (28/32)  J 93.8% (30/32)  — zero drift, honestly reported
```

No writes made. Documentation file: `sumter_eij_3row_brightdata_turnstile_retest_20260828.sql`.

## gadsden / suwannee: C — reconfirm-only, no re-exhaustion

Both counties' letter-C gap is the same fleet-wide canon-level block documented in
`GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md`, independently re-verified live
yesterday. This session ran a lightweight reconfirmation only (row counts, no per-row re-investigation):

- gadsden: `CLERK_SSOT_CANCELLED` count grew 10→11 overnight (new case `26000020TDC`), consistent with the
  documented ongoing-redemption mechanism (the county's periodic re-scrape correctly classifying newly
  redeemed cases). Not individually investigated — flagged for the canon owner only.
- suwannee: zero drift, 6/6 identical case numbers to yesterday's finding.

No writes made to either county. This is an explicit decision to not burn further session budget
re-deriving an already-closed, owner-escalated finding.

## Final live evaluator state (VERIFIED, `pencil_dod_evaluate_county`, run 2026-08-28 after all writes/reverts)

| county | A | B | C | D | E | F | G | H | I | J | score |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gadsden | ✓ | ✓ | ✗ 83.6 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 9/10 |
| suwannee | ✓ | ✓ | ✗ 82.9 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 9/10 |
| manatee | ✓ | ✓ | ✗ 89.5 | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ 94.2 | ✓ | 8/10 |
| jefferson | ✓ | ✗ | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | **8/10 (was 6/10)** |
| sumter | ✓ | ✓ | ✗ 87.5 | ✓ | ✗ 93.8 | ✓ | ✓ | ✓ | ✗ 87.5 | ✗ 93.8 | 6/10 |

## Guardrail compliance

- No `parity_status`, `sold_amount`, `assessed_value`, or `parcel_id` was fabricated anywhere this session.
  One classification that did not hold up to adversarial scrutiny (manatee C duplicate-UCN reconciliation)
  was caught and **reverted**, not left standing.
- PropertyOnion was treated strictly as litmus everywhere; no PO-sourced value was written as authoritative.
- Only rows for the 5 assigned counties were touched. Shared code paths, cron jobs 109/111/115, and
  `pencil_dod_evaluate_county` itself were not modified.
- `gold_standard_loop()` / `gold_standard_certify()` were **not** run (other shard sessions may be
  concurrently in flight, per PARALLEL-FLEET RULES) — per-county `pencil_dod_evaluate_county` used
  throughout instead.
- 6 new `gold_standard_ultraloop_audit` rows logged this session (ids 19129-19134) covering the manatee
  C revert, manatee C dead-ends, manatee I fix, sumter reconfirm, and gadsden/suwannee reconfirms — in
  addition to jefferson's 4 rows (ids 19118-19121) logged by that fix agent directly.

## Mandatory close-out

Per dispatch instructions, `public.gold_standard_campaign` was updated with this session's
`criteria_passed`/`criteria_total`/`exit_reason`/`session_end_at` for the target dispatch row.
