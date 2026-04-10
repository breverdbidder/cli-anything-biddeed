# CI Dossier Checkpoint Protocol v1

**Status:** MANDATORY — no dossier is complete until every checkpoint is ticked with verified evidence.
**Scope:** Every competitor in the 11-competitor fan-out (PropZone, Dono.AI, PropertyOnion, Algoma, Gridics, Zoneomics, TestFit, Autodesk Forma, Reonomy, RealtyMole/ATTOM, AI Topia).
**Owner:** AI Architect executing per competitor.
**Rule:** No execution of the next phase until all checkpoints in the current phase are green. No deliverable is produced until all 12 phases are green and EG14 gate passes.

---

## Checkpoint Format

Each checkpoint requires **three things** before it can be ticked:
1. **Artifact** — the concrete file / row / screenshot / JSON that was produced
2. **Evidence path** — where it's persisted (Supabase table + row ID, or bucket path)
3. **Verification command** — the shell command or SQL query that proves it exists

A checkpoint without all three is not ticked. No exceptions.

---

## PHASE 0 — Infrastructure Readiness (pre-flight)

**Gate rule:** Cannot proceed to Phase 1 until all Phase 0 checkpoints are green. These are one-time-per-session, not per-competitor.

- [ ] **0.1 Firecrawl API key verified live**
  - Artifact: curl response from `/v2/team/credit-usage`
  - Evidence: `plan=standard, remainingCredits>0`
  - Verification: `curl -H "Authorization: Bearer $FC_KEY" https://api.firecrawl.dev/v2/team/credit-usage`

- [ ] **0.2 Supabase ci_dossier tables exist**
  - Artifact: 8 tables in Supabase public schema
  - Evidence: `SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'ci_dossier%'` returns 8 rows
  - Verification: psql or REST API query against mocerqjnksmhcjzxrewo

- [ ] **0.3 ci-evidence storage bucket exists**
  - Artifact: bucket `ci-evidence` in Supabase storage
  - Evidence: bucket listing API returns 200
  - Verification: `curl -H "apikey: $SRK" "$SUPABASE_URL/storage/v1/bucket/ci-evidence"`

- [ ] **0.4 Playwright available (local sandbox OR Hetzner OR Firecrawl browser_execute)**
  - Artifact: successful browser launch with version string
  - Evidence: `playwright --version` output OR Firecrawl browser_execute 200 response
  - Verification: smoke test with `page.goto('about:blank')` + screenshot

- [ ] **0.5 Wayback Machine API reachable**
  - Artifact: CDX API returns for a known URL
  - Evidence: HTTP 200 from `https://web.archive.org/cdx/search/cdx`
  - Verification: `curl "https://web.archive.org/cdx/search/cdx?url=example.com&limit=1"`

- [ ] **0.6 Patent search endpoints reachable**
  - Artifact: search returns for USPTO + Google Patents + Justia
  - Evidence: HTTP 200 from each
  - Verification: firecrawl_search with patent-specific query

- [ ] **0.7 SerpAPI or Google Search equivalent reachable (for SEO + GEO layer)**
  - Artifact: search results JSON
  - Evidence: HTTP 200 from SerpAPI OR firecrawl_search
  - Verification: test query returns results

- [ ] **0.8 Credit budget reserved**
  - Artifact: budget of 400 credits reserved per competitor, 4,400 total for 11
  - Evidence: starting balance - 4,400 >= safety margin (10K)
  - Verification: `credits_remaining >= 14400` before starting

---

## PHASE 1 — Volume I: Surface Intelligence (corporate profile)

**Per competitor. No Firecrawl credits yet — mostly free data sources.**

- [ ] **1.1 Legal entity resolved**
  - Artifact: entity name, jurisdiction, registration number
  - Evidence: `ci_dossiers.legal_name, jurisdiction` populated
  - Source: OpenCorporates + state filings + website footer

- [ ] **1.2 HQ locations captured**
  - Artifact: primary HQ + all satellite offices with addresses
  - Evidence: `ci_dossiers.hq_primary, hq_locations[]` populated

- [ ] **1.3 Founding details captured**
  - Artifact: founding date + founding circumstances
  - Evidence: `ci_dossiers.founded_date, founding_story` populated

- [ ] **1.4 Employee count with trajectory**
  - Artifact: current count + LinkedIn company page employee number + growth signal
  - Evidence: `ci_dossiers.employee_count, employee_growth_30_90_365` populated

- [ ] **1.5 Crunchbase profile captured**
  - Artifact: scraped or queried Crunchbase row
  - Evidence: `ci_dossiers.crunchbase_url` populated + raw HTML in bucket

