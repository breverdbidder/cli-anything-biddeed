# SHARD-1 run2886 session report (baker, escambia, st_lucie, holmes, hamilton)

dispatch_id: 6005f806-75ca-426f-a39d-ab82ebba9890
Session: architect-20260704T080000

## Method

Used the Workflow tool (ultracode) per ULTRALOOP PROTOCOL: 5 parallel read-only diagnosis agents
(one per failing county+letter group), each followed by an independent adversarial refuter agent
that re-ran the key queries live before any finding was trusted. All DB access via Supabase REST
(`$SUPABASE_URL/rest/v1`) and the Management API SQL endpoint
(`POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query`, authenticated
with `SUPABASE_ACCESS_TOKEN`) — direct psql/psycopg2 (pooler host, both 5432 and 6543) fail
password auth in this sandbox; no generic `exec_sql`/`exec` RPC is live either. The Management
API SQL endpoint was the only path to arbitrary SQL and is what every fix in this report was
applied through.

Live evaluations were pulled BEFORE reading the dispatch's pasted metrics. They already
disagreed (escambia/st_lucie C/D had visibly improved since the brief was written — evidence
that another process/session touched them between brief generation and this session start),
confirming the mandate to never trust pasted numbers over a fresh query.

## BEFORE (fresh live query, start of session)

```
baker:     10/10 (A-J all PASS)
escambia:   8/10  C=26.7(71/266) D=26.7(71/266) fail, rest PASS
st_lucie:   8/10  C=25.0(18/72)  D=25.0(18/72)  fail, rest PASS
holmes:     6/10  B=null(0/0) C=7.7(1/13) D=7.7(1/13) F=null(0/0) fail, rest PASS
hamilton:   3/10  B=null(0/0) C=43.8(7/16) D=43.8(7/16) E=68.8(11/16) F=null(0/0)
                  I=6.3(1/16) J=37.5(6/16) fail; A/G/H PASS
```

## Fix #1 (SHIPPED): hamilton J, 37.5% → 100%

`bid_decisions` existed for hamilton's 6 foreclosure rows (from an earlier session) but not for
its 10 tax-deed rows. Reused the identical, already-proven Shapira V14 generator pattern from
`scripts/shard5_loop472_j_decisions.py` (which already moved holmes/collier/madison/osceola/union
J to 100%), scoped to hamilton only, as a new file
`scripts/shard1_run2886_hamilton_j_backfill.py` (did not modify the existing shard5 script —
other shards/sessions own it). ARV for the 10 tax-deed rows derives from `opening_bid * 1.8`
(all 10 have real `opening_bid` values from `tax_deed_outcomes`); `arv_source` is honestly
labeled `minimum_bid_factor`.

```
BEFORE: J FAIL metric=37.5 [deal_complete=6 of 16]
AFTER:  J PASS metric=100.0 [deal_complete=16 of 16]
```

Verified live via `pencil_dod_evaluate_county('hamilton')` immediately after the write (6
updates, 10 inserts, both confirmed in script output and by the re-query).

## Fix #2 (SHIPPED): escambia C/D ghost-success purge, 26.7% → honest 4.1%

The escambia_stlucie_CD diagnosis agent's evidence (fully reproduced, byte-for-byte, by an
independent refuter) found 60 `multi_county_auctions` rows carrying
`parity_status='matched_clean'` with `parity_source IN ('tier1_realtaxdeed_calendar_v1',
'tier1_realforeclose_calendar_v1')`, all stamped `parity_checked_at` this morning
(2026-07-04 08:22:04 / 08:22:13 UTC) with `tier1_authoritative=false` and
`tier1_source_run_id=NULL` — structurally indistinguishable from escambia's 185 genuinely
unmatched sibling rows (same `data_source='calendar_sweep_mca_v3'`, no cert_number, no
winning_bidder). Neither source label appears in any committed script or migration
(`grep -r` across `*.py`/`*.sql`/`*.yml`/`*.js` = zero hits). This is the same anti-pattern
already purged for escambia once before, per commit `652678dc`
(`20260702_shard1_pencil_dod_cd_tier1_filter.sql`), which found a *different* fake batch
(`official_parcel_linkage_shard2`, an E-criterion link mistakenly counted as a C/D litmus match).
Escambia's only real, backed tier1 rows are 11 (9× `tier1_realforeclose_escambia` from
2026-07-02 + 2× `tier1_foreclosure_outcome` from 2026-06-24).

