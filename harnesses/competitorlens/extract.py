#!/usr/bin/env python3
"""
CompetitorLens — Stage 2: DeepSeek V3.2 Layout Extractor
HTML → ComponentBlueprint JSON

Uses DeepSeek V3.2 via CLIProxyAPI (127.0.0.1:8317) or direct DeepSeek API.
Cost: ~$0.28/1M tokens — ultra-cheap for HTML parsing.

Environment:
    DEEPSEEK_API_KEY  — Direct DeepSeek API key
    CLIPROXY_URL      — CLIProxyAPI base (default: http://127.0.0.1:8317)
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

# CLIProxyAPI wraps DeepSeek/Gemini — prefer local proxy
CLIPROXY_URL = os.environ.get("CLIPROXY_URL", "http://127.0.0.1:8317")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"

EXTRACT_SYSTEM_PROMPT = """You are a UI/UX layout analyzer. Given raw HTML from a competitor real estate website,
extract the structural layout into a ComponentBlueprint JSON object.

Focus on:
1. Page sections (header, navigation, search/filter bar, main content, sidebar, footer)
2. Navigation items and structure
3. Filter/search controls (dropdowns, inputs, toggles, date pickers)
4. Data display patterns (calendar grid, property cards, list view, map view, table)
5. CTA placement (buttons, links, call-to-actions and their position)
6. Color scheme (extract hex codes or CSS classes observed)
7. Layout type (calendar, grid, list, map, hybrid)
8. Mobile approach (responsive breakpoints, separate mobile, stacked)

Output ONLY valid JSON matching this schema exactly:
{
  "competitor": "PropertyOnion|Foreclosure.com|Auction.com|Unknown",
  "component_type": "calendar|search|listing|map|hybrid",
  "sections": [
    {
      "name": "string",
      "type": "navigation|hero|filter|content|sidebar|footer",
      "elements": ["element descriptions"],
      "position": "top|left|right|bottom|center"
    }
  ],
  "navigation": {
    "type": "top-bar|sidebar|hamburger|tabs",
    "items": ["item names"],
    "hasAuth": true|false
  },
  "filters": [
    {
      "name": "string",
      "type": "dropdown|text-input|date-picker|toggle|range-slider|checkbox",
      "options": ["option values if visible"],
      "position": "top|sidebar|modal|inline"
    }
  ],
  "dataDisplayPatterns": ["calendar-grid", "property-cards", "list-view", "map-pins", "table"],
  "ctaPlacement": {
    "primary": "description of primary CTA location and text",
    "secondary": "description of secondary CTAs"
  },
  "colorScheme": {
    "primary": "#hex or description",
    "secondary": "#hex or description",
    "background": "#hex or description",
    "accent": "#hex or description"
  },
  "layoutType": "calendar|grid|list|map|hybrid",
  "mobileApproach": "responsive|separate|unknown",
  "keyUXPatterns": ["descriptive list of notable UX patterns"],
  "dataFields": ["property fields visible: address, price, date, beds, baths, etc."],
  "interactiveFeatures": ["calendar navigation", "view toggle", "county selector", etc.]
}

