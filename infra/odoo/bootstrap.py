#!/usr/bin/env python3
"""Post-init Odoo bootstrap for Deed Projects (issue #20008).

Run once after infra/odoo/init_db.sh has created the database. Uses only the
stdlib (urllib) against Odoo's /jsonrpc endpoint — no odoorpc/xmlrpc dep needed.

What it does:
  1. Logs in as the default admin user (login "admin", password from
     ODOO_ADMIN_BOOTSTRAP_PASSWORD — the password set on the admin user
     immediately after db init; Odoo's own default is "admin" on a fresh
     --without-demo install, so this MUST be rotated as step 1).
  2. Rotates the admin password to ODOO_ADMIN_PASSWORD.
  3. Creates one technical/worker user (login ODOO_WORKER_LOGIN) with only
     the groups it needs: Project (user), Invoicing (Billing, i.e. the
     Community-available account app — see docs/infra/ODOO.md for the
     Accounting-vs-Invoicing licensing note), Purchase (user). Nothing else —
     no Settings/group_system, no Documents admin.
  4. Logs in AS that technical user and calls the deed_budget addon's
     deed_generate_own_api_key() to mint its scoped API key (see
     infra/odoo/addons/deed_budget/models/res_users.py for why this can't be
     the private res.users.apikeys._generate() directly).
  5. Prints the API key ONCE to stdout for the operator to store in the vault
     (ODOO_API_KEY secret) — Odoo does not store it in retrievable form, and
     this script does not persist it anywhere.

Every value this script would need to print is either non-secret (uid, login)
or the one-time API key that Odoo itself only ever discloses once — never the
Odoo master/admin password.
"""
import json
import os
import sys
import urllib.request

ODOO_URL = os.environ["ODOO_URL"].rstrip("/")
ODOO_DB = os.environ["ODOO_DB_NAME"]
ADMIN_BOOTSTRAP_PASSWORD = os.environ.get("ODOO_ADMIN_BOOTSTRAP_PASSWORD", "admin")
ADMIN_PASSWORD = os.environ["ODOO_ADMIN_PASSWORD"]
WORKER_LOGIN = os.environ.get("ODOO_WORKER_LOGIN", "worker@deedprojects.internal")
WORKER_BOOTSTRAP_PASSWORD = os.environ["ODOO_WORKER_BOOTSTRAP_PASSWORD"]


def rpc(service, method, args):
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "call",
        "params": {"service": service, "method": method, "args": args},
        "id": 1,
    }).encode()
    req = urllib.request.Request(
        f"{ODOO_URL}/jsonrpc", data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    if "error" in body:
        raise RuntimeError(f"{service}.{method} failed: {body['error']}")
    return body["result"]


def authenticate(login, password):
    uid = rpc("common", "authenticate", [ODOO_DB, login, password, {}])
    if not uid:
        raise RuntimeError(f"authenticate failed for login={login}")
    return uid


def execute(uid, password, model, method, args, kwargs=None):
    return rpc("object", "execute_kw", [ODOO_DB, uid, password, model, method, args, kwargs or {}])


def main():
    print("[1/5] authenticating as admin (bootstrap password)")
    admin_uid = authenticate("admin", ADMIN_BOOTSTRAP_PASSWORD)

    print("[2/5] rotating admin password")
    execute(admin_uid, ADMIN_BOOTSTRAP_PASSWORD, "res.users", "write", [[admin_uid], {"password": ADMIN_PASSWORD}])
    admin_uid = authenticate("admin", ADMIN_PASSWORD)

    print(f"[3/5] creating technical user {WORKER_LOGIN}")
    group_ids = execute(
        admin_uid, ADMIN_PASSWORD, "ir.model.data", "search_read",
        [[
            ("module", "=", "project"), ("name", "=", "group_project_user"),
        ], ["res_id"]],
    )
    # Resolve group xmlids -> ids for project/account/purchase "user" level access.
    xmlids = [
        ("project", "group_project_user"),
        ("account", "group_account_invoice"),
        ("purchase", "group_purchase_user"),
    ]
    group_id_list = []
    for module, name in xmlids:
        rows = execute(
            admin_uid, ADMIN_PASSWORD, "ir.model.data", "search_read",
            [[("module", "=", module), ("name", "=", name)], ["res_id"]],
        )
        if rows:
            group_id_list.append(rows[0]["res_id"])
        else:
            print(f"  WARNING: group {module}.{name} not found — skipping (verify module installed)")

    existing = execute(admin_uid, ADMIN_PASSWORD, "res.users", "search", [[("login", "=", WORKER_LOGIN)]])
    if existing:
        worker_id = existing[0]
        execute(admin_uid, ADMIN_PASSWORD, "res.users", "write", [
            [worker_id], {"password": WORKER_BOOTSTRAP_PASSWORD, "groups_id": [(6, 0, group_id_list)]}
        ])
    else:
        worker_id = execute(admin_uid, ADMIN_PASSWORD, "res.users", "create", [{
            "name": "Deed Projects Worker",
            "login": WORKER_LOGIN,
            "password": WORKER_BOOTSTRAP_PASSWORD,
            "groups_id": [(6, 0, group_id_list)],
        }])
    print(f"  worker res.users id={worker_id}")

    print("[4/5] authenticating as worker to mint its own scoped API key")
    worker_uid = authenticate(WORKER_LOGIN, WORKER_BOOTSTRAP_PASSWORD)
    api_key = execute(
        worker_uid, WORKER_BOOTSTRAP_PASSWORD,
        "res.users", "deed_generate_own_api_key", [[worker_uid], "rpc", "deed-projects-worker"],
    )

    print("[5/5] done")
    print("")
    print("Store this as the ODOO_API_KEY secret NOW — Odoo will never show it again:")
    print(api_key)
    print("")
    print(f"ODOO_LOGIN={WORKER_LOGIN}")
    print(f"ODOO_DB={ODOO_DB}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 — top-level script, want a clean one-line failure
        print(f"bootstrap FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
