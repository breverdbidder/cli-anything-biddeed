#!/usr/bin/env python3
"""CONTINUOUS EXECUTOR — Never sleeps. Every 2 hours: pick top task, dispatch, verify last run, report.
Ariel wakes up to results, not requests."""
import requests, json, os, time
from datetime import datetime, timezone, timedelta

SB_URL = os.environ["SUPABASE_URL"]
SB_KEY = os.environ["SUPABASE_KEY"]
GH_PAT = os.environ["GH_PAT"]
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
EST = timezone(timedelta(hours=-4))
NOW = datetime.now(EST)
NL = chr(10)
REPO = "breverdbidder/cli-anything-biddeed"

sb_h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
gh_h = {"Authorization": f"token {GH_PAT}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"}

def log(msg):
    print(f"[{NOW.strftime('%H:%M')}] {msg}")

def tg(msg):
    if TG_TOKEN and TG_CHAT:
        try:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                json={"chat_id": TG_CHAT, "text": msg[:4000]}, timeout=10)
        except:
            pass

def is_shabbat():
    """No dispatches Friday sunset to Saturday sunset."""
    dow = NOW.weekday()  # 0=Mon
    hour = NOW.hour
    if dow == 4 and hour >= 17: return True   # Friday after 5pm
    if dow == 5: return True                   # Saturday
    if dow == 6 and hour < 6: return True      # Sunday before 6am (buffer)
    return False

# === 1. CHECK RUNNING SUMMITS (WIP=1) ===
def count_running():
    try:
        r = requests.get(f"https://api.github.com/repos/{REPO}/actions/workflows/summit-task.yml/runs?status=in_progress&per_page=5", headers=gh_h, timeout=10)
        return len(r.json().get("workflow_runs", [])) if r.status_code == 200 else 0
    except:
        return 0

# === 2. VERIFY LAST COMPLETED SUMMIT ===
def verify_last_completed():
    results = []
    try:
        r = requests.get(f"https://api.github.com/repos/{REPO}/actions/workflows/summit-task.yml/runs?status=completed&per_page=3", headers=gh_h, timeout=10)
        if r.status_code != 200: return results
        for run in r.json().get("workflow_runs", []):
            run_time = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - run_time).total_seconds() / 3600
            if age_hours > 4: continue  # only recent runs
            results.append({
                "conclusion": run.get("conclusion", "?"),
                "url": run["html_url"],
                "title": run.get("display_title", "")[:60],
            })
    except: pass
    return results

# === 3. ML PRIORITY SCORE ===
def score_task(t):
    s = 50.0
    pri = t.get("priority", "P3")
    s += {"P0": 30, "P1": 20, "P2": 10, "P3": 0}.get(pri, 0)
    sla = t.get("sla_deadline")
    if sla:
        try:
            dl = datetime.fromisoformat(sla.replace("Z", "+00:00"))
            days = (dl - datetime.now(timezone.utc)).days
            if days < 0: s += 25
            elif days < 3: s += 20
            elif days < 7: s += 12
            elif days < 14: s += 5
        except: pass
    domain = t.get("project", "")
    s += {"BIDDEED": 8, "ZONEWISE": 8, "GTM": 6, "ECOSYSTEM": 5, "MICHAEL": 3}.get(domain, 3)
    return s

# === 4. GET NEXT DISPATCHABLE TASK ===
def get_next_task():
    try:
        r = requests.get(f"{SB_URL}/rest/v1/nexus_tasks?status=eq.queued&owner=neq.ariel&order=priority.asc&limit=30", headers=sb_h, timeout=10)
        if r.status_code != 200: return None
        tasks = r.json()
        scored = [(score_task(t), t) for t in tasks]
        scored.sort(key=lambda x: -x[0])
        return scored[0] if scored else None
    except:
        return None

