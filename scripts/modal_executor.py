#!/usr/bin/env python3
"""MODAL PARALLEL EXECUTOR — Run multiple tasks simultaneously.
Replaces WIP=1 serial SUMMIT queue with parallel Modal containers.
Each task gets its own isolated container. Up to 5 concurrent tasks."""

import modal

app = modal.App("everest-executor")

# Container image with everything we need
executor_image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "requests", "httpx", "pyyaml"
)

# Secrets from Modal dashboard (set once, used forever)
secrets = modal.Secret.from_name("everest-secrets")


@app.function(
    image=executor_image,
    secrets=[secrets],
    timeout=5400,  # 90 minutes max per task
    retries=0,
    max_containers=5,  # Up to 5 parallel tasks
)
def execute_task(task: dict) -> dict:
    """Execute a single task autonomously in its own container."""
    import requests, json, os, time
    from datetime import datetime, timezone, timedelta

    SB_URL = os.environ["SUPABASE_URL"]
    SB_KEY = os.environ["SUPABASE_KEY"]
    GH_PAT = os.environ["GH_PAT"]
    TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
    REPO = "breverdbidder/cli-anything-biddeed"
    NL = chr(10)

    sb_h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
    gh_h = {"Authorization": f"token {GH_PAT}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"}

    tid = task.get("task_id", "?")
    desc = task.get("description", "")[:200]
    pri = task.get("priority", "P3")
    domain = task.get("project", "?")
    score = task.get("ml_score", 50)

    result = {"task_id": tid, "status": "started", "score": score}

    try:
        # 1. Create GitHub issue
        body = f"""## Modal Parallel Executor — Auto-Dispatched
**Task:** {tid} | **Priority:** {pri} | **ML Score:** {score:.0f}/100 | **Domain:** {domain}
**Description:** {desc}

### Execute autonomously. Verify with proof. Update nexus_tasks when done."""

        r = requests.post(f"https://api.github.com/repos/{REPO}/issues",
            headers=gh_h,
            json={"title": f"MODAL [{pri}|{score:.0f}] {tid}: {desc[:60]}", "body": body, "labels": ["summit"]},
            timeout=10)

        if r.status_code != 201:
            result["status"] = "issue_create_failed"
            result["error"] = f"HTTP {r.status_code}"
            return result

        inum = r.json()["number"]
        result["issue"] = inum

        # 2. Dispatch SUMMIT workflow
        r2 = requests.post(
            f"https://api.github.com/repos/{REPO}/actions/workflows/summit-task.yml/dispatches",
            headers=gh_h,
            json={"ref": "main", "inputs": {"issue_number": str(inum), "timeout_minutes": "90"}},
            timeout=10)

        if r2.status_code != 204:
            result["status"] = "dispatch_failed"
            return result

        # 3. Update nexus task status
        requests.patch(f"{SB_URL}/rest/v1/nexus_tasks?task_id=eq.{tid}",
            headers=sb_h, json={"status": "dispatched"}, timeout=5)

        # 4. Wait for run URL
        time.sleep(5)
        r3 = requests.get(
            f"https://api.github.com/repos/{REPO}/actions/runs?event=workflow_dispatch&per_page=3",
            headers=gh_h, timeout=10)
        run_url = ""
        if r3.status_code == 200:
            for run in r3.json().get("workflow_runs", []):
                run_url = run["html_url"]
                break

        result["status"] = "dispatched"
        result["run_url"] = run_url

        # 5. Telegram notification
        if TG_TOKEN and TG_CHAT:
            msg = f"MODAL EXEC [{score:.0f}] {tid}{NL}{desc[:80]}{NL}Issue #{inum}{NL}{run_url}"
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                json={"chat_id": TG_CHAT, "text": msg}, timeout=10)

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


