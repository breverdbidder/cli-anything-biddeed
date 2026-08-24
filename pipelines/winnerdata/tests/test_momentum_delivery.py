"""Unit tests for pipelines/winnerdata/momentum_delivery.py.

Includes the three DoD-mandated negative tests:
  1. malformed FF (missing insured name) -> rejected, logged, no artifact
  2. vacant-land / non-Tracerfy-verified-phone -> gate-blocked, never delivered
  3. duplicate delivery of the same FF -> update/skip, never a second insert
"""
import copy
import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import momentum_delivery as md  # noqa: E402


def base_ff(**overrides):
    ff = {
        "schema_version": "1.0",
        "id": "SLQ-2026-TEST-001",
        "lead_id": "11111111-1111-1111-1111-111111111111",
        "org_id": "22222222-2222-2222-2222-222222222222",
        "applicant": {
            "entity_name": {"value": "TEST INVESTOR LLC", "source": "SL"},
            "contact_name": {"value": "TEST INVESTOR LLC", "source": "SL"},
            "contact_phone": {"value": "5551234567", "source": "SL"},
            "contact_email": {"value": "test@example.com", "source": "SL"},
            "mailing_address": {"value": None, "source": "FLP"},
        },
        "property": {
            "address": {"value": "123 MAIN ST, ORLANDO, FL 32801", "source": "MCA"},
            "county": {"value": "orange", "source": "MCA"},
            "parcel_id": {"value": "01-23-45", "source": "SL"},
            "year_built": {"value": 1998, "source": "FLP"},
            "sqft": {"value": 1500, "source": "FLP"},
            "num_buildings": {"value": 1, "source": "FLP"},
            "construction_class": {"value": None, "source": "FLP"},
            "dor_use_code": {"value": None, "source": "FLP"},
            "zone_code": {"value": None, "source": "FLP"},
            "just_value": {"value": 150000, "source": "FLP"},
            "improved": {"value": True, "source": "FLP"},
            "occupancy_status": {"value": "unknown", "source": "PC"},
        },
        "purchase": {
            "sale_type": {"value": "tax_deed", "source": "MCA"},
            "sold_amount": {"value": 90000.0, "source": "MCA"},
            "auction_date": {"value": "2026-08-01", "source": "MCA"},
            "case_number": {"value": "2026-TXD-001", "source": "MCA"},
        },
        "buyer_profile": {
            "total_wins": {"value": 1, "source": "ABP"},
            "total_deployed": {"value": None, "source": "ABP"},
            "counties_active": {"value": None, "source": "ABP"},
            "is_repeat_investor": {"value": False, "source": "ABP"},
        },
        "bundle_doctrine": {
            "umbrella_quote_requested": False,
            "umbrella_quote_reason": None,
            "umbrella_limit": None,
            "flood_if_indicated": False,
            "flood_basis": None,
            "commercial_bop_if_applicable": None,
            "builders_risk_if_renovation": None,
            "auto_bundle": "ask_on_call_only",
            "master_policy_conversation": False,
        },
        "must_quote": ["dwelling_landlord"],
        "readiness_score": 80.0,
        "missing_required_fields": [],
        "compliance": {
            "outbound_lane": "compliant_outbound",
            "consent_status": "none",
            "compliance_flag": None,
            "dnc_scrubbed": False,
        },
        "producer_message_draft": "Hi TEST INVESTOR LLC, saw you picked up 123 MAIN ST.",
        "product_line": "dwelling_landlord",
    }
    for key, value in overrides.items():
        ff[key] = value
    return ff


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

def test_business_name_maps_to_commercial_name():
    bundle = md.build_payload(base_ff())
    assert bundle["prospect"]["commercial_name"] == "TEST INVESTOR LLC"
    assert bundle["prospect"]["first_name"] == ""
    assert bundle["meta"]["is_business"] is True


def test_person_name_splits_first_last():
    ff = base_ff()
    ff["applicant"] = copy.deepcopy(ff["applicant"])
    ff["applicant"]["entity_name"]["value"] = "DAVIS, RONALD L."
    bundle = md.build_payload(ff)
    assert bundle["prospect"]["first_name"] == "RONALD L."
    assert bundle["prospect"]["last_name"] == "DAVIS"
    assert bundle["prospect"]["commercial_name"] == ""


def test_address_parses_street_city_zip():
    street, city, state, zip_code = md._parse_property_address("30 CHICKAT TRL, CRAWFORDVILLE, FL 32327")
    assert (street, city, state, zip_code) == ("30 CHICKAT TRL", "CRAWFORDVILLE", "FL", "32327")


