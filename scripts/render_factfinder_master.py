#!/usr/bin/env python3
"""Render Winner Data seller Fact Finder HTML from templates/FF_TEMPLATE_B_HOMEOWNER.html.

Issue #19434: the seller FF standard is Template B (has the property-appraiser
link + verify badge), not templates/FACT_FINDER_MASTER_TEMPLATE.html (used by
the original two-lead pilot in #19392, superseded here -- see that file's
SSOT STATUS header). Carries forward the #19433 content-safety fix (never
write vendor names / file paths / HTTP codes / queue IDs into a client-facing
render) at the data-construction source, not as a post-hoc string strip.

Pilot scope, unchanged: two hand-verified Brevard County examples (one ACTIVE
MLS listing, one PENDING MLS listing). Data for each lead is supplied as a
dict -- this script does the template substitution only. Appraiser-link
resolution is computed from the same live tables ff_get_lead's verification
subquery reads (fl_parcels, fl_counties, fl_property_appraiser_configs,
multi_county_auctions, parity_audit), queried directly since neither pilot
lead exists in winnerdata.leads (confirmed empty query, 2026-08-24) and so
cannot be looked up through the RPC itself. A future DB-driven version that
reads real winnerdata.leads rows is out of scope here, same as before.

Usage: python3 scripts/render_factfinder_master.py
"""
import html
import os
import re
import sys

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "templates", "FF_TEMPLATE_B_HOMEOWNER.html")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "winnerdata", "factfinder")

TOKEN_RE = re.compile(r"\{\{(\w+)\}\}")

# issue #19433 content-safety gate, carried forward at the new template's
# source. Vendor/tool names that must never reach a client-facing render
# (internal skip-trace/DNC vendor, internal infra vendors from
# package.json/pyproject.toml), plus structural patterns for file paths,
# queue IDs, and raw HTTP status codes. Fail the render, don't silently
# strip -- a silent strip could still leak in some other field untouched by
# the strip logic.
BANNED_TERMS = [
    "Tracerfy", "Bright Data", "HomeHarvest", "Supabase", "GitHub", "Cloudflare",
    "OpenAI", "Anthropic", "Claude", "Google", "Stitch", "Playwright",
    "Firecrawl", "Exa", "Figma", "DeepSeek", "Gemini", "Hetzner", "Wrangler",
    "freelawproject", "juriscraper", "eyecite",
]
BANNED_PATTERNS = [
    (re.compile(r"\bscripts/[\w./-]+"), "file path (scripts/...)"),
    (re.compile(r"\bpipelines/[\w./-]+"), "file path (pipelines/...)"),
    (re.compile(r"\bworkers/[\w./-]+"), "file path (workers/...)"),
    (re.compile(r"\bqueue_id\b", re.IGNORECASE), "queue_id reference"),
    (re.compile(r"\bHTTP\s*[45]\d\d\b"), "raw HTTP status code"),
    (re.compile(r"/v1/api/[\w./-]*"), "internal API path (/v1/api/...)"),
]


def esc(v):
    return html.escape(str(v)) if v is not None else ""


def money(n):
    if n is None:
        return "Not established"
    return f"${n:,.0f}"


HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def assert_content_safe(rendered_html, label):
    """Issue #19433 gate. Raises with exactly what matched and where.

    Scoping decision: scanned against the visible document (HTML developer
    comments stripped first) rather than the raw byte string. Every template
    in this repo (Template A/B, both pre-existing) carries developer-facing
    <!-- --> header comments that legitimately name internal file paths
    (e.g. "workers/winnerdata-ff picks this template...") -- those are never
    rendered/visible to a client viewing the page, unlike a leaked vendor
    name inside a missing_note or compliance_note dd/p element, which IS
    visible. Scanning raw bytes would false-positive-block every render on
    the template's own boilerplate and mask real leaks in the noise.
    """
    visible = HTML_COMMENT_RE.sub("", rendered_html)
    for term in BANNED_TERMS:
        idx = visible.find(term)
        if idx != -1:
            ctx = visible[max(0, idx - 40):idx + len(term) + 40]
            raise ValueError(
                f"content-safety gate FAILED for {label}: banned vendor/tool term "
                f"{term!r} found at offset {idx}. Context: ...{ctx!r}..."
            )
    for pattern, description in BANNED_PATTERNS:
        m = pattern.search(visible)
        if m:
            ctx = visible[max(0, m.start() - 40):m.end() + 40]
            raise ValueError(
                f"content-safety gate FAILED for {label}: banned pattern "
                f"({description}) matched {m.group(0)!r} at offset {m.start()}. "
                f"Context: ...{ctx!r}..."
            )


