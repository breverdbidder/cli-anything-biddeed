#!/usr/bin/env python3
"""Remotion License V2 tripwire (issue #19787).

Three independent checks, run from gtm-validate.yml. Each writes one row to
public.agent_ops_log (dispatch_id='remotion_license_risk') so
public.gtm_watchdog()'s D8 detector (supabase/migrations/
20260903f_gtm_watchdog_d8_remotion_license_risk.sql) can pick up the result
without needing git/filesystem access from inside Postgres.

(a) authors  -- distinct human git authors, 90d, across zonewise-superpowers
               + any repo known to import remotion. Bot/CC identities
               excluded. >3 -> ADVISORY-FAIL (logged BLOCKED, does NOT
               exit non-zero -- the issue is explicit: "treat the count as
               ADVISORY-FAIL ... rather than silently passing", not a hard
               gate).
(b) player   -- @remotion/player or <Player> import in a customer-facing
               surface (biddeed-web, zonewise-web, src/worker.js,
               winnerdataai-web, winnerdataai-mvp). HARD FAIL (exits 1).
(c) usercode -- a code path that accepts user-supplied Remotion code/projects
               for rendering. Prohibited outright, not merely chargeable.
               HARD FAIL (exits 1).

Usage:
  python3 scripts/remotion_license_tripwire.py            # real run (needs GH_TOKEN, SUPABASE_*)
  python3 scripts/remotion_license_tripwire.py --selftest  # synthetic fixtures, no network
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile

BOT_AUTHOR_RE = re.compile(r"bot|claude|copilot|^cc-|dependabot|github-actions", re.I)
PLAYER_IMPORT_RE = re.compile(r"""from\s+['"]@remotion/player['"]|<Player\b""")
# Heuristic for "accepts user-supplied Remotion code/projects for rendering":
# a render call whose input composition/entry-point comes from a request
# body / uploaded file / external URL, rather than a fixed in-repo path.
USERCODE_RE = re.compile(
    r"renderMedia\([^)]*req\.(body|file|files|query)|"
    r"selectComposition\([^)]*req\.(body|file|files|query)|"
    r"bundle\([^)]*req\.(body|file|files|query)",
    re.I,
)

REMOTION_REPOS = ["breverdbidder/zonewise-superpowers", "breverdbidder/zonewise-video"]
CUSTOMER_FACING_REPOS = [
    "breverdbidder/biddeed-web",
    "breverdbidder/zonewise-web",
    "breverdbidder/winnerdataai-web",
    "breverdbidder/winnerdataai-mvp",
]
LOCAL_CUSTOMER_FACING_PATHS = ["src/worker.js"]  # this repo, checked in-place


class TripwireResult:
    def __init__(self, task: str, status: str, evidence: str):
        self.task = task
        self.status = status  # 'BLOCKED' or 'VERIFIED'
        self.evidence = evidence


def _sh(*args: str, cwd: str | None = None) -> str:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False).stdout


def check_authors_real(days: int = 90) -> TripwireResult:
    all_authors: set[str] = set()
    per_repo: dict[str, list[str]] = {}
    for repo in REMOTION_REPOS:
        with tempfile.TemporaryDirectory() as d:
            clone = subprocess.run(
                ["gh", "repo", "clone", repo, d, "--", "--depth", "500"],
                capture_output=True, text=True,
            )
            if clone.returncode != 0:
                per_repo[repo] = [f"CLONE_FAILED: {clone.stderr.strip()[:200]}"]
                continue
            since = f"--since={days}.days"
            log = _sh("git", "log", since, "--format=%ae|%an", cwd=d)
            repo_authors = set()
            for line in log.splitlines():
                if not line.strip():
                    continue
                email, name = (line.split("|", 1) + [""])[:2]
                ident = email or name
                if BOT_AUTHOR_RE.search(ident) or BOT_AUTHOR_RE.search(name):
                    continue
                repo_authors.add(ident.lower())
            per_repo[repo] = sorted(repo_authors)
            all_authors |= repo_authors
    n = len(all_authors)
    status = "BLOCKED" if n > 3 else "VERIFIED"
    evidence = (
        f"distinct_human_authors_90d={n} (threshold=3) across {REMOTION_REPOS}; "
        f"per_repo={per_repo}"
    )
    return TripwireResult("remotion_license_risk_authors", status, evidence)


def _grep_repo_for(pattern: re.Pattern, repo: str) -> list[str]:
    hits = []
    with tempfile.TemporaryDirectory() as d:
        clone = subprocess.run(
            ["gh", "repo", "clone", repo, d, "--", "--depth", "1"],
            capture_output=True, text=True,
        )
        if clone.returncode != 0:
            return [f"CLONE_FAILED:{repo}:{clone.stderr.strip()[:200]}"]
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if x not in (".git", "node_modules", "dist", "build")]
            for fn in files:
                if not fn.endswith((".ts", ".tsx", ".js", ".jsx")):
                    continue
                path = os.path.join(root, fn)
                try:
                    with open(path, "r", errors="ignore") as fh:
                        text = fh.read()
                except OSError:
                    continue
                if pattern.search(text):
                    hits.append(f"{repo}:{os.path.relpath(path, d)}")
    return hits


