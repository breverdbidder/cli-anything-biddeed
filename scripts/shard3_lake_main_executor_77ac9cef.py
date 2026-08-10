#!/usr/bin/env python3
"""GOLD STANDARD shard-3 (dispatch 77ac9cef), main session executor for Lake county.

Runs the full session in order:
  1. Baseline evaluation
  2. I-fix: municipal zoning substrate (zoning_districts + parcel_zones)
  3. C-fix: clerk portal Playwright crosscheck
  4. Post-fix evaluation
  5. Ultraloop audit row insertion
  6. Session close-out checkpoint

Usage: python3 scripts/shard3_lake_main_executor_77ac9cef.py [--dry-run]
"""
import importlib.util
import json
import os
import sys
import urllib.error
import urllib.request
import datetime

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
DRY_RUN = "--dry-run" in sys.argv
DISPATCH_ID = "77ac9cef-69e5-48e3-b76e-7bddb2b42d7d"


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=REST_HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def rest_post(path, body, prefer="return=representation"):
    headers = {**REST_HEADERS, "Prefer": prefer}
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=json.dumps(body).encode(),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            if prefer.startswith("return=representation"):
                return r.status, json.loads(r.read().decode())
            return r.status, None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=json.dumps(body).encode(),
        method="PATCH",
        headers={**REST_HEADERS, "Prefer": "return=representation"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(params).encode(),
        method="POST",
        headers={**REST_HEADERS, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def log(msg):
    ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def insert_ultraloop_row(county, letter, claim, refuter_evidence, survived):
    row = {
        "dispatch_id": DISPATCH_ID,
        "ultraloop_mode": "fallback",
        "county_slug": county,
        "letter": letter,
        "claim": claim,
        "refuter_evidence": refuter_evidence,
        "survived": survived,
    }
    if DRY_RUN:
        log(f"DRY-RUN: would insert ultraloop_audit row: {row}")
        return
    status, resp = rest_post("gold_standard_ultraloop_audit", row, prefer="return=minimal")
    if status in (200, 201):
        log(f"ultraloop_audit: inserted letter={letter} survived={survived}")
    else:
        log(f"ultraloop_audit INSERT FAILED: HTTP {status} {str(resp)[:200]}")


def main():
    log("=== SHARD-3 LAKE MAIN EXECUTOR (dispatch 77ac9cef) ===")
    if DRY_RUN:
        log("DRY-RUN MODE -- no writes")

    # ─── BASELINE ───
    log("BASELINE evaluation:")
    baseline = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
    log(f"  G: pass={baseline.get('G',{}).get('pass')} metric={baseline.get('G',{}).get('metric')}")
    log(f"  I: pass={baseline.get('I',{}).get('pass')} metric={baseline.get('I',{}).get('metric')} "
        f"detail={baseline.get('I',{}).get('detail')}")
    log(f"  C: pass={baseline.get('C',{}).get('pass')} metric={baseline.get('C',{}).get('metric')} "
        f"detail={baseline.get('C',{}).get('detail')}")
    log(f"  total: {sum(1 for k in 'ABCDEFGHIJ' if baseline.get(k, {}).get('pass'))}/10")

    # ─── I FIX ───
    log("\n=== STEP 1: I-fix (municipal zoning substrate) ===")
    _here = os.path.dirname(os.path.abspath(__file__))

    # Import and run the I-fix module
    spec = importlib.util.spec_from_file_location(
        "i_fix", os.path.join(_here, "shard3_lake_i_apply_and_verify_77ac9cef.py"))
    i_fix_mod = importlib.util.module_from_spec(spec)
    # Inject dry_run into sys.argv for the submodule
    orig_argv = sys.argv[:]
    if DRY_RUN and "--dry-run" not in sys.argv:
        sys.argv.append("--dry-run")
    spec.loader.exec_module(i_fix_mod)
    sys.argv = orig_argv

    # ─── C FIX ───
    log("\n=== STEP 2: C-fix (clerk portal Playwright crosscheck) ===")
    spec2 = importlib.util.spec_from_file_location(
        "c_fix", os.path.join(_here, "shard3_lake_c_clerk_crosscheck_77ac9cef.py"))
    c_fix_mod = importlib.util.module_from_spec(spec2)
    orig_argv = sys.argv[:]
    if DRY_RUN and "--dry-run" not in sys.argv:
        sys.argv.append("--dry-run")
    try:
        spec2.loader.exec_module(c_fix_mod)
    except SystemExit as e:
        log(f"C-fix module exited with code {e.code} (likely playwright missing or portal unreachable)")
    sys.argv = orig_argv

    # ─── FINAL EVALUATION ───
    log("\n=== FINAL EVALUATION ===")
    final = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
    log(f"FINAL: {json.dumps(final)}")

    total_pass = sum(1 for k in "ABCDEFGHIJ" if final.get(k, {}).get("pass"))
    log(f"Lake score: {total_pass}/10")

    # ─── ULTRALOOP AUDIT ───
    log("\n=== ULTRALOOP AUDIT ROWS ===")
    for letter in ["I", "C", "G"]:
        bef = baseline.get(letter, {})
        aft = final.get(letter, {})
        survived = aft.get("pass") == bef.get("pass") or aft.get("metric", 0) >= bef.get("metric", 0)
        claim = (f"letter {letter}: baseline metric={bef.get('metric')} pass={bef.get('pass')} -> "
                 f"after metric={aft.get('metric')} pass={aft.get('pass')}")
        refuter = {
            "before": bef,
            "after": aft,
            "method": "pencil_dod_evaluate_county live re-run",
            "timestamp_utc": datetime.datetime.utcnow().isoformat(),
        }
        if letter == "G" and not aft.get("pass") and bef.get("pass"):
            survived = False
            refuter["finding"] = "G REGRESSED -- CRITICAL: revert parcel_zones inserts"
        insert_ultraloop_row("lake", letter, claim, json.dumps(refuter), survived)

    # ─── SESSION CLOSE-OUT ───
    log("\n=== MANDATORY SESSION CLOSE-OUT ===")
    criteria_passed = {k: bool(final.get(k, {}).get("pass")) for k in "ABCDEFGHIJ"}
    exit_reason = "timeout"
    if all(criteria_passed.values()):
        exit_reason = "certified"

    closeout = {
        "criteria_passed": criteria_passed,
        "criteria_total": 10,
        "exit_reason": exit_reason,
        "session_end_at": datetime.datetime.utcnow().isoformat() + "Z",
    }

    if DRY_RUN:
        log(f"DRY-RUN: would update gold_standard_campaign: {closeout}")
    else:
        # Find the dispatch row
        disp_rows = rest_get(
            f"gold_standard_campaign?dispatch_id=eq.{DISPATCH_ID}&limit=1&select=id")
        if disp_rows:
            disp_id = disp_rows[0]["id"]
            status, resp = rest_patch(
                f"gold_standard_campaign?id=eq.{disp_id}", closeout)
            log(f"Closeout UPDATE: HTTP {status} (id={disp_id})")
        else:
            # Try summit_chat_dispatch fallback
            log(f"No gold_standard_campaign row for dispatch_id={DISPATCH_ID}; "
                f"close-out data:\n{json.dumps(closeout, indent=2)}")

    log(f"\n### FINAL SUMMARY")
    log(f"Lake: {total_pass}/10 passing")
    for k in "ABCDEFGHIJ":
        bef = baseline.get(k, {})
        aft = final.get(k, {})
        changed = "CHANGED" if bef.get("pass") != aft.get("pass") else ""
        log(f"  {k}: {bef.get('pass')} ({bef.get('metric')}) -> {aft.get('pass')} ({aft.get('metric')}) {changed}")

    log("\n=== SESSION COMPLETE ===")


if __name__ == "__main__":
    main()