Reverted via `supabase/migrations/20260704_shard1_run2886_escambia_cd_ghost_success_purge.sql`
(nulled `parity_status`/`parity_source`/`parity_checked_at` on the 60 rows). Logged to
`public.honesty_violations` (id `a87dc733-bbf0-405c-bc73-be8af5f708f1`, severity=CRITICAL,
resolved=true).

```
BEFORE: C FAIL metric=26.7 [matched_clean=71]   D FAIL metric=26.7 [matched_any=71]
AFTER:  C FAIL metric=4.1  [matched_clean=11]   D FAIL metric=4.1  [matched_any=11]
```

C/D still fail both before and after (no pass_count regression — escambia stays 8/10), but the
number is now honest. The real gap (255 of 266 rows have never been run through any independent
litmus/clerk comparison) is a genuine coverage build, not a data-correctness bug, and is flagged
below as future work. **Caution for future sessions**: since another concurrent shard/process
appears to be writing to this exact county+criterion during this exact run (the ghost batch was
stamped mid-morning today, not from an old migration), re-verify C/D live before trusting it in
any subsequent session this week — do not assume this purge is permanent if something else is
regenerating the same pattern.

## Investigated, no safe fix found — st_lucie C/D (unchanged, 25.0%)

3 rows (`2024CA001834`, `2025CC001033`, `2024CA000330`) carry `parity_status='mca_only'` with a
correctly-`tier1`-prefixed source (`tier1_realforeclose`) and `parity_divergences=NULL`. The
original diagnosis proposed flipping these to `matched_clean` on the theory that a null
divergence means "matched cleanly." Rejected: `mca_only` is a real, fleet-wide semantic
(2,494 rows use it) meaning "exists only in our system, no litmus counterpart found" — it is
already the honest label, not a mislabeled match. Flipping it without genuine cross-source
match evidence would repeat exactly the ghost-success pattern just purged in escambia (these 3
rows share the same tell: `tier1_authoritative=false`, no `tier1_source_run_id`). Left
unchanged. 16 additional rows (`matched_divergent`/`litmus_po_only`, real PropertyOnion
comparisons with genuine field diffs) are correctly excluded from the `tier1%` filter per HARD
GUARDRAIL #1 (PropertyOnion is litmus-only) — a migration
(`20260702_shard5_miami_dade_stlucie_propertyonion_relabel.sql`) already did this deliberately;
relabeling them back would reverse a documented guardrail fix. The remaining 35 rows are a
genuine, unattempted coverage gap.

## Investigated, honestly blocked — holmes B/F, hamilton B/F (unchanged)

Both counties have **zero** auctions with `sold_amount IS NOT NULL` — this is not a scraper or
wiring gap, it is the current real state of the data:
- hamilton: all 7 `tax_deed_outcomes` rows have `outcome='redeemed'` (the owner paid off the
  certificate before sale — a real, legally normal outcome, not a sale). 0 of 16 auctions have
  actually sold.
- holmes: 12 of 13 auctions are `auction_status='upcoming'` (dated 2026-07-07 through
  2026-07-30, i.e. genuinely in the future relative to today). The 1 `completed` row
  (`HOLMES-LEGACY-123a1bd5-...`) has a `foreclosure_outcomes` row with `outcome='sold'` but no
  dollar amount anywhere (`winning_bid`, `opening_bid`, `sold_amount` all NULL) — its
  `HOLMES-LEGACY-<uuid>` case number pattern strongly suggests a synthetic/placeholder row, not
  a scraped one.

