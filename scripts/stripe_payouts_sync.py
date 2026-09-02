#!/usr/bin/env python3
"""Sync Stripe payouts + balance_transactions into stripe.payouts / stripe.balance_transactions.

@stripe/sync-engine (installed #19717) does not sync these objects (Sigma-only in that
library). This script fills the gap with the restricted key's Payouts Read / Balance
Transaction Sources Read scopes (added 2026-09-02, issue #19738).

Reads the Stripe secret key from vault via the sanctioned public.vault_secret() RPC --
never from a raw env var, never printed. Writes via the Supabase Management API
(database/query) since PostgREST only exposes public/graphql_public/pascal/
geo_tracker/finance/winnerdata -- not `stripe` -- matching the fallback path already
established for this schema in #19717.

Usage: python3 scripts/stripe_payouts_sync.py [--since 1767225600]
"""
import os, sys, json, argparse, httpx

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SRK = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUPABASE_PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
STRIPE_API = "https://api.stripe.com/v1"

PAYOUT_FIELDS = [
    "id", "object", "amount", "application_fee", "application_fee_amount",
    "arrival_date", "automatic", "balance_transaction", "created", "currency",
    "description", "destination", "failure_balance_transaction", "failure_code",
    "failure_message", "livemode", "metadata", "method", "original_payout",
    "payout_method", "reconciliation_status", "reversed_by", "source_type",
    "statement_descriptor", "status", "trace_id", "type",
]
BT_FIELDS = [
    "id", "object", "amount", "available_on", "balance_type", "created", "currency",
    "description", "exchange_rate", "fee", "fee_details", "net", "reporting_category",
    "source", "status", "type",
]

COL_TYPES = {
    "id": "text", "object": "text", "amount": "bigint", "application_fee": "text",
    "application_fee_amount": "bigint", "arrival_date": "bigint", "automatic": "boolean",
    "balance_transaction": "text", "created": "bigint", "currency": "text",
    "description": "text", "destination": "text", "failure_balance_transaction": "text",
    "failure_code": "text", "failure_message": "text", "livemode": "boolean",
    "metadata": "jsonb", "method": "text", "original_payout": "text",
    "payout_method": "text", "reconciliation_status": "text", "reversed_by": "text",
    "source_type": "text", "statement_descriptor": "text", "status": "text",
    "trace_id": "jsonb", "type": "text",
    "available_on": "bigint", "balance_type": "text", "exchange_rate": "numeric",
    "fee": "bigint", "fee_details": "jsonb", "net": "bigint",
    "reporting_category": "text", "source": "text", "payout_id": "text",
    "_account_id": "text",
}


def vault_secret(name):
    r = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/vault_secret",
        headers={"apikey": SRK, "Authorization": f"Bearer {SRK}", "Content-Type": "application/json"},
        json={"p_name": name}, timeout=30,
    )
    r.raise_for_status()
    return r.json()


def stripe_get(key, path, params):
    out = []
    starting_after = None
    while True:
        p = dict(params)
        if starting_after:
            p["starting_after"] = starting_after
        r = httpx.get(f"{STRIPE_API}/{path}", headers={"Authorization": f"Bearer {key}"}, params=p, timeout=30)
        r.raise_for_status()
        body = r.json()
        out.extend(body["data"])
        if not body.get("has_more"):
            break
        starting_after = body["data"][-1]["id"]
    return out


def mgmt_query(query):
    r = httpx.post(
        f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/database/query",
        headers={"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"},
        json={"query": query}, timeout=120,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"mgmt query failed: {r.status_code} {r.text[:800]}")
    return r.json()


def upsert_schema(table, rows, account_id, fields):
    """Upsert into stripe.<table> via jsonb_to_recordset over the Management API --
    PostgREST doesn't expose the stripe schema, so this mirrors the fallback path
    already established for it in #19717."""
    if not rows:
        return
    cols = list(fields) + (["payout_id"] if table == "balance_transactions" else []) + ["_account_id"]
    for row in rows:
        row["_account_id"] = account_id
    recordset_def = ", ".join(f'"{c}" {COL_TYPES[c]}' for c in cols)
    col_list = ", ".join(f'"{c}"' for c in cols)
    update_list = ", ".join(f'"{c}"=excluded."{c}"' for c in cols if c != "id")
    payload = json.dumps(rows).replace("'", "''")
    query = f"""
    insert into stripe.{table} ({col_list})
    select {col_list} from jsonb_to_recordset('{payload}'::jsonb) as x({recordset_def})
    on conflict (id) do update set {update_list}, "_updated_at" = now(), "_last_synced_at" = now();
    """
    mgmt_query(query)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int, default=1767225600)  # 2026-01-01T00:00:00Z
    args = ap.parse_args()

    key = vault_secret("stripe_secret_key")
    account_id = "acct_1LPHtNKaSTwZgYdf"

    payouts = stripe_get(key, "payouts", {"created[gte]": args.since, "limit": 100})
    payout_rows = [{k: p.get(k) for k in PAYOUT_FIELDS} for p in payouts]
    upsert_schema("payouts", payout_rows, account_id, PAYOUT_FIELDS)
    print(f"payouts: fetched {len(payouts)} from API (created >= {args.since})")

    # Balance transactions: walk each payout's sources (Balance Transaction Sources Read
    # scope) so every row carries a payout_id, then also do a general created>=since sweep
    # to catch any not-yet-paid-out balance transactions.
    bt_by_id = {}
    for p in payouts:
        sources = stripe_get(key, "balance_transactions", {"payout": p["id"], "limit": 100})
        for s in sources:
            row = {k: s.get(k) for k in BT_FIELDS}
            row["payout_id"] = p["id"]
            bt_by_id[s["id"]] = row
    from_payout_walk = len(bt_by_id)

    general = stripe_get(key, "balance_transactions", {"created[gte]": args.since, "limit": 100})
    new_from_general = 0
    for s in general:
        if s["id"] not in bt_by_id:
            row = {k: s.get(k) for k in BT_FIELDS}
            row["payout_id"] = None
            bt_by_id[s["id"]] = row
            new_from_general += 1

    bt_rows = list(bt_by_id.values())
    upsert_schema("balance_transactions", bt_rows, account_id, BT_FIELDS)
    print(f"balance_transactions: {from_payout_walk} from per-payout source walk (payout_id set), "
          f"{len(general)} from general created>=since sweep ({new_from_general} not already covered "
          f"by the payout walk -- these are in-transit, payout_id left null), "
          f"{len(bt_rows)} total upserted")


if __name__ == "__main__":
    main()
