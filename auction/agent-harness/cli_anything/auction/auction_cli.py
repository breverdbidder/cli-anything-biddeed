#!/usr/bin/env python3
"""Auction CLI — Agent-native foreclosure auction intelligence.

Usage:
    cli-anything-auction --json discover upcoming
    cli-anything-auction analyze case --case 2024-CA-001234
    cli-anything-auction report generate --case 2024-CA-001234 --format text
    cli-anything-auction   # Enter REPL
"""

import json
import sys
import os
import click
from typing import Optional

from cli_anything.auction.core.session import Session
from cli_anything.auction.core import discovery
from cli_anything.auction.core import analysis
from cli_anything.auction.core import title_search
from cli_anything.auction.core import report as report_mod
from cli_anything.auction.core import export as export_mod

_session: Optional[Session] = None
_json_output = False


def get_session() -> Session:
    global _session
    if _session is None:
        _session = Session()
    return _session


def output(data, message: str = ""):
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    click.echo(f"  {k}: {json.dumps(v, default=str)}")
                else:
                    click.echo(f"  {k}: {v}")
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    click.echo(f"  {' | '.join(f'{k}={v}' for k, v in item.items())}")
                else:
                    click.echo(f"  {item}")


def handle_error(func):
    import functools
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ValueError, RuntimeError, FileNotFoundError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}))
            else:
                click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    return wrapper


# ── Main CLI Group ────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output in JSON format")
@click.option("--persist", is_flag=True, help="Persist results to Supabase")
@click.pass_context
def cli(ctx, use_json, persist):
    """Auction CLI — Agent-native foreclosure auction intelligence."""
    global _json_output
    _json_output = use_json
    ctx.ensure_object(dict)
    ctx.obj["json"] = use_json
    ctx.obj["persist"] = persist
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── Discover commands ─────────────────────────────────────────────────

@cli.group()
def discover():
    """Discover upcoming auctions."""
    pass


@discover.command("upcoming")
@click.option("--date", help="Target date (YYYY-MM-DD)")
@handle_error
def discover_upcoming(date):
    """List upcoming auction dates."""
    result = discovery.get_upcoming_auctions(date)
    output(result, f"Upcoming auctions:")


@discover.command("scrape")
@click.option("--date", required=True, help="Auction date (YYYY-MM-DD)")
@click.pass_context
@handle_error
def discover_scrape(ctx, date):
    """Scrape auction list for a date."""
    cases = discovery.scrape_auction_list(date)
    session = get_session()
    session.record(f"discover scrape --date {date}", f"{len(cases)} cases")

    result = {"date": date, "cases_found": len(cases), "cases": cases}
    if ctx.obj.get("persist"):
        try:
            from cli_anything_shared.supabase import persist_result
            db_row = persist_result("auction_scrapes", result, cli_name="auction")
            result["db_id"] = db_row.get("id")
        except Exception as e:
            result["persist_error"] = str(e)

    output(result, f"✓ Found {len(cases)} cases for {date}")


@discover.command("status")
@handle_error
def discover_status():
    """Show discovery status."""
    output({"status": "ready", "data_source": "sample"})


# ── Analyze commands ──────────────────────────────────────────────────

@cli.group()
def analyze():
    """Analyze foreclosure cases."""
    pass


@analyze.command("case")
@click.option("--case", "case_number", required=True, help="Case number")
@click.option("--arv", type=float, help="Override ARV estimate")
@click.option("--repairs", type=float, help="Override repair estimate")
@click.pass_context
@handle_error
def analyze_case_cmd(ctx, case_number, arv, repairs):
    """Full analysis of a single case."""
    case_data = discovery.get_case_details(case_number)
    if not case_data:
        raise ValueError(f"Case {case_number} not found. Use 'discover scrape --date sample' to load sample data.")

    result = analysis.analyze_case(case_data, arv=arv, repairs=repairs)
    session = get_session()
    session.record(f"analyze case --case {case_number}", result.get("recommendation"))

    if ctx.obj.get("persist"):
        try:
            from cli_anything_shared.supabase import persist_result
            db_row = persist_result("auction_analysis", result, cli_name="auction")
            result["db_id"] = db_row.get("id")
        except Exception as e:
            result["persist_error"] = str(e)

    rec = result.get("recommendation", "?")
    ratio = result.get("bid_ratio", 0)
    output(result, f"✓ Case {case_number}: {rec} (ratio: {ratio:.1%})")


