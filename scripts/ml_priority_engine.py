#!/usr/bin/env python3
"""ML Priority Engine — Three-tier scoring for task prioritization.
Tier 1: XGBoost (trained on historical data, primary scorer)
Tier 2: Gemini Flash (LLM context scoring, $0 free tier)
Tier 3: Heuristic (instant fallback, always available)
"""
import json, os, pickle, math
from datetime import datetime, timezone, timedelta

# === TIER 3: HEURISTIC (instant fallback) ===
def heuristic_score(task, now=None):
    """Static weights — always available, no dependencies."""
    if now is None:
        now = datetime.now(timezone(timedelta(hours=-4)))
    s = 50.0
    pri = task.get("priority", "P3")
    s += {"P0": 30, "P1": 20, "P2": 10, "P3": 0}.get(pri, 0)
    
    sla = task.get("sla_deadline")
    if sla:
        try:
            dl = datetime.fromisoformat(sla.replace("Z", "+00:00"))
            days = (dl - datetime.now(timezone.utc)).days
            if days < 0: s += 25
            elif days < 3: s += 20
            elif days < 7: s += 12
            elif days < 14: s += 5
        except: pass
    
    domain = task.get("project", "")
    s += {"BIDDEED": 8, "ZONEWISE": 8, "GTM": 6, "ECOSYSTEM": 5, "MICHAEL": 4, "PROPERTY": 3}.get(domain, 2)
    
    carry = task.get("carry_count", 0)
    s += min(carry * 5, 20)
    
    if task.get("status") == "blocked": s -= 20
    
    # Shabbat Thursday/Friday boost
    dow = now.weekday()
    if dow in (3, 4) and task.get("shabbat_sensitive"):
        s += 10
    
    return min(max(s, 0), 100)


# === TIER 1: XGBOOST (trained model) ===
def extract_features(task, history_stats=None):
    """Extract numeric features from a task for XGBoost."""
    if history_stats is None:
        history_stats = {}
    
    now = datetime.now(timezone.utc)
    features = {}
    
    # Priority encoding
    pri_map = {"P0": 3, "P1": 2, "P2": 1, "P3": 0}
    features["priority_num"] = pri_map.get(task.get("priority", "P3"), 0)
    
    # SLA days remaining (negative = overdue)
    sla = task.get("sla_deadline")
    if sla:
        try:
            dl = datetime.fromisoformat(sla.replace("Z", "+00:00"))
            features["sla_days"] = (dl - now).total_seconds() / 86400
        except:
            features["sla_days"] = 999
    else:
        features["sla_days"] = 999
    
    # Domain encoding
    domain_map = {"BIDDEED": 5, "ZONEWISE": 5, "GTM": 4, "ECOSYSTEM": 3, "MICHAEL": 2, "PROPERTY": 2, "PERSONAL": 1}
    features["domain_num"] = domain_map.get(task.get("project", ""), 1)
    
    # Owner encoding
    features["is_ariel"] = 1 if task.get("owner") == "ariel" else 0
    
    # Carry count (days task has been unfinished)
    features["carry_count"] = task.get("carry_count", 0)
    
    # Task age in days
    created = task.get("created_at")
    if created:
        try:
            ct = datetime.fromisoformat(created.replace("Z", "+00:00"))
            features["age_days"] = (now - ct).total_seconds() / 86400
        except:
            features["age_days"] = 0
    else:
        features["age_days"] = 0
    
    # Time features
    est = datetime.now(timezone(timedelta(hours=-4)))
    features["hour"] = est.hour
    features["day_of_week"] = est.weekday()
    features["is_friday"] = 1 if est.weekday() == 4 else 0
    
    # Historical stats from domain
    domain = task.get("project", "ECOSYSTEM")
    features["domain_completion_rate"] = history_stats.get(f"{domain}_completion_rate", 0.5)
    features["domain_avg_age"] = history_stats.get(f"{domain}_avg_age", 7.0)
    features["overall_queue_size"] = history_stats.get("queue_size", 100)
    
    # Task description features
    desc = task.get("description", "").lower()
    features["is_fix"] = 1 if any(w in desc for w in ["fix", "bug", "error", "fail", "broken"]) else 0
    features["is_build"] = 1 if any(w in desc for w in ["build", "create", "deploy", "ship"]) else 0
    features["is_gha"] = 1 if "gha" in desc or "workflow" in desc else 0
    features["desc_length"] = len(desc)
    
    # Status encoding
    status_map = {"queued": 0, "dispatched": 1, "running": 2, "blocked": -1}
    features["status_num"] = status_map.get(task.get("status", "queued"), 0)
    
    return features

FEATURE_NAMES = [
    "priority_num", "sla_days", "domain_num", "is_ariel", "carry_count",
    "age_days", "hour", "day_of_week", "is_friday",
    "domain_completion_rate", "domain_avg_age", "overall_queue_size",
    "is_fix", "is_build", "is_gha", "desc_length", "status_num"
]

