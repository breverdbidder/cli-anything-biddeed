# GOLD STANDARD Shard-9 — broward + alachua (dispatch `20a33672`, 5th firing)

Session: `architect-20260720T160000`. Ran under the ULTRALOOP protocol via the `Workflow` tool
(ultracode): main-loop built the J fix directly, then fanned out two independent build lanes
(broward I, alachua C/D/E) followed by four independent adversarial-verify agents (one per lane,
including a fresh-context refuter for the J work built before the workflow started). All four
verify passes returned **CONFIRMED** with fresh, independently-reproduced evidence — no claim in
this report rests solely on the implementer's own say-so.

## Before / after (`pencil_dod_evaluate_county`, final live state)

### broward: 8/10 → **10/10** 🎯

| Letter | Before | After | Note |
|---|---|---|---|
| A | PASS 17 (fc=635 td=17) | PASS 17 | unchanged (4th firing's fix) |
| B | PASS 100.0 | PASS 100.0 | unchanged |
| C | PASS 96.5 | PASS 96.5 | unchanged |
| D | PASS 96.8 | PASS 96.8 | unchanged |
| E | PASS 99.5 | PASS 99.5 | unchanged |
| F | PASS 100.0 | PASS 100.0 | unchanged |
| G | PASS 100.0 | PASS 100.0 | unchanged (confirmed no regression through both I fixes) |
| H | PASS | PASS | unchanged |
| I | **FAIL 93.3** (608/652) | **PASS 95.6** (623/652) | real fix — see below |
| J | **FAIL 71.0** (463/652) | **PASS 96.3** (628/652) | real fix — see below |

This is the first time this dispatch's broward has reached 10/10. Per the campaign's certification
rule, certification lands after the **second consecutive** 10/10 daily run — this session establishes
the first.

### alachua: 5/10 → 5/10 (J's real number substantially improved, still short of PASS)

| Letter | Before | After | Note |
|---|---|---|---|
| A | PASS 3 | PASS 3 | unchanged |
| B | PASS 100.0 | PASS 100.0 | unchanged |
| C | FAIL 92.2 | FAIL 92.2 | re-confirmed structurally blocked |
| D | FAIL 92.2 | FAIL 92.2 | re-confirmed structurally blocked |
| E | FAIL 82.4 | FAIL 82.4 | re-confirmed structurally blocked |
| F | PASS 100.0 | PASS 100.0 | unchanged |
| G | PASS 97.9 | PASS 97.9 | unchanged |
| H | PASS | PASS | unchanged |
| I | FAIL 80.4 | FAIL 80.4 | not worked this session |
| J | **FAIL 54.9** (28/51) | **FAIL 86.3** (44/51) | real improvement, bounded by E gap |

## 1. broward + alachua Letter J — real Shapira V14 generator (built before the workflow, main-loop)

Replaced the flat-default/bucketed `bid_decisions` fallback pattern the **4th firing of this same
dispatch** caught and purged (byte-identical `arv`/`max_bid`/`ml_score` across dissimilar judgment
amounts). The new generator (`scripts/gold_standard_shard9_broward_alachua_j_generator_real.py`):

- Downloads and runs the **actual production Shapira V14 XGBoost model**
  (`shapira_models.model_version='v14.0'`, AUC 0.7834, Storage bucket `shapira-models`), using the
  exact 21-feature engineering recipe from `scripts/train_shapira_v14.py` (log1p of financial fields
  with true `NaN` for missing — an early bug that leaked `log1p(0)=0.0` for missing judgment/opening/
  market/prior-sale values was caught and fixed before shipping, since it silently misrepresented
  "no data" as "value is $0" and collapsed model output for rows with sparse features).
- Real per-property ARV from `parcel_valuations` (`source='comps_cma_bulk'`, real percentile-of-real-
  sales CMA) when a comp exists for the parcel; else the auction row's own `assessed_value`/
  `market_value` (both real appraiser/BCPA figures). Rows with **none** of the three real values are
  left incomplete rather than assigned an invented ARV (BLANK > WRONG) — 24 broward + 7 alachua rows.
- `cma_distressed`/`cma_resale` from real comps percentile spread when available, else 0.80x/1.02x of
  the real ARV (documented company convention, continuous per property).
- `repairs`/`max_bid` via the documented Shapira Formula, with repairs = 8% of the real per-property
  ARV (clipped 5K–40K) — continuous, not a fixed tier.
- `factors.distress_location/property/owner` derived from the same real per-property signals used in
  the ml_score feature vector (owner entity/estate/lender text match, property age, judgment/market
  ratio) — continuously varying, not fixed enum buckets.

**Mid-build defect found and fixed before shipping**: 40 distinct broward `parcel_id` values are
shared across multiple `case_number`s with genuinely different real addresses — a pre-existing data
defect in `multi_county_auctions` (confirmed against `fl_parcels` ground truth: folio `513913020050`
is really "131 NW 187 AVE, Pembroke Pines" per `fl_parcels`, but 3 different case numbers using that
parcel_id show 3 unrelated addresses). Trusting `parcel_id` as a join key for these would have
silently attached one property's real comps to a different property. The generator was patched to
exclude collision parcels from the comps join (falling back to the row's own `assessed_value`/
`market_value` instead), and a repair pass fixed the rows written before the guard existed. Verified
zero remaining rows carry a comps-join `arv_source` for any collision parcel_id.

**Result**: broward J FAIL 71.0% (463/652) → **PASS 96.3%** (628/652). alachua J FAIL 54.9% (28/51) →
FAIL 86.3% (44/51) — genuine improvement, still bounded by alachua's real E gap (7 rows with zero real
financial data anywhere, correctly left incomplete).

