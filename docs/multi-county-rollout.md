# Multi-County RealAuction Rollout

**Status:** Production-tested on 5 of 6 ASCEND target counties as of 2026-05-14.
**Owner:** ASCEND session methodology; see `biddeed.claude_sessions` for the canonical session record.
**Generalized from:** `scrape_brevardclerk.py` v9.20 (single-county Brevard tax-deed scraper, 117 cards verified on 2026-05-14, run 38).

---

## 1. What this rolls out

A single scraper that handles any Florida county on a RealAuction platform
(`realtaxdeed`, `realforeclose`, or `realtaxlien` subdomains) parameterised by
`(county_slug, sale_type, auction_date)`. One script, one workflow, three
registry tables, four supported status canons. Brevard's hand-tuned v9.20 is
the reference implementation; this rollout makes the same logic addressable for
all 67 FL counties without per-county code.

Brevard remains its own workflow because it predates this and exercises
quirks (in-person courthouse element, `realforeclose` for both tax-deed and
foreclosure, BECA robots.txt). The new generic path is the SSOT for everything
else.

---

## 2. The three-file stack

| File | Role | Path |
|---|---|---|
| Scraper | Per-county scrape, parse, upsert | `.github/scripts/scrape_realauction_county.py` |
| Workflow | Dispatch surface + registry lookup + concurrency lock | `.github/workflows/scrape-realauction-county.yml` |
| Discovery | Find recent past auction dates per county | `.github/scripts/discover_auction_dates.py` v2 + `.github/workflows/discover-auction-dates.yml` |

The scraper takes 8 env vars (`COUNTY_SLUG`, `BASE_URL`, `PLATFORM`,
`SALE_TYPE`, `AUCTION_DATE`, `MAX_PAGES`, `SUPABASE_*`, `FIRECRAWL_API_KEY`)
and fails fast if any are missing. The workflow looks up the first four from
`public.realauction_subdomains` and passes them in. No hard-coded county logic
anywhere in the scraper.

---

## 3. Required registry rows per county

Three tables must contain matching rows before a dispatch will succeed.
Forgetting any one of them causes an FK violation at `scrape_log_start`:

| Table | Key | Purpose |
|---|---|---|
| `public.realauction_subdomains` | `(county_slug, sale_type)` | Tells the workflow which subdomain + platform serves this combo |
| `pipeline.source_systems` | `code` = `{county_slug}_{platform}` | FK target for `pipeline.scrape_runs.source_code` |
| `pipeline.counties` | `county_slug` | FK target for `pipeline.scrape_runs.county_slug` |

Onboarding a new county is three INSERTs. Examples are seeded in
`biddeed.app_files` and historical migrations; the pattern used in Phase 3
(`registry_expansion_required` + `counties_registry_expansion` events) is the
template.

---

## 4. Sale-type / platform matrix

RealAuction runs three product lines. Not every county has all three:

| sale_type | platform | subdomain pattern | PREVIEW renders past? |
|---|---|---|---|
| `tax_deed` | `realtaxdeed` | `{county}.realtaxdeed.com` | **No** — only in-flight + future |
| `foreclosure` | `realforeclose` | `{county}.realforeclose.com` | **Yes** — full calendar with past 5+ dates |
| `tax_lien` | `realtaxlien` | `{county}.realtaxlien.com` | Untested; most installs `is_active=false` |

This is the most important finding from the Phase 3 rollout. **Tax-deed PREVIEW
URLs do not surface past auctions in their rendered HTML.** That is not a
discovery bug, that is the platform. Past tax-deed data must be retrieved
from an alternate endpoint (likely the SEARCH/archive view) or from each
county's Clerk site directly. Foreclosure calendars work as expected.

Counties that have no `realauction` subdomain at all for the desired sale type
(e.g. Osceola foreclosure) require a separate scraper against the Clerk site.

---

## 5. Discovery flow