def train_xgboost(tasks_with_outcomes, history_stats=None):
    """Train XGBoost on historical task data.
    tasks_with_outcomes: list of dicts with task fields + 'outcome_score' (0-100).
    outcome_score: how urgent/important this task ACTUALLY was, based on:
      - Did it complete? When?
      - Did it block other tasks?
      - Was it carried for days?
      - Did Ariel escalate it manually?
    """
    try:
        import xgboost as xgb
        import numpy as np
    except ImportError:
        print("XGBoost not installed — using heuristic only")
        return None
    
    X = []
    y = []
    for task in tasks_with_outcomes:
        feats = extract_features(task, history_stats)
        row = [feats.get(f, 0) for f in FEATURE_NAMES]
        X.append(row)
        y.append(task.get("outcome_score", 50))
    
    X = np.array(X)
    y = np.array(y)
    
    model = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        objective="reg:squarederror",
        random_state=42,
    )
    model.fit(X, y)
    
    return model

def xgboost_score(task, model, history_stats=None):
    """Score a task using trained XGBoost model."""
    try:
        import numpy as np
    except ImportError:
        return heuristic_score(task)
    
    feats = extract_features(task, history_stats)
    row = np.array([[feats.get(f, 0) for f in FEATURE_NAMES]])
    pred = model.predict(row)[0]
    return float(min(max(pred, 0), 100))


# === TIER 2: GEMINI FLASH (LLM scoring) ===
def gemini_score(task, context=""):
    """Use Gemini Flash (free tier) for context-rich scoring."""
    import requests
    
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
    if not GEMINI_KEY:
        return None
    
    desc = task.get("description", "")[:200]
    pri = task.get("priority", "P3")
    domain = task.get("project", "?")
    owner = task.get("owner", "?")
    carry = task.get("carry_count", 0)
    sla = task.get("sla_deadline", "none")
    
    prompt = f"""Score this task 0-100 for execution priority. Higher = do first.
Consider: urgency, business impact, blocking potential, carry count (days delayed).

Task: {desc}
Priority: {pri} | Domain: {domain} | Owner: {owner}
Carry count: {carry} days | SLA: {sla}
{f"Context: {context}" if context else ""}

Respond with ONLY a number 0-100. Nothing else."""

    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=10
        )
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            score = float("".join(c for c in text if c.isdigit() or c == "."))
            return min(max(score, 0), 100)
    except:
        pass
    return None


# === UNIFIED SCORER ===
def score_task(task, model=None, history_stats=None, use_gemini=False):
    """Three-tier scoring: XGBoost → Gemini → Heuristic.
    Returns: (score, method, factors)"""
    
    # Tier 1: XGBoost (if model trained)
    if model is not None:
        try:
            xgb_score = xgboost_score(task, model, history_stats)
            factors = extract_features(task, history_stats)
            return xgb_score, "xgboost", factors
        except:
            pass
    
    # Tier 2: Gemini Flash (if enabled and key available)
    if use_gemini:
        gem_score = gemini_score(task)
        if gem_score is not None:
            return gem_score, "gemini", {"raw_score": gem_score}
    
    # Tier 3: Heuristic (always available)
    h_score = heuristic_score(task)
    return h_score, "heuristic", {"base": 50}


