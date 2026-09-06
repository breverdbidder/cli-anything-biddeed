"""Paginated variant of scripts/shard2_run2450_ajax_realforeclose_harvest.py.

WHY THIS EXISTS: the base harvester only requests PageDir=0 per AREA (W/C), capping
each date at ~20 items. The RealAuction AJAX endpoint paginates via PageDir=0,1,2,-1...
(non-sequential order, confirmed live 2026-07-04 against escambia.realtaxdeed.com) —
this variant pages until two consecutive pages return no new AIDs, capturing the full
calendar for a date (verified: escambia 08/05/2026 went from 20 items at PageDir=0-only
to 61 items with full pagination). Usage:
  python3 realforeclose_aids_paginated_harvest.py <subdomain> <platform_domain> <county_slug> <dates...>
  e.g. realforeclose_aids_paginated_harvest.py escambia realtaxdeed.com escambia 08/05/2026
"""
import urllib.request, urllib.parse, http.cookiejar, json, time, re, os

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

def to_float(s):
    if not s: return None
    m = re.search(r"\$?([\d,]+\.?\d*)", s)
    if not m: return None
    try: return float(m.group(1).replace(",", ""))
    except Exception: return None

def strip_html(s):
    if not s: return None
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s))).strip()
    return t or None

def parse_starts(s):
    if not s: return None
    cleaned = re.sub(r"\s+(?:ET|EST|EDT|CT|CST|CDT|MT|MST|MDT|PT|PST|PDT)\s*$", "", s.strip())
    from datetime import datetime
    for fmt in ("%m/%d/%Y %I:%M %p", "%m/%d/%Y %H:%M", "%m/%d/%Y"):
        try: return datetime.strptime(cleaned, fmt).isoformat()
        except ValueError: continue
    return None

AJAX_SUBS = [
    ("@A", '<div class="'), ("@B", "</div>"), ("@C", 'class="'), ("@D", "<div>"),
    ("@E", "AUCTION"), ("@F", "</td><td"), ("@G", "</td></tr>"), ("@H", "<tr><td "),
    ("@I", "table"), ("@J", 'p_back="NextCheck='), ("@K", 'style="Display:none"'),
    ("@L", "/index.cfm?zaction=auction&zmethod=details&AID="),
]
def decode_ajax_html(rh):
    for t,r in AJAX_SUBS: rh = rh.replace(t,r)
    return rh

def parse_aitem_blocks(html, county_sub):
    items = []
    starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', html)]
    if not starts: return items
    starts.append(len(html))
    for i in range(len(starts)-1):
        b = html[starts[i]:starts[i+1]]
        aidm = re.search(r'aid="(\d+)"', b)
        if not aidm: continue
        aid = aidm.group(1)
        sm = re.search(r'ASTAT_MSGA[^>]*>Auction Starts</div>\s*<div[^>]+>\s*([^<]+?)\s*</div>', b)
        starts_raw = sm.group(1).strip() if sm else None
        rows = re.findall(r'<td[^>]*class="AD_LBL"[^>]*>(.*?)</td>\s*<td[^>]*class="AD_DTA[^"]*"[^>]*>(.*?)</td>', b, re.DOTALL)
        data = {}; addr_lines = []; last_addr = False
        for lbl_h, dta_h in rows:
            lbl = re.sub(r"<[^>]+>", "", lbl_h).strip().rstrip(":").lower()
            if "property address" in lbl:
                t = strip_html(dta_h)
                if t: addr_lines.append(t)
                last_addr = True; continue
            if last_addr and not lbl:
                t = strip_html(dta_h)
                if t: addr_lines.append(t)
                continue
            last_addr = False
            if lbl: data[lbl] = dta_h
        items.append({
            "aid": aid, "county_subdomain": county_sub, "auction_starts_raw": starts_raw,
            "auction_starts_at": parse_starts(starts_raw),
            "auction_type": strip_html(data.get("auction type")),
            "case_number": strip_html(data.get("case #")),
            "judgment_amount": to_float(data.get("final judgment amount")),
            "parcel_id": strip_html(data.get("parcel id")),
            "property_address": ", ".join(addr_lines) if addr_lines else None,
            "assessed_value": to_float(data.get("assessed value")),
            "plaintiff_max_bid": to_float(data.get("plaintiff max bid")),
        })
    return items

