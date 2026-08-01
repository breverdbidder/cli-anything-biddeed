# Gold Standard shard-5: gilchrist / miami_dade / alachua — dispatch d74faadc, loop run 7858

Session type: ULTRALOOP native workflow (6 parallel fix agents, one per county+letter cluster, each followed by an
independent adversarial refuter that did not do the original work). All 6 claims **survived** verification. 6 live
commits shipped directly to `main` (no PRs, no side branches, per SHIP-TO-MAIN mandate).

## Scoreboard (BEFORE — fresh live query at session start, matches the dispatch brief exactly)

| County | Score | Failing letters |
|---|---|---|
| gilchrist | 8/10 | E FAIL 57.1 (parcel_linked=8 of 14), I FAIL 57.1 (card_complete=8 of 14) |
| miami_dade | 7/10 | C FAIL 90.7, D FAIL 90.7 (matched_clean/any=401 of 442), I FAIL 76.7 (card_complete=339 of 442) |
| alachua | 5/10 | C FAIL 91.8, D FAIL 91.8 (56 of 61), E FAIL 85.2 (52 of 61), I FAIL 77.0 (47 of 61), J FAIL 91.8 (56 of 61) |

## Scoreboard (AFTER — independently re-queried live via `pencil_dod_evaluate_county`, 2026-08-01 ~08:44Z, by the
orchestrating session directly, not copied from any fix agent)

| County | Score | Change |
|---|---|---|
| gilchrist | 8/10 | **No change.** E/I re-confirmed structurally blocked (see below). |
| **miami_dade** | **10/10** | **C 90.7→95.2 PASS, D 90.7→95.2 PASS, I 76.7→96.4 PASS. Full Gold Standard achieved this session.** |
| alachua | 7/10 | **C 91.8→100 PASS, D 91.8→100 PASS.** E moved 85.2→86.9, still FAIL. I unchanged 77.0, still FAIL. J unchanged 91.8, still FAIL. |

### SQL VERIFICATION (run live by the orchestrating session, 2026-08-01 ~08:44 UTC, after all 6 commits landed)
```
POST /rest/v1/rpc/pencil_dod_evaluate_county {"p_county":"gilchrist"}
-> A PASS 4 | B PASS 100.0 | C PASS 100.0 | D PASS 100.0 | E FAIL 57.1 (parcel_linked=8) | F PASS 100.0
   G PASS 100.0 | H PASS 0.1 | I FAIL 57.1 (card_complete=8 of 14) | J PASS 100.0 | auctions_total=14

POST /rest/v1/rpc/pencil_dod_evaluate_county {"p_county":"miami_dade"}
-> A PASS 111 | B PASS 100.0 | C PASS 95.2 (matched_clean=421) | D PASS 95.2 (matched_any=421)
   E PASS 97.1 (parcel_linked=429) | F PASS 100.0 | G PASS 99.7 | H PASS 0.1
   I PASS 96.4 (card_complete=426 of 442) | J PASS 95.5 | auctions_total=442

POST /rest/v1/rpc/pencil_dod_evaluate_county {"p_county":"alachua"}
-> A PASS 6 | B PASS 100.0 | C PASS 100.0 (matched_clean=61) | D PASS 100.0 (matched_any=61)
   E FAIL 86.9 (parcel_linked=53) | F PASS 100.0 | G PASS 97.9 | H PASS 0.1
   I FAIL 77.0 (card_complete=47 of 61) | J FAIL 91.8 (deal_complete=56) | auctions_total=61

SELECT criteria_passed FROM gold_standard_campaign WHERE dispatch_id='d74faadc-8b5e-4e53-ad81-084de4787499';
-> gilchrist{A-D,F-H,J:true, E,I:false} | miami_dade{A-J: all true} | alachua{A-D,F-H:true, E,I,J:false}
   criteria_total=10, exit_reason='timeout', session_end_at='2026-08-01 08:45:47 UTC'
```

## What shipped (6 commits, all confirmed on origin/main)

