#!/usr/bin/env python3
"""
LMS Credential Reset — helper for .github/workflows/lms-credential-reset.yml

Generates a fresh LMS_AUTH_USER/LMS_AUTH_PASS pair, rewrites the GitHub
Actions repo secrets to match (so the next deploy-winnerdata-lms.yml run
doesn't revert the rotation), and sends the reset email via Resend.
Values are never printed — only masked (::add-mask::) and handed off via
GITHUB_ENV/GITHUB_OUTPUT.

Usage:
  python3 scripts/lms_credential_reset.py generate
  python3 scripts/lms_credential_reset.py rotate-gh-secret
  python3 scripts/lms_credential_reset.py send-email

Env:
  SUPABASE_ACCESS_TOKEN   (generate/rotate-gh-secret, send-email — vault reads)
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (send-email)
  RESEND_API_KEY          (send-email)
  NEW_LMS_AUTH_USER, NEW_LMS_AUTH_PASS (rotate-gh-secret, send-email)
  GITHUB_ENV, GITHUB_OUTPUT              (set by Actions runner)
"""
import base64
import json
import os
import secrets
import string
import subprocess
import sys
import urllib.error
import urllib.request

REPO = "breverdbidder/cli-anything-biddeed"
PROJECT_ID = "mocerqjnksmhcjzxrewo"


def mask(value):
    print(f"::add-mask::{value}", flush=True)


def vault_fetch_via_management_api(name):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    payload = json.dumps({"query": f"SELECT vault_secret('{name}') AS v;"}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_ID}/database/query",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "cli-anything-biddeed-cc/1.0",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    return (data[0].get("v") or "") if (isinstance(data, list) and data) else ""


def vault_fetch_via_postgrest(name):
    req = urllib.request.Request(
        f"{os.environ['SUPABASE_URL']}/rest/v1/rpc/get_vault_secret_mcp",
        data=json.dumps({"p_name": name}).encode(),
        headers={
            "apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
            "Authorization": f"Bearer {os.environ['SUPABASE_SERVICE_ROLE_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def cmd_generate():
    new_user = f"ariel{secrets.randbelow(9000) + 1000}"
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    symbols = "!@#$%^&*()-_=+"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(28))
        if (
            any(c.islower() for c in pw)
            and any(c.isupper() for c in pw)
            and any(c.isdigit() for c in pw)
            and any(c in symbols for c in pw)
        ):
            new_pass = pw
            break

    mask(new_user)
    mask(new_pass)
    with open(os.environ["GITHUB_ENV"], "a") as f:
        f.write(f"NEW_LMS_AUTH_USER={new_user}\n")
        f.write(f"NEW_LMS_AUTH_PASS={new_pass}\n")
    print("Generated new credential pair (28-char password, values masked).")


def cmd_rotate_gh_secret():
    import requests
    from nacl import encoding, public

    new_user = os.environ["NEW_LMS_AUTH_USER"]
    new_pass = os.environ["NEW_LMS_AUTH_PASS"]

    gh_pat = vault_fetch_via_management_api("everest_gh_pat")
    if not gh_pat:
        print("::error::everest_gh_pat not returned from vault")
        sys.exit(1)
    mask(gh_pat)

    headers = {
        "Authorization": f"token {gh_pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    r = requests.get(f"https://api.github.com/repos/{REPO}/actions/secrets/public-key", headers=headers)
    if r.status_code != 200:
        print(f"::error::public-key fetch failed {r.status_code}: {r.text[:300]}")
        sys.exit(1)
    pk = r.json()
    key = public.PublicKey(pk["key"].encode("utf-8"), encoding.Base64Encoder())

    for name, value in [("LMS_AUTH_USER", new_user), ("LMS_AUTH_PASS", new_pass)]:
        encrypted = base64.b64encode(public.SealedBox(key).encrypt(value.encode("utf-8"))).decode("utf-8")
        r2 = requests.put(
            f"https://api.github.com/repos/{REPO}/actions/secrets/{name}",
            headers=headers,
            json={"encrypted_value": encrypted, "key_id": pk["key_id"]},
        )
        if r2.status_code not in (201, 204):
            print(f"::error::FAIL({r2.status_code}) updating {name}: {r2.text[:300]}")
            sys.exit(1)
        print(f"OK: {name} GH secret updated")


def cmd_send_email():
    new_user = os.environ["NEW_LMS_AUTH_USER"]
    new_pass = os.environ["NEW_LMS_AUTH_PASS"]

    try:
        from_addr = vault_fetch_via_postgrest("resend_from_address") or "BidDeed.AI Reports <reports@biddeed.ai>"
    except Exception as e:
        print(f"::warning::could not read resend_from_address from vault, using default: {e}")
        from_addr = "BidDeed.AI Reports <reports@biddeed.ai>"

    html = (
        "<p>Your Winner Data LMS admin login was just reset.</p>"
        f"<p><strong>Username:</strong> {new_user}<br>"
        f"<strong>Password:</strong> {new_pass}</p>"
        "<p>If you forget this again, go to GitHub Actions &rarr; "
        '"LMS Credential Reset (self-service forgot-password)" &rarr; Run workflow, '
        "and check this inbox.</p>"
    )
    payload = json.dumps({
        "from": from_addr,
        "to": ["everestcapital8@gmail.com"],
        "subject": "Winner Data LMS credentials reset",
        "html": html,
    })

    # curl, not urllib -- Resend sits behind Cloudflare bot protection that
    # 403s (error 1010) on urllib's TLS/HTTP fingerprint. Confirmed live
    # 2026-09-01: identical payload+key, curl succeeds where urllib and even
    # a curl request with urllib's User-Agent spoofed both get blocked, so
    # this is a TLS-fingerprint block, not a header check. Same workaround
    # already documented in send-s5-report-email.yml.
    result = subprocess.run(
        [
            "curl", "-sS", "-o", "/tmp/resend_resp.json", "-w", "%{http_code}",
            "-X", "POST", "https://api.resend.com/emails",
            "-H", f"Authorization: Bearer {os.environ['RESEND_API_KEY']}",
            "-H", "Content-Type: application/json",
            "--data-binary", "@-",
        ],
        input=payload,
        text=True,
        capture_output=True,
    )
    http_code = result.stdout.strip()
    if not http_code.startswith("2"):
        print(f"::error::Resend send failed HTTP {http_code}")
        sys.exit(1)

    with open("/tmp/resend_resp.json") as f:
        resp_body = json.load(f)
    os.remove("/tmp/resend_resp.json")
    resend_id = resp_body.get("id", "")
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"resend_id={resend_id}\n")
    print(f"Email sent to Ariel (everestcapital8@gmail.com), Resend id={resend_id}")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    {
        "generate": cmd_generate,
        "rotate-gh-secret": cmd_rotate_gh_secret,
        "send-email": cmd_send_email,
    }.get(action, lambda: (_ for _ in ()).throw(SystemExit(f"unknown action: {action}")))()
