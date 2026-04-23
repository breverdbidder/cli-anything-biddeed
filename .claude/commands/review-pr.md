---
description: Fresh-context PR review. Never share context with the implementer.
argument-hint: "[PR number, optional — defaults to PR for current branch]"
---

# /review-pr — Fresh-Context PR Review

You are reviewing a pull request you did NOT write. The session that implemented
this PR is NOT your session. You have zero bias toward approving this work — your
job is to find what's wrong, not ratify what's there.

**Hard rule:** If you see any evidence in this context window that you wrote,
planned, or touched the code being reviewed in this PR, STOP and respond with:
`ERROR: review-pr invoked in implementer context. Run /clear first, then retry.`
Do not proceed.

## Inputs

PR to review: `$ARGUMENTS` (if empty, resolve the PR for the current branch via
`gh pr view --json number,title,body,headRefName,files,url`).

## Process

1. **Resolve PR metadata** — `gh pr view <n> --json number,title,body,files,url`
   to get title, body, and the list of changed files. Capture the PR URL.

2. **Resolve linked issue** — scan the PR body for `Closes #N`, `Fixes #N`, or
   `Resolves #N`. If found, `gh issue view <N> --json title,body` and use the
   issue body as the spec against which to check the implementation. If no
   linked issue, say so and review against the PR's own stated intent.

3. **Compute the diff** — `git diff origin/main...HEAD` (or the PR's base branch).
   Keep the full diff in mind; the review must cover the complete change set.

4. **Run three independent review passes.** Use the Task tool three times in
   parallel (one Task call per pass, inline prompts — do NOT rely on named
   subagents that may not exist in this repo):

   - **Correctness & regression pass.** Does the code do what the issue/PR body
     says? Are any existing behaviors silently broken? Check type safety, off-by-
     one, null handling, error propagation, concurrency, and whether the diff
     touches files the scope didn't cover.

   - **Silent-failure hunter pass.** Scan for empty catches, ignored return codes,
     `|| true` suppressing real errors, missing `set -e` in bash, swallowed
     promises, uncaught exceptions, or any pattern where a failure could be
     reported as success. This is the highest-signal pass for SUMMIT work.

   - **Test coverage delta pass.** What tests were added/modified? Do they cover
     the happy path, error paths, edge cases named in the issue? Does the diff
     add code paths without matching tests? If the repo has no test infra, note
     it and check whether the PR at least includes manual verification steps.

5. **Synthesize.** Merge findings from the three passes. De-duplicate. Rank by
   severity: Blocking / Concern / Nit. Preserve the specific file:line
   references.

6. **Emit a verdict.** The FINAL line of your output MUST be exactly one of:

   ```
   VERDICT: APPROVE_SHIP_AS_IS
   VERDICT: APPROVE_WITH_CHANGES
   VERDICT: REQUEST_CHANGES
   ```

   No other verdict strings. Downstream automation greps for these literals.

## Output Format

```markdown
# Review: PR #<num> — <title>

**PR:** <url>
**Linked issue:** #<N> — <title> (or: none)
**Diff stats:** <N files changed, +X −Y>

## Blocking
- `path/to/file:LN` — <issue>. Evidence: <snippet or quote>. Fix: <proposal>.

## Concerns
- ...

## Nits
- ...

## Coverage
- Tests added: <list>. Tests missing: <list>.

## Scope fidelity
- Issue asked for X, Y, Z. PR delivers: X ✓, Y ✓, Z ✗ (missed because ...).

VERDICT: APPROVE_WITH_CHANGES
```

## Failure Modes

- **No PR for current branch:** exit with `ERROR: no PR open for <branch>.
  Create the PR first (gh pr create).`
- **Diff empty:** exit with `ERROR: PR diff is empty. Nothing to review.`
- **Cannot reach GitHub:** exit with `ERROR: gh CLI unauthenticated or network
  unreachable. Fix: gh auth status.`

## Why This Command Exists

Reviewing your own PR in the same context window where you wrote it produces
~30% false-approve rate in practice (observed on coleam00/GitHubIssueTriager
dogfood runs, April 2026). A fresh context has no prior commitment to the
implementation's correctness and catches silent-failure patterns the implementer
rationalized away. This command enforces the separation structurally — not via
prompt discipline, which fails.

Reference: EXTREPS distill, coleam00/GitHubIssueTriager, diamond_4.
