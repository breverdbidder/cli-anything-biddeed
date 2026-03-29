#!/usr/bin/env python3
"""Daily Action Plan — 6:00 AM EDT Telegram digest."""
import requests, json, os
from datetime import datetime, timezone, timedelta

SB_URL = os.environ["SUPABASE_URL"]
SB_KEY = os.environ["SUPABASE_KEY"]
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
GH_PAT = os.environ.get("GH_PAT", "")
EST = timezone(timedelta(hours=-4))
NOW = datetime.now(EST)
TODAY = NOW.strftime("%Y-%m-%d")
DAY_NAME = NOW.strftime("%A, %B %d")
sb_h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
gh_h = {"Authorization": f"token {GH_PAT}"} if GH_PAT else {}
NL = chr(10)

# 1. Pull open tasks from Nexus
open_tasks = []
try:
    r = requests.get(
        f"{SB_URL}/rest/v1/nexus_tasks?status=in.(queued,running,dispatched,blocked)&order=priority.asc,sla_deadline.asc.nullslast",
        headers=sb_h, timeout=10
    )
    if r.status_code == 200:
        open_tasks = r.json()
except Exception as e:
    print(f"Nexus query failed: {e}")

# 2. Classify tasks
p0_tasks, overdue, ariel_tasks, claude_tasks, blocked_tasks = [], [], [], [], []

for t in open_tasks:
    tid = t.get("task_id", "?")
    desc = t.get("description", "")[:100]
    pri = t.get("priority", "P3")
    owner = t.get("owner", "?")
    status = t.get("status", "?")
    sla = t.get("sla_deadline")
    project = t.get("project", "?")
    days_left = None
    urgent_flag = ""
    if sla:
        try:
            deadline = datetime.fromisoformat(sla.replace("Z", "+00:00"))
            days_left = (deadline - datetime.now(timezone.utc)).days
            if days_left < 0:
                urgent_flag = "OVERDUE"
                overdue.append(t)
            elif days_left <= 7:
                urgent_flag = "THIS WEEK"
            elif days_left <= 14:
                urgent_flag = "2 WEEKS"
        except Exception:
            pass
    entry = {"id": tid, "desc": desc, "pri": pri, "owner": owner,
             "status": status, "project": project, "days_left": days_left, "urgent": urgent_flag}
    if pri == "P0":
        p0_tasks.append(entry)
    if status == "blocked":
        blocked_tasks.append(entry)
    if owner == "ariel":
        ariel_tasks.append(entry)
    else:
        claude_tasks.append(entry)

# 3. GHA health from yesterday
gha_ok = gha_fail = 0
yesterday = (NOW - timedelta(days=1)).strftime("%Y-%m-%d")
try:
    repos = ["cli-anything-biddeed", "zonewise-web", "everest-nexus", "zonewise-gtm", "brevard-bidder-scraper"]
    for repo in repos:
        r = requests.get(
            f"https://api.github.com/repos/breverdbidder/{repo}/actions/runs?created=%3E{yesterday}T00:00:00Z&per_page=50",
            headers=gh_h, timeout=10
        )
        if r.status_code == 200:
            for run in r.json().get("workflow_runs", []):
                if run.get("conclusion") == "success":
                    gha_ok += 1
                elif run.get("conclusion") == "failure":
                    gha_fail += 1
except Exception:
    pass

# 3b. Honesty violations
violations = []
try:
    hv = requests.get(
        f"{SB_URL}/rest/v1/honesty_violations?resolved=eq.false&order=severity.asc",
        headers=sb_h, timeout=10
    )
    if hv.status_code == 200:
        violations = hv.json()
except Exception:
    pass

# 4. Build message
lines = []
lines.append(f"DAILY ACTION PLAN -- {DAY_NAME}")
lines.append(f"{NOW.strftime('%I:%M %p')} EST")
lines.append("")

if p0_tasks or overdue:
    lines.append("CRITICAL (P0 + Deadlines):")
    for t in p0_tasks:
        dl = f" [{t['days_left']}d left]" if t["days_left"] is not None else ""
        icon = "[ARIEL]" if t["owner"] == "ariel" else "[CC]"
        lines.append(f"  {icon} {t['id']}: {t['desc'][:60]}{dl} {t['urgent']}")
    lines.append("")

