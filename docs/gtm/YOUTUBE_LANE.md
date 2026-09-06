# YouTube Publish Lane

A dormant, code-complete lane for publishing the top BidDeed reel variants of
the day to YouTube. It has never uploaded a real video and cannot until three
OAuth credentials exist — until then every job in this lane runs, does
nothing, and reports why.

## Why it's dormant on purpose

The channel's OAuth application does not exist yet (that's a one-time
browser step, not something this code can do). Building the lane now means
the day the three credentials land, publishing starts working with zero
further engineering — no code path here waits on anything except those
credentials.

## Quota math (the whole design constraint)

A single video upload costs 1,600 of the Google Cloud project's 10,000
daily quota units. Every other call this lane makes — analytics polling,
channel reads — shares that same pool. 400 units are permanently reserved
for those smaller calls, leaving a 9,600-unit upload budget: **exactly 6
uploads per day**, not a separately-chosen number. The quota resets at
midnight Pacific.

The pre-flight check that enforces this is a single atomic database
function: it reserves units before any upload attempt starts, and refuses
cleanly (a logged skip, never a failure) the moment a 7th upload's projected
spend would cross 9,600. A refused upload isn't lost — it's still the
highest-ranked untried candidate the next day, so it's simply queued for
the next Pacific-day run.

## The 7-day trap

While the OAuth application is in Google's "Testing" publishing mode
(the default for a brand-new app), refresh tokens silently stop working
after 7 days. This lane runs a daily token-health check specifically to
catch that the moment it happens — the failure comes back from Google as
`invalid_grant`, gets recorded, and opens a visible alert with the plain-English
fix ("the OAuth app must move from Testing to Published/In production").
Nobody should ever be surprised by this a week after it happens.

## Selection

Candidates come from the same variant-ranking system that already measures
every reel variant's engagement (plays, watch-through, click-through). A
variant is only eligible if:
- it passed its own quality-assurance pass,
- it is not a draft render (see "Publish cadence" below — a draft render
  can never reach this lane, enforced at the view level and again
  defensively in the upload loop itself),
- its landing page returns a real HTTP 200,
- and a human has explicitly approved it.

How many of those eligible candidates actually get uploaded on a given day,
and which ones, is governed by the cadence rules below — up to 6/day is
what the API *allows*; the pilot cadence publishes far fewer, on purpose.

There is no code path that selects an unapproved variant, and no code path
that publishes anything as public — every upload this lane performs is
private, permanently, pending a second, separate, per-video human approval
before that ever changes.

## Metadata

Nothing is written at upload time. Title, description, tags, and category
are all built from the already-approved variant's own fields.

**Updated by issue #20057 (M9, 2026-09-06):** title/description/pinned-comment
text are no longer assembled fresh at upload time from raw row fields --
they are pre-built by `agents/reel_studio/post_text_builder.py` and stored
on `winnerdata.reel_variants.post_text` *before* a variant is even
queue-eligible (`youtube_publish_queue` refuses a row whose description's
first line doesn't carry the variant's own short link -- see the
`20260906j_post_text_publish_gate_20057.sql` migration). This exists because
the end-card link burned into the video frame is not clickable on any
platform; the description's first line and a pinned top-level comment are
the actual one-tap paths, and Ariel reviews that exact text on the LMS
`/reels` screen alongside the video, not a string this lane invents later.

The link in that first line is the variant's own `https://biddeed.ai/r/<code>`
short link (never the long UTM-tagged landing_url this doc originally
described) -- attribution now happens server-side in `resolve_reel_link()`
(docs/spec/20052.md), not via a query string built here.

Immediately after a successful upload, that same link is posted as a real
top-level comment via `commentThreads.insert` (`agents/youtube/
youtube_lib.py::post_top_level_comment`). **Known platform boundary:**
YouTube Data API v3 has no public endpoint to pin a comment -- pinning is a
YouTube Studio UI-only action. This lane posts the comment (which does carry
the clickable link) but cannot programmatically pin it; do not add a fake
"pin" call without first re-verifying Google has shipped one. A
comment-insert failure fails the whole variant (`reel_variants.status =
'publish_error'`) even though the video itself already uploaded -- per M9, a
Short with no clickable link in the post is not "published".

## Measurement

Once real uploads exist, a second daily job pulls each video's views,
watch time, and average view percentage from YouTube's own reporting API —
real, external ground truth to sit alongside this platform's own
click/watch measurement, budgeted against the same shared quota pool as
everything else.

## Publish cadence: sale-type-slotted (foreclosure + tax_deed), not global ranking — issue #19804

**Supersedes the earlier "1 Analyst-ranked winner + 1 exploration variant,
globally ranked" description** (shipped by #19793 PART 4, and never actually
approved — that amendment lived in an issue comment and #19804 makes it the
primary spec per M6). The problem with a single global ranking: a flat
`ORDER BY ctr/watch/plays DESC LIMIT 6` can starve an entire sale_type any
day the other type simply scores higher, even while real tax_deed inventory
sits unused. Two independent per-sale_type rankings fix that structurally
instead of hoping the numbers happen to balance.

**The 6-uploads-per-day figure above is still a quota CEILING, not a
publishing TARGET.** It is Google's hard math (10,000 units/day, 1,600 per
upload, 9,600 usable budget after the analytics/channel-read reserve) — the
most this lane is *physically able* to upload in a day before the API
itself refuses the call.

### The two slots

`public.youtube_publish_cadence` (singleton row) now carries
`foreclosure_slots` / `tax_deed_slots` (1 each by default) instead of a
single global `winner_slots`/`exploration_slots` pair (those columns are
left in the table for M2 additive-by-default but are no longer read).
`winnerdata.youtube_publish_queue` computes an independent `sale_type_rank`
(`row_number() over (partition by sale_type order by ctr/watch/plays desc)`)
so each sale_type has its own top-20 ranking, not one shared list.

