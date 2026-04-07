#!/usr/bin/env python3
"""Owner OSINT Layer — Public Records Enrichment
Issue: https://github.com/breverdbidder/cli-anything-biddeed/issues/387

For each auction defendant, queries zw_parcels to build owner intelligence:
- Classification: DISTRESSED_HOMEOWNER | INVESTOR | CORPORATE | ESTATE | UNKNOWN
- Portfolio analysis: total value, parcel count, out-of-state flag
- Telegram summary of all classifications

Usage:
  python scripts/owner_osint.py                          # Brevard upcoming auctions
  python scripts/owner_osint.py --county duval           # specific county
  python scripts/owner_osint.py --county brevard --limit 50
"""
import requests, json, os, sys, argparse, re
from datetime import datetime, date

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
TG_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
BASE = f"{SUPABASE_URL}/rest/v1"
H = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}

CORPORATE_PATTERNS = re.compile(
    r'\b(LLC|INC|CORP|CORPORATION|COMPANY|CO\b|LTD|LP|HOLDINGS|PROPERTIES|'
    r'PARTNERS|PARTNERSHIP|VENTURES|ENTERPRISES|GROUP|CAPITAL|INVESTMENTS|'
    r'MANAGEMENT|DEVELOPMENT|REALTY|REAL ESTATE)\b',
    re.IGNORECASE
)
TRUST_PATTERNS = re.compile(r'\b(TRUST|TRUSTEE|TRUSTEESHIP|TR\b|REVOCABLE|IRREVOCABLE|LIVING TRUST)\b', re.IGNORECASE)
ESTATE_PATTERNS = re.compile(r'\b(ESTATE|DECEASED|DECEDENT|PERSONAL REP|PR OF)\b', re.IGNORECASE)


def tg(msg):
    if TG_BOT and TG_CHAT:
        try:
            for i in range(0, len(msg), 4000):
                requests.post(f"https://api.telegram.org/bot{TG_BOT}/sendMessage",
                    data={"chat_id": TG_CHAT, "text": msg[i:i+4000], "parse_mode": "Markdown"}, timeout=10)
        except Exception as e:
            print(f"Telegram error: {e}")


def normalize_name(name):
    """Normalize defendant name for matching against owner_name in zw_parcels."""
    if not name:
        return ""
    n = name.upper().strip()
    # Remove common legal suffixes that won't appear in property records
    n = re.sub(r'\b(ET\s*(AL|UX|VIR))\b', '', n)
    n = re.sub(r'\b(A/?K/?A|F/?K/?A|N/?K/?A)\b.*', '', n)  # strip AKA and everything after
    n = re.sub(r'[,;]+\s*$', '', n)  # trailing punctuation
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def extract_last_name(name):
    """Extract primary last name for fuzzy matching."""
    normalized = normalize_name(name)
    if not normalized:
        return ""
    # "SMITH, JOHN" → "SMITH"; "JOHN SMITH" → "SMITH"
    if "," in normalized:
        return normalized.split(",")[0].strip()
    parts = normalized.split()
    return parts[-1] if parts else ""


def extract_first_name(name):
    """Extract first name from defendant for fuzzy matching."""
    normalized = normalize_name(name)
    if not normalized:
        return ""
    if "," in normalized:
        after_comma = normalized.split(",", 1)[1].strip()
        parts = after_comma.split()
        return parts[0] if parts else ""
    parts = normalized.split()
    return parts[0] if len(parts) >= 2 else ""


# Known cities/places in Brevard County FL that collide with last names
BREVARD_CITIES = {
    "MELBOURNE", "PALM BAY", "TITUSVILLE", "COCOA", "VIERA",
    "MERRITT ISLAND", "SATELLITE BEACH", "ROCKLEDGE", "CAPE CANAVERAL",
    "INDIAN HARBOUR BEACH", "PALM", "MERRITT", "SATELLITE", "CAPE",
    "INDIAN", "HARBOUR", "INDIALANTIC", "GRANT", "MIMS", "SCOTTSMOOR",
    "SHARPES", "SUNTREE", "WEST MELBOURNE",
}

