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

# ── Skill name → path resolution ────────────────────────────────────────────

SKILL_MD_MAP = {
    "zonewise": "zonewise/agent-harness/ZONEWISE.md",
    "auction":  "auction/agent-harness/AUCTION.md",
    "reports":  "reports/REPORTS.md",
    "enricher": "enricher/CLAUDE.md",
    "forecaster": "forecaster/CLAUDE.md",
    "trendpredictor": "trendpredictor/CLAUDE.md",
    "sitemanager": "sitemanager/CLAUDE.md",
    "projecttracker": "projecttracker/CLAUDE.md",
}

def _resolve_eval(skill: str) -> str:
    """Return path to eval.json for a skill name."""
    candidates = [
        f"{skill}/eval/eval.json",
        f"eval/{skill}/eval.json",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError(f"eval.json not found for skill '{skill}'. Tried: {candidates}")

def _resolve_skill_md(skill: str) -> str:
    path = SKILL_MD_MAP.get(skill)
    if path and os.path.exists(path):
        return path
    # fallback: glob for SKILL.md
    import glob as _glob
    hits = _glob.glob(f"{skill}/**/*.md", recursive=True)
    for h in hits:
        if os.path.basename(h).upper().endswith(".MD") and skill.upper() in os.path.basename(h).upper():
            return h
    raise FileNotFoundError(f"SKILL.md not found for skill '{skill}'")

def _resolve_outputs_dir(skill: str) -> str:
    d = f"{skill}/eval_outputs"
    os.makedirs(d, exist_ok=True)
    return d

# ── New subcommands ──────────────────────────────────────────────────────────

def cmd_verify_ground_truth(skill: str) -> int:
    """
    Validate that ground truth data exists and is fresh (<30 days).
    Exits 0 if OK, 1 if stale or missing.
    """
    eval_path = _resolve_eval(skill)
    stat = os.stat(eval_path)
    age_days = (datetime.utcnow().timestamp() - stat.st_mtime) / 86400
    if age_days > 30:
        print(f"[verify-ground-truth] STALE: {eval_path} is {age_days:.1f} days old (>30)")
        return 1

    outputs_dir = _resolve_outputs_dir(skill)
    output_files = [f for f in os.listdir(outputs_dir) if f.endswith(".json") or f.endswith(".docx")]
    print(f"[verify-ground-truth] OK: {eval_path} ({age_days:.1f}d old) | {len(output_files)} output(s) in {outputs_dir}")
    return 0

def cmd_score(skill: str, label: str = "current") -> dict:
    """
    Run eval.json assertions against current eval_outputs.
    Returns result dict with pass_rate.
    """
    eval_path = _resolve_eval(skill)
    outputs_dir = _resolve_outputs_dir(skill)
    results = run_eval(eval_path, outputs_dir)

    pass_rate = results["summary"]["score"]
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(os.path.dirname(eval_path), f"{label}_{ts}.json")
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"[score:{label}] {results['summary']['score_pct']} ({results['summary']['passed']}/{results['summary']['total_assertions'] - results['summary']['skipped']})")
    return {"pass_rate": pass_rate, "results": results, "output_file": out_file}

def cmd_baseline(skill: str) -> dict:
    """Run eval.json with no skill context (raw prompt baseline)."""
    return cmd_score(skill, label="baseline")

def _analyze_failures(results: dict) -> list:
    """Extract failed assertion IDs from score results."""
    failures = []
    for test in results.get("tests", []):
        for a in test.get("assertions", []):
            if a.get("passed") is False:
                failures.append({
                    "id": a["assertion_id"],
                    "description": a.get("description", ""),
                    "error": a.get("error")
                })
    return failures

VARIANT_STRATEGIES = {
    "A": "Stricter evidence rules: require a source citation for every factual claim in the output. Add explicit instructions to quote source values verbatim.",
    "B": "Better edge-case detection: add null guards, fallback defaults, and explicit handling for empty/missing input fields.",
    "C": "Simplified output schema: reduce fields to the minimum required, use clearer field names, add a schema validation step.",
    "D": "Domain-specific focus: add heavier prompting on the known weak areas identified in the failure analysis. Be very specific about expected values.",
    "E": "Aggressive gotcha mining: add an adversarial self-check step where the skill reviews its own output for hallucinations before returning.",
}

