# SUMMIT Dispatch Guide

## How to Dispatch

### Via GitHub CLI (recommended)

```bash
# Single issue
gh workflow run claude-code-direct.yml -f issues=440

# Multiple issues (parallel)
gh workflow run claude-code-direct.yml -f issues="440,441,442"
```

### Via GitHub API

```bash
curl -X POST \
  -H "Authorization: token $GH_PAT" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/breverdbidder/cli-anything-biddeed/actions/workflows/claude-code-direct.yml/dispatches \
  -d '{"ref":"main","inputs":{"issues":"440"}}'
```

### Via GitHub UI

1. Go to Actions > "Claude Code Direct — Parallel SUMMITs"
2. Click "Run workflow"
3. Enter comma-separated issue numbers (e.g., `440,441`)
4. Click "Run workflow"

## Input Validation

The workflow validates every issue number before running Claude Code on Hetzner. Validation happens in two stages:

### Stage 1: `validate-input` job

Runs before any matrix expansion. Rejects the entire dispatch if `issues` input is empty.

### Stage 2: Per-issue validation (first step in each matrix job)

Each matrix element is checked for:

| Check | Behavior on failure |
|-------|-------------------|
| Empty/whitespace | Hard fail with `::error` |
| Non-numeric value | Hard fail with `::error` |
| Issue #379 (dead placeholder) | Hard fail unless `ALLOW_PLACEHOLDER=1` |
| Issue does not exist (HTTP != 200) | Hard fail with `::error` |
| Issue is not open | Hard fail with `::error` |
| Missing `summit` label | Warning only, proceeds |

## Validation Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| `Empty 'issues' input` | Dispatch sent with blank issues field | Supply at least one issue number |
| `Empty issue number passed to workflow` | Matrix element resolved to empty string | Check comma formatting (no trailing commas) |
| `Issue number 'X' is not a positive integer` | Non-numeric value in issues list | Use only integer issue numbers |
| `Refusing to run against dead placeholder issue #379` | Issue #379 is a dead placeholder | Use a real issue number, or set `ALLOW_PLACEHOLDER=1` |
| `Issue #X does not exist` | GitHub API returned non-200 | Verify the issue number exists in the repo |
| `Issue #X is not open` | Issue is closed | Reopen the issue or use an open one |

## Escape Hatches

### Running against #379 intentionally

If you genuinely need to test against the placeholder issue #379:

1. Go to repo Settings > Secrets and variables > Actions > Variables
2. Add or set `ALLOW_PLACEHOLDER` = `1`
3. Dispatch normally
4. Remove the variable after testing

## Architecture

```
dispatch(issues="440,441")
  |
  +- validate-input job (ubuntu-latest, ~5s)
  |   +- Reject if issues is empty
  |
  +- run-claude-code job (needs: validate-input)
      +- matrix: [440, 441]
      |
      +- [440] Validate -> Announce -> SSH Hetzner -> Claude Code
      +- [441] Validate -> Announce -> SSH Hetzner -> Claude Code
```

Each matrix element runs independently with `fail-fast: false` — one failing issue does not cancel others.
