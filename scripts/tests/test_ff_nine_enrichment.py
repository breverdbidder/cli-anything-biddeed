"""Focused tests for the 2026-08-26 nine-case FF enrichment/render pipeline.

Covers the gaps this session's mission called out explicitly:
  - Tracerfy name-normalization must go through tracerfy_client (the module
    that already fixed the surname-first parsing bug), not a duplicate,
    naive re-implementation -- that duplication is the exact contract-
    mismatch bug this session repaired in ff_nine_portfolio_enrichment.py.
  - One PDF/report record per case_number, never merged across sibling
    cases for the same buyer (Mundi Marketing LLC, OK Business LLC each
    hold 2 of the 9 cases).
  - Idempotent report construction: re-deriving records from the same input
    rows twice must not duplicate sibling_case_numbers or change results.
  - Blank-over-wrong: an unresolved buyer must never get a fabricated
    mailing address/tier.
"""
import os
import sys
from unittest.mock import patch

from pytest import raises as pytest_raises

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ff_nine_portfolio_enrichment as enrich  # noqa: E402
import render_ff_9buyer_20260827 as render  # noqa: E402
import tracerfy_client  # noqa: E402


def test_split_owner_name_surname_first_not_reversed():
    """Regression guard for the exact bug this session's fix prevents
    reintroducing: 'DAVIS, RONALD L.' must split to first=RONALD, last=DAVIS,
    never first='DAVIS,' last='RONALD L.'."""
    first, last = tracerfy_client._split_owner_name("DAVIS, RONALD L.")
    assert first == "RONALD"
    assert last == "DAVIS,".rstrip(",")


def test_split_owner_name_suffix_after_comma_not_treated_as_first_name():
    first, last = tracerfy_client._split_owner_name("Labelle James,SR")
    assert last == "Labelle"
    assert first == "James"


def test_enrichment_tracerfy_wrapper_delegates_to_client_not_reimplemented():
    """ff_nine_portfolio_enrichment.tracerfy() must call tracerfy_client.trace_lead
    (proven name-split + Cloudflare-safe UA) rather than parsing the name itself."""
    with patch.object(enrich, "TRACERFY_KEY", "fake-key-for-test"), \
         patch.object(enrich.ff_credit_ledger, "spend", return_value={"granted": True}), \
         patch.object(enrich.tracerfy_client, "trace_lead") as mock_trace:
        mock_trace.return_value = {"phone": "5551234567", "email": "a@b.com", "full_name": "RONALD DAVIS", "parse_status": "OK", "cost_cents": 1500}
        result = enrich.tracerfy("DAVIS, RONALD L.", "1 Main St", "Orlando", "FL", "32801")
    mock_trace.assert_called_once_with("DAVIS, RONALD L.", "1 Main St", "Orlando", "FL", "32801")
    assert result["status"] == "OK"
    assert result["phone"] == "5551234567"


def test_enrichment_tracerfy_wrapper_no_address_never_calls_client():
    """Never-purchases-just-bought-address invariant: no address anchor -> no call at all."""
    with patch.object(enrich, "TRACERFY_KEY", "fake-key-for-test"), \
         patch.object(enrich.tracerfy_client, "trace_lead") as mock_trace:
        result = enrich.tracerfy("SOME BUYER", None, None, None, None)
    mock_trace.assert_not_called()
    assert result["status"] == "SKIPPED_NO_TRACERFY_OR_PRIOR_ADDRESS"