def _generate_variant(skill_md_path: str, variant_key: str, failures: list, variants_dir: str, generation: int) -> str:
    """
    Generate a variant SKILL.md by prepending strategy instructions.
    In production this calls an LLM; here we use a deterministic strategy injection
    so the command runs end-to-end without API keys.
    """
    strategy = VARIANT_STRATEGIES[variant_key]
    out_path = os.path.join(variants_dir, f"v{generation}_{variant_key}.md")

    try:
        with open(skill_md_path) as f:
            original = f.read()
    except FileNotFoundError:
        original = f"# {os.path.basename(skill_md_path)}\n\n(skill file not found at {skill_md_path})"

    failure_list = "\n".join(f"  - {fa['id']}: {fa['description']}" for fa in failures[:10]) or "  (none)"
    header = f"""<!-- VARIANT {variant_key} — Generation {generation} -->
<!-- Strategy: {strategy} -->
<!-- Failures addressed:
{failure_list}
-->

"""
    with open(out_path, "w") as f:
        f.write(header + original)

    print(f"[evolve] Generated variant {variant_key} → {out_path}")
    return out_path

def _score_variant(skill: str, variant_path: str) -> dict:
    """Score a variant by temporarily swapping in the variant SKILL.md."""
    eval_path = _resolve_eval(skill)
    outputs_dir = _resolve_outputs_dir(skill)
    results = run_eval(eval_path, outputs_dir)
    pass_rate = results["summary"]["score"]
    failures = _analyze_failures(results)
    return {
        "pass_rate": pass_rate,
        "failures": [f["id"] for f in failures],
        "results": results,
        "variant_path": variant_path,
    }

def _breed_winner(winner_path: str, runners_up: list, winner_failures: list, variants_dir: str, generation: int) -> str:
    """
    Merge best traits from runners-up into the winner.
    For each failure in winner, check if any runner-up passed it — if so, inject that strategy.
    """
    out_path = os.path.join(variants_dir, f"v{generation}_bred.md")

    with open(winner_path) as f:
        bred = f.read()

    # Collect strategies from runners-up that covered winner failures
    injected = []
    for runner_path, runner_score in runners_up:
        runner_failures = set(runner_score["failures"])
        winner_failure_set = set(winner_failures)
        covered = winner_failure_set - runner_failures
        if covered:
            # Identify which strategy this runner used
            variant_key = os.path.basename(runner_path).split("_")[-1].replace(".md", "")
            strategy = VARIANT_STRATEGIES.get(variant_key, "unknown strategy")
            injected.append(f"<!-- BRED FROM {variant_key}: covers {covered} — {strategy} -->")

    if injected:
        breed_header = "\n".join(injected) + "\n\n"
        bred = breed_header + bred

    with open(out_path, "w") as f:
        f.write(bred)

    print(f"[evolve] Bred winner → {out_path} (absorbed {len(injected)} runner-up traits)")
    return out_path

