"""
cli_anything_modal_spatial.py
=============================
CLI-Anything Harness for Modal-powered parallel spatial zoning.

Follows HARNESS.md 7-phase pipeline:
  1. INIT     → Load config, validate secrets
  2. FETCH    → Pull parcels from Supabase
  3. PROCESS  → Fan out to Modal containers
  4. VALIDATE → Verify match rates, flag anomalies
  5. STORE    → Bulk upsert to Supabase
  6. REPORT   → Generate run summary
  7. CLEANUP  → Clear temp data, log metrics

Usage:
  python cli_anything_modal_spatial.py --county brevard
  python cli_anything_modal_spatial.py --county brevard --chunk-size 10000
  python cli_anything_modal_spatial.py --multi --counties brevard,orange,hillsborough
  python cli_anything_modal_spatial.py --status  # check active runs
  python cli_anything_modal_spatial.py --health  # weekly health check
"""

import argparse
import json
import os
import sys
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent
CONFIG_PATH = PROJECT_ROOT / "configs" / "modal_spatial.json"
STATE_PATH = PROJECT_ROOT / "state" / "last_run.json"

DEFAULT_CONFIG = {
    "chunk_size": 5000,
    "max_parallel_per_county": 20,
    "match_rate_threshold": 85.0,  # alert if below this
    "supabase_table": "parcel_zoning",
    "modal_app_name": "zonewise-spatial",
    "counties_registry": {
        "brevard": {
            "gis_endpoint": "https://gis.brevardfl.gov/gissrv/rest/services/PublicWorks/Zoning/MapServer/0/query",
            "expected_parcels": 78689,
            "polygon_count": 10000,
            "district_count": 56,
        }
    },
    "telegram_alerts": True,
    "cost_ceiling_per_run": 0.50,  # USD
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return DEFAULT_CONFIG


def save_state(state: dict):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, default=str)


