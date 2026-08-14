#!/usr/bin/env python3
"""
Push workflow files to .github/workflows/ using everest_gh_pat from Supabase vault.

This script is designed to run in cc-runner-ghonly.yml context where
SUPABASE_ACCESS_TOKEN and SUPABASE_SERVICE_ROLE_KEY are available.

Per CLAUDE.md GTM-22D credential handling:
- Fetches everest_gh_pat via cli_anything_get_secret() (SECURITY DEFINER, allow-listed)
- Masks immediately with ::add-mask:: before any use
- Never prints raw value to logs

Usage (from cc-runner-ghonly.yml):
  python scripts/push_workflows_via_pat.py

Env required:
  SUPABASE_URL            - Supabase REST endpoint
  SUPABASE_SERVICE_ROLE_KEY - Service role key (for cli_anything_get_secret RPC)
  SUPABASE_ACCESS_TOKEN   - Management API token (for vault_secret fallback)

Files pushed to main:
  .github/workflows/set-mindstudio-gh-secret.yml
  .github/workflows/mindstudio-run-agents.yml
"""
import os
import sys
import json
import base64
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
REPO = "breverdbidder/cli-anything-biddeed"
PROJECT_ID = "mocerqjnksmhcjzxrewo"
TARGET_BRANCH = "main"


def fetch_pat_via_rpc() -> str:
    """Fetch everest_gh_pat via cli_anything_get_secret() RPC (service_role gated)."""
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY not set")
    url = f"{SUPABASE_URL}/rest/v1/rpc/cli_anything_get_secret"
    payload = json.dumps({"name": "everest_gh_pat"}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode()
            value = json.loads(body)
            if isinstance(value, str):
                return value
            if isinstance(value, list) and value:
                return value[0].get("cli_anything_get_secret") or value[0].get("result") or ""
            return ""
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"cli_anything_get_secret RPC failed: {e.code} {e.read().decode()[:300]}")


def fetch_pat_via_mgmt_api() -> str:
    """Fallback: fetch via Supabase Management API vault_secret()."""
    if not SUPABASE_ACCESS_TOKEN:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN not set")
    payload = json.dumps({"query": "SELECT vault_secret('everest_gh_pat') AS v;"}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_ID}/database/query",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "cli-anything-biddeed-cc/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            return (data[0].get("v") or "") if (isinstance(data, list) and data) else ""
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Mgmt API vault_secret failed: {e.code} {e.read().decode()[:300]}")


def get_file_sha(pat: str, path: str) -> str:
    """Get current SHA of file in repo (needed for updates)."""
    headers = {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"https://api.github.com/repos/{REPO}/contents/{path}?ref={TARGET_BRANCH}"
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            return data.get("sha", "")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return ""
        raise RuntimeError(f"get_file_sha failed for {path}: {e.code}")


def push_file(pat: str, path: str, content: str, message: str):
    """Push a file to .github/workflows/ via GitHub REST API."""
    sha = get_file_sha(pat, path)
    headers = {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        "branch": TARGET_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    data = json.dumps(payload).encode()
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    req = urllib.request.Request(url, data=data, method="PUT", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
            print(f"[OK] Pushed {path} (SHA: {result.get('content', {}).get('sha', '?')[:8]})")
            return True
    except urllib.error.HTTPError as e:
        print(f"[ERROR] push_file {path}: {e.code} {e.read().decode()[:300]}")
        return False


def read_file(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def main():
    print("[push_workflows_via_pat] Fetching everest_gh_pat from vault...")

    pat = ""
    try:
        pat = fetch_pat_via_rpc()
        if pat:
            print("[INFO] PAT fetched via cli_anything_get_secret() RPC")
    except Exception as e:
        print(f"[WARN] RPC fetch failed ({e}), trying Management API fallback...")

    if not pat:
        try:
            pat = fetch_pat_via_mgmt_api()
            if pat:
                print("[INFO] PAT fetched via Supabase Management API")
        except Exception as e:
            print(f"[ERROR] Management API fallback also failed: {e}")

    if not pat:
        print("::error::Could not fetch everest_gh_pat from vault — check vault contents and credentials")
        sys.exit(1)

    print(f"::add-mask::{pat}", flush=True)
    print("[INFO] PAT masked. Pushing workflow files...")

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files_to_push = [
        (".github/workflows/set-mindstudio-gh-secret.yml", "deploy: add set-mindstudio-gh-secret.yml workflow (acquisition sprint #19079)"),
        (".github/workflows/mindstudio-run-agents.yml", "deploy: add mindstudio-run-agents.yml workflow (acquisition sprint #19079)"),
    ]

    all_ok = True
    for rel_path, commit_msg in files_to_push:
        local_path = os.path.join(repo_root, rel_path)
        if not os.path.exists(local_path):
            print(f"[ERROR] Local file not found: {local_path}")
            all_ok = False
            continue
        content = read_file(local_path)
        ok = push_file(pat, rel_path, content, commit_msg)
        if not ok:
            all_ok = False

    if all_ok:
        print("\n[OK] All workflow files pushed to main/.github/workflows/")
        print("Next: trigger 'Set MindStudio GitHub Actions Secret' workflow via GHA dispatch")
    else:
        print("\n[PARTIAL] Some files failed to push — check errors above")
        sys.exit(1)


if __name__ == "__main__":
    main()
