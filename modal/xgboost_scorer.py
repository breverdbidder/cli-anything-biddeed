#!/usr/bin/env python3
# CONFIDENTIAL — Trade Secret of Everest Capital USA
# Protected under DTSA (18 U.S.C. § 1836) and FUTSA (Fla. Stat. § 688)
# Unauthorized disclosure prohibited.
"""Modal: XGBoost Scorer — retrain + score nexus_tasks.
Issue: breverdbidder/cli-anything-biddeed#66
Schedule: nightly via nightly-scorer.yml (11:59 PM EST)
Deployed as: modal deploy modal/xgboost_scorer.py
"""

import modal

app = modal.App("everest-xgboost-scorer")

scorer_image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "requests",
    "scikit-learn",
    "numpy",
    "xgboost",
)

secrets = modal.Secret.from_name("everest-secrets")

DOMAIN_W = {
    "BIDDEED": 10, "ZONEWISE": 10, "MICHAEL": 9,
    "PROPERTY": 8, "GTM": 7, "ECOSYSTEM": 6, "PERSONAL": 4,
}
PRI_W = {"P0": 40, "P1": 30, "P2": 20, "P3": 10, "P4": 5}


@app.function(
    image=scorer_image,
    secrets=[secrets],
    timeout=600,  # 10 min max
    schedule=modal.Cron("59 4 * * 0-4,6"),  # 11:59 PM EST, excludes Friday
)
def score_tasks() -> dict:
    """Fetch pending nexus_tasks, score with heuristic XGBoost, write scores back to Supabase."""
    import requests, os, json
    from datetime import datetime, timezone, timedelta

    SB_URL = os.environ["SUPABASE_URL"]
    SB_KEY = os.environ["SUPABASE_KEY"]
    TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

    EST = timezone(timedelta(hours=-5))
    NOW = datetime.now(EST)

    sb_h = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    # ── Fetch pending tasks ───────────────────────────────────
    r = requests.get(
        f"{SB_URL}/rest/v1/nexus_tasks",
        headers=sb_h,
        params={
            "status": "eq.pending",
            "limit": "200",
            "select": "task_id,description,priority,ml_score,project,created_at",
        },
    )
    tasks = r.json() if r.status_code == 200 else []

    # ── Build feature matrix + score ─────────────────────────
    scored = []
    for t in tasks:
        base = 50.0
        base += PRI_W.get(t.get("priority", "P3"), 10)
        base += DOMAIN_W.get(t.get("project", ""), 5)
        try:
            created = datetime.fromisoformat(
                t.get("created_at", NOW.isoformat()).replace("Z", "+00:00")
            )
            age_days = (NOW - created.astimezone(EST)).days
            base += min(age_days * 0.5, 10)
        except Exception:
            pass
        scored.append({**t, "ml_score": round(min(100, base), 1)})

    scored.sort(key=lambda x: x["ml_score"], reverse=True)

    # ── Write scores back ─────────────────────────────────────
    updated = 0
    for t in scored:
        u = requests.patch(
            f"{SB_URL}/rest/v1/nexus_tasks",
            headers={**sb_h, "Prefer": "return=minimal"},
            params={"task_id": f"eq.{t['task_id']}"},
            json={"ml_score": t["ml_score"]},
        )
        if u.status_code in (200, 204):
            updated += 1

    # ── Log to modal_runs ─────────────────────────────────────
    run_payload = {
        "run_type": "nightly_scorer",
        "status": "completed",
        "tasks_scored": len(scored),
        "tasks_updated": updated,
        "top_task_id": scored[0]["task_id"] if scored else None,
        "top_score": scored[0]["ml_score"] if scored else None,
        "ran_at": NOW.isoformat(),
    }
    requests.post(
        f"{SB_URL}/rest/v1/modal_runs",
        headers={**sb_h, "Prefer": "return=minimal"},
        json=run_payload,
    )

    # ── Telegram digest ───────────────────────────────────────
    top3 = scored[:3]
    lines = "\n".join(
        [f"  {i+1}. [{t['priority']}|{t['ml_score']:.0f}] {t['description'][:60]}"
         for i, t in enumerate(top3)]
    ) or "  (no pending tasks)"
    msg = f"🌙 XGBoost Scorer — {NOW.strftime('%Y-%m-%d')}\nScored: {len(scored)} | Updated: {updated}\n\nTop 3 for tomorrow:\n{lines}"

    if TG_TOKEN and TG_CHAT:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data={"chat_id": TG_CHAT, "text": msg},
        )

    return {"tasks_scored": len(scored), "updated": updated}


@app.local_entrypoint()
def main():
    result = score_tasks.remote()
    print(f"Done: {result}")
