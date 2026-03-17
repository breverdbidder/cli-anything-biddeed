#!/bin/bash
# setup-visual-explainer.sh — Zero human-in-the-loop installer
# Part of cli-anything-biddeed session hygiene
# Run: bash scripts/setup-visual-explainer.sh

set -e

SKILL_DIR="$HOME/.claude/skills/visual-explainer"
CMD_DIR="$HOME/.claude/commands"
DIAGRAMS_DIR="$HOME/.agent/diagrams"

echo "╔══════════════════════════════════════════╗"
echo "║  visual-explainer Skill Installer        ║"
echo "║  Source: breverdbidder/visual-explainer   ║"
echo "╚══════════════════════════════════════════╝"

# 1. Clone or update skill
if [ -d "$SKILL_DIR/.git" ]; then
    echo "[1/4] Updating existing skill..."
    cd "$SKILL_DIR" && git pull origin main --quiet
else
    echo "[1/4] Cloning skill from fork..."
    mkdir -p "$(dirname "$SKILL_DIR")"
    git clone --quiet https://github.com/breverdbidder/visual-explainer.git "$SKILL_DIR"
fi

# 2. Install slash commands
mkdir -p "$CMD_DIR"
echo "[2/4] Installing slash commands..."
CMDS=0
for cmd in "$SKILL_DIR/plugins/visual-explainer/commands/"*.md; do
    cp "$cmd" "$CMD_DIR/$(basename "$cmd")"
    CMDS=$((CMDS+1))
done
echo "       $CMDS commands installed"

# 3. Create diagrams output directory
mkdir -p "$DIAGRAMS_DIR"
echo "[3/4] Output directory: $DIAGRAMS_DIR"

# 4. Verify
echo "[4/4] Verification..."
PASS=0
FAIL=0

check() {
    if [ -f "$1" ]; then
        echo "  ✓ $2"
        PASS=$((PASS+1))
    else
        echo "  ✗ $2 MISSING"
        FAIL=$((FAIL+1))
    fi
}

check "$SKILL_DIR/plugins/visual-explainer/SKILL.md" "SKILL.md"
check "$SKILL_DIR/plugins/visual-explainer/templates/biddeed-brand-preset.html" "BidDeed brand preset"
check "$SKILL_DIR/plugins/visual-explainer/eval/eval.json" "AUTOLOOP eval.json"
check "$CMD_DIR/diff-review.md" "/diff-review command"
check "$CMD_DIR/project-recap.md" "/project-recap command"
check "$CMD_DIR/generate-slides.md" "/generate-slides command"

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo "═══ INSTALL COMPLETE ($PASS/$PASS checks passed) ═══"
    echo ""
    echo "Commands available in Claude Code:"
    echo "  /diff-review          Visual diff review"
    echo "  /plan-review          Plan vs codebase comparison"
    echo "  /project-recap        Mental model rebuild"
    echo "  /generate-web-diagram Interactive HTML diagram"
    echo "  /generate-visual-plan Visual implementation plan"
    echo "  /generate-slides      Magazine-quality slide deck"
    echo "  /fact-check           Verify docs against code"
else
    echo "═══ INSTALL INCOMPLETE ($FAIL checks failed) ═══"
    exit 1
fi
