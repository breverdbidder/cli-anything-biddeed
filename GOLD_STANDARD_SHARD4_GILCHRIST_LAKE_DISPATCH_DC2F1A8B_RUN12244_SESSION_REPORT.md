# Gold Standard shard-4: gilchrist + lake (dispatch `dc2f1a8b-a8cf-4a0f-babc-5517f05c86ef`, loop run 12244)

Session: architect-20260817T160000, headless, no human in loop. Mode: manual diagnose (gilchrist,
run_parity.py root cause, comp methodology review) + one native ULTRALOOP Workflow pass (lake G/J
diagnose, adversarial verify) via the Workflow tool.

## Result summary

One real, verified fix shipped (lake C, a caught regression). One shippable dead-end correctly
avoided (lake G — a plausible-looking source was adversarially refuted before it could be written).
One near-miss correctly declined (lake J — real new comp data found and verified, but a follow-up
methodology review judged it insufficient to write to a live bid-decision table). One shared-pipeline
bug precisely root-caused (not fixed — genuinely out of scope for a single-county session). Gilchrist
independently re-confirmed as a genuine, unchanged structural ceiling.

```
BEFORE (session start, live pencil_dod_evaluate_county):
  gilchrist: 8/10 — E FAIL 78.6% (parcel_linked=11 of 14), I FAIL 78.6% (card_complete=11 of 14)
  lake:      5/10 — C FAIL 89.2% (matched_clean=116), E FAIL 92.3%, G FAIL 50.0% (pk1000 binding),
                     I FAIL 92.3%, J FAIL 91.5%

AFTER (session end, live re-query):
  gilchrist: 8/10 — E FAIL 78.6%, I FAIL 78.6% — unchanged, genuine ceiling
  lake:      5/10 — C FAIL 90.0% (matched_clean=117, +1 row, live regression caught+fixed),
                     E/G/I/J unchanged (all near-misses correctly declined, see below)
```

## gilchrist (8/10, unchanged) — reconfirmed dead end with fresh evidence

Before doing any new work, re-derived the two blockers independently rather than trusting the last
5+ sessions' reports at face value:
- `gis1.hcpao.org`: `HTTP 000` (connection failure) on both `https://` and `http://`, 15s timeout —
  still unreachable from this sandbox.
- Gilchrist county's own domains (`gilchrist.fl.us`, `gilchristpa.com`, `gilchristcountypa.com`):
  all `HTTP 000`/403 — confirms the block is the whole county's web presence from this sandbox, not
  one specific endpoint.
- Wayback Machine CDX search for all 3 remaining unlinked case numbers
  (`212025CA000033CAAXMX`, `212025CA000043CAAXMX`, `212025CA000070CAAXMX`) and for
  `qpublic.schneidercorp.com`/gilchrist: zero snapshots exist anywhere in the archive.
- Firecrawl: `remainingCredits: -13` of 1000 (still exhausted, independently re-checked).

Same 3 cases block both E and I (E ⊆ I structurally — I additionally requires zoning linkage, moot
here since these 3 have no parcel_id at all). New for this session: captured the 3 cases' owner
names from `multi_county_auctions` (`Chad Slocum`; `Danielle Jay Mercado`; `Raya C. Hutchinson`) —
not previously recorded in a report — as a concrete lever for a future session once GIS/Firecrawl
connectivity is restored (owner-name search, not case-number search, is the only path these 3
sites support). Zero writes.

## lake (5/10, C moved within-FAIL) — 1 fix shipped, 2 real near-misses correctly declined

### C (89.2% → 90.0%) — caught and fixed a live regression

Live-queried `foreclosurecalendar.lakecountyclerkfl.gov` before touching anything. Case
`2024CA000186` carries two calendar entries: `id=20442` (old, "Canceled Per Judge", 08/18 sale) and
`id=20584` (new, not cancelled, rescheduled — confirmed live, `WHEN: Tuesday, December 8, 2026`).
This is the exact staleness bug diagnosed 2026-08-13 and fixed again 2026-08-16 — and it had been
silently **re-broken a third time** by an automated `run_parity.py` run between then and this
session (see root-cause section below). Re-patched via PostgREST:
`auction_status: CANCELLED→scheduled, auction_date: 2026-08-18→2026-12-08,
parity_status: CLERK_SSOT_CANCELLED→CLERK_VERIFIED, parity_source→manual_recheck_20260817`.
Verified live: `matched_clean` 116→117, C metric 89.2%→90.0%. Still FAIL — the remaining 13
`CLERK_SSOT_CANCELLED` rows are a separately-reconfirmed genuine ceiling (7 still show cancelled
live, 6 aged off with zero reschedule evidence), unchanged from the 2026-08-16 finding.

