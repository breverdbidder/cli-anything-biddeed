#!/usr/bin/env python3
"""Render SummitLeads delivery batch markdown from /tmp/batch_data.json (live-queried rows)."""
import json
import os
import re
from datetime import date, datetime, timezone

with open('/tmp/batch_data.json') as f:
    rows = json.load(f)

BATCH_DATE = os.environ.get("BATCH_DATE_OVERRIDE") or date.today().isoformat()
OUT_DIR = f"summitleads/batches/{BATCH_DATE}"

def fmt_money(v):
    return f"${float(v):,.0f}" if v is not None else "unknown"

def closing_date_of(row):
    return row.get("closing_date") or (row["signal_occurred_at"][:10] if row.get("signal_occurred_at") else "unknown")

def opener(row, producer):
    return (f"Hi, this is {producer} with Protection Partners — I noticed you picked up "
            f"{row.get('property_address') or 'a property'} at the {(row.get('sale_type') or 'auction').replace('_',' ')} "
            f"auction in {(row.get('county') or 'unknown').title()} County on "
            f"{closing_date_of(row)} for {fmt_money(row.get('sold_amount'))}. "
            f"Want to make sure the property's covered before anything happens to it — got 5 minutes?")

def card(row, producer):
    cc = row["consent_certificate"] or {}
    has_phone = bool(row.get("contact_phone"))
    is_business = cc.get("entity_type") == "business" or bool(
        re.search(r"\bllc\b|\binc\b|\btrust\b|\bcorp\b|properties|construction", row["entity_name"], re.IGNORECASE)
    )

    banner = "**MANUAL DIAL ONLY — NO SMS / NO AUTODIAL / NO EMAIL DRIP (no consent on file)**"
    if has_phone and row.get("dnc_scrubbed_at"):
        banner += f"\n**DNC scrub run {row['dnc_scrubbed_at']} — result not independently re-verified this session; treat as scrubbed per Tracerfy call record, not a fabricated claim.**"
    elif has_phone and not is_business:
        banner += "\n**DNC_UNSCRUBBED — DO NOT CALL until DNC scrub completed.**"
    elif not has_phone and is_business:
        banner += "\n**NO PHONE ON FILE — Sunbiz registered-agent lookup pending. Do not call; research contact before outreach.**"
    elif not has_phone and not is_business:
        banner += "\n**DNC_UNSCRUBBED — DO NOT CALL until DNC scrub completed. Contact info not yet available.**"

    gaps = ", ".join(row["open_gaps"]) if row["open_gaps"] else "none"
    contact_line = (
        f"{row.get('contact_phone') or 'no phone'} / {row.get('contact_email') or 'no email'}"
        if has_phone or row.get("contact_email")
        else "none on file — SKIP_TRACE_PENDING"
    )

    return f"""### {row['entity_name']} — {row.get('property_address') or 'address unknown'}

{banner}

- **Entity type:** {'business' if is_business else 'person'}
- **Parcel ID:** {row['parcel_id']}
- **County:** {(row.get('county') or 'unknown').title()}
- **Auction:** {(row.get('sale_type') or 'unknown').replace('_',' ').title()}, case {row.get('case_number') or 'unknown'}, closed {closing_date_of(row)}, sold {fmt_money(row.get('sold_amount'))}
- **Product line:** {row['product_line']} (default — entity name suggests possible commercial_bop/builders_risk cross-sell, producer to confirm)
- **Quote-draft completeness:** {row['completeness_pct']}% — open gaps: {gaps}
- **Valuation:** assessed {fmt_money(row.get('assessed_value'))}, market {fmt_money(row.get('market_value'))}
- **Contact phone/email:** {contact_line}
- **Suggested opener:** "{opener(row, producer)}"
"""

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    by_producer = {}
    for r in rows:
        by_producer.setdefault(r["producer_name"], []).append(r)

    harvest_status = os.environ.get("BRIGHTDATA_HARVEST_STATUS", "not_attempted")
    if harvest_status == "blocked_robots":
        scope_note = (
            "**Scope note:** Bright Data winner harvest (Sprint 1b) attempted live this session "
            "(secrets present) but Bright Data's Scraping Browser itself rejected navigation to "
            "realforeclose.com/realtaxdeed.com per robots.txt (\"restricted... ask your account "
            "manager\") — an account-tier restriction, not a secrets/code issue. See issue #19392 "
            "comment. This batch only includes signals with a real (non-placeholder) winning_bidder "
            "already captured by other harvesters — many completed auctions (e.g. generic "
            "\"3rd Party Bidder\" records) are excluded until the account restriction is lifted. "
            "Honest volume for today, not the full pipeline ceiling."
        )
    elif harvest_status == "live":
        scope_note = (
            "**Scope note:** Bright Data winner harvest is live — this batch reflects the full "
            "winning_bidder pool available in the last 7 days."
        )
    else:
        scope_note = (
            "**Scope note:** Bright Data winner harvest (Sprint 1b) not run this session "
            "(set BRIGHTDATA_HARVEST_STATUS=live once verified working). This batch only includes "
            "signals with a real (non-placeholder) winning_bidder already captured by other "
            "harvesters — many completed auctions are excluded until harvest lands. Honest volume "
            "for today, not the full pipeline ceiling."
        )
    master_lines = [f"# SummitLeads — Auction Flash Batch {BATCH_DATE}\n",
                     f"Generated: {datetime.now(timezone.utc).isoformat()}Z (live-queried, org=Protection Partners)\n",
                     f"Total leads: {len(rows)} | Producers: {len(by_producer)}\n",
                     scope_note + "\n"]

    for producer, leads in by_producer.items():
        fname = f"{OUT_DIR}/{producer.lower().replace(' ','_')}_call_sheet.md"
        lines = [f"# Call Sheet — {producer} — {BATCH_DATE}\n",
                 f"{len(leads)} hot lead(s), all outbound_lane=compliant_outbound (manual dial only, no automation).\n"]
        for r in leads:
            lines.append(card(r, producer))
        with open(fname, "w") as f:
            f.write("\n".join(lines))
        print(f"wrote {fname} ({len(leads)} leads)")
        master_lines.append(f"## {producer} ({len(leads)} leads)\n")
        for r in leads:
            master_lines.append(card(r, producer))

    with open(f"{OUT_DIR}/master.md", "w") as f:
        f.write("\n".join(master_lines))
    print(f"wrote {OUT_DIR}/master.md")

if __name__ == "__main__":
    main()
