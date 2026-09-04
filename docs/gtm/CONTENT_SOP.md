# CONTENT_SOP.md — BidDeed.AI website + content operating procedure

Status: v1.1 · 2026-09-04 · Owner: Ariel Shapira · Content lead: Claude (Cowork) · Executor: Claude Code via `cc-runner-ghonly.yml` in this repo, unattended.
Scope: biddeed.ai only. zonewise.ai and winnerdataai.com inherit later.
**Launch: T-0 = Sunday 2026-09-06 21:00 America/New_York (2026-09-07 01:00 UTC).** §3 is the 72-hour sprint that gets there. §4 is the steady state that starts the Monday after.

This document is procedure, not canon. It says **when** work happens, **what "done" means** per asset, **what is checked before anything goes public**, and **how every asset feeds the paid path**. It restates nothing from the canon files below; where this SOP and a canon file disagree, canon wins and this file is wrong.

## 0. Read order (every content session, every run)

| # | File / row | Why |
|---|---|---|
| 1 | `docs/intent/MANDATES.md` | M1–M6 standing mandates, injected into every cc-runner brief |
| 2 | `docs/gtm/BIDDEED_VOICE_CONTENT_META_PROMPT_v2.md` | **The content canon.** Voice, hero stack, founder story, pain points, M7 carve-out, checkpoints C0–C7, hard rules, model routing. Machine copy: `unified_context` key `biddeed_content_voice_v2` |
| 3 | `docs/gtm/MISSION.md` + `docs/gtm/META.md` | CMO Factory never-list, gates in code, autonomy dial, lanes, standing mandates M7/M8 |
| 4 | `docs/canon/01_WINNER_DATA_CANON.md`, `docs/canon/03_PRODUCT_AVATAR_MAP.md` | Product naming: the paid deliverable is the **SIGNAL$ Property Report** (18 sections). "S5" is internal shorthand only, never public |
| 5 | `CC_META_PROMPT.md` | Operating contract: VERIFIED means observed |
| 6 | `unified_context` keys `m7_founder_carveout_sep3`, `biddeed_tagline_v1` | Machine copies of the Sep 3 brand decisions |
| 7 | This file | Procedure |

Lane-specific specs, read only when touching that lane: `docs/gtm/REEL_SPEC_BOLT32.md`, `docs/gtm/REEL_STUDIO.md`, `docs/gtm/YOUTUBE_LANE.md`, `docs/gtm/DISTRIBUTION_LANE.md`, `harness/gtm/END-TO-END.md`.

## 1. Verified baseline — 2026-09-04 ~00:30 UTC (Honesty V3 tags; re-query before relying on any number)

