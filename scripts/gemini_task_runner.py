#!/usr/bin/env python3
"""
FLEET Gemini lane — grunt-tier task engine (T2/T3 only).

Reads an issue brief (title+body) as a prompt, asks Gemini to emit one or more
file blocks, writes those files to disk. Mirrors the shape of cc-runner-ghonly.yml's
`claude -p` step but for the Gemini second lane: no arbitrary tool use, no shell
access for the model — file emission only. This keeps the Gemini lane incapable of
touching billing/MCP-server/launcher code by construction (it can only write files
named in its own output, and the workflow's guard-rail step rejects protected paths).

Usage:
  python scripts/gemini_task_runner.py /tmp/prompt.md
"""
import os
import re
import sys
import json
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

FILE_BLOCK_RE = re.compile(
    r"===FILE:\s*(?P<path>[^\n=]+?)\s*===\n(?P<content>.*?)\n===ENDFILE===",
    re.DOTALL,
)

PROTECTED_PATH_PREFIXES = (
    "supabase/functions/claude-router",
    "supabase/functions/stripe",
    "supabase/functions/mcp",
    "src/mcp",
    "src/launcher",
    ".github/workflows/cc-runner",
)


def get_vault_secret(name: str) -> str:
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/get_vault_secret_mcp",
        data=json.dumps({"p_name": name}).encode(),
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode()).strip('"')


def call_gemini(api_key: str, prompt: str) -> str:
    instructions = (
        "You are a grunt-tier data/doc engineer. Produce ONLY file output, "
        "nothing else (no preamble, no explanation, no markdown fences around "
        "the whole response). Emit each file EXACTLY in this format, one block "
        "per file, with no protected paths (no supabase/functions/, no src/mcp, "
        "no src/launcher, no billing code):\n\n"
        "===FILE: relative/path/to/file.md===\n"
        "<full file content>\n"
        "===ENDFILE===\n\n"
        "Task brief follows:\n\n" + prompt
    )
    body = json.dumps({"contents": [{"parts": [{"text": instructions}]}]}).encode()
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    if "error" in data:
        raise RuntimeError(f"Gemini error {data['error'].get('code')}: {data['error'].get('message')}")
    return data["candidates"][0]["content"]["parts"][0]["text"]


def write_files(text: str) -> list:
    written = []
    for m in FILE_BLOCK_RE.finditer(text):
        path = m.group("path").strip()
        content = m.group("content")
        if path.startswith("/") or ".." in path.split("/"):
            print(f"::error::rejected unsafe path: {path}")
            continue
        if any(path.startswith(p) for p in PROTECTED_PATH_PREFIXES):
            print(f"::error::rejected protected path: {path}")
            continue
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(content.rstrip("\n") + "\n")
        written.append(path)
    return written


def main():
    if len(sys.argv) != 2:
        print("usage: gemini_task_runner.py <prompt-file>", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1]) as f:
        prompt = f.read()

    try:
        api_key = get_vault_secret("gemini_api_key")
    except Exception as e:
        print(f"::error::vault fetch failed: {e}")
        sys.exit(1)

    try:
        text = call_gemini(api_key, prompt)
    except urllib.error.HTTPError as e:
        print(f"::error::Gemini HTTP {e.code}: {e.read().decode()[:500]}")
        sys.exit(1)
    except Exception as e:
        print(f"::error::Gemini call failed: {e}")
        sys.exit(1)
    finally:
        api_key = None  # never persisted, cleared as soon as possible

    written = write_files(text)
    if not written:
        print("::error::no file blocks emitted by Gemini")
        print(text[:1000])
        sys.exit(1)

    print(f"WROTE {len(written)} file(s): {', '.join(written)}")


if __name__ == "__main__":
    main()