def test_address_parses_no_street_vacant_land_shape():
    street, city, state, zip_code = md._parse_property_address("BUNNELL, FL- 32110")
    assert street is None
    assert city == "BUNNELL"
    assert zip_code == "32110"


def test_bundle_doctrine_flags_land_in_custom_fields():
    ff = base_ff()
    ff["bundle_doctrine"] = copy.deepcopy(ff["bundle_doctrine"])
    ff["bundle_doctrine"]["umbrella_quote_requested"] = True
    ff["bundle_doctrine"]["flood_if_indicated"] = True
    bundle = md.build_payload(ff)
    labels = {f["text"]: f["value"] for f in bundle["custom_fields"]}
    assert labels["Umbrella Quote Requested"] == "True"
    assert labels["Flood If Indicated"] == "True"
    assert "Winner Data FF ID" in labels


def test_task_title_matches_dod_format():
    bundle = md.build_payload(base_ff())
    assert bundle["task"]["title"] == "Quote-ready Winner Data lead: TEST INVESTOR LLC"


# ---------------------------------------------------------------------------
# Negative test 1: malformed FF -> rejected, logged, no artifact
# ---------------------------------------------------------------------------

def test_malformed_ff_missing_name_fails_validation():
    ff = base_ff()
    ff["applicant"] = copy.deepcopy(ff["applicant"])
    ff["applicant"]["entity_name"]["value"] = None
    result = md.validate_ff(ff)
    assert result.ok is False
    assert "entity_name" in result.errors[0]


def test_malformed_ff_is_rejected_by_deliver_and_no_downstream_calls():
    ff = base_ff()
    ff["applicant"] = copy.deepcopy(ff["applicant"])
    ff["applicant"]["entity_name"]["value"] = None

    logged = []
    client = _RecordingClient()
    result = md.deliver(ff, client, log_fn=lambda *a: logged.append(a))

    assert result["status"] == "validation_failed"
    assert logged and logged[0][3] == "momentum_validation_failed"
    assert client.insert_prospect_calls == []
    assert client.find_prospect_calls == []


def test_fixtures_cli_produces_no_artifact_for_malformed_ff(tmp_path):
    intake_dir = tmp_path / "intake"
    intake_dir.mkdir()
    ff = base_ff()
    ff["applicant"] = copy.deepcopy(ff["applicant"])
    ff["applicant"]["entity_name"]["value"] = None
    (intake_dir / "SLQ-2026-BROKEN-001.json").write_text(json.dumps(ff))

    out_dir = tmp_path / "out"
    args = type("Args", (), {"intake": str(intake_dir / "*.json"), "out": str(out_dir)})()
    md.cmd_fixtures(args)

    assert list(out_dir.glob("*.json")) == []


# ---------------------------------------------------------------------------
# Negative test 2: vacant land / non-verified phone -> gate-blocked, never delivered
# ---------------------------------------------------------------------------

def test_vacant_land_is_gate_blocked():
    ff = base_ff()
    ff["property"] = copy.deepcopy(ff["property"])
    ff["property"]["num_buildings"]["value"] = 0
    gate = md.check_delivery_gate(ff)
    assert gate.eligible is False
    assert gate.reason == "vacant_land"


def test_unverified_phone_is_gate_blocked():
    ff = base_ff()
    ff["applicant"] = copy.deepcopy(ff["applicant"])
    ff["applicant"]["contact_phone"]["value"] = None
    gate = md.check_delivery_gate(ff)
    assert gate.eligible is False
    assert gate.reason == "non_tracerfy_verified_phone"


def test_unknown_num_buildings_is_not_gated_as_vacant():
    ff = base_ff()
    ff["property"] = copy.deepcopy(ff["property"])
    ff["property"]["num_buildings"]["value"] = None
    gate = md.check_delivery_gate(ff)
    assert gate.eligible is True


@patch("momentum_delivery.get_producer_id", return_value="producer-1")
def test_gated_lead_never_calls_nowcerts_insert(mock_producer):
    ff = base_ff()
    ff["property"] = copy.deepcopy(ff["property"])
    ff["property"]["num_buildings"]["value"] = 0

    logged = []
    client = _RecordingClient()
    result = md.deliver(ff, client, log_fn=lambda *a: logged.append(a))

    assert result["status"] == "gate_blocked"
    assert result["reason"] == "vacant_land"
    assert client.insert_prospect_calls == []
    assert logged[0][3] == "momentum_gate_blocked"