ariel_non_p0 = [t for t in ariel_tasks if t["pri"] != "P0"]
if ariel_non_p0:
    lines.append("ARIEL TODO:")
    for t in ariel_non_p0:
        dl = f" [{t['days_left']}d]" if t["days_left"] is not None else ""
        lines.append(f"  [{t['pri']}] {t['id']}: {t['desc'][:60]}{dl}")
    lines.append("")

if claude_tasks:
    lines.append("CLAUDE CODE QUEUE:")
    for t in claude_tasks[:5]:
        st = "RUN" if t["status"] == "running" else "QUE"
        lines.append(f"  {st} [{t['pri']}] {t['id']}: {t['desc'][:60]}")
    if len(claude_tasks) > 5:
        lines.append(f"  ... and {len(claude_tasks) - 5} more")
    lines.append("")

if blocked_tasks:
    lines.append("BLOCKED:")
    for t in blocked_tasks:
        lines.append(f"  {t['id']}: {t['desc'][:60]} (owner: {t['owner']})")
    lines.append("")

total_gha = gha_ok + gha_fail
if total_gha > 0:
    health = gha_ok / total_gha * 100
    lines.append(f"GHA: {gha_ok} ok / {gha_fail} fail ({health:.0f}% health)")
    lines.append("")

lines.append(f"SUMMARY: {len(open_tasks)} open | {len(p0_tasks)} P0 | {len(overdue)} overdue | {len(blocked_tasks)} blocked")
lines.append(f"Ariel: {len(ariel_tasks)} | Claude: {len(claude_tasks)}")

message = NL.join(lines)

if violations:
    message += NL + "HONESTY VIOLATIONS (OPEN):" + NL
    for v in violations:
        sev = v.get("severity", "?")
        dom = v.get("domain", "?")
        claim = v.get("claim", "?")[:50]
        message += f"  [{sev}] {dom}: {claim}" + NL

print(message)

# 5. Send to Telegram
if TG_TOKEN and TG_CHAT:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": message[:4000]},
            timeout=10
        )
        if r.status_code == 200:
            print(NL + "Telegram sent")
        else:
            print(f"{NL}Telegram error: {r.status_code} {r.text[:100]}")
    except Exception as e:
        print(f"{NL}Telegram failed: {e}")
else:
    print(NL + "No Telegram credentials -- skipping send")

# 6. Store in Supabase
try:
    rank = 0
    pri_map = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    for t in sorted(open_tasks, key=lambda x: pri_map.get(x.get("priority", "P3"), 3)):
        rank += 1
        item = {
            "date": TODAY,
            "rank": rank,
            "task": f"[{t.get('task_id', '?')}] {t.get('description', '')[:100]}",
            "domain": t.get("project", "PERSONAL"),
            "reason": f"Owner: {t.get('owner', '?')} | SLA: {t.get('sla_deadline', 'none')} | Status: {t.get('status', '?')}",
        }
        requests.post(f"{SB_URL}/rest/v1/daily_action_plans", headers=sb_h, json=item, timeout=5)

    score = {
        "date": TODAY,
        "total_items": len(open_tasks),
        "completed": len([t for t in open_tasks if t.get("status") == "success"]),
        "in_progress": len([t for t in open_tasks if t.get("status") == "running"]),
        "blocked": len([t for t in open_tasks if t.get("status") == "blocked"]),
        "completion_rate": 0.0,
        "top_domain": "NONE",
        "worst_domain": "NONE",
        "streak_days": 0,
    }
    if open_tasks:
        projects = [t.get("project", "?") for t in open_tasks]
        score["top_domain"] = max(set(projects), key=projects.count)
    requests.delete(f"{SB_URL}/rest/v1/daily_scores?date=eq.{TODAY}", headers=sb_h, timeout=5)
    requests.post(f"{SB_URL}/rest/v1/daily_scores", headers=sb_h, json=score, timeout=5)
    print("Supabase stored")
except Exception as e:
    print(f"Supabase store error: {e}")
