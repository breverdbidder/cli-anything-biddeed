# Gold Standard Shard-6: santa_rosa + osceola (dispatch 091fb9f9-f5a4-49b3-ad21-2472b3cc9f4a)

ULTRALOOP mode: native (Workflow tool fan-out: 4 research agents -> adversarial verify).

## santa_rosa — 10/10, no data change, freshness refresh only

Live `pencil_dod_evaluate_county('santa_rosa')` BEFORE and AFTER this session: **identical, no regression.**

| Letter | Before | After |
|---|---|---|
| A | PASS 41 (fc=62 td=41) | PASS 41 |
| B | PASS 100.0 (31/31) | PASS 100.0 |
| C | PASS 98.1 (101/103) | PASS 98.1 |
| D | PASS 98.1 (101/103) | PASS 98.1 |
| E | PASS 97.1 (100/103) | PASS 97.1 |
| F | PASS 100.0 (31/31) | PASS 100.0 |
| G | PASS 95.0 | PASS 95.0 |
| H | PASS 0.1h | PASS 0h |
| I | PASS 97.1 (100/103) | PASS 97.1 |
| J | PASS 100.0 (103/103) | PASS 100.0 |

Most letters' last `gold_standard_ultraloop_audit` survived=true row was 2026-07-24 — exactly at the campaign's 7-day certification-freshness edge as of today (2026-07-31). All 10 letters were independently re-derived live (not just re-called from the cached evaluator) by a dedicated research agent, then adversarially refuted by a second agent whose only job was to break each claim. 9 of 10 survived on the first pass; letter C's arithmetic was correct but the refuter correctly flagged that the claim ignored its own audit trail crossing the 7-day SLA and a denominator that moved (90→103 rows) since the last per-letter check — closed with a fresh row citing the current 103-row sample. Wrote 9 new `survived=true` audit rows (I already had a fresh 2026-07-31 row from a same-day earlier session). Residual, not blocking: 58 of the 101 letter-C `matched_clean` rows share a single `parity_checked_at` of 2026-07-02 (stale on the underlying parity check, not on the pass/fail verdict) — flagged for a future session.

## osceola — 8/10 (unchanged pass count), I honesty correction + G root-cause narrowed

Live `pencil_dod_evaluate_county('osceola')` BEFORE and AFTER:

| Letter | Before | After |
|---|---|---|
| A | PASS 5 | PASS 5 |
| B | PASS 100.0 | PASS 100.0 |
| C | PASS 97.8 | PASS 97.8 |
| D | PASS 97.8 | PASS 97.8 |
| E | PASS 100.0 | PASS 100.0 |
| F | PASS 100.0 | PASS 100.0 |
| **G** | FAIL 0.0 (density=93.0 far=0.0 pk1000=69.2) | FAIL 0.0 (density=**90.9** far=0.0 pk1000=**64.3**) |
| H | PASS 0.1h | PASS 0.1h |
| **I** | FAIL **89.8** (123/137, ghost-inflated) | FAIL **75.9** (104/137, honest) |
| J | PASS 99.3 | PASS 99.3 |

### I: ghost-success purge + root cause fixed

CONFIRMED (adversarially verified, survived refutation on 4 of 5 sub-claims): 410 `parcel_zones` rows tagged `source='shard4_run5153_osceola_i_default:INCORP_or_nomatch'` were a blind `zone_code='PD'` fallback default written whenever a live `gis.osceola.org` lookup returned INCORP/empty/unmatched — not a real zoning determination. Live spot-check against Osceola's own GIS for 3 sample parcels contradicted the uniform "PD": real leaf zones were `E-1/PD/PD/CR`, `INCORP x5`, and `RS-3 x4/INCORP x1`.

Root cause: a still-active daily 05:00Z cron (`.github/workflows/shard5-run1524-daily.yml` → `scripts/shard5_run1524_osceola_cd_fix.py` → `run_i_enrichment()`) unconditionally re-ran the fabrication script every day, which is why at least one prior purge attempt didn't stick (410 rows were live again as of this morning, with `created_at` timestamps on 07-24, 07-25, and 07-29 — all post-purge).

