# SUMMIT Dispatch — Usage & Validation Reference

## How to Dispatch

### Via GitHub CLI

```bash
# Single issue
gh workflow run "Claude Code Direct — Parallel SUMMITs" \
  -R breverdbidder/cli-anything-biddeed \
  -f issues=440

# Multiple issues (parallel matrix)
gh workflow run "Claude Code Direct — Parallel SUMMITs" \
  -R breverdbidder/cli-anything-biddeed \
  -f issues="440,441,442"
```

### Via GitHub API

```bash
curl -X POST \
  -H "Authorization: token $GH_PAT" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/breverdbidder/cli-anything-biddeed/actions/workflows/claude-code-direct.yml/dispatches" \
  -d '{"ref":"main","inputs":{"issues":"440"}}'
```

## Validation Checks

The workflow runs two layers of validation before any Hetzner SSH or Claude Code invocation:

### 1. Pre-matrix validation (`validate-input` job)

Runs before the matrix expands. Catches:

| Error | Meaning |
|-------|---------|
| `Empty 'issues' input. Dispatch rejected.` | You dispatched with `issues=""` or omitted it entirely. Supply at least one issue number. |

### 2. Per-issue validation (first step in `run-claude-code` job)

Runs once per matrix element. Catches:

| Error | Meaning |
|-------|---------|
| `Empty issue number passed to workflow` | A matrix element resolved to empty/whitespace. Check your comma-separated list for trailing commas. |
| `Issue number 'X' is not a positive integer` | Non-numeric value in the issues list (e.g., `issues="abc"`). |
| `Refusing to run against dead placeholder issue #379` | Issue #379 is a dead placeholder. See escape hatch below. |
| `Issue #N does not exist (HTTP 404)` | The issue number doesn't exist in the repo. |
| `Issue #N is not open (state=closed)` | The issue is closed. Only open issues are processed. |
| `Issue #N does not have 'summit' label` | Warning only — the run proceeds but flags the missing label. |

## Escape Hatch: Running Against #379

Issue #379 is blocked by default because it was a dead placeholder that caused orphan runs. To intentionally run against it:

1. Go to **Settings → Variables → Actions** in the `cli-anything-biddeed` repo
2. Create or set the repository variable `ALLOW_PLACEHOLDER` to `1`
3. Dispatch as normal with `issues=379`
4. Remove the variable after use to re-enable the guard

## Troubleshooting

**Workflow completes instantly with no matrix jobs:**
The `fromJson(format('[{0}]', inputs.issues))` expansion produced `[]`. This means the input was empty. The `validate-input` job should catch this first — if it didn't, check that `needs: validate-input` is present on the `run-claude-code` job.

**Workflow fails at SSH step:**
Not a validation issue. Check Hetzner connectivity and SSH key secrets.

**Issue passes validation but Claude Code does nothing useful:**
The issue may be open but lack actionable content. Validation confirms the issue exists and is open — it doesn't evaluate the issue body.
