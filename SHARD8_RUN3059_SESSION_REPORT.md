# SHARD-8 run3059 session report

dispatch_id: 97f56687-28a3-463c-8988-31b6fc424178
chat_session: architect-20260705T000000
counties: charlotte, levy, monroe, osceola, madison

## Environment constraint (CONFIRMED)

Direct DB connection (psycopg2) against the Supabase pooler and `db.<ref>.supabase.co`,
all host/port/user combinations, failed with `FATAL: password authentication failed` using
the `SUPABASE_DB_PASSWORD` documented in CLAUDE.md. This means no DDL (new SQL functions,
views, migrations) was possible this session. All work below was executed live through
PostgREST (`SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`), which is fully functional for
SELECT/INSERT/UPDATE/DELETE and RPC calls (including `pencil_dod_evaluate_county`,
`gold_standard_ultraloop_audit` inserts). Flagging for the next session to get a working
DB password before attempting anything that needs a real migration file applied.

## Process

1. Forensics workflow (5 parallel read-only agents, one per county) — CONFIRMED root causes
   for every failing letter via live queries, before any write.
2. Applied only real, evidenced fixes (no synthetic seed rows, no blanket UPDATEs).
3. Adversarial verification workflow (5 parallel refuter agents, independent of the fixer) —
   re-derived every claim from raw tables. See "Verification" below for outcomes, including
   one confirmed self-inflicted race condition (osceola).
4. Logged every claim to `gold_standard_ultraloop_audit` (dispatch_id above), including the
   reconciliation row for the osceola race.

## Plan vs Actual