# Common FL cities that could collide
FL_CITIES = BREVARD_CITIES | {
    "ORLANDO", "JACKSONVILLE", "TAMPA", "MIAMI", "NAPLES",
    "KISSIMMEE", "DAYTONA", "CLEARWATER", "LAKELAND", "GAINESVILLE",
    "TALLAHASSEE", "PENSACOLA", "SARASOTA", "FORT LAUDERDALE",
    "OCALA", "DELTONA", "SANFORD", "APOPKA", "OCOEE",
}


def is_city_name(last_name):
    """Check if extracted last name matches a known FL city/place."""
    return last_name.upper() in FL_CITIES


def levenshtein(s1, s2):
    """Simple Levenshtein distance for short strings."""
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (c1 != c2)))
        prev = curr
    return prev[-1]


def classify_by_name(defendant):
    """Pre-classify based on defendant name patterns before DB lookup."""
    if not defendant:
        return None
    if ESTATE_PATTERNS.search(defendant):
        return "ESTATE"
    if CORPORATE_PATTERNS.search(defendant) or TRUST_PATTERNS.search(defendant):
        return "CORPORATE"
    return None


def compute_confidence(defendant, parcels, page_cap_hit):
    """Compute confidence score 0.0-1.0 for the classification.

    Factors:
    - Name length (longer = more specific = higher confidence)
    - First-name match strength (Levenshtein distance)
    - Page-cap hit (if we hit 500 cap, confidence drops)
    - Owner-state agreement across parcels
    """
    if not parcels:
        return 0.0

    score = 0.0
    last_name = extract_last_name(defendant)
    first_name = extract_first_name(defendant)

    # Factor 1: Last name length (0-0.25)
    # >= 6 chars = full credit, 4-5 = partial, < 4 = minimal
    if len(last_name) >= 6:
        score += 0.25
    elif len(last_name) >= 4:
        score += 0.15
    else:
        score += 0.05

    # Factor 2: First-name match in parcels (0-0.35)
    if first_name and len(first_name) >= 2:
        best_dist = 999
        for p in parcels:
            owner = (p.get("owner_name") or "").upper()
            # Extract first name from owner_name
            if "," in owner:
                after = owner.split(",", 1)[1].strip().split()[0] if "," in owner else ""
            else:
                parts = owner.split()
                after = parts[0] if len(parts) >= 2 else ""
            if after:
                dist = levenshtein(first_name, after)
                best_dist = min(best_dist, dist)
        if best_dist <= 0:
            score += 0.35
        elif best_dist <= 1:
            score += 0.25
        elif best_dist <= 2:
            score += 0.15
        else:
            score += 0.0  # No first-name match
    else:
        score += 0.0  # No first name to match

    # Factor 3: Page-cap NOT hit (0-0.2)
    if not page_cap_hit:
        score += 0.2
    else:
        score += 0.05  # Some credit — we still have data

    # Factor 4: Owner-state consistency (0-0.2)
    states = [p.get("owner_state") for p in parcels if p.get("owner_state")]
    if states:
        most_common = max(set(states), key=states.count)
        agreement = states.count(most_common) / len(states)
        score += 0.2 * agreement
    else:
        score += 0.1  # Neutral

    return round(min(score, 1.0), 3)


def classify_owner(defendant, parcels, confidence_score):
    """Classify defendant based on matched zw_parcels data.

    INVESTOR requires >= 3 parcels AND confidence_score >= 0.7.
    """
    # Name-based classification takes priority for ESTATE and CORPORATE
    name_class = classify_by_name(defendant)
    if name_class == "ESTATE":
        return "ESTATE"

    count = len(parcels)
    if count == 0:
        if name_class == "CORPORATE":
            return "CORPORATE"
        return "UNKNOWN"

    # Corporate/Trust entity
    if name_class == "CORPORATE":
        return "CORPORATE"

    # INVESTOR: >= 3 parcels AND confidence >= 0.7
    if count >= 3 and confidence_score >= 0.7:
        return "INVESTOR"

    # Single property with high confidence — check if homestead residential
    if count == 1:
        p = parcels[0]
        luse = str(p.get("luse_code") or "").zfill(4)
        is_residential = luse[:2] == "00"
        if is_residential:
            return "DISTRESSED_HOMEOWNER"

    return "UNKNOWN"


