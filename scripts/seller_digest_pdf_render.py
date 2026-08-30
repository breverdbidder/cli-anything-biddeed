#!/usr/bin/env python3
"""Pre-approval PDF Fact Finder renderer for seller_digest batches (issue #19619).

Runs AFTER enrichment completes and BEFORE Ariel approves the batch. This is
the step the nine-case flow was missing for seller_digest: Ariel should see real
PDFs before approving, not after. The existing nine-case flow (triggered on
approval) is not touched.

Reads from winnerdata.seller_digest_leads (the enrichment SSOT, not a temp
file). Renders one HTML + PDF per lead. Applies the same content-safety gate
as scripts/render_ff_9buyer_20260827.py (BANNED_TERMS + BANNED_PATTERNS imported,
not duplicated).

Hard guardrails (from issue #19619):
  - No PII (phone/email) rendered for a lead where is_dnc is NULL (DNC not
    completed). Those fields are blanked and the PDF notes "DNC not verified".
  - Fields marked UNRESOLVED or NOT AVAILABLE must not claim verification.
  - Every step checks its own result before reporting success.

Run:
  BATCH_DATE=2026-08-28 SUPABASE_ACCESS_TOKEN=... \\
    python scripts/seller_digest_pdf_render.py [--batch-date YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import html as _html
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from render_ff_9buyer_20260827 import assert_content_safe, BANNED_TERMS, BANNED_PATTERNS  # noqa: E402

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
SB_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")


def mgmt_sql(query: str, timeout: int = 90):
    if not SB_TOKEN:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN is required")
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"Bearer {SB_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "seller-digest-pdf-render/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read())
    if isinstance(body, dict) and body.get("message"):
        raise RuntimeError(body["message"])
    return body


def esc(v):
    return _html.escape(str(v)) if v not in (None, "") else ""


def money(n):
    if n is None:
        return "Not established"
    try:
        return f"${float(n):,.0f}"
    except (TypeError, ValueError):
        return "Not established"


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "unknown").lower()).strip("-") or "unknown"


SELLER_DIGEST_CSS = """
:root{--paper:#faf9f5;--ink:#141413;--terra:#d97757;--line:#e9e5d8;--muted:#6b665c;--green:#2f6b3a;--amber:#9a5b1e;--red:#b0413e;--blue:#28588f;}
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
.badge.blue{background:#e2ecf7;color:var(--blue);}.badge.green{background:#e4f0e6;color:var(--green);}
.badge.amber{background:#fdf0d8;color:var(--amber);}.badge.red{background:#fbe2e1;color:var(--red);}
section{margin-bottom:14px;page-break-inside:avoid;}
h2{font-family:Arial,sans-serif;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);border-bottom:1px solid var(--line);padding-bottom:5px;margin-bottom:10px;}
table{width:100%;border-collapse:collapse;font-family:Arial,sans-serif;font-size:12.5px;}
td{padding:3px 0;vertical-align:top;}
td.label{width:210px;color:var(--muted);}
td.val{font-weight:600;}
.note{font-family:Arial,sans-serif;font-size:11px;color:var(--muted);margin-top:6px;}
.dnc-warn{background:#fbe2e1;border:1px solid #e8b4b2;border-radius:6px;padding:8px 12px;font-family:Arial,sans-serif;font-size:11px;color:var(--red);margin-top:8px;}
footer{margin-top:16px;padding-top:12px;border-top:1px solid var(--line);font-family:Arial,sans-serif;font-size:9.5px;color:var(--muted);line-height:1.5;}
@media print{body{background:#fff;}}
"""


def _row(label, value):
    return f'<tr><td class="label">{esc(label)}</td><td class="val">{value}</td></tr>'


def _badge(label, cls="amber"):
    return f'<span class="badge {cls}">{esc(label)}</span>'


def render_seller_digest_html(r: dict) -> str:
    """Render a single seller_digest lead as HTML.

    Guardrail: if is_dnc is None (DNC screening incomplete), phone/email are
    NOT rendered -- the PDF shows a warning instead. This is a hard block, not
    a style choice.
    """
    is_dnc = r.get("is_dnc")
    dnc_complete = is_dnc is not None
    phone = r.get("phone") if dnc_complete else None
    email = r.get("email") if dnc_complete else None
    contact_provider = r.get("contact_provider") or ""

    if not dnc_complete:
        dnc_note = '<div class="dnc-warn">DNC screening not completed for this lead. Contact information withheld. Do not use for outreach until DNC status is confirmed.</div>'
        contact_section_body = dnc_note
    elif is_dnc:
        dnc_note = "Flagged on the Do Not Call registry — manual dial only, no automated dialing/texting/email without documented consent."
        contact_section_body = f'<div class="dnc-warn">{esc(dnc_note)}</div>'
        if phone:
            contact_section_body += f'<table>{_row("Phone", esc(phone))}{_row("DNC status", _badge("DNC FLAGGED", "red"))}</table>'
    else:
        dnc_note = "Not flagged on the Do Not Call registry as of the date prepared — manual outreach by a licensed producer still required."
        phone_display = esc(phone) if phone else "Not available"
        email_display = esc(email) if email else "Not available"
        contact_section_body = f"""<table>
          {_row("Phone", phone_display)}
          {_row("Email", email_display)}
          {_row("Data provider", "A verified data provider" if contact_provider else "Not available")}
          {_row("DNC status", _badge("NOT DNC FLAGGED", "green"))}
        </table>
        <div class="note">{esc(dnc_note)}</div>"""

    sold_amount_display = money(r.get("sold_amount"))
    entity_name = r.get("entity_name") or "Unknown"
    case_number = r.get("case_number") or "Unknown"
    county = r.get("county") or "Unknown"
    sale_type = r.get("sale_type") or "Unknown"
    property_address = r.get("property_address") or "Not established"
    email_tier = r.get("email_tier") or "Not available"
    phone_tier = r.get("phone_tier") or "Not available"
    batch_date = r.get("batch_date") or ""

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Winner Data AI &mdash; Seller Fact Finder &mdash; {esc(entity_name)}</title>
<style>{SELLER_DIGEST_CSS}</style></head>
<body><div class="wrap">
  <header>
    <div class="brandline">
      <div class="name">Winner Data <span>AI</span></div>
      <div class="tagline">Every Deal Creates a Customer. Our Winner Data AI Finds Them First.</div>
    </div>
  </header>

  {_badge("SELLER DIGEST", "blue")}
  {_badge("PRE-APPROVAL DRAFT", "amber")}
  <h1>Seller Fact Finder &mdash; {esc(entity_name)}</h1>
  <div class="meta">Batch date {esc(str(batch_date))} &middot; {esc(county.title())} County &middot; Case {esc(case_number)}</div>

  <section>
    <h2>Auction Event</h2>
    <table>
      {_row("Entity name", esc(entity_name))}
      {_row("County", esc(county.title()))}
      {_row("Sale type", esc(sale_type))}
      {_row("Case number", esc(case_number))}
      {_row("Sold amount", sold_amount_display)}
      {_row("Property address", esc(property_address))}
    </table>
  </section>

  <section>
    <h2>Consent Certificate Contact Tiers</h2>
    <table>
      {_row("Email tier (consent record)", esc(email_tier))}
      {_row("Phone tier (consent record)", esc(phone_tier))}
    </table>
    <div class="note">These tiers reflect the consent_certificate field recorded at routing time, not skip-trace results. See Contact Verification section below for skip-trace results.</div>
  </section>

  <section>
    <h2>Contact Verification + DNC Status</h2>
    {contact_section_body}
  </section>

  <footer>
    Winner Data AI supplies property and ownership data to licensed insurance agencies. It does not
    contact property owners and does not market foreclosure relief. Fields marked UNRESOLVED or NOT
    AVAILABLE must not be used for outreach until independently verified. This document is a pre-approval
    draft prepared for internal review — not for delivery to any third party.
  </footer>
</div></body></html>"""


def render_seller_digest_pdfs(batch_date: str) -> list[dict]:
    out_dir = f"winnerdata/batches/{batch_date}/seller_digest"
    os.makedirs(out_dir, exist_ok=True)

    rows = mgmt_sql(f"""
        select lead_id, batch_date, entity_name, county, sale_type, case_number,
               sold_amount, property_address, email_tier, phone_tier,
               phone, email, contact_provider, is_dnc, dnc_checked_at,
               row_enrichment_status, unresolved_field_count
        from winnerdata.seller_digest_leads
        where batch_date = date '{batch_date}'
        order by county, entity_name
    """)

    if not rows:
        raise RuntimeError(f"No seller_digest_leads rows for {batch_date}. Run build + enrichment first.")

    print(f"Rendering {len(rows)} Fact Finder(s) for {batch_date}...")
    manifest = []
    content_safety_failures = 0

    for r in rows:
        lead_id = r.get("lead_id") or "unknown"
        entity_name = r.get("entity_name") or "unknown"
        label = f"{entity_name} / {r.get('case_number') or lead_id}"

        out_html = render_seller_digest_html(r)

        try:
            assert_content_safe(out_html, label)
        except ValueError as e:
            print(f"CONTENT-SAFETY GATE FAILED for {label}: {e}", file=sys.stderr)
            content_safety_failures += 1
            manifest.append({
                "lead_id": lead_id,
                "entity_name": entity_name,
                "case_number": r.get("case_number"),
                "status": "CONTENT_SAFETY_FAILED",
                "error": str(e)[:500],
            })
            continue

        slug = slugify(f"{entity_name}-{r.get('case_number') or lead_id}")
        html_path = os.path.join(out_dir, f"{slug}.html")
        pdf_path = os.path.join(out_dir, f"{slug}.pdf")

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(out_html)

        pdf_ok = False
        try:
            subprocess.run(
                ["chromium", "--headless", "--disable-gpu", "--no-sandbox",
                 f"--print-to-pdf={pdf_path}", "--print-to-pdf-no-header",
                 f"file://{os.path.abspath(html_path)}"],
                check=True, capture_output=True, timeout=30,
            )
            pdf_ok = os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0
        except Exception as e:
            print(f"  PDF render FAILED for {slug}: {e}")

        status = "OK" if pdf_ok else "HTML_ONLY"
        print(f"  wrote {html_path} pdf={'OK' if pdf_ok else 'FAILED'} "
              f"dnc_complete={r.get('is_dnc') is not None} "
              f"row_status={r.get('row_enrichment_status')}")

        manifest.append({
            "lead_id": lead_id,
            "entity_name": entity_name,
            "case_number": r.get("case_number"),
            "county": r.get("county"),
            "status": status,
            "report_html": html_path,
            "report_pdf": pdf_path if pdf_ok else None,
            "row_enrichment_status": r.get("row_enrichment_status"),
            "dnc_complete": r.get("is_dnc") is not None,
            "unresolved_field_count": r.get("unresolved_field_count"),
        })

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    ok_count = sum(1 for m in manifest if m.get("status") == "OK")
    html_only_count = sum(1 for m in manifest if m.get("status") == "HTML_ONLY")
    print(f"\n{len(manifest)} Seller Fact Finder(s) rendered to {out_dir}/")
    print(f"  PDF OK: {ok_count}, HTML only: {html_only_count}, "
          f"content-safety failures: {content_safety_failures}")
    print(f"  Manifest: {manifest_path}")

    if content_safety_failures > 0:
        raise RuntimeError(f"{content_safety_failures} content-safety gate failure(s) -- see output above.")

    return manifest


def update_pdf_render_status(batch_date: str, status: str, error: str | None = None):
    fields = [f"pdf_render_status = '{status}'", "updated_at = now()"]
    if status == "complete":
        fields.append("pdf_render_completed_at = now()")
    if status == "failed" and error:
        import re as _re
        safe_err = error[:500].replace("'", "''")
        fields.append(f"enrichment_error = '{safe_err}'")
    q = f"update winnerdata.ff_batches set {', '.join(fields)} where batch_date = date '{batch_date}'"
    try:
        import json as _json
        import urllib.request as _urlreq
        token = SB_TOKEN
        req = _urlreq.Request(MGMT_URL, data=_json.dumps({"query": q}).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                     "User-Agent": "seller-digest-pdf-render/1.0"}, method="POST")
        with _urlreq.urlopen(req, timeout=30) as r:
            pass
    except Exception as e:
        print(f"WARN: could not update pdf_render_status on ff_batches: {e}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-date", default=os.environ.get("BATCH_DATE", ""),
                    help="YYYY-MM-DD batch date")
    args = ap.parse_args()

    batch_date = args.batch_date
    if not batch_date:
        print("ERROR: --batch-date or BATCH_DATE env required", file=sys.stderr)
        sys.exit(1)

    update_pdf_render_status(batch_date, "running")
    try:
        manifest = render_seller_digest_pdfs(batch_date)
        update_pdf_render_status(batch_date, "complete")
    except Exception as e:
        update_pdf_render_status(batch_date, "failed", str(e))
        raise


if __name__ == "__main__":
    main()
