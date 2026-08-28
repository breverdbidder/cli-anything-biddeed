# Gold Standard Shard-5: st_lucie, escambia, pinellas — dispatch `d1deb159-ec7f-43db-8483-4dd5a63c6d45`

Session: `architect-20260828T160000`, loop run 15078. Ran via the Workflow tool (ULTRALOOP fallback mode
— 4 fix agents in parallel, 4 independent adversarial verifiers, 1 closeout agent), with two findings
(st_lucie C, pinellas G) established directly by the orchestrating session before dispatching the workflow.

## Result: escambia 7/10 → 9/10, pinellas 6/10 → 8/10, st_lucie unchanged at 9/10

| County | Letter | Before (live) | After (live) | Status |
|---|---|---|---|---|
| escambia | C | FAIL 94.8% (matched_clean=473) | **PASS 98.6%** (matched_clean=492) | FIXED, adversarially verified |
| escambia | D | FAIL 95.0% (matched_any=474) | **PASS 98.8%** (matched_any=493) | FIXED, adversarially verified |
| escambia | I | FAIL 94.8% (card_complete=473/499) | **PASS 99.0%** (card_complete=494/499) | FIXED, adversarially verified |
| escambia | G | PASS 97.1% | **FAIL 94.7%** (density=99.8 far=97.4 pk1000=94.7) | **REGRESSION — caused by this session's own I-fix, see below** |
| pinellas | C | FAIL 93.8% (matched_clean=437) | **PASS 98.1%** (matched_clean=457) | FIXED, adversarially verified |
| pinellas | D | FAIL 93.8% (matched_any=437) | **PASS 99.8%** (matched_any=465) | FIXED, adversarially verified |
| pinellas | I | FAIL 93.3% (card_complete=435/466) | **PASS 95.9%** (card_complete=447/466) | FIXED, adversarially verified |
| pinellas | G | FAIL 0.0% (pk1000, 1 applicable parcel) | FAIL 0.0% (unchanged) | Reconfirmed structural block, no fix attempted |
| st_lucie | C | FAIL 80.7% (matched_clean=201) | FAIL 80.7% (unchanged) | Reconfirmed structural block, no fix attempted |

