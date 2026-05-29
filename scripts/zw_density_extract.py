#!/usr/bin/env python3
"""
ZoneWise density extractor (Brevard).
HONESTY LAW: VERIFIED > ASSUMED, BLANK > WRONG. Never write a density that is
not explicitly stated in the ordinance. Single-family districts that regulate
by minimum lot size only are classified 'lot_governed' (NOT given a number).

Reads pending rows from zw_density_extraction_queue, renders each district's
municode page with Playwright, extracts a stated max density (du/acre) tied to
the district code, writes verified values to zone_standards (+provenance), and
records the outcome class on the queue. Bounded by LIMIT env (default 8) so the
first run is a yield-validation batch before scaling.
"""
import os, re, time, json, sys
from datetime import datetime, timezone
import httpx
from playwright.sync_api import sync_playwright

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_KEY"]
LIMIT        = int(os.environ.get("LIMIT", "8"))
TG_TOKEN     = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT      = os.environ.get("TELEGRAM_CHAT_ID", "")

def NOW():
    return datetime.now(timezone.utc).isoformat()

REST = f"{SUPABASE_URL}/rest/v1"
H = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}",
     "Content-Type": "application/json"}

# Density stated explicitly as units per acre.
DUAC = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:du|d\.?u\.?|dwelling\s+units?|units?)\s*(?:/|per)\s*"
    r"(?:gross\s+|net\s+)?acre", re.I)
DENS_LABEL = re.compile(
    r"(?:maximum|max\.?)\s+densit(?:y|ies)[^\d]{0,40}?(\d+(?:\.\d+)?)\s*"
    r"(?:du|dwelling\s+units?|units?)?\s*(?:/|per)?\s*(?:gross\s+|net\s+)?acre", re.I)
MINLOT = re.compile(r"minimum\s+lot\s+(?:area|size)", re.I)

def sb_get(path):
    r = httpx.get(f"{REST}/{path}", headers=H, timeout=30)
    r.raise_for_status()
    return r.json()

def sb_patch(path, body):
    h = dict(H); h["Prefer"] = "return=representation"
    r = httpx.patch(f"{REST}/{path}", headers=h, json=body, timeout=30)
    r.raise_for_status()
    return r.json()

def sb_post(path, body):
    h = dict(H); h["Prefer"] = "return=minimal"
    r = httpx.post(f"{REST}/{path}", headers=h, json=body, timeout=30)
    r.raise_for_status()
    return r

def extract_density(text, zone_code, district_name):
    """Return (value, evidence) only when a stated du/acre is tied to the district.
    Windowed search around the code/name; page-wide allowed only for deep-link
    single-district pages (caller decides via 'page_wide')."""
    anchors = []
    for needle in [zone_code, district_name]:
        if not needle:
            continue
        for m in re.finditer(re.escape(needle), text, re.I):
            anchors.append(m.start())
    candidates = []
    for pos in anchors:
        window = text[max(0, pos - 500): pos + 800]
        for rx in (DUAC, DENS_LABEL):
            for mm in rx.finditer(window):
                val = float(mm.group(1))
                if 0 < val <= 200:  # sanity bound
                    snip = window[max(0, mm.start() - 60): mm.end() + 40]
                    candidates.append((val, " ".join(snip.split())[:300]))
    if not candidates:
        return None, None
    # prefer the most frequently seen value (robustness), else first
    vals = {}
    for v, s in candidates:
        vals.setdefault(v, s)
    best = sorted(vals.keys(), key=lambda v: sum(1 for c in candidates if c[0] == v))[-1]
    return best, vals[best]

def write_verified(district_id, val, url, evidence):
    rows = sb_get(f"zone_standards?zoning_district_id=eq.{district_id}&select=id,max_density_du_acre")
    if rows:
        if rows[0].get("max_density_du_acre") is None:
            sb_patch(f"zone_standards?id=eq.{rows[0]['id']}&max_density_du_acre=is.null",
                     {"max_density_du_acre": val, "confidence_score": 0.75})
    else:
        sb_post("zone_standards", {"zoning_district_id": district_id,
                                   "max_density_du_acre": val,
                                   "confidence_score": 0.75, "source_url": url})

def set_queue(district_id, **kw):
    kw["updated_at"] = NOW()
    sb_patch(f"zw_density_extraction_queue?district_id=eq.{district_id}", kw)

def telegram(msg):
    if TG_TOKEN and TG_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                       json={"chat_id": TG_CHAT, "text": msg}, timeout=15)
        except Exception:
            pass

def main():
    q = sb_get(f"zw_density_extraction_queue?status=eq.pending&order=parcels.desc&limit={LIMIT}")
    print(f"[zw-density] picked {len(q)} districts (limit={LIMIT})")
    tally = {"verified": 0, "lot_governed": 0, "not_stated": 0, "blocked": 0, "error": 0}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"))
        page = ctx.new_page()
        for row in q:
            did = row["district_id"]; url = row["ordinance_url"]
            code = row.get("zone_code"); name = row.get("district_name")
            page_wide = bool(url and "nodeId=" in url)
            try:
                set_queue(did, claimed_at=NOW())
                page.goto(url, wait_until="networkidle", timeout=60000)
                time.sleep(2)
                body = page.inner_text("body")
                if not body or len(body) < 400:
                    tally["blocked"] += 1
                    set_queue(did, status="blocked", evidence="app-shell/empty render",
                              completed_at=NOW())
                    print(f"  #{did} {code}: blocked (len={len(body) if body else 0})")
                    time.sleep(3); continue
                val, ev = extract_density(body, code, name)
                if val is None and page_wide:
                    # single-district deep link: allow a page-wide stated du/acre
                    m = DUAC.search(body) or DENS_LABEL.search(body)
                    if m:
                        val = float(m.group(1))
                        ev = " ".join(body[max(0, m.start()-60):m.end()+40].split())[:300]
                if val is not None and 0 < val <= 200:
                    write_verified(did, val, url, ev)
                    tally["verified"] += 1
                    set_queue(did, status="verified", extracted_density=val,
                              confidence=0.75, evidence=ev, completed_at=NOW())
                    print(f"  #{did} {code}: VERIFIED {val} du/ac")
                elif MINLOT.search(body):
                    tally["lot_governed"] += 1
                    set_queue(did, status="lot_governed",
                              evidence="min lot stated; no du/acre", completed_at=NOW())
                    print(f"  #{did} {code}: lot_governed (no stated du/ac)")
                else:
                    tally["not_stated"] += 1
                    set_queue(did, status="not_stated",
                              evidence="district found; no density/lot stated",
                              completed_at=NOW())
                    print(f"  #{did} {code}: not_stated")
            except Exception as e:
                tally["error"] += 1
                set_queue(did, status="error", evidence=str(e)[:300], completed_at=NOW())
                print(f"  #{did} {code}: ERROR {e}")
            time.sleep(3)  # respectful rate limit
        browser.close()
    summary = ("ZoneWise density extract — " +
               ", ".join(f"{k}={v}" for k, v in tally.items()))
    print("[zw-density] " + summary)
    telegram("[ZoneWise] " + summary)

if __name__ == "__main__":
    main()
