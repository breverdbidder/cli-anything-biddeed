# END-TO-END.md — GTM journeys (today-only)

Source: `docs/gtm/META.md` §6. This file is a **protected path** — see
`.factory/gtm/locks/floor.json`. The validator role reads this from `main`,
never from a PR branch.

Convention: each journey is marked `[LIVE — evidence below]` only if I
directly observed it working in this session (query output, grep hit,
running code path), or `[NOT YET — do not gate]` if any part of it is
aspirational. A journey with a live core but an unverified compliance
property is marked `[PARTIAL — do not gate on the unverified part]` and the
gap is stated explicitly. `factory/gtm/locks/floor.json`'s
`journey_assertions` count is the number of individually-checkable claims
below, not the number of journeys (5).

---

## Journey 1 — third-party win → D+1 reel

Claim: a third-party auction win on day D produces a reel in
`status='pending_approval'` by D+1, with a parcel outline on every aerial
frame, Street View, `eleven_v3` voice, no names, and a deal page returning
200 with an email-capture form.

**[PARTIAL — do not gate on the frame-level parcel-outline claim]**

- CONFIRMED: `winnerdata.biddeed_reels` has 23 rows, **all** `status =
  'pending_approval'` — verified live via `public.list_public_reels(true)`
  RPC in this session (`count 23`, `Counter({'pending_approval': 23})`).
  This proves the reel engine produces `pending_approval` output and that
  M1 (no auto-publish) is currently holding — nothing has left pending state.