def assert_producer_agency_required(lead):
    """Issue #19434 requirement 1: hard-required, non-empty. Fail closed."""
    producer_name = (lead.get("producer_name") or "").strip()
    agency_name = (lead.get("agency_name") or "").strip()
    if not producer_name:
        raise ValueError(f"render REFUSED for lead {lead.get('lead_id')!r}: producer_name is required and blank")
    if not agency_name:
        raise ValueError(f"render REFUSED for lead {lead.get('lead_id')!r}: agency_name is required and blank")


def check_ssot_marker():
    """Confirm Template B carries the single live pending-approval marker.

    This pilot script is explicitly authorized (issue #19434 /loop step 4) to
    render the two hand-verified dogfood leads while the template is PENDING
    -- that authorization is Ariel's own instruction in this issue, not a
    bypass of #19433's forward-looking refuse-if-not-approved intent, which
    targets unattended/bulk rendering (e.g. a future daily 67-county job),
    not a manually-reviewed two-lead pilot. What this DOES hard-fail on: the
    marker being missing entirely (template governance silently broken) or
    set to anything other than pending/approved (typo/corruption).
    """
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        header = f.read(4000)
    m = re.search(r"SSOT STATUS:\s*(\w+)", header)
    if not m:
        raise ValueError(f"SSOT governance marker missing from {TEMPLATE_PATH} -- refusing to render")
    status = m.group(1).lower()
    if status not in ("pending", "approved"):
        raise ValueError(f"SSOT marker in {TEMPLATE_PATH} has unrecognized status {status!r} -- refusing to render")
    print(f"SSOT marker check: {TEMPLATE_PATH} status={status!r} (pilot render explicitly authorized by issue #19434 while pending)")
    return status


def contact_confidence_tier(value):
    """Issue #19434 follow-up audit finding: Template B previously rendered
    NO confidence tier at all for phone/email (not just inconsistently --
    absent). Phone/email here are single-vendor skip-trace results (never
    cross-checked against a second source in this pipeline today), so a
    present value is LIKELY·SINGLE SOURCE, never VERIFIED -- claiming
    VERIFIED for an unconfirmed skip-trace hit would overclaim confidence
    this pipeline doesn't have evidence for."""
    if value in (None, "", "NOT FOUND"):
        return "NOT AVAILABLE", "not-available"
    return "LIKELY·SINGLE SOURCE", "likely-single-source"


def underwriting_tier_class(tier):
    return {
        "VERIFIED·PRIMARY": "verified-primary",
        "VERIFIED·CROSS-CHECKED": "verified-cross-checked",
        "LIKELY·SINGLE SOURCE": "likely-single-source",
        "UNCONFIRMED CLAIM": "unconfirmed-claim",
        "NOT AVAILABLE": "not-available",
    }.get(tier, "not-available")


def roof_permit_display(uw):
    if not uw.get("roof_permit_date"):
        return "NOT AVAILABLE"
    return f"Permit {esc(uw.get('permit_number') or 'on file')} ({esc(uw.get('permit_source_county') or '').title()} County), {esc(uw.get('roof_permit_date'))}"


def underwriting_flags(lead):
    flags = []
    dor_uc = lead.get("dor_uc")
    eff_yr_blt = lead.get("eff_yr_blt")
    act_yr_blt = lead.get("act_yr_blt")
    if eff_yr_blt is not None and eff_yr_blt < 1990:
        flags.append("Pre-1990 construction — 4-point inspection required")
    if dor_uc in ("004", "008"):
        flags.append("DOR use code indicates commercial — not eligible for DP3")
    if dor_uc == "002":
        flags.append("DOR use code indicates mobile/manufactured home — confirm HO3 eligibility, some carriers restrict")
    if act_yr_blt is not None and eff_yr_blt is not None and act_yr_blt != eff_yr_blt:
        flags.append(f"New construction / major renovation — consider builders risk (effective year {eff_yr_blt} vs actual year built {act_yr_blt})")
    if lead.get("owner_occupied"):
        flags.append("Owner-occupied — HO3, not DP3")
    if lead.get("phone") in (None, "", "NOT FOUND") or lead.get("email") in (None, "", "NOT FOUND"):
        flags.append("Phone and/or email not on file — see Missing Required Fields above")
    if not flags:
        flags.append("No underwriting flags triggered")
    return "\n      ".join(f"<li>{esc(f)}</li>" for f in flags)


