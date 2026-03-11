#!/usr/bin/env python3
"""ZoneWise CLI — Agent-native zoning data pipeline.

Usage:
    cli-anything-zonewise --json county list
    cli-anything-zonewise county scrape --county brevard
    cli-anything-zonewise parcel lookup --address "123 Main St, Melbourne FL"
    cli-anything-zonewise   # Enter REPL
"""

import json
import sys
import os
import click
from typing import Optional

from cli_anything.zonewise.core.session import Session
from cli_anything.zonewise.core import scraper
from cli_anything.zonewise.core import parser
from cli_anything.zonewise.core import export as export_mod

_session: Optional[Session] = None
_json_output = False


def get_session() -> Session:
    global _session
    if _session is None:
        _session = Session()
    return _session


def output(data, message: str = ""):
    """Output data as JSON or human-readable."""
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
                    parts = [f"{k}={v}" for k, v in item.items()]
                    click.echo(f"  {' | '.join(parts)}")
                else:
                    click.echo(f"  {item}")


def handle_error(func):
    """Error handler wrapper for CLI commands."""
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
    """ZoneWise CLI — Agent-native zoning data pipeline."""
    global _json_output
    _json_output = use_json
    ctx.ensure_object(dict)
    ctx.obj["json"] = use_json
    ctx.obj["persist"] = persist
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── County commands ───────────────────────────────────────────────────

@cli.group()
def county():
    """County-level operations: scrape, list, status."""
    pass


@county.command("list")
@click.option("--state", default="FL", help="State filter (default: FL)")
@handle_error
def county_list(state):
    """List available counties."""
    counties = scraper.get_county_list(state)
    if _json_output:
        click.echo(json.dumps({"state": state, "count": len(counties), "counties": counties}, indent=2))
    else:
        click.echo(f"Available counties ({state}): {len(counties)}")
        for c in counties:
            click.echo(f"  {c['county']}")


@county.command("scrape")
@click.option("--county", "county_name", required=True, help="County name")
@click.option("--tier", default=1, type=int, help="Scraping tier (1-4)")
@click.pass_context
@handle_error
def county_scrape(ctx, county_name, tier):
    """Scrape zoning data for a county."""
    session = get_session()
    result = scraper.scrape_county(county_name, tier=tier)
    session.current_county = county_name.lower()
    session.record(f"county scrape --county {county_name} --tier {tier}", result.get("status"))

    if ctx.obj.get("persist"):
        try:
            from cli_anything_shared.supabase import persist_result
            db_row = persist_result("county_scrapes", result, cli_name="zonewise")
            result["db_id"] = db_row.get("id")
        except Exception as e:
            result["persist_error"] = str(e)

    output(result, f"✓ Scrape {result.get('status', 'unknown')} for {county_name}")


@county.command("status")
@click.option("--county", "county_name", required=True, help="County name")
@handle_error
def county_status(county_name):
    """Check last scrape status for a county."""
    result = scraper.get_scrape_status(county_name)
    output(result, f"Status for {county_name}:")


# ── Parcel commands ───────────────────────────────────────────────────

@cli.group()
def parcel():
    """Parcel-level operations: lookup, batch, report."""
    pass


@parcel.command("lookup")
@click.option("--address", help="Street address")
@click.option("--parcel-id", help="Parcel ID")
@handle_error
def parcel_lookup(address, parcel_id):
    """Look up zoning for a single parcel."""
    if not address and not parcel_id:
        raise ValueError("Provide --address or --parcel-id")
    result = {
        "query": address or parcel_id,
        "query_type": "address" if address else "parcel_id",
        "status": "stub",
        "message": "Parcel lookup requires BCPAO + zoning database integration",
    }
    output(result)


