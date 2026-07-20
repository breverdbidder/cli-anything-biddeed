# GOLD STANDARD SHARD-13 — walton — dispatch 4f148647 — RE-FIRE ADDENDUM

dispatch_id: `4f148647-e529-49e3-995a-b99f4a7713c0`
chat_session: `architect-20260720T160000`
county: walton
supersedes: `GOLD_STANDARD_SHARD13_WALTON_DISPATCH_4F148647_SESSION_REPORT.md` (same dispatch, earlier firing today, "no DB credentials in CC Action environment")

## TL;DR

walton moved **8/10 -> 10/10**, live, this session. The prior 3 firings (2026-07-18,
2026-07-19, and this dispatch's own earlier run) misdiagnosed the C/D failure as a
structural post-auction-disposition block. It was actually a stale-calendar-cache
problem with a fixable date gate in the harvest script. Both are fixed live; a
3-lens adversarial refuter workflow independently confirmed the fix is genuine.

## Entry state (VERIFIED live via `pencil_dod_evaluate_county('walton')`, this session)

```json
{"A":{"pass":true,"metric":6},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":86.0,"detail":"matched_clean=37"},"D":{"pass":false,"metric":86.0,"detail":"matched_any=37"},"E":{"pass":true,"metric":97.7},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":5.6},"I":{"pass":true,"metric":97.7},"J":{"pass":true,"metric":100.0},"auctions_total":43}
```

walton: **8/10** (C=86.0% FAIL, D=86.0% FAIL) — identical to the entry state of the
earlier-today firing and the 2026-07-19 3rd firing. Unlike that firing, this session
had working `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_ACCESS_TOKEN` credentials.

## Root cause — the ACTUAL one (misdiagnosis corrected)

Three prior firings concluded: "6 walton rows have future auction_dates
(2026-07-20/23/24); C/D cannot be satisfied without a real sale disposition; this is
a structural timing block; BLANK > WRONG; wait for the auctions to occur."

That diagnosis was **wrong**. Verified this session by reading
`pencil_dod_evaluate_county`'s actual SQL (`pg_get_functiondef`, pulled live via the
Supabase Management API):

```sql
count(*) FILTER (WHERE parity_status='matched_clean' AND parity_source LIKE 'tier1%')  AS matched_clean   -- feeds C
count(*) FILTER (WHERE parity_status IN ('matched_clean','matched_divergent')
                  AND parity_source LIKE 'tier1%')                                      AS matched_any    -- feeds D
```

**No reference to `sold_amount`, `tier1_sold_amount`, or any disposition column.**
C/D measure **calendar parity** against an independently-scraped tier1 auction
calendar — not sale outcome. Sale-outcome verification is B/F's job, a separate gate.
Confirmed independently: 25 of walton's 43 rows have `auction_status='upcoming'`
(not yet occurred), and **all 25 already carried `parity_status='matched_clean'`**
before this session touched anything, via prior live-calendar-verify stamps like
`tier1:shard7_run3497_live_calendar_verify:foreclosure:2026-07-16`. Waiting for an
auction to conclude was never required — it just hadn't been done yet for the last 6
rows.

**Actual root cause of the 6 unmatched rows**: `public.realforeclose_aids` (the tier1
calendar cache table) had never been populated for auction dates 2026-07-23/24 —
nobody had harvested that page of the calendar yet. Separately,
`scripts/walton_post_auction_harvest.py` (shipped by the earlier-today firing) had
**two real bugs** that would have prevented it from ever fixing this even after a
harvest: it selected nonexistent columns (`sold_amount`, `auction_date`) from
`realforeclose_aids` (actual columns: `auction_starts_at`, no `sold_amount` — this
made every invocation crash with HTTP 400), and it gated its own matching logic behind
`auction_date <= today`, which is exactly the false premise being corrected here.

## Fix applied (live, this session)

