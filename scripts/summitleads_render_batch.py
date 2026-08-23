#!/usr/bin/env python3
"""Render SummitLeads delivery batch markdown from /tmp/batch_data.json (live-queried rows)."""
import json
import os
from datetime import date, datetime, timezone

with open('/tmp/batch_data.json') as f:
    rows = json.load(f)

BATCH_DATE = os.environ.get("BATCH_DATE_OVERRIDE") or date.today().isoformat()
OUT_DIR = f"summitleads/batches/{BATCH_DATE}"

def fmt_money(v):
    return f"${float(v):,.0f}" if v is not None else "unknown"

def opener(row, producer):
    ep = row["event_payload"]
    return (f"Hi, this is {producer} with Protection Partners — I noticed you picked up "
            f"{row['payload']['location']['address']} at the {ep['sale_type'].replace('_',' ')} "
            f"auction in {row['payload']['location']['county'].title()} County on "
            f"{row['closing_date']} for {fmt_money(ep.get('sold_amount'))}. "
            f"Want to make sure the property's covered before anything happens to it — got 5 minutes?")

def card(row, producer):
    cc = row["consent_certificate"]
    banner = "**MANUAL DIAL ONLY — NO SMS / NO AUTODIAL / NO EMAIL DRIP (no consent on file)**"
    if cc.get("compliance_flag") == "DNC_UNSCRUBBED":
        banner += "\n**DNC_UNSCRUBBED — DO NOT CALL until DNC scrub completed. Contact info not yet available (Tracerfy key absent this session).**"
    elif cc.get("compliance_flag") == "NO_CONTACT_INFO_SUNBIZ_LOOKUP_PENDING":
        banner += "\n**NO PHONE ON FILE — Sunbiz registered-agent lookup pending (tool unavailable this session). Do not call; research contact before outreach.**"

    gaps = ", ".join(row["open_gaps"]) if row["open_gaps"] else "none"
    loc = row["payload"]["location"]
    val = row["payload"]["valuation"]
    ep = row["event_payload"]

    return f"""### {row['entity_name']} — {loc['address']}

{banner}

- **Entity type:** {cc['entity_type']}
- **Parcel ID:** {row['parcel_id']}
- **County:** {loc['county'].title()}
- **Auction:** {ep['sale_type'].replace('_',' ').title()}, case {ep['case_number']}, closed {row['closing_date']}, sold {fmt_money(ep.get('sold_amount'))}
- **Product line:** {row['product_line']} (default — entity name suggests possible commercial_bop/builders_risk cross-sell, producer to confirm)
- **Quote-draft completeness:** {row['completeness_pct']}% — open gaps: {gaps}
- **Valuation:** assessed {fmt_money(val.get('assessed_value'))}, market {fmt_money(val.get('market_value'))}
- **Contact phone/email:** none on file — {cc['skip_trace_status']}
- **Suggested opener:** "{opener(row, producer)}"
"""

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    by_producer = {}
    for r in rows:
        by_producer.setdefault(r["producer_name"], []).append(r)

    brightdata_live = bool(os.environ.get("BRIGHTDATA_API_KEY") and os.environ.get("BRIGHTDATA_BROWSER_WSS"))
    scope_note = (
        "**Scope note:** Bright Data winner harvest is live — this batch reflects the full "
        "winning_bidder pool available in the last 7 days."
        if brightdata_live else
        "**Scope note:** Bright Data winner harvest (Sprint 1b) is BLOCKED "
        "(BRIGHTDATA_API_KEY/BRIGHTDATA_BROWSER_WSS absent). This batch only includes signals with a "
        "real (non-placeholder) winning_bidder already captured by other harvesters — many completed "
        "auctions (e.g. Brevard tax deeds recorded as generic \"3rd Party Bidder\") are excluded until "
        "harvest secrets land. Honest volume for today, not the full pipeline ceiling."
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