### Root cause of the recurring C regression — diagnosed precisely, not fixed (shared script)

Ran a native ULTRALOOP Workflow pass (Diagnose → adversarial Verify) with 3 parallel diagnose
agents; one targeted this exact bug in `scripts/clerk_ssot/run_parity.py`. Both the diagnose agent
and its independent verifier read the raw file from scratch and reproduced identical findings:

1. The `clean_matches` UPDATE (lines 354–362) has `WHERE ... AND m.parity_status IS DISTINCT FROM
   'CLERK_SSOT_CANCELLED'` — this blocks the update from ever applying to a row currently marked
   `CLERK_SSOT_CANCELLED` by a prior run, even when the *current* run's SSOT fetch has already
   routed that same row into `clean_matches` (i.e., confirmed not-cancelled this run).
2. Even without that guard, the `clean_matches` UPDATE's `SET` clause (`parity_status='PARITY_OK',
   parity_source=..., auction_date=...`) never assigns `auction_status` at all — in contrast to the
   `cancelled_mismatch` UPDATE (line 340) which explicitly sets `auction_status='CANCELLED'`. So a
   row that was ever cancelled stays `auction_status='CANCELLED'` forever, regardless of the guard.

Both bugs compound to produce exactly the observed symptom (a legitimately-rescheduled case stays
permanently stuck as cancelled once any run marks it so). **Not fixed this session** — this is a
shared script whose `clean_matches`/`cancelled_mismatch` logic runs for 9 counties' parity checks;
a fix belongs to its own dedicated review, per the same scope boundary 2+ prior sessions (2026-08-13,
2026-08-16) already drew. Minimal correct fix for that future review: drop the line-361 guard (or
narrow it to rows the *current* SSOT fetch still reports cancelled) and add `auction_status=
'scheduled'` to the `clean_matches` SET clause.

### G (50.0%, unchanged FAIL) — a plausible source was found and adversarially refuted before shipping

The diagnose agent found a genuinely new channel — `r.jina.ai`, a reader proxy that server-renders
Municode's JS-SPA (342,636 bytes of real content vs. the ~2-6KB shell every direct curl/Wayback
attempt returns, reproduced byte-identical on a second independent fetch) — and quoted a real,
verbatim ratio for "Retail, general": 1 space / 250 sq ft GLA (= 4/1,000 sq ft). The adversarial
verifier independently re-fetched the same URL and confirmed the quoted text is genuinely present,
but caught a citation error: that ratio table actually lives in **Sec. 25-361**, not the claimed
Sec. 25-358 (which is procedural-only and ends before the table starts), and the cited C-1-
applicability language was misattributed to a *different*, corridor-limited section (25-360,
architectural design standards) rather than the actual parking article. Per ULTRALOOP protocol, a
refuted claim is a false positive — not counted, not shipped. **Zero writes.** Genuine forward
progress for a future session regardless: the correct section to verify C-1 applicability against
is now known to be Sec. 25-361 (whose own applicability clause reads "citywide... except CBD" —
plausibly still covers C-1, but that specific chain was not independently re-verified this session
and should not be assumed).

### J (91.5%, unchanged FAIL) — real new comp data found, verified, and correctly not shipped

Sourced 3 genuine, non-subject comparable sales for the one J-eligible gap case (`2025CA001392`,
110 S Chester St, Leesburg) from the FL DOR/GIO Statewide Cadastral ArcGIS FeatureServer (the same
endpoint this repo's `scripts/ingest_county.py` already relies on): 104 N Chester St ($218,000,
Feb 2024, 1,140 sf, built 1952, qualified sale, ~140m away); 1807/1809 W Main St ($265,000 each,
May 2024, 1,384 sf, built 2023, ~49-58m away). An adversarial verifier independently re-queried the
same service and reproduced every field verbatim, plus independently computed haversine distances
confirming all 3 sit within the claimed radius — the comp *facts* survive.

A follow-up methodology review (a second, skeptical agent, not the one that found the comps) was
run before writing anything to `bid_decisions`, because the existing repo pattern for this exact
letter (`scripts/lake_j_generator_shard2_*.py`) computes `cma_distressed`/`cma_resale` as fixed
percentages of `arv`, where `arv` itself is just the subject's own `assessed_value` — precisely the
single-value-pass-through fabrication a 2026-08-16 session for this same row already caught and
declined. Verdict: **DO_NOT_SHIP**. Extrapolating an ARV from a single age-appropriate comp via raw
price-per-sqft, then deriving `cma_distressed` as a fixed discount off that same figure, is one
data point wearing two `factors` keys — it satisfies the pipeline's `cma_distressed`+`cma_resale`
contract in form but not in substance. **Zero writes to `bid_decisions`.** Real, useful progress
for a future session: 3 verified comps now exist (there were none before); what's still missing is
2+ more resale comps in the right age band and at least one independent distressed/REO comp before
a defensible two-arm CMA can be written.

### E (92.3%, unchanged FAIL) — not re-investigated this session (unchanged since 2026-08-16, same
10-row ceiling blocking both E and I: owner-name-only rows, 0/10 unique ArcGIS matches, needs
JS-capable browser automation of a gated clerk portal — no new lever available this session).

### D, F, H — unchanged PASS, no action needed.

## ULTRALOOP audit ledger (`gold_standard_ultraloop_audit`, dispatch `dc2f1a8b`)

| county | letter | claim | survived |
|---|---|---|---|
| lake | C | case 2024CA000186 regression fix (self-verified) | true |
| lake | G | Leesburg Sec. 25-358 parking ratio | **false** — section misattribution, refuted |
| lake | J | 3 comp sales for 2025CA001392 | true (facts) — shipping separately declined, see report |
| lake | C | run_parity.py clean_matches root cause (diagnosis only) | true |
| gilchrist | E | 3-case structural ceiling, fresh re-verification | true |

5 rows written, ids 16364–16368. 6 subagents run via the Workflow tool (`ultraloop_mode='native'`
for the workflow-run claims), 390,805 tokens, 105 tool calls.

## Files changed this session

None (no script/schema files). All DB writes were row-level PATCH/POST through PostgREST
(`multi_county_auctions` 1 row, `gold_standard_ultraloop_audit` 5 rows, `gold_standard_campaign` 1
row) — no migration needed per guardrail 3.

### SQL VERIFICATION

```sql
SELECT public.pencil_dod_evaluate_county('gilchrist');
-- 8/10, E FAIL 78.6 (parcel_linked=11 of 14), I FAIL 78.6 (card_complete=11 of 14) -- identical to session start

