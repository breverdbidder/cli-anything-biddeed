"""
Test Suite — TeardownWise Agent
Issue: breverdbidder/cli-anything-biddeed#10
Tests: detection logic, HTML parsing, asset extraction, pipeline structure.
25 tests total.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

HARNESS_DIR = Path(__file__).parent.parent / "agent-harness"
sys.path.insert(0, str(HARNESS_DIR))


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="/static/main.css">
  <link href="/static/grid.css" rel="stylesheet">
  <style>
    body { display: grid; grid-template-columns: 1fr 2fr; background: #020617; }
    h1 { font-family: 'Inter', sans-serif; font-size: 24px; color: #1E3A5F; }
    .btn { background: #F59E0B; }
    .glass { backdrop-filter: blur(10px); }
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    :root { --primary: #1E3A5F; --accent: #F59E0B; }
  </style>
  <script src="/static/gsap.min.js"></script>
  <script src="/static/app.js"></script>
</head>
<body>
  <nav class="sticky top-0">Sticky Nav</nav>
  <section class="hero">Hero Section</section>
  <div class="card-grid">Cards</div>
  <div class="modal">Modal</div>
  <div class="pricing">Pricing</div>
  <div data-aos="fade-in">AOS element</div>
</body>
</html>
"""

SAMPLE_CSS = """
display: flex;
font-family: 'Inter', sans-serif;
font-size: 16px;
font-size: 2rem;
backdrop-filter: blur(8px);
"""

SAMPLE_JS = """
gsap.to('.hero', { opacity: 1, duration: 1 });
ScrollTrigger.create({ trigger: '.section' });
"""


class TestAssetExtraction:
    """Tests for CSS/JS URL extraction from HTML."""

    def test_extract_css_link_rel_first(self):
        from cli_anything.designwise.core.teardown_agent import _extract_asset_urls
        assets = _extract_asset_urls(SAMPLE_HTML, "https://example.com")
        assert any("main.css" in u for u in assets["css"])

    def test_extract_css_href_first(self):
        from cli_anything.designwise.core.teardown_agent import _extract_asset_urls
        assets = _extract_asset_urls(SAMPLE_HTML, "https://example.com")
        assert any("grid.css" in u for u in assets["css"])

    def test_extract_js_scripts(self):
        from cli_anything.designwise.core.teardown_agent import _extract_asset_urls
        assets = _extract_asset_urls(SAMPLE_HTML, "https://example.com")
        assert any("gsap.min.js" in u for u in assets["js"])
        assert any("app.js" in u for u in assets["js"])

    def test_inline_style_sentinel(self):
        from cli_anything.designwise.core.teardown_agent import _extract_asset_urls
        assets = _extract_asset_urls(SAMPLE_HTML, "https://example.com")
        assert "__inline__" in assets["css"]

    def test_relative_urls_resolved_to_absolute(self):
        from cli_anything.designwise.core.teardown_agent import _extract_asset_urls
        assets = _extract_asset_urls(SAMPLE_HTML, "https://example.com")
        for url in assets["css"] + assets["js"]:
            if url != "__inline__":
                assert url.startswith("https://"), f"URL not resolved: {url}"

    def test_caps_at_20_css(self):
        big_html = "\n".join(
            f'<link rel="stylesheet" href="/static/file{i}.css">' for i in range(30)
        )
        from cli_anything.designwise.core.teardown_agent import _extract_asset_urls
        assets = _extract_asset_urls(big_html, "https://example.com")
        assert len(assets["css"]) <= 20

    def test_caps_at_20_js(self):
        big_html = "\n".join(
            f'<script src="/static/file{i}.js"></script>' for i in range(30)
        )
        from cli_anything.designwise.core.teardown_agent import _extract_asset_urls
        assets = _extract_asset_urls(big_html, "https://example.com")
        assert len(assets["js"]) <= 20


class TestLayoutDetection:
    """Tests for CSS layout technique detection."""

    def test_detect_grid(self):
        from cli_anything.designwise.core.teardown_agent import _detect_layout
        assert _detect_layout("display: grid; grid-template-columns: 1fr 2fr;") == "css-grid"

    def test_detect_flex(self):
        from cli_anything.designwise.core.teardown_agent import _detect_layout
        assert _detect_layout("display: flex; flex-row") == "flexbox"

    def test_detect_grid_and_flex(self):
        from cli_anything.designwise.core.teardown_agent import _detect_layout
        combined = "display: grid; grid-cols-3 display: flex;"
        assert _detect_layout(combined) == "css-grid+flexbox"

    def test_detect_float(self):
        from cli_anything.designwise.core.teardown_agent import _detect_layout
        assert _detect_layout("float: left; clear: both;") == "float"

    def test_detect_unknown(self):
        from cli_anything.designwise.core.teardown_agent import _detect_layout
        assert _detect_layout("margin: 0; padding: 0;") == "unknown"

    def test_grid_in_sample_html(self):
        from cli_anything.designwise.core.teardown_agent import _detect_layout
        assert "grid" in _detect_layout(SAMPLE_HTML)


