# AUTOLOOP.md — Karpathy Self-Improvement Loop for cli-anything Skills

## Overview

Autonomous overnight skill improvement using binary assertion evals.
Based on Andrej Karpathy's "auto-research" pattern applied to Claude Code skills.

**Two layers of self-improvement:**
1. **Layer 1 (Activation):** Anthropic's built-in skill-creator description loop — improves YAML trigger accuracy
2. **Layer 2 (Output Quality):** This loop — improves SKILL.md instructions using binary true/false assertion evals

## Architecture

```
┌─────────────────────────────────────────────┐
│            Self-Improvement Loop              │
│                                               │
│  1. Read SKILL.md (ZONEWISE.md / AUCTION.md) │
│  2. Run skill against 5 test prompts          │
│  3. Check 25 binary assertions via eval.json  │
│  4. Score = passed / total                     │
│                                               │
│  ┌─ Score improved? ──► git commit, keep ──┐  │
│  │                                          │  │
│  └─ Score dropped?  ──► git reset, retry ──┘  │
│                                               │
│  Never stop. Never ask human. Loop until      │
│  perfect score or manually interrupted.       │
└─────────────────────────────────────────────┘
```

## Eval Structure

Each harness has: `{harness}/eval/eval.json`

```
zonewise/eval/eval.json   — 25 assertions: parcel format, zoning codes, spatial match, Supabase persist, errors
auction/eval/eval.json    — 25 assertions: max bid formula, lien priority, reports, BCPAO data, batch analysis
reports/eval/eval.json    — 25 assertions: brand compliance, DOCX validity, color theme, content accuracy, edge cases
```

## Eval Runner

```bash
python scripts/eval_runner.py --eval-file zonewise/eval/eval.json --outputs-dir zonewise/eval_outputs/
python scripts/eval_runner.py --eval-file auction/eval/eval.json --outputs-dir auction/eval_outputs/
python scripts/eval_runner.py --eval-file reports/eval/eval.json --outputs-dir reports/eval_outputs/
```

## Overnight Loop Prompts

### ZoneWise Scraper V4

```
Run a self-improvement loop on the ZoneWise scraper skill (zonewise/agent-harness/ZONEWISE.md).

Eval file: zonewise/eval/eval.json
Eval runner: python scripts/eval_runner.py --eval-file zonewise/eval/eval.json --outputs-dir zonewise/eval_outputs/

For each iteration:
1. Run the ZoneWise skill against all 5 test prompts in eval.json
2. Save outputs to zonewise/eval_outputs/{test_id}.json
3. Run eval_runner.py and read the score
4. If any assertions fail, make ONE targeted change to ZONEWISE.md to fix the failure
5. Re-run the tests and re-score
6. If score improved → git add + git commit with message "autoloop: {score}% → {new_score}% [{assertion_fixed}]"
7. If score dropped → git checkout -- zonewise/agent-harness/ZONEWISE.md (revert) and try a DIFFERENT change
8. Log each iteration to zonewise/eval/autoloop_log.jsonl

RULES:
- Make only ONE change per iteration to isolate what helped
- Never stop. Keep looping until perfect score (25/25) or I interrupt you
- Do not ask if I should keep going or is this a good stopping point
- I might be asleep. You are autonomous
- If stuck after 5 consecutive failed attempts on same assertion, skip it and target next failure
- Maximum 50 iterations per session
```

### Auction Analyzer

```
Run a self-improvement loop on the Auction Analyzer skill (auction/agent-harness/AUCTION.md).

Eval file: auction/eval/eval.json
Eval runner: python scripts/eval_runner.py --eval-file auction/eval/eval.json --outputs-dir auction/eval_outputs/

For each iteration:
1. Run the Auction skill against all 5 test prompts in eval.json
2. Save outputs to auction/eval_outputs/{test_id}.json and {test_id}.docx for report tests
3. Run eval_runner.py and read the score
4. If any assertions fail, make ONE targeted change to AUCTION.md to fix the failure
5. Re-run the tests and re-score
6. If score improved → git add + git commit with message "autoloop: {score}% → {new_score}% [{assertion_fixed}]"
7. If score dropped → git checkout -- auction/agent-harness/AUCTION.md (revert) and try a DIFFERENT change
8. Log each iteration to auction/eval/autoloop_log.jsonl

RULES:
- Make only ONE change per iteration to isolate what helped
- Never stop. Keep looping until perfect score (25/25) or I interrupt you
- Do not ask if I should keep going or is this a good stopping point
- I might be asleep. You are autonomous
- Pay special attention to max bid formula assertions — the math MUST be exact
- If stuck after 5 consecutive failed attempts on same assertion, skip it and target next failure
- Maximum 50 iterations per session
```