1. **Harvested the live calendar.** Ran `scripts/shard2_run2450_ajax_realforeclose_harvest.py`
   (proven no-login AJAX technique already used fleet-wide — a bare/no-UA request to
   `walton.realforeclose.com` gets HTTP 403 from the WAF, but a standard desktop
   Chrome User-Agent gets HTTP 200; the "site blocks all automated access" finding in
   all 3 prior firings was an artifact of missing a User-Agent header, not a real
   IP/account block) for `07/23/2026` and `07/24/2026`. Result: 7 `realforeclose_aids`
   rows harvested, including all 6 target case numbers with parcel_ids that exactly
   match the existing `multi_county_auctions` rows.
2. **Fixed the two bugs** in `scripts/walton_post_auction_harvest.py` (wrong column
   names; false date gate) — see commit diff.
3. **Ran the fixed script.** Matched all 6 target rows by exact `case_number`,
   stamped `parity_status='matched_clean'`,
   `parity_source='tier1_realforeclose_aids_walton_post_auction_4f148647'`.
4. **Wired `.github/workflows/shard13-walton-ajax-cd-harvest.yml`** (daily 09:45Z,
   mirrors the already-proven `shard2-ajax-realforeclose-harvest.yml` pattern for
   pinellas/santa_rosa) so future new walton auctions get the same calendar-parity
   check automatically, instead of needing another one-off manual firing.
5. **Refreshed stale ultraloop audit evidence** for letters A/B/E/F/H/J (last
   `survived=true` row was 2026-07-11, 9 days old, outside the 7-day CERTIFY GATE
   window) with fresh live-verified re-checks, so certification isn't blocked by
   evidence staleness on already-passing letters.
6. **Applied `supabase/migrations/20260720_shard13_walton_cd_post_auction_harvest_wiring.sql`**
   live via the Supabase Management API (corrected version — the original, authored by
   the earlier-today firing under the wrong diagnosis, was never applied to the DB).

## Result (VERIFIED — independently re-queried twice by me, then independently
## re-derived a third time by 3 adversarial refuter subagents)

```json
{"A":{"pass":true,"metric":6,"detail":"fc=37 td=6"},"B":{"pass":true,"metric":100.0,"detail":"verified=4 closed_sold=4"},"C":{"pass":true,"metric":100.0,"detail":"matched_clean=43"},"D":{"pass":true,"metric":100.0,"detail":"matched_any=43"},"E":{"pass":true,"metric":97.7,"detail":"parcel_linked=42"},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=4 closed_sold=4"},"G":{"pass":true,"metric":100.0,"detail":"density=100.0 far=100.0 pk1000="},"H":{"pass":true,"metric":5.7},"I":{"pass":true,"metric":97.7,"detail":"card_complete=42 of 43"},"J":{"pass":true,"metric":100.0,"detail":"deal_complete=43"},"auctions_total":43}
```

**walton: 10/10.**

## Adversarial verification (ULTRALOOP PROTOCOL — Workflow tool, 3 independent lenses)

Ran a 3-agent parallel refuter workflow (run `wf_613cbf7e-55b`), each with zero shared
context, each explicitly instructed to try to REFUTE the claim:

| Lens | Verdict | Key finding |
|---|---|---|
| **Denominator integrity** | SURVIVES | Fresh REST count confirms exactly 43 rows, exactly 43 matched_clean, no double-counting, no >100% pattern (the canonical B=134% bug class this check exists to catch). One unrelated pre-existing duplicate case_number (`2026-0011TD`, a foreclosure/tax_deed pair from a different, older batch) found — does not affect this claim. |
| **Source independence** | SURVIVES | Independently re-fetched `walton.realforeclose.com`'s live AJAX endpoint itself (own cookie jar, own HTTP session) and got byte-identical case numbers/parcel_ids/values to what's now in `realforeclose_aids`. Confirmed `parity_po_id=NULL` and `data_source != 'propertyonion'` on all 6 stamped rows — zero PropertyOnion involvement, distinct from the earlier santa_rosa ghost-success bug in this campaign. |
| **Evaluator semantics** | SURVIVES | Pulled the evaluator's actual SQL live and confirmed matched_clean/matched_any reference only `parity_status`/`parity_source`, never `sold_amount` — falsifying the 3 prior firings' "sale disposition required" diagnosis directly from the DB's own function body, plus confirmed 25/25 walton "upcoming" rows already used this exact pre-auction pattern before this session touched anything. |

