#!/usr/bin/env python3
"""
deploy_and_verify_worker.py — BidDeed.AI Cloudflare Worker deploy pipeline.

Pushes src/worker.js to GitHub (which triggers the existing "Deploy Cloudflare
Worker" GitHub Action -- wrangler deploy --no-bundle, the SAFE path), polls
that Action until it finishes, then verifies the live site actually reflects
the change (not just that the deploy step reported success).

Why this exists: a prior direct-Cloudflare-API push bypassed this pipeline
and corrupted the worker (Aug 7 2026 503 outage). This script only ever
pushes through GitHub -> Actions -> wrangler, and never calls the Cloudflare
API directly.

Usage:
    export SUPABASE_SERVICE_ROLE_KEY=...   # from Supabase vault: service_role_key
    export GITHUB_PAT=...                  # from Supabase vault: everest_gh_pat
    python3 deploy_and_verify_worker.py path/to/worker.js "commit message" \
        [--check "url_path:substring_to_find_in_response"] ...

    # Minimal (uses default route checks):
    python3 deploy_and_verify_worker.py src/worker.js "fix: whatever"

Exit code 0 = push + deploy + all verification checks passed.
Exit code 1 = anything failed; details printed to stdout.
"""

import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error

REPO = "breverdbidder/cli-anything-biddeed"
WORKER_PATH_IN_REPO = "src/worker.js"
SUPABASE_PROJECT_REF = "mocerqjnksmhcjzxrewo"
SUPABASE_URL = f"https://{SUPABASE_PROJECT_REF}.supabase.co"
GITHUB_API = "https://api.github.com"
SITE_BASE = "https://biddeed.ai"
DEPLOY_WORKFLOW_FILE = "deploy-worker.yml"

# Default smoke-test checks: (path, substring expected in response body).
# A None substring means "just check for HTTP 200".
DEFAULT_CHECKS = [
    ("/", None),
    ("/counties", None),
    ("/blog", None),
    ("/sitemap.xml", "biddeed.ai/county/"),
    ("/robots.txt", "Sitemap:"),
    ("/buy-report", None),
    ("/chat", None),
]


def _req(url, headers=None, data=None, method="GET"):
    h = {"User-Agent": "Mozilla/5.0 (compatible; BidDeedDeployVerify/1.0)"}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def get_env(name):
    v = os.environ.get(name)
    if not v:
        print(f"FATAL: missing required env var {name}", file=sys.stderr)
        sys.exit(1)
    return v


def push_worker(gh_pat, srk, local_path, commit_message, branch="main"):
    print(f"[1/4] Reading {local_path} ...")
    with open(local_path, "r", encoding="utf-8") as f:
        content = f.read()
    print(f"      {len(content)} bytes")

    print(f"[1/4] Pushing to {REPO}:{WORKER_PATH_IN_REPO} via github-put-content-v1 ...")
    payload = json.dumps({
        "repo": REPO,
        "path": WORKER_PATH_IN_REPO,
        "message": commit_message,
        "content": content,
        "branch": branch,
    }).encode("utf-8")

    status, body = _req(
        f"{SUPABASE_URL}/functions/v1/github-put-content-v1",
        headers={
            "Authorization": f"Bearer {srk}",
            "apikey": srk,
            "x-gh-pat": gh_pat,
            "Content-Type": "application/json",
        },
        data=payload,
        method="POST",
    )
    result = json.loads(body)
    if status != 200 or not result.get("ok"):
        print(f"FATAL: push failed (status {status}): {body}")
        sys.exit(1)
    print(f"      OK — commit {result.get('commit_url')}")
    return result


