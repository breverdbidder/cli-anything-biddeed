# Reventure Steal List — CMO Factory

Source: `docs/gtm/ci/REVENTURE_DOSSIER.md` (issue #19785). Ranked, each item has an owner, a
"why it works," and a "how it maps to biddeed.ai" line, per the issue's explicit format.
No competitor branding, UI, or names are copied — these are patterns, not assets.

| # | Steal | Why it works | How it maps to biddeed.ai | Owner | Target checkpoint |
|---|---|---|---|---|---|
| 1 | Video-as-product-demo: show the actual product on screen inside every piece of content, not a separate demo asset | Removes the "trust an unseen product" gap — the video IS the proof, every time, at zero incremental cost per view | Exactly Part 1 of issue #19785: the bolt32 "site reveal" segment (`scripts/reel_site_reveal.py`) puts the real deal page inside the reel instead of a bare QR code | CMO Factory / bolt32 owners (#19779, #19782) | Ship once the `/deal/:county/:case` production route exists (see docs/spec/19785.md blocker) and 2 reels pass the site-reveal QA gate |
| 2 | County/metro-page-per-video pattern: each video targets one geography, matching a page that already exists for that geography | Turns every video into an SEO-and-recall anchor for a specific, already-indexed page — viewer searches the place name later, lands on the matching page | biddeed.ai already has `/county/<name>` pages (confirmed live, 67 counties in sitemap) — bolt32 reels should 1:1 map to an existing county page, not just a per-case deal page | GTM/SEO lane (META.md §7) | Audit: every published reel's caption links to its county's `/county/<name>` page, not just the case-level QR |
| 3 | Free-tier-with-visible-locked-value gate: show the locked premium metric on the free screen (blurred/labeled), don't hide that it exists | Converts curiosity into a concrete "I know exactly what I'm missing" reason to pay, higher intent than a vague upsell banner | Apply to the SIGNAL$ report: free/preview view shows all 18 section headers with 1-2 unlocked, rest visibly present but gated, instead of hiding the full scope | Product/pricing lane | Ship a locked-preview state on the deal page before the next pricing-page redesign |
| 4 | The channel itself as continuous free demo, no separate "book a demo" friction | Zero-friction top of funnel — anyone can watch the product work before ever talking to anyone | Already the intent of this CMO Factory's reel program; steal item #1 (video-as-demo) is the mechanism, this item is the cadence discipline (consistent weekly output, not one-off) | CMO Factory / Reels lane owner | Sustain a minimum weekly reel cadence for 8 consecutive weeks, tracked in `daily_metrics` |
| 5 | Newsletter/retention layer as the connective tissue between video views and paid conversion | Reventure's dossier finding is that they do NOT clearly run one — that's their gap, and it's evidence the tactic is worth taking rather than skipping: an email layer between "watched a video" and "opens the app" compounds views into an owned channel | biddeed.ai's `/subscribe` page and Resend integration (per META.md §7 Email lane) already exist — wire reel viewers into it explicitly (link in caption/pinned comment, not just the deal-page QR) | Email lane (META.md §7) | Every reel caption includes a `/subscribe` link with its own UTM, tracked separately from the deal-page QR's UTM |
| 6 | Pinned-comment link discipline: put the single most important link in the pinned comment, not buried in a long description | Where viewers actually look for "the link" on a short-form video — matches how the QR-in-frame pattern in Part 1 works for reels specifically | For any longer-form YouTube content this factory produces (META.md §7's "Long-form YouTube" lane), pin the deal-page or county-page link as comment #1 | Long-form YouTube lane owner | Applied to the first long-form upload once that lane ships |

## Explicitly NOT stolen (per this issue's non-goals)

- No cloning of Reventure's UI, layout, or visual design.
- No use of Reventure's branding, name, or founder's name in any public asset.
- No copying of their "Reventure Score" name or scoring methodology — BidDeed's event-signal and
  lien-hierarchy data answer a structurally different question (auction-day bid math, not
  ZIP-level price forecasting) and should stay named and framed as our own.

## Registration

Registered in `docs/gtm/META.md` §7 CI/Sentinel lane as a monitoring target for the 4 triggers
listed in `REVENTURE_BATTLECARD.html`'s "Threat monitoring triggers" section. **Caveat, stated
plainly:** per the prior CMO Factory audit (`docs/spec/19778.md`, `docs/gtm/INVENTORY.md` line
125), `public.viral_competitor_reels` and the CI/Sentinel lane it depends on are schema-only —
no live cron or GHA workflow currently runs a monthly recheck for *any* competitor, Reventure
included. This registration records the *intent and the exact 4 triggers to check*; it does not
claim a monthly cron now exists. Building that cron is out of scope for this issue (M5 scope
discipline — no new workflow files without the issue naming it) and is logged as a follow-up.
