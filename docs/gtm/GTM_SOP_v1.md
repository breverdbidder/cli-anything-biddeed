# BidDeed.AI GTM + Operating SOP v1 — Reels-First, $10k MRR

**Owner:** Claude (AI Architect) orchestrates; Ariel decides, approves, merges. **T-0:** Tue Sep 8 2026, 21:00 ET.
**North star:** confirmed purchases (Stripe `checkout.session.completed`) → MRR. G-SPI tracks this; it is distinct from the Founder D0 SPI.
**Canon this obeys:** CMO Factory never-list (9 items), M7 (Ariel is the only nameable person), M8 (no publish at dial < 3), brand copy canon (hero stack, "For Everyone. Everywhere."), track-record rules (Lakewood/Rainsville, per-door), tier canon, no vendor/model names in public assets, no unverified numbers in copy.
**Evidence tags:** VERIFIED = observed live Sep 5 2026 · ASSUMED = planning assumption to be replaced by measurement within 7 days.

---

## 0. Baseline — where we actually are (VERIFIED Sep 5, 13:00 UTC)

| Metric | Value |
|---|---|
| MRR / paying customers | **$0 / 0**. `stripe_checkout_sessions` 12 pending, 0 completed; `subscription_events` 0 rows |
| Founder test purchase (`spi_gates.test_purchase`) | OPEN since Jul 31 — 36 days. The one gate that unlocks auto-publishing |
| Consented inbound leads | **1** (a test row). 360 `lead_profiles` rows are scraped LLC buyers / skip-trace / TAM, not inbound |
| Reels inventory (`winnerdata.biddeed_reels`) | 42 `pending_approval` (29 post-sale, 13 pre-sale), 188 `error` (disqualified: sub-$5k, sold above assessed, unknown address), **0 approved, 0 published** |
| Reel variants (`reel_variants`) | 25 built, **0 reviewed** in the LMS |
| Short links (`reel_links`) | 59 |
| YouTube | Channel BidDeed AI @biddeedai live and dressed; OAuth healthy (token_health ok Sep 4); **0 uploads**, queue empty; upload lane #19788 built, dormant |
| Social queue (`social_content_queue`) | 705 rows: 665 pending, 37 draft, 3 pending_approval, **0 published** |
| Website | biddeed.ai chat-first home live on Cloudflare (canon hero stack, SIGNAL$ Property Report, 67 county pages, 7 /answers assets, /deal + /reels in preview); parity board honest date Thu Sep 10 |
| CMO Factory | `gtm_factory_halt` OPEN since Sep 3 (watchdog `quota_no_reading`) — nothing publishes until closed |
| Hosting | 100% Cloudflare as of today (Vercel disabled itself at 12:20 UTC; both sites recovered by 13:12). Workers Free plan; R2 not enabled |
| LLM routing | Smart Router t1/t1.5 Gemini DOWN (prepay depleted); t2 Haiku (Max OAuth) healthy; OpenRouter GLM-5.3-flash is the pipeline vision/scoring model |

**Diagnosis in one line:** the factory has produced 42 reels, 25 variants, 59 links and 705 posts, and has published zero of them. The bottleneck is not production — it is the two human gates (test purchase, first approvals) and the halt. This SOP is built to open those gates Tuesday night and never let inventory pile up unpublished again.

---

## 1. The math — what $10k MRR requires

Blended ARPU **$130** (Investor $99 / Pro $199 / Pro Plus $199 mix; ASSUMED until the first 20 customers) → **77 paying customers**.

Funnel assumptions (ASSUMED; every rate gets a measured value by Sep 15 from PostHog + `v_reel_funnel`):

| Stage | Rate | Daily volume needed for 77 customers in 60 days (1.3 paid/day) |
|---|---|---|
| Short-form view → deal-page click | 1.0% | 54,000 views/day |
| Deal page → email / Deed chat capture | 15% | 540 deal-page visits/day |
| Email → free account | 40% | 81 emails/day |
| Free → paid within 30 days | 4% | 32 free signups/day |

**Reading the table honestly:** 54k views/day is not one channel with two uploads. It is the multiplication the factory already supports: 2 properties/day × 4 hook variants × 2 languages (EN + ES, PT-BR when ready) × 4 platforms (YouTube Shorts, TikTok, Instagram Reels, Facebook Reels) ≈ **64 posts/day** of distinct content, plus the non-reel channels below. Each variant carries its own `/r/{code}` so every post is measured on its own; Thompson sampling shifts volume to what converts. If the measured view→click rate is 3% instead of 1%, the required volume drops to 18k/day.

