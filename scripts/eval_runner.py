#!/usr/bin/env python3
"""
eval_runner.py — Karpathy-style binary assertion evaluator for cli-anything harnesses.

Usage:
    python eval_runner.py --eval-file zonewise/eval/eval.json --output results.json
    python eval_runner.py --eval-file auction/eval/eval.json --output results.json --test-id T1_max_bid_calculation
    python eval_runner.py --eval-file .claude/skills/zonewise-scraper/eval.json --output results.json --l3

Reads eval.json, runs each test's assertions against actual output files,
produces a pass/fail score. Designed for autonomous self-improvement loops.

--l3 flag: after scoring, call scripts/l3_analyze.py for post-execution LLM analysis.
           Also annotates each failed assertion with Levenshtein similarity score.
"""

import json
import re
import sys
import os
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime


# ── L3: Levenshtein fuzzy similarity ──────────────────────────────────────

def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        return _levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for ca in a:
        curr = [prev[0] + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if ca == cb else 1)))
        prev = curr
    return prev[-1]


def levenshtein_similarity(a: str, b: str) -> float:
    """Normalized Levenshtein similarity in [0, 1]."""
    a, b = str(a), str(b)
    if not a and not b:
        return 1.0
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 1.0
    return 1.0 - (_levenshtein(a, b) / max_len)


def classify_failure(expected: str, actual: str) -> tuple:
    """Classify failed assertion: returns (evolution_type, similarity_score)."""
    sim = levenshtein_similarity(str(expected), str(actual))
    if sim > 0.7:
        return "fix", sim
    elif sim > 0.3:
        return "derived", sim
    else:
        return "captured", sim

def load_eval(eval_path: str) -> dict:
    with open(eval_path) as f:
        data = json.load(f)
    # Normalize flat "assertions" format (no "tests" wrapper) → wrap into single test
    if "assertions" in data and "tests" not in data:
        normalized = []
        for a in data["assertions"]:
            normalized.append({
                "id": a.get("id", ""),
                "description": a.get("description") or a.get("desc", ""),
                "check": a.get("check", ""),
                **{k: v for k, v in a.items() if k not in ("id", "description", "desc", "check")}
            })
        data["tests"] = [{
            "id": data.get("name", "eval"),
            "prompt": data.get("description", ""),
            "assertions": normalized
        }]
    return data

def check_json_parseable(output: str) -> bool:
    try:
        json.loads(output)
        return True
    except (json.JSONDecodeError, TypeError):
        return False

def check_regex_match(data: dict, field: str, pattern: str) -> bool:
    if isinstance(data, list):
        return all(re.match(pattern, str(item.get(field, ""))) for item in data)
    return bool(re.match(pattern, str(data.get(field, ""))))

def check_field_not_null(data, field: str) -> bool:
    if isinstance(data, list):
        return all(item.get(field) is not None and item.get(field) != "" for item in data)
    return data.get(field) is not None and data.get(field) != ""

def check_field_exists(data: dict, field: str) -> bool:
    return field in data and data[field] is not None

def check_field_equals(data: dict, field: str, value) -> bool:
    return data.get(field) == value

def check_field_is_number(data: dict, field: str) -> bool:
    val = data.get(field)
    return isinstance(val, (int, float)) and not isinstance(val, bool)

def check_field_positive_number(data: dict, field: str) -> bool:
    val = data.get(field)
    return isinstance(val, (int, float)) and not isinstance(val, bool) and val > 0

def check_field_in_set(data: dict, field: str, values: list) -> bool:
    return data.get(field) in values

def check_array_length(data: dict, field: str, expected: int) -> bool:
    arr = data.get(field, [])
    return isinstance(arr, list) and len(arr) == expected

def check_field_contains(data: dict, field: str, substring: str) -> bool:
    return substring in str(data.get(field, ""))

def check_field_not_contains(data: dict, field: str, forbidden: str) -> bool:
    return forbidden not in str(data.get(field, ""))

