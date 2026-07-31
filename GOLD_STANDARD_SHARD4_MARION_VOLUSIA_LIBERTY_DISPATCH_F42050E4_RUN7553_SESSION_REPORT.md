# Gold Standard shard-4 (marion / volusia / liberty) — dispatch f42050e4, loop run 7553

Session date: 2026-07-31. Ultracode Workflow fan-out (17 agents: 5 investigate + 6 verify
for volusia's stale letters, 2 independent refuters for volusia G, 4 parallel investigators
+ 1 adversarial verifier for liberty). `ultraloop_mode='native'` (real Workflow tool, not
manual Task fan-out). All agent findings independently spot-checked against the live DB by
the orchestrating session before and after the workflow ran.

## TL;DR

- **marion**: 10/10, zero drift from the brief. Already has `survived=true` ultraloop audit
  rows for all 10 letters within the last 7 days — no action needed, positioned to
  self-certify on the next periodic `gold_standard_certify()` run. Did not force it (other
  shards may be mid-flight; ran `pencil_dod_evaluate_county` only, per parallel-fleet rules).
- **volusia**: **9/10 → 10/10 on live metrics.** G flipped PASS (83.3 → 97.1) via yesterday's
  `20260730f` Daytona Beach M-1 zonelink migration — this session adversarially confirmed
  that fix is real (see below), plus backfilled 7-day audit-freshness on A/B/F/J (all
  survived=true). **However, letter H's audit row from this session is `survived=false`** —
  see the open finding below. Volusia's ultraloop audit coverage is NOT clean 10/10 as of
  this session; H needs reconciliation before certification should be trusted.
- **liberty**: still 7/10 (A/B/F). Today (07-31, day 10 post-sale) was the exact day three
  prior sessions flagged as the earliest legitimate recheck. 4th consecutive identical
  result: Cloudflare Turnstile still blocks civitekflorida.com OCRS and myfloridacounty.com
  ORI at the search-submit step (not bypassed, per hard guardrails); libertyclerk.com pages
  are structurally incapable of surfacing post-sale outcomes; qpublic.schneidercorp.com is
  gated even harder (at page load). No new independent outcome found — NO_WRITE correctly
  re-confirmed for A/B/F, 3 fresh audit rows written.

## Before / after (`pencil_dod_evaluate_county`, live)

### marion — unchanged, 10/10
```
A=PASS(252) B=PASS(100.0) C=PASS(96.7) D=PASS(96.7) E=PASS(98.4) F=PASS(100.0)
G=PASS(100.0) H=PASS(0.1h) I=PASS(95.1) J=PASS(96.7)
```

### volusia — before
```
A=PASS(116) B=PASS(100.0) C=PASS(99.7) D=PASS(99.7) E=PASS(100.0) F=PASS(100.0)
G=PASS(97.1, was 83.3 as of the brief) H=PASS(0.1h) I=PASS(95.7) J=PASS(100.0)
```
(G had already flipped before this session started, via the 07-30 migration — this
session's job was to adversarially verify that flip and refresh stale audit evidence, not
to fix G itself.)

### volusia — after (unchanged live metrics; audit coverage changed, see below)
Identical to "before" — this was a verification session, zero writes to
`multi_county_auctions` / outcome tables / zoning tables.

### liberty — unchanged, 7/10
```
A=FAIL(0, fc=1 td=0) B=FAIL(null, verified=0 closed_sold=0) C=PASS(100.0) D=PASS(100.0)
E=PASS(100.0) F=FAIL(null, tier1_sold=0 closed_sold=0) G=PASS(100.0) H=PASS(12.9h)
I=PASS(100.0) J=PASS(100.0)
```

## Volusia G — adversarial verification detail (both refuters: SURVIVED)

Two independent refuters confirmed the `20260730f_gold_standard_shard3_volusia_g_daytona_m1_zonelink.sql`
migration is genuine, not ghost-success:
- `parcel_zones` row for parcel_id `533801110032` / jurisdiction 938 now reads `M-1`,
  matching `zoning_districts.id=6536`; no leftover unnormalized `M1` rows remain.
