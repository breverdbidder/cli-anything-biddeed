#!/usr/bin/env python3
"""Evening Verification Sweep — 5 PM EST daily.
Issue: breverdbidder/cli-anything-biddeed#21
Purpose: Check completed tasks for proof, score daily honesty %, pre-build carryforward.
"""
import requests, json, os
from datetime import datetime, timezone, timedelta

SB_URL = os.environ["SUPABASE_URL"]
SB_KEY = os.environ["SUPABASE_KEY"]
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

EST = timezone(timedelta(hours=-4))
NOW = datetime.now(EST)
TODAY = NOW.strftime("%Y-%m-%d")
NL = "\n"

sb_h = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

# ──────────────────────────────────────────────────────────────
# 1. Load today's task_carryforward records
# ──────────────────────────────────────────────────────────────

today_records = []
try:
    r = requests.get(
        f"{SB_URL}/rest/v1/task_carryforward?date=eq.{TODAY}",
        headers=sb_h, timeout=10,
    )
    if r.status_code == 200:
        today_records = r.json()
    print(f"Today's records: {len(today_records)}")
except Exception as e:
    print(f"Load today records failed: {e}")

# ──────────────────────────────────────────────────────────────
# 2. Check nexus_tasks for tasks marked done today
# ──────────────────────────────────────────────────────────────

completed_today = []
try:
    r = requests.get(
        f"{SB_URL}/rest/v1/nexus_tasks"
        f"?status=eq.success"
        f"&updated_at=gte.{TODAY}T00:00:00Z",
        headers=sb_h, timeout=10,
    )
    if r.status_code == 200:
        completed_today = r.json()
    print(f"Completed today (nexus): {len(completed_today)}")
except Exception as e:
    print(f"Completed tasks query failed: {e}")

# ──────────────────────────────────────────────────────────────
# 3. Mark tasks completed in task_carryforward, flag unverified
# ──────────────────────────────────────────────────────────────

completed_ids = {t.get("task_id") for t in completed_today}
verified_count = unverified_count = 0

for t in completed_today:
    tid = t.get("task_id")
    if not tid:
        continue
    # Check if it has verification proof in metadata
    meta = t.get("metadata") or {}
    has_proof = bool(meta.get("verification_proof") or meta.get("completion_proof"))

    row = {
        "status": "completed",
        "verified": has_proof,
        "verification_method": "self_report" if has_proof else None,
        "verification_proof": meta.get("verification_proof", meta.get("completion_proof")),
    }
    try:
        # Update existing carryforward record for today if exists
        r = requests.patch(
            f"{SB_URL}/rest/v1/task_carryforward?task_id=eq.{tid}&date=eq.{TODAY}",
            headers=sb_h, json=row, timeout=5,
        )
        if r.status_code == 404 or r.content == b'[]':
            # Insert new record if not yet in today's carryforward
            requests.post(
                f"{SB_URL}/rest/v1/task_carryforward",
                headers={**sb_h, "Prefer": "resolution=ignore-duplicates"},
                json={"task_id": tid, "date": TODAY, **row},
                timeout=5,
            )
    except Exception:
        pass

    if has_proof:
        verified_count += 1
    else:
        unverified_count += 1

# ──────────────────────────────────────────────────────────────
# 4. Calculate daily honesty_score
# ──────────────────────────────────────────────────────────────

total_completed = len(completed_today)
honesty_score = round(verified_count / total_completed, 2) if total_completed > 0 else None
honesty_pct = f"{honesty_score * 100:.0f}%" if honesty_score is not None else "N/A (no completions)"

print(f"Honesty score: {honesty_pct} ({verified_count} verified / {total_completed} completed)")

# ──────────────────────────────────────────────────────────────
# 5. Update daily_digest with evening honesty_score
# ──────────────────────────────────────────────────────────────

try:
    r = requests.patch(
        f"{SB_URL}/rest/v1/daily_digest?date=eq.{TODAY}",
        headers=sb_h,
        json={"honesty_score": honesty_score},
        timeout=5,
    )
    print(f"daily_digest honesty updated: {r.status_code}")
except Exception as e:
    print(f"daily_digest update failed: {e}")

# ──────────────────────────────────────────────────────────────
# 6. Log honesty violations for unverified completions
# ──────────────────────────────────────────────────────────────

unverified_tasks = [t for t in completed_today if not (t.get("metadata") or {}).get("verification_proof")]
for t in unverified_tasks:
    violation = {
        "claim": f"Task {t.get('task_id', '?')} marked done without proof",
        "domain": t.get("project", "UNKNOWN"),
        "severity": "WARN",
        "resolved": False,
        "context": f"Evening sweep {TODAY}: no verification_proof in metadata",
    }
    try:
        requests.post(
            f"{SB_URL}/rest/v1/honesty_violations",
            headers={**sb_h, "Prefer": "resolution=ignore-duplicates"},
            json=violation, timeout=5,
        )
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────
# 7. Send Telegram sweep summary
# ──────────────────────────────────────────────────────────────

lines = []
lines.append(f"EVENING SWEEP -- {NOW.strftime('%A, %B %d')} 5 PM")
lines.append("")
lines.append(f"Completed today: {total_completed}")
lines.append(f"Verified: {verified_count} | Unverified: {unverified_count}")
lines.append(f"Honesty score: {honesty_pct}")

if unverified_tasks:
    lines.append("")
    lines.append("UNVERIFIED COMPLETIONS (carry to tomorrow):")
    for t in unverified_tasks[:5]:
        tid = t.get("task_id", "?")
        desc = t.get("description", "")[:55]
        lines.append(f"  {tid}: {desc}")
    lines.append("Add verification_proof to metadata to clear these.")

if total_completed == 0:
    lines.append("")
    lines.append("No tasks completed today — nothing to verify.")

message = NL.join(lines)
print(NL + message)

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

print(NL + f"Evening sweep complete. Honesty: {honesty_pct}")
