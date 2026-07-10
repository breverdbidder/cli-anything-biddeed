#!/usr/bin/env python3
"""
CompetitorLens — Stage 5: BrandGuard Integration
Validates generated JSX against BidDeed.AI house brand rules.

Programmatic checks (no LLM needed — deterministic rules).

House Brand:
    Navy:       #1E3A5F
    Orange:     #F59E0B
    Background: #020617 (slate-950)
    Font:       Inter
    Framework:  Tailwind CSS only

Returns PASS/BLOCK with detailed violation list.
Stores result in competitor_analyses.brand_guard_status.
"""

import json
import os
import re
from pathlib import Path

# ─── BRAND PALETTE ────────────────────────────────────────────────────────────

BRAND_NAVY = "#1E3A5F"
BRAND_ORANGE = "#F59E0B"
BRAND_BG = "#020617"
BRAND_FONT = "Inter"

# Approved colors (hex + Tailwind equivalents)
APPROVED_COLORS = {
    # Core brand
    "#1e3a5f", "#1E3A5F",   # Navy
    "#f59e0b", "#F59E0B",   # Orange
    "#020617",               # slate-950 bg

    # Slate scale (approved neutrals)
    "#0f172a",               # slate-900
    "#1e293b",               # slate-800
    "#334155",               # slate-700
    "#475569",               # slate-600
    "#64748b",               # slate-500
    "#94a3b8",               # slate-400
    "#cbd5e1",               # slate-300
    "#e2e8f0",               # slate-200
    "#f1f5f9",               # slate-100
    "#f8fafc",               # slate-50

    # Status colors (for BID/REVIEW/SKIP badges)
    "#10b981",               # emerald-500
    "#34d399",               # emerald-400
    "#d97706",               # amber-600
    "#fbbf24",               # amber-400
    "#ef4444",               # red-500
    "#f87171",               # red-400

    # Transparent/opacity variants are allowed
}

# Forbidden color patterns (off-brand)
FORBIDDEN_PATTERNS = [
    # Purple (biggest violation)
    (r'#[67][0-9a-fA-F][02][0-9a-fA-F][89a-fA-F][0-9a-fA-F]', "purple-like hex"),
    (r'#7[Cc]3[Aa][Ee][Dd]', "purple-600"),
    (r'#8[Bb]5[Cc][Ff]6', "purple-500"),
    (r'#9333[Ee][Aa]', "purple-600"),
    (r'#6[Dd]28[Dd]9', "violet-700"),
    (r'purple', "purple color keyword"),
    (r'violet', "violet color keyword"),
    (r'indigo', "indigo color keyword (use navy instead)"),

    # Bootstrap/generic blues (not our navy)
    (r'#007[Bb][Ff][Ff]', "Bootstrap blue"),
    (r'#0[Dd]6[Ee][Ff][Dd]', "Bootstrap primary"),

    # White backgrounds on the page level
    (r'bg-white(?!\s*/)', "white background (use bg-\\[#020617\\] or bg-slate-950)"),
    (r"style=\{?\{[^}]*background[^}]*#(?:fff|ffffff|FFF|FFFFFF)[^}]*\}", "inline white background"),

    # Tailwind blue as primary brand color
    (r'bg-blue-[56789]00', "Tailwind blue (not brand navy)"),
    (r'text-blue-[56789]00', "Tailwind blue text (not brand navy)"),
]

# Required brand elements
REQUIRED_PATTERNS = [
    (r'#1[Ee]3[Aa]5[Ff]|bg-\[#1E3A5F\]|\[#1e3a5f\]', "Navy (#1E3A5F)"),
    (r'#[Ff]59[Ee]0[Bb]|bg-\[#F59E0B\]|\[#f59e0b\]|amber-400|amber-300', "Orange (#F59E0B)"),
    (r'#020617|bg-slate-950|bg-\[#020617\]', "Background (#020617 / slate-950)"),
    (r'Inter|font-\[Inter\]|inter', "Inter font"),
    (r'export default', "default export"),
    (r'useEffect|useState', "React hooks (Supabase data binding)"),
    (r'NEXT_PUBLIC_SUPABASE_URL|supabase', "Supabase integration"),
]

