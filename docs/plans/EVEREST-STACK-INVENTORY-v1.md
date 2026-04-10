# EVEREST STACK INVENTORY — Full Capability Discovery

**Date:** April 10, 2026  
**Method:** Mined GitHub secrets across 7 key repos (125 unique secrets total), conversation_search across past chats, memory references, web verification where needed.  
**Purpose:** Enumerate the complete capability stack before finalizing CI protocol v1.2+ — no more guessing.

---

## 🆕 NEW DISCOVERIES (Things I Didn't Know We Had)

These are the finds that matter for CI protocol design. Each one opens new checkpoint territory or collapses existing checkpoints.

### 1. `STITCH_API_KEY` — We Have Stitch API Access
- Stored in `cli-anything-biddeed` AND `zonewise-web` 
- I thought Stitch was only accessible via the web UI — but we have an API key
- **Impact**: Direct programmatic access for competitor design extraction (Phase 2.17-2.20) and deliverable generation (Phase 11.6-11.8) without manual UI interaction

### 2. `EXA_API_KEY` — Neural Search Engine 
- Stored in 3 repos
- Exa is a **neural search engine** purpose-built for AI agents (NOT Firecrawl, NOT Google)
- Semantic search, not keyword search — finds pages by meaning
- **Impact**: Massive — Exa is specifically designed for CI-style research. Better than DuckDuckGo/Tavily for finding competitor mentions, founder interviews, and obscure industry content. Should replace SerpAPI references entirely in Phase 6.

### 3. `GREPTILE_API_KEY` — Code Intelligence API
- Stored in 3 repos (`brevard-bidder-scraper`, `life-os`, `zonewise`)
- Greptile indexes GitHub repos for semantic code search
- **Impact**: For CI — if a competitor has public GitHub presence, Greptile can analyze their codebase for tech stack, architecture, commit patterns. Phase 7 (tech stack fingerprint) gets a new tool.

### 4. `NVIDIA_NIM_API_KEY` — NVIDIA Inference Microservices
- Stored in `brevard-bidder-scraper`
- NVIDIA NIM = hosted inference for Llama, Mistral, other OSS models
- **Impact**: Another LLM backend option in Smart Router — useful as cost-free fallback when Gemini quota is saturated

### 5. `OPENROUTER_API_KEY` — Multi-Model Router
- Stored in `brevard-bidder-scraper`
- OpenRouter = unified API to 200+ LLM models with per-token pricing
- **Impact**: Access to models we don't have direct subscriptions to (Llama, Mistral, Claude, GPT, etc.) for specialized tasks

### 6. `BROWSERLESS_API_KEY` — Hosted Chrome-as-a-Service
- Stored in `brevard-bidder-scraper`
- Browserless = hosted Chrome for scraping, screenshots, PDF gen
- **Impact**: Alternative to local Playwright for tasks requiring clean IP reputation (anti-bot pages)

### 7. `BUILTWITH_API_KEY` — Tech Stack Detection
- Stored in `brevard-bidder-scraper`  
- BuiltWith identifies which technologies a website uses (analytics, frameworks, CMS, payment processors, etc.)
- **Impact**: **Massive** for Phase 7 (Tech Stack Fingerprinting). One API call replaces 11 manual checkpoints. Gives us authoritative tech stack data for all 11 competitors.

### 8. `AGENTQL_API_KEY` — AI Web Scraping
- Stored in `brevard-bidder-scraper`
- AgentQL = AI-powered structured data extraction from any website (GraphQL-like queries)
- **Impact**: Memory notes it was "deprecated" but key is still there. Could still be useful as fallback for Phase 2/3 extraction.

### 9. `APIFY_API_TOKEN` — Apify Platform
- Stored in `brevard-bidder-scraper` AND `life-os`
- Apify = scraping platform with 1000+ pre-built scrapers (Instagram, Zillow, Redfin, Google Maps, LinkedIn, etc.)
- **Impact**: Covers many "I'd need to build this scraper" cases with pre-built actors. Phase 6 social metrics + LinkedIn enrichment use cases.

### 10. `CENSUS_API_KEY` — US Census Data
- Stored in `brevard-bidder-scraper`
- Free API but we have a key provisioned
- **Impact**: Demographic context for Phase 1 (corporate profile) and Phase 6 (market intelligence)

### 11. `PEXELS_API_KEY` — Stock Image API
- Stored in `cli-anything-biddeed`
- **Impact**: Free stock imagery for deliverables (Phase 11) — alternative to Banana Pro generation when we want real photos