All numbers above are literal `pencil_dod_evaluate_county()` output, re-queried directly by the
orchestrating session (not copy-pasted from any subagent's self-report) immediately before writing this
report.

## What happened

Diagnosed all three counties directly (PostgREST, no psql — `SUPABASE_DB_PASSWORD` is the known-broken
constraint documented in prior sessions) before dispatching any agent:

- **st_lucie C**: live `parity_status` partition = matched_clean:139, PARITY_OK:62, CLERK_SSOT_CANCELLED:47,
  matched_divergent:1 (of 249). This is the exact fleet-wide canon-level block documented in
  `GOLD_STANDARD_C_STRUCTURAL_BLOCK_CROSS_COUNTY_FINDING_20260827.md` — CLERK_SSOT_CANCELLED rows are
  deliberately excluded from `matched_clean` (C) but count toward `matched_any` (D), which is why D=100%
  and C=80.7% on the same county. Even resolving the lone `matched_divergent` row only reaches 81.1%,
  nowhere near 95%. This is the 7th+ st_lucie session to independently reach this conclusion. No fix
  attempted — this needs an architect-level canon decision (Option A/B/C in the cross-county doc), not
  more per-county data work.
- **escambia C/D**: live partition showed 473 `matched_clean`, 1 `matched_divergent`, 25 `NULL` — no
  `CLERK_SSOT_CANCELLED` at all, meaning (unlike st_lucie) this was a genuine, fixable parity gap, not a
  canon block. All 25 NULL rows turned out to be upcoming (not-yet-occurred) tax-deed/foreclosure sales.
- **escambia I**: cross-referencing `multi_county_auctions.parcel_id` against
  `v_zoning_gold_standard_card` showed 25 parcels with a real parcel_id/address/value but no zone-linked
  `parcel_zones` row — a zoning-linkage gap, not a missing-data gap (E was already 99.8%).
- **pinellas C/D**: 438 `matched_clean`, 0 `CLERK_SSOT_CANCELLED`, 28 `NULL` — same genuine-gap pattern as
  escambia, but mixed: some already-sold rows, some cancelled, some still upcoming.
- **pinellas I**: 31 parcels with real data but no zone-linked `parcel_zones` row, heavily overlapping the
  C/D gap set.
- **pinellas G**: `v_zoning_gold_standard_kpi_v3` showed exactly 1 `pk1000_applicable` parcel in all of
  Pinellas (`parcel_id=143001420300300210`, zone `B`, jurisdiction Indian Rocks Beach). A prior session
  (dispatch `8da482b6`) had already researched this exact parcel and correctly left `parking_per_1000sf`
  NULL after Municode returned HTTP 403 and no citable ordinance section could be found. Independently
  re-attempted this session (WebFetch on the zoneomics.com mirror, the municode.com nodeId directly, the
  `mcclibraryfunctions.azurewebsites.us` PDF backend, and targeted WebSearch) — same result, no verifiable
  citation exists anywhere accessible. Left NULL, matching the prior finding.

With the diagnosis in hand (exact case_numbers and parcel_ids identified for every gap), dispatched a
4-way parallel `Workflow` fix pass (escambia-cd, escambia-i, pinellas-cd, pinellas-i), each agent reusing
this campaign's proven, already-committed code (`scripts/gold_standard_shard1_escambia_cd_fix_2931b3a1.py`'s
harvest→match→patch pattern, `scripts/pinellas_i_zoning_geo_shard1_3ce988ac.py`'s per-jurisdiction ArcGIS
routing table) rather than reinventing it, followed by 4 independent adversarial verifiers that re-derived
each claim from scratch against live sources before any DB state was trusted.

## Fix detail (VERIFIED)

- **escambia C/D**: re-harvested the live `escambia.realforeclose.com` (3 upcoming Sep 2026 dates) and
  `escambia.realtaxdeed.com` (01/06/2027) AJAX calendars. 19 of 25 targeted case numbers matched exactly;
  patched `parity_status='matched_clean'` with a session-specific `parity_source` tag, guarded by
  `parity_status=is.null` on every write (idempotent). The remaining 6 (all `2024 TD` series) were absent
  from the live 60-item calendar harvest and left as a genuine residual — not fabricated.
