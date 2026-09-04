# biddeed.ai — Claude.ai Parity PRD + Audit SOP
Status: v1.0 · 2026-09-04 · Owner: Ariel Shapira · Architect/Judge: Claude chat · Builders: Claude Code runs + chat-authored PRs
Canon: docs/gtm/BIDDEED_VOICE_CONTENT_META_PROMPT_v2.md (voice, palette, M7) · docs/gtm/CONTENT_SOP.md (content DoD) · docs/design/BIDDEED_CLAUDE_UI_PARITY_ARCHITECTURE.md (C1–C5 build) · biddeed-web `app/globals.css :root` (the only source of colour)

## 0. Why this file exists
Until 2026-09-04 every "verified" on this site meant *the string was in the HTML*. That is how seven answer pages shipped with white text on cream, the county pages ran two hours of 500s, the report kept a retired navy theme, and the map said "Mapbox token not configured" for days. Parity with Claude.ai is a **rendered, functional** standard: a human opens every route on a phone and a laptop and nothing is unreadable, off-palette, broken, empty, or lying. This PRD defines that standard per route and the harness that checks it automatically before and after every deploy.

## 1. Definition of parity (the bar, not the roadmap)
A route is at parity when all eight gates pass in Chromium at 1440×900 and 390×844:

| Gate | Check | How |
|---|---|---|
| G-RENDER | HTTP 200; no "Internal server error", "Not found", "not configured", "undefined", "NaN", "[object Object]" in visible text | harness |
| G-PALETTE | every computed colour on the page resolves to a canon token value (cream `#fbfaf7/#f5f0e8/#ede3d7`, ink `#1f1b16`, muted `#6e655e`, border `#ddd5c9/#b5a9a0`, terracotta `#9f4d32/#823f29`, semantic `#1f7a3f/#b42318`, white on those) — no Tailwind red/amber/gray/slate, no navy/amber legacy | harness (computed styles) |
| G-CONTRAST | 0 visible text nodes < 4.5:1 against the effective background (gradients evaluated on their darkest stop) | harness |
| G-COPY | canon strings exact; 0 retired lines ("before the gavel", "know your number"); 0 buzzwords (P18); 0 contempt (P17); ≤1 "!"; 0 competitor names; 0 "S5"; patent number-free; persons = Ariel Shapira only | harness + judge |
| G-DATA | every number on the page equals the SSOT RPC queried in the same minute (`auctions_summary_ssot`, `auctions_calendar_counts`); em-dash only on RPC failure; never "no auctions" when the RPC is non-zero | harness (paired query) |
| G-FUNCTION | the route's primary interaction works end-to-end (see §2) | harness / manual script |
| G-SEO | exactly one H1 (server HTML), title ≤60, meta ≤155, canonical, required JSON-LD types parse, in sitemap, no 404 links | harness |
| G-A11Y | Lighthouse a11y ≥ 95; keyboard reachable; focus visible; images alt'd | harness (lighthouse) |

Parity for the SITE = every route in §2 passes all eight, twice (both viewports), on the deployed URL — not a branch, not a preview.

## 2. Route matrix (what "works" means per route)
| Route | Owner repo | Primary function that must work | Data that must match RPC | Required JSON-LD |
|---|---|---|---|---|
| `/` | biddeed-web | composer sends a message and gets a Deed answer; "Talk to Deed" opens voice; hero + founder block render | upcoming, counties, total | Organization, WebSite, Person |
| `/chat` | worker | identity 200 → upload cites document → recents persist → search finds thread; voice widget opens | Brevard/any county "no auctions" never contradicts calendar | — |
| `/radar` (+ `?view=map|calendar|table|spreadsheet|split`) | biddeed-web | map renders pins (no "token not configured"); calendar chips = calendar_counts; table paginates; filters change all views together | per-day counts, upcoming, counties | — |
| `/counties`, `/county/{slug}` → `/counties/{slug}` | worker → biddeed-web | 67 pages 200; numbers live; buy-CTA only on complete coverage; old URL 301 | upcoming, next_auction_date | Dataset, Place, BreadcrumbList, FAQPage |
| `/answers/{slug}` | worker | text visible; answer_first verbatim; links 200 | tokens resolved | FAQPage, BreadcrumbList, Person, Organization (+HowTo) |
| `/blog`, `/blog/{slug}` | worker | renders through site.site_content (B4) | — | Article |
| `/report/{id}` (sample + paid) | worker | 18 sections expand; PDF downloads; verdict/max bid render on canon surfaces | figures from report row | — |
| `/buy-report`, `/subscribe`, `/free-report`, `/pioneers` | worker | form submits → Stripe/lead row; one H1 | live price from checkout config | — |
| `/reels`, `/reels/{code}`, `/deal/{county}/{case}` | worker | video plays; deal page links county + radar + report | — | VideoObject (reels) |
| `/terms /privacy /security /disclaimer` | worker | render; meta; one H1 | — | — |

## 3. Audit SOP (runs, not opinions)
1. **Before any PR is merged** the builder runs `python3 scripts/ui-audit/audit.py --base https://biddeed.ai --routes routes.json` on a faithful preview (branch deploy for biddeed-web; for the Worker: the live HTML with the branch's CSS applied — the harness supports `--css-from <branch>`) and pastes the table in the PR body. A red gate = not mergeable, no exceptions, no "close enough".
2. **After every production deploy** `ui-audit.yml` runs the same harness against the live URL and posts the table on the tracking issue; any red gate re-opens the issue and pages Ariel only if it is G-RENDER or G-DATA (customer-facing lies).
3. **Weekly** (Sun 22:07 UTC, alongside the content report) the full matrix is re-run and the launch-report table updated.
4. **Judge ≠ builder.** The verdict on a PR is written by a fresh-context session from the harness output, never by the run that built it.

## 4. Change control
- Every production change is a PR on `main`; Ariel's merge is the publish (M8). A run that pushes to `main` is a P0 incident (see 2026-09-04 cc02164).
- No new colour literal may enter either repo: the harness's G-PALETTE also greps source (`#[0-9a-f]{6}` outside the token file; Tailwind red/amber/gray/slate classes) and fails the PR.
- Secrets required by a route (Mapbox, Chatwoot, service-role) are listed in `scripts/ui-audit/required_env.json`; the harness fails G-FUNCTION with the exact env name when a route reports "not configured".

## 5. Current gap list (2026-09-04 12:10 UTC, from the harness)
Open: `/radar` palette (PR #27) · Mapbox token (PR #19881 + #28) · Worker site-wide palette (PR #19878) · `/buy-report` 3 H1s · `/blog` Article schema · 23 `:root` blocks → 1 token file (#19845) · C2b verified identity · C3–C5 · county pages at `/counties/*` (B3) · PDF extraction in chat uploads · Deed "no auctions" contradiction (P0).
