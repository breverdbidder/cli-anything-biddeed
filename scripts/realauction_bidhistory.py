#!/usr/bin/env python3
"""Brevard RealAuction bid-history via Firecrawl actions (clean-IP bypass).

WHY FIRECRAWL: RealForeclose/RealTaxDeed 403 cloud IPs (GitHub runners included).
Proven in prior sessions. The working bypass = the active scraping_proxy_backend
= Firecrawl (residential IPs + JS render + scriptable actions). Drives the SAME
login flow that worked historically (#LogName/#LogPass + #LogButton) through
Firecrawl so it runs from anywhere.

Creds from env (GitHub Secrets, runner-only): REALFORECLOSE_EMAIL / _PASSWORD.
Never logged. Firecrawl key from FIRECRAWL_API_KEY.
Usage: realauction_bidhistory.py <platform> [YYYY-MM-DD]
"""
import sys, os, json, re, datetime as dt
import urllib.request

PLATFORM = (sys.argv[1] if len(sys.argv) > 1 else "realtaxdeed").lower()
HOST = {"realforeclose": "https://brevard.realforeclose.com",
        "realtaxdeed": "https://brevard.realtaxdeed.com"}[PLATFORM]
SALE_TYPE = {"realforeclose": "foreclosure", "realtaxdeed": "tax_deed"}[PLATFORM]

EMAIL = os.environ.get("REALFORECLOSE_EMAIL", "")
PW = os.environ.get("REALFORECLOSE_PASSWORD", "")
FC_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
assert EMAIL and PW and FC_KEY and SB_URL and SB_KEY, "missing required env"

def firecrawl_actions(url, actions, formats=("rawHtml",)):
    payload = {"url": url, "formats": list(formats), "actions": actions,
               "waitFor": 3000, "timeout": 90000}
    r = urllib.request.Request("https://api.firecrawl.dev/v1/scrape",
                               data=json.dumps(payload).encode(), method="POST")
    r.add_header("Authorization", f"Bearer {FC_KEY}")
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=150) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))

def rpc(fn, payload):
    r = urllib.request.Request(f"{SB_URL}/rest/v1/rpc/{fn}",
                               data=json.dumps({"p": payload}).encode(), method="POST")
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=120) as resp:
        return resp.status

def dump(event_type, text):
    try:
        rpc("upsert_live_auction_events", [{
            "county_slug": "brevard", "sale_type": SALE_TYPE,
            "auction_date": dt.date.today().isoformat(), "event_type": event_type,
            "payload_text": (text or "")[:50000],
            "event_ts": dt.datetime.now(dt.timezone.utc).isoformat()}])
    except Exception as e:
        print(f"dump skipped: {e}", file=sys.stderr)

def harvest(date_iso):
    d = dt.date.fromisoformat(date_iso)
    date_mdY = d.strftime("%m/%d/%Y")
    results_url = f"{HOST}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date_mdY}"
    actions = [
        {"type": "wait", "milliseconds": 2500},
        {"type": "write", "selector": "#LogName", "text": EMAIL},
        {"type": "write", "selector": "#LogPass", "text": PW},
        {"type": "click", "selector": "#LogButton"},
        {"type": "wait", "milliseconds": 4000},
        {"type": "navigate", "url": results_url},
        {"type": "wait", "milliseconds": 4000},
        {"type": "scrape"},
    ]
    res = firecrawl_actions(HOST + "/index.cfm", actions)
    html = ""
    if res.get("success"):
        data = res.get("data", {})
        html = data.get("rawHtml") or ""
        sc = (data.get("actions") or {}).get("scrapes") or []
        if sc and sc[-1].get("html"):
            html = sc[-1]["html"]
    dump("_discovery_dump", html or json.dumps(res)[:5000])
    return d, html

FOOTER_RE = re.compile(r"final bid was made by[^:]*:\s*</?[^>]*>?\s*([A-Za-z0-9 ,.&'\-]+?)\s*<", re.I)
AMOUNT_RE = re.compile(r"\$([\d,]+\.\d{2})")
ROW_RE = re.compile(r"(\d{4,6})\D{0,40}?(Auto Bid|tied high bid|winning bid)?\D{0,40}?"
                    r"\$([\d,]+\.\d{2})\D{0,40}?(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2} [AP]M)", re.I)

def num(s):
    return float(s.replace(",", "")) if s else None

def parse_lot(block, date_iso):
    acct = (re.search(r"Parcel ID:\s*</?[^>]*>?\s*([0-9\-]+)", block) or [None, None])[1] if "Parcel ID" in block else None
    case = (re.search(r"Case #:\s*</?[^>]*>?\s*([0-9A-Za-z\-]+)", block) or [None, None])[1] if "Case #" in block else None
    sm = AMOUNT_RE.search(block.split("Amount")[-1][:120]) if "Amount" in block else None
    fm = FOOTER_RE.search(block)
    winner = fm.group(1).strip() if fm else None
    bids, win_bidder = [], None
    for m in ROW_RE.finditer(block):
        bid_id, btype, amt, ts = m.group(1), (m.group(2) or "").lower(), m.group(3), m.group(4)
        if btype == "winning bid":
            win_bidder = bid_id
        bids.append({"auction_date": date_iso, "case_number": case, "account_number": acct,
                     "bidder_id": bid_id, "bid_amount": num(amt), "bid_type": btype or "manual",
                     "bid_ts": dt.datetime.strptime(ts, "%m/%d/%Y %I:%M:%S %p").isoformat(),
                     "is_winner": btype == "winning bid"})
    return {"account_number": acct, "case_number": case, "sold_amount": num(sm.group(1)) if sm else None,
            "winner_name": winner, "winner_bidder_id": win_bidder, "bids": bids}

if __name__ == "__main__":
    date_arg = sys.argv[2] if len(sys.argv) > 2 else dt.date.today().isoformat()
    d, html = harvest(date_arg)
    blocks = re.split(r"Auction (?:Sold|Closed|Canceled)", html)
    print(f"blocks={len(blocks)-1} html_len={len(html)}")
    all_bids, identities, events, lots = [], [], [], 0
    for blk in blocks[1:]:
        lot = parse_lot(blk, d.isoformat())
        if not lot["bids"] and not lot["winner_name"]:
            continue
        lots += 1
        all_bids += lot["bids"]
        if lot["winner_name"] and lot["winner_bidder_id"]:
            identities.append({"bidder_id": lot["winner_bidder_id"], "resolved_name": lot["winner_name"],
                               "confidence": "footer_winner", "first_seen": d.isoformat(),
                               "last_seen": d.isoformat(), "auctions_seen": 1, "wins": 1})
        if lot["winner_name"]:
            events.append({"county_slug": "brevard", "sale_type": SALE_TYPE, "auction_date": d.isoformat(),
                           "account_number": lot["account_number"], "case_number": lot["case_number"],
                           "event_type": "sold", "amount": lot["sold_amount"],
                           "winner_name": lot["winner_name"], "winner_bidder_id": lot["winner_bidder_id"],
                           "event_ts": dt.datetime.now(dt.timezone.utc).isoformat()})
    if all_bids:
        rpc("upsert_brevard_bid_history", all_bids)
    if identities:
        rpc("upsert_brevard_bidder_identity", identities)
    if events:
        rpc("upsert_live_auction_events", events)
    print(f"lots={lots} bids={len(all_bids)} names={len(identities)} events={len(events)}")
    sys.exit(0 if lots else 1)