- [ ] **1.6 PitchBook profile captured (if accessible)**
  - Artifact: PitchBook record OR noted as gated
  - Evidence: `ci_dossiers.pitchbook_url` OR `pitchbook_status='gated'`

- [ ] **1.7 OpenCorporates registry checked**
  - Artifact: registry filings
  - Evidence: `ci_dossiers.opencorporates_url` populated

- [ ] **1.8 SEC Reg D Form D filings checked**
  - Artifact: EDGAR search for entity name
  - Evidence: `ci_dossiers.sec_form_d_count` populated (0 or positive)

- [ ] **1.9 Funding rounds fully documented**
  - Artifact: every round with date, amount, lead, participants, angels
  - Evidence: `ci_dossiers.funding_rounds` JSONB populated

- [ ] **1.10 Cap table / investor thesis inferred**
  - Artifact: investor list + each investor's portfolio context
  - Evidence: `ci_dossiers.investor_context` JSONB populated

- [ ] **1.11 Board composition**
  - Artifact: board members if disclosed
  - Evidence: `ci_dossiers.board_members[]` populated

- [ ] **1.12 All founders enumerated with background**
  - Artifact: each founder: name, title, prior exits, LinkedIn URL, patents, publications
  - Evidence: `ci_dossiers.founders` JSONB populated with per-founder depth

- [ ] **1.13 Key executives (non-founder) enumerated**
  - Artifact: CEO (if not founder), CTO, COO, CRO, VP Eng, VP Sales
  - Evidence: `ci_dossiers.key_executives` JSONB populated

- [ ] **1.14 Notable technical / domain hires**
  - Artifact: industry veterans on team
  - Evidence: `ci_dossiers.notable_hires[]` populated

- [ ] **1.15 Phase 1 row written to Supabase and verified**
  - Verification: `SELECT * FROM ci_dossiers WHERE competitor_slug='X'` returns 1 row with all above fields populated

---

## PHASE 2 — Volume II: Full Visual & Interactive Capture (Playwright)

**Per competitor. Credits-heavy phase.**

- [ ] **2.1 URL inventory loaded from Phase 0 sitemap**
  - Artifact: list of N URLs to capture
  - Evidence: `ci_dossier_urls.count` matches Phase 0 Layer 0 total

- [ ] **2.2 Desktop 1920x1080 full-page screenshot per URL**
  - Artifact: N PNG files, each >= 10KB
  - Evidence: `ci_dossier_urls.screenshot_desktop_path` populated for all rows
  - Storage: `ci-evidence/{slug}/screenshots/{url_hash}_desktop.png`

- [ ] **2.3 Mobile 375x812 full-page screenshot per URL**
  - Artifact: N PNG files, each >= 10KB
  - Evidence: `ci_dossier_urls.screenshot_mobile_path` populated for all rows
  - Storage: `ci-evidence/{slug}/screenshots/{url_hash}_mobile.png`

- [ ] **2.4 Above-the-fold screenshots (both viewports)**
  - Artifact: 2N additional PNGs
  - Storage: `ci-evidence/{slug}/screenshots/{url_hash}_{viewport}_atf.png`

- [ ] **2.5 Rendered HTML snapshot per URL**
  - Artifact: N HTML files
  - Storage: `ci-evidence/{slug}/html/{url_hash}.html`

- [ ] **2.6 Rendered markdown snapshot per URL**
  - Artifact: N markdown files
  - Storage: `ci-evidence/{slug}/markdown/{url_hash}.md`

- [ ] **2.7 Network capture: all XHR/fetch during page load**
  - Artifact: N JSON files with request logs
  - Storage: `ci-evidence/{slug}/network/{url_hash}.json`

- [ ] **2.8 Console capture: errors, warnings, feature flags**
  - Artifact: N JSON files with console output
  - Storage: `ci-evidence/{slug}/console/{url_hash}.json`

- [ ] **2.9 Interactive element enumeration per URL**
  - Artifact: per URL list of all [role=tab], details, [aria-expanded], [data-toggle], modal triggers
  - Evidence: `ci_dossier_urls.interactive_elements` JSONB populated

- [ ] **2.10 Each interactive element clicked, state captured**
  - Artifact: screenshot per element state change
  - Evidence: `ci_dossier_feature_screenshots` rows with step_number per state
  - Storage: `ci-evidence/{slug}/features/{feature_id}/step_{n}.png`

- [ ] **2.11 Every modal/popup captured (newsletter, cookie, consent, demo, intercom)**
  - Artifact: screenshot + DOM state per modal
  - Evidence: `ci_dossier_feature_screenshots` rows with captured_via='modal'

