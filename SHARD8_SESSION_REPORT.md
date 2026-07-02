# SHARD-8 Session Report — martin, columbia, lake (2026-07-02)

Dispatch: `e8753921-4814-4a11-be35-839594f91e8b`. Interactive session, not a scheduled GHA run.
`loop run 2346` in the brief was already 30-90 min stale by session start — re-verified everything
live via `pencil_dod_evaluate_county` before doing any work, per Evidence-Before-Claims.

## Headline finding: fabricated data in the live Gold Standard scoreboard (columbia, lake)

Before touching anything, live verification surfaced that the brief's numbers for columbia and
lake did not match the underlying data honestly. Investigation found **fabricated placeholder
auction rows in production**, not a metrics/scraper gap:

- **columbia — ALL 9 rows in `multi_county_auctions` were fake.** `case_number` values like
  `COLUMBIA-TD-2026-001`, `parcel_id` literally prefixed `SYN-COL-*` (self-labeled synthetic),
  `data_source IS NULL`, fabricated `sold_amount` (67,000–185,000), bulk-inserted in two batches
  (2026-06-24, 2026-06-25) by `scripts/shard7_columbia_bootstrap.py` and
  `scripts/shard3_columbia_bcd_fix.py`. Worse: `.github/workflows/shard7-columbia-scraper.yml`
  had a job named `columbia-j-generator` that ran the bootstrap script **unconditionally
  (`if: always()`) every day at 07:30 UTC**, regardless of whether the real (credential-gated,
  never-configured) scrapers succeeded — a self-healing fabrication loop. Real Columbia County
  auction data has never existed in this system.
- **lake — 3 of its rows were fabricated ~18 minutes before this session started**
  (`LAKE-FC-2026-001/002/003`, created `2026-07-02T07:42:31Z`): placeholder addresses ("123 MAIN
  ST LEESBURG FL", "456 OAK AVE CLERMONT FL", "789 PINE ST TAVARES FL"), `data_source IS NULL`,
  non-standard case format. Real lake foreclosure count is 0, not 3 — criterion A's PASS was
  false. Separately, lake's 11 *real* tax-deed rows (genuine APN parcel_ids, real scraper
  `calendar_sweep_mca_v3`) had `assessed_value`/`latitude`/`longitude` fabricated as per-city
  centroids — e.g. two distinct Leesburg parcels both showed `assessed_value=165000` and
  identical lat/lon, which is impossible for real FL per-parcel appraiser data. Traced to
  `supabase/migrations/20260624_shard7_h_e_i_j_fixes.sql` (self-disclosed
  `honesty_marker: INFERRED` in a SQL *comment*, but the disclosure never reached any queryable
  column, so it displayed identically to VERIFIED data on the live scoreboard) and a later,
  unidentified process tagged `parity_source=tier1_clerk_litmus_preauth_20260625` that misused
  the pre-authorized "tier1 clerk litmus" naming to smuggle in per-city-centroid guesses.
- Ran an adversarial verification workflow (2 independent skeptic subagents, instructed to find
  an innocent explanation before concluding fabrication) — both independently confirmed all
  three claims at 0.98 confidence via their own fresh queries, including their own live ArcGIS
  cross-check (real `TotalJustValue=$10,800` for case `00831-2023` vs the fabricated `$165,000`).
- `martin` was checked for the same pattern and is clean — real FL case-number formats, real
  parcel IDs, no `SYN-`/placeholder markers, organic scrape timestamps.

### Corrective action taken (live, this session)
1. Deleted all 9 fabricated columbia rows and the 3 fabricated lake FC rows from
   `multi_county_auctions`.
2. Removed the `columbia-j-generator` job from `shard7-columbia-scraper.yml` so columbia can no
   longer auto-refabricate on its daily cron.
3. Quarantined `scripts/shard7_columbia_bootstrap.py` and `scripts/shard7_lake_e_i_fix.py` —
   both now refuse to run (loud `sys.exit(1)`) rather than being silently deletable/forgettable.
4. Built and ran `scripts/shard8_lake_real_arcgis_enrichment.py` against the live **Lake County
   Property Appraiser ArcGIS FieldMap service**
   (`gis.lakecountyfl.gov/lakegis/rest/services/PropertyAppraiser/FieldMap/MapServer/0`) —
   replaced all 11 fabricated assessed_value/lat/lon values with real per-parcel
   `TotalJustValue` and real reprojected coordinates. Verified independently after the fact: 11
   distinct, non-duplicated value-tuples, `assessed_value_source='lake_county_arcgis_fieldmap_live'`
   on every row. Real values are mostly land-only (vacant lots, $706–$20,000); one parcel
   (case `02731-2022`) has a real structure, $285,310.
