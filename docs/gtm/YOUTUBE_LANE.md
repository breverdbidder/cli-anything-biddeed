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

Each day's top 6 candidates come from the same variant-ranking system that
already measures every reel variant's engagement (plays, watch-through,
click-through). A variant is only eligible if:
- it passed its own quality-assurance pass,
- its landing page returns a real HTTP 200,
- and a human has explicitly approved it.

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
