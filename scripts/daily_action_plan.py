#!/usr/bin/env python3
"""Daily Action Plan V2 — Intelligent Task Engine.
Issue: breverdbidder/cli-anything-biddeed#21
Flow: 10-step pipeline with ML scoring, carryforward, artifact vault, 7-section Telegram digest.
"""
import requests, json, os
from datetime import datetime, timezone, timedelta, date

SB_URL = os.environ["SUPABASE_URL"]
SB_KEY = os.environ["SUPABASE_KEY"]
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
GH_PAT = os.environ.get("GH_PAT", "")

EST = timezone(timedelta(hours=-4))
NOW = datetime.now(EST)
TODAY = NOW.strftime("%Y-%m-%d")
YESTERDAY = (NOW - timedelta(days=1)).strftime("%Y-%m-%d")
DAY_NAME = NOW.strftime("%A, %B %d")
WEEKDAY = NOW.weekday()  # 0=Mon, 4=Fri, 6=Sun

sb_h = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}
gh_h = {"Authorization": f"token {GH_PAT}"} if GH_PAT else {}
NL = "\n"


# ──────────────────────────────────────────────────────────────
# ML PRIORITY SCORING (heuristic v1 — no LLM calls, $0 cost)
# ──────────────────────────────────────────────────────────────

DOMAIN_WEIGHTS = {
    "BIDDEED": 10, "ZONEWISE": 10, "MICHAEL": 9,
    "PROPERTY": 8, "GTM": 7, "ECOSYSTEM": 6, "PERSONAL": 4,
}


def is_thursday_or_friday():
    return WEEKDAY in (3, 4)


def ml_priority_score(task, carry_count=0, blocker_count=0):
    """Score a task 0-100. Pure heuristics, no LLM."""
    score = 50.0

    # Time pressure (+30 max)
    sla = task.get("sla_deadline")
    if sla:
        try:
            deadline = datetime.fromisoformat(sla.replace("Z", "+00:00"))
            days_left = (deadline - datetime.now(timezone.utc)).days
            if days_left < 0:
                score += 30
            elif days_left < 3:
                score += 25
            elif days_left < 7:
                score += 15
            elif days_left < 14:
                score += 8
        except Exception:
            pass

    # Carryforward penalty (+5 per day carried, max +20)
    score += min(carry_count * 5, 20)

    # Domain weight (+0-10)
    domain = task.get("project", task.get("domain", "PERSONAL"))
    score += DOMAIN_WEIGHTS.get(domain, 5)

    # Blocker multiplier (+3 per blocker)
    score += blocker_count * 3

    # Shabbat sensitivity: push harder Thu/Fri
    if is_thursday_or_friday() and task.get("shabbat_sensitive"):
        score += 10

    # Blocked tasks deprioritized
    if task.get("status") == "blocked":
        score -= 20

    # P0 gets baseline boost
    if task.get("priority") == "P0":
        score += 15

    return round(min(max(score, 0), 100), 1)


# ──────────────────────────────────────────────────────────────
# STEP 1: LOAD YESTERDAY from task_carryforward
# ──────────────────────────────────────────────────────────────

yesterday_records = []
yesterday_honesty_score = None
try:
    r = requests.get(
        f"{SB_URL}/rest/v1/task_carryforward?date=eq.{YESTERDAY}&order=ml_priority_score.desc.nullslast",
        headers=sb_h, timeout=10,
    )
    if r.status_code == 200:
        yesterday_records = r.json()
        completed = [t for t in yesterday_records if t.get("status") == "completed"]
        verified = [t for t in completed if t.get("verified")]
        if completed:
            yesterday_honesty_score = round(len(verified) / len(completed), 2)
    print(f"Yesterday records: {len(yesterday_records)}")
except Exception as e:
    print(f"Yesterday load failed: {e}")

yesterday_completed = [t["task_id"] for t in yesterday_records if t.get("status") == "completed"]
yesterday_open = [t for t in yesterday_records if t.get("status") not in ("completed", "dropped")]


# ──────────────────────────────────────────────────────────────
# STEP 2: CARRYFORWARD LOGIC
# ──────────────────────────────────────────────────────────────

carry_map = {}  # task_id → carry_count
for t in yesterday_open:
    tid = t["task_id"]
    carry_count = t.get("carry_count", 0) + 1
    esc = t.get("escalation_level", 0)
    if carry_count >= 7:
        esc = 3  # critical
    elif carry_count >= 3:
        esc = max(esc, 1)  # nudge
    carry_map[tid] = {"carry_count": carry_count, "escalation_level": esc}


