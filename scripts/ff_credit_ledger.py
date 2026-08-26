#!/usr/bin/env python3
"""Combined Tracerfy + Bright Data daily spend cap client.

Thin wrapper around the public.ff_ledger_spend() RPC (see
supabase/migrations/20260824_ff_daily_credit_ledger.sql for the credit-unit
definition and why it's call-count-based, not a reconciled dollar figure).
Called over PostgREST/rpc, not direct psql, per this repo's documented
psql-unavailable-in-sandbox fallback pattern (see decision_log ids
169/205/287 and scripts/winnerdata_pipeline.py's own docstring).

Usage: call spend(source, n) BEFORE making the vendor API call it accounts
for. If granted is False, do not call the vendor -- log the skip with a
reason and move on to the next lead/county. Never call the vendor first and
account for it after; that risks going over cap on a crash/retry.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def spend(source: str, n: int = 1) -> dict:
    """source: 'tracerfy' | 'brightdata'. Returns the ff_ledger_spend() jsonb
    response, e.g. {"granted": true, "granted_n": 1, "total_calls": 4, "cap": 100}.
    On any transport error, fails CLOSED (granted=False) -- never lets a
    ledger outage become unlimited spend."""
    if not SB_KEY:
        return {"granted": False, "error": "SUPABASE_SERVICE_ROLE_KEY absent"}
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/ff_ledger_spend",
        data=json.dumps({"p_source": source, "p_n": n}).encode(),
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"granted": False, "error": f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}"}
    except Exception as e:
        return {"granted": False, "error": str(e)}