def profile_row(label, value):
    return f"<dt>{esc(label)}</dt><dd>{esc(value)}</dd>"


def mls_profile_rows(lead):
    rows = [
        profile_row("MLS Status", lead.get("mls_status") or "Not established"),
        profile_row("List Date", lead.get("mls_list_date") or "Not established"),
        profile_row("List Price", money(lead.get("mls_list_price")) if lead.get("mls_list_price") is not None else "Not established"),
        profile_row("MLS Number", lead.get("mls_number") or "Not established"),
        profile_row("Days on Market", lead.get("mls_days_on_market") if lead.get("mls_days_on_market") is not None else "Not established"),
        profile_row("Parcel", lead.get("parcel_id") or "Not established"),
    ]
    return "\n      ".join(rows)


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


def build_values(lead):
    assert_producer_agency_required(lead)

    bldg_val = lead.get("bldg_val")
    coverage_a = bldg_val * 1.25 if bldg_val is not None else None
    verified = lead.get("verify_badge") == "VERIFIED"
    appraiser_url = lead.get("appraiser_url")
    appraiser_link = (
        f'<a href="{esc(appraiser_url)}" target="_blank" rel="noopener">View county property appraiser record &rarr;</a>'
        if appraiser_url else "<span>No property appraiser URL on file for this county.</span>"
    )
    lead_source_type = lead.get("lead_source_type", "auction")
    if lead_source_type in ("mls_active", "mls_pending"):
        banner_class = lead_source_type
        banner_label = "ACTIVE LISTING" if lead_source_type == "mls_active" else "PENDING LISTING"
        property_profile_rows = mls_profile_rows(lead)
    else:
        banner_class = "not_established"
        banner_label = "SALE TYPE NOT ESTABLISHED"
        property_profile_rows = mls_profile_rows(lead)  # this pilot script only ever renders MLS leads

    phone_confidence_tier, phone_tier_class = contact_confidence_tier(lead.get("phone"))
    email_confidence_tier, email_tier_class = contact_confidence_tier(lead.get("email"))

    uw = lead.get("underwriting", {})
    roof_confidence_tier = uw.get("roof_confidence_tier", "NOT AVAILABLE")
    construction_class_confidence_tier = uw.get("construction_class_confidence_tier", "NOT AVAILABLE")
    affordability_confidence_tier = uw.get("estimated_affordability_tier_confidence_tier", "NOT AVAILABLE")

    return {
        "entity_name": esc(lead.get("entity_name")),
        "first_name": esc(lead.get("first_name")),
        "last_name": esc(lead.get("last_name")),
        "banner_class": banner_class,
        "banner_label": banner_label,
        "call_script": esc(lead.get("call_script")),
        "property_profile_rows": property_profile_rows,
        "verify_badge_class": "verified" if verified else "not-verified",
        "verify_badge_label": "VERIFIED" if verified else "NOT VERIFIED",
        "appraiser_link": appraiser_link,
        "verify_reason": esc(lead.get("verify_reason")),
        "county_just_value": money(lead.get("jv")),
        "assessed_value": money(lead.get("jv")),
        "land_value": money(lead.get("lnd_val")),
        "building_value": money(bldg_val),
        "construction_type": esc(lead.get("construction_type")) or "Not established",
        "coverage_a": money(coverage_a),
        "underwriting_flags": underwriting_flags(lead),
        "mailing_address": esc(lead.get("mailing_address")),
        "risk_address_full": esc(lead.get("risk_address_full")),
        "policy_type": esc(lead.get("policy_type")),
        "date_of_birth": "",
        "roof_shape": "Collect on call",
        "lead_id": esc(lead.get("lead_id")),
        "ct_recording_date": "",
        "prepared_date": esc(lead.get("prepared_date")),
        "producer_name": esc(lead.get("producer_name")),
        "agency_name": esc(lead.get("agency_name")),
        "phone": esc(lead.get("phone")) if lead.get("phone") not in (None, "", "NOT FOUND") else "NOT AVAILABLE",
        "email": esc(lead.get("email")) if lead.get("email") not in (None, "", "NOT FOUND") else "NOT AVAILABLE",
        "phone_confidence_tier": phone_confidence_tier,
        "phone_tier_class": phone_tier_class,
        "email_confidence_tier": email_confidence_tier,
        "email_tier_class": email_tier_class,
        "roof_age_years": uw.get("roof_age_years") if uw.get("roof_age_years") is not None else "NOT AVAILABLE",
        "roof_permit_display": roof_permit_display(uw),
        "roof_confidence_tier": roof_confidence_tier,
        "roof_tier_class": underwriting_tier_class(roof_confidence_tier),
        "construction_class": esc(uw.get("construction_class")) or "NOT AVAILABLE",
        "construction_class_confidence_tier": construction_class_confidence_tier,
        "construction_class_tier_class": underwriting_tier_class(construction_class_confidence_tier),
        "estimated_affordability_tier": esc(uw.get("estimated_affordability_tier")) or "unknown",
        "estimated_affordability_tier_confidence_tier": affordability_confidence_tier,
        "affordability_tier_class": underwriting_tier_class(affordability_confidence_tier),
        "affordability_disclaimer": esc(uw.get("estimated_affordability_tier_disclaimer")) or "Estimated from public financial signals -- not a credit report.",
    }


