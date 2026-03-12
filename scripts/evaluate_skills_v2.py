#!/usr/bin/env python3
"""Skills.sh Evaluator V2 — Keyword + optional Gemini Flash scoring"""
import os, json, subprocess, time, hashlib, re, sys
from pathlib import Path

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

REPOS = [
    "vercel-labs/agent-skills", "vercel-labs/agent-browser", "vercel-labs/next-skills",
    "anthropics/skills", "anthropics/claude-code", "obra/superpowers",
    "browser-use/browser-use", "coreyhaines31/marketingskills", "supabase/agent-skills",
    "firecrawl/cli", "wshobson/agents", "github/awesome-copilot",
    "google-labs-code/stitch-skills", "supercent-io/skills-template",
    "better-auth/skills", "tavily-ai/skills", "squirrelscan/skills",
    "currents-dev/playwright-best-practices-skill", "imbue-ai/vet", "shadcn/ui"
]

# Stack-relevant keyword weights
KEYWORDS = {
    # Critical (15 pts each)
    "supabase": 15, "postgresql": 15, "postgres": 15, "foreclosure": 15, "real estate": 15,
    "firecrawl": 15, "scraping": 12, "scraper": 12, "crawler": 12,
    # High (10 pts)
    "react": 10, "tailwind": 10, "nextjs": 10, "next.js": 10, "typescript": 10,
    "cloudflare": 10, "github actions": 10, "ci/cd": 10, "deployment": 10,
    "playwright": 10, "testing": 8, "e2e": 10, "debugging": 10,
    "seo": 10, "marketing": 8, "landing page": 10, "conversion": 8,
    "langraph": 12, "langgraph": 12, "agent": 8, "orchestration": 10,
    "browser": 8, "automation": 8, "puppeteer": 10,
    "security": 8, "authentication": 8, "auth": 6, "rls": 12,
    # Medium (5 pts)
    "python": 5, "node": 5, "javascript": 5, "api": 5, "rest": 5,
    "database": 6, "sql": 6, "migration": 6, "schema": 6,
    "docker": 5, "git": 4, "commit": 3, "code review": 6,
    "performance": 5, "optimization": 5, "monitoring": 5,
    "documentation": 4, "markdown": 3, "pdf": 5, "docx": 5,
    "shadcn": 8, "design system": 6, "component": 4,
    "search": 6, "tavily": 8, "web search": 8,
    # Negative (reduce score for irrelevant stacks)
    "swift": -10, "swiftui": -10, "ios": -8, "android": -5,
    "flutter": -10, "dart": -10, "kotlin": -8,
    "vue": -5, "angular": -8, "svelte": -3,
    "azure": -8, "aws lambda": -5, "gcp": -5,
    "ruby": -8, "rails": -8, "php": -8, "laravel": -8,
    "java": -5, "spring": -8, "c#": -8, ".net": -8,
    "rust": -3, "go ": -3, "golang": -3,
    "chinese": -5, "japanese": -5, "korean": -5,  # Language-specific content
}

CATEGORIES = {
    "frontend": ["react", "tailwind", "nextjs", "next.js", "css", "component", "ui", "design", "shadcn"],
    "backend": ["api", "rest", "graphql", "server", "node", "express", "endpoint"],
    "database": ["supabase", "postgresql", "postgres", "sql", "migration", "schema", "rls", "database"],
    "scraping": ["scraper", "scraping", "crawler", "firecrawl", "browser", "puppeteer", "playwright"],
    "testing": ["test", "e2e", "playwright", "jest", "vitest", "tdd", "debugging"],
    "marketing_seo": ["seo", "marketing", "landing", "conversion", "copywriting", "analytics", "content"],
    "ai_orchestration": ["agent", "langgraph", "orchestration", "llm", "prompt", "subagent"],
    "deployment": ["deploy", "cloudflare", "github actions", "ci/cd", "docker", "vercel"],
    "security": ["security", "auth", "authentication", "vulnerability", "audit", "encryption"],
    "infrastructure": ["monitoring", "logging", "performance", "optimization", "git", "workflow"],
    "documentation": ["documentation", "markdown", "pdf", "docx", "report", "template"],
    "design": ["design", "ui", "ux", "figma", "wireframe", "mockup", "brand"],
    "search": ["search", "tavily", "web search", "crawl", "index"],
}

