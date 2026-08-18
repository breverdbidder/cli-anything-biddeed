#!/usr/bin/env python3
"""Runs scripts/backfill_geom_fdor.py --county N sequentially for the given
list, smallest-missing-first, logging per-county before/after JSON to stdout.
Used for this session's continuation of the ZoneWise GIS mission only."""
import json, os, subprocess, sys, time

COUNTIES = [
    (76, "Walton"), (61, "Pasco"), (64, "Putnam"), (68, "Sarasota"),
    (45, "Lake"), (67, "Santa Rosa"), (47, "Leon"), (19, "Citrus"),
    (59, "Osceola"), (18, "Charlotte"), (58, "Orange"), (21, "Collier"),
    (60, "Palm Beach"), (16, "Broward"),
]

def main():
    results = []
    for co_no, name in COUNTIES:
        print(f"\n##### BEGIN {name} (co_no={co_no}) #####", flush=True)
        t0 = time.time()
        proc = subprocess.run(
            [sys.executable, "scripts/backfill_geom_fdor.py", "--county", str(co_no)],
            capture_output=True, text=True,
        )
        elapsed = time.time() - t0
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        print(f"##### END {name} (co_no={co_no}) elapsed={elapsed:.0f}s rc={proc.returncode} #####", flush=True)
        results.append({"county": name, "co_no": co_no, "elapsed_s": round(elapsed), "rc": proc.returncode})

    print("\n\n===== SWEEP SUMMARY =====")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