@analyze.command("batch")
@click.option("--date", required=True, help="Auction date or 'sample'")
@click.pass_context
@handle_error
def analyze_batch(ctx, date):
    """Analyze all cases for a date."""
    cases = discovery.scrape_auction_list(date)
    if not cases:
        raise ValueError(f"No cases found for {date}. Try --date sample")

    result = analysis.batch_analyze(cases)
    session = get_session()
    session.record(f"analyze batch --date {date}", f"{result['bid']} BID / {result['review']} REVIEW / {result['skip']} SKIP")

    if ctx.obj.get("persist"):
        try:
            from cli_anything_shared.supabase import persist_result
            db_row = persist_result("auction_batch_analysis", result, cli_name="auction")
            result["db_id"] = db_row.get("id")
        except Exception as e:
            result["persist_error"] = str(e)

    output(result, f"✓ Analyzed {result['total']}: {result['bid']} BID / {result['review']} REVIEW / {result['skip']} SKIP")


@analyze.command("liens")
@click.option("--case", "case_number", required=True, help="Case number")
@handle_error
def analyze_liens(case_number):
    """Lien priority analysis for a case."""
    liens = title_search.search_liens(case_number)
    priority = title_search.get_lien_priority(liens)

    case_data = discovery.get_case_details(case_number)
    plaintiff = case_data.get("plaintiff", "") if case_data else ""
    senior = title_search.detect_senior_mortgage(liens, plaintiff)

    result = {"case_number": case_number, "liens": priority, "senior_mortgage": senior}
    output(result, f"Liens for {case_number}:")


# ── Recommend commands ────────────────────────────────────────────────

@cli.group()
def recommend():
    """Get recommendations."""
    pass


@recommend.command("bid")
@click.option("--date", required=True, help="Auction date or 'sample'")
@click.option("--min-ratio", type=float, default=0.75, help="Minimum bid ratio")
@handle_error
def recommend_bid(date, min_ratio):
    """Show BID recommendations."""
    cases = discovery.scrape_auction_list(date)
    batch = analysis.batch_analyze(cases)
    bids = [r for r in batch["results"] if r.get("recommendation") == "BID"]
    result = {"date": date, "min_ratio": min_ratio, "count": len(bids), "cases": bids}
    output(result, f"BID recommendations for {date}: {len(bids)}")


@recommend.command("summary")
@click.option("--date", required=True, help="Auction date or 'sample'")
@handle_error
def recommend_summary(date):
    """Full recommendation summary."""
    cases = discovery.scrape_auction_list(date)
    result = analysis.batch_analyze(cases)
    output(result, f"Summary for {date}:")


# ── Report commands ───────────────────────────────────────────────────

@cli.group()
def report():
    """Generate reports."""
    pass


@report.command("generate")
@click.option("--case", "case_number", required=True, help="Case number")
@click.option("--format", "fmt", default="text", type=click.Choice(["text", "json", "docx"]))
@click.option("-o", "--output-path", help="Output file path")
@handle_error
def report_generate(case_number, fmt, output_path):
    """Generate report for a single case."""
    case_data = discovery.get_case_details(case_number)
    if not case_data:
        raise ValueError(f"Case {case_number} not found")
    case_analysis = analysis.analyze_case(case_data)

    if not output_path:
        ext = {"text": "txt", "json": "json", "docx": "docx"}[fmt]
        output_path = f"report_{case_number.replace('-', '_')}.{ext}"

    result = report_mod.generate_report(case_analysis, fmt=fmt, output_path=output_path)
    output(result, f"✓ Report generated: {output_path}")


