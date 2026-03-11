"""Unit tests for ZoneWise CLI core modules.

No external dependencies — all API calls mocked.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ── Scraper tests ─────────────────────────────────────────────────────

from cli_anything.zonewise.core.scraper import (
    get_county_list, scrape_county, get_scrape_status, FL_COUNTIES,
)


class TestScraper:
    def test_county_list_fl(self):
        counties = get_county_list("FL")
        assert len(counties) == 46
        assert {"county": "brevard", "state": "FL"} in counties

    def test_county_list_other_state(self):
        assert get_county_list("TX") == []

    def test_county_list_case_insensitive(self):
        assert len(get_county_list("fl")) == 46

    def test_scrape_county_valid(self):
        result = scrape_county("brevard", tier=4)
        assert result["county"] == "brevard"
        assert result["status"] == "manual_flag"

    def test_scrape_county_invalid(self):
        with pytest.raises(ValueError, match="Unknown county"):
            scrape_county("fake_county")

    def test_scrape_county_normalizes_name(self):
        result = scrape_county("miami-dade", tier=4)
        assert result["county"] == "miami_dade"

    def test_scrape_tier1_no_key(self):
        result = scrape_county("brevard", tier=1)
        assert result["status"] == "error"
        assert "API key" in result.get("message", "")

    def test_scrape_tier2_stub(self):
        result = scrape_county("brevard", tier=2)
        assert result["status"] == "stub"
        assert "Tier 2" in result["message"]

    def test_scrape_tier3_stub(self):
        result = scrape_county("brevard", tier=3)
        assert result["status"] == "stub"
        assert "Tier 3" in result["message"]

    def test_scrape_tier4_manual(self):
        result = scrape_county("orange", tier=4)
        assert result["status"] == "manual_flag"
        assert "orange" in result["message"]

    def test_scrape_has_timestamp(self):
        result = scrape_county("brevard", tier=4)
        assert "timestamp" in result
        assert "2026" in result["timestamp"] or "202" in result["timestamp"]

    def test_fl_counties_count(self):
        assert len(FL_COUNTIES) == 46

    def test_fl_counties_no_duplicates(self):
        assert len(FL_COUNTIES) == len(set(FL_COUNTIES))

    def test_get_scrape_status_unknown(self):
        result = get_scrape_status("brevard")
        assert result["county"] == "brevard"


# ── Parser tests ──────────────────────────────────────────────────────

from cli_anything.zonewise.core.parser import (
    classify_zoning, parse_zoning_record, parse_zoning_from_markdown,
    _parse_int, _parse_setbacks,
)


class TestParser:
    def test_classify_residential(self):
        assert classify_zoning("RS-1") == "residential"
        assert classify_zoning("RU-2") == "residential"

    def test_classify_commercial(self):
        assert classify_zoning("CG") == "commercial"
        assert classify_zoning("BU-1") == "commercial"

    def test_classify_industrial(self):
        assert classify_zoning("IL") == "industrial"
        assert classify_zoning("MH") == "residential"  # MH = mobile home = residential

    def test_classify_agricultural(self):
        assert classify_zoning("AG") == "agricultural"
        assert classify_zoning("AU") == "agricultural"

    def test_classify_mixed_use(self):
        assert classify_zoning("MU-1") == "mixed_use"
        assert classify_zoning("MX") == "mixed_use"

    def test_classify_conservation(self):
        assert classify_zoning("CON") == "conservation"
        assert classify_zoning("OS") == "conservation"

    def test_classify_other(self):
        assert classify_zoning("ZZZ") == "other"
        assert classify_zoning("X99") == "other"

    def test_classify_with_name(self):
        assert classify_zoning("R1", "Single Family Residential") == "residential"

    def test_parse_zoning_record(self):
        raw = {"code": "rs-1", "name": "Single Family", "min_lot_size": "7500", "max_height": "35"}
        rec = parse_zoning_record(raw)
        assert rec["zone_code"] == "RS-1"
        assert rec["zone_name"] == "Single Family"
        assert rec["category"] == "residential"
        assert rec["min_lot_size_sqft"] == 7500
        assert rec["max_height_ft"] == 35

    def test_parse_zoning_record_missing_fields(self):
        rec = parse_zoning_record({"code": "CG"})
        assert rec["zone_code"] == "CG"
        assert rec["min_lot_size_sqft"] is None

    def test_parse_int_various(self):
        assert _parse_int("7,500 sqft") == 7500
        assert _parse_int("35 ft") == 35
        assert _parse_int(None) is None
        assert _parse_int("") is None
        assert _parse_int(42) == 42

    def test_parse_setbacks(self):
        result = _parse_setbacks({"front": "25", "rear": "20", "side": "7.5"})
        assert result["front"] == 25
        assert result["rear"] == 20
        assert result["side"] == 7

    def test_parse_setbacks_empty(self):
        result = _parse_setbacks({})
        assert result["front"] is None

    def test_parse_markdown_extracts_codes(self):
        md = """
