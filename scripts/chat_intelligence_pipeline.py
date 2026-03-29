#!/usr/bin/env python3
"""Chat Intelligence Pipeline — Extracts strategic signals from chat history,
feeds XGBoost with context it can't get from database fields alone.

Two layers:
1. Frequency Analysis: what topics/tasks appear most often and most recently
2. Gemini Flash: deep semantic extraction of importance, urgency, strategic value
"""
import requests, json, os
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SB_KEY = os.environ.get("SUPABASE_KEY", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
sb_h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
NL = chr(10)

# === LAYER 1: FREQUENCY ANALYSIS ===

# Strategic keywords and their domain mapping
SIGNAL_KEYWORDS = {
    # BIDDEED + ZONEWISE (always paired)
    "biddeed": {"domain": "BIDDEED", "weight": 1.0},
    "zonewise": {"domain": "ZONEWISE", "weight": 1.0},
    "foreclosure": {"domain": "BIDDEED", "weight": 0.9},
    "tax deed": {"domain": "BIDDEED", "weight": 0.9},
    "auction": {"domain": "BIDDEED", "weight": 0.8},
    "envelope conquest": {"domain": "ZONEWISE", "weight": 1.0},
    "parcel": {"domain": "ZONEWISE", "weight": 0.7},
    "zoning": {"domain": "ZONEWISE", "weight": 0.8},
    "67 county": {"domain": "ZONEWISE", "weight": 0.9},
    "lien": {"domain": "BIDDEED", "weight": 0.8},
    "title search": {"domain": "BIDDEED", "weight": 0.8},
    
    # MICHAEL
    "michael": {"domain": "MICHAEL", "weight": 0.9},
    "swim": {"domain": "MICHAEL", "weight": 0.8},
    "futures": {"domain": "MICHAEL", "weight": 1.0},
    "50 free": {"domain": "MICHAEL", "weight": 0.9},
    "lcm": {"domain": "MICHAEL", "weight": 0.8},
    
    # GTM
    "competitor": {"domain": "GTM", "weight": 0.9},
    "algoma": {"domain": "GTM", "weight": 1.0},
    "gridics": {"domain": "GTM", "weight": 0.8},
    "propertyonion": {"domain": "GTM", "weight": 0.8},
    "investor": {"domain": "GTM", "weight": 0.9},
    "gtm": {"domain": "GTM", "weight": 0.8},
    "deploy": {"domain": "GTM", "weight": 0.6},
    "ship": {"domain": "GTM", "weight": 0.7},
    
    # PROPERTY
    "625 ocean": {"domain": "PROPERTY", "weight": 1.0},
    "dvora": {"domain": "PROPERTY", "weight": 1.0},
    "bliss": {"domain": "PROPERTY", "weight": 0.9},
    "building permit": {"domain": "PROPERTY", "weight": 0.8},
    "site plan": {"domain": "PROPERTY", "weight": 0.8},
    
    # ECOSYSTEM
    "summit": {"domain": "ECOSYSTEM", "weight": 0.5},
    "gha": {"domain": "ECOSYSTEM", "weight": 0.4},
    "sentinel": {"domain": "ECOSYSTEM", "weight": 0.4},
    "autoloop": {"domain": "ECOSYSTEM", "weight": 0.5},
    "paperclip": {"domain": "ECOSYSTEM", "weight": 0.7},
    "modal": {"domain": "ECOSYSTEM", "weight": 0.6},
    "honesty protocol": {"domain": "ECOSYSTEM", "weight": 0.5},
}

# Urgency signal words
URGENCY_SIGNALS = {
    "offline": 2.0, "down": 2.0, "broken": 1.5, "critical": 2.0,
    "urgent": 2.0, "asap": 1.8, "today": 1.5, "immediately": 2.0,
    "blocked": 1.5, "stuck": 1.3, "failing": 1.5, "deadline": 1.8,
    "overdue": 2.0, "burning": 1.5, "drain": 1.5, "never delivered": 2.0,
    "months": 1.3, "ship": 1.2, "fix": 1.0, "failure": 1.3,
}

# Ariel frustration signals (= highest priority)
FRUSTRATION_SIGNALS = {
    "big failure": 3.0, "sabotage": 3.0, "drain my energy": 3.0,
    "burning me out": 3.0, "never delivered": 2.5, "mess": 2.0,
    "what's wrong with you": 2.5, "look for alternatives": 3.0,
    "lazy": 2.0, "passive": 2.0, "not enough": 1.5,
}

def analyze_chat_frequency(chat_summaries):
    """Extract frequency-based signals from chat summaries.
    Returns: {domain: {keyword: {count, recency_score, urgency}}}
    """
    now = datetime.now(timezone.utc)
    domain_signals = defaultdict(lambda: defaultdict(lambda: {"count": 0, "recency": 0, "urgency": 0, "chats": []}))
    
    for chat in chat_summaries:
        text = (chat.get("title", "") + " " + chat.get("summary", "")).lower()
        chat_date = chat.get("updated_at", "")
        
        # Calculate recency (0-1, higher = more recent)
        recency = 0.5
        if chat_date:
            try:
                dt = datetime.fromisoformat(chat_date.replace("Z", "+00:00"))
                days_ago = (now - dt).total_seconds() / 86400
                recency = max(0, 1.0 - (days_ago / 30))  # decays over 30 days
            except: pass
        
        # Scan for keywords
        for keyword, meta in SIGNAL_KEYWORDS.items():
            count = text.count(keyword)
            if count > 0:
                domain = meta["domain"]
                weight = meta["weight"]
                entry = domain_signals[domain][keyword]
                entry["count"] += count
                entry["recency"] = max(entry["recency"], recency * weight)
                entry["chats"].append(chat.get("url", ""))
        
        # Scan for urgency
        for word, urgency_weight in URGENCY_SIGNALS.items():
            if word in text:
                # Find which domain this urgency belongs to
                for keyword, meta in SIGNAL_KEYWORDS.items():
                    if keyword in text:
                        domain_signals[meta["domain"]][keyword]["urgency"] = max(
                            domain_signals[meta["domain"]][keyword]["urgency"],
                            urgency_weight * recency
                        )
        
        # Scan for frustration (= P0 everything mentioned in that chat)
        for phrase, frust_weight in FRUSTRATION_SIGNALS.items():
            if phrase in text:
                for keyword, meta in SIGNAL_KEYWORDS.items():
                    if keyword in text:
                        domain_signals[meta["domain"]][keyword]["urgency"] = max(
                            domain_signals[meta["domain"]][keyword]["urgency"],
                            frust_weight
                        )
    
    return domain_signals


def compute_domain_priority(domain_signals):
    """Compute priority score per domain based on chat frequency analysis."""
    domain_scores = {}
    for domain, keywords in domain_signals.items():
        total_mentions = sum(k["count"] for k in keywords.values())
        max_recency = max(k["recency"] for k in keywords.values()) if keywords else 0
        max_urgency = max(k["urgency"] for k in keywords.values()) if keywords else 0
        top_keywords = sorted(keywords.items(), key=lambda x: -(x[1]["count"] * x[1]["recency"]))[:5]
        
        # Composite score
        score = (
            min(total_mentions * 2, 30) +  # mention frequency (max 30)
            max_recency * 25 +               # recency (max 25)
            max_urgency * 20 +               # urgency signals (max 40+)
            len(keywords) * 1                # breadth (how many keywords hit)
        )
        
        domain_scores[domain] = {
            "score": round(score, 1),
            "mentions": total_mentions,
            "recency": round(max_recency, 2),
            "urgency": round(max_urgency, 2),
            "top_keywords": [(k, v["count"]) for k, v in top_keywords],
        }
    
    return domain_scores


# === LAYER 2: GEMINI FLASH DEEP ANALYSIS ===

def gemini_extract_priorities(chat_summaries, domain_scores):
    """Use Gemini Flash to extract strategic priorities from chat context."""
    if not GEMINI_KEY:
        return None
    
    # Build context from top chats
    context = ""
    for chat in chat_summaries[:10]:  # Top 10 most recent
        title = chat.get("title", "?")
        summary = chat.get("summary", "")[:500]
        context += f"CHAT: {title}{NL}{summary}{NL}{NL}"
    
    domain_summary = json.dumps(domain_scores, indent=2)
    
    prompt = f"""You are analyzing chat history for a real estate AI startup (BidDeed.AI + ZoneWise.AI).
Based on the frequency analysis and chat summaries below, output a JSON array of the top 15 strategic priorities.

DOMAIN FREQUENCY SCORES:
{domain_summary}

RECENT CHAT SUMMARIES:
{context}

For each priority, provide:
- "task": what needs to be done (1 sentence)
- "domain": BIDDEED|ZONEWISE|GTM|MICHAEL|PROPERTY|ECOSYSTEM
- "xgboost_boost": how much to boost XGBoost score for matching tasks (0-30 points)
- "reason": why this is important based on chat evidence (1 sentence)
- "matching_keywords": list of keywords that should trigger this boost

Respond with ONLY valid JSON array. No markdown, no explanation."""

    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30
        )
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            # Clean JSON
            text = text.replace("```json", "").replace("```", "").strip()
            priorities = json.loads(text)
            return priorities
    except Exception as e:
        print(f"Gemini extraction error: {e}")
    return None


