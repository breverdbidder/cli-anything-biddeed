# GOLD STANDARD shard (sarasota, nassau, bay, gulf) — dispatch `9f070f2b-162c-43a2-b7f1-bc7940c13f8f`

chat_session: `architect-20260718T160000` · 2026-07-18 · mode: ULTRALOOP native (Workflow tool, 7 diagnose+fix agents,
5 adversarial verify agents)

## Environment correction (logged for future sessions)

`SUPABASE_DB_PASSWORD` does **not** authenticate against either the pooler (`aws-0-us-west-2.pooler.supabase.com`,
ports 5432/6543) or the direct host (`db.mocerqjnksmhcjzxrewo.supabase.co:5432`) in this environment — confirmed by
repeated `FATAL: password authentication failed`. There is also no working `exec_sql`/`run_sql` RPC (confirmed 404 —
several committed `shard28_*.py` scripts in the repo root call a `rpc/exec_sql` that does not exist in the live schema
cache, meaning those scripts cannot have executed their SQL payloads as written). All writes this session went through
plain PostgREST REST calls (`$SUPABASE_URL/rest/v1/<table>`) with the service-role key, which is confirmed working and
sufficient for data backfills on existing tables/columns. DDL (new tables/functions/schema changes) was **not**
possible this session with the credentials available; nothing here required it.

## Self-corrected false start

My first live query for sarasota (`pencil_dod_evaluate_county('sarasota')`, no snapshot arg) showed C/D/I/J collapsed
to ~58% against a denominator of 341 — looked like a serious regression from the brief's stated 10/10. Before building
any fix around it, I read `supabase/migrations/20260718_gtm22_phase1_3_pencil_dod_snapshot_param_and_loop_rewire.sql`
(applied earlier today by another session) and found sarasota is one of 7 counties under an active
`gold_standard_cert_scope` freeze (`snapshot_at=2026-06-24T00:02:01Z`). Re-querying with that snapshot parameter
confirms sarasota is genuinely **10/10 PASS**, matching the brief exactly. This was my own diagnostic error (wrong
function call), caught and corrected before anything was written. No action was taken on sarasota this session beyond
confirming zero regression.

## Starting state (live query, before this session's work)

```
sarasota (scoped, snapshot 2026-06-24): 10/10 A-J all PASS — unchanged, confirmed only
nassau  8/10: A✓ B✗(null) C✓(100.0) D✓(100.0) E✓(100.0) F✗(null) G✓(100.0) H✓(0.7h) I✓(97.1) J✓(100.0)
bay     6/10: A✓(59) B✓(100.0) C✗(92.9) D✗(92.9) E✓(98.4) F✓(100.0) G✗(92.3,FAR-binding) H✓(0.7h) I✗(88.2) J✓(100.0)
gulf    3/10: A✓(5) B✗(null) C✗(78.6) D✗(78.6) E✗(78.6) F✗(null) G✓(100.0) H✗(183.7h) I✗(64.3) J✓(100.0)
```

## What this session did

Ran a full ULTRALOOP fan-out (Workflow tool, 7 diagnose+fix agents in parallel/pipeline, each followed by an
independent adversarial verify agent whenever a write was claimed) against every open letter across the 4 counties.

## Findings — real writes made (verified)

### bay I: real progress, verified — 88.2% → 93.7% (still FAIL, 2 rows short)
Sourced Bay County's live ArcGIS parcel service (`gis.baycountyfl.gov/arcgis/rest/services/TEST_Parcels/FeatureServer/1`)
and its separate `LandUsePlanning/Zoning` layer. Backfilled real `latitude`/`longitude`/`assessed_value` on 7
`multi_county_auctions` rows and inserted 7 real `parcel_zones` rows (zone codes matched against pre-existing
`zoning_districts` for the correct jurisdiction). **All 14 writes independently reproduced byte-for-byte** by the
verifier against fresh DB reads and fresh ArcGIS refetches. `card_complete` moved 112/127 → 119/127. The 8 residual
rows are honest blockers: 4 have junk placeholder `parcel_id` values (`'TIMESHARE'`, `'Property Appraiser'`,
`'MULTIPLE PARCELS'`) from an apparent scraper defect, behind a bidder-auth-gated case portal (confirmed 403); 1 is a
genuine multi-parcel case with no single situs address by definition; 2 have zero scraped data and no accessible
case-number lookup; 2 are real, fully-addressed Lynn Haven parcels where Bay County's own zoning layer explicitly
returns `ZONING='See FLU'` (deferred to the city) and Lynn Haven publishes no reachable zoning API.

