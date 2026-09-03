# CMO Factory CP3g — Distribution Lane (issue #19789)

Multimedia distribution: YouTube is the hub (#19788, separate issue). This
issue builds the spokes — Instagram, Facebook, TikTok, X — plus a
purpose-built LinkedIn B2B agent for a LinkedIn Company Page. All five are
thin adapters under `agents/distribution/`, all read from and write to the
existing `public.social_content_queue` (audited/migrated, not replaced),
all gated on Ariel's LMS approval before anything is attempted (M1/M8).

## License verdicts (re-verified live via GitHub API, Sep 3 2026)

| Repo | License | Stars | Verdict | Why |
|---|---|---|---|---|
| gitroomhq/postiz-app | AGPL-3.0 | 35,416 | **REJECTED** | Best-known open-source social scheduler, blocked outright by License V2. Do not re-propose. |
| joeyism/linkedin_scraper | GPL-3.0 | 4,469 | **REJECTED** | Copyleft AND scraping LinkedIn breaches their ToS — rejected on the terms ground alone even ignoring the license. |
| n8n | NOASSERTION (Sustainable Use) | — | **REJECTED** | Not adding a second workflow engine; pg_cron + GHA is the ticker. |
| activepieces | NOASSERTION | — | **REJECTED** | Same reason as n8n. |
| langchain-ai/social-media-agent | MIT | 2,772 | **ADOPT** (pattern only) | Curate → draft → human gate → schedule → verify orchestration shape, adopted conceptually in `agents/distribution/base.py`'s `run()` pipeline and the LinkedIn skill's Working Mode. Not vendored as a dependency — no new package entered `agents/requirements.txt` (verified: `test_distribution_lane_manifest_has_no_copyleft_scheduler_deps`, `tests/test_cmo_factory_distribution.py`). |
| inovector/mixpost | MIT | 3,655 | **REFERENCE ONLY** | Clean license but Laravel/PHP needing its own server — contradicts GHA-only mandate. Not deployed. |
| browser-use | MIT | 112,139 | **CONDITIONAL** | Permitted only for our own surfaces (e.g. QA-driving biddeed.ai). Never for posting to or reading from a social platform — automating a logged-in social session breaches platform terms. `test_distribution_adapters_never_import_the_rejected_linkedin_scraper` also asserts no adapter imports `playwright`/`browser_use`. |

### OPEN FINDING (pre-existing, found during this session's audit, not created by it)

`linkedin/vendor/linkedin_scraper/` (added SUMMIT #286, commit `57e81967`)
is a vendored copy of the exact GPL-3.0 `joeyism/linkedin_scraper` rejected
above, used by `linkedin/scraper.py` for **read-only post extraction** via
a Playwright session cookie (`linkedin setup` / `linkedin post <url>`),
not for posting. It predates this issue's license verdicts and this
issue's scope is the distribution/posting lane, not that extraction tool,
so it has not been touched here — but it is the same category of risk
this issue explicitly rejects (copyleft + ToS-breaching automation of a
logged-in LinkedIn session) and should get its own remediation pass.
Flagged for Ariel, same posture as GTM-22D's `get_vault_secret_mcp` open
finding.

## Platform requirements (VERIFIED live against official docs, Sep 3 2026)

### Instagram Reels — Content Publishing API
- Scopes: `instagram_business_basic`, `instagram_business_content_publish` (or `instagram_content_publish` + `pages_read_engagement` on the Facebook Login path)
- Prerequisites: IG Business/Creator account linked to a Facebook Page (Page Publishing Authorization complete), Meta Developer app, **App Review + Business Verification** for Advanced Access
- Media: 3s–15min, ≤300MB, aspect 0.01:1–10:1 (9:16 recommended), caption ≤2200 chars, ≤30 hashtags, ≤20 mentions
- Rate limit: Meta's own docs disagree — 50/24h on one reference page, 100/24h on another. Adapter uses the conservative floor (25) pending a definitive answer.
- **No draft/private state** — `media_publish` goes live immediately. M8 compliance is entirely our own `approved_at` gate (`agents/distribution/instagram.py`), not a platform-side safety net.
- Doc: developers.facebook.com/docs/instagram-platform/content-publishing/

### Facebook Page Reels — Video API
- Scopes: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts` + Page access token with `CREATE_CONTENT`
- Prerequisites: Facebook Page, Meta Developer app, 3-phase resumable upload (`/{page_id}/video_reels`)
- Media: aspect 9:16 (16:9–9:16 range), 1080×1920 recommended, duration 3–90s, H.264/H.265
- Rate limit: **30 API-published Reels / 24h** (VERIFIED, used as the adapter's cap)
- **Does support DRAFT/SCHEDULED `video_state`** — real platform-side safety net. `agents/distribution/facebook.py` always finishes uploads with `video_state=DRAFT`; flipping to live `PUBLISHED` is a separate, not-yet-built action.
- Doc: developers.facebook.com/docs/video-api/guides/reels-publishing/

### TikTok — Content Posting API
- Scope: `video.publish` (per-account OAuth, no bulk), app must pass App Review (~days–2wks)
- **Unaudited apps are forced `SELF_ONLY` (private)** — TikTok's own wording: "All content posted by unaudited clients will be restricted to private viewing mode." This is exactly the safety net M8 needs pre-audit — but the adapter hardcodes `privacy_level=SELF_ONLY` regardless, never trusting audit status alone.
- Media: caption ≤2200 UTF-16 runes, duration checked dynamically via `creator_info`, formats mp4/mov/webm
- Rate limit: ~15 posts/day/creator via Direct Post (used as the adapter's cap), 6 req/min per token
- Doc: developers.tiktok.com/docs/en/content-posting-api-get-started, .../content-sharing-guidelines

### X (Twitter) API v2 — IMPORTANT, overturns the issue's own starting hypothesis
- X retired the tiered Free/Basic model **Feb 6, 2026**. New access is **pay-per-usage: $0.015/post ($0.20 if it contains a URL)**. `developer.x.com/en/portal/products` now returns 402. There is no free write quota to build a ledger cap around.
- `POST /2/tweets` has **no scheduling/draft field** — every successful call publishes immediately and publicly, with no platform-side hold at all (worse than Instagram/LinkedIn, which are at least free to attempt).
- This directly conflicts with this issue's own "no paid vendors" non-goal.
- **Policy decision (this build)**: `agents/distribution/x.py` ships with `daily_cap_default = 0` — structurally disabled even if a token is ever added, until Ariel explicitly accepts the per-post cost and signs off raising the cap. NOT_CONFIGURED fires first regardless (no vault secret exists).
- Doc: docs.x.com/x-api/getting-started/pricing, docs.x.com/x-api/posts/creation-of-a-post

### LinkedIn Company Page — Community Management API (Posts API)
- Scope: `w_organization_social`, restricted to page roles ADMINISTRATOR / DIRECT_SPONSORED_CONTENT_POSTER / CONTENT_ADMIN
- **The Community Management API is a "Vetted Product"** — NOT self-serve. Development Tier needs an access-request form (verified business email, verified org, verified domain). Standard Tier (real posting volume) needs a *second* form plus a **screencast video** of the OAuth flow. Say this plainly, per the issue: do not attempt a workaround.
- Prerequisites: LinkedIn Company Page, Developer app verified by a super admin of that page
- **`lifecycleState` only accepts `PUBLISHED` on create** — no native draft/scheduled state at all. Like Instagram, M8 compliance is entirely our own `approved_at` gate — calling `agents/distribution/linkedin.py`'s `upload()` at all IS Ariel's per-item approval taking effect; there is no lower-risk intermediate platform state to fall back to.
- Rate limits: Dev Tier defaults 500 req/app, 100 req/member; no published Standard Tier number
- Documents/native video supported via separate Documents/Videos APIs; organic carousel is **not** supported (sponsored-only)
- Doc: learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api, .../community-management-app-review

## One-page account setup checklist (for Ariel — do this once)

| Platform | What to create | Depends on |
|---|---|---|
| Instagram | IG Business/Creator account → link to a Facebook Page → complete Page Publishing Authorization → create Meta Developer app → submit for App Review (`instagram_business_content_publish`) + Business Verification | A Facebook Page must exist first |
| Facebook | Facebook Page (same one as above works) → Meta Developer app (same app as Instagram) → request `pages_manage_posts` | Same Meta app as Instagram |
| TikTok | TikTok Developer account → create app → add Content Posting API product, enable Direct Post → submit for App Review (`video.publish`) | Independent of Meta |
| X | **Decision needed, not just setup**: X has no free posting tier anymore ($0.015/post). Ariel must decide whether to accept per-post billing before any account work happens here. | Standalone decision |
| LinkedIn | LinkedIn Company Page (admin access) → LinkedIn Developer app tied to that page → submit Community Management API Development Tier access-request form (verified business email + org + domain) → later, Standard Tier form + screencast video | Company Page must exist and Ariel must be an admin |

Once any platform's credentials land in the vault (secret names: see each
adapter's `required_secrets` in `agents/distribution/<platform>.py`),
`scripts/social_token_health_probe.py` picks it up automatically on its
next scheduled run — no redeploy needed.

## Architecture

- `agents/distribution/base.py` — shared `PlatformAdapter` contract (`validate → build_payload → upload → verify → record`), `run_adapter_cli()` (NOT_CONFIGURED short-circuit + queue polling), `check_and_reserve_quota()`.
- `agents/distribution/{instagram,facebook,tiktok,x,linkedin}.py` — one per platform.
- `.claude/skills/linkedin-b2b-agent/SKILL.md` + `scripts/linkedin_b2b_agent.py` — LinkedIn's own voice/pillars/validator, entirely separate from the Bolt32 reel grammar.
- `public.social_content_queue` — reused (684 pre-existing rows audited, not migrated destructively), gained `variant_key`/`short_code`/`utm_source`/`utm_content`/`approved_at`/`approved_by` + `pending_approval`/`approved`/`not_configured` statuses (migration `20260903f`).
- `public.social_quota_ledger`, `public.social_token_health` — new, RLS enabled, no anon policy (migration `20260903f`).
- `public.create_platform_short_link()` / `public.resolve_reel_link()` — per-platform `/r/<code>` short links with `utm_source=<platform>`, `utm_content=<variant_key>`, reusing the existing `winnerdata.reel_links` + Cloudflare Worker `/r/:code` redirect infra from the Bolt32 reel pipeline (`reel_id` made nullable in follow-up migration `20260903g` so non-reel content like LinkedIn text posts can get a link too).
- `.github/workflows/cmo-factory-distribution-scheduler.yml` — polls the queue, dispatches each adapter, gated on the halt check (STOP file / `factory:halt` label / `spi_gates.gtm_factory_halt`) and `quota_gate_check('engineering')`.

## Known compliance fix bundled into this same PR

`supabase/functions/social-publish-worker/index.ts` (the pre-existing
LinkedIn-personal-profile worker, unrelated code path to the new company-
page adapter) published any `status='pending'` row **unconditionally**
the moment `linkedin_access_token` landed in the vault — its own code
comment read "No content review gate here by design." That is a live
M1/M8 violation: once OAuth completes, it would post to Ariel's *personal*
LinkedIn profile with zero human review. Fixed by adding
`.not("approved_at", "is", null)` to its query — same approval contract
as everywhere else in this lane. `target_platform='linkedin_personal'`
is left as-is (237 pending rows); re-pointing that worker at a company
page needs its own OAuth grant this session has no way to obtain.

## Non-goals (per issue, honored)

No public posts anywhere in this build (all 5 platforms structurally
cannot reach a live/public state without Ariel's `approved_at`). No
browser automation of any social platform. No Postiz. No second workflow
engine. No paid vendors (X ships disabled by policy pending a decision).
No personal-profile posting from the new LinkedIn agent. No connection/DM
automation.
