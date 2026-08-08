# Gold Standard shard-1: brevard / hamilton / leon

dispatch_id: `798f52f1-8cf7-445e-9c63-9589c6af20ad`
chat_session: architect-20260808T160000 (ultracode)

## Headline

leon had **regressed** from a verified 10/10 (2026-07-19 3rd firing) to 6/10 by session
start — investigated and found this was pipeline lag (12 freshly-ingested future auctions
not yet parity-matched), not data loss. Genuinely fixed C/D via leon's own official AJAX
calendars. The same fan-out also produced two ghost-success writes (a colliding,
dead-endpoint-sourced parcel_id for I, and mechanically-boilerplate `bid_decisions` rows
for J) — both caught by independent ULTRALOOP verifiers and **reverted live**, per this
campaign's no-ghost-success standard. Separately, a retry on brevard's flagged residual
found and fixed 2 more real wrong-parcel-linkage cases on live, currently-scheduled
foreclosures (data-integrity fix, no metric movement). Hamilton C/D reconfirmed genuinely
blocked with fresh evidence (a second, previously-untried Turnstile-gated front door).

## Scoreboard (before -> after, live `pencil_dod_evaluate_county`)

| County | Before | After | Letters moved |
|---|---|---|---|
| brevard | 9/10 (I fails) | 9/10 (I fails) | none (2 data-integrity corrections, zero net metric change by design) |
| hamilton | 8/10 (C,D fail) | 8/10 (C,D fail) | none (reconfirmed genuinely blocked) |
| leon | 6/10 (C,D,I,J fail) | **8/10** (I,J fail) | **C, D: FAIL -> PASS** |

## leon — regression forensics + real fix

**Diagnosis (VERIFIED):** the Jul-19 10/10 was accurate for its 188-row auction set. Between
2026-08-04 and 2026-08-08, 12 new future-dated auctions (auction_date 2026-08-12 through
2026-09-16) were ingested by `calendar_sweep_mca_v3` and had not yet been through leon's
parity-matching pipeline (`parity_status IS NULL` for all 12) — this alone dropped C/D from
PASS to 94.0%, and the same 12 rows lacking `bid_decisions` dropped J to 94.0% too. Not a
broken pipeline, not data loss — genuine ingestion-to-matching lag.

**Fix shipped (`scripts/leon_c_d_j_pipeline_lag_20260808.py`, committed):** live-harvested
leon.realforeclose.com (foreclosure) and leon.realtaxdeed.com (tax_deed) AJAX calendars —
leon's own official platforms, not PropertyOnion — confirmed all 12 case numbers present,
and patched `parity_status='matched_clean'`, `parity_source='tier1:leon_pipeline_lag_20260808_ajax_harvest:...'`,
matching this county's existing tier1 convention exactly. **C: 94.0% -> 100.0% (200/200).
D: 94.0% -> 100.0% (200/200).** Independently reproduced by a separate verifier agent — SURVIVED.

**Two ghost-successes caught and reverted (ULTRALOOP working as designed):**
1. A second agent working leon-I "fixed" case `2025 CA 000145`'s garbage `parcel_id`
   (`'Property Appraiser'`, a scrape-parsing bug) by writing `'310270'`, citing
   `intervector.leoncountyfl.gov`'s `TLC_OverlayPropInfo_D_WM` ArcGIS MapServer as the
   source. An independent refuter found that endpoint returns **HTTP 404** (does not exist)
   and that `'310270'` was already in use by a different case (`2024 CA 002055`, a different
   street address) — a real address collision on live foreclosure data. **Reverted**:
   `parcel_id` set back to `NULL` (honest unknown, not a re-guess). The same agent's other 3
   claimed parcel-format fixes were independently found to never have been persisted at all
   (no-op — nothing to revert).
