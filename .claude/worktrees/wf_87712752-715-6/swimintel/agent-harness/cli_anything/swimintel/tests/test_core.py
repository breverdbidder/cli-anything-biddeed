"""Unit tests for SwimIntel CLI Agent #139."""

import pytest
import json
import os
import sys

# Add parent to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from cli_anything.swimintel.core.parser import (
    parse_time_to_seconds,
    detect_course,
    detect_qualifier,
)
from cli_anything.swimintel.core.analyzer import (
    filter_age_group,
    estimate_probability,
    determine_verdict,
)
from cli_anything.swimintel.core.session import Session


# ============================================================
# Parser Tests
# ============================================================
class TestParser:
    def test_parse_time_minutes(self):
        assert parse_time_to_seconds("1:53.03") == 113.03

    def test_parse_time_seconds(self):
        assert parse_time_to_seconds("21.88") == 21.88

    def test_parse_time_with_suffix(self):
        assert parse_time_to_seconds("31.00L") == 31.00

    def test_detect_course_scy(self):
        assert detect_course("21.88", "SRCH") == "SCY"

    def test_detect_course_lcm(self):
        assert detect_course("31.00L", "SRCH") == "LCM"

    def test_detect_qualifier_srch(self):
        assert detect_qualifier("SRCH") == "SRCH"

    def test_detect_qualifier_bonus(self):
        assert detect_qualifier("55.87Y B") == "B"

    def test_detect_qualifier_empty(self):
        assert detect_qualifier("") == ""


# ============================================================
# Analyzer Tests
# ============================================================
class TestAnalyzer:
    SAMPLE_ENTRIES = [
        {"name": "Fast, Swimmer", "age": 16, "seed_time": 21.50},
        {"name": "Medium, Swimmer", "age": 15, "seed_time": 22.00},
        {"name": "Slow, Swimmer", "age": 17, "seed_time": 22.50},
        {"name": "Young, Swimmer", "age": 14, "seed_time": 23.00},
        {"name": "Old, Swimmer", "age": 19, "seed_time": 21.00},
    ]

    def test_filter_age_group_15_16(self):
        result = filter_age_group(self.SAMPLE_ENTRIES, "15-16")
        assert len(result) == 2
        assert all(15 <= e["age"] <= 16 for e in result)

    def test_filter_age_group_17_18(self):
        result = filter_age_group(self.SAMPLE_ENTRIES, "17-18")
        assert len(result) == 1

    def test_estimate_probability_inside(self):
        # Already inside cut (gap positive)
        prob = estimate_probability(0.05, 50)
        assert prob >= 0.80

    def test_estimate_probability_small_gap_sprint(self):
        # Small gap in sprint event
        prob = estimate_probability(-0.30, 50)
        assert 0.20 <= prob <= 0.50

    def test_estimate_probability_large_gap_distance(self):
        # Large gap in distance event
        prob = estimate_probability(-10.0, 200)
        assert prob < 0.05

    def test_determine_verdict_a_final(self):
        assert determine_verdict(0.60, 0.90) == "A-FINAL CONTENDER"

    def test_determine_verdict_b_final(self):
        assert determine_verdict(0.10, 0.70) == "B-FINAL LIKELY"

    def test_determine_verdict_development(self):
        assert determine_verdict(0.01, 0.02) == "DEVELOPMENT"


# ============================================================
# Session Tests
# ============================================================
class TestSession:
    def test_session_create(self):
        sess = Session()
        assert sess.age_group == "15-16"
        assert not sess.has_data

    def test_session_status(self):
        sess = Session(swimmer_name="Shapira, Michael")
        status = sess.status()
        assert status["swimmer"] == "Shapira, Michael"
        assert status["age_group"] == "15-16"

    def test_session_save_load(self, tmp_path):
        sess = Session(swimmer_name="Test, Swimmer", age_group="17-18")
        path = str(tmp_path / "test_session.json")
        sess.save(path)

        loaded = Session.load(path)
        assert loaded.swimmer_name == "Test, Swimmer"
        assert loaded.age_group == "17-18"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
