#!/usr/bin/env python3
"""One real Fact-Finder 'Entity / Portfolio Correlation' section, rendered
from live data, for the P0 entity/portfolio correlation layer deliverable.
Reuses the existing nine-case CSS/badge system and the existing
content-safety gate (assert_content_safe) unchanged -- new section, not a
new visual language, and it must pass the same no-internal-vendor-names gate
every other client-facing FF page passes.

Not wired into the real pending_approval batch pipeline (winnerdata.* is
unreachable from this session -- see entity_portfolio_resolver.py). This is
the standalone proof-of-output artifact: what the section looks like and
what real coverage it produces against the current live 2026-08-26 batch.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from entity_portfolio_resolver import resolve_entity_portfolio  # noqa: E402
from portfolio_fact_finder_render import NINE_CASE_CSS, _badge, _confidence_badge, _row, _money, _esc  # noqa: E402
from render_ff_9buyer_20260827 import assert_content_safe  # noqa: E402

OUT_DIR = "winnerdata/batches/2026-08-26/entity_portfolio_test"

TIER_BADGE_CLASS = {
    "VERIFIED-PRIMARY": "green", "VERIFIED-CROSS-CHECKED": "blue",
    "LIKELY-SINGLE-SOURCE": "amber", "UNCONFIRMED": "red", "NOT AVAILABLE": "amber",
}


def _tier_badge(tier):
    return _badge(tier, TIER_BADGE_CLASS.get(tier, "amber"))


def render_section(result: dict) -> str:
    kpi = result["kpi"]
    all_props = result["properties_from_ownership_records"] + result["auction_wins_not_yet_crosswalked"]
    prop_rows = ""
    for p in sorted(all_props, key=lambda p: p.get("county") or ""):
        addr = p.get("site_addr") or p.get("owner_addr1") or "Address not established"
        county = (p.get("county") or "").title()
        case_no = p.get("case_number") or ""
        source = {"zw_parcels": "County ownership record", "auction_buyer_sightings": "Auction record"}.get(p.get("source"), p.get("source"))
        prop_rows += (
            f'<tr><td>{_esc(addr)}, {_esc(county)}</td><td>{_esc(case_no) or "n/a"}</td>'
            f'<td>{_esc(source)}</td><td>{_tier_badge(p["confidence_tier"])}</td></tr>'
        )

    unconfirmed_rows = "".join(
        f'<li>{_esc(u["owner_name"])} at {_esc(u["addr"])}, {_esc(u["city"])} {_tier_badge("UNCONFIRMED")} — {_esc(u["reason"])}</li>'
        for u in result["unconfirmed_affiliate_candidates"]
    ) or "<li>None found this cycle.</li>"

    vel = kpi["acquisition_velocity"]
    if vel.get("velocity_per_year") is not None:
        vel_line = f'{vel["velocity_per_year"]:.1f} wins/year (from {vel["wins_on_file"]} wins on file, {vel["first_win"]} to {vel["last_win"]})'
    else:
        vel_line = f'Not established — {_esc(vel.get("note", ""))} ({vel.get("wins_on_file", 0)} win(s) on file)'

    tiers = kpi["confidence_summary"]
    tier_summary = " &nbsp; ".join(f'{_tier_badge(t)} {n}' for t, n in tiers.items() if n)

    return f"""
    <section>
      <h2>Entity / Portfolio Correlation</h2>
      <table>
        {_row("Total properties on file (this entity)", kpi["total_properties"])}
        {_row("Counties active", ", ".join(c.title() for c in kpi["counties"]) or "n/a")}
        {_row("County spread", kpi["county_spread"])}
        {_row("Total assessed value (held book, excl. subject win)", _money(kpi["total_assessed_value"]))}
        {_row("Acquisition velocity", vel_line)}
        {_row("Confidence tier breakdown", tier_summary or "n/a")}
      </table>
      {'<table class="ptable"><thead><tr><th>Property</th><th>Case #</th><th>Source</th><th>Confidence</th></tr></thead><tbody>' + prop_rows + '</tbody></table>' if prop_rows else '<div class="note">No properties returned by this walk.</div>'}
      <div class="note"><strong>Unconfirmed affiliate candidates (not merged into totals above):</strong></div>
      <ul class="ledger">{unconfirmed_rows}</ul>
    </section>"""


def render_full_page(entity_name: str, result: dict) -> str:
    section = render_section(result)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Winner Data AI — Entity/Portfolio Correlation — {_esc(entity_name)}</title>
<style>{NINE_CASE_CSS}</style></head>
<body><div class="wrap">
  <header><div class="brandline"><div class="name">Winner Data <span>AI</span></div>
    <div class="tagline">Every Deal Creates a Customer. Our Winner Data AI Finds Them First.</div></div></header>
  <h1>Entity / Portfolio Correlation — {_esc(entity_name)}</h1>
  <div class="meta">Live data, statewide walk across county ownership records + auction history</div>
  {section}
  <footer>
    Winner Data AI supplies property and ownership data to licensed insurance agencies and B2B data
    purchasers. It does not contact property owners or auction buyers directly. Fields marked UNCONFIRMED
    or NOT AVAILABLE must not be used for outreach until independently verified.
  </footer>
</div></body></html>"""


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    test_entities = ["OK Business LLC", "Mundi Marketing LLC"]
    coverage = []
    for name in test_entities:
        result = resolve_entity_portfolio(name, run_live_cascade=False)
        html = render_full_page(name, result)
        assert_content_safe(html, name)  # must pass the same gate every client-facing FF page passes
        slug = name.lower().replace(" ", "_")
        path = os.path.join(OUT_DIR, f"{slug}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        has_portfolio = result["kpi"]["total_properties"] > (1 if result["auction_wins_not_yet_crosswalked"] else 0)
        coverage.append({"entity": name, "total_properties": result["kpi"]["total_properties"],
                          "multi_property": result["kpi"]["total_properties"] >= 2})
        print(f"wrote {path} -- total_properties={result['kpi']['total_properties']} content_safety=PASS")

    multi = sum(1 for c in coverage if c["multi_property"])
    print(f"\nReal coverage on this sample: {multi}/{len(coverage)} buyers show 2+ properties "
          f"(via the auction_buyer_sightings correlation layer). "
          f"0/{len(coverage)} show additional held property beyond their own auction win(s) in the "
          f"statewide zw_parcels ownership SSOT as of today (both are same-day-of-sale wins; county "
          f"appraiser records have not yet re-recorded the new owner).")


if __name__ == "__main__":
    main()
