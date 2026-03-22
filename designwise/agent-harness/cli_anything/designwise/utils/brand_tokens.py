"""
brand_tokens.py — DesignWise brand design token utilities.
Provides color validation, font checks, contrast calculations for ZoneWise.AI brand compliance.
House brand (5 canonical colors): Navy #1E3A5F, Orange #F59E0B, bg #020617, hover #D97706, dark navy #162D4A
Font: Inter

Design policy:
  - CANONICAL_BRAND_COLORS: The 5 exact hex values that define the brand.
  - Tailwind utility classes (bg-slate-*, text-gray-*, etc.) are ALLOWED — they compile
    to CSS variables, not hardcoded hex, and do not require explicit approval.
  - Only hardcoded hex values that are not in CANONICAL_BRAND_COLORS are flagged.
"""

import math
import re
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

# ── 5 Canonical brand colors (S3.0 — tightened from 10+ to 5) ─────────────────

CANONICAL_BRAND_COLORS: Dict[str, str] = {
    "navy":       "#1E3A5F",  # Primary navy — headings, navbar, buttons
    "orange":     "#F59E0B",  # Accent orange — CTAs, highlights
    "bg":         "#020617",  # Background (slate-950) — all page backgrounds
    "hover":      "#D97706",  # Hover state (orange-500) — interactive elements
    "dark_navy":  "#162D4A",  # Dark navy (navy-700) — surfaces, cards
}

# Canonical tokens for backwards compat + BrandGuard full validation
CANONICAL_TOKENS: Dict[str, Any] = {
    "colors": {
        "primary":    "#1E3A5F",
        "accent":     "#F59E0B",
        "background": "#020617",
        "hover":      "#D97706",
        "dark_navy":  "#162D4A",
    },
    "banned_colors": [
        "#FF0000",  # pure red
        "#00FF00",  # pure green
        "#0000FF",  # pure blue
        "#FF00FF",  # magenta
        "#FFFF00",  # yellow
        "#00FFFF",  # cyan
        "#FFA500",  # html orange (use #F59E0B instead)
        "#800080",  # purple
        "#008000",  # html green
        "#FF6600",  # orange-red
        "#FFFFFF",  # pure white bg (use #020617)
        "#000000",  # pure black (use #020617)
    ],
    # Tailwind utility prefixes that are always allowed (compiled to CSS vars)
    "tailwind_allowed_prefixes": [
        "bg-", "text-", "border-", "ring-", "fill-", "stroke-",
        "from-", "to-", "via-", "shadow-", "outline-",
    ],
    "fonts": {
        "heading": "Inter",
        "body": "Inter",
        "mono": "JetBrains Mono",
    },
    "font_size_min": 11,
    "spacing": {
        "base": "4px",
        "sm": "8px",
        "md": "16px",
        "lg": "24px",
        "xl": "32px",
        "2xl": "48px",
    },
    "contrast_min": {
        "body": 4.5,
        "large": 3.0,
    },
}

# Normalized sets for fast lookup
_BRAND_COLOR_VALS = {v.lstrip("#").lower() for v in CANONICAL_BRAND_COLORS.values()}
_BANNED_COLOR_VALS = {c.lstrip("#").lower() for c in CANONICAL_TOKENS["banned_colors"]}
_ALLOWED_FONTS = {"inter", "jetbrains mono", "jetbrains+mono"}

# Tailwind scale classes never flagged as violations (they use CSS variables at build time)
_TAILWIND_SCALE_NAMES = {
    "slate", "gray", "zinc", "neutral", "stone", "red", "orange", "amber",
    "yellow", "lime", "green", "emerald", "teal", "cyan", "sky", "blue",
    "indigo", "violet", "purple", "fuchsia", "pink", "rose", "white", "black",
    "transparent", "current",
}