SELECT public.pencil_dod_evaluate_county('lake');
-- 5/10, C FAIL 90.0 (matched_clean=117, was 116) -- C metric moved, all others unchanged

SELECT case_number, auction_status, auction_date, parity_status, parity_source
FROM multi_county_auctions WHERE county='lake' AND case_number='2024CA000186';
-- scheduled, 2026-12-08, CLERK_VERIFIED, manual_recheck_20260817 -- confirmed live
```
Timestamp UTC: 2026-08-17T22:53Z.

## Scope note

Gilchrist + lake only, per shard-4 assignment. Confirmed via `gold_standard_campaign` that 3 other
shards (alachua/miami_dade, brevard/bradford/liberty/union, madison) were mid-flight at the same
launch timestamp — `gold_standard_loop()`/`gold_standard_certify()` were **not** run, per
PARALLEL-FLEET RULES; per-county `pencil_dod_evaluate_county` used throughout instead. No cron jobs
touched. `scripts/clerk_ssot/run_parity.py` was read but not modified (see root-cause section).

## Next-session priorities

1. **lake G**: verify Sec. 25-361's actual applicability to C-1 specifically (its own clause reads
   "citywide... except CBD" — plausible but not independently confirmed this session) before
   writing the 4/1,000 sq ft ratio. The `r.jina.ai` reader-proxy channel is a real, working,
   previously-untried way to get real content out of Municode's JS-SPA — reusable for other
   Municode-blocked counties too.
2. **lake J**: 3 verified comps exist for `2025CA001392`; need 2+ more age-appropriate resale
   comps and at least 1 independent distressed/REO comp before the two-arm CMA is defensible.
3. **lake C's shared root cause**: `run_parity.py`'s `clean_matches` UPDATE needs the guard
   narrowed and `auction_status` added to its SET clause (exact lines and fix identified above) —
   a dedicated 9-county-impact review, not a single-shard session.
4. **gilchrist E/I**: still blocked on sandbox connectivity (GIS + county domains unreachable) and
   exhausted Firecrawl credits — re-check once either is restored. Owner names for the 3 remaining
   cases are now on record for that session to use directly.

---
dispatch_id: dc2f1a8b-a8cf-4a0f-babc-5517f05c86ef

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
