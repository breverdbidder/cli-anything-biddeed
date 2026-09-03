# BidDeed Reel Spec — bolt32 (32-second BoltMotivation-technique edit)

Every BidDeed reel is built to a fixed 32-second length using a
story-arc-with-hard-timings technique reverse-engineered from a
high-performing Shorts creator's public output (40 shorts sampled,
14K-27M views each). The core mechanic: a ~30s video with an average view
duration over 60 seconds is being watched roughly twice — the video loops
and the viewer rewatches it. The edit is built to make that loop natural,
not to trick the platform.

## T1 — Title

Curiosity-gap title, third person, never explains, ends with an ellipsis
("…") then exactly two emoji from a fixed vocabulary: 😳 😱 🥹 🤯 🥶 😰 ❤️
💔 🏆 👀.

Protagonist is always **the property**, **a bidder**, **the bank**, or
**the county** — never a person's name. Stakes must be concrete: a dollar
figure, a count, or a superlative. Weak-stakes titles have a low ceiling;
titles with real numbers in them have a much higher one.

Validation (all required):
- Starts uppercase
- 20-60 characters before the ellipsis
- Ends with the ellipsis then exactly two vocabulary emoji
- No person's name from the property's own case record; no vendor/tool name
- Contains a `$` figure, a count, or a superlative word

Generate 5 candidates per property; use the first one that passes every
check.

## T2 — Story Arc

A protagonist, a stake, a turn, a payoff — not a list of facts. Postsale:
the stake is the sold price vs. the county's assessed value. Presale: the
stake is the opening bid/judgment vs. assessed value and the auction date.

## T3 — Retention Engineering

- The payoff (the number) lands late in the edit, not up front.
- The final beat returns to the exact opening frame — a real frame match,
  so an autoplay loop visibly cuts back to where it started.
- No subscribe/follow call-to-action. No brand card before the final beat.

## T4 — Delivery

Continuous voiceover narration with emotional delivery tags per beat, large
centered captions (3-5 words at a time), a visual change every 2-4 seconds,
music bed under the voice where a licensed track is available.

## Beat Sheet (hard timings)

| Beat | Window | Content |
|---|---|---|
| Hook | 0.0–2.0s | Title spoken verbatim; opening frame = aerial with the parcel boundary; this exact frame returns at the end |
| Setup | 2.0–8.0s | County/city, size, the opening number; a street-level shot |
| Tension | 8.0–20.0s | The value spread, condition notes, comps; several visual cuts |
| Payoff | 20.0–28.0s | The number — sold price/value-band delta or bid-vs-assessed gap; the largest caption in the edit |
| Loop line | 28.0–31.0s | One line restating the hook as a callback |
| End | 31.0–32.0s | Returns to the opening frame; small wordmark + QR |

Total: 32.000 seconds ±0.1s.

## Measurement

The public reel player emits watch-progress events (play, 25%, 50%, 75%,
100%, loop) so an internal average-view-duration proxy exists independent
of any third-party platform analytics. A reel template is promotable to the
next factory checkpoint only once its median viewer reaches 100% watch-
through (or loops) across at least 20 real plays.