- [ ] **2.12 Every form state captured (empty, filled, error, submitted)**
  - Artifact: screenshots per state
  - Evidence: same table

- [ ] **2.13 Mobile nav / hamburger expanded and captured**
  - Artifact: mobile nav open state screenshot
  - Evidence: captured_via='mobile_nav'

- [ ] **2.14 Load more / show more exhausted**
  - Artifact: screenshots per click until no new content
  - Evidence: interaction_log per URL

- [ ] **2.15 Minimum screenshot count per URL enforced**
  - Rule: minimum 4 artifacts per URL (desktop full, mobile full, desktop ATF, mobile ATF)
  - Evidence: `SELECT count(*) FROM ci_dossier_feature_screenshots WHERE competitor_slug='X' GROUP BY url` >= 4 per URL

- [ ] **2.16 All screenshots uploaded to Supabase bucket**
  - Verification: `curl "$SUPABASE_URL/storage/v1/object/list/ci-evidence?prefix={slug}/screenshots/"` returns >= (N × 4)

---

## PHASE 3 — Volume III: API & Endpoint Discovery

- [ ] **3.1 robots.txt Disallow lines inventoried**
  - Artifact: all Disallow paths (often reveal backend)
  - Evidence: `ci_dossier_api_endpoints` rows with discovery_source='robots_disallow'

- [ ] **3.2 Common API paths probed**
  - Paths: `/api, /v1, /v2, /v3, /graphql, /rest, /rpc, /openapi.json, /swagger.json, /api-docs, /docs, /healthz, /status, /metrics`
  - Artifact: HTTP status per probe
  - Evidence: `ci_dossier_api_endpoints` rows with discovery_source='path_probe'

- [ ] **3.3 JS bundle URLs extracted from HTML**
  - Artifact: list of all .js file URLs referenced
  - Evidence: stored in bucket at `ci-evidence/{slug}/js_bundles/`

- [ ] **3.4 JS bundles downloaded and regex mined**
  - Artifact: extracted URL patterns, API key patterns, feature flags, internal routes
  - Regex targets: `https?://`, `/api/`, `/v\d+/`, `sk_|pk_|fc-|AIza`, feature flag patterns
  - Evidence: `ci_dossier_api_endpoints` rows with discovery_source='js_mining'

- [ ] **3.5 Sourcemap detection**
  - Artifact: list of .js.map files found
  - Evidence: `ci_dossier_api_endpoints.sourcemap_available` boolean

- [ ] **3.6 Sourcemap download + reconstruction (if available)**
  - Artifact: reconstructed original source
  - Storage: `ci-evidence/{slug}/sourcemaps/`

- [ ] **3.7 GraphQL introspection (if GraphQL endpoint detected)**
  - Artifact: introspection query + response
  - Evidence: `ci_dossier_api_endpoints.graphql_schema` populated

- [ ] **3.8 Playwright network capture merged**
  - Artifact: unique endpoints found via network listener during Layer 2
  - Evidence: `ci_dossier_api_endpoints` rows with discovery_source='playwright_network'

- [ ] **3.9 Wayback Machine archive mining**
  - Artifact: all archived versions of domain
  - Query: CDX API for domain
  - Evidence: list of archived URLs stored in bucket
  - Storage: `ci-evidence/{slug}/wayback/cdx_inventory.json`

- [ ] **3.10 Wayback diff — removed endpoints**
  - Artifact: URLs that existed historically but don't now
  - Evidence: `ci_dossier_api_endpoints.historical_removed` boolean per row

- [ ] **3.11 Hidden vs public vs authenticated classification**
  - Artifact: every endpoint classified
  - Evidence: `ci_dossier_api_endpoints.is_hidden_endpoint, is_authenticated, auth_type` populated

- [ ] **3.12 Each endpoint mapped to feature it powers**
  - Evidence: `ci_dossier_api_endpoints.reveals_feature` populated

- [ ] **3.13 All API endpoint rows written to Supabase**
  - Verification: `SELECT count(*) FROM ci_dossier_api_endpoints WHERE competitor_slug='X'` > 0

---

## PHASE 4 — Volume IV: Service Scope, Pricing, Business Model

- [ ] **4.1 Service catalog extracted**
  - Artifact: every product line, feature, service tier, add-on
  - Evidence: `ci_dossier_features` rows with feature_category populated

- [ ] **4.2 Explicit pricing extracted**
  - Artifact: every listed price, tier, unit
  - Evidence: `ci_dossiers.pricing_tiers` JSONB populated

- [ ] **4.3 Implicit pricing signals captured**
  - Signals: "contact sales", "starting at", "enterprise only", volume discounts, free tier
  - Evidence: `ci_dossiers.pricing_signals` JSONB populated

