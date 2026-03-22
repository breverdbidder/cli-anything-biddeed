#!/usr/bin/env python3
"""
CompetitorLens — Stage 4: JSX Generator
UXPatternReport + house brand rules → Branded .jsx component

Uses Sonnet 4.5 (free on Max plan) via CLIProxyAPI.
Falls back to DeepSeek V3.2 ($0.28/1M) if Claude unavailable.

HOUSE BRAND (MANDATORY — enforced by BrandGuard):
    Navy:       #1E3A5F  (primary)
    Orange:     #F59E0B  (accent/CTA)
    Background: #020617  (slate-950)
    Font:       Inter
    Framework:  Tailwind CSS utility classes only

Environment:
    CLIPROXY_URL     — CLIProxyAPI base (default: http://127.0.0.1:8317)
    DEEPSEEK_API_KEY — Fallback to direct DeepSeek API
"""

import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

CLIPROXY_URL = os.environ.get("CLIPROXY_URL", "http://127.0.0.1:8317")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"

OUTPUT_DIR = Path(__file__).parent / "output"
COMPONENTS_DIR = Path(__file__).parent.parent.parent / "components" / "competitor-lens"

PREFERRED_MODELS = ["claude-sonnet-4-5", "deepseek-chat"]

HOUSE_BRAND_RULES = """
BIDDEED.AI HOUSE BRAND — MANDATORY RULES (enforced by BrandGuard):

Colors (use exact hex values or Tailwind equivalents):
  Primary Navy:   #1E3A5F  → bg-[#1E3A5F] / text-[#1E3A5F] / border-[#1E3A5F]
  Orange Accent:  #F59E0B  → bg-[#F59E0B] / text-[#F59E0B] / border-[#F59E0B] / bg-amber-400
  Background:     #020617  → bg-[#020617] / bg-slate-950
  Surface:        #0f172a  → bg-slate-900 (cards, panels)
  Text Primary:   #f8fafc  → text-slate-50
  Text Secondary: #94a3b8  → text-slate-400
  Border:         #1e293b  → border-slate-800

Typography:
  Font: Inter (import: "import { Inter } from 'next/font/google'" or "@import url Google Fonts")
  Scale: text-xs / text-sm / text-base / text-lg / text-xl / text-2xl (Tailwind)

CTA Buttons (ALWAYS orange):
  Primary: bg-[#F59E0B] text-[#020617] font-semibold hover:bg-amber-300 px-4 py-2 rounded-lg
  Secondary: border border-[#1E3A5F] text-slate-50 hover:bg-[#1E3A5F] px-4 py-2 rounded-lg

Cards/Panels:
  bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg

Status Badges (BidDeed.AI scoring):
  BID:    bg-emerald-500/20 text-emerald-400 border-emerald-500/30
  REVIEW: bg-amber-500/20 text-amber-400 border-amber-500/30
  SKIP:   bg-red-500/20 text-red-400 border-red-500/30

FORBIDDEN:
  - Purple gradients of any kind
  - Off-brand blues (Bootstrap blue, Tailwind blue-500 as primary)
  - White backgrounds (#fff, bg-white) as page background
  - Any inline style={{ color: '#purple' }} or similar off-brand colors
"""

GENERATE_SYSTEM_PROMPT = f"""You are a senior React/Tailwind developer building for BidDeed.AI, a foreclosure auction intelligence platform.

Given a UXPatternReport from a competitor analysis, generate a complete, production-ready React JSX component.

{HOUSE_BRAND_RULES}

COMPONENT REQUIREMENTS:
1. Default export named component (e.g., AuctionCalendar, PropertySearchGrid)
2. Include realistic Supabase data hooks:
   - useEffect + fetch() calls to Supabase REST API
   - Use env var: process.env.NEXT_PUBLIC_SUPABASE_URL and process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
   - For calendar: fetch from 'auctions_free' view with date range filter
   - For search: fetch from 'auctions_pro' view with county/type/price filters
3. Loading state (spinner with navy/orange brand colors)
4. Error state (displayed in brand colors)
5. Empty state (helpful message + CTA)
6. BidDeed.AI enhancements OVER competitor:
   - ML probability score (0-100) shown per property/date (use mock field: bid_score)
   - BID/REVIEW/SKIP badge based on bid_score (>=70=BID, 40-69=REVIEW, <40=SKIP)
   - Lien warning badge when applicable
   - Max bid hint: show "(Est. max bid: $XXX,XXX)" when arv and repair_cost available
7. Responsive (mobile-first): sm: md: lg: breakpoints
8. Accessible: proper aria-labels, role attributes, focus rings (focus:ring-[#F59E0B])

SUPABASE QUERY PATTERNS:
```javascript
// Fetch auctions by date range (calendar view)
const response = await fetch(
  `${{process.env.NEXT_PUBLIC_SUPABASE_URL}}/rest/v1/auctions_free?sale_date=gte.${{startDate}}&sale_date=lte.${{endDate}}&select=*&order=sale_date`,
  {{
    headers: {{
      'apikey': process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
      'Authorization': `Bearer ${{process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY}}`,
    }}
  }}
);

// Fetch with filters (search/grid view)
const params = new URLSearchParams({{
  county: `eq.${{selectedCounty}}`,
  sale_type: `eq.${{selectedType}}`,
  select: '*',
  order: 'sale_date',
}});
const response = await fetch(
  `${{process.env.NEXT_PUBLIC_SUPABASE_URL}}/rest/v1/auctions_free?${{params}}`,
  {{ headers: {{ apikey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY, ... }} }}
);
```

OUTPUT FORMAT:
- Return ONLY the JSX file content (no markdown, no explanation, no ```jsx fences)
- First line must be an import statement
- Must be a complete, runnable React component
- Include all imports at the top
- PropTypes or TypeScript types as JSDoc comments (not .d.ts)"""