Applied and pushed to main (commit `bb580aa5`):
1. **Code fix** — `scripts/shard4_run5153_osceola_i_enrichment.py` no longer inserts a `PD` fallback; it skips parcels with no real GIS match. The daily cron now calls the corrected function, so this stops recurring.
2. **Live DELETE** of all 410 fabricated rows.
3. **Real backfill** — geo/value for 4 rows (cited Osceola GIS + property appraiser data), real GIS zone (`RS-2`, point-in-polygon confirmed) for 1 of those 4 parcels.
4. 3 of the 4 geo/value-backfilled rows remain correctly zone-unlinked: point-in-polygon confirms they're genuinely inside Kissimmee/St Cloud municipal limits (not unincorporated county jurisdiction_id=1186) — a real structural gap (needs jurisdiction reassignment + that municipality's own zoning layer), left unlinked rather than fabricated. **Flagged for next session.**

Net: I moves from a ghost-inflated 89.8% to an honest 75.9%. **FAIL before and after** — no certification was ever mis-issued on this number, but the daily fabrication is now stopped.

**Correction to initial research claim:** the ghost-zone research agent initially reported "letter G is unaffected" by the purge. Live re-measurement after applying the DELETE disproved this — G's density (93.0→90.9) and pk1000 (69.2→64.3) both shifted, meaning some of the fabricated rows were feeding G's applicable-parcel set too. G's pass/fail verdict is unchanged (FAIL before and after), so this didn't affect certification, but it's recorded here per the Honesty Protocol rather than left as the original (incorrect) claim.

### G: root cause narrowed (investigation only, no data written, still FAIL)

4th firing on this letter this dispatch. Confirmed, correcting prior sessions' hypothesis: `far_applicable_parcels=3` in `v_zoning_gold_standard_kpi_v3` is **not** caused by the orphan unincorporated C-1/A-1/I-1 zoning_districts rows (zero osceola parcels actually use those codes) — it's caused by exactly **3 parcels** (2× Kissimmee `T3`, 1× Kissimmee `T5-M`, jurisdiction_id=957) having **zero matching row in `zoning_districts` at all**. The KPI view's join-miss defaults them to `applicable=true` with NULL standards, guaranteeing they inflate every denominator and never populate a numerator. Same 3 parcels are also the entire density gap (40/43 populated → 93.0%, now 90.9% post-purge denominator shift). **One real, cited `zoning_districts` row for Kissimmee T3 or T5-M would clear the density gate outright.**

Blocked: real T3/T5-M dimensional standards (Kissimmee LDC Ch 14-5, Form-Based Code, Table 5-2) and the citywide parking table (corrected this session to Ch 14-7, not 14-6 as previously assumed) remain **UNKNOWN**. Municode/kissimmee.gov/PDF mirrors all returned HTTP 403 to WebFetch this session — the 4th firing in a row to hit this exact block. Firecrawl confirmed still out of API credits (tested live this session). `zoneomics.com` (worked for Ch 14-4 in a prior session) confirmed to not mirror Ch 14-5/14-6/14-7 at all. No ordinance value was fabricated.

## Verification protocol executed

- Live `pencil_dod_evaluate_county` before/after both counties (pasted above, exact).
- 11 fresh rows written to `gold_standard_ultraloop_audit` (9 santa_rosa, 2 osceola) with adversarial `refuter_evidence`.
- Did **not** run `gold_standard_loop()`/`gold_standard_certify()` — per PARALLEL-FLEET RULES, other shard sessions may be mid-flight; per-county `pencil_dod_evaluate_county` was used instead.
- Migration: `supabase/migrations/20260731d_gold_standard_shard6_osceola_i_ghost_purge_and_santarosa_freshness_091fb9f9.sql`.
- Commit `bb580aa5`, pushed directly to main (rebased on top of `5a9b2342`, no conflicts).

## Next-session priorities (osceola)

1. **I**: 3 remaining rows need Kissimmee/St Cloud jurisdiction reassignment + that municipality's own zoning layer (not Osceola-unincorporated). ~33 other card-incomplete rows untouched this session (137 total gap minus the 4 addressed) — same real-folio-in-address-text pattern is worth re-checking for the rest.
2. **G**: the gap is now pinned to 1-3 specific `zoning_districts` rows (Kissimmee T3/T5-M) — a session with working Firecrawl credits or a different fetch path (e.g. Wayback Machine mirror of the Kissimmee LDC, not yet tried) should attempt this narrowly-scoped target rather than broad zoning ingestion.