- [ ] **4.4 Pricing model type classified**
  - Values: seat_based / usage_based / outcome_based / hybrid / freemium
  - Evidence: `ci_dossiers.pricing_model_type` populated

- [ ] **4.5 Subscription term signals**
  - Artifact: monthly / annual / multi-year defaults, minimum commitments, auto-renewal
  - Evidence: `ci_dossiers.subscription_terms` JSONB populated

- [ ] **4.6 Revenue stream decomposition**
  - Primary + secondary revenue streams identified
  - Evidence: `ci_dossiers.revenue_streams` JSONB populated

- [ ] **4.7 Unit economics signals**
  - Customer count, claimed revenue, retention, NPS, deal size
  - Evidence: `ci_dossiers.unit_economics` JSONB populated

- [ ] **4.8 Business model summary**
  - Artifact: narrative summary: how they make money, from whom, at what scale
  - Evidence: `ci_dossiers.business_model_summary` TEXT populated

---

## PHASE 5 — Volume V: Legal, IP, Moat Analysis

- [ ] **5.1 USPTO exhaustive patent search**
  - Queries: company name + all named founders + notable executives + assignee search on former employers
  - Artifact: list of hits per query
  - Evidence: `ci_dossiers.patent_search_uspto` JSONB populated

- [ ] **5.2 Google Patents worldwide search**
  - Same queries as 5.1
  - Evidence: `ci_dossiers.patent_search_google` JSONB populated

- [ ] **5.3 EPO Espacenet search (European filings)**
  - Evidence: `ci_dossiers.patent_search_epo` JSONB populated

- [ ] **5.4 WIPO PatentScope search (international)**
  - Evidence: `ci_dossiers.patent_search_wipo` JSONB populated

- [ ] **5.5 Justia Patents inventor search**
  - Evidence: `ci_dossiers.patent_search_justia` JSONB populated

- [ ] **5.6 Per-founder individual patent search**
  - Artifact: separate search per founder across all 5 databases
  - Evidence: `ci_dossiers.per_founder_patent_search` JSONB with founder_name → hits

- [ ] **5.7 USPTO TESS trademark search**
  - Company name + product names in Class 9 + Class 42
  - Evidence: `ci_dossiers.trademark_search` JSONB populated

- [ ] **5.8 PACER federal court search**
  - Company as plaintiff + defendant + founders as parties
  - Evidence: `ci_dossiers.litigation_federal` JSONB populated

- [ ] **5.9 State court search (Delaware, Florida, Israel)**
  - Evidence: `ci_dossiers.litigation_state` JSONB populated

- [ ] **5.10 Regulatory filings inventory**
  - SEC, state lobbying, industry regulator filings
  - Evidence: `ci_dossiers.regulatory_filings` JSONB populated

- [ ] **5.11 Patent claim impact mapping — all 12 of our claims**
  - Artifact: each of our 12 patent claims mapped to overlap/none with evidence
  - Evidence: `ci_dossiers.patent_claim_impacts` JSONB populated for all 12

- [ ] **5.12 Trade secret boundary inference**
  - Artifact: what they disclose vs what they don't — the gaps = their secrets
  - Evidence: `ci_dossiers.trade_secret_inference` TEXT populated

- [ ] **5.13 Prior art severity classification**
  - Values: none / low / medium / high / critical
  - Evidence: `ci_dossiers.prior_art_severity` populated + `prior_art_risk_flag` boolean

---

## PHASE 6 — Volume VI: Customer & Market Intelligence

- [ ] **6.1 Customer name extraction from site**
  - Artifact: every customer mentioned (testimonials, case studies, logo wall, partners page)
  - Evidence: `ci_dossiers.known_customers[]` populated

- [ ] **6.2 LinkedIn customer signal scan**
  - Search: "uses {company}", "implementing {company}", "powered by {company}"
  - Evidence: `ci_dossiers.linkedin_customer_signals[]` populated

- [ ] **6.3 G2/Capterra/TrustRadius review mining**
  - Artifact: review count + average rating + common praise/complaints
  - Evidence: `ci_dossiers.review_intelligence` JSONB populated

- [ ] **6.4 Press mention timeline**
  - Artifact: chronological list of press mentions with sentiment
  - Evidence: `ci_dossiers.press_timeline` JSONB populated

- [ ] **6.5 Social media presence + growth signals**
  - LinkedIn followers, Twitter/X, YouTube subs, Instagram, TikTok
  - Evidence: `ci_dossiers.social_metrics` JSONB populated

- [ ] **6.6 Google Trends search volume**
  - Artifact: 12-month trend for company name + key product terms
  - Evidence: `ci_dossiers.search_trends` JSONB populated