def check_field_starts_with(data: dict, field: str, prefix: str) -> bool:
    return str(data.get(field, "")).startswith(prefix)

def check_ratio_gte(data: dict, numerator: str, denominator: str, threshold: float) -> bool:
    num = data.get(numerator, 0)
    den = data.get(denominator, 1)
    if not isinstance(num, (int, float)) or not isinstance(den, (int, float)) or den == 0:
        return False
    return (num / den) >= threshold

def check_docx_valid(filepath: str) -> bool:
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            names = z.namelist()
            return "word/document.xml" in names and "[Content_Types].xml" in names
    except (zipfile.BadZipFile, FileNotFoundError):
        return False

def check_docx_contains_text(filepath: str, text: str) -> bool:
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            with z.open("word/document.xml") as f:
                content = f.read().decode("utf-8")
                return text in content
    except Exception:
        return False

def check_docx_not_contains_text(filepath: str, forbidden: list) -> bool:
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            with z.open("word/document.xml") as f:
                content = f.read().decode("utf-8")
                return not any(f in content for f in forbidden)
    except Exception:
        return False

def check_docx_xml_contains(filepath: str, pattern: str) -> bool:
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            for name in z.namelist():
                if name.startswith("word/") and name.endswith(".xml"):
                    with z.open(name) as f:
                        if pattern in f.read().decode("utf-8"):
                            return True
        return False
    except Exception:
        return False

def check_docx_landscape(filepath: str) -> bool:
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            with z.open("word/document.xml") as f:
                content = f.read().decode("utf-8")
                return 'orient="landscape"' in content.lower() or "landscape" in content.lower()
    except Exception:
        return False