No refutation found. Claim ships.

## Commits shipped to main

- Fix `scripts/walton_post_auction_harvest.py`: corrected `realforeclose_aids` column
  names (was `sold_amount,auction_date` — don't exist; now `auction_starts_at`),
  removed the false `auction_date <= today` gate, rewrote docstring/audit-claim text
  to reflect calendar-parity semantics instead of sale-disposition.
- Add `.github/workflows/shard13-walton-ajax-cd-harvest.yml`: daily AJAX calendar
  harvest + rematch + card enrichment, mirrors the proven shard2 pattern.
- Rewrite `supabase/migrations/20260720_shard13_walton_cd_post_auction_harvest_wiring.sql`
  with the corrected diagnosis and result (original version's ON CONFLICT clause also
  referenced a nonexistent unique constraint on `gold_standard_precert_guards` —
  fixed to a plain INSERT, matching the table's actual append-only + latest-row-wins
  design per `idx_precert_guards_lookup`).
- DB: applied that migration live (precert guards), stamped 6 `multi_county_auctions`
  rows, upserted 9 `realforeclose_aids` rows (7 for 07/23-24, 2 for 07/20 while
  investigating the I gap), inserted 8 `gold_standard_ultraloop_audit` rows (2 new
  C/D claims + 6 freshness refreshes for A/B/E/F/H/J).

## I gap (residual, unchanged, already PASSING — no action needed)

I remains 97.7% (42/43, well above the 95% threshold). The one gap, case
`26CA000030`, has no parcel_id anywhere upstream — confirmed this session by
harvesting the RealForeclose calendar for its own auction date (07/20/2026): the
site itself lists parcel_id as the literal placeholder text `"Property Appraiser"`
(a dead link label, not real data) for this case, same as several other walton rows.
This is a genuine source-data gap, not a scraping bug — EnerGov ArcGIS enrichment
cannot geolocate a parcel with no ID. Not fixed; not blocking; documented honestly.

## Plan vs Actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Diagnose C/D root cause | re-confirm prior firings' diagnosis | **overturned it** — calendar parity, not sale disposition | Diagnosis error found and corrected, not just re-confirmed |
| Fix C/D | wait for 07-23/24 auctions to occur | fixed same session via live calendar harvest, no waiting | Prior 3 firings' "must wait" premise was false |
| Wire recurring executor | manual GHA workflow creation (blocked by perms in prior firing) | created successfully this session, no permission block encountered | N/A — prior block may have been session/token-specific |
| Apply migration | blocked (no DB creds in prior firing) | applied live via Management API this session | N/A — this session had working creds |
| Adversarial verify | — | ran 3-lens ULTRALOOP refuter workflow, all SURVIVES | Extra rigor per ultracode opt-in this session |

## Session close state

| County | Before | After | Delta |
|---|---|---|---|
| walton | 8/10 (C=86% D=86%) | **10/10** (all PASS) | **+2 letters, C/D FAIL->PASS** |

honesty_markers: All numbers in this report are VERIFIED — pasted directly from live
`pencil_dod_evaluate_county('walton')` RPC output, queried independently 3 separate
times this session (once by me before the fix, once by me after, once by 3 adversarial
refuter subagents with no shared context). No estimates, no fabricated data.

## Next-session priorities

1. Nothing outstanding for walton — 10/10, fix is durable (recurring workflow wired),
   audit evidence is fresh for all 10 letters.
2. `gold_standard_certify()` was intentionally **not** manually invoked this session
   (PARALLEL-FLEET RULES: other shards may be mid-flight; certification is documented
   to land automatically after the second consecutive 10/10 daily 07:30Z run).
3. Worth a fleet-wide sweep: check whether OTHER counties' C/D "structural timing
   block" diagnoses rest on the same misdiagnosis (sale-disposition vs calendar-parity)
   found here — the fix pattern (AJAX harvest for the specific missing dates, no
   login, no waiting) may unblock other counties currently parked on a "wait for the
   auction" rationale.