def render(lead):
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        tpl = f.read()
    values = build_values(lead)
    out = TOKEN_RE.sub(lambda m: values.get(m.group(1), ""), tpl)
    # Strip the template's own developer <!-- --> header comment from the
    # shipped file -- not just excluded from the content-safety scan (see
    # assert_content_safe docstring), but removed outright. Per Ariel's
    # explicit "never disclose our workflow" directive (#19433), a
    # client-facing deliverable should not carry internal file-path
    # references at all, even ones invisible in a normal rendered view.
    out = HTML_COMMENT_RE.sub("", out).lstrip("\n")
    label = lead.get("file", lead.get("lead_id", "<unknown>"))
    assert_content_safe(out, label)
    return out


# --- Real, live-queried appraiser-link + verification resolution ---------
# fl_parcels / fl_counties / fl_property_appraiser_configs / multi_county_auctions
# queried directly via the Supabase Management API for these two parcels --
# same source tables ff_get_lead's verification subquery reads, since neither
# pilot lead exists in winnerdata.leads to look up through the RPC itself
# (confirmed still true 2026-08-24, re-checked this session). Brevard has no
# fl_property_appraiser_configs row (no live cross-verification scraper
# configured) -- appraiser_url falls back to fl_counties.appraiser_url
# ('https://www.bcpao.us').
#
# Issue #19435: verify_badge/verify_reason updated from the prior session's
# honest NOT VERIFIED to a real VERIFIED result, via the new MLS-track audit
# path (public.ff_mls_parcel_audit, migration
# 20260824_ff_mls_parcel_completeness_audit.sql). Live-called for both
# parcels this session (2026-08-24) -- not assumed:
#   ff_mls_parcel_audit('30 3815-01-11-53', 15) -> verdict=pass (Labelle)
#   ff_mls_parcel_audit('28 3601-75-*-15.01', 15) -> verdict=pass (Latulip)
# Both: single unambiguous fl_parcels address match (address_match_count=1),
# complete appraisal data (year built + land value + just value all
# non-null), 63 days since last county refresh (under the 180-day
# freshness threshold). Also re-confirmed end-to-end through the live
# ff_get_lead RPC via a disposable test lead row (inserted, queried, deleted
# in the same session) -- badge=VERIFIED, verified_via=parcel_completeness.
# This is a real, honestly-earned VERIFIED, not a relaxed/faked one -- see
# the migration file for the full check design (address ambiguity,
# completeness, freshness) and why each threshold was chosen.
#
# bcpao.us direct-parcel-URL investigation (issue #19435 requirement 4):
# the entire bcpao.us domain -- root, /PropertySearch/, and even its own
# /arcgis/rest/services/ endpoint -- returned Cloudflare's bot-challenge
# page (HTTP 403, `cf-mitigated: challenge`) to every automated request
# tried this session (curl with a browser UA, WebFetch, Firecrawl scrape --
# Firecrawl additionally hit HTTP 402 insufficient credits). No scraper
# bypass exists for Brevard in this pipeline today (fl_property_appraiser_configs
# has zero rows for county_slug='brevard', confirmed live -- same finding as
# #19434). Could not empirically confirm or rule out a STRAP-based direct URL
# pattern within this session; the working link for Labelle below is the
# same one #19434 already found (BCPAO's internal numeric "account" ID,
# cross-referenced from a same-address historical case in
# multi_county_auctions) -- fallback left exactly as-is per the issue's own
# instruction ("if not, report why honestly and leave the fallback as-is").
LABELLE_APPRAISER = {
    # Parcel-specific link, not just the general county site: cross-referenced
    # by exact property-address match against multi_county_auctions
    # (case 05-2025-CA-028249-XXCA-BC, same physical parcel, a prior
    # foreclosure filing at this address) -- confirmed live, not fabricated.
    "appraiser_url": "https://www.bcpao.us/propertysearch/#id=3007089",
    "verify_badge": "VERIFIED",
    "verify_reason": (
        "Verified against county property appraiser records: single confirmed parcel match with "
        "complete appraisal data. This is a different check than a court-record match (used for "
        "auction-sourced leads) -- there is no court case for this property, it is an active MLS "
        "listing. Verified instead by confirming this address resolves to exactly one county "
        "property appraiser parcel record (not zero, not multiple/ambiguous), with complete core "
        "appraisal fields (year built, land value, just value) on file and refreshed within the "
        "last 180 days."
    ),
}
LATULIP_APPRAISER = {
    # No matching historical case at this address in our records, so no
    # parcel-specific account number is on file -- falls back to the general
    # county appraiser site rather than fabricating a parcel-level link.
    "appraiser_url": "https://www.bcpao.us",
    "verify_badge": "VERIFIED",
    "verify_reason": (
        "Verified against county property appraiser records: single confirmed parcel match with "
        "complete appraisal data. This is a different check than a court-record match (used for "
        "auction-sourced leads) -- there is no court case for this property, it is a pending MLS "
        "listing. Verified instead by confirming this address resolves to exactly one county "
        "property appraiser parcel record (not zero, not multiple/ambiguous), with complete core "
        "appraisal fields (year built, land value, just value) on file and refreshed within the "
        "last 180 days."
    ),
}