### bay G: FAR component genuinely fixed, but G still FAILs — newly-exposed real parking gap
Backfilled `zone_standards` FAR/density/setback values for Panama City MU-1 (cited directly to ULDC Sec. 104-31, PDF
fetched and read) and Lynn Haven C/IND/C-1 (cited to the 2018 Comprehensive Plan, flagged `INFERRED`
confidence 0.55–0.60 since Municode 403s Lynn Haven's actual ULDC for both `curl` and `WebFetch` — confirmed
independently by the verifier, real blocker not a shortcut). Corrected 3 Panama City districts (ND/NG/NR) to
`far_regulated=false` after confirming via primary ordinance text they're genuinely form-based codes with no FAR
metric. **6 of 7 writes verified byte-for-byte against re-fetched primary sources; 1 (district 7271, Panama City NR)
was refuted — the write never landed in the DB despite correct research. Re-applied and reconfirmed live this
session** (`zoning_districts.id=7271.far_regulated` now `false`, confirmed via direct re-query).

Net effect, live-measured: **far 92.3→100.0** (real fix). But `pk1000_applicable_parcels` jumped 0→8 once real zoning
landed on more parcels, exposing a parking-coverage metric that was previously masked at `null`: **pk1000 now 27.3%**,
which is the new binding constraint (`density` also dipped 97.2→96.5, likely from the same newly-measured denominator
shift). **G is still FAIL — the overall PASS/FAIL letter did not flip** and the numeric G score got worse, but this is
honest newly-measured truth from real data landing, not a regression caused by bad work: Panama City's Chapter 108
parking code is regulated per specific use-type (varies 1/200sf–1/1000sf by retail/medical/industrial/etc.), not as a
single per-district scalar, so writing one number per district would misrepresent the ordinance — this needs a
methodology decision for a future session, not a data lookup.

### bay C/D: genuine PropertyOnion coverage-horizon gap, no write
All 9 unmatched rows trace to two real causes: PropertyOnion's bay scrape is stale (last run 2026-05-20, coverage
horizon ends 2026-07-07) while the 8 unmatched auctions run 2026-07-23–2026-08-03 (dates PO simply hasn't reached
yet); the 9th is a timeshare parcel, an asset class PropertyOnion never lists. Specifically checked one candidate for
a false-negative (case `20001459CA`) and confirmed the only PO match at that address is a different, older, canceled
2023 auction cycle on the same property — correctly left unmatched. No `po_mca_matches` candidate exists for any of
the 9 rows. Should self-resolve once PropertyOnion's bay coverage catches up.

## Findings — genuinely blocked, no fabrication (all independently reproduced or re-confirmed)

- **gulf H (freshness, 184h stale)**: root-caused, not fixed. No working scheduled scraper feeds gulf.
  `.github/workflows/shard5-daily-scraper.yml`'s `h-freshness` job fails daily (invalid `SUPABASE_ACCESS_TOKEN`
  secret) and its own header already documents it as a previously-purged ghost-success job; the workflow's own header
  states verbatim "gilchrist/gulf: smaller custom_clerk counties — custom parsers not yet implemented."
  `shard7-gulf-outcomes.yml` is real and honest (B/F-outcomes-only, correctly wrote nothing after finding 0 real
  results). A repo-root script `scripts/shard5_h_freshness_gulf.py` exists that would blindly `UPDATE
  last_seen_at=NOW()` on all gulf rows with zero real scrape behind it — the exact ghost-success pattern this repo's
  git history is full of reverting. **Not run.** Concrete fix for a future session: rotate the GHA token AND rewrite
  the job so it only stamps rows a real scrape actually touched; separately, build a genuine gulf clerk scraper (no
  such script currently exists in the repo) and wire it to a daily cron.
- **gulf B/F**: third independent confirmation of a structural block. This session had real browser automation
  (Playwright) that the 2026-07-11 session (curl/WebFetch only) lacked, and used it on `floridapublicnotices.com` —
  a real, working, searchable notice archive. 1 of 3 target cases has a pre-sale notice only (no CT/amount); 2 have
  zero indexed notices (their auction dates are still in the future); `portstjoestar.column.us` is now confirmed
  login-gated even under real JS rendering, closing out the one lead the prior report flagged as "tooling, not
  source." **Side finding, out of scope this session**: 10 of gulf's 14 rows carry `auction_status='upcoming'` with
  `auction_date` already in the past relative to today — a status-staleness bug worth a future session's attention.
- **nassau B/F**: re-verified one week after the 2026-07-11 finding. Still exactly 1 `completed` auction in nassau,
  still resolved via a private Warranty Deed (not a Certificate of Title) per the full 8-instrument deed history
  pulled from `search.ncpafl.com`. New reusable lead: discovered the site's actual JSON API
  (`GET /api/livesearch/{query}`), which pulls full deed history via plain `curl` — no browser automation needed,
  contradicting the prior session's assumption. Still structurally blocked.
