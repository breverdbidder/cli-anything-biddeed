#!/usr/bin/env python3
"""validate_platform_skills.py — Structural validator for .claude/skills/ Platform Skills.

Runs without DB or network access. Checks:
  1. SKILL.md frontmatter: name, description required
  2. SKILL.md body: Role, Working Mode, Focus Areas, Quality Gates, Output Format, Constraints, Guard Rail
  3. eval.json: 25 binary assertions, pass_threshold=0.8, autoloop_compatible=true

Exit 0 = all pass. Exit 1 = failures found.
"""
import json
import sys
import re
from pathlib import Path

SKILLS_DIR = Path(".claude/skills")
REQUIRED_SECTIONS = [
    "## Role",
    "## Working Mode",
    "## Focus Areas",
    "## Quality Gates",
    "## Output Format",
    "## Constraints",
    "## Guard Rail",
]
REQUIRED_EVAL_FIELDS = {"skill_id", "version", "assertions", "pass_threshold", "autoloop_compatible"}
EXPECTED_ASSERTIONS = 25
EXPECTED_THRESHOLD = 0.8

# Platform Skills candidates from spec
CANDIDATES = [
    "zonewise-scraper",
    "cost-discipline",
    "honesty-protocol",
    "brand-colors",
    "ship-gate",
]


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter between --- delimiters."""
    lines = content.split("\n")
    if not lines[0].strip() == "---":
        return {}, content
    end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), None)
    if end is None:
        return {}, content
    fm_lines = lines[1:end]
    body = "\n".join(lines[end + 1:])
    fm = {}
    for line in fm_lines:
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip()
    return fm, body


def validate_skill(skill_id: str) -> list[str]:
    """Returns list of failure messages (empty = pass)."""
    failures = []
    skill_dir = SKILLS_DIR / skill_id

    # 1. Directory exists
    if not skill_dir.is_dir():
        return [f"MISSING: .claude/skills/{skill_id}/ directory does not exist"]

    # 2. SKILL.md exists and is valid
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        failures.append(f"MISSING: .claude/skills/{skill_id}/SKILL.md")
    else:
        content = skill_md.read_text()
        fm, body = parse_frontmatter(content)

        # Frontmatter checks
        if "name" not in fm:
            failures.append(f"FAIL [{skill_id}] SKILL.md missing 'name' in frontmatter")
        elif fm["name"] != skill_id:
            failures.append(f"FAIL [{skill_id}] SKILL.md name='{fm['name']}' does not match dir '{skill_id}'")

        if "description" not in fm or len(fm.get("description", "")) < 20:
            failures.append(f"FAIL [{skill_id}] SKILL.md missing or too-short 'description' in frontmatter")

        # Body section checks
        for section in REQUIRED_SECTIONS:
            if section not in content:
                failures.append(f"FAIL [{skill_id}] SKILL.md missing section '{section}'")

        # Guard Rail must be a single sentence (not a list)
        guard_rail_match = re.search(r"## Guard Rail\s*\n(.+)", content)
        if guard_rail_match:
            guard_text = guard_rail_match.group(1).strip()
            if guard_text.startswith("-") or len(guard_text.split("\n")) > 2:
                failures.append(f"WARN [{skill_id}] Guard Rail should be a single directive, found multi-line")
        else:
            failures.append(f"FAIL [{skill_id}] SKILL.md Guard Rail section has no content")

    # 3. eval.json exists and is valid
    eval_json = skill_dir / "eval.json"
    if not eval_json.exists():
        failures.append(f"MISSING: .claude/skills/{skill_id}/eval.json")
    else:
        try:
            data = json.loads(eval_json.read_text())
        except json.JSONDecodeError as e:
            failures.append(f"FAIL [{skill_id}] eval.json invalid JSON: {e}")
            return failures

        # Required fields
        for field in REQUIRED_EVAL_FIELDS:
            if field not in data:
                failures.append(f"FAIL [{skill_id}] eval.json missing field '{field}'")

        # Assertion count
        assertions = data.get("assertions", [])
        if len(assertions) != EXPECTED_ASSERTIONS:
            failures.append(
                f"FAIL [{skill_id}] eval.json has {len(assertions)} assertions, expected {EXPECTED_ASSERTIONS}"
            )

        # All assertions are binary type
        non_binary = [a.get("id") for a in assertions if a.get("type") != "binary"]
        if non_binary:
            failures.append(f"FAIL [{skill_id}] eval.json non-binary assertion IDs: {non_binary}")

        # Required assertion fields
        for a in assertions:
            for field in ("id", "input", "expected", "type"):
                if field not in a:
                    failures.append(f"FAIL [{skill_id}] eval.json assertion {a.get('id','?')} missing '{field}'")
                    break

        # pass_threshold
        if data.get("pass_threshold") != EXPECTED_THRESHOLD:
            failures.append(
                f"FAIL [{skill_id}] eval.json pass_threshold={data.get('pass_threshold')}, expected {EXPECTED_THRESHOLD}"
            )

        # autoloop_compatible
        if not data.get("autoloop_compatible"):
            failures.append(f"FAIL [{skill_id}] eval.json autoloop_compatible must be true")

    return failures


def main():
    print("=" * 60)
    print("PLATFORM SKILLS STRUCTURAL VALIDATOR")
    print(f"Checking: {SKILLS_DIR}")
    print("=" * 60)

    all_pass = True
    results = {}

    for skill_id in CANDIDATES:
        failures = validate_skill(skill_id)
        results[skill_id] = failures
        if failures:
            all_pass = False
            print(f"\n❌ {skill_id}: {len(failures)} issue(s)")
            for f in failures:
                print(f"   {f}")
        else:
            print(f"\n✅ {skill_id}: PASS (SKILL.md + 25 assertions, threshold=0.8, autoloop=true)")

    print("\n" + "=" * 60)
    if all_pass:
        print(f"RESULT: ALL {len(CANDIDATES)} SKILLS PASS — VERIFIED")
        print("Status: UNTESTED (functional eval requires summit-task.yml + DB)")
        print("Migration: BLOCKED (SUPABASE_DB_PASSWORD stale)")
        print("Next: Reset DB password → dispatch platform-skills-migrate.yml → run dual evals")
    else:
        failures_total = sum(len(v) for v in results.values())
        print(f"RESULT: {failures_total} FAILURE(S) FOUND — fix before eval")
    print("=" * 60)

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