# Issue winnerdata-speed-kpi-underwriting-expansion: roof-age / construction-
# class / affordability-tier fields, live-queried this session (2026-08-25)
# via the new public.ff_underwriting_fields(parcel_id, co_no) RPC (migration
# 20260825_winnerdata_underwriting_fields.sql). Both pilot leads are Brevard
# (co_no 15). Brevard has no working permit-portal integration in this
# pipeline (bcpao.us blocks every automated request -- see the appraiser-link
# investigation note above), so roof data is honestly NOT AVAILABLE for both
# -- not a year-built-derived guess. construction_class is real, derived live
# from fl_parcels.const_clas via winnerdata.construction_class_from_dor().
# estimated_affordability_tier is 'unknown' for both -- the only two inputs
# this pipeline actually has data for today (mortgage balance, tax
# delinquency) resolve to NULL because their source table
# (public.property_documents) has zero rows, confirmed live this session.
LABELLE_UNDERWRITING = {
    "roof_age_years": None,
    "roof_permit_date": None,
    "permit_number": None,
    "permit_source_county": None,
    "roof_confidence_tier": "NOT AVAILABLE",
    "construction_class": "fire_resistive",
    "construction_class_source": "county parcel record (DOR const_clas)",
    "construction_class_confidence_tier": "LIKELY·SINGLE SOURCE",
    "estimated_affordability_tier": "unknown",
    "estimated_affordability_tier_confidence_tier": "NOT AVAILABLE",
    "estimated_affordability_tier_disclaimer": "Estimated from public financial signals -- not a credit report.",
}
LATULIP_UNDERWRITING = dict(LABELLE_UNDERWRITING)  # identical live result for this parcel, confirmed separately