- [ ] **6.7 Semrush/Similarweb traffic signals (if accessible)**
  - Evidence: `ci_dossiers.traffic_intelligence` JSONB populated

- [ ] **6.8 Backlink profile**
  - Ahrefs / Majestic / Moz signals
  - Evidence: `ci_dossiers.backlink_profile` JSONB populated

- [ ] **6.9 Current job postings scraped**
  - Artifact: every open role from careers page + LinkedIn jobs
  - Reveals: technical stack, growth plans, location expansion
  - Evidence: `ci_dossiers.current_jobs[]` populated

- [ ] **6.10 Historical job postings from archive**
  - Artifact: Wayback Machine archive of careers page
  - Evidence: `ci_dossiers.historical_jobs[]` populated

- [ ] **6.11 Market positioning signals**
  - Artifact: claimed TAM, serviceable market, growth rate
  - Evidence: `ci_dossiers.market_claims` JSONB populated

---

## PHASE 7 — Volume VII: Technology Stack Fingerprinting

- [ ] **7.1 Frontend framework detected**
  - Artifact: React/Vue/Angular/Next.js/Nuxt + version
  - Evidence: `ci_dossiers.frontend_stack` JSONB populated

- [ ] **7.2 CSS framework detected**
  - Tailwind / styled-components / CSS modules
  - Evidence: `ci_dossiers.css_stack` populated

- [ ] **7.3 Analytics stack detected**
  - PostHog / GA / Amplitude / Segment / Mixpanel / Heap / FullStory / Hotjar
  - Evidence: `ci_dossiers.analytics_stack[]` populated

- [ ] **7.4 Chat/booking tools detected**
  - Evidence: `ci_dossiers.chat_booking_tools[]` populated

- [ ] **7.5 A/B testing + personalization tools**
  - Optimizely, VWO, Mutiny, Dynamic Yield
  - Evidence: `ci_dossiers.experimentation_tools[]` populated

- [ ] **7.6 Tag manager + pixels**
  - GTM, Tealium, FB pixel, LinkedIn insight tag, Google Ads tag
  - Evidence: `ci_dossiers.tracking_pixels[]` populated

- [ ] **7.7 CDN + hosting detected**
  - Cloudflare / Fastly / Vercel / Netlify / AWS CF / Akamai
  - Evidence: `ci_dossiers.hosting_stack` populated

- [ ] **7.8 Auth provider detected**
  - Auth0 / Clerk / Supabase / Okta / Custom
  - Evidence: `ci_dossiers.auth_stack` populated

- [ ] **7.9 Security headers**
  - CSP, HSTS, X-Frame-Options, Referrer-Policy, Permissions-Policy
  - Evidence: `ci_dossiers.security_headers` JSONB populated

- [ ] **7.10 TLS configuration**
  - Version, cipher suites, cert issuer, validity
  - Evidence: `ci_dossiers.tls_config` JSONB populated

- [ ] **7.11 Security compliance claims**
  - SOC 2 / ISO 27001 / GDPR / CCPA claims
  - Evidence: `ci_dossiers.compliance_claims[]` populated

---

## PHASE 8 — Volume IX: Marketing, SEO, GEO, Customer Behavior, Lead Gen, Recurring Revenue

**This is the newly added phase per Ariel's April 10 2026 correction.**

### 8a — SEO Intelligence

- [ ] **8a.1 Target keywords extracted from meta titles + H1s + H2s**
  - Artifact: keyword list per page
  - Evidence: `ci_dossiers.seo_keywords` JSONB populated

- [ ] **8a.2 Schema markup (JSON-LD / microdata) extracted**
  - Artifact: all schema entities marked up
  - Evidence: `ci_dossiers.schema_markup` JSONB populated

- [ ] **8a.3 Internal linking graph mapped**
  - Artifact: every internal link → anchor text → destination
  - Evidence: `ci_dossiers.internal_link_graph` JSONB populated

- [ ] **8a.4 Canonical tag strategy analyzed**
  - Evidence: `ci_dossiers.canonical_strategy` TEXT populated

- [ ] **8a.5 robots meta directives inventoried**
  - Evidence: `ci_dossiers.robots_meta_patterns` JSONB populated

- [ ] **8a.6 XML sitemap priority weights extracted**
  - Artifact: priority per URL from sitemap.xml
  - Evidence: `ci_dossier_urls.priority_from_sitemap` populated

- [ ] **8a.7 Core Web Vitals proxies measured via Playwright**
  - LCP, FID, CLS, TTFB
  - Evidence: `ci_dossiers.web_vitals` JSONB populated

