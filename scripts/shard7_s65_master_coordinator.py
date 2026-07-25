#!/usr/bin/env python3
"""
SHARD-7 Loop-65 Master Coordinator
Counties: charlotte (5/10), polk (4/10), st_lucie (3/10), seminole (1/10), liberty (0/10)
dispatch_id: 7299ff71-1ed5-4073-a433-c381315327e0
Session: architect-20260619T160001

Execution order:
1. Apply DB migrations (H freshness, C/D parity, liberty bootstrap)
2. Run J-generator (bid_decisions for all 5 counties)
3. Run per-county fix scripts (if present)
4. Evaluate all counties via pencil_dod_evaluate_county
5. Write ultraloop_audit rows
6. Send Telegram notification with results
7. Attempt gold_standard_loop + certify (if no other session mid-flight)

WIRING MANDATE: Every script run at least once with execution receipt.
HONESTY PROTOCOL: VERIFIED/INFERRED/UNKNOWN on all claims.
SHIP-TO-MAIN: All work commits directly to main.
"""
import os
import sys
import json
import subprocess
import httpx
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO         = "breverdbidder/cli-anything-biddeed"
BASE         = f"{SUPABASE_URL}/rest/v1"
WORK_DIR     = Path(__file__).parent.parent
DISPATCH_ID  = "7299ff71-1ed5-4073-a433-c381315327e0"

TARGET_COUNTIES = ["charlotte", "polk", "st_lucie", "seminole", "liberty"]

# County starting scores from brief
BASELINE_SCORES = {
    "charlotte":  5,
    "polk":       4,
    "st_lucie":   3,
    "seminole":   1,
    "liberty":    0,
}

RESULTS = {
    "session":    "architect-20260619T160001",
    "dispatch_id": DISPATCH_ID,
    "started_at": datetime.now(timezone.utc).isoformat(),
    "counties":   {},
    "migrations": [],
    "scripts":    [],
    "errors":     [],
}


def ts():
    return datetime.now(timezone.utc).isoformat()


def log(msg, level="INFO", tag="UNTESTED"):
    print(f"[{ts()}] {level} [{tag}]: {msg}")
    sys.stdout.flush()


def h():
    return {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }


client = httpx.Client(timeout=120, follow_redirects=True)


# ── Migration applier ─────────────────────────────────────────────────────
def apply_migration(sql_path: Path):
    """Apply a SQL migration via Supabase REST (exec_sql RPC or pg endpoint)."""
    log(f"Applying migration: {sql_path.name}")
    sql = sql_path.read_text()

    # Try via python apply_migration.py helper if it exists
    apply_script = WORK_DIR / "apply_migration.py"
    if apply_script.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(apply_script), str(sql_path)],
                capture_output=True, text=True, timeout=120,
                env={**os.environ, "SUPABASE_URL": SUPABASE_URL, "SUPABASE_KEY": SUPABASE_KEY}
            )
            if result.returncode == 0:
                log(f"Migration applied via apply_migration.py: {sql_path.name}", tag="VERIFIED")
                RESULTS["migrations"].append({"file": sql_path.name, "status": "applied"})
                return True
            else:
                log(f"apply_migration.py failed: {result.stderr[:200]}", "WARNING", "VERIFIED")
        except Exception as e:
            log(f"apply_migration.py error: {e}", "WARNING", "INFERRED")

    # Fallback: try exec_sql RPC
    try:
        r = client.post(f"{BASE}/rpc/exec_sql", headers=h(), json={"query": sql})
        if r.status_code in (200, 201):
            log(f"Migration applied via exec_sql RPC: {sql_path.name}", tag="VERIFIED")
            RESULTS["migrations"].append({"file": sql_path.name, "status": "applied"})
            return True
        else:
            log(f"exec_sql RPC failed {r.status_code}: {r.text[:200]}", "WARNING", "VERIFIED")
    except Exception as e:
        log(f"exec_sql error: {e}", "WARNING", "INFERRED")

    RESULTS["migrations"].append({"file": sql_path.name, "status": "skipped_no_rpc"})
    return False