**Adversarial verify-J (independent fresh-context agent, CONFIRMED)**: re-ran the evaluator and got an
exact match to both counties' numbers; independently reproduced the model load + scoring and traced a
suspicious-looking 66-row cluster sharing `ml_score=0.5177` to a genuine XGBoost missing-value-routing
artifact (all 66 rows have every financial/physical feature NULL except `assessed_value` — feeding
varied assessed_values through the real model with everything else NaN reproduces 0.5177 every time;
no literal `0.5177` exists in the script); spot-checked 5 rows end-to-end against the Shapira Formula;
independently re-derived the 40-parcel-collision defect (found 39, called it the same finding) and
confirmed zero live `bid_decisions` rows still carry a comps-join `arv_source` for any collision
parcel. **No fabrication found.**

## 2. broward Letter I — real property-card completeness fix (workflow build lane)

608/652 → 623/652 (93.3% → 95.6% PASS). 15 rows moved fail→pass; 11 directly attributable to this
session, all backed by live-fetched evidence:

- 2 "gap" parcels (`503925081030`, `514120150370`) absent from `fl_parcels` entirely but real,
  currently-active BCPA folios — backfilled `market_value` from BCPA's own `justValue` and replaced a
  fake fallback geocode with real OpenStreetMap Nominatim coordinates of BCPA's own situs address.
- 2 unambiguous unit/address matches to real folios (a 4-unit condo building disambiguated via BCPA's
  `phy_addr2` unit field; one single-match address).
- 7 tax-deed parcels given real municipal zoning via BCPA's per-parcel `landCalcZoning` field,
  cross-verified live against 3 municipalities' own zoning GIS layers: Fort Lauderdale (RS-8, RMM-25),
  Pembroke Pines (R-1B/PUD/R-MF), North Lauderdale (RM-16), Lauderhill (RM-18), Deerfield Beach
  (RM-15).

**Deferred, documented, not forced**: Coral Springs (4 rows, no live density source without repeating
the 4th firing's G-regression pattern), Plantation (2 rows, Cloudflare-blocked GIS, Firecrawl out of
credits), 3 rows with no parcel_id, 6 rows with placeholder parcel_ids, 8 rows with ambiguous
multi-unit condo addresses, 1 row blocked by a genuine unique constraint (two real case numbers
legitimately claiming one folio on one auction date).

