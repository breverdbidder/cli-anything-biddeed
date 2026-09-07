# biddeed.ai — Claude.ai Parity PRD + Audit SOP
Status: v1.0 · 2026-09-04 · Owner: Ariel Shapira · Architect/Judge: Claude chat · Builders: Claude Code runs + chat-authored PRs
Canon: docs/gtm/BIDDEED_VOICE_CONTENT_META_PROMPT_v2.md (voice, palette, M7) · docs/gtm/CONTENT_SOP.md (content DoD) · docs/design/BIDDEED_CLAUDE_UI_PARITY_ARCHITECTURE.md (C1–C5 build) · biddeed-web `app/globals.css :root` + `lib/design-tokens.ts` (the only two files allowed to carry a colour literal - `scripts/palette-gate.mjs` fails any PR that adds one elsewhere)

## 0. Why this file exists
Until 2026-09-04 every "verified" on this site meant *the string was in the HTML*. That is how seven answer pages shipped with white text on cream, the county pages ran two hours of 500s, the report kept a retired navy theme, and the map said "Mapbox token not configured" for days. Parity with Claude.ai is a **rendered, functional** standard: a human opens every route on a phone and a laptop and nothing is unreadable, off-palette, broken, empty, or lying. This PRD defines that standard per route and the harness that checks it automatically before and after every deploy.

## 1. Definition of parity (the bar, not the roadmap)
A route is at parity when all eight gates pass in Chromium at 1440×900 and 390×844:

