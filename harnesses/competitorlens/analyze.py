#!/usr/bin/env python3
"""
CompetitorLens — Stage 3: UX Pattern Analyzer
ComponentBlueprint JSON → UXPatternReport

Uses Sonnet 4.5 (free on Max plan) via CLIProxyAPI.
Falls back to DeepSeek V3.2 ($0.28/1M) if Claude unavailable.

Environment:
    CLIPROXY_URL      — CLIProxyAPI base (default: http://127.0.0.1:8317)
    DEEPSEEK_API_KEY  — Fallback to direct DeepSeek API
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

CLIPROXY_URL = os.environ.get("CLIPROXY_URL", "http://127.0.0.1:8317")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"

# Preferred model order: Claude Sonnet first (free), DeepSeek fallback (cheap)
PREFERRED_MODELS = ["claude-sonnet-4-5", "deepseek-chat"]

ANALYZE_SYSTEM_PROMPT = """You are a senior UX analyst specializing in real estate auction platforms.
Given a ComponentBlueprint JSON from a competitor's website, produce a detailed UXPatternReport.

Analyze and identify:
1. Navigation flow — how users move through the interface
2. Filter/search mechanics — how properties are filtered, sorted, queried
3. Data display patterns — calendar grid, property cards, table, map, list
4. CTA placement + copy — where calls-to-action appear and what text they use
5. Mobile approach — responsive design, stacked layouts, touch targets
6. Trust signals — badges, counters, social proof elements
7. Information architecture — what data is shown at each level (list → detail)
8. Interaction patterns — hover states, modal dialogs, inline expansion

For each pattern, rate BidDeed.AI's opportunity to improve on it (1-5, 5=major opportunity).

Output ONLY valid JSON matching this schema:
{
  "competitor": "string",
  "component_type": "string",
  "analyzed_at": "ISO timestamp",
  "summary": "2-3 sentence executive summary of key UX patterns",
  "navigation_flow": {
    "type": "string",
    "description": "string",
    "steps": ["step1", "step2"],
    "pain_points": ["identified friction points"],
    "biddeed_opportunity": 1
  },
  "filter_mechanics": {
    "filters": [
      {
        "name": "string",
        "type": "dropdown|text|date|toggle|slider",
        "position": "top|sidebar|modal",
        "default_value": "string or null",
        "ux_notes": "string"
      }
    ],
    "filter_count": 0,
    "filter_layout": "horizontal-bar|sidebar|modal|inline",
    "biddeed_opportunity": 1
  },
  "data_display": {
    "primary_pattern": "calendar-grid|property-cards|list-view|map|table",
    "secondary_patterns": [],
    "density": "high|medium|low",
    "data_fields_shown": ["field1", "field2"],
    "visual_hierarchy": "description of visual hierarchy",
    "biddeed_opportunity": 1
  },
  "cta_analysis": {
    "primary_cta": {"text": "string", "position": "string", "style": "string"},
    "secondary_ctas": [{"text": "string", "position": "string"}],
    "conversion_pattern": "description",
    "biddeed_opportunity": 1
  },
  "mobile_approach": {
    "type": "responsive|separate|unknown",
    "breakpoints": ["sm", "md", "lg"],
    "touch_targets": "adequate|inadequate|unknown",
    "notes": "string",
    "biddeed_opportunity": 1
  },
  "key_patterns": [
    {
      "name": "pattern-name-slug",
      "description": "What this pattern does and why it works",
      "adapt_for_biddeed": "How to improve this for BidDeed.AI with ML scores, lien data, etc.",
      "priority": "high|medium|low"
    }
  ],
  "biddeed_enhancements": [
    "ML probability score overlay per auction date",
    "BID/REVIEW/SKIP color coding per property",
    "ZoneWise zoning data per parcel",
    "Lien priority warning badges",
    "Max bid calculation (ARV formula) shown inline"
  ],
  "reusable_patterns_for_library": [
    {
      "pattern_name": "slug",
      "description": "string",
      "implementation_notes": "string"
    }
  ]
}