1. **`c3900c7e`** — gilchrist E/I, docs-only honest residual. Fresh attempt (4th independent session on these same
   6 rows: 2026-07-25, 2026-07-30, 2026-07-31, this session) confirmed the identical structural block: RealForeclose
   only publishes a broken, non-identifying qPublic placeholder link (`Q=548715190`, empty `KeyValue`, identical
   across all 6 cases) for Parcel ID; `qpublic.schneidercorp.com` and `gilchristclerk.com` both 403; Civitek OCRS
   was walked further than any prior session (county-select → Public access → disclaimer → search page) and
   confirmed genuinely Turnstile-gated on submit, AND has no case-number search field at all (name/DOB/SSN/business
   only) — a dead end even ignoring Turnstile, since no defendant name is known for these stub rows. Zero writes.
2. **`6ff57b5f`** — miami_dade C/D, 90.7%→95.2% (both now PASS). Root cause: `scripts/shard2_main_executor.py`'s
   `run_cd_parity()` step was intentionally disabled 2026-07-04 (commit `25fafcd5`) after a ghost-success incident
   on okaloosa, leaving it a read-only status report that never re-invokes real matching — so every miami_dade row
   scraped since then accumulated with `parity_status`/`parity_source` NULL. Re-invoked the existing (unmodified)
   AJAX harvester against the 40 gap rows' auction dates; 20 rows on 2 still-live upcoming dates matched cleanly.
   The other 20 sit on 5 already-passed dates whose AJAX preview calendar no longer serves the original case list —
   correctly left as an explicit residual (would need a county-clerk post-sale-results feed, not the live calendar).
3. **`cac3974e`** — miami_dade I, 76.7%→96.4% (PASS) — **this also completed miami_dade's full 10/10.** Decomposed
   the 103-row gap into address/geo/value nulls (52 rows) and zoning-card-linkage misses (51 rows, later merged to
   87 after geo backfill revealed those rows also failed the zoning check). Closed via FL GIO cadastral centroid
   backfill plus two real spatial-join sources: Miami-Dade's countywide `MunicipalZone_gdb` ArcGIS layer (51 rows,
   inserting 6 missing jurisdictions + 21 new `zoning_districts` rows with explicit far/density/pk1000 flags) and
   the separate `MD_MDCZoning` unincorporated layer (36/36 rows). Caught and fixed a live **G regression** introduced
   mid-fix (99.3%→94.1% FAIL, newly-linked parcels landing on already-incomplete `zoning_districts` rows) by
   backfilling `max_density_du_acre` for the 10 affected districts — net G improved to 99.7%. 16 rows remain a
   genuine residual (calendar source never captured a folio, or a UI rendering artifact) — left BLANK, not guessed.
4. **`846bcc0a`** — alachua C/D, 91.8%→100% (both now PASS). The existing alachua matcher only queried `AREA=W` on
   `realforeclose.com` for past dates. The 5 gap rows split into: 1 case living in `AREA=C` (never queried), and 4
   upcoming-auction cases (1 foreclosure the old matcher's future-date filter skips, 3 tax-deed cases on the
   entirely separate `realtaxdeed.com` platform domain never targeted at all). Reused the existing harvester
   functions verbatim (no new parity engine) to confirm all 5 in the live public AJAX calendar before promoting.
5. **`76a8c459`** — alachua E/I, one row fixed (85.2%→86.9% E, still FAIL; I unchanged at 77.0%, still FAIL). Of 9
   E-gap rows, 8 reconfirmed genuinely blocked (empty Clerk docids, ambiguous multi-lot/multi-parcel legal
   descriptions, or 2-way ambiguous owner match with no free disambiguating value source). 1 row (`01 2025 CC
   001127`) newly resolved via a Clerk judgment record cross-verified against Alachua Property Appraiser ArcGIS
   AND FL GIO Statewide Cadastral independently (both matched exactly: owner, address, JV=345532). I did not move
   for this row — the parcel sits in unincorporated Alachua, which has zero zoning-layer coverage on the county's
   public ArcGIS server (all 7 folders probed, none expose a zoning service) — a substrate gap, not a linkage bug.
