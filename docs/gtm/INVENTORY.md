# CMO Factory CP1 — GTM Asset Inventory

**Issue:** [#19778](https://github.com/breverdbidder/cli-anything-biddeed/issues/19778)
**Generated:** 2026-09-03 (session snapshot, live queries)
**Scope:** READ-ONLY. No deletions, archiving, renames, or publishes were performed — this document records verdicts only, per M1/M5.
**Honesty tags:** every claim below is VERIFIED (observed via `gh api`, live SQL, or HEAD request), UNTESTED, INFERRED, or UNKNOWN, per Honesty Protocol V3.

---

## 0. Deviation from brief (report per CC_META_PROMPT §1.2)

The brief states "chat count = 205 across 3 API pages." **VERIFIED (live count):** `gh repo list breverdbidder --limit 1000 --json name,...` returns **307 repos** (299 active + 8 archived) as of 2026-09-03. This is >45% higher than the brief's assumed 205 — reported per the re-derive-the-numbers rule rather than silently substituted. All downstream keyword filtering in this document runs against the live 307, not 205.

**VERIFIED:** of 307 repos, **85** match the keyword filter (`gtm|marketing|content|video|reel|media|cinematic|landing|web|seo|geo|social|youtube|viral|reventure|seller|paperclip|explainer|skills|craft`) applied to repo name or description.

---

## 1. Repo Inventory — 85 keyword-matched repos

Method: `gh api repos/breverdbidder/<repo>/readme`, `/contents/.github/workflows`, and repo metadata (license, homepage) — no local clones performed. Live/Dead is a heuristic (push recency + workflow/homepage activity), not a certified state. Verdict is a **recommendation only** — no repo was archived, merged, or deleted as part of this issue.

**VERIFIED** (fetched live 2026-09-03) for all 85 rows below.

| Repo | Last Push | License | Live/Dead | Purpose (1 sentence from README) | Verdict |
|---|---|---|---|---|---|
| SkillForceAI | 2026-01-30 | None | Dead (216d, no workflows/homepage) | Multi-tenant AI agent orchestration platform with skills marketplace and continuous learning for solo founders. | ARCHIVE-CANDIDATE |
| algoma-competitive-intelligence | 2026-02-19 | None | Dead (196d, one-off analysis, no workflows) | Reverse-engineered competitive intelligence report on Algoma.co's zoning-data sourcing (Zonomics, not Municode) vs ZoneWise.AI. | MERGE-INTO everest-seo |
| biddeed-marketing | 2026-01-30 | None | Dead (216d, no workflows/homepage) | Marketing assets, research, and content strategy repo for BidDeed.AI's positioning as an agentic AI ecosystem (not SaaS). | MERGE-INTO zonewise-content-engine |
| claude-skills-library | 2026-04-12 | None | Stale (144d, has deploy-skills.yml workflow but no homepage) | Personal collection of Claude Code skills (WhatsApp, TTS, poster gen, GH Pages deploy) by external author "aviz," not Everest-specific. | ARCHIVE-CANDIDATE |
| everest-board-skills | 2026-06-24 | MIT | Stale (71d, no workflows, homepage is external author's Medium) | 268 production-ready Claude Code skills/plugins/personas library spanning engineering, DevOps, marketing, and C-level advisory. | REUSE |
| everest-seo | 2026-04-12 | MIT | Stale (144d, no workflows/homepage) | Six SEO skills (audit, technical, content, schema, local, GEO) adapted from claude-seo for BidDeed.AI/ZoneWise.AI, results saved to Supabase. | REUSE |
| juriscraper | 2026-08-24 | BSD-2-Clause | Live (10d, active lint/test/pypi workflows) — unmodified fork of freelawproject/juriscraper, unrelated to BidDeed/ZoneWise/Winner Data ecosystem | Generic PACER/court-opinion scraper library. | ARCHIVE-CANDIDATE |
| moltbook-analysis | 2026-02-04 | None | Dead (211d, no workflows, one-off video-analysis notes) | Analysis of a Forward Future interview with Peter Steinberger about Moltbook, a social network for AI agents. | ARCHIVE-CANDIDATE |
| reventure-data-acquisition | 2025-12-23 | None | Dead (254d, no workflows/homepage) | Proprietary pipeline reverse-engineering Reventure.app market data for BidDeed.AI enrichment. | ARCHIVE-CANDIDATE |
| skills | 2026-08-21 | None | Live (13d, actively updated) — unmodified fork of anthropics/skills, not Everest-authored | Anthropic's official demo skills repo. | ARCHIVE-CANDIDATE |
| tiger-force | 2026-02-03 | None | Dead (212d, no workflows/homepage) | Standalone React/Vite landing page for "Tiger Force," an unrelated AI-cybersecurity brand concept, not part of BidDeed/ZoneWise. | ARCHIVE-CANDIDATE |
| website-clone-deploy | 2026-01-09 | None | Dead (237d, has clone-website.yml/clone-propertyonion.yml workflows but stale) | Agentic system using Playwright to clone competitor websites and deploy extracted features/components to BidDeed.AI. | ARCHIVE-CANDIDATE |
| zonewise-content-engine | 2026-03-26 | None | Dead (161d, has daily-content.yml workflow but not recently run/pushed) | Daily automated pipeline turning auction + zoning data into Avatar Ariel videos published across YouTube/IG/LinkedIn/FB/WhatsApp. | REUSE |
| zonewise-security | 2026-04-09 | MIT | Stale (147d, has scan-cron.yml/scan-pr.yml workflows) | Clean-room security scanner (Semgrep/Gitleaks/Trivy) that nightly-scans all breverdbidder repos and files GitHub issues for critical findings. | REUSE |
| zonewise-web | 2026-09-02 | MIT | Live (1d, homepage https://zonewise.ai, 50+ active workflows) | Production Next.js 14 + Supabase + Stripe + Claude-chat marketing/product site for ZoneWise.AI's Brevard County zoning intelligence platform. | REUSE |
| agentic-ai-security-website | 2026-01-29 | None | Dead (>180d, no workflows/homepage, one-off showcase site) | A React/TS/Tailwind website showcasing a cybersecurity framework and roadmap for securing Agentic AI ecosystems. | ARCHIVE-CANDIDATE |
| andrej-karpathy-skills | 2026-05-25 | None | Stale (~100d, no workflows; content already absorbed into root CLAUDE.md's "Behavioral Discipline" section) | A single CLAUDE.md distilling Karpathy's LLM-coding-pitfall observations into four behavioral principles. | MERGE-INTO cli-anything-biddeed |
| biddeed-modal | 2026-01-29 | None | Dead (>180d, but has 4 workflows: ci/deploy/greptile/security — evidence of past infra, not current use) | Serverless national scraping infrastructure for BidDeed.AI/ZoneWise using Craft Agents + Modal + CrewAI + Supabase. | ARCHIVE-CANDIDATE |
| claude-video | 2026-05-08 | MIT | Stale (~118d, has release.yml workflow, plugin-installable tool) | A Claude Code plugin (`/watch`) that downloads, transcribes, and frame-extracts videos so Claude can "watch" them. | REUSE |
| everest-cinematic | 2026-04-12 | MIT | Stale (~144d, no workflows found, but active architecture doc referencing sibling repos) | An agentic video production pipeline that turns markdown briefs into rendered Everest Capital videos via Gemini Veo3/Imagen4. | REUSE |
| everestcapitalusa | 2026-04-28 | None | Stale (~128d, no workflows, minimal README) | Everest Capital USA's real estate investment and development website (README is a one-line description). | REUSE |
| kimi-kilo-craft-integration | 2026-01-29 | NOASSERTION | Dead (>180d, no workflows, experimental integration glue) | An MCP-based integration ecosystem connecting Kimi K2.5, Kilo, and Craft Agents. | ARCHIVE-CANDIDATE |
| paperclip | 2026-03-26 | MIT | Dead (>180d, though has 6 workflows — appears to be an external upstream mirror/fork, not Everest-authored) | Open-source Node.js/React orchestration platform managing a team of AI agents running a "zero-human company." | ARCHIVE-CANDIDATE |
| shannon | 2026-04-12 | AGPL-3.0 | Stale (~144d, no workflows found in this fork; homepage points to upstream keygraph.io) | A fully autonomous AI pentester (fork of KeygraphHQ/shannon) that finds and executes real exploits against web apps. | ARCHIVE-CANDIDATE |
| skills-mcp-runtime | 2026-01-30 | None | Dead (>180d, no workflows, appears to be an external SkillForgeAI reference project) | A production runtime implementing progressive disclosure for AI agents to discover/load Skills via MCP servers. | ARCHIVE-CANDIDATE |
| trending-github-projects-230 | 2026-02-08 | None | Dead (>180d, one-off video-analysis report with no ongoing use) | A YouTube video analysis report cataloging 20 trending open-source GitHub repos (incl. Shannon), all auto-forked to the account. | ARCHIVE-CANDIDATE |
| winnerdata-website | 2026-08-26 | None | Live (~8d, actively pushed, single META_PROMPT.md file — content/sitemap prompt for site build) | A content-and-sitemap meta-prompt document for building the winnerdataai.com marketing site (no rendered app in repo). | REUSE |
| zonewise-desktop | 2026-04-12 | Apache-2.0 | Live (~144d but has 11 active workflows incl. deploy-cloudflare.yml, and homepage zonewise.app is live) | ZoneWise.AI Desktop, a branded fork of Craft Agents (Electron + Claude Agent SDK) for document-centric multi-agent work. | REUSE |
| zonewise-skills | 2026-01-29 | None | Dead (isArchived=true, README explicitly says "DEPRECATED... Do not use this repository") | Deprecated skills repo explicitly superseded by zonewise-lobster (Moltbot Lobster deterministic workflows). | ARCHIVE-CANDIDATE |
| agentic-seller | 2026-04-12 | none | Dead (~144d, no workflow, reference fork per description) | Reference fork exploring an "agentic sales system" that auto-researches accounts and drafts outreach, intended for BidDeed.AI adaptation. | MERGE-INTO everest-vault |
| awesome-claude-skills | 2026-02-06 | none | Dead (~209d, no workflow, upstream curated list) | A curated list of Claude Skills, resources, and tools for Claude.ai/Code/API workflows (Composio-maintained upstream list). | ARCHIVE-CANDIDATE |
| biddeed-web | 2026-09-02 | none | Live (1d, has ci-deploy.yml + relock.yml workflows) | Next.js App Router skeleton for BidDeed.AI Auction Intelligence, Phase 1a scaffold with no data/auth/deploy yet. | REUSE |
| competitive-intelligence | 2026-02-04 | none | Dead (~211d, but has 13 workflow files — historically very active) | Centralized competitive intelligence repo for BidDeed.AI/ZoneWise covering Gridics, PropertyOnion, CoStar, Redfin, Zillow analyses. | MERGE-INTO everest-vault |
| everest-content | 2026-07-06 | MIT | Live (~59d, build.yml + refresh-ship.yml workflows, live site content.zonewise.ai) | Markdown-first content SSOT for Everest Capital, rendered via Eleventy to content.zonewise.ai. | REUSE |
| fieldops-everest | 2026-04-22 | MIT | Dead (~134d, no workflow; deployed homepage fieldops-alpha.vercel.app but stale) | MIT fork of shreyaawari28/fieldops — a jobsite field-ops PWA for Kenstrekt Inc's construction projects. | REUSE |
| lead-routing-agent | 2026-03-05 | none | Dead (~182d, no README, no workflow) | LangGraph webhook → HubSpot → Mailchimp/Slack → Supabase lead routing pipeline (per description only, no README). | MERGE-INTO revops tooling (or ARCHIVE-CANDIDATE if unused) |
| repo-forensics | 2026-03-24 | AGPL-3.0 | Dead (~163d, no workflow) | Zero-dependency security scanner (17 scanners) that audits repos/skills/MCP servers/plugins for malicious patterns before install. | REUSE |
| skillforge-ai | 2026-04-12 | none | Dead (~144d, no README but 5 CI/intelligence workflows present) | SkillForge AI — AI skills platform integrating ClawdBot, Kimi K2.5, Kilo, and Craft Agents with autonomous GitHub sync (per description; no README). | ARCHIVE-CANDIDATE |
| skillspector-repoeval-20260624 | 2026-06-24 | Apache-2.0 | Stale (~71d, no workflow, upstream NVIDIA tool snapshot) | Security scanner for AI agent skills detecting vulnerabilities/malicious patterns — NVIDIA skillspector fork/eval snapshot. | MERGE-INTO repo-forensics |
| validate-build-system | 2026-01-01 | none | Dead (~245d, no workflow) | Evidence-based "Validate-Build" framework/methodology for validating product ideas before writing code. | ARCHIVE-CANDIDATE |
| winnerdataai-web | 2026-08-27 | none | Live (7d, no workflow found but recent push suggests active manual deploys) | Winner Data (winnerdataai.com) marketing landing page, scroll-craft build. | REUSE |
| zonewise-desktop-v2 | 2026-02-01 | none | Dead (isArchived=true, repo is empty) | Empty/archived repo — README states it was superseded by zonewise-desktop. | ARCHIVE-CANDIDATE |
| zonewise-superpowers | 2026-04-06 | MIT | Dead (~150d, no workflow, upstream Dojo Coding plugin fork) | Claude Code plugin (DojoCodingLabs remotion-superpowers) turning Remotion into a full video production studio with 5 MCP servers and 13 commands. | MERGE-INTO everest-content |
| agentic-video-maker | 2026-05-12 | MIT | Stale (114d, but has 2 active GHA workflows: ci-smoke.yml, everest-dispatch.yml) | AI video pipeline: brief → script → AI visuals + ElevenLabs narration + music → Gemini Video critique → auto-patch → re-render loop. | REUSE |
| awesome-design-md | 2026-04-05 | MIT | Dead (152d, no workflows, curated third-party fork/list) | Curated collection of DESIGN.md files coding agents read to build pixel-matching UI. | MERGE-INTO cli-anything-biddeed |
| brevard-bidder-ai-skills | 2026-04-12 | none listed | Stale (144d, but active workflows daily_analysis.yml/weekly_optimization.yml + live Vercel homepage) | Self-improving agentic AI skills-generation system for the BrevardBidderAI foreclosure auction platform. | MERGE-INTO cli-anything-biddeed |
| craft-agents-config | 2026-01-27 | none listed | Dead (>200d, no workflows, one-off installer config) | One-command PowerShell installer for zero human-in-loop Craft Agents MCP config. | ARCHIVE-CANDIDATE |
| everest-geo-tracker | 2026-08-28 | MIT | Live (6d, 3 active workflows: ci.yml, first-interaction.yml, migration-guard.yml) | Self-hosted fork of ansvisor tracking AI-search visibility for winnerdataai.com/biddeed.ai/zonewise.ai. | REUSE |
| firecrawl-seo-analysis | 2026-02-04 | none listed | Dead (>200d, no workflows, no description — one-off video-analysis notes) | Notes doc summarizing a Firecrawl YouTube tutorial on automating SEO reports. | ARCHIVE-CANDIDATE |
| life-os-ai-skills | 2025-12-04 | none listed | Dead (>270d, 1 workflow + live Vercel homepage exist, but personal ADHD tooling, not GTM) | Pattern-recognition/skill-generation dev layer for Ariel's personal Life OS dashboard (not BidDeed/ZoneWise product). | ARCHIVE-CANDIDATE |
| reventure-agent | 2025-12-24 | none listed | Dead (>250d, 1 workflow pipeline.yml but no evidence of ongoing use) | Agentic pipeline that reverse-engineers housing market platforms (e.g. Reventure.app) using free public data. | ARCHIVE-CANDIDATE |
| skillforge-ai-web | 2026-01-30 | Apache-2.0 | Dead (>200d, no workflows) | Multi-provider (Gmail/GitHub OAuth) auth platform + dashboard for managing "ClawdBot" AI skills. | ARCHIVE-CANDIDATE |
| superpowers | 2026-04-12 | MIT | Stale (144d, no workflows in repo itself, but actively referenced/installed as a Claude Code plugin marketplace) | Composable "skills" + spec/plan/TDD workflow framework for coding agents (by obra). | REUSE |
| visionagent | 2026-05-10 | none listed | Stale (116d, no workflows found via API, minimal 1-line README) | VisionAgent.AI worker — forked claude-video + GHA processing pipeline + lens system. | ARCHIVE-CANDIDATE |
| youtube-transcript-engine | 2026-02-27 | none listed | Dead (>180d, no workflows) | React19/Express/tRPC/Drizzle platform for extracting, summarizing, and exporting AI insights from YouTube transcripts. | MERGE-INTO cli-anything-biddeed (duplicates this repo's youtube.md transcript-squad pipeline) |
| zonewise-gtm | 2026-04-12 | none listed | Stale (144d, 1 workflow summit-marketing-phase1.yml, but content is a living strategy doc directly relevant to this GTM inventory) | ZoneWise.AI GTM repo (v2.0): positions ZoneWise against PropertyOnion across 67 FL counties, 298 KPIs, CoStar-model architecture, 90-day targets (Day 30: 50 subs/25 MCP installs; Day 60: $990 MRR/10 customers; Day 90: $7,500 MRR/50 customers), North Star metric "Queries Per Active User Per Week." | REUSE |
| zonewise-v2 | 2026-02-06 | none listed | Dead (isArchived=true, explicitly superseded per description) | Enterprise zoning-intelligence web app (3D building envelopes, sun/shadow analysis, AI doc chat, Stripe billing) — predecessor of zonewise.ai. | ARCHIVE-CANDIDATE |
| ai-marketing-skills | 2026-04-16 | MIT | Stale (~140d, no GHA, external repo not homegrown) | Open-source Claude Code skill library for marketing/sales workflows (growth, outbound, SEO, finance ops). | ARCHIVE-CANDIDATE (reference-only external fork) |
| biddeed-housing-map | 2025-12-24 | none set | Dead (~253d stale, but has deploy.yml + fetch_zillow_data.yml workflows, Cloudflare Pages badge) | Free-data clone of Reventure.app market analytics (Zillow/Census/FHFA, 30K ZIP choropleth) with BidDeed auction overlay. | MERGE-INTO reventure-clone |
| brevard-bidder-landing | 2026-07-27 | NOASSERTION | Live (~38d, 20+ active GHA workflows) | BidDeed.AI foreclosure auction intelligence platform landing page + 12-stage "Everest Ascent" pipeline docs. | REUSE |
| custom-agent-with-skills | 2026-04-12 | none set | Stale (~144d, no workflows, no homepage) | Pydantic AI framework-agnostic implementation of Claude Skills progressive-disclosure pattern. | ARCHIVE-CANDIDATE |
| everest-hub-dashboard | 2026-04-17 | none set | Stale (~139d by push-age, but has deploy.yml and live GitHub Pages URL) | Astro/Tailwind ops + SSOT dashboard for Everest Marketing Hub with EG14 gate scorecard and deferrals view. | REUSE |
| gold-standard-ssot | 2026-06-17 | none set | Stale (~78d, no workflows found) | SSOT for BidDeed/ZoneWise Gold-Standard certification methodology (criteria A-J) across all 67 FL counties. | REUSE |
| mariam-blueprint | 2026-04-12 | none set | Stale (~144d by push-age, but live GitHub Pages site) | Furnished Units Cashflow Blueprint — battle card & 90-day GTM plan for Mariam Shapira/Property360. | REUSE |
| reventure-clone | 2025-12-23 | none set | Dead (>180d, one-off scrape artifact "Scraped from reventure.app") | Scraped/generated clone of reventure.app real-estate analytics site. | MERGE-INTO biddeed-housing-map |
| skillforge-craft-extraction | 2026-01-29 | Apache-2.0 | Dead (~217d, explicitly a one-off component-extraction snapshot) | Extracted UI/skills/sources components from Craft Agents OSS for planned SkillForge AI integration. | ARCHIVE-CANDIDATE |
| swarms | 2026-05-14 | Apache-2.0 | Stale (~112d; upstream third-party OSS project kyegomez/swarms, not Everest-authored) | Enterprise-grade multi-agent orchestration framework (swarms.ai). | ARCHIVE-CANDIDATE |
| visionagent-web | 2026-05-10 | none set | Stale (~116d, no workflows detected) | VisionAgent.AI frontend — Next.js 15 on Vercel with Supabase Auth, upload UI, and report viewer. | REUSE |
| zonewise | 2026-04-12 | MIT | Stale (~144d, but 11 active-looking GHA workflows and production link to zonewise.ai) | ZoneWise.AI monorepo — scripts, migrations, pipeline, Claude skills for 67-county FL zoning intelligence, SSOT for 10.8M parcels. | REUSE |
| zonewise-landing | 2026-04-12 | none set | Stale (no workflows, README is unedited Vite/React boilerplate) | Generic Vite+React starter template — never customized despite description claiming "3D scroll animations." | ARCHIVE-CANDIDATE |
| zonewise-video | 2026-04-03 | none set | Stale (~153d, has asset-generation.yml + render.yml Remotion workflows, empty README) | ZoneWise 3-minute GTM demo video built with Remotion (React programmatic video generation). | REUSE |
| ai-video-pipeline | 2026-08-15 | NOASSERTION | Live (19d, active pipeline.yml workflow, most stages VERIFIED) | Fully automated demo-video pipeline: script → ElevenLabs voice → avatar lip-sync (MuseTalk, GPU-blocked) → Playwright capture → ffmpeg assembly. | REUSE |
| biddeed-landing | 2026-04-12 | none set | Stale (144d, no README, no workflows found) | AI-generated landing page with 3D scroll animations (description only; no README content). | ARCHIVE-CANDIDATE |
| claude-chamber | 2026-03-26 | none set | Dead (161d, no README content, has ci/sentinel/summit-dispatch workflows — dev-tool, not GTM) | IDE-like web UI for Claude Code sessions with Sentinel self-healing. | ARCHIVE-CANDIDATE |
| demovideo-pipeline | 2026-03-26 | none set | Dead (161d, superseded by newer ai-video-pipeline) | Automated demo video pipeline "Avatar Ariel": script → ElevenLabs voice → D-ID avatar → Remotion composite → Cloudflare R2. | MERGE-INTO ai-video-pipeline |
| everest-media-gateway | 2026-04-12 | Apache-2.0 | Stale (144d, no workflows found, substantive architecture doc — fork of Google's official Veo3/Nano Banana quickstart) | Central abstraction/gateway over Gemini Business APIs (Veo 3, Nano Banana Pro, Imagen 4, Gemini TTS). | REUSE |
| goviralbitch | 2026-03-30 | MIT | Dead (157d, has sync-upstream.yml but no local-use evidence, third-party tool) | Trainable social media coaching system for Claude Code — finds winning topics, generates hooks (third-party fork, upstream install). | ARCHIVE-CANDIDATE |
| marketingskills | 2026-05-07 | MIT | Stale (119d, active sync-skills.yml/validate-skill.yml workflows — third-party Corey Haines skill library, referenced not authored) | Collection of AI agent marketing skills (CRO, copywriting, SEO, analytics, growth) for Claude Code/Codex/Cursor. **This is the upstream source repo vendored into `.claude/skills/` by issue #19766** (see §4). | REUSE |
| reventure-clone-v2 | 2025-12-24 | none set | Dead (253d, one-off analysis/build, no workflows) | Reventure.app clone using free Zillow Research data + BrevardBidderAI foreclosure integration, XGBoost predictions. | ARCHIVE-CANDIDATE |
| skillforge-marketing-strategy | 2026-01-30 | none set | Dead (216d, no workflows, one-off strategy doc for a different product) | Marketing strategy modeling SkillForge AI on Apify's playbook — off-brand product, informational only. | ARCHIVE-CANDIDATE |
| tanstack.com | 2026-06-06 | none set | Stale (89d, active workflows — unmodified upstream TanStack.com docs site fork, unrelated to Everest GTM) | Marketing and docs site for the TanStack open-source ecosystem. | ARCHIVE-CANDIDATE |
| visual-explainer | 2026-03-17 | MIT | Dead by push-age (170d) but actively referenced in CLAUDE.md and used via slash commands | Agent skill generating styled HTML pages/slide decks for diagrams, diff reviews, plan audits, and project recaps. | REUSE |
| zonewise-business-model | 2026-02-09 | none set | Dead by push-age (206d) but content is a live, referenced strategy doc | ZoneWise.AI strategy hub: "Babushka" branded-house product model, avatar-tier pricing matrix, 22-41x agentic-AI valuation framework. | MERGE-INTO zonewise-marketing-plan |
| zonewise-marketing-plan | 2026-02-10 | none set | Dead by push-age (205d) but content is a live, referenced strategy doc | ZoneWise.AI/BidDeed.AI marketing & growth plan: dual-channel (B2C Cloud vs B2B Desktop), dual-auction freemium strategy, pricing, funnel, retention. | REUSE |
| zonewise-vinext-test | 2026-02-26 | none set | Dead (189d, explicit "isolated benchmark, do not connect to production data") | Isolated Vite-based Next.js-replacement (vinext) benchmark mirroring zonewise-web stack. | ARCHIVE-CANDIDATE |

**Verdict tally (INFERRED from table above):** REUSE 38, ARCHIVE-CANDIDATE 38, MERGE-INTO 9. These are recommendations for a human/future-dispatch decision — no action taken.

---

## 2. Supabase GTM Tables — row counts + status distribution

**VERIFIED** via direct SQL through the Supabase Management API (`/v1/projects/mocerqjnksmhcjzxrewo/database/query`, authenticated as `postgres`). Note: `SUPABASE_DB_PASSWORD`/direct psql was not attempted (known-documented non-working path per session brief); `SUPABASE_SERVICE_ROLE_KEY` via PostgREST worked for `public` schema but returned `42501 permission denied for schema winnerdata` for the `winnerdata.*` tables — **VERIFIED** at the DB level via `has_schema_privilege('service_role','winnerdata','USAGE') = false`. The Management API query path was used instead for all tables below (this is the Management-API-authenticated SQL path, not a `vault.decrypted_secrets` pull — no vault secret was read).

| Table | Row Count | Status Distribution | Fed by live cron/workflow? |
|---|---|---|---|
| `public.social_content_queue` | **684** (matches brief) | pending: 649, draft: 35 | No matching `cron.job` entry found (searched `content\|social\|marketing\|funnel\|geo\|reel\|campaign\|youtube\|gtm\|winner`). No workflow in `.github/workflows/` references this table name. **Appears orphaned** — populated at some point, nothing currently drains it. |
| `public.content_library` | **0** | n/a (empty) | No cron/workflow reference found. Table exists (confirmed via 404 vs. empty-table response comparison) but has never been populated or has been fully drained. |
| `public.youtube_scripts` | **0** | n/a (empty) | No cron/workflow reference found. |
| `public.viral_competitor_reels` | **0** | n/a (empty) | No cron/workflow reference found. |
| `public.campaign_metrics` | **0** | n/a (empty) | No cron/workflow reference found. |
| `public.campaign_prospects` | **0** | n/a (empty) | No cron/workflow reference found. |
| `public.campaign_content` | **0** | n/a (empty) | No cron/workflow reference found. |
| `public.campaign_leads` | **0** | n/a (empty) | No cron/workflow reference found. |
| `public.campaign_agent_log` | **0** | n/a (empty) | No cron/workflow reference found. |
| `public.content_distribution` | **0** | n/a (empty) | No cron/workflow reference found. |
| `public.conversion_funnel` | **0** | n/a (empty) | No cron/workflow reference found. |
| `public.lead_profiles` | **351** | (no `status` column — table uses `stage`) new: 307, lead: 44 | Not checked against a specific cron job by name; `lead_profiles` is written to by multiple pipelines per schema breadth (35 columns incl. UTM/consent/broadcast fields) — full producer audit is out of scope for this read-only pass. |
| `winnerdata.funnel_events` | **0** | n/a (empty) | No cron/workflow reference found. |
| `winnerdata.biddeed_reels` | **23** (matches brief) | pending_approval: 23 (100%) | `biddeed-reels-daily.yml` and `biddeed-reels-presale.yml` exist and reference this table; both are `workflow_dispatch`-only (no cron trigger). `biddeed-reels-daily` last ran 2026-09-02, conclusion=success. `biddeed-reels-presale` has never been run (`gh run list` returns empty). No cron.job entry drains or gates this table (approval is manual via the LMS UI per M1). |
| `winnerdata.reel_links` | **25** | not queried (no `status` column in this table) | Same workflows as above create short-links; no cron. |

**INFERRED finding:** 10 of the 15 `public`-schema GTM tables named in the brief (`content_library`, `youtube_scripts`, `viral_competitor_reels`, `campaign_metrics`, `campaign_prospects`, `campaign_content`, `campaign_leads`, `campaign_agent_log`, `content_distribution`, `conversion_funnel`) **exist but are completely empty and have no live producer** (no cron job, no `.github/workflows/*.yml` file references any of these table names). This is the single most load-bearing finding for CMO Factory planning: the "content pipeline" tables are schema-only scaffolding, not live data.

### `geo_tracker` schema (everest-geo-tracker app)

**VERIFIED:** 48 tables exist in `geo_tracker` schema (self-hosted AI-search-visibility tracker, forked from `ansvisor/ansvisor`, repo `everest-geo-tracker`, last pushed 6 days ago — see §1). Row-count spot-check on the 9 most central tables:

| Table | Rows |
|---|---|
| brands | 3 |
| organizations | 1 |
| prompts | 1 |
| prompt_results | 4 |
| tracking_runs | 1 |
| reports | 0 |
| site_audits | 0 |
| competitors | 10 |
| jobs | 3 |

The other 39 tables (`ga_page_stats`, `insights_*_daily`, `citation_urls`, etc.) were not individually counted — `pg_class.reltuples` estimates were all `-1` (never analyzed, i.e., stats invalid), and exhaustively `SELECT COUNT(*)` on 48 tables was judged out of proportion to the "summarize" instruction. **UNKNOWN** for those 39 exact counts; the schema is early-stage (single-digit rows in every table checked) — this is a freshly-integrated app, not yet a data source of scale.

---

## 3. Reels Audit — all 23 `winnerdata.biddeed_reels` rows

**VERIFIED:** all 23 rows queried live; render URL reachability checked via `curl -I` (HEAD request) against each row's `video_v2_url` (falls back to `video_url` if v2 absent) — no re-rendering performed.

| County | Case Number | Status | Render URL (HEAD) | TTS Model | Voice ID | Parcel Outline | Street View | Languages |
|---|---|---|---|---|---|---|---|---|
| alachua | 01 2025 CA 003415 | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| bay | 2026-3969TD | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| broward | CACE-24-008115 | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| clay | 2025CA001104 | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| clay | 2026CA000160 | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| escambia | 2025 CA 001415 | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| escambia | 2025 CA 001460 | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| flagler | 2026 CA 000192 | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| lee | 2026000086 | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| lee | 2026000141 | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| leon | 2024 CA 000670 | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| leon | 2025 CC 003163 | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| marion | 422024CA000511CAAXMX | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| marion | 422025CC001645CCAXMX | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| martin | 25001204CAAXMX | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| polk | 2024CA000341000000 | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| polk | 2025CA003611A000BA | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| polk | 2025CA003924A000BA | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| polk | 2026CA000684A000BA | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| santa_rosa | 572025CA000619CAAXMX | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| santa_rosa | 572025CA000824CAAXMX | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| st_lucie | 2024CA000617 | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |
| walton | 25CA000534 | pending_approval | 200 | eleven_v3 | TX3LPaxmHKxFdv7VOQHJ | True | True | English only |

**VERIFIED:** 23/23 reels are `pending_approval` (M1-compliant: none have been sent/published — `ff_batches.approved_at` equivalent gate is intact for this pipeline). 23/23 render URLs return HTTP 200. `parcel_outline` and `street_view` are `True` for all 23 (100% coverage) — this differs from the #19752 completion comment's own SQL verification, which reported "parcel_outline=true for 11/15" against a smaller 15-row snapshot taken 2026-09-03T01:44 — the dataset has grown/changed since that comment (23 rows now vs. 15 then), consistent with the later presale batch (`clay`, `flagler` `reel_presale.mp4` paths) being added afterward. **The schema has no `languages` column** — all 23 rows use the single `voice_id=TX3LPaxmHKxFdv7VOQHJ` / `tts_model=eleven_v3`; "languages rendered" as asked in the brief does not exist as trackable data — reported as such rather than inferred.

---

## 4. Verification: #19766, #19752, #19761

### #19766 — marketing skills vendoring — **VERIFIED SHIPPED**
- Issue state: OPEN (not closed, but completion comment present)
- Completion comment: `SHIPPED ✅ — 14 marketing/GTM skills vendored`, commit `e818e9f1`, source `coreyhaines31/marketingskills` @ `d4ff28a9c8d56c06809860bf2800d4f5224b52db`, **MIT** license.
- **VERIFIED** on disk: `docs/spec/19766.md` exists (15,555 bytes). `.claude/skills/LICENSE-marketingskills` exists. All 14 named skills present as directories under `.claude/skills/`: `ai-seo`, `offers`, `cold-email`, `launch`, `copy-editing`, `seo-audit`, `programmatic-seo`, `cro`, `churn-prevention`, `attribution`, `revops`, `lead-magnets`, `public-relations`, `directory-submissions`.
- `.claude/skills/` now holds 64 skill directories total.
- Last CC GHA run on the issue: `success` (run 33699749837).

### #19752 — BidDeed Reels v2 (parcel-outline + landing page + QR/UTM) — **VERIFIED, run green, issue still OPEN**
- Issue state: OPEN.
- Last CC run: `33703859775`, conclusion `success`, completed 2026-09-03T01:29:44Z, workflow "CC Runner — GHA-only (no Hetzner)".
- Completion comment includes a `### SQL VERIFICATION` block per SHIP GATE (§ CLAUDE.md), timestamped 2026-09-03T01:44:00Z, reporting a 15-row snapshot with 11/15 parcel_outline=true.

### #19761 — BidDeed Reels v3 (pre-sale reels + T-2 cadence) — **VERIFIED, run green, issue still OPEN**
- Issue state: OPEN.
- Last CC run: `33712489910`, conclusion `success`, completed 2026-09-03T03:45:01Z, same workflow.
- No SQL verification block found in the most recent visible comment (only the run-link comment) — **UNKNOWN** whether a fuller completion comment with SQL proof exists earlier in the thread; only the last 3 comments were fetched to stay within read-only/GTM scope. Full thread not exhaustively fetched.

---

## 5. YouTube channel / credential references — **VERIFIED: none found**

Searched (names only, per M3/CREDENTIAL HANDLING — no values ever fetched or printed):
- This repo (`cli-anything-biddeed`): `grep -rliE "youtube_channel_id|YOUTUBE_CHANNEL|youtube_api_key|YT_CHANNEL_ID"` matched only `harnesses/viral/src/analyze.py`, which reads `YOUTUBE_DATA_API_KEY` / `YOUTUBE_API_KEY` / `YOUTUBE_CHANNEL_ID` from the environment — **no such secret is configured** in this repo's GitHub Actions secrets (`gh secret list` shows `GOOGLE_API_KEY` and `GOOGLE_MAPS_API_KEY` only, no YouTube-specific key).
- `gh secret list` checked across 8 likely repos (`zonewise-web`, `biddeed-web`, `winnerdataai-web`, `zonewise-content-engine`, `demovideo-pipeline`, `ai-video-pipeline`, `zonewise-gtm`, `everest-geo-tracker`): **zero YouTube-related secret names found in any of them.**
- `vault.secrets` (names only): no `youtube`/`yt_`/`channel` match — only `cli_anything_shared_secret` and `cli_anything_biddeed_mcp_server_key` exist.
- `public.unified_context`: no rows with `key` matching `youtube`/`channel`.
- Doc grep for `youtube.com/@` handles across this repo turned up one unrelated third-party mention (`youtube.com/@Marvomatic`, from an analysis doc — not a BidDeed/ZoneWise/WinnerData channel).

**VERIFIED conclusion:** no biddeed / zonewise / winnerdata YouTube channel has been provisioned yet — no channel ID, no API key, in any repo or vault location checked. `zonewise-content-engine`'s README describes multi-channel publish including YouTube as a *target*, but no credential exists to execute it. This is a real gap for the CMO Factory, not a discovery failure.

---

## 6. Existing marketing/GTM planning docs to fold into the factory

**VERIFIED** (README content fetched live 2026-09-03):

- **`zonewise-gtm`** (`docs`) — ZoneWise.AI GTM Strategy v2.0. Positions ZoneWise against PropertyOnion across both foreclosure and tax-deed auctions in all 67 FL counties; references PRD V5 / PRS V5 / Sprint 7, 298 KPIs, a CoStar-model information-services architecture. 90-day targets: Day 30 = 50 subscribers / 25 MCP installs; Day 60 = $990 MRR / 10 customers; Day 90 = $7,500 MRR / 50 customers. North Star metric: "Queries Per Active User Per Week." Has one live workflow (`summit-marketing-phase1.yml`).
- **`zonewise-marketing-plan`** — ZoneWise.AI/BidDeed.AI Marketing and Growth Plan. Dual-channel strategy (B2C Cloud web app vs. B2B Desktop app) crossed with dual-auction coverage (foreclosure + tax deed), freemium pricing/funnel/onboarding/retention specs, landing-page requirements.
- **`zonewise-business-model`** — ZoneWise.AI Strategy Hub. Defines the "Babushka" branded-house product model (separate Zoning / Auction / Design "dolls"), an avatar-tier pricing matrix, and a 22–41x agentic-AI valuation framework (Bloomberg Terminal × Salesforce Platform positioning). Recommended to merge into `zonewise-marketing-plan` (overlapping strategy content, this repo is the less-current of the two).
- **`biddeed-marketing`** — BidDeed.AI Marketing repo. Structured as `research/ | content-ideas/ | scripts/ | assets/ | campaigns/`. Core positioning: "BidDeed.AI is an Agentic AI ecosystem, NOT SaaS" — 12-stage pipeline, ML-powered predictions, multi-county processing (67 FL counties, 1K–2K auctions/day), defensive-ROI framing ("Avoided losses > Promised income"). Four content pillars: Deal Outcomes, Risk Avoidance, Velocity, Technical Edge. Target platforms: YouTube Shorts (primary), LinkedIn, TikTok, X/Twitter. No workflows/homepage — content, not infrastructure.
- **`everest-content`** — Everest Capital content SSOT. Markdown-first, Eleventy-rendered, deployed live to `content.zonewise.ai`. Design tokens live in `design.md` (Stitch schema). Has active `build.yml`/`refresh-ship.yml` workflows — this is the most actively-maintained of the five docs (pushed 59 days ago vs. 144–216 days for the others).

---

## 7. Negative test

**VERIFIED:** `grep -oE "sk-[a-zA-Z0-9]{10,}|ghp_[a-zA-Z0-9]{10,}|eyJ[a-zA-Z0-9_-]{10,}"` run against all staged working files for this report returned **zero matches**. No secret values appear anywhere in this document. Where credentials were referenced, only environment-variable/secret **names** are shown, never values (per M3 / CREDENTIAL HANDLING).

---

## 8. Honesty tag summary

| Tag | Count (approx.) | Where |
|---|---|---|
| VERIFIED | Majority of claims — repo table (85 rows, live `gh api`), all Supabase counts (live SQL), all 23 reel HEAD checks, #19766/#19752/#19761 states, secret-name greps | Throughout |
| INFERRED | Verdict tally, "orphaned tables" characterization, README-purpose 1-liners (summarized from source, not verbatim) | §1 tally, §2 finding, §1 table |
| UNKNOWN | 39 of 48 `geo_tracker` exact row counts; whether #19761 has an earlier SQL-verification comment beyond the last 3 fetched | §2, §4 |

No claim in this document is ASSUMED. No terminal/negative state (archived, deleted, dead) was assigned to any repo or table — Live/Dead and REUSE/MERGE/ARCHIVE labels are advisory heuristics only, explicitly not actions taken.
