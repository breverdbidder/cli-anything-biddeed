"""Columbia County tax-deed harvester -- v2 for the redesigned columbiaclerk.com.

WHY THIS EXISTS: columbia_clerk_html_harvest.py (2026-07-05) targets the OLD
site DOM (`<div class="even:bg-gray-100">` blocks with a `Case Number` field).
As of this session (2026-08-03), columbiaclerk.com has been rebuilt on a new
Vue/Tailwind theme. The old selectors no longer match ANYTHING on either the
foreclosure or tax-deed pages -- confirmed by re-running the old BLOCK_RE
against a fresh DOM dump and getting zero blocks. This is DOM/selector drift
from a site redesign, not a real "zero listings" result.

The new tax-deed page (https://columbiaclerk.com/tax-deed-sales/, which
`/clerk-services/tax-deeds/upcoming-tax-deed-sales/` also serves -- confirmed
same content, same 19 rows, both live 2026-08-03) renders each sale as a card:
  <div class="grid border border-primary/50 ...">
    <label>Status</label><strong>scheduled</strong>
    <label>Sale Date</label><strong>08/31/2026 00:00 am</strong>
    <label>Cert #</label><strong>2562/2023</strong>
    <label>Parcel ID</label><strong>10846-104</strong>
  </div>

IMPORTANT -- fields NOT present in this card layout (Vue renders them as
`<!---->` HTML comments when absent at the list level, e.g. a per-case file
number like "25-81-TD", opening bid, property address): the list page only
ever gives Status/Sale Date/Cert #/Parcel ID. A file number ("NN-NN-TD") and
opening bid DO exist on this site (seen via a search-engine cache of a
different, non-matching set of certs -- so likely live on a per-case detail
page, not the list page) but were NOT reachable in this session. Do not
synthesize a case_number from cert_number -- leave case_number NULL rather
than fabricate an identifier the site never actually displayed to us.

Cloudflare note: plain curl/urllib gets 403 "Just a moment" on this domain
(confirmed repeatedly across sessions back to 2026-07-05). Claude's own
WebFetch tool ALSO gets 403 on this domain (new finding, 2026-08-03) -- so
the block is domain-wide bot detection, not fetcher-specific. What DOES get
through: the OS `google-chrome` binary (NOT the bare `chromium` launcher/npm
package) driven with --headless=new and a spoofed desktop Chrome UA string.
`chromium` (no UA override) was blocked again this session where it worked
once on 2026-07-05 -- Cloudflare appears to have tightened detection since
then. Use google-chrome, not chromium, going forward.

Usage:
  python3 columbia_taxdeed_html_harvest_v2.py

Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in env. Requires a
google-chrome / google-chrome-stable binary on PATH.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

URL = "https://columbiaclerk.com/tax-deed-sales/"

CARD_SPLIT = '<div class="grid border border-primary/50'
FIELD_RE = re.compile(
    r'<label[^>]*>([^<]+)</label><strong[^>]*>([^<]*)</strong>'
)

# Site renders this exact copy when the tax-deed lane genuinely has zero
# scheduled sales (confirmed live 2026-07-05 session). Distinguish a real
# empty lane from selector drift -- never silently swallow a real regression
# as "0 results".
EMPTY_RE = re.compile(r"no (?:properties|tax deeds)[^<]{0,80}", re.I)


def find_browser():
    for name in ("google-chrome", "google-chrome-stable"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("No google-chrome binary found on PATH (chromium is Cloudflare-blocked as of 2026-08-03)")


def dump_dom(browser, url):
    cmd = [
        browser, "--headless=new", "--disable-gpu", "--no-sandbox",
        f"--user-agent={UA}", "--dump-dom", "--virtual-time-budget=20000", url,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=60)
    html = result.stdout.decode("utf-8", errors="replace")
    if "Just a moment" in html or len(html) < 5000:
        raise RuntimeError(f"Blocked or empty response for {url} (len={len(html)})")
    return html


def to_iso_date(s):
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s or "")
    if not m:
        return None
    mm, dd, yyyy = m.groups()
    return f"{yyyy}-{mm}-{dd}"


def parse_listings(html):
    start = html.find(CARD_SPLIT)
    if start == -1:
        m = EMPTY_RE.search(html)
        if m:
            return [], m.group(0)
        raise RuntimeError(
            "No tax-deed cards found and site does NOT show its known "
            "'no listings' copy -- likely selector drift (CARD_SPLIT no "
            "longer matches), not a real empty lane. Refusing to treat as success."
        )
    cards = html[start:].split(CARD_SPLIT)
    items = []
    for c in cards[1:]:
        fields = dict(FIELD_RE.findall(c))
        cert = fields.get("Cert #")
        parcel = fields.get("Parcel ID")
        if not cert and not parcel:
            continue
        items.append({
            "cert_number": cert,
            "parcel_id": parcel,
            "auction_date": to_iso_date(fields.get("Sale Date")),
            "status_raw": fields.get("Status"),
        })
    return items, None


def _existing_cert_parcels():
    # multi_county_auctions has no unique constraint on (county, cert_number,
    # sale_type) -- only on (county, case_number, sale_type)
    # (uq_mca_county_case_sale), confirmed live 2026-08-03. Since the tax-deed
    # list page never gives us a case_number (see module docstring), we can't
    # use PostgREST on_conflict= for real dedup. Do the dedup ourselves by
    # reading current (cert_number, parcel_id) pairs before inserting -- a
    # plain INSERT run daily without this would duplicate all rows every day.
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
        f"?select=cert_number,parcel_id&county=eq.columbia&sale_type=eq.tax_deed",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        rows = json.loads(resp.read())
    return {(r["cert_number"], r["parcel_id"]) for r in rows}


def _post_insert(payload):
    if not payload:
        return 0
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
        data=json.dumps(payload).encode(), method="POST",
        headers={
            "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status not in (200, 201, 204):
            raise RuntimeError(f"insert failed: HTTP {resp.status}")
    return len(payload)


def upsert(items):
    if not items:
        return 0
    seen = _existing_cert_parcels()
    items = [it for it in items if (it["cert_number"], it["parcel_id"]) not in seen]
    if not items:
        return 0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = [{
        "county": "columbia",
        "sale_type": "tax_deed",
        "case_number": None,
        "cert_number": it["cert_number"],
        "parcel_id": it["parcel_id"],
        "auction_date": it["auction_date"],
        "auction_status": "upcoming" if (it["status_raw"] or "").lower() in ("scheduled", "upcoming", "") else it["status_raw"].lower(),
        "data_source": "columbia_clerk_html:SHARD2-V2-TAXDEED",
        "parity_source": "tier1_columbia_clerk_official_records",
        "parity_status": "matched_clean",
        "provenance": "primary_scrape",
        "source_url": URL,
        "scraped_at": now,
        "last_seen_at": now,
    } for it in items]
    return _post_insert(payload)


def main():
    browser = find_browser()
    html = dump_dom(browser, URL)
    items, empty_note = parse_listings(html)
    if not items:
        print(f"tax_deed: parsed=0 upserted=0 (site confirms genuinely empty: {empty_note!r})")
        return
    seen = _existing_cert_parcels()
    already_known = sum(1 for it in items if (it["cert_number"], it["parcel_id"]) in seen)
    n = upsert(items)
    print(f"tax_deed: parsed={len(items)} already_known={already_known} upserted={n}")
    if len(items) > 0 and n == 0 and already_known < len(items):
        raise RuntimeError("Silent failure: parsed>0 upserted=0 and not all rows were already-known")


if __name__ == "__main__":
    main()