def check_player_import_real() -> TripwireResult:
    hits: list[str] = []
    for repo in CUSTOMER_FACING_REPOS:
        hits += _grep_repo_for(PLAYER_IMPORT_RE, repo)
    for path in LOCAL_CUSTOMER_FACING_PATHS:
        if os.path.exists(path):
            with open(path, "r", errors="ignore") as fh:
                if PLAYER_IMPORT_RE.search(fh.read()):
                    hits.append(path)
    status = "BLOCKED" if hits else "VERIFIED"
    evidence = f"@remotion/player or <Player> import found in: {hits}" if hits else \
        f"no @remotion/player / <Player> import found across {CUSTOMER_FACING_REPOS + LOCAL_CUSTOMER_FACING_PATHS}"
    return TripwireResult("remotion_license_risk_player", status, evidence)


def check_usercode_real() -> TripwireResult:
    hits: list[str] = []
    for repo in CUSTOMER_FACING_REPOS + REMOTION_REPOS:
        hits += _grep_repo_for(USERCODE_RE, repo)
    for path in LOCAL_CUSTOMER_FACING_PATHS:
        if os.path.exists(path):
            with open(path, "r", errors="ignore") as fh:
                if USERCODE_RE.search(fh.read()):
                    hits.append(path)
    status = "BLOCKED" if hits else "VERIFIED"
    evidence = f"user-supplied-code-render pattern found in: {hits}" if hits else \
        "no render call accepting req.body/file/query as the Remotion composition/entry-point"
    return TripwireResult("remotion_license_risk_usercode", status, evidence)


def log_ops(result: TripwireResult) -> None:
    import httpx
    url = os.environ["SUPABASE_URL"] + "/rest/v1/agent_ops_log"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    severity = "blocker" if result.status == "BLOCKED" else "info"
    payload = {
        "dispatch_id": "remotion_license_risk",
        "task": result.task,
        "status": result.status,
        "evidence": result.evidence[:4000],
        "severity": severity,
    }
    r = httpx.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()


def _selftest() -> int:
    rc = 0

    # (a) authors: synthetic set with 4 distinct human idents -> ADVISORY-FAIL
    fake_log = ["a@x.com|Alice", "b@x.com|Bob", "c@x.com|Carol", "d@x.com|Dave", "bot@x.com|dependabot[bot]"]
    authors = set()
    for line in fake_log:
        email, name = line.split("|", 1)
        if BOT_AUTHOR_RE.search(email) or BOT_AUTHOR_RE.search(name):
            continue
        authors.add(email.lower())
    assert len(authors) == 4, authors
    print(f"test_authors_over_3_advisory_fail: PASS (n={len(authors)}, bot excluded)")

    # (b) player import detection
    sample_ok = "import React from 'react';\nexport const X = () => <div/>;"
    sample_bad_1 = "import { Player } from '@remotion/player';"
    sample_bad_2 = "return <Player component={X} durationInFrames={90} />;"
    assert not PLAYER_IMPORT_RE.search(sample_ok)
    assert PLAYER_IMPORT_RE.search(sample_bad_1)
    assert PLAYER_IMPORT_RE.search(sample_bad_2)
    print("test_player_import_detection: PASS (clean passes, both import styles caught)")

    # (c) user-supplied render code path detection
    sample_ok = "renderMedia({ composition: FIXED_COMPOSITION, codec: 'h264' });"
    sample_bad = "renderMedia({ composition: req.body.compositionId, codec: 'h264' });"
    assert not USERCODE_RE.search(sample_ok)
    assert USERCODE_RE.search(sample_bad)
    print("test_usercode_render_detection: PASS (fixed composition passes, req.body-driven caught)")

    print("SELFTEST PASS")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="run real checks but skip agent_ops_log write")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    results = [check_authors_real(), check_player_import_real(), check_usercode_real()]
    hard_fail = False
    for r in results:
        print(f"{r.task}: {r.status} -- {r.evidence[:300]}")
        if not args.dry_run:
            log_ops(r)
        if r.status == "BLOCKED" and r.task != "remotion_license_risk_authors":
            hard_fail = True
        if r.status == "BLOCKED" and r.task == "remotion_license_risk_authors":
            print(f"::warning::{r.task} ADVISORY-FAIL -- {r.evidence[:300]}")

    if hard_fail:
        print("::error::Remotion License V2 tripwire HARD FAIL -- see agent_ops_log dispatch_id=remotion_license_risk")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
