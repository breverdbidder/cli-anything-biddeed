---
description: Adversarial PR review via Codex (GPT), layered on top of /review-pr.
argument-hint: "[PR number, optional]"
---

# /cross-review — Adversarial Cross-Model PR Review

Claude reviewing Claude has correlated blind spots. Running Codex (GPT) against
the same PR catches bugs Claude's training doesn't surface, and vice versa. This
command delegates the adversarial pass to `codex exec` and merges the findings
with `/review-pr`.

## Preflight

1. **Check codex CLI availability:**
   ```bash
   which codex
   codex --version
   ```
   If `which codex` fails, emit exactly:
   ```
   CODEX_UNAVAILABLE — codex CLI not installed. Install: https://github.com/openai/codex
   Skipping cross-review. Run /review-pr alone for single-model coverage.
   ```
   and stop. Do NOT block the developer — this is an additive quality gate, not
   a required one.

2. **Check codex auth:**
   ```bash
   codex auth status 2>&1 | head -5
   ```
   If unauthenticated, emit:
   ```
   CODEX_UNAUTHED — run: codex auth login. Skipping cross-review.
   ```
   and stop.

## Process

1. **Resolve PR** — same as `/review-pr`: `gh pr view $ARGUMENTS --json number,title,body,files,url`
   (or for current branch if no argument).

2. **Build the adversarial prompt.** Write to a tempfile `/tmp/cross-review-<PR#>.md`:

   ```markdown
   # Adversarial PR Review

   You are an adversarial code reviewer. Your job is to break this PR, not
   approve it. You have no prior commitment to the implementation.

   ## PR
   <PR title, body, URL>

   ## Diff
   <output of git diff origin/main...HEAD>

   ## Your task
   Find every bug, silent failure, regression, edge case, security hole, race
   condition, and broken assumption in this diff. Rank by severity.

   End your output with exactly one of:
   VERDICT: APPROVE_SHIP_AS_IS | APPROVE_WITH_CHANGES | REQUEST_CHANGES
   ```

3. **Invoke codex:**
   ```bash
   codex exec --prompt-file /tmp/cross-review-<PR#>.md --model gpt-5-codex
   ```
   Capture stdout into `/tmp/cross-review-<PR#>-codex.md`. Give it a hard
   timeout of 5 minutes:
   ```bash
   timeout 300 codex exec ... || echo "CODEX_TIMEOUT"
   ```

4. **Invoke /review-pr in parallel** via the Task tool (fresh-context Claude
   review). Capture its output.

5. **Merge the two reviews.** Walk both outputs:
   - **Agreement:** flag findings both reviewers raised (these are high-confidence).
   - **Disagreement:** flag findings only one reviewer raised, and keep them
     with a `[only Codex]` or `[only Claude]` tag. Do NOT drop them — the
     single-reviewer findings are often the ones worth shipping for.
   - **Verdict:** if both verdicts agree, emit that verdict. If they disagree,
     emit the more conservative one (REQUEST_CHANGES > APPROVE_WITH_CHANGES >
     APPROVE_SHIP_AS_IS) and add a note explaining the disagreement.

## Output Format

```markdown
# Cross-Review: PR #<num> — <title>

**Claude verdict:** <verdict>
**Codex verdict:**  <verdict>
**Combined verdict:** <more conservative of the two>

## Agreed findings (both reviewers)
- `path:LN` — <issue>

## Claude-only findings
- `path:LN` — <issue> [only Claude]

## Codex-only findings
- `path:LN` — <issue> [only Codex]

## Verdict disagreement (if any)
- Claude said X because ..., Codex said Y because ... . Combined: more
  conservative wins, which is <Y> because <reason>.

VERDICT: <combined>
```

## Failure Modes

- **codex exec hangs:** caught by the 300s timeout. Emit `CODEX_TIMEOUT` and
  fall back to Claude-only review output. Don't block.
- **codex produces unparseable output:** emit `CODEX_MALFORMED — using Claude
  review only`, attach raw Codex output for debugging.
- **Both reviewers fail:** emit `ERROR: both reviewers failed. Investigate.`
  with full logs. This is rare and should escalate.

## Why This Command Exists

Single-model review misses ~15% of issues that a second model catches (observed
on coleam00/GitHubIssueTriager dogfood, April 2026, n=20 PRs). The cost of a
Codex call (~$0.10 per PR) is negligible relative to the cost of shipping a
regression. Fallback gracefully when Codex isn't available so this never blocks
development.

Reference: EXTREPS distill, coleam00/GitHubIssueTriager, diamond_4.