Most counties don't publish a clean machine-readable list of recent auction
dates. The discovery script (`discover_auction_dates.py` v2) Firecrawls the
calendar URL with a 15-second initial wait plus two scroll actions, then
extracts dates from both the markdown and the raw HTML using four regex
patterns: `MM/DD/YYYY`, `YYYY-MM-DD`, `data-(auction-)?date="..."`, and
`AUCTIONDATE=...`. It probes two URL variants
(`zaction=USER&zmethod=CALENDAR` and `zaction=AUCTION&Zmethod=CALENDAR`) and
keeps whichever returned the larger render.

Results land in `biddeed.discovered_auction_dates` via the
`public.upsert_discovered_date(jsonb)` RPC (because the `biddeed` schema isn't
in PostgREST's default search path). Each row is tagged with `position` in
`('past','today','future')` and a `rank_within` so the most recent past date
is `position='past' AND rank_within=1`.

The matrix workflow runs all 5 ASCEND-target counties in parallel; expect
30-60 seconds per county wall-clock.

---

## 6. The no-silent-skip guard

The scraper raises `RuntimeError: Zero cards extracted` and exits non-zero
when Firecrawl returns rows but the parser finds no card markup, OR when
Firecrawl returns nothing at all. This is intentional and required.

| Old behaviour | New behaviour |
|---|---|
| `rows_inserted=0, status='success'` (silent skip) | `status='failed', error_message='RuntimeError: Zero cards extracted'` |
| GHA conclusion `success` regardless | GHA conclusion `failure`, raising visibility |

A failed run with zero cards is a **verified null result**, not a bug. It means
either (a) no auctions were scheduled on that date for that county, or
(b) the platform returned an empty page for some other reason. Both are
information. The point of the guard is to keep the success column honest:
every `status='success'` row in `pipeline.scrape_runs` actually has cards
in `pipeline.tier1_card_raw`. No exceptions.

If you see a `failed` row with `Zero cards extracted`, the response is to
re-dispatch against a different date (using discovery to find one), not to
relax the guard.

---

## 7. Onboarding a new county — checklist

1. **Confirm the subdomain serves the sale type.** `curl -sI
   https://{county}.realtaxdeed.com | head -2` — expect 200 or 301 to HTTPS.
2. **Add `public.realauction_subdomains` row** if missing. `subdomain`,
   `platform`, `sale_type`, `base_url` (with full `index.cfm?zaction=USER...`),
   `is_active=true`.
3. **Add `pipeline.source_systems` row.** `code` = `{county_slug}_{platform}`.
   `access_method='firecrawl'`. `enabled=true`. Skipping this gives FK
   `scrape_runs_source_code_fkey` violation.
4. **Add `pipeline.counties` row.** `county_slug`, `county_name`, `state='FL'`.
   Pick `pipeline_status='active'` for new rollouts, `live` once verified.
   Skipping this gives FK `scrape_runs_county_slug_fkey` violation.
5. **Run discovery first if it's not Brevard.** Dispatch
   `discover-auction-dates.yml`, check
   `biddeed.discovered_auction_dates` for `position='past'`. If empty,
   you're scraping a tax_deed PREVIEW with no past data; switch to
   `sale_type=foreclosure` or accept verified-null results.
6. **Dispatch the scraper.** `gh workflow run scrape-realauction-county.yml
   -f county_slug=X -f auction_date=YYYY-MM-DD -f sale_type=Y`.
7. **Verify.** `SELECT status, rows_inserted FROM pipeline.scrape_runs WHERE
   id=(SELECT MAX(id) FROM pipeline.scrape_runs WHERE county_slug='X' AND
   auction_date='YYYY-MM-DD')`. If success, spot-check three
   `pipeline.tier1_card_raw` rows for non-blank `auction_status_canon` and a
   real `case_number_text`.

---

## 8. Empirical evidence from Phase 3 (2026-05-14)

Six counties dispatched, 11 total scrape attempts, 6 verified successes, 5
verified nulls. Total verified data: **163 cards across 5 counties and 2 sale
types**.

| Run | County | Sale type | Date | Cards | Notes |
|---|---|---|---|---|---|
| 38 | brevard | tax_deed | 2026-05-14 | 117 | reference baseline (v9.20 pre-rollout) |
| 51 | hillsborough | tax_deed | 2026-05-14 | 14 | first generic-scraper success |
| 53 | hillsborough | tax_deed | 2026-05-07 | 19 | Path B v2-discovered past date |
| 55 | volusia | tax_deed | 2026-05-12 | 1 | Path B v2-discovered past date, $1,900 SOLD |
| 56 | polk | foreclosure | 2026-05-14 | 10 | $253,200 sold; canon classification bug |
| 57 | marion | foreclosure | 2026-05-14 | 2 | $72,702 SOLD, clean canon |

Verified nulls (all tax_deed PREVIEW pages with no past data):
osceola 5/14 + 5/12, polk 5/14 + 5/7, volusia 5/14, marion 5/14.

---

## 9. Known issues and follow-ups

| ID | Issue | Severity | Fix scope |
|---|---|---|---|
| P3C-CANON-01 | Polk foreclosure cards have `auction_status_canon=''`. Sold amounts present, status text on Polk's pages doesn't match scraper canon patterns. | Medium | 30-min Phase 4 fix: extend canon regex to handle Polk-specific status terms (probably `Sale Confirmed`, `No Bid`, similar). |
| P3-TAXDEED-PAST | Tax-deed PREVIEW URLs don't render past auctions. Affects Polk, Marion, Osceola at minimum. | Medium | Build a `scrape_clerk_taxdeed_archive.py` against each county's Clerk site OR find the RealAuction SEARCH endpoint that exposes archives. |
| P3-OSCEOLA-FCL | Osceola has no `realauction` foreclosure subdomain. | Low | Add a Clerk-site foreclosure scraper for Osceola (`apps.osceolaclerk.com` or similar). |
| P3-DISCOVERY-TZ | Discovery script uses `date.today()` which is UTC; runs at 23:30 ET tag dates as +1. | Cosmetic | Pass timezone explicitly or use `date.today()` with America/New_York. |

---

## 10. Operational notes

- **Concurrency.** The workflow has a concurrency lock keyed by
  `county+date+sale_type`. Re-dispatching the same triple while a run is
  in-flight queues the second dispatch rather than running it in parallel.
  Different counties or different dates run truly parallel.
- **Timeouts.** Workflow timeout is 20 minutes. Typical run is 30-65 seconds
  for under 30 cards, ~4 minutes for the Brevard-sized 117-card sets. Pages
  that exceed 12 take longer linearly because Firecrawl is called per page.
- **Cost.** Each scraper run burns ~1-12 Firecrawl calls (one per pagination
  page). Discovery is ~2 Firecrawl calls per county (two URL probes). Budget
  ~15 calls per fresh county onboarding.
- **Permissions.** Registering a new county requires writing to
  `pipeline.source_systems` and `pipeline.counties`. Under ASCEND session
  policy these are gated as "pipeline registry data write" (allowed,
  additive) rather than "schema change" (denied). Each write should be
  logged in `biddeed.session_events` for audit.

---

## 11. What this is NOT

- Not a Brevard replacement. `scrape_brevardclerk.py` v9.20 remains the
  SSOT for Brevard tax-deed and exercises tighter parsing.
- Not a county-discovery tool. `public.realauction_subdomains` is the
  source of truth for which counties live on which subdomains; this
  rollout consumes that registry, it doesn't build it.
- Not an archive backfill. Each dispatch covers exactly one
  `(county, date, sale_type)` triple. Backfilling historical data is a
  separate workstream and probably wants a different orchestration
  pattern (matrix over date ranges rather than single dispatches).

---

## Appendix A — Session record

This rollout was executed under ASCEND session
(`biddeed.claude_sessions WHERE codename='ASCEND'`) starting
2026-05-14 23:13Z with an 800K token budget and a 7-hour window.
Session events including phase transitions, permission-boundary actions,
and discovery failures are auditable in `biddeed.session_events`.

EG18 gate passed 18/18 at activation. K2 (no-silent-skip) discipline held
through 5 honest RuntimeError failures with zero false-positive successes.
