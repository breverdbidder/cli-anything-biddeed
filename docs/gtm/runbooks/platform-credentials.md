# Platform credential inventory + one-session runbook (GTM-0, #20029)

**VERIFIED live Sep 5 2026** via `select name from vault.secrets`, `gh secret list --repo breverdbidder/cli-anything-biddeed`, and `select * from public.social_token_health` (populated by `scripts/social_token_health_probe.py` against each adapter's `required_secrets` in `agents/distribution/*.py`). No secret values were read or printed — names and health-probe booleans only.

## Table 1 — what exists today

| Platform | Vault secret(s) required | Present in vault? | Present as GH secret? | `social_token_health` |
|---|---|---|---|---|
| YouTube | `youtube_client_id`, `youtube_client_secret`, `youtube_oauth_refresh_token` | **YES** (all 3) | n/a (Worker/GHA reads from vault) | `youtube_token_health.ok=true` as of 2026-09-04 (not in `social_token_health`, has its own table) |
| Instagram Reels | `instagram_access_token`, `instagram_business_account_id` | NO | NO | `healthy=false`, `NOT_CONFIGURED — missing vault secret(s) ['instagram_access_token', 'instagram_business_account_id']` |
| Facebook Page Reels | `facebook_page_access_token`, `facebook_page_id` | NO | NO | `healthy=false`, `NOT_CONFIGURED — missing ['facebook_page_access_token', 'facebook_page_id']` |
| TikTok | `tiktok_access_token` | NO | NO | `healthy=false`, `NOT_CONFIGURED — missing ['tiktok_access_token']` |
| X (Twitter) | `x_access_token` | NO | NO | `healthy=false`, `NOT_CONFIGURED — missing ['x_access_token']`. **Policy note:** `agents/distribution/x.py` ships `daily_cap_default = 0` regardless — X retired free posting Feb 6 2026 ($0.015/post, $0.20 if it contains a URL); do not treat "get a token" as sufficient, Ariel must accept per-post billing first. |
| LinkedIn Company Page | `linkedin_company_access_token`, `linkedin_organization_urn` | NO | NO | `healthy=false`, `NOT_CONFIGURED — missing ['linkedin_company_access_token', 'linkedin_organization_urn']` |
| Typefully (founder LinkedIn drafts) | `typefully_api_key` | NO (searched `vault.secrets` for `%typefully%` — zero rows) | NO | n/a — not probed by the distribution lane; used only by the founder-ghostwriter draft path |

Note: GH secrets do include `LINKEDIN_EMAIL` / `LINKEDIN_PASSWORD` / `LINKEDIN_LI_AT` / `LINKEDIN_SESSION_JSON`. Those belong to a **different, pre-existing** tool (`linkedin/vendor/linkedin_scraper` — read-only post extraction via a logged-in browser session cookie) and are unrelated to, and must not be reused for, the Company Page Posts-API adapter above. `DISTRIBUTION_LANE.md` already flags that scraper as an open compliance finding (GPL-3.0 + ToS risk) separate from this issue's scope.

## Table 2 — what each platform needs before a token can exist (one-time, Ariel)

| Platform | Setup path | Blocking prerequisite |
|---|---|---|
| Instagram | IG Business/Creator account → link to a Facebook Page → complete Page Publishing Authorization → create Meta Developer app → App Review + Business Verification for `instagram_business_content_publish` | A Facebook Page must exist first |
| Facebook | Same Facebook Page as above → same Meta Developer app → request `pages_manage_posts` | Same Meta app as Instagram — do Instagram+Facebook in one Meta session |
| TikTok | TikTok Developer account → create app → add Content Posting API product → enable Direct Post → submit App Review for `video.publish` | Independent of Meta; App Review takes days–2wks, unaudited apps post `SELF_ONLY` (private) in the meantime — safe to request now, nothing goes public before review clears **and** an LMS approval exists |
| X | **Decision, not setup**: no free tier since Feb 6 2026. Ariel must decide to accept $0.015/post ($0.20 w/ URL) before any account work | Standalone go/no-go — do not spend time on this platform until decided |
| LinkedIn Company Page | LinkedIn Company Page (Ariel admin) → LinkedIn Developer app tied to that page → submit Community Management API **Development Tier** access-request form (verified business email + org + domain) → later, Standard Tier form + a screencast video of the OAuth flow | This is a *Vetted Product*, not self-serve — expect a multi-day approval, not a 15-minute click path like YouTube |
| Typefully | typefully.com → connect Ariel's personal LinkedIn account (drafts only, Ariel taps publish) → generate API key → hand to Claude to write `typefully_api_key` into the vault | None — this is the fastest one to close and unblocks deliverable 7's Typefully-draft path instead of the `social_content_queue` fallback |

## Recommended order for Ariel's one 15-minute session (fastest unlock first)

1. **Typefully** (~3 min) — connect LinkedIn, copy API key, hand it to Claude. Unblocks real Typefully drafts for the 3 founder posts in this issue instead of the `social_content_queue` fallback.
2. **Meta Business (Instagram + Facebook)** (~10 min to start, App Review is asynchronous) — create/confirm the Facebook Page, create one Meta Developer app, request both scopes in the same session. Nothing publishes until App Review clears *and* an LMS approval exists (M8), so starting the review clock now costs nothing.
3. **TikTok** (~5 min to start) — create developer account + app, enable Direct Post, submit for `video.publish` review. Same "start the clock, nothing goes live yet" logic.
4. **LinkedIn Company Page API** — only after the Company Page itself exists and Ariel is its admin; the Development Tier form is the long pole (expect days), so file it this session even though nothing else in GTM-0 depends on it.
5. **X** — hold. This is a spend decision (per-post billing, no free tier), not a credential gap. Revisit after the funnel has revenue data to justify $/post economics; `agents/distribution/x.py`'s `daily_cap_default = 0` will keep it off even if a token appears.

Until any of these land, **variants publish to YouTube only** — this matches `GTM_SOP_v1.md` §7 ("until then variants go to YouTube only") and is not a gap this session can close without Ariel's manual account/App-Review actions above.
