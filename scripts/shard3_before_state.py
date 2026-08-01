#!/usr/bin/env python3
import os, json, urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

def evaluate(county):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=json.dumps({"county_slug_arg": county}).encode(),
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

counties = ["seminole", "hamilton", "union", "flagler", "lake"]
results = {}
for c in counties:
    try:
        results[c] = evaluate(c)
        print(f"BEFORE {c}: {json.dumps(results[c])}")
    except Exception as e:
        print(f"BEFORE {c}: ERROR {e}")
        results[c] = {"error": str(e)}

with open("/tmp/shard3_before.json", "w") as f:
    json.dump(results, f)
print("Saved to /tmp/shard3_before.json")
