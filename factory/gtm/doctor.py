#!/usr/bin/env python3
"""CMO FACTORY (issue #19777) -- autonomy-dial doctor.

Checklist of what the factory needs before it may claim each autonomy dial
(docs/gtm/META.md SS4). Every item is checked live (filesystem, `gh`,
Supabase RPC) -- nothing here is a hand-maintained checkbox. This script is
EXPECTED to fail on its first run (and for some while after CP0): several
items (real holdout content, mutation-set-of-5, a drilled kill switch) are
explicitly out of scope for CP0 and land in later checkpoints.

Exit code: 0 only if every item passes (i.e. dial 5 fully earned). Prints a
todo list of exactly what remains and which dial each blocks.
"""
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _exists(rel_path):
    return os.path.exists(os.path.join(REPO_ROOT, rel_path))


def _read(rel_path):
    with open(os.path.join(REPO_ROOT, rel_path), "r", encoding="utf-8") as f:
        return f.read()


def _gh_json(args):
    try:
        out = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            return None, out.stderr.strip()
        return json.loads(out.stdout), None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def _supabase_rpc(fn, payload):
    import urllib.request
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None, "SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set"
    req = urllib.request.Request(
        f"{url}/rest/v1/rpc/{fn}",
        data=json.dumps(payload).encode(),
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode() or "null"), None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def check_dial0_workflows_exist():
    ok = _exists(".github/workflows/gtm-validate.yml") and _exists(".github/workflows/gtm-merge.yml")
    return ok, "gtm-validate.yml and gtm-merge.yml present" if ok else "gtm-validate.yml/gtm-merge.yml missing"


def check_dial1_mission_never_items():
    if not _exists("docs/gtm/MISSION.md"):
        return False, "docs/gtm/MISSION.md missing"
    text = _read("docs/gtm/MISSION.md")
    import re
    items = re.findall(r"^\d+\.\s", text, re.MULTILINE)
    n = len(items)
    return (n >= 7), f"MISSION.md has {n} NEVER-list items (need >=7)"


def check_dial1_journeys_documented():
    if not _exists("harness/gtm/END-TO-END.md"):
        return False, "harness/gtm/END-TO-END.md missing"
    text = _read("harness/gtm/END-TO-END.md")
    n = text.count("## Journey ")
    return (n >= 5), f"END-TO-END.md documents {n}/5 journeys"


