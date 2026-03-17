# API/MCP Security & Value Assessment: Firecrawl CLI + Agent Skill

**Assessment Date:** March 16, 2026
**Assessor:** Claude AI Architect
**Assessment Version:** 1.0
**Status:** ADOPT (Score: 87/100)

---

## 1. Executive Summary

| Category | Score | Weight | Weighted |
|----------|-------|--------|----------|
| Security | 82/100 | 35% | 28.7 |
| Value Add | 92/100 | 30% | 27.6 |
| Integration Fit | 90/100 | 20% | 18.0 |
| Maintenance/Support | 85/100 | 15% | 12.8 |
| **TOTAL** | | | **87.1/100** |

**Decision:** ✅ **ADOPT** — Firecrawl CLI replaces direct API calls with an agent-native interface. Critical upgrade for ZoneWise municipal scraping and BidDeed auction data pipelines.

---

## 2. What It Is

Firecrawl CLI (`firecrawl-cli`) is a unified command-line interface wrapping all Firecrawl API endpoints — scrape, search, crawl, map, and browser automation. The companion "Skill" package teaches AI agents (Claude Code, Codex) to self-install and self-authenticate.

**Key difference from current integration:** We already use the Firecrawl Python SDK in ZoneWise Scraper V4's waterfall pipeline (`Firecrawl→Gemini→Claude`). The CLI adds:
- Cloud browser sessions for JavaScript-heavy municipal GIS portals
- File-based output (results → `.firecrawl/` dir, not stuffed into LLM context)
- Agent-native discovery (Skill protocol, auto-install)
- Parallel agent execution (batch hundreds of queries)

---

## 3. Security Assessment (82/100)

### 3.1 Authentication & Access Control
- **API Key auth** — same `FIRECRAWL_API_KEY` we already manage via GitHub Secrets
- `firecrawl login --api-key` or env var — no new auth surface
- Keys stored in `/opt/cliproxy-gateway/config.yaml` pattern or `.env` per repo
- **Risk:** CLI stores credentials in `~/.firecrawl/config.json` — ensure this is excluded from git and container images
- **Score: 85/100**

### 3.2 Data Exposure
- Scraped data written to local `.firecrawl/` directory — no cloud persistence beyond Firecrawl's processing
- Cloud browser sessions run on Firecrawl's infrastructure — scraped pages pass through their servers
- No PII processed in our use case (public property records, zoning codes, auction listings)
- **Risk:** Municipal GIS portal scraping could capture internal notes or restricted data if portals leak — low probability
- **Score: 80/100**

### 3.3 Telemetry & Privacy
- Anonymous telemetry ON by default (CLI version, OS, Node version)
- Disableable: `FIRECRAWL_NO_TELEMETRY=1`
- **MANDATE:** All BidDeed deployments MUST set `FIRECRAWL_NO_TELEMETRY=1`
- **Score: 75/100**

### 3.4 Dependency Surface
- npm package: `firecrawl-cli` — Node.js 18+ required
- 142 GitHub stars (young repo, firecrawl/cli)
- Parent org (firecrawl/firecrawl) has 90K+ stars — not a fly-by-night
- CLI is a thin wrapper; actual scraping runs on Firecrawl's hosted infra
- **Score: 85/100**

### 3.5 Network Security
- All API calls over HTTPS to `api.firecrawl.dev`
- Cloud browser sessions use secure WebSocket connections
- No self-hosted option for CLI (Fire-engine proprietary proxy layer is hosted-only)
- **Score: 82/100**

### Mitigations Required
1. `FIRECRAWL_NO_TELEMETRY=1` in all environments
2. `.firecrawl/` added to `.gitignore` in all repos
3. API key rotation quarterly (add to SECURITY.md calendar)
4. Rate limit monitoring — set max credits per session in CLI config

---

## 4. Value Assessment (92/100)

### 4.1 Problem It Solves
| Current Pain | CLI Solution |
|-------------|-------------|
| Municipal GIS portals (Palm Bay, Melbourne) require JS interaction | Cloud browser sessions with `firecrawl browser execute` |
| Firecrawl API results dumped into LLM context (token waste) | File-based output to `.firecrawl/` — agents read incrementally |
| Manual scraper maintenance when sites change HTML | Firecrawl handles anti-bot, JS rendering, proxy rotation |
| No unified search+scrape in one step | `firecrawl search "query" --scrape` returns full page content |
| Parallel execution requires custom code | `firecrawl agent` with parallel batch processing built-in |

### 4.2 Cost Analysis

**Current Firecrawl spend:** Already on Hobby plan ($16/month, 3,000 credits)

**CLI changes nothing about cost** — same API key, same credits. The CLI is just a different interface to the same API.

**Upgrade path if needed:**
| Plan | Credits/mo | Cost/mo | Per-page |
|------|-----------|---------|----------|
| Free | 500 lifetime | $0 | — |
| Hobby | 3,000 | $16 | $0.0053 |
| Standard | 100,000 | $83 | $0.00083 |
| Growth | 500,000 | $333 | $0.00067 |

**Current usage estimate:** ~800-1,200 credits/month (ZoneWise scraping)
**With CLI browser sessions:** Expect +500-800 credits/month for municipal GIS
**Verdict:** Hobby plan still sufficient. Monitor. Upgrade to Standard only if municipal conquests exceed 3,000 pages/month.

### 4.3 Value to Each Platform

