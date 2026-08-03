#!/usr/bin/env python3
"""Weekly control report: cc_session_cost, agent_ops_log, gold_standard_certifications
summarized over the trailing 7 days and emailed via Resend to vault.alerts_to_email.

Vault secrets (resend_api_key, alerts_from_email, alerts_to_email) are read via the
vault_secret() RPC — EXECUTE on that function is restricted to postgres+service_role,
so this script must run with SUPABASE_SERVICE_ROLE_KEY, never an anon key.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import httpx

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}


def rest_get(path):
    r = httpx.get(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def vault_secret(name):
    r = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/vault_secret",
        headers=HEADERS,
        json={"p_name": name},
        timeout=30,
    )
    if not r.is_success:
        return None
    v = r.json()
    return v if isinstance(v, str) else None


def cc_session_cost_summary(since_iso):
    rows = rest_get(
        f"cc_session_cost?started_at=gte.{since_iso}&select=cost_usd,dod_met"
    )
    n = len(rows)
    total_cost = sum(float(r["cost_usd"] or 0) for r in rows)
    dod_known = [r for r in rows if r["dod_met"] is not None]
    dod_pass_rate = (
        100.0 * sum(1 for r in dod_known if r["dod_met"]) / len(dod_known)
        if dod_known
        else None
    )
    return n, total_cost, dod_pass_rate


def agent_ops_log_summary(since_iso):
    rows = rest_get(f"agent_ops_log?created_at=gte.{since_iso}&select=status")
    counts = {"VERIFIED": 0, "BLOCKED": 0, "PARTIAL": 0}
    for r in rows:
        status = (r.get("status") or "").upper()
        if status in counts:
            counts[status] += 1
    return counts


def gold_standard_certified_count():
    rows = rest_get("gold_standard_certifications?certified=eq.true&select=county_slug")
    return len(rows)


def build_report(n_sessions, total_cost, dod_pass_rate, ops_counts, certified_count):
    dod_str = f"{dod_pass_rate:.1f}%" if dod_pass_rate is not None else "n/a (no dod_met data)"
    lines = [
        "BidDeed.AI Weekly Control Report",
        f"Window: trailing 7 days as of {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "-- CC Sessions --",
        f"Sessions: {n_sessions}",
        f"Total cost: ${total_cost:.2f}",
        f"DoD pass rate: {dod_str}",
        "",
        "-- Agent Ops Log --",
        f"VERIFIED: {ops_counts['VERIFIED']}",
        f"BLOCKED:  {ops_counts['BLOCKED']}",
        f"PARTIAL:  {ops_counts['PARTIAL']}",
        "",
        "-- Gold Standard Campaign --",
        f"Certified counties: {certified_count}",
    ]
    return "\n".join(lines)


def send_email(body_text):
    resend_key = vault_secret("resend_api_key")
    from_addr = vault_secret("alerts_from_email")
    to_addr = vault_secret("alerts_to_email")
    if not resend_key or not from_addr or not to_addr:
        print("BLOCKED: resend_api_key/alerts_from_email/alerts_to_email not in vault", file=sys.stderr)
        return False, "vault secrets missing"

    r = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
        json={
            "from": from_addr,
            "to": [to_addr],
            "subject": "BidDeed.AI Weekly Control Report",
            "text": body_text,
        },
        timeout=30,
    )
    if not r.is_success:
        print(f"BLOCKED: resend send failed {r.status_code}: {r.text[:500]}", file=sys.stderr)
        return False, f"resend {r.status_code}"
    return True, None


def log_ops_result(status, evidence):
    httpx.post(
        f"{SUPABASE_URL}/rest/v1/agent_ops_log",
        headers={**HEADERS, "Prefer": "return=minimal"},
        json={
            "dispatch_id": "59f3574e-86d9-41f4-8ba9-2bd2a44eaade",
            "task": "weekly-control-report",
            "status": status,
            "severity": "info" if status == "VERIFIED" else "blocker",
            "evidence": evidence[:2000],
        },
        timeout=30,
    )


def main():
    # 'Z' suffix, not '+00:00' — an unescaped '+' in a query string is decoded
    # as a space by PostgREST's URL parser and breaks the gte. filter.
    since_iso = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    n_sessions, total_cost, dod_pass_rate = cc_session_cost_summary(since_iso)
    ops_counts = agent_ops_log_summary(since_iso)
    certified_count = gold_standard_certified_count()

    report = build_report(n_sessions, total_cost, dod_pass_rate, ops_counts, certified_count)
    print(report)

    sent, err = send_email(report)
    if sent:
        log_ops_result("VERIFIED", f"report emailed: sessions={n_sessions} cost=${total_cost:.2f} certified={certified_count}")
    else:
        log_ops_result("BLOCKED", f"report generated but email failed: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