# ──────────────────────────────────────────────────────────────
# STEP 3: LOAD TODAY'S TASKS from nexus_tasks
# ──────────────────────────────────────────────────────────────

open_tasks = []
try:
    r = requests.get(
        f"{SB_URL}/rest/v1/nexus_tasks"
        f"?status=in.(queued,running,dispatched,blocked)"
        f"&order=priority.asc,sla_deadline.asc.nullslast",
        headers=sb_h, timeout=10,
    )
    if r.status_code == 200:
        open_tasks = r.json()
    print(f"Open tasks: {len(open_tasks)}")
except Exception as e:
    print(f"Nexus query failed: {e}")


# ──────────────────────────────────────────────────────────────
# STEP 4: ML SCORING — rank all tasks
# ──────────────────────────────────────────────────────────────

scored_tasks = []
for t in open_tasks:
    tid = t.get("task_id", "?")
    cf = carry_map.get(tid, {})
    carry_count = cf.get("carry_count", 0)
    score = ml_priority_score(t, carry_count=carry_count)
    scored_tasks.append({
        **t,
        "_ml_score": score,
        "_carry_count": carry_count,
        "_escalation": cf.get("escalation_level", 0),
    })

scored_tasks.sort(key=lambda x: x["_ml_score"], reverse=True)
must_do_today = scored_tasks[:5]  # ML top 5

# Classify
p0_tasks = [t for t in scored_tasks if t.get("priority") == "P0"]
overdue = []
ariel_tasks = [t for t in scored_tasks if t.get("owner") == "ariel"]
claude_tasks = [t for t in scored_tasks if t.get("owner") != "ariel"]
blocked_tasks = [t for t in scored_tasks if t.get("status") == "blocked"]

for t in scored_tasks:
    sla = t.get("sla_deadline")
    if sla:
        try:
            deadline = datetime.fromisoformat(sla.replace("Z", "+00:00"))
            if (deadline - datetime.now(timezone.utc)).days < 0:
                overdue.append(t)
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────
# STEP 5: ARTIFACT CHECK — surface buried high-value items
# ──────────────────────────────────────────────────────────────

buried_artifacts = []
try:
    r = requests.get(
        f"{SB_URL}/rest/v1/artifact_vault"
        f"?status=eq.buried&importance=gte.7&order=importance.desc&limit=5",
        headers=sb_h, timeout=10,
    )
    if r.status_code == 200:
        buried_artifacts = r.json()
    print(f"Buried artifacts: {len(buried_artifacts)}")
except Exception as e:
    print(f"Artifact vault query failed: {e}")


# ──────────────────────────────────────────────────────────────
# STEP 6: GHA HEALTH from yesterday
# ──────────────────────────────────────────────────────────────

gha_ok = gha_fail = 0
gha_repo_health = {}
repos = [
    "cli-anything-biddeed", "zonewise-web", "everest-nexus",
    "zonewise-gtm", "brevard-bidder-scraper",
]
try:
    for repo in repos:
        r = requests.get(
            f"https://api.github.com/repos/breverdbidder/{repo}/actions/runs"
            f"?created=%3E{YESTERDAY}T00:00:00Z&per_page=50",
            headers=gh_h, timeout=10,
        )
        if r.status_code == 200:
            ok = fail = 0
            for run in r.json().get("workflow_runs", []):
                if run.get("conclusion") == "success":
                    ok += 1; gha_ok += 1
                elif run.get("conclusion") == "failure":
                    fail += 1; gha_fail += 1
            gha_repo_health[repo] = (ok, fail)
except Exception:
    pass


# ──────────────────────────────────────────────────────────────
# STEP 7: HONESTY AUDIT
# ──────────────────────────────────────────────────────────────

violations = []
try:
    hv = requests.get(
        f"{SB_URL}/rest/v1/honesty_violations?resolved=eq.false&order=severity.asc",
        headers=sb_h, timeout=10,
    )
    if hv.status_code == 200:
        violations = hv.json()
except Exception:
    pass

# Tasks completed yesterday without verification
unverified_completions = [
    t for t in yesterday_records
    if t.get("status") == "completed" and not t.get("verified")
]


# ──────────────────────────────────────────────────────────────
# STEP 8: BUILD 7-SECTION TELEGRAM MESSAGE
# ──────────────────────────────────────────────────────────────

lines = []
lines.append(f"DAILY ACTION PLAN V2 -- {DAY_NAME}")
lines.append(f"{NOW.strftime('%I:%M %p')} EST")
lines.append("")

