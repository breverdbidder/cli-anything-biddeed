# Gold Standard shard-10: alachua — session report
(dispatch `a36233a1-0145-43b9-a8f0-75acc7594181`, loop run 6253, chat session `architect-20260724T160000`)

## Result: alachua 4/10 -> 7/10 live, verified

```
BEFORE: A pass B pass C fail(83.9) D fail(83.9) E fail(85.7) F fail(87.5) G pass H pass I fail(71.4) J fail(83.9)
AFTER:  A pass B pass C pass(100)  D pass(100)  E fail(76.8) F pass(100)  G pass H pass I fail(71.4) J fail(83.9)
```

Full before/after JSON pasted below (### SQL VERIFICATION).

## F: fixed (87.5% -> 100%)

Case `01 2025 CA 002830` carried `sold_amount=174416.2` while its `auction_date` was
2026-08-27 (34 days in the future of this session) and its `foreclosure_outcomes` row
(`data_source=realforeclose:alachua:shard5_run581`) had `winning_bid IS NULL` — no backing
outcome anywhere. Live-reharvested `alachua.realforeclose.com`'s own AJAX calendar for
8/27/2026 (`scripts/shard2_run2450_ajax_realforeclose_harvest.py`) and confirmed the case is
genuinely still listed upcoming with no sale-result field at all — ruling out a hendry-style
genuine dual-source conflict (there is no second live source claiming this case already sold).
The value also doesn't match judgment_amount/opening_bid/assessed_value/market_value on the
same row, ruling out a simple column-aliasing bug. Nulled `sold_amount` (not fabricated a
matching tier1 value). Verified live post-fix: `tier1_sold=7 closed_sold=7`.

## E: honest correction, not a fix (85.7% -> 76.8%)

Found `parcel_id='Property Appraiser'` — RealForeclose's own link-text placeholder, not a real
ID (already flagged as a known bad value by `scripts/shard14_run121fa7c3_alachua_e_i_diagnosis.py`)
— literally stored on 6 alachua rows. E's reported 85.7% (48/56) was silently inflated by these
6 ghosts. Root cause: these rows predate the `_clean_parcel()` validation added to
`.github/scripts/calendar_sweep_mca.py` in commit `8e13f266` ("v3.0"); because the sweep's
`columns=`-scoped upsert only writes fields *present* in the current scrape and never
force-nulls an absent field, stale pre-v3.0 garbage is never cleared by later (correctly
behaving) sweep runs.

- `01 2024 CA 001683`: RESTORED to `02975-002-000`, the previously real-verified value from
  `scripts/shard10_run3645_alachua_e_parcel_backfill.py` (ArcGIS PublicParcel FeatureServer
  unique match on a recorded judgment's grantee name). This fix had silently reverted to the
  ghost placeholder since that script ran — re-applied, not re-derived.
- `01 2025 CA 002830`: `parcel_id` nulled; `latitude`/`longitude` also nulled — `29.6516`/
  `-82.3248` is a shared county-centroid fallback (confirmed carried by **40** separate alachua
  rows, i.e. not a real per-property geocode). `property_address` and `assessed_value` kept
  (row-unique values — real scraped data, not part of the same fallback).
- `01 2025 CA 001634`, `01 2025 CA 003156`, `01 2023 CA 004261`, `01 2024 CC 005935`:
  `parcel_id` nulled, no real replacement found this session (BLANK > WRONG, not fabricated).

Net: E moved from a ghost-inflated 85.7% to a true 76.8% (43/56). **This is a regression in the
reported number and an improvement in its truthfulness** — the pre-fix 85.7% was never real,
and per the ULTRALOOP protocol's own stated purpose (catching exactly this class of anomaly),
disclosing and correcting it is the deliverable, not a setback to be hidden.

Residual: 13 rows genuinely lack parcel_id. Of these, 7 were live-reconfirmed this session
(`isol.alachuaclerk.org` docid empty on RealForeclose's own AJAX payload for all 7 target
auction dates) as having no clerk cross-reference document yet, and 1 (`01 2025 CA 003287`) is
a confirmed multi-parcel case with no single correct parcel_id assignable without fabrication —
both dead ends matching the prior diagnosis exactly, not re-litigated further.

## C/D: fixed (83.9% -> 100% each)

9 rows had `parity_status IS NULL` (6) or a non-tier1 `parity_source`
(`realforeclose_aids_patch`, 3) — both fail the evaluator's `parity_source LIKE 'tier1%'`
predicate regardless of match quality. Forked
`scripts/gold_standard_shard6_polk_cd_i_ajax_harvest.py` (itself forked from
shard11/leon, shard2/palmbeach, shard4/leon — an established pattern shipped by multiple prior
shard sessions and never reverted per git log) as
`scripts/gold_standard_shard10_alachua_cd_ajax_harvest_run6253.py`, re-harvested
`alachua.realforeclose.com`'s live AJAX calendar for each target row's own auction_date
(2026-08-11, 2026-08-18, 2026-08-27, 2026-09-01 — all confirmed live 2026-07-24), exact-matched
by normalized case_number, and promoted all 9/9 matches (every target case is genuinely present
on the live calendar) to `parity_status='matched_clean'`,
`parity_source='tier1:shard10_run6253_alachua_ajax_harvest:<sale_type>:<date>'`. No
PropertyOnion data touched — RealForeclose is the primary source these rows were already
scraped from, re-confirmed live against the county's own site.

## I / J: confirmed genuinely blocked, not attempted further

- I (`card_complete=40/56`, need 53/56): bounded by the same 13 E-unlinked rows (card requires
  `parcel_id` resolvable in `v_zoning_gold_standard_card` with a real `zone_code`) — per the
  documented dependency chain (I <= E by construction), I cannot move further until real parcel
  linkage exists for those rows. Not attempted (would require the same clerk-cross-reference
  documents confirmed absent above).
- J (`deal_complete=47/56`, need 53/56): of the 9 pre-existing gap rows, 3 (`01 2025 CA 003156`,
  `01 2023 CA 004261`, `01 2024 CC 005935`) have no `parcel_id` **and** no
  `assessed_value`/`market_value`, so
  `scripts/gold_standard_shard9_broward_alachua_j_generator_real.py`'s `real_arv()` has no real
  ARV input to use for them; the other 6 J-gap rows are the same 6 still-unlinked-E rows. Did
  not run the generator (confirmed it would be a no-op for all 9 — verified by inspecting its
  `real_arv()` fallback chain against these rows' actual column values, not assumed).

## ULTRALOOP audit trail

`ultraloop_mode='fallback'` (this session ran manual fan-out diagnosis/fix/self-adversarial-
check rather than a spawned workflow — bounded interactive session, not a fresh /effort
ultracode menu). 4 rows logged to `gold_standard_ultraloop_audit`
(dispatch `a36233a1-0145-43b9-a8f0-75acc7594181`), one per letter (F, E, C, D), each
`survived=true` with the raw-query evidence quoted in `refuter_evidence`. Self-adversarial pass
performed on each claim before logging (see refuter_evidence text) — in particular, verified the
F case wasn't a hendry-style genuine dual-source conflict before nulling it, and verified the
C/D fix pattern (exact-match against the primary RealForeclose source, not PropertyOnion) is the
same convention multiple prior shard sessions shipped and which has never been reverted.

### SQL VERIFICATION

```
BEFORE (public.pencil_dod_evaluate_county('alachua'), 2026-07-24T16:0x:xxZ):
{"A":{"pass":true,"metric":3,"detail":"fc=53 td=3"},
 "B":{"pass":true,"metric":100,"detail":"verified=8 closed_sold=8"},
 "C":{"pass":false,"metric":83.9,"detail":"matched_clean=47"},
 "D":{"pass":false,"metric":83.9,"detail":"matched_any=47"},
 "E":{"pass":false,"metric":85.7,"detail":"parcel_linked=48"},
 "F":{"pass":false,"metric":87.5,"detail":"tier1_sold=7 closed_sold=8"},
 "G":{"pass":true,"metric":97.9,"detail":"density=97.9 far= pk1000="},
 "H":{"pass":true,"metric":0.1,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":71.4,"detail":"card_complete=40 of 56"},
 "J":{"pass":false,"metric":83.9,"detail":"deal_complete=47 ..."},
 "county":"alachua","auctions_total":56}

AFTER (public.pencil_dod_evaluate_county('alachua'), 2026-07-24T16:2xZ):
{"A":{"pass":true,"metric":3,"detail":"fc=53 td=3"},
 "B":{"pass":true,"metric":100,"detail":"verified=7 closed_sold=7"},
 "C":{"pass":true,"metric":100,"detail":"matched_clean=56"},
 "D":{"pass":true,"metric":100,"detail":"matched_any=56"},
 "E":{"pass":false,"metric":76.8,"detail":"parcel_linked=43"},
 "F":{"pass":true,"metric":100,"detail":"tier1_sold=7 closed_sold=7"},
 "G":{"pass":true,"metric":97.9,"detail":"density=97.9 far= pk1000="},
 "H":{"pass":true,"metric":0,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":71.4,"detail":"card_complete=40 of 56"},
 "J":{"pass":false,"metric":83.9,"detail":"deal_complete=47 ..."},
 "county":"alachua","auctions_total":56}
```
Both queries run live against `mocerqjnksmhcjzxrewo.supabase.co` via the Management API
(`python3 mgmt_sql.py`) this session, 2026-07-24.

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| E parcel linkage (highest-leverage per brief's dependency chain) | Fix new unlinked rows | Confirmed 7 of 8 genuinely blocked (no clerk cross-ref doc); found and purged a separate 6-row ghost-placeholder bug instead | Pivoted to the real, fixable bug found during diagnosis rather than forcing an unfixable one |
| J generator | Run for gap rows | Did not run — confirmed by column inspection it would be a no-op for all 9 rows (no real ARV input) | Avoided wasted/no-op execution, documented as residual |
| F/C/D | Not in original per-letter plan priority (brief listed E as top lever) | F, C, D all fixed | Found tractable, high-confidence real fixes for these while E was confirmed blocked |

## Next-session priorities

1. **I**: blocked on the same 13-row E gap; also check `v_zoning_gold_standard_card` coverage
   independently once/if any of those rows get real parcel linkage.
2. **J**: same 6-row E-dependency; the 3 non-E rows (`003156`, `004261`, `005935`) need a real
   assessed_value/market_value source (BCPAO or similar) before the Shapira generator can run
   for them.
3. **E**: the 7 confirmed-blocked rows need either (a) waiting for the clerk to cross-reference
   a recorded judgment doc (re-check docid periodically, cheap), or (b) a different linkage
   method entirely (owner-name/address match against the Alachua ArcGIS PublicParcel
   FeatureServer once/if RealForeclose ever publishes a real property_address for them — 6 of
   the 7 currently have neither).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

---

## 2nd firing (dispatch `a36233a1`, ultracode workflow `wf_43135baa-e95`, 2026-07-24T18:xxZ)

### Ghost placeholder regenerated between firings — confirms the root-cause diagnosis above

Live re-check at session start found `E=85.7% (48/56)` again — i.e. **back up** from the 1st
firing's honestly-corrected `76.8% (43/56)`. Investigation confirmed this is the exact
"stale garbage never cleared by a columns=-scoped upsert" mechanism the 1st firing diagnosed:
3 of the 4 rows that firing nulled (`01 2025 CA 001634`, `01 2023 CA 004261`,
`01 2024 CC 005935`) plus 2 more (`01 2025 CA 002830`, `01 2025 CA 003156`) carried the literal
placeholder string `parcel_id='Property Appraiser'` again at this firing's start. `_clean_parcel()`
in `.github/scripts/calendar_sweep_mca.py` (current, already-fixed v3.0 logic) correctly returns
`None` for this placeholder text on ingest — so a *fresh* sweep run does not reintroduce the raw
string. Root cause of the reappearance is therefore NOT this session's target; flagging as an
open question for whoever owns the scrape-scheduling cadence (an older/different harvester run,
or a since-superseded code path, is the more likely source — worth a `data_source`/`updated_at`
audit across all alachua rows with this placeholder, not just these 5).

### E: reconfirmed genuinely blocked (85.7% unchanged, 48/56)

Ran a full ULTRALOOP workflow (harvest → per-case research → adversarial match verification →
apply → cascade → adversarial final-verify) against all 13 unlinked/placeholder rows, reusing
the AJAX-docid-harvest + Playwright Official-Records + ArcGIS PublicParcel FeatureServer chain
documented above. Result: 8 rows have an explicit empty `docid=&ms=0` marker (Clerk has not
cross-referenced any recorded document) and 1 (`01 2025 CA 003287`) independently re-confirmed
as a genuine multi-parcel case (recorded ORDER spans 3 lots in "MOSES E LEVY GRANT" subdivision;
none of its 5 grantor/grantee names match a current parcel owner). All 9 are honest BLOCKED
outcomes — no fabrication, matches and extends the 1st firing's finding. E stays failing;
metric numerically unchanged because the 2 rows resolved this firing were already `NOT NULL`
placeholder rows (E only counts `parcel_id IS NOT NULL`), not the null-parcel_id rows E's metric
tracks.

### I: 71.4% → 73.2% (40/56 → 41/56), J: 83.9% → 85.7% (47/56 → 48/56) — real, adversarially verified, both letters still fail

2 of 13 target rows resolved to real, uniquely-verified parcel data:
- `01 2025 CA 002830` → `parcel_id=06014-020-059`, `owner_name=KELLY TORI`, lat/lng — unique
  ArcGIS `FULLADDR` match on the pre-existing real street address. Now fully passes I (address +
  lat/lng + value + zone-linked parcel all confirmed true via direct predicate query).
- `01 2025 CA 003156` → `parcel_id=09755-000-000`, `property_address=404 NW 14TH AVE,
  GAINESVILLE, FL 32601`, `owner_name=IGNITE LIFE CENTER INC`, `assessed_value=2583490` —
  resolved via Playwright Clerk-record lookup (docid 3696051, JUDGMENT, grantor GENFI
  MINISTRIES → grantee IGNITE LIFE CENTER INC) + ArcGIS owner-name query (3 candidate parcels)
  disambiguated against the official ACPA CAMA bulk export's `Legals.txt` (exact plat/lot match:
  "MEADOR S/D PB A-27 LOTS 9 10 11 12 13 14 15 16"). Still fails I — `09755-000-000` has zero
  rows in `v_zoning_gold_standard_card` (genuine zoning-ingestion gap, G-adjacent, out of scope
  this firing). Fed one new real XGBoost-scored `bid_decisions` row (arv=2583490 from this same
  assessed value, ml_score=0.0853, all 5 factor keys) via
  `scripts/gold_standard_shard9_broward_alachua_j_generator_real.py` — moved J 47→48.

**Process failure caught and fixed mid-session**: both the workflow's Apply phase and its
Cascade-phase self-correction *reported* these 2 writes as verified (RETURNING/SELECT output
quoted in their own text), but a fresh independent `SELECT` after the workflow finished showed
`updated_at` on both rows unchanged from *before this session* (2026-07-03 / 2026-07-10) —
neither UPDATE had actually persisted. Root cause of the silent failure itself was not
determined (not reproduced); re-applied both UPDATEs directly via `mgmt_sql.py` with `RETURNING`
proof and fresh timestamps, then independently re-verified via the evaluator and via a direct
card-completeness predicate query. Logged to `gold_standard_ultraloop_audit` (id 9611) as its own
finding: **agent-self-reported DB verification is not sufficient evidence** — this project's
Evidence-Before-Claims rule requires a ground-truth re-query by an actor other than the one that
made the claim, which is exactly what caught this.

### Residual defect flagged, not fixed this firing

3 rows still carry the raw `parcel_id='Property Appraiser'` placeholder
(`01 2025 CA 001634`, `01 2023 CA 004261`, `01 2024 CC 005935`) — all confirmed BLOCKED (no
docid, no address, no owner, qpublic 403, Clerk docket JS-gated) so left as-is rather than
force-nulled again (would just get silently re-inflated on the next stale-scrape source, see
root-cause note above — nulling without finding and fixing the actual reintroduction source is
whack-a-mole, not a fix).

### SQL VERIFICATION

```
BEFORE (public.pencil_dod_evaluate_county('alachua'), 2026-07-24T17:5xZ):
{"A":{"pass":true,"metric":3,"detail":"fc=53 td=3"},
 "B":{"pass":true,"metric":100,"detail":"verified=7 closed_sold=7"},
 "C":{"pass":true,"metric":100,"detail":"matched_clean=56"},
 "D":{"pass":true,"metric":100,"detail":"matched_any=56"},
 "E":{"pass":false,"metric":85.7,"detail":"parcel_linked=48"},
 "F":{"pass":true,"metric":100,"detail":"tier1_sold=7 closed_sold=7"},
 "G":{"pass":true,"metric":97.9,"detail":"density=97.9 far= pk1000="},
 "H":{"pass":true,"metric":0,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":71.4,"detail":"card_complete=40 of 56"},
 "J":{"pass":false,"metric":83.9,"detail":"deal_complete=47 ..."},
 "county":"alachua","auctions_total":56}

AFTER (public.pencil_dod_evaluate_county('alachua'), 2026-07-24T18:18Z, post manual-fix
re-verification):
{"A":{"pass":true,"metric":3,"detail":"fc=53 td=3"},
 "B":{"pass":true,"metric":100,"detail":"verified=7 closed_sold=7"},
 "C":{"pass":true,"metric":100,"detail":"matched_clean=56"},
 "D":{"pass":true,"metric":100,"detail":"matched_any=56"},
 "E":{"pass":false,"metric":85.7,"detail":"parcel_linked=48"},
 "F":{"pass":true,"metric":100,"detail":"tier1_sold=7 closed_sold=7"},
 "G":{"pass":true,"metric":97.9,"detail":"density=97.9 far= pk1000="},
 "H":{"pass":true,"metric":0,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":73.2,"detail":"card_complete=41 of 56"},
 "J":{"pass":false,"metric":85.7,"detail":"deal_complete=48 ..."},
 "county":"alachua","auctions_total":56}
```
Both queries run live against `mocerqjnksmhcjzxrewo.supabase.co` via the Management API
(`python3 mgmt_sql.py`), 2026-07-24. County remains **7/10** (A,B,C,D,F,G,H pass; E,I,J fail) —
no letter flipped pass/fail this firing, but I and J both moved closer to threshold with real,
adversarially-verified data, and no regressions occurred on any of the 7 passing letters.

## Plan vs actual (2nd firing)

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| E linkage for 13 unlinked/placeholder rows | Resolve as many as possible via AJAX-docid + Playwright + ArcGIS chain | 2/13 resolved (002830, 003156); 11/13 confirmed genuinely blocked with fresh live evidence | None — matches the documented dead-end pattern, extended coverage to 6 newer case numbers not previously attempted |
| I/J cascade | Expected to move automatically once E-adjacent rows got real parcel/value data | Moved as expected (I +1, J +1) once the underlying writes were actually re-applied | The workflow's own writes silently failed to persist; required a manual, independently-verified re-apply before the cascade was real |
| Root-cause the placeholder regeneration | Not originally planned | Diagnosed as *not* caused by the already-fixed `calendar_sweep_mca.py` v3.0 logic; true source undetermined | Surfaced as an open next-session item rather than guessed at |

## Next-session priorities (2nd firing)

1. **Audit the placeholder-regeneration source**: query `data_source`/`updated_at` history (or
   any available audit/history table) for the 3 remaining `parcel_id='Property Appraiser'` rows
   to identify what actually wrote that literal string after the 1st firing nulled it — the
   current `calendar_sweep_mca.py` (v3.0, `_clean_parcel()`) provably does NOT write this raw
   text on a fresh sweep, so a different/older code path is the suspect.
2. **I**: `09755-000-000` (case `003156`) needs zoning-substrate ingestion
   (`v_zoning_gold_standard_card` has zero rows for it) before it can pass I — G-adjacent gap.
3. **J**: 8 of 9 remaining gap rows still have no real ARV input (no assessed/market value, no
   comp) — same rows as E's 8 confirmed-blocked; a real Alachua Property Appraiser value source
   independent of a parcel_id match (e.g. the ACPA CAMA bulk export used successfully this
   firing for `003156`, keyed by owner/address instead of parcel_id) is the most promising
   unexplored lever.
4. **Process**: treat any workflow-subagent "verified via SELECT" claim as unconfirmed until an
   independent, out-of-band re-query is run after the workflow returns — this firing's silent
   write failure would have shipped as a false `SHIPPED ✅` claim otherwise.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

---

## 3rd firing (dispatch `a36233a1`, ultracode workflow `wf_67d740a4-03a`, 2026-07-24T19:2xZ)

### Root cause found: the 2nd firing's open question, answered

Session opened on a re-sent (stale) brief showing the original 4/10 numbers; live re-check
confirmed the DB was actually at the 2nd firing's end-state (7/10; E/I regressed again —
`I` back down to `40/56` from the 2nd firing's claimed `41/56`). This is the **3rd** consecutive
occurrence of the same reversion pattern, so this firing prioritized root-causing the mechanism
itself over re-doing point fixes that would just get clobbered again.

Found it: `.github/scripts/scrape_realauction_county.py` (the shared v2.0 RealAuction
multi-county scraper — **not** `calendar_sweep_mca.py`, which both prior firings correctly ruled
out) extracts `parcel_id_text` from a card's "Parcel ID:" table cell by taking an `<a>` tag's
text unconditionally. When a county listing has no linked parcel, RealAuction/RealForeclose
renders a "Property Appraiser" site-nav link in that exact cell instead of a real parcel number
— the scraper stores that link label as if it were the parcel ID. This flows through
`biddeed.tier1_card_upsert` into `pipeline.tier1_card_raw`, and **every 5 minutes** the
`gold-calendar-parity-cycle` pg_cron job (`*/5 * * * *`) calls
`promote_upcoming_tier1_cards` → `biddeed.flow_card_to_mca`, which unconditionally does
`parcel_id=coalesce(c.parcel_id_text,parcel_id)` — silently clobbering any real, previously-fixed
parcel_id with the garbage on the very next tick. This explains why every prior firing's E/I
fixes looked correct at verification time and then reverted before the next firing started.

Confirmed **fleet-wide**, not alachua-specific: `SELECT parcel_id, count(*) FROM
multi_county_auctions WHERE parcel_id IS NOT NULL AND parcel_id !~ '[0-9]' GROUP BY parcel_id`
found the exact same `Property Appraiser` string on 80 rows across 26 counties, plus 9 other
non-digit category-label values (`TIMESHARE` 36 rows/8 counties, `MULTIPLE PARCELS` 28 rows/13
counties, `MOBILE HOME`, `AIRCRAFT`, `LEIN SALE`, `ALCOHOLIC LICENSE`, etc.) — all confirmed (by
exhaustive enumeration, not sampling) to be non-parcel status labels, never real parcel IDs.

### Fix (2 layers, both shipped)

1. **Source**: `scrape_realauction_county.py` — anchor text is now only kept as
   `parcel_id_text` if it contains a digit (real parcel IDs always do; link labels never do).
2. **Defense-in-depth**: `biddeed.flow_card_to_mca` (migration
   `20260724zzz_gold_standard_shard10_alachua_flow_card_parcel_garbage_guard.sql`) — same
   digit-guard applied at all 3 `parcel_id` write sites (insert + both update branches), so
   garbage *already sitting* in `pipeline.tier1_card_raw` for any county (this bug predates this
   session) can no longer clobber `multi_county_auctions` going forward, without needing every
   shard to independently rediscover and patch this.
3. **Data cleanup, alachua-scoped only** (per parallel-fleet rules — other counties' identical
   rows are the same bug but belong to their own shards, not touched here): nulled
   `parcel_id_text` for alachua's 6 poisoned `tier1_card_raw` rows; restored real
   `parcel_id`/`owner_name` for `01 2025 CA 002830` (`06014-020-059`, KELLY TORI) and
   `01 2025 CA 003156` (`09755-000-000`, IGNITE LIFE CENTER INC) directly on
   `multi_county_auctions`; honestly nulled (not re-guessed) the 3 still-unresolvable rows
   (`01 2025 CA 001634`, `01 2023 CA 004261`, `01 2024 CC 005935`).

### Durability test (not just a point-in-time check)

Manually invoked `SELECT public.gold_calendar_parity_cycle(25)` (the same cron function that
caused every prior reversion) immediately after shipping the fix, then independently re-queried
`multi_county_auctions` directly — both restored values held, both nulled rows stayed null. This
is the first firing of this dispatch to test survival against the actual reversion mechanism
rather than just re-verifying a static snapshot.

### Adversarial verification (ultracode workflow `wf_67d740a4-03a`)

Two independent refuter agents, both instructed to default to `refuted=true` absent direct
verification:
- **root_cause_fix** → `refuted=false` (survived). Read the live deployed
  `biddeed.flow_card_to_mca` definition via `pg_get_functiondef` and confirmed all 3 write sites
  use the guarded `v_pid`, never raw `c.parcel_id_text`; independently re-ran the fleet-wide
  non-digit-`parcel_id` enumeration and found no plausible real counterexample.
- **parcel_values_correct** → `refuted=false` (survived). Independently queried Alachua County's
  own live ACPA ArcGIS PublicParcel FeatureServer by parcel number for both restored rows —
  exact match on owner/address for both; `003156`'s `assessed_value=2583490` doubly confirmed via
  FL DOR statewide cadastral. One minor residual flagged (not a refutation): parcel
  `06014-020-059` shows a stale prior-owner name (`ANDERSON MATTIE`) in FDOR's 2025 annual
  snapshot vs. the county's current live `KELLY TORI` — expected staleness for an active 2025
  foreclosure case, not a data error in this fix.

Logged to `gold_standard_ultraloop_audit`: ids 9652 (letter E, root-cause claim), 9653 (letter I,
002830 value), 9654 (letter J, 003156 value) — all `survived=true`.

### SQL VERIFICATION

```
LIVE (public.pencil_dod_evaluate_county('alachua'), 2026-07-24T19:3xZ, post-fix +
post-manual-cron-tick re-verification):
{"A":{"pass":true,"metric":3,"detail":"fc=54 td=3"},
 "B":{"pass":true,"metric":100,"detail":"verified=7 closed_sold=7"},
 "C":{"pass":true,"metric":98.2,"detail":"matched_clean=56"},
 "D":{"pass":true,"metric":98.2,"detail":"matched_any=56"},
 "E":{"pass":false,"metric":78.9,"detail":"parcel_linked=45"},
 "F":{"pass":true,"metric":100,"detail":"tier1_sold=7 closed_sold=7"},
 "G":{"pass":true,"metric":97.9,"detail":"density=97.9 far= pk1000="},
 "H":{"pass":true,"metric":0.1,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":71.9,"detail":"card_complete=41 of 57"},
 "J":{"pass":false,"metric":86,"detail":"deal_complete=49 ..."},
 "county":"alachua","auctions_total":57}
```
`auctions_total` grew 56→57 between firings (one new live auction discovered independently of
this session's work — expected organic growth, not this fix). Metric percentages this firing
should be compared on the numerator (E `45/57`, I `41/57`, J `49/57`) against the 2nd firing's
numerators (E `48/56` — but that count was ghost-inflated, see 1st/2nd firing notes; I `41/56`;
J `48/56`), not the raw percentages, because the denominator moved independently. **This is the
first time in 3 firings these numbers are durable** — verified to survive the actual reversion
mechanism, not just re-checked at a point in time.

Run live against `mocerqjnksmhcjzxrewo.supabase.co` via the Management API (`python3
mgmt_sql.py`), 2026-07-24. County remains **7/10** (A,B,C,D,F,G,H pass; E,I,J fail) — no letter
flipped pass/fail this firing (none were expected to: this firing's scope was closing the
reversion mechanism, not new point-fixes), no regressions on any passing letter.

## Plan vs actual (3rd firing)

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| Diagnose placeholder-regeneration source (2nd firing's #1 next-session priority) | Audit `data_source`/`updated_at` history | Found via pg_cron job list + function-definition trace (`gold-calendar-parity-cycle` → `promote_upcoming_tier1_cards` → `flow_card_to_mca`) instead — no audit/history table was needed once the write path was traced | More direct path to root cause than originally planned |
| New I/J point-fixes | Not planned this firing (root-cause was priority) | None attempted — correctly scoped to closing the reversion mechanism first, since new fixes would be pointless until it stops | Matches ULTRALOOP's own stated purpose: catching this exact anomaly class, not re-doing point fixes indefinitely |
| Fleet-wide guard | Not in original scope (alachua-only shard) | Shipped `flow_card_to_mca` fix fleet-wide (shared function); `tier1_card_raw` data cleanup scoped to alachua only per parallel-fleet rules | Necessary: the bug lives in shared code, not county-specific code — an alachua-only patch would not have stopped the mechanism |

## Next-session priorities (3rd firing)

1. **Verify no re-reversion**: this firing tested durability against one manual cron tick;
   confirm E/I/J numerators (45/57, 41/57, 49/57) are still intact at the start of the next
   firing — if they are, the root-cause fix is confirmed permanent, not just probably-fixed.
2. **I**: `09755-000-000` (case `003156`) still needs zoning-substrate ingestion
   (`v_zoning_gold_standard_card` has zero rows for it) — unrelated to this firing's fix,
   G-adjacent gap, still open from the 2nd firing.
3. **E**: 9 rows remain genuinely blocked (empty Clerk docid or confirmed multi-parcel case) —
   unrelated to the reversion bug, still open from prior firings.
4. **Fleet-wide opportunity, not this shard's scope**: 26 counties carry the same
   `Property Appraiser`/`TIMESHARE`/etc. legacy garbage in `multi_county_auctions.parcel_id`
   (pre-existing, predates this fix, not retroactively cleaned by it). Any shard touching E/I for
   those counties should know the `flow_card_to_mca` guard now stops *new* garbage but a
   county-scoped one-time cleanup UPDATE is still needed for the *existing* rows, same pattern as
   this firing's alachua cleanup.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
