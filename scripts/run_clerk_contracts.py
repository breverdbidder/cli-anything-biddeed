#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = ROOT / "config" / "county_source_overrides.json"
ADAPTER = ROOT / "scripts" / "clerk_public_sales_adapter.py"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--days-ahead", type=int, default=14)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    registry = json.loads(OVERRIDES.read_text()).get("counties", {})
    report = {"start_date": args.start_date, "days_ahead": args.days_ahead, "apply": args.apply, "results": [], "errors": []}
    for county, config in sorted(registry.items()):
        for source in config.get("sources", []):
            if source.get("adapter") != "clerk_html_discovery" or not source.get("url"):
                continue
            sale_types = ["foreclosure", "tax_deed"] if source.get("sale_type") == "both" else [source.get("sale_type")]
            for sale_type in sale_types:
                cmd = [sys.executable, str(ADAPTER), "--county", county, "--sale-type", sale_type, "--url", source["url"], "--start-date", args.start_date, "--days-ahead", str(args.days_ahead)]
                if args.apply:
                    cmd.append("--apply")
                proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=90)
                if proc.returncode != 0:
                    report["errors"].append({"county": county, "sale_type": sale_type, "url": source["url"], "stderr": proc.stderr[-1000:]})
                    continue
                try:
                    report["results"].append(json.loads(proc.stdout.strip().splitlines()[-1]))
                except json.JSONDecodeError:
                    report["errors"].append({"county": county, "sale_type": sale_type, "url": source["url"], "stderr": "adapter returned non-JSON output"})
    report["parsed"] = sum(x.get("parsed", 0) for x in report["results"])
    report["inserted"] = sum(x.get("inserted", 0) for x in report["results"])
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