# Optional but scored (each adds to brand score)
BONUS_PATTERNS = [
    (r'bid_score|bidScore', "ML bid score field"),
    (r'BID|REVIEW|SKIP', "BID/REVIEW/SKIP badge system"),
    (r'lien|Lien', "Lien data integration"),
    (r'aria-label|role=', "Accessibility attributes"),
    (r'max_bid|maxBid|max bid', "Max bid calculation"),
    (r'focus:ring-\[#F59E0B\]|focus:ring-amber', "Orange focus ring"),
]


def validate_jsx(jsx_content: str) -> dict:
    """
    Run BrandGuard checks on JSX content.

    Returns:
        {
            "status": "PASS" | "BLOCK",
            "score": 0-100,
            "violations": [...],
            "warnings": [...],
            "checks_passed": [...],
            "bonus_features": [...],
            "summary": str,
        }
    """
    if not jsx_content or not jsx_content.strip():
        return {
            "status": "BLOCK",
            "score": 0,
            "violations": ["JSX content is empty"],
            "warnings": [],
            "checks_passed": [],
            "bonus_features": [],
            "summary": "BLOCK — empty content",
        }

    violations = []
    warnings = []
    checks_passed = []
    bonus_features = []

    # ── Check 1: Forbidden patterns ──────────────────────────────────────────
    for pattern, description in FORBIDDEN_PATTERNS:
        matches = re.findall(pattern, jsx_content, re.IGNORECASE)
        if matches:
            unique = list(set(matches))[:3]  # Show up to 3 examples
            violations.append({
                "rule": f"FORBIDDEN_COLOR",
                "description": f"Off-brand color: {description}",
                "examples": unique,
                "severity": "critical",
            })

    # ── Check 2: Required patterns ────────────────────────────────────────────
    for pattern, description in REQUIRED_PATTERNS:
        if re.search(pattern, jsx_content, re.IGNORECASE):
            checks_passed.append(description)
        else:
            violations.append({
                "rule": "MISSING_REQUIRED",
                "description": f"Missing required brand element: {description}",
                "examples": [],
                "severity": "critical",
            })

    # ── Check 3: Font check ───────────────────────────────────────────────────
    has_font_import = (
        "Inter" in jsx_content or
        "next/font/google" in jsx_content or
        "inter" in jsx_content.lower()
    )
    if not has_font_import:
        warnings.append({
            "rule": "FONT_NOT_IMPORTED",
            "description": "Inter font not explicitly imported (ensure it's in layout.tsx or tailwind config)",
            "severity": "warning",
        })

    # ── Check 4: Background check ─────────────────────────────────────────────
    has_brand_bg = bool(re.search(r'#020617|bg-slate-950|bg-\[#020617\]', jsx_content))
    if not has_brand_bg:
        violations.append({
            "rule": "MISSING_BRAND_BG",
            "description": "Background color #020617 (slate-950) not found — page will not match brand",
            "examples": [],
            "severity": "critical",
        })
    else:
        checks_passed.append("Brand background #020617")

    # ── Check 5: CTA orange check ─────────────────────────────────────────────
    has_orange_cta = bool(re.search(r'#[Ff]59[Ee]0[Bb]|bg-\[#F59E0B\]|bg-amber-400', jsx_content))
    if has_orange_cta:
        checks_passed.append("Orange CTA color (#F59E0B)")
    else:
        warnings.append({
            "rule": "NO_ORANGE_CTA",
            "description": "No orange (#F59E0B) CTA buttons found — CTAs should use brand orange",
            "severity": "warning",
        })

    # ── Check 6: No inline style for off-brand colors ─────────────────────────
    inline_colors = re.findall(
        r'style=\{?\{[^}]*(?:color|background)[^}]*#(?!1[Ee]3[Aa]5[Ff]|[Ff]59[Ee]0[Bb]|020617)[0-9a-fA-F]{3,6}[^}]*\}',
        jsx_content
    )
    if inline_colors:
        warnings.append({
            "rule": "INLINE_OFF_BRAND_STYLE",
            "description": f"Inline styles with potentially off-brand colors ({len(inline_colors)} instances) — prefer Tailwind classes",
            "severity": "warning",
        })

    # ── Check 7: Bonus features ───────────────────────────────────────────────
    for pattern, description in BONUS_PATTERNS:
        if re.search(pattern, jsx_content, re.IGNORECASE):
            bonus_features.append(description)

    # ── Scoring ───────────────────────────────────────────────────────────────
    critical_violations = [v for v in violations if v.get("severity") == "critical"]
    total_required = len(REQUIRED_PATTERNS) + 1  # +1 for bg check
    passed_required = len([c for c in checks_passed if c != "Brand background #020617"])
    passed_required += (1 if has_brand_bg else 0)

    base_score = int((passed_required / total_required) * 80)
    bonus_score = min(20, len(bonus_features) * 4)  # 4 pts per bonus feature, max 20
    penalty = len(critical_violations) * 15  # -15 per critical violation

    score = max(0, min(100, base_score + bonus_score - penalty))

    # PASS requires: no critical violations AND score >= 70
    status = "PASS" if (len(critical_violations) == 0 and score >= 70) else "BLOCK"

    summary = (
        f"{status} — Score: {score}/100. "
        f"Critical violations: {len(critical_violations)}. "
        f"Required checks passed: {passed_required}/{total_required}. "
        f"Bonus features: {len(bonus_features)}."
    )

    return {
        "status": status,
        "score": score,
        "violations": violations,
        "warnings": warnings,
        "checks_passed": checks_passed,
        "bonus_features": bonus_features,
        "summary": summary,
        "critical_count": len(critical_violations),
        "warning_count": len(warnings),
    }