- [ ] **8a.8 Content topic clusters identified**
  - Artifact: blog posts grouped by theme
  - Evidence: `ci_dossiers.content_clusters` JSONB populated

- [ ] **8a.9 Editorial cadence inferred**
  - Artifact: publishing frequency + gaps
  - Evidence: `ci_dossiers.editorial_cadence` populated

- [ ] **8a.10 Lead magnet inventory**
  - Artifact: every gated asset + what it asks for
  - Evidence: `ci_dossiers.lead_magnets` JSONB populated

- [ ] **8a.11 CTA per page**
  - Evidence: `ci_dossier_urls.primary_cta` populated per URL

- [ ] **8a.12 Backlink profile signals (Ahrefs / Moz)**
  - DR/DA, referring domains, anchor text distribution
  - Evidence: `ci_dossiers.backlink_signals` JSONB populated

- [ ] **8a.13 Press mention velocity (last 30/90/365)**
  - Evidence: `ci_dossiers.press_velocity` JSONB populated

- [ ] **8a.14 Wikipedia presence check**
  - Evidence: `ci_dossiers.wikipedia_url` populated or null

### 8b — GEO Intelligence (Generative Engine Optimization)

- [ ] **8b.1 Perplexity citation test**
  - Query: "what is {company}" + "best {category} tools"
  - Artifact: does Perplexity cite the company? which URLs?
  - Evidence: `ci_dossiers.geo_perplexity_cited[]` populated

- [ ] **8b.2 ChatGPT browse surfacing test**
  - Evidence: `ci_dossiers.geo_chatgpt_cited[]` populated

- [ ] **8b.3 Claude citation test**
  - Evidence: `ci_dossiers.geo_claude_cited[]` populated

- [ ] **8b.4 Gemini grounding test**
  - Evidence: `ci_dossiers.geo_gemini_cited[]` populated

- [ ] **8b.5 llms.txt presence check**
  - URL: `/llms.txt` and `/llms-full.txt`
  - Evidence: `ci_dossiers.llms_txt_published` boolean

- [ ] **8b.6 AI agent onboarding skill check**
  - URL: `/agent-onboarding/SKILL.md`
  - Evidence: `ci_dossiers.agent_skill_published` boolean

- [ ] **8b.7 Markdown-native content check**
  - Artifact: are pages consumable without JS execution?
  - Evidence: `ci_dossiers.ssr_score` populated

- [ ] **8b.8 Claim density per paragraph**
  - Higher = more LLM-citable
  - Evidence: `ci_dossiers.claim_density_score` populated

### 8c — Customer Behavior Intelligence

- [ ] **8c.1 Analytics stack fully enumerated**
  - See 7.3 — cross-referenced here for completeness
  - Evidence: `ci_dossiers.analytics_stack` populated

- [ ] **8c.2 Heatmap / session recording tools**
  - Hotjar / FullStory / Smartlook / LogRocket
  - Evidence: `ci_dossiers.behavior_tools[]` populated

- [ ] **8c.3 A/B testing platforms detected**
  - See 7.5

- [ ] **8c.4 Personalization engines detected**
  - Mutiny, Dynamic Yield, Intellimize
  - Evidence: `ci_dossiers.personalization_tools[]` populated

- [ ] **8c.5 Intent data vendors detected**
  - Bombora, 6sense, Demandbase
  - Evidence: `ci_dossiers.intent_data_stack[]` populated

- [ ] **8c.6 Visitor reveal tools detected**
  - RB2B, Clearbit Reveal, ZoomInfo WebSights
  - Evidence: `ci_dossiers.visitor_reveal_tools[]` populated

- [ ] **8c.7 Cookie consent stack detected**
  - OneTrust / Cookiebot / Termly
  - Evidence: `ci_dossiers.consent_stack` populated

- [ ] **8c.8 Retargeting pixels inventoried**
  - Facebook, LinkedIn, Google, Twitter, TikTok, Taboola, Outbrain
  - Evidence: `ci_dossiers.retargeting_pixels[]` populated

- [ ] **8c.9 Exit-intent + scroll-depth tracking detected**
  - Evidence: `ci_dossiers.behavior_triggers[]` populated

- [ ] **8c.10 Form abandonment recovery detected**
  - Evidence: `ci_dossiers.abandonment_recovery` boolean

### 8d — Lead Generation Mechanics

- [ ] **8d.1 Primary lead magnets cataloged with field lists**
  - Evidence: `ci_dossiers.lead_magnets` populated with field matrices

- [ ] **8d.2 Demo booking flow analyzed**
  - Required fields, qualifying/disqualifying fields
  - Evidence: `ci_dossiers.demo_flow` JSONB populated