**BidDeed.AI:**
- `firecrawl search "foreclosure auction brevard" --scrape` → automated competitive intel
- Cloud browser for RealForeclose.com dynamic content (auction calendars, bid results)
- Parallel agent for bulk property listing extraction

**ZoneWise.AI:**
- **PRIMARY VALUE** — Cloud browser sessions for municipal GIS portals that require JS interaction
- `firecrawl browser launch-session` → navigate to Palm Bay GIS → execute spatial queries
- Replace Selenium dependency in BECA Scraper with managed cloud browser
- `firecrawl crawl` for bulk municipal code page ingestion

### 4.4 Time Savings
- Eliminates custom Selenium/Playwright maintenance for JS-heavy sites
- Agent self-install via Skill means zero manual setup in new Claude Code sessions
- File-based output reduces context window pollution by ~40-60%

---

## 5. Integration Fit (90/100)

### 5.1 cli-anything Compatibility
- **Perfect fit** — CLI is already a command-line tool with `--json` output
- Wrapping in a cli-anything harness is trivial (see companion spec)
- `firecrawl_backend.py` already listed in BIDDEED_OVERLAY.md
- Every command supports `--json` flag → LangGraph orchestration compatible

### 5.2 Existing Stack Alignment
| Component | Compatibility |
|-----------|--------------|
| GitHub Actions | ✅ `npm install -g firecrawl-cli` in workflow setup |
| Hetzner (everest-dispatch) | ✅ Node.js already installed, CLI runs natively |
| CLIProxyAPI Gateway | ✅ CLI uses same API key, no gateway changes |
| Supabase | ✅ `--persist` flag writes results to Supabase via existing backend |
| AUTOLOOP eval | ✅ CLI output is deterministic JSON → easy assertion testing |

### 5.3 Migration Path
1. **Phase 1:** Install CLI alongside existing Python SDK (parallel operation)
2. **Phase 2:** Route browser-dependent scraping through CLI (municipal GIS)
3. **Phase 3:** Migrate remaining SDK calls to CLI where file-based output improves workflow
4. **Phase 4:** Retire Python SDK calls (keep as fallback only)

### 5.4 Conflicts / Risks
- Node.js dependency (already present on Hetzner)
- CLI version pinning needed — `firecrawl-cli@1.8.0` not `@latest` in production
- Cloud browser sessions have TTL limits — must handle session expiry gracefully

---

## 6. Maintenance & Support (85/100)

### 6.1 Project Health
- Parent repo: firecrawl/firecrawl — 90K+ stars, active development, YC-backed
- CLI repo: firecrawl/cli — 142 stars, 22 forks (young but backed by core team)
- 3 Spark models (Fast/Mini/Pro) actively being improved
- Dedicated blog, docs, Discord community

### 6.2 Update Cadence
- CLI versioned independently from API
- Skill auto-updates when agents re-discover it
- API backwards-compatible (v1 stable since 2024)

### 6.3 Vendor Lock-in Risk
- **MEDIUM** — Fire-engine (proxy/anti-bot layer) is proprietary and hosted-only
- Self-hosted Firecrawl exists but lacks Fire-engine → blocked by anti-bot on many sites
- Mitigation: Our public data sources (BCPAO, AcclaimWeb) don't use anti-bot → self-hosted fallback viable for core use cases
- CLI is open-source (MIT license)

---

## 7. Decision Matrix

| Criteria | Weight | Score | Weighted |
|----------|--------|-------|----------|
| API key security model | 10% | 85 | 8.5 |
| Data privacy | 10% | 80 | 8.0 |
| Telemetry/tracking | 5% | 75 | 3.8 |
| Dependency risk | 5% | 85 | 4.3 |
| Network security | 5% | 82 | 4.1 |
| Problem-solution fit | 15% | 95 | 14.3 |
| Cost impact | 10% | 95 | 9.5 |
| Time savings | 5% | 88 | 4.4 |
| cli-anything compat | 10% | 95 | 9.5 |
| Stack alignment | 10% | 90 | 9.0 |
| Project health | 5% | 88 | 4.4 |
| Vendor lock-in risk | 5% | 72 | 3.6 |
| Update cadence | 5% | 85 | 4.3 |
| **TOTAL** | **100%** | | **87.7** |

---

## 8. Adoption Mandate

### ADOPT ✅ (Score: 87.7 ≥ 80)

### Required Actions Before Deploy
1. [ ] Add `FIRECRAWL_NO_TELEMETRY=1` to all GitHub Actions workflows
2. [ ] Pin CLI version: `npm install -g firecrawl-cli@1.8.0`
3. [ ] Add `.firecrawl/` to `.gitignore` in all repos
4. [ ] Create `cli-anything-firecrawl` harness (see companion spec)
5. [ ] Update SECURITY.md with Firecrawl CLI-specific entries
6. [ ] Test cloud browser session against Palm Bay GIS portal as POC
7. [ ] Add credit usage monitoring to weekly health check workflow

### Deferred Actions
- Upgrade to Standard plan ($83/mo) only when monthly credits consistently exceed 2,500
- Evaluate `/extract` token-based endpoint separately (different billing model, separate assessment needed)
- Cloud browser session monitoring dashboard (if usage exceeds 50 sessions/week)

---

*Assessment stored: `docs/assessments/FIRECRAWL_CLI_ASSESSMENT.md`*
*Next review: June 16, 2026 (quarterly)*
