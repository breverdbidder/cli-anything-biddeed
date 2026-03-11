#!/usr/bin/env python3
"""Spatial Conquest CLI — Shapely-powered county zoning assignment.

Usage:
    cli-anything-spatial conquer --county brevard
    cli-anything-spatial discover --county brevard
    cli-anything-spatial validate --county brevard --safeguard 85
    cli-anything-spatial --json status
    cli-anything-spatial   # Enter REPL
"""

import json
import sys
import os
import click
from typing import Optional

from cli_anything.spatial.core.session import Session
from cli_anything.spatial.core import discovery
from cli_anything.spatial.core import conquest
from cli_anything.spatial.core import export as export_mod

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


# ── Main CLI Group ────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, help="Output in JSON format")
@click.pass_context
def cli(ctx, use_json):
    """Spatial Conquest CLI — Shapely-powered county zoning assignment."""
    global _json_output
    _json_output = use_json
    ctx.ensure_object(dict)
    ctx.obj["json"] = use_json
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ── Conquer command ───────────────────────────────────────────

@cli.command()
@click.option("--county", required=True, help="County name (e.g. brevard)")
@click.option("--safeguard", type=float, default=85.0, help="Minimum coverage % (default 85)")
@click.option("--persist", is_flag=True, help="Upsert results to Supabase")
@handle_error
def conquer(county, safeguard, persist):
    """Conquer a county — full spatial join pipeline."""
    endpoint = discovery.get_endpoint(county)
    if not endpoint:
        raise ValueError(f"No GIS endpoint known for '{county}'. Use 'discover' to add one.")

    def progress(n):
        click.echo(f"  ... {n:,} parcels downloaded")

    result, matched = conquest.conquer_county(
        county=county,
        zoning_endpoint=endpoint["zoning"],
        parcel_endpoint=endpoint["parcels"],
        zone_field=endpoint.get("zone_field", "ZONING"),
        parcel_field=endpoint.get("parcel_field", "PARCELID"),
        progress_callback=progress,
    )

    session = get_session()
    session.current_county = county
    session.record(f"conquer --county {county}", f"{result.coverage_pct:.1f}%")

    if persist and matched:
        try:
            from cli_anything_shared.supabase import upsert_rows
            for row in matched:
                row["county"] = county
            count = upsert_rows("zoning_assignments", matched, cli_name="spatial")
            result_dict = result.to_dict()
            result_dict["db_upserted"] = count
            output(result_dict, f"✓ {county}: {result.parcels_matched:,} zoned, {count:,} persisted")
            return
        except Exception as e:
            click.echo(f"  Persist error: {e}", err=True)

    output(result.to_dict(), f"✓ {county}: {result.parcels_matched:,}/{result.parcels_downloaded:,} ({result.coverage_pct:.1f}%)")


# ── Discover command ──────────────────────────────────────────

@cli.command()
@click.option("--county", required=True, help="County to probe")
@click.option("--url", help="GIS MapServer URL to probe")
@handle_error
def discover(county, url):
    """Discover and probe GIS endpoints for a county."""
    endpoint = discovery.get_endpoint(county)

    if endpoint:
        info = {"county": county, "status": "known", **endpoint}
        zones = discovery.discover_zones(endpoint["zoning"], endpoint.get("zone_field", "ZONING"))
        info["districts_found"] = len(zones)
        info["total_polygons"] = sum(zones.values())
        info["zones"] = dict(sorted(zones.items(), key=lambda x: -x[1])[:20])
        output(info, f"✓ {county}: {len(zones)} districts, {sum(zones.values()):,} polygons")
    elif url:
        fields = discovery.probe_fields(url)
        count = discovery.probe_count(url)
        sample = discovery.probe_sample(url, n=3)
        output({"county": county, "url": url, "fields": fields, "count": count, "sample": sample})
    else:
        output({"county": county, "status": "unknown",
                "message": "No endpoint known. Provide --url to probe a GIS MapServer."})


# ── Validate command ──────────────────────────────────────────

@cli.command()
@click.option("--county", required=True, help="County to validate")
@click.option("--safeguard", type=float, default=85.0, help="Minimum coverage %")
@handle_error
def validate(county, safeguard):
    """Validate zoning coverage for a county against safeguard threshold."""
    try:
        from cli_anything_shared.supabase import query_table
        total = len(query_table("zoning_assignments", {"county": county.lower()}, limit=1, cli_name="spatial"))
        zoned = len(query_table("zoning_assignments", {"county": county.lower()}, limit=1, cli_name="spatial"))
        # This is a simplified check — real validation counts from DB
        output({"county": county, "safeguard": safeguard, "status": "requires_db_query"})
    except Exception:
        output({"county": county, "safeguard": safeguard, "status": "no_supabase_connection",
                "message": "Run 'conquer --persist' first to populate data."})


# ── List command ──────────────────────────────────────────────

@cli.command("list")
@handle_error
def list_counties():
    """List counties with known GIS endpoints."""
    counties = discovery.list_known_counties()
    if _json_output:
        click.echo(json.dumps({"counties": counties, "count": len(counties)}, indent=2))
    else:
        click.echo(f"Known counties: {len(counties)}")
        for c in counties:
            click.echo(f"  {c['county']: <15} zoning={'✓' if c['has_zoning'] else '✗'}  parcels={'✓' if c['has_parcels'] else '✗'}")


# ── Status command ────────────────────────────────────────────

@cli.command()
@handle_error
def status():
    """Show session status."""
    output(get_session().status())


# ── Config commands ───────────────────────────────────────────

@cli.group()
def config():
    """Configuration management."""
    pass


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    from cli_anything_shared.config import save_config
    save_config("spatial", key, value)
    output({"key": key, "status": "saved"}, f"✓ Set {key}")


@config.command("get")
@click.argument("key", required=False)
def config_get(key):
    from cli_anything_shared.config import load_config, get_config
    if key:
        output({"key": key, "value": get_config("spatial", key)})
    else:
        output(load_config("spatial"))


# ── Session commands ──────────────────────────────────────────

@cli.group()
def session():
    """Session management."""
    pass


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


# ── REPL ──────────────────────────────────────────────────────

@cli.command(hidden=True)
def repl():
    """Interactive REPL mode."""
    try:
        from cli_anything.spatial.utils.repl_skin import ReplSkin
        skin = ReplSkin("spatial", version="1.0.0")
        skin.print_banner()
    except ImportError:
        skin = None
        click.echo("Spatial Conquest CLI v1.0.0")

    s = get_session()
    while True:
        try:
            label = s.current_county or "ready"
            line = input(f"spatial[{label}]> ").strip()
            if not line:
                continue
            if line in ("exit", "quit", "q"):
                click.echo("Goodbye! 👋")
                break
            try:
                cli.main(line.split(), standalone_mode=False)
            except SystemExit:
                pass
            except Exception as e:
                click.echo(f"Error: {e}", err=True)
        except (EOFError, KeyboardInterrupt):
            click.echo("\nGoodbye! 👋")
            break


def main():
    cli()

if __name__ == "__main__":
    main()
