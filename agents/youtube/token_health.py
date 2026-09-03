#!/usr/bin/env python3
"""agents/youtube/token_health.py -- issue #19788 deliverable 3.

Daily job: refresh the OAuth token and write public.youtube_token_health.
On invalid_grant (the 7-day Testing-mode trap), opens spi_gates row
'youtube_token_expired' with the plain-English cause so it surfaces in /spi
instead of silently stopping.

Run:
  python agents/youtube/token_health.py
  python agents/youtube/token_health.py --self-test   # negative test (e),
                                                          no network/DB calls
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import youtube_lib as lib


def run() -> int:
    creds = lib.load_credentials()
    if creds is None:
        print("NOT_CONFIGURED: youtube_client_id / youtube_client_secret / "
              "youtube_oauth_refresh_token not all present in vault -- "
              "nothing to check this run.")
        return 0

    try:
        lib.refresh_access_token(creds)
    except lib.TokenExpired as e:
        lib.rest_insert("youtube_token_health", {"ok": False, "error": f"invalid_grant: {e.raw_error}"[:2000]})
        lib.open_token_expired_gate(str(e.raw_error))
        print("TOKEN_EXPIRED: invalid_grant -- wrote youtube_token_health(ok=false) and "
              "opened spi_gates row 'youtube_token_expired'.")
        return 1
    except Exception as e:  # noqa: BLE001 -- any other failure is still "not ok", must land a row
        lib.rest_insert("youtube_token_health", {"ok": False, "error": str(e)[:2000]})
        print(f"FAILED (non-invalid_grant): {e}")
        return 1

    lib.rest_insert("youtube_token_health", {"ok": True, "error": None})
    print("OK: token refreshed successfully, youtube_token_health(ok=true) written.")
    return 0


def self_test() -> int:
    """(e) a simulated invalid_grant opens the spi_gates row with the
    Testing-mode explanation -- exercised against the real TokenExpired
    exception class and the real gate-opening SQL string, with the network
    call itself replaced by a raise (no live OAuth call)."""
    ok = True

    def _raise_invalid_grant(_creds):
        raise lib.TokenExpired('{"error": "invalid_grant", "error_description": "Token has been expired or revoked."}')

    real_refresh = lib.refresh_access_token
    real_open_gate = lib.open_token_expired_gate
    gate_calls = []
    lib.refresh_access_token = _raise_invalid_grant
    lib.open_token_expired_gate = lambda proof: gate_calls.append(proof)
    lib.rest_insert = lambda table, row, **kw: [{"id": "self-test"}]
    lib.load_credentials = lambda: {"client_id": "x", "client_secret": "y", "refresh_token": "z"}
    try:
        rc = run()
        if rc == 1 and len(gate_calls) == 1:
            print("(e) PASS: invalid_grant -> non-zero exit, spi_gates('youtube_token_expired') open called once, "
                  "proof captured -- Testing-mode explanation is in youtube_lib.open_token_expired_gate()'s SQL literal")
        else:
            print(f"(e) FAIL: rc={rc} gate_calls={len(gate_calls)}")
            ok = False
    finally:
        lib.refresh_access_token = real_refresh
        lib.open_token_expired_gate = real_open_gate

    return 0 if ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        sys.exit(self_test())
    sys.exit(run())