Levers ranked by leverage: (1) publish at all — 0 → 2/day is infinite improvement; (2) platforms — each added platform multiplies reach at ~zero marginal cost; (3) deal-page conversion — Street View + parcel outline + the SIGNAL$ Property Report preview is the hook, the email/Deed capture is the ask; (4) free→paid — Deed's in-chat upgrade sheet on the first gated action (exact Max Bid, plaintiff intel, zoning); (5) ARPU — Pro Plus/Projects (win-to-exit) and the credit model.

Milestones (targets, not promises): **Week 1 (Sep 8–14):** publishing live 2+/day on YouTube, funnel instrumented, first 3 paying customers. **Week 2–4 (by Oct 6):** 4 platforms live, ≥100 posts/week, 15 paying ($1.9k MRR). **Day 60 (Nov 7):** 77 paying, $10k MRR — only if measured rates hold; the Friday memo re-forecasts weekly from real rates.

---

## 2. Funnel architecture (the machine)

```
Auction record (multi_county_auctions / v_upcoming_auctions_ssot)
   └─ biddeed-reels-daily.yml (deterministic render path, workflow 348521514)
        ├─ post-sale T+1: 3rd-party wins (foreclosure + tax deed)      → phase=postsale
        └─ pre-sale  T-2: top 20 per auction date, top 5 shortlisted   → phase=presale
   └─ Reel Variant Studio (#19782): Hook Writer ×4 variant_dna → Animator → Director/QA → Analyst
        └─ bolt32 (#19779): 32.000 s, curiosity-gap title + 2 emojis, parcel outline every aerial frame,
           Street View mandatory, eleven_v3 voice TX3LPaxmHKxFdv7VOQHJ, ES/HE (+PT-BR) renders
   └─ Every variant: biddeed.ai/r/{code} → biddeed.ai/deal/{county}/{case} (email capture + QR) ; /reels/{code} player
        └─ Deal page = public teaser (address, photos, sale result / opening bid) ; premium intel gated (login/paid)
   └─ Deed (site AI) → free-forever account → first gated action → upgrade sheet → Stripe → MRR
   └─ Measurement: reel_variant_metrics · v_reel_funnel · v_variant_scoreboard · PostHog · Stripe → G-SPI daily
```

