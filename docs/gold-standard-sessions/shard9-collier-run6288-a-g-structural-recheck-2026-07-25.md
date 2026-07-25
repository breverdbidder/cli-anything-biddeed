# Gold Standard shard-9 collier (loop run 6288, dispatch 24d13132) — A/G fresh re-verification, no writes

Issue: breverdbidder/cli-anything-biddeed#13944

## Live state at session start (VERIFIED via `SELECT public.pencil_dod_evaluate_county('collier')`)

```json
A: pass=false, metric=0,    detail="fc=0 td=212"
B: pass=true,  metric=100.0
C: pass=true,  metric=100.0
D: pass=true,  metric=100.0
E: pass=true,  metric=100.0
F: pass=true,  metric=100.0
G: pass=false, metric=0.0,  detail="density=100.0 far=0.0 pk1000="
H: pass=true,  metric=4.0
I: pass=true,  metric=95.8
J: pass=true,  metric=100.0
```
8/10. Only A and G open.

## Prior work already found (read before touching anything)

Three independent prior sessions already did rigorous, adversarially-verified
work on exactly these two letters:

- **A**: `scripts/shard9_collier_realdata_bootstrap.py` (2026-07-03) and
  `scripts/shard5_a_lane_collier.py` (explicit "DO NOT RUN" header, later
  session) both independently confirmed Collier foreclosure + tax-deed sales
  are conducted **in-person only** — `collier.realforeclose.com` /
  `collier.realtaxdeed.com` are a deprovisioned vendor account, and
  `cms.collierclerk.com/showcaseweb/` (the Clerk's ShowCase court-events
  system) is a reCAPTCHA-gated Angular/Blazor SPA with no server-rendered
  data — every plausible API path returns the same SPA shell. The tax-deed
  lane was later independently solved via a *different* source (Laserfiche
  `LFOfficialRecords` PDF sale lists — `collier_clerk_laserfiche`, 212 real
  rows, wired to `.github/workflows/gold-standard-collier-taxdeed-laserfiche.yml`),
  but that workflow's own header states foreclosure sales use "a separate
  Blazor-Server court-events system with no scrapable REST surface" and
  covers tax_deed only.
- **G**: `supabase/migrations/20260718o_...`, `20260719_gold_standard_shard12_collier_g_zoning_backfill.sql`,
  `20260720_gold_standard_shard12_collier_g_far_pk1000_2nd_firing.sql`, and
  `20260724u`/`20260724v_..._shard6_collier_...` progressively closed density
  (84.4 -> 98.8 -> 100.0, most recently the Naples R1-7.5 fix via City of
  Naples Comp Plan FLUE, `gold_standard_ultraloop_audit` id=9303,
  survived=true) and correctly re-scoped `pk1000_applicable`/`far_applicable`
  down to the true regulated set (C-1, C-4, C-5, Industrial in unincorporated
  Collier) using real LDC Sec 4.02.01 Table 2 / Sec 4.05.04 Table 17 text
  (2 independent fetch strategies, 4 refuters). The one thing they explicitly
  declined to fabricate: **C-4/C-5 max_far**. Collier LDC Table 2's FAR
  column for C-4/C-5 is not a single district-wide number — it lists
  per-use figures ("Hotels .60", "Destination resort .80") with no
  district-level default, and the schema (`zone_standards`, one row per
  `zoning_district_id`) has no way to hold a per-use value. Two refuters
  initially disagreed on whether to treat this as `far_regulated=false`; the
  more rigorous one (footnote-marker + sibling-row check) overturned that and
  the value was correctly left NULL as an honest residual gap.

## This session: fresh independent re-check, not a blind re-read