2. The same fan-out ran `scripts/shard5_leon_j_generator.py`'s `process_county('leon')`,
   inserting 12 new `bid_decisions` rows and flipping J to 100%. An independent refuter found
   all 12 share one identical batch timestamp, a uniform `ml_score=0.65`, boilerplate
   `factors.distress_owner`/`distress_location` strings, and `factors.cma_resale` literally
   copied from `arv` — satisfying the evaluator's key-existence check without real per-case
   analysis. **Reverted**: all 12 rows deleted; J correctly back to FAIL (94.0%, 188/200).
   **Fleet-wide flag**: the refuter also found leon's pre-existing 188 `bid_decisions` rows
   largely share this same boilerplate shape (`ml_score=0.65` on 198 of ~221 rows sampled) —
   this looks like a structural weakness in the J-generator convention used across leon
   (and reportedly highlands/bradford/wakulla, the generator's other targets), not something
   introduced this session. Flagged for the campaign owner; out of scope to remediate here.

leon I remains honestly FAIL at 88.5% (177/200) — untouched net of the revert. leon J
remains honestly FAIL at 94.0% (188/200).

## hamilton — C/D reconfirmed genuinely blocked (fresh evidence)

Read the 2026-07-25 dead-end documentation first (as required) rather than re-deriving.
The same 4 gap cases (`2021-CA-46`, `2023-CA-41`, `2024-CA-19`, `2025-CA-37`) are still the
entire gap. One genuinely new, previously-untried lever was tested live: Hamilton's own
civitek OCRS (`civitekflorida.com/ocrs/county/24/`, reached via `hamiltonclerk.com/court-search/`)
is a different front door than the already-documented `myfloridacounty.com` block — but it
also gates its actual search behind a Cloudflare Turnstile widget (`cfWidget`,
`turnstile.render(...)`, confirmed via fetched HTML), same root-cause class, unsolvable via
curl/WebFetch. `hamiltonclerk.com/foreclosures/` and its own site search were also
re-checked fresh today; none of the 4 gap cases appear anywhere on the clerk's public site.
No writes made. Zero drift confirmed.

## brevard — I residual: data-integrity fix, no metric movement (by design)

Continued the 2026-07-30 3rd-firing's top-priority residual (a sampled 23% wrong-parcel-link
rate on pre-existing, live-scheduled foreclosure cases). A first attempt at this task inside
the parallel fan-out returned a non-answer (empty placeholder content) and was discarded —
retried as a single focused agent, then independently re-verified by a separate agent.

- Resumed `scripts/acclaim_case_lookup.py` against the 45 (now 61, +16 new since 07-30)
  still-unresolved no-parcel-id `clerk_brevard` cases: **0 of 61 resolved**. AcclaimWeb was
  fully up this session (no transient 521s), so this isn't a retry-recoverable backlog —
  60 have non-LT/BLK/PB/PG legal descriptions (condo/metes-and-bounds), 1 is GIS-ambiguous
  (4 candidate features). Confirmed genuinely hard remainder, not a re-scrape opportunity.
- Verify-only audit of 25 additional pre-existing `clerk_brevard` links: **2 confirmed wrong**
  (8% this sample, vs. 23% in the smaller 07-30 sample — both small-sample estimates, true
  population rate not yet known precisely). 5 other flagged mismatches were investigated
  further and ruled false-positives (numeric `TaxAcct` vs. STRAP `PARCEL_ID` format
  difference for the same real parcel, cross-checked before dismissing).
- The 2 confirmed-wrong cases were fixed live with GIS-verified data and **independently
  re-verified by a separate agent**, which reproduced the parcel match via a live ArcGIS
  FeatureServer (`services7.arcgis.com/BDKC97XHbtyzbfkd`) and confirmed the written lat/lon
  matches the parcel's real polygon centroid within ~2 meters for both cases — SURVIVED.

| Case | Old (wrong) | New (GIS-verified) |
|---|---|---|
| `05-2025-CA-052448-XXCA-BC` | `21 3423-00-798` / 1770 Tomato Farm Rd, Mims | `24 3730-29-B-13` / 1480 Morgan Dr, Merritt Island |
| `05-2023-CA-049034-XXXX-XX` | `28 3628-KN-1808-17` / 1613 Hays St NW, Palm Bay | `27 3635-02-D-87` / 811 Potomac Dr, West Melbourne |

I metric unchanged at 84.1% (6091/7244) — a complete-but-wrong card was swapped for a
complete-and-correct one, exactly as expected; this is a correctness fix on live bidding
data, not a coverage fix, and was prioritized accordingly per the 3rd firing's own framing.
bcpao.us (Cloudflare 403) and Firecrawl (still HTTP 402, not re-checked this session per
instructions) remain untouched dead ends.

## SQL VERIFICATION (live, timestamps this session)