Non-reel channels feeding the same funnel: 67 `/county/{slug}` SEO pages + 67 programmatic county pages (#19821 C2), 7 `/answers/*` GEO assets (+ weekly gap→asset loop on everest-geo-tracker), daily email digest (biddeed-daily-digest.yml, Resend), founder LinkedIn (3/week, Typefully drafts in Ariel's voice), mcp.biddeed.ai in the Anthropic MCP directory (agent customers pay per execution), YouTube long-form (Remotion "Hollywood" lane, 1/week).

---

## 3. Daily production SOP (runs without Ariel)

| Time (ET) | Job | Owner | Output |
|---|---|---|---|
| 06:00 | Harvest yesterday's results (RealAuction sweep) + tomorrow's calendar | existing crons | rows in `multi_county_auctions`, `v_upcoming_auctions_ssot` |
| 06:30 | Reel candidates: best FORECLOSURE + best TAX DEED of the day (post-sale), top 20 pre-sale for T-2 | biddeed-reels-daily.yml | `biddeed_reels` pending_approval, disqualifiers applied (sub-$5k, sold above assessed, unknown address) |
| 07:30 | Variant Studio: 4 variants per shortlisted property, EN + ES (+PT-BR), each with `/r/` code + QR | #19782 agents | `reel_variants` |
| 08:30 | Director/QA verdict (critique loop) + never-list scan (no names, no vendor/model names, no unverified numbers, no relief language) | Director/QA | verdict file per variant |
| 09:00 | Publish queue built: YouTube slot A (foreclosure) + slot B (tax deed), never two variants of one property the same day; other platforms take the remaining variants | Analyst | `youtube_publish_queue` (+ per-platform queues) |
| 09:15 | **Gate** — dial < 3: waits for Ariel's LMS approve/reject (ground truth #1). Dial ≥ 3 (after test purchase + 4 clean days): auto-publish variants with a PASS verdict | LMS / dial | published or held |
| 09:30 / 15:30 | Uploads (2 slots/day minimum; 6/day YouTube quota ceiling) with caption, `/r/` link, county hashtag set | #19788 upload lane | `youtube_uploads` |
| 12:00 | Deal pages + /reels gallery refreshed for everything rendered today | Worker routes | live pages |
| 18:00 | Daily digest email (yesterday's results + tomorrow's top 3 + 1 reel) to consented list | biddeed-daily-digest.yml | Resend send |
| 23:00 | Analyst: pull YouTube Analytics + PostHog + Stripe → `v_variant_scoreboard`, Thompson allocation for tomorrow; G-SPI daily row | Analyst + CFO | `spi_daily` (G-SPI), scoreboard |
| Weekly Mon | SEO/GEO gap scan (everest-geo-tracker + GSC) → one task per gap → `/answers` drafts | content engine #19821 | drafts |
| Weekly Tue/Thu/Sat | Founder LinkedIn post drafts (Lakewood/Rainsville proof, per-door framing, courthouse story) | ghostwriter skill → Typefully drafts | Ariel taps publish |
| Weekly Fri | Friday memo: shipped vs drafted, funnel rates, MRR, CAC, kill/keep per archetype, re-forecast | CFO + Analyst | memo in chat + docs/gtm/memos/ |

Volume caps: YouTube 6/day hard (quota), start 2/day and raise by 1/day per clean week; other platforms cap 8/day each. If pending inventory exceeds 3 days of slots, production pauses (do not add agents — publish more or cut volume).

---

## 4. Agent roster — who owns what

| Agent / lane | Repo / issue | Role in GTM |
|---|---|---|
| biddeed-reels-daily (deterministic) | cli-anything-biddeed wf 348521514 | Source of truth for renders; CC agent issues are not a render path |
| bolt32 / reel-edit-bolt | #19779 | 32-second template; every reel |
| Reel Variant Studio: Hook Writer, Animator (motion-canvas/revideo), Director/QA (agentic-video-maker critique loop), Analyst (Thompson) | #19782 | 4 variants per property, verdicts, allocation |
| YouTube upload lane + Analytics fetcher | #19788 | Publishing + retention data; 6/day quota ledger |
| Hollywood (zonewise-superpowers, Remotion Free License, 7 agents) + everest-cinematic + everest-media-gateway | #19787 | Long-form YouTube (1/week: "how the courthouse auction works", county spotlights), branded one-offs. Never the daily reels (those stay MIT stack) |
| Content engine CP-C0/C1/C2 | #19821 | County pages, /answers assets, newsletter body |
| GTM-CMO Pro Plus/Projects content | #20011 | Pricing card, upgrade sheet, Plans copy |
| Founder Ghostwriter skill | .claude/skills (founder-ghostwriter) | LinkedIn in Ariel's voice; Typefully drafts only |
| Deed (site AI) + Projects + Skills | biddeed-web + Worker | Conversion surface; upgrade sheet on first gated action |
| CFO agent (finance.*, Stripe Sync Engine, LLM cost monitor) | everest-cfo-agent | MRR, ARPU, CAC, vendor spend, G-SPI money columns, Friday memo numbers |
| Smart Router | claude-router edge fn | All pipeline LLM calls (OpenRouter GLM / DeepSeek first; Haiku OAuth last resort; never Anthropic API) |
| PostHog | connected | Funnel events: reel_view → deal_view → email_capture → signup → checkout_started → purchased |
| Watchdog + kill switch | spi_gates.gtm_factory_halt, label factory:halt | Fail-closed stop; Ariel's button |

---

## 5. Gates and the autonomy dial (what unlocks when)

| Dial | State | Unlock condition |
|---|---|---|
| 0–2 (now) | Produce everything, publish nothing; Ariel approves in LMS | — |
| **3** | Auto-publish PASS-verdict variants to YouTube/FB/IG/TikTok within caps | `spi_gates.test_purchase` closed (Ariel's real-card purchase verified in `subscription_events`) **and** `gtm_factory_halt` closed **and** 4 consecutive clean days of Director/QA verdicts with zero never-list hits |
| 4 | Auto-publish long-form YouTube + newsletter sends | 14 days at dial 3 with zero rollbacks |
| 5 | Paid ads test (never before one confirmed purchase; budget = 20% of net subscription revenue, Ariel's $3k bootstrap cap) | ≥5 paying customers and measured CAC < 3× ARPU |

Forever human-click: producer sends (Winner Data), anything with a legal/financial claim, anything naming a person other than Ariel.

---

## 6. Website conversion SOP (the sticky site earns the click)

Deal page (`/deal/{county}/{case}`): hero = Street View + aerial with parcel outline; the number that hooked the reel repeated in words; sale result or opening bid + assessed; **one ask**: "Get the SIGNAL$ Property Report for this property" → email or Deed chat; QR/short-link parity with the reel end card. Gated tiles (blurred Max Bid range, plaintiff intel, zoning) show what paying unlocks — never invent a number to fill a blurred tile.

Home (`/`): Deed composer answers the reel's question in one turn ("what did 14470 SE 91st Ter sell for?"), surfaces the county's next auction, and offers the free account. First gated action (exact Shapira Max Bid, plaintiff max bid, lien stack, zoning) opens the upgrade sheet — Claude.ai upgrade pattern, tier pills, no vendor names.

Sticky layers S1–S5 (docs/gtm/CTA_AND_STICKY_SPEC.md) applied to Projects: every visitor sees Projects in both sidebars; a basic project works from Investor; win-to-exit tabs are Pro Plus.

Pricing surface stays the live canon (Free forever · Investor $99 · Pro $199 · Pro Plus $199/3 seats) until Ariel reviews the pricing card; the credit-based billing pivot runs as a product track and does not block launch.

Measurement contract: every CTA fires a PostHog event with `reel_code`, `variant_id`, `county`, `sale_type`; Stripe metadata carries `first_reel_code` so revenue attributes back to the variant that started it.

---

## 7. Channel matrix

| Channel | Status Sep 5 | Launch action |
|---|---|---|
| YouTube Shorts @biddeedai | Live, OAuth healthy, 0 uploads | Slot A + B daily from Tue night |
| YouTube long-form | Channel ready | 1/week from week 2 (Hollywood lane) |
| TikTok, Instagram Reels, Facebook Reels | Accounts/OAuth UNKNOWN — GTM-0 inventories | One 15-minute credential session for Ariel with a runbook (like the YouTube one); until then variants go to YouTube only |
| X / LinkedIn (founder) | Typefully drafts-only decided Aug 22; typefully_api_key pending in vault | 3 drafts/week; Ariel taps publish from phone |
| Email (Resend) | Daily digest workflow live; 1 consented contact | Deal-page captures grow the list; digest carries one reel |
| SEO: 67 county pages + programmatic county pages + /answers | 67 live, 7 assets live, C2 pending | Weekly gap→asset loop |
| MCP directory (ai.biddeed/biddeed-mcp) | mcp.biddeed.ai live on Cloudflare, 25 tools | Fix registry count (36→25), refresh listing copy; agents are customers too |
| BiggerPockets / forums | Human only | Ariel posts when he wants; URL logged |
| Paid ads | Never before first confirmed purchase | Dial 5 |

---

## 8. Measurement — G-SPI daily (real re-queried numbers only)

Daily row: uploads (by platform), views, view→click, deal visits, captures, signups, checkouts started, **purchases**, MRR, ARPU, best/worst variant archetype, never-list hits, quota used, LLM spend, ElevenLabs/Maps spend. Source of truth: `youtube_uploads`, `reel_variant_metrics`, `v_reel_funnel`, PostHog, `stripe.*` (Sync Engine), `finance.*`.

Kill/keep: an archetype with ≥2,000 views and view→click < 0.3% is retired for that county/sale-type; a variant_dna with click > 2% gets 2× allocation next day (Thompson). Any never-list hit halts the lane (label factory:halt) until reviewed.

---

## 9. Compliance never-list (unchanged, in every issue body)

No homeowner contact · no foreclosure-relief messaging · no person names except Ariel (M7) · no vendor/model names in public media · insurance SIGNAL$ exclusive to Protection Partners · no external notification channels (LMS + chat only) · no unverified numbers in copy · no second dispatcher/CRM/queue · no paid ads before one confirmed purchase · no publish at dial < 3 (M8). Public copy states these are US county foreclosure and tax deed auctions; "For Everyone. Everywhere."

---

## 10. Budget (monthly)

$0 hosting (Cloudflare) · ElevenLabs Creator $22 · OpenRouter ≤ $30 · Google Maps ≤ $20 (alert set) · Resend free tier · PostHog free tier · **Decisions for Ariel, not blockers:** Workers Paid $5 (PDF reliability on mcp), R2 (free tier; enables ISR cache), Gemini prepay top-up (restores t1/t1.5 so Deed chat is not 100% on Max quota). Anthropic API: never on pipeline calls.

---

## 11. Launch-night runbook — Tue Sep 8 (Ariel: ~25 minutes total)

**Two T-0s, not one (reconciled Sun Sep 6):** the platform launch per Ariel's CTO Replacement OS brief is **Tue Sep 8 00:01 ET** (site, MCP, billing, rate limits, status page — owned by the launch-readiness lanes #20035–#20041, gate Mon Sep 7 21:00 ET: restarts/hr ≤1, 429s observed, Workers plan decided, FF Access on/deferred, status green). The **content T-0 is Tue Sep 8 21:00 ET** ("starting Tuesday night") — the runbook below. Nothing in this section publishes before the platform gate passes.

**State Sun Sep 6 13:00 UTC (VERIFIED):** 18/18 launch-pick reels have live deal pages + short links; 20/20 EN variants qa_pass; 0 finals rendered (ElevenLabs 0 credits — decision: kokoro as final $0 vs. top-up); 13 reels still need variants (OpenRouter weekly cap — decision: raise limit); `youtube_publish_queue` = 0 until finals exist AND Ariel approves in LMS `/reels`; `test_purchase` + `gtm_factory_halt` open; 13 pending / 0 paid checkouts; LMS `/connections` live, no social credentials yet (setup page pending).

| ET | Step | Who | Evidence |
|---|---|---|---|
| Sat–Mon | GTM-0…5 (#20029–#20034, #20040) landed: LMS /reels + /connections, 18 deal pages live, 20 EN variants QA-clean, digest consent-gated, G-SPI + CFO views, platform runbook. Still open before 21:00 Tue: finals (voice decision) and variants for 13 reels (OpenRouter limit) | factory | docs/spec/2002x–20040.md |
| 21:00 | **Test purchase** — Investor $99 on biddeed.ai with a real card (or the $25 report) | Ariel | `stripe_customer_id` set, `subscription_events` row, entitlement live → `spi_gates.test_purchase` closed by chat; refund after proof |
| 21:10 | Approve the first 14 reels/variants in the LMS (or reply "auto" — chat then sets dial 3 and closes `gtm_factory_halt`) | Ariel | `reel_variant_review` rows |
| 21:15 | Slot A + Slot B publish to YouTube (public), deal pages + short links verified, first digest queued | upload lane | `youtube_uploads` 2 rows, live URLs in chat |
| 21:30 | Founder LinkedIn post #1 ("The best prices in US real estate are set at foreclosure and tax deed auctions…" + today's reel) | Ariel taps Typefully | link |
| Wed 09:00 | First G-SPI row: views, clicks, captures; Thompson allocation for day 2 | Analyst | `spi_daily` |
| Fri 18:00 | Friday memo #1 with measured rates replacing every ASSUMED value above | CFO + Analyst | memo |

Optional same night, one-time credentials: TikTok/Instagram/Facebook business accounts + OAuth (runbook provided), Typefully API key to vault, Workers Paid, R2.

---

## 12. Ariel's role (and nothing else)

Approve/reject in the LMS (until dial 3), merge PRs in stated order, tap publish on LinkedIn, the test purchase, platform credentials once, spend decisions ($5 Workers Paid, Gemini top-up), and the Friday memo read. Everything else is automated or Claude's.

---

## 13. Risks and fallbacks

| Risk | Fallback |
|---|---|
| Claude Max weekly quota freeze halts cc-runner | Deterministic workflows (reels-daily, upload lane, digest) keep running — they do not use Claude; agents resume after the window |
| Workers Free 10 ms CPU fails PDF or heavy SSR | JSON/tools unaffected; PDF via Modal endpoint fallback; Ariel's $5 decision |
| Gemini t1/t1.5 down → Deed chat on Max OAuth only | Wire OpenRouter GLM/DeepSeek tiers into claude-router (key in vault) |
| YouTube quota (6/day) or strikes | Cap 2→6 gradually; never two variants of one property/day; Director/QA never-list gate |
| Vercel dispute fallout | Already off Vercel; #20027 pauses projects and builds the evidence pack |
| Pricing pivot (credits) mid-launch | Launch on live tiers; credits ship behind a flag after 20 customers of data |
| Inventory piles up unpublished (the current failure) | Dial 3 after test purchase; volume cap rule §3; "no new agents" rule |
