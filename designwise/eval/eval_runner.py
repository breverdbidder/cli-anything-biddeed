#!/usr/bin/env python3
"""
DesignWise Eval Runner
Executes 25 binary assertions from eval.json.
Follows existing autoloop pattern from scripts/eval_runner.py.

Usage:
  python eval_runner.py                    # Run all 25 assertions
  python eval_runner.py --level L1         # Run only L1 assertions
  python eval_runner.py --agent commander  # Run specific agent assertions
  python eval_runner.py --json             # JSON output
  python eval_runner.py --fail-fast        # Stop on first failure
"""

import json
import os
import sys
import time
import subprocess
import argparse
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

EVAL_JSON_PATH = Path(__file__).parent / "eval.json"
RESULTS_DIR = Path(__file__).parent / "results"
HARNESS_DIR = Path(__file__).parent.parent / "agent-harness"


def load_assertions(
    level: Optional[str] = None,
    agent: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Load assertions from eval.json with optional filters."""
    with open(EVAL_JSON_PATH) as f:
        eval_data = json.load(f)

    assertions = eval_data["assertions"]

    if level:
        assertions = [a for a in assertions if a.get("level") == level]
    if agent:
        assertions = [a for a in assertions if a.get("agent") == agent]

    return assertions


def run_assertion(assertion: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    """
    Execute a single assertion command and check result.

    Returns:
        {id, passed, exit_code, output, error, duration_ms}
    """
    assertion_id = assertion["id"]
    command = assertion["command"]
    pass_condition = assertion["pass_condition"]

    start = time.time()
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(HARNESS_DIR),
            env={**os.environ, "PYTHONPATH": str(HARNESS_DIR)},
        )
        duration_ms = int((time.time() - start) * 1000)
        exit_code = result.returncode
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        passed = _evaluate_condition(pass_condition, exit_code, stdout, assertion)

        return {
            "id": assertion_id,
            "agent": assertion.get("agent"),
            "level": assertion.get("level"),
            "description": assertion.get("description"),
            "passed": passed,
            "exit_code": exit_code,
            "output": stdout[:500],
            "error": stderr[:300] if stderr else None,
            "duration_ms": duration_ms,
        }

    except subprocess.TimeoutExpired:
        return {
            "id": assertion_id,
            "agent": assertion.get("agent"),
            "level": assertion.get("level"),
            "description": assertion.get("description"),
            "passed": False,
            "exit_code": -1,
            "output": "",
            "error": f"Timed out after {timeout}s",
            "duration_ms": timeout * 1000,
        }
    except Exception as e:
        return {
            "id": assertion_id,
            "agent": assertion.get("agent"),
            "level": assertion.get("level"),
            "description": assertion.get("description"),
            "passed": False,
            "exit_code": -1,
            "output": "",
            "error": str(e),
            "duration_ms": int((time.time() - start) * 1000),
        }


def _evaluate_condition(
    condition: str,
    exit_code: int,
    output: str,
    assertion: Dict,
) -> bool:
    """Evaluate a pass condition against command output."""
    if condition == "exit_code_0":
        return exit_code == 0

    if condition == "exit_code_0_and_valid_json":
        if exit_code != 0:
            return False
        try:
            data = json.loads(output)
            key = assertion.get("key")
            if key:
                # Support nested key access with dot notation
                parts = key.split(".")
                val = data
                for part in parts:
                    if isinstance(val, dict):
                        val = val.get(part)
                    else:
                        val = None
                return val is not None
            return True
        except json.JSONDecodeError:
            return False

    if condition == "json_field_equals":
        if exit_code != 0:
            return False
        try:
            data = json.loads(output)
            key = assertion.get("key", "")
            expected = assertion.get("value")
            return _get_nested(data, key) == expected
        except (json.JSONDecodeError, KeyError):
            return False

    if condition == "json_field_in_list":
        if exit_code != 0:
            return False
        try:
            data = json.loads(output)
            key = assertion.get("key", "")
            values = assertion.get("values", [])
            return _get_nested(data, key) in values
        except (json.JSONDecodeError, KeyError):
            return False

    if condition == "json_field_is_bool":
        if exit_code != 0:
            return False
        try:
            data = json.loads(output)
            key = assertion.get("key", "")
            return isinstance(_get_nested(data, key), bool)
        except (json.JSONDecodeError, KeyError):
            return False

    if condition == "json_field_is_number":
        if exit_code != 0:
            return False
        try:
            data = json.loads(output)
            key = assertion.get("key", "")
            return isinstance(_get_nested(data, key), (int, float))
        except (json.JSONDecodeError, KeyError):
            return False

    if condition == "json_array_length_equals":
        if exit_code != 0:
            return False
        try:
            data = json.loads(output)
            key = assertion.get("key", "")
            expected_len = assertion.get("length", 0)
            val = _get_nested(data, key)
            return isinstance(val, list) and len(val) == expected_len
        except (json.JSONDecodeError, KeyError):
            return False

    if condition == "json_field_gte":
        if exit_code != 0:
            return False
        try:
            data = json.loads(output)
            key = assertion.get("key", "")
            threshold = assertion.get("value", 0)
            val = _get_nested(data, key)
            return isinstance(val, (int, float)) and val >= threshold
        except (json.JSONDecodeError, KeyError):
            return False

    if condition in ("violations_array_not_empty", "json_array_nonempty"):
        if exit_code != 0:
            return False
        try:
            data = json.loads(output)
            key = assertion.get("key", "")
            val = _get_nested(data, key)
            return isinstance(val, list) and len(val) > 0
        except (json.JSONDecodeError, KeyError):
            return False

    if condition in ("violations_array_empty", "json_array_empty"):
        if exit_code != 0:
            return False
        try:
            data = json.loads(output)
            key = assertion.get("key", "")
            val = _get_nested(data, key)
            return isinstance(val, list) and len(val) == 0
        except (json.JSONDecodeError, KeyError):
            return False

    if condition == "json_field_in_range":
        if exit_code != 0:
            return False
        try:
            data = json.loads(output)
            key = assertion.get("key", "")
            range_vals = assertion.get("range", [0, 1000])
            val = _get_nested(data, key)
            return isinstance(val, (int, float)) and range_vals[0] <= val <= range_vals[1]
        except (json.JSONDecodeError, KeyError):
            return False

    # Default: check exit code
    return exit_code == 0


def _get_nested(data: Dict, key: str) -> Any:
    """Get nested dict value using dot notation (e.g. 'remaining.pro')."""
    parts = key.split(".")
    val = data
    for part in parts:
        if isinstance(val, dict):
            val = val.get(part)
        else:
            return None
    return val


def run_all(
    assertions: List[Dict],
    fail_fast: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Run all assertions and collect results.

    Returns:
        {passed, failed, total, score, results, duration_ms}
    """
    results = []
    start = time.time()

    for i, assertion in enumerate(assertions):
        print(f"[{i+1}/{len(assertions)}] {assertion['id']} — {assertion['description'][:60]}...", end=" ", flush=True)
        result = run_assertion(assertion)
        results.append(result)
        status = "✓" if result["passed"] else "✗"
        print(f"{status} ({result['duration_ms']}ms)")

        if verbose and not result["passed"]:
            if result.get("error"):
                print(f"    Error: {result['error']}")
            if result.get("output"):
                print(f"    Output: {result['output'][:200]}")

        if fail_fast and not result["passed"]:
            print(f"\nFail-fast: stopping at {assertion['id']}")
            break

    total_duration_ms = int((time.time() - start) * 1000)
    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed
    score = f"{passed}/{len(assertions)}"

    return {
        "passed": passed,
        "failed": failed,
        "total": len(assertions),
        "score": score,
        "pass_rate": round(passed / len(assertions), 3) if assertions else 0,
        "results": results,
        "duration_ms": total_duration_ms,
        "run_at": datetime.utcnow().isoformat(),
    }


def save_results(run_result: Dict[str, Any]) -> str:
    """Save eval results to results/ directory."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filepath = RESULTS_DIR / f"eval_{timestamp}.json"
    with open(filepath, "w") as f:
        json.dump(run_result, f, indent=2)
    return str(filepath)


def print_summary(run_result: Dict[str, Any]) -> None:
    """Print human-readable summary."""
    print("\n" + "="*60)
    print(f"DesignWise Eval — {run_result['score']} passed")
    print(f"Pass rate: {run_result['pass_rate']:.1%}")
    print(f"Duration: {run_result['duration_ms']}ms")

    if run_result["failed"] > 0:
        print("\nFailed assertions:")
        for r in run_result["results"]:
            if not r["passed"]:
                print(f"  ✗ {r['id']} — {r['description']}")
                if r.get("error"):
                    print(f"    {r['error'][:100]}")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(description="DesignWise Eval Runner — 25 binary assertions")
    parser.add_argument("--level", choices=["L1", "L2"], help="Filter by assertion level")
    parser.add_argument("--agent", help="Filter by agent name")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show failure details")
    parser.add_argument("--save", action="store_true", help="Save results to results/ dir")
    args = parser.parse_args()

    assertions = load_assertions(level=args.level, agent=args.agent)
    if not assertions:
        print("No assertions match filters")
        sys.exit(1)

    print(f"Running {len(assertions)} assertions...")
    run_result = run_all(assertions, fail_fast=args.fail_fast, verbose=args.verbose)

    if args.save or True:  # Always save
        filepath = save_results(run_result)
        run_result["saved_to"] = filepath

    if args.json:
        print(json.dumps(run_result, indent=2))
    else:
        print_summary(run_result)

    # Exit 1 if any assertions failed
    sys.exit(0 if run_result["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