- CONFIRMED: deal-page route exists (`/deal/{county}/{case}` per commit
  history for issue #19752) and is served by `src/worker.js`
  (`buildCountyPage` / deal-page handlers call `injectChatwootWidget` and
  render through `withPublicShell`).
- INFERRED (not directly observed this session): parcel-outline-on-every-
  frame, Street View compositing, and `eleven_v3` voice ID
  `TX3LPaxmHKxFdv7VOQHJ` are described in `docs/gtm/META.md` §3 as shipped
  in #19752 v2, but I did not render a video or inspect frame-by-frame
  output in this session — no video file was opened. Treat the *existence*
  of the 23 pending reels as LIVE evidence and the *frame-level rendering
  claim* as INFERRED from prior commit messages, not re-verified here.
- The D → D+1 timing claim is UNTESTED — no auction-win timestamp was
  correlated against a reel `created_at` in this session.

## Journey 2 — `/r/{code}` resolves and increments `reel_links.clicks`

**[LIVE — evidence below]**

- CONFIRMED: `src/worker.js` line ~2500 implements the `/r/` route by
  calling `public.resolve_reel_link` via PostgREST RPC
  (`${SUPABASE_URL}/rest/v1/rpc/resolve_reel_link`), with error logging via
  `logErr(env, '/r', ...)` on non-2xx.
  `supabase/migrations/20260902l_biddeed_reels_v2_rpc.sql:78` defines
  `resolve_reel_link(p_code text)` as a `SECURITY DEFINER` function, granted
  to `anon, authenticated, service_role`
  (`supabase/migrations/20260902l_biddeed_reels_v2_rpc.sql:105`), and the
  gallery-RPC migration's own comment
  (`20260902s_biddeed_reels_v2_gallery_rpc.sql:42`) explicitly distinguishes
  `resolve_reel_link` ("302s and increments clicks") from the read-only
  `get_reel_by_code` used by the player page — confirming click-increment is
  this function's designed behavior, not incidental.
- NOT independently re-verified in this session: I did not fire a live HTTP
  request against `/r/{code}` and diff `reel_links.clicks` before/after
  (would require a real short code and a live Worker deploy check, out of
  scope for a docs/DDL-only CP0 install). The code-path evidence above is
  strong but this is INFERRED-from-code, not an observed HTTP round trip.

## Journey 3 — daily digest: re-queried certified count, zero banned terms

**[NOT YET — do not gate]**

- CONFIRMED the digest renders and runs on schedule: `.github/workflows/
  biddeed-daily-digest.yml` has `schedule: cron: '0 10 * * 1-5'`, and
  `scripts/biddeed-daily-digest.cjs` (436 lines) queries live
  `multi_county_auctions` for the county snapshot.
- **FINDING, not a pass:** `scripts/biddeed-daily-digest.cjs:65-69` sources
  its gold-standard/certified badge from `gold_standard_scoreboard`
  (`.from('gold_standard_scoreboard').select('county_slug, gold_standard')
  .eq('gold_standard', true)`) — **not** `public.v_certified_counties`.
  `CC_META_PROMPT.md` §2.2 states explicitly: *"`gold_standard_scoreboard`
  is known-untrustworthy — never cite it as proof of anything."* This means
  the digest's county-count claim does not meet the re-query bar
  `docs/gtm/MISSION.md` §4 requires. This is exactly the kind of drift the
  factory exists to catch — logged here rather than silently gated as pass.
- **FINDING:** no banned-terms scan of any kind exists in
  `scripts/biddeed-daily-digest.cjs` — grepped for `certif|GOLD|gold|
  banned|vendor|Tracerfy` and the only hits are the (untrustworthy-source)
  gold badge above. "Zero banned terms" is currently true only by accident
  (nobody has put a vendor name in the template), not by enforcement.
  `factory/gtm/gate.py`'s `banned_terms` check is what would need to run
  against this template before this journey can be marked LIVE.

## Journey 4 — county SEO buy-CTA only on complete-coverage counties

**[LIVE — evidence below]**

- CONFIRMED: `src/worker.js` gates the S5-purchasable / buy-CTA state on
  **both** gold-certification and co_no-confirmation:
  - line ~930: fetches `v_certified_counties` (the correct SSOT, unlike
    Journey 3's digest) — `SUPABASE_URL + '/rest/v1/v_certified_counties?
    select=county_slug'`.
  - line ~938: separately fetches co_no-confirmed counties.
  - line ~946: comment `// S5-purchasable = both gold-certified AND
    co_no-confirmed`.
  - line ~1055-1059: per-county page also cross-checks
    `gold_standard_certifications` (`certified` column) directly and sets
    `isGold` from that live row, not a cached scoreboard.
  - line ~3265: template swap `COUNTY_CERT_BADGE_TEXT` renders `⭐ Gold
    Standard certified` only when `isGold` is true, else `⚠️ Data under
    review`.
- This is the one journey that already matches `docs/gtm/MISSION.md` §4's
  bar (live re-query, not a cached scoreboard) — worth noting as the
  reference implementation the digest (Journey 3) should be brought in line
  with.

## Journey 5 — Chatwoot script present iff token set, homepages 200

**[LIVE — evidence below]**

- CONFIRMED: `src/worker.js:1662-1674` — `injectChatwootWidget(html, env)`
  reads `env.CHATWOOT_WEBSITE_TOKEN_BIDDEED`; `if (!token) return html;`
  (no-op, ships dark, matches the function's own comment: *"No-ops (renders
  nothing) when the website token isn't bound yet"*). When the token is
  present, it injects a `<script>` snippet loading
  `{CHATWOOT_BASE_URL}/packs/js/sdk.js` before `</body>`.
  `injectChatwootWidget` is called on `/terms`, `/tos`, `/privacy`,
  `/disclaimer`, `/security`, `/data-retention`, the homepage handler, the
  buy-report page, county pages, the counties index, and blog pages — i.e.
  broadly wired across public routes, not just one page.
  Also confirmed the backend half of the Chatwoot integration shipped this
  session per `git log`: commit `9cfacc05 feat(19776): Chatwoot Agent Bot
  webhook — POST /support/bot (AI-only, no human handoff)`.
- NOT verified in this session: an actual HTTP `curl` against a live
  homepage URL returning 200 with the script tag present — this repo's
  checkout does not include a running deploy to curl against from this
  sandbox, and doing so was out of scope for a docs/DDL-only CP0 install.
  Code-path evidence is strong; live-HTTP 200 is UNTESTED here.

---

## Summary table

| # | Journey | Status | Gate on it? |
|---|---------|--------|-------------|
| 1 | win → D+1 reel, no publish | PARTIAL | gate on `pending_approval` invariant only, not frame-level rendering |
| 2 | `/r/{code}` resolve + click count | LIVE (code-path) | yes |
| 3 | digest: certified count + banned terms | NOT YET | no — digest sources from untrustworthy `gold_standard_scoreboard`, zero banned-terms enforcement |
| 4 | county SEO buy-CTA gating | LIVE | yes |
| 5 | Chatwoot token-gated widget | LIVE (code-path) | yes |

`factory/gtm/locks/floor.json.journey_assertions` = 11 (the individually
checkable CONFIRMED/FINDING claims enumerated above: J1 has 2 confirmed +
1 finding-boundary, J2 has 1 confirmed, J3 has 1 confirmed-render + 2
findings, J4 has 1 confirmed (5 sub-facts collapsed to 1 assertion), J5 has
1 confirmed + 1 commit-evidence — total 11 distinct evidence-backed
statements above the "NOT YET" line).
