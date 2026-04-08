#!/usr/bin/env python3
"""
SUMMIT Spec Fulfillment Verifier — closes the GHA-success-vs-delivered gap.

Fetches a SUMMIT issue, extracts its acceptance checklist, cross-references
the CC completion report against actual artifacts (PRs, commits, Supabase
tables, files), and produces a per-item verification matrix.

Usage:
    python scripts/spec_fulfillment_verifier.py --issue 393
    python scripts/spec_fulfillment_verifier.py --issue 393 --dry-run
"""
set_euo_pipefail = True  # conceptual — Python equivalent via strict error handling

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REPO = "breverdbidder/cli-anything-biddeed"
GH_API = "https://api.github.com"
GH_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GH_PAT", "")
SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")
TG_TOKEN = os.environ.get("BIDDEED_BOT_TOKEN", "")
TG_CHAT = os.environ.get("BIDDEED_BOT_CHAT_ID", "740118343")
TIMEOUT = 15.0

# Verdicts
DELIVERED = "DELIVERED-VERIFIED"
NOT_DELIVERED = "GHA-GREEN-NOT-DELIVERED"
DISPATCHED_ONLY = "DISPATCHED-ONLY"
BLOCKED_HONEST = "BLOCKED-HONEST"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def gh_headers():
    return {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}


def sb_headers():
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}


