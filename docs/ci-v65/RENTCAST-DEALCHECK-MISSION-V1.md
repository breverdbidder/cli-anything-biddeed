# SUMMIT-E Mission · RentCast + DealCheck CI V6.5 Dossier

**Audience:** Claude Code running on Hetzner via `summit-rentcast-dossier.yml`
**Date:** 2026-05-27
**Authorized:** Ariel Shapira — INTERNAL CI USE ONLY, DO NOT PUBLISH
**SUMMIT id:** `05f7873d-09b7-41ac-8724-99e0b4ec9983`
**Dossier ids (v65, use for DB writes):**
- RentCast: `c2c2b95c-0cfc-4d0f-a96c-6f5b0126a668`
- DealCheck: `d08d32b7-9159-4842-859b-d6bf87d47373`

## Mission

Produce an audit-able CI V6.5 dossier on RentCast and DealCheck to confirm or invalidate the working hypothesis that BidDeed's MCP V1 should be priced and structured like RentCast's self-serve B2B tier (not Cherre/ATTOM enterprise tier). Same depth on both targets.

## Honesty Protocol V3 (mandatory on every claim)

- `VERIFIED` — directly observed
- `UNTESTED` — observed but not E2E-validated
- `INFERRED` — derived from VERIFIED inputs with reasoning
- `ASSUMED` — placeholder pending verification
- `UNKNOWN` — sought but not findable; record what was tried

**Wrong VERIFIED = 3× penalty.** Downgrade when unsure. Stamp every JSONB write:
```json
{"value": 12, "_marker": "INFERRED", "_source": "LinkedIn header"}
```

## Environment (set by workflow)

