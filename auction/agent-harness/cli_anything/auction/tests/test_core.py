"""Unit tests for Auction CLI core modules."""

import json
import pytest

# ── Analysis tests (the core business logic) ─────────────────────────

from cli_anything.auction.core.analysis import (
    calculate_max_bid, calculate_bid_ratio, recommend,
    analyze_case, estimate_arv, estimate_repairs, batch_analyze,
    BID_THRESHOLD, REVIEW_THRESHOLD,
)


class TestMaxBid:
    def test_standard_calculation(self):
        # ARV=285K, Repairs=35K
        # (285000*0.70) - 35000 - 10000 - min(25000, 285000*0.15)
        # = 199500 - 35000 - 10000 - 25000 = 129500
        result = calculate_max_bid(285000, 35000)
        assert result["max_bid"] == 129500
        assert result["arv"] == 285000
        assert result["repairs"] == 35000

    def test_low_arv_uses_15pct(self):
        # ARV=100K, Repairs=10K
        # (100000*0.70) - 10000 - 10000 - min(25000, 15000)
        # = 70000 - 10000 - 10000 - 15000 = 35000
        result = calculate_max_bid(100000, 10000)
        assert result["max_bid"] == 35000
        assert result["contingency"] == 15000

    def test_high_arv_caps_at_25k(self):
        # ARV=500K → contingency = min(25000, 75000) = 25000
        result = calculate_max_bid(500000, 50000)
        assert result["contingency"] == 25000

    def test_negative_result_floors_at_zero(self):
        result = calculate_max_bid(50000, 40000)
        assert result["max_bid"] >= 0

    def test_zero_arv_raises(self):
        with pytest.raises(ValueError, match="ARV must be positive"):
            calculate_max_bid(0, 10000)

    def test_negative_repairs_raises(self):
        with pytest.raises(ValueError, match="Repairs cannot be negative"):
            calculate_max_bid(200000, -5000)

    def test_zero_repairs(self):
        result = calculate_max_bid(200000, 0)
        assert result["repairs"] == 0
        assert result["max_bid"] > 0


class TestBidRatio:
    def test_standard_ratio(self):
        ratio = calculate_bid_ratio(150000, 200000)
        assert ratio == 0.75

    def test_zero_judgment(self):
        assert calculate_bid_ratio(100000, 0) == 0.0

    def test_ratio_above_one(self):
        ratio = calculate_bid_ratio(250000, 200000)
        assert ratio == 1.25


class TestRecommend:
    def test_bid(self):
        assert recommend(150000, 200000) == "BID"  # 0.75

    def test_review(self):
        assert recommend(130000, 200000) == "REVIEW"  # 0.65

    def test_skip(self):
        assert recommend(100000, 200000) == "SKIP"  # 0.50

    def test_exact_bid_threshold(self):
        assert recommend(75000, 100000) == "BID"  # exactly 0.75

    def test_just_below_bid(self):
        assert recommend(74900, 100000) == "REVIEW"  # 0.749

    def test_exact_review_threshold(self):
        assert recommend(60000, 100000) == "REVIEW"  # exactly 0.60

    def test_just_below_review(self):
        assert recommend(59900, 100000) == "SKIP"  # 0.599


class TestAnalyzeCase:
    def test_full_analysis(self):
        case = {"case_number": "2024-CA-001234", "judgment": 223000,
                "address": "123 Main St", "plaintiff": "Bank of America"}
        result = analyze_case(case, arv=285000, repairs=35000)
        assert result["case_number"] == "2024-CA-001234"
        assert result["recommendation"] in ("BID", "REVIEW", "SKIP")
        assert result["max_bid"] > 0
        assert result["bid_ratio"] > 0
        assert "breakdown" in result

    def test_analysis_with_estimates(self):
        case = {"case_number": "TEST-001", "judgment": 200000}
        result = analyze_case(case)
        assert result["arv"] > 0  # Should use estimate
        assert result["repairs"] > 0

    def test_estimate_arv(self):
        assert estimate_arv({"judgment": 200000}) == 260000  # 200K * 1.3

    def test_estimate_repairs(self):
        assert estimate_repairs({}) == 30000


class TestBatchAnalyze:
    def test_batch(self):
        cases = [
            {"case_number": "A", "judgment": 100000},
            {"case_number": "B", "judgment": 200000},
            {"case_number": "C", "judgment": 300000},
        ]
        result = batch_analyze(cases)
        assert result["total"] == 3
        assert result["analyzed"] == 3
        assert result["bid"] + result["review"] + result["skip"] == 3
        assert len(result["results"]) == 3

    def test_batch_empty(self):
        result = batch_analyze([])
        assert result["total"] == 0