@app.function(
    image=executor_image,
    secrets=[secrets],
    timeout=300,
    schedule=modal.Cron("0 */2 * * *"),  # Every 2 hours
)
def continuous_loop():
    """Main loop: score tasks, dispatch top N in parallel, verify completions."""
    import requests, json, os, math
    from datetime import datetime, timezone, timedelta

    SB_URL = os.environ["SUPABASE_URL"]
    SB_KEY = os.environ["SUPABASE_KEY"]
    GH_PAT = os.environ["GH_PAT"]
    TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
    NL = chr(10)

    sb_h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
    gh_h = {"Authorization": f"token {GH_PAT}", "Accept": "application/vnd.github+json"}
    EST = timezone(timedelta(hours=-4))
    NOW = datetime.now(EST)

    # --- SHABBAT GUARD (Satellite Beach FL) ---
    lat, lng = 28.1798, -80.5996
    def get_sunset(target_date):
        n = target_date.timetuple().tm_yday
        lng_hour = lng / 15.0
        t = n + ((18 - lng_hour) / 24.0)
        M = (0.9856 * t) - 3.289
        L = (M + (1.916 * math.sin(math.radians(M))) + (0.020 * math.sin(math.radians(2*M))) + 282.634) % 360
        RA = math.degrees(math.atan(0.91764 * math.tan(math.radians(L)))) % 360
        RA += (L // 90) * 90 - (RA // 90) * 90
        RA /= 15.0
        sinDec = 0.39782 * math.sin(math.radians(L))
        cosDec = math.cos(math.asin(sinDec))
        cos_H = (math.cos(math.radians(90.833)) - sinDec * math.sin(math.radians(lat))) / (cosDec * math.cos(math.radians(lat)))
        if abs(cos_H) > 1: return 19, 0
        H = math.degrees(math.acos(cos_H)) / 15.0
        T = H + RA - (0.06571 * t) - 6.622
        UT = (T - lng_hour) % 24
        local = UT + (-4)
        if local < 0: local += 24
        return int(local), int((local - int(local)) * 60)

    dow = NOW.weekday()
    cur_min = NOW.hour * 60 + NOW.minute
    if dow == 4:  # Friday
        sh, sm = get_sunset(NOW.date())
        if cur_min >= sh * 60 + sm:
            print("Shabbat Shalom — paused until havdalah")
            return
    elif dow == 5:  # Saturday
        sh, sm = get_sunset(NOW.date())
        havdalah = sh * 60 + sm + 42 + 10  # sunset + 42min + 10min buffer
        if cur_min < havdalah:
            print(f"Shabbat — resuming after havdalah ({havdalah//60}:{havdalah%60:02d})")
            return

    # --- COUNT RUNNING SUMMITS ---
    running = 0
    try:
        r = requests.get(
            f"https://api.github.com/repos/breverdbidder/cli-anything-biddeed/actions/workflows/summit-task.yml/runs?status=in_progress&per_page=10",
            headers=gh_h, timeout=10)
        running = len(r.json().get("workflow_runs", [])) if r.status_code == 200 else 0
    except:
        pass

    MAX_PARALLEL = 3  # Modal can do 5, but GHA runners are limited
    slots = max(0, MAX_PARALLEL - running)
    print(f"Running: {running} | Slots available: {slots}")

    if slots == 0:
        print("All slots full — waiting")
        # Still send heartbeat
        if TG_TOKEN:
            requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                json={"chat_id": os.environ.get("TELEGRAM_CHAT_ID",""),
                      "text": f"EXECUTOR {NOW.strftime('%I:%M %p')}: {running} tasks running, waiting for slots"},
                timeout=10)
        return

    # --- PULL & SCORE TASKS ---
    try:
        r = requests.get(
            f"{SB_URL}/rest/v1/nexus_tasks?status=eq.queued&owner=neq.ariel&order=priority.asc&limit=50",
            headers=sb_h, timeout=10)
        tasks = r.json() if r.status_code == 200 else []
    except:
        tasks = []

    def ml_score(t):
        s = 50.0
        s += {"P0": 30, "P1": 20, "P2": 10, "P3": 0}.get(t.get("priority", "P3"), 0)
        sla = t.get("sla_deadline")
        if sla:
            try:
                dl = datetime.fromisoformat(sla.replace("Z", "+00:00"))
                days = (dl - datetime.now(timezone.utc)).days
                if days < 0: s += 25
                elif days < 3: s += 20
                elif days < 7: s += 12
            except: pass
        dm = t.get("project", "")
        s += {"BIDDEED": 8, "ZONEWISE": 8, "GTM": 6, "ECOSYSTEM": 5}.get(dm, 3)
        return s

    scored = [(ml_score(t), t) for t in tasks]
    scored.sort(key=lambda x: -x[0])
    to_dispatch = scored[:slots]

    if not to_dispatch:
        print("No tasks to dispatch")
        return

    # --- DISPATCH IN PARALLEL ---
    print(f"Dispatching {len(to_dispatch)} tasks in parallel:")
    futures = []
    for score, task in to_dispatch:
        task["ml_score"] = score
        tid = task.get("task_id", "?")
        print(f"  → [{score:.0f}] {tid}: {task.get('description','')[:50]}")
        futures.append(execute_task.spawn(task))

    # Collect results
    results = []
    for f in futures:
        try:
            r = f.get(timeout=30)
            results.append(r)
        except Exception as e:
            results.append({"status": "error", "error": str(e)})

    # --- TELEGRAM SUMMARY ---
    lines = [f"EXECUTOR {NOW.strftime('%I:%M %p')} EST — {len(results)} dispatched"]
    for r in results:
        status = r.get("status", "?")
        tid = r.get("task_id", "?")
        score = r.get("score", 0)
        emoji = "OK" if status == "dispatched" else "FAIL"
        lines.append(f"  {emoji} [{score:.0f}] {tid}")
        if r.get("run_url"):
            lines.append(f"    {r['run_url']}")
    
    msg = NL.join(lines)
    print(msg)
    if TG_TOKEN:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": os.environ.get("TELEGRAM_CHAT_ID",""), "text": msg[:4000]},
            timeout=10)


@app.local_entrypoint()
def main():
    """Manual trigger: modal run modal_executor.py"""
    continuous_loop.remote()
