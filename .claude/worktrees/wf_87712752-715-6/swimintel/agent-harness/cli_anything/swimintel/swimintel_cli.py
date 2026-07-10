#!/usr/bin/env python3
"""SwimIntel CLI — Agent-native competitive swim intelligence pipeline.

Agent #139 Orchestrator in the BidDeed AI Army.
Coordinates: Parser (#139.1), Analyzer (#139.2), Report (#139.3)

Usage:
    cli-anything-swimintel parse --pdf psychsheet.pdf --output parsed.json
    cli-anything-swimintel analyze --data parsed.json --swimmer "Shapira, Michael" --age-group 15-16
    cli-anything-swimintel report --data parsed.json --swimmer "Shapira, Michael" --output report.docx
    cli-anything-swimintel pipeline --pdf psychsheet.pdf --swimmer "Shapira, Michael"
    cli-anything-swimintel   # Enter REPL
"""

import json
import sys
import os
import click
import functools
from typing import Optional

from cli_anything.swimintel.core.session import Session
from cli_anything.swimintel.core import parser
from cli_anything.swimintel.core import analyzer
from cli_anything.swimintel.core import report

__version__ = "1.0.0"
__agent_id__ = 139

_session: Optional[Session] = None
_json_output = False


def get_session() -> Session:
    global _session
    if _session is None:
        _session = Session.load()
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
                    click.echo(f"  {k}: {json.dumps(v, default=str)[:120]}")
                else:
                    click.echo(f"  {k}: {v}")


def handle_error(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e)}))
            else:
                click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    return wrapper


# ============================================================
# CLI GROUP
# ============================================================
@click.group(invoke_without_command=True)
@click.option("--json", "json_flag", is_flag=True, help="Output as JSON")
@click.option("--version", is_flag=True, help="Show version")
@click.pass_context
def cli(ctx, json_flag, version):
    """SwimIntel CLI — Competitive swim intelligence pipeline (Agent #139)."""
    global _json_output
    _json_output = json_flag

    if version:
        click.echo(f"cli-anything-swimintel v{__version__} (Agent #{__agent_id__})")
        return

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl_cmd)


# ============================================================
# PARSE COMMAND
# ============================================================
@cli.command("parse")
@click.option("--pdf", required=True, type=click.Path(exists=True), help="Path to psych sheet PDF")
@click.option("--output", "-o", default=None, help="Output JSON path")
@handle_error
def parse_cmd(pdf, output_path):
    """Parse a psych sheet PDF into structured JSON."""
    click.echo(f"Parsing: {pdf}")

    data = parser.parse_pdf(pdf)

    if output_path:
        parser.save_parsed(data, output_path)
        click.echo(f"Saved to: {output_path}")

    sess = get_session()
    sess.parsed_data = data
    sess.pdf_path = pdf
    sess.save()

    output(data["stats"], f"Parsed {data['stats']['total_events']} events, {data['stats']['total_entries']} entries")


# ============================================================
# ANALYZE COMMAND
# ============================================================
@cli.command("analyze")
@click.option("--data", "data_path", type=click.Path(exists=True), help="Parsed JSON path")
@click.option("--swimmer", required=True, help="Swimmer name (Last, First)")
@click.option("--age-group", default="15-16", help="Age group (14U, 15-16, 17-18, 19O)")
@click.option("--output", "-o", default=None, help="Output JSON path")
@handle_error
def analyze_cmd(data_path, swimmer, age_group, output_path):
    """Analyze a swimmer's competitive position."""
    sess = get_session()

    if data_path:
        with open(data_path) as f:
            parsed = json.load(f)
    elif sess.has_data:
        parsed = sess.parsed_data
    else:
        raise click.UsageError("No data loaded. Run 'parse' first or provide --data")

    click.echo(f"Analyzing: {swimmer} in {age_group} age group")
    analysis = analyzer.analyze_swimmer(parsed, swimmer, age_group)

    sess.analysis = analysis
    sess.swimmer_name = swimmer
    sess.age_group = age_group
    sess.save()

    if output_path:
        with open(output_path, "w") as f:
            json.dump(analysis, f, indent=2, default=str)
        click.echo(f"Analysis saved to: {output_path}")

    # Print summary
    for evt in analysis["events"]:
        verdict_color = "green" if "FINAL" in evt["verdict"] else "yellow"
        click.echo(
            f"  {evt['event_name']:30s} "
            f"#{evt['age_group_rank']:>3}/{evt['age_group_total']:<3}  "
            f"A:{evt['a_final_pct']:>4.0%}  B:{evt['b_final_pct']:>4.0%}  "
            f"{evt['verdict']}"
        )

    if analysis.get("summary"):
        click.echo(f"\n  Best event: {analysis['summary']['best_event']} ({analysis['summary']['best_verdict']})")