| Gate | Check | How |
|---|---|---|
| G-RENDER | HTTP 200; no "Internal server error", "Not found", "not configured", "undefined", "NaN", "[object Object]" in visible text | harness |
| G-PALETTE | every computed colour on the page is one of the seven canon values Ariel set on 2026-09-04: white `#ffffff`, tint `#E8F4FC`, ink `#222222`, navy `#002A54` (headings + secondary text), border `#CCCCCC`, brand blue `#0073CF`, hover `#005DAA` — nothing else: no cream/terracotta (retired 2026-09-04), no Tailwind red/amber/gray/slate, no navy/amber legacy. Semantic states (sold, canceled, grade, signal) are encoded with weight and fill inside the seven, never with a new hue | harness (computed styles, `scripts/ui-audit/audit.py` CANON) |
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
2026-09-07 (enterprise-blue canon, PR biddeed-web #53 + this): Ariel set the single site palette to enterprise blue -- #005EB8 brand, #004A92 hover, #0A2540 navy, #1A1A1A ink, #E6F0FA tint, #D7E3F1 border, white. audit.py CANON flipped from the cream set to the enterprise-blue seven; src/worker.js remapped (blue + cream stragglers -> the seven). biddeed-web renders these via precision HSL tokens that round-trip to the exact hexes; the Worker writes them as direct literals. VICTORY = audit.py G-PALETTE/G-CONTRAST/G-TYPE green on the DEPLOYED biddeed.ai via ui-parity-audit post-merge. NOTE: a parallel session is committing cream/#0073CF to these repos; point it at #005EB8 or it will revert this.
2026-09-06 (PR biddeed-web #45 + this PR): `/discover` rendered terracotta because the page read `var(--terracotta,#c15f3c)` fallbacks that no token defines; 431 colour literals outside the token files in biddeed-web -> 0, source gate `palette-gate.yml` added, post-deploy `ui-parity-audit` job added to `cloudflare-production.yml`; Worker `src/worker.js` residue (98 rgba + 45 hex off-palette: dark scorecard page with navy text, pastel signal chips at ~1.5:1, county-page Tailwind slate/amber, `#F26A36` sticky CTA) mapped to the seven; harness CANON updated from the retired cream/terracotta set (which flagged the CORRECT blue on 42/42 rows on 2026-09-06 15:26 UTC) to the seven; `/discover /auctions /sign-in /sign-up` added to routes.json.

Open (2026-09-04): `/radar` palette (PR #27) · Mapbox token (PR #19881 + #28) · Worker site-wide palette (PR #19878) · `/buy-report` 3 H1s · `/blog` Article schema · 23 `:root` blocks → 1 token file (#19845) · C2b verified identity · C3–C5 · county pages at `/counties/*` (B3) · PDF extraction in chat uploads · Deed "no auctions" contradiction (P0).


## 6. The five Deed layers — Claude.ai's five sticky tools, mapped (Ariel, 2026-09-04)
Claude keeps people because five product layers reinforce each other: Chat (thinking), Cowork (background execution), Code (autonomous engineering), Projects (memory), Skills (standardised workflows). Parity means Deed has all five, named for bidders, and our 5 Sticky Layers (CTA_AND_STICKY_SPEC §S1–S5) live inside Projects.

| Claude layer | Deed layer | What it is for a bidder | Where it lives | Issue |
|---|---|---|---|---|
| Chat | **Deed Chat** | one composer everywhere: ask about a county, a case, an address; upload a document and Deed cites it; voice | `/` + `/chat`, same "+" menu, same mic | C2 (#19835 live), C2c (#19934) |
| Cowork | **Deed Watches** (scheduled work) | background execution while the bidder sleeps: watch a case, a county, a sale date; regenerate the report before the sale; deliver by email/calendar; export to Drive | sidebar "Scheduled" (= Claude's Scheduled), Alerts & Watches, Google Calendar/Drive connectors, Resend delivery | C4 (#19829 P3) |
| Code | **Deed Research + Deed API** | autonomous multi-step work on one property (Deep Research → SIGNAL$ report, 18 sections, evidence per section) and the same power for developers: API keys + `mcp.biddeed.ai` so Deed runs inside their own tools | Deep Research in the "+" menu; Settings → API keys & MCP | C2 (Deep Research), C8 (developer surface, new) |
| Projects | **Projects** | one project per property the bidder intends to win: files (upload/version/download), project-scoped chat, S1–S5 sticky layers, report sections with progressive disclosure | sidebar "Projects" | C3 (#19847) |
| Skills | **Skills** | the six system skills bound to live RPCs + user-authored SKILL.md playbooks (a bidder's own due-diligence checklist) that produce the same deliverable every time | sidebar "Skills", `/` picker in the composer | C4b (#19924) |

Rule: no layer ships as a page without its harness row in §2 and its function proof in the PR body. Vendor/model names appear only on Settings → Models (C6, #19925).


## 7. Checkpoint board v2 — parity = every row VERIFIED (supersedes the CP-C table of 2026-09-04 03:5x UTC)
Verified = live URL, Chromium, both viewports, harness row green, function proof pasted in the PR, judge ≠ builder. A green run is not evidence.

| CP | Layer | Deliverable | Closes on | Issue | State 2026-09-04 16:00 UTC |
|---|---|---|---|---|---|
| C1 | Projects | chat persistence tables | migration live, cross-user 0 rows | #19835 | ✅ approved |
| C2 | Chat | composer "+" menu, uploads cited, recents, search (Worker /chat) | PDF cited; recents survive reload; search hits | #19835 | ✅ live (TXT); ❌ PDF extractor; ❌ Deed "no auctions" contradiction (P0) |
| C2b | Chat | verified identity (magic link / OTP or Clerk) — no email-claim reads | other-email token → 0 rows AND unverified email cannot read | #19829 | ❌ not started — blocks D10 |
| C2c | Chat | one composer everywhere — homepage gets "+", mic, project scope | PDF uploaded from `/` cited by Deed | #19934 | ❌ queued |
| C3 | Projects | Projects sidebar; files up/version/download (signed URLs); project chat; S1–S5 sticky layers; report progressive disclosure | create → upload → cite → download → S1 greeting after 10 min | #19847 | ⏳ running |
| C4 | Watches (Cowork) | Scheduled sidebar; watch case/county/sale date; regenerate before sale; Resend + Calendar + Drive | one watch fires (Resend id), one calendar event, one Drive export | #19829 P3 | ❌ not started |
| C4b | Skills | six live-RPC system skills + user SKILL.md playbooks; `/` picker | six skills return live rows; user skill runs | #19924 | ❌ queued |
| C5 | Chat | slash commands, ⌘K, Quick/Deep/Voice selector, i18n, a11y ≥ 95 | Lighthouse ≥ 95 every route; keyboard walkthrough | #19829 P4 | ❌ not started |
| C6 | Chat | model providers: Router default, BYOK, Ollama, free tier | BYOK round trip ×2, key absent from every log, Ollama ping, free-tier note | #19925 | ⏳ running |
| C8 | Research + API | Settings → Developers: API keys + MCP config | create key → MCP call → revoke → 401 | #19937 | ❌ queued |
| A | Design | tokens: 23 `:root` → 1 generated, 0 hex outside it, gate wired | harness PALETTE green on all routes | #19845 | ❌ (site-wide literal mapping shipped 15:13 UTC as the interim) |
| B3 | Content | `/counties/*` + 301 + 503-on-RPC-error | 5 counties live = RPC same minute | #19846 | ❌ 5 runs died |
| B4 | Content | blog through the renderer, Article JSON-LD | byte-identical bodies | #19830 | ❌ |
| D10 | Gate | C2b verified identity live | negative test | — | ❌ |
| D11 | Gate | harness: 0 red gates on every route in routes.json | ui-audit.yml run link | — | 92 red at 15:40 UTC |
| D12 | Gate | all five Deed layers with function proof | this board all ✅ | — | ❌ |

### Sprint (honest, from today's throughput)
- **Fri Sep 4 (W1, to 18:00 ET):** Worker palette ✅, map ✅, calendar ✅, PRD ✅; C3 + C6 PRs if the runs deliver.
- **Shabbat (runner only):** C2c, C4b, C3/C6 fixes, B3 retry — stacked as verified PRs.
- **Sat Sep 5 21:00–23:00 ET (W2):** merge batch → Chat, Projects, Skills, Providers live.
- **Sun Sep 6 (W3):** content T-0 per CONTENT_SOP §3 stands on its own; parity rows C4, C5, C8, C2b, A, B3/B4 will NOT all be green by 21:00 ET.
- **Wed Sep 9:** earliest credible D12 — all five layers verified — if the runner delivers one clean PR per phase per day. Anything later than that is reported as slip, not hidden.


## 8. Typography and contrast parity (Ariel, 2026-09-04: identical reading experience to Claude.ai)
Claude.ai reads the way it does because of four things we can copy exactly, and one we cannot. What we cannot copy: Anthropic's licensed typefaces. What we copy exactly: the size ramp, the line-height rhythm, the weight discipline, and the contrast policy. One token file (packages/tokens, #19845) carries these for both repos; the harness enforces them (G-TYPE).

| Role | Desktop | Phone | Weight / line-height | Colour (light) | Min contrast |
|---|---|---|---|---|---|
| Message / body text | 16 px | 16 px (never below - avoids iOS zoom and matches Claude) | 400 / 1.6 | ink #222222 on white | 16:1 (AAA) |
| Secondary text (sidebar rows, chat list, meta) | 14 px | 14 px | 400-500 / 1.5 | navy #002A54 | 8.5:1 |
| Labels, eyebrows, timestamps, footnotes | 12-13 px, uppercase eyebrows tracked | 12-13 px | 500-600 / 1.4 | navy #002A54 | 8.5:1 |
| Composer input | 16 px | 16 px | 400 / 1.5 | ink | 7:1 |
| H1 / greeting (serif display) | 40-48 px | 30-34 px | 500 / 1.1 | ink | 7:1 |
| H2 (serif display) | 28-32 px | 24-26 px | 500 / 1.15 | ink | 7:1 |
| H3 / card titles (sans) | 18-20 px | 17-18 px | 600 / 1.3 | ink | 7:1 |
| Numbers (stats, prices) | 24-32 px | 20-24 px, never wrap | 600, tabular-nums | ink or brand blue #0073CF | 4.5:1 (#0073CF on white = 4.8:1) |
| Buttons | 14-15 px | 15 px | 600 / 1 | white on brand blue (hover #005DAA) / ink on white | 4.5:1, hit area >= 44 px on phones |

Rules
- Two families only: the UI sans (Inter today) and the serif display - the same pairing Claude uses (sans UI, serif headline). No third family, no per-page font-size literals; every size is a token step (--fs-1 ... --fs-8).
- Brand blue #0073CF is the only accent and clears 4.5:1 on white (4.8:1), so it may carry text at any size. The Tailwind amber/orange/red/green families and the retired terracotta #9f4d32 / #d97757 are not decoration either - they are gone (G-PALETTE).
- Line length 60-75 characters on desktop (max-w-prose on message bodies), full width on phones with 16 px side gutters.
- Dark mode inherits the same ramp; only colours change (tokens), never sizes.
- Harness gate G-TYPE: on every route, body/message text >= 16 px on phones and >= 15 px on desktop, secondary >= 14 px, nothing under 12 px; font-family set == {sans, serif, mono}; contrast per the table. A route with any literal font-size outside the token steps fails.

Measured 2026-09-04 (Chromium 390): /buy-report has 29 text elements under 14 px, /counties 25, the sample report 11, /chat 8 - see #19943 M1.
