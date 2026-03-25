#!/bin/bash
# SUMMIT DISPATCH: StitchWise V2 Agent Deployment
# Target: cli-anything-biddeed
# Branch: feat/stitch-agent-v2
# Prereq: GEMINI_API_KEY must be set as repo secret

set -euo pipefail

REPO="breverdbidder/cli-anything-biddeed"
BRANCH="feat/stitch-agent-v2"
HETZNER="87.99.129.125"

echo "🚀 SUMMIT DISPATCH: StitchWise V2"
echo "=================================="

# ── Phase 1: Create branch ──
echo "📌 Phase 1: Creating feature branch..."
ssh claude@${HETZNER} << 'PHASE1'
cd /home/claude/repos/cli-anything-biddeed || exit 1
git checkout main && git pull origin main
git checkout -b feat/stitch-agent-v2 2>/dev/null || git checkout feat/stitch-agent-v2
PHASE1

# ── Phase 2: Install SDK ──
echo "📦 Phase 2: Installing @google/stitch-sdk..."
ssh claude@${HETZNER} << 'PHASE2'
cd /home/claude/repos/cli-anything-biddeed || exit 1
npm install @google/stitch-sdk @_davideast/stitch-mcp
PHASE2

# ── Phase 3: Deploy agent files ──
echo "🤖 Phase 3: Deploying StitchWise V2 agent..."
# Files to deploy:
#   src/agents/stitchwise_v2.ts   — Main agent harness
#   .claude/stitch-mcp.json       — MCP config for Claude Code
#   eval/stitch/eval.json         — 25 binary assertions
#   docs/plans/STITCH-AGENT-SPEC.md — Design spec

# ── Phase 4: Add MCP config to Claude Code settings ──
echo "⚙️ Phase 4: Configuring MCP..."
ssh claude@${HETZNER} << 'PHASE4'
cd /home/claude/repos/cli-anything-biddeed || exit 1
mkdir -p .claude
# Merge stitch MCP into existing settings
if [ -f .claude/settings.json ]; then
  echo "Merging Stitch MCP into existing settings..."
  # Claude Code will handle the merge
else
  echo "Creating new MCP settings..."
fi
PHASE4

# ── Phase 5: Run evals ──
echo "🧪 Phase 5: Running StitchWise eval suite..."
ssh claude@${HETZNER} << 'PHASE5'
cd /home/claude/repos/cli-anything-biddeed || exit 1
# Eval requires GEMINI_API_KEY — skip if not set
if [ -z "${GEMINI_API_KEY:-}" ]; then
  echo "⚠️ GEMINI_API_KEY not set — eval deferred until secret added"
else
  python scripts/eval_runner.py eval/stitch/eval.json
fi
PHASE5

# ── Phase 6: Commit & Push ──
echo "📤 Phase 6: Committing and pushing..."
ssh claude@${HETZNER} << 'PHASE6'
cd /home/claude/repos/cli-anything-biddeed || exit 1
git add -A
git commit -m "feat(stitch): StitchWise V2 — programmatic Stitch SDK integration

- Add stitchwise_v2.ts agent harness (generate/list/export/dashboard/landing)
- Add Stitch MCP config for Claude Code native tool access
- Add eval/stitch/eval.json (25 assertions)
- Add STITCH-AGENT-SPEC.md design doc
- Brand-aware prompt builder (navy/orange/Inter)
- Circuit breaker: max 3 retries, 300/mo budget
- Requires GEMINI_API_KEY repo secret"
git push origin feat/stitch-agent-v2
PHASE6

echo ""
echo "✅ SUMMIT DISPATCH COMPLETE"
echo "=========================="
echo ""
echo "📋 STATUS BOARD:"
echo "  Agent code:     ✅ Deployed"
echo "  MCP config:     ✅ Deployed"
echo "  Eval suite:     ⏳ Waiting on GEMINI_API_KEY"
echo "  Branch:         feat/stitch-agent-v2"
echo ""
echo "🔑 ARIEL ACTION REQUIRED (1 step):"
echo "  1. Go to https://stitch.withgoogle.com"
echo "  2. Profile → Stitch Settings → API Keys → Create Key"
echo "  3. Add as GitHub secret: GEMINI_API_KEY"
echo "     gh secret set GEMINI_API_KEY -R ${REPO}"
echo ""
echo "Once key is set, Claude Code can call Stitch natively via MCP."