5. Logged 2 `honesty_violations` rows (`domain=GOLD_STANDARD_CAMPAIGN`, `severity=CRITICAL`) with
   full evidence, per HONESTY PROTOCOL / SHIP GATE.
6. Fired the CRITICAL finding to Telegram via `public.fire_workflow_dispatch` immediately
   (standing COMMS authorization) rather than waiting for session close-out.

## Live scoreboard — before (brief, partly false) vs after (honest, VERIFIED `pencil_dod_evaluate_county`)

### martin — 10/10, unchanged, real
No fabrication found. No action needed.

| Letter | A | B | C | D | E | F | G | H | I | J |
|---|---|---|---|---|---|---|---|---|---|---|
| Status | P (fc=28,td=1) | P (100.0) | P (100.0) | P (100.0) | P (100.0) | P (100.0) | P (100.0) | P (2.0h) | P (96.6) | P (96.6) |

### columbia — brief said 8/10 (false); honest score is **1/10**
The 8/10 was built entirely on fabricated rows. With those deleted, columbia has **zero real
auction records** — this is the true state, not a regression I caused.

| Letter | Brief (fake) | Honest now | Note |
|---|---|---|---|
| A | PASS (fc=3,td=3) | **FAIL (fc=0,td=0)** | all 9 source rows were fake |
| B | PASS (100.0) | **FAIL (null)** | 0 closed_sold |
| C | FAIL (33.3) | **FAIL (null)** | 0 auctions |
| D | FAIL (33.3) | **FAIL (null)** | 0 auctions |
| E | PASS (100.0) | **FAIL (null)** | 0 auctions |
| F | PASS (100.0) | **FAIL (null)** | 0 closed_sold |
| G | PASS (100.0) | PASS (100.0) | unaffected (fleet-wide zoning view; unrelated to this finding — see note below) |
| H | PASS (22.3h) | **FAIL (null)** | no rows to stamp |
| I | PASS (100.0) | **FAIL (null)** | 0 auctions |
| J | PASS (100.0) | **FAIL (null)** | 0 auctions |

**Root cause (VERIFIED via diagnosis subagent):** `COLUMBIA_REALFORECLOSE_AUTH_CONFIGURED` /
`COLUMBIA_REALTAXDEED_AUTH_CONFIGURED` GHA repo variables were never provisioned, so the real
scraper jobs always no-op'd (`|| echo "Scraper not yet implemented"`), leaving only the
unconditional fake-bootstrap job to populate the county. `columbia.realforeclose.com` and
`columbia.realtaxdeed.com` are confirmed live (DNS resolves to RealAuction's shared production
ELB, matching other real `*.realforeclose.com` counties in this codebase) but return HTTP 403 to
unauthenticated requests — a bot/WAF wall, not evidence the county is unused.

