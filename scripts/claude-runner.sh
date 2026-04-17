#!/bin/bash
# claude-runner.sh — executes Claude Code on Hetzner as summit user
# Apr 16 2026 REVERT: OAuth creds expired on Hetzner → Gemini primary for tonight
# TIER ORDER (TEMP): cliproxy→Gemini PRIMARY, Max OAuth FALLBACK (currently 401)
# RESTORE AFTER OAUTH REFRESH (Apr 17+): flip back to OAuth primary (see commit a55544be)
# Usage: claude-runner.sh ISSUE_NUMBER
set -e
ISSUE="$1"
if [ -z "$ISSUE" ]; then
  echo "ERROR: ISSUE number required as arg 1"
  exit 1
fi
cd "/home/summit/summit-${ISSUE}/work"

# Model selection: env override wins, default gemini-pro while OAuth is stale
CLAUDE_MODEL="${CLAUDE_MODEL:-gemini-pro}"

# Auth routing — Gemini primary tonight (flipped Apr16 due to expired OAuth)
if [ -n "$CLIPROXY_KEY" ]; then
  export ANTHROPIC_BASE_URL="http://127.0.0.1:8317"
  export ANTHROPIC_API_KEY="$CLIPROXY_KEY"
  MODEL_FLAG="--model $CLAUDE_MODEL"
  echo "=== TIER 2: cliproxy -> $CLAUDE_MODEL (Gemini primary while OAuth expired) ==="
elif [ -f /home/summit/.claude/.credentials.json ] || [ -f /home/summit/.claude/credentials.json ]; then
  unset ANTHROPIC_API_KEY
  unset ANTHROPIC_BASE_URL
  MODEL_FLAG="--model ${CLAUDE_MODEL/#gemini-pro/claude-sonnet-4-6}"
  echo "=== TIER 1 FALLBACK: Max OAuth -> ${MODEL_FLAG#--model } (CLIPROXY_KEY missing) ==="
else
  echo "::error::No auth path available"
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
