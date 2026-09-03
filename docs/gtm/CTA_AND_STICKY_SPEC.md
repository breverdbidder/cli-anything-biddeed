# BidDeed CTA/Link System + the 5 Sticky Layers

Every reel now carries a machine-verified call-to-action, and every
click-through carries context forward into the site. This doc covers both
halves: the CTA system that makes the link unmissable on the video itself,
and the 5 Sticky Layers that make the deal page remember who's looking and
show them the right thing first.

## The CTA system

A reel is not "done" when the video renders — it's done when a human can
actually get from the video to the deal page without guessing. Four things
are enforced in code, not just checked by eye:

### 1. Safe area

All on-screen text and graphics render inside a fixed pixel box
(`x∈[80,1000], y∈[220,1700]` on the 1080×1920 frame), leaving margin for
each platform's own UI chrome (caption bars, profile chip, share rail).
Every caption wraps to at most 2 lines of ≤26 characters. If a rendered
element's bounding box would exit that box, the render **fails** —
`SafeAreaViolation` is raised before ffmpeg ever runs, not caught after the
fact by someone watching the output.

### 2. The URL chip

A rounded navy chip sits bottom-centre from 24.0s to 32.0s (the video's
final quarter, not just the last second): the human-typeable short link on
line one, "See this deal →" on line two. The URL line renders in a
monospace font specifically — a bold sans "7" and "/" turned out to be
genuinely hard for OCR to tell apart at video-compression resolution;
monospace digits/punctuation don't have that problem.

### 3. The spoken CTA

The voiceover speaks the domain once, naturally, in the closing beat
("...the full breakdown is on biddeed dot A I"). A script that never says
it fails QA.

### 4. The QR code

A ≥260×260px code with a proper quiet zone sits on its own white plate,
bottom-right, from 24.0s. Every render is verified end to end: the frame is
extracted at 26.0s and 31.5s, the QR is decoded (not just "present"), and
the decoded string is checked against the actual short link.

### 5. Off-video surfaces

An MP4 can't hold a clickable link. Every reel now also gets: a caption
whose first line is the bare URL (no preamble), a pinned-comment string
with the same link, and per-platform UTM'd links (Instagram/TikTok/
YouTube/Facebook) carrying a variant identifier so attribution survives
which platform a click came from. These are stored on the row so posting
is copy-paste, never re-typed by hand.

### Title + emoji diversity

A batch of reels assigns each one a title sentence-frame and an emoji pair
from a rotating pool, not independently per property — the failure mode
this fixes is a whole batch converging on the same frame and the same pair
because they're always the first passing candidate for any property with
a sold price. A rolling window of 10 reels may not repeat either more than
twice.

## The 5 Sticky Layers

The promise made in 32 seconds of video should be the first thing the
landing page delivers — and a returning visitor shouldn't get a cold page.

**S1 — Persistent context.** A first-party, anonymous visitor id (no
cookie — this site doesn't use cookies/sessions for tracking, so this
lives in localStorage) remembers which reel brought someone, which county,
and which properties they've already looked at. A second visit in the same
county greets with "N more &lt;County&gt; auctions since you were here"
instead of a cold page.

**S2 — Hooks.** The reel's intent (a shock number, a "nobody bid on this"
story, a red-flag condition story, a presale countdown) travels with the
short link and reorders the landing page to lead with whatever the video
promised, instead of a fixed layout regardless of what got someone there.

**S3 — Progressive disclosure.** Three rungs: free and visible (the
headline number, county, sale figures); visible but locked, with the real
section **names** shown and the values blurred (so a visitor sees the
shape of what's behind the gate, not a generic teaser); and the full
report, unlocked by a single email field.

**S4 — Property-scoped chat.** A one-click entry into the site's existing
AI chat, pre-scoped to the property being viewed, so the first question
gets answered without re-typing the address.

**S5 — Memory.** The visitor and lead records both carry which reel/county/
intent first brought someone in, so a follow-up touch can reference it
instead of opening cold. B2B-appropriate only — no homeowner-directed
messaging.

## Data model

- `winnerdata.reel_links` gained `utm_content` (per-variant attribution).
- `winnerdata.biddeed_reels` gained `archetype`, the off-video CTA strings,
  and a QA evidence column (OCR readback, decoded QR string, live-link
  status, and the two extracted-frame image URLs — the actual proof, not a
  claim).
- `public.lead_profiles` (existing lead table, extended, not duplicated)
  gained an anonymous visitor id, first-touch reel/county/intent, a viewed-
  properties list, and a last-seen timestamp.
- `winnerdata.v_reel_funnel` reports reel → clicks → deal views → gate
  views → email submits → conversion %, per variant.