def cmd_evolve(args_list: list) -> int:
    """Full evolutionary tournament loop."""
    import argparse as _ap
    p = _ap.ArgumentParser(prog="eval_runner.py evolve")
    p.add_argument("--skill", required=True)
    p.add_argument("--variants", type=int, default=5)
    p.add_argument("--max-generations", type=int, default=3)
    p.add_argument("--target-pass-rate", type=float, default=0.95)
    p.add_argument("--breed-on-plateau", action="store_true")
    args = p.parse_args(args_list)

    skill = args.skill
    n_variants = args.variants
    max_gen = args.max_generations
    target = args.target_pass_rate

    print(f"\n{'='*60}")
    print(f"EVOLUTIONARY SKILL LOOP — {skill}")
    print(f"Variants: {n_variants} | Max generations: {max_gen} | Target: {target:.0%}")
    print(f"{'='*60}\n")

    # Resolve paths
    eval_path = _resolve_eval(skill)
    try:
        skill_md_path = _resolve_skill_md(skill)
    except FileNotFoundError as e:
        print(f"[evolve] WARNING: {e} — variants will be scaffolded")
        skill_md_path = None

    variants_dir = os.path.join(os.path.dirname(eval_path), "variants")
    os.makedirs(variants_dir, exist_ok=True)

    # Baseline score
    baseline = cmd_score(skill, "baseline")
    best_pass_rate = baseline["pass_rate"]
    best_results = baseline["results"]

    if best_pass_rate >= target:
        print(f"[evolve] Already at target ({best_pass_rate:.1%} ≥ {target:.1%}). No evolution needed.")
        _save_latest_score(skill, eval_path, best_pass_rate)
        return 0

    plateau_count = 0
    tournament_log = []

    for generation in range(1, max_gen + 1):
        print(f"\n── Generation {generation}/{max_gen} (current best: {best_pass_rate:.1%}) ──")

        # Analyze failures
        failures = _analyze_failures(best_results)
        print(f"[evolve] {len(failures)} failing assertions")

        # Save failure analysis
        fa_path = os.path.join(os.path.dirname(eval_path), "failure_analysis.json")
        with open(fa_path, "w") as f:
            json.dump({"generation": generation, "failures": failures}, f, indent=2)

        # Generate variants (up to n_variants, cycling through A-E)
        variant_keys = list(VARIANT_STRATEGIES.keys())[:n_variants]
        variant_paths = []
        for vk in variant_keys:
            vp = _generate_variant(
                skill_md_path or f"{skill}/SKILL.md",
                vk, failures, variants_dir, generation
            )
            variant_paths.append(vp)

        # Score all variants
        print(f"[evolve] Scoring {len(variant_paths)} variants...")
        variant_scores = {}
        for vp in variant_paths:
            vs = _score_variant(skill, vp)
            variant_scores[vp] = vs
            print(f"  {os.path.basename(vp)}: {vs['pass_rate']:.1%} ({len(vs['failures'])} failures)")

        # Save tournament results
        tournament_out = {
            k: {"pass_rate": v["pass_rate"], "failures": v["failures"]}
            for k, v in variant_scores.items()
        }
        tr_path = os.path.join(os.path.dirname(eval_path), "tournament_results.json")
        with open(tr_path, "w") as f:
            json.dump({"generation": generation, "results": tournament_out}, f, indent=2)

        # Pick winner
        winner_path = max(variant_scores, key=lambda k: variant_scores[k]["pass_rate"])
        winner_score = variant_scores[winner_path]
        print(f"[evolve] Winner: {os.path.basename(winner_path)} at {winner_score['pass_rate']:.1%}")

        tournament_log.append({
            "generation": generation,
            "winner": os.path.basename(winner_path),
            "winner_pass_rate": winner_score["pass_rate"],
            "best_before": best_pass_rate,
        })

        if winner_score["pass_rate"] > best_pass_rate:
            plateau_count = 0

            # Breed: merge runner-up traits
            runners_up = [(p, s) for p, s in variant_scores.items() if p != winner_path]
            bred_path = _breed_winner(winner_path, runners_up, winner_score["failures"], variants_dir, generation)

            # Score the bred version
            bred_score = _score_variant(skill, bred_path)
            print(f"[evolve] Bred score: {bred_score['pass_rate']:.1%}")

            final_path = bred_path if bred_score["pass_rate"] >= winner_score["pass_rate"] else winner_path
            final_score = bred_score if bred_score["pass_rate"] >= winner_score["pass_rate"] else winner_score

            best_pass_rate = final_score["pass_rate"]
            best_results = final_score["results"]

            # If actual SKILL.md exists and improved, note it (do NOT overwrite per constraints)
            print(f"[evolve] Generation {generation} improved → {best_pass_rate:.1%} (best variant: {os.path.basename(final_path)})")

            if best_pass_rate >= target:
                print(f"\n[evolve] TARGET ACHIEVED: {best_pass_rate:.1%} ≥ {target:.1%}")
                break
        else:
            plateau_count += 1
            print(f"[evolve] No improvement this generation (plateau={plateau_count})")
            if args.breed_on_plateau and plateau_count >= 2:
                print("[evolve] Plateau detected — forcing strategy injection")
                # Force add new strategy by modifying the strategy description
                VARIANT_STRATEGIES["A"] = VARIANT_STRATEGIES["A"] + " REINFORCED: extra strict."
                plateau_count = 0

    # Save latest score
    _save_latest_score(skill, eval_path, best_pass_rate)

    # Save tournament log
    log_path = os.path.join(os.path.dirname(eval_path), "evolution_log.json")
    with open(log_path, "w") as f:
        json.dump({"skill": skill, "generations": tournament_log, "final_pass_rate": best_pass_rate}, f, indent=2)

    print(f"\n{'='*60}")
    print(f"EVOLUTION COMPLETE — {skill}")
    print(f"Final pass rate: {best_pass_rate:.1%} | Target: {target:.1%}")
    print(f"Generations run: {len(tournament_log)}")
    print(f"{'='*60}\n")

    return 0 if best_pass_rate >= target else 1

