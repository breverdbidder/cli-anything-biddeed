#!/usr/bin/env python3
"""Brevard RealAuction authenticated bid-history engine -> the moat.

Login decoded 2026-06-11 (Summit session). RealAuction auth is a plain JSON POST
(no Playwright):
  POST /index.cfm  ZACTION=AJAX ZMETHOD=LOGIN func=LOGIN USERNAME=.. USERPASS=..
  -> {"isOk":"YES"} + session cookie

Then the closed-auction results page exposes, per lot:
  - winner footer: "The final bid was made by 3rd party bidder: <NAME>"
  - bid ladder rows: persistent numeric bidder IDs, amount, type, timestamp

Writes:
  pipeline.brevard_bid_history     (every bid row, bidder IDs = the moat)
  pipeline.brevard_bidder_identity (ID -> name, confidence='footer_winner')
  pipeline.live_auction_events     (winner_name + winner_bidder_id per sold lot)
  + back-fills tier1_card_raw.sold_to_text where matched

CREDENTIAL HANDLING: reads REALFORECLOSE_EMAIL / REALFORECLOSE_PASSWORD from env
(GitHub Actions secrets). Never logged, never echoed. Account-safety: single
session, polite throttle, realistic UA, backoff -- standard member browsing
cadence, never hammered.

Usage: realauction_bidhistory.py <platform> [YYYY-MM-DD]
  platform: 'realforeclose' (foreclosure) | 'realtaxdeed' (tax deed)
  date: sale date to harvest (default: today)
Env: REALFORECLOSE_EMAIL, REALFORECLOSE_PASSWORD, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
import sys, os, json, re, time, datetime as dt
import urllib.request, urllib.parse, http.cookiejar

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
THROTTLE = 4.0  # polite member cadence; never hammer

PLATFORM = (sys.argv[1] if len(sys.argv) > 1 else "realforeclose").lower()
HOST = {"realforeclose": "https://brevard.realforeclose.com",
        "realtaxdeed": "https://brevard.realtaxdeed.com"}[PLATFORM]
SALE_TYPE = {"realforeclose": "foreclosure", "realtaxdeed": "tax_deed"}[PLATFORM]

EMAIL = os.environ.get("REALFORECLOSE_EMAIL", "")
PW = os.environ.get("REALFORECLOSE_PASSWORD", "")
SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
assert EMAIL and PW, "REALFORECLOSE_EMAIL / REALFORECLOSE_PASSWORD env required"
assert SB_URL and SB_KEY, "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY env required"

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def req(path, data=None, hdrs=None, retries=4):
    url = path if path.startswith("http") else HOST + path
    for a in range(retries):
        time.sleep(THROTTLE * (2 ** a if a else 1))
        try:
            body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else \
                   (data.encode() if isinstance(data, str) else data)
            r = urllib.request.Request(url, data=body)
            r.add_header("User-Agent", UA)
            r.add_header("Referer", HOST + "/index.cfm")
            if isinstance(data, dict):
                r.add_header("Content-Type", "application/x-www-form-urlencoded")
                r.add_header("X-Requested-With", "XMLHttpRequest")
            for k, v in (hdrs or {}).items():
                r.add_header(k, v)
            with op.open(r, timeout=60) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            sys.stderr.write(f"retry {a+1}: {e}\n")
            if a == retries - 1:
                raise

def rpc(fn, payload):
    body = json.dumps({"p": payload}).encode()
    r = urllib.request.Request(f"{SB_URL}/rest/v1/rpc/{fn}", data=body, method="POST")
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=120) as resp:
        return resp.status

def login():
    req("/index.cfm")  # seed session
    resp = req("/index.cfm", data={"ZACTION": "AJAX", "ZMETHOD": "LOGIN", "func": "LOGIN",
                                   "USERNAME": EMAIL, "USERPASS": PW})
    try:
        ok = json.loads(resp).get("isOk", "").upper() == "YES"
    except Exception:
        ok = "isOk" in (resp or "") and "YES" in (resp or "")
    if not ok:
        raise RuntimeError("LOGIN FAILED -- check REALFORECLOSE_EMAIL/PASSWORD secrets "
                           "(value rotated?). Auth response did not return isOk=YES.")
    print("login ok")

def results_page(date_mdY):
    # Closed/canceled auctions for a given sale date.
    return req(f"/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={urllib.parse.quote(date_mdY)}")

FOOTER_RE = re.compile(
    r"final bid was made by[^:]*:\s*</?[^>]*>?\s*([A-Za-z0-9 ,.&'\-]+?)\s*<", re.I)
AMOUNT_RE = re.compile(r"\$([\d,]+\.\d{2})")
# bid ladder row: bidderID, [type], $amount, timestamp
ROW_RE = re.compile(
    r"(\d{4,6})\D{0,40}?(Auto Bid|tied high bid|winning bid)?\D{0,40}?"
    r"\$([\d,]+\.\d{2})\D{0,40}?(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2} [AP]M)", re.I)

def num(s):
    return float(s.replace(",", "")) if s else None

def parse_lot(block, date_iso):
    """Extract winner + bid ladder from one auction block's HTML."""
    acct = (re.search(r"Parcel ID:\s*</?[^>]*>?\s*([0-9\-]+)", block) or [None, None])[1] \
        if "Parcel ID" in block else None
    case = (re.search(r"Case #:\s*</?[^>]*>?\s*([0-9A-Za-z\-]+)", block) or [None, None])[1] \
        if "Case #" in block else None
    sold = AMOUNT_RE.search(block.split("Amount")[-1][:120]) if "Amount" in block else None
    sold_amt = num(sold.group(1)) if sold else None
    fm = FOOTER_RE.search(block)
    winner = fm.group(1).strip() if fm else None
    bids, win_bidder = [], None
    for m in ROW_RE.finditer(block):
        bidder_id, btype, amt, ts = m.group(1), (m.group(2) or "").lower(), m.group(3), m.group(4)
        is_win = btype == "winning bid"
        if is_win:
            win_bidder = bidder_id
        bids.append({"auction_date": date_iso, "case_number": case, "account_number": acct,
                     "bidder_id": bidder_id, "bid_amount": num(amt),
                     "bid_type": btype or "manual",
                     "bid_ts": dt.datetime.strptime(ts, "%m/%d/%Y %I:%M:%S %p").isoformat(),
                     "is_winner": is_win})
    return {"account_number": acct, "case_number": case, "sold_amount": sold_amt,
            "winner_name": winner, "winner_bidder_id": win_bidder, "bids": bids}