An initial diagnosis proposed simply running `scripts/county_outcome_harvester.py` for holmes
(claiming zero new work needed since holmes is a standard realforeclose/realtaxdeed county). An
independent refuter falsified this: the harvester's only code paths capable of writing
`sold_amount`/`tier1_sold_amount` (`build_outcome_records`/`load_outcomes`/`fix_parity_status`/
`fix_tier1_sold_amount`) were explicitly disabled in `main()` as of today's own commit
`f749c834` ("orange B ghost-success purge + shared harvester safety fixes"), and
`holmes.realforeclose.com` is independently confirmed WAF-blocked/inactive in
`realauction_subdomains`. Running it today would write nothing. No fabrication attempted —
B/F remain honestly un-passable for both counties this session.

A separate diagnosis claimed holmes' C/D 7.7% was a pure "eval-timing/denominator" defect
(scoring against not-yet-sold future auctions) and proposed excluding `upcoming` rows from the
denominator, extending the same fix to escambia/st_lucie. An independent refuter falsified
this too: thousands of DB-wide rows are `matched_clean` while still `auction_status='upcoming'`
(pre-sale/calendar-based matching is a real, working mechanism elsewhere — e.g. 57 escambia rows,
before this session's purge, used exactly this pattern), and applying the proposed denominator
to escambia/st_lucie yields nonsensical ratios (3550%, 900%). Holmes' real gap is a genuine
`tier1_realtaxdeed` matcher coverage hole — never wired for this county — not an eval bug. No
change made; flagged as future scraper/matcher work.

## Investigated, honestly blocked — hamilton E (68.8%) and I (6.3%)

E: 5 foreclosure rows (`2024-CA-19`, `2023-CA-41`, `2025-CA-37`, `2025-CA-46`, `2025-CA-66`)
have real addresses/geo/value but no `parcel_id`. I: those same 5 rows block on the same cause,
plus 10 tax-deed rows that have `parcel_id` (matching a real zoning-card row, zone_code='R-1')
but **no** address/geo/value at all.

**Significant side-finding (CONFIRMED, not yet fixed)**: `fl_parcels_addr_lookup` has a 15,940-row
bucket labeled `co_no=24` that the codebase treats as Hamilton (`fl_counties.co_no=24` for
Hamilton). I queried the live FL GIO Florida_Statewide_Cadastral ArcGIS FeatureServer directly:
`WHERE CO_NO=24` returns Arcadia, FL addresses — that's **DeSoto** County (`fl_counties.co_no=14`
for DeSoto), not Hamilton. Querying `WHERE PHY_CITY='JASPER'` (Hamilton's county seat) returns
`CO_NO=34` in that same ArcGIS layer. This means the ArcGIS layer's internal `CO_NO` field does
**not** match `fl_counties.co_no` for at least this county pair, and `fl_parcels_addr_lookup`'s
"Hamilton" bucket is actually mislabeled DeSoto data — the same class of bug as the previously
found "franklin fl_counties.co_no bug." I did not use this table for enrichment (would have
cross-contaminated hamilton with DeSoto parcels) and did not attempt a broader re-ingestion fix
(shared reference table, out of this session's safe blast radius — flagging for a dedicated
follow-up rather than a rushed cross-county fix). A direct attempt to query the ArcGIS layer with
the correct `CO_NO=34` and match the 5 known addresses timed out repeatedly from this sandbox
(2+ minutes, no response) — not forced through under time pressure. No parcel_id fabricated.

## Skipped

- `gold_standard_loop()` / `gold_standard_certify()` — not run. Per PARALLEL-FLEET RULES, other
  shards are mid-flight in the same run2886 (confirmed: `SHARD5_RUN2886_SESSION_REPORT.md`,
  `SHARD10_RUN2886_...md` etc. already exist from concurrent sessions today).
- Ultraloop audit table (`gold_standard_ultraloop_audit`) — not populated this session; the
  workflow tool's diagnose→verify transcript is the audit trail (this report + `honesty_violations`
  row), but the specific table wasn't written to. Flagging as a gap for a future session to close
  before any of these letters could count toward certification under the V6 gate.

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Baseline all 5 counties | live query | done | brief's pasted numbers were already stale |
| Hamilton E fix | backfill parcel_id | not done | no trustworthy source found; co_no bug discovered instead |
| Hamilton I fix | backfill card fields | not done | blocked by same cause as E |
| Escambia/st_lucie C/D | reconcile parity | escambia: purged fake data (honesty fix, not a gain); st_lucie: investigated, correctly declined to fabricate | metric went down for escambia, correctly |
| Holmes/hamilton B/F | build independent outcome scraper | not done | confirmed structurally zero-closed-sales / disabled harvester, not a build task this session |
| Hamilton J | not originally targeted first | 37.5%→100%, PASS | opportunistic win once J generator pattern was recognized as reusable |

