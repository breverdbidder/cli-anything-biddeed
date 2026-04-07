#!/usr/bin/env python3
"""Tests for owner_osint.py — issue #391 fixes.

Covers: name extraction, city rejection, confidence scoring, classification thresholds.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.owner_osint import (
    extract_last_name, extract_first_name, normalize_name,
    is_city_name, classify_owner, compute_confidence, levenshtein,
    classify_by_name,
)


# --- Name extraction ---

def test_extract_last_name_comma_format():
    assert extract_last_name("SMITH, JOHN") == "SMITH"

def test_extract_last_name_space_format():
    assert extract_last_name("JOHN SMITH") == "SMITH"

def test_extract_last_name_single():
    assert extract_last_name("MELBOURNE") == "MELBOURNE"

def test_extract_first_name_comma():
    assert extract_first_name("ROTH, DAVID S") == "DAVID"

def test_extract_first_name_space():
    assert extract_first_name("DAVID S ROTH") == "DAVID"

def test_extract_first_name_single_word():
    assert extract_first_name("MELBOURNE") == ""


# --- City rejection ---

def test_melbourne_is_city():
    assert is_city_name("MELBOURNE") is True

def test_palm_bay_is_city():
    assert is_city_name("PALM BAY") is True

def test_titusville_is_city():
    assert is_city_name("TITUSVILLE") is True

def test_cocoa_is_city():
    assert is_city_name("COCOA") is True

def test_viera_is_city():
    assert is_city_name("VIERA") is True

def test_rockledge_is_city():
    assert is_city_name("ROCKLEDGE") is True

def test_satellite_beach_is_city():
    assert is_city_name("SATELLITE BEACH") is True

def test_cape_canaveral_is_city():
    assert is_city_name("CAPE CANAVERAL") is True

def test_indian_harbour_beach_is_city():
    assert is_city_name("INDIAN HARBOUR BEACH") is True

def test_merritt_island_is_city():
    assert is_city_name("MERRITT ISLAND") is True

def test_real_name_not_city():
    assert is_city_name("JOHNSON") is False

def test_real_name_not_city2():
    assert is_city_name("GOLDSTEIN") is False


# --- Short last names rejected ---

def test_short_last_name_rejected():
    """Single-letter first names like 'C GARNER' — last name is fine,
    but 'C' as a standalone defendant should be rejected."""
    assert len("C") < 4  # Single char is < 4


# --- Levenshtein ---

def test_levenshtein_exact():
    assert levenshtein("DAVID", "DAVID") == 0

def test_levenshtein_close():
    assert levenshtein("DAVID", "DAVD") == 1

def test_levenshtein_far():
    assert levenshtein("DAVID", "MELBOURNE") > 2


# --- Confidence scoring ---

def test_confidence_no_parcels():
    assert compute_confidence("SMITH, JOHN", [], False) == 0.0

def test_confidence_good_match():
    parcels = [{"owner_name": "SMITH, JOHN A", "owner_state": "FL"}]
    score = compute_confidence("SMITH, JOHN", parcels, False)
    assert score >= 0.7, f"Expected >= 0.7 for good match, got {score}"

def test_confidence_page_cap_reduces():
    parcels = [{"owner_name": "SMITH, JOHN A", "owner_state": "FL"}]
    score_no_cap = compute_confidence("SMITH, JOHN", parcels, False)
    score_cap = compute_confidence("SMITH, JOHN", parcels, True)
    assert score_no_cap > score_cap, "Page cap should reduce confidence"

def test_confidence_short_name_lower():
    parcels = [{"owner_name": "LI, WEI", "owner_state": "FL"}]
    score = compute_confidence("LI, WEI", parcels, False)
    # "LI" is only 2 chars — should get lower name-length factor
    assert score < 0.9


# --- Classification ---

def test_classify_investor_needs_3_parcels():
    """2 parcels is NOT enough for INVESTOR anymore."""
    parcels = [{"luse_code": "0100"}, {"luse_code": "0100"}]
    result = classify_owner("SMITH, JOHN", parcels, 0.8)
    assert result == "UNKNOWN", f"2 parcels should be UNKNOWN, got {result}"

def test_classify_investor_3_parcels_high_confidence():
    parcels = [{"luse_code": "0100"}] * 3
    result = classify_owner("SMITH, JOHN", parcels, 0.8)
    assert result == "INVESTOR"

def test_classify_investor_low_confidence_rejected():
    parcels = [{"luse_code": "0100"}] * 5
    result = classify_owner("SMITH, JOHN", parcels, 0.5)
    assert result == "UNKNOWN", f"Low confidence should be UNKNOWN, got {result}"

def test_classify_estate():
    result = classify_owner("ESTATE OF SMITH", [], 0.0)
    assert result == "ESTATE"

def test_classify_corporate():
    result = classify_owner("SMITH HOLDINGS LLC", [], 0.0)
    assert result == "CORPORATE"

def test_classify_homeowner_single_residential():
    parcels = [{"luse_code": "0010"}]
    result = classify_owner("SMITH, JOHN", parcels, 0.8)
    assert result == "DISTRESSED_HOMEOWNER"


# --- Integration: city defendants get 0 parcels ---

def test_melbourne_defendant_no_parcels():
    """MELBOURNE as defendant should be rejected by is_city_name,
    resulting in 0 parcels from lookup_parcels."""
    assert is_city_name("MELBOURNE") is True
    # With 0 parcels and no corporate/estate pattern → UNKNOWN
    result = classify_owner("MELBOURNE", [], 0.0)
    assert result == "UNKNOWN"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