# === 5. DISPATCH ===
def dispatch(task, score):
    tid = task.get("task_id", "?")
    desc = task.get("description", "")[:200]
    pri = task.get("priority", "P3")
    domain = task.get("project", "?")
    body = f"""## Auto-Dispatched by Continuous Executor
**Task:** {tid} | **Priority:** {pri} | **ML Score:** {score:.0f}/100 | **Domain:** {domain}
**Description:** {desc}

### Execute autonomously. Verify with proof. Mark done in nexus_tasks."""

    try:
        r = requests.post(f"https://api.github.com/repos/{REPO}/issues",
            headers=gh_h, json={"title": f"AUTO [{pri}|{score:.0f}] {tid}: {desc[:60]}", "body": body, "labels": ["summit"]}, timeout=10)
        if r.status_code != 201:
            log(f"Issue create failed: {r.status_code}")
            return None
        inum = r.json()["number"]

        r2 = requests.post(f"https://api.github.com/repos/{REPO}/actions/workflows/summit-task.yml/dispatches",
            headers=gh_h, json={"ref": "main", "inputs": {"issue_number": str(inum), "timeout_minutes": "90"}}, timeout=10)
        if r2.status_code != 204:
            log(f"Dispatch failed: {r2.status_code}")
            return None

        requests.patch(f"{SB_URL}/rest/v1/nexus_tasks?task_id=eq.{tid}", headers=sb_h, json={"status": "dispatched"}, timeout=5)

        time.sleep(5)
        r3 = requests.get(f"https://api.github.com/repos/{REPO}/actions/runs?event=workflow_dispatch&per_page=1", headers=gh_h, timeout=10)
        run_url = r3.json()["workflow_runs"][0]["html_url"] if r3.status_code == 200 and r3.json().get("workflow_runs") else ""

        log(f"Dispatched #{inum} → {run_url}")
        return {"issue": inum, "run_url": run_url, "task_id": tid, "score": score, "desc": desc[:60]}
    except Exception as e:
        log(f"Dispatch error: {e}")
        return None

# === 6. UPTIME CHECK ===
def check_sites():
    results = {}
    for site in ["https://biddeed.ai", "https://zonewise.ai"]:
        try:
            r = requests.head(site, timeout=5, allow_redirects=True)
            results[site] = r.status_code
        except:
            results[site] = 0
    return results

# === MAIN LOOP ===
def main():
    log("=== CONTINUOUS EXECUTOR ===")

    # Shabbat guard
    if is_shabbat():
        log("Shabbat mode — no dispatches. Shabbat Shalom.")
        return

    # 1. Check if summit already running
    running = count_running()
    log(f"Running SUMMITs: {running}")

    # 2. Verify recent completions
    completed = verify_last_completed()
    for c in completed:
        emoji = "OK" if c["conclusion"] == "success" else "FAIL"
        log(f"Recent: {emoji} — {c['title']}")

    # 3. Site health
    sites = check_sites()
    for url, code in sites.items():
        log(f"Site: {url} → {code}")

    # 4. If slot available, dispatch next task
    dispatched = None
    if running < 1:
        result = get_next_task()
        if result:
            score, task = result
            log(f"Next task: {task.get('task_id')} (ML:{score:.0f}) — {task.get('description','')[:60]}")
            dispatched = dispatch(task, score)
        else:
            log("No dispatchable tasks in queue")
    else:
        log("WIP=1 — waiting for current SUMMIT to finish")

    # 5. Build Telegram receipt
    lines = []
    lines.append(f"EXECUTOR {NOW.strftime('%I:%M %p')} EST")
    lines.append("")

    if completed:
        lines.append("RECENT RESULTS:")
        for c in completed:
            e = "OK" if c["conclusion"] == "success" else "FAIL"
            lines.append(f"  {e}: {c['title']}")
        lines.append("")

    if dispatched:
        lines.append(f"DISPATCHED: [{dispatched['score']:.0f}] {dispatched['task_id']}")
        lines.append(f"  {dispatched['desc']}")
        if dispatched.get("run_url"):
            lines.append(f"  {dispatched['run_url']}")
    elif running > 0:
        lines.append(f"WORKING: {running} SUMMIT in progress (WIP=1)")
    else:
        lines.append("IDLE: No tasks in queue")

    lines.append("")
    for url, code in sites.items():
        status = "UP" if code == 200 else "DOWN"
        name = "biddeed" if "biddeed" in url else "zonewise"
        lines.append(f"  {name}: {status} ({code})")

    msg = NL.join(lines)
    print(msg)
    tg(msg)

    # 6. Log execution to Supabase
    try:
        requests.post(f"{SB_URL}/rest/v1/daily_metrics", headers=sb_h, json={
            "date": NOW.strftime("%Y-%m-%d"),
            "metric_type": "executor_run",
            "value": 1 if dispatched else 0,
            "metadata": json.dumps({
                "time": NOW.isoformat(),
                "running": running,
                "dispatched": dispatched.get("task_id") if dispatched else None,
                "sites": sites,
                "completed": len(completed),
            })
        }, timeout=5)
    except:
        pass

if __name__ == "__main__":
    main()
