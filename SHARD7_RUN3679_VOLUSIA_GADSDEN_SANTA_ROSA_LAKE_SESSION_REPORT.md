# SHARD-7 Session Report — volusia, gadsden, santa_rosa, lake

- issue: `breverdbidder/cli-anything-biddeed#11637` — "GOLD STANDARD SHARD-7: volusia, gadsden,
  santa_rosa, lake — parallel 6h session (SHIP TO MAIN)"
- loop run: 3679 (per brief)
- date: 2026-07-11
- mode: fix-phase (parallel builder agents) → adversarial verify-phase (independent re-check) →
  this closeout step

## Ship-to-main status

All fix-phase commits already landed on `main` before this closeout step began (confirmed via
`git log` and a clean `git status`). No new schema/DDL was attempted — DML only, per the DB
ACCESS guardrails (no working generic SQL-exec RPC, no `supabase` CLI, direct `psycopg2` to the
pooler unavailable in this sandbox). All reads/writes went through PostgREST
(`{SUPABASE_URL}/rest/v1/...` and `rpc/pencil_dod_evaluate_county`). This closeout adds one
report file and pushes directly to `main` — no branches, no PRs, per the issue's explicit
no-human-reviewer-in-this-loop instruction.

## Fresh verification run (this step, immediately before writing this report)

Ran `pencil_dod_evaluate_county` fresh for all four counties, right now, as the literal basis for
every number below.

```json
{
  "volusia": {"A":{"pass":true,"metric":94,"detail":"fc=94 td=279"},
              "B":{"pass":true,"metric":100.0,"detail":"verified=175 closed_sold=175"},
              "C":{"pass":true,"metric":98.1,"detail":"matched_clean=366"},
              "D":{"pass":true,"metric":98.9,"detail":"matched_any=369"},
              "E":{"pass":true,"metric":100.0,"detail":"parcel_linked=373"},
              "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=175 closed_sold=175"},
              "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},
              "H":{"pass":true,"metric":9.2,"detail":"hours since last_seen (SLA 48h)"},
              "I":{"pass":true,"metric":98.4,"detail":"card_complete=367 of 373"},
              "J":{"pass":true,"metric":100.0,"detail":"deal_complete=373"},
              "auctions_total":373},
  "gadsden": {"A":{"pass":true,"metric":7,"detail":"fc=16 td=7"},
              "B":{"pass":true,"metric":100.0,"detail":"verified=1 closed_sold=1"},
              "C":{"pass":true,"metric":95.7,"detail":"matched_clean=22"},
              "D":{"pass":true,"metric":95.7,"detail":"matched_any=22"},
              "E":{"pass":false,"metric":78.3,"detail":"parcel_linked=18"},
              "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=1 closed_sold=1"},
              "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},
              "H":{"pass":true,"metric":0.7,"detail":"hours since last_seen"},
              "I":{"pass":false,"metric":30.4,"detail":"card_complete=7 of 23"},
              "J":{"pass":true,"metric":100.0,"detail":"deal_complete=23"},
              "auctions_total":23},
  "santa_rosa": {"A":{"pass":true,"metric":22,"detail":"fc=54 td=22"},
              "B":{"pass":true,"metric":100.0,"detail":"verified=31 closed_sold=31"},
              "C":{"pass":true,"metric":100.0,"detail":"matched_clean=76"},
              "D":{"pass":true,"metric":100.0,"detail":"matched_any=76"},
              "E":{"pass":true,"metric":96.1,"detail":"parcel_linked=73"},
              "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=31 closed_sold=31"},
              "G":{"pass":true,"metric":100.0,"detail":"density=100.0 far= pk1000="},
              "H":{"pass":true,"metric":0.7,"detail":"hours since last_seen"},
              "I":{"pass":false,"metric":86.8,"detail":"card_complete=66 of 76"},
              "J":{"pass":true,"metric":100.0,"detail":"deal_complete=76"},
              "auctions_total":76},
  "lake": {"A":{"pass":true,"metric":11,"detail":"fc=87 td=11"},
              "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
              "C":{"pass":false,"metric":13.3,"detail":"matched_clean=13"},
              "D":{"pass":false,"metric":27.6,"detail":"matched_any=27"},
              "E":{"pass":false,"metric":74.5,"detail":"parcel_linked=73"},
              "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},
              "G":{"pass":false,"metric":0.0,"detail":"density=23.3 far=0.0 pk1000=0.0"},
              "H":{"pass":true,"metric":0.4,"detail":"hours since last_seen"},
              "I":{"pass":false,"metric":39.8,"detail":"card_complete=39 of 98"},
              "J":{"pass":true,"metric":95.9,"detail":"deal_complete=94"},
              "auctions_total":98}
}
```

