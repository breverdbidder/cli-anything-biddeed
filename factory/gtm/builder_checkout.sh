#!/usr/bin/env bash
# CMO FACTORY (issue #19777) -- builder-role checkout rule.
#
# Any workflow step that runs the FACTORY BUILDER role (writes code/content
# against a GTM issue) MUST call this script immediately after
# actions/checkout, before any agent or script runs, so the holdout answer
# key at .factory/gtm/holdout/ never lands on the builder's filesystem.
#
# The validator role (factory/gtm/gate.py running from `main`, never a PR
# branch) does NOT call this script -- it needs the full checkout, holdout
# included, to grade a submission against it.
#
# Mechanism: git sparse-checkout, non-cone mode (cone mode has no exclude
# primitive pre-2.37 semantics we want to rely on), pattern list derived
# from .gitattributes entries carrying `gtm-checkout=validator-only`.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# Derive the exclude list from .gitattributes rather than hardcoding it here
# a second time -- single source of truth.
EXCLUDE_PATTERNS=$(git check-attr -a -- '.factory/gtm/holdout/HOLDOUT.md' 2>/dev/null \
  | grep 'gtm-checkout: validator-only' | cut -d: -f1 || true)

if [ -z "$EXCLUDE_PATTERNS" ]; then
  echo "::error::builder_checkout.sh: no gtm-checkout=validator-only attribute found on .factory/gtm/holdout/HOLDOUT.md -- refusing to proceed, this would silently checkout the holdout set to a builder" >&2
  exit 1
fi

git sparse-checkout init --no-cone
SPARSE_FILE="$(git rev-parse --git-path info/sparse-checkout)"
{
  echo '/*'
  echo '!/.factory/gtm/holdout/'
} > "$SPARSE_FILE"
git sparse-checkout reapply

if [ -e ".factory/gtm/holdout/HOLDOUT.md" ]; then
  echo "::error::builder_checkout.sh: sparse-checkout applied but .factory/gtm/holdout/HOLDOUT.md is still present -- holdout exclusion FAILED" >&2
  exit 1
fi

echo "builder_checkout.sh: holdout excluded, builder-role checkout ready"
