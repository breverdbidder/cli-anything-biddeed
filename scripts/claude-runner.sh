#!/bin/bash
# claude-runner.sh — executes Claude Code on Hetzner as summit user
# TIER 1 (PRIMARY per mem:18 cost-discipline): Max OAuth → claude-sonnet-4-6
# TIER 2 (FALLBACK only): cliproxy → Gemini (if OAuth creds missing)
# Apr16 2026: Patched to honor cost-discipline — OAuth was dead code before.
# Usage: claude-runner.sh ISSUE_NUMBER
set -e
ISSUE="$1"
if [ -z "$ISSUE" ]; then
  echo "ERROR: ISSUE number required as arg 1"
  exit 1
fi
cd "/home/summit/summit-${ISSUE}/work"

# Model selection: env override > default (Sonnet 4.6 for code per cost-discipline)
CLAUDE_MODEL="${CLAUDE_MODEL:-claude-sonnet-4-6}"

# Auth routing: Max OAuth PRIMARY (Tier 1), cliproxy FALLBACK (Tier 2 only)
if [ -f /home/summit/.claude/.credentials.json ] || [ -f /home/summit/.claude/credentials.json ]; then
  # TIER 1: Max OAuth — Sonnet 4.6 for code/precision, Opus 4.7 if env requests
  unset ANTHROPIC_API_KEY
  unset ANTHROPIC_BASE_URL
  MODEL_FLAG="--model $CLAUDE_MODEL"
  echo "=== TIER 1: Max OAuth → $CLAUDE_MODEL ==="
elif [ -n "$CLIPROXY_KEY" ]; then
  # TIER 2: cliproxy → Gemini fallback when OAuth unavailable
  export ANTHROPIC_BASE_URL="http://127.0.0.1:8317"
  export ANTHROPIC_API_KEY="$CLIPROXY_KEY"
  MODEL_FLAG="--model gemini-pro"
  echo "=== TIER 2: cliproxy → Gemini (OAuth credentials not found) ==="
else
  echo "::error::No auth path — neither Max OAuth creds nor CLIPROXY_KEY available"
  exit 1
fi
export IS_SANDBOX=1

PROMPT=$(cat "/home/summit/summit-${ISSUE}-prompt.txt")
echo "=== Launching claude -p on SUMMIT #${ISSUE} ==="
echo "Prompt length: ${#PROMPT}"
echo "Model flag: ${MODEL_FLAG:-<default>}"

timeout 6000 claude -p "$PROMPT" \
  ${MODEL_FLAG} \
  --dangerously-skip-permissions \
  --max-turns 200 \
  2>&1 | tee "/home/summit/summit-${ISSUE}-output.log"