`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `GH_PAT`, `FIRECRAWL_API_KEY` (~400 credit budget total), `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DOSSIER_TARGET` (matrix: `rentcast`|`dealcheck`), `DOSSIER_ID` (matching v65 UUID)

## Pre-flight

```bash
# Firecrawl credits
REMAINING=$(curl -sS -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  https://api.firecrawl.dev/v2/team/credit-usage | jq -r '.data.remainingCredits // 0')
[[ "$REMAINING" -lt 500 ]] && { echo "FATAL: low Firecrawl ($REMAINING)"; exit 1; }

# Playwright
which playwright || (npm install -g playwright && playwright install chromium)

# DB write
curl -sS -X PATCH "$SUPABASE_URL/rest/v1/ci_v65_dossiers?id=eq.$DOSSIER_ID" \
  -H "apikey: $SUPABASE_SERVICE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
  -H "Content-Type: application/json" -H "Prefer: return=minimal" \
  -d '{"current_phase":"P1_RECON"}'
```

---

## Phase 1 · Recon (~90 min, ~250 Firecrawl credits)

**RentCast targets:** `rentcast.io/` `/api` `/pricing` `/about` `/features/*` `/blog/*` `developers.rentcast.io/` `help.rentcast.io/en/*` `/terms` `/privacy` `app.rentcast.io/` (login page only)

**DealCheck targets:** `dealcheck.io/` `/pricing` `/features` `/blog/*` `app.dealcheck.io/` (login page only), help center if discoverable

**Method:**
1. Sitemap discovery: `curl -sS https://www.rentcast.io/sitemap.xml | grep -oP '(?<=<loc>)[^<]+' > /tmp/urls.txt` — cap at 60 URLs
2. Firecrawl batch crawl: `format=markdown,html` `includeTags=main,article,section`
3. Playwright (full-page PNG + DOM evaluation per URL):
```python
from playwright.async_api import async_playwright
async with async_playwright() as p:
    browser = await p.chromium.launch()
    for url in urls:
        page = await browser.new_page(viewport={"width":1440,"height":900})
        await page.goto(url, wait_until="networkidle", timeout=35000)
        await page.screenshot(path=f"/tmp/{slug(url)}.png", full_page=True)
        metrics = await page.evaluate("""() => ({
          title: document.title,
          metaDescription: document.querySelector('meta[name=description]')?.content,
          h1: Array.from(document.querySelectorAll('h1')).map(h => h.textContent.trim()),
          requestCount: performance.getEntriesByType('resource').length,
          thirdPartyDomains: [...new Set(performance.getEntriesByType('resource').map(r => new URL(r.name).host))].filter(h => !h.includes(location.host))
        })""")
```
4. Upload to `ci-evidence/dossiers/{slug}/2026-05-27/`
5. Persist every 10 URLs: PATCH `ci_v65_dossiers` with `total_urls_scraped` + `firecrawl_credits_used` + ALSO update legacy `ci_dossiers` row via `unified_id` join

**Phase 1 done when:** `current_phase = 'P2_TECH_FOOTPRINT'`, screenshots uploaded, markdown extracted.

---

## Phase 2 · MCP/API teardown + Mermaid + ACTIVE PROBE (~75 min)

### 2a. Endpoint catalog

Walk `developers.rentcast.io/reference/*`. Per endpoint: method, URL, params (required/optional, type, example), request body, response schema, rate limit, auth, tier required.
Output: `ci-evidence/dossiers/rentcast/2026-05-27/api-endpoint-catalog.json` (OpenAPI-ish)

DealCheck: no public API. Sift JS bundle for endpoint hints. If none, mark `VERIFIED_NO_API`.

### 2b. ACTIVE MCP PROBE — RentCast only (DealCheck has no MCP)

**This is the highest-signal artifact. Treat as load-bearing.**

1. Register Developer-tier free API key at `https://app.rentcast.io/upgrade-api?plan=api-developer` using email `everestcapital8@gmail.com`
2. Email verification: if `$GMAIL_APP_PASSWORD` env set, IMAP-fetch; else pause + write `_marker:UNVERIFIED_REGISTRATION` + continue with public docs
3. Find MCP endpoint URL in their docs
4. Connect via `@modelcontextprotocol/sdk` Node client. Call `tools/list`, capture verbatim. Call `tools/call` on safe read-only tools with placeholder FL parcel `"123 Main St, Miami FL"`.
5. Output `ci-evidence/dossiers/rentcast/2026-05-27/mcp-active-probe.json`:
```json
{
  "transport": "http|sse|stdio",
  "endpoint": "https://...",
  "auth_method": "bearer|oauth|api_key_header",
  "tools_count": N,
  "tools": [{"name":"...","description":"...","inputSchema":{...}}],
  "sample_calls": [{"tool":"...","input":{...},"output_bytes":N,"latency_ms":N,"output_excerpt":"..."}],
  "_marker": "VERIFIED",
  "_captured_at": "..."
}
```

**Failure modes:**
- Signup blocked / phone verify → `_marker:BLOCKED`, skip
- MCP gated to paid tier → document gating, skip
- TOS forbids competitive analysis → STOP, `_marker:TOS_VIOLATION_RISK`, public-docs only

### 2c. Mermaid diagrams (4 per dossier where applicable)

- **C1:** Data flow (User → Client → API → DB)
- **C2:** MCP flow (User → MCP Client → RentCast MCP Server → API) — RentCast only
- **C3:** Auth flow (key create/use/rotate)
- **C4:** Pricing tier gating decision tree

Render: `mmdc -i {file}.mmd -o {file}.svg`. Upload both to Storage.

Updates: `pricing_tiers`, `subscription_terms`, `ux_flows`, `pricing_signals`, `business_model_summary`, `pricing_model_type` on legacy `ci_dossiers` row.

---

## Phase 3 · Team, founding, funding (~45 min, $0)

| Source | Query | Method |
|---|---|---|
| Tracxn | RentCast + DealCheck pages | web_fetch |
| Crunchbase free | `/organization/rentcast` `/dealcheck` | web_fetch |
| Wikipedia | RentCast, DealCheck, Anton Ivanov | web_fetch |
| LinkedIn company | `/company/rentcast` `/dealcheck` | web_fetch (rate-limited) |
| LinkedIn founder | "Anton Ivanov" + RentCast | web_search + profile fetch |
| Wayback | 3+ snapshots of `/pricing` per domain over 2-3yr | direct fetch |
| OpenCorporates | RentCast + DealCheck US entities | web_fetch (free tier) |
| US state SOS | Delaware likely; check CA too | web_fetch |
| SEC EDGAR | Form D filings | web_fetch |

**Honesty:** Revenue is ALWAYS INFERRED/UNKNOWN unless SEC filing found. "No funding raised" from Tracxn = VERIFIED. Founding date from About = VERIFIED. employee_count from LinkedIn = INFERRED unless directly observed.

Updates: `legal_name`, `jurisdiction`, `hq_primary`, `founded_date`, `founding_story`, `employee_count`, `founders`, `key_executives`, `funding_rounds`, `crunchbase_url`, `opencorporates_url`, `wikipedia_url`, `sec_form_d_count` on legacy `ci_dossiers`.

---

## Phase 4 · Three sibling reports

### 4a. BuiltWith (~20 min, $0)

For each of: `rentcast.io`, `dealcheck.io`, `app.rentcast.io`, `developers.rentcast.io`:

1. `web_fetch https://builtwith.com/{domain}` (free profile, ~80% of paid API coverage)
2. Cross-check direct: `curl -sSI https://{domain} | head -30` for headers; `curl -sS https://{domain} | grep -iE 'react|next|vue|tailwind|posthog|gtag|stripe|auth0|clerk|supabase|cloudflare|vercel'`
3. TLS: `echo | openssl s_client -connect {domain}:443 -servername {domain} 2>/dev/null | openssl x509 -noout -issuer -dates`

Capture: frontend framework, CSS, analytics, marketing-automation, A/B, chat/booking, CDN/hosting, auth, email, payments, security headers, TLS, tag manager, schema markup.

Output: `ci-evidence/dossiers/{slug}/2026-05-27/builtwith-{domain}.{json,md}`

Updates: `frontend_stack`, `css_stack`, `analytics_stack`, `behavior_tools`, `hosting_stack`, `auth_stack`, `security_headers`, `tls_config`, `builtwith_profile`, `schema_markup`, `tracking_pixels`, `retargeting_pixels`, `consent_stack`.

### 4b. SimilarWeb (~30 min, $0 Apify free tier)

```bash
apify call tri_angle/similarweb-scraper \
  --input '{"websites":["rentcast.io","dealcheck.io"]}' \
  --token $APIFY_TOKEN --output-mode json > /tmp/similarweb.json
```
Fallback if no `APIFY_TOKEN`: `curl -sS "https://www.similarweb.com/website/rentcast.io/"` — extract JSON-LD or use headless browser.

Capture: monthly visits (3-month trail), duration, bounce, source mix (Direct/Search/Social/Referral/Mail/Display), top 10 organic keywords + position, top 5 referrers, geographic top 5, mobile/desktop split, global/country/category rank.

**Honesty:** SimilarWeb estimates → ALWAYS INFERRED with `confidence: low|medium|high`.

Output: `similarweb-{domain}.{json,md}` + comparison file across both domains.

Updates: `traffic_intelligence`, `social_metrics`, `search_trends`, `backlink_signals`, `seo_keywords`, `content_clusters`, `press_velocity`.

### 4c. GEO citations (~30 min, ~$0.50)

```python
queries = [
  "What's the best real estate API in 2026?",
  "How can I get rental price estimates programmatically?",
  "Best MCP server for real estate data?",
  "RentCast vs PropStream — what's the difference?",
  "Property valuation API with AVM and comps"
]
# Gemini (direct API), Perplexity (web_fetch), ChatGPT (web search proxy)
# Claude EXCLUDED (circular)
```

Per (llm, query): mentions of RentCast/DealCheck by name, citation position 1-5, tone (positive/neutral/skeptical), competitor names alongside.

Output: `geo-citations-matrix.json` (4 LLMs × 5 queries × 2 brands = 40 cells)

Updates: `geo_perplexity_cited`, `geo_chatgpt_cited`, `geo_gemini_cited`, `geo_claude_cited`, `geo_gemini_grounded`, `llms_txt_published`, `agent_skill_published`, `ssr_score`, `claim_density_score`.

---

## Phase 5 · Patent + IP search (~30 min, $0)

### USPTO (free, PatFT/PatPub at `ppubs.uspto.gov`)

1. `IN/(Anton Ivanov)` — every Anton Ivanov patent
2. `RentCast` assignee/applicant
3. `DealCheck` assignee/applicant
4. `(rental ADJ estimate) AND (machine ADJ learn$)` — AVM prior art
5. `(property ADJ valuation) AND (comparable ADJ sale)` — comps methodology
6. `(real ADJ estate) AND (auction) AND (predict$)` — DIRECT overlap with Shapira Triangle Claim 8

### Google Patents

Same queries via `patents.google.com`. Top 20 per query.

### USPTO TESS trademarks

`RENTCAST`, `DEALCHECK`, `BIDDEED` (check our own — make sure no one filed first).

### Litigation

CourtListener: `?type=r&q=rentcast` and `dealcheck`. State courts: CA Superior, FL.

### Anton Ivanov adjacent

USPTO assignee search for any other company Ivanov has assigned patents to.

Updates: `patent_search_uspto`, `patent_search_google`, `per_founder_patent_search`, `trademark_search`, `litigation_federal`, `litigation_state`, `prior_art_severity` (enum: `none|low|medium|high|blocking`), `prior_art_risk_flag` (boolean), `prior_art_notes`.

**🚨 IMMEDIATE TELEGRAM ALERT if any patent could block Shapira Triangle Claim 8 (stacked ensemble for distressed property auctions), Claim 13 (convergence detection), or Claim 14 (cycle intelligence).**

---

## Phase 6 · BidDeed positioning delta + battle card (~30 min)

Produce ONE battle card at `breverdbidder/everest-vault/600-Research/battle-cards/rentcast-v5-REFERENCE.md`:

```markdown
# Battle Card · RentCast (+ DealCheck) v5 REFERENCE
**Generated:** 2026-05-27 by SUMMIT-E
**Audit:** ci_v65_event_log {uuid}
**Internal use only**

## TL;DR
{3-5 sentences}

## Side-by-side: BidDeed vs RentCast vs DealCheck

| Axis | BidDeed | RentCast | DealCheck |
|---|---|---|---|
| ICP | FL distressed bidders | nationwide rental investors | nationwide deal analyzers |
| Data corpus | 356K FL auctions / 10.5M parcels | 140M nationwide | none (uses RentCast) |
| Pricing entry | $99/mo (planned) | $0 → $74 | $0 → $X |
| Pricing ceiling | $2,999 + custom | $449 + custom | $X |
| MCP server | V14 trained, building | shipped | none |
| Compliance | none | none observed | none observed |
| Auth | API key (planned) | API key | session |
| Team size | 1 (Ariel) | ~10-15 (inferred) | ~10-15 shared |
| Funding | bootstrapped | bootstrapped (verified) | bootstrapped |
| Founded | 2024 | 2020 | 2017 |
| Founder | Ariel Shapira | Anton Ivanov | Anton Ivanov |
| Patent posture | 14 claims filed | {phase 5 finding} | {phase 5 finding} |

## 5 places we differentiate (sourced)
## 5 places they pull ahead
## Prior art risk assessment (from Phase 5)
## Positioning conclusion (confirm or invalidate the "match RentCast structure" hypothesis explicitly)
## Recommended actions
```

ALSO at `breverdbidder/everest-content/dossiers/competitive-intel/RENTCAST-MCP-DOSSIER-V1.md` — narrative form with embedded mermaid + screenshots.

Final state:
- Both `ci_v65_dossiers` rows → `current_phase='P12_DELIVER'`, `classification='READY_FOR_SIGNOFF'`
- `ci_v65_event_log` entry `source='summit_e_complete'` with synthesis summary
- `summit_chat_dispatch` SUMMIT-E → `state='closed'` with delivery_proof
- Telegram final ping

---

## Failure handling

Any phase fails:
1. Write `ci_v65_event_log` with `signal_kind='other'`, `source='summit_e_phase_{N}_fail'`, full payload
2. PATCH `ci_v65_dossiers.current_phase` stays where it was; add note in `meta.failures`
3. Telegram alert
4. CONTINUE TO NEXT PHASE — partial dossier > nothing
5. Phase 6 documents which phases failed

R5 quarantine: 3 consecutive Supabase write errors → quarantine + exit + Telegram. Don't burn Firecrawl on broken DB.

Credential hygiene: never echo secrets to stdout. Pre-flight grep blocks `ghp_|sbp_|sk-|AIza[A-Za-z0-9_-]{20,}` patterns.

## Telegram cadence

Every 30 min: progress ping `{slug}, phase {N}, {X}%, credits: {N}, errors: {N}`
Phase boundaries: ping with key findings
Prior-art risk in Phase 5: IMMEDIATE alert with patent number + claim impact

## Exit criteria

All MUST be true:
- [ ] Both `ci_v65_dossiers` rows at `current_phase='P12_DELIVER'` `classification='READY_FOR_SIGNOFF'`
- [ ] Both `ci_dossiers` (legacy) have non-null: pricing_tiers, founders, patent_search_uspto, traffic_intelligence
- [ ] Storage `ci-evidence/dossiers/{slug}/2026-05-27/` has screenshots + JSON artifacts for both
- [ ] Battle card committed to everest-vault
- [ ] Narrative dossier committed to everest-content
- [ ] `ci_v65_event_log` synthesis entry
- [ ] `summit_chat_dispatch` SUMMIT-E → `state='closed'`
- [ ] Telegram final summary

Missing any → run not complete; do another pass.

**Authorized:** Ariel Shapira, 2026-05-27, "I aporoved Their MCP server actual interaction... Deal check same level"