def _rows_two_buyers_three_cases():
    return [
        {"case_number": "24000615", "county": "highlands", "winning_bidder": "Mundi Marketing LLC",
         "resolved_entity_name": "MUNDI MARKETING LLC", "resolved_principal_name": "Lorena Lopes",
         "identity_type": "business", "registered_agent_name": "Lorena Lopes",
         "registered_agent_address": "6560 Sand Lake Sound Rd, Orlando, FL 32819", "principal_home_address": None,
         "phone": "3213200530", "phone_validity": "current_mobile_no_dnc_no_tcpa", "email": None, "contact_provider": "tracerfy",
         "property_address": "6929 Cortez Blvd", "tier1_sold_amount": 5700, "sale_type": "tax_deed",
         "dor_luse_desc": "VACANT", "val_market": 14000, "val_assessed": 14000},
        {"case_number": "24000637", "county": "highlands", "winning_bidder": "Mundi Marketing LLC",
         "resolved_entity_name": "MUNDI MARKETING LLC", "resolved_principal_name": "Lorena Lopes",
         "identity_type": "business", "registered_agent_name": "Lorena Lopes",
         "registered_agent_address": "6560 Sand Lake Sound Rd, Orlando, FL 32819", "principal_home_address": None,
         "phone": "3213200530", "phone_validity": "current_mobile_no_dnc_no_tcpa", "email": None, "contact_provider": "tracerfy",
         "property_address": "OTHER ADDR", "tier1_sold_amount": 8100, "sale_type": "tax_deed",
         "dor_luse_desc": "VACANT", "val_market": 14000, "val_assessed": 14000},
        {"case_number": "24000618", "county": "highlands", "winning_bidder": "ellen horwitz",
         "resolved_entity_name": None, "resolved_principal_name": None,
         "identity_type": "person", "registered_agent_name": None,
         "registered_agent_address": None, "principal_home_address": None,
         "phone": None, "phone_validity": None, "email": None, "contact_provider": None,
         "property_address": "SOME ADDR", "tier1_sold_amount": 8100, "sale_type": "tax_deed",
         "dor_luse_desc": "VACANT", "val_market": 14000, "val_assessed": 14000},
    ]


def test_load_report_from_db_one_record_per_case_not_per_buyer():
    with patch.object(render, "_sql", return_value=_rows_two_buyers_three_cases()):
        out = render.load_report_from_db("2026-08-26")
    assert len(out) == 3
    case_numbers = sorted(r["case_numbers"][0] for r in out)
    assert case_numbers == ["24000615", "24000618", "24000637"]
    # each record's own property table has exactly its own case, never merged
    for r in out:
        assert len(r["properties"]) == 1
        assert r["properties"][0]["case_number"] == r["case_numbers"][0]


def test_load_report_from_db_sibling_cases_tracked_not_merged():
    with patch.object(render, "_sql", return_value=_rows_two_buyers_three_cases()):
        out = render.load_report_from_db("2026-08-26")
    mundi_615 = next(r for r in out if r["case_numbers"][0] == "24000615")
    mundi_637 = next(r for r in out if r["case_numbers"][0] == "24000637")
    assert mundi_615["sibling_case_numbers"] == ["24000637"]
    assert mundi_637["sibling_case_numbers"] == ["24000615"]
    ellen = next(r for r in out if r["case_numbers"][0] == "24000618")
    assert ellen["sibling_case_numbers"] == []


def test_load_report_from_db_idempotent():
    with patch.object(render, "_sql", return_value=_rows_two_buyers_three_cases()):
        out1 = render.load_report_from_db("2026-08-26")
        out2 = render.load_report_from_db("2026-08-26")
    assert out1 == out2


def test_unresolved_buyer_gets_no_fabricated_mailing_tier():
    """Blank-over-wrong: a buyer with no registered_agent_address and no
    principal_home_address must render mailing_tier=None, never a fabricated
    VERIFIED badge with a NOT AVAILABLE value (the exact bug found and fixed
    this session for Hart Land Development / Mundi Marketing)."""
    with patch.object(render, "_sql", return_value=_rows_two_buyers_three_cases()):
        out = render.load_report_from_db("2026-08-26")
    ellen = next(r for r in out if r["case_numbers"][0] == "24000618")
    assert ellen["mailing_address"] is None
    assert ellen["mailing_tier"] is None


def test_resolved_buyer_mailing_address_matches_its_tier_claim():
    with patch.object(render, "_sql", return_value=_rows_two_buyers_three_cases()):
        out = render.load_report_from_db("2026-08-26")
    mundi = next(r for r in out if r["case_numbers"][0] == "24000615")
    assert mundi["mailing_tier"] == "VERIFIED·CROSS-CHECKED"
    assert mundi["mailing_address"]["addr1"] == "6560 Sand Lake Sound Rd, Orlando, FL 32819"