## volusia — 10/10, still all-PASS, NO REGRESSION

Volusia was reported as already 10/10 all-PASS at session start with no assigned fix work this
run. Fresh re-check confirms it is **still 10/10, all PASS**, byte-for-byte consistent with the
session-start baseline (A=94% fc/td split, B=100%, C=98.1%, D=98.9%, E=100%, F=100%, G=100%,
H=9.2h, I=98.4%, J=100%). No shared-code change from the santa_rosa/lake/gadsden fix work this
session touched volusia's scoring. Confirmed clean — not a P0, nothing to flag.

## gadsden — 8/10, one real letter improved (E), I genuinely blocked

**Before → After:**

| Letter | Before | After | Verify survived? | Status |
|---|---|---|---|---|
| E | FAIL, `parcel_linked=17`, 73.9% | FAIL, `parcel_linked=18`, 78.3% | **true** | Real, verified improvement. Still short of 95.65% (22/23) needed to pass. |
| I | FAIL, `card_complete=7 of 23`, 30.4% | FAIL, `card_complete=7 of 23`, 30.4% | **true** | Unchanged — correctly reported as blocked, no fabrication attempted. |

Fix: linked foreclosure case `25000545CA` (defendant "Est. of Kourogenis") to parcel
`1-33-4N-6W-0000-00431-0400` via a unique nationwide owner-name match (KOUROGENIS ANASTASIA)
against `fl_parcels` (co_no=30, real Gadsden FL GIO cadastral data). Independent verifier
spot-checked the parcel record, confirmed the write (address, assessed_value, lat/lng all
persisted, non-PropertyOnion data_source `clerk_fc:gadsdenclerk.com`), and confirmed the fresh
RPC call matches the claim exactly. **Survived.**

**Blocked, honestly:**
- **E** capped at 18/23: the 5 remaining NULL-parcel_id rows all failed a conservative
  single-candidate-only owner-name match rule — every remaining surname (Burger, Ramon's
  Construction, Booker-Barnes, Woods, White) either has multiple real ArcGIS/`fl_parcels`
  candidates with no way to disambiguate, or the source case is no longer present on the live
  Clerk sheet to re-verify. Writing any of these would mean guessing between real owners/parcels
  — explicitly forbidden by BLANK > WRONG and the quarantined `shard7_lake_e_i_fix.py` precedent.