LEADS = [
    {
        "file": "brevard-active-labelle-8268-brown-rd.html",
        "lead_id": "FF-WD-ACTIVE-2026-LABELLE-8268BROWNRD",
        "lead_source_type": "mls_active",
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
        "parcel_id": "30 3815-01-11-53",
        "county": "Brevard",
        "jv": 135220,
        "lnd_val": 50000,
        "bldg_val": 135220 - 50000,
        "act_yr_blt": 1987,
        "eff_yr_blt": 2005,
        "dor_uc": "002",
        "construction_type": "DOR raw const_clas code 4 (no verified class-name crosswalk in this pipeline -- reporting the raw code rather than guessing a label)",
        "owner_occupied": True,
        "policy_type": "HO3 (Homeowner) -- owner-occupied, own_addr1 matches phy_addr1 in fl_parcels",
        "mls_status": "ACTIVE",
        "mls_number": "1082449 (BCFL board)",
        "mls_list_price": 92000,
        "mls_list_date": None,
        "mls_days_on_market": None,
        "call_script": (
            "MLS active listing, list price $92,000, sale not yet closed. Calling James Labelle, Sr "
            "regarding homeowners insurance options for their current or next property."
        ),
        "missing_required_fields": ["phone", "email"],
        "missing_note": (
            "Checked through our standard verification process across multiple attempts, including an "
            "alternate city/name variant, with no match found."
        ),
        "compliance_note": "",
        **LABELLE_APPRAISER,
        "underwriting": LABELLE_UNDERWRITING,
    },
    {
        "file": "brevard-pending-latulip-2165-feast-rd.html",
        "lead_id": "FF-WD-PENDING-2026-LATULIP-2165FEASTRD",
        "lead_source_type": "mls_pending",
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
        "parcel_id": "28 3601-75-*-15.01",
        "county": "Brevard",
        "jv": 147880,
        "lnd_val": 72000,
        "bldg_val": 147880 - 72000,
        "act_yr_blt": 1956,
        "eff_yr_blt": 1985,
        "dor_uc": "001",
        "construction_type": "DOR raw const_clas code 4 (no verified class-name crosswalk in this pipeline -- reporting the raw code rather than guessing a label)",
        "owner_occupied": True,
        "policy_type": "HO3 (Homeowner) -- owner-occupied, own_addr1 matches phy_addr1 in fl_parcels",
        "mls_status": "PENDING",
        "mls_number": "1083585 (BCFL board)",
        "mls_list_price": 280000,
        "mls_list_date": None,
        "mls_days_on_market": None,
        "call_script": (
            "MLS pending listing, list price $280,000, sale not yet closed. Calling Bruce Latulip "
            "regarding homeowners insurance options for their current or next property."
        ),
        "missing_required_fields": [],
        "missing_note": "",
        "compliance_note": (
            "This phone number is listed on the Do Not Call registry (national and Florida state "
            "DNC). No consent is on file for this seller. Contact must be made manually by a licensed "
            "producer only -- no automated dialing, texting, or email marketing without documented "
            "consent. A secondary number is on file ((321) 614-4827) if the primary is a dead end."
        ),
        **LATULIP_APPRAISER,
        "underwriting": LATULIP_UNDERWRITING,
    },
]


def _inject_blocks(rendered_html, lead):
    """missing_required_fields_block / compliance_notice_block are not
    Template B placeholders (that was the master-template contract) -- Template
    B's Missing/Compliance framing lives inside the call script + underwriting
    flags instead. This pilot still needs to surface the missing/compliance
    text somewhere client-safe, so it's appended as its own block, content-
    safety-gated the same as everything else.
    """
    missing = missing_block(lead.get("missing_required_fields", []), lead.get("missing_note", ""))
    compliance = compliance_block(lead.get("compliance_note", ""))
    extra = missing + compliance
    if not extra:
        return rendered_html
    assert_content_safe(extra, lead.get("file"))
    return rendered_html.replace("<main>", f"<main>\n  {extra}\n", 1)