PAGE_SIZE = 200
MAX_PARCELS = 500


def _paginated_query(params):
    """Paginate PostgREST queries using Range header until exhausted, cap at MAX_PARCELS."""
    all_results = []
    offset = 0
    while offset < MAX_PARCELS:
        end = offset + PAGE_SIZE - 1
        hdrs = {**H, "Range": f"{offset}-{end}", "Prefer": "count=exact"}
        r = requests.get(f"{BASE}/zw_parcels", headers=hdrs, params=params, timeout=15)
        if r.status_code not in (200, 206):
            break
        batch = r.json() if isinstance(r.json(), list) else []
        if not batch:
            break
        all_results.extend(batch)
        if len(batch) < PAGE_SIZE:
            break  # Last page
        offset += PAGE_SIZE
    return all_results[:MAX_PARCELS]


def lookup_parcels(defendant, county, co_no):
    """Query zw_parcels for all parcels owned by this defendant name.

    Returns (parcels, page_cap_hit) tuple.
    Rejects defendants whose last name is a known FL city (< 4 chars or city match).
    """
    normalized = normalize_name(defendant)
    if not normalized:
        return [], False

    last_name = extract_last_name(defendant)

    # Reject if last name too short (< 4 chars) — too many collisions
    if len(last_name) < 4:
        return [], False

    # Reject if last name is a known city/place
    if is_city_name(last_name):
        return [], False

    select_cols = ("pin,site_addr,site_city,val_market,luse_code,luse_desc,"
                   "owner_name,owner_state,owner_zip,sale_date,sale_price,"
                   "sqft_heated,year_built,zoning_code,acres_deed")

    # Try exact match first (most reliable)
    params = {
        "select": select_cols,
        "owner_name": f"ilike.{normalized}",
        "co_no": f"eq.{co_no}",
    }
    results = _paginated_query(params)

    # If no exact match, try last-name match
    if not results:
        if last_name and len(last_name) >= 4:
            params["owner_name"] = f"ilike.{last_name}%"
            candidates = _paginated_query(params)
            # Filter: last name must match beginning of owner_name
            results = [p for p in candidates if (p.get("owner_name") or "").upper().startswith(last_name)]

    page_cap_hit = len(results) >= MAX_PARCELS
    return results, page_cap_hit


def build_portfolio(parcels):
    """Build portfolio summary from matched parcels."""
    if not parcels:
        return {"total_value": 0, "is_out_of_state": False, "owner_state": None,
                "last_sale_date": None, "days_since_last_sale": None, "is_homestead": False}

    total_value = sum(p.get("val_market") or 0 for p in parcels)
    states = [p.get("owner_state") for p in parcels if p.get("owner_state")]
    owner_state = states[0] if states else None
    is_out_of_state = owner_state is not None and owner_state.upper() != "FL"

    sale_dates = []
    for p in parcels:
        sd = p.get("sale_date")
        if sd:
            try:
                sale_dates.append(datetime.strptime(str(sd)[:10], "%Y-%m-%d").date())
            except (ValueError, TypeError):
                pass

    last_sale = max(sale_dates) if sale_dates else None
    days_since = (date.today() - last_sale).days if last_sale else None

    # Homestead: any residential parcel (luse_code 00xx)
    is_homestead = any(
        str(p.get("luse_code") or "").zfill(4)[:2] == "00"
        for p in parcels
    )

    return {
        "total_value": total_value,
        "is_out_of_state": is_out_of_state,
        "owner_state": owner_state,
        "last_sale_date": str(last_sale) if last_sale else None,
        "days_since_last_sale": days_since,
        "is_homestead": is_homestead,
    }