if __name__ == "__main__":
    date_arg = sys.argv[2] if len(sys.argv) > 2 else dt.date.today().isoformat()
    d = dt.date.fromisoformat(date_arg)
    date_mdY = d.strftime("%m/%d/%Y")
    login()
    html = results_page(date_mdY)
    # split into per-lot blocks on the "Auction Sold/Closed" card boundary
    blocks = re.split(r"Auction (?:Sold|Closed|Canceled)", html)
    print(f"blocks: {len(blocks)-1}")
    all_bids, identities, events, lots = [], [], [], 0
    for blk in blocks[1:]:
        lot = parse_lot(blk, d.isoformat())
        if not lot["bids"] and not lot["winner_name"]:
            continue
        lots += 1
        all_bids += lot["bids"]
        if lot["winner_name"] and lot["winner_bidder_id"]:
            identities.append({"bidder_id": lot["winner_bidder_id"],
                               "resolved_name": lot["winner_name"],
                               "confidence": "footer_winner",
                               "first_seen": d.isoformat(), "last_seen": d.isoformat(),
                               "auctions_seen": 1, "wins": 1})
        if lot["winner_name"]:
            events.append({"county_slug": "brevard", "sale_type": SALE_TYPE,
                           "auction_date": d.isoformat(), "account_number": lot["account_number"],
                           "case_number": lot["case_number"], "event_type": "sold",
                           "amount": lot["sold_amount"], "winner_name": lot["winner_name"],
                           "winner_bidder_id": lot["winner_bidder_id"],
                           "event_ts": dt.datetime.now(dt.timezone.utc).isoformat()})
    if all_bids:
        rpc("upsert_brevard_bid_history", all_bids)
    if identities:
        rpc("upsert_brevard_bidder_identity", identities)
    if events:
        rpc("upsert_live_auction_events", events)
    print(f"lots={lots} bids={len(all_bids)} names={len(identities)} events={len(events)}")
    if lots == 0:
        print("WARNING: zero lots parsed -- results-page shape may differ when authenticated; "
              "first-run discovery: dumping raw to stderr head", file=sys.stderr)
        sys.stderr.write((html or "")[:2000])
        sys.exit(1)
