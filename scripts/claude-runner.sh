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
echo "=== Launching claude -p on SUMMIT #${ISSUE} ==="
echo "Prompt length: ${#PROMPT}"
timeout 6000 claude -p "$PROMPT" \
  --dangerously-skip-permissions \
  --max-turns 200 \
  2>&1 | tee "/home/summit/summit-${ISSUE}-output.log"
