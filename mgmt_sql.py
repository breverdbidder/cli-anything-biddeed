#!/usr/bin/env python3
"""Run SQL against the live Supabase project via the Management API. Usage: python3 mgmt_sql.py 'SELECT 1'  or  python3 mgmt_sql.py -f file.sql"""
import os, sys, json, httpx

REF = "mocerqjnksmhcjzxrewo"
TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]

def run(query: str):
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    r = httpx.post(f"https://api.supabase.com/v1/projects/{REF}/database/query", headers=h, json={"query": query}, timeout=580)
    return r

if __name__ == "__main__":
    if sys.argv[1] == "-f":
        query = open(sys.argv[2]).read()
    else:
        query = sys.argv[1]
    r = run(query)
    print(f"STATUS {r.status_code}")
    try:
        print(json.dumps(r.json(), indent=2, default=str)[:8000])
    except Exception:
        print(r.text[:8000])