# ============================================================
# REPORT COMMAND
# ============================================================
@cli.command("report")
@click.option("--data", "data_path", type=click.Path(exists=True), help="Parsed JSON path")
@click.option("--analysis", "analysis_path", type=click.Path(exists=True), help="Analysis JSON path")
@click.option("--swimmer", default=None, help="Swimmer name (if re-analyzing)")
@click.option("--age-group", default="15-16", help="Age group")
@click.option("--output", "-o", default="swim_report.docx", help="Output DOCX path")
@handle_error
def report_cmd(data_path, analysis_path, swimmer, age_group, output_path):
    """Generate a DOCX competitive intelligence report."""
    sess = get_session()

    if analysis_path:
        with open(analysis_path) as f:
            analysis = json.load(f)
    elif sess.has_analysis:
        analysis = sess.analysis
    elif data_path and swimmer:
        with open(data_path) as f:
            parsed = json.load(f)
        analysis = analyzer.analyze_swimmer(parsed, swimmer, age_group)
    elif sess.has_data and swimmer:
        analysis = analyzer.analyze_swimmer(sess.parsed_data, swimmer, age_group)
    else:
        raise click.UsageError("No analysis data. Run 'analyze' first or provide --analysis/--data")

    click.echo(f"Generating report: {output_path}")
    result = report.generate_report(analysis, output_path)

    if result.get("status") == "ok":
        click.echo(f"Report saved: {output_path}")
    else:
        click.echo(f"Report generation failed: {result.get('message', 'Unknown error')}", err=True)

    output(result)


# ============================================================
# PIPELINE COMMAND (full flow)
# ============================================================
@cli.command("pipeline")
@click.option("--pdf", required=True, type=click.Path(exists=True), help="Psych sheet PDF")
@click.option("--swimmer", required=True, help="Swimmer name (Last, First)")
@click.option("--age-group", default="15-16", help="Age group")
@click.option("--output", "-o", default="swim_report.docx", help="Output DOCX path")
@handle_error
def pipeline_cmd(pdf, swimmer, age_group, output_path):
    """Full pipeline: parse PDF → analyze → generate DOCX report."""
    click.echo(f"SwimIntel Pipeline v{__version__} (Agent #{__agent_id__})")
    click.echo(f"{'='*60}")

    # Phase 1: Parse
    click.echo(f"\n[1/3] Parsing: {pdf}")
    parsed = parser.parse_pdf(pdf)
    click.echo(f"  → {parsed['stats']['total_events']} events, {parsed['stats']['total_entries']} entries")

    # Phase 2: Analyze
    click.echo(f"\n[2/3] Analyzing: {swimmer} ({age_group})")
    analysis = analyzer.analyze_swimmer(parsed, swimmer, age_group)
    for evt in analysis["events"]:
        click.echo(f"  → {evt['event_name']:30s} #{evt['age_group_rank']}/{evt['age_group_total']}  {evt['verdict']}")

    # Phase 3: Report
    click.echo(f"\n[3/3] Generating report: {output_path}")
    result = report.generate_report(analysis, output_path)

    if result.get("status") == "ok":
        click.echo(f"\n{'='*60}")
        click.echo(f"Report ready: {output_path}")
        if analysis.get("summary"):
            click.echo(f"Best event: {analysis['summary']['best_event']} ({analysis['summary']['best_verdict']})")
    else:
        click.echo(f"Report failed: {result.get('message')}", err=True)

    # Save session
    sess = get_session()
    sess.parsed_data = parsed
    sess.analysis = analysis
    sess.swimmer_name = swimmer
    sess.age_group = age_group
    sess.pdf_path = pdf
    sess.save()


# ============================================================
# STATUS COMMAND
# ============================================================
@cli.command("status")
@handle_error
def status_cmd():
    """Show current session status."""
    sess = get_session()
    output(sess.status(), "SwimIntel Session Status:")


# ============================================================
# REPL
# ============================================================
@cli.command("repl", hidden=True)
def repl_cmd():
    """Interactive REPL mode."""
    click.echo(f"┌{'─'*58}┐")
    click.echo(f"│ {'SwimIntel CLI v' + __version__:^56s} │")
    click.echo(f"│ {'Agent #139 — BidDeed AI Army':^56s} │")
    click.echo(f"│ {'Competitive Swim Intelligence Pipeline':^56s} │")
    click.echo(f"└{'─'*58}┘")
    click.echo()
    click.echo("Commands: parse, analyze, report, pipeline, status, quit")
    click.echo("Type 'help' for usage or 'quit' to exit.")
    click.echo()

    while True:
        try:
            line = input("swimintel> ").strip()
        except (EOFError, KeyboardInterrupt):
            click.echo("\nGoodbye.")
            break

        if not line:
            continue
        if line in ("quit", "exit", "q"):
            click.echo("Goodbye.")
            break
        if line == "help":
            click.echo("  parse    --pdf <file>                    Parse psych sheet PDF")
            click.echo("  analyze  --swimmer <name> [--age-group]  Analyze swimmer position")
            click.echo("  report   --output <file>                 Generate DOCX report")
            click.echo("  pipeline --pdf <file> --swimmer <name>   Full pipeline")
            click.echo("  status                                   Show session state")
            continue

        # Parse REPL input into Click args
        parts = line.split()
        try:
            cli.main(parts, standalone_mode=False)
        except SystemExit:
            pass
        except Exception as e:
            click.echo(f"Error: {e}")


def main():
    cli()


if __name__ == "__main__":
    main()