| Item | State | Tag |
|---|---|---|
| `auctions_summary_ssot()` | total 117,048 · upcoming (live scope) 2,407 · counties 67 · counties_upcoming 55 · date range 2017-04-10 → 2027-02-03 · `generated_at` 2026-09-04T00:27Z | VERIFIED |
| Same figures in the canon's moat table (written 2026-09-03) | 108,968 · 2,709 · 56 · 2027-01-06 — **already different after one day.** This is the live-number rule proving itself: canon figures are a snapshot, never copy | VERIFIED |
| `v_certified_counties` (consecutive_gold ≥ 1) | 13 | VERIFIED |
| `seo_query_universe` (C1) | 365 rows (335 county×template + 30 authored informational) | VERIFIED |
| `social_content_queue` / `content_library` / `youtube_scripts` / `viral_competitor_reels` | 696 / 0 / 0 / 0 rows | VERIFIED |
| `site.site_content` | exists, 0 rows, columns `slug, title, hero_copy, body_jsonb, published, updated_at` — nothing renders it yet | VERIFIED |
| `spi_gates.gtm_factory_halt` | OPEN (opened 2026-09-03 09:50Z, `verified_at` null) → `gtm-validate.yml` / `gtm-merge.yml` refuse to run (fails closed by design, `.factory/gtm/STOP.md`). The other two halt signals are clear: control issue #19780 carries `factory:queued` only, no `.factory/gtm/STOP` file | VERIFIED |
| `spi_gates.test_purchase` | OPEN since 2026-07-31 → publish dial = human click for every external publish (META §4) | VERIFIED |
| Autonomy dial | no live record of dial ≥ 3; `factory/gtm/doctor.py` is the only authority | VERIFIED (per #19821 spec) |
| County pages LIVE | `/county/{slug}` × 67 on the Worker (`src/worker.js`), schema `Dataset`+`Organization`+`Place`, data via `v_property_card_verified`; `/counties` index live | VERIFIED (curl 200) |
| County pages C2 | `/counties/{county}` + `/counties/{county}/{foreclosure\|tax-deed}` built in biddeed-web PR #17 + Worker proxy PR #19823; **not merged, 404 live** — held at M8 | VERIFIED (curl 404, PR branches read) |
| Calendar surface | `/radar` (biddeed-web behind the Worker proxy), filterable `?county={slug}&sale_type={foreclosure\|tax_deed}`; `/auctions` is a JSON endpoint (400 without `?county=`), not a page | VERIFIED |
| Paid path | `/buy-report?county={slug}` → biddeed-checkout, tier `s5_onetime` (internal id), rendered as "Buy SIGNAL$ Property Report — $25" on property cards | VERIFIED |
| Reels / deal pages | `/reels`, `/reels/{code}`, `/deal/{county}/{case}`, `/r/{code}` live; reels daily 11:00 UTC (`biddeed-reels-daily.yml`), all rows `pending_approval` | VERIFIED |
| `/blog` | 6 posts hard-coded in `BLOG_POSTS` (worker.js ~L3380) — code deploy per post. **Frozen: no new entries** | VERIFIED |
| Compliance gate in this repo | `factory/gtm/gate.py` — 6 checks (banned/vendor terms, person names, homeowner contact, certified-count re-query, insurance copy scoped to Protection Partners). `VENDOR_NAMES` has **no** competitor spellings, no "S5", no retired tagline, no patent pattern | VERIFIED (file read) |
| `scripts/audit-site.mjs` referenced by canon hard rule 1 | exists only on biddeed-web branch `cp-c2-counties-pages-19821` (PR #17): competitor spellings + `COMPETITOR_FIELD_LEAK` + `HARDCODED_COUNT`. Not on biddeed-web `main`, not in this repo | VERIFIED |
| Live copy on `/` (biddeed-web) | canon hero stack **not live** (0 hits for any of its three lines); "Get S5 Report — $25", "S5 Single Report", "12 provisional patent claims pending" (×2) — violates MANDATES M3 and canon hard rule 6 | VERIFIED (curl 2026-09-04 00:42Z) |
| C0 technical gaps | no meta description on `/chat` `/disclaimer` `/privacy` `/security` `/terms`; no H1 on `/radar`; no `Organization`/`WebSite` JSON-LD on `/`; blog posts carry no `Article` schema | VERIFIED (`docs/spec/19821.md`) |
| GEO tracker (C5) | `geo_tracker.*` schema live (49 tables), `everest-geo-tracker` repo exists, `cloro_api_key` vaulted; weekly run over the C1 set **not wired** | VERIFIED (schema) / UNTESTED (run) |
| Machine copy `biddeed_content_voice_v2` | absent before this commit; written by this session from the canon file | VERIFIED |
| Founder proof-point figures on everestcapitalusa.com | not re-fetched this session | UNTESTED |

## 2. Asset types and the funnel contract

Canon flow: **Answer asset → County page → Calendar → SIGNAL$ Property Report.** Free question answered → free county data → the one number that costs money. No orphans: every asset carries the next hop.

### 2.1 Canonical URLs (single source for every link an asset emits)

| Hop | Live URL today | After C2 merges | Notes |
|---|---|---|---|
| County page | `/county/{slug}` | `/counties/{county}` (+ `/foreclosure`, `/tax-deed`) | Switch happens in ONE issue that also adds the 301 from the old path and updates `sitemap.xml`. Until then all assets link the live path. Never link a 404 |
| Calendar | `/radar?county={slug}` (+ `&sale_type=foreclosure\|tax_deed`) | same | Canon says "/auctions calendar"; on the live site the human calendar is `/radar` and `/auctions` is JSON. Link `/radar` |
| Report (paid) | `/buy-report?county={slug}` | same | Visible label is always "SIGNAL$ Property Report". `$25` may be stated only if read from the live checkout config in the same run |
| Deal page | `/deal/{county}/{case}` | same | Reel end card + QR target |
| Answer asset | `/answers/{slug}` (renderer = SPR-02) | same | Server-rendered from `site.site_content` |

Slugs: county slug is the `county` value in `auctions_summary_ssot().counties_detail` (snake_case, e.g. `miami_dade`, `palm_beach`). Never invent a slug; join to the RPC output.

### 2.3 Founder-narrative anchor (why anyone cares that we built this)

Every asset that carries the founder's voice — homepage founder block, About, the intro of any long-form, the YouTube channel trailer, a reel's framing line — is anchored to ONE archetype and never drifts: **the "Problem" founder — "I identify with you."** Ariel spent 20+ years buying distressed Florida assets at courthouse steps and online tax deed sales, got burned by the exact traps in the PAIN POINTS table, and wrote the software for his own money first. That is the canon founder story; §2.3 exists so no asset re-frames it as a generic "visionary disrupting real estate" or an "analyst who spotted an AI trend" — those are different archetypes we do not use, because they are not true and they do not convert an auction bidder. The narrative DoD in §5.9 and the N-checks (P15–P18) enforce it. This is a marketing-narrative rule, not a compliance one; the compliance never-list (M7, homeowner contact, competitor) still governs on top of it.

### 2.2 Link contract per asset type

| Asset | Must link out to | Must be linked from | Feeds next hop by |
|---|---|---|---|
| Answer asset (statewide) | `/counties` index + the 3 counties with the most `upcoming` at render time (RPC, never static) · `/radar` · `/buy-report` | county pages' "Questions" block, `/blog` index, long-form description, reel deal pages | "See the calendar for {county}" → `/radar?county=` |
| Answer asset (county-scoped) | that county's page · `/radar?county=` · `/buy-report?county=` | that county's page FAQ, `seo_query_universe.target_page` | same |
| County page | `/radar?county=` (both sale types) · `/buy-report?county=` (buy-CTA only on complete-coverage counties — journey 4) · ≥2 answer assets | `/counties`, `/sitemap.xml`, every answer asset, deal pages in that county | live counts + next sale date are the urgency (energy rule 3) |
| Long-form YouTube (weekly) | description block: county page(s) covered · `/radar` · `/buy-report` · 1 answer asset · signature line | channel, `social_content_queue` captions | "Full calendar at biddeed.ai/radar" |
| Reel + deal page | deal page → county page · `/radar?county=` · report CTA | `/reels`, `/r/{code}`, social captions | end card = clickable deal page (Everest-hosted only) |
| Social caption | the asset's `/r/{code}` short link (UTM'd) | — | measured per variant in `winnerdata.reel_links.clicks` |
| Site copy change (hero/banner/footer) | unchanged link set | — | hero CTA → `/radar` |

Rule: a link is only "present" if the target returned 200 in the same run (`gate.py --check-url`). A link to a route that is not live yet is a FAIL, not a placeholder.

## 3. 72-HOUR LAUNCH SPRINT — T-72h Thu 2026-09-03 21:00 ET → T-0 Sun 2026-09-06 21:00 ET

Everything below is one lane per issue, dispatched in parallel to `cc-runner-ghonly.yml` (shard by issue — one issue can never hold two lanes; different issues run concurrently). Machines run around the clock. Humans click in three windows only.

### 3.1 Click windows (Ariel — the only human steps in the sprint)

| Window | When (ET) | What gets clicked |
|---|---|---|
| W1 | Fri 2026-09-04 09:00–18:00 | Merge SPR-03 (homepage canon copy + S5/patent drift), SPR-06 (C0 fixes), and — recommended — SPR-08 (C2: biddeed-web PR #17 first, then this repo's PR #19823). Rollback for C2 is one line: remove `/counties` from the Worker proxy allowlist |
| W2 | Sat 2026-09-05 21:00–23:00 | Merge SPR-04 + SPR-05 (7 answer assets) and SPR-02 (renderer) if their verdicts are PASS; anything that failed a verdict stays open |
| W3 | Sun 2026-09-06 09:00–20:00 | Merge whatever W2 left; close `spi_gates.gtm_factory_halt` (SPR-11) so the validator/merge workflows run in steady state; 20:00 go/no-go against §3.4 |

No click window exists Fri 18:00 → Sat 21:00 ET. Nothing in the plan waits on a click inside that gap; every shard that finishes then simply sits as an open PR with a verdict.

### 3.2 Shards (each row = one GitHub issue, template §4.1, dispatched at the time shown)

| ID | Issue | Repo | Deliverable | DoD | Click? | Dispatch |
|---|---|---|---|---|---|---|
| SPR-01 | Gate extension | this repo | `factory/gtm/gate.py`: `COMPETITOR_TERMS` (both spellings from canon hard rule 1), `RETIRED_LINES`, `PATENT_RE`, `CANON_STRINGS` read from the canon file, visible-text exclamation / urgency / positioning checks, person-name regex widened with the founder allowlist, plus `CONTEMPT_RE` (P17) and `BUZZWORD_RE` (P18) for the narrative layer; fixtures + `test_gate_negative.sh` cases including one contempt line and one buzzword line | §6 P2–P9 and P17–P18 turn from GAP to EXISTS; negative tests fail on the right strings | No — code lands on `main`, no publish | T-72h |
| SPR-02 | Answer-asset renderer + sync | this repo | Worker route `/answers/:slug` reading `site.site_content where published`, same public shell as `/county`, renderer tokens for live figures (em-dash on RPC failure), sitemap entries; `.github/workflows/content-sync.yml`: push to `main` touching `content/**` → upsert into `site.site_content` (`published=true`) → `gate.py --check-url`. Route ships dark (404 until a row is published) | §5.1 A10 reproducible on a test slug that is deleted after; `deploy-worker.yml` run success | Renderer code: no. First published row: W2 | T-72h |
| SPR-03 | Homepage canon copy + drift | biddeed-web (clone to `/tmp`, PR) | Hero stack exactly per canon (three lines, that order); every "S5" label → SIGNAL$ Property Report; patent line → number-free or removed; nothing else touched (K3). Check biddeed-web PR #16 first — if it already carries any of this, build on it, do not fork it. The founder block on `/` also carries the narrative layer: §5.9 N1–N7 | §5.6 S1–S4 **and §5.9 N1–N7 for the founder block**; curl of the PR preview shows all three hero lines, zero "S5", zero `/patent/i` hits outside the allowed phrase | W1 | T-72h |
| SPR-04 | Answer assets shard A | this repo (branch + PR) | `content/answers/` for: what survives a foreclosure sale · what survives a tax deed sale · foreclosure vs tax deed · how the max bid is calculated | §5.1 A1–A11 per file; A12 at W2 | W2 | T-72h |
| SPR-05 | Answer assets shard B | this repo (branch + PR) | `content/answers/` for: deposits and payment · redemption · surplus funds | §5.1 A1–A11 per file; A12 at W2 | W2 | T-72h |
| SPR-06 | C0 technical fixes | this repo (Worker) + biddeed-web (PR) | Worker: meta descriptions on `/chat` `/disclaimer` `/privacy` `/terms`; `Article` JSON-LD on the 6 blog posts. biddeed-web: meta description on `/security`, H1 on `/radar`, `Organization` + `WebSite` JSON-LD on `/` with `sameAs` → @biddeedai | §5.7 | Worker side: no. biddeed-web side: W1 | T-72h |
| SPR-07 | County page verification, all 67 | this repo | Run §5.2 K2/K3/K4/K6/K7 against every live `/county/{slug}`; defect list in `docs/spec/<issue>.md` with paired RPC-vs-curl evidence; fixes only for K2/K4 defects (live number ≠ RPC, competitor-sourced field rendered) — everything else is a filed issue, not a fix | `agent_ops_log` row per county (`dispatch_id='content-county-verify'`) | No | T-72h |
| SPR-08 | C2 merge + URL switch | biddeed-web + this repo | After W1 merges PR #17 and #19823: live curl proof on 5 counties (`docs/spec/19821.md` DoD), Rich Results Test on 2 URLs, then ONE issue that 301s `/county/{slug}` → `/counties/{slug}`, updates `sitemap.xml`, rewrites `links.county` in `content/answers/*.md` | §5.2 K1–K9 on the new pages; old URLs 301 | W1 (merge); switch runs after, no click | T-48h (after W1) |
| SPR-09 | Launch long-form script | this repo | "Auction Week in Florida" for launch week → `youtube_scripts` row `status='draft'` + `content/longform/2026-W37.md`; upload lane stays on its own quota rules | §5.3 L1–L7 **+ §5.9 N1–N7** (the founder intro/outro is founder voice) | No (draft) | T-48h |
| SPR-10 | GEO T-0 baseline (C5) | this repo + `everest-geo-tracker` | Wire the weekly run over the C1 set; execute once before T-0 so the parity review has a pre-launch baseline; report per model | §5.8 | No | T-48h; if not green by T-12h, mark UNTESTED and launch without it |
| SPR-11 | Un-halt the factory | Supabase (M2-protected) | Close `spi_gates.gtm_factory_halt` (`verified_at = now()`, `proof` = link to the W3 go decision); confirm #19780 has no `factory:halt`; run `doctor.py` and record the earned dial in `docs/gtm/reports/launch-2026-09-06.md` | validator + merge workflows run on the next `17 */6` tick | W3 — Ariel's stop button, only he closes it | W3 |
| SPR-12 | Launch report | this repo | `docs/gtm/reports/launch-2026-09-06.md`: §3.4 gate table with live evidence, everything that shipped, everything that did not (tagged), sitemap submitted to GSC if a property exists ("not connected" if not) | Honesty V3 | No | T-0 + 2h |

Reels need no sprint issue: `biddeed-reels-daily.yml` (11:00 UTC) and the pre-sale lane keep producing `pending_approval` rows; the deal pages already satisfy §2.2 once SPR-07 confirms their links.

### 3.3 Day board

| Day | Machines | Humans |
|---|---|---|
| Thu night (T-72h) | Dispatch SPR-01..07 in parallel. Builders read intent → canon → this SOP. Every shard ends with `docs/spec/<issue>.md` and an open PR or a `main` commit where no publish is involved | — |
| Fri (T-60h → T-48h) | SPR-01 lands → the validator tick at 17:xx UTC re-runs gate.py on every open PR with the new checks; verdicts written. SPR-08 dispatched after W1 merges; SPR-09/10 dispatched | W1 09:00–18:00 ET |
| Sat (T-36h → T-24h) | Validator ticks every 6h; failed verdicts bounce to the builder issue with the failing string quoted; builders fix on the same branch. GEO baseline runs. Nothing publishes | W2 21:00–23:00 ET |
| Sun (T-12h → T-0) | `content-sync.yml` publishes merged answer assets; live curl proofs; Rich Results Test on public URLs; SPR-12 assembles the gate table | W3 09:00–20:00 ET; go/no-go 20:00; T-0 21:00 |
| Mon 2026-09-07 | Steady state begins: §4 planner first run 05:07 ET | — |

### 3.4 Launch gate (T-0 is called only when every row is PASS with evidence in the launch report)

| # | Gate | Evidence |
|---|---|---|
| G1 | `/` renders the canon hero stack, zero "S5", zero patent-phrasing violations | curl + screenshot 320/1440 |
| G2 | ≥ 5 answer assets live at `/answers/{slug}`, each: curl contains `answer_first` verbatim, FAQPage parses, links 200, verdict PASS from `main`, extraction test PASS | verdict files + curl |
| G3 | 67 county pages: live number = RPC number at the same minute on a 10-county sample; zero competitor-sourced fields rendered; buy-CTA only where coverage is complete | SPR-07 log rows |
| G4 | `sitemap.xml` lists every live answer asset and county page, no 404s in it | crawl of the sitemap |
| G5 | `gate.py` with SPR-01 checks passes on every published asset and on the rendered `/` | validator run log |
| G6 | `spi_gates.gtm_factory_halt` closed by Ariel; `gtm-validate.yml` produced a real run (not halted) after closure | workflow run id |
| G7 | Reels lane unaffected: last daily run success, rows still `pending_approval` (M1 holding) | `list_public_reels` count |
| G8 | Nothing producer-facing was sent; no Vercel configuration touched; incumbent's name absent from every diff in the sprint (`git log -p` grep) | grep output |

Anything not PASS at 20:00 ET Sunday launches without that item, tagged in the report — never with a patched-over claim.

### 3.5 Rollback

Per shard, one line: SPR-02 renderer → revert the Worker commit (`deploy-worker.yml` redeploys the prior SHA); SPR-03/06 → revert the biddeed-web merge (`cloudflare-production.yml` redeploys); SPR-08 → remove `/counties` from the proxy allowlist; answer assets → set `site.site_content.published=false` for the slug (renderer returns 404, sitemap regenerates). Nothing in the sprint touches checkout, `multi_county_auctions`, or any M2 object.

## 4. Steady state after launch (weekly, from Mon 2026-09-07)

C6 target, fixed: **2 answer assets · 5 county refreshes · 1 long-form · reels from the reels pipeline** per week. Judged by an agent that did not write it. Four straight weeks with no human writing copy closes C6.

| When (ET) | Cron (UTC) | Job | Mechanism | Output | Gate |
|---|---|---|---|---|---|
| Mon 05:07 | `7 9 * * 1` | **Plan** | `content-weekly-plan.yml` (built as the first steady-state issue) runs a deterministic script: picks 2 queries from `seo_query_universe` not yet covered (informational first, then county navigational where GEO shows us absent), picks 5 counties by `upcoming` desc with `next_auction_date` ≤ 14 days, rotating so every county is refreshed at least every 14 weeks; fills the issue template in §4.1; creates 3 issues (one per lane, M5) via `gha_create_issue`; dispatches each once to `cc-runner-ghonly.yml` (workflow 297104962) | 3 issues, 3 runs | halt check (§6 P1) + `quota_gate_check('engineering')`; NO_READING → dispatch only the county-refresh issue |
| Mon–Wed | — | **Build** | cc-runner session per issue. Answer assets → `content/answers/{slug}.md` on a branch + PR. County refresh → verification report + fix PR only if a defect is found. Long-form → `youtube_scripts` row `status='draft'` + `content/longform/{yyyy}-W{ww}.md` | PRs / rows / `docs/spec/<issue>.md` | MANDATES M1–M6; §5 DoD |
| Every 6h | `17 */6 * * *` (exists) | **Validate + judge** | `gtm-validate.yml` reads protected paths from `main`, runs `factory/gtm/gate.py --paths <artifacts> --check-url <live urls>`; judge pass = fresh-context session (never the builder's) using `.claude/skills/copy-editing`, `ai-seo`, `seo-audit`; writes `docs/gtm/verdicts/<issue>.json` (`validated_from: "main"`) | verdict file | markers `GTM_COMPLIANCE_PASSED` / `GTM_PAGE_200` / `GTM_RENDER_OK`; absence = FAIL |
| Thu 09:00–17:00 | — | **Founder click window** | Ariel merges PRs with `verdict==PASS && gates_green` (dial < 3) — this merge IS the publish. At dial ≥ 3 and `test_purchase` closed, `gtm-merge.yml` merges instead (META §4) | live pages | M8 |
| On merge to `main` | push | **Publish** | `content-sync.yml` (SPR-02) upserts merged `content/**` into `site.site_content` (`published=true`), then `gate.py --check-url https://biddeed.ai/answers/{slug}`; Worker changes deploy via `deploy-worker.yml` (exists) | 200 + row | `GTM_PAGE_200` |
| Daily 07:00 | `0 11 * * *` (exists) | Reels | `biddeed-reels-daily.yml` → `pending_approval` | reels | REEL_SPEC_BOLT32 |
| Daily 11:00 | `0 15 * * *` (exists, dormant by design) | YouTube upload lane | `youtube-publish.yml` per `YOUTUBE_LANE.md` slots/quota | uploads | M8 |
| Sat 00:07 | `7 4 * * 6` | **GEO run** (C5, SPR-10) | `everest-geo-tracker` over the C1 set across ChatGPT/Claude/Perplexity/Gemini/Copilot/Grok/Google AIO → `geo_tracker.prompt_results` | per-model rows | none (read-only) |
| Sun 18:07 | `7 22 * * 0` | **Weekly content report** | `docs/gtm/reports/content-{yyyy}-W{ww}.md`: assets shipped vs target, verdict pass rate, GEO mention/citation/rank per model + who is cited instead, county-page live-number spot checks, C6 streak (weeks with zero human-written copy), G-SPI leading metrics (deal-page captures, `/r/` clicks). Numbers from SQL only; the LLM writes the prose, never the number | report file + `agent_ops_log` row | Honesty V3 |

No job waits on a human click Friday afternoon through Saturday night. The queue holds; nothing expires.

Blocked-week rule: if the halt gate is open or quota says NO_READING for two consecutive Mondays, the planner files one issue titled `CONTENT: blocked 2 weeks — <reason>` and stops. That issue is the only thing that reaches Ariel.

### 4.1 Issue template (sprint shards and weekly issues; the planner fills the brackets — the LLM never chooses the plan)

```
Operating contract: CC_META_PROMPT.md. Read it first. READ ALL COMMENTS ON THIS ISSUE BEFORE STARTING.
Canon: docs/gtm/BIDDEED_VOICE_CONTENT_META_PROMPT_v2.md · Procedure: docs/gtm/CONTENT_SOP.md
Lane: [answer-assets | county-refresh | longform | gate | web | geo | ops]   Sprint/Week: [SPR-nn | yyyy-Www]
M7 (founder carve-out applies, no other person names) · M8 (no publish step; open a PR / write status='draft' rows only)

/goal
[answer-assets]  Ship answer assets for queries [ids or the C3 question list] → content/answers/[slug].md each
[county-refresh] Refresh + verify county pages for [c1 … cn]
[longform]       Script "Auction Week in Florida" for [yyyy-Www] → youtube_scripts row (status='draft') + content/longform/[yyyy-Www].md
[gate|web|geo|ops] [the single deliverable from CONTENT_SOP.md §3.2 for this SPR id]

DoD: docs/gtm/CONTENT_SOP.md §5 for this lane, every item, with evidence in docs/spec/<issue>.md
Pre-publish checklist: docs/gtm/CONTENT_SOP.md §6 P1–P14, each tagged PASS/FAIL/N-A with the command or query used
Non-goals: no copy outside this lane, no workflow/cron edits unless this SPR names the file, no schema changes, no new tables, no merge, no publish, no competitor name anywhere, no Vercel
Negative test: [answer-assets] a draft containing a retired tagline line must FAIL gate.py; [county-refresh] a page whose rendered count ≠ RPC count at the same minute is logged as a defect, never "close enough"; [longform] a script with any person name other than the founder's must FAIL; [gate] each new check has a fixture that fails; [web] the PR preview is curl'd, not assumed
```

## 5. Definition of done, per asset type

"Done" = every row in the table for that asset is PASS with evidence in `docs/spec/<issue>.md`, plus the §6 checklist. Partial = `TASK — PARTIAL` with the failing rows named. Nothing is done because it was committed; done is observed (CC_META_PROMPT prime directive).

### 5.1 Answer asset (AEO page, canon C3)

Source of truth: one file `content/answers/{slug}.md` (git), rendered from `site.site_content` at `/answers/{slug}`.

| # | Requirement | Evidence |
|---|---|---|
| A1 | Frontmatter: `slug`, `title` (≤ 60 chars), `meta_description` (≤ 155), `question` = exact `query_text` of the targeted `seo_query_universe` row(s) + their ids, `scope` (`statewide` or a county slug), `statutes[]`, `faq[]` (3–5 Q/A pairs), `links {county, radar, report}`, `author: ariel-shapira` (Person schema ref), `version`, `date` | file |
| A2 | `answer_first`: the first 40–60 words of the body answer the question standalone, no preamble, no "in this article" | word count + extraction test A9 |
| A3 | Body order: pain → proof → product (canon PAIN POINTS). Second person. Short sentences. Active verbs | judge verdict |
| A4 | Every statute cited is fetched from leg.state.fl.us in the same run and the fetched sentence is quoted in `docs/spec/<issue>.md` (pattern from #19821); no statute from memory | spec file |
| A5 | No auction counts, certified counts, outcome counts, percentages or dollar figures in the static body. Live figures only via renderer tokens `{{county.upcoming}}`, `{{county.next_auction_date}}`, `{{state.upcoming}}` resolved from `auctions_summary_ssot()` at request time; RPC failure renders an em-dash | grep + render check |
| A6 | Founder proof points, if used, match everestcapitalusa.com character-for-character; the page is fetched in the same run and the figure grep'd | spec file |
| A7 | Links per §2.2, each returning 200 in the same run | `gate.py --check-url` |
| A8 | Schema: `FAQPage` (from `faq[]`) + `BreadcrumbList`; `HowTo` when the question is procedural (deposits, payment, how to bid); `Person` for the author with `sameAs` → everestcapitalusa.com, zonewise.ai; `Organization` `sameAs` → @biddeedai | JSON-LD parses; Rich Results Test clean once public (UNTESTED before) |
| A9 | Extraction test: a fresh-context judge session is handed ONLY the first 60 words and the `question`, and must return the correct answer without hedging. Recorded PASS/FAIL in the verdict file | verdict |
| A10 | Rendered page: server-rendered HTML contains `answer_first` verbatim (curl, no JS), exactly one H1 = the question, canonical tag, in `sitemap.xml`, meta description present | curl output |
| A11 | Compliance §6 all PASS | verdict |
| A12 | Published only by merge (dial < 3: Ariel's click; ≥ 3: `merge.py`) → `content-sync.yml` upsert `published=true` → live 200 | `GTM_PAGE_200` |

### 5.2 County page — build (C2) and weekly refresh

| # | Requirement | Evidence |
|---|---|---|
| K1 | Every number on the page is a live expression from `auctions_calendar_counts()` / `auctions_summary_ssot()`; no literal counts in source (`HARDCODED_COUNT` check) | audit script |
| K2 | curl of the live URL contains the same `upcoming` / `next_auction_date` as the RPC queried in the same minute; mismatch = defect issue, never "close enough" | paired output in spec |
| K3 | Buy-CTA rendered only for complete-coverage counties (journey 4); other counties show calendar + answer assets only | curl grep |
| K4 | No competitor-sourced columns reach the template (`photo_url`, `source_url`, `data_source`, any `po_*`) — the legacy Worker page selects `po_seo_url` but must never render it (outbound link removed Aug 17 2026; keep it that way) | `COMPETITOR_FIELD_LEAK` + code read |
| K5 | Schema `Dataset` + `Place` + `BreadcrumbList` + `FAQPage`; `Organization` `sameAs` → @biddeedai | JSON-LD parse; Rich Results Test once public |
| K6 | ≥ 2 answer-asset links relevant to the county's sale types; `/radar?county=` both sale types; sitemap entry; meta description ≤ 155; one H1 | curl |
| K7 | Negative tests: unknown county → 404; unknown sale type → 404 | curl |
| K8 | Weekly refresh (5 counties): K2, K3, K4, K6 re-run; result row in `agent_ops_log` (`dispatch_id='content-county-refresh'`, status VERIFIED/BLOCKED per county); defect → one issue per county, not a silent fix outside scope | log rows |
| K9 | Fewer pages beats padded pages: a county with `total = 0` in the RPC gets no sale-type sub-page (canon C2) | RPC + route list |

### 5.3 Long-form YouTube script (weekly "Auction Week in Florida", META §7)

| # | Requirement | Evidence |
|---|---|---|
| L1 | `youtube_scripts` row: `content_id = longform-{yyyy}-W{ww}`, `title`, `hook`, `sections` jsonb, `cta`, `status='draft'`; mirror file `content/longform/{yyyy}-W{ww}.md` | row + file |
| L2 | Narrative arc per canon: built it for my own money → it worked, here are the closings → now it's yours. Pain-first | judge |
| L3 | Every figure spoken is re-queried in the run and the SQL + result stored in `sections[].evidence`; figures older than the run are not spoken | row |
| L4 | No person names except the founder's (M7 carve-out); no county-clerk staff, no bidders, no defendants | gate.py + judge |
| L5 | Description block = canon YouTube description verbatim + links per §2.2 + signature line; title/description built by `agents/youtube/metadata_builder.py`, not by hand | file |
| L6 | Drafting on the providers named in the canon's Model routing section (router t1/t1.5, the routed GLM / DeepSeek lane); Haiku t2 via Max OAuth only for the judge pass; no Anthropic API call anywhere in the run | run log |
| L7 | Render/upload is the YouTube lane's business (`YOUTUBE_LANE.md` slots, quota, 7-day trap); this SOP's DoD ends at `status='draft'` + verdict PASS | verdict |

### 5.4 Reel + deal page

DoD lives in `docs/gtm/REEL_SPEC_BOLT32.md` and `docs/gtm/REEL_STUDIO.md` and is not repeated here. This SOP adds exactly one requirement: the deal page carries the county-page link, `/radar?county=` and the report CTA (§2.2), verified 200 in the run.

### 5.5 Social caption / distribution

DoD lives in `docs/gtm/DISTRIBUTION_LANE.md`. Additions: `social_content_queue.source_ref` names the asset it promotes; `short_code` + `utm_*` set; `approved_at` stays null until the click; caption passes §6 P2–P9.

### 5.6 Site copy change (hero, banner, footer, YouTube description, checkout labels)

| # | Requirement | Evidence |
|---|---|---|
| S1 | Strings are the canon strings character-for-character (hero stack order, short forms, signature). Nothing paraphrased | diff |
| S2 | Diff touches only the named strings (K3 surgical). Screenshot at 320 and 1440 attached to the spec | Playwright |
| S3 | §6 P6 (patent), P7 (canon strings), P2 (no "S5") pass on the rendered page, not just the source | curl |
| S4 | Which repo: Worker routes → this repo `src/worker.js` (deploys via `deploy-worker.yml` on push to `main`); `/`, `/radar`, `/discover`, `/alerts` → `breverdbidder/biddeed-web` (clone to `/tmp`, PR there; its `main` auto-deploys to Cloudflare via `cloudflare-production.yml`). Never touch Vercel configuration or workflows | PR link |

### 5.7 Technical SEO / schema fix (C0 findings, C4)

One issue per finding class. DoD: before/after curl of `<title>`, `<meta name=description>`, H1 count, JSON-LD types; sitemap/robots unchanged unless named; Rich Results Test clean once public.

### 5.8 GEO weekly report (C5)

DoD: `geo_tracker.prompt_results` rows for the week across all enabled platforms for every active prompt in the C1 set; report table per model: mention rate, citation rate, average rank, top 3 domains cited instead (domains only — the incumbent is never named in prose, its domain appears only as a data cell); "not connected" stated plainly for any platform with zero rows. Report is a file; nothing here publishes.

### 5.9 Founder-story / narrative asset (the "why anyone cares" layer — new)

Applies to any asset carrying the founder's voice: the homepage founder block, About, the intro/outro of a long-form, the YouTube channel trailer, and the framing line of a reel. Derived from the "How to Make People Care" founder-narrative framework, kept only where it fits an auction bidder — the parts of that framework written for a B2B procurement/RFP tool do not apply and are not used. These sit ON TOP of the compliance never-list, never instead of it.

| # | Requirement | Evidence |
|---|---|---|
| N1 | **Archetype lock (§2.3).** The asset is the Problem founder — "I identify with you." It never re-frames Ariel as a market-trend analyst ("I trust you") or a visionary disruptor ("I'd follow you"); those archetypes are not true here and do not convert a bidder. Aligns to the canon founder story verbatim in substance | judge verdict names the archetype |
| N2 | **Scene, not summary.** The story opens on ONE concrete auction scene a bidder recognizes, mapped to a canon PAIN POINT with its real cost — "a senior mortgage survived the HOA foreclosure I won" (six figures), "a tax deed I couldn't sell for two years without quiet title" — not an abstract "I was frustrated by inefficiency." At least one such scene present; zero if it reads as generic | judge + grep for a PAIN POINTS row |
| N3 | **The bidder is the hero.** The arc lands on "now it's yours" (canon). The founder is the proof and the guide, never the hero of the payoff. An asset where the founder is the protagonist of the resolution FAILS | judge |
| N4 | **Respect the bidder — no contempt for the status quo.** Name the enemy (guesswork, blind bidding, spreadsheets, showing up unprepared) — never the *person* who used them. Frame: "bidding off a spreadsheet made sense before; here's what's possible now." Any line that makes the reader feel stupid FAILS. This is how canon's "name the enemy" and the framework's "don't shame the prospect" coexist: the enemy is the friction, not the bidder | P17 regex + judge |
| N5 | **Vivid over vague.** Every claim is a concrete scene or a live number — zero buzzwords ("comprehensive intelligence solution," "next-gen platform," "streamlined workflow," "revolutionary," "seamless"). Reuses the energy checks | P18 denylist + judge |
| N6 | **Proof is public and real.** Founder proof points come only from everestcapitalusa.com (13 closed projects, recorded clerk instrument numbers) and match it exactly (A6). Milestones may be broadcast as proof — a launch, a county-coverage number, a real auction week from the SSOT — but never a named buyer, defendant, or auction subject (M7), and never an invented win | spec file + A6 |
| N7 | **Channel fits the archetype.** The Problem founder's native formats are short-form organic video (the reels lane) and honest written narrative (answer assets, long-form). Founder story rides those; it is not forced into a data-analyst essay or a keynote-vision format that the archetype does not carry | asset lane matches |

Narrative DoD is additive: a founder-voice answer asset must pass BOTH §5.1 (A-series) AND §5.9 (N-series).

## 6. Pre-publish checklist (every asset, every time; machine-checked where a check exists, judge-checked otherwise)

Legend — Where: `gate` = `factory/gtm/gate.py` · `audit` = biddeed-web `scripts/audit-site.mjs` · `judge` = fresh-context verdict session · `render` = curl of the live/preview URL. Status: EXISTS / GAP (→ sprint shard).

| ID | Check | Rule | How | Status |
|---|---|---|---|---|
| P1 | Halt + quota | None of the three halt signals active (`.factory/gtm/STOP`, label `factory:halt` on the control issue, `spi_gates.gtm_factory_halt` open); `quota_gate_check('engineering')` allow or cap. Unreadable = halted | workflow steps (exist in `gtm-validate.yml`) | EXISTS |
| P2 | Banned terms | `gate.py` VENDOR_NAMES + MISSION §3 list; **plus** the incumbent's name in both spellings exactly as listed in canon hard rule 1 (the strings live in code, never in prose); "S5" as a product name; the retired schema name listed in MISSION §3; the retired tagline line; "Shapira Analysis"/"Shapira Formula" as public product names (public name is SIGNAL$ Property Report) | gate `competitor_terms_scan` + `retired_lines_and_product_names_scan` | EXISTS (SPR-01, issue #19826) |
| P3 | Person names (M7, amended) | Allowed: `Ariel Shapira` and the six public roles in `m7_founder_carveout_sep3`. Forbidden: every other person — Mariam Shapira, homeowners, defendants, auction subjects, producers, customers, competitor staff. Never "licensed GC" about the founder. Reels keep their stricter no-names-at-all rule (`agents/reel_studio/hook_writer.py` bans the founder's name in reels on purpose — do not "fix" it) | gate `person_name_detector` + judge | EXISTS (SPR-01 widened the trigger set + added the founder allowlist) |
| P4 | Homeowner contact / relief | `gate.py` patterns + second-person-to-owner phrasing ("your home", "behind on your", "facing foreclosure", "stop the sale"); insurance-shaped copy scoped to Protection Partners only | gate `homeowner_contact_scan` (widened) | EXISTS (SPR-01, issue #19826) |
| P5 | Live-number rule | Static bodies carry no auction/certified/outcome counts, no accuracy %, no MRR/ARR. Live figures only through renderer tokens resolved from `auctions_summary_ssot()` / `auctions_calendar_counts()` at request time; em-dash on failure, never a stand-in. County counts pass `certified_county_count_match` (live `v_certified_counties`). Founder proof points fetched from everestcapitalusa.com in the same run and matched exactly. Canon table figures are never pasted (see §1 drift) | gate check 5 + render + spec evidence | EXISTS (count match) / judge for the rest |
| P6 | Patent phrasing | Default: no mention at all (background only). If unavoidable, exactly one of: `provisional patent application, 14 claims` or `provisional patent application` (number-free). Any other `/patent/i` hit FAILS, including "12", "14 patents", "patented", "patent-pending". Live `/` currently FAILS this (§1) | gate `patent_phrasing_scan` | Check EXISTS (SPR-01, issue #19826); live `/` still FAILS until SPR-03 lands the copy fix |
| P7 | Canon strings | Tagline, product line, signature, hero stack, banner, YouTube description only in their canon form (case and punctuation exact: `For Everyone. Everywhere.`). Retired line banned (P2) | gate `canon_strings_scan` — `CANON_STRINGS` parsed live from `docs/gtm/BIDDEED_VOICE_CONTENT_META_PROMPT_v2.md` (hero stack, banner, short forms, YouTube description), fallback list if the canon file is unreadable | EXISTS (SPR-01, issue #19826) |
| P8 | Energy rules | ≤ 1 `!` in visible text per page; no "act now" / "limited time" / "hurry" / "don't miss"; no competitor brand; passive "is provided" / "leveraged" → WARN | gate `energy_rules_scan` (strips `<script>`/`<style>` before counting) | EXISTS (SPR-01, issue #19826) — competitor-brand and passive-voice WARN still judge-only |
| P9 | Positioning | "US county" / "nationwide" per canon rule 5; never "all 50 states" or "3,000 counties" until live (tagline compliance note); always say these are real auctions run by US counties | gate `positioning_scan` + judge | EXISTS (SPR-01, issue #19826) |
| P10 | Funnel links | Required links per §2.2 present and each returns 200 in the run | `gate.py --check-url` | EXISTS |
| P11 | Technical | JSON-LD parses; required types per asset (§5); title ≤ 60; meta description ≤ 155 present; exactly one H1; canonical; in `sitemap.xml`; Rich Results Test clean once public | render + `seo-audit` skill | partial → SPR-06 |
| P12 | Extraction test (answer assets) | §5.1 A9 — judge ≠ builder | judge | EXISTS (procedure) |
| P13 | Evidence | `docs/spec/<issue>.md` written with files touched, SSOT objects used, DoD per row, commands run; `agent_ops_log` row; markers observed; verdict file produced from `main` | M6 + `merge.py` contract | EXISTS |
| P14 | Publish dial | M8: dial < 3 → PR open, Ariel's merge is the click; dial ≥ 3 and `test_purchase` closed → `merge.py`; producer-facing sends never (M1) | `doctor.py` + `gtm-merge.yml` | EXISTS |
| P15 | Archetype consistency (founder-voice assets only) | The asset reads as the Problem founder — "I identify with you" (§2.3, N1). A trend-analyst or visionary-disruptor frame FAILS. Non-founder-voice assets: N-A | judge names the archetype in the verdict | EXISTS (procedure) |
| P16 | Hero check | The bidder/customer is the hero of the payoff; the founder is proof + guide (N3). Founder-as-protagonist-of-the-resolution FAILS | judge | EXISTS (procedure) |
| P17 | Status-quo respect | No line shames the reader's current process. Regex seed: "you're doing it wrong", "still using spreadsheets", "if you're still", "amateur", "rookie mistake", "most bidders are too lazy/dumb" → FAIL. Enemy = guesswork/friction, never the bidder (N4) | gate `contempt_scan` (`CONTEMPT_RE`) + judge | EXISTS (SPR-01, issue #19826) |
| P18 | Vividness | Buzzword denylist → FAIL: "comprehensive solution", "next-gen", "cutting-edge", "streamlined", "seamless", "revolutionary", "industry-leading", "best-in-class", "leverage", "synergy", "robust platform". Founder-voice assets must contain ≥ 1 concrete auction scene or live number (N2/N5) | gate `buzzword_scan` (`BUZZWORD_RE`) + judge | EXISTS (SPR-01, issue #19826) — N2/N5 concrete-scene requirement still judge-only |

A FAIL on P2, P3, P4, P6 voids the asset (canon: "violating any one voids the work"); it is not patched in the validator, it goes back to the builder issue with the failing string quoted. A FAIL on P15–P18 does not void the asset but blocks publish until the builder rewrites the flagged passage; the judge quotes the passage.

## 7. Roles (who may write what)

| Role | Runs as | May write | May not |
|---|---|---|---|
| Planner | scheduled workflow, deterministic script | issues from the §4.1 template, `agent_ops_log` | copy, plan choices by LLM |
| Builder | cc-runner session for one issue (one lane) | `content/**`, code on a branch/PR, `youtube_scripts` drafts, `docs/spec/<issue>.md` | verdict files, `main` for content, protected paths, protected tables (M2) |
| Validator / judge | `gtm-validate.yml` + fresh-context session from `main` | `docs/gtm/verdicts/<issue>.json` | the asset itself |
| Merger | Ariel (dial < 3) / `merge.py` (dial ≥ 3) | `main` | — |
| Publisher | `content-sync.yml`, `deploy-worker.yml` | `site.site_content`, Worker deploy | producer sends |

## 8. After the sprint — what remains to make the loop fully unattended

Nothing here needs a new table, dispatcher, queue or CRM (MISSION never-list #8): `site.site_content` already exists for pages, `youtube_scripts` / `social_content_queue` / `content_library` for the other lanes, `seo_query_universe` for the plan.

| ID | Issue | Needs Ariel's click? |
|---|---|---|
| POST-01 | `content-weekly-plan.yml` + `scripts/content_weekly_plan.py` (§4 Plan row; `gha_create_issue` + `fire_workflow_dispatch`; blocked-week rule) — first steady-state issue, Mon 2026-09-07 | No |
| POST-02 | Weekly content report job (§4 Sun row) reading `agent_ops_log`, `geo_tracker.*`, `winnerdata.reel_links`, `winnerdata.funnel_events` — SQL only | No |
| POST-03 | C7 parity review on the C1 set against the SPR-10 baseline (keep/kill list, losses by how much) — two weeks after launch | No |
| POST-04 | Migrate the 6 frozen `BLOG_POSTS` into `site.site_content` so `/blog` stops needing a code deploy | Merge = publish → yes |

## 9. Non-goals of this SOP

Restated by pointer only: canon "Non-goals" and MISSION never-list #1–#9 apply verbatim. In addition, this file never contains marketing copy, never names the incumbent, never touches Vercel, and never decides the autonomy dial — `doctor.py` does.
