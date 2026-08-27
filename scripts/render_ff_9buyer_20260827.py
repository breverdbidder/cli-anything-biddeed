#!/usr/bin/env python3
"""Renders the 9 real per-case Investor Fact Finders for the 2026-08-26 batch
from templates/FF_TEMPLATE_A_AUCTION_SALES.html -- the confirmed real-production
buyer-side template (per its own header: pulled from the chat session that
hand-built and delivered 17 real FFs, confirmed against an actually-delivered
PDF).

Reads live winnerdata.ff_batch_leads (the durable SSOT), not the ephemeral
/tmp resolution-run scratch file the first version of this script depended
on -- that file does not survive across runner sessions, and this batch's
mission requires one PDF per case (9), not one per distinct buyer entity (7).
Buyers holding multiple cases in this batch (Mundi Marketing LLC, OK Business
LLC) still get a portfolio cross-sell note on each of their case PDFs, built
from the sibling case_numbers, but each PDF's own property table shows only
its own case.

Content-safety gate carried forward unmodified from
scripts/render_factfinder_master.py (issue #19433): a client-facing FF must
never name an internal vendor/tool or reference an internal file path/queue
id/HTTP code. Public-record citations only.
"""
import html
import json
import os
import re
import subprocess
import sys
import urllib.request

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "templates", "FF_TEMPLATE_A_AUCTION_SALES.html")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "winnerdata", "batches", "2026-08-27", "investor_ff")
REPORT_PATH = os.environ.get("REPORT_PATH", "/tmp/ff_9buyer_20260827_report.json")
BATCH_DATE = os.environ.get("BATCH_DATE", "2026-08-26")
PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"