def fetch(url, jar, referer=None, headers=None):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    hdrs = {"User-Agent": UA}
    if referer: hdrs["Referer"] = referer
    if headers: hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with opener.open(req, timeout=20) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")

def harvest_date_full(subdomain, platform_domain, date, max_pages=30):
    base = f"https://{subdomain}.{platform_domain}"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date}"
    jar = http.cookiejar.CookieJar()
    try:
        status, _ = fetch(preview_url, jar)
    except Exception as e:
        print(f"  PREVIEW fetch failed {date}: {e}"); return []
    if status != 200:
        print(f"  PREVIEW non-200 ({status}) {date}"); return []

    all_items = {}
    for area in ("W","C"):
        seen_aids = set()
        pagedir = 0
        stagnant = 0
        while pagedir < max_pages and stagnant < 4:
            ts = int(time.time()*1000)
            ajax_url = (f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                        f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(date)}&PageDir={pagedir}"
                        f"&doR=0&tx={ts}&bypassPage=0&test=1")
            try:
                status, body = fetch(ajax_url, jar, referer=preview_url, headers={"X-Requested-With":"XMLHttpRequest"})
            except Exception as e:
                print(f"  AJAX fail area={area} pagedir={pagedir}: {e}"); break
            if status != 200: break
            try: data = json.loads(body)
            except Exception: break
            ret_html = data.get("retHTML") or ""
            if not ret_html: break
            decoded = decode_ajax_html(ret_html)
            parsed = parse_aitem_blocks(decoded, subdomain)
            new_count = 0
            for it in parsed:
                if it["aid"] not in seen_aids:
                    seen_aids.add(it["aid"])
                    all_items[it["aid"]] = it
                    new_count += 1
            if new_count == 0:
                stagnant += 1
            else:
                stagnant = 0
            pagedir += 1
            time.sleep(0.3)
    return list(all_items.values())

def upsert_aids(items, county_slug):
    if not items: return 0
    payload = []
    for a in items:
        if not a.get("case_number"): continue
        payload.append({
            "aid": a["aid"], "county_slug": county_slug, "auction_type": a["auction_type"],
            "case_number": a["case_number"], "judgment_amount": a["judgment_amount"],
            "parcel_id": a["parcel_id"], "property_address": a["property_address"],
            "assessed_value": a["assessed_value"], "plaintiff_max_bid": a["plaintiff_max_bid"],
            "auction_starts_at": a["auction_starts_at"], "auction_starts_raw": a["auction_starts_raw"],
            "county_subdomain": a["county_subdomain"],
        })
    if not payload: return 0
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/realforeclose_aids?on_conflict=aid",
        data=json.dumps(payload).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"},
    )
    import time as _t
    last_err = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
            if status not in (200,201,204):
                raise RuntimeError(f"upsert failed: HTTP {status}")
            return len(payload)
        except Exception as e:
            last_err = e
            _t.sleep(2 * (attempt + 1))
    raise RuntimeError(f"upsert failed after retries: {last_err}")

def patch_mca(county_slug):
    """Promote harvested evidence into canonical MCA fields through the verified RPC."""
    payload = json.dumps({"p_dispatch_id": None, "p_county_slug": county_slug}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/realforeclose_aids_to_mca_patch",
        data=payload,
        method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        body = response.read().decode("utf-8", errors="replace")
        if response.status not in (200, 201, 204):
            raise RuntimeError(f"MCA promotion failed HTTP {response.status}: {body[:1000]}")
        return body

if __name__ == "__main__":
    import sys
    subdomain, platform, county_slug = sys.argv[1], sys.argv[2], sys.argv[3]
    dates = sys.argv[4:]
    total_parsed = 0; total_inserted = 0
    for d in dates:
        items = harvest_date_full(subdomain, platform, d)
        n = upsert_aids(items, county_slug)
        total_parsed += len(items); total_inserted += n
        print(f"{d}: parsed={len(items)} inserted_or_merged={n}")
    promotion = patch_mca(county_slug)
    print(f"MCA_PROMOTION county={county_slug} result={promotion}")
    print(f"TOTAL: parsed={total_parsed} inserted_or_merged={total_inserted}")
    if total_parsed > 0 and total_inserted == 0:
        raise RuntimeError("Silent failure: parsed>0 inserted=0")
