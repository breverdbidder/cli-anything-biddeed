#!/usr/bin/env python3
"""
Lead volume expansion: build final lead_profiles rows from Sunbiz matches +
fl_parcels fallback, dedupe against existing rows, and insert.

Usage:
  python scripts/lead_llc_expansion_insert.py \
    --sunbiz /tmp/sunbiz/sunbiz_matches.json \
    --parcels-fallback /tmp/sunbiz/parcels_fallback.json \
    --existing /tmp/sunbiz/existing_leads.json \
    --out /tmp/sunbiz/final_rows.json \
    [--apply]

Without --apply, only builds and prints the projected insert (dry run).
"""
import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


def normalize(name):
    if not name:
        return ""
    QUALIFIER_RE = re.compile(
        r",?\s*A\s+[A-Z]+\s+(LIMITED\s+LIABILITY\s+COMPANY|CORPORATION|"
        r"LIMITED\s+PARTNERSHIP|GENERAL\s+PARTNERSHIP|PARTNERSHIP)\.?\s*$",
        re.I,
    )
    name = name.split(";")[0]
    name = QUALIFIER_RE.sub("", name)
    name = name.upper()
    name = re.sub(r"[.,]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def sb_post(path, rows):
    data = json.dumps(rows).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=data,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sunbiz", required=True)
    ap.add_argument("--parcels-fallback", required=True)
    ap.add_argument("--existing", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    sunbiz = json.load(open(args.sunbiz))
    parcels_fb = json.load(open(args.parcels_fallback))
    existing = json.load(open(args.existing))

    existing_keys = {normalize(e["name"]) for e in existing if e.get("name")}

    rows = []
    skipped_no_address = []
    skipped_dup = []

    for key, entry in sunbiz.items():
        if key in existing_keys:
            skipped_dup.append(key)
            continue

        bidder = entry["bidders"][0]
        county = bidder["county"]
        display_name = entry.get("sunbiz_name") or bidder["winning_bidder"]

        mailing_address = entry.get("mailing_address")
        registered_agent = entry.get("registered_agent")
        source_detail = "sunbiz_registry" if entry.get("matched") else None

        if not mailing_address:
            fb = parcels_fb.get(key)
            if fb:
                mailing_address = fb["mailing_address"]
                source_detail = "fl_parcels_own_addr1"

        if not mailing_address:
            skipped_no_address.append(key)
            continue

        rows.append({
            "name": display_name.strip()[:250],
            "email": None,
            "county": county,
            "investor_type": "corporate_bidder",
            "source": "auction_llc_expansion",
            "stage": "new",
            "mailing_address": mailing_address,
            "registered_agent": registered_agent,
            "score": 0,
            "_match_key": key,
            "_address_source": source_detail,
        })

    print(f"Built {len(rows)} candidate rows")
    print(f"  Skipped (already in lead_profiles): {len(skipped_dup)}")
    print(f"  Skipped (no address found via Sunbiz or fl_parcels): {len(skipped_no_address)}")

    json.dump(rows, open(args.out, "w"), indent=2)

    if not args.apply:
        print("DRY RUN — not inserting. Re-run with --apply to write to lead_profiles.")
        return

    if not SUPABASE_KEY:
        print("FATAL: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
        sys.exit(1)

    inserted = 0
    errors = 0
    BATCH = 50
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        payload = [
            {k: v for k, v in r.items() if not k.startswith("_")}
            for r in batch
        ]
        status, resp = sb_post("lead_profiles", payload)
        if status in (200, 201):
            inserted += len(resp) if isinstance(resp, list) else len(batch)
        else:
            errors += len(batch)
            print(f"  [ERROR] batch {i}-{i+len(batch)}: HTTP {status}: {resp}", file=sys.stderr)

    print(f"\nInserted: {inserted}  Errors: {errors}")


if __name__ == "__main__":
    main()
