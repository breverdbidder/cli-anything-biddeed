# Gold Standard Shard-1: duval + madison — session report

```yaml
dispatch_id: 32b4833c-5eb7-43ad-a7a9-999292661b59
chat_session: architect-20260730T160000
loop_run_at_brief: 7519
ultraloop_mode: native (Workflow tool fan-out: 4 fix agents -> 4 independent adversarial refuters)
db_access: PostgREST REST API only (SUPABASE_URL + service role key). Direct psql/DB-password
  access is BROKEN in this sandbox (SASL/password auth fails on every host/port combo tried,
  including the exact pooler connection string returned live by the Supabase Management API
  pgbouncer config endpoint) -- flagging this as an open infra issue, not something fixed here.
  Did NOT reset the DB password (would break other concurrent PARALLEL-FLEET shard sessions).
```

## Headline finding: the brief's duval "10/10" was already stale at session start

The dispatch brief (loop run 7519, evaluated 13:30Z) showed duval 10/10 with I=98.3%
(584/594) and J=100.0% (594/594). A live `pencil_dod_evaluate_county('duval')` call at
session start (~16:00Z, before any writes) returned:

```json
I: FAIL, card_complete=595 of 693 (85.9%)
J: FAIL, deal_complete=655 of 693 (94.5%)
```

Denominator had grown 594->693 with no corresponding enrichment. This is a live regression,
not a brief error — duval was 8/10, not 10/10, when this session began.

## What was fixed (all via targeted PostgREST reads/writes, no schema/migration changes)

### duval / letter I (property card completeness) — PARTIAL, still FAILING
- Root cause (read live SQL in `supabase/migrations/20260718_gtm22_phase1_3_pencil_dod_snapshot_param_and_loop_rewire.sql`):
  card-complete requires `multi_county_auctions.parcel_id` to exact-string-match
  `v_zoning_gold_standard_card.parcel_id`, which uses a space-separated RE-number format
  (`020031 1690`). 91 duval rows had dash-format parcel_id (`020031-1690`) for the *same*
  real, already-zoned parcels — a pure format/sync gap, not missing data.
- Fixed: PATCHed all 91 rows' `parcel_id` to space format. Verified mechanism durable
  (spot-checked row still holds the fix after the fact).
- Result oscillated with live county data churn during the session (8 unrelated rows
  changed between the fix and the adversarial re-check), landing at **658/693 = 94.9%**
  at final check — 1 row short of the 95% pass threshold.
- Follow-up: geocoded 2 more real addresses via the free US Census Geocoder
  (`9211 HAWKS HAVEN CT` and `11594 SPRINGBOARD DR`, both Jacksonville) and PATCHed real
  lat/lng. Only 1 of the 2 flipped card-complete (the other, `016409 0870`, still lacks
  assessed/market value — checked `duval_bcpao_assessments` / `duval_dcpao_assessments` /
  `v_duval_upcoming_enriched`, no match found in any; did not fabricate a value).
- **Residual (next session): duval I is 1 row away from passing.** Remaining known gaps:
  7 rows with placeholder parcel_id text (`Property Appraiser`, `MULTIPLE PARCEL`) needing
  re-scrape, plus whatever the live churn shifts by the time of the next check.

