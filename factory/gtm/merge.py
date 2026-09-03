#!/usr/bin/env python3
"""CMO FACTORY (issue #19777) -- merge decision.

Reads docs/gtm/verdicts/<issue>.json and merges the named PR ONLY when the
verdict file says verdict == "PASS" AND gates_green == true. This script
IS the merge decision -- there is no code path here that asks a model
whether to merge, and no code path that merges on partial evidence. If the
verdict file is missing, malformed, or incomplete, this refuses and exits
non-zero. Fails closed, same as .factory/gtm/STOP.md.

Verdict file shape (written by the validator role, never the builder):
{
  "issue": 19777,
  "pr": 12345,
  "verdict": "PASS" | "FAIL",
  "gates_green": true | false,
  "markers_observed": ["GTM_COMPLIANCE_PASSED", "GTM_PAGE_200", "GTM_RENDER_OK"],
  "validated_at": "2026-09-03T12:00:00Z",
  "validated_from": "main"
}

Usage:
    factory/gtm/merge.py --issue 19777 [--verdicts-dir docs/gtm/verdicts] [--dry-run]

Exit codes: 0 = merged (or would-merge in --dry-run), 1 = refused.
"""
import argparse
import json
import os
import subprocess
import sys

REQUIRED_KEYS = {"issue", "pr", "verdict", "gates_green", "markers_observed", "validated_at", "validated_from"}


def load_verdict(path):
    if not os.path.isfile(path):
        return None, f"no verdict file at {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return None, f"verdict file unreadable/invalid JSON: {e}"
    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        return None, f"verdict file missing required keys: {sorted(missing)}"
    return data, None


def decide(verdict_data):
    """Pure function: verdict dict -> (should_merge: bool, reason: str).

    This is the ONLY place the merge/no-merge decision is made. No LLM
    call, no heuristic, no partial-credit path.
    """
    if verdict_data["verdict"] != "PASS":
        return False, f"verdict={verdict_data['verdict']!r}, not PASS"
    if verdict_data["gates_green"] is not True:
        return False, f"gates_green={verdict_data['gates_green']!r}, not true"
    if verdict_data.get("validated_from") != "main":
        return False, f"validated_from={verdict_data.get('validated_from')!r} -- verdict must be produced from a checkout of main, not a PR branch"
    return True, "verdict==PASS and gates_green==true and validated_from==main"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--issue", required=True, type=int)
    ap.add_argument("--verdicts-dir", default="docs/gtm/verdicts")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "breverdbidder/cli-anything-biddeed"))
    ap.add_argument("--dry-run", action="store_true", help="print the decision but do not call gh pr merge")
    args = ap.parse_args()

    verdict_path = os.path.join(args.verdicts_dir, f"{args.issue}.json")
    verdict_data, err = load_verdict(verdict_path)
    if err:
        print(f"MERGE REFUSED: {err}", file=sys.stderr)
        sys.exit(1)

    should_merge, reason = decide(verdict_data)
    print(f"decision: {'MERGE' if should_merge else 'REFUSE'} -- {reason}")

    if not should_merge:
        sys.exit(1)

    pr = verdict_data["pr"]
    if args.dry_run:
        print(f"--dry-run: would run `gh pr merge {pr} --repo {args.repo} --squash`")
        sys.exit(0)

    result = subprocess.run(
        ["gh", "pr", "merge", str(pr), "--repo", args.repo, "--squash"],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    print(f"MERGED PR #{pr} for issue #{args.issue}")
    sys.exit(0)


if __name__ == "__main__":
    main()
