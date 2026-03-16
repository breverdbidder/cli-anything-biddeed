#!/bin/bash
# Claude Code Session Hygiene Setup
# Run this ONCE on any dev machine to install mandatory plugins
# Created: Mar 15, 2026

set -e

echo "=== Claude Code Session Hygiene Setup ==="
echo ""

# 1. Install CC Status Line
echo "[1/2] Installing CC Status Line..."
npx cc-status-line@latest
echo "✅ CC Status Line installed"
echo ""

# 2. Context7 - must be installed from within Claude Code
echo "[2/2] Context7 Plugin"
echo "  → Open Claude Code and run: /plugin"
echo "  → Navigate to Discover tab"  
echo "  → Search for 'context7'"
echo "  → Install it"
echo ""

echo "=== Setup Complete ==="
echo ""
echo "REMEMBER:"
echo "  • Kill sessions at 50% context (watch the status bar)"
echo "  • NEVER use /compact — start fresh instead"
echo "  • Use Superpowers execute-plan for heavy work (sub-agents)"
echo ""