def is_tailwind_utility(class_name: str) -> bool:
    """
    Return True if class_name looks like a Tailwind color utility.
    e.g. bg-slate-950, text-gray-400, border-amber-500
    Tailwind utilities are ALWAYS allowed — they compile to CSS vars, not raw hex.
    """
    prefixes = CANONICAL_TOKENS["tailwind_allowed_prefixes"]
    name_lower = class_name.lower().strip()
    for prefix in prefixes:
        if name_lower.startswith(prefix):
            remainder = name_lower[len(prefix):]
            # remainder is like "slate-950" or "gray-400" or "white"
            parts = remainder.split("-")
            if parts[0] in _TAILWIND_SCALE_NAMES:
                return True
    return False


# ── Public API ─────────────────────────────────────────────────────────────────

def get_canonical_colors() -> Dict[str, str]:
    """Return the 5 canonical brand colors."""
    return dict(CANONICAL_BRAND_COLORS)


def load_design_md(path: str = "DESIGN.md") -> Dict[str, Any]:
    """
    Parse DESIGN.md and return design tokens dict.
    Returns canonical defaults when file not found.
    """
    p = Path(path)
    if not p.exists():
        return dict(CANONICAL_TOKENS)

    try:
        content = p.read_text(encoding="utf-8")
        tokens = dict(CANONICAL_TOKENS)
        # Extract hex color overrides from DESIGN.md
        hex_pattern = re.compile(r"#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b")
        found_colors = hex_pattern.findall(content)
        if found_colors:
            # Keep canonical structure but note file was parsed
            tokens["_source"] = str(p)
        return tokens
    except Exception:
        return dict(CANONICAL_TOKENS)


def parse_design_md(path: str = "DESIGN.md") -> Dict[str, Any]:
    """Alias for load_design_md for backwards compat."""
    return load_design_md(path=path)


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Convert hex color string to (R, G, B) tuple. Handles #RGB and #RRGGBB."""
    h = hex_str.lstrip("#").strip()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"Invalid hex color: {hex_str}")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return r, g, b


def relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """Calculate relative luminance (WCAG 2.1 formula)."""
    def linearize(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def contrast_ratio(hex1: str, hex2: str) -> float:
    """
    Calculate WCAG contrast ratio between two hex colors.
    Returns float ratio (1.0 to 21.0).
    """
    lum1 = relative_luminance(hex_to_rgb(hex1))
    lum2 = relative_luminance(hex_to_rgb(hex2))
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


def check_color(hex_value: str, tokens: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
    """
    Check if hex_value is valid per brand tokens.
    Returns (valid: bool, violation_detail: str | None).
    """
    if tokens is None:
        tokens = CANONICAL_TOKENS
    try:
        normalized = hex_value.lstrip("#").lower()
        # Check if banned
        banned = {c.lstrip("#").lower() for c in tokens.get("banned_colors", [])}
        if normalized in banned:
            return False, f"Banned color: {hex_value}"
        return True, None
    except Exception as e:
        return False, str(e)


def check_font(font_family: str, tokens: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
    """
    Check if font_family is allowed per brand tokens.
    Returns (valid: bool, violation_detail: str | None).
    """
    if tokens is None:
        tokens = CANONICAL_TOKENS
    allowed = set()
    for v in tokens.get("fonts", {}).values():
        allowed.add(v.lower())
    ff_lower = font_family.lower().strip().strip("'\"")
    if ff_lower in allowed or any(ff_lower.startswith(a) for a in allowed):
        return True, None
    return False, f"Non-brand font: {font_family}. Allowed: {sorted(allowed)}"


def check_contrast(fg_hex: str, bg_hex: str, min_ratio: float = 4.5) -> Tuple[bool, float]:
    """
    Check if fg/bg pair meets minimum contrast ratio.
    Returns (passes: bool, actual_ratio: float).
    """
    ratio = contrast_ratio(fg_hex, bg_hex)
    return ratio >= min_ratio, round(ratio, 3)


def is_banned_color(hex_value: str) -> bool:
    """Return True if hex_value is in the banned color list."""
    normalized = hex_value.lstrip("#").lower()
    return normalized in _BANNED_COLOR_VALS


def is_brand_color(hex_value: str) -> bool:
    """Return True if hex_value is one of the canonical brand colors."""
    normalized = hex_value.lstrip("#").lower()
    return normalized in _BRAND_COLOR_VALS
