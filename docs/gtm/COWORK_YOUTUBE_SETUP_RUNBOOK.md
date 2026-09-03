# COWORK RUN-BOOK — BidDeed.AI YouTube channel + OAuth
> **STATUS: EXECUTED 2026-09-03 (Ariel, guided by Claude Cowork).** Channel `BidDeed AI` / `@biddeedai` / `UCzI93Hf1RCtja1UdCtgzfEQ` live; OAuth app `BidDeed Publisher` **In production**; the three vault secrets exist and resolve via `get_vault_secret_mcp`. Part F passed: channels.list(mine) → BidDeed AI; two token refreshes 65 s apart OK; yt-analytics resultTable OK; private test upload `ORTZjYLruaQ` (32.000 s bolt32) uploaded and deleted (HTTP 204). Corrections learned during execution are marked **[CORRECTED]** below.

**Hand this whole file to Claude Cowork.** It drives Ariel's logged-in browser. Everything here is a click path with the exact value to type. Ariel touches the keyboard only three times (marked KEY).

Two constraints that decide the design — verified Sep 3 2026, do not "optimise" around them:
- A video upload costs **1,600 quota units**; the default project quota is **10,000/day** -> **6 uploads/day maximum**.
- If the OAuth app is left in **Testing** mode, the refresh token **dies after 7 days**. External + **Production** is the only configuration that yields a permanent token on a Gmail/Brand account. Publishing the app is not optional.

## PART A — CHANNEL
A1. youtube.com — confirm the signed-in account is the one that should own this channel. KEY: hand the keyboard to Ariel at any password or 2FA prompt.
A2. **[CORRECTED]** youtube.com/channel_switcher -> Create a channel. YouTube now shows the same "How you'll appear" dialog for both paths; when the account already has a personal channel (it lists one on the All channels page), the new one is a Brand Account. Original text: youtube.com/account -> Create a new channel -> choose the **Brand Account / business-or-other-name** path (NOT the personal channel). A Brand Account can be transferred, co-managed and moved into the company later; a personal channel is welded to Ariel's identity. If the flow does not offer it, STOP and report — do not create a personal channel as a substitute.
A3. Fill from PART D: name, handle, description, links.
A4. Settings -> Channel -> Advanced: country United States; audience "No, set this channel as not made for kids".
A5. Settings -> Channel -> Feature eligibility -> verify phone (needed for custom thumbnails and 15+ min videos). KEY: the SMS code is Ariel's.
A6. Report back the exact handle accepted and the Channel ID (Settings -> Advanced settings, starts UC).

## PART B — GOOGLE CLOUD + OAUTH
B1. console.cloud.google.com -> select the EXISTING project **ZoneWise**, id gen-lang-client-0704450208 (billing already linked). Do not create a new project.
B2. Enable **YouTube Data API v3** and **YouTube Analytics API**. Confirm both read "API enabled".
B3. OAuth consent screen (or Google Auth Platform -> Branding/Audience): User type **External**; App name `BidDeed Publisher`; support + developer contact = Ariel's email; add scopes youtube.upload, youtube, yt-analytics.readonly; add Ariel as a test user.
B4. **THE STEP THAT BREAKS EVERYTHING IF SKIPPED** — **[CORRECTED]** Publish app stays greyed until Branding has: home page `https://biddeed.ai`, privacy policy `https://biddeed.ai/privacy`, terms `https://biddeed.ai/terms`, authorized domain `biddeed.ai`, developer contact email. Fill those, Save, then click **PUBLISH APP** so publishing status reads **In production**, not Testing. Testing = silent death in 7 days with invalid_grant. Screenshot the "In production" state.
B5. **[CORRECTED]** Clients -> Create client -> **Web application** (NOT Desktop app — Desktop clients have no redirect-URI field, so C3 is impossible) -> name `biddeed-publisher-web` -> Authorised redirect URI exactly `https://developers.google.com/oauthplayground` -> Create -> Download JSON. Keep local, never commit.

## PART C — REFRESH TOKEN
C1. developers.google.com/oauthplayground
C2. Gear icon -> tick "Use your own OAuth credentials" -> paste Client ID + secret -> OAuth flow Server-side, Access type **Offline**, Force prompt Consent if shown.
C3. **[CORRECTED]** Already done in B5 (redirect URI is set at client creation on the Web application client). Without it, C4 fails with redirect_uri_mismatch.
C4. Playground Step 1: paste the three scopes -> Authorize APIs -> choose the channel's account. KEY: Ariel clicks Continue. An "unverified app" warning is expected — Advanced -> Go to BidDeed Publisher (unsafe) -> continue. It is our own app; Google has simply not reviewed it.
C5. Step 2: Exchange authorization code for tokens. Copy the **Refresh token** (starts 1//).
C6. Report youtube_client_id, youtube_client_secret, youtube_oauth_refresh_token **in the Claude chat** — never in a GitHub issue or commit; issue bodies and run logs are readable by the runner. If Cowork has the Supabase MCP connected it may write them to the vault directly under those exact names and report only "written, not printed".

## PART D — CHANNEL IDENTITY
Name: `BidDeed AI` **[CORRECTED]** — YouTube rejects `BidDeed.AI` ("This name can't be used": dot-TLD names read as domains). The handle carries the brand: `@biddeedai`.
Handle: `@biddeedai` — if taken, in order: `@biddeed`, `@biddeedauctions`, `@biddeedai_fl`
Banner tagline: `REAL AUCTIONS. REAL NUMBERS. EVERY DAY.`
Description:
Every weekday we break down what actually sold at Florida's foreclosure and tax deed auctions — the opening bid, the judgment, the assessed value, and what it really went for.
No hype, no guru course. Just the numbers off the courthouse record, with the parcel on the map.
See the full breakdown for any property at biddeed.ai
Links: biddeed.ai first and primary. Banner 2560x1440, safe area 1546x423 centred.
Compliance (public surface, non-negotiable): no homeowner-directed language; no foreclosure- or mortgage-relief framing; no person's name anywhere; no county count, accuracy percentage, model score, or revenue/subscriber claim — every public number must be re-queryable from the database; no vendor or internal tool names.

## PART E — WHAT CLAUDE DOES WHEN THE TOKEN LANDS
Already built and dormant: resumable upload lane with a 6/day quota ledger, token-health alarm, description builder whose first line is the bare UTM'd deal link, pinned-comment template, and the Analytics fetcher that replaces the internal watch-proxy with real average view duration. Every upload is private and pending Ariel's approval; no code path sets a video public.

## PART F — VERIFICATION CLAUDE RUNS AFTERWARD
1. channels.list(mine=true) returns the channel ID and title.
2. A token refresh executed twice, 60+ seconds apart — proves the app is genuinely in Production and the refresh token is durable.
3. yt-analytics returns a result set without an auth error.
4. One private test upload of a 32-second reel, then deleted, with the video ID recorded.
