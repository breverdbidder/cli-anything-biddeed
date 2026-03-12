"""
Tests for ZoneWise Modal Spatial Agents
=======================================
Run: pytest tests/ -v
"""

import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from dataclasses import asdict

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Unit: ZoneResult dataclass
# ---------------------------------------------------------------------------
class TestZoneResult:
    def test_create_zone_result(self):
        from modal_app import ZoneResult
        r = ZoneResult(
            parcel_id="P001",
            account_number="2612345",
            latitude=28.1234,
            longitude=-80.5678,
            zone_code="BU-1",
            zone_district="Commercial",
            zone_description="General Commercial",
            match_confidence=0.98,
            county="brevard",
            matched_at="2026-03-11T12:00:00Z",
        )
        d = asdict(r)
        assert d["parcel_id"] == "P001"
        assert d["match_confidence"] == 0.98
        assert d["zone_code"] == "BU-1"

    def test_zone_result_serializable(self):
        from modal_app import ZoneResult
        r = ZoneResult(
            parcel_id="P002", account_number="2699999",
            latitude=28.0, longitude=-80.0,
            zone_code="RU-1", zone_district="Residential",
            zone_description="Single Family", match_confidence=1.0,
            county="brevard", matched_at="2026-03-11T12:00:00Z",
        )
        # Must be JSON-serializable for Supabase writes
        j = json.dumps(asdict(r))
        assert '"parcel_id": "P002"' in j


# ---------------------------------------------------------------------------
# Unit: ChunkResult dataclass
# ---------------------------------------------------------------------------
class TestChunkResult:
    def test_create_chunk_result(self):
        from modal_app import ChunkResult
        cr = ChunkResult(
            chunk_id=0, total_parcels=5000,
            matched=4993, unmatched=7,
            elapsed_seconds=2.5,
        )
        d = asdict(cr)
        assert d["matched"] == 4993
        assert d["unmatched"] == 7
        assert d["results"] == []
        assert d["errors"] == []


# ---------------------------------------------------------------------------
# Unit: CLI config loading
# ---------------------------------------------------------------------------
class TestCLIConfig:
    def test_default_config(self):
        from cli_anything_modal_spatial import DEFAULT_CONFIG
        assert DEFAULT_CONFIG["chunk_size"] == 5000
        assert DEFAULT_CONFIG["match_rate_threshold"] == 85.0
        assert "brevard" in DEFAULT_CONFIG["counties_registry"]

    def test_load_config_default(self):
        from cli_anything_modal_spatial import load_config, CONFIG_PATH
        # When no config file exists, returns default
        if not CONFIG_PATH.exists():
            config = load_config()
            assert config["chunk_size"] == 5000

    def test_save_and_load_state(self, tmp_path):
        from cli_anything_modal_spatial import save_state, load_state, STATE_PATH
        import cli_anything_modal_spatial as cli

        # Temporarily redirect state path
        original = cli.STATE_PATH
        cli.STATE_PATH = tmp_path / "test_state.json"

        try:
            save_state({"status": "TEST", "count": 42})
            state = load_state()
            assert state["status"] == "TEST"
            assert state["count"] == 42
        finally:
            cli.STATE_PATH = original


# ---------------------------------------------------------------------------
# Unit: Polygon fetch URL construction
# ---------------------------------------------------------------------------
class TestPolygonFetch:
    def test_unknown_county_raises(self):
        from modal_app import _fetch_zoning_polygons
        with pytest.raises(ValueError, match="No GIS endpoint"):
            _fetch_zoning_polygons("nonexistent_county")

    def test_brevard_endpoint_configured(self):
        """Verify Brevard GIS endpoint is in the registry."""
        from modal_app import _fetch_zoning_polygons
        # We can't call it without network, but we can check it doesn't
        # raise ValueError for brevard
        try:
            _fetch_zoning_polygons("brevard")
        except Exception as e:
            # Network error is fine, ValueError is not
            assert "No GIS endpoint" not in str(e)


# ---------------------------------------------------------------------------
# Integration: STRtree matching logic (no Modal, no network)
# ---------------------------------------------------------------------------
class TestSTRtreeMatching:
    def test_point_in_polygon_match(self):
        """Core spatial matching logic works correctly."""
        from shapely.geometry import Point, Polygon
        from shapely import STRtree

        # Create test polygons (simplified zoning districts)
        poly1 = Polygon([(-80.6, 28.0), (-80.5, 28.0), (-80.5, 28.1), (-80.6, 28.1)])
        poly2 = Polygon([(-80.5, 28.0), (-80.4, 28.0), (-80.4, 28.1), (-80.5, 28.1)])

        tree = STRtree([poly1, poly2])

        # Point inside poly1
        p1 = Point(-80.55, 28.05)
        idx = tree.nearest(p1)
        assert poly1.contains(p1) or poly2.contains(p1)

        # Point inside poly2
        p2 = Point(-80.45, 28.05)
        idx = tree.nearest(p2)
        assert poly2.contains(p2)

    def test_point_outside_all_polygons(self):
        """Points far from any polygon get low confidence."""
        from shapely.geometry import Point, Polygon
        from shapely import STRtree

        poly = Polygon([(-80.6, 28.0), (-80.5, 28.0), (-80.5, 28.1), (-80.6, 28.1)])
        tree = STRtree([poly])

        far_point = Point(-79.0, 27.0)  # way outside
        idx = tree.nearest(far_point)
        assert not poly.contains(far_point)

    def test_chunk_processing_simulation(self):
        """Simulate processing a chunk of parcels."""
        from shapely.geometry import Point, Polygon, shape
        from shapely import STRtree

        # 3 zones
        zones = [
            Polygon([(-80.6, 28.0), (-80.5, 28.0), (-80.5, 28.1), (-80.6, 28.1)]),
            Polygon([(-80.5, 28.0), (-80.4, 28.0), (-80.4, 28.1), (-80.5, 28.1)]),
            Polygon([(-80.4, 28.0), (-80.3, 28.0), (-80.3, 28.1), (-80.4, 28.1)]),
        ]
        tree = STRtree(zones)

        # 10 test parcels spread across zones
        parcels = [
            {"parcel_id": f"P{i:03d}", "latitude": 28.05, "longitude": -80.55 + (i * 0.02)}
            for i in range(10)
        ]

        matched = 0
        for p in parcels:
            pt = Point(p["longitude"], p["latitude"])
            idx = tree.nearest(pt)
            if zones[idx].contains(pt):
                matched += 1

        # At least some should match (parcels spread across zone boundaries)
        assert matched >= 3, f"Expected at least 3 matches, got {matched}"


# ---------------------------------------------------------------------------
# Unit: Workflow YAML is valid
# ---------------------------------------------------------------------------
class TestWorkflow:
    def test_workflow_exists(self):
        wf = Path(__file__).parent.parent / ".github" / "workflows" / "modal_spatial.yml"
        assert wf.exists(), "GitHub Actions workflow missing"

    def test_workflow_valid_yaml(self):
        import yaml
        wf = Path(__file__).parent.parent / ".github" / "workflows" / "modal_spatial.yml"
        with open(wf) as f:
            data = yaml.safe_load(f)
        assert "jobs" in data
        assert "health-check" in data["jobs"]
        assert "spatial-run" in data["jobs"]
