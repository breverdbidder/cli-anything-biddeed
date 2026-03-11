"""Unit tests for Spatial Conquest CLI core modules."""

import json
import pytest
from unittest.mock import patch, MagicMock

# ── Discovery tests ───────────────────────────────────────────

from cli_anything.spatial.core.discovery import (
    get_endpoint, list_known_counties, validate_point_in_florida,
    KNOWN_ENDPOINTS, FLORIDA_BBOX,
)


class TestDiscovery:
    def test_get_brevard_endpoint(self):
        ep = get_endpoint("brevard")
        assert ep is not None
        assert "zoning" in ep
        assert "parcels" in ep

    def test_get_unknown_county(self):
        assert get_endpoint("fake_county") is None

    def test_case_insensitive(self):
        assert get_endpoint("BREVARD") is not None
        assert get_endpoint("Brevard") is not None

    def test_list_known_counties(self):
        counties = list_known_counties()
        assert len(counties) >= 1
        assert any(c["county"] == "brevard" for c in counties)

    def test_validate_point_florida(self):
        assert validate_point_in_florida(28.5, -80.7) is True  # Melbourne
        assert validate_point_in_florida(25.7, -80.2) is True  # Miami

    def test_validate_point_outside_florida(self):
        assert validate_point_in_florida(40.7, -74.0) is False  # NYC
        assert validate_point_in_florida(0.0, 0.0) is False

    def test_florida_bbox_valid(self):
        assert FLORIDA_BBOX["lat_min"] < FLORIDA_BBOX["lat_max"]
        assert FLORIDA_BBOX["lon_min"] < FLORIDA_BBOX["lon_max"]


# ── Conquest engine tests ─────────────────────────────────────

from cli_anything.spatial.core.conquest import (
    ConquestResult, build_spatial_index, spatial_join, SAFEGUARD_PCT,
)


class TestConquestResult:
    def test_default_result(self):
        r = ConquestResult(county="test")
        assert r.county == "test"
        assert r.parcels_matched == 0
        assert r.safeguard_met is False

    def test_to_dict(self):
        r = ConquestResult(county="brevard", parcels_matched=100, coverage_pct=95.5, safeguard_met=True)
        d = r.to_dict()
        assert d["county"] == "brevard"
        assert d["coverage_pct"] == 95.5
        assert d["safeguard_met"] is True

    def test_safeguard_threshold(self):
        assert SAFEGUARD_PCT == 85


class TestBuildSpatialIndex:
    def test_build_from_features(self):
        features = [
            {
                "attributes": {"ZONING": "RS-1"},
                "geometry": {"rings": [[[-80.6, 28.0], [-80.5, 28.0], [-80.5, 28.1], [-80.6, 28.1], [-80.6, 28.0]]]}
            },
            {
                "attributes": {"ZONING": "CG"},
                "geometry": {"rings": [[[-80.4, 28.0], [-80.3, 28.0], [-80.3, 28.1], [-80.4, 28.1], [-80.4, 28.0]]]}
            },
        ]
        tree, geometries, lookup = build_spatial_index(features)
        assert len(geometries) == 2
        assert lookup[0] == "RS-1"
        assert lookup[1] == "CG"

    def test_build_empty(self):
        tree, geometries, lookup = build_spatial_index([])
        assert len(geometries) == 0

    def test_build_skips_invalid(self):
        features = [
            {"attributes": {"ZONING": "RS-1"}, "geometry": {"rings": []}},  # No rings
            {"attributes": {"ZONING": ""}, "geometry": {"rings": [[[-80, 28], [-80, 29], [-79, 29], [-80, 28]]]}},  # Empty zone
        ]
        tree, geometries, lookup = build_spatial_index(features)
        assert len(geometries) == 0  # Both should be skipped


class TestSpatialJoin:
    def test_point_in_polygon(self):
        features = [
            {
                "attributes": {"ZONING": "RS-1"},
                "geometry": {"rings": [[[-80.7, 28.0], [-80.5, 28.0], [-80.5, 28.2], [-80.7, 28.2], [-80.7, 28.0]]]}
            },
        ]
        tree, geometries, lookup = build_spatial_index(features)
        parcels = [{"parcel_id": "P001", "lon": -80.6, "lat": 28.1}]
        results = spatial_join(tree, geometries, lookup, parcels)
        assert len(results) == 1
        assert results[0]["zone_code"] == "RS-1"
        assert results[0]["parcel_id"] == "P001"

    def test_point_outside_polygon(self):
        features = [
            {
                "attributes": {"ZONING": "RS-1"},
                "geometry": {"rings": [[[-80.7, 28.0], [-80.5, 28.0], [-80.5, 28.2], [-80.7, 28.2], [-80.7, 28.0]]]}
            },
        ]
        tree, geometries, lookup = build_spatial_index(features)
        parcels = [{"parcel_id": "P002", "lon": -79.0, "lat": 25.0}]  # Miami, outside polygon
        results = spatial_join(tree, geometries, lookup, parcels)
        assert len(results) == 0

    def test_multiple_parcels_multiple_zones(self):
        features = [
            {
                "attributes": {"ZONING": "RS-1"},
                "geometry": {"rings": [[[-80.7, 28.0], [-80.6, 28.0], [-80.6, 28.1], [-80.7, 28.1], [-80.7, 28.0]]]}
            },
            {
                "attributes": {"ZONING": "CG"},
                "geometry": {"rings": [[[-80.5, 28.0], [-80.4, 28.0], [-80.4, 28.1], [-80.5, 28.1], [-80.5, 28.0]]]}
            },
        ]
        tree, geometries, lookup = build_spatial_index(features)
        parcels = [
            {"parcel_id": "P001", "lon": -80.65, "lat": 28.05},  # In RS-1
            {"parcel_id": "P002", "lon": -80.45, "lat": 28.05},  # In CG
            {"parcel_id": "P003", "lon": -79.0, "lat": 25.0},    # Outside both
        ]
        results = spatial_join(tree, geometries, lookup, parcels)
        assert len(results) == 2
        zones = {r["parcel_id"]: r["zone_code"] for r in results}
        assert zones["P001"] == "RS-1"
        assert zones["P002"] == "CG"

    def test_empty_parcels(self):
        features = [
            {
                "attributes": {"ZONING": "RS-1"},
                "geometry": {"rings": [[[-80.7, 28.0], [-80.5, 28.0], [-80.5, 28.2], [-80.7, 28.2], [-80.7, 28.0]]]}
            },
        ]
        tree, geometries, lookup = build_spatial_index(features)
        results = spatial_join(tree, geometries, lookup, [])
        assert len(results) == 0


# ── Session tests ─────────────────────────────────────────────

from cli_anything.spatial.core.session import Session


class TestSession:
    def test_init(self, tmp_path):
        s = Session(path=str(tmp_path / "s.json"))
        assert s.current_county is None

    def test_record_and_undo(self, tmp_path):
        s = Session(path=str(tmp_path / "s.json"))
        s.record("conquer --county brevard")
        assert len(s.history) == 1
        entry = s.undo()
        assert entry["command"] == "conquer --county brevard"
