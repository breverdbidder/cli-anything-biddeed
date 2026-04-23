#!/usr/bin/env bash
# assign-port.sh — deterministic port assignment for parallel SUMMIT worktrees.
#
# WHY:
#   Running multiple SUMMIT / claude-code sessions in parallel (one per worktree)
#   collides on dev ports unless each session gets a distinct, predictable port.
#   Using a registry or sequence counter adds coordination state. Hashing the
#   working directory gives us a pure-function mapping: same worktree → same
#   port, no registry needed, collision-resistant at normal fleet sizes.
#
# CONVENTIONS:
#   - BASE_PORT (4000): used by the main checkout only (basename of main repo).
#     Keeps the "canonical" dev instance on a known port for bookmarks/configs.
#   - WORKTREE_BASE (4100) + WORKTREE_RANGE (100): worktree sessions map into
#     4100–4199. MD5 of cwd → first 4 bytes big-endian → mod 100 → offset.
#     Collision rate: ~5% expected with 50 simultaneous worktrees (birthday paradox,
#     100-slot space). Acceptable for Ariel's fleet size (typical: <10 parallel).
#   - PORT env override: highest precedence. Lets CI and one-offs pin explicitly.
#
# USAGE:
#   ./scripts/assign-port.sh                    # prints the port for $PWD
#   PORT=9999 ./scripts/assign-port.sh          # prints 9999
#   CWD=/some/other/path ./scripts/assign-port.sh # prints port for CWD

set -euo pipefail

BASE_PORT=4000
WORKTREE_BASE=4100
WORKTREE_RANGE=100

# Set via env or default to $PWD. CWD override primarily exists so .ps1 and .sh
# can be tested against identical inputs for cross-platform parity.
cwd="${CWD:-$PWD}"
leaf="$(basename "$cwd")"

# Env override always wins.
if [ -n "${PORT:-}" ]; then
  printf '%s\n' "$PORT"
  exit 0
fi

# Main repo checkout returns base port. Adjust the allowlist if repo is renamed.
case "$leaf" in
  cli-anything-biddeed)
    printf '%s\n' "$BASE_PORT"
    exit 0
    ;;
esac

# Hash cwd to a stable offset within [0, WORKTREE_RANGE).
# md5sum first 8 hex chars = first 4 bytes big-endian unsigned int.
md5hex="$(printf '%s' "$cwd" | md5sum | cut -c1-8)"
offset=$(( 16#${md5hex} % WORKTREE_RANGE ))
printf '%s\n' "$(( WORKTREE_BASE + offset ))"