def _call_llm(messages: list) -> dict:
    """Try Claude Sonnet → DeepSeek fallback."""
    for model in PREFERRED_MODELS:
        result = _call_cliproxy(messages, model)
        if "error" not in result:
            return result
        print(f"[generate] Model {model} failed: {result.get('error', 'unknown')}")

    if DEEPSEEK_API_KEY:
        print("[generate] Trying direct DeepSeek API...")
        return _call_deepseek_direct(messages)

    return {"error": "All LLM backends failed"}


def _call_cliproxy(messages: list, model: str) -> dict:
    endpoint = f"{CLIPROXY_URL}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 4000,
        # No json_object format — JSX is plain text
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer local",
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        return {"error": f"CLIProxy unavailable: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def _call_deepseek_direct(messages: list) -> dict:
    if not DEEPSEEK_API_KEY:
        return {"error": "DEEPSEEK_API_KEY not set"}
    endpoint = f"{DEEPSEEK_API_BASE}/chat/completions"
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 4000,
    }
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}", "detail": error_body}
    except Exception as e:
        return {"error": str(e)}


def _component_name_from_report(report: dict) -> str:
    """Derive PascalCase component name from UXPatternReport."""
    comp_type = report.get("component_type", "Component")
    type_map = {
        "calendar": "AuctionCalendar",
        "search": "PropertySearchGrid",
        "listing": "PropertyListing",
        "map": "PropertyMap",
        "hybrid": "AuctionDashboard",
        "unknown": "CompetitorComponent",
    }
    return type_map.get(comp_type.lower(), "BidDeedComponent")


def generate_jsx(report: dict, component_name: str = None) -> dict:
    """
    Generate a BidDeed.AI branded JSX component from a UXPatternReport.

    Args:
        report: Output from analyze.analyze_blueprint()
        component_name: Override component name (optional)

    Returns:
        {"jsx": str, "component_name": str, "file_name": str}
        or {"error": str}
    """
    if not report:
        return {"error": "UXPatternReport is empty"}
    if "error" in report:
        return {"error": f"Invalid report: {report['error']}"}

    name = component_name or _component_name_from_report(report)
    competitor = report.get("competitor", "Unknown")
    component_type = report.get("component_type", "unknown")

    print(f"[generate] Generating {name}.jsx from {competitor} {component_type} analysis...")

    # Build a focused summary for JSX generation prompt
    report_summary = {
        "competitor": competitor,
        "component_type": component_type,
        "summary": report.get("summary", ""),
        "data_display": report.get("data_display", {}),
        "filter_mechanics": report.get("filter_mechanics", {}),
        "key_patterns": report.get("key_patterns", [])[:5],  # Top 5
        "biddeed_enhancements": report.get("biddeed_enhancements", []),
        "cta_analysis": report.get("cta_analysis", {}),
    }

    messages = [
        {"role": "system", "content": GENERATE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Generate a React JSX component named '{name}' for BidDeed.AI.\n\n"
                f"Competitor pattern analysis:\n{json.dumps(report_summary, indent=2)}\n\n"
                f"Component type: {component_type}\n"
                f"Competitor being adapted: {competitor}\n\n"
                f"Generate the complete {name}.jsx file with all house brand rules applied."
            )
        }
    ]

    llm_response = _call_llm(messages)

    if "error" in llm_response:
        return {"error": f"LLM generation failed: {llm_response['error']}"}

    # Extract JSX content
    try:
        choices = llm_response.get("choices", [])
        if not choices:
            return {"error": "LLM returned no choices"}
        jsx_content = choices[0].get("message", {}).get("content", "")
        if not jsx_content:
            return {"error": "LLM returned empty content"}
    except Exception as e:
        return {"error": f"Response parsing failed: {e}"}

    # Strip markdown fences if present
    jsx_content = _strip_markdown_fences(jsx_content)

    # Validate it looks like JSX
    validation = _validate_jsx_structure(jsx_content)
    if not validation["valid"]:
        return {
            "error": f"Generated content is not valid JSX: {validation['issues']}",
            "raw_content": jsx_content[:500],
        }

    usage = llm_response.get("usage", {})
    total_tokens = usage.get("total_tokens", 0)
    model_used = llm_response.get("model", "unknown")
    cost = (total_tokens / 1_000_000) * 0.28
    print(f"[generate] OK — model={model_used}, tokens={total_tokens:,}, cost=${cost:.4f}")
    print(f"[generate] JSX: {len(jsx_content):,} chars")

    file_name = f"{name}.jsx"
    return {
        "jsx": jsx_content,
        "component_name": name,
        "file_name": file_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_used": model_used,
        "tokens": total_tokens,
    }


