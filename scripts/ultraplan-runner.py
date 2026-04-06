#!/usr/bin/env python3
"""
ULTRAPLAN RUNNER — Launches Claude Code interactively and dispatches /ultraplan.

Usage:
  python3 ultraplan-runner.py "migrate auth to JWT tokens"
  python3 ultraplan-runner.py --issue 270
  REPO_PATH=/opt/biddeed/zonewise-web python3 ultraplan-runner.py "redesign dashboard"

Environment:
  REPO_PATH       — repo working directory (default: /opt/biddeed/cli-anything-biddeed)
  GH_PAT          — GitHub PAT for issue fetching
  TG_TOKEN        — Telegram bot token for notifications
  TG_CHAT         — Telegram chat ID
  ULTRAPLAN_TIMEOUT — max wait seconds (default: 2400 = 40 min)
"""

import subprocess, sys, os, time, re, json, urllib.request, ssl

REPO_PATH = os.environ.get("REPO_PATH", "/opt/biddeed/cli-anything-biddeed")
GH_PAT = os.environ.get("GH_PAT", "")
TG_TOKEN = os.environ.get("TG_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT", "")
TIMEOUT = int(os.environ.get("ULTRAPLAN_TIMEOUT", "2400"))
LOG_FILE = "/tmp/ultraplan-session.log"


def telegram(msg: str):
    """Send Telegram notification."""
    if not TG_TOKEN or not TG_CHAT:
        print(f"[TG skip] {msg}")
        return
    try:
        data = json.dumps({"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        ctx = ssl.create_default_context()
        urllib.request.urlopen(req, context=ctx, timeout=10)
    except Exception as e:
        print(f"[TG error] {e}")


def fetch_issue(issue_num: str) -> str:
    """Fetch GitHub issue body as task description."""
    repo = os.path.basename(REPO_PATH)
    url = f"https://api.github.com/repos/breverdbidder/{repo}/issues/{issue_num}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {GH_PAT}",
        "Accept": "application/vnd.github.v3+json",
    })
    ctx = ssl.create_default_context()
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    data = json.loads(resp.read())
    title = data.get("title", "")
    body = data.get("body", "")
    return f"{title}\n\n{body}"