- **I** capped at 7/23 (30.4%): the only 7 rows currently satisfying the zoning-card join carry a
  synthetic `zone_code='R-1'` explicitly labeled `HYPOTHESIS` in `zone_standards.description`
  (`parcel_zones.source='shard8_gadsden_bootstrap_synthetic'`) from a prior quarantined bootstrap
  script. `fl_parcels WHERE co_no=30` (real Gadsden cadastral data) has **zero** rows with
  non-null `zone_code`/`future_land_use` — no real per-parcel zoning source exists in this DB for
  Gadsden. Live-fetch attempts to `gadsdencountyfl.gov`, `qpublic.net/fl/gadsden`,
  `qpublic.schneidercorp.com`, and `gadsdenpa.com` all returned HTTP 403 (Cloudflare-blocked to
  this sandbox's UA — consistent with the prior SHARD12_RUN3497 finding). `library.municode.com`
  was reachable but ordinance text alone can't produce a real per-parcel zone assignment without
  a GIS spatial join. Correctly refused to extend the synthetic R-1 label to more parcels.

## santa_rosa — 9/10, two letters flipped to PASS, one real gain short of threshold

**Before → After:**

| Letter | Before | After | Verify survived? | Status |
|---|---|---|---|---|
| B | FAIL, `verified=0 closed_sold=0`, null | **PASS**, `verified=31 closed_sold=31`, 100.0% | **true** | Shipped. Within the 95–105% canonical band. |
| F | FAIL, `tier1_sold=0 closed_sold=0`, null | **PASS**, `tier1_sold=31 closed_sold=31`, 100.0% | **true** | Shipped. |
| I | FAIL, `card_complete=54 of 76`, 71.1% | FAIL, `card_complete=66 of 76`, 86.8% | **true** | Real, verified improvement. Still short of 95% (73/76). |

B and F fix: pulled the authenticated `santarosa.realforeclose.com` Auction Results Report
(`report_id=18`) — an independent Clerk/RealAuction post-sale ledger, not our own scraper's
guess, not PropertyOnion. 31 rows matched with real `sold_amount` values; 2 `Cancelled`-status
rows with stray bid figures were deliberately excluded to avoid a false "sold" count. Independent
verifier re-fetched the source, confirmed no PropertyOnion contamination, confirmed the metric
lands cleanly inside the 95–105% band, and confirmed referential integrity between
`multi_county_auctions` and `foreclosure_outcomes`. **Both survived.**

I fix: 13 new `parcel_zones` rows from Santa Rosa County's own public ArcGIS
(`ParcelsOpenData` + `Zoning` FeatureServers, owner `gisupdates_SantaRosaGIS`), plus 5
`zoning_districts`/`zone_standards` rows backed by real codified density figures from the county's
own LDC (Table 2.04.02) — specifically to avoid causing a Letter-G regression the way lake's I fix
did. Verifier confirmed the 5 zone codes (AG-RR, R1, R1M, R2M, PUD) have real
non-placeholder standards and that G held at 100%. **Survived**, but still 10 rows short of the
95% (73/76) threshold.

**Blocked, honestly (I residual, 10 rows):**
- 3 rows have no `parcel_id` at all — that's Letter E's scope, not I's, and E already passes at
  96.1%, so deliberately not touched to avoid risking a regression there.
- 6 rows resolve to a real parcel centroid, but a spatial point-in-polygon query against the
  county's own Zoning FeatureServer at that centroid returns only a coarse `DISTRICT=CITY`
  municipal-boundary marker, not a real zoning district code.
- 1 row (an HOA-owned vacant lot) has no `assessed_value`/`market_value` field available anywhere
  in the county's public ArcGIS parcel layer (confirmed via a full field-list query).

An AcclaimWeb (`acclaim.srccol.com`) Clerk official-records fallback was also explored per the
issue's standing authorization before the RealForeclose path was confirmed working; the search
form POSTed cleanly (HTTP 200) but the server-side AJAX search never registered a query
(`GET /Search/HasResults` returned `False` regardless of form fields). No data read or written
from this path — abandoned once RealForeclose was confirmed live.

## lake — 3/10 (A, H, J pass), one real letter improved (I), one honest regression disclosed (G), rest genuinely blocked

**Before → After:**

| Letter | Before | After | Verify survived? | Status |
|---|---|---|---|---|
| I | FAIL, `card_complete=11 of 98`, 11.2% | FAIL, `card_complete=39 of 98`, 39.8% | **true** | Real, verified improvement. Still far short of 95%. |
| G | PASS, 100.0% | FAIL, `density=23.3 far=0.0 pk1000=0.0`, 0.0% | **true** (regression confirmed genuine) | **Disclosed regression**, not hidden. |
| B | FAIL, null | FAIL, null (unchanged) | **true** | Genuinely blocked — real-world ceiling, not a scraper gap. |
| F | FAIL, null | FAIL, null (unchanged) | **true** | Same root cause as B. |
| C | FAIL, 13.3% | FAIL, 13.3% (unchanged) | **true** | Genuine litmus-source ceiling, no new matches found. |
| D | FAIL, 27.6% | FAIL, 27.6% (unchanged) | **true** | Same ceiling as C. |
| E | FAIL, 74.5% | FAIL, 74.5% (unchanged) | **true** | Owner-name matcher re-run fresh, 0 new matches — at or near real ceiling. |

I fix: 33 new/updated `parcel_zones` rows sourced from Lake County's own live zoning GIS layer
(`gis.lakecountyfl.gov/InteractiveMap/MapServer/50`), a real point-in-polygon query against each
parcel's already-real lat/lon. Root cause of the prior low score: the substrate join for
jurisdiction 835 only had 15 rows, all a synthetic blanket `zone_code='R-1'` from the quarantined
`shard7_g_i_fix` script. 36 of 73 parcel-linked rows hit real zoning (unincorporated county land);
37 fall inside incorporated municipalities not covered by this layer and were deliberately left
untouched rather than defaulted. Verifier confirmed real, diverse zone codes (A, CFD, PUD, R-3,
R-6, R-7, RM), clean data sources, no fabrication patterns. **Survived.**

**G regression — verified genuine, not swept under the rug:** the prior 100% G pass rested
entirely on `zoning_districts id=10716`, whose own `name` column literally read
`"Single Family Residential (Shard7 Synthetic)"`, backed by `zone_standards id=3401` with
hardcoded `max_far=0.35`/`max_density_du_acre=4.0`/`parking_per_1000sf=2.0` and
`source_url`/`ordinance_section`/`confidence_score` all NULL — i.e., G's earlier "pass" for lake
was itself resting on the same fabrication this session was tasked to clean up. The new real zone
codes have no `zoning_districts`/`zone_standards` rows yet, so G correctly now scores as
missing-standards (0%) rather than a fabricated 100%. **Not** patched with a fabricated
replacement standard — real Lake County LDR/Municode dimensional-standards scraping is out of
scope for this session's assigned letters and is called out below as the next-session priority.
Independent verifier confirmed the root cause and confirmed the builder disclosed this openly in
the commit message rather than hiding it.

**Blocked, honestly:**
- **B/F**: the only closed Lake auction (TD case `00389-2023`) shows `Auction Status=Redeemed` on
  the live `lake.realtaxdeed.com` Preview page — a redemption has no sold_amount by definition,
  independent of scraping effort. Lake has no RealForeclose FC platform at all (confirmed via the
  RealAuction county picker — only "Lake Taxdeed" is listed). Two stale statuses were corrected
  honestly (`00389-2023`: sold→redeemed; `02731-2022`: upcoming→canceled_bankruptcy per
  bankruptcy filing shown live) — no sold amounts fabricated. This is a genuine "nothing has sold
  yet" real-world ceiling, not a data gap.
- **C/D**: the FC lane (87 of 98 rows) has only 18 reachable PropertyOnion litmus cross-references
  (`po_mca_matches`), all already wired to a tier1 parity_source by a prior session. A direct
  case_number join against 668 archived PropertyOnion rows for lake found 0 overlaps (PO archive
  uses synthetic `PO-nnnnnnn` case numbers for most rows, not real court case numbers). Reaching
  95% would need ~83 more FC matches via either a new fuzzy address/owner matcher (out of scope
  for a DML-only session) or an authenticated Lake Clerk records session (unavailable here).
- **E**: re-ran the existing conservative owner-name matcher
  (`scripts/shard14_lake_e_ownername_match.py`, dry-run) against all 25 remaining unlinked rows —
  0 new unique matches; every candidate was either ambiguous (multiple ArcGIS `OwnerName` hits
  sharing the surname token) or had zero/too-common hits to disambiguate safely. At or very near
  the real ceiling for this matching strategy against this data source.
- **I residual** (59 rows still incomplete beyond the 39 fixed): 37 rows fall inside incorporated
  municipalities not covered by the county zoning layer used this session; the rest trail E's own
  unresolved 25-row gap (no parcel_id) and other data-completeness gaps out of I's direct scope.

## ULTRALOOP audit trail

Every claim above corresponds to an independent adversarial verify-phase row (see dispatch input)
run against a fresh `pencil_dod_evaluate_county` call and, where applicable, direct spot-checks of
the underlying source rows. **All 12 claims across the 3 worked counties survived** adversarial
verification (`survived=true`) — none were refuted this session. This is unusually clean for a
shard session; it reflects that every fix agent this run either shipped a real, narrowly-scoped
improvement or correctly reported a blocker without attempting to launder a fabricated pass.
Audit rows logged to `gold_standard_ultraloop_audit` per county/letter (dispatch_id
`9fe2973e-44ea-441c-9770-92ff736483dd` for gadsden/santa_rosa/lake I claims, additional row ids
noted inline in the verify evidence above).

## Plan vs actual

| Task | Planned | Actual | Deviation |
|---|---|---|---|
| volusia (no assigned work) | Confirm still 10/10, no regression | Confirmed still 10/10, byte-identical to baseline | None. |
| gadsden E/I → 95% | Fix as many rows as safely possible | E: 17→18/23 (73.9%→78.3%), real but short. I: unchanged, correctly blocked (synthetic-zoning ceiling) | Both real progress or honest blocker; neither flips PASS this session. |
| santa_rosa B/F/I → 95% | Fix all 3 | **B and F flipped to PASS** (100%/100%). I: 54→66/76 (71.1%→86.8%), real but short of 95% | 2 of 3 shipped; I improved substantially but not enough alone. |
| lake I/B/F/C/D/E → 95% | Fix as many as safely possible | I: 11→39/98 (11.2%→39.8%), real but far short. B/F/C/D/E: all genuinely blocked, correctly reported unchanged. G: honest regression (100%→0%) from cleaning up a fabricated standard | Real gain on I, disclosed regression on G, rest correctly blocked with no fabrication. |
| Run `gold_standard_loop()`/`certify()` | Only if a county reaches 10/10 | Not run — no county reached 10/10 this session | Per SHIP GATE, correctly skipped. |
| Telegram notification (fire_workflow_dispatch) | Only if a county reaches 10/10 | Not fired — no county reached 10/10 | Per instructions, correctly skipped. |

## Scoreboard

- **volusia**: 10/10, unchanged, no regression confirmed.
- **gadsden**: 8/10 (unchanged letter count — E and I both still FAIL, but E's underlying metric
  moved 73.9%→78.3%, a real verified gain not yet enough to flip the letter).
- **santa_rosa**: 9/10 (**up from 7/10** — B and F both flipped FAIL→PASS this session; I moved
  71.1%→86.8%, real gain, still FAIL).
- **lake**: 3/10 (A, H, J pass — down from what would nominally look like 4/10 if G's fabricated
  pass were still counted, but that "4/10" was resting on a fabricated zone standard). Honest
  count is 3/10 both before and after this session's I fix: I improved 11.2%→39.8% real (still
  FAIL), while G's fake pass was correctly replaced by an honest fail once its fabricated basis
  was removed as a side effect of the legitimate I fix. Net letter-count is unchanged at 3/10, but
  the underlying data is now materially more honest than before.

