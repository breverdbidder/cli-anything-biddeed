#!/usr/bin/env python3
"""Shapira Formula V1 — Score all Brevard upcoming auctions + Telegram report"""
import requests, json, os, sys
from datetime import datetime, timedelta

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
TG_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
BASE = f"{SUPABASE_URL}/rest/v1"
H = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}

def tg(msg):
    if TG_BOT and TG_CHAT:
        try:
            # Split long messages
            for i in range(0, len(msg), 4000):
                requests.post(f"https://api.telegram.org/bot{TG_BOT}/sendMessage",
                    data={"chat_id": TG_CHAT, "text": msg[i:i+4000], "parse_mode": "Markdown"}, timeout=10)
        except Exception as e:
            print(f"Telegram error: {e}")

def shapira_score(just_value, opening_bid=None, sqft=0, year_built=0, luse_code="001"):
    """Shapira Formula V1: conservative foreclosure bidding"""
    if not just_value or just_value <= 0:
        return {"recommendation": "UNKNOWN", "max_bid": None, "bid_ratio": None, "color": "#6B7280"}
    
    # Base: 70% ARV minus rehab reserve minus closing costs
    rehab_reserve = min(25000, just_value * 0.15)
    max_bid = round(just_value * 0.70 - 10000 - rehab_reserve)
    if max_bid < 0: max_bid = 0
    
    # Age penalty
    if year_built and year_built > 1900:
        age = 2026 - year_built
        if age > 40: max_bid = round(max_bid * 0.90)
        elif age > 25: max_bid = round(max_bid * 0.95)
    
    # $/sqft sanity check — skip if < $50/sqft (likely data issue)
    if sqft and sqft > 0 and just_value / sqft < 50:
        return {"recommendation": "SKIP", "max_bid": max_bid, "bid_ratio": 0, "color": "#EF4444"}
    
    compare = opening_bid if opening_bid and opening_bid > 0 else just_value
    bid_ratio = round((max_bid / compare) * 100) if compare > 0 else 0
    
    is_res = luse_code and str(luse_code).zfill(3)[:2] == "00"
    
    if bid_ratio >= 75 and is_res:
        return {"recommendation": "BID", "max_bid": max_bid, "bid_ratio": bid_ratio, "color": "#22C55E"}
    elif bid_ratio >= 60:
        return {"recommendation": "REVIEW", "max_bid": max_bid, "bid_ratio": bid_ratio, "color": "#F59E0B"}
    else:
        return {"recommendation": "SKIP", "max_bid": max_bid, "bid_ratio": bid_ratio, "color": "#EF4444"}

# ── MAIN ──
print("=" * 60)
print("SHAPIRA FORMULA V1 — Brevard Auction Scoring")
print("=" * 60)

# Get upcoming Brevard auctions
today = datetime.now().strftime("%Y-%m-%d")
r = requests.get(f"{BASE}/multi_county_auctions", headers=H, timeout=30, params={
    "county": "ilike.%brevard%",
    "auction_status": "eq.upcoming",
    "auction_date": f"gte.{today}",
    "select": "id,case_number,auction_date,property_address,parcel_id,market_value,assessed_value,opening_bid,sqft,year_built,city,plaintiff",
    "order": "auction_date.asc",
    "limit": "500"
})
auctions = r.json()
print(f"Upcoming Brevard auctions: {len(auctions)}")

scored = {"BID": [], "REVIEW": [], "SKIP": [], "UNKNOWN": []}
updates = []

for a in auctions:
    jv = a.get("market_value") or 0
    ob = a.get("opening_bid")
    sqft = a.get("sqft") or 0
    yb = a.get("year_built") or 0
    
    # If no market value, try zw_parcels lookup
    if jv <= 0 and a.get("parcel_id"):
        pid = a["parcel_id"]
        r2 = requests.get(f"{BASE}/zw_parcels", headers=H, timeout=10, params={
            "co_no": "eq.15", "pin": f"eq.{pid}",
            "select": "val_market,sqft_heated,year_built,luse_code"
        })
        pdata = r2.json()
        if isinstance(pdata, list) and pdata:
            p = pdata[0]
            jv = p.get("val_market") or 0
            sqft = sqft or (p.get("sqft_heated") or 0)
            yb = yb or (p.get("year_built") or 0)
    
    # Determine land use from parcel
    luse = "001"  # default residential
    if a.get("parcel_id"):
        r3 = requests.get(f"{BASE}/zw_parcels", headers=H, timeout=10, params={
            "co_no": "eq.15", "pin": f"eq.{a['parcel_id']}",
            "select": "luse_code"
        })
        ldata = r3.json()
        if isinstance(ldata, list) and ldata:
            luse = ldata[0].get("luse_code", "001") or "001"
    
    result = shapira_score(jv, ob, sqft, yb, luse)
    rec = result["recommendation"]
    scored[rec].append({
        **a,
        "just_value": jv,
        "max_bid": result["max_bid"],
        "bid_ratio": result["bid_ratio"],
        "recommendation": rec,
        "luse_code": luse
    })
    
    # Prepare update for multi_county_auctions
    if result["max_bid"] is not None:
        updates.append({
            "id": a["id"],
            "market_value": jv if jv > 0 else None,
            "sqft": sqft if sqft > 0 else None,
            "year_built": yb if yb > 0 else None,
        })

# Update market values in multi_county_auctions
updated = 0
for u in updates:
    aid = u.pop("id")
    update_data = {k: v for k, v in u.items() if v is not None}
    if update_data:
        r4 = requests.patch(f"{BASE}/multi_county_auctions?id=eq.{aid}",
            headers={**H, "Prefer": "return=minimal"}, json=update_data, timeout=10)
        if r4.status_code in [200, 204]:
            updated += 1

print(f"\nUpdated {updated} auctions with market data")
print(f"\nResults: 🟢 BID={len(scored['BID'])} | 🟡 REVIEW={len(scored['REVIEW'])} | 🔴 SKIP={len(scored['SKIP'])} | ❓ UNKNOWN={len(scored['UNKNOWN'])}")

# ── TELEGRAM REPORT ──
lines = ["🏠 *SHAPIRA FORMULA V1 — Brevard Auctions*\n"]
lines.append(f"🟢 BID: {len(scored['BID'])} | 🟡 REVIEW: {len(scored['REVIEW'])} | 🔴 SKIP: {len(scored['SKIP'])}\n")

# Group by date
from collections import defaultdict
by_date = defaultdict(list)
for rec in ["BID", "REVIEW"]:
    for a in scored[rec]:
        by_date[a["auction_date"]].append(a)

for date in sorted(by_date.keys()):
    items = by_date[date]
    lines.append(f"\n📅 *{date}*")
    for a in sorted(items, key=lambda x: -(x.get("just_value") or 0)):
        icon = "🟢" if a["recommendation"] == "BID" else "🟡"
        jv = a.get("just_value", 0)
        mb = a.get("max_bid", 0)
        addr = (a.get("property_address") or "?")[:35]
        city = (a.get("city") or "")[:12]
        sqft = a.get("sqft") or 0
        lines.append(f"{icon} ${jv:,} → max ${mb:,} | {sqft}sqft | {addr}")

lines.append(f"\n_Scored {len(auctions)} auctions at {datetime.now().strftime('%I:%M %p')} EST_")

report = "\n".join(lines)
print(f"\n{report}")
tg(report)

print(f"\n{'=' * 60}")
print("SHAPIRA SCORING COMPLETE")
print(f"{'=' * 60}")