| County | Planned | Actual | Deviation |
|---|---|---|---|
| charlotte | Fix C/D | Found + purged 11 fabricated ghost-success rows (`CHARLOTTE-PO-COVERAGE-V2`, zero outcome-table backing, from an earlier session's unexecuted-but-claimed-shipped migration). C/D corrected DOWN (28.2%→17.5%, 30.1%→19.4%) — honest baseline restored, not a new pass. | Real fix was an integrity correction, not new coverage. Growing real C/D further requires running a tax-deed AJAX harvest against charlotte.realforeclose.com, not attempted this session (time). |
| levy | Fix C/D | Promoted 28/32 rows to matched_clean via exact case_number + sold_amount match against `tax_deed_outcomes` (clerk-sourced, non-PO). C/D 0.0%→87.5%. Still FAIL — remaining 4 rows are 3 foreclosure cases + 1 tax-deed case with future auction dates (not yet held), zero `foreclosure_outcomes` coverage for levy. | None — matches plan, partial pass as expected once ceiling found. |
| monroe | Fix C/D, investigate A | Live AJAX-harvested monroe.realtaxdeed.com (03/25/2026, paginated across 2 pages, 25/25 unique aids), exact-matched, promoted 22 new + 3 pre-existing → **C/D 12.0%→100.0%, both PASS**. A confirmed genuine structural ceiling (foreclosures conducted in-person at Key West courthouse; corroborated by an external web search, not just the DB config row). | Monroe moved 7/10 → 9/10. |
| osceola | Investigate B/C/D/F/I | Harvested osceola.realtaxdeed.com across all 11 distinct auction dates present in the data (195 unique aids total; 2026-05-15 returned 0 items both attempts — genuine site anomaly, not forced). Exact-matched 94/134 rows → C/D 0.0%→70.1%. Still FAIL. B/F remain a genuine structural ceiling (only listing data was harvested, not post-sale winning-bid results). I remains 0% (65/94 matched rows got real address/value backfill; the other 29 still carry the pre-existing placeholder address / null value — partial, not fabricated). | Ran the harvest in two waves; the second (full) wave overlapped with the verify workflow, which had been given the first wave's numbers — see Verification note below. |
| madison | Bootstrap A | Inserted 5 real, live-scraped foreclosure sale rows from `madisonclerk.com/departments-services/property-sales/foreclosure-sales/` (independent clerk source, not RealAuction, not PropertyOnion). auctions_total 0→5, fc 0→5. A still FAILs — td=0 is genuine (madisonclerk.com's tax-deed-sales page explicitly states "There are no properties on the list of tax deeds at this time"; `madison.realtdm.com` was checked live and found to be a non-production **TEST** tenant instance, not usable). E and H newly PASS. | Madison moved 1/10 → 3/10 (G was already vacuously passing on an empty set before; now non-vacuously passing with real rows). |

## Verification note (osceola)

The adversarial verify workflow was launched with the osceola claim text describing wave 1
(11 rows / 8.2%). While it was running, wave 2 (94 rows / 70.1%) was applied. The verifier
correctly flagged a mismatch between the claim it was given and live state, and marked
osceola REFUTED. Independently, the verifier re-derived the case_number join itself from raw
tables and got exactly 94 matches with 0 false positives — confirming the CURRENT live state
(70.1%) is genuine and not fabricated; the refute was about stale claim attribution/timing,
not about the underlying data. Reconciliation logged to `gold_standard_ultraloop_audit`.
The verifier also caught a real, accurate gap: 29 of the 94 matched rows still carry the
pre-existing placeholder address (`"Osceola County, FL 34741"`) / null assessed_value because
the harvest only provided real address/value data for a subset of matched cases — flagged
honestly rather than backfilled with invented values.

Charlotte, levy, monroe, and madison claims all **SURVIVED** adversarial verification, each
with one minor, non-disqualifying caveat (see verifier transcripts): a pre-existing
`charlotte_clerk_shard6` placeholder-value smell unrelated to this session's fix; a factual
correction to levy's root-cause language ("upcoming auctions", not "unsold"); a missing
provenance field on monroe's new `realforeclose_aids` rows; and one unconfirmable (not
disproved) sub-claim about `madison.realtdm.com` being a test tenant, since the verifier's
own fetch tool got a 403 where mine got 200.

## Verification evidence — before/after `pencil_dod_evaluate_county`

### charlotte: 8/10 → 8/10 (honesty-corrected, no new pass)
```
before: {"A":T,"B":T,"C":F(28.2),"D":F(30.1),"E":T,"F":T,"G":T,"H":T,"I":T,"J":T}
after:  {"A":T,"B":T,"C":F(17.5),"D":F(19.4),"E":T,"F":T,"G":T,"H":T,"I":T,"J":T}
```

### levy: 8/10 → 8/10 (real C/D improvement, still below threshold)
```
before: {"A":T,"B":T,"C":F(0.0), "D":F(0.0), "E":T,"F":T,"G":T,"H":T,"I":T,"J":T}
after:  {"A":T,"B":T,"C":F(87.5),"D":F(87.5),"E":T,"F":T,"G":T,"H":T,"I":T,"J":T}
```

### monroe: 7/10 → 9/10 (C, D newly PASS)
```
before: {"A":F,"B":T,"C":F(12.0), "D":F(12.0), "E":T,"F":T,"G":T,"H":T,"I":T,"J":T}
after:  {"A":F,"B":T,"C":T(100.0),"D":T(100.0),"E":T,"F":T,"G":T,"H":T,"I":T,"J":T}
```

### osceola: 5/10 → 5/10 (large real C/D gain, still below threshold)
```
before: {"A":T,"B":F,"C":F(0.0), "D":F(0.0), "E":T(96.3),"F":F,"G":T,"H":T,"I":F(0.0),"J":T(96.3)}
after:  {"A":T,"B":F,"C":F(70.1),"D":F(70.1),"E":T(96.3),"F":F,"G":T,"H":T,"I":F(0.0),"J":T(96.3)}
```

### madison: 1/10 → 3/10 (E, H newly PASS; G now non-vacuous)
```
before: {"A":F,"B":F,"C":F,"D":F,"E":F,"F":F,"G":T(vacuous, 0 rows),"H":F,"I":F,"J":F}
after:  {"A":F(fc=5,td=0),"B":F,"C":F,"D":F,"E":T(100.0),"F":F,"G":T(real,5 rows),"H":T,"I":F,"J":F}
```

## Deferred (out of scope this session, flagged for next dispatch)

- charlotte C/D: needs a tax-deed AJAX harvest against charlotte.realforeclose.com
  (`last_td_scraped_at` is null — never run) matched by exact case_number.
- levy C/D: remaining 4 rows need `foreclosure_outcomes` coverage for levy (currently 0 rows)
  once the 3 upcoming foreclosure cases and 1 upcoming tax-deed case actually close.
- monroe A: genuine structural ceiling — in-person courthouse foreclosures. Would need manual/
  clerk-record capture, not an online scraper, to ever move.
- osceola B/F: need a post-sale winning-bid/results scrape (this session only harvested
  pre-sale listing data) written into `tax_deed_outcomes`/`foreclosure_outcomes` with a real,
  non-PropertyOnion `data_source`. osceola I: needs lat/long enrichment (e.g. FL GIO cadastral
  API by parcel_id) on top of the address/value backfill already done.
- madison A: needs recurring monitoring of madisonclerk.com's tax-deed-sales page (currently
  empty) — no fix exists until a real sale is scheduled there.
- All counties: no DDL was possible this session (stale DB password) — the exact-match
  promotion logic used here mirrors the existing `refresh_shard2_cd_tier1_v1()` SQL function
  pattern; a future session with working DB credentials could formalize it as a proper SQL
  function/migration instead of ad-hoc REST PATCHes.
