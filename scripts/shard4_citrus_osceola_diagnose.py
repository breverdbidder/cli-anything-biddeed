#!/usr/bin/env python3
"""
Shard-4 citrus/osceola diagnosis script - query current county status.
Reads SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from environment.
"""
from __future__ import annotations
import json
import os
import urllib.parse
import urllib.request


def _headers():
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def evaluate_county(sb_url: str, county: str) -> dict:
    url = f"{sb_url.rstrip('/')}/rest/v1/rpc/pencil_dod_evaluate_county"
    data = json.dumps({"p_county": county}).encode()
    req = urllib.request.Request(url, data=data, headers=_headers(), method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    sb_url = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
    counties = ["polk", "jefferson", "okaloosa"]
    for county in counties:
        try:
            result = evaluate_county(sb_url, county)
            print(f"\n=== {county.upper()} ===")
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"\n=== {county.upper()} ERROR: {e} ===")


if __name__ == "__main__":
    main()
