#!/bin/bash
# Claude Code Session Hygiene Setup
# Run this ONCE on any dev machine to install mandatory plugins
# Created: Mar 15, 2026 | Updated: Mar 29, 2026 (claude-2x-statusline replaces cc-status-line)

set -e

echo "=== Claude Code Session Hygiene Setup ==="
echo ""

# 1. Install claude-2x-statusline (RepoEval 86 → ADOPT, replaces cc-status-line)
echo "[1/3] Installing claude-2x-statusline (Full tier)..."
if [ ! -d "$HOME/.claude/cc-2x-statusline" ]; then
  git clone https://github.com/Nadav-Fux/claude-2x-statusline.git ~/.claude/cc-2x-statusline
  bash ~/.claude/cc-2x-statusline/install.sh <<< "3"
  echo "✅ claude-2x-statusline installed (Full tier)"
else
  echo "✅ claude-2x-statusline already installed at ~/.claude/cc-2x-statusline"
fi
# Remove old cc-status-line if present
npm uninstall -g cc-status-line 2>/dev/null || true
echo ""

# 2. Install cctop (Claude Code Sessions Dashboard)
echo "[2/3] Installing cctop..."
if command -v jq >/dev/null 2>&1 && command -v uv >/dev/null 2>&1; then
    curl -fsSL https://raw.githubusercontent.com/DeanLa/cctop/main/install.sh | bash
    echo "✅ cctop installed — run 'cctop' in a separate terminal"
else
    echo "⚠️  cctop requires jq and uv. Install them first:"
    echo "    brew install jq  (macOS) or apt install jq (Linux)"
    echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"
fi
echo ""

# 3. Context7 - must be installed from within Claude Code
echo "[3/3] Context7 Plugin"
echo "  → Open Claude Code and run: /plugin"
echo "  → Navigate to Discover tab"
echo "  → Search for 'context7'"
echo "  → Install it"
echo ""

echo "=== Setup Complete ==="
echo ""
echo "REMEMBER:"
echo "  • Kill sessions at 50% context (watch the claude-2x-statusline bar)"
echo "  • NEVER use /compact — start fresh instead"
echo "  • Run cctop in a separate terminal to monitor all sessions"
echo "  • Use Superpowers execute-plan for heavy work (sub-agents)"
echo ""
