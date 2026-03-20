#!/usr/bin/env python3
"""
Normalize Jurisdictions — merge 22 values → 17 canonical BCPAO names.

Operations:
- UPDATE jurisdiction = 'unincorporated_brevard' WHERE jurisdiction IN
  ('unincorporated', 'merritt_island', 'mims', 'barefoot_bay', 'micco', 'fellsmere')

Since Supabase REST API doesn't support bulk UPDATE with IN clause directly,
we use the RPC approach or patch with filter.

Supabase REST PATCH with query filter:
  PATCH /rest/v1/zoning_assignments?jurisdiction=eq.{value}
  Body: {"jurisdiction": "unincorporated_brevard"}

NEVER-LIE: Reports COUNT(*) before and after each operation.
"""
import httpx, os, sys, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

# These values all map to 'unincorporated_brevard'
UNINC_VALUES = ["unincorporated", "merritt_island", "mims", "barefoot_bay", "micco", "fellsmere"]

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})


def telegram(msg):
    print(msg)
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]}, timeout=10)
        except Exception as e:
            print(f"  [telegram error] {e}", file=sys.stderr)


def sb_headers_patch():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def sb_count_jurisdiction(jurisdiction):
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "count=exact",
    }
    url = f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=parcel_id&limit=0&jurisdiction=eq.{jurisdiction}"
    resp = client.get(url, headers=h)
    cr = resp.headers.get("content-range", "")
    return int(cr.split("/")[1]) if "/" in cr and cr.split("/")[1] != "*" else 0


def sb_count_total():
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "count=exact",
    }
    url = f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=parcel_id&limit=0&county=eq.brevard"
    resp = client.get(url, headers=h)
    cr = resp.headers.get("content-range", "")
    return int(cr.split("/")[1]) if "/" in cr and cr.split("/")[1] != "*" else -1


def patch_jurisdiction(from_value, to_value):
    """PATCH all rows where jurisdiction=from_value to to_value."""
    h = sb_headers_patch()
    h["Prefer"] = "count=exact"
    url = f"{SUPABASE_URL}/rest/v1/zoning_assignments?jurisdiction=eq.{from_value}&county=eq.brevard"
    resp = client.patch(url, headers=h, json={"jurisdiction": to_value})
    if resp.status_code in (200, 204):
        cr = resp.headers.get("content-range", "")
        count = int(cr.split("/")[1]) if "/" in cr and cr.split("/")[1] != "*" else "?"
        return count
    else:
        print(f"  [patch error] {from_value}→{to_value}: {resp.status_code} {resp.text[:200]}", file=sys.stderr)
        return 0


def get_jurisdiction_counts():
    """Get distinct jurisdiction counts."""
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    counts = {}
    jurisdictions = UNINC_VALUES + ["unincorporated_brevard"]
    for j in jurisdictions:
        counts[j] = sb_count_jurisdiction(j)
    return counts


def main():
    start = time.time()
    telegram("🏔️ NORMALIZE JURISDICTIONS: Merging 6 uninc values → unincorporated_brevard")

    before_total = sb_count_total()
    before_counts = get_jurisdiction_counts()

    print("BEFORE counts:", flush=True)
    for j, c in before_counts.items():
        print(f"  {j}: {c:,}", flush=True)
    telegram(f"📊 BEFORE total={before_total:,}\n" + "\n".join(f"  {j}: {c:,}" for j, c in before_counts.items()))

    # Patch each value
    results = []
    for val in UNINC_VALUES:
        before_c = before_counts.get(val, 0)
        if before_c == 0:
            print(f"  {val}: 0 rows, skipping", flush=True)
            results.append(f"  {val}: 0 rows (skipped)")
            continue
        print(f"  Patching {val} ({before_c:,} rows) → unincorporated_brevard...", flush=True)
        count = patch_jurisdiction(val, "unincorporated_brevard")
        results.append(f"  {val} → unincorporated_brevard: {count} rows updated")
        print(f"    Updated: {count}", flush=True)
        time.sleep(1)

    # AFTER
    time.sleep(2)
    after_total = sb_count_total()
    after_uninc = sb_count_jurisdiction("unincorporated_brevard")
    elapsed = int(time.time() - start)

    results_text = "\n".join(results)
    telegram(f"""🏔️ NORMALIZE JURISDICTIONS COMPLETE

📊 OPERATIONS:
{results_text}

📈 COUNT(*):
  BEFORE total: {before_total:,}
  AFTER total:  {after_total:,}
  unincorporated_brevard now: {after_uninc:,}

⏱️ {elapsed//60}m {elapsed%60}s | 💰 $0""")


if __name__ == "__main__":
    main()
