"""
Test Suite — DesignWise Utils
Tests: supabase_client, brand_tokens, vercel_api.
10 tests total.
"""

import sys
from pathlib import Path

import pytest

HARNESS_DIR = Path(__file__).parent.parent / "agent-harness"
sys.path.insert(0, str(HARNESS_DIR))


class TestBrandTokens:
    """Test brand_tokens.py utility."""

    def test_imports(self):
        from cli_anything.designwise.utils.brand_tokens import CANONICAL_TOKENS
        assert CANONICAL_TOKENS is not None

    def test_canonical_colors(self):
        from cli_anything.designwise.utils.brand_tokens import get_canonical_colors
        colors = get_canonical_colors()
        assert colors["primary"] == "#1E3A5F"
        assert colors["accent"] == "#F59E0B"
        assert colors["background"] == "#020617"

    def test_contrast_ratio_returns_float(self):
        from cli_anything.designwise.utils.brand_tokens import contrast_ratio
        ratio = contrast_ratio("#FFFFFF", "#000000")
        assert isinstance(ratio, float)
        assert ratio == pytest.approx(21.0, rel=0.01)

    def test_contrast_ratio_wcag_aa_text(self):
        from cli_anything.designwise.utils.brand_tokens import contrast_ratio
        # White on black must be > 4.5
        ratio = contrast_ratio("#FFFFFF", "#000000")
        assert ratio >= 4.5

    def test_is_banned_color(self):
        from cli_anything.designwise.utils.brand_tokens import is_banned_color
        assert is_banned_color("#FF0000") is True   # Pure red = banned
        assert is_banned_color("#1E3A5F") is False  # Brand navy = not banned

    def test_is_brand_color(self):
        from cli_anything.designwise.utils.brand_tokens import is_brand_color
        assert is_brand_color("#1E3A5F") is True
        assert is_brand_color("#F59E0B") is True
        assert is_brand_color("#FF0000") is False

    def test_load_design_md_returns_dict(self):
        from cli_anything.designwise.utils.brand_tokens import load_design_md
        tokens = load_design_md(path="/nonexistent/DESIGN.md")
        # Should return canonical defaults when file not found
        assert isinstance(tokens, dict)
        assert "colors" in tokens
        assert "fonts" in tokens


class TestSupabaseClient:
    """Test supabase_client.py utility (structure, not live calls)."""

    def test_imports(self):
        from cli_anything.designwise.utils import supabase_client
        assert supabase_client is not None

    def test_tables_list(self):
        from cli_anything.designwise.utils.supabase_client import TABLES
        assert "design_tasks" in TABLES
        assert "brand_violations" in TABLES
        assert "stitch_usage" in TABLES
        assert len(TABLES) == 11

    def test_invalid_table_raises(self):
        from cli_anything.designwise.utils.supabase_client import insert
        with pytest.raises(ValueError, match="Unknown table"):
            insert("nonexistent_table_xyz", {"key": "value"})
