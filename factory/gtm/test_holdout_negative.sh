#!/usr/bin/env bash
# CMO FACTORY (issue #19777) -- negative test proving a builder-role
# checkout cannot read .factory/gtm/holdout/, while an unrestricted
# (validator-role) checkout can.
#
# Method: build a real commit object from the current index (git write-tree
# + commit-tree -- does not move HEAD or touch any branch), then check that
# commit out into two throwaway worktrees sharing this repo's object store:
#   builder/   -- runs factory/gtm/builder_checkout.sh first (the rule every
#                 builder-role workflow step must apply)
#   validator/ -- plain checkout, no sparse-checkout applied
# PASS requires: holdout file ABSENT in builder/, PRESENT in validator/.
set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
cd "$REPO_ROOT"

WORK=$(mktemp -d)
BUILDER_DIR="$WORK/builder"
VALIDATOR_DIR="$WORK/validator"
trap 'git worktree remove --force "$BUILDER_DIR" >/dev/null 2>&1 || true; \
      git worktree remove --force "$VALIDATOR_DIR" >/dev/null 2>&1 || true; \
      rm -rf "$WORK"' EXIT

TREE=$(git write-tree)
COMMIT=$(GIT_AUTHOR_NAME="gtm-factory-test" GIT_AUTHOR_EMAIL="gtm-factory-test@local" \
         GIT_COMMITTER_NAME="gtm-factory-test" GIT_COMMITTER_EMAIL="gtm-factory-test@local" \
         git commit-tree "$TREE" -p HEAD -m "CMO FACTORY CP0 negative-test snapshot (not merged, dangling)")
echo "test snapshot commit: $COMMIT (dangling -- not on any branch)"

git worktree add --detach "$VALIDATOR_DIR" "$COMMIT" >/dev/null
git worktree add --detach "$BUILDER_DIR" "$COMMIT" >/dev/null

FAIL=0

echo "--- control: validator-role checkout (no rule applied) ---"
if [ -f "$VALIDATOR_DIR/.factory/gtm/holdout/HOLDOUT.md" ]; then
  echo "PASS (control): validator-role checkout CAN read HOLDOUT.md"
else
  echo "FAIL (control): validator-role checkout could not read HOLDOUT.md -- test setup is broken, not proving anything"
  FAIL=1
fi

echo "--- builder-role checkout (factory/gtm/builder_checkout.sh applied) ---"
(cd "$BUILDER_DIR" && bash factory/gtm/builder_checkout.sh)
if [ -f "$BUILDER_DIR/.factory/gtm/holdout/HOLDOUT.md" ]; then
  echo "FAIL: builder-role checkout could still read HOLDOUT.md -- exclusion did NOT work"
  FAIL=1
else
  if cat "$BUILDER_DIR/.factory/gtm/holdout/HOLDOUT.md" 2>/dev/null; then
    echo "FAIL: read of HOLDOUT.md succeeded via cat despite missing from ls"
    FAIL=1
  else
    echo "PASS: builder-role read of .factory/gtm/holdout/HOLDOUT.md fails (file absent, cat errors)"
  fi
fi

if [ "$FAIL" -eq 0 ]; then
  echo "NEGATIVE TEST RESULT: PASS"
  exit 0
else
  echo "NEGATIVE TEST RESULT: FAIL"
  exit 1
fi