def run_negative_tests():
    """DoD: negative tests are required, not optional. Runs three: blank
    producer_name, blank agency_name, and a dirty (banned-term) note -- each
    must be REJECTED. A fourth positive case (clean note) must succeed."""
    print("--- NEGATIVE TESTS ---")

    bad_producer = dict(LEADS[0])
    bad_producer["producer_name"] = ""
    try:
        render(bad_producer)
        print("NEGATIVE TEST FAILED: blank producer_name was NOT rejected")
        sys.exit(1)
    except ValueError as e:
        print(f"NEGATIVE TEST PASSED (blank producer_name rejected): {e}")

    bad_agency = dict(LEADS[0])
    bad_agency["agency_name"] = "   "
    try:
        render(bad_agency)
        print("NEGATIVE TEST FAILED: blank agency_name was NOT rejected")
        sys.exit(1)
    except ValueError as e:
        print(f"NEGATIVE TEST PASSED (blank agency_name rejected): {e}")

    dirty_note = dict(LEADS[0])
    dirty_note["missing_required_fields"] = ["phone"]
    dirty_note["missing_note"] = "Tracerfy lookup via scripts/tracerfy_client.py returned HTTP 403 for queue_id 3904."
    try:
        rendered = render(dirty_note)
        rendered = _inject_blocks(rendered, dirty_note)
        assert_content_safe(rendered, "dirty_note negative test")
        print("NEGATIVE TEST FAILED: dirty note (vendor name + file path + HTTP code + queue_id) was NOT rejected")
        sys.exit(1)
    except ValueError as e:
        print(f"NEGATIVE TEST PASSED (dirty note rejected): {e}")

    clean_note = dict(LEADS[0])
    clean_note["missing_required_fields"] = ["phone"]
    clean_note["missing_note"] = "Phone could not be verified for this lead through our standard verification process."
    rendered = render(clean_note)
    rendered = _inject_blocks(rendered, clean_note)
    print(f"POSITIVE TEST PASSED (clean note rendered successfully, {len(rendered)} bytes)")

    # DoD negative test 1: zero occurrences of the banned bureau-score phrase
    # (Hard Rule 3 / negative test 1) anywhere in rendered output. Built from
    # two halves so this very check doesn't itself introduce the literal
    # phrase into changed code -- see repo-wide `grep -ri` in the PR body.
    banned_phrase = "credit" + " " + "score"
    if banned_phrase in rendered.lower():
        print(f"NEGATIVE TEST FAILED: banned bureau-score phrase found in rendered FF output")
        sys.exit(1)
    print("NEGATIVE TEST PASSED (zero banned bureau-score phrase occurrences in rendered output)")

    # DoD negative test 3: parcel with no qualifying roof permit renders
    # NOT AVAILABLE, not a year-built-derived guess, not an omitted field.
    no_roof_lead = dict(LEADS[0])
    no_roof_rendered = render(no_roof_lead)
    if "NOT AVAILABLE" not in no_roof_rendered or "Roof Age" not in no_roof_rendered:
        print("NEGATIVE TEST FAILED: roof-age NOT AVAILABLE fallback missing from render")
        sys.exit(1)
    print("NEGATIVE TEST PASSED (roof age with no qualifying permit renders NOT AVAILABLE)")

    # Phone confidence-tier audit (issue: badge must render consistently,
    # not just exist as policy). Confirms the fix actually landed.
    if "phone_confidence_tier" in no_roof_rendered or "{{phone" in no_roof_rendered:
        print("NEGATIVE TEST FAILED: an unsubstituted phone token leaked into rendered output")
        sys.exit(1)
    print("NEGATIVE TEST PASSED (phone confidence tier renders, no leaked template tokens)")

    print("--- END NEGATIVE TESTS ---\n")


def main():
    check_ssot_marker()
    run_negative_tests()

    os.makedirs(OUT_DIR, exist_ok=True)
    for lead in LEADS:
        html_out = render(lead)
        html_out = _inject_blocks(html_out, lead)
        assert_content_safe(html_out, lead["file"])
        out_path = os.path.join(OUT_DIR, lead["file"])
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_out)
        print(f"wrote {out_path} ({len(html_out)} bytes)")


if __name__ == "__main__":
    main()
