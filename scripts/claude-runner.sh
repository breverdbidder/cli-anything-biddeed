#!/bin/bash
# claude-runner.sh — executes Claude Code on Hetzner as summit user
# Routes via cliproxy (127.0.0.1:8317) → Gemini (paid zonewise.ai pool)
# No Anthropic OAuth needed, no pay-as-you-go ANTHROPIC_API_KEY needed
# Usage: claude-runner.sh ISSUE_NUMBER
set -e
ISSUE="$1"
if [ -z "$ISSUE" ]; then
  echo "ERROR: ISSUE number required as arg 1"
  exit 1
fi
cd "/home/summit/summit-${ISSUE}/work"

# Route Claude Code through cliproxy → Gemini backend
# Gateway key + base URL are passed via sudo env from the GHA workflow
# If not set, fall back to OAuth (for backward compat only)
if [ -n "$CLIPROXY_KEY" ]; then
  export ANTHROPIC_BASE_URL="http://127.0.0.1:8317"
  export ANTHROPIC_API_KEY="$CLIPROXY_KEY"
  MODEL_FLAG="--model gemini-flash"
  echo "=== Using cliproxy → Gemini backend ==="
else
  unset ANTHROPIC_API_KEY
  MODEL_FLAG=""
  echo "=== Using Claude Max OAuth (legacy path) ==="
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
