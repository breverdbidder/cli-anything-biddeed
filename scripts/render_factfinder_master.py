#!/usr/bin/env python3
"""Render Winner Data Fact Finder HTML from templates/FACT_FINDER_MASTER_TEMPLATE.html.

Pilot scope (issue: Winner Data active/pending seller-trigger proof, Aug 2026):
two hand-verified Brevard County examples (one ACTIVE listing, one PENDING
listing), not a statewide pipeline. Data for each lead is supplied as a dict
-- this script does the template substitution only, no DB reads. A future
DB-driven version (read winnerdata.leads directly) is out of scope here.

Usage: python3 scripts/render_factfinder_master.py

Content safety: every render is scanned against a banned-terms list (vendor
names, internal file paths, HTTP status codes, queue IDs, API paths) before
being written. A match raises ContentSafetyError instead of writing the file
-- see content_safety_check(). The template is also gated on an "SSOT STATUS"
marker (see templates/FACT_FINDER_MASTER_TEMPLATE.html): render() refuses to
run at all until that marker reads "approved" (Ariel-only edit).
"""
import html
import os
import re

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "templates", "FACT_FINDER_MASTER_TEMPLATE.html")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "winnerdata", "factfinder")
REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")

CORE_FIELDS = [
    "lead_id", "first_name", "last_name", "entity_name", "phone", "email",
    "mailing_address", "risk_address_full", "producer_name", "prepared_date",
    "agency_name", "case_number", "year_built", "living_area_sqft",
    "county_just_value", "land_value", "purchase_price", "county",
    "policy_type", "construction_type",
]

# Vendor/tool names that must never appear in a rendered Fact Finder (Ariel
# directive, issue #19392: "I asked not to disclose our workflow or vendors.
# Never!"). Explicit names per that directive, plus every vendor referenced
# in this repo's root package.json / pyproject.toml / deploy .env.example as
# of the 2026-08-24 sanitization pass.
BANNED_VENDOR_TERMS = [
    "Tracerfy", "Bright Data", "BrightData", "HomeHarvest", "Supabase",
    "GitHub", "Cloudflare", "OpenAI", "Anthropic", "Claude",
    "Playwright", "freelawproject", "Juriscraper", "Eyecite",
]

# Internal engineering narrative that must never appear client-side: file
# paths, queue IDs, HTTP status codes, raw API paths.
BANNED_PATTERNS = [
    re.compile(r"\bscripts/[\w\-./]+"),
    re.compile(r"\bpipelines/[\w\-./]+"),
    re.compile(r"\bqueue_id\b", re.IGNORECASE),
    re.compile(r"\bHTTP\s*[45]\d{2}\b"),
    re.compile(r"/v1/api/[\w\-./{}]*"),
]

SSOT_APPROVED_RE = re.compile(r"SSOT STATUS:\s*approved", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


class ContentSafetyError(RuntimeError):
    """Raised when a rendered Fact Finder would leak vendor/internal content."""


class TemplateNotApprovedError(RuntimeError):
    """Raised when the master template's SSOT marker is not 'approved'."""


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


def content_safety_check(rendered_html, label):
    """Scan fully-rendered Fact Finder HTML for vendor names / internal narrative.

    Fails loudly (raises) instead of silently stripping -- a silent strip
    could still leak in some other field we didn't think to scrub.
    """
    hits = []
    for term in BANNED_VENDOR_TERMS:
        idx = rendered_html.find(term)
        if idx != -1:
            snippet = rendered_html[max(0, idx - 30):idx + len(term) + 30]
            hits.append(f"banned vendor term {term!r} at offset {idx}: ...{snippet}...")
    for pattern in BANNED_PATTERNS:
        m = pattern.search(rendered_html)
        if m:
            snippet = rendered_html[max(0, m.start() - 30):m.end() + 30]
            hits.append(f"banned pattern {pattern.pattern!r} matched {m.group(0)!r} at offset {m.start()}: ...{snippet}...")
    if hits:
        raise ContentSafetyError(
            f"content safety gate rejected render of {label!r} -- refusing to write file. "
            "Matches found:\n  " + "\n  ".join(hits)
        )


def _load_template():
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read()


def _check_ssot_approved(tpl):
    if not SSOT_APPROVED_RE.search(tpl):
        raise TemplateNotApprovedError(
            "BLOCKED: templates/FACT_FINDER_MASTER_TEMPLATE.html SSOT STATUS is not "
            "'approved'. Ariel must review and mark the master template approved before "
            "any Fact Finder can be generated from it -- see issue #19392."
        )


def _render_body(tpl, data):
    """Core render: strip dev-only HTML comments, substitute fields, safety-check."""
    out = HTML_COMMENT_RE.sub("", tpl)
    for field in CORE_FIELDS:
        out = out.replace("{{" + field + "}}", esc(data.get(field, "")))
    out = out.replace("{{missing_required_fields_block}}", missing_block(data.get("missing_required_fields", []), data.get("missing_note", "")))
    out = out.replace("{{compliance_notice_block}}", compliance_block(data.get("compliance_note", "")))
    content_safety_check(out, data.get("file", "unknown"))
    return out


def render(data):
    """Gated entry point: refuses to render unless the master template is SSOT-approved."""
    tpl = _load_template()
    _check_ssot_approved(tpl)
    return _render_body(tpl, data)


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
            "No public contact record was found through our standard verification process."
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
            "This phone number is listed on the Do Not Call registry. Contact must be made "
            "manually by a licensed producer only -- no automated dialing, texting, or email "
            "marketing without documented consent. A secondary number is on file if needed."
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
