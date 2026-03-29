#!/usr/bin/env python3
"""
l3_analyze.py — AUTOLOOP L3 Post-Execution Analyzer
Spec: specs/AUTOLOOP-L3-SPEC.md
Issue: breverdbidder/cli-anything-biddeed#16

Pipes eval_runner.py results + SKILL.md content to Gemini Flash (or DeepSeek)
for structured LLM analysis. Outputs to skill_analyses Supabase table.

Usage:
    python scripts/l3_analyze.py \\
        --skill zonewise-scraper \\
        --skill-md .claude/skills/zonewise-scraper/SKILL.md \\
        --eval-results zonewise/eval/final_20260329.json \\
        --run-id autoloop_20260329_020000

    python scripts/l3_analyze.py \\
        --skill cost-discipline \\
        --skill-md .claude/skills/cost-discipline/SKILL.md \\
        --eval-results cost-discipline/eval/final_20260329.json \\
        --run-id autoloop_20260329_020000 \\
        --dry-run
"""

import argparse
import json
import os
import sys
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path


def levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein distance between two strings."""
    if len(a) < len(b):
        return levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if ca == cb else 1)))
        prev = curr
    return prev[-1]


def levenshtein_similarity(a: str, b: str) -> float:
    """Normalized Levenshtein similarity (0-1)."""
    if not a and not b:
        return 1.0
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 1.0
    return 1.0 - (levenshtein(a, b) / max_len)


def classify_failure(expected: str, actual: str) -> tuple[str, float]:
    """Classify a failed assertion by similarity. Returns (type, similarity)."""
    sim = levenshtein_similarity(str(expected), str(actual))
    if sim > 0.7:
        return "fix", sim
    elif sim > 0.3:
        return "derived", sim
    else:
        return "captured", sim


def load_eval_results(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def load_skill_md(path: str) -> str:
    with open(path) as f:
        return f.read()


def get_prior_analyses(skill_name: str, supabase_url: str, supabase_key: str, limit: int = 3) -> list:
    """Fetch last N analyses for this skill from Supabase."""
    try:
        import urllib.request
        url = (
            f"{supabase_url}/rest/v1/skill_analyses"
            f"?skill_name=eq.{skill_name}"
            f"&order=created_at.desc"
            f"&limit={limit}"
        )
        req = urllib.request.Request(url, headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[l3_analyze] Warning: could not fetch prior analyses: {e}", file=sys.stderr)
        return []


def call_gemini_flash(prompt_template: str, context: dict, api_key: str) -> dict:
    """Call Gemini Flash via REST API. Returns parsed JSON or raises."""
    import urllib.request
    import urllib.parse

    user_message = json.dumps(context, indent=2)
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": f"{prompt_template}\n\n## Context\n```json\n{user_message}\n```"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 512,
            "responseMimeType": "application/json"
        }
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        response = json.loads(resp.read())

    text = response["candidates"][0]["content"]["parts"][0]["text"]
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def call_deepseek(prompt_template: str, context: dict, api_key: str) -> dict:
    """Fallback: DeepSeek V3.2 via OpenAI-compatible API."""
    import urllib.request

    user_message = json.dumps(context, indent=2)
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": prompt_template
            },
            {
                "role": "user",
                "content": f"```json\n{user_message}\n```\n\nOutput ONLY valid JSON."
            }
        ],
        "temperature": 0.1,
        "max_tokens": 512,
        "response_format": {"type": "json_object"}
    }

    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        response = json.loads(resp.read())

    return json.loads(response["choices"][0]["message"]["content"])


def persist_to_supabase(record: dict, supabase_url: str, supabase_key: str) -> bool:
    """Insert analysis record into skill_analyses table."""
    try:
        import urllib.request
        url = f"{supabase_url}/rest/v1/skill_analyses"
        req = urllib.request.Request(
            url,
            data=json.dumps(record).encode(),
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        print(f"[l3_analyze] DB write failed: {e}", file=sys.stderr)
        return False


def update_lineage_counters(skill_name: str, run_id: str, pass_count: int, fail_count: int,
                             content_hash: str, supabase_url: str, supabase_key: str) -> bool:
    """Increment total_runs/total_pass/total_fail for the active lineage record."""
    try:
        import urllib.request

        # Fetch active record
        url = (
            f"{supabase_url}/rest/v1/skill_lineage"
            f"?skill_name=eq.{skill_name}&is_active=eq.true&limit=1"
        )
        req = urllib.request.Request(url, headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            records = json.loads(resp.read())

        if not records:
            print(f"[l3_analyze] No active lineage for {skill_name}", file=sys.stderr)
            return False

        record_id = records[0]["id"]
        current_runs = records[0]["total_runs"]
        current_pass = records[0]["total_pass"]
        current_fail = records[0]["total_fail"]

        patch = {
            "total_runs": current_runs + 1,
            "total_pass": current_pass + pass_count,
            "total_fail": current_fail + fail_count,
            "content_hash": content_hash
        }

        patch_url = f"{supabase_url}/rest/v1/skill_lineage?id=eq.{record_id}"
        req2 = urllib.request.Request(
            patch_url,
            data=json.dumps(patch).encode(),
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            method="PATCH"
        )
        with urllib.request.urlopen(req2, timeout=10) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        print(f"[l3_analyze] Lineage update failed: {e}", file=sys.stderr)
        return False


def get_content_hash(skill_md_path: str) -> str:
    """SHA256 of SKILL.md content."""
    content = Path(skill_md_path).read_bytes()
    return hashlib.sha256(content).hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser(description="AUTOLOOP L3 Post-Execution Analyzer")
    parser.add_argument("--skill", required=True, help="Skill name (e.g. zonewise-scraper)")
    parser.add_argument("--skill-md", required=True, help="Path to SKILL.md")
    parser.add_argument("--eval-results", required=True, help="Path to eval_runner.py output JSON")
    parser.add_argument("--run-id", required=True, help="Autoloop run ID for tracing")
    parser.add_argument("--dry-run", action="store_true", help="Print analysis JSON, skip DB write")
    parser.add_argument("--output", default=None, help="Write analysis JSON to file")
    args = parser.parse_args()

    # Load inputs
    eval_results = load_eval_results(args.eval_results)
    skill_md = load_skill_md(args.skill_md)
    content_hash = get_content_hash(args.skill_md)

    summary = eval_results.get("summary", {})
    pass_count = summary.get("passed", 0)
    fail_count = summary.get("failed", 0)
    total = summary.get("total_assertions", 25)
    pass_rate = summary.get("score", 0.0)

    # Collect per-assertion context with Levenshtein similarity
    assertions_context = []
    for test in eval_results.get("tests", []):
        for a in test.get("assertions", []):
            entry = {
                "id": a.get("assertion_id"),
                "description": a.get("description", ""),
                "passed": a.get("passed"),
                "error": a.get("error")
            }
            # Add similarity score for failed assertions
            if not a.get("passed") and a.get("error"):
                expected = a.get("description", "")
                actual = a.get("error", "")
                evo_type, sim = classify_failure(expected, actual)
                entry["similarity_score"] = round(sim, 3)
                entry["suggested_evolution"] = evo_type
            assertions_context.append(entry)

    # Env vars
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_KEY", "")

    # Load prompt template
    prompt_path = Path(__file__).parent.parent / "prompts" / "l3_analyzer.md"
    if prompt_path.exists():
        prompt_template = prompt_path.read_text()
    else:
        prompt_template = (
            "You are a skill quality analyzer. Given eval results and SKILL.md, "
            "output ONLY JSON: {task_completed, execution_note, skill_applied, evolution_suggestion}."
        )

    # Prior analyses for context
    prior_analyses = []
    if supabase_url and supabase_key and not args.dry_run:
        prior_analyses = get_prior_analyses(args.skill, supabase_url, supabase_key)

    context = {
        "skill_name": args.skill,
        "skill_md": skill_md[:3000],  # Truncate to avoid token waste
        "pass_rate": round(pass_rate, 3),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "total_assertions": total,
        "run_id": args.run_id,
        "eval_results": assertions_context[:25],
        "prior_analyses": prior_analyses
    }

    # Call LLM
    analysis = None
    analyzer_used = "gemini-flash"

    if gemini_key:
        try:
            analysis = call_gemini_flash(prompt_template, context, gemini_key)
            analyzer_used = "gemini-flash"
        except Exception as e:
            print(f"[l3_analyze] Gemini failed: {e} — trying DeepSeek", file=sys.stderr)

    if analysis is None and deepseek_key:
        try:
            analysis = call_deepseek(prompt_template, context, deepseek_key)
            analyzer_used = "deepseek-v3"
        except Exception as e:
            print(f"[l3_analyze] DeepSeek failed: {e}", file=sys.stderr)

    if analysis is None:
        # Fallback: rule-based analysis (no LLM)
        print("[l3_analyze] No LLM available — using rule-based fallback", file=sys.stderr)
        evo_suggestion = None
        if pass_rate < 0.8 and fail_count > 0:
            # Use most common Levenshtein suggestion
            types = [e.get("suggested_evolution") for e in assertions_context if e.get("suggested_evolution")]
            evo_type = max(set(types), key=types.count) if types else "fix"
            evo_suggestion = {
                "type": evo_type,
                "target_skill": args.skill,
                "direction": f"{fail_count}/{total} assertions failed — review skill instructions for failed cases"
            }
        analysis = {
            "task_completed": pass_rate >= 0.8,
            "execution_note": f"Rule-based: {pass_count}/{total} passed ({pass_rate:.0%})",
            "skill_applied": True,
            "evolution_suggestion": evo_suggestion
        }
        analyzer_used = "rule-based"

    # Build DB record
    record = {
        "skill_name": args.skill,
        "task_id": args.run_id,
        "run_id": args.run_id,
        "task_completed": analysis.get("task_completed", pass_rate >= 0.8),
        "execution_note": analysis.get("execution_note", ""),
        "skill_applied": analysis.get("skill_applied", True),
        "evolution_type": analysis.get("evolution_suggestion", {}).get("type") if analysis.get("evolution_suggestion") else None,
        "evolution_direction": analysis.get("evolution_suggestion", {}).get("direction") if analysis.get("evolution_suggestion") else None,
        "target_skill": analysis.get("evolution_suggestion", {}).get("target_skill") if analysis.get("evolution_suggestion") else None,
        "analyzed_by": analyzer_used
    }

    output = {
        "skill": args.skill,
        "run_id": args.run_id,
        "content_hash": content_hash,
        "pass_rate": round(pass_rate, 3),
        "analyzer": analyzer_used,
        "analysis": analysis,
        "db_record": record,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    if args.output:
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"[l3_analyze] Analysis written to {args.output}")

    if args.dry_run:
        print(json.dumps(output, indent=2))
        print(f"[l3_analyze] DRY RUN — skipping DB write")
        return

    # Persist to Supabase
    if supabase_url and supabase_key:
        ok = persist_to_supabase(record, supabase_url, supabase_key)
        print(f"[l3_analyze] skill_analyses insert: {'OK' if ok else 'FAILED'}")

        ok2 = update_lineage_counters(
            args.skill, args.run_id, pass_count, fail_count,
            content_hash, supabase_url, supabase_key
        )
        print(f"[l3_analyze] skill_lineage update: {'OK' if ok2 else 'FAILED'}")
    else:
        print("[l3_analyze] SUPABASE_URL/SUPABASE_KEY not set — skipping DB write")

    # Print summary
    evo = analysis.get("evolution_suggestion")
    print(f"\n[l3_analyze] {args.skill} | pass_rate={pass_rate:.0%} | "
          f"task_completed={analysis.get('task_completed')} | "
          f"evolution={evo['type'] if evo else 'none'}")

    if evo:
        print(f"[l3_analyze] Evolution({evo['type']}): {evo.get('direction', '')}")

    # Exit non-zero if evolution needed (signals autoloop to act)
    sys.exit(0 if not evo else 2)


if __name__ == "__main__":
    main()