# === TRAINING DATA BUILDER ===
def build_training_data(sb_url, sb_key):
    """Build training dataset from historical Supabase data."""
    import requests
    sb_h = {"apikey": sb_key, "Authorization": f"Bearer {sb_key}"}
    training = []
    
    # 1. Nexus tasks — completed vs cancelled vs still queued
    try:
        r = requests.get(f"{sb_url}/rest/v1/nexus_tasks?select=*&limit=500", headers=sb_h, timeout=15)
        tasks = r.json() if r.status_code == 200 else []
        
        for t in tasks:
            status = t.get("status", "queued")
            created = t.get("created_at", "")
            
            # Calculate outcome score based on what actually happened
            if status == "success":
                outcome = 85  # completed = was important
            elif status == "cancelled":
                outcome = 15  # cancelled = wasn't important
            elif status == "running" or status == "dispatched":
                outcome = 70  # in progress = moderately important
            elif status == "blocked":
                outcome = 40  # blocked = important but stuck
            elif status == "queued":
                # Age matters — old queued tasks should have been done or cancelled
                age = 0
                if created:
                    try:
                        ct = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        age = (datetime.now(timezone.utc) - ct).total_seconds() / 86400
                    except: pass
                if age > 14:
                    outcome = 20  # old and untouched = probably not important
                elif age > 7:
                    outcome = 35
                else:
                    outcome = 50  # fresh = unknown
            else:
                outcome = 50
            
            # Boost outcome if P0/P1
            pri = t.get("priority", "P3")
            if pri == "P0": outcome = min(outcome + 15, 100)
            elif pri == "P1": outcome = min(outcome + 10, 100)
            
            # Boost if it was for ariel (owner escalated)
            if t.get("owner") == "ariel":
                outcome = min(outcome + 10, 100)
            
            t["outcome_score"] = outcome
            training.append(t)
    except Exception as e:
        print(f"Nexus fetch error: {e}")
    
    # 2. Daily checkpoints — completed tasks get high scores
    try:
        r = requests.get(f"{sb_url}/rest/v1/daily_checkpoints?select=*&limit=500", headers=sb_h, timeout=15)
        checkpoints = r.json() if r.status_code == 200 else []
        
        for cp in checkpoints:
            fake_task = {
                "priority": cp.get("priority", "P2"),
                "project": cp.get("domain", "ECOSYSTEM"),
                "owner": "claude_code",
                "description": cp.get("task", ""),
                "status": cp.get("status", "queued"),
                "created_at": cp.get("created_at", ""),
                "sla_deadline": None,
                "carry_count": 0,
            }
            if cp.get("status") == "completed":
                fake_task["outcome_score"] = 80
            elif cp.get("status") == "failed":
                fake_task["outcome_score"] = 60  # was attempted = was important
            else:
                fake_task["outcome_score"] = 45
            training.append(fake_task)
    except Exception as e:
        print(f"Checkpoints fetch error: {e}")
    
    # 3. Compute history stats for feature engineering
    history_stats = {}
    from collections import Counter, defaultdict
    
    domain_completed = defaultdict(int)
    domain_total = defaultdict(int)
    domain_ages = defaultdict(list)
    
    for t in training:
        d = t.get("project", "ECOSYSTEM")
        domain_total[d] += 1
        if t.get("status") == "success" or t.get("outcome_score", 0) >= 75:
            domain_completed[d] += 1
        age = 0
        created = t.get("created_at", "")
        if created:
            try:
                ct = datetime.fromisoformat(created.replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - ct).total_seconds() / 86400
            except: pass
        domain_ages[d].append(age)
    
    for d in domain_total:
        history_stats[f"{d}_completion_rate"] = domain_completed[d] / max(domain_total[d], 1)
        ages = domain_ages[d]
        history_stats[f"{d}_avg_age"] = sum(ages) / max(len(ages), 1)
    
    history_stats["queue_size"] = sum(1 for t in training if t.get("status") == "queued")
    
    return training, history_stats


if __name__ == "__main__":
    import sys
    
    SB_URL = os.environ.get("SUPABASE_URL", "")
    SB_KEY = os.environ.get("SUPABASE_KEY", "")
    
    if not SB_URL:
        print("No SUPABASE_URL — cannot train")
        sys.exit(1)
    
    print("Building training data from Supabase...")
    training_data, history_stats = build_training_data(SB_URL, SB_KEY)
    print(f"Training samples: {len(training_data)}")
    print(f"History stats: {json.dumps({k: round(v, 2) for k, v in history_stats.items()}, indent=2)}")
    
    print("\nTraining XGBoost...")
    model = train_xgboost(training_data, history_stats)
    
    if model:
        # Save model
        model_path = os.environ.get("MODEL_PATH", "/tmp/priority_model.pkl")
        with open(model_path, "wb") as f:
            pickle.dump({"model": model, "history_stats": history_stats, "trained_at": datetime.now().isoformat()}, f)
        print(f"Model saved: {model_path}")
        
        # Feature importance
        import numpy as np
        importances = model.feature_importances_
        sorted_idx = np.argsort(importances)[::-1]
        print("\nFeature importance:")
        for i in sorted_idx[:10]:
            print(f"  {FEATURE_NAMES[i]:30s} {importances[i]:.4f}")
        
        # Score some sample tasks
        print("\nSample scores:")
        samples = [
            {"priority": "P0", "project": "BIDDEED", "owner": "ariel", "description": "biddeed.ai offline", "sla_deadline": "2026-03-30T00:00:00Z", "carry_count": 5, "status": "queued", "created_at": "2026-03-20T00:00:00Z"},
            {"priority": "P2", "project": "ECOSYSTEM", "owner": "claude_code", "description": "GHA failure fix", "carry_count": 0, "status": "queued", "created_at": "2026-03-29T00:00:00Z"},
            {"priority": "P1", "project": "MICHAEL", "owner": "ariel", "description": "Find LCM meets May-Jul for Futures prep", "sla_deadline": "2026-05-01T00:00:00Z", "carry_count": 0, "status": "queued", "created_at": "2026-03-29T00:00:00Z"},
        ]
        for s in samples:
            score, method, factors = score_task(s, model=model, history_stats=history_stats)
            print(f"  [{method}] {score:.1f} — {s['description'][:50]}")
    else:
        print("XGBoost training failed — heuristic only")