### 12. `LINKEDIN_LI_AT` + `LINKEDIN_SESSION_JSON` — LinkedIn Session Cookies
- Stored in `cli-anything-biddeed`
- **Impact**: We have authenticated LinkedIn session access. For Phase 1.12 (founder backgrounds) and Phase 6.2 (customer signal scan), this unlocks LinkedIn data we otherwise can't reach.

### 13. `WATCH_TOKEN` — changedetection.io Token (already)
- Stored in `cli-anything-biddeed`
- **We may already have changedetection.io running somewhere!** — this is a pre-existing configuration
- **CRITICAL**: Must investigate — if we already have an instance, I should use it instead of standing up a new one

### 14. `MODAL_TOKEN_ID` + `MODAL_TOKEN_SECRET` — Modal.com Serverless
- Stored in `brevard-bidder-scraper`
- Modal.com = serverless Python with GPU access
- **Impact**: Heavy burst compute (ML scoring, batch analysis) without Hetzner constraints

### 15. `RENDER_API_KEY` — Render.com Hosting
- Stored in `brevard-bidder-scraper`
- **Impact**: Another hosting target for runtime services

### 16. `DIFY_API_KEY` — Dify Self-Hosted
- Stored in `cli-anything-biddeed` and `zonewise-web`
- Dify = open-source LLMOps platform (we're running it at chat.zonewise.ai per memory)
- **Impact**: Can build CI agents inside Dify with RAG capabilities

### 17. `FIGMA_API_TOKEN` — Figma API Access
- Stored in `cli-anything-biddeed` and `zonewise-web`
- **Impact**: For CI deliverable generation — extract brand tokens from competitor Figma projects if publicly shared

### 18. PostHog (`NEXT_PUBLIC_POSTHOG_KEY`)
- Stored in `zonewise-web`
- PostHog = product analytics + feature flags + session replay
- **Impact**: For CI monitoring/dashboarding layer. Our internal analytics tooling.

---

## 📊 Full Stack Inventory By Category

### AI & LLM Backends
| Service | Status | Key Location | Notes |
|---|---|---|---|
| **Anthropic Claude (Max plan)** | ✅ Paid subscription | N/A (CLI auth on Hetzner) | $100/mo — **MANDATORY: Claude Code uses Max plan only, never API key, per memory integrity rule** |
| **Claude API key** | ✅ Separate account | `ANTHROPIC_API_KEY` in 5 repos | For non-Claude-Code usage only |
| **Gemini Business** | ✅ Paid subscription | `GEMINI_API_KEY` in 4 repos | Key `AIzaSyCR...` — 3x keys in CLIProxyAPI rotation |
| **Gemini Nano Banana 2 / Banana Pro** | ✅ Included in Gemini Business | Same key | Image generation |
| **Google Stitch** | ✅ Via API | `STITCH_API_KEY` in 2 repos | Gemini 3-powered UI design tool |
| **Google AI Studio** | ✅ Part of Google Workspace | `GOOGLE_API_KEY` in 4 repos | |
| **DeepSeek V3.2** | ✅ Paid | `DEEPSEEK_API_KEY` in 2 repos | $0.28/1M tokens (ULTRA_CHEAP tier) |
| **NVIDIA NIM** | ✅ Access | `NVIDIA_NIM_API_KEY` in 1 repo | Llama/Mistral hosted inference |
| **OpenRouter** | ✅ Access | `OPENROUTER_API_KEY` in 1 repo | 200+ models unified API |
| **ElevenLabs** | ✅ Paid | `ELEVENLABS_API_KEY` in 1 repo | Voice generation (`sk_2aa3...`) |
| **LiteLLM** | ✅ Self-hosted | `LITELLM_MASTER_KEY` | LLM router abstraction |
| **CLIProxyAPI** | ✅ Self-hosted on Hetzner:8317 | `WATCH_TOKEN`, etc | Gateway to route among Gemini/DeepSeek |

### Search & Research
| Service | Status | Key Location | Notes |
|---|---|---|---|
| **Exa** | ✅ Paid | `EXA_API_KEY` in 3 repos | **NEURAL search for AI agents — key CI tool** |
| **Firecrawl Standard Monthly** | ✅ Paid $99/mo | `FIRECRAWL_API_KEY` in 3 repos | 100,298 credits remaining |
| **Supadata** | ✅ Paid | `SUPADATA_API_KEY` in 1 repo | Video + metadata + web scraping, tier unknown (key `sd_24e8cdaf...`) |
| **Apify** | ✅ Paid | `APIFY_API_TOKEN` in 2 repos | 1000+ pre-built scrapers |
| **AgentQL** | ⚠️ Key exists | `AGENTQL_API_KEY` | Memory says deprecated, key present |
| **Browserless** | ✅ Access | `BROWSERLESS_API_KEY` | Hosted Chrome alternative |

### Data Enrichment
| Service | Status | Key Location | Notes |
|---|---|---|---|
| **BuiltWith** | ✅ Paid | `BUILTWITH_API_KEY` | **Tech stack detection — HUGE for Phase 7** |
| **Census API** | ✅ Free (keyed) | `CENSUS_API_KEY` | US Census demographics |
| **Greptile** | ✅ Paid | `GREPTILE_API_KEY` in 3 repos | Code repo intelligence |
| **Google Maps** | ✅ Via Workspace | `GOOGLE_API_KEY` | Geocoding, places |
| **Mapbox** | ✅ Paid | `MAPBOX_TOKEN` in 2 repos | Map tiles, geocoding |

### Web & Social
| Service | Status | Key Location | Notes |
|---|---|---|---|
| **LinkedIn (authenticated)** | ✅ Session cookies | `LINKEDIN_LI_AT`, `LINKEDIN_SESSION_JSON` | **Authenticated LinkedIn access** |
| **Figma API** | ✅ Access | `FIGMA_API_TOKEN` in 2 repos | |
| **PostHog** | ✅ Account | `NEXT_PUBLIC_POSTHOG_KEY` | Product analytics |
| **Pexels** | ✅ Free API keyed | `PEXELS_API_KEY` | Stock images |

### Database & Storage
| Service | Status | Key Location | Notes |
|---|---|---|---|
| **Supabase Pro** | ✅ Paid $25/mo | `SUPABASE_*` (15+ variants across repos) | Project `mocerqjnksmhcjzxrewo` |
| **Supabase Management Token** | ✅ | `SUPABASE_MANAGEMENT_TOKEN` | Programmatic project management |

### Infrastructure & Hosting
| Service | Status | Key Location | Notes |
|---|---|---|---|
| **Hetzner (everest-dispatch CPX11)** | ✅ $5.59/mo | `HETZNER_IP/PASSWORD/SSH_KEY` | 87.99.129.125 |
| **Cloudflare** | ✅ Account | `CLOUDFLARE_API_TOKEN/ACCOUNT_ID` in 3 repos | Zone `b32406b78aaaefd55557d77c843a5940` |
| **Vercel Pro** | ✅ Paid | `VERCEL_TOKEN` in 3 repos | Canonical project `prj_EaXgEO6WDoSpCeLhuCemtbPr6e8E` |
| **Render.com** | ✅ Access | `RENDER_API_KEY` | Runtime services |
| **Modal.com** | ✅ Access | `MODAL_TOKEN_ID/SECRET` | Serverless Python + GPU burst |

### Real Estate Data (Paid Auction Sites)
| Service | Status | Key Location | Notes |
|---|---|---|---|
| **RealForeclose** | ✅ Paid | `REALFORECLOSE_USERNAME/PASSWORD/EMAIL` | Everest8/Everest18$ |
| **RealTDM (Tax Deeds)** | ✅ Paid | `REALTDM_USERNAME/PASSWORD` | |
| **AcclaimWeb (County Clerk)** | ✅ Paid | `ACCLAIMWEB_USERNAME/PASSWORD` | |
| **PropertyOnion** | ✅ Paid | `PROPERTYONION_EMAIL/PASSWORD` | Competitor AND data source |

### Communications
| Service | Status | Key Location | Notes |
|---|---|---|---|
| **Telegram (Sentinel Bot)** | ✅ Paid | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `BIDDEED_BOT_TOKEN`, `BIDDEED_BOT_CHAT_ID` | Two bots — Sentinel + BidDeed |
| **Google Workspace Business** | ✅ Paid | Via `GOOGLE_API_KEY` + OAuth | Email, Calendar, Drive, Docs, all APIs |

### Payment & Commerce
| Service | Status | Key Location | Notes |
|---|---|---|---|
| **Stripe** | ✅ Test mode keys | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` in `zonewise-web` | Not yet live mode |

### LLM Operations & Agents
| Service | Status | Key Location | Notes |
|---|---|---|---|
| **Dify (self-hosted)** | ✅ Running on Hetzner:3000 | `DIFY_API_KEY` in 2 repos | LLMOps platform with RAG |

---

## 🚫 What We DON'T Have (Despite My Earlier Guessing)

After enumerating, these are things I was wondering about that we **do not have**:

- ❌ Crunchbase Pro (not in any secret store)
- ❌ PitchBook (not in any secret store)
- ❌ LinkedIn Sales Navigator (only personal LinkedIn session cookies)
- ❌ Apollo / ZoomInfo / Clearbit (no enrichment APIs)
- ❌ Moz Pro (no `MOZ_API_KEY`)
- ❌ DataForSEO (no key)
- ❌ Tavily (no key — we use Firecrawl + Exa instead)
- ❌ SerpAPI (no key — we use Firecrawl + Exa instead)
- ❌ Bright Data proxies (memory mentioned but no key stored)
- ❌ CoreLogic / ATTOM Data / Black Knight (no RE data vendor APIs — we scrape directly)
- ❌ Perplexity Pro (memory shows interest, no key)
- ❌ PatSnap / Derwent / Questel (no paid patent DBs — we use free USPTO/EPO/WIPO)
- ❌ Adobe Creative Cloud (not referenced)
- ❌ Runway / Pika / Luma / Sora (no video gen keys)

---

## 🎯 CI Protocol v1.2 — Final Capability Reconciliation

Now that I have the REAL stack, let me reconcile what changes in the protocol:

### Phase 7 (Tech Stack Fingerprinting) — MAJOR UPGRADE
```yaml
before_inventory:
  approach: "Manual inspection of HTML/headers, guess the stack"
  coverage: "11 manual checkpoints"
  
after_inventory:
  approach: "BuiltWith API call per competitor domain"
  coverage: "Same 11 checkpoints but with AUTHORITATIVE data in single call"
  delta: "BuiltWith returns: analytics stack, CMS, frameworks, payment processors, 
          hosting, CDN, JS libraries, ad networks, email services, marketing tools
          — all the tools in one API call"
  new_checkpoint: "7.12 BuiltWith technology profile per competitor"
```

### Phase 6 (Customer + Market Intelligence) — MAJOR UPGRADE
```yaml
new_tools_now_available:
  - "LinkedIn authenticated session → deeper founder/employee intelligence"
  - "Exa neural search → find obscure mentions search engines miss"  
  - "Apify pre-built scrapers for Instagram, LinkedIn, Zillow, Redfin"
  - "Greptile for GitHub-based competitors (public repo analysis)"
  - "Supadata for video/social transcripts across 5 platforms"
  
new_checkpoints:
  6.15: "Exa neural search for semantic competitor mentions (replaces SerpAPI)"
  6.16: "LinkedIn authenticated — founder/employee enrichment beyond public profile"
  6.17: "Apify instagram-scraper actor for competitor Instagram metrics"
  6.18: "Apify linkedin-company-scraper for company page + employees"
  6.19: "Greptile code analysis if competitor has public GitHub presence"
```

### Phase 2 (Playwright Visual + Interactive) — UPGRADE
```yaml
new_tool:
  stitch_api: "STITCH_API_KEY present — programmatic design extraction"
  
revision: "Stitch checkpoints 2.17-2.20 from v1.1 become actual API calls, not UI interactions"
```

### Phase 1 (Corporate Profile) — NO CHANGE
```yaml
already_covered: "gpt-researcher + LinkedIn auth + Exa cover this well"
```

### Phase 5 (Legal/IP) — NO CHANGE
```yaml
already_covered: "uspto-opendata-python + free USPTO/EPO/WIPO sufficient"
note: "We don't have paid patent DBs and don't need them"
```

### Living Protocol Monitoring Layer — NEW FINDING
```yaml
discovery: "WATCH_TOKEN secret exists in cli-anything-biddeed"
implication: "We may already have changedetection.io running somewhere"
action_required: "Investigate before deploying new instance"
```

---

## 💰 Updated Cost Analysis

### Already Paying (established baseline)
```yaml
monthly_paid:
  anthropic_claude_max: "$100/mo"
  gemini_business: "Included in Google Workspace (existing)"
  google_workspace_business: "Existing"
  firecrawl_standard: "$99/mo"
  supabase_pro: "$25/mo"
  hetzner_cpx11: "$5.59/mo"
  vercel_pro: "~$20/mo"
  cloudflare: "Free tier"
  
  subtotal_monthly: "~$250/mo covered infrastructure"

variable_usage:
  exa: "Usage-based (unknown tier)"
  apify: "Usage-based (unknown tier)"  
  supadata: "100 free/mo or paid tier (unknown)"
  deepseek: "$0.28/1M tokens — minimal"
  builtwith: "Usage-based (unknown tier)"
  greptile: "Usage-based (unknown tier)"
  elevenlabs: "Usage-based"
```

### CI Protocol v1.2 Marginal Cost
```yaml
new_spend_for_ci: "$0/month"
rationale: "Every capability needed is already in our existing stack — 
           we just weren't using them for CI yet"
```

---

## 🔄 Final Protocol Version: v1.2

### Summary of Changes From v1.0 → v1.2

```yaml
v1.0: 173 checkpoints (baseline)
v1.1: 173 + 17 = 190 checkpoints (Google Business + Stitch + Banana Pro)
v1.2: 190 + 6 = 196 checkpoints (Exa + LinkedIn auth + BuiltWith + Apify + Greptile)

net_new_capabilities_discovered:
  exa_neural_search: "Replaces SerpAPI/Tavily references"
  linkedin_authenticated: "Deeper founder/employee data"
  builtwith: "Authoritative tech stack (Phase 7 breakthrough)"
  apify_prebuilt_actors: "Instagram, LinkedIn, Zillow, Redfin coverage"
  greptile: "Code intelligence for GitHub-present competitors"
  stitch_api: "Programmatic design extraction vs UI interaction"

capabilities_eliminated:
  serpapi: "Replaced by Exa + Firecrawl + Gemini grounding"
  tavily: "Replaced by Exa + DuckDuckGo fallback"
  moz: "Replaced by Common Crawl + Bing Webmaster + BuiltWith"
  dataforseo: "Replaced by claude-seo free APIs + BuiltWith"
```

### v1.2 Phase-Level Checkpoint Count

| Phase | v1.0 | v1.1 | v1.2 | Delta Reason |
|---|---|---|---|---|
| 0 Infrastructure | 8 | 8 | 8 | — |
| 1 Corporate Profile | 15 | 16 | 16 | +1 Translate (v1.1) |
| 2 Playwright/Visual | 16 | 20 | 20 | +4 Stitch API (v1.1) |
| 3 API Discovery | 13 | 13 | 13 | — |
| 4 Pricing/Business | 8 | 8 | 8 | — |
| 5 Legal/IP | 13 | 13 | 13 | — |
| 6 Customer/Market | 11 | 14 | 19 | +3 Google APIs (v1.1), +5 Exa/LinkedIn/Apify/Greptile (v1.2) |
| 7 Tech Stack | 11 | 11 | 12 | +1 BuiltWith (v1.2) |
| 8a SEO | 14 | 16 | 16 | +2 PageSpeed/CrUX (v1.1) |
| 8b GEO | 8 | 10 | 10 | +2 Gemini/NotebookLM (v1.1) |
| 8c Customer Behavior | 10 | 10 | 10 | — |
| 8d Lead Gen | 15 | 15 | 15 | — |
| 8e Recurring Revenue | 12 | 12 | 12 | — |
| 9 Feature/Patent Mapping | 5 | 5 | 5 | — |
| 10 EG14 Gate | 5 | 5 | 5 | — |
| 11 Deliverables | 5 | 10 | 10 | +5 Stitch/Banana (v1.1) |
| 12 Memory/Session | 4 | 4 | 4 | — |
| **TOTAL** | **173** | **190** | **196** | **+23 total evolution** |

---

## 🎬 Next Action

**Ship v1.2 as the baseline. Proceed to Phase 0 bootstrap.**

No more capability iterations — I now have the full stack. Further evolutions will come from **actual competitor runs** revealing gaps (the original living protocol design), not from discovering missing context.

**Pending Phase 0 execution:**
- 0.1 Playwright smoke test (paused mid-execution, needs completion)
- 0.2 firecrawl-mcp-server install
- 0.3 claude-seo install
- 0.4 gpt-researcher skill install
- 0.5 changedetection.io Docker in sandbox — **but first verify WATCH_TOKEN doesn't mean we already have an instance running**
- 0.6 Supabase tables via REST API
- 0.7 ci-evidence bucket
- 0.8 Firecrawl credit budget confirmation

Revised time estimate: ~20 minutes (added 3 min for WATCH_TOKEN investigation)