def _strip_markdown_fences(content: str) -> str:
    """Remove ```jsx ... ``` or ``` ... ``` wrappers if present."""
    # Remove opening fence
    content = re.sub(r'^```(?:jsx|tsx|javascript|js)?\n', '', content.strip())
    # Remove closing fence
    content = re.sub(r'\n```$', '', content.strip())
    return content.strip()


def _validate_jsx_structure(content: str) -> dict:
    """Basic structural validation of generated JSX."""
    issues = []

    if not content.strip():
        issues.append("content is empty")
        return {"valid": False, "issues": issues}

    # Must have imports
    if not re.search(r'^import\s+', content, re.MULTILINE):
        issues.append("no import statements found")

    # Must have a default export
    if "export default" not in content:
        issues.append("no 'export default' found")

    # Must have JSX return
    if "return (" not in content and "return(" not in content:
        issues.append("no return statement found")

    # Warn if off-brand colors detected (for logging, not blocking)
    off_brand = re.findall(r'#(?:7C3AED|8B5CF6|9333EA|6D28D9)', content, re.IGNORECASE)
    if off_brand:
        issues.append(f"WARNING: off-brand purple colors detected: {off_brand}")

    return {
        "valid": len([i for i in issues if not i.startswith("WARNING")]) == 0,
        "issues": issues,
    }


def save_jsx(jsx_result: dict, output_dir: Path = None) -> str:
    """
    Save generated JSX to disk.

    Returns absolute file path.
    """
    if "error" in jsx_result:
        raise ValueError(f"Cannot save invalid JSX result: {jsx_result['error']}")

    # Save to harness output dir
    harness_out = OUTPUT_DIR
    harness_out.mkdir(parents=True, exist_ok=True)

    # Also save to components/competitor-lens/
    comp_out = COMPONENTS_DIR
    comp_out.mkdir(parents=True, exist_ok=True)

    file_name = jsx_result["file_name"]
    jsx_content = jsx_result["jsx"]

    harness_path = harness_out / file_name
    harness_path.write_text(jsx_content, encoding="utf-8")

    comp_path = comp_out / file_name
    comp_path.write_text(jsx_content, encoding="utf-8")

    print(f"[generate] Saved: {harness_path}")
    print(f"[generate] Saved: {comp_path}")

    return str(harness_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CompetitorLens JSX Generator")
    parser.add_argument("input", help="UXPatternReport JSON from analyze.py")
    parser.add_argument("--output", "-o", help="Output .jsx path (default: auto-named in output/)")
    parser.add_argument("--name", help="Override component name (default: auto-detected)")
    args = parser.parse_args()

    with open(args.input) as f:
        report = json.load(f)

    result = generate_jsx(report, component_name=args.name)

    if "error" in result:
        print(f"[ERROR] {result['error']}")
        if "raw_content" in result:
            print(f"        Raw (first 200 chars): {result['raw_content'][:200]}")
        exit(1)

    if args.output:
        Path(args.output).write_text(result["jsx"], encoding="utf-8")
        print(f"\nJSX saved to: {args.output}")
    else:
        saved_path = save_jsx(result)
        print(f"\nJSX saved to: {saved_path}")

    print(f"Component:  {result['component_name']}")
    print(f"File:       {result['file_name']}")
    print(f"Generated:  {result['generated_at']}")
    print(f"Tokens:     {result.get('tokens', 'N/A')}")