# ---------------------------------------------------------------------------
# Negative test 3: duplicate delivery -> update/skip, never a second insert
# ---------------------------------------------------------------------------

class _RecordingClient:
    """Fake NowCertsClient. `existing` seeds find_prospect's search result
    to simulate a record already present in Momentum from a prior run.
    """

    def __init__(self, existing=None):
        self.existing = existing or []
        self.find_prospect_calls = []
        self.insert_prospect_calls = []
        self.insert_custom_field_calls = []
        self.insert_task_calls = []

    def find_prospect(self, phone=None, email=None):
        self.find_prospect_calls.append((phone, email))
        return self.existing

    def insert_prospect(self, prospect):
        self.insert_prospect_calls.append(prospect)
        return {"databaseId": "new-prospect-id"}

    def insert_custom_field(self, field):
        self.insert_custom_field_calls.append(field)
        return {}

    def insert_task(self, task):
        self.insert_task_calls.append(task)
        return {}


@patch("momentum_delivery.get_producer_id", return_value="producer-1")
def test_first_delivery_inserts_prospect(mock_producer):
    client = _RecordingClient(existing=[])
    logged = []
    result = md.deliver(base_ff(), client, log_fn=lambda *a: logged.append(a))

    assert result["status"] == "delivered"
    assert len(client.insert_prospect_calls) == 1
    assert len(client.insert_task_calls) == 1
    assert logged[0][3] == "momentum_delivered"


@patch("momentum_delivery.get_producer_id", return_value="producer-1")
def test_duplicate_delivery_skips_insert(mock_producer):
    client = _RecordingClient(existing=[
        {"databaseId": "existing-id", "commercialName": "TEST INVESTOR LLC"}
    ])
    logged = []
    result = md.deliver(base_ff(), client, log_fn=lambda *a: logged.append(a))

    assert result["status"] == "skipped_duplicate"
    assert result["nowcerts_id"] == "existing-id"
    assert client.insert_prospect_calls == []
    assert client.insert_task_calls == []
    assert logged[0][3] == "momentum_skipped_duplicate"


@patch("momentum_delivery.get_producer_id", return_value="producer-1")
def test_duplicate_delivery_of_same_ff_twice_never_double_inserts(mock_producer):
    """Simulates running deliver() twice for the same FF, the second time
    with the client's search seeded from the first insert's response --
    exactly what a second pipeline run against a warm Momentum DB does.
    """
    shared_client = _RecordingClient(existing=[])
    logged = []
    first = md.deliver(base_ff(), shared_client, log_fn=lambda *a: logged.append(a))
    assert first["status"] == "delivered"
    assert len(shared_client.insert_prospect_calls) == 1

    shared_client.existing = [{"databaseId": first["nowcerts_id"], "commercialName": "TEST INVESTOR LLC"}]
    second = md.deliver(base_ff(), shared_client, log_fn=lambda *a: logged.append(a))

    assert second["status"] == "skipped_duplicate"
    assert len(shared_client.insert_prospect_calls) == 1  # still just the one insert


def test_normalize_name_dedupe_key_ignores_punctuation_and_case():
    assert md.normalize_name("Pafford Properties & Construction") == md.normalize_name("PAFFORD PROPERTIES  CONSTRUCTION")


# ---------------------------------------------------------------------------
# Fixture schema conformance (docs/winnerdata/payload_fixtures/)
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
FIXTURES_DIR = os.path.join(_REPO_ROOT, "docs", "winnerdata", "payload_fixtures")


def test_committed_fixtures_exist_and_cover_all_intake_ffs():
    import glob
    intake_count = len(glob.glob(os.path.join(_REPO_ROOT, "summitleads", "intake", "*.json")))
    fixture_count = len(glob.glob(os.path.join(FIXTURES_DIR, "*.nowcerts.json")))
    assert intake_count > 0, "no intake FFs found -- check working directory"
    assert fixture_count == intake_count


def test_committed_fixtures_validate_against_schema():
    import glob
    jsonschema = pytest.importorskip("jsonschema")
    schema_path = os.path.join(FIXTURES_DIR, "SCHEMA.json")
    with open(schema_path) as f:
        schema = json.load(f)
    fixture_paths = glob.glob(os.path.join(FIXTURES_DIR, "*.nowcerts.json"))
    assert fixture_paths
    for path in fixture_paths:
        with open(path) as f:
            data = json.load(f)
        jsonschema.validate(data, schema)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
