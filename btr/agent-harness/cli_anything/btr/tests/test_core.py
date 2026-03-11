"""
Tests for cli-anything-btr: EVEREST-BTR Squad
==============================================
Target: 20+ tests covering all 10 agents.
"""
import json
import pytest
from click.testing import CliRunner
from cli_anything.btr.btr_cli import cli, MAI_WEIGHTS, THRESHOLDS, _decision


runner = CliRunner()


# ── Decision logic ───────────────────────────────────────────

class TestDecisionLogic:
    def test_bid_threshold(self):
        assert _decision(75) == "BID"
        assert _decision(100) == "BID"

    def test_review_threshold(self):
        assert _decision(60) == "REVIEW"
        assert _decision(74) == "REVIEW"

    def test_skip_threshold(self):
        assert _decision(59) == "SKIP"
        assert _decision(0) == "SKIP"

    def test_mai_weights_exist_for_all_types(self):
        for pt in ("sfr", "duplex", "multifamily", "new_construct", "distressed"):
            assert pt in MAI_WEIGHTS
            w = MAI_WEIGHTS[pt]
            total = w["income"] + w["comp"] + w["cost"]
            assert abs(total - 1.0) < 0.001, f"{pt} weights don't sum to 1.0"


# ── Squad Commander ──────────────────────────────────────────