class TestAnimationDetection:
    """Tests for animation library detection."""

    def test_detect_gsap(self):
        from cli_anything.designwise.core.teardown_agent import _detect_animation_library
        assert _detect_animation_library("gsap.to('.el', { opacity: 1 })") == "gsap"

    def test_detect_gsap_scroll_trigger(self):
        from cli_anything.designwise.core.teardown_agent import _detect_animation_library
        assert _detect_animation_library("ScrollTrigger.create({})") == "gsap"

    def test_detect_css_animations(self):
        from cli_anything.designwise.core.teardown_agent import _detect_animation_library
        assert _detect_animation_library("@keyframes fadeIn { }") == "css-animations"

    def test_detect_none(self):
        from cli_anything.designwise.core.teardown_agent import _detect_animation_library
        assert _detect_animation_library("margin: 0; padding: 0;") == "none"

    def test_gsap_beats_css_animations(self):
        from cli_anything.designwise.core.teardown_agent import _detect_animation_library
        combined = "gsap.to('.el', {}); @keyframes fadeIn {}"
        assert _detect_animation_library(combined) == "gsap"


class TestEffectsDetection:
    """Tests for visual effects detection."""

    def test_detect_glassmorphism(self):
        from cli_anything.designwise.core.teardown_agent import _detect_effects
        assert "glassmorphism" in _detect_effects("backdrop-filter: blur(10px);")

    def test_detect_parallax(self):
        from cli_anything.designwise.core.teardown_agent import _detect_effects
        assert "parallax" in _detect_effects("data-depth='0.5' parallax")

    def test_detect_scroll_animations(self):
        from cli_anything.designwise.core.teardown_agent import _detect_effects
        assert "scroll-animations" in _detect_effects('data-aos="fade-in"')

    def test_detect_sticky_nav(self):
        from cli_anything.designwise.core.teardown_agent import _detect_effects
        assert "sticky-nav" in _detect_effects("position: sticky; top: 0;")

    def test_no_false_positives(self):
        from cli_anything.designwise.core.teardown_agent import _detect_effects
        effects = _detect_effects("margin: 0; padding: 0; color: red;")
        assert effects == []

    def test_sample_html_glassmorphism(self):
        from cli_anything.designwise.core.teardown_agent import _detect_effects
        assert "glassmorphism" in _detect_effects(SAMPLE_HTML)


class TestComponentDetection:
    """Tests for component pattern detection."""

    def test_detect_hero(self):
        from cli_anything.designwise.core.teardown_agent import _detect_components
        assert "hero-section" in _detect_components('<section class="hero">Hero</section>')

    def test_detect_card_grid(self):
        from cli_anything.designwise.core.teardown_agent import _detect_components
        assert "card-grid" in _detect_components('<div class="card-grid">Cards</div>')

    def test_detect_modal(self):
        from cli_anything.designwise.core.teardown_agent import _detect_components
        assert "modal" in _detect_components('<div class="modal">Modal</div>')

    def test_detect_pricing(self):
        from cli_anything.designwise.core.teardown_agent import _detect_components
        assert "pricing-table" in _detect_components('<section class="pricing">Pricing</section>')

    def test_sample_html_detects_multiple_components(self):
        from cli_anything.designwise.core.teardown_agent import _detect_components
        comps = _detect_components(SAMPLE_HTML)
        assert "hero-section" in comps
        assert "card-grid" in comps


class TestOutputSchema:
    """Tests that output contains required fields per acceptance criteria."""

    @pytest.mark.asyncio
    async def test_analyze_returns_required_fields(self):
        """Result must include layout_technique, animation_library, color_system, typography, effects, component_patterns."""
        from cli_anything.designwise.core.teardown_agent import TeardownWiseAgent

        mock_response = MagicMock()
        mock_response.text = SAMPLE_HTML
        mock_response.status_code = 200

        agent = TeardownWiseAgent()
        agent._persist = AsyncMock(return_value={"id": "test-uuid"})

        with patch(
            "cli_anything.designwise.core.teardown_agent.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            result = await agent.analyze("https://example.com")

        assert "techniques" in result
        t = result["techniques"]
        assert "layout_technique" in t
        assert "animation_library" in t
        assert "color_system" in t
        assert "typography" in t
        assert "components" in result
        c = result["components"]
        assert "effects" in c
        assert "component_patterns" in c

    @pytest.mark.asyncio
    async def test_analyze_connect_error_returns_error_dict(self):
        """ConnectError returns {"error": ..., "url": ...} not exception."""
        import httpx as _httpx
        from cli_anything.designwise.core.teardown_agent import TeardownWiseAgent

        agent = TeardownWiseAgent()

        with patch(
            "cli_anything.designwise.core.teardown_agent.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=_httpx.ConnectError("refused"))
            result = await agent.analyze("https://unreachable.invalid")

        assert "error" in result
        assert result["url"] == "https://unreachable.invalid"

    def test_html_hash_is_16_chars(self):
        from cli_anything.designwise.core.teardown_agent import _html_hash
        h = _html_hash("<html>test</html>")
        assert len(h) == 16

    def test_supabase_table_registered(self):
        from cli_anything.designwise.utils.supabase_client import TABLES
        assert "teardown_bundles" in TABLES
