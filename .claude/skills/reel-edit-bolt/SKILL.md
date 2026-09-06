---
name: reel-edit-bolt
description: >
  BoltMotivation-technique 32-second BidDeed reel edit template ("bolt32").
  Trigger words: reel script, reel title, write a reel title, reel edit,
  bolt32, 32-second reel, BoltMotivation, reel beat sheet. Input: a
  winnerdata.biddeed_reels row (or equivalent property facts: county,
  sale_type, sold_amount/opening_bid/judgment_amount, assessed_value,
  delta_pct, condition_tier, days_to_auction) plus any known
  defendant/plaintiff/owner/buyer names for that case (M7 banned-name
  input). Output: 5 validated title candidates + the chosen title, a
  6-beat timing map (beat_map jsonb), and eleven_v3-tagged script text --
  either as data for scripts/biddeed_reels_pipeline_bolt32.py to render, or
  as a standalone answer when asked to "write a reel title" with no
  pipeline run attached.
---

# reel-edit-bolt

Own the 32-second BidDeed reel edit as a story-arc-with-hard-timings
production spec, not a generic short-form video checklist. Every BidDeed
reel is cut to this exact template (Ariel directive, 2026-09-03): 32 seconds
because a ~30s video watched roughly twice (loop-and-rewatch) is what drives
the AVD signal that makes a Short surface — the technique is reverse-engineered
from @boltmotivationyt (Mathis, 18, 2.96M subs, ~250M views/month).

## Working Mode

1. **Map** — pull the row's real facts (county, sale_type, sold_amount OR
   opening_bid/judgment_amount, assessed_value, delta_pct, condition_tier,
   days_to_auction) and the case's known names (defendant/plaintiff/owner/
   buyer) from whatever source is available. Never fabricate a missing
   figure.
2. **Separate evidence from hypothesis** — a number that is null in the
   source stays null in the output ("Opening bid has not posted yet"), it is
   never estimated or guessed to fill a template slot.
3. **Smallest intervention** — reuse existing v2/presale imagery, condition
   scoring, and short-link/QR infrastructure verbatim; bolt32 only changes
   title generation, beat timing, and the final edit assembly. Never
   re-spend a Maps or vision-scoring call to build a bolt32 render of a row
   that already has v2/presale imagery.
4. **Validate** — every generated title runs through the T1 validator
   before it is usable; every assembled video's duration is asserted against
   32.0s ±0.1s before it is uploaded or written to the DB.

## T1 — Title Generator

Protagonist is always **the property**, **a bidder**, **the bank**, or
**the county** — NEVER a person's name (M7). Structure: curiosity gap, third
person, never explains, ends with an ellipsis ("…") then **exactly two**
emoji from this fixed vocabulary: 😳 😱 🥹 🤯 🥶 😰 ❤️ 💔 🏆 👀.

Generate 5 candidates, each carrying a real numeric fact (a `$` figure, a
day count, etc.) so the stakes-score check always has something concrete to
point at. Validate every candidate against ALL of:

| Check | Rule |
|---|---|
| Case | Starts uppercase |
| Length | 20-60 characters before the ellipsis |
| Emoji | Ends with "…" then exactly 2 tokens from the fixed vocabulary (grapheme-aware — the heart emoji is one 2-codepoint token, never split) |
| Banned names | No token from the case's own defendant/plaintiff/owner/buyer names (M7); no vendor name (ElevenLabs, OpenRouter, Firecrawl, DeepSeek, GLM, Tracerfy, SummitLeads); no "foreclosure relief" |
| Stakes score | Contains a `$` figure, a bare digit (a count), or a superlative (best/worst/greatest/most/least/highest/lowest/biggest/smallest/never/only/first) |

Pick the **first candidate that passes all checks**. If none of the 5 pass,
do not force a 6th or silently degrade a check — report which checks failed
per candidate.

Code reference: `scripts/biddeed_reels_lib.py` —
`generate_bolt32_titles()` / `validate_bolt32_title()` / `pick_bolt32_title()`.

## T2 — Story Arc (not information)

A protagonist, a stake, a turn, a payoff. The payoff (the dollar number)
lands late; the closing line loops back into the opening frame so an
autoplay viewer rewatches. Postsale protagonist stake = sold price vs
assessed value; presale protagonist stake = opening bid/judgment vs assessed
value and days-to-auction.

## T3 — Retention Engineering

- The payoff number lands in the 20.0-28.0s beat, not earlier.
- The 31.0-32.0s "end" beat reuses the EXACT same still frame as the
  0.0-2.0s "hook" beat — a real frame match, not just a duration coincidence
  — so the loop is a visible cut back to the opening shot.
- No "subscribe/follow" CTA anywhere. No brand card before the 31.0s mark.

## T4 — Delivery

Continuous eleven_v3 voiceover (voice `TX3LPaxmHKxFdv7VOQHJ`) with inline
audio tags per beat: `[surprised]` hook, neutral setup, `[serious]` tension,
`[excited]` payoff, `[warm]` loop line. Big centered captions, one visual
change every 2-4s, no unlicensed music bed (logged as a standing deviation —
no royalty-free asset exists in this org; do not source one from an
unverified vendor to fill this gap, per the standing non-goal on new
vendors).