# === STORE RESULTS ===

def store_chat_intelligence(domain_scores, gemini_priorities=None):
    """Store extracted intelligence in Supabase for XGBoost to consume."""
    if not SB_KEY:
        return
    
    # Store domain scores
    for domain, data in domain_scores.items():
        try:
            requests.post(f"{SB_URL}/rest/v1/insights", headers=sb_h, json={
                "type": "chat_intelligence",
                "category": f"domain_priority_{domain}",
                "content": json.dumps({
                    "domain": domain,
                    "score": data["score"],
                    "mentions": data["mentions"],
                    "recency": data["recency"],
                    "urgency": data["urgency"],
                    "top_keywords": data["top_keywords"],
                    "extracted_at": datetime.now().isoformat(),
                }),
            }, timeout=5)
        except: pass
    
    # Store Gemini priorities
    if gemini_priorities:
        try:
            requests.post(f"{SB_URL}/rest/v1/insights", headers=sb_h, json={
                "type": "chat_intelligence",
                "category": "gemini_priorities",
                "content": json.dumps({
                    "priorities": gemini_priorities,
                    "extracted_at": datetime.now().isoformat(),
                }),
            }, timeout=5)
        except: pass


# === XGBOOST FEATURE ENRICHMENT ===

def enrich_task_with_chat_intel(task, domain_scores, gemini_priorities=None):
    """Add chat intelligence features to a task before XGBoost scoring."""
    domain = task.get("project", "ECOSYSTEM")
    desc = task.get("description", "").lower()
    
    # Domain priority from chat frequency
    ds = domain_scores.get(domain, {})
    task["chat_domain_score"] = ds.get("score", 0)
    task["chat_domain_recency"] = ds.get("recency", 0)
    task["chat_domain_urgency"] = ds.get("urgency", 0)
    task["chat_domain_mentions"] = ds.get("mentions", 0)
    
    # Keyword match boost from Gemini priorities
    gemini_boost = 0
    if gemini_priorities:
        for p in gemini_priorities:
            keywords = p.get("matching_keywords", [])
            for kw in keywords:
                if kw.lower() in desc:
                    gemini_boost = max(gemini_boost, p.get("xgboost_boost", 0))
                    break
    task["gemini_boost"] = gemini_boost
    
    # Frustration signal detection
    frust = 0
    for phrase, weight in FRUSTRATION_SIGNALS.items():
        if phrase in desc:
            frust = max(frust, weight)
    task["frustration_signal"] = frust
    
    return task


