#!/usr/bin/env bash
# Stand up claudecodeui (CloudCLI) — phone dashboard for Claude Code sessions.
# Run on the HOST that runs your `claude` sessions (e.g. your Hetzner box), as root or sudo.
# Usage:  sudo RUN_AS_USER=ariel ./bootstrap.sh
set -euo pipefail

REPO="https://github.com/siteboon/claudecodeui.git"
DIR="/opt/claudecodeui"
DATA="/opt/claudecodeui-data"
RUN_AS_USER="${RUN_AS_USER:-$(logname 2>/dev/null || echo root)}"

echo ">> Target run user (must own ~/.claude): $RUN_AS_USER"

# 1) System deps (node-pty needs a toolchain; git/curl for clone)
if ! command -v node >/dev/null || [ "$(node -v | sed 's/v\([0-9]*\).*/\1/')" -lt 20 ]; then
  echo ">> Installing Node.js 22 LTS"
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi
apt-get install -y build-essential python3 git

# 2) Clone or update
if [ -d "$DIR/.git" ]; then
  echo ">> Updating existing checkout"
  git -C "$DIR" pull --ff-only
else
  echo ">> Cloning claudecodeui"
  git clone "$REPO" "$DIR"
fi

# 3) Persistent data dir for the auth DB
mkdir -p "$DATA"
chown -R "$RUN_AS_USER":"$RUN_AS_USER" "$DIR" "$DATA"

# 4) Env (edit .env afterward if your claude CLI path differs)
if [ ! -f "$DIR/.env" ]; then
  cp "$(dirname "$0")/.env" "$DIR/.env"
  echo ">> Wrote $DIR/.env (review CLAUDE_CLI_PATH if needed)"
fi

# 5) Build (as the run user so node-pty compiles under the right perms)
echo ">> Installing deps + building (this takes a few minutes)"
sudo -u "$RUN_AS_USER" bash -lc "cd '$DIR' && npm ci && npm run build"

# 6) systemd service (templated on the run user)
UNIT="/etc/systemd/system/claudecodeui@.service"
cp "$(dirname "$0")/claudecodeui.service" "$UNIT"
systemctl daemon-reload
systemctl enable --now "claudecodeui@${RUN_AS_USER}.service"

echo ""
echo ">> Up. Local check:  curl -sI http://127.0.0.1:3001 | head -1"
echo ">> Logs:            journalctl -u claudecodeui@${RUN_AS_USER}.service -f"
echo ">> Next: expose to your phone over HTTPS via cloudflared (see README)."
