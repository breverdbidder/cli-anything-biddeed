#!/usr/bin/env python3
"""Post worker log tail + exit code to fl_ingest_worker_logs. Never fails the job itself."""
import json, os, sys, urllib.request
try:
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/fl_ingest_worker_logs"
    key = os.environ["SUPABASE_SERVICE_KEY"]
    tail = ""
    if os.path.exists("/tmp/ingest.log"):
        tail = open("/tmp/ingest.log", errors="replace").read()[-3000:]
    body = json.dumps({"lane": os.environ.get("LANE", "?"),
                       "run_id": os.environ.get("GITHUB_RUN_ID", "?"),
                       "rc": int(sys.argv[1]) if len(sys.argv) > 1 else -1,
                       "log_tail": tail or "<empty log>"}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "apikey": key, "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30).read()
    print("log reported")
except Exception as e:
    print(f"log report failed: {e!r}")
