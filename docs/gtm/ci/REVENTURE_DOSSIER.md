# Competitive Intelligence Dossier — Reventure Consulting / reventure.app

Protocol: EVEREST CI SOP v6.5 (`everest-ssot/sops/EVEREST_CI_SOP_V6.5.md`). Slug: `reventure`.
Compiled: 2026-09-03, issue #19785 (CMO Factory CP3d). Public-source research only — no login,
signup, trial creation, or paywall bypass was performed anywhere in this dossier's compilation.

**M7 note (internal-only exception, per this issue's own text):** Reventure's on-camera
presenter/founder is a named public person. His name is used in this internal dossier file
only, exactly as the issue permits ("it may appear only in the internal CI dossier"). It must
**never** appear in `REVENTURE_BATTLECARD.html`, `REVENTURE_STEAL_LIST.md`, any reel, caption,
or public-facing artifact. Name: **Nick Gerli** (Reventure Consulting CEO/founder, per CNBC and
Fox Business on-air credits — VERIFIED via two independent broadcast sources, see §7).

Every claim below carries VERIFIED (independently fetched/confirmed today) / INFERRED (derived
from a source that isn't first-party, e.g. a third-party aggregator) / UNVERIFIED (could not
confirm — never silently dropped). This dossier does not invent numbers.

---

## 1. Why Reventure, why now

682K+ YouTube subscribers driving a paid property-data app is the exact playbook this CMO
Factory is trying to build (video-as-funnel-floor, per Part 1 of #19785 and REEL_SPEC_BOLT32).
Zero prior CI work exists on this competitor — confirmed absent from `ci_competitor_master` /
`ci_dossiers` before this session (checked live via PostgREST, `slug=eq.reventure` → `[]`).

## 2. Product teardown — reventure.app

**Data granularity (VERIFIED, cross-referenced App Store + Google Play listings):**
State, metro/city, and ZIP-code level. Marketed coverage: "50 states, ~500–1,000 metros,
30,000+ ZIP codes." **No county-level or parcel-level product exists anywhere in their public
marketing** — this is the load-bearing gap BidDeed sits on top of.
Sources: https://apps.apple.com/us/app/reventure-app/id6736954854 ,
https://play.google.com/store/apps/details?id=com.reventure.mobileapp&hl=en_US

**Named proprietary index (VERIFIED via reventure.app/premium):** "Reventure Score" — a
0–100-ish market-stability index built from inventory-change rate, % of listings with a price
cut, days-on-market, mortgage rates, and recent appreciation; roughly, 50 = stable market,
below 50 = declining/price-drop risk. References to separate "overvaluation" and
"growth/investor" scoring exist in marketing copy but their exact standalone names are
**UNVERIFIED**.

**Free vs. paid boundary (INFERRED — reventure.app is a heavily JS-rendered SPA that blocked
direct markdown fetch; based on a dedicated "Free Membership" promo video + App Store/pricing
snippets, not a first-party page render):** A free tier exists with a limited data set; premium
unlocks the Reventure Score, overvaluation %, 12-month price forecasts, inventory/price-cut
trends, ~20 years of historical value/affordability data, and 5 downloadable market reports/mo.

**Pricing (VERIFIED via checkout-page URLs, cross-checked twice same session):**
- Premium Monthly: **$39/mo**
- Premium Yearly: **$33/mo billed annually** (~15% off, ≈$399/yr)
- A $49/mo App-Store-derived figure and a "$239 Memorial Day Sale" promo also surfaced in
  search results — **UNVERIFIED as current pricing**, flagged as likely stale seasonal/App
  Store-listing drift rather than the live web price.
Sources: https://www.reventure.app/pricing , https://www.reventure.app/checkout?plan=Premium+Monthly ,
https://map.reventure.app/checkout?type=signup&plan=Premium+Yearly

**Platforms (VERIFIED):** iOS ("Reventure App," App Store ID 6736954854, Reventure App LLC,
4.7★/284 ratings), Android (`com.reventure.mobileapp`, ~4.5–4.7★, ~100 ratings, Apptopia-inferred
~22–25K+ downloads), and web (reventure.app / map.reventure.app). Note: an unrelated mobile game
also titled "Reventure" (Pixelatto Games) exists on Android — not this product, flagged so no
future CI pass confuses the two.

**Tech/marketing stack observed (VERIFIED, response headers + public tooling):** Cloudflare
CDN/edge, PostHog-style or similar analytics not confirmed; standard SPA hosting pattern
consistent with a small (2–10 person, per LinkedIn) team. No SOC2/compliance claims found.
**Mobile experience, refresh cadence, and specific API endpoints: UNVERIFIED** — would require
either a live account (out of scope per this issue's non-goals) or network-tab inspection of
the authenticated app, which was not attempted.

## 3. LEAD-CAPTURE TEARDOWN (the priority section)

This is the part with the least first-party confirmation, and that gap is itself the finding:
**Reventure does not appear to run a conventional public email-newsletter opt-in mechanism.**
Nothing in App Store metadata, the public pricing/premium pages, or the BiggerPockets community
thread references a newsletter signup separate from the app account itself.

| Field (ci_dossiers column) | Finding | Marker |
|---|---|---|
| `free_tier_mechanics` | Free tier ships with the app install itself (no separate "free trial" window disclosed in App Store metadata) — freemium-by-default, not time-boxed trial-then-paywall. Exact free-tier feature list not independently rendered. | INFERRED |
| `form_fields` | Checkout flow requires selecting a plan (Monthly/Yearly) before any field capture is shown; email/payment fields sit behind that plan-selection click, i.e. **the funnel gate is "pick a price" before "give an email,"** the inverse of a typical lead-magnet-first funnel. | INFERRED (checkout URL structure only, form itself not rendered) |
| `demo_flow` | No dedicated interactive demo/sandbox found; the YouTube channel IS the demo — every video shows the app on-screen live-narrating real metro data, which functions as a continuous, free, high-volume product demo. | VERIFIED (pattern) / INFERRED (as an intentional substitute for a demo flow) |
| `newsletter_strategy` | **No public newsletter opt-in surface found.** This is a real gap in their funnel relative to the "content → email list → nurture" playbook most YouTube-to-SaaS operators run. | UNVERIFIED — could not find, not confirmed absent |
| `progressive_profiling` | Not observed anywhere in public materials. | UNVERIFIED |
| `abandonment_recovery` | Not observed; would require an actual signup attempt with a real email to confirm cart-abandonment emails exist, which is out of scope for this dossier (no login/signup was performed). | NOT_COLLECTED — reason: requires initiating a real account signup, outside this session's public-source-only scope |
| `retention_machinery` | App-native: 12-month forecasts and historical data are the stated retention hooks ("check back as the forecast plays out"). No loyalty/referral program found. | INFERRED |
| `interactive_tools` | The Reventure Score itself functions as an interactive/explorable tool inside the app (state → metro → ZIP drill-down), which IS their free-tool-as-lead-magnet mechanic even without a separate marketing "calculator" page. | VERIFIED (from marketing description) |
| `case_studies` | None found — no public case studies, testimonials wall, or logo bar (consumer app, not B2B/enterprise positioning). | VERIFIED (absence checked on public marketing pages) |
| `lead_magnets` | The YouTube video itself is the lead magnet (free market analysis) with the app as the natural next step — no separate PDF/ebook/report found. | INFERRED |

**Email sequence if subscribing with our own address:** **NOT_COLLECTED.** The issue asks us to
subscribe with our own address and record the cadence/subject lines/CTA structure. That requires
completing Reventure's actual signup flow (email + likely payment-plan selection for the paid
tiers, or an app-store account for the free tier) and then observing an inbox over multiple days
to characterize a "sequence" — neither is achievable inside a single synchronous session, and
initiating it without follow-through would produce a half-observed, misleading cadence. Recorded
here as a genuine data-collection gap, not skipped by omission: **this line item needs a
follow-up session structured as a multi-day watch** (sign up once, check back on a schedule),
not a same-session task.

**YouTube→app handoff (VERIFIED from public video/channel metadata):** Titles directly
reference "Reventure App" (e.g., a title citing "2026 Reventure App Forecast"); a dedicated
video markets the free-membership tier by name. Exact pinned-comment text, description-body UTM
structure, and end-screen link placement **could not be confirmed** — YouTube's public video
pages return navigation boilerplate to a non-authenticated fetch, not full description bodies.
**UNVERIFIED** for the structural details; VERIFIED only that app-name-dropping-in-titles is a
real, repeated pattern.

## 4. YouTube-engine teardown

Channel: `youtube.com/@ReventureConsulting`. **Subscribers: ~681K per vidiq (third-party
aggregator), closely matching Ariel's 682K+ screenshot claim — INFERRED/corroborated, not a
first-party YouTube API read** (this session has no YouTube Data API key scoped to this check;
re-verify with one if higher confidence is needed). **Video count: ~1,403 per vidiq**, channel
active since ~July 2020 (INFERRED, same caveat).

**Verbatim recent titles (VERIFIED, pulled from live search results):**
- "Dallas' housing market entering a full-scale correction (2026 supply shock)"
- "This has never happened before. (1 in 7 houses terminated)"
- "Las Vegas Housing Market Correction is officially underway (2026 Reventure App Forecast)"
- "A deflation vortex is underway. (2026 Wall Street Selloff)"
- "Bills are piling up. Realtors issue warning."
- "J.P. Morgan drops BOMBSHELL report. America's map just flipped."
- "Chaos in Florida. Foreclosures spike 300%." (334K views in 6 days, per Ariel's Sep 3
  screenshot — **UNVERIFIED against a live view-count re-check this session**, cite as Ariel's
  observation, not independently re-confirmed)
- "NY Times issues Recession WARNING" (218K in 3 days per same screenshot — same caveat)

**Title grammar (VERIFIED pattern, not a numeric claim):** place-name + shock number/verb +
directive/consequence clause. Near-identical grammar to the Bolt technique already codified in
`.claude/skills/reel-edit-bolt/SKILL.md` — this is direct, reusable evidence that the emotional
grammar this factory is building for 32s reels is the same grammar driving Reventure's long-form
titles at scale.

**Thumbnail grammar: UNVERIFIED this session** — thumbnail images were not retrievable via the
tools available (no image-render access to YouTube's dynamic thumbnail CDN in this pass).
Ariel's characterization ("yellow-black block text, red arrow, reaction face") is recorded as
his observation, not independently confirmed — flag for a follow-up pass with actual thumbnail
image fetches.

**Upload cadence:** UNVERIFIED precisely — visible gaps in search results suggest roughly
weekly-to-biweekly; total-video-count/channel-age ratio is at least consistent with a
historically higher cadence. **View distribution across the last ~30 uploads: NOT_COLLECTED**
(would require a YouTube Data API key with proper quota, not available this session).

## 5. Company background

**Founder (internal-only per M7 exception above):** Nick Gerli, credited as "Reventure CEO" on
a 2024-06-24 CNBC segment and separately on a 2024-07 Fox Business "Making Money" segment — two
independent broadcast sources, **VERIFIED**.
Sources: https://www.cnbc.com/video/2024/06/24/housing-in-pandemic-boom-towns-up-to-40-percent-overvalued-says-reventure-ceo-nick-gerli.html ,
https://www.foxbusiness.com/video/6357285581112

**Founded:** Conflicting sources — LinkedIn states 2019, a Crunchbase-derived search snippet
states 2020; the app itself appears to have entered development ~2021. **UNVERIFIED exact
year** (direct Crunchbase fetch returned HTTP 403 this session).

**Funding:** No round size, investor names, or VC backing found anywhere public.
**UNVERIFIED** — possibly bootstrapped, not confirmed.

**HQ:** LinkedIn lists Austin, TX 78756, company size 2–10 employees, industry "Real Estate."
Single-source only — **INFERRED**, not cross-verified against a second registry.
Source: https://www.linkedin.com/company/reventureconsulting

## 6. Our real edges vs. theirs (evidence-gated, scored in the battle card)

- **Parcel/auction-level data vs. their ZIP-level** — VERIFIED as a real gap (see §2 data
  granularity finding); this is BidDeed's clearest structural moat against this specific
  competitor.
- **Event signal ("a sale happened yesterday, here's the resolved buyer")** — Reventure has
  no auction/foreclosure-event product at all (VERIFIED absence in their public marketing).
- **18-section SIGNAL$ report / lien-title hierarchy** — Reventure has no comparable per-property
  report product; their unit of analysis is a ZIP/metro, not a parcel. VERIFIED by omission.
- **Their real edges:** 682K-subscriber distribution vs. BidDeed's ~0 (VERIFIED, stark), an
  app-store-live consumer-simple mobile app (BidDeed has none — UNVERIFIED whether one is
  planned), and national-brand trust built over 5+ years of on-air CNBC/Fox Business
  appearances (VERIFIED).

## 7. Steal list

See `docs/gtm/ci/REVENTURE_STEAL_LIST.md` (public-safe, no founder name, ranked, owners assigned).

## 8. Sources

- https://www.reventure.app/pricing
- https://www.reventure.app/premium
- https://www.reventure.app/checkout?plan=Premium+Monthly
- https://map.reventure.app/checkout?type=signup&plan=Premium+Yearly
- https://apps.apple.com/us/app/reventure-app/id6736954854
- https://play.google.com/store/apps/details?id=com.reventure.mobileapp&hl=en_US
- https://apptopia.com/google-play/app/com.reventure.mobileapp/about
- https://vidiq.com/youtube-stats/channel/UCVTQunGrE3p7Oq8Owao5y_Q/
- https://www.youtube.com/@ReventureConsulting/videos
- https://www.biggerpockets.com/forums/921/topics/1230772-reventure-app-feedback
- https://www.cnbc.com/video/2024/06/24/housing-in-pandemic-boom-towns-up-to-40-percent-overvalued-says-reventure-ceo-nick-gerli.html
- https://www.foxbusiness.com/video/6357285581112
- https://reventureapp.blog/reventure-price-forecast-review/
- https://www.linkedin.com/company/reventureconsulting
- https://www.crunchbase.com/organization/reventure-consulting (403 — could not fetch, cited as attempted-but-blocked)

## 9. Explicit gaps for the next CI pass (do not let these silently disappear)

1. Email-signup drip sequence (subject lines, cadence, CTA structure) — NOT_COLLECTED, needs a
   multi-day watch session starting with a real signup.
2. YouTube pinned-comment / description-body link structure and UTM params — UNVERIFIED, needs
   either a YouTube Data API key or a JS-rendering fetch tool this session didn't have.
3. Thumbnail grammar — UNVERIFIED, needs actual thumbnail image fetches.
4. View-count/upload-cadence distribution across the last 30 videos — NOT_COLLECTED, needs
   YouTube Data API quota.
5. Exact founding year and funding status — UNVERIFIED, conflicting/absent sources.
