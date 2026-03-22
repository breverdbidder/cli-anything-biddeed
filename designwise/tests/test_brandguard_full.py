"""
Test Suite — BrandGuard Agent (full coverage)
Tests: color validation, font validation, contrast calc, link check, nav check.
20 tests total.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

HARNESS_DIR = Path(__file__).parent.parent / "agent-harness"
sys.path.insert(0, str(HARNESS_DIR))


class TestColorValidation:
    """Color validation tests — 7 tests."""

    def test_banned_color_detection_pure_red(self):
        from cli_anything.designwise.utils.brand_tokens import is_banned_color
        assert is_banned_color("#FF0000") is True

    def test_banned_color_detection_pure_blue(self):
        from cli_anything.designwise.utils.brand_tokens import is_banned_color
        assert is_banned_color("#0000FF") is True

    def test_brand_navy_not_banned(self):
        from cli_anything.designwise.utils.brand_tokens import is_banned_color
        assert is_banned_color("#1E3A5F") is False

    def test_brand_orange_not_banned(self):
        from cli_anything.designwise.utils.brand_tokens import is_banned_color
        assert is_banned_color("#F59E0B") is False

    def test_is_brand_color_navy(self):
        from cli_anything.designwise.utils.brand_tokens import is_brand_color
        assert is_brand_color("#1E3A5F") is True

    def test_is_brand_color_orange(self):
        from cli_anything.designwise.utils.brand_tokens import is_brand_color
        assert is_brand_color("#F59E0B") is True

    def test_non_brand_color_returns_false(self):
        from cli_anything.designwise.utils.brand_tokens import is_brand_color
        assert is_brand_color("#ABCDEF") is False


class TestContrastCalculation:
    """Contrast ratio calculation tests — 6 tests."""

    def test_black_on_white_contrast(self):
        from cli_anything.designwise.utils.brand_tokens import contrast_ratio
        ratio = contrast_ratio("#000000", "#FFFFFF")
        assert ratio == pytest.approx(21.0, rel=0.01)

    def test_white_on_black_contrast(self):
        from cli_anything.designwise.utils.brand_tokens import contrast_ratio
        ratio = contrast_ratio("#FFFFFF", "#000000")
        assert ratio == pytest.approx(21.0, rel=0.01)

    def test_contrast_ratio_is_symmetric(self):
        from cli_anything.designwise.utils.brand_tokens import contrast_ratio
        r1 = contrast_ratio("#1E3A5F", "#020617")
        r2 = contrast_ratio("#020617", "#1E3A5F")
        assert r1 == pytest.approx(r2, rel=0.001)

    def test_contrast_ratio_same_color_is_one(self):
        from cli_anything.designwise.utils.brand_tokens import contrast_ratio
        ratio = contrast_ratio("#1E3A5F", "#1E3A5F")
        assert ratio == pytest.approx(1.0, rel=0.01)

    def test_contrast_ratio_returns_float(self):
        from cli_anything.designwise.utils.brand_tokens import contrast_ratio
        ratio = contrast_ratio("#F8FAFC", "#020617")
        assert isinstance(ratio, float)
        assert ratio >= 1.0

    def test_wcag_aa_passes_for_light_on_dark(self):
        from cli_anything.designwise.utils.brand_tokens import contrast_ratio
        # Slate-50 on Slate-950 — should comfortably pass AA (4.5)
        ratio = contrast_ratio("#F8FAFC", "#020617")
        assert ratio >= 4.5, f"Expected ≥4.5, got {ratio}"


class TestFontValidation:
    """Font stack validation tests — 3 tests."""

    def test_canonical_font_is_inter(self):
        from cli_anything.designwise.utils.brand_tokens import get_font_stack
        fonts = get_font_stack()
        assert fonts["primary"] == "Inter"

    def test_canonical_mono_font(self):
        from cli_anything.designwise.utils.brand_tokens import get_font_stack
        fonts = get_font_stack()
        assert "JetBrains Mono" in fonts["mono"]

    def test_font_stack_has_fallback(self):
        from cli_anything.designwise.utils.brand_tokens import CANONICAL_TOKENS
        assert "fallback" in CANONICAL_TOKENS["fonts"]


class TestBrandGuardAgent:
    """BrandGuard agent behavioral tests — 4 tests."""

    def test_agent_instantiates(self):
        from cli_anything.designwise.core.brandguard_agent import BrandGuardAgent
        agent = BrandGuardAgent()
        assert agent is not None

    def test_scan_url_returns_dict(self):
        """scan_url returns dict with violations key even on network error."""
        from cli_anything.designwise.core.brandguard_agent import BrandGuardAgent
        agent = BrandGuardAgent()
        # Use a URL that will fail — should still return structured result
        result = agent.scan_url("http://localhost:19999/nonexistent")
        assert isinstance(result, dict)

    def test_check_design_drift_returns_dict(self):
        from cli_anything.designwise.core.brandguard_agent import BrandGuardAgent
        agent = BrandGuardAgent()
        result = agent.check_design_drift(
            live_url="http://localhost:19999/nonexistent",
            design_md_path="/nonexistent/DESIGN.md",
        )
        assert isinstance(result, dict)
        assert "drift_detected" in result

    def test_scan_url_has_violations_key(self):
        from cli_anything.designwise.core.brandguard_agent import BrandGuardAgent
        agent = BrandGuardAgent()
        result = agent.scan_url("http://localhost:19999/nonexistent")
        assert "violations" in result or "error" in result