If a field cannot be determined from the HTML, use null or empty array. Never invent data."""


def _call_cliproxy(html_snippet: str, url: str) -> dict:
    """Call DeepSeek V3.2 via CLIProxyAPI (local proxy)."""
    endpoint = f"{CLIPROXY_URL}/v1/chat/completions"
    payload = {
        "model": "deepseek-chat",  # DeepSeek V3.2 via proxy
        "messages": [
            {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this competitor page HTML from {url}:\n\n{html_snippet}"}
        ],
        "temperature": 0.1,  # Low temp for deterministic JSON
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer local",  # CLIProxyAPI doesn't require real key
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        return {"error": f"CLIProxy unavailable: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def _call_deepseek_direct(html_snippet: str, url: str) -> dict:
    """Fallback: call DeepSeek API directly."""
    if not DEEPSEEK_API_KEY:
        return {"error": "DEEPSEEK_API_KEY not set and CLIProxyAPI unavailable"}

    endpoint = f"{DEEPSEEK_API_BASE}/chat/completions"
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this competitor page HTML from {url}:\n\n{html_snippet}"}
        ],
        "temperature": 0.1,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}", "detail": error_body}
    except Exception as e:
        return {"error": str(e)}


def _truncate_html_for_llm(html: str, markdown: str, max_chars: int = 30000) -> str:
    """
    Prepare HTML for LLM analysis.
    Prefer markdown (cleaner signal) but fall back to HTML.
    Truncate to stay within token budget.
    """
    # Prefer markdown — it's cleaner and cheaper on tokens
    content = markdown if len(markdown) > 500 else html

    if len(content) <= max_chars:
        return content

    # Smart truncation: take head + tail to catch nav + footer patterns
    sep = "\n\n[... content truncated ...]\n\n"
    budget = max_chars - len(sep)
    head = content[:int(budget * 0.7)]
    tail = content[-(int(budget * 0.3)):]
    return head + sep + tail


def extract_blueprint(crawl_result: dict) -> dict:
    """
    Extract ComponentBlueprint JSON from a crawl result.

    Args:
        crawl_result: Output from crawl.crawl_url()

    Returns:
        ComponentBlueprint dict or {"error": "..."}
    """
    url = crawl_result.get("url", "unknown")
    html = crawl_result.get("html", "")
    markdown = crawl_result.get("markdown", "")

    if not html and not markdown:
        return {"error": "No HTML or markdown content in crawl result"}

    html_snippet = _truncate_html_for_llm(html, markdown)
    print(f"[extract] Sending {len(html_snippet):,} chars to DeepSeek V3.2")

    # Try CLIProxyAPI first (free / local)
    print(f"[extract] Trying CLIProxyAPI at {CLIPROXY_URL}...")
    llm_response = _call_cliproxy(html_snippet, url)

    if "error" in llm_response:
        print(f"[extract] CLIProxy failed: {llm_response['error']}")
        print(f"[extract] Falling back to DeepSeek direct API...")
        llm_response = _call_deepseek_direct(html_snippet, url)

    if "error" in llm_response:
        return {"error": f"LLM extraction failed: {llm_response['error']}"}

    # Parse the LLM JSON response
    try:
        choices = llm_response.get("choices", [])
        if not choices:
            return {"error": "LLM returned no choices", "raw": llm_response}

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            return {"error": "LLM returned empty content"}

        # Parse JSON from LLM response
        blueprint = json.loads(content)

    except json.JSONDecodeError as e:
        return {
            "error": f"LLM returned invalid JSON: {e}",
            "raw_content": content if 'content' in dir() else str(llm_response)
        }

    # Enrich blueprint with crawl metadata
    blueprint["url"] = url
    blueprint["screenshot"] = crawl_result.get("screenshot", "")
    blueprint["crawled_at"] = crawl_result.get("crawled_at", datetime.now(timezone.utc).isoformat())
    blueprint["extractedAt"] = datetime.now(timezone.utc).isoformat()

    # Auto-detect competitor from URL if not set
    if not blueprint.get("competitor") or blueprint["competitor"] == "Unknown":
        blueprint["competitor"] = _detect_competitor(url)

    # Validate required fields
    missing = _validate_blueprint(blueprint)
    if missing:
        print(f"[extract] WARN: Missing fields in blueprint: {missing}")

    usage = llm_response.get("usage", {})
    tokens_used = usage.get("total_tokens", 0)
    cost_usd = (tokens_used / 1_000_000) * 0.28
    print(f"[extract] OK — blueprint extracted. Tokens: {tokens_used:,}, Cost: ${cost_usd:.4f}")

    return blueprint


def _detect_competitor(url: str) -> str:
    url_lower = url.lower()
    if "propertyonion" in url_lower:
        return "PropertyOnion"
    if "foreclosure.com" in url_lower:
        return "Foreclosure.com"
    if "auction.com" in url_lower:
        return "Auction.com"
    return "Unknown"


def _validate_blueprint(blueprint: dict) -> list[str]:
    """Return list of missing required fields."""
    required = ["sections", "navigation", "filters", "dataDisplayPatterns",
                "ctaPlacement", "layoutType"]
    return [f for f in required if f not in blueprint or blueprint[f] is None]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CompetitorLens Layout Extractor")
    parser.add_argument("input", help="Input raw crawl JSON from crawl.py")
    parser.add_argument("--output", "-o", default="/tmp/cl_blueprint.json")
    args = parser.parse_args()

    with open(args.input) as f:
        raw = json.load(f)

    blueprint = extract_blueprint(raw)

    if "error" in blueprint:
        print(f"[ERROR] {blueprint['error']}")
        exit(1)

    with open(args.output, "w") as f:
        json.dump(blueprint, f, indent=2)

    print(f"\nBlueprint saved to: {args.output}")
    print(f"Competitor:    {blueprint.get('competitor')}")
    print(f"Layout type:   {blueprint.get('layoutType')}")
    print(f"Sections:      {len(blueprint.get('sections', []))}")
    print(f"Filters:       {len(blueprint.get('filters', []))}")
    print(f"Data patterns: {blueprint.get('dataDisplayPatterns', [])}")
