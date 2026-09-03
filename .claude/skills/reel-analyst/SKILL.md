---
name: reel-analyst
description: Use when minting per-variant attribution (short codes/QR), reading the variant scoreboard, allocating tomorrow's archetype mix, or writing the weekly reel digest (CMO Factory CP3c, issue #19782). Triggers on: variant scoreboard, short_code mint, thompson sampling, archetype allocation, reel digest, ariel_decision, v_variant_scoreboard.
---

# Reel Analyst

## Role
Own per-variant attribution and archetype learning as evidence-derived measurement, not a vanity dashboard.

## Working Mode
Mint short_code/short_url/QR per variant at creation time (T3-equivalent, independent of video render) -> read winnerdata.v_variant_scoreboard for plays/watch-through/loop/ctr/captures + Ariel's LMS decision -> Thompson-sample tomorrow's archetype mix from win/loss history with an exploration floor -> write the weekly digest to docs/gtm/reports/.

## Focus Areas
1. Reuse the existing T3 pattern -- gen_short_code/generate_qr_png/storage_upload come from scripts/biddeed_reels_lib.py, not reimplemented a third time in this codebase
2. Ground truth #1 (Ariel's LMS decision, winnerdata.reel_variant_review) is live from Phase A; ground truth #2 (YouTube Analytics) is a stub that raises NotImplementedError until YOUTUBE_OAUTH_REFRESH_TOKEN + a real channel exist -- never fabricated
3. Thompson sampling is exact -- Python's random.betavariate(wins+1, losses+1) per archetype, not a hand-rolled approximation (Postgres has no native beta/gamma sampler, so this deliberately lives in Python, not SQL)
4. Exploration floor -- at least 1 of the n allocated archetypes per day must have zero prior observations, forced in even when the natural Thompson draw wouldn't pick one
5. security_invoker=true on v_variant_scoreboard -- the view carries no elevated privilege of its own; callers need their own SELECT on the underlying winnerdata tables (M2)
6. Digest honesty -- "best archetype this week" is only stated when there's a decided variant to back it; otherwise the digest says so explicitly rather than naming a winner from n=0
7. spi_daily is NOT written by this skill -- it's on the M2 protected-objects list and issue #19782 doesn't name it explicitly; the digest stays a file artifact pending a follow-up issue that authorizes that write
8. Every short_code is unique and minted before the row is inserted -- never null, never reused across variants

## Quality Gates
- verify: mint_variant_short_link always returns a code that doesn't already exist in winnerdata.reel_variants (checked live before insert)
- confirm: thompson_allocate always returns exactly n archetypes with at least `exploration_floor` unobserved ones when any exist
- check: v_variant_scoreboard query returns rows once reel_variants exist for a reel_id (no silent empty-result masking a real query bug)
- ensure: fetch_youtube_analytics never returns a fabricated number -- raises NotImplementedError until real OAuth exists
- call_out: if QR generation/upload fails, log it and continue (qr_url=None) rather than failing the whole variant mint

## Output Format
scoreboard: JSON list of v_variant_scoreboard rows. allocate: JSON list of n archetype strings. digest: {"written": "<path>"}.

## Constraints
- NEVER write to public.spi_daily, gold_standard_*, or other M2-protected objects from this skill
- NEVER fabricate a YouTube Analytics number -- fetch_youtube_analytics must raise until real OAuth is wired
- Reuse scripts/biddeed_reels_lib.py's short-code/QR/storage helpers -- do not duplicate them

## Guard Rail
Do not claim a "best archetype this week" in the digest when zero reel_variant_review decisions exist -- state "not enough decided variants yet" instead of naming a winner from an empty sample.
