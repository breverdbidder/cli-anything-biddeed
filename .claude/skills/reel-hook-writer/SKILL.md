---
name: reel-hook-writer
description: Use when generating multiple measured reel-script variants for one biddeed_reels property (CMO Factory CP3c, issue #19782). Triggers on: hook writer, reel variants, variant_dna, K=4 variants, reel copywriter, T1 title rules, archetype diversity, bolt32 variant script.
---

# Reel Hook Writer

## Role
Own per-property reel variant copywriting as measurable creative diversity, not one-title-fits-all guessing.

## Working Mode
Fetch one winnerdata.biddeed_reels row + controlled SIGNAL$ fields -> prompt claude-router (T1 Gemini / T1.5 DeepSeek only) for K=4 variant packages -> validate title/diversity/banned-terms in code -> retry on any violation -> mint short_code/QR via Analyst -> insert pending_approval rows into winnerdata.reel_variants.

## Focus Areas
1. Non-Anthropic LLM only -- agents/reel_studio/router_client.py rejects any router response whose tier/provider is anthropic, since claude-router's own force_tier param cannot guarantee the cascade skips its T2 Claude tier
2. T1 title rules -- 5-9 words, third person (no I/you/we), literal ellipsis, exactly two emoji -- enforced by regex, not model self-report
3. variant_dna diversity -- Jaccard distance >=0.5 pairwise across the 6-axis dna, no two variants of one property sharing archetype (also a DB unique constraint on (reel_id, archetype) as a second line of defense)
4. Controlled-fact-only prompting -- only sold_amount/assessed_value/delta_pct/condition tier ever enter the prompt; no bidder/buyer/person name, no vendor/tool name
5. Attribution handoff -- every inserted variant gets its own short_code/short_url/qr_url from analyst.mint_variant_short_link before the row exists (never null)
6. Retry discipline -- up to max_retries+1 full regenerations on any validation failure; after that, report failure explicitly, never insert a variant that failed validation
7. Caption structure -- caption_groups <=5 words each (readability), beat0 ends <=2.0s (hook clarity handoff to Director)
8. Status floor -- every insert lands at status='pending_approval'; nothing in this skill ever sets approved/rejected (that's reel_variant_review, a human decision)

## Quality Gates
- verify: every inserted variant has a non-null short_code (negative test: a variant without one is rejected)
- confirm: the 4-variant set for one property has zero duplicate archetypes and >=0.5 pairwise Jaccard distance on every pair
- check: no router response used came from tier T2/provider anthropic
- ensure: every title passes the 4-part T1 regex/emoji/pronoun check before insert
- call_out: if router_proxy_key is unavailable (env + vault both fail), report BLOCKED, do not fabricate variant text

## Output Format
JSON: {county, reel_id, ok, inserted: [{variant_id, variant_key, short_code, archetype}], router_meta: {tier, provider, model}} or {ok: false, errors: [...]}.

## Constraints
- NEVER call api.anthropic.com or any Claude model directly from this skill
- NEVER write a person's name, bidder identity, or vendor/tool name into title/script/caption/hashtags (M7/M3)
- NEVER insert a variant at any status other than pending_approval (M8 -- no publish step exists downstream)
- Reuse agents/reel_studio/analyst.py for short-code minting -- do not duplicate gen_short_code logic
- Reuse factory/gtm/gate.py's compliance checks for the banned-term scan -- do not maintain a second banned-terms list

## Guard Rail
Do not accept an LLM response whose router tier is T2 (Claude/Anthropic) -- discard it and fail the attempt, even if the text itself looks compliant.
