#!/usr/bin/env python3
"""BCPAO account -> parcel bridge -> pipeline.brevard_account_parcel.

BCPAO (www.bcpao.us) is Cloudflare-challenged from datacenter IPs, so requests
route through Firecrawl (residential rendering). Worklist comes from the public
view v_brevard_unbridged_accounts (tax account numbers seen on auction cards
that lack a parcel mapping).

Endpoint probed: https://www.bcpao.us/api/v1/account/{account} (JSON expected;
response shape is parsed DEFENSIVELY and stored raw -- Honesty V3: extraction
confidence is recorded, never guessed).

Usage: bcpao_bridge.py [limit]   (default 100 accounts/run to bound spend)
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, FIRECRAWL_API_KEY.
"""
import sys, os, json, re, time
import urllib.request

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
FC_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
assert SB_URL and SB_KEY and FC_KEY, "SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY/FIRECRAWL_API_KEY required"

PARCEL_RE = re.compile(r"\b\d{2}[- ]\d{4}[- ][A-Z0-9]{2}[- ][A-Z0-9*]+[- ][A-Z0-9.]+\b")

def http_json(url, payload=None, headers=None, method=None):
    body = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=body, method=method or ("POST" if body else "GET"))
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    if body:
        r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))

def sb_headers():
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}

def worklist(limit):
    return http_json(f"{SB_URL}/rest/v1/v_brevard_unbridged_accounts?limit={limit}",
                     headers=sb_headers())

def rpc(fn, payload):
    return http_json(f"{SB_URL}/rest/v1/rpc/{fn}", {"p": payload}, sb_headers())

def firecrawl(url):
    d = http_json("https://api.firecrawl.dev/v1/scrape",
                  {"url": url, "formats": ["rawHtml", "markdown"]},
                  {"Authorization": f"Bearer {FC_KEY}"})
    data = d.get("data") or {}
    return data.get("rawHtml") or data.get("markdown") or ""

def extract(account, body):
    """Defensive parse. Returns row dict with confidence flag."""
    row = {"account_number": account, "parcel_id": None, "site_address": None,
           "market_value": None, "raw": None, "confidence": "raw_only"}
    txt = re.sub(r"<[^>]+>", " ", body or "")
    j = None
    for candidate in (body, txt):
        try:
            j = json.loads((candidate or "").strip())
            break
        except Exception:
            continue
    if isinstance(j, list) and j:
        j = j[0]
    if isinstance(j, dict):
        row["raw"] = {k: j.get(k) for k in list(j)[:40]}
        for k in ("parcelID", "parcelId", "parcel_id", "ParcelID", "parcelNumber"):
            if j.get(k):
                row["parcel_id"] = str(j[k]).strip()
                break
        for k in ("siteAddress", "site_address", "address", "propertyAddress"):
            if j.get(k):
                row["site_address"] = str(j[k]).strip()[:160]
                break
        for k in ("marketValue", "market_value", "totalMarketValue", "justValue"):
            v = j.get(k)
            if v not in (None, ""):
                try:
                    row["market_value"] = str(float(re.sub(r"[^0-9.]", "", str(v))))
                except Exception:
                    pass
                break
    if not row["parcel_id"]:
        m = PARCEL_RE.search(txt)
        if m:
            row["parcel_id"] = m.group(0)
    if row["parcel_id"]:
        row["confidence"] = "parsed"
    return row

if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else 100
    wl = worklist(limit)
    print(f"worklist: {len(wl)} accounts")
    batch, parsed = [], 0
    for i, w in enumerate(wl):
        acct = w["account_number"]
        try:
            body = firecrawl(f"https://www.bcpao.us/api/v1/account/{acct}")
            row = extract(acct, body)
            batch.append(row)
            parsed += row["confidence"] == "parsed"
        except Exception as e:
            print(f"{acct}: ERROR {e}", file=sys.stderr)
        if len(batch) >= 20:
            rpc("upsert_brevard_account_parcel", batch)
            batch = []
        time.sleep(1.5)
    if batch:
        rpc("upsert_brevard_account_parcel", batch)
    print(f"done: {len(wl)} attempted, {parsed} parcel-parsed")
    if wl and parsed == 0:
        print("WARNING: zero parcels parsed -- BCPAO response shape needs review "
              "(inspect pipeline.brevard_account_parcel.raw)", file=sys.stderr)
        sys.exit(1)
