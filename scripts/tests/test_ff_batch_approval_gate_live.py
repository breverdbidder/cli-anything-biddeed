#!/usr/bin/env python3
"""Negative-test proof for the unforgeable FF batch approval gate (issue
#19745). Hits the LIVE Supabase project (Management API + PostgREST) -- there
is no meaningful way to prove "a forged approval is rejected" against a
mock, since the whole point is that Postgres itself (RLS + a BEFORE INSERT
trigger + a SECURITY DEFINER RPC's own auth.uid() check) rejects it, not any
application code.

Proves the exact 2026-09-01 incident vector (a service-role call setting
approval without a human click) is now structurally impossible:
  1. Calling public.ff_batch_approve_authenticated() with the SERVICE_ROLE
     key (no real user JWT) must fail -- either at the grant layer
     (EXECUTE was revoked from service_role) or, if ever re-granted, inside
     the function's own auth.uid() IS NULL check.
  2. A raw INSERT into winnerdata.ff_batch_approvals issued with no
     PostgREST JWT context (auth.uid() is null) must be rejected by the
     BEFORE INSERT trigger -- this is the real, unconditional backstop; it
     fires regardless of RLS bypass or who owns the table.
  3. After both forgery attempts, winnerdata_ff_send_approved.py's
     get_verified_approval() must still return None for the test batch --
     proving the send path has nothing to trust and would hard-block.

Uses a synthetic, far-future batch_date (never a real production row) and
batch_kind='nine_case_portfolio' specifically because
scripts/winnerdata_ff_send_approved.py only ever queries
batch_kind='seller_digest' -- this test can never accidentally cause a real
send regardless of what it does to winnerdata.ff_batches. The synthetic row
is deleted at the end (cascades to any ff_batch_approvals row via FK).

Run: SUPABASE_ACCESS_TOKEN=... SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=...
  python3 scripts/tests/test_ff_batch_approval_gate_live.py
Requires live network + those three env vars -- not part of the mocked
scripts/tests/ suite ci.yml runs, by design (same reasoning
docs/spec/19659.md gives for why its own verification queried the live DB
directly rather than a fixture).
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from winnerdata_ff_digest_lib import get_verified_approval, run_sql, sql_str  # noqa: E402

TEST_BATCH_DATE = "2099-12-31"
TEST_BATCH_KIND = "nine_case_portfolio"  # never touched by the seller_digest sender -- see docstring
TEST_LEAD_COUNT = 0


def rest_call(path, api_key, bearer, body):
    req = urllib.request.Request(
        f"{os.environ['SUPABASE_URL']}{path}",
        data=json.dumps(body).encode(),
        headers={
            "apikey": api_key,
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
            "User-Agent": "ff-batch-approval-gate-negative-test/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def setup_batch():
    run_sql(f"""
        insert into winnerdata.ff_batches (batch_date, status, batch_kind, lead_count)
        values ({sql_str(TEST_BATCH_DATE)}, 'pending_approval', {sql_str(TEST_BATCH_KIND)}, {TEST_LEAD_COUNT})
        on conflict (batch_date) do update set status = 'pending_approval', approved_at = null,
          approved_by = null, approval_provenance = null;
    """)


def teardown_batch():
    run_sql(f"delete from winnerdata.ff_batches where batch_date = {sql_str(TEST_BATCH_DATE)};")


def test_service_role_rpc_call_is_rejected():
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    status, body = rest_call(
        "/rest/v1/rpc/ff_batch_approve_authenticated",
        service_key, service_key,
        {"p_batch_date": TEST_BATCH_DATE},
    )
    # Either outcome is an acceptable REJECTION: 42501 permission-denied at
    # the grant layer (EXECUTE revoked from service_role), or a 200 with
    # ok=false/reason=not_authenticated if EXECUTE were ever re-granted --
    # what must NEVER happen is ok=true.
    approved = isinstance(body, dict) and body.get("ok") is True
    assert not approved, f"CRITICAL: service-role call approved a batch! status={status} body={body}"
    print(f"PASS: service-role RPC call rejected (status={status}, body={body})")


def test_direct_insert_with_no_jwt_context_is_rejected():
    # run_sql() goes through the Supabase Management API, which executes as
    # postgres with NO request.jwt.claims set -- i.e. exactly the
    # "auth.uid() is null" scenario the trigger exists to reject, and it is
    # not gated by RLS/grants at all (Management API runs as a superuser),
    # so this is the strongest possible proof the trigger itself is the
    # backstop, not just a grant. run_sql() retries transient errors up to
    # MGMT_API_RETRIES times before raising -- a rejected INSERT is not
    # transient (same error every attempt), so this eats that retry/backoff
    # cost every run; acceptable for a test invoked manually/in CI, not on
    # a hot path.
    try:
        run_sql(f"""
            insert into winnerdata.ff_batch_approvals
              (batch_date, batch_kind, lead_count_snapshot, snapshot_hash, approved_by_user_id, approved_by_email)
            values
              ({sql_str(TEST_BATCH_DATE)}, {sql_str(TEST_BATCH_KIND)}, {TEST_LEAD_COUNT}, 'forged-hash',
               '00000000-0000-0000-0000-000000000000', 'forged@evil.example');
        """)
    except (RuntimeError, urllib.error.HTTPError) as e:
        msg = str(e) if isinstance(e, RuntimeError) else e.read().decode(errors="replace")
        assert "auth.uid() is null" in msg or "not_authenticated" in msg or "ff_batch_approvals insert rejected" in msg, \
            f"insert failed but not for the expected reason: {msg}"
        print(f"PASS: direct forged INSERT rejected by trigger: {msg.strip()[:300]}")
        return
    raise AssertionError("CRITICAL: forged INSERT into ff_batch_approvals with no auth.uid() succeeded!")


def test_send_path_has_no_verified_approval_to_trust():
    approval = get_verified_approval(TEST_BATCH_DATE, TEST_BATCH_KIND, TEST_LEAD_COUNT)
    assert approval is None, f"CRITICAL: get_verified_approval() found something for a never-approved test batch: {approval}"
    print("PASS: get_verified_approval() correctly returns None -- send path has nothing to trust")


def main():
    setup_batch()
    failures = []
    for test in (
        test_service_role_rpc_call_is_rejected,
        test_direct_insert_with_no_jwt_context_is_rejected,
        test_send_path_has_no_verified_approval_to_trust,
    ):
        try:
            test()
        except Exception as e:  # noqa: BLE001 -- must not skip teardown_batch() below on any failure
            failures.append(f"{test.__name__}: {e}")
            print(f"FAIL: {test.__name__}: {e}")
    teardown_batch()

    if failures:
        print(f"\n{len(failures)} FAILURE(S) -- approval gate is NOT holding.")
        sys.exit(1)
    print("\nALL PASS -- forged/service-role approval attempts are rejected; send path trusts nothing unverified.")


if __name__ == "__main__":
    main()