def validate_file(jsx_path: str) -> dict:
    """Validate a JSX file by path."""
    path = Path(jsx_path)
    if not path.exists():
        return {
            "status": "BLOCK",
            "score": 0,
            "violations": [{"rule": "FILE_NOT_FOUND", "description": f"File not found: {jsx_path}", "severity": "critical"}],
            "warnings": [],
            "checks_passed": [],
            "bonus_features": [],
            "summary": f"BLOCK — file not found: {jsx_path}",
        }

    content = path.read_text(encoding="utf-8")
    result = validate_jsx(content)
    result["file_path"] = str(jsx_path)
    return result


def format_report(result: dict, verbose: bool = False) -> str:
    """Format validation result for terminal output."""
    lines = []
    status_icon = "✅" if result["status"] == "PASS" else "🚫"
    lines.append(f"\n{status_icon} BrandGuard: {result['summary']}")
    lines.append(f"   Score: {result['score']}/100")

    if result.get("violations"):
        lines.append(f"\n🚨 Violations ({len(result['violations'])}):")
        for v in result["violations"]:
            lines.append(f"   [{v.get('severity','?').upper()}] {v['description']}")
            if verbose and v.get("examples"):
                lines.append(f"          Examples: {v['examples']}")

    if result.get("warnings"):
        lines.append(f"\n⚠️  Warnings ({len(result['warnings'])}):")
        for w in result["warnings"]:
            lines.append(f"   {w['description']}")

    if result.get("checks_passed"):
        lines.append(f"\n✓ Required checks passed ({len(result['checks_passed'])}):")
        for c in result["checks_passed"]:
            lines.append(f"   ✓ {c}")

    if result.get("bonus_features"):
        lines.append(f"\n⭐ Bonus features ({len(result['bonus_features'])}):")
        for b in result["bonus_features"]:
            lines.append(f"   ⭐ {b}")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CompetitorLens BrandGuard Validator")
    parser.add_argument("input", help="JSX file to validate")
    parser.add_argument("--output", "-o", help="Save validation result JSON to this path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show violation examples")
    parser.add_argument("--analysis-id", help="Supabase competitor_analyses.id to update")
    args = parser.parse_args()

    result = validate_file(args.input)

    print(format_report(result, verbose=args.verbose))

    # Update Supabase if analysis ID provided
    if args.analysis_id:
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            from supabase_client import update_analysis
            update_result = update_analysis(args.analysis_id, {
                "brand_guard_status": result["status"],
                "brand_guard_violations": result["violations"],
            })
            if "error" not in update_result:
                print(f"\n[Supabase] Updated analysis {args.analysis_id} → brand_guard_status={result['status']}")
            else:
                print(f"\n[Supabase] Update failed: {update_result.get('error')}")
        except Exception as e:
            print(f"\n[Supabase] Update skipped: {e}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nValidation result saved to: {args.output}")

    # Exit 1 if BLOCK (for CI)
    if result["status"] == "BLOCK":
        exit(1)