- **escambia I**: 21 of 25 parcels zone-linked via live point-in-polygon against `gismaps.myescambia.com`
  (unincorporated) and the City of Pensacola's zoning ArcGIS layer, including one new `zoning_districts`
  catalog row for a previously-uncataloged `RMU` code. 4 parcels left blank (null/junk parcel_id, or
  confirmed absent from the county's parcel layer).
- **pinellas C/D**: 20 of 28 rows resolved (12 via the live Clerk Auction Results Report, 8 via a live
  DAYLIST sweep — 12 as `matched_clean`, 8 as `CLERK_SSOT_CANCELLED` per this repo's C/D canon, which
  correctly moves D but not C). One stale DB row (`522024CA002012XXCICI`, still marked "upcoming" in our
  system when the live platform already showed it cancelled) was caught and corrected as a byproduct.
- **pinellas I**: 13 of 31 parcels zone-linked across 7 jurisdictions, including two newly-discovered
  endpoints not used by any prior pinellas session (Gulfport's `Energov1/GP_Zoning`, Madeira Beach's
  `AGO/PPC_Data` layer). 18 left blank (11 Largo parcels with no discoverable city zoning ArcGIS service
  after an exhaustive AGOL-org sweep; 7 with null/junk parcel_id and no address/owner to resolve by).

Every fix was independently adversarially re-verified (separate agent, re-ran its own from-scratch
harvest against the live source, did not reuse the fixer's code or trust its self-report) before the
closeout accepted any number.

## Regression found and corrected in this report (important — read before trusting the closeout agent's summary)

The Workflow's own closeout agent claimed escambia G's drop (97.1% → 94.7%) was "pre-existing,
untouched by this session's writes." **That claim is wrong, and this orchestrating session caught it** by
independently re-querying `v_zoning_district_applicability` and `v_zoning_gold_standard_card` after the
workflow finished, rather than accepting the self-report. Root cause: the escambia-I fix's new `RMU`
zoning-district catalog row (jurisdiction 1151, Escambia County unincorporated, one live parcel
`192N314200022001`) is flagged `far_applicable=true` and `pk1000_applicable=true` but has `max_far` and
`parking_per_1000sf` both NULL (no ordinance citation was found for it at insert time). That single
applicable-but-valueless parcel is exactly what pushed `far` to 97.4% and `pk1000` to 94.7%, both now
under the 95% bar. This orchestrating session attempted to source the real Escambia LDC § 3-2.4 RMU
FAR/parking values (WebFetch against `escambiacounty-fl.elaws.us` and a Loopnet PDF mirror) — both
attempts failed to load/were blocked, so per BLANK > WRONG no value was written. Logged as a corrective
`gold_standard_ultraloop_audit` row (id `19223`) separate from the closeout's 8 rows, explicitly flagging
the closeout's mischaracterization and the true cause, so this doesn't get lost or re-litigated from
scratch next session.

**Next-session priority for escambia**: source real Escambia LDC § 3-2.4 (RMU) FAR/parking values, or
revisit whether `RMU` should carry `far_applicable`/`pk1000_applicable=true` flags at all pending real
data — either closes this 1-parcel regression and returns escambia to 10/10 on G.

## Side effects (disclosed)

Pinellas C/D's live-verification also backfilled a `sold_amount` on 3 already-completed rows that had been
missing it, which rippled into B (verified=160/closed_sold=165, still PASS at 97.0%) and F
(tier1_sold=165/closed_sold=165, PASS at 100%) — neither letter was targeted; both remain PASS.

## Verification protocol evidence

- Live `pencil_dod_evaluate_county` called for all three counties, before this session's writes and again
  immediately before writing this report (not mid-session self-reports).
- 9 `gold_standard_ultraloop_audit` rows this dispatch (ids 19192–19199 from the closeout agent, plus
  19223 inserted directly by the orchestrating session correcting the escambia-G mischaracterization).
- `gold_standard_campaign` id `5260` closed out: `criteria_passed` set to the live per-letter A-J pass/fail
  for all three counties (st_lucie 9/10, only C fails; escambia 9/10, only G fails; pinellas 8/10, C/D/G
  correction — G fails, C and D now pass), `criteria_total=10`, `exit_reason='timeout'`,
  `session_end_at='2026-08-28T16:47:58Z'`.
- `gold_standard_loop()` / `gold_standard_certify()` were **not** invoked — other shard sessions were
  concurrently mid-flight on other counties (confirmed via `git pull --rebase` picking up 3 other shards'
  commits between this session's diagnosis and closeout).
- No `parity_status`/`zone_code`/`sold_amount` was fabricated anywhere; PropertyOnion was not used as a
  source anywhere in either county's fix. `pencil_dod_evaluate_county`, cron jobs 109/111/115, and all
  `gold-standard-loop-*` jobs were not modified.

## Files

- `scripts/gold_standard_escambia_cd_gap25_run20260828.py` — escambia C/D harvest+match+patch (19/25 rows)
- `scripts/escambia_i_zoning_geo_shard_20260828.py` — escambia I zone-linkage (21/25 parcels)
- `scripts/gold_standard_pinellas_cd_28gap_20260828.py` — pinellas C/D harvest+match+patch (20/28 rows)
- `scripts/pinellas_i_zoning_geo_shard5_5d40a513.py` — pinellas I zone-linkage (13/31 parcels)
- This report: `GOLD_STANDARD_SHARD5_STLUCIE_ESCAMBIA_PINELLAS_DISPATCH_D1DEB159_SESSION_REPORT.md`
