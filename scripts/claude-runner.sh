#!/bin/bash
# claude-runner.sh — executes Claude Code on Hetzner as summit user
#
# 2026-04-20: RESTORED tier order — Max OAuth primary / cliproxy fallback.
#   The Apr 16 temporary revert that inverted this was never restored, causing
#   every post-Apr16 dispatch (4 days) to silently run on Gemini Pro via cliproxy,
#   which cannot do agentic file operations reliably. Result: ghost-success pattern
#   (GHA reports job=success, no commits produced, no work done). See dispatch
#   1bbe2680-e45c-4f4d-9455-32e44af3c516 (Brevard ROD recon, 2026-04-20) which
#   surfaced this — 5min runtime, 1 byte output, no commit.
#
#   New behavior:
#     - Tier 1 (Max OAuth): used whenever /home/summit/.claude/credentials.json exists.
#       If OAuth tokens are expired (401), claude -p fails — this is the DESIRED
#       failure mode. Loud > silent.
#     - Tier 2 (cliproxy/Gemini): only used when OAuth creds file is absent, AND
#       only allowed for prompts that do NOT contain "PUSHED commit:" marker.
#       Gemini cannot do agentic file ops, so any commit-requiring dispatch must
#       abort here rather than produce ghost-success.
#     - Post-hoc guard: if claude -p produces <50 bytes of output AND the prompt
#       expected a commit, treat as failure regardless of claude -p exit code.
#
# Usage: claude-runner.sh ISSUE_NUMBER

set -eo pipefail
ISSUE="$1"
if [ -z "$ISSUE" ]; then
  echo "ERROR: ISSUE number required as arg 1"
  exit 1
fi
cd "/home/summit/summit-${ISSUE}/work"

PROMPT_FILE="/home/summit/summit-${ISSUE}-prompt.txt"
OUTPUT_LOG="/home/summit/summit-${ISSUE}-output.log"

# Model selection: env override wins, default claude-sonnet-4-6 for Tier 1
CLAUDE_MODEL="${CLAUDE_MODEL:-claude-sonnet-4-6}"

# Detect whether the prompt requires a real commit (ghost-success indicator)
PROMPT_REQUIRES_COMMIT="no"
if grep -q "PUSHED commit:" "$PROMPT_FILE" 2>/dev/null; then
  PROMPT_REQUIRES_COMMIT="yes"
fi

# Auth routing — Max OAuth primary (restored from Apr 16 temporary revert)
if [ -f /home/summit/.claude/.credentials.json ] || [ -f /home/summit/.claude/credentials.json ]; then
  unset ANTHROPIC_API_KEY
  unset ANTHROPIC_BASE_URL
  MODEL_FLAG="--model ${CLAUDE_MODEL/#gemini-pro/claude-sonnet-4-6}"
  TIER="1"
  echo "=== TIER 1: Max OAuth -> ${MODEL_FLAG#--model } ==="
elif [ -n "$CLIPROXY_KEY" ]; then
  # Tier 2 fallback: cliproxy/Gemini. CHAT-ONLY. Cannot do agentic file ops.
  if [ "$PROMPT_REQUIRES_COMMIT" = "yes" ]; then
    echo "::error::Tier 2 cliproxy/Gemini is active but prompt expects a commit (PUSHED commit: marker detected). Tier 2 cannot do agentic file operations reliably — running claude -p here would produce a ghost-success. Refusing to launch. Fix: refresh Max OAuth creds on Hetzner at /home/summit/.claude/.credentials.json (or /root/.claude/). Exiting 2."
    exit 2
  fi
  export ANTHROPIC_BASE_URL="http://127.0.0.1:8317"
  export ANTHROPIC_API_KEY="$CLIPROXY_KEY"
  CLAUDE_MODEL_T2="${CLAUDE_MODEL/#claude-sonnet-4-6/gemini-pro}"
  MODEL_FLAG="--model $CLAUDE_MODEL_T2"
  TIER="2"
  echo "=== TIER 2 FALLBACK: cliproxy -> $CLAUDE_MODEL_T2 (CHAT-ONLY; Max OAuth creds absent on Hetzner) ==="
else
  echo "::error::No auth path available — neither OAuth creds file nor CLIPROXY_KEY env var is set"
  exit 1
fi
export IS_SANDBOX=1

PROMPT=$(cat "$PROMPT_FILE")
echo "=== Launching claude -p on SUMMIT #${ISSUE} (Tier ${TIER}) ==="
echo "Prompt length: ${#PROMPT}"
echo "Model flag: ${MODEL_FLAG:-<default>}"
echo "Prompt requires commit: ${PROMPT_REQUIRES_COMMIT}"

CLAUDE_EXIT=0
timeout 6000 claude -p "$PROMPT" \
  ${MODEL_FLAG} \
  --dangerously-skip-permissions \
  --max-turns 200 \
  2>&1 | tee "$OUTPUT_LOG" || CLAUDE_EXIT=$?

OUTPUT_BYTES=$(wc -c < "$OUTPUT_LOG" 2>/dev/null || echo 0)
echo "=== claude -p complete: exit=${CLAUDE_EXIT} output_bytes=${OUTPUT_BYTES} tier=${TIER} ==="

# Post-hoc ghost-success guard: if prompt expected a commit but output is trivially
# small, treat as failure regardless of claude -p exit code. Catches cases where
# the LLM returns a minimal chat response instead of doing actual work.
if [ "$PROMPT_REQUIRES_COMMIT" = "yes" ] && [ "$OUTPUT_BYTES" -lt 50 ]; then
  echo "::error::Ghost-success detected: prompt expected a commit (PUSHED commit: marker) but claude -p produced only ${OUTPUT_BYTES} bytes of output. claude -p exit code was ${CLAUDE_EXIT}. Treating as failure to prevent silent pipeline corruption."
  exit 3
fi

exit $CLAUDE_EXIT
