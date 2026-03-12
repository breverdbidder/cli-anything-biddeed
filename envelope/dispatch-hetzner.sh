#!/usr/bin/env bash
# ============================================================================
# HETZNER DISPATCH — Envelope Squad Claude Code Session
# ============================================================================
# Usage: ssh into Hetzner → run this script
# Requires: claude CLI on Max plan
# ============================================================================

set -euo pipefail

REPO_DIR="$HOME/repos/cli-anything-biddeed"
SESSION_NAME="envelope-squad-$(date +%Y%m%d-%H%M)"

echo "🏔️  ENVELOPE SQUAD — Hetzner Claude Code Dispatch"
echo "   Session: ${SESSION_NAME}"
echo "   Time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

# Ensure repo is up to date
cd "${REPO_DIR}" 2>/dev/null || {
  echo "Cloning repo..."
  git clone https://github.com/breverdbidder/cli-anything-biddeed.git "${REPO_DIR}"
  cd "${REPO_DIR}"
}
git pull origin main

# Navigate to envelope harness
cd envelope/agent-harness

echo "━━━ SESSION 1: Schema + Foundation ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Dispatching to Claude Code..."
echo ""

# Launch Claude Code with the envelope task
# Using --dangerously-skip-permissions until --enable-auto-mode is live
claude --dangerously-skip-permissions --session "${SESSION_NAME}" << 'CLAUDE_PROMPT'
You are executing the Envelope Squad deployment. Read envelope/CLAUDE.md and envelope/TODO.md first.

Execute Phase 1 and Phase 2 from TODO.md:

PHASE 1: Run the Supabase migration.
- Use the Supabase Management API or psql to execute migrations/001_envelope_cache.sql
- Supabase URL: https://mocerqjnksmhcjzxrewo.supabase.co
- Verify the table, views, and functions were created

PHASE 2: Test each agent individually with Palm Bay.
- Run each of the 7 agents one at a time
- Verify output file exists and has records after each
- Fix any errors before moving to next agent

PHASE 3: Run the full pipeline.
- chmod +x cli_anything.envelope.sh
- ./cli_anything.envelope.sh palm_bay
- Verify Supabase has data

After each completed task, update TODO.md marking [x] and push to GitHub.

Cost discipline: $10/session max. No paid API calls. You're on Max plan = FREE.
CLAUDE_PROMPT

echo ""
echo "🏔️  Session complete."