No county reached 10/10 this session. Per the SHIP GATE mandate, **no letter is being claimed
"SHIPPED"/certified** beyond what fresh verification directly supports; `gold_standard_loop()`/
`gold_standard_certify()` were not invoked, and the Telegram `fire_workflow_dispatch` notification
is correctly being skipped this session.

## Next-session priorities

1. **gadsden I**: needs a real per-parcel zoning source for Gadsden County. Every county GIS/
   appraiser endpoint tried this session (gadsdencountyfl.gov, qpublic.net/fl/gadsden,
   qpublic.schneidercorp.com, gadsdenpa.com) 403s from this sandbox's UA — try from a different
   egress path or with browser automation (Firecrawl/Playwright) before assuming it's unreachable
   entirely. Do not extend the existing synthetic R-1 placeholder to more parcels.
2. **gadsden E**: the remaining 5 rows need either an authenticated Clerk case-search session (to
   re-pull the current defendant/case details for `Woods`/`White`, which have dropped off the live
   sheet) or a smarter disambiguation signal beyond bare surname match (e.g. cross-referencing
   property address fragments against `fl_parcels` situs address, if any partial address exists
   in the case record) for `Burger`/`Ramon's Construction`/`Booker-Barnes`.
3. **santa_rosa I**: 10 rows from 95% (73/76). 3 need E-lane parcel linkage first (deliberately
   not touched this session to protect E's 96.1% pass) — do that as a separate, careful pass. 6
   need a real (non-`CITY`-marker) zoning district lookup — may require a different Santa Rosa GIS
   layer or a manual review of those 6 specific parcels. 1 has no value source anywhere in the
   county's public data at all — likely a genuine dead end absent a new source.
4. **lake G**: needs real, sourced dimensional zoning standards (max FAR, max density, parking
   ratio) for the 7 new real zone codes (A, PUD, R-6, R-7, RM, R-3, CFD) from Lake County's actual
   LDR/Municode — this is the highest-leverage single fix available for lake, since it would
   restore G to a real (not fabricated) pass and is a bounded, well-scoped scrape.
5. **lake B/F**: structurally blocked until a Lake auction actually closes with a sale (vs.
   redemption/cancellation) — re-check `lake.realtaxdeed.com` periodically rather than re-running
   the same probe; also worth checking whether `or.lakecountyclerk.org` (official records) ever
   becomes reachable, since it failed to resolve entirely this session.
6. **lake C/D**: would need either a genuinely new fuzzy address/owner matcher against the FC lane
   (real engineering effort, not a quick DML fix) or an authenticated Lake Clerk records session —
   flag as a candidate for a dedicated future session rather than another shard-style quick pass.
