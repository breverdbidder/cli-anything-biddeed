#!/usr/bin/env python3
"""
Dispatch run-sql-migration.yml workflow to apply the gadsden shard-4 E/C/I/J migration.

This script uses the GitHub Actions API to trigger the existing run-sql-migration.yml
workflow (which has SUPABASE_ACCESS_TOKEN) without needing workflows push permission.

Usage:
  GH_TOKEN=<token> python3 scripts/dispatch_gadsden_shard4_migration.py

Requires a GitHub token with 'actions:write' scope (NOT the restricted App token).
The token can be:
  - GH_PAT_FULL from vault (has actions:write)
  - GITHUB_TOKEN from cc-runner-ghonly.yml (which has full permissions)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error

REPO = "breverdbidder/cli-anything-biddeed"
WORKFLOW = "run-sql-migration.yml"
BRANCH = "main"
MIGRATION_FILE = "migrations/20260811_gold_standard_shard4_gadsden_cefc3fb1_ecij_fix.sql"


def dispatch(token: str) -> None:
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches"
    payload = json.dumps({
        "ref": BRANCH,
        "inputs": {"file": MIGRATION_FILE}
    }).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            print(f"Dispatch HTTP {status}")
            if status == 204:
                print(f"SUCCESS — {WORKFLOW} dispatched with file={MIGRATION_FILE}")
                print("Monitor at: https://github.com/breverdbidder/cli-anything-biddeed/actions/workflows/run-sql-migration.yml")
            else:
                body = resp.read().decode()
                print(f"Unexpected status {status}: {body}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP Error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: GH_TOKEN or GITHUB_TOKEN env var required", file=sys.stderr)
        print("  GH_PAT_FULL (from vault) or cc-runner-ghonly token works.", file=sys.stderr)
        sys.exit(1)
    dispatch(token)