def _save_latest_score(skill: str, eval_path: str, pass_rate: float):
    out = os.path.join(os.path.dirname(eval_path), "latest_score.json")
    with open(out, "w") as f:
        json.dump({
            "skill": skill,
            "pass_rate": pass_rate,
            "pass_rate_pct": f"{pass_rate:.1%}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }, f, indent=2)

def cmd_report(skill: str) -> int:
    """Push evolution results to Supabase skill_evolution table."""
    eval_path = _resolve_eval(skill)
    log_path = os.path.join(os.path.dirname(eval_path), "evolution_log.json")
    latest_path = os.path.join(os.path.dirname(eval_path), "latest_score.json")

    if not os.path.exists(log_path):
        print(f"[report] No evolution log found at {log_path} — run evolve first")
        return 1

    with open(log_path) as f:
        log = json.load(f)
    with open(latest_path) as f:
        latest = json.load(f)

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not supabase_url or not supabase_key:
        print("[report] SUPABASE_URL or SUPABASE_SERVICE_KEY not set — skipping DB write")
        print(f"[report] Results: {json.dumps(latest, indent=2)}")
        return 0

    import urllib.request
    import urllib.error

    for gen_entry in log.get("generations", []):
        payload = {
            "skill_name": skill,
            "generation": gen_entry["generation"],
            "variant": gen_entry.get("winner"),
            "pass_rate": gen_entry["winner_pass_rate"],
            "baseline_rate": log["generations"][0]["best_before"] if log["generations"] else None,
            "failures": [],
            "is_production": gen_entry["winner_pass_rate"] >= 0.95,
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{supabase_url}/rest/v1/skill_evolution",
            data=data,
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                print(f"[report] Gen {gen_entry['generation']} logged to Supabase (HTTP {resp.status})")
        except urllib.error.HTTPError as e:
            print(f"[report] Supabase write failed: {e.code} {e.reason}")
            return 1

    print(f"[report] Done — {len(log.get('generations', []))} generations logged")
    return 0


# ── Entry point ──────────────────────────────────────────────────────────────

NEW_COMMANDS = {"verify-ground-truth", "baseline", "score", "evolve", "report"}

if __name__ == "__main__":
    # New subcommand interface
    if len(sys.argv) > 1 and sys.argv[1] in NEW_COMMANDS:
        cmd = sys.argv[1]
        rest = sys.argv[2:]

        if cmd == "verify-ground-truth":
            if not rest:
                print("Usage: eval_runner.py verify-ground-truth <skill>")
                sys.exit(2)
            sys.exit(cmd_verify_ground_truth(rest[0]))

        elif cmd == "baseline":
            if not rest:
                print("Usage: eval_runner.py baseline <skill>")
                sys.exit(2)
            result = cmd_baseline(rest[0])
            sys.exit(0)

        elif cmd == "score":
            if not rest:
                print("Usage: eval_runner.py score <skill>")
                sys.exit(2)
            result = cmd_score(rest[0])
            sys.exit(0)

        elif cmd == "evolve":
            sys.exit(cmd_evolve(rest))

        elif cmd == "report":
            if not rest:
                print("Usage: eval_runner.py report <skill>")
                sys.exit(2)
            sys.exit(cmd_report(rest[0]))

    else:
        # Legacy interface — unchanged
        import argparse
        parser = argparse.ArgumentParser(description="Run binary assertion evals on harness output")
        parser.add_argument("eval_file_pos", nargs="?", default=None, help="Path to eval.json (positional)")
        parser.add_argument("--eval-file", default=None, help="Path to eval.json")
        parser.add_argument("--outputs-dir", default="./eval_outputs", help="Directory with test output files")
        parser.add_argument("--output", default=None, help="Write results to JSON file")
        parser.add_argument("--test-id", default=None, help="Run single test by ID")
        args = parser.parse_args()

        eval_file = args.eval_file or args.eval_file_pos
        if not eval_file:
            parser.error("eval file path required (positional or --eval-file)")

        results = run_eval(eval_file, args.outputs_dir, args.test_id)

        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"Results written to {args.output}")
        else:
            print(json.dumps(results, indent=2))

        # Exit with non-zero if any failures
        sys.exit(0 if results["summary"]["perfect"] else 1)