- **nassau I** (already passing, 97.1%): the 1 residual gap row (Hilliard jurisdiction) is a genuine GIS coverage gap
  — `parcel_zones` has zero rows for `jurisdiction_id=1067`, and no reachable Nassau zoning GIS endpoint was found
  this session. Not blocking since I already passes.

## Adversarial verification summary

5 independent refuter agents ran against every claimed write:
- **bay_g**: 6/7 sub-claims CONFIRMED byte-for-byte against re-fetched primary ordinance PDFs and live DB; 1 REFUTED
  (write didn't land) — fixed directly this session, confirmed landed.
- **bay_i**: 14/14 writes CONFIRMED byte-for-byte against fresh ArcGIS refetches and fresh DB reads; 6 of 8
  "left FAIL" blockers spot-checked and confirmed genuine (junk parcel_ids, realforeclose 403, Lynn Haven "See FLU"
  deferral all independently reproduced).
- bay_cd, gulf_h, gulf_bf, nassau_i, nassau_bf made no writes; their "genuinely blocked" conclusions are taken as
  reported since there was nothing to adversarially verify beyond the live re-measurement already embedded in each
  agent's own report (all cross-checked against a fresh live `pencil_dod_evaluate_county` call in this synthesis).

7 rows logged to `public.gold_standard_ultraloop_audit` (`dispatch_id='9f070f2b-162c-43a2-b7f1-bc7940c13f8f'`,
`ultraloop_mode='native'`, all `survived=true`).

## Closing scoreboard (live, re-verified after this session)

```
sarasota (scoped) 10/10: unchanged — false-alarm self-corrected, confirmed no regression
nassau  8/10: A✓ B✗(null) C✓(100.0) D✓(100.0) E✓(100.0) F✗(null) G✓(100.0) H✓(0.1h) I✓(97.1) J✓(100.0)  — unchanged
bay     6/10: A✓(59) B✓(100.0) C✗(92.9) D✗(92.9) E✓(98.4) F✓(100.0) G✗(27.3, pk1000-binding, was 92.3 FAR-binding)
              H✓(1.2h) I✗(93.7, was 88.2) J✓(100.0)  — PASS/FAIL count unchanged (6/10), real data-quality gains on
              I and G's FAR component; G's headline number moved the wrong way because real data exposed a real,
              previously-hidden gap, not because of any regression
gulf    3/10: A✓(5) B✗(null) C✗(78.6) D✗(78.6) E✗(78.6) F✗(null) G✓(100.0) H✗(184.2h) I✗(64.3) J✓(100.0)  — unchanged
```

No county flipped its PASS/FAIL letter count this session. Real, verified improvements landed inside bay's I and G
metrics; every other open letter across the 4 counties was re-confirmed as a genuine structural block (data-source
coverage gap, auth-gated portal, or missing/broken scraper infrastructure) rather than an unexplored research surface
— per `gold_standard_loop()`/`gold_standard_certify()`, no county in this shard reaches 10/10 from this session's
work alone.

## Next-session priorities (concrete, in order)

1. **gulf H**: rotate the `SUPABASE_ACCESS_TOKEN` GHA secret used by `shard5-daily-scraper.yml`, rewrite its
   `h-freshness` job to only stamp rows a real scrape touched (never a blind bulk `UPDATE`), and build a real gulf
   clerk scraper — none exists in the repo today. This is an infrastructure gap, not a data-lookup task.
2. **bay G pk1000**: needs a methodology decision (per-use-type parking table vs. a single per-district proxy value)
   before any more zone_standards writes — do not force a single number into Panama City's use-type-based parking
   code.
3. **bay G remaining FAR gaps**: Lynn Haven MU (no fixed FAR per its own Comp Plan — genuinely N/A, do not force a
   value) and Callaway's 5 remaining districts (blocked by Municode 403/Angular-SPA-shell, no PDF mirror found —
   needs either a Municode-authenticated fetch path or a manual ordinance PDF request).
4. **bay I**: the 4 junk-`parcel_id` rows need `bay.realforeclose.com` case detail behind an authenticated bidder
   session — a credentials/auth-automation prerequisite, not a research gap.
5. **gulf status-staleness bug** (flagged this session, not investigated): 10/14 gulf rows show
   `auction_status='upcoming'` with `auction_date` already past — likely affects B/F denominators fleet-wide if the
   same pattern exists elsewhere; worth a quick audit.
6. **nassau B/F, gulf B/F/C/D/E/I**: all reconfirmed structurally blocked (private-deed-not-CT for nassau;
   auth/login-gated sources and future-dated auctions for gulf). No further curl/WebFetch/Playwright investigation
   is likely to move these until either more nassau auctions age into `completed` status or gulf gets a real clerk
   scraper (item 1).

---
dispatch_id: 9f070f2b-162c-43a2-b7f1-bc7940c13f8f
