# BidDeed Reel Variant Studio

Every property used to get one reel with one title. Reel Variant Studio
gives each shortlisted property several reels at once — each with its own
creative identity — so the numbers can show which one actually works, and
the next day's mix leans toward what won.

## The four roles

**Hook Writer** — writes K=4 script/title packages per property. Every
package has a `variant_dna`: an archetype (the emotional angle — a shocking
number, an underdog bidder, a nobody-showed-up mystery, and so on), a voice
register, a caption style, a music mood, and an edit style. No two variants
of the same property share an archetype, and every pair differs on at least
3 of those 5 dimensions — checked in code, not just asked for.

Every title: 5-9 words, third person (the property is the protagonist,
never a person), an ellipsis, exactly two emoji. No bidder/owner name ever
appears anywhere. No vendor or internal tool name ever appears anywhere.

**Animator** — renders the animated beat-slot elements (an opening
kinetic-typography hook, a parcel-outline reveal, a price count-up, a loop
seam) that the video assembler drops into place. Deterministic and seeded,
so a re-render reproduces the same output. Budgeted: 90 seconds per
element, or it falls back to a simpler version rather than stall.

**Director / QA** — grades every variant before it can be reviewed: title
rules, no banned names or vendor terms, caption readability, whether the
hook lands in the first two seconds, and (once video exists) exact timing
and a clean loop seam. A variant that fails any applicable check does not
pass — no partial credit.

**Analyst** — mints each variant its own short link and QR code so clicks,
watch-through, and email captures are counted per variant, not lumped into
one property number. Reads the scoreboard, picks tomorrow's archetype mix
(always keeping at least one experimental pick in the rotation so the
system keeps learning, not just repeating yesterday's winner), and writes
the weekly "what worked and why" summary.

## What "approved" means

Every variant lands waiting for review. Nothing renders, posts, or sends
anywhere on its own. A human decision — approve, reject, or "needs more
work" — is what moves a variant forward, made from the same review screen
used for every other approval queue in this system.

## Status

This is under active build. See the engineering changelog for what has
shipped, what's been verified against live data, and what's still ahead.
