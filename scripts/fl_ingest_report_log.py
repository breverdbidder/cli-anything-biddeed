#!/usr/bin/env python3
"""Report worker log via two channels: Supabase (if reachable) and repo commit via ambient GITHUB_TOKEN."""
import base64, json, os, sys, urllib.request

rc = sys.argv[1] if len(sys.argv) > 1 else "-1"
tail = ""
if os.path.exists("/tmp/ingest.log"):
    tail = open("/tmp/ingest.log", errors="replace").read()[-3000:]
sb_url = os.environ.get("SUPABASE_URL", "")
sb_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
diag = (f"[diag] SUPABASE_URL set={bool(sb_url)} prefix={sb_url[:35]!r} "
        f"key_set={bool(sb_key)} key_len={len(sb_key)} rc={rc}\n")
payload_txt = diag + (tail or "<empty log>")
print(diag, flush=True)

# channel 1: supabase
try:
    req = urllib.request.Request(
        sb_url.rstrip("/") + "/rest/v1/fl_ingest_worker_logs",
        data=json.dumps({"lane": os.environ.get("LANE", "?"),
                         "run_id": os.environ.get("GITHUB_RUN_ID", "?"),
                         "rc": int(rc), "log_tail": payload_txt}).encode(),
        method="POST",
        headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}",
                 "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30).read()
    print("supabase log reported")
except Exception as e:
    print(f"supabase report failed: {e!r}")

# channel 2: commit log file with ambient GITHUB_TOKEN
try:
    gh_token = os.environ["GITHUB_TOKEN"]
    repo = os.environ.get("GITHUB_REPOSITORY", "breverdbidder/cli-anything-biddeed")
    run_id = os.environ.get("GITHUB_RUN_ID", "na")
    path = f"logs/fl-ingest/{run_id}.log"
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/contents/{path}",
        data=json.dumps({"message": f"[fl-ingest log] run {run_id} rc={rc}",
                         "content": base64.b64encode(payload_txt.encode()).decode(),
                         "branch": "main"}).encode(),
        method="PUT",
        headers={"Authorization": f"Bearer {gh_token}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "fl-ingest-logger"})
    urllib.request.urlopen(req, timeout=30).read()
    print("github log committed")
except Exception as e:
    print(f"github report failed: {e!r}")