def run_assertion(assertion: dict, output_data, output_file: str = None) -> dict:
    """Run a single assertion and return result."""
    check = assertion.get("check", "")
    passed = False
    error = None

    try:
        if check == "json_parseable":
            passed = check_json_parseable(json.dumps(output_data) if isinstance(output_data, (dict, list)) else str(output_data))
        elif check == "regex_match":
            passed = check_regex_match(output_data, assertion["field"], assertion["pattern"])
        elif check == "field_not_null":
            passed = check_field_not_null(output_data, assertion["field"])
        elif check == "fields_not_null":
            passed = all(check_field_not_null(output_data, f) for f in assertion["fields"])
        elif check == "field_exists":
            passed = check_field_exists(output_data, assertion["field"])
        elif check == "field_exists_any":
            passed = any(check_field_exists(output_data, f) for f in assertion["fields"])
        elif check == "field_equals":
            passed = check_field_equals(output_data, assertion["field"], assertion["value"])
        elif check == "field_is_number":
            passed = check_field_is_number(output_data, assertion["field"])
        elif check == "field_positive_number" or check == "field_positive_integer":
            passed = check_field_positive_number(output_data, assertion["field"])
        elif check == "field_in_set":
            passed = check_field_in_set(output_data, assertion["field"], assertion["values"])
        elif check == "field_contains":
            passed = check_field_contains(output_data, assertion["field"], assertion["substring"])
        elif check == "field_not_contains":
            passed = check_field_not_contains(output_data, assertion["field"], assertion["forbidden"])
        elif check == "field_starts_with":
            passed = check_field_starts_with(output_data, assertion["field"], assertion["prefix"])
        elif check == "field_lowercase":
            val = output_data.get(assertion["field"], "")
            passed = isinstance(val, str) and val == val.lower() and len(val) > 0
        elif check == "field_is_array":
            passed = isinstance(output_data.get(assertion["field"]), list)
        elif check == "field_gte":
            val = output_data.get(assertion["field"], 0)
            passed = isinstance(val, (int, float)) and val >= assertion["threshold"]
        elif check == "ratio_gte":
            passed = check_ratio_gte(output_data, assertion["numerator"], assertion["denominator"], assertion["threshold"])
        elif check == "ratio_calculated":
            passed = check_field_is_number(output_data, assertion["field"])
        elif check == "array_length":
            passed = check_array_length(output_data, assertion["field"], assertion["expected"])
        elif check == "array_unique":
            arr = output_data.get(assertion["field"], [])
            passed = isinstance(arr, list) and len(arr) == len(set(str(x) for x in arr))
        elif check == "array_field_not_empty":
            arr = output_data.get(assertion["array"], [])
            passed = isinstance(arr, list) and all(item.get(assertion["field"]) for item in arr)
        elif check == "array_field_in_set":
            arr = output_data.get(assertion["array"], [])
            vals = assertion["values"]
            passed = isinstance(arr, list) and all(item.get(assertion["field"]) in vals for item in arr)
        elif check == "sum_equals":
            total = sum(
                output_data.get(f.split(".")[-1], 0) if "." in f else output_data.get(f, 0)
                for f in assertion["fields"]
            )
            passed = total == assertion["expected_sum"]
        elif check == "field_iso_datetime":
            val = output_data.get(assertion["field"], "")
            try:
                datetime.fromisoformat(str(val).replace("Z", "+00:00"))
                passed = True
            except ValueError:
                passed = False
        elif check == "value_in_set":
            prefix_set = assertion.get("prefix_set", [])
            if isinstance(output_data, list):
                passed = all(
                    any(str(item.get(assertion["field"], "")).startswith(p) for p in prefix_set)
                    for item in output_data
                )
            else:
                val = str(output_data.get(assertion["field"], ""))
                passed = any(val.startswith(p) for p in prefix_set)
        elif check == "no_null_top_level":
            passed = isinstance(output_data, dict) and all(v is not None for v in output_data.values())
        elif check == "exit_code_nonzero":
            passed = output_data.get("exit_code", 0) != 0
        elif check == "status_code_in":
            passed = output_data.get("status_code") in assertion["values"]
        # DOCX-specific checks
        elif check == "docx_valid" and output_file:
            passed = check_docx_valid(output_file)
        elif check == "docx_contains_text" and output_file:
            passed = check_docx_contains_text(output_file, assertion["text"])
        elif check == "docx_not_contains_text" and output_file:
            passed = check_docx_not_contains_text(output_file, assertion["forbidden"])
        elif check == "docx_xml_contains" and output_file:
            passed = check_docx_xml_contains(output_file, assertion["pattern"])
        elif check == "docx_xml_not_contains" and output_file:
            passed = not check_docx_xml_contains(output_file, assertion.get("forbidden_pattern", ""))
        elif check == "docx_landscape" and output_file:
            passed = check_docx_landscape(output_file)
        elif check == "docx_has_table" and output_file:
            passed = check_docx_xml_contains(output_file, "<w:tbl")
        elif check == "file_size_gte" and output_file:
            passed = os.path.getsize(output_file) >= assertion.get("threshold_bytes", 0)
        elif check.startswith("docx_contains_any") and output_file:
            patterns = assertion.get("patterns", [])
            passed = any(check_docx_contains_text(output_file, p) for p in patterns)
        elif check == "docx_contains_number" and output_file:
            passed = check_docx_contains_text(output_file, str(assertion.get("expected", "")))
        elif check == "docx_contains_pattern" and output_file:
            try:
                with zipfile.ZipFile(output_file, 'r') as z:
                    with z.open("word/document.xml") as f:
                        content = f.read().decode("utf-8")
                        passed = bool(re.search(assertion["pattern"], content))
            except Exception:
                passed = False
        elif check == "docx_table_has_margins" and output_file:
            passed = check_docx_xml_contains(output_file, "w:tblCellMar") or check_docx_xml_contains(output_file, "tcMar")
        elif check == "docx_min_pages" and output_file:
            passed = check_docx_valid(output_file)  # Simplified: valid = at least 1 page
        else:
            # Custom/complex checks — log as skipped, require human or LLM judge
            passed = None
            error = f"Unknown check type: {check}"
    except Exception as e:
        passed = False
        error = str(e)

    result = {
        "assertion_id": assertion["id"],
        "description": assertion["description"],
        "passed": passed,
        "error": error
    }

    # L3: annotate failures with Levenshtein similarity for evolution classification
    if passed is False and error:
        evo_type, sim = classify_failure(
            assertion.get("description", ""),
            error
        )
        result["l3_similarity"] = round(sim, 3)
        result["l3_evolution_hint"] = evo_type

    return result