# ── Discovery tests ──────────────────────────────────────────────────

from cli_anything.auction.core.discovery import (
    get_upcoming_auctions, scrape_auction_list, get_case_details, SAMPLE_CASES,
)


class TestDiscovery:
    def test_upcoming(self):
        result = get_upcoming_auctions()
        assert result["county"] == "brevard"
        assert result["count"] > 0

    def test_upcoming_with_date(self):
        result = get_upcoming_auctions(date="2026-03-15")
        assert result["date"] == "2026-03-15"

    def test_scrape_sample(self):
        cases = scrape_auction_list("sample")
        assert len(cases) == len(SAMPLE_CASES)

    def test_get_case_details(self):
        case = get_case_details("2024-CA-001234")
        assert case is not None
        assert case["case_number"] == "2024-CA-001234"

    def test_get_case_not_found(self):
        assert get_case_details("FAKE-999") is None


# ── Title Search tests ───────────────────────────────────────────────

from cli_anything.auction.core.title_search import (
    search_liens, get_lien_priority, detect_senior_mortgage,
)


class TestTitleSearch:
    def test_search_liens(self):
        liens = search_liens("2024-CA-001234")
        assert len(liens) >= 1
        assert all("type" in l for l in liens)

    def test_lien_priority(self):
        liens = [{"position": 2, "type": "hoa"}, {"position": 1, "type": "mortgage"}]
        sorted_liens = get_lien_priority(liens)
        assert sorted_liens[0]["position"] == 1

    def test_detect_senior_no_risk(self):
        liens = [{"position": 1, "holder": "Bank of America", "amount": 200000}]
        result = detect_senior_mortgage(liens, "Bank of America")
        assert result["senior_survives"] is False
        assert result["risk"] == "low"

    def test_detect_senior_high_risk(self):
        liens = [{"position": 1, "holder": "Bank of America", "amount": 200000}]
        result = detect_senior_mortgage(liens, "HOA Sunset Palms")
        assert result["senior_survives"] is True
        assert result["risk"] == "high"
        assert result["senior_amount"] == 200000

    def test_detect_senior_no_liens(self):
        result = detect_senior_mortgage([], "Anyone")
        assert result["risk"] == "unknown"


# ── Report tests ─────────────────────────────────────────────────────

from cli_anything.auction.core.report import generate_text_report, generate_report, batch_reports


class TestReport:
    def test_text_report(self):
        data = {"case_number": "TEST-001", "address": "123 Main",
                "plaintiff": "Bank", "judgment_amount": 200000,
                "arv": 260000, "repairs": 30000, "max_bid": 100000,
                "bid_ratio": 0.5, "recommendation": "SKIP"}
        text = generate_text_report(data)
        assert "TEST-001" in text
        assert "SKIP" in text

    def test_generate_text_to_file(self, tmp_path):
        data = {"case_number": "TEST-002", "recommendation": "BID",
                "judgment_amount": 100000, "arv": 200000, "repairs": 20000,
                "max_bid": 80000, "bid_ratio": 0.8, "address": "x", "plaintiff": "y"}
        result = generate_report(data, fmt="text", output_path=str(tmp_path / "r.txt"))
        assert result["format"] == "text"
        assert (tmp_path / "r.txt").exists()

    def test_generate_json_to_file(self, tmp_path):
        data = {"case_number": "TEST-003", "recommendation": "REVIEW"}
        result = generate_report(data, fmt="json", output_path=str(tmp_path / "r.json"))
        assert result["format"] == "json"

    def test_batch_reports(self, tmp_path):
        analyses = [
            {"case_number": "A", "recommendation": "BID", "judgment_amount": 100000,
             "arv": 200000, "repairs": 20000, "max_bid": 80000, "bid_ratio": 0.8,
             "address": "x", "plaintiff": "y"},
            {"case_number": "B", "recommendation": "SKIP", "judgment_amount": 50000,
             "arv": 60000, "repairs": 10000, "max_bid": 20000, "bid_ratio": 0.4,
             "address": "z", "plaintiff": "w"},
        ]
        result = batch_reports(analyses, str(tmp_path / "reports"))
        assert result["generated"] == 2


# ── Export tests ─────────────────────────────────────────────────────

from cli_anything.auction.core.export import to_json, to_csv


class TestExport:
    def test_to_json(self, tmp_path):
        result = to_json({"test": True}, str(tmp_path / "out.json"))
        assert result["format"] == "json"
        assert result["size_bytes"] > 0

    def test_to_csv(self, tmp_path):
        data = [{"case": "A", "bid": 100}, {"case": "B", "bid": 200}]
        result = to_csv(data, str(tmp_path / "out.csv"))
        assert result["records"] == 2