- `zone_standards.max_far=1.00` for district 6536 confirmed present.
- Refuter #1 went further than the migration's own citation and fetched the **live
  Municode API directly** (`api.municode.com/CodesContent?jobId=492952&nodeId=DABELADECO_ART4ZODI_S4.4INBAZODI&productId=13509`,
  HTTP 200) and found the verbatim ordinance text: *"Local Industry (M-1)" → "Intensity and
  Dimensional Standards" → "Floor area ratio (FAR), maximum 1.0"* — exact match, correct
  district. Also confirmed Sec. 4.4.B.4 genuinely defers parking to Article 6 with no
  per-district M-1 override, and that Table 6.2.C.1's compound "1.5 + 3.5 per 1,000sf"
  formula is real, supporting `pk1000_regulated=false` as a legitimate non-fabrication
  rather than a dodge.
- Refuter #2 independently confirmed the same DB state; Municode direct-fetch attempt via
  WebFetch hit a 403 (JS-rendered, not a CAPTCHA bypass attempt) but cross-validated the
  jobId/nodeId/productId identifiers as real and internally consistent with a separate
  migration 6 days earlier for the same jurisdiction.

Verdict: **G is a genuine fix.** Audit rows 11260, 11261 written, both `survived=true`.

## OPEN FINDING — volusia H freshness claim did not reconcile (flagging, not fixing)

The H refuter independently queried `multi_county_auctions WHERE county='volusia'` directly
(not through the RPC) and could not reproduce the RPC's claimed ~0h freshness:
- Most recent genuine `scrape_timestamp`/`created_at` for volusia: **2026-07-29T01:17:10Z**,
  ~47h before the query — right at the edge of the 48h SLA, not near-zero.
- The most recent `updated_at` (~8.5h old) belongs to a **PropertyOnion row** (case
  `PO-1267702`, `data_source='propertyonion'`) whose own `scrape_timestamp` is frozen at
  2026-07-06 (24 days stale) — and exactly **10 volusia PO-\* rows share that identical
  microsecond `updated_at`**, a bulk mass-touch UPDATE signature, not organic scraping.
- Ruled out a global pipeline outage: jackson, miami_dade, duval, and pinellas all had
  genuinely fresh writes in the same window.

This is consistent with the exact staleness-arbitrage failure mode `pencil_dod_criteria.H`'s
own rationale warns against — if the evaluator's H branch reads `updated_at` rather than a
true last-organic-scrape signal, a bulk enrichment/backfill touch on unrelated
PropertyOnion rows could be masking genuine staleness. **This was not fixed this session** —
the evaluator function is scoring logic (`gold_standard-loop-*` adjacent) and per repo
guardrails should not be modified without dedicated review, not as a side effect of an
audit pass. Audit row 11259 (`survived=false`) is on record. **Recommend next session: pull
the actual SQL body of `pencil_dod_evaluate_county`'s H branch and confirm which column it
reads before trusting H PASSes fleet-wide**, not just for volusia — the PropertyOnion
bulk-touch mechanism found here is not volusia-specific.

## Liberty — 4th consecutive identical recheck, 07-31 (the flagged day)

Four parallel investigators, fresh Playwright/Chromium sessions today:
- **civitekflorida.com/ocrs/county/39**: reached the Case Search tab, filled Year=2024/
  CA/Seq=22, confirmed a live interactive Turnstile iframe (sitekey `0x4AAAAAAAR0Af-5MfzdbO3p`,
  unchanged) gates the search-submit step specifically (not page load) — submitting without
  a token silently resets the form (HTTP AJAX postback, no error text). Not bypassed.
- **myfloridacounty.com/orisearch/39**: search form itself loads clean, but the results
  endpoint (`/orisearch/s/search`) returns a literal "Please verify you are human" Turnstile
  checkbox (sitekey `0x4AAAAAAA64PTBePmuGbrkR`, unchanged). New detail vs prior sessions: an
  `onTurnstileSuccess(token)` JS callback explicitly gates the real form submission. Not
  bypassed.