def check_dial1_labels_exist():
    # `gh label list --json` has been observed to silently truncate/omit
    # results on repos with a large label set (this repo has 100+ labels) --
    # `gh api ... --paginate` does not have that failure mode, use it instead.
    try:
        out = subprocess.run(
            ["gh", "api", "repos/breverdbidder/cli-anything-biddeed/labels", "--paginate", "--jq", ".[].name"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:  # noqa: BLE001
        return False, f"could not list labels: {e}"
    if out.returncode != 0:
        return False, f"could not list labels: {out.stderr.strip()}"
    names = {n for n in out.stdout.splitlines() if n}
    required = {"factory:queued", "factory:building", "factory:validating", "factory:pass",
                "factory:fail", "factory:merged", "factory:needs-human", "factory:halt"}
    missing = required - names
    return (not missing), ("all 8 factory: labels present" if not missing else f"missing labels: {sorted(missing)}")


def check_dial1_control_issue():
    issues, err = _gh_json(["issue", "list", "--repo", "breverdbidder/cli-anything-biddeed",
                             "--search", "CMO FACTORY — control in:title", "--json", "number,title,state", "--limit", "5"])
    if issues is None:
        return False, f"could not search issues: {err}"
    hit = [i for i in issues if "CMO FACTORY" in i["title"] and "control" in i["title"].lower()]
    return (len(hit) >= 1), (f"control issue #{hit[0]['number']} found" if hit else "no pinned 'CMO FACTORY — control' issue found")


def check_dial2_holdout_real():
    if not _exists(".factory/gtm/holdout/HOLDOUT.md"):
        return False, "HOLDOUT.md missing entirely"
    text = _read(".factory/gtm/holdout/HOLDOUT.md")
    is_stub = "written by validator role in CP4" in text and "This file is a stub" in text
    return (not is_stub), ("HOLDOUT.md is authored content" if not is_stub else "HOLDOUT.md is still the CP0 stub -- CP4 work")


def check_dial2_builder_block_proven():
    script = os.path.join(REPO_ROOT, "factory", "gtm", "test_holdout_negative.sh")
    if not os.path.exists(script):
        return False, "test_holdout_negative.sh missing"
    r = subprocess.run(["bash", script], capture_output=True, text=True, timeout=120, cwd=REPO_ROOT)
    ok = r.returncode == 0 and "NEGATIVE TEST RESULT: PASS" in r.stdout
    return ok, ("builder-role holdout read proven blocked (live re-run)" if ok else f"negative test did not pass: rc={r.returncode}")


def check_dial3_mutation_set():
    # CP0 does not ship a mutation set at all -- expected FAIL until CP4/CP5.
    exists = _exists(".factory/gtm/mutation_set")
    if not exists:
        return False, "mutation set (5/5) not built -- CP4/CP5 work, not in CP0 scope"
    n = len(os.listdir(os.path.join(REPO_ROOT, ".factory/gtm/mutation_set")))
    return (n >= 5), f"mutation set has {n}/5 entries"


def check_dial3_ratchet_floor():
    if not _exists(".factory/gtm/locks/floor.json"):
        return False, "floor.json missing"
    try:
        data = json.loads(_read(".factory/gtm/locks/floor.json"))
    except json.JSONDecodeError as e:
        return False, f"floor.json invalid JSON: {e}"
    ok = "journey_assertions" in data and data.get("compliance_checks") == 6
    return ok, f"floor.json: journey_assertions={data.get('journey_assertions')} compliance_checks={data.get('compliance_checks')}"


def check_dial3_kill_switch_drilled():
    # A drill means an actual halted workflow run was observed, not just the
    # doc existing. CP0 ships the doc + the 3 signals' plumbing but has not
    # yet run gtm-validate.yml against a live .factory/gtm/STOP file and
    # observed it refuse -- that drill is explicitly deferred to CP5.
    doc_ok = _exists(".factory/gtm/STOP.md")
    return False, ("STOP.md semantics documented but NOT yet drilled against a live workflow run -- CP5 work" if doc_ok else "STOP.md missing")


def check_dial8_watchdog_function():
    result, err = _supabase_rpc("gtm_watchdog", {})
    if err:
        return False, f"could not call public.gtm_watchdog(): {err}"
    return True, f"public.gtm_watchdog() callable, returned: {json.dumps(result)[:200]}"


CHECKS = [
    ("dial0_workflows_exist", check_dial0_workflows_exist, 0),
    ("dial1_mission_never_items", check_dial1_mission_never_items, 1),
    ("dial1_journeys_documented", check_dial1_journeys_documented, 1),
    ("dial1_labels_exist", check_dial1_labels_exist, 1),
    ("dial1_control_issue", check_dial1_control_issue, 1),
    ("dial2_holdout_real", check_dial2_holdout_real, 2),
    ("dial2_builder_block_proven", check_dial2_builder_block_proven, 2),
    ("dial3_mutation_set", check_dial3_mutation_set, 3),
    ("dial3_ratchet_floor", check_dial3_ratchet_floor, 3),
    ("dial3_kill_switch_drilled", check_dial3_kill_switch_drilled, 3),
    ("watchdog_function_live", check_dial8_watchdog_function, 3),
]


def main():
    results = []
    all_ok = True
    for name, fn, dial in CHECKS:
        try:
            ok, detail = fn()
        except Exception as e:  # noqa: BLE001
            ok, detail = False, f"CHECK RAISED: {e}"
        results.append((name, ok, detail, dial))
        all_ok = all_ok and ok

    print("=== CMO FACTORY doctor.py ===")
    for name, ok, detail, dial in results:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name} (blocks dial {dial}+): {detail}")

    todo = [(name, detail, dial) for name, ok, detail, dial in results if not ok]
    print()
    if not todo:
        print("ALL CHECKS PASS -- dial 5 fully earned.")
        sys.exit(0)

    max_clean_dial = min((d for _, ok, _, d in results if not ok), default=5) - 1
    print(f"CURRENT EARNED DIAL: {max(max_clean_dial, -1)}")
    print(f"REMAINING TODO ({len(todo)} items):")
    for name, detail, dial in todo:
        print(f"  - [{name}] blocks dial {dial}+: {detail}")
    sys.exit(1)


if __name__ == "__main__":
    main()