def run_ultraplan(task: str):
    """Run claude interactively via script(1) pseudo-TTY, send /ultraplan."""
    os.chdir(REPO_PATH)

    # Ensure repo is fresh
    subprocess.run(["git", "fetch", "origin", "main"], capture_output=True)
    subprocess.run(["git", "reset", "--hard", "origin/main"], capture_output=True)

    # Sanitize task for shell (escape single quotes)
    safe_task = task.replace("'", "'\\''").replace("\n", " ")
    # Truncate to avoid shell limits
    if len(safe_task) > 2000:
        safe_task = safe_task[:2000] + "..."

    telegram(f"🏔️ <b>ULTRAPLAN STARTING</b>\n\n📋 {safe_task[:200]}...")

    # Use script(1) to provide a pseudo-TTY, pipe /ultraplan command
    # The approach: create a shell script that starts claude, waits, sends ultraplan
    runner_script = f"""#!/bin/bash
set -e
cd {REPO_PATH}
export CLAUDE_SKIP_PERMISSIONS=1

# Start claude in a tmux session
tmux kill-session -t ultraplan 2>/dev/null || true
tmux new-session -d -s ultraplan -x 200 -y 50

# Launch claude inside tmux
tmux send-keys -t ultraplan 'claude --dangerously-skip-permissions' Enter

# Wait for claude to initialize
sleep 8

# Send the ultraplan command
tmux send-keys -t ultraplan '/ultraplan {safe_task}' Enter

# Wait for ultraplan confirmation prompt, then accept
sleep 5
tmux send-keys -t ultraplan 'y' Enter

echo "ULTRAPLAN_DISPATCHED"

# Now poll for completion
ELAPSED=0
POLL_INTERVAL=30
MAX_WAIT={TIMEOUT}
URL_FOUND=""

while [ $ELAPSED -lt $MAX_WAIT ]; do
    sleep $POLL_INTERVAL
    ELAPSED=$((ELAPSED + POLL_INTERVAL))

    # Capture tmux pane content
    tmux capture-pane -t ultraplan -p > /tmp/ultraplan-pane.txt 2>/dev/null || true

    # Check for session URL
    if grep -qoP 'https://claude\\.ai/code/[^\\s]+' /tmp/ultraplan-pane.txt; then
        URL_FOUND=$(grep -oP 'https://claude\\.ai/code/[^\\s]+' /tmp/ultraplan-pane.txt | head -1)
        echo "ULTRAPLAN_URL=$URL_FOUND"
    fi

    # Check for completion signals
    if grep -q "ultraplan ready" /tmp/ultraplan-pane.txt 2>/dev/null; then
        echo "ULTRAPLAN_COMPLETE"
        break
    fi
    if grep -q "Results will land" /tmp/ultraplan-pane.txt 2>/dev/null; then
        echo "ULTRAPLAN_EXECUTING"
    fi
    if grep -q "pull request" /tmp/ultraplan-pane.txt 2>/dev/null; then
        echo "ULTRAPLAN_PR_CREATED"
        break
    fi
    if grep -q "fills, press" /tmp/ultraplan-pane.txt 2>/dev/null; then
        echo "ULTRAPLAN_IN_PROGRESS"
    fi
    if grep -q "error\\|failed\\|Error" /tmp/ultraplan-pane.txt 2>/dev/null; then
        echo "ULTRAPLAN_ERROR"
        cat /tmp/ultraplan-pane.txt
        break
    fi

    echo "POLL: ${{ELAPSED}}s / ${{MAX_WAIT}}s"
done

# Capture final state
tmux capture-pane -t ultraplan -p > /tmp/ultraplan-final.txt 2>/dev/null || true
cat /tmp/ultraplan-final.txt

# Cleanup
tmux kill-session -t ultraplan 2>/dev/null || true
echo "ULTRAPLAN_SESSION_END"
"""

    with open("/tmp/ultraplan-exec.sh", "w") as f:
        f.write(runner_script)
    os.chmod("/tmp/ultraplan-exec.sh", 0o755)

    # Execute and stream output
    proc = subprocess.Popen(
        ["/tmp/ultraplan-exec.sh"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    url_found = ""
    status = "unknown"

    with open(LOG_FILE, "w") as log:
        for line in proc.stdout:
            print(line, end="")
            log.write(line)

            if "ULTRAPLAN_URL=" in line:
                url_found = line.split("ULTRAPLAN_URL=")[1].strip()
                telegram(f"🔗 <b>ULTRAPLAN SESSION</b>\n{url_found}")

            if "ULTRAPLAN_COMPLETE" in line:
                status = "complete"
            elif "ULTRAPLAN_PR_CREATED" in line:
                status = "pr_created"
            elif "ULTRAPLAN_ERROR" in line:
                status = "error"
            elif "ULTRAPLAN_SESSION_END" in line and status == "unknown":
                status = "timeout"

    proc.wait()

    # Final notification
    emoji = {"complete": "✅", "pr_created": "🎉", "error": "❌", "timeout": "⏰"}.get(status, "❓")
    telegram(
        f"{emoji} <b>ULTRAPLAN {status.upper()}</b>\n"
        f"📋 {safe_task[:150]}\n"
        f"{'🔗 ' + url_found if url_found else ''}"
    )

    return status


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ultraplan Runner")
    parser.add_argument("task", nargs="?", help="Task description")
    parser.add_argument("--issue", "-i", help="GitHub issue number to fetch task from")
    args = parser.parse_args()

    if args.issue:
        task = fetch_issue(args.issue)
        print(f"[Issue #{args.issue}] {task[:200]}...")
    elif args.task:
        task = args.task
    else:
        print("Usage: ultraplan-runner.py <task> or --issue <number>")
        sys.exit(1)

    status = run_ultraplan(task)
    sys.exit(0 if status in ("complete", "pr_created") else 1)


if __name__ == "__main__":
    main()
