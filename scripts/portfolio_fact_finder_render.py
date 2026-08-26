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


if __name__ == "__main__":
    main()