Be specific. Ground your analysis in the actual ComponentBlueprint data provided.
If a field cannot be determined, use null. Never invent data."""


def _call_llm(messages: list, prefer_model: str = None) -> dict:
    """
    Call LLM via CLIProxyAPI. Tries Claude Sonnet first, then DeepSeek.
    Returns raw API response dict.
    """
    models_to_try = [prefer_model] + PREFERRED_MODELS if prefer_model else PREFERRED_MODELS

    for model in models_to_try:
        if not model:
            continue
        result = _call_cliproxy(messages, model)
        if "error" not in result:
            return result
        print(f"[analyze] Model {model} failed: {result.get('error', 'unknown')}")

    # Final fallback: direct DeepSeek
    if DEEPSEEK_API_KEY:
        print("[analyze] Trying direct DeepSeek API...")
        return _call_deepseek_direct(messages)

    return {"error": "All LLM backends failed. Set DEEPSEEK_API_KEY or ensure CLIProxyAPI is running."}


def _call_cliproxy(messages: list, model: str) -> dict:
    """POST to CLIProxyAPI."""
    endpoint = f"{CLIPROXY_URL}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 3000,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer local",
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        return {"error": f"CLIProxy unavailable: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def _call_deepseek_direct(messages: list) -> dict:
    """Direct DeepSeek API fallback."""
    if not DEEPSEEK_API_KEY:
        return {"error": "DEEPSEEK_API_KEY not set"}
    endpoint = f"{DEEPSEEK_API_BASE}/chat/completions"
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 3000,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}", "detail": error_body}
    except Exception as e:
        return {"error": str(e)}


def analyze_blueprint(blueprint: dict) -> dict:
    """
    Analyze a ComponentBlueprint JSON → UXPatternReport.

    Args:
        blueprint: Output from extract.extract_blueprint()

    Returns:
        UXPatternReport dict or {"error": "..."}
    """
    if not blueprint:
        return {"error": "Blueprint is empty"}

    if "error" in blueprint:
        return {"error": f"Invalid blueprint: {blueprint['error']}"}

    blueprint_json = json.dumps(blueprint, indent=2)
    competitor = blueprint.get("competitor", "Unknown")
    component_type = blueprint.get("layoutType", blueprint.get("component_type", "unknown"))

    print(f"[analyze] Analyzing {competitor} {component_type} blueprint...")
    print(f"[analyze] Blueprint size: {len(blueprint_json):,} chars")

    messages = [
        {"role": "system", "content": ANALYZE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Analyze this ComponentBlueprint from {competitor} "
                f"(component type: {component_type}):\n\n{blueprint_json}"
            )
        }
    ]

    llm_response = _call_llm(messages)

    if "error" in llm_response:
        return {"error": f"LLM analysis failed: {llm_response['error']}"}

    # Parse response
    try:
        choices = llm_response.get("choices", [])
        if not choices:
            return {"error": "LLM returned no choices"}
        content = choices[0].get("message", {}).get("content", "")
        if not content:
            return {"error": "LLM returned empty content"}
        report = json.loads(content)
    except json.JSONDecodeError as e:
        return {"error": f"LLM returned invalid JSON: {e}"}

    # Enrich with metadata
    report["analyzed_at"] = datetime.now(timezone.utc).isoformat()
    if not report.get("competitor"):
        report["competitor"] = competitor
    if not report.get("component_type"):
        report["component_type"] = component_type
    report["source_blueprint_url"] = blueprint.get("url", "")

    # Log cost
    usage = llm_response.get("usage", {})
    total_tokens = usage.get("total_tokens", 0)
    model_used = llm_response.get("model", "unknown")
    cost = (total_tokens / 1_000_000) * 0.28  # DeepSeek pricing as baseline
    print(f"[analyze] OK — model={model_used}, tokens={total_tokens:,}, cost=${cost:.4f}")

    return report


def extract_patterns_for_library(report: dict) -> list:
    """
    Extract reusable patterns from a UXPatternReport for storage in ux_pattern_library.

    Returns list of pattern dicts ready for supabase_client.save_ux_pattern().
    """
    patterns = []
    competitor = report.get("competitor", "Unknown")

    for raw in report.get("reusable_patterns_for_library", []):
        if not raw.get("pattern_name"):
            continue
        patterns.append({
            "pattern_name": raw["pattern_name"],
            "source_competitor": competitor,
            "description": raw.get("description", ""),
            "implementation_notes": raw.get("implementation_notes", ""),
            "reuse_count": 0,
        })

    return patterns


def validate_report(report: dict) -> list:
    """Return list of missing required top-level fields in UXPatternReport."""
    required = [
        "competitor", "component_type", "analyzed_at", "summary",
        "navigation_flow", "filter_mechanics", "data_display",
        "cta_analysis", "key_patterns",
    ]
    return [f for f in required if f not in report or report[f] is None]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CompetitorLens UX Pattern Analyzer")
    parser.add_argument("input", help="ComponentBlueprint JSON from extract.py")
    parser.add_argument("--output", "-o", default="/tmp/cl_ux_report.json")
    parser.add_argument("--save-patterns", action="store_true",
                        help="Save extracted patterns to Supabase ux_pattern_library")
    args = parser.parse_args()

    with open(args.input) as f:
        blueprint = json.load(f)

    report = analyze_blueprint(blueprint)

    if "error" in report:
        print(f"[ERROR] {report['error']}")
        exit(1)

    # Validate
    missing = validate_report(report)
    if missing:
        print(f"[WARN] Missing fields in report: {missing}")

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nUX report saved to: {args.output}")
    print(f"Competitor:     {report.get('competitor')}")
    print(f"Component:      {report.get('component_type')}")
    print(f"Key patterns:   {len(report.get('key_patterns', []))}")
    print(f"Library patterns: {len(report.get('reusable_patterns_for_library', []))}")
    print(f"Summary: {report.get('summary', '')[:120]}...")

    if args.save_patterns:
        from supabase_client import save_ux_pattern
        patterns = extract_patterns_for_library(report)
        for p in patterns:
            result = save_ux_pattern(p)
            status = "OK" if "error" not in result else f"FAIL: {result.get('error')}"
            print(f"  [pattern] {p['pattern_name']}: {status}")