@parcel.command("batch")
@click.option("--input", "input_file", required=True, type=click.Path(exists=True), help="CSV input file")
@handle_error
def parcel_batch(input_file):
    """Batch parcel lookup from CSV."""
    import csv
    with open(input_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    result = {
        "input_file": input_file,
        "parcels_count": len(rows),
        "status": "stub",
        "message": "Batch lookup requires integration — use single lookup for now",
    }
    output(result, f"Read {len(rows)} parcels from {input_file}")


# ── Export commands ───────────────────────────────────────────────────

@cli.group("export")
def export_group():
    """Export operations: supabase, csv, json."""
    pass


@export_group.command("json")
@click.option("--county", "county_name", required=True, help="County name")
@click.option("-o", "--output-path", required=True, help="Output file path")
@handle_error
def export_json(county_name, output_path):
    """Export county data to JSON file."""
    try:
        from cli_anything_shared.supabase import query_table
        data = query_table("zoning_records", {"county": county_name.lower()}, limit=10000, cli_name="zonewise")
    except Exception:
        data = []
    result = export_mod.to_json(data, output_path)
    output(result, f"✓ Exported {result['records']} records to {output_path}")


@export_group.command("csv")
@click.option("--county", "county_name", required=True, help="County name")
@click.option("-o", "--output-path", required=True, help="Output file path")
@handle_error
def export_csv(county_name, output_path):
    """Export county data to CSV file."""
    try:
        from cli_anything_shared.supabase import query_table
        data = query_table("zoning_records", {"county": county_name.lower()}, limit=10000, cli_name="zonewise")
    except Exception:
        data = []
    result = export_mod.to_csv(data, output_path)
    output(result, f"✓ Exported {result['records']} records to {output_path}")


@export_group.command("supabase")
@click.option("--county", "county_name", required=True, help="County name")
@click.option("--table", default="zoning_records", help="Target table")
@handle_error
def export_supabase(county_name, table):
    """Push county data to Supabase."""
    result = export_mod.to_supabase([], table=table, county=county_name)
    output(result, f"✓ Exported to {table}")


# ── Config commands ───────────────────────────────────────────────────

@cli.group()
def config():
    """Configuration management."""
    pass


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set a configuration value."""
    from cli_anything_shared.config import save_config
    save_config("zonewise", key, value)
    output({"key": key, "status": "saved"}, f"✓ Set {key}")


@config.command("get")
@click.argument("key", required=False)
def config_get(key):
    """Get configuration value(s)."""
    from cli_anything_shared.config import load_config, get_config
    if key:
        val = get_config("zonewise", key)
        output({"key": key, "value": val})
    else:
        output(load_config("zonewise"))


# ── Session commands ──────────────────────────────────────────────────

@cli.group()
def session():
    """Session management: status, history, undo."""
    pass


@session.command("status")
def session_status():
    """Show current session state."""
    output(get_session().status())


@session.command("history")
def session_history():
    """Show command history."""
    s = get_session()
    if _json_output:
        click.echo(json.dumps(s.history, indent=2, default=str))
    else:
        for entry in s.history[-20:]:
            click.echo(f"  [{entry.get('timestamp', '?')}] {entry.get('command', '?')}")


@session.command("undo")
def session_undo():
    """Undo last operation."""
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
        from cli_anything.zonewise.utils.repl_skin import ReplSkin
        skin = ReplSkin("zonewise", version="1.0.0")
    except ImportError:
        skin = None

    if skin:
        skin.print_banner()

    session = get_session()

    while True:
        try:
            county = session.current_county or "none"
            if skin:
                try:
                    pt_session = skin.create_prompt_session()
                    line = skin.get_input(pt_session, project_name=county)
                except Exception:
                    line = input(f"zonewise[{county}]> ")
            else:
                line = input(f"zonewise[{county}]> ")

            line = line.strip()
            if not line:
                continue
            if line in ("exit", "quit", "q"):
                if skin:
                    skin.print_goodbye()
                else:
                    click.echo("Goodbye! 👋")
                break

            # Parse and invoke Click command
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


# ── Entry point ───────────────────────────────────────────────────────

def main():
    cli()


if __name__ == "__main__":
    main()
