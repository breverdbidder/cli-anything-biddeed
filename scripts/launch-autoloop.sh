#!/bin/bash
# AUTOLOOP LAUNCHER — Run from cli-anything-biddeed root
# Usage: bash scripts/launch-autoloop.sh [zonewise|auction|reports|all]

SKILL="${1:-zonewise}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "🔄 AUTOLOOP: Launching $SKILL self-improvement loop"
echo "📍 Repo: $REPO_ROOT"
echo "⏰ $(date)"
echo ""

if [ "$SKILL" = "all" ]; then
  SKILLS="zonewise auction reports"
else
  SKILLS="$SKILL"
fi

for S in $SKILLS; do
  EVAL_FILE="$REPO_ROOT/$S/eval/eval.json"
  if [ ! -f "$EVAL_FILE" ]; then
    echo "❌ Missing: $EVAL_FILE"
    exit 1
  fi
  echo "✅ Found: $EVAL_FILE"
done

PROMPT="Run a self-improvement loop on the $SKILL skill.

Eval file: $SKILL/eval/eval.json
Eval runner: python scripts/eval_runner.py --eval-file $SKILL/eval/eval.json --outputs-dir $SKILL/eval_outputs/

For each iteration:
1. Run the skill against all 5 test prompts in eval.json
2. Save outputs to $SKILL/eval_outputs/{test_id}.json (and .docx for report tests)
3. Run eval_runner.py and read the score
4. If any assertions fail, make ONE targeted change to the skill .md file to fix the failure
5. Re-run the tests and re-score
6. If score improved: git add + git commit with message 'autoloop: {score}% -> {new_score}% [{assertion_fixed}]'
7. If score dropped: git checkout to revert and try a DIFFERENT change
8. Log each iteration to $SKILL/eval/autoloop_log.jsonl

RULES:
- Make only ONE change per iteration to isolate what helped
- Never stop. Keep looping until perfect score (25/25) or I interrupt you
- Do not ask if I should keep going or is this a good stopping point
- I might be asleep. You are autonomous
- If stuck after 5 consecutive failed attempts on same assertion, skip it and target next failure
- Maximum 50 iterations per session"

echo ""
echo "🚀 Launching Claude Code with auto-mode..."
echo ""

cd "$REPO_ROOT"
mkdir -p "$SKILL/eval_outputs"

claude --auto "$PROMPT"