- [ ] **8d.3 Contact form field matrix**
  - What they ask at each step
  - Evidence: `ci_dossiers.form_fields` JSONB populated

- [ ] **8d.4 Newsletter signup placement + frequency**
  - Evidence: `ci_dossiers.newsletter_strategy` populated

- [ ] **8d.5 Webinar inventory (past + upcoming)**
  - Evidence: `ci_dossiers.webinars` JSONB populated

- [ ] **8d.6 Founder podcast appearances**
  - Evidence: `ci_dossiers.founder_podcasts[]` populated

- [ ] **8d.7 Conference speaking appearances**
  - Evidence: `ci_dossiers.conference_appearances[]` populated

- [ ] **8d.8 Guest post backlinks**
  - Founders writing for other sites
  - Evidence: `ci_dossiers.guest_posts[]` populated

- [ ] **8d.9 Case study asset library**
  - Evidence: `ci_dossiers.case_studies[]` populated

- [ ] **8d.10 ROI calculators / interactive tools**
  - Evidence: `ci_dossiers.interactive_tools[]` populated

- [ ] **8d.11 Freemium / free trial mechanics**
  - Evidence: `ci_dossiers.free_tier_mechanics` JSONB populated

- [ ] **8d.12 Partner / affiliate / referral programs**
  - Evidence: `ci_dossiers.partner_programs` JSONB populated

- [ ] **8d.13 Community strategy (Slack, Discord, Circle)**
  - Evidence: `ci_dossiers.community_presence` JSONB populated

- [ ] **8d.14 Progressive profiling / conditional form logic detected**
  - Evidence: `ci_dossiers.progressive_profiling` boolean

- [ ] **8d.15 Firmographic enrichment detected**
  - Clearbit, ZoomInfo signals in forms
  - Evidence: `ci_dossiers.enrichment_stack[]` populated

### 8e — Recurring Revenue Strategy

- [ ] **8e.1 Pricing model type classified**
  - See 4.4 — cross-referenced

- [ ] **8e.2 Subscription term lengths documented**
  - Monthly / annual / multi-year signals
  - Evidence: `ci_dossiers.subscription_terms` populated

- [ ] **8e.3 Expansion revenue mechanics**
  - Seat expansion, feature gating, usage overage, product line extensions
  - Evidence: `ci_dossiers.expansion_mechanics` JSONB populated

- [ ] **8e.4 Workflow embedding depth**
  - Integration lock-in scoring (1-10)
  - Evidence: `ci_dossiers.workflow_lock_in_score` populated

- [ ] **8e.5 Data portability signals**
  - Can customers export? How hard to leave?
  - Evidence: `ci_dossiers.data_portability_score` populated

- [ ] **8e.6 Customer success / account management presence**
  - Visible CS team, onboarding program, renewal playbook
  - Evidence: `ci_dossiers.retention_machinery` JSONB populated

- [ ] **8e.7 Contract templates published (MSA / DPA / SLA)**
  - Evidence: `ci_dossiers.contract_templates[]` populated

- [ ] **8e.8 SLA guarantees + uptime commitments**
  - Evidence: `ci_dossiers.sla_commitments` populated

- [ ] **8e.9 New product line announcement cadence**
  - Revenue expansion velocity signal
  - Evidence: `ci_dossiers.product_expansion_velocity` populated

- [ ] **8e.10 Geographic expansion pattern**
  - Evidence: `ci_dossiers.geo_expansion_pattern` JSONB populated

- [ ] **8e.11 Vertical expansion pattern**
  - Evidence: `ci_dossiers.vertical_expansion_pattern` JSONB populated

- [ ] **8e.12 Recent acquisitions (as acquirer)**
  - Evidence: `ci_dossiers.acquisitions_made[]` populated

---

## PHASE 9 — Layer 5: Feature Extraction + Patent Claim Mapping

- [ ] **9.1 Every feature discovered in phases 1-8 written as row**
  - Evidence: `SELECT count(*) FROM ci_dossier_features WHERE competitor_slug='X'` > 0

- [ ] **9.2 Each feature has evidence_url + evidence_path**
  - Evidence: no NULL values in those columns for the slug

- [ ] **9.3 Each feature mapped to our patent claims (0-12)**
  - Evidence: `ci_dossier_features.our_patent_claim` array populated

- [ ] **9.4 Winner designation per feature (them/us/tie)**
  - Evidence: `ci_dossier_features.winner` populated

- [ ] **9.5 patent_claim_impacts JSONB populated per feature**
  - Evidence: no NULL values

---

## PHASE 10 — EG14 Gate Execution