def test_candidate_address_marked_unconfirmed_not_verified():
    rows = _rows_two_buyers_three_cases()
    rows[0]["registered_agent_address"] = None
    rows[0]["principal_home_address"] = "341 Broward Rd, Jacksonville, FL 32218 (candidate, multi-source corroborated, not deed-recorded)"
    with patch.object(render, "_sql", return_value=rows):
        out = render.load_report_from_db("2026-08-26")
    r = next(r for r in out if r["case_numbers"][0] == "24000615")
    assert r["mailing_tier"] == "UNCONFIRMED CLAIM"


def test_slug_includes_case_number_no_collision_for_shared_buyer():
    slug_615 = render.slugify("MUNDI MARKETING LLC") + "-" + render.slugify("24000615")
    slug_637 = render.slugify("MUNDI MARKETING LLC") + "-" + render.slugify("24000637")
    assert slug_615 != slug_637


# --- Web-search cross-check step (issue #19533) ---------------------------

def test_web_search_cross_check_not_eligible_when_already_resolved():
    row = {"business_phone": "(813) 831-3885", "resolved_principal_name": "Vincent J. Cassidy"}
    eligible, reason = enrich.web_search_cross_check_eligible(row)
    assert eligible is False
    assert "already resolved" in reason


def test_web_search_cross_check_not_eligible_without_named_individual():
    row = {"business_phone": None, "business_website": None, "business_email": None,
           "resolved_principal_name": None, "registered_agent_name": None}
    eligible, reason = enrich.web_search_cross_check_eligible(row)
    assert eligible is False
    assert "no named individual" in reason


def test_web_search_cross_check_eligible_when_unresolved_with_named_principal():
    row = {"business_phone": None, "business_website": None, "business_email": None,
           "resolved_principal_name": "Vincent J. Cassidy", "registered_agent_name": None}
    eligible, reason = enrich.web_search_cross_check_eligible(row)
    assert eligible is True
    assert "Cassidy" in reason


def test_web_search_cross_check_rejects_single_source():
    with pytest_raises(ValueError, match="2\\+ independent"):
        enrich.validate_web_search_cross_check(["https://prweb.com/x"])


def test_web_search_cross_check_rejects_related_entity_without_note():
    with pytest_raises(ValueError, match="relationship note"):
        enrich.validate_web_search_cross_check(
            ["https://prweb.com/x", "https://business-wise.org/y"], is_related_entity=True)


def test_web_search_cross_check_accepts_two_sources_with_relationship_note():
    entry = enrich.build_web_search_evidence_entry(
        sources=["https://prweb.com/x", "https://business-wise.org/y"],
        fields_supported=["business_phone", "business_website"],
        match_method="exact_name_plus_related_entity",
        is_related_entity=True,
        relationship_note="President/CEO of Majesty Title Services, a related entity Cassidy also controls.",
    )
    assert entry["confidence"] == "verified_cross_checked_two_independent_sources"
    assert entry["note"].startswith("President/CEO")
    assert set(entry["fields_supported"]) == {"business_phone", "business_website"}


def test_render_extracts_related_entity_note_from_evidence_ledger_by_shape():
    """render_ff_9buyer_20260827._related_entity_contact_note scans by shape
    (note + fields_supported), not by a hardcoded key name -- it must find
    an entry built by build_web_search_evidence_entry under any key."""
    entry = enrich.build_web_search_evidence_entry(
        sources=["https://prweb.com/x", "https://business-wise.org/y"],
        fields_supported=["business_phone", "business_website"],
        match_method="exact_name_plus_related_entity",
        is_related_entity=True,
        relationship_note="President/CEO of a related company.",
    )
    ledger = {"some_case_specific_key": entry}
    note = render._related_entity_contact_note(ledger)
    assert note == "President/CEO of a related company."