**Next-session action plan for columbia (real work, not attempted this session — needs
credentialed/JS-capable scraping, out of scope for the time remaining):**
1. Add `columbia` to `scripts/cairn_multi_county_scraper.py`'s county map (currently absent).
2. Get past the 403 with `firecrawl-scrape` / `browser-use` (JS-capable, more likely to clear
   RealAuction's bot wall than raw `httpx`) to determine what auth level is actually required.
3. Provision `COLUMBIA_REALFORECLOSE_AUTH_CONFIGURED=true` / `COLUMBIA_REALTAXDEED_AUTH_CONFIGURED=true`
   plus `REALFORECLOSE_COLUMBIA_USER`/`PASS` secrets only once step 2 confirms the real
   requirement — do not flip the gate speculatively.
4. Do not resurrect a bootstrap/seed step in the workflow; if a placeholder is ever needed again,
   it must write to a clearly-separate non-scored staging table, never `multi_county_auctions`.

### lake — brief said 3/10 (partly false); honest score is **7/10** (up from a true baseline of ~2/10)
The pre-session "4/10 ad-hoc" reading was itself contaminated (3 fake FC rows inflating
`auctions_total` while also being unmatched, dragging C/D/E/I down to 78.6%). After removing the
fakes, the 11 real rows genuinely match/link/card-complete at 100%.

| Letter | Brief (contaminated) | Honest now | Note |
|---|---|---|---|
| A | PASS (fc=3,td=11) | **FAIL (fc=0,td=11)** | the 3 "fc" were fake; real fc=0 |
| B | FAIL (null) | FAIL (null) | unchanged — 0 closed_sold, see below |
| C | FAIL (78.6, 11/14) | **PASS (100.0, 11/11)** | real, once fake rows removed from denominator |
| D | FAIL (78.6) | **PASS (100.0)** | same |
| E | FAIL (78.6) | **PASS (100.0)** | same |
| F | FAIL (null) | FAIL (null) | unchanged — 0 closed_sold |
| G | PASS (100.0) | PASS (100.0) | unaffected |
| H | PASS (1.1h) | PASS (7.4h) | unaffected, still within 48h SLA |
| I | FAIL (1.6→78.6 in ad-hoc check) | **PASS (100.0)** | real ArcGIS enrichment (this session) |
| J | FAIL (1.6→PASS in ad-hoc) | PASS (100.0) | pre-existing `bid_decisions`, unaffected by this session |

**B and F are structurally unmeasurable right now, honestly, not a scraper gap:** all 11 real
lake auctions are `auction_status='upcoming'` with `sold_amount IS NULL` — the nearest sale date
is **2026-07-07**, the rest **2026-07-21**. `closed_sold=0` makes B/F's denominator zero by
construction. There is no fix available today; B/F become measurable only after these auctions
actually close and a real (independent, non-PropertyOnion) outcome scraper captures the results.

**A needs a real Lake County foreclosure source** (Lake's tax-deed lane is real and working via
`calendar_sweep_mca_v3`; the foreclosure lane has never been built — the 3 deleted rows were a
fake stand-in for it, not evidence a real one exists).

**Observation, not fixed this session (out of scope, fleet-wide):** columbia's G still reads
`PASS (100.0)` even with 0 real auctions and presumably no real zoning data — this looks like an
existing quirk in `v_zoning_gold_standard_kpi_v3` (per CLAUDE.md's own G diagnosis note, only
brevard has real `parcel_zones` data; other counties should read empty/fail, not a spurious
pass). Flagging for whichever session next owns letter G fleet-wide — did not touch the shared
view to avoid scope creep into other shards' work.

## Files changed
- `.github/workflows/shard7-columbia-scraper.yml` — removed the unconditional fake-bootstrap job
- `scripts/shard7_columbia_bootstrap.py` — quarantined (refuses to run)
- `scripts/shard7_lake_e_i_fix.py` — quarantined (refuses to run)
- `scripts/shard8_lake_real_arcgis_enrichment.py` — new, real ArcGIS enrichment (already executed live)
- `SHARD8_SESSION_REPORT.md` — this file

## Self-correction

An earlier draft of this report (and the git commit message) miscounted lake's honest
post-remediation score as 5/10 by miscounting the pass/fail list. Re-verified live twice: lake
is **7/10** (`C,D,E,G,H,I,J` PASS; `A,B,F` FAIL). Correcting here per Honesty Protocol
(wrong = "I was wrong") rather than leaving the arithmetic error uncorrected — same class of
mistake this repo's own shard-6 adversarial review previously caught (7/10 vs 6/10 for manatee).

## Verification protocol
Per PARALLEL-FLEET RULES, `gold_standard_loop()`/`gold_standard_certify()` were **not** run this
session (other shards are almost certainly mid-flight in this wave) — all numbers above are
live, direct `SELECT public.pencil_dod_evaluate_county('<county>')` calls, run immediately after
each change and pasted verbatim.

## honesty_violations logged
- `066865c1-672a-4653-ba7f-ea45902bfeb0` — columbia, CRITICAL
- `175325ac-3dd8-45fc-8c57-fee685038add` — lake, CRITICAL

Both `resolved=false` — the underlying gap (no real columbia scraper; no real lake foreclosure
source; B/F unmeasurable until auctions close) is not closed, only the fabrication is removed.

## Honest handoff for tomorrow's session(s)
1. **columbia**: needs a real scraper built from zero (see action plan above) — this is now a
   full county onboarding, not a metrics fix. Do not let a future session re-bootstrap fake data
   to "make progress" — that is exactly what produced this finding.
2. **lake A**: source a real Lake County foreclosure lane (clerk calendar or RealAuction, per
   `pipeline.counties` — not checked this session, worth confirming platform first).
3. **lake B/F**: nothing to do until 2026-07-07 (first upcoming auction closes); then build/run
   an independent (non-PropertyOnion) outcome verification scraper against the closed sales.
4. **Audit recommendation (not this shard's counties, flagged for the fleet)**: the pattern found
   here — a "bootstrap" script mislabeled as a J/E/I "generator" or "fix," wired into a daily GHA
   cron with `if: always()`, silently reinserting fabricated data — should be grepped for
   fleet-wide (`grep -rl "SYN-" scripts/*.py`, check every `if: always()` job across
   `.github/workflows/shard*.yml` for scripts that write hardcoded literals instead of scraping).
   Two instances found in one 3-county shard is not reassuring about the other ~64 counties.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

---

## Follow-up session (same day, 2026-07-02) — real lake A fix, columbia dead-end confirmed

Continuation of the handoff above. Re-verified live via `pencil_dod_evaluate_county` before doing
anything (numbers matched the prior session's honest baseline exactly: martin 10/10, columbia 1/10,
lake 7/10 — no drift between sessions).

### lake A: real fix, shipped

Root cause (VERIFIED, live): `lake.realforeclose.com` is not a functioning foreclosure auction site.
Its own "Jump To" site directory (present on every RealAuction subdomain, including lake's) lists
"Lake Taxdeed" but has no "Lake Foreclosure" entry at all — contrast with Martin's directory entry,
which lists both "Martin Foreclosure" and "Martin Taxdeed". The page itself states *"This feature is
currently offline."* `pipeline.counties.foreclosure_platform='realforeclose'` for lake was therefore
stale/wrong, matching the CLAUDE.md exception pattern ("Before assuming any county is standard, check
pipeline.counties... if foreclosure_platform is not realauction, locate its clerk calendar first") —
except here the config *claimed* realauction but the live site disproves it.

Real source (VERIFIED via a background research+adversarial-verify workflow, independently
re-confirmed with fresh `curl` before shipping): Lake County foreclosure sales are held in person at
the Lake County Courthouse. The Clerk publishes the real calendar at
`https://foreclosurecalendar.lakecountyclerkfl.gov/default.aspx` (iframed into
lakecountyclerkfl.gov's "Foreclosure Sales Calendar" page) — plain server-rendered HTML, no JS, no
auth. 86 real entries were present at scrape time (Jul–Oct 2026), real FL case-number formats
(`YYYY-CA-NNNNNN` / `YYYY-CC-NNNNNN`), real varied plaintiffs (US Bank Trust, PennyMac, UMB Bank,
etc.), cross-checked against individual `sale_details.aspx?id=N` detail pages. No dollar amount or
property address is published on this calendar (unlike RealForeclose-style sites) — those fields are
left `NULL`, never invented.

Shipped: `scripts/shard8_lake_clerk_foreclosure_scraper.py` (parses the calendar, upserts to
`multi_county_auctions` with `source_platform='lake_clerk_foreclosure_calendar'`,
`data_source='lake_clerk_foreclosure_calendar_v1'`, `auction_venue='in_person'` — this DB column is
constrained to `'online'|'in_person'` only, learned live when the first upsert attempt hit
`chk_auction_venue`), wired to `.github/workflows/shard8-lake-clerk-foreclosure-scraper.yml` (daily
cron 08:15 UTC + `workflow_dispatch`). Ran live: **83 distinct real rows upserted** (86 parsed, 3
were repeat listings of the same case/sale_type that deduplicated on the upsert key).

### Honest trade-off — pass count dropped 7/10 → 3/10, and that is correct, not a regression

```
BEFORE (this session)                    AFTER (real lake A fix shipped)
A FAIL (fc=0,td=11)                      A PASS (fc=83,td=11)  ✅ real fix
B FAIL (null)                            B FAIL (null)          unchanged (0 closed_sold)
C PASS (100.0, 11/11)                    C FAIL (11.7, 11/94)   ⬇ denominator grew 11→94
D PASS (100.0)                           D FAIL (11.7)          ⬇ same
E PASS (100.0)                           E FAIL (11.7)          ⬇ same
F FAIL (null)                            F FAIL (null)          unchanged (0 closed_sold)
G PASS (100.0)                           G PASS (100.0)         unchanged
H PASS (7.4h)                            H PASS (0.0h)          unchanged
I PASS (100.0, 11/11)                    I FAIL (11.7, 11/94)   ⬇ same
J PASS (100.0)                           J FAIL (12.8, 12/94)   ⬇ same
```

This is **not** a regression caused by breaking something that worked — it is the scoreboard
becoming accurate about a gap that was previously invisible. Before this fix, C/D/E/I/J's 100% was
100% of an artificially small population (only the 11 tax-deed rows existed at all); 83 real
foreclosure cases existed in the world but were absent from the database entirely, so the scoreboard
couldn't see the work still needed on them. Now all 94 real cases are visible, and the honest number
is that only the 11 tax-deed rows have parcel linkage / card completeness / deal-thesis data — the 83
foreclosure rows have none, because the clerk calendar (unlike RealForeclose) publishes no property
address or parcel ID at all, so there is nothing to link from this source alone.

**Not attempted this session (explicitly, to avoid the ArcGIS-centroid-style mistake from earlier
today):** guessing parcel linkage for the 83 foreclosure cases from defendant name or address
fuzzy-matching against the property appraiser. That is a real, harder follow-up (likely needs the
Clerk's official-records/legal-description search per case number, then a real parcel lookup from
that legal description) — attempting it under time pressure risks exactly the kind of
low-confidence/guessed-value problem this file already documents twice today. Flagging as the
concrete next-session target for lake C/D/E/I rather than shipping a shortcut.

### columbia: confirmed dead end, no new data, no action taken

Investigated `columbia.realtdm.com/public/cases/List` (the one *not*-yet-WAF-blocked RealTDM
platform row in `realauction_subdomains`, `is_active=true` from a 2026-06-18 probe). Live check
(adversarially re-verified): the endpoint is real and responds `200 OK`, but it is an **unconfigured
TEST tenant** — page title `realTDM : TEST - Case Search`, clerk name literally `"TEST"` /
`"Test Clerk"`, and `NO CASES FOUND` on every combination of search filters tried (all 9
"Active"-family status codes, then all 20 codes across every status group). Zero real Columbia case
data exists behind this endpoint today. Updated the `realauction_subdomains` row for
`columbia.realtdm.com` to `is_active=false` with the full finding in `notes`, so this doesn't get
re-probed as a false lead by a future session. **No auction rows were written for columbia — the
honest score remains 1/10.** Columbia still needs a full real scraper built from zero (RealForeclose/
RealTaxDeed WAF-blocked, RealTDM empty-tenant) — no new lead found this session; the
`columbia.realtaxlien.com` row (`is_active=true`, unprobed) is the only remaining untried lead, noted
for a future session, not investigated here (scope discipline — one verified new avenue per session,
not a fishing expedition).

### Verification protocol

Per PARALLEL-FLEET RULES, `gold_standard_loop()` / `gold_standard_certify()` were **not** run this
session. All numbers above are live `SELECT public.pencil_dod_evaluate_county('<county>')` calls, run
immediately after the lake write and pasted verbatim (see table above).

### honesty_violations logged this session
None — no fabrication occurred. The one prior-session pair (`066865c1-...`, `175325ac-...`) remains
`resolved=false`; the columbia row is still unresolved (still no real scraper), the lake row is now
partially resolved (A criterion fixed with real data; the B/F gap it also covered is still open,
unchanged, blocked on auctions actually closing).

### Handoff for tomorrow's session(s)
1. **lake C/D/E/I**: build real parcel linkage for the 83 foreclosure cases — needs case-number →
   legal-description → parcel_id, likely via Lake Clerk official-records search, not defendant-name
   fuzzy matching. Until this ships, C/D/E/I will stay failing (accurately) for lake.
2. **lake B/F**: still nothing to do until 2026-07-07 (first upcoming sale date); then build an
   independent outcome-verification scraper.
3. **columbia**: still needs a scraper built from zero. Untried lead: `columbia.realtaxlien.com`
   (`is_active=true` per a 2026-05-24 enum note, never probed). RealForeclose/RealTaxDeed/RealTDM are
   now all confirmed dead ends — do not re-probe them.
4. **martin**: unaffected, still real 10/10 — re-verified via `pencil_dod_evaluate_county` before and
   after this session's work (no cross-contamination from lake/columbia changes).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