## Beat Sheet (hard timings — enforce in ffmpeg assembly, not advisory)

| Beat | Window | Content |
|---|---|---|
| hook | 0.0-2.0s | Title line spoken verbatim; on-screen text = title minus emoji; opening frame = aerial with parcel outline (reused at 31.0s) |
| setup | 2.0-8.0s | County/city, beds/sqft, opening/judgment number; Street View mandatory |
| tension | 8.0-20.0s | Judgment-vs-value spread, condition/red flags, comps; 2-4 visual cuts (bounded by however many real stills exist for the row — never fabricate a comp-card) |
| payoff | 20.0-28.0s | The number: sold price/value-band delta (postsale) or SIGNAL$ Max Bid vs opening bid (presale). Largest caption of the reel |
| loop_line | 28.0-31.0s | One sentence restating the hook as a question/callback |
| end | 31.0-32.0s | Return to the 0.0s frame; small biddeed.ai wordmark + QR bottom-right |

Total = 32.000s ±0.1s. Code reference: `BOLT32_SEGMENTS` / `assemble_video_bolt32()`
/ `assert_bolt32_duration()` in `scripts/biddeed_reels_lib.py`.

## Focus Areas

1. Title validity is binary — a candidate either passes all 5 checks or it
   is not used. No partial credit, no "close enough."
2. Numeric facts only ever come from the row's own data — never estimate a
   missing `$` figure or day count to satisfy the stakes-score check.
3. The banned-names list must be built from the actual case record
   (defendant/plaintiff/owner/buyer), not skipped because it is
   inconvenient to look up. An empty result (no name on file) is a valid
   outcome and is not the same as skipping the check.
4. Person names never appear in on-screen text, captions, or voice script —
   this is enforced independently of the banned-list check by construction
   (the generator's templates never interpolate a free-text name field).
5. Reuse v2/presale imagery/condition-scoring/short-link infrastructure —
   bolt32 never re-fetches Maps imagery or re-runs vision scoring for a row
   that already has it.
6. The 32.0s±0.1s duration assert and the loop-frame-reuse check both run
   BEFORE a video is uploaded or written to the DB, not after.
7. Everything renders to `status='pending_approval'` (M8) — this skill never
   flips status to `approved`/`posted` and never calls a publish/social API.
8. Client-facing text (title, caption, on-screen overlays) never names an
   internal vendor, tool, GitHub issue number, or run ID (M3).

## Quality Gates

- **verify**: every chosen title passes `validate_bolt32_title()` with zero
  `reasons` before it is used anywhere (script, caption, on-screen text).
- **confirm**: the assembled video's ffprobed duration is within 32.0s
  ±0.1s AND `tts_model == 'eleven_v3'` before the DB row is updated.
- **check**: the row's `status` is not `'approved'` before writing any
  bolt32 field (refuse and report `blocked_approved_row` if it is).
- **ensure**: the `end` beat's still image is byte-identical in source to
  the `hook` beat's still image (same file), so the loop is a real frame
  match.
- **call_out**: any candidate/field that could not be validated (missing
  imagery, missing short link, all 5 titles failing) is reported as an
  explicit error, never silently skipped or defaulted.

## Return Format

`scope` (which row/case this render covers) → `finding+evidence` (which
title candidates passed/failed and why, the ffprobed duration, the
tts_model actually used) → `intervention` (what was rendered/written) →
`validated` (the 4 quality gates above, pass/fail each) → `residual` (any
DoD item not reachable this run, e.g. no case names on file for the
banned-name check, imagery missing so bolt32 can't run yet).

## Guard Rail

Do not fabricate a numeric fact, a person name's absence, or a passing
title-validator result to force a render through — a row with no usable
title candidate, no imagery, or a failing duration/tts_model assert is a
reported error, not a render.

## CTA/link system + title diversity (issue #19786, added 2026-09-03)

Every bolt32 render now carries a persistent 24.0-32.0s URL chip + QR plate
(`build_cta_chip_png()`/`build_qr_plate_png()`), a spoken CTA in the
loop-line beat (`assert_bolt32_spoken_cta()`), and code-enforced safe-area
text wrapping (`dt_wrapped_centered()`, raises `SafeAreaViolation`). Director
QA additionally runs OCR (tesseract, cropped to the chip's own bbox --
whole-frame OCR over a busy aerial photo is unreliable, live-reproduced) and
QR decode (pyzbar) against the actual rendered frame at 26.0s/31.5s before
any DB write. `gen_short_code()` draws from an OCR-safe alphabet (excludes
0/1/I/i/L/l/O/o) for this reason.

For a BATCH of reels (not a single row), use
`scripts/biddeed_reels_pipeline_bolt32.py --cta-batch <ids>` instead of
`--ids` -- it calls `assign_batch_diversity()` to round-robin title frame +
emoji pair across the batch (`check_batch_diversity()` enforces no more than
2 repeats of either in any rolling 10-item window) and computes each row's
`archetype` (`compute_bolt32_archetype()`) for S2 intent-routing on the deal
page. `--ids`/`process_row_bolt32()` still works for a single fresh row but
does not run diversity assignment or the QA gate.
