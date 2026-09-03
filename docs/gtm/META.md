# CMO FACTORY — META PROMPT v1.0
Everest Capital of Brevard LLC · D3 GTM department as a lights-out software factory. Scope: biddeed.ai + winnerdataai.com launch GTM (zonewise.ai inherits later). Repo home: cli-anything-biddeed/docs/gtm/.

## 0. WHAT THIS IS
A GTM system that takes a campaign intent in as a GitHub issue and ships published, measured, compliant marketing out — reels, deal pages, digests, county SEO pages, YouTube uploads, email sequences — with nobody at the keyboard, with gates that make an unread merge AND an unread publish defensible. Cole Medin's "dark factory" pattern (issue → plan → build → judge by something that didn't build it → merge → scheduled regression files its own bugs), rebuilt natively on the Everest stack. We take his mechanisms, not his code.

## 1. EXTERNAL-INPUT GATE RULING
- coleam00/ai-software-factory code: DO NOT VENDOR — no LICENSE file (all rights reserved). Patterns are not copyrightable; implement our own.
- coleam00/archon: DO NOT ADOPT — MIT but a local daemon (loop.sh tick/min, worktrees, .factory state on disk); violates GHA-ONLY mandate. Ticker = pg_cron, runner = cc-runner-ghonly.yml, state = Supabase + GitHub labels.
- His 7 code-enforced gates: ADOPT ALL (§5). Autonomy dial 0–5: ADOPT (§4). Cost warning (working harness ≈20× solo agent): ADOPT AS RULE — token metering day one, quota_gate_check on every scheduled job.

## 2. MISSION.md
Product: Winner Data = FL property-data platform layer (10.5M-parcel moat) supplying SIGNAL$ (resolved property signals) to businesses. BidDeed.ai = its auction-intelligence surface (SIGNAL$ Property Report, 18 sections). "We deliver the SIGNAL$. First."
NEVER-list (factory rejects as drift even when well argued):
1. Homeowner contact of any kind (mailers/texts/calls/ads). B2B data sales only.
2. Foreclosure-relief / save-your-home / mortgage-relief messaging in any channel.
3. Naming a buyer, owner, or bidder in any reel, page, caption, post.
4. Vendor/internal-tooling names in public media (Tracerfy, Bright Data, Apify, OpenRouter, ElevenLabs, issue numbers).
5. Insurance-shaped SIGNAL$ to anyone but Protection Partners (exclusive statewide, all lines).
6. External notification/approval channels (Telegram/Slack/SMS). Approvals in LMS + Claude chat only.
7. Unverified numbers in copy ("49,973 outcomes", "82.6% ensemble", county counts not re-queried from v_certified_counties, MRR/ARR projections as fact). Honesty V3 applies to marketing copy.
8. A second dispatcher, CRM, or content queue. Existing tables are SSOT.
9. Paid ads before one confirmed end-to-end purchase (spi_gates.test_purchase open).

## 3. ASSET INVENTORY (verified Sep 3 2026)
GitHub: 205 repos under breverdbidder. GTM-relevant for CP1 audit: zonewise-gtm, zonewise-marketing-plan, biddeed-marketing, marketingskills, ai-marketing-skills, everest-content, everest-media-gateway, everest-cinematic, agentic-video-maker, claude-video, zonewise-video, goviralbitch, reventure-clone(-v2), reventure-agent, biddeed-landing, brevard-bidder-landing, winnerdataai-web, winnerdataai-mvp, everest-geo-tracker, zonewise-landing, agentic-seller, paperclip, visual-explainer, skillforge-ai, craft-agents-config.
Supabase: 28 schemas, 1,084 public tables. Existing GTM tables (reuse): social_content_queue (684), content_library (0), youtube_scripts (0), viral_competitor_reels (0), campaign_* , content_distribution, conversion_funnel/v_conversion_funnel, v_teaser_funnel, winnerdata.funnel_events, winnerdata.biddeed_reels (23, all pending_approval), winnerdata.reel_links, geo_tracker.* (49), site.site_content, lead_profiles.
Reels engine live: #19736 v1, #19752 v2 (parcel outline, eleven_v3 voice TX3LPaxmHKxFdv7VOQHJ, ES/HE, /deal/{county}/{case}, /r/{code}, /reels), #19761 pre-sale calendar reels (smoke Sep 4). Vision = OpenRouter z-ai/glm-5.3-flash. The factory WRAPS this engine, never rewrites it.
Other live: biddeed-daily-digest.yml, weekly content cron, 67-county SEO pages, Chatwoot bot #19776, GEO tracker, growth Sprint 0 #19480, Typefully drafts-only.
NOT FOUND: "Mathis 18-year-old YouTube creator" technique analysis — needs Ariel to paste link/transcript → skill reel-edit-mathis in CP3.