### Report Generation

```
Run a self-improvement loop on the Report Generation skill.

Eval file: reports/eval/eval.json
Eval runner: python scripts/eval_runner.py --eval-file reports/eval/eval.json --outputs-dir reports/eval_outputs/

For each iteration:
1. Generate DOCX reports for all 5 test prompts in eval.json
2. Save outputs to reports/eval_outputs/{test_id}.docx
3. Run eval_runner.py and read the score
4. If any assertions fail, make ONE targeted change to the report generation code/skill to fix the failure
5. Re-run the tests and re-score
6. If score improved → git add + git commit with message "autoloop: {score}% → {new_score}% [{assertion_fixed}]"
7. If score dropped → git reset and try a DIFFERENT change
8. Log each iteration to reports/eval/autoloop_log.jsonl

RULES:
- Make only ONE change per iteration to isolate what helped
- Never stop. Keep looping until perfect score (25/25) or I interrupt you
- Do not ask if I should keep going or is this a good stopping point
- I might be asleep. You are autonomous
- Brand compliance is CRITICAL: navy #1E3A5F, Arial font, BidDeed.AI branding, NO Property360
- DOCX must validate — use docx-js with ShadingType.CLEAR, dual table widths, LevelFormat.BULLET
- If stuck after 5 consecutive failed attempts on same assertion, skip it and target next failure
- Maximum 50 iterations per session
```

## Iteration Log Format (JSONL)

Each line in `autoloop_log.jsonl`:

```json
{
  "iteration": 1,
  "timestamp": "2026-03-16T04:00:00Z",
  "score_before": 0.88,
  "score_after": 0.92,
  "change_made": "Added explicit instruction: 'All parcel_id fields must match Brevard format XX-XX-XX-XX-XXXXX.X-XXXX.X'",
  "file_changed": "ZONEWISE.md",
  "assertion_targeted": "T1_A2",
  "kept": true,
  "commit_sha": "abc1234"
}
```

## Running the Loop

### Option A: Claude Code CLI (Recommended)
```bash
cd cli-anything-biddeed
claude --auto "$(cat AUTOLOOP.md | head -n 5) Run ZoneWise loop. Eval: zonewise/eval/eval.json"
```

### Option B: Claude Code with /rc (Remote Control from phone)
```bash
claude remote-control
# Then paste the overnight prompt from your phone
```

### Option C: GitHub Actions (Scheduled)
See `.github/workflows/autoloop.yml` for nightly runs at 2AM EST.

## Safety Guards

- **Max 50 iterations** per session (prevents runaway loops)
- **Git commit on improvement** (every good change is saved)
- **Git reset on regression** (bad changes are immediately reverted)
- **Skip after 5 failures** on same assertion (prevents infinite retry on impossible assertions)
- **JSONL log** of every iteration (full audit trail)
- **50% context rule** still applies — if context window fills, the loop should checkpoint and restart

## Binary Assertion Design Principles

Good assertions are **binary** (true/false, no subjectivity):
- ✅ "Output is valid JSON"
- ✅ "Field matches regex pattern"
- ✅ "Word count under 300"
- ✅ "Does not contain forbidden string"
- ❌ "Output is well-written" (subjective)
- ❌ "Good tone of voice" (subjective)
- ❌ "Compelling headline" (subjective)

Subjective quality checks → use Anthropic's skill-creator eval dashboard (Layer 1)
Structural/format checks → use this binary loop (Layer 2)