import urllib.request

def keyword_score(content):
    """Score based on keyword matching"""
    content_lower = content.lower()
    score = 30  # Base score
    matched = []
    
    for kw, weight in KEYWORDS.items():
        if kw.lower() in content_lower:
            score += weight
            if weight > 0:
                matched.append(kw)
    
    return max(0, min(100, score)), matched

def detect_category(content):
    """Detect best category"""
    content_lower = content.lower()
    scores = {}
    for cat, keywords in CATEGORIES.items():
        scores[cat] = sum(1 for kw in keywords if kw in content_lower)
    return max(scores, key=scores.get) if any(scores.values()) else "other"

def upsert_batch(records):
    """Upsert to Supabase via REST"""
    url = f"{SUPABASE_URL}/rest/v1/skills_catalog"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    data = json.dumps(records).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return resp.status
    except Exception as e:
        print(f"  Supabase upsert error: {e}")
        return 0

def main():
    workdir = "/tmp/skills-eval"
    os.makedirs(workdir, exist_ok=True)
    
    print("=" * 60)
    print("  SKILLS.SH EVALUATOR V2 — Agent 17")
    print("=" * 60)
    
    # Clone
    print(f"\n[1/3] Cloning {len(REPOS)} repos...")
    procs = []
    for repo in REPOS:
        name = repo.replace("/", "_")
        dest = os.path.join(workdir, name)
        if not os.path.exists(dest):
            p = subprocess.Popen(["git", "clone", "--depth", "1", f"https://github.com/{repo}.git", dest],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            procs.append(p)
    for p in procs:
        p.wait()
    print(f"  Done")
    
    # Extract
    print("[2/3] Extracting skills...")
    skills = []
    for root, dirs, files in os.walk(workdir):
        for f in files:
            if f == "SKILL.md":
                path = os.path.join(root, f)
                parts = path.replace(workdir + "/", "").split("/")
                repo = parts[0].replace("_", "/", 1)
                skill_name = parts[-2] if len(parts) > 2 else "root"
                with open(path, "r", errors="replace") as fh:
                    content = fh.read()
                skills.append({"repo": repo, "skill_name": skill_name, "content": content})
    print(f"  Found {len(skills)} skills")
    
    # Evaluate
    print("[3/3] Scoring...")
    batch = []
    stats = {"ADOPT": 0, "EVALUATE": 0, "CONDITIONAL": 0, "SKIP": 0}
    
    for skill in skills:
        score, matched = keyword_score(skill["content"])
        category = detect_category(skill["content"])
        status = "ADOPT" if score >= 80 else "EVALUATE" if score >= 60 else "CONDITIONAL" if score >= 40 else "SKIP"
        stats[status] += 1
        
        record = {
            "id": hashlib.md5(f"{skill['repo']}:{skill['skill_name']}".encode()).hexdigest(),
            "repo": skill["repo"],
            "skill_name": skill["skill_name"],
            "score": score,
            "category": category,
            "status": status,
            "reason": f"Keywords: {', '.join(matched[:5])}" if matched else "No matching keywords",
            "content_hash": hashlib.md5(skill["content"].encode()).hexdigest(),
            "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        batch.append(record)
        
        if len(batch) >= 50:
            upsert_batch(batch)
            batch = []
    
    if batch:
        upsert_batch(batch)
    
    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {len(skills)} skills evaluated")
    print(f"  ADOPT: {stats['ADOPT']} | EVALUATE: {stats['EVALUATE']} | CONDITIONAL: {stats['CONDITIONAL']} | SKIP: {stats['SKIP']}")
    print(f"{'=' * 60}")
    
    # Print top ADOPT skills
    all_records = []
    for skill in skills:
        score, matched = keyword_score(skill["content"])
        all_records.append((score, skill["skill_name"], skill["repo"], matched))
    
    all_records.sort(reverse=True)
    print("\nTop 20 Skills for BidDeed.AI/ZoneWise:")
    for score, name, repo, matched in all_records[:20]:
        print(f"  {score:3d} | {name:40s} | {repo}")

if __name__ == "__main__":
    main()
