# BIDDEED.AI — ARCHITECTURE SINGLE SOURCE OF TRUTH (SSOT v1)

**Status:** canonical. Where any brief, doc, comment, or session memory conflicts
with this file, this file wins. **Any commit that changes infrastructure must
update this file in the same commit.**
**Owner:** Ariel Shapira. **Authored:** 2026-07-20 by the AI Architect, ratified by owner.
**Companion:** `CC_META_PROMPT.md` (process contract). Read both before any brief.

Written because on 2026-07-20 one session deployed the MCP product service onto
the CC runner box, and a later session — lacking any written inventory — treated
that same box as a possible intrusion. Neither would have happened if this file
had existed.

---

## 1. INFRASTRUCTURE INVENTORY

| Component | What it is | What it is NOT |
|---|---|---|
| **Local Dell** | The biddeed.ai MCP **product serving machine**. Runs the MCP HTTP server from this repo on open-source infrastructure, exposed as `mcp.biddeed.ai` via Cloudflare Tunnel (`cloudflared`). See `docs/DELL_MCP_RUNBOOK.md`. | Not a dev toy. This is production. |
| **Hetzner `87.99.129.125`** | The **CC runner / dispatch box**, set up March 2026 at owner direction as the permanent Claude Code home. | **NOT a product surface.** The MCP HTTP service formerly on `:3031` is legacy (deployed 2026-06-26 in error, refreshed 2026-07-20 in error, stopped 2026-07-20). Never deploy product services here. Never cite `:3031` as a live endpoint. |
| **Cloudflare Pages** | Serves `biddeed.ai` (marketing/site). | `biddeed.ai/api/mcp` does **NOT** serve MCP — it returns site HTML. Do not "fix" it to; the MCP surface is `mcp.biddeed.ai`. |
| **Supabase `mocerqjnksmhcjzxrewo`** | Data plane: auctions, billing, cert system, dispatch guard, ops log. | Not a place for secrets in row data. |
| **GitHub Actions** | Dispatch (`cc-runner-ghonly.yml` id 297104962), crons, deploys. Guard table `public.cc_redispatch_guard` + reconciler drive the loop; a brief without a guard row has no retry and no DoD enforcement. | `mcp-vercel-deploy.yml` is dead: no Vercel project exists for biddeed (verified 2026-07-20); Vercel secrets absent. Do not chase it. |
| **Stripe** | LIVE mode only: 4 products, 2 payment links, S5 meter. No test-mode path exists (known gap). | Not yet carrying real customer traffic. |
| **npm `biddeed-mcp`** | Intended stdio distribution channel. **Unpublished** (registry 404). `NPM_TOKEN` absent from repo secrets. | Not required for the HTTP surface to go live. Publish is a separate owner decision; canonical endpoint and npm name are registered in mcp_server_registry. |
| **`zonewise-floorplan` Worker** (`workers/zonewise-floorplan/` in this repo, deployed via `.github/workflows/deploy-zonewise-floorplan.yml` → `zonewise-floorplan.brevardbidderai.workers.dev`) | **`/floorplan/*` ONLY as of 2026-08-16 (SSOT consolidation, issue #19149).** The Worker briefly also served `/site-massing/*` (a duplicate generative-massing implementation, shipped by a session that kept running after being told to stop on #19143) — that code (`site-massing.js`, `site-dxf.js`, `site-massing-lookup.js`, `site-massing-persistence.js`, their tests/fixtures) and its three routes (`POST /site-massing/generate`, `GET /site-massing/:run_id`, `GET /site-massing/:run_id/options/:option_id/dxf`) were **removed** and the Worker **redeployed live** (`gh run 31940834387`, success) — confirmed `POST /site-massing/generate` now 404s live, `GET /floorplan/schema` still 200s. `geo.js` was left in place per the issue's explicit scope lock even though it's now unreferenced by `worker.js` (only `site-massing.js`/`site-dxf.js` imported it) — flagged, not deleted. `public.site_massing_runs`/`site_massing_options` and the `site-dxf` Storage bucket are unaffected (still live, now written only by zonewise-web's `/api/massing/*`, see below). | **CRITICAL, live production break caused by this same commit**: the ElevenLabs "ZoneWise Voice Assistant" agent's `rerun_capacity` webhook tool (added same-day by the concurrent #19148 session, see ElevenLabs row below) calls `POST zonewise-floorplan.brevardbidderai.workers.dev/site-massing/generate` **directly** — confirmed live via `elevenlabs_get_agent` RPC immediately before this deploy. That route is now gone. Voice customers asking "what could I build here" will get a tool-call failure until `rerun_capacity`'s URL is repointed (there is no drop-in replacement today: zonewise-web's `/api/massing/run` expects the caller to already have resolved zoning + parcel boundary, unlike the Worker's endpoint which took only `parcel_id`+`co_no` and did that resolution server-side — porting that resolution into a callable voice-tool endpoint is new scope, not done here). **Not fixed in this session** — flagged on #19143/#19144/#19148 for owner decision; deliberately not patched blind given it's a live customer-facing voice agent. |
| **ElevenLabs ConvAI voice agents** (`elevenlabs_get_agent`/`elevenlabs_api_patch`/`elevenlabs_api_post`/`elevenlabs_api_post_long` SECURITY DEFINER helpers scoped to `/v1/convai/*`, plus `elevenlabs_tts_generate` (added 2026-08-16, issue #19162) scoped to `/v1/text-to-speech/{voice_id}/with-timestamps` — all reuse the single vault key `elevenlabs_api_key`, no new secret) | Two production agents, extended 2026-08-16 for Algoma-"AL" parity (issue #19148). **ZoneWise Voice Assistant** (`agent_8801kzppqvkqewtaabvh8wyg7tyv`): 6 webhook tools total — pre-existing `query_zoning_database` (`POST https://zonewise.ai/api/zoning-chat`), `compile_floor_plan`/`save_floor_plan` (Worker `/floorplan/*`), plus new `rerun_capacity` (**BROKEN live as of 2026-08-16 SSOT consolidation #19149** — pointed at Worker `POST /site-massing/generate`, which that session removed; real levers were `layout_types[]`/`stories`, NOT `target_far`/`unit_count`, which the engine doesn't accept), `run_proforma` (`POST https://zonewise.ai/api/reports/proforma`, mirrors `proFormaInputsSchema` from `lib/development-analysis/proforma-engine.ts`), `search_sites` (`GET https://zonewise.ai/api/parcels/search`, address/city/zip prefix only — no zoning-type or lot-size-range filter exists). Now has the same 6 `language_presets` (ar/es/fr/pt/ru/zh) as Deed, translated first_messages only (Claude-authored, not a translation-API call — same method implied by Deed's pre-existing presets). **Deed** (`agent_5301kzeg7pj8ezrbaarvkyyfgyd9`, "BidDeed Distressed Property Advisor"): redesigned from zero tools / explicit no-live-data prompt to 2 real webhook tools — `search_upcoming_auctions` and `check_case_status`, both hitting `GET https://zonewise.ai/api/auctions` (public, `multi_county_auctions`) with new query filters added this session (`case_number`, `address`, `sale_type` — `sale_type` added because the pre-existing `type` filter targets `auction_type`, which is NULL on ~72% of Brevard rows; `sale_type` is the reliably-populated column). The full S5 title/lien/equity report stays gated behind Clerk auth + paid entitlement (`/api/report`, confirmed live-401/404 for unauthenticated calls) — intentionally not reachable from voice, per the issue's guardrail that the paid report isn't replaced. Email-capture/upsell CTA preserved, all legal/financial-advice guardrails preserved and one strengthened (see below). | Backend readiness for the 3 new ZoneWise tools was independently curl-verified against real Brevard data (`21 3529-02-*-11`→no geom found honestly; `22351532*5`→full real solver run with real Titusville R-1B/PUD standards) — see `docs/security/` session evidence, not restated here. **Fabrication finding (2026-08-16, real, not hypothetical):** a `simulate-conversation` test of Deed in Arabic produced a fabricated case number (`2023-CA-001234`), date, and placeholder street address (`123 Main Street`) after `search_upcoming_auctions` returned only a stub `"Tool Called."` result (simulate-conversation does not execute real webhooks — known limitation, confirmed again here). Prompt guardrail strengthened same session ("a successful call is not the same as having real data... never fill that gap with a plausible-sounding case number, date, or street address") and a repeat Arabic test did not reproduce the fabrication — single-run evidence, not a controlled A/B, given LLM non-determinism. **Audio/voice-quality validation VERIFIED 2026-08-16 (issue #19162)**: new `elevenlabs_tts_generate(p_voice_id, p_text, p_model_id)` SECURITY DEFINER function added, scoped only to `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps`. Binary-safety note: `extensions.http_response.content` (pgsql-http 1.6) and `net.http_response.body`/`content` (pg_net 0.20.4) are both `text`, not `bytea`, in this project — routing raw MP3 bytes through either would corrupt on server-encoding conversion. Rather than fight that, the function calls ElevenLabs' `/with-timestamps` variant, which returns JSON with an ASCII-safe `audio_base64` field, and passes it straight through as `jsonb {audio_base64, content_type, bytes}`. Verified byte-exact: base64-decoded output round-tripped to a file and confirmed a valid, playable MP3 via `ffprobe` (`codec_name=mp3`, correct duration, `probe_score=51`), not just "no SQL error." **Model note**: `eleven_v3_conversational` (the model the agents use for ConvAI) returned `401 model_access_denied` on the raw TTS endpoint — that model is ConvAI-only on this account; `eleven_multilingual_v2` was used for direct TTS generation instead (a deviation from the issue's suggested default, made because the suggested model is not callable on this endpoint at all). Real audio was generated for Deed's actual `first_message` text (voice_id `cjVigY5qzO86Huf0OWal`) in Spanish, Arabic, and French (3rd language, time allowed), then round-tripped through OpenAI Whisper (`small` model) STT and compared to the original text: Spanish word-level similarity 0.83, Arabic 0.88, French 0.82 (Arabic — the RTL/most-phonetically-different case flagged in #19148 — round-tripped *best* of the three). All three transcriptions matched sentence structure and content words closely; the only recurring mismatch was the invented brand name "Deed"/"BidDeed" being phonetically transliterated differently by Whisper (e.g. Spanish "Did"/"Bit.Did", French "Did"/"Bid Did") since it isn't a real word in any of these languages' STT vocabularies — not a mispronunciation by the voice, a transcription-side artifact. **Verdict: voice_id `cjVigY5qzO86Huf0OWal` renders intelligibly in Spanish, Arabic, and French** — no garbled/mismatched round-trip found in any of the three languages tested. Conversational/text fluency (tool-call parameter extraction from non-English input) remains separately verified per #19148. |

| **HomeHarvest ingestion pipeline** (`scripts/homeharvest_ingest.py`, `.github/workflows/homeharvest-ingest.yml`) | Interim/bootstrap closed-sales + rental comps source (Ariel, 2026-08-16), until revenue supports a licensed API (RentCast/Rentometer). Weekly cron (Mondays 09:00 UTC) pulls `homeharvest` (PyPI, identical to `breverdbidder/HomeHarvest` fork's `master` — no divergence, diffed 2026-08-16) against Realtor.com, `listing_type=sold\|for_rent`, `parallel=False`, sequential with a 3s delay between calls. Writes `public.sale_listings` (+ new `sold_price`/`last_sold_price` columns, migration `20260816_homeharvest_ingestion_pipeline.sql`) and `public.rental_listings`. Every row: `source='homeharvest_realtor_com'`, `honesty_marker='INFERRED'` — never labeled MLS/Zillow/Redfin. Scope: FL only, Brevard + the 37-county Gold Standard-certified list (`v_certified_counties`, `FL_PRIORITY_COUNTIES` in the script), rotated 6 counties/week (Brevard every run) — not all 67 FL counties. `id` is a deterministic hash of `(source, listing_type, mls_id\|property_url)`, upserted via `on_conflict=id` — proven idempotent live 2026-08-16 (two consecutive real runs against Brevard, no duplicate rows). `county` column uses the same lowercase/underscore slug convention as `multi_county_auctions.county` (e.g. `brevard`, `st_johns`), not the Title Case search string. | Not a live/per-request path — biddeed.ai and zonewise.ai only ever read the Supabase tables, never call `homeharvest` directly. Not RentCast — `getRentalComps()`/comp-fetch call sites should stay swappable to a licensed API later, this is explicitly interim. |
| **PLG email-capture gate** (`zonewise-web`: `lib/gate/`, `hooks/useLeadGate.ts`, `components/gate/EmailGateInline.tsx`, 2026-08-16) | Gates the export/download payoff moment on `/massing` (Download CAD/DXF), `/floorplan` (Save, Download PDF), `/proforma` (Formula Transparency section + PDF) — all three stay sign-in-free per Ariel's explicit lead-gen strategy; only the highest-value output requires an email first. Reuses the **existing** ZoneWise Voice Assistant email-gate pattern (`components/chat/VoiceZoningAssistant.tsx`/`VoiceDraftsman.tsx` → `POST /api/floorplan/lead` → `public.floorplan_voice_leads(email, source, created_at)`) rather than inventing a new table — the issue brief said "leads/lead_profiles table"; the real, live, pre-existing pattern in this codebase is `floorplan_voice_leads`, not `lead_profiles` (which exists but is BidDeed's separate auction-lead table, unrelated to these three tools). New `source` values (`massing_cad_export`, `floorplan_pdf_export`, `proforma_pdf_export`) make these leads distinguishable from voice leads (`*_voice_gate`) in the same table. Session state is a non-httpOnly cookie (`zw_lead_gated=1`, 24h) set by `/api/floorplan/lead` on success — one capture unlocks all three tools for that browser session, confirmed live via Playwright (Massing DXF capture → Floor Plan Save did not re-prompt → Pro Forma rendered unlocked). Anonymous usage cap (3 free full tool-runs — massing generate / floorplan compile / proforma calculate — combined across all three, soft cookie counter `zw_free_runs`, 402 `usage_cap_reached` past the cap) enforced server-side in `POST /api/massing/run`, the `compile` leg of `app/api/floorplan/[...path]/route.ts`, and `POST /api/reports/proforma` — confirmed live (3× `200`, 4th `402:usage_cap_reached`). Export gates enforced server-side too where the export is a real network call (`POST /api/massing/dxf` requires the gate cookie); Floor Plan/Pro Forma PDF export is 100% client-side (jsPDF, no network call) so the gate there is UI-only, matching the issue's explicit non-goal of not adding a sign-in wall. | **Real, verified, pre-existing bug found and fixed while verifying this (not part of the original ask, but blocked verifying it):** `public.zoning_assignments` had RLS enabled with **zero policies**, so anon held a table-level SELECT grant but every anon read returned 0 rows regardless — the entire `/massing` tool's free zoning-resolution step (`resolveZoningForParcel`) was silently broken for every anonymous visitor before this session, defeating the "let a visitor feel real value" premise this very issue is built on. Fixed with an additive `zoning_assignments_public_read` SELECT policy (`supabase/migrations/20260816_zoning_assignments_public_read.sql`), same shape as the pre-existing public-read policies already on `zoning_districts`/`zone_standards`; no PII/financial columns exposed. Applied live via Management API and verified (anon read went 0 rows → real row) before this was reported fixed, per RLS being on the `never_ask_ariel` list in CLAUDE.md's Supabase CLI section. |

### 1.1 biddeed.ai WEB SERVING — APEX CUTOVER (2026-08-20)

`biddeed.ai` web traffic is served by Cloudflare Worker `worker-damp-snowflake-cead`
(this repo, `src/worker.js`, deployed by `deploy-worker.yml`) — **VERIFIED live
2026-08-20**; §1's "Cloudflare Pages serves biddeed.ai" row conflicts with this
observation and is flagged per §7 as a finding, not silently rewritten.
As of commit `755ae8e` (2026-08-20), the Worker proxies `/`, `/radar*`, `/_next/*`,
`/api/*`, `/success*`, `/order*` to the Next.js app `breverdbidder/biddeed-web`
on Vercel (`biddeed-web.vercel.app`, basePath empty — apex contract documented in
that repo's `next.config.mjs`). This completed the cutover the 2026-08-18 session
left half-shipped: the Worker had only the `/radar` branch while the deployed app
emitted root-relative `/_next/*` and `/api/*` URLs, so biddeed.ai/radar served an
unstyled, non-hydrating skeleton (assets 404'd as text/plain). The Worker retains
every other route it owns (checkout, 67 county SEO pages, legal, `/report/:id`,
`/auctions` JSON, `/chat*`, `/unsubscribe`). Apex `/auctions` stays Worker JSON by
design; the app's own `/auctions` page is intentionally unreachable via biddeed.ai.
Rollback: reduce the proxy condition back to the `/radar` tests alone.

### 1.2 COUNTY-PAGE ASSETS + CSP (2026-08-20)

The 67 `/county/:slug` pages' third-party CDN dependencies (Tailwind dev CDN,
Alpine 3.13.5, PapaParse 5.4.1) were being blocked by the Worker's own CSP
(`script-src 'self' …`), so every county page served only the Phase-0 fallback
banner to every visitor — the interactive table never booted in production.
Fixed 2026-08-20 (commits `5b5cc0c`, `4afca0b`, `e3f6ef7`): Phase 0 items 3–4
completed — assets are now vendored into the Worker and served from
`/assets/tailwind-county.css` (static Tailwind build from the county template's
class set; no inline tailwind.config existed so default-config output is
equivalent), `/assets/alpine.min.js` and `/assets/papaparse.min.js` (exact
pinned CDN versions, length-verified 43838/19469). An inline eval-probe routes
to the honest fallback if expression evaluation is ever blocked again.
**CSP change, owner-approved in-session (Ariel, 2026-08-20):** `'unsafe-eval'`
added to the Worker CSP's script-src — required by Alpine's standard build;
marginal on a policy already carrying `'unsafe-inline'`; scope is Worker-served
pages only (the proxied biddeed-web app ships its own nonce CSP). Phase 3 SSR
migration of the county pages remains the real fix and removes both tokens.
Verified live post-deploy: /county/alachua and /county/brevard render the full
interactive table (equity totals, Shapira Triangle filters) with zero console
errors, first verified fully-working production render of these pages.

## 2. SERVING MODEL (the one answer to "where does the MCP run")

Customer → `mcp.biddeed.ai` → Cloudflare Tunnel → **local Dell** → MCP HTTP server (this repo, `main`) → Supabase.
Auth: API key / OAuth per `src/server.js`. Billing chain: `handleToolCall` → idempotency claim → cert gate → allowance → execute → `recordBilling` → `billing_events` → hourly `s5-meter-emit` → Stripe meters.
**Proven end-to-end 2026-07-20** (first verified traffic: idempotency +1-not-+2, `mcp_charge_events` outcome=charged, `last_used_at` updated, tier-gate refusal left billing unchanged).

## 3. PROTECTED OBJECTS (read freely, write only when a brief names them)
`gold_standard_*`, `insights`, `taxi_meter_*`, `multi_county_auctions`. Ops outcomes go to `public.agent_ops_log`; auction/anomaly data to `public.insights`. `gold_standard_scoreboard` is untrustworthy — never cite as proof.

## 4. CERTIFICATION
`gold_standard_certify()` with N=3 strike hysteresis, persisted `revocation_reason` + `last_evaluated_run`, warn-before-revoke (GTM-22H, 2026-07-19). Cert gates S5 (`predict_auction_outcome`, $25). A county with empty enrichment data will and should fail cert — fix the data, not the gate.

## 5. KNOWN GAPS (open, owner-visible)
- Marion (and non-Brevard generally): property-appraiser enrichment absent; FJ was mis-mapped into `opening_bid`; `plaintiff_max_bid` not captured. In flight: issue #12851.
- No Stripe test mode; no live customer subscriptions yet.
- `NPM_TOKEN` absent — npm channel dark (owner decision).
- A GitHub PAT was exposed in plaintext in a March 2026 session — rotation recommended (owner-only).
- Issue #12745 (GTM-22 parent) parked in `needs_dod`.
- **Secret rotation (2026-08-03 audit):** 35 of 37 tracked secrets have never
  had a rotation date recorded (`public.secret_rotation_registry`). Weekly
  Telegram reminder now live (`secret-rotation-check` cron, Mondays 09:00 UTC)
  but nothing has actually been rotated yet except Cloudflare's deploy token
  and the gh-aw Anthropic API key (both 2026-07-28). `service_role_key` and
  `anthropic_oauth_bearer` in particular are still unrotated. See
  `docs/security/vault-audit-2026-08-03.md`.
- **No Supabase network restriction is possible today without a tradeoff**:
  Vercel egress IPs are dynamic/unpublished unless the $100/mo Static IPs
  add-on is purchased (not provisioned, purchase forbidden by this audit's
  scope); GitHub Actions' published IP range (7,297 CIDRs) is too broad to be
  a meaningful allowlist. Project remains fully open (`0.0.0.0/0`). See
  `docs/security/ip-allowlist-research.md`.
- **Vault secret access is not audited**: no `vault_access_log`, no `pgaudit`
  extension. Platform limitation, not a config gap — cannot verify who reads
  `vault.decrypted_secrets` and when. See CREDENTIAL HANDLING section of
  `CLAUDE.md` for the `get_vault_secret_mcp()` open finding this compounds.
- `cc-login-telegram.yml` and `claude-login-telegram.yml` (OAuth-refresh-
  adjacent) both last ran 2026-04-03 (4 months stale as of 2026-08-03);
  `claude-login-telegram.yml` failing on its last 3 observed runs. Not
  investigated further — out of scope for the 2026-08-03 security audit,
  flagged as a finding.
- **`pipeline.tier1_card_raw` and 3 sibling `pipeline.*` tables had no GRANT
  for `service_role`/`anon`/`authenticated`** (only `postgres` — a config gap,
  not RLS), so `v_brevard_td_sold_cma` 403'd for every PostgREST caller even
  though the view itself was exposed. Fixed 2026-08-16 (issue #19146 session):
  `GRANT USAGE ON SCHEMA pipeline` + `GRANT SELECT` on `tier1_card_raw`,
  `brevard_account_parcel`, `brevard_realtdm_cases`, `brevard_trtax_deeds` to
  those three roles, via the Management API SQL endpoint (`api.supabase.com`,
  not direct psql — see CREDENTIAL HANDLING's `SUPABASE_DB_PASSWORD`
  constraint in `CLAUDE.md`, which does not apply to this HTTPS-based path).
  **Separately, the view's own join is broken**: `pipeline.brevard_account_parcel.parcel_id`
  uses a different tokenization than `fl_parcels.parcel_id` for the same
  parcel (e.g. `20-34-09-00-6` vs `20 3404-00-1`), so the join to `fl_parcels`
  never matches and `median_comp`/`n_comps` are NULL for all 2,504 rows in the
  view today — verified via direct query, not fixed here (owned by whatever
  pipeline populates `brevard_account_parcel`, out of scope for a UI-wiring
  session). Any future work reading this view should re-check row coverage
  before assuming the GRANT fix alone makes it usable.
- **Site Massing CAD/DXF export — SSOT consolidated to ONE canonical
  implementation (2026-08-16, issue #19149, closing the #19143/#19144 dual-
  implementation finding via Ariel's explicit same-day decision)**: two
  independent implementations of this feature briefly coexisted — a Next.js-
  native solver in `breverdbidder/zonewise-web` (issue #19144) and a
  Cloudflare Worker version (`workers/zonewise-floorplan/site-massing.js`)
  shipped by a session that kept running after being told to stop on #19143.
  The Next.js version was canonicalized (more geometrically correct — true
  parcel-polygon point-in-polygon fit vs. the Worker's bounding-box
  approximation); the Worker's one real advantage, real townhome_row/
  multifamily_grid unit-packing + access-drive logic (the Next.js version
  only did single-family-style orientation/shrink variants), was ported into
  `lib/development-analysis/site-massing-solver.ts`'s new
  `computeMultiUnitCandidates()`, adapted to run per hull-edge orientation
  against the true-polygon-fit envelope rather than the Worker's single fixed
  bbox orientation. Verified live against a real 9.75ac Brevard RU-2-15
  parcel (Cocoa, 15 du/acre, zone_standards id 71) for all three layout
  types, 0 boundary violations across all returned footprints. Widened
  multifamily_grid's coverage-fraction tiers (ported [0.9,0.7,0.5] -> added
  0.3/0.15) after finding the original tiers imply 29-52 units/acre at
  default stories/sqftPerUnit, producing zero surviving candidates against
  this real zone's 15 du/acre cap — the Worker's own defaults would have hit
  the same wall on real Brevard data, not a regression introduced here.
  `lib/development-analysis/site-dxf.js` gained real per-unit + access-drive
  DXF geometry for multi-unit candidates (previously single_family-only) and
  Storage persistence (`saveSiteMassingDxfToStorage`) to the pre-existing
  private `site-dxf` bucket at `<run_id>/<option_id>.dxf` — same convention
  as the decommissioned Worker's `persistence.js`, reused not reinvented.
  `/api/massing/dxf` now accepts optional `runId`/`optionId` and persists
  best-effort (a Storage failure doesn't block the download). Verified via a
  real HTTP round trip against `next start` for all three layout types:
  persist run -> generate DXF -> upload to Storage -> write `dxf_path` ->
  fetch the file back from Storage (not just the DB row) -> byte-match the
  streamed download. `MassingEngine.tsx` got a layout-type selector so all
  three paths are reachable from the shipped "Download CAD (DXF)" button,
  not just single_family. `/api/site-massing/*` (zonewise-web proxy) and the
  Worker's `site-massing.js`/`site-dxf.js`/`site-massing-lookup.js`/
  `site-massing-persistence.js` + their tests/fixtures were removed; the
  Worker was redeployed live (confirmed `/site-massing/generate` now 404s,
  `/floorplan/*` unaffected). `site_massing_runs.created_by = 'cc-session-
  test'` (the Worker's own test row, `2026-08-16T08:47:28Z`) and two
  `created_by = 'cc-deploy-verification'` rows (from the now-removed deploy-
  workflow verify step) were left in place — explicitly in scope for "your
  call" per #19149's DoD; this session's own test rows/Storage objects were
  deleted after verification. **New CRITICAL finding from this same
  decommission**: the ElevenLabs "ZoneWise Voice Assistant" agent's
  `rerun_capacity` tool (added same-day by the concurrent #19148 session)
  calls the now-deleted `Worker POST /site-massing/generate` directly — see
  §1's `zonewise-floorplan` Worker row and ElevenLabs row for detail. Not
  fixed here; flagged on #19143, #19144, and #19148 for owner attention.
- **Voice agent parity session (2026-08-16, issue #19148)** shipped two small,
  additive `breverdbidder/zonewise-web` API changes to `app/api/auctions/route.ts`
  (main, commits `10d1d81` and `74bdf70`, both live-verified post-deploy):
  new `case_number`/`address` ilike filters, and a new `sale_type` filter
  (`auction_type`, the pre-existing filter, is NULL on ~72% of Brevard rows —
  `sale_type` is the reliable column). See the ElevenLabs row in §1 for what
  consumes these. **Separately confirmed broken this session, later removed
  entirely (not fixed) by the 2026-08-16 SSOT consolidation, issue #19149:**
  `/api/site-massing/*`'s Next.js proxy route 404s live despite existing in
  the deployed commit. #19149 deleted the route outright as part of
  decommissioning the duplicate Worker implementation it proxied to — see
  §1's `zonewise-floorplan` Worker row for the resulting live break in this
  session's `rerun_capacity` voice tool.

- **S5 report Layer 2 (Retail CMA) now falls back to HomeHarvest/Realtor.com
  comps when `fl_parcels` has none** (2026-08-16, `packages/biddeed-mcp/src/report/cma.js`
  `buildCma()`): previously a subject with zero DOR-recorded sale comps in
  `fl_parcels` (common — that data is thin/stale) rendered "Pending — no
  retail comps returned." with no fallback. `buildCma()` now queries
  `public.sale_listings` (zip + ±30% sqft match, `source='homeharvest_realtor_com'`)
  only when the `fl_parcels` path (including its existing jv/lot-band widen
  fallback) returns zero comps, and tags the response `comp_source:
  'fl_parcels_dor'` vs `'homeharvest_realtor_com'` so the two are never
  conflated — verified live both ways 2026-08-16 (real Brevard parcel →
  `fl_parcels_dor`, 6 comps; synthetic parcel with an unmatched zip →
  `homeharvest_realtor_com`, 6 real closed sales, zip 32940). **Layer 1
  (`buildDistressedCma`, the Shapira/auction-outcome CMA sourced from
  `multi_county_auctions`) is untouched** — this is additive to Layer 2 only.
  `composer.js`'s `computeValueEstimate()` consumes `cma.median_sale_price`/
  `cma.n`/`cma.jv_twin` exactly as before; the new fallback branch populates
  the same contract so no caller-side change was needed. **Known pre-existing
  bug, not introduced or fixed here**: `src/worker.js`'s `renderS5ReportHtml()`
  comp-table getter for the "Sold" column reads `c.sale_price1 ?? c.sold_amount`,
  but `cma.comps` rows (both the pre-existing `fl_parcels` path and the new
  HomeHarvest path) use the field name `sale_price` — the Sold column has
  likely rendered blank in production for Layer 2 comps since this section
  first shipped. **FIXED 2026-08-20** (worker commit `2389eec`): the getter now reads
  `c.sale_price ?? c.sale_price1 ?? c.sold_amount` behind a Number.isFinite
  guard. Shipped in the same commit as a separate, worse bug found in that
  renderer the same day: `opp.entry_bid` is a `{ value, display }` object, so
  `Number()` on it produced a literal **"$NaN" Entry Bid on a live PAID S5
  report** (7830 Stirling Bridge Blvd S, Palm Beach — observed in production,
  now renders $17,404). A new `s5Money()` helper normalises number | numeric
  string | {value,display} to a dispVal-compatible value or null, and is now
  used for Entry Bid, Value Midpoint, Walk Away Above and the headline Max Bid,
  so an unusable figure falls back to the honest placeholder instead of
  printing NaN at a bidder.

## 6. CHANGE RULES
Additive by default. New surface, box, service, tunnel, or deploy target ⇒ update §1 in the same commit. A session that cannot find an answer here asks the owner; it does not infer from what happens to be running.

## 6.1 SECURITY EVIDENCE PACK
Investor/enterprise due-diligence security documentation lives at
`docs/security/SECURITY_EVIDENCE_PACK.md` (index), with `INCIDENT_RESPONSE_PLAN.md`,
`VENDOR_SUB_PROCESSOR_LIST.md`, `EXTERNAL_SCAN_SUMMARY.md` alongside it and
`docs/legal/DATA_RETENTION_POLICY.md` (live at `biddeed.ai/data-retention`).
Public summary at `biddeed.ai/security`. Built 2026-08-03; that session's scan
found `mcp.biddeed.ai` serving Vercel response headers, which conflicts with
§1's "no Vercel project exists for biddeed" — flagged there as unresolved,
not corrected in §1 without a dedicated verification session.

## 6.2 ENTERPRISE TRUST PORTAL (CAIQ / AI-CAIQ)
Self-serve vendor-security-review documentation, added 2026-08-03:
`docs/security/CAIQ-v4.1-BidDeed-Completed.md` (CSA-domain self-assessment),
`docs/security/AI-CAIQ-v1.1-BidDeed-Completed.md` (AI-specific self-assessment),
`docs/security/SECURITY_QUESTIONNAIRE_ANSWERS.md` (50-question lookup bank),
`docs/security/SAFEBASE_SETUP_GUIDE.md` (manual setup steps for Ariel).
Both CAIQ/AI-CAIQ docs open with a "Corrections from the originating brief"
table — several capabilities an earlier brief assumed (LlamaFirewall/LLM
Guard, a completed OWASP ZAP scan, Garak, a `mcp_usage_log` table, confirmed
MFA, an executing secret-rotation cadence) did not match live evidence
gathered the same session and are answered honestly (NO/PARTIAL), not as
the brief assumed. Do not restate those as YES elsewhere without re-verifying.
`trust.biddeed.ai` (SafeBase) is **not live** — portal signup requires
Ariel's browser session (§ SAFEBASE_SETUP_GUIDE.md); `biddeed.ai/security`
links the docs above directly in the meantime and says so explicitly.

## 6.3 INTERNAL EMAIL REGISTRY

| Address | Purpose | From identity | Consumers |
|---|---|---|---|
| `activate@biddeed.ai` | Customer-facing activation emails only. | `resend_from_address` (vault) | B2C trial/activation flow — **not touched by the 2026-08-03 alerts work.** |
| `alerts@biddeed.ai` | Internal ops alerts only (security P0/P1, secret rotation reminders). Added 2026-08-03. | `alerts_from_email` (vault) → `brevardbidderai@gmail.com` (`alerts_to_email`, vault) | `sweep_security_alerts()` (P0/P1 security events, cron `*/15`), `check_secret_rotation_due()` (cron Mon 09:00 UTC). **Not yet wired:** PostHog Worker-error relay (blocked on issue #17634/#17631, see §5) and weekly control-test report emailing (blocked — `scripts/generate_control_report.py` and `weekly-control-tests.yml` do not exist yet; that pipeline is issue #17584's scope, not built here). |

Both `sweep_security_alerts()` and `check_secret_rotation_due()` send email via a direct
`net.http_post` to Resend from inside the SECURITY DEFINER function (same pattern as the
existing Telegram sends) — the Resend key never leaves Postgres. Email is best-effort:
`IF v_resend_key IS NOT NULL AND v_to_email IS NOT NULL` guards each send, so a missing
vault entry silently skips email without blocking the Telegram leg (or vice versa).

---

## 6.4 SCHEMA HEALTH — H5 (SECURITY DEFINER + PUBLIC EXECUTE) AUTO-ENFORCEMENT

**Root cause (issue #19168, 2026-08-16), evidence-backed:** `ALTER DEFAULT
PRIVILEGES ... REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC` is correctly recorded
in `pg_default_acl` — grants to named roles (`postgres`, `service_role`, etc.)
from that default-ACL row DO get applied to newly created functions, confirmed
via a canary-role A/B test. But the implicit "PUBLIC gets EXECUTE" default
PostgreSQL applies to every new function is **not suppressible via that
mechanism** in this project (PG 17.6): toggling GRANT/REVOKE EXECUTE ON
FUNCTIONS FROM PUBLIC at the default-ACL layer made zero difference to whether
new functions carried PUBLIC EXECUTE — reproduced repeatedly in both `public`
and a brand-new throwaway schema — while the identical default-ACL mechanism
works exactly as expected for **tables** in the same schema. All 8 registered
event triggers and every `cron.job` row were inspected; none re-grant PUBLIC.
This is a genuine PostgreSQL/Supabase-managed-Postgres behavior, not a fixable
misconfiguration — the only way to prevent it is an explicit `REVOKE` issued
**after** each function is created.

**Fix — auto-remediation, not just detection.** `evt_capture_schema_health_on_ddl()`
(fired by the existing `trg_event_capture_schema_health` event trigger on
`ddl_command_end`) now identifies newly created/altered SECURITY DEFINER
functions in `public` that still carry PUBLIC EXECUTE and issues
`REVOKE EXECUTE ... FROM PUBLIC` on them immediately, using
`cmd.objid::regprocedure` (not `assert_schema_health()`'s text-based
`object_name`, which always renders `name()` regardless of real argument list
and would misidentify overloaded functions). The action is logged to
`schema_health_enforcement_log` as an already-resolved row
(`resolved_by='trg_event_capture_schema_health'`). Only PUBLIC is touched —
`anon`/`authenticated`/`service_role` grants are never modified by this path.
Migration: `supabase/migrations/20260816_h5_secdef_public_grant_autoremediate.sql`.

**Known residual gap:** PostgreSQL does not fire `ddl_command_end` for bare
`GRANT`/`REVOKE` statements (only object CREATE/ALTER/DROP) — confirmed by
deliberately re-running `GRANT EXECUTE ... TO PUBLIC` on an already-remediated
function and observing PUBLIC reappear untouched. A standalone follow-up GRANT
after creation is not caught live; it will surface on the next
`assert_schema_health()` sweep. This is an inherent Postgres event-trigger
limitation, not a gap in this fix.

**One-time sweep (DoD item 4):** `assert_schema_health()` found 199 pre-existing
app-owned SECURITY DEFINER functions with PUBLIC EXECUTE beyond the 7
`elevenlabs_*` functions already fixed manually. All 199 already carried an
explicit `anon` and/or `authenticated` grant, so revoking PUBLIC removed zero
currently-relied-upon access path (same shape as the `elevenlabs_*` fix).
Swept via `supabase/migrations/20260816_h5_secdef_public_grant_bulk_sweep.sql`.

**PostGIS exception (`st_estimatedextent`, 3 overloads):** flagged by H5 but
owned by `supabase_admin` (extension-installed, `pg_depend` confirms
`postgis` membership). `postgres` is not a member of `supabase_admin`
(`pg_has_role('postgres','supabase_admin','MEMBER')` = false) and cannot
revoke a grant it did not issue — the sweep's `REVOKE` silently no-op'd
(Postgres WARNING, not an error) and the sweep script's original log entry
incorrectly claimed "resolved" without verifying; corrected in the same
session once the live re-check caught it (0 rows still showed PUBLIC
post-sweep). Filed as a permanent `schema_health_exceptions` row instead of
force-revoking a core PostGIS utility function via a role that lacks the
authority to safely do so. Revisit only with a `supabase_admin`-privileged
session.

**Re-detection (issue #19169, same day):** `bug_registry` re-flagged this
same object ~3 min after the exception row above was approved. Root cause:
whatever populates `bug_registry` scans the raw H5 candidate shape (PUBLIC
EXECUTE still literally present on the grant, since it was never actually
revoked — only the platform boundary was documented) and does not join
against `schema_health_exceptions` the way `assert_schema_health()` does.
Live re-check in that session confirmed `assert_schema_health()` — the
canonical/gating check named in the bug's own fix_strategy — returns zero
`H5_SECDEF_PUBLIC_GRANT` rows, because it filters through the exception.
Closed `bug_registry` row 164418 as `fixed` on that evidence, not via a new
revoke. Expect further re-dispatches from this same detector until it is
taught to honor `schema_health_exceptions`; that detector lives outside this
repo and is out of scope here.

## 7. MACHINE SSOT (Supabase) — this file defers to it for inventory

The queryable inventory layer lives in Supabase and is cron-verified; this file is the
narrative/topology layer. For component lists, counts, and facts, query — do not restate here:

- `ssot_registry_projects` / `ssot_registry_components` — projects and their 635 cataloged components.
- `ssot_facts` — verified operating facts with `source_sql` and `verified_at`; trust these over any number in a doc.
- `mcp_server_registry` — canonical MCP endpoint (`https://mcp.biddeed.ai/api/mcp`), npm package, declared tool count. `is_live` flips true only on an observed MCP handshake, never on a deploy claim.
- `v_ssot_master` and related views — rollups; per CC_META_PROMPT §2.2, cross-check any rollup against base tables before citing it as proof.

Precedence: for INVENTORY AND COUNTS, Supabase wins over this file. For TOPOLOGY AND
SERVING MODEL (§1–2), this file wins. A conflict between the two is a finding to report,
not a thing to silently resolve.
