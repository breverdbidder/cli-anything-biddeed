#!/usr/bin/env python3
"""Portfolio Fact Finder renderer -- one document per resolved operator,
listing their FULL held book (winnerdata.owner_portfolio), not just the
parcel won at auction. Part 2 of the identity-cascade + portfolio issue
(2026-08-25), supersedes the single-property call sheets from
scripts/winnerdata_render_batch.py for any buyer with 2+ properties.

Billing note (per the issue): POC rate stays $9/Fact-Finder delivered
regardless of property_count -- this script emits property_count and a
per-property bind_state on every FF so a future per-property rate change
is a config edit, not a rebuild.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from skiptrace_20260825_portfolio_batch import run_sql, BATCH_ID  # noqa: E402

BATCH_DATE = os.environ.get("BATCH_DATE_OVERRIDE") or date.today().isoformat()
OUT_DIR = f"winnerdata/batches/{BATCH_DATE}/portfolio"
RATE_PER_FF_CENTS = 900  # $9.00, flat per Fact Finder delivered -- NOT per property (issue directive, do not invent per-property pricing)

DOR_UC_MAP = {
    "000": "Vacant Residential", "001": "Single Family", "002": "Mobile Home",
    "003": "Multi-Family <10", "004": "Condo", "005": "Co-op", "006": "Retirement",
    "007": "Misc Residential", "008": "Multi-Family 10+", "009": "Residential Common",
    "010": "Vacant Commercial", "011": "Retail", "012": "Mixed Use", "017": "Office",
    "018": "Professional Service", "019": "Hotel/Motel", "021": "Light Industrial",
    "022": "Heavy Industrial", "027": "Auto Service", "028": "Parking",
}

COMMERCIAL_DOR_PREFIXES = ("01", "02")  # 010-029: commercial/industrial per DOR_UC_MAP


def fmt_money(v):
    try:
        return f"${float(v):,.0f}"
    except (TypeError, ValueError):
        return "unknown"


def bundle_doctrine(property_count: int, rows: list[dict]) -> list[str]:
    flags = []
    if property_count >= 2:
        flags.append(f"UMBRELLA -- {property_count} properties held, umbrella conversation warranted (2+ trigger)")
    if property_count >= 5:
        flags.append(f"MASTER POLICY -- {property_count} properties, master-policy conversation warranted (5+ trigger)")
    commercial_rows = [r for r in rows if (r.get("dor_uc") or "").startswith(COMMERCIAL_DOR_PREFIXES) or (r.get("no_buldng") or 0) >= 3]
    if commercial_rows:
        flags.append(f"COMMERCIAL BOP -- {len(commercial_rows)} propert{'y is' if len(commercial_rows)==1 else 'ies are'} commercial-use or 3+ buildings")
    coastal_rows = [r for r in rows if r.get("coastal_flood_indicator") not in (None, "UNKNOWN")]
    if coastal_rows:
        flags.append(f"FLOOD -- {len(coastal_rows)} propert{'y' if len(coastal_rows)==1 else 'ies'} flagged coastal/flood-zone")
    else:
        flags.append("FLOOD -- UNKNOWN for all properties (flood_zones table has real polygon coverage only for Brevard County as of 2026-08-25; not guessed for the other 8 counties in this batch)")
    return flags


def property_line(r: dict) -> str:
    use = DOR_UC_MAP.get(r.get("dor_uc"), f"DOR-{r.get('dor_uc')}" if r.get("dor_uc") else "unknown use")
    tag = "AUCTION WIN" if r["acquisition_source"] == "auction_win" else "prior holding"
    link = {"exact_name": "", "affiliate_own_addr": f" [affiliate: {r.get('linked_via_detail') or ''}]",
            "shared_principal": f" [affiliate: {r.get('linked_via_detail') or ''}]"}.get(r["linked_via"], "")
    return (f"- **{r.get('address') or 'address unknown'}, {r['county'].replace('_',' ').title()} County** "
            f"({tag}{link}) -- {use}, JV {fmt_money(r.get('jv'))} -- **bind_state: NOT BOUND** (prospecting, no policy on file)")


def card(owner_key: str, entity_name: str, rows: list[dict], contact: dict) -> str:
    property_count = len(rows)
    total_jv = sum(float(r["jv"]) if r.get("jv") not in (None, "") else 0 for r in rows)
    counties = sorted({r["county"] for r in rows})
    doctrine = bundle_doctrine(property_count, rows)
    lines = [
        f"## {entity_name}",
        "",
        f"**Resolved principal:** {contact.get('principal_name') or 'UNRESOLVED -- ' + (contact.get('tag') or 'no individual name on record')}",
        f"**Contact phone/email:** {contact.get('phone') or 'none on file'} / {contact.get('email') or 'none on file'}",
        f"**DNC state:** {contact.get('dnc_state') or 'NOT SCRUBBED -- do not call until scrub completed'}",
        f"**Sources tried (if unresolved):** {', '.join(contact.get('sources_tried', [])) or 'n/a'}",
        "",
        f"**property_count: {property_count}** across {len(counties)} counties ({', '.join(c.replace('_',' ').title() for c in counties)}) -- total JV {fmt_money(total_jv)}",
        f"**billing: 1 Fact Finder delivered @ ${RATE_PER_FF_CENTS/100:.2f} flat (POC rate, not per-property)**",
        "",
        "### Bundle doctrine",
    ]
    lines += [f"- {d}" for d in doctrine]
    lines += ["", "### Properties (per-property bind state)"]
    lines += [property_line(r) for r in sorted(rows, key=lambda r: (r["county"], r.get("address") or ""))]
    return "\n".join(lines) + "\n"


def load_portfolio_rows():
    rows = run_sql(f"select * from winnerdata.owner_portfolio where batch_id = '{BATCH_ID}' order by owner_key, county, parcel_id;")
    by_owner: dict[str, list[dict]] = {}
    for r in rows:
        by_owner.setdefault(r["owner_key"], []).append(r)
    return by_owner


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    by_owner = load_portfolio_rows()
    cascade = json.load(open("/tmp/cascade_cache_20260825.json")) if os.path.exists("/tmp/cascade_cache_20260825.json") else {}

    master_lines = [f"# Portfolio Fact Finders -- {BATCH_DATE} (batch {BATCH_ID})\n",
                     f"Generated: {datetime.now(timezone.utc).isoformat()}Z\n",
                     f"{len(by_owner)} owner(s) with 1+ properties enumerated in winnerdata.owner_portfolio.\n"]

    rendered = 0
    for owner_key, rows in by_owner.items():
        if not rows:
            continue
        entity_name = rows[0]["entity_name_raw"]
        cascade_hit = cascade.get(owner_key, {})
        contact = {
            "principal_name": cascade_hit.get("principal_name"),
            "phone": None,  # Tracerfy enhanced_trace not yet re-run against Sunbiz-resolved addresses this session -- see final report
            "email": None,
            "dnc_state": None,
            "sources_tried": cascade_hit.get("sources_tried", []),
            "tag": cascade_hit.get("tag"),
        }
        text = card(owner_key, entity_name, rows, contact)
        fname = f"{OUT_DIR}/{owner_key.lower().replace(' ', '_').replace('&','and')}.md"
        with open(fname, "w") as f:
            f.write(f"# Portfolio Fact Finder -- {entity_name} -- {BATCH_DATE}\n\n" + text)
        master_lines.append(text)
        rendered += 1
        print(f"  wrote {fname} ({len(rows)} properties)")

    with open(f"{OUT_DIR}/master.md", "w") as f:
        f.write("\n".join(master_lines))
    print(f"\n{rendered} Portfolio Fact Finders rendered to {OUT_DIR}/")


# ---------------------------------------------------------------------------
# Nine-case Elementix-parity portfolio PDF renderer (issue #19531).
#
# Separate code path, gated behind --nine-case, reading directly from
# winnerdata.ff_batch_leads (the enrichment SSOT) rather than the legacy
# owner_portfolio/cascade-cache Markdown path above -- that path stays
# unmodified for whatever still calls it. Reuses the same brand/CSS system as
# templates/FF_TEMPLATE_A_AUCTION_SALES.html and the same content-safety gate
# as scripts/render_ff_9buyer_20260827.py (imported, not duplicated) so a
# client PDF can never leak an internal vendor name, file path, or issue
# number.
# ---------------------------------------------------------------------------
import html as _html
import re as _re
import subprocess as _subprocess
import urllib.error as _urlerr
import urllib.request as _urlreq

_MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"


def _sanitize_for_client(text):
    """Redact internal vendor names / file paths / issue numbers from any
    free-text DB value before it reaches a client PDF. identity_match_rationale,
    qa_errors_json reasons, and similar fields are internal QA provenance
    written by enrichment code with no client-safety discipline applied at
    write time (unlike scripts/render_ff_9buyer_20260827.py's hand-authored
    strings) -- assert_content_safe() below is the backstop, this is the
    fix, not a substitute for it."""
    from render_ff_9buyer_20260827 import BANNED_TERMS, BANNED_PATTERNS  # noqa: E402
    if text in (None, ""):
        return text
    out = str(text)
    for term in BANNED_TERMS:
        out = _re.sub(_re.escape(term), "a verified data provider", out, flags=_re.IGNORECASE)
    for pattern, _desc in BANNED_PATTERNS:
        out = pattern.sub("[internal reference redacted]", out)
    return out


def mgmt_sql(query: str, timeout: int = 90):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = _urlreq.Request(
        _MGMT_URL, data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "portfolio-ff-render-nine-case/1.0"},
        method="POST",
    )
    with _urlreq.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read())
    if isinstance(body, dict) and body.get("message"):
        raise RuntimeError(body["message"])
    return body


def _esc(v):
    return _html.escape(_sanitize_for_client(v)) if v not in (None, "") else ""


def _money(v):
    try:
        return f"${float(v):,.0f}"
    except (TypeError, ValueError):
        return "Not established"


def _badge(label, cls="amber"):
    return f'<span class="badge {cls}">{_esc(label)}</span>'


def _confidence_badge(value):
    m = {"verified": "green", "probable": "blue", "unresolved": "amber", "conflict": "red", "not_run_no_key": "amber"}
    return _badge((value or "unresolved").upper(), m.get(value, "amber"))


NINE_CASE_CSS = """
:root{ --paper:#faf9f5; --ink:#141413; --terra:#d97757; --line:#e9e5d8; --muted:#6b665c; --green:#2f6b3a; --amber:#9a5b1e; --red:#b0413e; --blue:#28588f; }
body{margin:0;background:var(--paper);color:var(--ink);font-family:Georgia,'Times New Roman',serif;}
.wrap{max-width:820px;margin:0 auto;padding:24px 28px 30px;}
header{border-bottom:2px solid var(--ink);padding-bottom:10px;margin-bottom:12px;}
.brandline{font-family:Arial,sans-serif;}
.brandline .name{font-size:22px;font-weight:800;}
.brandline .name span{color:var(--terra);}
.brandline .tagline{font-size:12px;color:var(--muted);font-style:italic;font-weight:700;margin-top:4px;}
h1{font-size:19px;margin:8px 0 2px;font-family:Arial,sans-serif;}
.meta{font-family:Arial,sans-serif;font-size:11px;color:var(--muted);margin-bottom:14px;}
.badge{display:inline-block;font-family:Arial,sans-serif;font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;letter-spacing:.03em;margin-right:6px;}
.badge.blue{background:#e2ecf7;color:var(--blue);} .badge.green{background:#e4f0e6;color:var(--green);}
.badge.amber{background:#fdf0d8;color:var(--amber);} .badge.red{background:#fbe2e1;color:var(--red);}
section{margin-bottom:14px;page-break-inside:avoid;}
h2{font-family:Arial,sans-serif;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);border-bottom:1px solid var(--line);padding-bottom:5px;margin-bottom:10px;}
table{width:100%;border-collapse:collapse;font-family:Arial,sans-serif;font-size:12.5px;}
td{padding:3px 0;vertical-align:top;}
td.label{width:210px;color:var(--muted);}
td.val{font-weight:600;}
table.ptable thead th{font-family:Arial,sans-serif;font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);text-align:left;border-bottom:1px solid var(--ink);padding:4px 6px 6px 0;}
table.ptable tbody td{padding:5px 6px 5px 0;border-bottom:1px solid var(--line);font-size:12px;}
.note{font-family:Arial,sans-serif;font-size:11px;color:var(--muted);margin-top:6px;}
.ledger{font-family:Arial,sans-serif;font-size:10.5px;color:var(--muted);}
.ledger li{margin-bottom:3px;}
section.cross{background:#fbeee0;border:1px solid #f0d2b0;border-radius:8px;padding:12px 16px;}
section.cross h2{border-bottom:none;color:var(--amber);margin-bottom:8px;}
section.cross ul{margin:0;padding-left:18px;font-family:Arial,sans-serif;font-size:12px;}
footer{margin-top:16px;padding-top:12px;border-top:1px solid var(--line);font-family:Arial,sans-serif;font-size:9.5px;color:var(--muted);line-height:1.5;}
@media print{ body{background:#fff;} }
"""


def _row(label, value):
    return f'<tr><td class="label">{_esc(label)}</td><td class="val">{value}</td></tr>'


def render_nine_case_html(r: dict) -> str:
    entity_type = "Individual(s)" if r.get("identity_type") == "individual" else "Business Entity"
    property_row = (
        f'<tr><td>{_esc(r.get("property_address") or "Address not established")}'
        f'<div class="note">{_esc(r.get("site_addr"))}, {_esc(r.get("site_city"))} {_esc(r.get("site_zip"))}</div></td>'
        f'<td>{_esc(r.get("dor_luse_desc") or "unknown use")}</td><td>{_money(r.get("val_market"))}</td>'
        f'<td>{_money(r.get("val_assessed"))}</td><td>{_esc(r.get("case_number"))}</td></tr>'
    )

    portfolio_rows = ""
    for p in (r.get("portfolio_properties_json") or [])[:25]:
        portfolio_rows += (
            f'<tr><td>{_esc(p.get("address") or "address unknown")}, {_esc((p.get("county") or "").title())}</td>'
            f'<td>{_esc(p.get("dor_uc"))}</td><td>{_money(p.get("jv"))}</td>'
            f'<td>{_esc((p.get("acquisition_source") or "unknown").replace("_", " ").title())}</td></tr>'
        )
    portfolio_section = ""
    if r.get("portfolio_property_count") is not None:
        portfolio_section = f"""
    <section>
      <h2>Held Portfolio Summary</h2>
      <table>
        {_row("Total properties held", r.get("portfolio_property_count"))}
        {_row("Counties", ", ".join((r.get("portfolio_counties") or [])) or "n/a")}
        {_row("Total JV/market value", _money(r.get("portfolio_total_jv")))}
        {_row("Total buildings", r.get("portfolio_total_buildings"))}
      </table>
      {'<table class="ptable"><thead><tr><th>Property</th><th>DOR use</th><th>JV</th><th>Acquisition</th></tr></thead><tbody>' + portfolio_rows + '</tbody></table>' if portfolio_rows else ''}
    </section>"""
    else:
        portfolio_section = """
    <section>
      <h2>Held Portfolio Summary</h2>
      <div class="note">UNRESOLVED -- no owner_portfolio coverage on file for this entity yet (batch-scoped table, not a live statewide scan). Not reported as zero holdings.</div>
    </section>"""

    related = r.get("related_entities") or []
    related_rows = "".join(_row(o.get("position") or "officer", _esc(o.get("name"))) for o in related[:10]) or _row("Related entities", "none on file")

    qa_errors = r.get("qa_errors_json") or []
    ledger_items = "".join(f"<li>{_esc(e.get('field'))}: {_esc(e.get('reason'))}</li>" for e in qa_errors) or "<li>No unresolved fields logged.</li>"

    flags = []
    if r.get("umbrella_opportunity"):
        flags.append("UMBRELLA -- 2+ properties held, umbrella conversation warranted")
    if r.get("master_policy_opportunity"):
        flags.append("MASTER POLICY -- 5+ properties held")
    if r.get("commercial_bop_opportunity"):
        flags.append("COMMERCIAL BOP -- commercial-use or multi-building property in portfolio")
    if r.get("flood_opportunity") == "flagged":
        flags.append("FLOOD -- coastal/flood-zone property flagged")
    next_action_section = ""
    if flags:
        next_action_section = (
            '<section class="cross"><h2>Bundle Opportunity + Next Action</h2><ul>'
            + "".join(f"<li>{_esc(f)}</li>" for f in flags)
            + "</ul></section>"
        )

    dnc_note = "Flagged on the Do Not Call registry -- manual dial only, no automated dialing/texting/email without documented consent." if r.get("is_dnc") else (
        "Not flagged on the Do Not Call registry as of the date prepared -- manual outreach by a licensed producer still required." if r.get("is_dnc") is False else
        "Do Not Call status not independently verified this cycle -- confirm before any automated contact.")

    out = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Winner Data AI &mdash; Portfolio Fact Finder &mdash; {_esc(r.get('resolved_entity_name'))}</title>
<style>{NINE_CASE_CSS}</style></head>
<body><div class="wrap">
  <header><div class="brandline"><div class="name">Winner Data <span>AI</span></div>
    <div class="tagline">Every Deal Creates a Customer. Our Winner Data AI Finds Them First.</div></div></header>

  {_badge(r.get('qa_status') or 'PARTIAL_ENRICHMENT', 'green' if r.get('qa_status') == 'FULLY_ENRICHED' else 'amber')}
  <h1>Portfolio Fact Finder &mdash; {_esc(r.get('resolved_entity_name'))}</h1>
  <div class="meta">Auction date {_esc(r.get('auction_date'))} &middot; {_esc((r.get('county') or '').title())} County &middot; Case {_esc(r.get('case_number'))}</div>

  <section>
    <h2>Auction Trigger + Buyer Classification</h2>
    <table>
      {_row("Buyer / Entity Name", _esc(r.get('winning_bidder')))}
      {_row("Buyer Type", entity_type)}
      {_row("Sale Type", _esc(r.get('sale_type')))}
      {_row("Sold Amount", _money(r.get('tier1_sold_amount')))}
    </table>
    <table class="ptable"><thead><tr><th>Property Won at Auction</th><th>Use</th><th>Just Value</th><th>Assessed Value</th><th>Case #</th></tr></thead>
      <tbody>{property_row}</tbody></table>
  </section>

  <section>
    <h2>Parcel / DOR SSOT Summary</h2>
    <table>
      {_row("Owner of record on file", _esc(r.get('owner_name')))}
      {_row("Parcel match method", _esc(r.get('parcel_match_method')))}
      {_row("Parcel match confidence", _confidence_badge(r.get('parcel_match_confidence')))}
      {_row("Property appraiser link", f'<a href="{_esc(r.get("pa_link"))}">County Appraiser &rarr;</a>' if r.get('pa_link') else 'Not on file')}
    </table>
  </section>

  <section>
    <h2>Resolved Investor Identity + Confidence Rationale</h2>
    <table>
      {_row("Resolved principal", _esc(r.get('resolved_principal_name')) or 'UNRESOLVED')}
      {_row("Identity match method", _esc(r.get('identity_match_method')))}
      {_row("Identity confidence", _confidence_badge(r.get('identity_match_confidence')))}
      {_row("Rationale", _esc(r.get('identity_match_rationale')))}
    </table>
  </section>

  {portfolio_section}

  <section>
    <h2>Registered Agent / Principal / Related-Entity Graph</h2>
    <table>
      {_row("Registered agent", _esc(r.get('registered_agent_name')) or 'Not on file')}
      {_row("Registered agent address", _esc(r.get('registered_agent_address')) or 'Not on file')}
      {_row("Registered agent confidence", _confidence_badge(r.get('registered_agent_confidence')))}
      {_row("Principal address", _esc(r.get('principal_address')) or 'UNRESOLVED')}
      {related_rows}
    </table>
  </section>

  <section>
    <h2>Business + Individual Contact Verification</h2>
    <table>
      {_row("Business phone", _esc(r.get('business_phone')) or 'Not available')}
      {_row("Business email", _esc(r.get('business_email')) or 'Not available')}
      {_row("Individual phone", _esc(r.get('individual_phone')) or 'Not available')}
      {_row("Individual email", _esc(r.get('individual_email')) or 'Not available')}
      {_row("Contact match status", _confidence_badge(r.get('contact_confidence')))}
    </table>
    <div class="note">{_esc(dnc_note)}</div>
  </section>

  <section>
    <h2>Source and Conflict Ledger</h2>
    <ul class="ledger">{ledger_items}</ul>
    <div class="note">Relationship conflict status: {_esc(r.get('relationship_conflict_status') or 'no_conflict')} &middot; Unresolved required fields: {r.get('unresolved_field_count')}</div>
  </section>

  {next_action_section}

  <footer>
    Winner Data AI supplies property and ownership data to licensed insurance agencies. It does not
    contact property owners and does not market foreclosure relief. Fields marked UNRESOLVED or NOT
    AVAILABLE must not be used for outreach until independently verified. County Just Value is a
    tax-assessment figure, not replacement cost or market value.
  </footer>
</div></body></html>"""
    return out


def slugify_nine_case(name: str) -> str:
    return _re.sub(r"[^a-z0-9]+", "-", (name or "unknown").lower()).strip("-") or "unknown"


def render_nine_case_pdfs(batch_date: str):
    sys.path.insert(0, os.path.dirname(__file__))
    from render_ff_9buyer_20260827 import assert_content_safe  # noqa: E402 -- reuse, do not duplicate the banned-term gate

    out_dir = f"winnerdata/batches/{batch_date}/nine_case_portfolio"
    os.makedirs(out_dir, exist_ok=True)

    rows = mgmt_sql(f"select * from winnerdata.ff_batch_leads where batch_date = date '{batch_date}' order by county, case_number;")
    manifest = []
    for r in rows:
        out_html = render_nine_case_html(r)
        label = r.get("winning_bidder") or r.get("auction_id")
        try:
            assert_content_safe(out_html, label)
        except ValueError as e:
            print(f"CONTENT-SAFETY GATE FAILED for {label}: {e}", file=sys.stderr)
            raise
        # One file per case_number, not per buyer -- Mundi Marketing LLC and
        # OK Business LLC each won 2 of the 9 cases, so a buyer-name-only
        # slug collides and silently overwrites the first case's PDF.
        slug = slugify_nine_case(f"{r.get('winning_bidder')} {r.get('case_number')}")
        html_path = os.path.join(out_dir, f"{slug}.html")
        pdf_path = os.path.join(out_dir, f"{slug}.pdf")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(out_html)
        pdf_ok = False
        try:
            _subprocess.run(
                ["chromium", "--headless", "--disable-gpu", "--no-sandbox",
                 f"--print-to-pdf={pdf_path}", "--print-to-pdf-no-header",
                 f"file://{os.path.abspath(html_path)}"],
                check=True, capture_output=True, timeout=30,
            )
            pdf_ok = os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0
        except Exception as e:
            print(f"  PDF render FAILED for {slug}: {e}")
        print(f"wrote {html_path} pdf={'OK' if pdf_ok else 'FAILED'}")
        manifest.append({
            "auction_id": r.get("auction_id"), "case_number": r.get("case_number"),
            "report_html": html_path, "report_pdf": pdf_path if pdf_ok else None,
            "qa_status": r.get("qa_status"), "unresolved_field_count": r.get("unresolved_field_count"),
            "source_snapshot_hash": r.get("source_snapshot_hash"),
        })

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)
    print(f"\n{len(manifest)} nine-case Portfolio Fact Finder(s) rendered to {out_dir}/ (manifest: {manifest_path})")
    return manifest


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--nine-case", action="store_true", help="Render the issue #19531 nine-case portfolio PDFs from winnerdata.ff_batch_leads instead of the legacy owner_portfolio Markdown path")
    ap.add_argument("--batch-date", default=BATCH_DATE)
    args = ap.parse_args()
    if args.nine_case:
        render_nine_case_pdfs(args.batch_date)
    else:
        main()
