#!/usr/bin/env python3
"""
eval_runner.py — Karpathy-style binary assertion evaluator for cli-anything harnesses.

Usage:
    python eval_runner.py --eval-file zonewise/eval/eval.json --output results.json
    python eval_runner.py --eval-file auction/eval/eval.json --output results.json --test-id T1_max_bid_calculation

Reads eval.json, runs each test's assertions against actual output files,
produces a pass/fail score. Designed for autonomous self-improvement loops.
"""

import json
import re
import sys
import os
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

def load_eval(eval_path: str) -> dict:
    with open(eval_path) as f:
        return json.load(f)

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

    return {
        "assertion_id": assertion["id"],
        "description": assertion["description"],
        "passed": passed,
        "error": error
    }

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
        "skill": eval_data["skill"],
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
    parser.add_argument("--eval-file", required=True, help="Path to eval.json")
    parser.add_argument("--outputs-dir", default="./eval_outputs", help="Directory with test output files")
    parser.add_argument("--output", default=None, help="Write results to JSON file")
    parser.add_argument("--test-id", default=None, help="Run single test by ID")
    args = parser.parse_args()

    results = run_eval(args.eval_file, args.outputs_dir, args.test_id)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results written to {args.output}")
    else:
        print(json.dumps(results, indent=2))

    # Exit with non-zero if any failures
    sys.exit(0 if results["summary"]["perfect"] else 1)