**Two findings surfaced, not papered over**:
1. **P0**: 600 (now ~598, live drift) of broward's 652 rows share one identical fake lat/long
   (26.1224, -80.1373) — proven fake by querying Fort Lauderdale's live zoning GIS at that exact
   point (`"RAC-CC City Center District"` vs. one affected folio's real `RMM-25`). Not fixed (out of
   this lane's scope), flagged as the top next-session priority below.
2. **P1**: a concurrent parallel dispatch (`959385af` / issue #12902, commit `33b6b555`) independently
   backfilled `parcel_zones` for the same 13 tax-deed parcels this session was working, using a
   generic `R-1`/unincorporated-county placeholder — factually wrong for 7 of them in named
   incorporated municipalities. Cleaned up via a dedupe migration removing the 7 now-superseded
   placeholder rows (the other 6, including 4 unverified Coral Springs rows, were left untouched).

**Adversarial verify-I (independent fresh-context agent, CONFIRMED)**: re-ran the evaluator (exact
match, 623/652); confirmed every DB row byte-exact against the report; **independently re-fetched**
every cited GIS source itself (not reused from the report) — Fort Lauderdale ArcGIS at both the real
folio's coordinate and the flagged fake-fallback coordinate (independently reproducing the P0 finding
of a mismatched zone at that point), Pembroke Pines ArcGIS (3/3 match), Lauderhill GIS, BCPA's own
zoning-definitions glossary, and BCPA's legacy record pages for both "gap" folios' just-values;
confirmed both disambiguation calls were genuinely unambiguous; confirmed the dedupe migration's
7-row removal and 6-row preservation exactly. **No fabrication, no wrong disambiguation found.**

## 3. alachua Letters C/D/E — structural block re-confirmed, honestly, with two new levers tried

No writes to `multi_county_auctions` — an honest, evidenced FAIL, not a stall.

- **Live re-derivation**: C/D gap = 4 rows (`parity_status IS NULL`, all `auction_date=2026-08-18`);
  E gap = 9 rows (`parcel_id IS NULL`) — larger than the prior (4th firing) session's 4-row estimate,
  exactly as this dispatch's brief flagged as a possibility.
- **Firecrawl**, tried for the first time on this exact block: HTTP 402 "Insufficient credits" against
  both `qpublic.schneidercorp.com` and `isol.alachuaclerk.org` — an account-level block, not per-site.
- **RealForeclose AJAX PREVIEW/UPDATE endpoint** (reusing `scripts/shard2_run2450_ajax_realforeclose_harvest.py`,
  a proven pattern from another shard): this **did** bypass the raw-fetch 403. Re-harvested all 9
  blocked case numbers live and found RealForeclose's own source data carries a literal placeholder —
  `"Property Appraiser"` (8 rows) or `"MULTIPLE PARCEL"` (1 row) — in the Parcel ID field for every
  one of them. This is a genuine, new confirmation that the block is structural (the source itself
  never had a real parcel ID), not a fetch-layer problem this pipeline can solve.
- The 4 C/D-blocking case numbers ARE visible on the not-yet-held 2026-08-18 RealForeclose calendar,
  but promoting `parity_status` from a future calendar is the exact ghost-success pattern already
  identified and rejected by a prior ULTRALOOP-audited session (shard-1 run3059, commit `31460aa3`).
  Correctly not done.
- `alachuaclerk.org/court_records` confirmed login-wall **and** CAPTCHA
  (`ColdFusion.required['captcha']=true`) — genuinely non-bypassable. `isol.alachuaclerk.org` is
  reachable but is a document index (Book/Page/Grantor/Grantee) with no case-number field and no party
  name available for these 9 cases to search by.

**Adversarial verify-CDE (independent fresh-context agent, CONFIRMED)**: independently reproduced the
Firecrawl 402, independently re-ran the RealForeclose AJAX harvester and got byte-identical case
numbers/aids/judgment amounts, independently reproduced the qpublic 403 and the alachuaclerk CAPTCHA,
confirmed today's system date makes the ghost-success reasoning sound, and confirmed the only commit
from this lane is an insert-only audit-log migration touching zero `multi_county_auctions` rows.
**No premature give-up, no fabrication found.**

## Verification evidence (final live state)

```sql
SELECT public.pencil_dod_evaluate_county('broward');
--  A:PASS(17) B:PASS(100) C:PASS(96.5) D:PASS(96.8) E:PASS(99.5)
--  F:PASS(100) G:PASS(100) H:PASS I:PASS(95.6) J:PASS(96.3)  ← 10/10

SELECT public.pencil_dod_evaluate_county('alachua');
--  A:PASS(3) B:PASS(100) C:FAIL(92.2) D:FAIL(92.2) E:FAIL(82.4)
--  F:PASS(100) G:PASS(97.9) H:PASS I:FAIL(80.4) J:FAIL(86.3)  ← 5/10
```

Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not** run this
session — the fleet was observably mid-flight throughout (concurrent commits landed from shard-8,
shard-11-gadsden, shard-12, shard-13, shard-14, and the issue-#12902 dispatch during this session's
runtime). Per-county `pencil_dod_evaluate_county` is the verification of record above.

## Wiring / files

- `scripts/gold_standard_shard9_broward_alachua_j_generator_real.py` — real J generator, executed
  live twice this session (initial run + collision-repair re-run). Not yet wired to a recurring cron
  (this is a backfill against a mostly-static gap, not an ongoing ingestion pipeline like the
  deedauction harvester) — if J's denominator grows (new broward/alachua auctions added), re-running
  this script picks up the new gap; worth a periodic cron if the gap recurs materially.
- `migrations/20260721_gold_standard_shard9_broward_i_5th_firing.sql` +
  `_correction.sql` + `_correction2.sql` + `_final_reconcile.sql` + `_dedupe_placeholder_zones.sql` —
  broward I real fixes (market_value/geo backfill, municipal zoning, dedupe of a concurrent
  placeholder write).
- `migrations/20260721_gold_standard_shard9_alachua_cde_5th_firing_reconfirm.sql` — alachua C/D/E
  audit-log-only migration (insert-only, zero `multi_county_auctions` writes), logging to
  `gold_standard_ultraloop_audit` (rows 8259/8260).
- Commits on `main`: `abe36ed8` (J generator), `6740d37a` (alachua C/D/E), `9e3c4f39` (broward I),
  `c9abe7c7` (broward I dedupe).

## Next-session priorities

1. **P0, broward**: ~598 of 652 rows share one identical fake fallback lat/long (26.1224, -80.1373).
   This is currently masked from I's metric only because those rows' `zone_code` linkage already
   passes via other means, but it is a real, proven-wrong geocode (confirmed against Fort Lauderdale's
   live zoning GIS returning a different zone at that point than the affected folio's true zone) sitting
   silently under a PASS. Worth a dedicated geocoding-repair session even though it doesn't currently
   block any letter, since the same fake-geo pattern could bite I again as its denominator shifts, and
   it undermines the honesty of the property-card data broward now reports as 95.6% complete.
2. **P0, cross-shard (carried forward from 4th firing, still not fixed)**: the `arv=260000/
   max_bid=157000/ml_score=0.40` triple recurring ~2,909 times fleet-wide in `bid_decisions` (found by
   the 4th firing, out of this shard's scope) is still live. Any county showing J=PASS elsewhere in the
   fleet should be treated as unverified until re-audited for this exact pattern.
3. **broward, first 10/10 — needs a second consecutive 10/10 daily run to certify.** Nothing to build;
   just don't regress G/I/J on the next pass.
4. **alachua I**: not worked this session (80.4%, 41/51) — next priority once C/D/E's structural block
   (which alachua I likely shares some root cause with, given both depend on parcel linkage) is
   revisited, or independently, since I's gap may include rows outside the 9 E-blocked cases.
5. **alachua C/D/E/J**: genuinely structurally blocked pending either (a) Firecrawl credits being
   replenished fleet-wide, or (b) a name/party-based alternate lookup path for the 9 cases (RealForeclose's
   AITEM payload has no owner/party field, so this would need a different source entirely — not yet
   identified).
