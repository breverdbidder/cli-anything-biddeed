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