def run_test(test: dict, output_data, output_file: str = None) -> dict:
    """Run all assertions for a test."""
    results = []
    for assertion in test["assertions"]:
        result = run_assertion(assertion, output_data, output_file)
        results.append(result)

    passed_count = sum(1 for r in results if r["passed"] is True)
    failed_count = sum(1 for r in results if r["passed"] is False)
    skipped_count = sum(1 for r in results if r["passed"] is None)
    total = len(results)

    return {
        "test_id": test["id"],
        "prompt": test["prompt"],
        "passed": passed_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "total": total,
        "score": passed_count / max(total - skipped_count, 1),
        "assertions": results
    }

def run_eval(eval_path: str, outputs_dir: str, test_id: str = None) -> dict:
    """Run full eval suite or single test."""
    eval_data = load_eval(eval_path)
    tests = eval_data["tests"]

    if test_id:
        tests = [t for t in tests if t["id"] == test_id]

    all_results = []
    for test in tests:
        # Look for output file: {outputs_dir}/{test_id}.json or {test_id}.docx
        json_output = os.path.join(outputs_dir, f"{test['id']}.json")
        docx_output = os.path.join(outputs_dir, f"{test['id']}.docx")

        output_data = {}
        output_file = None

        if os.path.exists(json_output):
            with open(json_output) as f:
                output_data = json.load(f)
        if os.path.exists(docx_output):
            output_file = docx_output

        result = run_test(test, output_data, output_file)
        all_results.append(result)

    total_passed = sum(r["passed"] for r in all_results)
    total_failed = sum(r["failed"] for r in all_results)
    total_skipped = sum(r["skipped"] for r in all_results)
    total_assertions = sum(r["total"] for r in all_results)
    scoreable = total_assertions - total_skipped

    return {
        "skill": eval_data.get("skill") or eval_data.get("name", "unknown"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "total_assertions": total_assertions,
            "passed": total_passed,
            "failed": total_failed,
            "skipped": total_skipped,
            "score": total_passed / max(scoreable, 1),
            "score_pct": f"{(total_passed / max(scoreable, 1)) * 100:.1f}%",
            "perfect": total_failed == 0
        },
        "tests": all_results
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run binary assertion evals on harness output")
    parser.add_argument("eval_file_pos", nargs="?", default=None, help="Path to eval.json (positional)")
    parser.add_argument("--eval-file", default=None, help="Path to eval.json")
    parser.add_argument("--outputs-dir", default="./eval_outputs", help="Directory with test output files")
    parser.add_argument("--output", default=None, help="Write results to JSON file")
    parser.add_argument("--test-id", default=None, help="Run single test by ID")
    # L3 flags
    parser.add_argument("--l3", action="store_true",
                        help="Run L3 post-execution analyzer after eval (requires GEMINI_API_KEY or DEEPSEEK_API_KEY)")
    parser.add_argument("--skill-md", default=None,
                        help="Path to SKILL.md (required with --l3)")
    parser.add_argument("--run-id", default=None,
                        help="Run ID for L3 tracing (defaults to timestamp)")
    # Evolution V2 flags
    parser.add_argument("--evolve", action="store_true",
                        help="Run AUTOLOOP V2 evolution on score drop instead of blind revert")
    parser.add_argument("--score-before", type=float, default=None,
                        help="Baseline score (0.0-1.0) to compare against for regression detection")
    parser.add_argument("--session-log", default=None,
                        help="Path to session log file for additional signal detection")
    args = parser.parse_args()

    eval_file = args.eval_file or args.eval_file_pos
    if not eval_file:
        parser.error("eval file path required (positional or --eval-file)")

    results = run_eval(eval_file, args.outputs_dir, args.test_id)

    output_path = args.output
    if output_path:
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results written to {output_path}")
    else:
        print(json.dumps(results, indent=2))

    # ── L3: Post-Execution Analyzer ────────────────────────────────────────
    if args.l3:
        skill_name = results.get("skill", "unknown")
        run_id = args.run_id or f"autoloop_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # Resolve skill-md path: explicit arg or auto-discover from .claude/skills/
        skill_md = args.skill_md
        if not skill_md:
            candidate = Path(f".claude/skills/{skill_name}/SKILL.md")
            if candidate.exists():
                skill_md = str(candidate)

        # Write results to temp file if no --output was given
        if not output_path:
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
            json.dump(results, tmp)
            tmp.close()
            output_path = tmp.name

        if skill_md and Path(skill_md).exists():
            l3_output = output_path.replace(".json", "_l3.json") if output_path else f"{skill_name}_l3.json"
            l3_cmd = [
                sys.executable, str(Path(__file__).parent / "l3_analyze.py"),
                "--skill", skill_name,
                "--skill-md", skill_md,
                "--eval-results", output_path,
                "--run-id", run_id,
                "--output", l3_output
            ]
            print(f"\n[eval_runner] Running L3 analyzer: {' '.join(l3_cmd)}", file=sys.stderr)
            l3_exit = subprocess.call(l3_cmd)
            if l3_exit == 2:
                print(f"[eval_runner] L3: evolution suggestion generated → {l3_output}", file=sys.stderr)
            elif l3_exit != 0:
                print(f"[eval_runner] L3: analyzer exited {l3_exit}", file=sys.stderr)
        else:
            print(f"[eval_runner] L3: SKILL.md not found at {skill_md or 'auto-discover failed'} — skipping", file=sys.stderr)

    # ── Evolution V2: on score drop, generate patches instead of blind revert ──
    if args.evolve:
        current_score = results["summary"]["score"]
        score_before = args.score_before
        skill_name = results.get("skill", "unknown")
        evolved = False

        if score_before is not None and current_score < score_before:
            print(f"\n[eval_runner] ⚠️  Score dropped: {score_before:.1%} → {current_score:.1%} — triggering evolution", file=sys.stderr)
            try:
                # Add evolution/ parent dir to path if needed
                evolution_dir = Path(__file__).parent.parent / "evolution"
                if evolution_dir.exists():
                    sys.path.insert(0, str(Path(__file__).parent.parent))
                from evolution.service import EvolutionService

                # Read session log if provided
                session_log_text = None
                if args.session_log and Path(args.session_log).exists():
                    session_log_text = Path(args.session_log).read_text()

                svc = EvolutionService(skill_name=skill_name)
                evo_result = svc.on_eval_score_drop(
                    score_before=score_before,
                    score_after=current_score,
                    session_log=session_log_text,
                )
                print(
                    f"[eval_runner] Evolution: signals={evo_result.get('signals', 0)} "
                    f"entries={evo_result.get('entries', 0)} "
                    f"applied={evo_result.get('applied', 0)}",
                    file=sys.stderr,
                )
                evolved = evo_result.get("applied", 0) > 0
            except ImportError:
                print("[eval_runner] evolution/ module not found — skipping V2 evolution", file=sys.stderr)
            except Exception as e:
                print(f"[eval_runner] Evolution error: {e}", file=sys.stderr)
        elif score_before is not None:
            print(f"[eval_runner] Score: {score_before:.1%} → {current_score:.1%} (no regression)", file=sys.stderr)

    # Exit with non-zero if any failures
    sys.exit(0 if results["summary"]["perfect"] else 1)
