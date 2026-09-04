# BidDeed Claude-UI parity - architecture (as built)
Status: v1.0 as-built, 2026-09-04. Owner: Ariel Shapira. Architect: Claude chat. This file was referenced by the website meta prompt but never existed in this repo; this is the first committed version and it records what actually shipped. The acceptance reference (five layers, checkpoint board, typography and contrast standard) is docs/design/PARITY_PRD.md sections 6-8; where the two disagree, the PRD wins.

## 1. Naming and schema convention (approved by Ariel 2026-09-04)
All parity tables live in the public schema with a prefix - public.biddeed_* - not in separate chat / deal / artifacts / skills / connectors schemas, because a schema that PostgREST does not expose is invisible to the Worker (the #19688 trap that bit site.site_content). RLS on, zero anon/authenticated policies, GRANT to service_role only; owner_email is always derived server-side from a verified X-Chat-Token, never trusted from the client. DDL ships as a migration file in the PR and is applied at merge (Ariel's merge is the approval) - never by a runner against production; there is no auto-apply workflow yet, so the applier is chat until one exists.

## 2. Tables per layer
| Layer | Tables | State |
|---|---|---|
| Deed Chat C1/C2 | biddeed_chat_conversations, biddeed_chat_messages, biddeed_chat_uploads (bucket chat-uploads) | live |
| Projects C3 (= Claude Projects; renamed from Deal Rooms) | biddeed_projects (first_touch, last_viewed_at, conversation_id), biddeed_project_items, biddeed_project_files (versioned by filename), biddeed_reports (pdf/csv/json versions), biddeed_share_links (token, revoked_at); bucket artifacts (private, signed URLs) | live, PR #19930 |
| Deed Chat C6 providers | biddeed_user_providers (provider, key ciphertext via pgp_sym_encrypt under a Vault master key, model, cap), accessors biddeed_provider_upsert / biddeed_provider_get_decrypted (SECURITY DEFINER) | PR #19933 |
| Skills C4b | biddeed_skills, biddeed_user_skills, biddeed_skill_runs | planned #19924 |
| Watches C4 (= Claude Cowork / Scheduled) | biddeed_watches, biddeed_watch_deliveries (+ connectors: Calendar, Drive, Resend) | planned |
| Research + API C8 | api keys + MCP config surfaced in Settings; mcp.biddeed.ai exists | planned #19937 |
| Generative UI C7 | no tables; show_widget tool + sandboxed widget runtime; widgets stored as artifacts | planned #19947 |

## 3. Identity
HMAC-signed {email, exp} issued by POST /chat/api/identity (C2). It isolates owners but does not verify the inbox: C2b (magic link / OTP via Resend, or Clerk session) is a launch blocker (PRD D10).

## 4. Surfaces
Worker (src/worker.js): /chat and every /chat/api/* route, county pages, answers, reports, buy/subscribe. biddeed-web (Next on Cloudflare): /, /radar*, /order/success. One composer everywhere is C2c (#19934). Vendor and model names only on Settings -> Models.

## 5. Gates
Every page PR: eight-gate Chromium harness (scripts/ui-audit) green on a faithful preview before merge; re-run on the live URL after deploy (ui-audit.yml). Board and dates: PRD section 7.
