"""
TeardownWise Agent — Site Teardown Analyzer
DesignWise Squad | Agent 14
Version: 1.0.0 (UPGRADE 1 per DESIGNWISE-V3-UPGRADES.md)

Pipeline:
  web_fetch(url) → extract HTML → parse CSS/JS → fetch each FULL
  → detect layout, animation, color system, typography, effects, components
  → store structured bundle in teardown_bundles Supabase table

Issue: breverdbidder/cli-anything-biddeed#10
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

_FETCH_TIMEOUT = 30
_MAX_ASSET_BYTES = 500_000   # 500 KB cap per CSS/JS file


def _supabase_headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

_ANIMATION_LIBS: dict[str, list[str]] = {
    "gsap":          ["gsap", "TweenMax", "TweenLite", "ScrollTrigger", "gsap.min.js"],
    "framer-motion": ["framer-motion", "motion.div", "AnimatePresence", "useAnimation"],
    "anime-js":      ["anime.min.js", "anime(", "animejs"],
    "lottie":        ["lottie-web", "lottie.min.js", "lottie_svg", "lottie_canvas"],
    "aos":           ["aos.min.js", 'data-aos=', "AOS.init"],
    "swiper":        ["swiper.min.js", "new Swiper", "Swiper("],
    "three-js":      ["three.min.js", "THREE.", "WebGLRenderer"],
    "css-animations": ["@keyframes", "animation:", "transition:"],
}

_EFFECTS: dict[str, list[str]] = {
    "glassmorphism":       ["backdrop-filter", "backdrop-blur", "bg-opacity", "glass"],
    "parallax":            ["parallax", "data-depth", "data-speed", "ScrollTrigger"],
    "scroll-animations":   ["data-aos", "IntersectionObserver", "scrollY", "scroll-behavior"],
    "gradient-mesh":       ["conic-gradient", "radial-gradient", "mesh-gradient"],
    "neumorphism":         ["neumorphism", "box-shadow.*inset.*box-shadow"],
    "particle-effects":    ["particles.js", "tsparticles", "particlesJS"],
    "blur-overlay":        ["blur(", "filter: blur"],
    "sticky-nav":          ["position: sticky", "position:sticky", "sticky top-0"],
}

_COMPONENT_PATTERNS: dict[str, list[str]] = {
    "hero-section":        ["hero", "<section.*hero", "landing-hero", "hero-banner"],
    "card-grid":           ["card-grid", "grid.*card", "cards-container"],
    "pricing-table":       ["pricing", "price-card", "pricing-tier"],
    "testimonials":        ["testimonial", "review-card", "customer-quote"],
    "sticky-nav":          ["sticky.*nav", "fixed.*header", "navbar.*sticky"],
    "modal":               ["modal", "dialog", "lightbox", "overlay"],
    "accordion":           ["accordion", "collapse", "faq-item", "expandable"],
    "tabs":                ["tab-panel", "tablist", "tab-content", "nav-tabs"],
    "infinite-scroll":     ["infinite-scroll", "load-more", "pagination"],
    "toast-notifications": ["toast", "notification", "snackbar", "alert-banner"],
}


def _html_hash(html: str) -> str:
    return hashlib.md5(html.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Asset extraction
# ---------------------------------------------------------------------------

def _extract_asset_urls(html: str, base_url: str) -> dict[str, list[str]]:
    """Extract CSS and JS URLs from HTML, resolved against base_url."""
    css_urls: list[str] = []
    js_urls: list[str] = []

    # CSS: <link rel="stylesheet" href="...">
    for href in re.findall(
        r'<link[^>]+rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\']',
        html, re.IGNORECASE
    ):
        css_urls.append(urljoin(base_url, href))

    # Also: <link href="..." rel="stylesheet">
    for href in re.findall(
        r'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']stylesheet["\']',
        html, re.IGNORECASE
    ):
        url = urljoin(base_url, href)
        if url not in css_urls:
            css_urls.append(url)

    # Inline <style> blocks — use a sentinel URL
    inline_styles = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE)
    if inline_styles:
        css_urls.append("__inline__")

    # JS: <script src="...">
    for src in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE):
        js_urls.append(urljoin(base_url, src))

    return {"css": css_urls[:20], "js": js_urls[:20]}  # cap at 20 each


async def _fetch_asset(client: httpx.AsyncClient, url: str) -> str:
    """Fetch a CSS/JS URL and return text, capped at _MAX_ASSET_BYTES."""
    try:
        resp = await client.get(url, timeout=_FETCH_TIMEOUT)
        content = resp.text[:_MAX_ASSET_BYTES]
        return content
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def _detect_layout(combined: str) -> str:
    """Detect primary layout technique from combined CSS/JS/HTML."""
    has_grid = bool(re.search(r"display\s*:\s*grid|grid-template|grid-cols", combined, re.IGNORECASE))
    has_flex = bool(re.search(r"display\s*:\s*flex|flexbox|flex-row|flex-col", combined, re.IGNORECASE))
    if has_grid and has_flex:
        return "css-grid+flexbox"
    if has_grid:
        return "css-grid"
    if has_flex:
        return "flexbox"
    if re.search(r"float\s*:\s*(left|right)", combined, re.IGNORECASE):
        return "float"
    return "unknown"


def _detect_animation_library(combined: str) -> str:
    """Return first matched animation library, or 'css-animations' if @keyframes found."""
    for lib, patterns in _ANIMATION_LIBS.items():
        if lib == "css-animations":
            continue
        for p in patterns:
            if p in combined:
                return lib
    if "@keyframes" in combined or "animation:" in combined:
        return "css-animations"
    return "none"


def _detect_color_system(html: str) -> dict[str, Any]:
    """Extract CSS custom properties and dominant hex colors."""
    css_vars: dict[str, str] = {}
    for name, value in re.findall(r'--([\w-]+)\s*:\s*(#[0-9A-Fa-f]{6})', html):
        css_vars[f"--{name}"] = value.upper()

    hex_colors = list({
        f"#{c.upper()}"
        for c in re.findall(r'#([0-9A-Fa-f]{6})\b', html)
    })[:20]

    return {
        "css_variables": css_vars,
        "hex_colors": hex_colors,
        "has_design_tokens": len(css_vars) > 0,
    }


def _detect_typography(combined: str) -> dict[str, Any]:
    """Extract font families and size range."""
    fonts = list({
        f.strip().strip("'\"")
        for f in re.findall(r"font-family\s*:\s*([^;\"'<>{}]+)", combined, re.IGNORECASE)
    })[:10]

    sizes_px: list[float] = []
    for value, unit in re.findall(r'font-size\s*:\s*(\d+(?:\.\d+)?)(px|rem|em)', combined, re.IGNORECASE):
        if unit == "px":
            sizes_px.append(float(value))
        elif unit == "rem":
            sizes_px.append(float(value) * 16)
        elif unit == "em":
            sizes_px.append(float(value) * 16)

    return {
        "font_families": fonts,
        "font_size_range_px": {
            "min": min(sizes_px) if sizes_px else None,
            "max": max(sizes_px) if sizes_px else None,
        },
        "uses_variable_fonts": bool(re.search(r"font-variation-settings|wght|ital", combined)),
    }


def _match_any(combined: str, patterns: list[str]) -> bool:
    """Return True if any pattern matches combined (literal substring, case-insensitive)."""
    lower = combined.lower()
    return any(p.lower() in lower for p in patterns)


def _detect_effects(combined: str) -> list[str]:
    """Return list of detected visual effects."""
    detected: list[str] = []
    for effect, patterns in _EFFECTS.items():
        if _match_any(combined, patterns):
            detected.append(effect)
    return detected


def _detect_components(combined: str) -> list[str]:
    """Return list of detected component patterns."""
    detected: list[str] = []
    for component, patterns in _COMPONENT_PATTERNS.items():
        if _match_any(combined, patterns):
            detected.append(component)
    return detected


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

class TeardownWiseAgent:
    """
    Site teardown analyzer.
    Fetches a URL, extracts HTML + all linked CSS/JS (FULL, not summarized),
    detects layout, animation, color system, typography, effects, components,
    and stores the structured bundle in Supabase teardown_bundles.
    """

    async def analyze(self, url: str) -> dict[str, Any]:
        """
        Full teardown pipeline:
          1. Fetch URL → HTML
          2. Extract CSS/JS asset URLs
          3. Fetch each asset FULL
          4. Run all detectors
          5. Persist to Supabase
          6. Return structured result
        """
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "TeardownWise/1.0 (BidDeed.AI)"},
        ) as client:
            # Step 1: Fetch HTML
            try:
                resp = await client.get(url)
                html = resp.text
            except httpx.ConnectError as exc:
                return {"error": f"Cannot connect to {url}: {exc}", "url": url}
            except httpx.TimeoutException:
                return {"error": f"Timeout fetching {url}", "url": url}

            # Step 2: Extract asset URLs
            assets = _extract_asset_urls(html, url)

            # Step 3: Fetch CSS/JS FULL
            css_texts: list[str] = []
            js_texts: list[str] = []

            inline_styles = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE)
            css_texts.extend(inline_styles)

            for css_url in assets["css"]:
                if css_url == "__inline__":
                    continue
                css_texts.append(await _fetch_asset(client, css_url))

            for js_url in assets["js"]:
                js_texts.append(await _fetch_asset(client, js_url))

        # Step 4: Combine all content for analysis
        combined = html + "\n".join(css_texts) + "\n".join(js_texts)

        techniques = {
            "layout_technique":   _detect_layout(combined),
            "animation_library":  _detect_animation_library(combined),
            "color_system":       _detect_color_system(html + "\n".join(css_texts)),
            "typography":         _detect_typography(combined),
        }

        components = {
            "effects":            _detect_effects(combined),
            "component_patterns": _detect_components(combined),
        }

        bundle = {
            "url":         url,
            "html_hash":   _html_hash(html),
            "techniques":  techniques,
            "components":  components,
            "assets_fetched": {
                "css_count": len([u for u in assets["css"] if u != "__inline__"]),
                "js_count":  len(assets["js"]),
                "inline_style_blocks": len(inline_styles),
            },
            "analyzed_at": datetime.utcnow().isoformat(),
        }

        # Step 5: Persist to Supabase
        db_result = await self._persist(bundle)
        bundle["db_id"] = db_result.get("id")

        return bundle

    async def _persist(self, bundle: dict[str, Any]) -> dict[str, Any]:
        """Insert bundle into teardown_bundles table."""
        payload = {
            "url":        bundle["url"],
            "html_hash":  bundle["html_hash"],
            "techniques": bundle["techniques"],
            "components": bundle["components"],
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{SUPABASE_URL}/rest/v1/teardown_bundles",
                    headers=_supabase_headers(),
                    json=payload,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    return data[0] if isinstance(data, list) and data else {"status": "inserted"}
                return {"error": f"Supabase {resp.status_code}: {resp.text[:200]}"}
        except Exception as exc:
            return {"error": str(exc)}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="TeardownWise — site technique analyzer")
    parser.add_argument("url", nargs="?", help="URL to analyze")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    if not args.url:
        parser.print_help()
        return

    async def run() -> None:
        agent = TeardownWiseAgent()
        result = await agent.analyze(args.url)

        if "error" in result:
            print(f"[TeardownWise] ERROR: {result['error']}")
            return

        if args.json:
            print(json.dumps(result, indent=2, default=str))
            return

        t = result.get("techniques", {})
        c = result.get("components", {})
        print(f"\n[TeardownWise] {result['url']}")
        print(f"  Layout:     {t.get('layout_technique', 'unknown')}")
        print(f"  Animation:  {t.get('animation_library', 'none')}")
        print(f"  Effects:    {', '.join(c.get('effects', [])) or 'none'}")
        print(f"  Components: {', '.join(c.get('component_patterns', [])) or 'none'}")
        fonts = t.get('typography', {}).get('font_families', [])
        print(f"  Fonts:      {', '.join(fonts[:3]) or 'unknown'}")
        colors = t.get('color_system', {}).get('hex_colors', [])
        print(f"  Colors:     {', '.join(colors[:5]) or 'none'}")
        if result.get("db_id"):
            print(f"  DB id:      {result['db_id']}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
