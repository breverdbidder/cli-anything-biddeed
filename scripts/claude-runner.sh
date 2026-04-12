#!/bin/bash
# claude-runner.sh — executes Claude Code on Hetzner as summit user
# Usage: claude-runner.sh ISSUE_NUMBER
set -e
ISSUE="$1"
if [ -z "$ISSUE" ]; then
  echo "ERROR: ISSUE number required as arg 1"
  exit 1
fi
cd "/home/summit/summit-${ISSUE}/work"
unset ANTHROPIC_API_KEY
export IS_SANDBOX=1
PROMPT=$(cat "/home/summit/summit-${ISSUE}-prompt.txt")
# [SUPERPOWERS ACTIVATION TEST — treatment branch]
# Prepend mandatory skill-activation preamble to the SUMMIT prompt.
# A/B test against main. Remove this block to revert.
SKILL_PREAMBLE='MANDATORY PREFLIGHT — READ AND FOLLOW BEFORE ANY WORK:
1. Read .claude/skills/brainstorming/SKILL.md — refine the spec before coding.
2. Read .claude/skills/writing-plans/SKILL.md — break work into 2-5 min tasks with exact file paths.
3. Read .claude/skills/using-git-worktrees/SKILL.md — create an isolated worktree for EVERY parallel subtask. No concurrent edits on the same branch.
4. Read .claude/skills/subagent-driven-development/SKILL.md — dispatch fresh subagent per task, two-stage review (spec compliance → code quality) before declaring any task done.
5. Read .claude/skills/verification-before-completion/SKILL.md — no ghost-success. Verify with evidence before EG14 gate.
These are BLOCKING gates, not suggestions. EG14 will verify worktree usage and two-stage review were performed.

---
ORIGINAL SUMMIT TASK FOLLOWS:

'
PROMPT="${SKILL_PREAMBLE}${PROMPT}"
echo "=== [TREATMENT] Skill-activation preamble injected. Prompt length: ${#PROMPT} ==="

echo "=== Launching claude -p on SUMMIT #${ISSUE} ==="
echo "Prompt length: ${#PROMPT}"
timeout 6000 claude -p "$PROMPT" \
  --dangerously-skip-permissions \
  --max-turns 200 \
  2>&1 | tee "/home/summit/summit-${ISSUE}-output.log"
