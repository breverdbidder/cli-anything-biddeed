#!/usr/bin/env python3
"""Render Winner Data Fact Finder HTML from templates/FACT_FINDER_MASTER_TEMPLATE.html.

Pilot scope (issue: Winner Data active/pending seller-trigger proof, Aug 2026):
two hand-verified Brevard County examples (one ACTIVE listing, one PENDING
listing), not a statewide pipeline. Data for each lead is supplied as a dict
-- this script does the template substitution only, no DB reads. A future
DB-driven version (read winnerdata.leads directly) is out of scope here.

Usage: python3 scripts/render_factfinder_master.py
"""
import html
import os

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "templates", "FACT_FINDER_MASTER_TEMPLATE.html")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "winnerdata", "factfinder")

CORE_FIELDS = [
    "lead_id", "first_name", "last_name", "entity_name", "phone", "email",
    "mailing_address", "risk_address_full", "producer_name", "prepared_date",
    "agency_name", "case_number", "year_built", "living_area_sqft",
    "county_just_value", "land_value", "purchase_price", "county",
    "policy_type", "construction_type",
]


def esc(v):
    return html.escape(str(v)) if v is not None else ""


def missing_block(missing_fields, note):
    if not missing_fields:
        return ""
    fields = ", ".join(missing_fields)
    return (
        '<div class="missing"><h2>Missing Required Fields</h2>'
        f'<p>{esc(fields)} could not be verified for this lead. {esc(note)} '
        "This is reported honestly rather than left blank -- no fabricated contact data.</p></div>"
    )


def compliance_block(note):
    if not note:
        return ""
    return f'<div class="compliance"><strong>Compliance note:</strong> {esc(note)}</div>'


def render(data):
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        tpl = f.read()
    out = tpl
    for field in CORE_FIELDS:
        out = out.replace("{{" + field + "}}", esc(data.get(field, "")))
    out = out.replace("{{missing_required_fields_block}}", missing_block(data.get("missing_required_fields", []), data.get("missing_note", "")))
    out = out.replace("{{compliance_notice_block}}", compliance_block(data.get("compliance_note", "")))
    return out


LEADS = [
    {
        "file": "brevard-active-labelle-8268-brown-rd.html",
        "lead_id": "FF-WD-ACTIVE-2026-LABELLE-8268BROWNRD",
        "first_name": "James",
        "last_name": "Labelle, Sr",
        "entity_name": "Labelle James, SR",
        "phone": "NOT FOUND",
        "email": "NOT FOUND",
        "mailing_address": "8268 Brown Rd, Barefoot Bay, FL 32976",
        "risk_address_full": "8268 Brown Rd, Barefoot Bay, FL 32976",
        "producer_name": "Mariam Shapira",
        "prepared_date": "2026-08-24",
        "agency_name": "Protection Partners",
        "case_number": "N/A -- active MLS listing (MLS# 1082449, BCFL board), not a court case",
        "year_built": "1987",
        "living_area_sqft": "966",
        "county_just_value": "$135,220",
        "land_value": "$50,000",
        "purchase_price": "$92,000 (current list price -- sale not yet closed, no new deed of record)",
        "county": "Brevard",
        "policy_type": "HO3 (Homeowner) -- owner-occupied, own_addr1 matches phy_addr1 in fl_parcels",
        "construction_type": "DOR raw const_clas code 4 (no verified class-name crosswalk in this pipeline -- reporting the raw code rather than guessing a label)",
        "missing_required_fields": ["phone", "email"],
        "missing_note": (
            "Tracerfy enhanced (name+address) trace against Labelle James,SR / 8268 Brown RD, "
            "Barefoot Bay, FL 32976 returned hit=false across 4 attempts (original name order, "
            "swapped first/last, alternate city Micco, suffix variants). Confirmed no-hit, not a "
            "lookup error -- consistent with the documented method's real ceiling (not every seller "
            "resolves; ~88% hit rate observed elsewhere, this is in the ~12% miss)."
        ),
        "compliance_note": "",
    },
    {
        "file": "brevard-pending-latulip-2165-feast-rd.html",
        "lead_id": "FF-WD-PENDING-2026-LATULIP-2165FEASTRD",
        "first_name": "Bruce",
        "last_name": "Latulip",
        "entity_name": "Bruce Latulip",
        "phone": "(954) 701-4841",
        "email": "brucelatulip@gmail.com",
        "mailing_address": "2165 Feast Rd, W Melbourne, FL 32904",
        "risk_address_full": "2165 Feast Rd, Melbourne, FL 32904",
        "producer_name": "Mariam Shapira",
        "prepared_date": "2026-08-24",
        "agency_name": "Protection Partners",
        "case_number": "N/A -- pending MLS listing (MLS# 1083585, BCFL board), not a court case",
        "year_built": "1956",
        "living_area_sqft": "2,924",
        "county_just_value": "$147,880",
        "land_value": "$72,000",
        "purchase_price": "$280,000 (current list price -- sale pending, not yet closed)",
        "county": "Brevard",
        "policy_type": "HO3 (Homeowner) -- owner-occupied, own_addr1 matches phy_addr1 in fl_parcels",
        "construction_type": "DOR raw const_clas code 4 (no verified class-name crosswalk in this pipeline -- reporting the raw code rather than guessing a label)",
        "missing_required_fields": [],
        "missing_note": "",
        "compliance_note": (
            "Tracerfy enhanced trace returned this number flagged dnc=true (rank-1 mobile, "
            "Omnipoint Miami E License LLC). No consent on file for this seller. Manual dial by a "
            "licensed producer ONLY -- no autodialer, no SMS, no email drip, per the standing "
            "compliant_outbound rule. The official Tracerfy v2 DNC-scrub queue confirmation "
            "(queue_id 3904) returned HTTP 403 'no permission to access this queue' on 6 polls over "
            "2 minutes -- a genuine platform/permission gap, not a false negative; this DNC flag is "
            "sourced from the per-phone flag already embedded in the enhanced-trace response, not "
            "a completed async scrub. A secondary, non-DNC-flagged number is on file "
            "((321) 614-4827, T-Mobile, lower match rank) as a fallback if the primary is a dead end."
        ),
    },
]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for lead in LEADS:
        html_out = render(lead)
        out_path = os.path.join(OUT_DIR, lead["file"])
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_out)
        print(f"wrote {out_path} ({len(html_out)} bytes)")


if __name__ == "__main__":
    main()