def wait_for_deploy(gh_pat, since_sha, timeout_s=180, poll_s=8):
    print(f"[2/4] Waiting for '{DEPLOY_WORKFLOW_FILE}' workflow to pick up the push ...")
    headers = {"Authorization": f"Bearer {gh_pat}", "Accept": "application/vnd.github+json"}
    deadline = time.time() + timeout_s
    seen_run_id = None

    while time.time() < deadline:
        status, body = _req(
            f"{GITHUB_API}/repos/{REPO}/actions/workflows/{DEPLOY_WORKFLOW_FILE}/runs?per_page=5",
            headers=headers,
        )
        data = json.loads(body)
        runs = data.get("workflow_runs", [])
        for run in runs:
            if run.get("head_sha", "").startswith(since_sha[:7]) or seen_run_id == run["id"]:
                seen_run_id = run["id"]
                if run["status"] == "completed":
                    print(f"      Run {run['id']}: {run['conclusion']}")
                    return run["conclusion"] == "success", run["html_url"]
                else:
                    print(f"      Run {run['id']}: {run['status']} ...")
                    break
        time.sleep(poll_s)

    print("FATAL: timed out waiting for deploy workflow to complete")
    sys.exit(1)


def get_latest_commit_sha(gh_pat, branch="main"):
    headers = {"Authorization": f"Bearer {gh_pat}", "Accept": "application/vnd.github+json"}
    status, body = _req(f"{GITHUB_API}/repos/{REPO}/commits/{branch}", headers=headers)
    return json.loads(body)["sha"]


def run_checks(checks, retries=4, retry_delay_s=5):
    print(f"[3/4] Verifying live site ({len(checks)} checks, up to {retries} retries each for edge propagation lag) ...")
    all_ok = True
    for path, expect_substr in checks:
        ok = False
        status = None
        body = ""
        for attempt in range(1, retries + 1):
            status, body = _req(f"{SITE_BASE}{path}")
            ok = status == 200 and (expect_substr is None or expect_substr in body)
            if ok:
                break
            if attempt < retries:
                time.sleep(retry_delay_s)
        marker = "OK  " if ok else "FAIL"
        detail = f"status={status}"
        if expect_substr is not None:
            detail += f" contains({expect_substr!r})={expect_substr in body}"
        attempt_note = "" if ok and attempt == 1 else f" (took {attempt} attempt(s))" if ok else ""
        print(f"      [{marker}] {path}  ({detail}){attempt_note}")
        if not ok:
            all_ok = False
    return all_ok


def check_worker_syntax(srk):
    print("[4/4] Running check-worker-syntax (parses inline <script> blocks from live /chat) ...")
    status, body = _req(
        f"{SUPABASE_URL}/functions/v1/check-worker-syntax",
        headers={"Authorization": f"Bearer {srk}", "apikey": srk},
    )
    try:
        result = json.loads(body)
    except Exception:
        print(f"      FAIL — unparseable response: {body[:300]}")
        return False
    bad = [r for r in result.get("results", []) if not r.get("ok")]
    if bad:
        print(f"      FAIL — {len(bad)} of {result.get('scriptCount')} inline scripts have syntax errors:")
        for b in bad:
            print(f"        {b.get('error')}")
        return False
    print(f"      OK — {result.get('scriptCount')} inline scripts, all parse clean")
    return True


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    local_path = sys.argv[1]
    commit_message = sys.argv[2]
    extra_checks = []
    args = sys.argv[3:]
    i = 0
    while i < len(args):
        if args[i] == "--check" and i + 1 < len(args):
            spec = args[i + 1]
            if ":" in spec:
                p, sub = spec.split(":", 1)
            else:
                p, sub = spec, None
            extra_checks.append((p, sub))
            i += 2
        else:
            i += 1

    gh_pat = get_env("GITHUB_PAT")
    srk = get_env("SUPABASE_SERVICE_ROLE_KEY")

    push_worker(gh_pat, srk, local_path, commit_message)
    latest_sha = get_latest_commit_sha(gh_pat)
    deploy_ok, run_url = wait_for_deploy(gh_pat, latest_sha)

    if not deploy_ok:
        print(f"FATAL: deploy workflow did not succeed — {run_url}")
        sys.exit(1)

    # Give Cloudflare's edge a moment to propagate after the Action reports success.
    time.sleep(5)

    checks = DEFAULT_CHECKS + extra_checks
    checks_ok = run_checks(checks)
    syntax_ok = check_worker_syntax(srk)

    print()
    if deploy_ok and checks_ok and syntax_ok:
        print("RESULT: SUCCESS — pushed, deployed, and verified live.")
        sys.exit(0)
    else:
        print("RESULT: FAILURE — see checks above. Site may be in a bad state; consider rollback.")
        sys.exit(1)


if __name__ == "__main__":
    main()