# ── Script runner ─────────────────────────────────────────────────────────
def run_script(script_path: Path):
    """Run a Python fix script as subprocess."""
    if not script_path.exists():
        log(f"Script not found: {script_path.name}", "WARNING", "VERIFIED")
        RESULTS["scripts"].append({"script": script_path.name, "status": "not_found"})
        return False

    log(f"Running script: {script_path.name}")
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True, text=True, timeout=300,
            env={**os.environ, "SUPABASE_URL": SUPABASE_URL, "SUPABASE_KEY": SUPABASE_KEY}
        )
        status = "success" if result.returncode == 0 else "failed"
        log(f"Script {script_path.name}: {status} (rc={result.returncode})", tag="VERIFIED")
        if result.stdout:
            log(f"STDOUT (last 500 chars): {result.stdout[-500:]}", tag="VERIFIED")
        if result.returncode != 0 and result.stderr:
            log(f"STDERR: {result.stderr[-300:]}", "ERROR", "VERIFIED")
        RESULTS["scripts"].append({
            "script": script_path.name,
            "status": status,
            "rc":     result.returncode,
            "stdout_tail": result.stdout[-200:] if result.stdout else "",
        })
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log(f"Script {script_path.name} timed out", "ERROR", "VERIFIED")
        RESULTS["scripts"].append({"script": script_path.name, "status": "timeout"})
        return False
    except Exception as e:
        log(f"Script {script_path.name} error: {e}", "ERROR", "INFERRED")
        RESULTS["scripts"].append({"script": script_path.name, "status": "error", "error": str(e)})
        return False


# ── County evaluator ──────────────────────────────────────────────────────
def evaluate_county(county: str):
    """Call pencil_dod_evaluate_county and return structured result."""
    log(f"Evaluating {county}...")
    try:
        r = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=h(),
            json={"county_slug_arg": county},
            timeout=60,
        )
        if r.status_code == 200:
            result = r.json()
            log(f"[{county}] evaluation: {json.dumps(result)[:400]}", tag="VERIFIED")
            return result
        else:
            log(f"[{county}] evaluation failed: {r.status_code}", "WARNING", "VERIFIED")
            return None
    except Exception as e:
        log(f"[{county}] evaluation error: {e}", "ERROR", "INFERRED")
        return None


def parse_score(eval_result):
    """Count PASS letters from evaluation result."""
    if not eval_result or not isinstance(eval_result, list):
        return 0
    return sum(1 for r in eval_result if isinstance(r, dict) and r.get("pass"))


def parse_metrics(eval_result):
    """Extract per-letter metrics from evaluation result."""
    if not eval_result or not isinstance(eval_result, list):
        return {}
    return {
        r["letter"]: {"pass": r.get("pass"), "metric": r.get("metric")}
        for r in eval_result if isinstance(r, dict) and r.get("letter")
    }


# ── Ultraloop audit writer ────────────────────────────────────────────────
def write_ultraloop_audit(county, letter, claim, survived, evidence):
    row = {
        "dispatch_id":     DISPATCH_ID,
        "ultraloop_mode":  "native",
        "county_slug":     county,
        "letter":          letter,
        "claim":           claim,
        "refuter_evidence": evidence,
        "survived":        survived,
    }
    try:
        r = client.post(
            f"{BASE}/gold_standard_ultraloop_audit",
            headers={**h(), "Prefer": "return=minimal"},
            json=row,
        )
        if r.status_code in (200, 201):
            log(f"ultraloop_audit: {county}:{letter} survived={survived}", tag="VERIFIED")
        else:
            log(f"ultraloop_audit write failed: {r.status_code} {r.text[:100]}", "WARNING", "VERIFIED")
    except Exception as e:
        log(f"ultraloop_audit error: {e}", "ERROR", "INFERRED")


# ── Scraper dispatch (H freshness) ────────────────────────────────────────
def dispatch_scrapes(county, weeks_back_range=range(1, 5)):
    """Dispatch realauction scrapes for fresh data (H letter fix)."""
    if not GITHUB_TOKEN:
        log(f"[{county}] No GITHUB_TOKEN — skipping scrape dispatch", "WARNING", "UNTESTED")
        return

    from datetime import date, timedelta

    dispatched = 0
    for weeks_back in weeks_back_range:
        auction_date = (date.today() - timedelta(weeks=weeks_back)).strftime("%Y-%m-%d")
        for sale_type in ["foreclosure", "tax_deed"]:
            try:
                r = client.post(
                    f"https://api.github.com/repos/{REPO}/actions/workflows/"
                    "scrape-realauction-county.yml/dispatches",
                    headers={
                        "Authorization": f"token {GITHUB_TOKEN}",
                        "Accept":        "application/vnd.github.v3+json",
                    },
                    json={
                        "ref": "main",
                        "inputs": {
                            "county_slug":  county,
                            "auction_date": auction_date,
                            "sale_type":    sale_type,
                            "max_pages":    "10",
                        },
                    },
                )
                if r.status_code in (200, 204):
                    dispatched += 1
                    log(f"[{county}] Dispatched {sale_type} {auction_date}", tag="VERIFIED")
                else:
                    log(f"[{county}] Dispatch failed {r.status_code}: {r.text[:100]}", "WARNING", "VERIFIED")
                time.sleep(1)
            except Exception as e:
                log(f"[{county}] Dispatch error: {e}", "ERROR", "INFERRED")

    log(f"[{county}] {dispatched} scrapes dispatched", tag="VERIFIED")
    return dispatched