## AFTER (fresh live query, end of session)

```
baker:     10/10 (unchanged)
escambia:   8/10  C=4.1(11/266) D=4.1(11/266) fail [honesty-corrected from 26.7%], rest PASS
st_lucie:   8/10  C=25.0(18/72) D=25.0(18/72) fail [unchanged, investigated], rest PASS
holmes:     6/10  B=null C=7.7(1/13) D=7.7(1/13) F=null fail [unchanged, investigated], rest PASS
hamilton:   4/10  B=null C=43.8(7/16) D=43.8(7/16) E=68.8(11/16) F=null I=6.3(1/16) fail;
                  A/G/H/J PASS [J moved 37.5→100 this session]
```

Net pass-count change this session: hamilton 3/10 → 4/10 (J). Escambia/holmes/st_lucie/baker
pass-counts unchanged (escambia's C/D number changed but stayed FAIL both sides — an honesty
correction, not a regression).

## Addendum (same dispatch, continuation turn): ultraloop_audit gap closed

The "Skipped" section above flagged that `gold_standard_ultraloop_audit` was never populated for
this session's two shipped claims, which blocks certification under the V6 gate. Closed this gap:

1. Re-verified both claims live, fresh, before writing anything — did not trust this report's own
   numbers: `pencil_dod_evaluate_county('hamilton')` still returns `J.pass=true, metric=100`
   (independently recounted via `bid_decisions` join `multi_county_auctions`, arv/max_bid/ml_score/
   factors(5 keys) all present: 16 of 16). `pencil_dod_evaluate_county('escambia')` still returns
   `C.metric=4.1, D.metric=4.1` (recounted the purged ghost-pattern rows: 0 remain, purge held).
2. Also confirmed no other concurrent shard has touched these two counties since the purge —
   `SHARD3/4/5/9/10_RUN2886` reports/commits exist for other counties only, none overlap
   baker/escambia/st_lucie/holmes/hamilton.
3. Inserted 3 rows into `public.gold_standard_ultraloop_audit` (ids 3409-3411): hamilton/J,
   escambia/C, escambia/D — each `survived=true` with `refuter_evidence` containing the live
   reverify query + independently recounted result, dated this addendum's timestamp.
4. `gold_standard_loop()`/`gold_standard_certify()` still NOT run — SHARD3/4/5/9/10 are actively
   mid-flight on run2886 (commits as recent as `50e814d4`), so a fleet-wide certify pass would be
   premature per PARALLEL-FLEET RULES regardless of this shard's own state.

Remaining open items from this shard, unchanged and not attempted this turn (would need dedicated
follow-up sessions, flagged rather than rushed): hamilton `fl_parcels_addr_lookup` co_no=24
mislabeling (shared reference table, out of blast radius), holmes/hamilton B/F structural
zero-closed-sales (harvester write paths disabled fleet-wide as of `f749c834`), escambia/st_lucie/
holmes C/D genuine coverage gaps (no independent litmus source wired for the bulk of rows).