Per Karpathy K1 (state assumptions, don't just trust) and the ultraloop
"re-run refuters within the 7-day window" guidance (G's last fix landed
2026-07-24, 1 day old), I re-verified both blockers live rather than taking
the migration comments at face value:

- `curl -I https://collier.realforeclose.com` / `.../realtaxdeed.com` ->
  both now `HTTP/2 403` (awselb/2.0) — still dead, same conclusion as the
  prior `302`-redirect finding, different failure mode (ELB-level block vs.
  redirect), consistent with "confirmed dead at the ELB/vhost level" per the
  Laserfiche workflow's `run3713` note.
- Fetched `www.collierclerk.com/court-divisions/civil-court/foreclosures/foreclosure-sales/`
  fresh (200, 103KB) and extracted every search/calendar/API-looking link on
  the page. Found one path not explicitly named in the 2026-07-03 investigation
  log: `cms.collierclerk.com/showcaseweb/calendar`. Probed it plus 6 plausible
  REST paths under `showcaseweb/` (`api/calendar`, `api/courtevents/calendar`,
  `api/events`, `api/CourtCalendar`, `api/hearings/search`, `api/health`) —
  every single one returns the identical 28,210-byte Angular SPA shell
  (`ng-app="sc"`, reCAPTCHA v3 loader), confirming this is a client-side
  routing catch-all, not real JSON, exactly as the 2026-07-03 session found
  for the root path. No new surface.
- Attempted the two live-fetch sources the 2026-07-20 G session used to get
  the real Table 2 text (`colliercounty.elaws.us` direct, Wayback-archived
  ordinance PDF): `elaws.us` still `503` (same as every prior session's
  attempt), Wayback CDX API `503` this session (couldn't even re-derive the
  snapshot URL to re-check it), `library.municode.com` now `403` (was a
  JS-shell before, now blocked outright — same practical outcome). No new
  avenue found; re-confirms rather than contradicts the 2026-07-20 finding.
  WebSearch for the Table 2 FAR text turned up nothing beyond the Municode
  index page itself.

## Conclusion — no writes this session

Both A and G remain genuine structural blockers, not neglect:

- **A**: no anonymously-reachable digital source exists for Collier
  foreclosure sales (in-person only, courthouse annex, Naples). Defeating
  the ShowCase reCAPTCHA/SPA wall would require browser automation +
  CAPTCHA-solving, a distinct larger build explicitly out of scope for this
  pass (same call made twice before).
- **G**: blocked on a single data-model limitation — Collier LDC regulates
  C-4/C-5 FAR per land-use, not per zoning district, and `zone_standards`
  has no per-use column. `pk1000` is separately, correctly NULL (Sec
  4.05.04's parking table is keyed by land use, not district — confirmed
  `pk1000_regulated=false` for all 4 applicable Collier commercial/industrial
  districts). This also means `pk1000` will stay NULL under the *current*
  evaluator forever for Collier — `LEAST(density, far, pk1000)` with a NULL
  input is `NULL`, and `pencil_dod_evaluate_county` does
  `COALESCE(LEAST(...) >= 95, false)`, so a genuinely-inapplicable pk1000 is
  scored as a fail rather than excluded. Flagging this as a fleet-wide
  evaluator question (same shape as the H fleet-wide finding flagged in the
  2026-07-24 bay session), **not** fixing it myself — `pencil_dod_evaluate_county`
  is shared scoring code touching every county in the fleet and out of a
  single shard session's blast radius.

Live re-check after this session (identical to the start-of-session read,
confirming no regression from re-checking the vendor platform/ShowCase):

```json
A: pass=false, metric=0,    detail="fc=0 td=212"
G: pass=false, metric=0.0,  detail="density=100.0 far=0.0 pk1000="
```

collier stays 8/10. Per the ship-to-main mandate, "done" is defined by the
live scoreboard — no metric moved, so nothing is claimed as shipped. No
`gold_standard_loop()`/`gold_standard_certify()` run (can't confirm no
sibling shard is mid-flight this pass; skipped per the parallel-fleet
fallback instruction, per-county evaluation reported instead).

## What would actually move these (flagged for a future session with the right scope)

- **A**: a Playwright/browser-automation build that can execute JS and clear
  the ShowCase reCAPTCHA v3 challenge against `cms.collierclerk.com/showcaseweb/`
  — a genuinely new build-phase task, not a config/data fix.
- **G**: either (a) a schema change to `zone_standards` to hold per-use FAR
  values (e.g. a `zone_standards_by_use` table) — fleet-wide, needs
  coordination, not a single-county fix — or (b) an evaluator change so a
  criterion with 0 applicable parcels is excluded from `LEAST(...)` instead
  of nulling the whole G score. Both are out of scope for a shard session
  scoped to collier only.