# ── Section 1: YESTERDAY RESULTS ──
if yesterday_records:
    completed_count = len(yesterday_completed)
    carried_count = len(yesterday_open)
    dropped = len([t for t in yesterday_records if t.get("status") == "dropped"])
    honesty_pct = f"{yesterday_honesty_score * 100:.0f}%" if yesterday_honesty_score is not None else "N/A"
    lines.append(f"1/ YESTERDAY: {completed_count} done | {carried_count} carried | {dropped} dropped | honesty {honesty_pct}")
    if unverified_completions:
        lines.append(f"   ⚠ {len(unverified_completions)} completed without proof")
else:
    lines.append("1/ YESTERDAY: no records (first run or table empty)")
lines.append("")

# ── Section 2: MUST DO TODAY (ML top 5) ──
lines.append("2/ MUST DO TODAY (ML TOP 5):")
if must_do_today:
    for t in must_do_today:
        tid = t.get("task_id", "?")
        desc = t.get("description", "")[:55]
        score = t["_ml_score"]
        carry = t["_carry_count"]
        esc = t["_escalation"]
        carry_tag = f" [{carry}d carry]" if carry > 0 else ""
        esc_tag = " CRITICAL" if esc >= 3 else (" WARN" if esc >= 1 else "")
        lines.append(f"  [{score}] {tid}: {desc}{carry_tag}{esc_tag}")
else:
    lines.append("  (no tasks — nexus_tasks empty or all blocked)")
lines.append("")

# ── Section 3: ARIEL TASKS ──
ariel_non_top5 = [t for t in ariel_tasks if t not in must_do_today]
if ariel_non_top5:
    lines.append("3/ ARIEL TODO:")
    for t in ariel_non_top5[:6]:
        pri = t.get("priority", "P3")
        tid = t.get("task_id", "?")
        desc = t.get("description", "")[:55]
        sla = t.get("sla_deadline", "")
        dl_tag = ""
        if sla:
            try:
                dl = (datetime.fromisoformat(sla.replace("Z", "+00:00")) - datetime.now(timezone.utc)).days
                dl_tag = f" [{dl}d]"
            except Exception:
                pass
        lines.append(f"  [{pri}] {tid}: {desc}{dl_tag}")
    lines.append("")

# ── Section 4: CLAUDE CODE QUEUE ──
cc_non_top5 = [t for t in claude_tasks if t not in must_do_today]
if cc_non_top5:
    lines.append("4/ CLAUDE CODE QUEUE:")
    for t in cc_non_top5[:5]:
        st = "RUN" if t.get("status") == "running" else "QUE"
        score = t["_ml_score"]
        tid = t.get("task_id", "?")
        desc = t.get("description", "")[:55]
        lines.append(f"  {st} [{score}] {tid}: {desc}")
    if len(cc_non_top5) > 5:
        lines.append(f"  ... +{len(cc_non_top5) - 5} more")
    lines.append("")

# ── Section 5: BURIED ARTIFACTS ──
if buried_artifacts:
    lines.append("5/ BURIED ARTIFACTS (deploy these!):")
    for a in buried_artifacts:
        title = a.get("title", "?")[:60]
        imp = a.get("importance", 0)
        domain = a.get("domain", "?")
        url = a.get("source_chat_url", "")
        link = f" -> {url[:40]}" if url else ""
        lines.append(f"  [{imp}/10] [{domain}] {title}{link}")
    lines.append("")

# ── Section 6: BLOCKED + HONESTY VIOLATIONS ──
has_section6 = blocked_tasks or violations
if has_section6:
    lines.append("6/ BLOCKED + VIOLATIONS:")
    for t in blocked_tasks[:4]:
        tid = t.get("task_id", "?")
        desc = t.get("description", "")[:50]
        owner = t.get("owner", "?")
        lines.append(f"  BLOCKED {tid}: {desc} (owner: {owner})")
    for v in violations[:3]:
        sev = v.get("severity", "?")
        dom = v.get("domain", "?")
        claim = v.get("claim", "?")[:40]
        lines.append(f"  VIOLATION [{sev}] {dom}: {claim}")
    lines.append("")

# ── Section 7: GHA HEALTH + STATS ──
lines.append("7/ GHA + STATS:")
total_gha = gha_ok + gha_fail
if total_gha > 0:
    health = gha_ok / total_gha * 100
    lines.append(f"  GHA: {gha_ok} ok / {gha_fail} fail ({health:.0f}%)")
    worst = [repo for repo, (ok, fail) in gha_repo_health.items() if fail > 0]
    if worst:
        lines.append(f"  Failing: {', '.join(worst)}")
else:
    lines.append("  GHA: no runs yesterday")
