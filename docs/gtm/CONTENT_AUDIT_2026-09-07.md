# CONTENT AUDIT — biddeed.ai, page by page and tab by tab

Date: 2026-09-07 · Issue: [#20081](https://github.com/breverdbidder/cli-anything-biddeed/issues/20081) · Owner: Ariel Shapira
Executor: CC (cli-anything-biddeed dispatch, issue #20081)

## Canon sources used for every verdict below

- `unified_context` (Supabase, live query 2026-09-07): `biddeed_content_voice_v2` (project `biddeed`, category `canon`), `m7_founder_carveout_sep3` (category `brand_canon`), `biddeed_tagline_v1` (category `positioning`).
- `docs/gtm/BIDDEED_VOICE_CONTENT_META_PROMPT_v2.md` (the file `biddeed_content_voice_v2` machine-copies).
- `docs/gtm/MISSION.md` §2 (9-item never-list).
- Live fetch of `everestcapitalusa.com` (2026-09-07) — used only to settle the Lakewood number conflict (§3 below).
- `docs/spec/20029.md` — prior session's reconciliation of the same track-record figures (found mid-audit; corroborates, did not fix the live copy).

Hero stack (canon, exact order): (1) "THE BEST PRICES IN US REAL ESTATE ARE SET AT FORECLOSURE AND TAX DEED AUCTIONS." (2) "Our data is your unfair advantage at every US county auction." (3) "We fought in the trenches for over two decades so you don't have to." Short forms: "EVERY FORECLOSURE. EVERY TAX DEED. YOURS TO WIN." · "OUTBID THE GUESSWORK." · "For Everyone. Everywhere." Retired: "Know your number before the gavel."

Verdict key: **PASS** (matches canon) · **OFF-CANON** (wrong wording/number, fixable by copy edit) · **NON-COMPLIANT** (violates a MISSION never-list item or M7) · **N/A** (no user-facing copy on this route).

---

## 1. Worker routes (`src/worker.js`, cli-anything-biddeed)

| Route | Current copy (key elements) | Verdict | Citation |
|---|---|---|---|
| `/counties` | H1 "Florida Auction Intelligence by County"; nav CTA "Investor $99/mo"; footer standard legal nav. `worker.js:6393-6399` | **PASS** | No canon phrase required here (index page); no forbidden terms; pricing matches PLANS ($99/mo Investor, biddeed-web `LandingSections.tsx`) |
| `/county/:slug` (×67, shared `COUNTY_PAGE_TEMPLATE`) | "Shapira Bid Card", "Shapira Formula", "Shapira Triangle" branding throughout; "SIGNAL$ Max Bid" / "SIGNAL$ Property Report" naming; grade filter bands; `worker.js:8564-9383` | **PASS** | "Shapira Max Bid" (the retired phrase) does not occur — product-facing formula name is correctly "SIGNAL$ Max Bid". Using "Shapira" as a formula/tool brand name (not naming a buyer/owner) is consistent with the M7 carve-out (`m7_founder_carveout_sep3`), which permits Ariel Shapira's name publicly. SIGNAL$ is consistently all-caps with `$`. |
| — same, minor finding | Checkbox label hardcodes a live-looking count: "Unknown street addresses (**31** deals)" `worker.js:8884-8958` | **OFF-CANON (minor)** | MISSION never-list #7: "no unverified numbers in copy." This is a UI filter label, not marketing copy, but the literal `31` is not computed from a query at render time the way every other count on the page is (`{N}`, `{count}`). Recommend: replace with a live-computed count or drop the parenthetical. Not PR'd — needs an engineering change to the filter-sheet data binding, not a copy edit. |
| `/blog` + posts | Index H1 "Guides & Case Studies"; per-post legal disclaimer verbatim across all 6 posts: "This is general educational information, not legal, financial, or investment advice..."; CTA "Get a SIGNAL$ Property Report — $25 →"; `worker.js:5261-6326` | **PASS** | Consistent disclaimer, correct SIGNAL$ naming, no forbidden terms, no person names other than none at all. |
| `/answers/:slug` (8 live slugs, DB-driven via `get_published_content`/`list_published_content_slugs`) | Titles: Deposits & Payment, Foreclosure vs. Tax Deed, How Max Bid Is Calculated, Redemption, Surplus Funds, What Happens After You Win, What Survives a Foreclosure Sale, What Survives a Tax Deed Sale | **PASS** | Live-queried 2026-09-07 (`list_published_content_slugs` RPC → 8 rows; `get_published_content` per slug scanned for banned terms — zero hits on Mariam / enterprise grade / 14 patents / Shapira Max Bid / retired tagline / 28,100). This is exactly the canon C3 answer-asset checklist (`BIDDEED_VOICE_CONTENT_META_PROMPT_v2.md` §C3), live and populated. |
| `/terms`, `/tos` (alias) | Full ToS, last updated Jul 28 2026, §1-10, `worker.js:10257-10293` | **PASS** | No canon conflicts; correctly hedged ("not legal advice", independent-verification language matches Disclaimer). |
| `/privacy` | Full policy, last updated Jul 28 2026, `worker.js:10295-10333` | **PASS** | Names real sub-processors (Stripe, PostHog, Supabase, Cloudflare, Anthropic) — no vendor-name violation (MISSION #4 bans vendor names in *public media/marketing*, not in a legally-required privacy disclosure of who processes data; this is the standard carve-out every SaaS privacy policy needs). |
| `/disclaimer` | Full disclaimer, last updated Jul 28 2026, `worker.js:10335-10363` | **PASS** | Matches the blog/answer-page disclaimer language verbatim; no unverified numbers. |
| `/data-retention` | Full retention table, last updated Aug 3 2026, `worker.js:10365-10417` | **PASS** | Cites real statute (FS 501.171), real retention windows, no invented numbers. |
| `/security` | Full page, `worker.js:10421-10508` | **PASS** | Explicitly non-inflated ("No fake badges"), states real RLS coverage ("723 of 728 tables, 99% — verified by direct query"), discloses open gaps (CSP inline-script item, legacy vault-read function) rather than hiding them. Exemplary honesty-protocol compliance. |
| `/contact` | 301 redirect to `/support`, no content of its own | **N/A** | — |
| `/buy-report` + sub-steps | "SIGNAL$ Property Report" naming, $25 price, 18-feature list, legal fine print; `worker.js:8202-8543` | **PASS** | Consistent naming/pricing with `/county/:slug` and biddeed-web PLANS. |
| `/subscribe` + sub-steps | Tier pricing pulled from `TIER_LABEL`/price vars; "Try 67 counties free" CTA; `worker.js:8082-8152` | **PASS** | $99/mo Investor consistent across worker + biddeed-web. |
| `/free-report` + delivery | Real opt-in checkboxes ("Send me the daily auction digest by email" / "Text me urgent auction alerts (SMS)"), server-enforced "check at least one" rule; `worker.js:2196-2320` | **PASS** | This is the one capture point site-wide with genuine, unbundled affirmative consent UI for both channels — flagged in the companion consent audit as the reference pattern the rest of the site should match. |
| `/pioneers`, `/pioneers/join` | "$990/yr Pioneer" copy; code comment explicitly forbids wiring to Stripe/SAFE until legal review; `worker.js:6055-6165, 4007-4086` | **PASS** (copy) | No canon violation in the visible copy. (Consent gap — server hardcodes `marketing_consent:true` — is a CONSENT finding, not a content/canon finding; see companion doc.) |
| `/reels`, `/reels/:code` | Minimal card copy, "PREVIEW MODE" banner on unapproved reels; `worker.js:5953-6052` | **PASS** | No canon violation. Recommend confirming (outside this audit) that `pending_approval` reels are structurally unreachable by an unauthenticated crawler/social scraper, matching the M1 approval-gate intent. |
| `/deal/:county/:case` (postsale + presale) | H1s, stat labels, "Get the full property signal report" / "Get notified before the gavel drops" CTAs; `worker.js:5493-5815` | **PASS** (copy) | No banned phrase, no invented numbers, masked-placeholder pattern (`$•••,•••`) for locked sections is honest (doesn't fake a number). Consent-copy gap on the same page is a CONSENT finding (§ companion doc), not a canon violation. |
| `/report/:id` | Full SIGNAL$ report renderer; explicit "SKIP — UNLOCATABLE" / "An estimate here would be fabrication" fallbacks; `worker.js:1210-1410+` | **PASS** | Exemplary honesty-protocol compliance — the report code path visibly refuses to fabricate a number rather than defaulting to a guess. |
| `/order`, `/success`, `/report-success` | `/order` and `/success` are proxied to biddeed-web (`worker.js:2952-2980`); a local `/success` block and `REPORT_SUCCESS_HTML` constant exist but are dead code (unreachable due to route order / never wired to a path) | **FINDING (technical, not content)** | Not a canon issue — flagging because `EXIT_EXCLUDED_PATHS` (`worker.js:10186`) references `/report-success` as if it were a live destination. Recommend a follow-up engineering ticket (out of scope for a copy PR) to either wire `/report-success` or remove the dead `REPORT_SUCCESS_HTML` constant and the stale reference. |
| `/section18-teaser` | OG title/description referenced a "$431K Naples Deal" / "$381K" equity that matched no on-page content (on-page case is Palm Beach/Delray Beach, $329K ceiling, $50K sale, ~$335K equity) | **OFF-CANON → FIXED** | MISSION #7 (no unverified numbers). **Fixed in PR [#20083](https://github.com/breverdbidder/cli-anything-biddeed/pull/20083)** — OG tags now match the page's own substantiated figures. |
| `/proof/marion-summerfield` | Single seeded, verified case; code comment explicitly instructs against synthesizing additional cards; `worker.js:5415-5486` | **PASS** | Exemplary — matches MISSION #7 by construction. |
| `/chat` (+ `/chat/api*`) | Full chat shell copy, disclosure bar "Informational only — not legal, financial, or investment advice.", "70+ languages" claim; `worker.js:6405-6784` | **PASS**, with one flag | "Talk or type in 70+ languages" (`worker.js:6717`) — this session did not independently test multilingual output quality; tag as **UNTESTED**, not a canon violation, but worth a real verification pass before it's repeated in ad copy. |
| `/unsubscribe` | Honest, plain-language copy: "You have been unsubscribed and will not receive further marketing emails..." with a human-fallback message on failure; `worker.js:3170-3194` | **PASS** (copy) | Whether the underlying RPC actually feeds the two new suppression tables is a CONSENT finding, not a copy finding — see companion doc. |
| `/support`, `/discover`, `/radar`, `/alerts`, `/sign-in`, `/sign-up` | Proxied to biddeed-web (`worker.js:2956-2980`) — no Worker-owned copy | **N/A** (audited under biddeed-web below) | |
| `/referral/code`, `/deal/visitor` | JSON APIs, no HTML | **N/A** | |

**Global string sweep across `src/worker.js`** (repo-wide grep, 2026-09-07): zero hits for `28,100`/`28100`, `Lakewood`, `enterprise grade`/`enterprise-grade`, `Shapira Max Bid` (exact phrase), `Know your number before the gavel`, `14 patents`, `Mariam`. The retired tagline and every named forbidden phrase have already been fully purged from this codebase.

---

## 2. App routes (`biddeed-web`, Next.js)

| Route | Current copy (key elements) | Verdict | Citation |
|---|---|---|---|
| `/` hero | Exact canon hero stack, three lines, correct order: `components/deed-home/DeedHome.tsx:97,100,103` | **PASS — exemplary** | Byte-for-byte match to `biddeed_content_voice_v2` hero_stack. |
| `/` Founder section | "Ariel Shapira · Founder · Developer · Builder · Property Manager · Inventor of ZoneWise.AI · The Real Estate AI Oracle™" (`LandingSections.tsx:135`); "pending provisional patent application; nothing here is issued" (`:415`); Rainsville $5,330→$398,600 (correct) + **Lakewood $28,100 (wrong)** →$320,000 | **OFF-CANON → FIXED** | Role list matches M7 (`m7_founder_carveout_sep3.ariel_public_roles`) exactly. Patent phrasing matches canon guidance exactly ("provisional patent application, 14 claims... background only" — this copy doesn't even state the claim count, which is the safest possible phrasing). Mariam is never named (confirmed, repo-wide grep). **The $28,100/$1,756-a-door Lakewood figures were wrong — canon and a live fetch of everestcapitalusa.com both say $20,100 entry, $1,256/door. Fixed in PR [#55](https://github.com/breverdbidder/biddeed-web/pull/55).** See §3 below for the full reconciliation. |
| `/` PLANS section headline | **"Cheaper than one bad bid."** `LandingSections.tsx:297` | **OPEN DECISION — see comment on issue #20081**, not fixed in a PR per the issue's own instruction ("anything needing Ariel's taste goes in the audit doc as a recommendation, NOT into a PR") | Ariel flagged this line directly. 3 replacement options + a recommendation are given in the issue comment and in §4 below. |
| `/` PLANS tiers | Free $0 / Investor $99/mo ("Most chosen") / Pro $199/mo / Pro Plus $299/mo / standalone SIGNAL$ Report $25; `LandingSections.tsx:232-386` | **PASS** | Consistent with worker.js pricing everywhere it's referenced. No "enterprise grade" anywhere (only a plain "Enterprise" value inside an unrelated support-ticket category dropdown, which is not customer-facing marketing copy and not the banned phrase). |
| `/` "How it works" | H2 "OUTBID THE GUESSWORK." `LandingSections.tsx:169` | **PASS** | Exact canon short-form, correctly used as the product line (not merged with the hero, not used as the primary headline) per canon's "use together, never merged" rule. |
| `/` proof section | Marion County $82,000 max-bid vs $73,501 sale, "clerk's recorded sale" citation; `LandingSections.tsx:83-119` | **PASS** | Matches `worker.js` `/proof/marion-summerfield` numbers exactly (72,100 entry not shown here, but the $82,000/$73,501 pair is identical across both surfaces — cross-checked). |
| `/radar` (+ calendar, map, spreadsheet views — same route, tab/view-switcher, not separate URLs) | H1 "Auction Intelligence"; fine print "Shapira Formula™ · (ARV × 70%) - Repairs - $10K - MIN($25K, 15% ARV)" `AuctionDetail.tsx:367` | **PASS** | Formula text matches the internal deal-analysis formula exactly (CLAUDE.md `deal_analysis` trigger: `(ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)`). No forbidden terms. |
| `/discover` | H1 "Find the next auction worth your attention."; empty state explicitly refuses to show an unsourced table: "No result table is shown without source-backed records..." `DiscoveryPage.tsx:92,153` | **PASS — exemplary** | The empty-state copy is itself a MISSION #7 compliance control (refuses to render numbers it can't source). |
| `/alerts` | H1 "Stay ahead of the auction clock."; consent copy: "Email delivery requires a separate confirmed consent record. Informational only—this is not legal, financial, or investment advice." (`AlertDashboard.tsx:185`); skip-trace consent checkbox: "I confirm that I have a documented permissible purpose and consent basis for this request." (`SkipTracePanel.tsx:9`) | **PASS** (copy) | Good compliance-forward language. Whether a "confirmed consent record" is actually created and enforced anywhere is a CONSENT finding — see companion doc §5. |
| `/support` | H1 "How can we help?"; "We only use your email to answer this request. See our Privacy Policy." `SupportForm.tsx:202-205` | **PASS** | Minimal, honest, unbundled data-use statement. |
| `/sign-in`, `/sign-up` | Clerk-hosted components, no app-authored copy; fallback if unconfigured: "Sign-in is not configured on this deployment" | **N/A / PASS** | No canon-relevant copy to judge. |

**Global string sweep across biddeed-web** (repo-wide grep, excluding `node_modules`/`.next`, 2026-09-07): zero hits for `enterprise grade`/`enterprise-grade`, `Shapira Max Bid`, `Know your number before the gavel`, `14 patents` (repo explicitly instructs its own AI system prompt at `lib/deed/context.ts:108`: "never state a claim count and never say anything is issued or patented"), `Mariam`. One hit each for `28,100` and `Lakewood` (the fixed line) and one exact hit for `Cheaper than one bad bid` (the open decision).

---

## 3. Canon conflict resolved: Lakewood entry price

**Question:** was it $20,100 (canon meta-prompt) or $28,100 (Ariel's stated figure per the issue body)?

**Finding: $20,100 is correct; $28,100 was the error.**

- `unified_context.biddeed_content_voice_v2` / `docs/gtm/BIDDEED_VOICE_CONTENT_META_PROMPT_v2.md` line 60: "$20,100 two lots → 16-unit multifamily entitled pad sold $320,000."
- Live fetch of `everestcapitalusa.com` (2026-09-07), the company's own published track record: **1581 & 1591 Lakewood Drive NE, Palm Bay, FL** (Lots 5 & 6, Block 5, Palm Bay Homes Subdivision), Brevard tax deed auction **2022-01-20**, entry **$20,100**, exit **$320,000**, described on the site itself as "the headline transaction in the Everest Capital track record."
- A prior CC session (`docs/spec/20029.md` §8, 2026-09-05/06) independently reached the same conclusion reconciling a different issue's figures ("$28,100" appears nowhere in canon; "$20,100" does) but did not touch the live copy — this is the first session to trace it to the actual rendered page and fix it.
- Both sources agree on the $320,000 exit; only the entry price and its derived per-door figure ($1,756 vs the corrected $1,256) were wrong.
- **Not independently verified:** the Brevard County Clerk's raw instrument number for this specific parcel (the site publishes instrument numbers for the other 12 track-record entries but not for this one). If Ariel wants instrument-number-level proof, that requires a direct Brevard Clerk Official Records search — out of scope for this session's cost/time budget given two independent canonical sources already agree.

**Fixed:** `components/deed-home/LandingSections.tsx:142` in biddeed-web, PR [#55](https://github.com/breverdbidder/biddeed-web/pull/55).

### 3a. Addendum — a second, concurrent PR reached the opposite conclusion with a fabricated citation

Mid-session, `git fetch` surfaced PR **[#20082](https://github.com/breverdbidder/cli-anything-biddeed/pull/20082)** — merged 2026-09-07T02:05:59Z, filed under this same issue's lane — which had changed the canon doc from $20,100 **to $28,100**, citing "recorded tax deed file 160654, OR Book 7806 / Page 1987, Brevard County, Jan 27 2017."

That citation does not verify. A raw `curl` fetch of `everestcapitalusa.com`'s HTML (deliberately bypassing any LLM-summarization layer, to eliminate hallucination risk) contains the literal string `20,100` for this exact deal and **zero** occurrences anywhere on the page of `28,100`, `160654`, or `7806`. The page's own text: "Two vacant lots (Lots 5 & 6, Block 5, Palm Bay Homes Subdivision) acquired at the Brevard tax deed auction **January 20, 2022** at **$20,100**... sold April 24, 2026 for $320,000." Parcel 28-37-22-01-5-5. None of PR #20082's specifics — the instrument number, the OR Book/Page, or the 2017 date — appear anywhere on the source it cited. PR #20082's own corroboration claim ("the live homepage already carries $28,100") also doesn't hold up as independent evidence: that was the same wrong number this audit found and fixed on the live homepage (§ above), not a second source.

**Corrective action taken this session:**
- Logged a CRITICAL honesty-protocol violation: `public.honesty_violations` id `bc98d02f-9792-4f59-a25b-4490c59cc452`.
- Opened PR [#20086](https://github.com/breverdbidder/cli-anything-biddeed/pull/20086) reverting the canon doc to $20,100, with the verified address/parcel/date details in place of the fabricated instrument citation.
- Did not re-open or comment on PR #20082 itself (out of this session's scope — the corrective PR speaks for itself and is the actionable artifact).

This is presented as a factual finding, not speculation about who or what produced PR #20082 — this session has no visibility into whether it was a different concurrent dispatch on the same issue, a different issue's dispatch that cross-filed under this lane, or something else. What's verifiable is only the merged diff, its citation, and that citation's failure to appear on the page it names as its source.

---

## 4. Decision 1 — PLANS headline replacement ("Cheaper than one bad bid.")

Ariel flagged `"Cheaper than one bad bid."` (`LandingSections.tsx:297`, the PLANS section H2) as a decision this lane owns, not a taste call to make ad hoc. Same reasoning that retired "Know your number before the gavel": it's dread-framed (the sentence's whole logic runs through the fear of a *bad* bid, not the pull of a *good* one), and it's tool-before-category (leads with "cheaper," a price defense, not with the auction itself).

**Three replacements, in canon voice (category first, enthusiasm over dread, per `BIDDEED_VOICE_CONTENT_META_PROMPT_v2.md` §"Voice spec"):**

1. **"One bad bid costs more than a year of this."** — keeps the price-comparison logic Ariel's original had (this is presumably why he wrote it — PLANS sections need a value anchor), but flips it to lead with the stakes of the auction, not a defensive "cheaper than." Still uses "bid" so it doesn't require new user education.
2. **"Every plan pays for itself at your first auction."** — pure upside framing, no dread language at all, states the ROI logic PLANS sections exist to make ("this is worth it") without invoking a loss.
3. **"Priced for people who actually show up to bid."** — leans on the enthusiasm-for-the-category energy the whole voice doc calls for ("we sell to bidders"), implicitly contrasts with tourists/lookers rather than with a hypothetical bad outcome.

**Recommendation: #1, "One bad bid costs more than a year of this."** It's the smallest edit to Ariel's original intent (same "bad bid" price-anchor logic he clearly wanted) while removing the passive, defensive "cheaper than" framing that mirrors the exact problem "before the gavel" had — it also reads faster as a PLANS-section H2 (7 words vs. option 2's 8, option 3's 9) and keeps "bid" as the operative noun, matching every other CTA on the page ("Start Investor," "Get a report"). Ariel decides; not shipped in a PR per the issue's own rule that taste calls stay in the doc.

---

## 5. Decision 2 — status-hue question

The canon palette is 7 colors, no green/red/amber: `#005EB8 #004A92 #0A2540 #1A1A1A #E6F0FA #D7E3F1 #FFFFFF` (deployed and verified on 23/23 routes per the issue's own framing). biddeed-web's own token file makes this explicit:

> `lib/design-tokens.ts:4-6`: "This is the ONLY file besides `app/globals.css` that may carry a colour literal (PARITY_PRD.md §4 change control; `scripts/palette-gate.mjs` enforces it)."

Confirmed live: `AuctionDetail.tsx`, `AuctionTable.tsx`, `AuctionSpreadsheet.tsx`, and `AuctionMap.tsx` all color BID/REVIEW/SKIP status purely from the existing brand tokens (`brand`/`navy`/`tint` family) via inline `style={{backgroundColor}}` — **zero** `text-green-*`/`text-red-*`/`text-amber-*` Tailwind classes exist anywhere in the repo today. A delta value like "9% below assessed value" is currently rendered as plain text with brand-color badges for discrete status buckets (BID/REVIEW/SKIP), not a continuous red-green scale for the number itself.

**The tradeoff, stated plainly:**
- **Words-only (status quo):** zero engineering cost, zero palette-gate risk, zero risk of an accidental W3C-contrast or colorblind-accessibility regression. Cost: a delta like "9% below assessed value" reads as a fact, not a signal — a user scanning a table has to read every cell rather than pattern-match a color.
- **One released status hue (8th color):** lets BID/REVIEW/SKIP (or a magnitude scale) be scanned at a glance, which is a real UX gain on `/radar`'s table/spreadsheet views specifically (dozens of rows, high scan-cost today). Cost: touches `scripts/palette-gate.mjs`, `scripts/ui-audit/audit.py`, and `scripts/ui-audit/palette_gate_worker.py` in the same PR (this issue explicitly forbids editing those three files in *this* lane), breaks the "23/23 routes verified" palette claim until every route is re-audited, and reopens a change-control process Ariel settled as recently as 2026-09-07 per `palette_gate_worker.py:20`.

**Recommendation: confirm words-only for now.** The palette was just settled today (`palette_gate_worker.py:20`: "the canon is Ariel's palette (settled 2026-09-07...)") and re-litigating it the same day, in the same lane that's explicitly forbidden from touching the enforcement scripts, is exactly the kind of scope creep this lane should avoid. If the scan-cost problem on `/radar`'s table view is real (it likely is, at scale), the cleaner fix is a **shape/weight** signal instead of color — bold text, an icon, or a border-only "chip" using the existing 7 colors at different opacities/weights (BID = filled `#005EB8` chip, REVIEW = outlined `#0A2540`, SKIP = ghost `#D7E3F1` text) — which gets the scan-at-a-glance benefit without adding an 8th hue or touching the gate scripts. Ariel decides; flagged as a recommendation only, no PR.

---

## 6. Summary

| Category | Count |
|---|---|
| Routes/route-groups audited | 30 (23 Worker, 7 biddeed-web incl. `/radar`'s internal views) |
| PASS | 27 |
| OFF-CANON, fixed this session | 2 (Section 18 OG tags — PR #20083; Lakewood figure — PR #55) |
| CRITICAL — fabricated citation found in a concurrent merged PR, reverted | 1 (PR #20082 → reverted in PR #20086; logged to `honesty_violations` id `bc98d02f-9792-4f59-a25b-4490c59cc452`) |
| Open taste decisions (not fixed, per issue rule) | 2 (PLANS headline; status hue) |
| NON-COMPLIANT (MISSION never-list violation) | 0 found |
| Technical finding, non-content (dead `/report-success` route) | 1 — recommend a separate engineering issue |

No occurrence of "Shapira Max Bid," "Know your number before the gavel," "14 patents," "enterprise grade," or "Mariam" was found anywhere in either codebase as of 2026-09-07 — the retired terms are fully purged, not just avoided going forward.