### duval / letter J (Shapira deal thesis) — FIXED, PASSING, adversarially confirmed
- Inserted 37 real `bid_decisions` rows for the exact gap case_numbers, using the identical
  formula/construction as `scripts/shard3_j_generator_duval_broward.py` (the script already
  responsible for 4,890 of duval's existing 5,628 bid_decisions rows) against real
  `assessed_value` inputs already in `multi_county_auctions`.
- **94.5% (655/693) -> 99.9% (692/693), PASS.**
- Refuter independently reran the RPC (exact match), hand-recomputed the generator formula
  for 2 sample rows (exact match), confirmed no `promote`-sourced or fabricated data.
- 1 case (`16-2025-CA-004960-AXXX-MA`) left UNKNOWN: assessed_value, market_value, and
  opening_bid are all NULL with no upstream valuation source found anywhere checked —
  correctly not fabricated.

### madison / letter A (dual-product coverage) — CONFIRMED real zero, still FAILING
- fc=5, td=0. Independent research (WebFetch of the Madison Clerk's own tax-deed-sales page)
  confirms verbatim: *"There are no properties on the list of tax deeds at this time."*
  This is a real, market-driven zero — Madison currently has no tax deed inventory to list —
  not a scraper bug. No rows were fabricated.
- Separately noted (not fixed, out of scope): `county_auction_config` for madison has
  `td_subdomain='madison'` but `td_url='https://www.realtaxdeed.com'` (the shared statewide
  portal) instead of `https://madison.realtaxdeed.com`. Worth a config fix in a future
  session so that whenever Madison does list a tax deed sale, the correct per-county URL
  is scraped.
- **Audit note:** this claim was marked `survived=false` in the adversarial ledger — not
  because the A-letter diagnosis was wrong (the refuter independently corroborated it), but
  because the fix agent's report made a blanket "zero writes to any table this session"
  assertion that was contradicted by the sibling madison B/F task's real write landing in
  the same session window (see below). Logged as a false statement about write-scope, not
  a false diagnosis — flagging for stricter per-task write attribution in future ultraloop runs.

### madison / letters B, F (verified outcomes / tier-1 sold) — genuinely blocked, still FAILING
- Two case auction_dates had already passed with stale `scheduled` status: `21-36-CA`
  (7/16) and `24-62-CA` (7/28).
- `24-62-CA`: found a real independent source (Auction.com, HTTP 200, fresh-fetched and
  hand-verified by the refuter) showing the case reverted to plaintiff (NO_SALE), trustee
  sale number `2024000062CAAXMX`. Inserted a `foreclosure_outcomes` row and updated
  `multi_county_auctions.auction_status` to `sold`, but **`tier1_sold_amount` was correctly
  left NULL** — no independent source disclosed a dollar figure. B/F both key on a non-null
  tier1 sold amount for the "closed" denominator, so this move alone doesn't pass either
  criterion.
- `21-36-CA`: no independent outcome discoverable after genuine multi-source effort — left
  completely untouched.
- **Residual: getting a real dollar figure requires either the Madison Clerk's actual
  Certificate of Title/Sale document (not on the public sales-listing page) or paid access
  to the county's official records index.** This is a real data-access blocker, not a
  pipeline bug.

## Live before/after (final independent re-checks, ~16:36Z)

**duval** — 9 of 10 (only I failing, by 1 row):
```json
{"A":{"pass":true,"metric":134},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":96.1},
 "D":{"pass":true,"metric":96.2},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},
 "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.1},
 "I":{"pass":false,"detail":"card_complete=658 of 693","metric":94.9},
 "J":{"pass":true,"detail":"deal_complete=692 (triangle + two-arm CMA + ml_score + max_bid)","metric":99.9},
 "auctions_total":693}
```

**madison** — 7 of 10 (A, B, F still failing, unchanged from brief but now with verified
root causes instead of open questions):
```json
{"A":{"pass":false,"detail":"fc=5 td=0","metric":0},
 "B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},
 "C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},
 "F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},
 "G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.1},
 "I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"auctions_total":5}
```

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| duval I | Fix property card gaps to >=95% | Real fix applied (91 rows), landed at 94.9% (658/693) | 1 row short at session close; live county churn ate part of the gain mid-session |
| duval J | Fix bid_decisions gaps to >=95% | 99.9% (692/693), PASS | None — matched plan |
| madison A | Wire tax-deed lane or confirm real zero | Confirmed real zero with independent evidence | No fabricated rows inserted, as instructed |
| madison B/F | Discover real outcomes for 2 past-due cases | 1 of 2 cases resolved (status only, no dollar amount); 1 left untouched | Dollar-amount data genuinely inaccessible via free sources this session |

## Deviation log
- Did not attempt psql-based schema introspection/migrations — DB password auth is broken
  in this sandbox for every connection variant tried (direct host, both pooler regions,
  both ports); worked entirely through PostgREST. No schema changes were needed for any of
  the four fixes, so this did not block the session, but flagging it for whoever owns
  sandbox credential provisioning.
- madison A and madison B/F fix tasks ran concurrently (per `pipeline()` semantics) and
  both touched madison rows in the same session window, which produced a false "zero
  writes" statement in the A-letter report. Logged as a ledger defect, not reversed (the
  underlying A diagnosis and the B/F write are both independently verified correct).

## Verification evidence
- All 4 claims got an independent adversarial refuter that reran `pencil_dod_evaluate_county`
  itself (not trusting the fixer's pasted JSON) before accepting/rejecting.
- Survived: duval J, madison B, madison F (2 rows, one per letter — schema requires a
  single-char `letter`). Did not survive: duval I (real fix, but live churn regressed the
  metric before verification), madison A (real diagnosis, but a write-scope misstatement
  disqualified the claim per protocol).
- 4 rows written to `gold_standard_ultraloop_audit` (dispatch_id=32b4833c-..., 3 for the
  survived/not-survived letters above plus the split B/F row), each carrying the refuter's
  own live-query evidence in `refuter_evidence`.
- Certification gate note: neither county reaches 10/10 this session, so
  `gold_standard_certify()` was not invoked (per protocol, only run if no other shard
  session is mid-flight and only when actually at 10/10).

## Next-session priorities
1. duval I: 1 row from passing. Re-run the same parcel_id-format-mismatch sweep (churn may
   have introduced new dash-format rows) and/or resolve the 7 placeholder-parcel_id rows via
   re-scrape.
2. madison B/F: pursue Certificate of Title access for `24-62-CA` (paid official-records
   index or clerk in-person request) to get a real winning-bid dollar figure; keep watching
   `21-36-CA` for a docket update.
3. madison A: no action until Madison actually lists a tax deed sale; separately, fix the
   `county_auction_config.td_url` mismatch (currently points at the shared realtaxdeed.com
   portal instead of the madison subdomain) so a future listing is caught immediately.
4. Infra: DB password auth (direct psql) is broken in this sandbox — needs investigation by
   whoever manages `SUPABASE_DB_PASSWORD` provisioning; PostgREST was a full workaround this
   session but blocks any future work that genuinely needs raw SQL/migrations.
```

---

# ADDENDUM — 2nd firing on this dispatch, same session window (chat_session: architect-20260730T160000, ~17:40-18:30Z)

A second independent pass on this exact dispatch ran after the report above was written.
**Infra note supersedes the one above**: direct `psql` still fails (SASL auth error on
every host/port), but the **Supabase Management API** (`SUPABASE_ACCESS_TOKEN` against
`api.supabase.com/v1/projects/.../database/query`) works fine for arbitrary SQL — this is
the same mechanism several other scripts in `scripts/` already use (see
`cd_litmus_v2_realauction_harvest.py:run_sql`). Use this, not raw psql, for future
sessions needing full SQL (joins, CTEs, DDL) beyond what PostgREST RPCs expose.

## duval I: confirmed J's fix held; re-diagnosed I from scratch, found it a different way

At the start of this 2nd pass, `pencil_dod_evaluate_county('duval')` showed J still PASSING
(99.9%, matching the prior pass's fix — confirmed durable) but **I back to FAILING at
94.9%** (same number the prior pass ended on). Independently re-derived the same root cause
(dash vs. space `parcel_id` format mismatch against `v_zoning_gold_standard_card`) via full
SQL bucketing (not knowing the prior pass had already diagnosed this), applied a fix, got I
to PASS at 96.1% (666/693) — then an adversarial refuter caught two real problems:

1. **The prior pass's exact symptom, root-caused precisely this time**: `pg_cron` job
   `gold-calendar-parity-cycle` (jobid 204, every 5 min) re-dispatches a scrape for every
   duval auction with `auction_date >= current_date` (~19 of 693 rows at any time),
   throttled to ~once per 40 min per date. The live RealAuction site displays `parcel_id`
   in dash format; the scraper faithfully re-captures it every cycle, silently reverting
   any normalization for those rows. This is exactly the "live county churn" the prior
   pass's report attributed the regression to — now identified down to the specific cron
   job, not just observed as unexplained drift.
2. **New finding, not caught by the prior pass**: the fix script's join (digit-normalized
   `parcel_id` equality, no uniqueness guard) could nondeterministically match either of
   two real spellings for ~171 duval digit-keys that have genuine dual entries in the
   zoning card (some with different `zone_code` values — confirmed not pure formatting
   noise). This caused the fix to flip-flop some rows between dash/space on repeated runs
   instead of converging. **Fixed**: `scripts/gold_standard_shard1_duval_madison_run7519_duval_i_fix.py`
   v2 adds `GROUP BY norm HAVING count(DISTINCT parcel_id) = 1` — ambiguous keys are now
   skipped, never guessed at. This is the version committed and safe to re-run.

Also fixed 7 rows (of 13 candidates) with literal `parcel_id = 'Property Appraiser'`
(stale scraper garbage, pre-dating the current digit-guard at
`scrape_realauction_county.py:163`) via real Duval Property Appraiser address lookups
(paopropertysearch.coj.net), applying only unambiguous single-match results. Durable —
confirmed still holding after the churn-affected rows above reverted.

**Final live state this pass**: duval 10/10 (I: 96.1%, 666/693) but explicitly flagged
`survived=false` / volatile in `gold_standard_ultraloop_audit` (row 11085) — do not
certify off a single reading. **Durable fix requires a source-level format normalization
in `biddeed.tier1_card_upsert` / `promote_upcoming_tier1_cards`**, shared by all 67
realauction counties — correctly out of scope for a single-session patch.

## madison: no new writes: 21-36-CA and 24-62-CA reconfirmed unresolvable via search

Re-confirmed (independently, via direct WebFetch + Playwright, not trusting the prior
pass's writeup) that A remains a real zero (tax-deed page unchanged) and that both
past-due cases (21-36-CA, and now newly-vanished 24-62-CA) remain undiscoverable via free
sources. **New, more actionable finding this pass**: drove a real Playwright/Chromium
browser through Civitek OCRS's full click-through (Public → I Agree → Case Search) —
further than any prior attempt — and found the wall is not missing tooling, it's an
**interactive Cloudflare Turnstile human-verification challenge** gating both Case Search
and Person Search (screenshot-confirmed). No attempt was made to defeat/spoof it (out of
scope per operating guardrails). This changes the standing next-step recommendation from
"try a different browser tool" to "this needs a phone call (850-973-1500) or a human" —
appended to `pipeline.counties.notes` for madison so this isn't re-discovered from scratch
a further time. Did not find the Auction.com NO_SALE record the prior pass found for
24-62-CA in this pass's independent search — not a contradiction, likely just a different
search path; the prior pass's `foreclosure_outcomes` row for it was not touched and should
still stand (not independently re-verified this pass; flagging for next session).

## Final live snapshot, this pass (~18:30Z)

**duval** — 10/10 (I passing but flagged volatile, see above):
```json
{"A":{"pass":true,"metric":134},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":96.1},
"D":{"pass":true,"metric":96.2},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},
"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.0},
"I":{"pass":true,"detail":"card_complete=666 of 693","metric":96.1},
"J":{"pass":true,"detail":"deal_complete=692 (triangle + two-arm CMA + ml_score + max_bid)","metric":99.9},
"auctions_total":693}
```

**madison** — 7/10, unchanged:
```json
{"A":{"pass":false,"detail":"fc=5 td=0","metric":0},
"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},
"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},
"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},
"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":1.7},"I":{"pass":true,"metric":100.0},
"J":{"pass":true,"metric":100.0},"auctions_total":5}
```

## Updated next-session priorities (supersedes the list above where they conflict)

1. **Duval I durable fix**: normalize `parcel_id` format at the write chokepoint
   (`biddeed.tier1_card_upsert` or `promote_upcoming_tier1_cards`), scoped to Duval's
   RE-number convention only (other counties format differently — do not apply a blanket
   regex). Until this ships, I will keep oscillating near the 95% threshold for the
   ~19 upcoming-auction rows on a ~40min cycle. Mitigation available now: re-run
   `scripts/gold_standard_shard1_duval_madison_run7519_duval_i_fix.py` (v2, collision-safe,
   idempotent) periodically.
2. **Madison B/F**: escalate the phone call (850-973-1500) to Ariel for 21-36-CA and
   24-62-CA — confirmed via real browser automation to be the only remaining path, not a
   tooling gap. Also verify the prior pass's Auction.com-sourced `foreclosure_outcomes` row
   for 24-62-CA is still present and independently re-confirm it before relying on it for B.
3. **Madison A**: unchanged — no action until Madison lists an actual tax deed sale.
4. Do NOT re-attempt browser automation against `civitekflorida.com/ocrs/county/40/`
   case/person search in future sessions — confirmed dead end this pass (Turnstile-gated),
   save the budget for the phone-call escalation instead.

---

# ADDENDUM 2 — 3rd firing on this dispatch (chat_session: architect-20260730T160000, ~19:00-20:00Z)

Infra confirmed unchanged: Management API still returns Cloudflare block (HTTP 403, code
1010) and direct psql still fails SASL auth, from this sandbox, on this firing too. All
work done via PostgREST REST API only (`SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`).

## duval I: shipped the durable chokepoint fix as a migration; REST mitigation confirmed non-durable by an independent refuter

Wrote `supabase/migrations/20260730c_gold_standard_shard1_duval_parcel_id_chokepoint_normalize.sql`
— the source-level fix flagged as the top next-session priority by the 2nd firing.
It adds the same collision-safe dash→space normalization directly inside
`biddeed.flow_card_to_mca()`, gated strictly on `county_slug='duval'` and a
digit-dash-digit pattern match, so no other county's write path changes. **Could not be
applied live** — no DDL execution surface is reachable from this sandbox (Management API
blocked, psql blocked, PostgREST has no arbitrary-SQL RPC). An independent refuter
reviewed the migration by reading (diffed it against the last-applied function version)
and the guard logic against 30 real ambiguous cases: **SURVIVED** — correctly scoped,
byte-identical to the prior function outside the additive block, collision-safe.

Also re-ran the REST-based data-level mitigation (new script,
`scripts/gold_standard_shard1_duval_madison_run7519_duval_i_fix_v3_rest.py` — same v2
collision guard, reimplemented as PostgREST GET+PATCH calls since the Management-API-based
v1/v2 script can't reach its endpoint from this sandbox either). This is the fourth
independent implementation of the same normalization logic across three firings on this
dispatch, each rediscovering the DB-access blocker fresh.

**New, more precise finding this firing**: the mitigation's effect reverted in under 10
minutes — an independent refuter re-checked shortly after I reported PASS (96.1%,
666/693) and found I back to FAIL (94.9%, 658/693), with the claim's own cited example
row (`16-2025-CA-005443-AXXX-MA`, parcel `013837-0010`) already reverted to dash format.
This is faster than the ~40min reversion cycle both prior firings measured for
`gold-calendar-parity-cycle` (jobid 204). **Open question for next session**: either job
204's cadence assumption is wrong, or a second, more frequent process also writes duval
`parcel_id`. Re-applied the mitigation once more at session close (16 rows, same set) —
**do not trust any single reading of duval I without a fresh live re-check immediately
before use; it is confirmed volatile on a sub-10-minute cycle, not just a ~40min one.**
Logged `survived=false` in `gold_standard_ultraloop_audit` (id 11177) for the "stable
PASS" claim, per protocol — the migration's correctness is a separate, survived claim
folded into the same audit row's evidence.

## madison: B/F row reconfirmed real again; found and backfilled a real $100 opening bid the enrichment had missed

Re-confirmed (3rd independent check across 3 firings) that the `foreclosure_outcomes` row
for `24-62-CA` (Auction.com NO_SALE/plaintiff_reverted) is untouched and real, and that
B/F correctly still FAIL. An independent refuter corroborated the row, the live source
URL, and the B/F metrics, but caught a real overstatement in my claim: I said no dollar
figure was disclosed "anywhere" for this case — false. The live Auction.com page has an
`opening_bid_value` of **$100** that our enrichment never captured into
`multi_county_auctions.opening_bid` / `foreclosure_outcomes.opening_bid`. Backfilled both
(source-verified, not fabricated). This does **not** flip B or F — both key on a real
sold/winning amount, and $100 is the nominal opening bid on a listing that reverted to
the plaintiff with no third-party sale, not a transaction amount. Logged `survived=false`
for both the B and F reconfirmation claims (ids 11178, 11179) per protocol, since the
overstatement disqualifies the claim even though the core diagnosis holds — same pattern
as the 1st firing's madison-A ledger defect.

No further movement was possible on madison A (unchanged real zero) or the 21-36-CA /
24-62-CA dollar-amount blocker (still requires the phone-call escalation to Ariel per the
1st firing's finding — not actioned, out of scope for an autonomous session).

## Final live snapshot, this firing (~19:55Z, immediately after re-applying the duval mitigation — expect further drift)

**duval** — 10/10 by this instant's reading only, confirmed volatile, do not certify off it:
```json
{"A":{"pass":true,"metric":134},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":96.1},
"D":{"pass":true,"metric":96.2},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},
"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.0},
"I":{"pass":true,"detail":"card_complete=666 of 693","metric":96.1},
"J":{"pass":true,"detail":"deal_complete=692 (triangle + two-arm CMA + ml_score + max_bid)","metric":99.9},
"auctions_total":693}
```

**madison** — 7/10, unchanged, now with opening_bid=$100 backfilled on 24-62-CA:
```json
{"A":{"pass":false,"detail":"fc=5 td=0","metric":0},
"B":{"pass":false,"detail":"verified=0 closed_sold=0","metric":null},
"C":{"pass":true,"metric":100.0},"D":{"pass":true,"metric":100.0},"E":{"pass":true,"metric":100.0},
"F":{"pass":false,"detail":"tier1_sold=0 closed_sold=0","metric":null},
"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.0},"I":{"pass":true,"metric":100.0},
"J":{"pass":true,"metric":100.0},"auctions_total":5}
```

`gold_standard_certify()` was NOT invoked — duval's 10/10 reading is confirmed transient
(refuted), and madison is not at 10/10.

## Updated next-session priorities (supersedes prior lists where they conflict)

1. **Apply migration 20260730c live** the moment DDL access (working `supabase db push`,
   psql, or a functioning Management API path) is available from wherever the session
   runs. This is the only actual cure for duval I — every firing on this dispatch so far
   has re-derived and re-applied the same data-level mitigation, which now provably
   reverts in under 10 minutes.
2. **Investigate the actual reversion cadence** — confirm whether `gold-calendar-parity-cycle`
   (job 204) really runs every ~40min as previously assumed, or whether a second process
   touches duval `parcel_id` more frequently. The sub-10-minute reversion observed this
   firing doesn't match the prior model.
3. **Madison B/F**: still needs the phone-call escalation (850-973-1500) to Ariel for
   `21-36-CA` and `24-62-CA` — confirmed three times now this is a real data-access wall,
   not a tooling gap. No further autonomous progress possible without it.
4. Infra: Management API (`api.supabase.com/v1/projects/.../database/query`) now returns a
   Cloudflare block (403/1010) from this sandbox, in addition to psql's pre-existing SASL
   failure — meaning **no DDL/arbitrary-SQL path currently works from this sandbox at
   all**. This has now blocked three consecutive firings from applying the one change that
   would actually fix duval I. Needs escalation to whoever owns sandbox network/credential
   provisioning — this is no longer a minor flag, it is the single blocker on this
   dispatch's only remaining real fix.
