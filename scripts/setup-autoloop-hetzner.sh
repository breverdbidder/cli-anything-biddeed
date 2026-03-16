#!/bin/bash
# setup-autoloop-hetzner.sh
# One-time setup for autoloop on Hetzner everest-dispatch
# Run via: ssh root@87.99.129.125 'bash -s' < scripts/setup-autoloop-hetzner.sh

set -e

echo "=== Autoloop Hetzner Setup ==="
echo "Server: $(hostname) | $(date)"
echo ""

# 1. Node.js
echo "[1/6] Node.js..."
if ! command -v node &>/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y -qq nodejs
fi
echo "  ✅ Node $(node --version)"

# 2. Claude Code CLI
echo "[2/6] Claude Code CLI..."
if ! command -v claude &>/dev/null; then
  npm install -g @anthropic-ai/claude-code
fi
echo "  ✅ claude: $(which claude)"

# 3. Python deps
echo "[3/6] Python dependencies..."
python3 -m pip install --break-system-packages -q zipfile36 2>/dev/null || true
echo "  ✅ Python $(python3 --version 2>&1 | awk '{print $2}')"

# 4. Git config (for autoloop commits)
echo "[4/6] Git config..."
git config --global user.email "ariel@everestcapitalusa.com"
git config --global user.name "Autoloop Bot"
git config --global credential.helper store
echo "  ✅ Git configured"

# 5. Repo
echo "[5/6] Repository..."
REPO_PATH="/opt/biddeed/cli-anything-biddeed"
mkdir -p /opt/biddeed
if [ ! -d "$REPO_PATH" ]; then
  cd /opt/biddeed
  git clone "https://github.com/breverdbidder/cli-anything-biddeed.git"
else
  cd "$REPO_PATH"
  git pull origin main --ff-only 2>&1 | tail -1
fi

# Ensure eval dirs exist
mkdir -p "$REPO_PATH/zonewise/eval_outputs"
mkdir -p "$REPO_PATH/auction/eval_outputs"
mkdir -p "$REPO_PATH/reports/eval_outputs"
echo "  ✅ Repo: $REPO_PATH"

# 6. Claude Code auth check
echo "[6/6] Claude Code auth..."
if claude --version &>/dev/null; then
  echo "  ✅ Claude Code installed"
  echo ""
  echo "=== AUTH CHECK ==="
  echo "Claude Code needs one-time authentication."
  echo "If not yet authenticated, SSH in and run:"
  echo ""
  echo "  ssh root@87.99.129.125"
  echo "  claude login"
  echo ""
  echo "This opens a browser URL. Complete it once, auth persists."
  echo ""
  echo "Alternative for headless (Max plan):"
  echo "  export ANTHROPIC_API_KEY=sk-ant-..."
  echo "  echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> /root/.bashrc"
  echo ""
else
  echo "  ❌ Claude Code not functional"
  exit 1
fi

# Verify eval files
echo "=== Eval Infrastructure ==="
for SKILL in zonewise auction reports; do
  if [ -f "$REPO_PATH/$SKILL/eval/eval.json" ]; then
    COUNT=$(python3 -c "import json; d=json.load(open('$REPO_PATH/$SKILL/eval/eval.json')); print(d['scoring']['total_assertions'])")
    echo "  ✅ $SKILL: $COUNT assertions"
  else
    echo "  ❌ $SKILL: eval.json missing"
  fi
done

[ -f "$REPO_PATH/scripts/eval_runner.py" ] && echo "  ✅ eval_runner.py" || echo "  ❌ eval_runner.py missing"
[ -f "$REPO_PATH/AUTOLOOP.md" ] && echo "  ✅ AUTOLOOP.md" || echo "  ❌ AUTOLOOP.md missing"

echo ""
echo "=== READY ==="
echo "Manual test:  cd $REPO_PATH && bash scripts/launch-autoloop.sh zonewise"
echo "GHA trigger:  gh workflow run autoloop.yml -f skill=zonewise"
echo "Nightly:      2 AM EST automatic via cron"
