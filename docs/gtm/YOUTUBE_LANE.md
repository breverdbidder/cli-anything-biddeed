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
are all built from the already-approved variant's own fields. The
description's first line is always the bare link to the property's public
deal page, tagged so results can be measured back to the specific variant
that drove them.

## Measurement

Once real uploads exist, a second daily job pulls each video's views,
watch time, and average view percentage from YouTube's own reporting API —
real, external ground truth to sit alongside this platform's own
click/watch measurement, budgeted against the same shared quota pool as
everything else.

## Publish cadence: 2/day, not 6/day — do not "simplify" this back

**The 6-uploads-per-day figure above is a quota CEILING, not a publishing
TARGET.** It is Google's hard math (10,000 units/day, 1,600 per upload,
9,600 usable budget after the analytics/channel-read reserve) — the most
this lane is *physically able* to upload in a day before the API itself
refuses the call. It was never a recommendation about how many videos
should actually go out.

The lane's real publish rate is governed by a separate, tighter config —
`public.youtube_publish_cadence` (a singleton row, not a hardcoded
constant, so it's queryable/auditable and changeable without a code
deploy):

| Setting | Pilot value | Why |
|---|---|---|
| `max_uploads_per_day` | 2 | A brand-new channel with zero upload/retention history has no data to justify publishing at the quota ceiling. Ship slow, watch retention, then decide. |
| `weekdays_only` | true | Mon-Fri only for the first 14 days — no weekend publishing during the pilot. |
| `winner_slots` / `exploration_slots` | 1 / 1 | Each day's 2 uploads are 1 Analyst-ranked top variant (exploit the best-performing signal so far) + 1 exploration variant chosen from the *least*-observed candidate property (a Thompson-sampling floor — deliberately trying under-sampled variants instead of always exploiting the current leader, so the ranking signal itself doesn't collapse onto one early winner). |
| `same_property_per_day` | true | Never more than ONE variant of the same property publishes to YouTube on the same day. Four archetype takes on one property in the same feed on the same day is self-competition — it splits the audience the short codes exist to measure per-variant, defeating the entire point of running variants in the first place. The other 3 variants of that property still go to the other distribution lanes (site player, other platforms) — this rule is YouTube-feed-specific, not "only publish one variant of a property ever." |

Both gates apply independently: the cadence cap (2/day) is checked first
and is always the binding constraint during the pilot, since it's tighter
than the quota ceiling (6/day). The quota preflight-reserve function still
runs on every attempt regardless — cadence controls *whether* an upload is
attempted at all; quota controls whether an attempted upload is allowed to
spend.

**Revisit trigger, explicit:** do not raise `max_uploads_per_day` back
toward the 6/day ceiling, and do not file a YouTube quota-increase request,
until there are 30 days of real retention data from actual uploads to make
that call on. Raising the number back up "to be more efficient" without
that data is exactly the kind of drift this section exists to prevent — if
a future session reads only the quota-math section above and concludes
"6/day" is the target, that is the bug this section is here to stop.

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