| Slot | Source | Ranking |
|---|---|---|
| SLOT 1 | best `sale_type='foreclosure'` reel of the day | Analyst-ranked (ctr → watch-through → plays desc) within foreclosure only |
| SLOT 2 | best `sale_type='tax_deed'` reel of the day | Analyst-ranked within tax_deed only, **with a starvation ladder** (below) |

Both slots are a **floor, not a cap** — the 6/day quota ceiling from #19788
still bounds the top; nothing here prevents publishing more if a future
session explicitly raises the slot counts, it just guarantees these two
happen first.

### Starvation ladder — slot 2 (tax_deed) only

Tax deed is the side that has historically run dry
(`winnerdata.biddeed_reels`: 20 foreclosure rows vs 5 tax_deed rows,
live-verified 2026-09-03 — see `docs/spec/19804.md` for the full count and
the `public.clerk_ssot_sale_rows` wiring-gap context from #19794). Rather
than silently skip the slot, `agents/youtube/uploader.py::select_tax_deed_slot()`
runs a ladder every day:

1. **(a)** the most recent unpublished tax_deed reel within
   `starvation_lookback_days` (14 by default) — labelled by its own real
   `auction_date` in the video description (`metadata_builder.build_description()`
   now takes `sale_type`/`auction_date` and stamps "Sale date: `<real date>`."),
   **never** relabelled as if the sale happened today.
2. **(b)** if none, a **presale** tax_deed reel for an upcoming county sale
   (`phase='presale'`).
3. **(c)** if still none, publish slot 1 alone and print `SLOT_STARVED`.

A foreclosure row is never promoted into slot 2 at any rung — the ladder
only ever reads from a tax_deed-filtered pool.

### Exploration rides inside the weaker-CI slot, not its own slot

The Thompson-sampling floor variant (explore the least-observed candidate,
not just the 2nd-ranked one) no longer consumes a third daily slot. Instead,
`apply_exploration_overlay()` compares the two slots' picks by `plays`
(fewer plays = weaker confidence interval) and replaces **that slot's**
Analyst winner with the least-observed candidate from the same eligible
pool (same sale_type; for tax_deed, the same ladder rung the winner came
from). In practice this means the chronically-thinner tax_deed slot gets
explored more often — which is the right prior on real data.

### Same-property rule (unchanged)

| Setting | Value | Why |
|---|---|---|
| `same_property_per_day` | true | Never more than ONE variant of the same property publishes to YouTube on the same day, across BOTH slots. Four archetype takes on one property in the same feed on the same day is self-competition — it splits the audience the short codes exist to measure per-variant. The other 3 variants of that property still go to the other distribution lanes (site player, other platforms) — this rule is YouTube-feed-specific, not "only publish one variant of a property ever." |

The cadence gate (2/day floor) is checked first and is always the binding
constraint during the pilot, since it's tighter than the 6/day quota
ceiling. The quota preflight-reserve function still runs on every attempt
regardless — cadence controls *whether* an upload is attempted at all;
quota controls whether an attempted upload is allowed to spend.

**Revisit trigger, explicit:** do not raise the slot counts back toward the
6/day ceiling, and do not file a YouTube quota-increase request, until
there are 30 days of real retention data from actual uploads to make that
call on.

## Language distribution — ES/PT-BR do not get a second channel

Translated (es/pt-BR) reel variants are NOT uploaded to their own YouTube
channel and do not get a second/localized channel. There is one BidDeed
YouTube channel. Distribution for the multilingual set is: YouTube's native
per-video localized titles/descriptions on the single existing channel
(when/if wired), per-language playlists on that same channel, and the full
multilingual variant set living on biddeed.ai/reels and the other
distribution lanes (site player, other platforms). `youtube_publish_queue`
itself only ever selects `lang='en'` rows — a non-English variant reaching
this lane's upload path today would be a bug, not a feature, until the
native-localization wiring above actually exists.

## Blocked languages — recorded, not silently dropped

kokoro (the draft/multilingual TTS engine, see the draft-lane docs) covers
en/es/pt(-BR)/fr/it/hi/ja/zh. Two of those, plus Hebrew, are explicitly
**not** built by issue #19793 and are recorded here so a future session
doesn't have to rediscover why:

| Lang | Status | Reason |
|---|---|---|
| Arabic (ar) | BLOCKED | Needs full RTL layout for captions, the URL chip, and safe-area math. `biddeed_reels_lib.py`'s safe-area system (`SAFE_AREA_X/Y`, `dt_wrapped_centered`, the CTA chip/QR-plate placement) is LTR-only throughout — this is a rendering-pipeline redesign, not a translation-string problem. |
| Mandarin (zh) | BLOCKED | Needs a CJK-glyph font in the render environment — `_ensure_font()`'s Inter/DejaVu Sans fallback has no CJK coverage, so `drawtext` would render tofu boxes, not silently-wrong-but-visible text. Also needs a different caption-density rule: the 26-char/line wrap budget is a Latin-script (word-based) heuristic; CJK captions need a per-character budget instead. |
| Hebrew (he) | BLOCKED | kokoro has no `lang_code` for Hebrew at all — HE stays on the eleven_v3-only path, which is the same ElevenLabs-credit-blocked path EN/final rendering is already blocked on. Also needs RTL layout, same as Arabic. |

A flag alone ("skip he/ar/zh") is not sufficient per the issue's own
instruction — the reasons above are what a future session needs to actually
close each of these, not just a reminder that they're closed for now.