lines.append(
    f"  Tasks: {len(open_tasks)} open | {len(p0_tasks)} P0 | "
    f"{len(overdue)} overdue | {len(blocked_tasks)} blocked"
)
lines.append(f"  Ariel: {len(ariel_tasks)} | Claude: {len(claude_tasks)}")
if len(carry_map) > 0:
    lines.append(f"  Carried forward: {len(carry_map)} tasks")

message = NL.join(lines)
print(message)


# ──────────────────────────────────────────────────────────────
# STEP 9a: SEND TO TELEGRAM
# ──────────────────────────────────────────────────────────────

if TG_TOKEN and TG_CHAT:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": message[:4000]},
            timeout=10,
        )
        if r.status_code == 200:
            print(NL + "Telegram: sent")
        else:
            print(f"{NL}Telegram error: {r.status_code} {r.text[:100]}")
    except Exception as e:
        print(f"{NL}Telegram failed: {e}")
else:
    print(NL + "Telegram: no credentials — skipping")


# ──────────────────────────────────────────────────────────────
# STEP 9b: STORE IN daily_digest
# ──────────────────────────────────────────────────────────────

buried_ids = [a.get("id") for a in buried_artifacts if a.get("id")]
domains = list({t.get("project", "PERSONAL") for t in open_tasks})

digest_row = {
    "date": TODAY,
    "digest_text": message[:8000],
    "stats": {
        "total": len(open_tasks),
        "p0": len(p0_tasks),
        "overdue": len(overdue),
        "blocked": len(blocked_tasks),
        "carried": len(carry_map),
        "gha_health": round(gha_ok / total_gha * 100, 1) if total_gha > 0 else None,
        "ml_top5": [
            {"task_id": t.get("task_id"), "score": t["_ml_score"]}
            for t in must_do_today
        ],
    },
    "artifacts_referenced": buried_ids,
    "domains_covered": domains,
    "honesty_score": yesterday_honesty_score,
    "carryforward_count": len(carry_map),
}
try:
    # Upsert (delete+insert for idempotency)
    requests.delete(f"{SB_URL}/rest/v1/daily_digest?date=eq.{TODAY}", headers=sb_h, timeout=5)
    r = requests.post(
        f"{SB_URL}/rest/v1/daily_digest",
        headers={**sb_h, "Prefer": "return=representation"},
        json=digest_row,
        timeout=5,
    )
    if r.status_code in (200, 201):
        print("Supabase daily_digest: stored")
    else:
        print(f"Supabase daily_digest error: {r.status_code} {r.text[:100]}")
except Exception as e:
    print(f"Supabase store error: {e}")


# ──────────────────────────────────────────────────────────────
# STEP 9c: INSERT TODAY'S TASKS into task_carryforward
# ──────────────────────────────────────────────────────────────

inserted = skipped = 0
for t in scored_tasks:
    tid = t.get("task_id")
    if not tid:
        continue
    cf = carry_map.get(tid, {})
    row = {
        "task_id": tid,
        "date": TODAY,
        "status": "carried" if tid in carry_map else "new",
        "carry_count": cf.get("carry_count", 0),
        "escalation_level": cf.get("escalation_level", 0),
        "ml_priority_score": t["_ml_score"],
        "ml_factors": {
            "domain": t.get("project", "PERSONAL"),
            "priority": t.get("priority"),
            "status": t.get("status"),
        },
    }
    try:
        r = requests.post(
            f"{SB_URL}/rest/v1/task_carryforward",
            headers={**sb_h, "Prefer": "resolution=ignore-duplicates"},
            json=row,
            timeout=5,
        )
        if r.status_code in (200, 201):
            inserted += 1
        else:
            skipped += 1
    except Exception:
        skipped += 1

print(f"task_carryforward: {inserted} inserted, {skipped} skipped")


# ──────────────────────────────────────────────────────────────
# STEP 10: LEGACY — also store in daily_action_plans (backward compat)
# ──────────────────────────────────────────────────────────────

try:
    rank = 0
    for t in scored_tasks:
        rank += 1
        item = {
            "date": TODAY,
            "rank": rank,
            "task": f"[{t.get('task_id', '?')}] {t.get('description', '')[:100]}",
            "domain": t.get("project", "PERSONAL"),
            "reason": (
                f"ML:{t['_ml_score']} | Owner:{t.get('owner', '?')} | "
                f"SLA:{t.get('sla_deadline', 'none')} | Carry:{t['_carry_count']}"
            ),
        }
        requests.post(
            f"{SB_URL}/rest/v1/daily_action_plans",
            headers=sb_h, json=item, timeout=5,
        )
    print(f"daily_action_plans: {rank} rows stored")
except Exception as e:
    print(f"daily_action_plans error: {e}")