# County number lookup
COUNTY_MAP = {
    "brevard": 15, "orange": 48, "duval": 16, "volusia": 64,
    "seminole": 59, "osceola": 49, "lake": 35, "polk": 53,
    "hillsborough": 29, "pinellas": 52, "palm beach": 50,
    "broward": 6, "miami-dade": 13, "lee": 36, "sarasota": 58,
    "manatee": 41, "collier": 11, "alachua": 1, "leon": 37,
    "escambia": 17, "marion": 42, "pasco": 51, "st. lucie": 56,
}


def get_co_no(county):
    return COUNTY_MAP.get(county.lower(), 15)


def main():
    parser = argparse.ArgumentParser(description="Owner OSINT — classify auction defendants via zw_parcels")
    parser.add_argument("--county", default="brevard", help="County name (default: brevard)")
    parser.add_argument("--limit", type=int, default=500, help="Max auctions to process")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing to DB")
    args = parser.parse_args()

    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_SERVICE_KEY not set")
        sys.exit(1)

    county = args.county.lower()
    co_no = get_co_no(county)
    today = datetime.now().strftime("%Y-%m-%d")

    print("=" * 60)
    print(f"OWNER OSINT — {county.title()} County Defendant Classification")
    print("=" * 60)

    # Step 1: Fetch upcoming auction defendants from fl_auctions
    r = requests.get(f"{BASE}/fl_auctions", headers=H, timeout=30, params={
        "county": f"ilike.%{county}%",
        "status": "eq.SCHEDULED",
        "auction_date": f"gte.{today}",
        "select": "id,case_number,auction_date,defendant,plaintiff,judgment_amount,parcel_id,address",
        "order": "auction_date.asc",
        "limit": str(args.limit)
    })

    if r.status_code != 200:
        print(f"ERROR fetching fl_auctions: {r.status_code} {r.text[:200]}")
        sys.exit(1)

    auctions = r.json()
    if not isinstance(auctions, list):
        print(f"ERROR: unexpected response: {str(auctions)[:200]}")
        sys.exit(1)

    # Fallback: also try multi_county_auctions if fl_auctions empty
    if not auctions:
        print("No fl_auctions found, trying multi_county_auctions...")
        r2 = requests.get(f"{BASE}/multi_county_auctions", headers=H, timeout=30, params={
            "county": f"ilike.%{county}%",
            "auction_status": "eq.upcoming",
            "auction_date": f"gte.{today}",
            "select": "id,case_number,auction_date,property_address,plaintiff,parcel_id",
            "order": "auction_date.asc",
            "limit": str(args.limit)
        })
        if r2.status_code == 200 and isinstance(r2.json(), list):
            auctions = r2.json()

    print(f"Found {len(auctions)} upcoming auctions with defendants")

    if not auctions:
        print("No auctions found. Nothing to classify.")
        tg(f"🔍 *Owner OSINT — {county.title()}*\nNo upcoming auctions found.")
        return

    # Step 2: Classify each defendant
    results = {"DISTRESSED_HOMEOWNER": [], "INVESTOR": [], "CORPORATE": [], "ESTATE": [], "UNKNOWN": []}
    intel_records = []

    for i, a in enumerate(auctions):
        defendant = a.get("defendant") or ""
        if not defendant:
            continue

        # Skip defendants whose name IS a known city (no useful data)
        last_name = extract_last_name(defendant)
        if is_city_name(last_name) or len(last_name) < 4:
            continue

        case_number = a.get("case_number", "")
        auction_date = a.get("auction_date")
        plaintiff = a.get("plaintiff")
        judgment = a.get("judgment_amount")

        # Lookup parcels owned by defendant
        parcels, page_cap_hit = lookup_parcels(defendant, county, co_no)
        confidence = compute_confidence(defendant, parcels, page_cap_hit)
        classification = classify_owner(defendant, parcels, confidence)
        portfolio = build_portfolio(parcels)

        # Build compact parcel summaries for JSONB storage
        parcel_summaries = [
            {
                "pin": p.get("pin"),
                "addr": p.get("site_addr"),
                "city": p.get("site_city"),
                "val": p.get("val_market"),
                "luse": p.get("luse_code"),
                "sqft": p.get("sqft_heated"),
                "year": p.get("year_built"),
                "zoning": p.get("zoning_code"),
            }
            for p in parcels
        ]

        record = {
            "auction_id": a.get("id"),
            "case_number": case_number,
            "county": county,
            "defendant": defendant,
            "classification": classification,
            "match_count": len(parcels),
            "total_portfolio_value": portfolio["total_value"],
            "parcels_owned": json.dumps(parcel_summaries),
            "is_homestead": portfolio["is_homestead"],
            "is_out_of_state": portfolio["is_out_of_state"],
            "is_corporate": bool(CORPORATE_PATTERNS.search(defendant) or TRUST_PATTERNS.search(defendant)),
            "owner_state": portfolio["owner_state"],
            "last_sale_date": portfolio["last_sale_date"],
            "days_since_last_sale": portfolio["days_since_last_sale"],
            "auction_date": auction_date,
            "judgment_amount": judgment,
            "plaintiff": plaintiff,
            "confidence_score": confidence,
        }
        intel_records.append(record)
        results[classification].append({"defendant": defendant, "case": case_number, "parcels": len(parcels),
                                         "value": portfolio["total_value"], "state": portfolio["owner_state"]})

        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(auctions)} defendants...")

    # Step 3: Upsert to auction_owner_intel
    upserted = 0
    if not args.dry_run:
        for rec in intel_records:
            r = requests.post(
                f"{BASE}/auction_owner_intel",
                headers={**H, "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=rec, timeout=10
            )
            if r.status_code in [200, 201, 204]:
                upserted += 1
            else:
                print(f"  WARN: upsert failed for {rec['defendant']}: {r.status_code}")

    # Step 4: Print summary
    total = len(intel_records)
    print(f"\n{'=' * 60}")
    print(f"CLASSIFICATION RESULTS — {county.title()} County")
    print(f"{'=' * 60}")
    print(f"Total defendants: {total}")
    for cls in ["DISTRESSED_HOMEOWNER", "INVESTOR", "CORPORATE", "ESTATE", "UNKNOWN"]:
        count = len(results[cls])
        pct = round(count / total * 100) if total else 0
        print(f"  {cls}: {count} ({pct}%)")

    if not args.dry_run:
        print(f"\nUpserted {upserted}/{total} records to auction_owner_intel")
    else:
        print("\n[DRY RUN] No records written to DB")

    # Show top investors
    investors = sorted(results["INVESTOR"], key=lambda x: -x["value"])
    if investors:
        print(f"\n📊 TOP INVESTORS:")
        for inv in investors[:10]:
            print(f"  {inv['defendant'][:40]} — {inv['parcels']} parcels, ${inv['value']:,} portfolio")

    # Step 5: Telegram summary
    lines = [f"🔍 *Owner OSINT — {county.title()} County*\n"]
    lines.append(f"Defendants classified: {total}")
    for cls, emoji in [("DISTRESSED_HOMEOWNER", "🏠"), ("INVESTOR", "💰"), ("CORPORATE", "🏢"),
                        ("ESTATE", "⚰️"), ("UNKNOWN", "❓")]:
        count = len(results[cls])
        lines.append(f"{emoji} {cls}: {count}")

    if investors:
        lines.append(f"\n*Top Investors:*")
        for inv in investors[:5]:
            lines.append(f"  💰 {inv['defendant'][:30]} — {inv['parcels']}x ${inv['value']:,}")

    out_of_state = sum(1 for r in intel_records if r.get("is_out_of_state"))
    if out_of_state:
        lines.append(f"\n🌎 Out-of-state owners: {out_of_state}")

    lines.append(f"\n_Processed at {datetime.now().strftime('%I:%M %p')} EST_")
    report = "\n".join(lines)
    print(f"\n{report}")
    tg(report)


if __name__ == "__main__":
    main()