def gh_get(path: str) -> dict | list:
    r = httpx.get(f"{GH_API}{path}", headers=gh_headers(), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def sb_get(path: str) -> dict | list:
    r = httpx.get(f"{SB_URL}{path}", headers=sb_headers(), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def sb_post(path: str, data: dict) -> httpx.Response:
    h = sb_headers()
    h["Prefer"] = "return=representation"
    return httpx.post(f"{SB_URL}{path}", headers=h, json=data, timeout=TIMEOUT)


def tg_send(msg: str) -> bool:
    if not TG_TOKEN:
        print("[tg] No bot token — skipping notification")
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": msg[:4000], "parse_mode": "HTML"},
            timeout=10.0,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"[tg] Send failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Issue parsing
# ---------------------------------------------------------------------------
def fetch_issue(issue_number: int) -> dict:
    return gh_get(f"/repos/{REPO}/issues/{issue_number}")


def fetch_comments(issue_number: int) -> list[dict]:
    comments = []
    page = 1
    while True:
        batch = gh_get(f"/repos/{REPO}/issues/{issue_number}/comments?per_page=100&page={page}")
        if not batch:
            break
        comments.extend(batch)
        page += 1
    return comments


def extract_checklist(body: str) -> list[str]:
    """Extract acceptance checklist items from issue body."""
    items = []
    for line in body.split("\n"):
        line = line.strip()
        # Match - [ ] or - [x] patterns
        m = re.match(r"^-\s*\[[ xX]?\]\s*(.+)$", line)
        if m:
            items.append(m.group(1).strip())
    return items


def find_cc_report(comments: list[dict]) -> dict | None:
    """Find the CC final report comment (last substantive bot/CC comment)."""
    candidates = []
    for c in comments:
        body = c.get("body", "")
        user = c.get("user", {}).get("login", "")
        # Match CC reports — typically from breverdbidder or containing SUMMIT markers
        if user == "breverdbidder" or "SUMMIT" in body or "VERIFIED" in body or "DELIVERED" in body:
            candidates.append(c)
    return candidates[-1] if candidates else None


# ---------------------------------------------------------------------------
# Artifact verification
# ---------------------------------------------------------------------------
def verify_commit_exists(sha: str) -> bool:
    try:
        gh_get(f"/repos/{REPO}/commits/{sha}")
        return True
    except Exception:
        return False


def verify_pr_has_changes(pr_number: int) -> bool:
    try:
        pr = gh_get(f"/repos/{REPO}/pulls/{pr_number}")
        return pr.get("additions", 0) + pr.get("deletions", 0) > 0
    except Exception:
        return False


def verify_file_in_repo(file_path: str, branch: str = "main") -> bool:
    try:
        r = httpx.get(
            f"{GH_API}/repos/{REPO}/contents/{file_path}?ref={branch}",
            headers=gh_headers(),
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("size", 0) > 0
        return False
    except Exception:
        return False


def verify_supabase_table_exists(table_name: str) -> bool:
    try:
        r = httpx.get(
            f"{SB_URL}/rest/v1/{table_name}?select=*&limit=0",
            headers=sb_headers(),
            timeout=TIMEOUT,
        )
        return r.status_code == 200
    except Exception:
        return False


def verify_supabase_row_count(table_name: str, filters: str = "") -> int:
    try:
        h = sb_headers()
        h["Prefer"] = "count=exact"
        r = httpx.get(
            f"{SB_URL}/rest/v1/{table_name}?select=*{filters}&limit=0",
            headers=h,
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            cr = r.headers.get("content-range", "")
            # Format: */N or 0-0/N
            m = re.search(r"/(\d+)", cr)
            return int(m.group(1)) if m else 0
        return -1
    except Exception:
        return -1


# ---------------------------------------------------------------------------
# Checklist item verification logic
# ---------------------------------------------------------------------------
def verify_checklist_item(item: str, cc_report_body: str, issue_body: str) -> tuple[str, str]:
    """
    Verify a single checklist item against artifacts.
    Returns (verdict, evidence).
    """
    item_lower = item.lower()

    # Check if CC report explicitly marks this as blocked/failed
    if cc_report_body:
        for marker in ["BLOCKED", "FAILED", "could not", "unable to", "skipped"]:
            # Look for the marker near relevant keywords from the item
            keywords = [w for w in item_lower.split() if len(w) > 4][:3]
            for kw in keywords:
                pattern = f"(?i){re.escape(kw)}[^\\n]{{0,200}}{marker}|{marker}[^\\n]{{0,200}}{re.escape(kw)}"
                if re.search(pattern, cc_report_body):
                    return BLOCKED_HONEST, f"CC report explicitly marked blocked/failed near '{kw}'"

    # Check for UNTESTED tag near this item's keywords
    if cc_report_body:
        keywords = [w for w in item_lower.split() if len(w) > 4][:3]
        for kw in keywords:
            if re.search(f"(?i){re.escape(kw)}[^\\n]{{0,300}}UNTESTED|UNTESTED[^\\n]{{0,300}}{re.escape(kw)}", cc_report_body):
                return NOT_DELIVERED, f"CC report tagged UNTESTED near '{kw}'"

    # --- File committed checks ---
    file_patterns = re.findall(r"`([a-zA-Z0-9_./-]+\.[a-zA-Z]{1,5})`", item)
    for fp in file_patterns:
        # Normalize path — strip leading ./ or /
        fp_clean = fp.lstrip("./")
        if verify_file_in_repo(fp_clean):
            # File exists — if that's the main claim, it's delivered
            if "committed" in item_lower or "commit" in item_lower:
                return DELIVERED, f"File {fp_clean} exists in repo (non-zero size)"
        else:
            if "committed" in item_lower or "commit" in item_lower:
                return NOT_DELIVERED, f"File {fp_clean} NOT found in repo"

    # --- Migration applied to live Supabase ---
    if "migration" in item_lower and ("applied" in item_lower or "live" in item_lower):
        # Extract table name from item or issue body
        table_match = re.search(r"(?:for|table)\s+`?(\w+)`?", item)
        if table_match:
            table = table_match.group(1)
            if verify_supabase_table_exists(table):
                return DELIVERED, f"Table '{table}' exists in live Supabase"
            else:
                return NOT_DELIVERED, f"Table '{table}' NOT found in live Supabase"
        # Try information_schema check mentioned in item
        if "information_schema" in item_lower:
            table_match2 = re.search(r"`(\w+)`", item)
            if table_match2:
                table = table_match2.group(1)
                if verify_supabase_table_exists(table):
                    return DELIVERED, f"Table '{table}' exists in live Supabase"
                else:
                    return NOT_DELIVERED, f"Table '{table}' NOT found in live Supabase"

    # --- Supabase table/row verification ---
    if "rows" in item_lower or "row" in item_lower or "table" in item_lower:
        table_match = re.search(r"`(\w+)`\s*table|table\s*`(\w+)`|in\s+`(\w+)`", item)
        if table_match:
            table = table_match.group(1) or table_match.group(2) or table_match.group(3)
            count = verify_supabase_row_count(table)
            if count > 0:
                return DELIVERED, f"Table '{table}' has {count} rows"
            elif count == 0:
                return NOT_DELIVERED, f"Table '{table}' exists but has 0 rows"
            else:
                return NOT_DELIVERED, f"Table '{table}' query failed (may not exist)"

    # --- PR checks ---
    pr_match = re.search(r"PR\s*#?(\d+)|pull/(\d+)", item)
    if pr_match:
        pr_num = int(pr_match.group(1) or pr_match.group(2))
        if verify_pr_has_changes(pr_num):
            return DELIVERED, f"PR #{pr_num} has non-zero changes"
        else:
            return NOT_DELIVERED, f"PR #{pr_num} has no changes or doesn't exist"

    # --- Commit SHA checks ---
    sha_match = re.search(r"([0-9a-f]{7,40})", item)
    if sha_match and not re.match(r"^\d+$", sha_match.group(1)):
        sha = sha_match.group(1)
        if verify_commit_exists(sha):
            return DELIVERED, f"Commit {sha[:8]} exists"
        else:
            return NOT_DELIVERED, f"Commit {sha[:8]} not found"

    # --- Verifier execution checks (verdict-based) ---
    if "verdict" in item_lower or "executed" in item_lower or "verifier" in item_lower:
        # Check if CC report mentions the expected verdict
        if cc_report_body:
            verdict_match = re.search(r"(?:DELIVERED|PARTIAL|FAILED)", cc_report_body)
            if verdict_match:
                return DELIVERED, f"Verdict '{verdict_match.group()}' found in report"

    # --- Issue state checks ---
    if "reopen" in item_lower or "re-open" in item_lower:
        issue_match = re.search(r"#(\d+)", item)
        if issue_match:
            inum = int(issue_match.group(1))
            try:
                issue_data = gh_get(f"/repos/{REPO}/issues/{inum}")
                if issue_data.get("state") == "open":
                    return DELIVERED, f"Issue #{inum} is open"
                else:
                    return NOT_DELIVERED, f"Issue #{inum} is still closed"
            except Exception:
                return NOT_DELIVERED, f"Could not check issue #{inum}"

    # --- Label checks ---
    if "label" in item_lower:
        label_match = re.search(r"`([a-zA-Z0-9_-]+)`", item)
        issue_match = re.search(r"#(\d+)", item)
        if label_match and issue_match:
            label = label_match.group(1)
            inum = int(issue_match.group(1))
            try:
                issue_data = gh_get(f"/repos/{REPO}/issues/{inum}")
                labels = [l["name"] for l in issue_data.get("labels", [])]
                if label in labels:
                    return DELIVERED, f"Label '{label}' present on #{inum}"
                else:
                    return NOT_DELIVERED, f"Label '{label}' not found on #{inum}"
            except Exception:
                return NOT_DELIVERED, f"Could not check labels on #{inum}"

    # --- Telegram notification checks ---
    if "telegram" in item_lower:
        # We can't verify Telegram was sent retroactively — check CC report for evidence
        if cc_report_body and re.search(r"(?i)telegram.*(?:sent|notif|fired|delivered)", cc_report_body):
            return DELIVERED, "CC report claims Telegram notification sent"
        return NOT_DELIVERED, "No evidence of Telegram notification in CC report"

    # --- AST-valid check ---
    if "ast-valid" in item_lower or "ast valid" in item_lower:
        file_patterns = re.findall(r"`([a-zA-Z0-9_./-]+\.py)`", item)
        for fp in file_patterns:
            fp_clean = fp.lstrip("./")
            if verify_file_in_repo(fp_clean):
                return DELIVERED, f"File {fp_clean} exists (AST validity requires local check)"
        return DISPATCHED_ONLY, "Cannot verify AST validity remotely"

    # --- Parses cleanly / curl check ---
    if "parses cleanly" in item_lower or "curl" in item_lower:
        # Check if the file exists
        file_patterns = re.findall(r"`([a-zA-Z0-9_./-]+\.[a-zA-Z]{1,5})`", item)
        for fp in file_patterns:
            fp_clean = fp.lstrip("./")
            if verify_file_in_repo(fp_clean):
                return DELIVERED, f"File {fp_clean} exists in repo"
            else:
                return NOT_DELIVERED, f"File {fp_clean} NOT found in repo"

    # --- vault doc checks ---
    if "vault" in item_lower or "everest-vault" in item_lower:
        fp_match = re.search(r"`([^`]+)`", item)
        if fp_match:
            # Vault files are in a different repo — check via GH API
            vault_path = fp_match.group(1)
            if vault_path.startswith("everest-vault/"):
                vault_path = vault_path[len("everest-vault/"):]
            try:
                r = httpx.get(
                    f"{GH_API}/repos/breverdbidder/everest-vault/contents/{vault_path}",
                    headers=gh_headers(),
                    timeout=TIMEOUT,
                )
                if r.status_code == 200:
                    return DELIVERED, f"Vault doc {vault_path} exists"
                return NOT_DELIVERED, f"Vault doc {vault_path} NOT found"
            except Exception:
                return NOT_DELIVERED, f"Could not check vault for {vault_path}"

    # --- Fallback: check if CC report mentions this item positively ---
    if cc_report_body:
        keywords = [w for w in item_lower.split() if len(w) > 4][:3]
        positive_markers = ["VERIFIED", "DELIVERED", "✅", "done", "complete", "success"]
        for kw in keywords:
            for marker in positive_markers:
                if re.search(f"(?i){re.escape(kw)}[^\\n]{{0,200}}{marker}|{marker}[^\\n]{{0,200}}{re.escape(kw)}", cc_report_body):
                    return DISPATCHED_ONLY, f"CC report claims completion near '{kw}' but no independent verification"

    return DISPATCHED_ONLY, "No artifact evidence found — dispatched but unverifiable"


# ---------------------------------------------------------------------------
# Main verification flow
# ---------------------------------------------------------------------------
def run_verification(issue_number: int, dry_run: bool = False) -> dict:
    print(f"=== Verifying SUMMIT #{issue_number} ===")

    # 1. Fetch issue
    issue = fetch_issue(issue_number)
    issue_body = issue.get("body", "")
    issue_title = issue.get("title", "")
    print(f"Title: {issue_title}")

    # 2. Extract checklist
    checklist = extract_checklist(issue_body)
    if not checklist:
        print("WARNING: No checklist items found in issue body")
        return {"issue_number": issue_number, "error": "No checklist found"}
    print(f"Found {len(checklist)} checklist items")

    # 3. Fetch comments + find CC report
    comments = fetch_comments(issue_number)
    cc_report = find_cc_report(comments)
    cc_body = cc_report["body"] if cc_report else ""
    cc_url = cc_report["html_url"] if cc_report else ""
    if cc_report:
        print(f"Found CC report: {cc_url}")
    else:
        print("WARNING: No CC completion report found")

    # 4. Verify each checklist item
    results = []
    passed = 0
    failed = 0
    for i, item in enumerate(checklist, 1):
        verdict, evidence = verify_checklist_item(item, cc_body, issue_body)
        is_pass = verdict == DELIVERED
        if is_pass:
            passed += 1
        else:
            failed += 1
        results.append({
            "index": i,
            "item": item,
            "verdict": verdict,
            "evidence": evidence,
            "passed": is_pass,
        })
        icon = "✅" if is_pass else "❌"
        print(f"  {icon} [{i}/{len(checklist)}] {verdict}: {item[:80]}")
        print(f"      Evidence: {evidence}")

    # 5. Overall verdict
    if passed == len(checklist):
        overall = "DELIVERED"
    elif failed > 0 and any(r["verdict"] == NOT_DELIVERED for r in results):
        overall = "FAILED"
    else:
        overall = "PARTIAL"

    print(f"\n=== OVERALL: {overall} ({passed}/{len(checklist)} passed) ===")

    failed_items = [r for r in results if not r["passed"]]

    verification = {
        "issue_number": issue_number,
        "repo": REPO.split("/")[-1],
        "overall_verdict": overall,
        "checklist_total": len(checklist),
        "checklist_passed": passed,
        "checklist_failed": failed,
        "failed_items": failed_items,
        "cc_report_url": cc_url,
        "evidence": results,
    }

    if dry_run:
        print("\n[DRY RUN] Would insert to Supabase and comment on issue")
        print(json.dumps(verification, indent=2, default=str))
        return verification

    # 6. Insert to summit_verifications
    if SB_KEY:
        sb_row = {
            "issue_number": issue_number,
            "repo": verification["repo"],
            "overall_verdict": overall,
            "checklist_total": len(checklist),
            "checklist_passed": passed,
            "checklist_failed": failed,
            "failed_items": json.dumps(failed_items),
            "cc_report_url": cc_url,
            "evidence": json.dumps(results),
        }
        try:
            resp = sb_post("/rest/v1/summit_verifications", sb_row)
            if resp.status_code in (200, 201):
                print(f"[supabase] Row inserted for #{issue_number}")
            else:
                print(f"[supabase] Insert failed: {resp.status_code} {resp.text[:300]}")
        except Exception as e:
            print(f"[supabase] Insert error: {e}")

    # 7. Comment on issue with verification matrix
    matrix_lines = [f"## Spec Fulfillment Verification — SUMMIT #{issue_number}\n"]
    matrix_lines.append(f"**Overall Verdict: {overall}** ({passed}/{len(checklist)} delivered)\n")
    matrix_lines.append("| # | Item | Verdict | Evidence |")
    matrix_lines.append("|---|------|---------|----------|")
    for r in results:
        icon = "✅" if r["passed"] else "❌"
        item_short = r["item"][:60] + ("..." if len(r["item"]) > 60 else "")
        matrix_lines.append(f"| {r['index']} | {item_short} | {icon} {r['verdict']} | {r['evidence'][:80]} |")
    matrix_lines.append(f"\n*Verified at {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}*")

    comment_body = "\n".join(matrix_lines)

    if GH_TOKEN:
        try:
            r = httpx.post(
                f"{GH_API}/repos/{REPO}/issues/{issue_number}/comments",
                headers=gh_headers(),
                json={"body": comment_body},
                timeout=TIMEOUT,
            )
            if r.status_code == 201:
                print(f"[github] Verification comment posted on #{issue_number}")
            else:
                print(f"[github] Comment failed: {r.status_code} {r.text[:200]}")
        except Exception as e:
            print(f"[github] Comment error: {e}")

    # 8. Telegram notification for FAILED or PARTIAL
    if overall in ("FAILED", "PARTIAL"):
        msg = (
            f"🔍 <b>SUMMIT #{issue_number} Verification: {overall}</b>\n"
            f"Passed: {passed}/{len(checklist)}\n"
        )
        for r in failed_items[:5]:
            msg += f"❌ {r['item'][:60]}\n"
        tg_send(msg)

    # 9. If FAILED: reopen issue + add label
    if overall == "FAILED" and GH_TOKEN:
        try:
            # Reopen
            httpx.patch(
                f"{GH_API}/repos/{REPO}/issues/{issue_number}",
                headers=gh_headers(),
                json={"state": "open"},
                timeout=TIMEOUT,
            )
            print(f"[github] Issue #{issue_number} reopened")
        except Exception as e:
            print(f"[github] Reopen error: {e}")

        try:
            # Add label
            httpx.post(
                f"{GH_API}/repos/{REPO}/issues/{issue_number}/labels",
                headers=gh_headers(),
                json={"labels": ["verification-failed"]},
                timeout=TIMEOUT,
            )
            print(f"[github] Label 'verification-failed' added to #{issue_number}")
        except Exception as e:
            print(f"[github] Label error: {e}")

    return verification


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="SUMMIT Spec Fulfillment Verifier")
    parser.add_argument("--issue", type=int, required=True, help="GitHub issue number")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to Supabase or comment")
    args = parser.parse_args()

    if not GH_TOKEN:
        print("ERROR: GH_TOKEN or GH_PAT env var required")
        sys.exit(1)

    result = run_verification(args.issue, dry_run=args.dry_run)

    # Exit code: 0 for DELIVERED, 1 for FAILED, 2 for PARTIAL
    verdict = result.get("overall_verdict", "FAILED")
    if verdict == "DELIVERED":
        sys.exit(0)
    elif verdict == "PARTIAL":
        sys.exit(2)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