## 4. AUTONOMY DIAL (doctor refuses each level without evidence)
0 workflows exist, run by hand (install here) · 1 accepted issue → branch/PR (needs MISSION ≥7 never-items + journeys) · 2 + validator writes verdict (needs holdout + builder-block proven) · 3 + merges/stages publish when gates green (needs mutation set ≥5/5, ratchet floor, kill switch tested) · 4 + triages own issues, regression files bugs (14 days at L3 clean) · 5 + writes own campaign issues (Ariel's explicit turn).
Publishing is a SEPARATE dial: external publish stays human-click until test-purchase gate closes; then auto-publish reels/pages, human-click email. Nothing ever auto-sends to a producer (M1).

## 5. GATES IN CODE
Merge = factory/merge.py reads docs/gtm/verdicts/<issue>.json, merges only on PASS && gates_green; CC never runs gh pr merge · Proof-it-ran markers GTM_RENDER_OK / GTM_PAGE_200 / GTM_COMPLIANCE_PASSED, absence = FAIL · Evidence not claim: every assertion carries observed value · Protected paths (docs/gtm/MISSION.md, harness/gtm/, .factory/gtm/holdout/, .factory/gtm/locks/) auto-reject PRs; validator reads them from main · Ratchet .factory/gtm/locks/floor.json · Stop button: .factory/gtm/STOP + label factory:halt on control issue (fails closed) + spi_gates gtm_factory_halt · Watchdog public.gtm_watchdog() pg_cron */15, 7 detectors (same-issue revalidated >3×/3h; zero merges 48h with open queue; spend >2× 7d median; 3 consecutive FAILs same journey; publish attempted with approval NULL; compliance FAIL on main; quota NO_READING) → halt + control-issue comment + /spi.

## 6. THREE FILES
docs/gtm/MISSION.md (§2) · harness/gtm/END-TO-END.md journeys (today-only): (1) third-party win D → D+1 reel pending_approval w/ parcel outline every aerial frame, Street View, eleven_v3, no names, deal page 200 with email capture; (2) /r/{code} resolves and increments reel_links.clicks; (3) daily digest renders with re-queried certified count, zero banned terms; (4) county SEO buy-CTA only on complete-coverage counties; (5) Chatwoot script present iff token set, homepages 200 · .factory/gtm/holdout/HOLDOUT.md written by validator role, builder blocked, negative test proves it.

## 7. LANES (one issue per lane)
Reels (exists) · Long-form YouTube (weekly "Auction Week in Florida", YouTube Data API v3, youtube_scripts; DeepSeek draft, Haiku t2 final) · Reel edit spec (Mathis, pending) · Distribution (captions → social_content_queue via Typefully drafts; Ollama llama3.2:3b on GHA runner, fallback GLM flash) · SEO/GEO · Email (Resend, B2B only) · CI/Sentinel (Exa + Bright Data → viral_competitor_reels; registered targets: `reventure` — 4 triggers in `docs/gtm/ci/REVENTURE_BATTLECARD.html`, monthly pricing/gate recheck intent logged 2026-09-03 per #19785, no live cron yet — see `docs/gtm/ci/REVENTURE_STEAL_LIST.md` "Registration" caveat) · Measurement (PostHog + conversion_funnel + campaign_metrics; north star = confirmed purchases; SQL only, LLM never writes the number).
Free/OSS first: Ollama (MIT), DeepSeek via OpenRouter, GLM-5.3-flash, Gemini free when 429 clears, ffmpeg, yt-dlp, Whisper. Claude API never on pipeline calls; Haiku t2 via Max OAuth only.

## 8. CHECKPOINTS
CP0 install skeleton (#19777) · CP1 read-only inventory (#19778) · CP2 first lap by hand, dial→1 · CP3 long-form YouTube + Mathis skill + YouTube OAuth · CP4 holdout + mutation set 5/5, dial→2 · CP5 ratchet + kill switch + watchdog drill, dial→3 (code merge) · CP6 publish gate after test_purchase closes · CP7 14-day L3 run, dial→4 · CP8 G-SPI keep/kill review.

## 9. METRICS
North star confirmed_purchases_30d (Stripe checkout.session.completed w/ stripe_customer_id). Leading: deal-page captures, /r/ clicks, YouTube watch-time, Chatwoot conversations, GEO score. Cost: tokens/lane/day from campaign_agent_log; hard stop at >$100/7d beyond Max. G-SPI = EV/PV, distinct from Founder D0 SPI.

## 10. STANDING MANDATES (in every CP issue body)
M1 no producer send without Ariel's LMS click · M2 protected objects read-only · M3 no vendor/internal names in public media · M4 Honesty V3 · M5 scope · M6 intent>spec>body>comments, write docs/spec/<issue>.md · M7 no person names in any public asset · M8 no publish step at dial<3.