def load_state() -> dict:
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------------------
# Phase 1: INIT
# ---------------------------------------------------------------------------
def phase_init(config: dict) -> bool:
    """Validate environment and secrets."""
    print("\n[1/7] INIT — Validating environment...")

    checks = {
        "modal_installed": False,
        "supabase_url": False,
        "supabase_key": False,
        "modal_token": False,
    }

    # Check Modal CLI
    try:
        result = subprocess.run(["modal", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            checks["modal_installed"] = True
            print(f"  ✓ Modal CLI: {result.stdout.strip()}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("  ✗ Modal CLI not found. Run: pip install modal && modal token new")

    # Check env vars
    for key, check_name in [
        ("SUPABASE_URL", "supabase_url"),
        ("SUPABASE_SERVICE_KEY", "supabase_key"),
    ]:
        val = os.environ.get(key, "")
        if val:
            checks[check_name] = True
            print(f"  ✓ {key}: ...{val[-8:]}")
        else:
            print(f"  ✗ {key}: not set")

    # Check Modal token (stored in ~/.modal)
    modal_config = Path.home() / ".modal" / "token"
    if modal_config.exists() or (Path.home() / ".modal.toml").exists():
        checks["modal_token"] = True
        print("  ✓ Modal token: configured")
    else:
        print("  ✗ Modal token: not found. Run: modal token new")

    all_ok = all(checks.values())
    if not all_ok:
        failed = [k for k, v in checks.items() if not v]
        print(f"\n  ⚠ Failed checks: {', '.join(failed)}")
    else:
        print("  ✓ All checks passed")

    return all_ok


# ---------------------------------------------------------------------------
# Phase 2-5: PROCESS (delegates to Modal)
# ---------------------------------------------------------------------------
def phase_process(county: str, config: dict, chunk_size: int) -> dict:
    """Launch Modal parallel processing."""
    print(f"\n[2-5/7] PROCESS — Launching Modal for {county}...")
    print(f"  Chunk size: {chunk_size}")
    print(f"  Max parallel: {config.get('max_parallel_per_county', 20)}")

    # Launch via Modal CLI
    cmd = [
        "modal", "run", str(PROJECT_ROOT / "modal_app.py"),
        "--county", county,
        "--chunk-size", str(chunk_size),
    ]

    print(f"  CMD: {' '.join(cmd)}")
    print(f"  {'='*50}")

    start = time.monotonic()

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=1800,  # 30 min max
        cwd=str(PROJECT_ROOT),
    )

    elapsed = time.monotonic() - start

    if result.returncode != 0:
        print(f"  ✗ Modal run failed (exit {result.returncode})")
        print(f"  stderr: {result.stderr[:500]}")
        return {"status": "FAILED", "error": result.stderr[:500], "elapsed": elapsed}

    # Parse JSON output from Modal
    stdout = result.stdout.strip()
    try:
        # Find the JSON object in output (Modal may print logs before it)
        json_start = stdout.rfind("{")
        if json_start >= 0:
            summary = json.loads(stdout[json_start:])
        else:
            summary = {"status": "UNKNOWN", "raw_output": stdout[-500:]}
    except json.JSONDecodeError:
        summary = {"status": "PARSE_ERROR", "raw_output": stdout[-500:]}

    summary["cli_elapsed_seconds"] = round(elapsed, 2)
    return summary


# ---------------------------------------------------------------------------
# Phase 6: REPORT
# ---------------------------------------------------------------------------
def phase_report(summary: dict, config: dict):
    """Generate and display run report."""
    print(f"\n[6/7] REPORT")
    print(f"  {'='*50}")

    status = summary.get("status", "UNKNOWN")
    county = summary.get("county", "?")
    total = summary.get("total_parcels", 0)
    matched = summary.get("total_matched", 0)
    rate = summary.get("match_rate_pct", 0)
    elapsed = summary.get("elapsed_seconds", summary.get("cli_elapsed_seconds", 0))

    print(f"  County:      {county}")
    print(f"  Status:      {status}")
    print(f"  Parcels:     {total:,}")
    print(f"  Matched:     {matched:,}")
    print(f"  Match Rate:  {rate}%")
    print(f"  Elapsed:     {elapsed:.1f}s")

    threshold = config.get("match_rate_threshold", 85.0)
    if rate < threshold and total > 0:
        print(f"  ⚠ ALERT: Match rate {rate}% below threshold {threshold}%")

    print(f"  {'='*50}")


# ---------------------------------------------------------------------------
# Phase 7: CLEANUP
# ---------------------------------------------------------------------------
def phase_cleanup(summary: dict):
    """Save state, log metrics."""
    print(f"\n[7/7] CLEANUP")
    save_state({
        "last_run": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
    })
    print("  ✓ State saved")


# ---------------------------------------------------------------------------
# Multi-county mode
# ---------------------------------------------------------------------------
def run_multi(counties: list[str], config: dict, chunk_size: int):
    """Run multiple counties via Modal multi_county_orchestrator."""
    print(f"\n[MULTI] Launching {len(counties)} counties in parallel...")

    cmd = [
        "modal", "run", str(PROJECT_ROOT / "modal_app.py"),
        "--multi",
        "--chunk-size", str(chunk_size),
    ]

    print(f"  CMD: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=3600,
        cwd=str(PROJECT_ROOT),
    )

    if result.returncode != 0:
        print(f"  ✗ Multi-county run failed")
        print(result.stderr[:500])
        return

    print(result.stdout[-2000:])


# ---------------------------------------------------------------------------
# Health check (for weekly Sunday 9AM cron)
# ---------------------------------------------------------------------------
def health_check(config: dict):
    """Weekly health check — outputs Telegram-ready status."""
    print("\n[HEALTH] ZoneWise Modal Spatial Agent")
    print(f"  Time: {datetime.now(timezone.utc).isoformat()}")

    state = load_state()
    last_run = state.get("last_run", "never")
    last_summary = state.get("summary", {})

    print(f"  Last run: {last_run}")
    print(f"  Last status: {last_summary.get('status', 'N/A')}")
    print(f"  Last match rate: {last_summary.get('match_rate_pct', 'N/A')}%")

    # Staleness check
    if last_run != "never":
        try:
            last_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - last_dt).days
            if age_days > 7:
                print(f"  ⚠ STALE: Last run {age_days} days ago")
            else:
                print(f"  ✓ Fresh: {age_days} days since last run")
        except Exception:
            print(f"  ⚠ Could not parse last run timestamp")

    # Modal CLI check
    try:
        result = subprocess.run(["modal", "--version"], capture_output=True, text=True, timeout=10)
        print(f"  ✓ Modal CLI: {result.stdout.strip()}")
    except Exception:
        print("  ✗ Modal CLI: not available")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="ZoneWise Modal Spatial Agent — CLI-Anything Harness"
    )
    parser.add_argument("--county", default="brevard", help="County to process")
    parser.add_argument("--chunk-size", type=int, default=5000, help="Parcels per Modal container")
    parser.add_argument("--multi", action="store_true", help="Run all configured counties")
    parser.add_argument("--counties", help="Comma-separated county list for --multi")
    parser.add_argument("--status", action="store_true", help="Show last run status")
    parser.add_argument("--health", action="store_true", help="Weekly health check")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, don't process")

    args = parser.parse_args()
    config = load_config()

    if args.health:
        health_check(config)
        return

    if args.status:
        state = load_state()
        print(json.dumps(state, indent=2, default=str))
        return

    # Phase 1: Init
    if not phase_init(config):
        if not args.dry_run:
            print("\n✗ Init failed. Fix issues above before running.")
            sys.exit(1)

    if args.dry_run:
        print("\n✓ Dry run complete. Environment validated.")
        return

    # Phase 2-5: Process
    if args.multi:
        counties = args.counties.split(",") if args.counties else list(config["counties_registry"].keys())
        run_multi(counties, config, args.chunk_size)
    else:
        summary = phase_process(args.county, config, args.chunk_size)

        # Phase 6: Report
        phase_report(summary, config)

        # Phase 7: Cleanup
        phase_cleanup(summary)


if __name__ == "__main__":
    main()