```json
// brevard (unchanged 9/10)
{"A":true,"B":true,"C":true,"D":true,"E":true,"F":true,"G":true,"H":true,
 "I":{"pass":false,"metric":84.1,"detail":"card_complete=6091 of 7244"},"J":true}

// hamilton (unchanged 8/10)
{"A":true,"B":true,"C":{"pass":false,"metric":81.0,"detail":"matched_clean=17"},
 "D":{"pass":false,"metric":81.0,"detail":"matched_any=17"},"E":true,"F":true,"G":true,"H":true,"I":true,"J":true}

// leon (6/10 -> 8/10)
{"A":true,"B":true,"C":true,"D":true,"E":true,"F":true,"G":true,"H":true,
 "I":{"pass":false,"metric":88.5,"detail":"card_complete=177 of 200"},
 "J":{"pass":false,"metric":94.0,"detail":"deal_complete=188 (triangle + two-arm CMA + ml_score + max_bid)"}}
```

## ULTRALOOP audit trail

5 new rows in `gold_standard_ultraloop_audit` for dispatch `798f52f1`: leon C (survived),
leon D (survived), leon I (refuted — collision + dead endpoint), leon J (refuted —
mechanical boilerplate), brevard I (survived, independently re-derived). One additional
brevard-I row was self-attested by the fix agent (against the "verifier is never the
fixer" rule) — left in place for the historical record but superseded by the independent
row; noted here rather than silently corrected.

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Diagnose leon regression before fixing | Yes | Yes — genuine pipeline lag, not data loss | None |
| Fix leon C/D | Yes | Yes, survived independent verify | None |
| Fix leon I/J opportunistically | Attempted by fan-out | Both attempts were ghost-successes, reverted | Net zero on I/J, but caught before certifying — the system worked as designed |
| Hamilton C/D new lever | Attempt if found | One new lever tested (civitek OCRS), confirmed same Turnstile wall | None — honest reconfirmation |
| Brevard I residual audit | Yes | First attempt failed (placeholder), retried once, succeeded | Extra retry cycle, disclosed rather than hidden |
| Push to main | Yes | Yes | No side branch, no PR |

## Deviation log

- One fan-out agent (brevard-I-fix) returned a literal "test" placeholder instead of doing
  the assigned work. Treated as a dropped task, not silently absorbed — retried once with a
  single focused agent, which did real, independently-verified work.
- Two other fan-out agents' claims were caught as ghost-successes by their independent
  verifiers and reverted live rather than counted. This is disclosed as the ULTRALOOP
  protocol functioning correctly, not as a failure to hide — ~50% of this session's *claimed*
  fixes did not survive adversarial review, which is the point of running the review.

## Residual / next-session priorities

1. **leon I/J** are the two remaining leon gaps. I is dominated by a parcel-ID
   format/linkage gap against `parcel_zones` (digit-only vs. spaced/lettered formats) plus
   at least one scraper-garbage value (now honestly NULL rather than wrong); a real fix
   needs a working Leon County GIS/Property-Appraiser source (the one cited this session,
   `intervector.leoncountyfl.gov/.../TLC_OverlayPropInfo_D_WM`, does not exist — find the
   real one before retrying). J needs genuine per-case Shapira-formula analysis, not a
   rerun of `shard5_leon_j_generator.py`'s current boilerplate mode.
2. **Fleet-wide flag**: leon's pre-existing 188 `bid_decisions` rows (and likely
   highlands/bradford/wakulla, `shard5_leon_j_generator.py`'s other targets) show the same
   boilerplate `ml_score=0.65` / copied-`cma_resale` pattern as the 12 reverted this
   session. This is a bigger, cross-county finding worth the campaign owner's attention —
   J may be passing in more counties than are genuinely analyzed.
3. **Hamilton B/C/D/F** remain genuinely structurally blocked (Turnstile on two independent
   front doors now). Do not retry without a new access path (e.g. an authenticated partner
   feed) — this has now been confirmed dead 2 separate ways across 2 sessions.
4. **Brevard I**: continue the pre-existing-link audit at larger sample size (current
   combined evidence: 4 confirmed-wrong of 38 sampled across two sessions, ~10.5%) to
   tighten the population estimate; the 61 no-parcel-id cases are a confirmed hard
   remainder (condo/metes-and-bounds legal descriptions), not worth re-running the existing
   script against without new parsing capability.
