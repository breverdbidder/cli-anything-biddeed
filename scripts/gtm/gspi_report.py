#!/usr/bin/env python3
"""GTM-2 (issue #20031) -- G-SPI daily report + Friday memo generator.

Reads public.v_gspi_daily / finance.v_gtm_unit_economics /
winnerdata.v_variant_scoreboard / public.spi_daily / public.spi_gates
(read-only, never written by this script -- spi_daily/spi_gates are on
the M2 protected list) via the Management API, same live-SQL path this
repo already uses everywhere psql/exec_sql are unavailable
(scripts/biddeed_reels_lib.run_sql, SUPABASE_ACCESS_TOKEN).

G-SPI stays distinct from the Founder D0 SPI per Ariel's Aug 26 directive:
this script's `spi` command prints the D0 block as a separate, clearly
labeled section above the G-SPI block -- it never merges the two, and it
never writes to spi_daily/spi_gates.

CLI:
  python3 scripts/gtm/gspi_report.py spi              # D0 SPI + G-SPI block, stdout only (for chat's /spi)
  python3 scripts/gtm/gspi_report.py memo [--date YYYY-MM-DD]   # renders docs/gtm/memos/YYYY-MM-DD.md
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import biddeed_reels_lib as lib  # noqa: E402


def q(sql: str):
    return lib.run_sql(sql)


def fmt_usd(v) -> str:
    if v is None:
        return "n/a"
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return "n/a"


def gspi_rows(days: int = 7):
    return q(f"select * from public.v_gspi_daily order by day desc limit {int(days)}")


def unit_economics():
    rows = q("select * from finance.v_gtm_unit_economics")
    return rows[0] if rows else {}


def variant_kill_keep():
    return q(
        """
        select archetype,
               coalesce(sum(plays), 0) as plays,
               coalesce(sum(clicks), 0) as clicks,
               coalesce(sum(captures), 0) as captures,
               case when sum(plays) > 0 then round(100.0 * sum(clicks) / sum(plays), 2) else null end as ctr_pct
        from winnerdata.v_variant_scoreboard
        group by archetype
        order by ctr_pct desc nulls last
        """
    )


def spi_daily_latest():
    rows = q("select * from public.spi_daily order by day desc limit 1")
    return rows[0] if rows else None


def spi_gates_open():
    return q(
        "select gate_key, title, opened_at from public.spi_gates "
        "where verified_at is null order by opened_at"
    )


def render_d0_block() -> str:
    lines = ["## D0 Founder SPI"]
    latest = spi_daily_latest()
    if latest:
        lines.append(
            f"Latest row ({latest['day']}, VERIFIED public.spi_daily): "
            f"SPI={latest.get('spi')} · gate_age_days={latest.get('gate_age_days')} · "
            f"abandonment={latest.get('abandonment')} · build_sell_pct={latest.get('build_sell_pct')}"
        )
    else:
        lines.append("No rows yet in public.spi_daily (VERIFIED: queried live, 0 rows).")
    gates = spi_gates_open()
    if gates:
        lines.append("")
        lines.append("Open gates (public.spi_gates, verified_at IS NULL):")
        for g in gates:
            lines.append(f"- `{g['gate_key']}` ({g['title']}) -- opened {g['opened_at']}")
    else:
        lines.append("")
        lines.append("No open gates (VERIFIED: queried public.spi_gates live).")
    return "\n".join(lines)


def render_gspi_block(days: int = 7) -> str:
    rows = gspi_rows(days)
    ue = unit_economics()
    any_activity = any(
        int(r.get("clicks") or 0) or int(r.get("purchases") or 0) or int(r.get("deal_views") or 0)
        for r in rows
    )
    lines = ["## G-SPI (growth) -- distinct from the Founder D0 SPI above"]
    lines.append("")
    if not any_activity:
        lines.append(
            f"No rows yet with real activity in the last {days} days "
            "(VERIFIED: queried public.v_gspi_daily live -- 0 is a real reading, not a gap)."
        )
    lines.append("")
    lines.append("| day | views | clicks | view→click% | deal_views | captures | signups | checkouts | purchases | MRR |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"| {r['day']} | {r['views']} | {r['clicks']} | {r.get('view_to_click_pct') or '—'} | "
            f"{r['deal_views']} | {r['captures']} | {r['signups']} | {r['checkouts_started']} | "
            f"{r['purchases']} | {fmt_usd(r.get('mrr_usd'))} |"
        )
    lines.append("")
    lines.append(
        f"Current MRR (VERIFIED, finance.v_gtm_unit_economics): {fmt_usd(ue.get('mrr_usd'))} · "
        f"paying customers: {ue.get('paying_customers', 0)} · ARPU: {fmt_usd(ue.get('arpu_usd'))} · "
        f"CAC per paying customer (all-time, thin manually-reconciled ledger -- INFERRED, not a full "
        f"vendor feed): {fmt_usd(ue.get('cac_usd_per_paying_customer'))} · "
        f"LTV proxy (ASSUMED 12mo avg tenure, no churn history exists yet): "
        f"{fmt_usd(ue.get('ltv_proxy_usd_assumed_12mo'))}"
    )
    return "\n".join(lines)


def render_kill_keep_block() -> str:
    rows = variant_kill_keep()
    lines = ["## Kill/keep -- per-archetype scoreboard (winnerdata.v_variant_scoreboard)"]
    lines.append("")
    if not rows:
        lines.append("No rows yet (VERIFIED: queried live, 0 archetypes with variants).")
        return "\n".join(lines)
    lines.append("| archetype | plays | clicks | captures | ctr% | verdict |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        plays = int(r["plays"] or 0)
        ctr = r.get("ctr_pct")
        if plays >= 2000 and (ctr is None or float(ctr) < 0.3):
            verdict = "kill (SOP §8: ≥2,000 plays, <0.3% CTR)"
        elif ctr is not None and float(ctr) > 2.0:
            verdict = "2x allocation (SOP §8: >2% CTR)"
        else:
            verdict = "hold -- insufficient signal" if plays < 2000 else "hold"
        lines.append(f"| {r['archetype']} | {plays} | {r['clicks']} | {r['captures']} | {ctr if ctr is not None else '—'} | {verdict} |")
    return "\n".join(lines)


def render_reforecast_block(days: int = 7) -> str:
    """SOP §1 re-forecast: recompute required daily volume from measured
    rates when there is enough signal; otherwise say so flatly (Honesty
    V3 -- ASSUMED values stand until measured)."""
    rows = gspi_rows(days)
    total_views = sum(int(r.get("views") or 0) for r in rows)
    total_clicks = sum(int(r.get("clicks") or 0) for r in rows)
    total_deal_views = sum(int(r.get("deal_views") or 0) for r in rows)
    total_captures = sum(int(r.get("captures") or 0) for r in rows)
    lines = ["## Re-forecast (SOP §1)"]
    lines.append("")
    if total_views < 100:
        lines.append(
            f"ASSUMED rates still stand -- only {total_views} views measured over the last {days} days "
            "(too small a sample to re-forecast honestly). SOP §1 assumptions unchanged: "
            "view→click 1.0%, deal→capture 15%, capture→free 40%, free→paid 4%."
        )
        return "\n".join(lines)
    view_to_click = round(100.0 * total_clicks / total_views, 2) if total_views else None
    deal_to_capture = round(100.0 * total_captures / total_deal_views, 2) if total_deal_views else None
    lines.append(f"Measured view→click over last {days} days: {view_to_click}% (SOP assumption: 1.0%)")
    lines.append(f"Measured deal-view→capture over last {days} days: {deal_to_capture if deal_to_capture is not None else 'n/a'}% (SOP assumption: 15%)")
    if view_to_click:
        daily_views_needed = round(1.3 / (view_to_click / 100) / (deal_to_capture / 100 if deal_to_capture else 0.15) / 0.40 / 0.04)
        lines.append(f"Re-forecast daily views needed for 1.3 paid/day at these measured rates: {daily_views_needed:,}")
    return "\n".join(lines)


def cmd_spi(args):
    print(render_d0_block())
    print()
    print(render_gspi_block(days=args.days))


def cmd_memo(args):
    date_str = args.date
    if not date_str:
        rows = q("select current_date::text as d")
        date_str = rows[0]["d"]
    sections = [
        f"# GTM Friday memo -- {date_str}",
        "",
        "Evidence tags: VERIFIED = observed live this run · INFERRED = derived from a partial/thin "
        "source, methodology stated · ASSUMED = SOP planning assumption not yet replaced by measurement.",
        "",
        render_gspi_block(days=7),
        "",
        render_kill_keep_block(),
        "",
        render_reforecast_block(days=7),
    ]
    content = "\n".join(sections) + "\n"
    out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "gtm", "memos")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{date_str}.md")
    with open(out_path, "w") as f:
        f.write(content)
    print(out_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_spi = sub.add_parser("spi", help="D0 SPI + G-SPI growth block, stdout only")
    p_spi.add_argument("--days", type=int, default=7)
    p_spi.set_defaults(func=cmd_spi)

    p_memo = sub.add_parser("memo", help="render docs/gtm/memos/YYYY-MM-DD.md")
    p_memo.add_argument("--date", default=None, help="YYYY-MM-DD; defaults to current_date from the DB")
    p_memo.set_defaults(func=cmd_memo)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