- **libertyclerk.com**: tax-deeds page genuinely empty (4th consecutive identical
  confirmation across 07-05/18/24/27/31 — letter A is a genuine absence, not a scraper gap).
  foreclosure-sales page confirmed structurally forward-looking only (no results/archive
  section exists on this domain at all) — it cannot surface a post-sale outcome for
  24-CA-22 regardless of CT recording status.
- **qpublic.schneidercorp.com** (3 AppID/LayerID variants, including the pair actually
  hyperlinked from libertypa.org): gated by Turnstile at page LOAD itself — worse than the
  OCRS sites. libertypa.org confirmed (again) to have no real parcel search of its own, just
  a WordPress blog search box.

Adversarial verifier independently re-confirmed the DB is unchanged (`multi_county_auctions`
row for 24-CA-22: `sold_amount`/`tier1_sold_amount` still null, `foreclosure_outcomes`/
`tax_deed_outcomes` still 0 rows for liberty) and wrote 3 audit rows (A/B/F, ids 11304-11306,
`survived=true` — the claim that verified is "genuinely blocked, NO_WRITE is correct," not
that the letters pass). Firecrawl was checked fresh this session: still exhausted
(`remaining_credits: -2` against a 1000 plan limit) — not a viable alternate path.

**Escalation recommendation (from the verifier agent, endorsed here):** this is now 4
consecutive daily-manual-recheck sessions spanning a full week (07-24, 07-25, 07-27, 07-31)
reaching an identical result with zero new lever discovered. Recommend the AI Architect
decide between (a) a licensed/sanctioned Turnstile-solving service (new spend category —
not covered by the existing ARM-2 $50/mo comps-API authorization, needs explicit approval)
or (b) a one-time manual clerk-office pull for this specific case, rather than continuing to
burn a daily investigator session re-confirming an unchanged external block. Case 24-CA-22 is
now 10 days post-sale with a Certificate of Title plausibly already recorded but structurally
unreachable via any automated path currently available to the fleet.

## Certification status (not forced this session, per parallel-fleet rules)

- `gold_standard_loop()` / `gold_standard_certify()` were **not** run — cannot confirm no
  other shard is mid-flight. Verification used `pencil_dod_evaluate_county` per county only.
- marion: full 10-letter `survived=true` audit coverage within 7 days as of 2026-07-30T19:54Z
  — should self-certify on the next periodic run without further action.
- volusia: now 9-of-10-confirmed (H open per above) + G newly confirmed this session. Not
  recommended for certification until H is reconciled — a stale/masked freshness signal
  should not be allowed to gate a certify pass just because the RPC currently returns PASS.
- liberty: unchanged 7/10, genuine external blocker, not certification-track this week.

## Verification evidence (loop closure)

- Command: `POST {SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county` with
  `{"p_county":"<slug>"}`, run before and after the workflow for all three counties —
  outputs pasted above, byte-identical before/after (zero regression, zero drift).
- 11 new rows written to `gold_standard_ultraloop_audit` this session (ids 11253-11261,
  11303-11306), all `dispatch_id=f42050e4-56e1-424c-b0ec-f9b4942ec2ec`,
  `ultraloop_mode=native`: 10 `survived=true`, 1 `survived=false` (volusia H, flagged above).
- Firecrawl credit check: `GET api.firecrawl.dev/v1/team/credit-usage` →
  `remaining_credits: -2` (still exhausted, confirmed fresh this session).

## Deviation from plan

Planned to spend equal effort across all three counties; in practice marion required zero
new work (already fully covered), so effort shifted to volusia audit-freshness backfill +
liberty's flagged recheck day, which was the higher-leverage use of the session. The volusia
H finding was not in the original plan — it surfaced from the adversarial refuter doing its
job correctly (this is exactly what the ULTRALOOP protocol's "adversarial survival vote" is
for: catching a claim that looks like a PASS but doesn't reconcile against raw data).