6. **No commit for alachua J** — remains FAIL at 91.8%, honest no-fix. All 5 gap case numbers lack any real
   valuation input (parcel_id, assessed_value, and market_value all NULL for 2; the other 3 carry a bare parcel_id
   string absent from the `parcels` table entirely, with 0 rows in `parcel_valuation_comparables`). The existing
   real J-generator (`scripts/gold_standard_shard9_broward_alachua_j_generator_real.py`) would legitimately skip
   all 5 by its own no-fabrication design. Fabricating inputs here would repeat the exact failure mode already
   caught and reverted in `supabase/migrations/20260725_gold_standard_shard6_alachua_j_fabrication_purge.sql`.

## Not fixed this session (honest residuals)

- **gilchrist E/I** (6 rows): re-confirmed structurally blocked for the 4th consecutive session — no further
  session time should be spent here without a new lead (e.g. if RealForeclose ever populates a real qPublic link,
  or Civitek adds a case-number search tab).
- **miami_dade I** (16 rows): calendar-source folio/address never captured, or a rendering-artifact parcel_id.
- **alachua E** (8 rows), **alachua I** (14 rows), **alachua J** (5 rows): alachua E's 8 remaining rows are
  genuinely blocked at the source; alachua I's zoning-substrate gap (unincorporated Alachua has no public zoning
  GIS layer) blocks I even after any future E fix; alachua J is entirely downstream of alachua E/I — recheck J
  immediately once parcel-linkage/valuation data lands for any of its 5 case numbers.

## Verification protocol followed

ULTRALOOP native workflow: 6 fix agents (worktree-isolated, full Bash/Edit/Write/DB access), each followed by an
independent adversarial refuter agent that did not do the original work, re-ran the claimed SQL/queries live from
scratch (not copy-pasting the fix agent's evidence strings), and checked for ghost-success patterns (denominator
mismatches, PropertyOnion-derived writes, anomalous >100% ratios, unreal commits). **All 6 verifications returned
`survived=true`.** The orchestrating session then independently re-ran all 3 counties' `pencil_dod_evaluate_county`
calls itself (pasted above) before writing this report — a third, non-agent layer of confirmation.

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were NOT run this session (other shards
may be mid-flight) — the per-county `pencil_dod_evaluate_county` evaluations above are the authoritative
before/after proof.

## Close-out

`gold_standard_campaign` row (dispatch `d74faadc-8b5e-4e53-ad81-084de4787499`) updated: `criteria_passed` set to
the real per-county A-J booleans above, `criteria_total=10`, `exit_reason='timeout'` (miami_dade hit 10/10 but
campaign-level certification requires two consecutive 10/10 daily runs, which is an automated process outside this
session's scope), `session_end_at` stamped.

## Next-session priorities

1. **alachua J**: recheck immediately after any future alachua E/I session lands a parcel_id + assessed_value for
   any of the 5 gap case numbers — this letter is purely downstream, not independently blocked.
2. **alachua I**: needs real zoning-ingestion work for unincorporated Alachua (no public GIS zoning layer exists
   today) — same class of problem as the documented Brevard/other-counties G/I zoning-substrate gap in CLAUDE.md.
3. **gilchrist E/I**: do not re-attempt without a new lead — 4 independent sessions have now reached the identical
   conclusion (Turnstile-gated OCRS with no case-number search tab, broken qPublic placeholder link site-wide).
4. **miami_dade**: now 10/10 — needs a second consecutive 10/10 daily run to auto-certify; worth a lightweight
   freshness recheck in ~24h given this county's auction volume grows organically (356→442 rows between
   2026-07-11 and today) and could regress C/D/I if new rows outpace the parity/enrichment pipelines, as happened
   to palm_beach on 2026-07-31.