**This is the blocking gate before deliverables.**

- [ ] **10.1 Run eg14_ci_dossier evaluator script**
  - Verification: script outputs pass/fail per criterion

- [ ] **10.2 Insert row into ci_dossier_eg14_runs**
  - Evidence: row exists with verdict populated

- [ ] **10.3 If any criterion fails: enter regression-fix loop**
  - Max 3 iterations
  - Each iteration: fix the failure, re-run gate, log to eg14_runs
  - Evidence: multiple rows in eg14_runs with run_number incrementing

- [ ] **10.4 Final verdict = 'pass' before proceeding**
  - Gate rule: cannot write deliverables until verdict='pass'

- [ ] **10.5 Telegram notification on verdict**
  - Evidence: `notified_telegram=true`

---

## PHASE 11 — Deliverables (regenerated from Supabase, not in-memory)

- [ ] **11.1 Patent Appendix regenerated from SQL queries**
  - Rule: NO in-memory reasoning — pull from ci_dossiers + ci_dossier_features + patent_claim_impacts
  - Artifact: markdown file in `/mnt/user-data/outputs/`

- [ ] **11.2 Battle card HTML regenerated from SQL queries**
  - Same rule
  - Artifact: HTML file in `/mnt/user-data/outputs/`

- [ ] **11.3 Executive summary JSON generated from SQL**
  - Artifact: JSON summary for downstream use

- [ ] **11.4 All deliverables link to evidence paths in ci-evidence bucket**
  - Verification: every cited screenshot / quote / endpoint has a resolvable URL

- [ ] **11.5 Deliverables saved to /mnt/user-data/outputs/**
  - Naming convention: `{slug}-patent-appendix-v1.md`, `{slug}-battle-card-v1.html`

---

## PHASE 12 — Memory Update + Session Close

- [ ] **12.1 Memory edit: add or update competitor profile**
  - Rule: memory update must reflect VERIFIED findings only

- [ ] **12.2 Session checkpoint to daily_action_plans table**
  - Evidence: row in `daily_action_plans` with source='ci_dossier_run'

- [ ] **12.3 Telegram summary posted**
  - Evidence: message sent to primary channel

- [ ] **12.4 Credits consumed logged**
  - Evidence: `ci_dossiers.firecrawl_credits_used` populated

---

## Phase Gate Rules (MANDATORY)

1. **No phase starts until the prior phase is 100% green.** No exceptions.
2. **No checkpoint is ticked without all three: artifact, evidence path, verification command.**
3. **No deliverable is produced before Phase 10 EG14 gate returns verdict='pass'.**
4. **No shortcuts via in-memory reasoning.** All deliverables regenerated from SQL queries in Phase 11.
5. **If a tool fails, fix the tool or document why it can't be used — do not route around silently.**
6. **Honesty protocol applies:** VERIFIED / UNTESTED / INFERRED labels on every finding.
7. **Ghost-success detection:** if a checkpoint looks passed but the verification command would fail, it's NOT passed.
8. **Regression-fix loop max: 3 attempts per phase.** After 3, escalate to human.

---

## Time & Credit Budget Per Competitor

| Phase | Est Duration | Est Credits | Notes |
|---|---|---|---|
| 0 (one-time) | 15 min | 5 | Infrastructure |
| 1 | 15 min | 0 | Free data sources |
| 2 | 35 min | 200 | Playwright visual (credit-heavy) |
| 3 | 20 min | 30 | API discovery |
| 4 | 10 min | 20 | Pricing/business model |
| 5 | 20 min | 40 | Legal/IP deep |
| 6 | 20 min | 50 | Customer/market |
| 7 | 10 min | 10 | Tech stack |
| 8 | 45 min | 120 | SEO + GEO + behavior + lead gen + recurring rev |
| 9 | 5 min | 0 | Feature mapping |
| 10 | 5 min | 0 | Gate execution |
| 11 | 10 min | 0 | Deliverables from SQL |
| 12 | 5 min | 0 | Session close |
| **Total per competitor** | **~3.5 hrs** | **~475** | |
| **Total for 11** | **~38.5 hrs** | **~5,225** | Well within 100,284 budget |

---

## Checkpoint Compliance Commitment

This protocol supersedes any prior informal execution. The AI Architect commits:
- Every checkpoint will be ticked only with verified evidence
- No deliverable will be produced that references evidence not in ci-evidence bucket
- No phase will be skipped to save time
- Ghost-success patterns (claiming done without verification) are forbidden
- Regression-fix loops will run before escalation to human

**Version:** 1.0
**Date:** April 10, 2026
**Authority:** Approved by Ariel Shapira as mandatory per this message