class TestCommander:
    def test_analyze_full(self):
        result = runner.invoke(cli, ["--json", "analyze", "123 Ocean Ave", "--type", "sfr", "--scenario", "full"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["agent"] == "cli_btr.commander"
        assert len(data["pipeline"]) == 8

    def test_analyze_land_scenario(self):
        result = runner.invoke(cli, ["--json", "analyze", "456 Beach St", "--type", "duplex", "--scenario", "land"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "cli_btr.land" in data["pipeline"]
        assert "cli_btr.hbu" in data["pipeline"]

    def test_analyze_rehab_scenario(self):
        result = runner.invoke(cli, ["--json", "analyze", "789 Main St", "--type", "multifamily", "--scenario", "rehab"])
        data = json.loads(result.output)
        assert "cli_btr.rehab" in data["pipeline"]
        assert "cli_btr.cost" in data["pipeline"]


# ── MAI Valuation Engine ─────────────────────────────────────

class TestMAI:
    def test_income_approach_only(self):
        result = runner.invoke(cli, ["--json", "mai", "100 Test St", "--type", "multifamily",
                                     "--noi", "100000", "--cap-rate", "0.065"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["agent"] == "cli_btr.mai"
        assert abs(data["approach_values"]["income"] - 1538461.54) < 1
        assert data["confidence"] == "low"

    def test_all_three_approaches(self):
        result = runner.invoke(cli, ["--json", "mai", "200 Test St", "--type", "sfr",
                                     "--noi", "24000", "--cap-rate", "0.07",
                                     "--comp-value", "350000", "--cost-value", "320000"])
        data = json.loads(result.output)
        assert data["confidence"] == "high"
        assert data["reconciled_value"] > 0

    def test_sfr_weights_favor_comps(self):
        result = runner.invoke(cli, ["--json", "mai", "300 Test St", "--type", "sfr",
                                     "--noi", "24000", "--cap-rate", "0.07",
                                     "--comp-value", "400000", "--cost-value", "300000"])
        data = json.loads(result.output)
        # SFR: 60% comp weight, so reconciled should be closer to comp value
        assert data["reconciled_value"] > 350000


# ── Rehab Agent ──────────────────────────────────────────────

class TestRehab:
    def test_max_bid_formula(self):
        result = runner.invoke(cli, ["--json", "rehab", "500 Distressed Ave", "--type", "sfr",
                                     "--arv", "300000", "--repairs", "50000"])
        data = json.loads(result.output)
        assert data["agent"] == "cli_btr.rehab"
        # (300000 * 0.70) - 50000 - 10000 - min(25000, 45000) = 210000 - 50000 - 10000 - 25000 = 125000
        assert data["max_bid"] == 125000.0
        assert data["decision"] in ("BID", "REVIEW", "SKIP")

    def test_negative_max_bid_skips(self):
        result = runner.invoke(cli, ["--json", "rehab", "999 Money Pit", "--type", "sfr",
                                     "--arv", "100000", "--repairs", "80000"])
        data = json.loads(result.output)
        assert data["max_bid"] < 0
        assert data["decision"] == "SKIP"


# ── Permanent Funding ────────────────────────────────────────

class TestPermanent:
    def test_max_perm_loan(self):
        result = runner.invoke(cli, ["--json", "permanent", "600 Perm St",
                                     "--noi", "120000", "--rate", "0.065", "--dcr", "1.25"])
        data = json.loads(result.output)
        assert data["agent"] == "cli_btr.perm"
        assert data["max_perm_loan"] > 0
        assert data["max_annual_debt_service"] == 96000.0

    def test_rate_lock_recommendation(self):
        result = runner.invoke(cli, ["--json", "permanent", "700 Lock St",
                                     "--noi", "100000", "--rate", "0.055", "--dcr", "1.20"])
        data = json.loads(result.output)
        assert data["recommendation"] == "lock_rate"


# ── Cost Estimator ───────────────────────────────────────────

class TestCost:
    def test_sfr_new_construction(self):
        result = runner.invoke(cli, ["--json", "cost", "--type", "sfr",
                                     "--units", "1", "--sf-per-unit", "2000", "--scope", "new"])
        data = json.loads(result.output)
        assert data["agent"] == "cli_btr.cost"
        assert data["cost_per_sf"] == 185
        assert data["total_budget"] > 0

    def test_multifamily_rehab(self):
        result = runner.invoke(cli, ["--json", "cost", "--type", "multifamily",
                                     "--units", "10", "--sf-per-unit", "900", "--scope", "rehab"])
        data = json.loads(result.output)
        assert data["cost_per_sf"] == 75
        assert data["per_unit_cost"] > 0

    def test_premium_finish_multiplier(self):
        std = runner.invoke(cli, ["--json", "cost", "--type", "sfr",
                                  "--units", "1", "--sf-per-unit", "2000", "--scope", "new", "--finish", "standard"])
        prem = runner.invoke(cli, ["--json", "cost", "--type", "sfr",
                                   "--units", "1", "--sf-per-unit", "2000", "--scope", "new", "--finish", "premium"])
        std_data = json.loads(std.output)
        prem_data = json.loads(prem.output)
        assert prem_data["total_budget"] > std_data["total_budget"]


# ── Lender Vetting ───────────────────────────────────────────

class TestLenderVet:
    def test_strong_lender(self):
        result = runner.invoke(cli, ["--json", "lender-vet",
                                     "--dcr", "1.20", "--rate-lock", "commitment",
                                     "--term", "10", "--prepay", "1pct", "--amort", "30"])
        data = json.loads(result.output)
        assert data["agent"] == "cli_btr.lv"
        assert data["recommendation"] == "strong_fit"

    def test_weak_lender(self):
        result = runner.invoke(cli, ["--json", "lender-vet",
                                     "--dcr", "1.40", "--rate-lock", "none",
                                     "--term", "3", "--prepay", "5-4-3-2-1"])
        data = json.loads(result.output)
        assert data["recommendation"] in ("weak_fit", "evaluate")


# ── Status ───────────────────────────────────────────────────

class TestStatus:
    def test_status_shows_all_agents(self):
        result = runner.invoke(cli, ["--json", "status"])
        data = json.loads(result.output)
        assert data["total_agents"] == 10
        assert len(data["agents"]) == 10
        assert "sfr" in data["property_types"]


# ── Construction Funding ─────────────────────────────────────

class TestConstruction:
    def test_duplex_budget_range(self):
        result = runner.invoke(cli, ["--json", "construction", "800 Build St",
                                     "--type", "duplex", "--units", "2", "--sf-per-unit", "1200"])
        data = json.loads(result.output)
        assert data["agent"] == "cli_btr.con"
        assert data["total_sf"] == 2400
        assert "$" in data["budget_range"]


# ── Land Acquisition ─────────────────────────────────────────

class TestLand:
    def test_land_only_path(self):
        result = runner.invoke(cli, ["--json", "land", "900 Vacant Lot",
                                     "--type", "sfr", "--units", "0"])
        data = json.loads(result.output)
        assert data["loan_path"] == "land_only"

    def test_acq_plus_construction_path(self):
        result = runner.invoke(cli, ["--json", "land", "901 Ready Lot",
                                     "--type", "multifamily", "--units", "12"])
        data = json.loads(result.output)
        assert data["loan_path"] == "acquisition_plus_construction"