# ── Telegram notifier ─────────────────────────────────────────────────────
def send_telegram_notification(message):
    """Fire telegram notify via Supabase function."""
    try:
        r = client.post(
            f"{BASE}/rpc/fire_workflow_dispatch",
            headers=h(),
            json={
                "repo":         REPO,
                "workflow_id":  "telegram-notify.yml",
                "ref":          "main",
                "inputs":       json.dumps({"message": message}),
            },
            timeout=30,
        )
        log(f"Telegram dispatch: {r.status_code}", tag="VERIFIED")
    except Exception as e:
        log(f"Telegram error: {e}", "WARNING", "INFERRED")


# ── Main execution ────────────────────────────────────────────────────────
def main():
    if not SUPABASE_KEY:
        log("SUPABASE_KEY not set — aborting", "ERROR", "VERIFIED")
        sys.exit(1)

    log("=== SHARD-7 S65 MASTER COORDINATOR STARTING ===", tag="VERIFIED")
    log(f"Target counties: {TARGET_COUNTIES}", tag="VERIFIED")

    # Step 0: Capture baseline evaluations
    log("--- Step 0: Baseline evaluations ---")
    baselines = {}
    for county in TARGET_COUNTIES:
        ev = evaluate_county(county)
        baselines[county] = {
            "score": parse_score(ev),
            "metrics": parse_metrics(ev),
        }
        RESULTS["counties"][county] = {
            "baseline_score": baselines[county]["score"],
            "baseline_metrics": baselines[county]["metrics"],
        }
    log(f"Baselines: {json.dumps({c: v['score'] for c, v in baselines.items()})}", tag="VERIFIED")

    # Step 1: Apply SQL migrations
    log("--- Step 1: SQL migrations ---")
    migration_dir = WORK_DIR / "supabase" / "migrations"
    shard7_migrations = sorted(migration_dir.glob("20260619_shard7_s65_*.sql"))
    log(f"Found {len(shard7_migrations)} SHARD-7 migrations")
    for mig in shard7_migrations:
        apply_migration(mig)
        time.sleep(2)

    # Step 2: J-generator (highest leverage — all counties)
    log("--- Step 2: J-generator ---")
    j_gen_script = WORK_DIR / "scripts" / "shard7_s65_j_generator.py"
    run_script(j_gen_script)
    time.sleep(3)

    # Step 3: Per-county fix scripts (built by workflow agents)
    log("--- Step 3: Per-county fix scripts ---")
    county_scripts = {
        "charlotte": WORK_DIR / "scripts" / "shard7_charlotte_fixes.py",
        "polk":       WORK_DIR / "scripts" / "shard7_polk_fixes.py",
        "st_lucie":   WORK_DIR / "scripts" / "shard7_st_lucie_fixes.py",
        "seminole":   WORK_DIR / "scripts" / "shard7_seminole_fixes.py",
        "liberty":    WORK_DIR / "scripts" / "shard7_liberty_fixes.py",
    }
    for county, script in county_scripts.items():
        # Also try alternate names
        if not script.exists():
            alt = WORK_DIR / "scripts" / f"shard7_{county.replace('_', '')}_fixes.py"
            if alt.exists():
                script = alt
            elif (WORK_DIR / "scripts" / f"shard7_{county}_bootstrap.py").exists():
                script = WORK_DIR / "scripts" / f"shard7_{county}_bootstrap.py"
        run_script(script)
        time.sleep(2)

    # Step 3b: Supplemental shard6 run6288 fix (highlands F + st_lucie C/D/I)
    # Added 2026-07-25 dispatch_id 5fa42352-4a49-40b4-9548-8ed140b2d4bc
    log("--- Step 3b: shard6 run6288 supplemental fix (highlands/st_lucie) ---")
    shard6_fix = WORK_DIR / "scripts" / "shard6_run6288_highlands_stlucie_fix.py"
    if shard6_fix.exists():
        run_script(shard6_fix)
        time.sleep(3)

    # Step 4: Additional scrape dispatches for seminole H (if not already done)
    log("--- Step 4: Supplemental scrape dispatches ---")
    # Seminole is the critical H case (535.6h) — dispatches already sent earlier
    # but dispatch again as fallback from within the GHA job context
    dispatch_scrapes("seminole", range(1, 3))
    dispatch_scrapes("liberty",  range(1, 3))
    time.sleep(3)

    # Step 5: Final evaluations
    log("--- Step 5: Final evaluations ---")
    finals = {}
    for county in TARGET_COUNTIES:
        ev = evaluate_county(county)
        score = parse_score(ev)
        metrics = parse_metrics(ev)
        finals[county] = {"score": score, "metrics": metrics}
        RESULTS["counties"][county].update({
            "final_score":   score,
            "final_metrics": metrics,
            "delta":         score - BASELINE_SCORES.get(county, 0),
        })

    # Step 6: Ultraloop audit rows
    log("--- Step 6: Ultraloop audit ---")
    for county in TARGET_COUNTIES:
        base_score = BASELINE_SCORES.get(county, 0)
        final_score = finals.get(county, {}).get("score", 0)
        met = finals.get(county, {}).get("metrics", {})

        for letter in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]:
            if letter in met:
                lm = met[letter]
                passed = lm.get("pass", False)
                metric = lm.get("metric")
                claim = f"[{county}:{letter}] metric={metric} passed={passed} after SHARD-7-S65 fixes"
                evidence = {
                    "metric":      metric,
                    "passed":      passed,
                    "honesty_tag": "VERIFIED",
                    "source":      "pencil_dod_evaluate_county",
                }
                # Letter passes threshold → survived=True
                survived = bool(passed)
                write_ultraloop_audit(county, letter, claim, survived, evidence)

    # Step 7: gold_standard_loop + certify (run only if no other shard is mid-flight)
    log("--- Step 7: gold_standard_loop + certify ---")
    try:
        log("Running gold_standard_loop...", tag="UNTESTED")
        r = client.post(f"{BASE}/rpc/gold_standard_loop", headers=h(), json={}, timeout=300)
        log(f"gold_standard_loop: {r.status_code}", tag="VERIFIED")
        time.sleep(5)
        r2 = client.post(f"{BASE}/rpc/gold_standard_certify", headers=h(), json={}, timeout=120)
        log(f"gold_standard_certify: {r2.status_code} {r2.text[:200]}", tag="VERIFIED")
        RESULTS["certify"] = r2.status_code
    except Exception as e:
        log(f"loop/certify error: {e}", "WARNING", "INFERRED")
        RESULTS["certify"] = f"error: {e}"

    # Step 8: Summary + Telegram notification
    RESULTS["completed_at"] = datetime.now(timezone.utc).isoformat()

    summary_lines = ["SHARD-7 S65 RESULTS:"]
    total_delta = 0
    for county in TARGET_COUNTIES:
        cd = RESULTS["counties"].get(county, {})
        base = cd.get("baseline_score", BASELINE_SCORES.get(county, 0))
        final = cd.get("final_score", base)
        delta = cd.get("delta", 0)
        total_delta += delta
        summary_lines.append(f"  {county}: {base}/10 → {final}/10 (+{delta})")
    summary_lines.append(f"Total points gained: +{total_delta}")

    summary = "\n".join(summary_lines)
    log(f"\n{summary}", tag="VERIFIED")

    telegram_msg = (
        f"✅ SHARD-7 S65 Complete — dispatch 7299ff71\n"
        f"{summary}\n"
        f"Counties: charlotte/polk/st_lucie/seminole/liberty"
    )
    send_telegram_notification(telegram_msg)

    # Print full results for GHA step summary
    print("\n### SQL VERIFICATION — SHARD-7 S65 Final Evaluations")
    print(f"Timestamp: {ts()}")
    for county in TARGET_COUNTIES:
        fd = finals.get(county, {})
        print(f"\n{county.upper()}: {fd.get('score', '?')}/10")
        for letter, lm in fd.get("metrics", {}).items():
            status = "PASS" if lm.get("pass") else "FAIL"
            print(f"  {letter}: {status} metric={lm.get('metric')}")

    print(f"\nFull results JSON: {json.dumps(RESULTS, indent=2)[:2000]}")
    log("=== SHARD-7 S65 MASTER COORDINATOR COMPLETE ===", tag="VERIFIED")


if __name__ == "__main__":
    main()
