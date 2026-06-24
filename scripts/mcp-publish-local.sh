#!/usr/bin/env bash
# mcp-publish-local.sh — Publish biddeed-mcp and zonewise-mcp to npm
# Run locally with your npm Automation token:
#   NODE_AUTH_TOKEN=npm_xxx ./scripts/mcp-publish-local.sh
#
# Or with a specific version bump (patch/minor/major):
#   BUMP=patch NODE_AUTH_TOKEN=npm_xxx ./scripts/mcp-publish-local.sh

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -z "${NODE_AUTH_TOKEN:-}" ]; then
  echo "ERROR: NODE_AUTH_TOKEN not set."
  echo "Get an Automation token at: https://www.npmjs.com/settings/<username>/tokens"
  echo "Then run: NODE_AUTH_TOKEN=npm_xxx ./scripts/mcp-publish-local.sh"
  exit 1
fi

BUMP="${BUMP:-}" # patch | minor | major | (empty = no version bump)

publish_package() {
  local PKG_DIR="$1"
  local PKG_NAME="$2"

  echo ""
  echo "=== Publishing ${PKG_NAME} ==="
  cd "$PKG_DIR"
  npm install

  if [ -n "$BUMP" ]; then
    npm version "$BUMP" --no-git-tag-version
    echo "  Bumped to $(node -p "require('./package.json').version")"
  fi

  echo "  Dry run first..."
  npm publish --dry-run --access public 2>&1 | tail -5

  echo "  Publishing..."
  NPM_TOKEN="$NODE_AUTH_TOKEN" npm publish --access public
  echo "  ✅ ${PKG_NAME} published"

  cd "$REPO_ROOT"
}

publish_package "${REPO_ROOT}/packages/biddeed-mcp" "biddeed-mcp"
publish_package "${REPO_ROOT}/packages/zonewise-mcp" "zonewise-mcp"

echo ""
echo "✅ Both packages published."
echo ""
echo "Test with:"
echo "  npx biddeed-mcp@latest --version 2>&1 || echo 'no --version flag is ok'"
echo "  npx zonewise-mcp@latest --version 2>&1 || echo 'no --version flag is ok'"
echo ""
echo "Then deploy HTTP server:"
echo "  gh workflow run mcp-http-deploy-hetzner.yml"