@report.command("batch")
@click.option("--date", required=True, help="Auction date or 'sample'")
@click.option("-o", "--output-dir", default="./reports", help="Output directory")
@click.option("--format", "fmt", default="text", type=click.Choice(["text", "json", "docx"]))
@handle_error
def report_batch(date, output_dir, fmt):
    """Generate reports for all cases on a date."""
    cases = discovery.scrape_auction_list(date)
    analyses = [analysis.analyze_case(c) for c in cases]
    result = report_mod.batch_reports(analyses, output_dir, fmt=fmt)
    output(result, f"✓ Generated {result['generated']} reports in {output_dir}")


# ── Export commands ───────────────────────────────────────────────────

@cli.group("export")
def export_group():
    """Export data."""
    pass


@export_group.command("csv")
@click.option("--date", required=True, help="Auction date or 'sample'")
@click.option("-o", "--output-path", required=True, help="Output file")
@handle_error
def export_csv(date, output_path):
    """Export analysis to CSV."""
    cases = discovery.scrape_auction_list(date)
    batch = analysis.batch_analyze(cases)
    result = export_mod.to_csv(batch["results"], output_path)
    output(result, f"✓ Exported to {output_path}")


@export_group.command("supabase")
@click.option("--date", required=True, help="Auction date or 'sample'")
@handle_error
def export_supabase(date):
    """Push analysis to Supabase."""
    cases = discovery.scrape_auction_list(date)
    batch = analysis.batch_analyze(cases)
    result = export_mod.to_supabase(batch["results"])
    output(result)


# ── Config commands ───────────────────────────────────────────────────

@cli.group()
def config():
    """Configuration."""
    pass


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    from cli_anything_shared.config import save_config
    save_config("auction", key, value)
    output({"key": key, "status": "saved"}, f"✓ Set {key}")


@config.command("get")
@click.argument("key", required=False)
def config_get(key):
    from cli_anything_shared.config import load_config, get_config
    if key:
        output({"key": key, "value": get_config("auction", key)})
    else:
        output(load_config("auction"))


# ── Session commands ──────────────────────────────────────────────────

@cli.group()
def session():
    """Session management."""
    pass


@session.command("status")
def session_status():
    output(get_session().status())


@session.command("history")
def session_history():
    s = get_session()
    if _json_output:
        click.echo(json.dumps(s.history, indent=2, default=str))
    else:
        for entry in s.history[-20:]:
            click.echo(f"  [{entry.get('timestamp', '?')}] {entry.get('command', '?')}")


@session.command("undo")
def session_undo():
    entry = get_session().undo()
    if entry:
        output(entry, f"✓ Undid: {entry.get('command', '?')}")
    else:
        output({"message": "Nothing to undo"})


# ── REPL ──────────────────────────────────────────────────────────────

@cli.command(hidden=True)
def repl():
    """Interactive REPL mode."""
    try:
        from cli_anything.auction.utils.repl_skin import ReplSkin
        skin = ReplSkin("auction", version="1.0.0")
    except ImportError:
        skin = None

    if skin:
        skin.print_banner()

    s = get_session()

    while True:
        try:
            label = s.current_county or "ready"
            if skin:
                try:
                    pt_session = skin.create_prompt_session()
                    line = skin.get_input(pt_session, project_name=label)
                except Exception:
                    line = input(f"auction[{label}]> ")
            else:
                line = input(f"auction[{label}]> ")

            line = line.strip()
            if not line:
                continue
            if line in ("exit", "quit", "q"):
                if skin:
                    skin.print_goodbye()
                else:
                    click.echo("Goodbye! 👋")
                break

            args = line.split()
            try:
                cli.main(args, standalone_mode=False)
            except SystemExit:
                pass
            except Exception as e:
                click.echo(f"Error: {e}", err=True)

        except (EOFError, KeyboardInterrupt):
            click.echo()
            if skin:
                skin.print_goodbye()
            else:
                click.echo("Goodbye! 👋")
            break


def main():
    cli()


if __name__ == "__main__":
    main()