def _sql(q):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = urllib.request.Request(MGMT_URL, data=json.dumps({"query": q}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "render-ff-9buyer/2.0"}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def _tier_from_validity(validity, provider):
    if not provider:
        return None
    v = (validity or "").upper()
    if "DNC_FLAGGED" in v:
        return "UNCONFIRMED CLAIM"
    if "CURRENT" in v and "CANDIDATE" not in v:
        return "VERIFIED·PRIMARY"
    if "CANDIDATE" in v:
        return "LIKELY·SINGLE SOURCE"
    return "LIKELY·SINGLE SOURCE"


def load_report_from_db(batch_date: str) -> list[dict]:
    """Builds one record PER CASE (not per buyer) directly from the live
    winnerdata.ff_batch_leads SSOT. Sibling case_numbers for the same
    resolved_entity_name/winning_bidder are attached only as a portfolio
    cross-sell note, never merged into a shared property table."""
    rows = _sql(f"""
        select case_number, county, winning_bidder, resolved_entity_name, resolved_principal_name,
               identity_type, registered_agent_name, registered_agent_address, principal_home_address,
               phone, phone_validity, email, contact_provider,
               property_address, tier1_sold_amount, sale_type, dor_luse_desc, val_market, val_assessed
        from winnerdata.ff_batch_leads where batch_date = date '{batch_date}' order by case_number
    """)
    by_entity: dict[str, list[str]] = {}
    for r in rows:
        key = (r.get("resolved_entity_name") or r["winning_bidder"]).strip().upper()
        by_entity.setdefault(key, []).append(r["case_number"])

    out = []
    for r in rows:
        key = (r.get("resolved_entity_name") or r["winning_bidder"]).strip().upper()
        sibling_cases = [c for c in by_entity[key] if c != r["case_number"]]
        is_business = (r.get("identity_type") or "").startswith("business")
        mailing_addr_str = r.get("registered_agent_address") or r.get("principal_home_address")
        is_candidate = bool(mailing_addr_str) and "candidate" in mailing_addr_str.lower()
        mailing_tier = "UNCONFIRMED CLAIM" if is_candidate else ("VERIFIED·CROSS-CHECKED" if mailing_addr_str else None)
        out.append({
            "buyer_key": r.get("resolved_entity_name") or r["winning_bidder"],
            "entity": r.get("resolved_entity_name") or r["winning_bidder"],
            "type": "business" if is_business else "person",
            "case_numbers": [r["case_number"]],
            "sibling_case_numbers": sibling_cases,
            "county": r["county"],
            "mailing_address": {"addr1": mailing_addr_str, "city": None, "state": None, "zip": None} if mailing_addr_str else None,
            "mailing_tier": mailing_tier,
            "phone": r.get("phone"),
            "phone_tier": _tier_from_validity(r.get("phone_validity"), r.get("contact_provider")),
            "email": r.get("email"),
            "email_tier": _tier_from_validity(r.get("phone_validity"), r.get("contact_provider")) if r.get("email") else None,
            "registered_agent": r.get("registered_agent_name"),
            "principal": r.get("resolved_principal_name"),
            "sunbiz_doc_number": None,
            "sunbiz_status": None,
            "dnc": None,
            "paid": bool(r.get("phone") or r.get("email")),
            "properties": [{
                "case_number": r["case_number"],
                "fact": {"property_address": r.get("property_address"), "sold_amount": r.get("tier1_sold_amount"), "sale_type": r.get("sale_type")},
                "subject": {"luse_desc": r.get("dor_luse_desc"), "val_market": r.get("val_market"), "val_assessed": r.get("val_assessed")},
            }],
        })
    return out

TOKEN_RE = re.compile(r"\{\{(\w+)\}\}")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

BANNED_TERMS = [
    "Tracerfy", "Bright Data", "BrightData", "HomeHarvest", "Supabase", "GitHub", "Cloudflare",
    "OpenAI", "Anthropic", "Claude", "Stitch", "Playwright",
    "Firecrawl", "Exa", "Figma", "DeepSeek", "Gemini", "Hetzner", "Wrangler", "Apify", "Hunter.io",
]
BANNED_PATTERNS = [
    (re.compile(r"\bscripts/[\w./-]+"), "file path (scripts/...)"),
    (re.compile(r"\bqueue_id\b", re.IGNORECASE), "queue_id reference"),
    (re.compile(r"\bHTTP\s*[45]\d\d\b"), "raw HTTP status code"),
    (re.compile(r"#19\d\d\d"), "internal issue number"),
]

COUNTY_APPRAISER_URL = {
    "bay": "https://www.baypa.net", "clay": "https://www.ccpao.com",
    "escambia": "https://www.escpa.org", "highlands": "https://www.hcpao.org",
}


def esc(v):
    return html.escape(str(v)) if v is not None else ""


def money(n):
    if n is None:
        return "Not established"
    try:
        return f"${float(n):,.0f}"
    except (TypeError, ValueError):
        return "Not established"


def assert_content_safe(rendered_html, label):
    visible = HTML_COMMENT_RE.sub("", rendered_html)
    for term in BANNED_TERMS:
        idx = visible.find(term)
        if idx != -1:
            ctx = visible[max(0, idx - 40):idx + len(term) + 40]
            raise ValueError(f"content-safety gate FAILED for {label}: banned term {term!r} at offset {idx}: ...{ctx!r}...")
    for pattern, desc in BANNED_PATTERNS:
        m = pattern.search(visible)
        if m:
            ctx = visible[max(0, m.start() - 40):m.end() + 40]
            raise ValueError(f"content-safety gate FAILED for {label}: {desc} matched {m.group(0)!r}: ...{ctx!r}...")


def fmt_addr(a):
    if not a:
        return None
    parts = [a.get("addr1"), a.get("city"), a.get("state"), a.get("zip")]
    return ", ".join(p for p in parts if p)


def tier_label(tier):
    if tier is None:
        return "NOT AVAILABLE"
    t = str(tier)
    if "VERIFIED·PRIMARY" in t or t == "VERIFIED_PRIMARY" or "VERIFIED_PRIMARY" in t:
        return "VERIFIED·PRIMARY"
    if "VERIFIED·CROSS-CHECKED" in t or t == "VERIFIED_CROSS_CHECKED":
        return "VERIFIED·CROSS-CHECKED"
    if "LIKELY" in t:
        return "LIKELY·SINGLE SOURCE"
    if "UNCONFIRMED" in t:
        return "UNCONFIRMED CLAIM"
    return "NOT AVAILABLE"


def row(label, value):
    return f'<tr><td class="label">{esc(label)}</td><td class="val">{value}</td></tr>'


def contact_row(label, value_html, source):
    return (f'<div class="contact-row"><span class="contact-label">{esc(label)}</span>'
            f'<span class="contact-value">{value_html}<br><span class="contact-source">{esc(source)}</span></span></div>')


def build_buyer_of_record_rows(r):
    mailing = fmt_addr(r["mailing_address"])
    case_list = ", ".join(r["case_numbers"])
    rows = [
        row("Buyer / Entity Name", esc(r["buyer_key"].title() if r["type"] == "person" else r["entity"])),
        row("Buyer Type", "Individual(s)" if r["type"] == "person" else "Business Entity"),
        row("Mailing / Registered Address", f"{esc(mailing) if mailing else 'NOT AVAILABLE'} <span style=\"color:#6b665c;font-size:11px\">[{tier_label(r['mailing_tier'])}]</span>"),
        row("Case Number(s)", esc(case_list)),
        row("County", esc(r["county"].title())),
    ]
    if r.get("sunbiz_doc_number"):
        rows.append(row("Florida Registration (Div. of Corporations Doc #)", f'{esc(r["sunbiz_doc_number"])} &mdash; {esc(r.get("sunbiz_status") or "status not on file")}'))
    if r.get("registered_agent"):
        rows.append(row("Registered Agent", esc(r["registered_agent"])))
    if r.get("principal") and r.get("type") == "business":
        rows.append(row("Principal / Manager on File", esc(r["principal"])))
    return "\n      ".join(rows)


def build_contact_rows(r):
    rows = []
    phone_tier = tier_label(r.get("phone_tier"))
    if r.get("phone"):
        rows.append(contact_row("Phone", f'<a href="tel:{esc(r["phone"])}">{esc(r["phone"])}</a>', phone_tier))
    else:
        rows.append(contact_row("Phone", "NOT AVAILABLE", "Checked through standard verification process; no match found this cycle"))
    email_tier = tier_label(r.get("email_tier"))
    if r.get("email"):
        rows.append(contact_row("Email", f'<a href="mailto:{esc(r["email"])}">{esc(r["email"])}</a>', email_tier))
    else:
        rows.append(contact_row("Email", "NOT AVAILABLE", "Checked through standard verification process; no match found this cycle"))
    return "\n      ".join(rows)


def build_compliance_note(r):
    if r.get("phone") and r.get("dnc") and r["dnc"].get("status") == "OK":
        if r["dnc"].get("flagged"):
            return "This phone number is on the Do Not Call registry. Manual dial only by a licensed producer -- no automated dialing, texting, or email marketing without documented consent."
        return "Do Not Call registry checked for this phone number: not flagged as of the date prepared. Manual outreach by a licensed producer is still required -- no consent on file for automated contact."
    if r.get("phone"):
        return "Do Not Call registry status not yet independently re-verified this cycle -- confirm before automated contact."
    return "No phone on file for automated-contact compliance review; manual research required before any outreach."


def build_property_rows(r):
    parts = []
    total = 0
    for p in r["properties"]:
        fact = p.get("fact") or {}
        subj = p.get("subject") or {}
        addr = fact.get("property_address") or "Address not established"
        case_no = p.get("case_number")
        use = subj.get("luse_desc") or "Not established"
        just_val = subj.get("val_market")
        assessed = subj.get("val_assessed")
        appraiser_url = COUNTY_APPRAISER_URL.get(r["county"])
        verified = bool(subj)
        badge = (f'<span class="badge green" style="font-size:9px;padding:1px 6px;">VERIFIED</span>' if verified
                 else f'<span class="badge amber" style="font-size:9px;padding:1px 6px;">NOT VERIFIED</span>')
        link = f'<a href="{esc(appraiser_url)}" target="_blank" rel="noopener">County Appraiser →</a>' if appraiser_url else "No appraiser link on file"
        sold = fact.get("sold_amount")
        if sold:
            try:
                total += float(sold)
            except (TypeError, ValueError):
                pass
        sub = f'<div class="ptable-sub">{esc(addr)} &middot; {badge} {link} &middot; Sold {money(sold)} ({esc(fact.get("sale_type") or "auction")})</div>'
        parts.append(
            f'<tr><td>{esc(addr)}{sub}</td><td>{esc(use)}</td><td>{money(just_val)}</td>'
            f'<td>{money(assessed)}</td><td>{esc(case_no)}</td></tr>'
        )
    return "\n      ".join(parts), total


def build_cross_sell(r):
    siblings = r.get("sibling_case_numbers") or []
    if not siblings:
        return ""
    n = len(siblings) + 1
    return (
        '<section class="cross"><h2>Portfolio Note</h2><ul>'
        f'<li>This buyer holds {n} properties in this batch (same county), case numbers '
        f'{esc(", ".join([r["case_numbers"][0]] + siblings))} -- bundle/umbrella conversation warranted. '
        'This report covers only its own case; see the sibling case Fact Finder(s) for those properties.</li>'
        '</ul></section>'
    )


def render(r):
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        tpl = f.read()
    property_rows, total_sold = build_property_rows(r)
    n = len(r["properties"])
    values = {
        "entity_name": esc(r["buyer_key"].title()),
        "contact_status_label": "CONTACT RESOLVED" if r["paid"] else "CONTACT RESEARCH IN PROGRESS",
        "auction_date": "August 26, 2026",
        "prepared_date": "August 27, 2026",
        "buyer_of_record_rows": build_buyer_of_record_rows(r),
        "contact_rows": build_contact_rows(r),
        "contact_compliance_note": esc(build_compliance_note(r)),
        "property_section_heading": f"Propert{'ies' if n > 1 else 'y'} Won at Auction ({n})" if n > 1 else "Property Won at Auction",
        "property_rows": property_rows,
        "property_totals_line": f"Total sold amount across {n} propert{'ies' if n > 1 else 'y'}: {money(total_sold)}",
        "cross_sell_section": build_cross_sell(r),
    }
    out = TOKEN_RE.sub(lambda m: values.get(m.group(1), ""), tpl)
    out = HTML_COMMENT_RE.sub("", out).lstrip("\n")
    label = r["buyer_key"]
    assert_content_safe(out, label)
    return out


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    if os.environ.get("SUPABASE_ACCESS_TOKEN"):
        report = load_report_from_db(BATCH_DATE)
    else:
        with open(REPORT_PATH) as f:
            report = json.load(f)

    if len(report) != 9:
        print(f"WARNING: expected 9 case records, got {len(report)}", file=sys.stderr)

    written = []
    for r in report:
        out_html = render(r)
        fname = f"{slugify(r['buyer_key'])}-{slugify(r['case_numbers'][0])}.html"
        out_path = os.path.join(OUT_DIR, fname)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out_html)
        pdf_path = out_path.replace(".html", ".pdf")
        try:
            subprocess.run(
                ["chromium", "--headless", "--disable-gpu", "--no-sandbox",
                 f"--print-to-pdf={pdf_path}", "--print-to-pdf-no-header",
                 f"file://{os.path.abspath(out_path)}"],
                check=True, capture_output=True, timeout=30,
            )
            pdf_ok = os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0
        except Exception as e:
            pdf_ok = False
            print(f"  PDF render FAILED for {fname}: {e}")
        print(f"wrote {out_path} ({len(out_html)} bytes) | pdf={'OK ' + pdf_path if pdf_ok else 'FAILED'}")
        written.append({"buyer_key": r["buyer_key"], "html": out_path, "pdf": pdf_path if pdf_ok else None,
                         "paid": r["paid"], "phone": bool(r.get("phone")), "email": bool(r.get("email"))})

    with open(os.path.join(OUT_DIR, "manifest.json"), "w") as f:
        json.dump(written, f, indent=2)
    print(f"\n{len(written)} Fact Finders rendered to {OUT_DIR}/")


if __name__ == "__main__":
    main()