if __name__ == "__main__":
    # Test with sample chat data
    sample_chats = [
        {"title": "Ecosystem Audit", "summary": "biddeed.ai offline, GHA health 41%, envelope conquest stuck at 68% for months, competitive analysis buried, modal deployment, burning me out, look for alternatives", "updated_at": "2026-03-29T11:00:00Z", "url": "test1"},
        {"title": "Competitive Intelligence", "summary": "8 competitors analyzed gridics zoneomics testfit propertyonion algoma arkdesign reventure, zonewise is the only platform combining zoning and foreclosure and tax deed data, investor material buried in chat", "updated_at": "2026-03-29T10:00:00Z", "url": "test2"},
        {"title": "Michael Swimming", "summary": "michael 50 free 21.74 relay, 0.45s from futures cut 21.29, need lcm meets may through july, futures july 29 aug 1", "updated_at": "2026-03-29T06:00:00Z", "url": "test3"},
        {"title": "Property Tasks", "summary": "625 ocean st building permit, dvora gavish payoff letter to lisa wavra spira law, site plan compliance", "updated_at": "2026-03-28T18:00:00Z", "url": "test4"},
        {"title": "Envelope Conquest", "summary": "cocoa beach 9% titusville 39% cocoa 41% melbourne 82% conquest stuck never delivered fix the scrapers benchmark guardian", "updated_at": "2026-03-29T09:00:00Z", "url": "test5"},
    ]
    
    print("=== LAYER 1: FREQUENCY ANALYSIS ===")
    signals = analyze_chat_frequency(sample_chats)
    scores = compute_domain_priority(signals)
    
    for domain in sorted(scores.keys(), key=lambda d: -scores[d]["score"]):
        s = scores[domain]
        print(f"\n{domain}: {s['score']} pts")
        print(f"  Mentions: {s['mentions']} | Recency: {s['recency']} | Urgency: {s['urgency']}")
        print(f"  Top keywords: {s['top_keywords'][:3]}")
    
    print("\n=== LAYER 2: GEMINI DEEP ANALYSIS ===")
    if GEMINI_KEY:
        priorities = gemini_extract_priorities(sample_chats, scores)
        if priorities:
            for i, p in enumerate(priorities[:10], 1):
                print(f"  {i}. [{p.get('domain','?')}] +{p.get('xgboost_boost',0)} — {p.get('task','?')}")
    else:
        print("  No GEMINI_API_KEY — skipping deep analysis")
    
    print("\n=== ENRICHMENT TEST ===")
    test_tasks = [
        {"description": "Fix biddeed.ai offline", "project": "BIDDEED", "priority": "P0"},
        {"description": "Envelope conquest cocoa beach 9%", "project": "ZONEWISE", "priority": "P2"},
        {"description": "Find LCM meets for Michael Futures prep", "project": "MICHAEL", "priority": "P1"},
        {"description": "GHA failure utcc-build.yml", "project": "ECOSYSTEM", "priority": "P2"},
    ]
    for t in test_tasks:
        enriched = enrich_task_with_chat_intel(t, scores)
        print(f"  {t['description'][:40]:40s} | domain_score={enriched['chat_domain_score']:5.1f} | urgency={enriched['chat_domain_urgency']:.1f} | gemini_boost={enriched['gemini_boost']}")