**RS-1** - Single Family Residential
**CG** - General Commercial
**IL** - Light Industrial
Some other text here.
"""
        records = parse_zoning_from_markdown(md, "brevard")
        assert len(records) >= 2
        codes = [r["zone_code"] for r in records]
        assert "RS-1" in codes or "CG" in codes


# ── Export tests ──────────────────────────────────────────────────────

from cli_anything.zonewise.core.export import to_json, to_csv


class TestExport:
    def test_to_json(self, tmp_path):
        data = [{"zone_code": "RS-1", "category": "residential"}]
        result = to_json(data, str(tmp_path / "out.json"))
        assert result["format"] == "json"
        assert result["records"] == 1
        assert result["size_bytes"] > 0
        # Verify file is valid JSON
        parsed = json.loads(Path(result["path"]).read_text())
        assert len(parsed) == 1

    def test_to_csv(self, tmp_path):
        data = [{"zone_code": "RS-1", "category": "residential"}, {"zone_code": "CG", "category": "commercial"}]
        result = to_csv(data, str(tmp_path / "out.csv"))
        assert result["format"] == "csv"
        assert result["records"] == 2
        # Verify CSV content
        content = Path(result["path"]).read_text()
        assert "zone_code" in content
        assert "RS-1" in content

    def test_to_csv_empty(self, tmp_path):
        result = to_csv([], str(tmp_path / "empty.csv"))
        assert result["records"] == 0

    def test_to_json_creates_dirs(self, tmp_path):
        deep_path = str(tmp_path / "a" / "b" / "c" / "out.json")
        result = to_json([{"test": True}], deep_path)
        assert result["records"] == 1

    def test_to_csv_nested_values(self, tmp_path):
        data = [{"code": "RS-1", "setbacks": {"front": 25, "rear": 20}}]
        result = to_csv(data, str(tmp_path / "nested.csv"))
        content = Path(result["path"]).read_text()
        assert "front" in content  # Nested dict should be JSON-serialized


# ── Session tests ─────────────────────────────────────────────────────

from cli_anything.zonewise.core.session import Session


class TestSession:
    def test_session_init(self, tmp_path):
        s = Session(path=str(tmp_path / "session.json"))
        assert s.current_county is None
        assert s.history == []

    def test_session_save_load(self, tmp_path):
        path = str(tmp_path / "session.json")
        s = Session(path=path)
        s.current_county = "brevard"
        s.record("county scrape --county brevard")
        s.save()

        s2 = Session(path=path)
        assert s2.current_county == "brevard"
        assert len(s2.history) == 1

    def test_session_undo(self, tmp_path):
        s = Session(path=str(tmp_path / "session.json"))
        s.record("cmd1")
        s.record("cmd2")
        entry = s.undo()
        assert entry["command"] == "cmd2"
        assert len(s.undo_stack) == 1

    def test_session_undo_empty(self, tmp_path):
        s = Session(path=str(tmp_path / "session.json"))
        assert s.undo() is None

    def test_session_status(self, tmp_path):
        s = Session(path=str(tmp_path / "session.json"))
        s.current_county = "orange"
        s.record("test")
        status = s.status()
        assert status["current_county"] == "orange"
        assert status["history_count"] == 1
        assert status["undo_available"] == 1

    def test_session_clear(self, tmp_path):
        s = Session(path=str(tmp_path / "session.json"))
        s.current_county = "brevard"
        s.record("test")
        s.clear()
        assert s.current_county is None
        assert s.history == []
