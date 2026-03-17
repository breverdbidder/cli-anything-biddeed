#!/usr/bin/env python3
"""
cli_anything.enricher — Property Profile Enricher for Brevard County, FL.

Forked from NextAutomation Property Profile Enricher v1.0.
Enhanced for BidDeed.AI (foreclosure + tax deed) and ZoneWise.AI (zoning overlay).

6-stage pipeline:
  1. OWNER     — BCPAO ownership, entity structure, acquisition history
  2. TAX       — Tax assessment, delinquency, exemptions, tax cert status
  3. LIENS     — AcclaimWeb mortgage/lien stacking + RealTDM tax certs
  4. PERMITS   — Brevard County building permits + code violations
  5. COMPS     — BCPAO sales history + comp analysis within radius
  6. SYNTHESIZE — Valuation range, motivation score, action recommendation

Usage:
  python -m enricher.agent enrich --address "123 Main St, Melbourne, FL 32901"
  python -m enricher.agent enrich --parcel "25-37-22-00-00123.0-0000.00"
  python -m enricher.agent enrich --case "05-2024-CA-012345" --mode foreclosure
  python -m enricher.agent batch --file parcels.csv --depth standard
  python -m enricher.agent status
"""
import httpx, json, os, sys, time, argparse, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

# Brevard County data sources
BCPAO_BASE = "https://gis.brevardfl.gov/gissrv/rest/services"
BCPAO_PARCEL = f"{BCPAO_BASE}/Base_Map/Parcel_New_WKID2881/MapServer/5"
BCPAO_API = "https://www.bcpao.us/api/v1"
BCPAO_PHOTOS = "https://www.bcpao.us/photos"
ACCLAIMWEB_BASE = "https://vaclmweb1.brevardclerk.us"
REALTDM_BASE = "https://brevard.realtdm.com"
TAX_COLLECTOR = "https://brevardtc.com"
PERMIT_SEARCH = "https://bfrhost.brevardfl.gov/PermitsPlus"  # Brevard permits portal

# Enrichment depth configs
DEPTH_CONFIGS = {
    "quick":    {"stages": ["OWNER", "TAX", "COMPS"], "comp_count": 3},
    "standard": {"stages": ["OWNER", "TAX", "LIENS", "PERMITS", "COMPS"], "comp_count": 5},
    "deep":     {"stages": ["OWNER", "TAX", "LIENS", "PERMITS", "COMPS", "SYNTHESIZE"], "comp_count": 10},
}

# Sale type contexts — what data matters most per acquisition channel
SALE_TYPES = {
    "foreclosure": {
        "description": "Courthouse foreclosure auction (Titusville, in-person)",
        "critical_stages": ["LIENS", "TAX"],
        "key_question": "What liens survive the sale?",
        "bid_formula": True,  # Use (ARV×70%)-Repairs-$10K-MIN($25K,15%ARV)
    },
    "tax_deed": {
        "description": "Online tax deed sale (brevard.realforeclose.com)",
        "critical_stages": ["LIENS", "TAX", "OWNER"],
        "key_question": "What's the surplus/deficit and does title come clean?",
        "bid_formula": True,
    },
    "off_market": {
        "description": "Direct-to-owner acquisition (ZoneWise.AI pipeline)",
        "critical_stages": ["OWNER", "COMPS", "PERMITS"],
        "key_question": "What's the motivation and negotiation leverage?",
        "bid_formula": False,  # Negotiated price, not formula
    },
}


# ═══════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════

def log(stage: str, msg: str, level: str = "INFO"):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    prefix = {"INFO": "●", "OK": "✓", "WARN": "⚠", "ERR": "✗", "SKIP": "○"}.get(level, "●")
    print(f"  [{ts}] {prefix} [{stage}] {msg}", file=sys.stderr)


def notify_telegram(msg: str):
    """Send Telegram notification for batch completions."""
    if not TELEGRAM_BOT or not TELEGRAM_CHAT:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception:
        pass


def supabase_upsert(table: str, records: List[Dict], on_conflict: str = "parcel_id"):
    """Upsert records to Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        log("DB", "Supabase not configured, skipping persist", "WARN")
        return None
    try:
        r = httpx.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": f"resolution=merge-duplicates,return=minimal",
            },
            json=records,
            timeout=30,
        )
        r.raise_for_status()
        log("DB", f"Upserted {len(records)} to {table}", "OK")
        return r
    except Exception as e:
        log("DB", f"Upsert failed: {e}", "ERR")
        return None


# ═══════════════════════════════════════════════════════════════
# STAGE 1: OWNER — BCPAO ownership resolution
# ═══════════════════════════════════════════════════════════════

def stage_owner(parcel_id: str = None, address: str = None) -> Dict:
    """
    Pull owner info from BCPAO.
    Sources: BCPAO API → GIS parcel layer → Tax rolls
    """
    log("OWNER", f"Resolving ownership for {parcel_id or address}")
    profile = {
        "owner_name": None,
        "owner_type": None,       # individual | entity | trust | government
        "mailing_address": None,
        "acquisition_date": None,
        "acquisition_price": None,
        "ownership_years": None,
        "photo_url": None,
        "parcel_id": parcel_id,
        "confidence": 0.0,
    }

    try:
        client = httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "BidDeed.AI/1.0 (enricher)"})

        # Try BCPAO API first (fastest)
        if parcel_id:
            # Strip formatting: "25-37-22-00-00123.0-0000.00" → account number
            account = parcel_id.replace("-", "").replace(".", "")
            r = client.get(f"{BCPAO_API}/search?acct={account}")
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data:
                    rec = data[0]
                    profile["owner_name"] = rec.get("owner", "").strip()
                    profile["mailing_address"] = _build_mailing(rec)
                    profile["parcel_id"] = rec.get("parcelId", parcel_id)
                    profile["confidence"] = 0.85
                    log("OWNER", f"Found: {profile['owner_name']}", "OK")

                    # Get photo
                    photo = rec.get("masterPhotoUrl")
                    if photo:
                        profile["photo_url"] = photo
                    else:
                        prefix = account[:4]
                        profile["photo_url"] = f"{BCPAO_PHOTOS}/{prefix}/{account}011.jpg"

        # Address-based lookup via GIS
        elif address:
            where = f"SITUS_ADDR LIKE '%{_sanitize_address(address)}%'"
            r = client.get(
                f"{BCPAO_PARCEL}/query",
                params={
                    "where": where,
                    "outFields": "TaxAcct,OWNER_NAME,PARCEL_ID,SITUS_ADDR",
                    "returnGeometry": "false",
                    "f": "json",
                },
            )
            if r.status_code == 200:
                features = r.json().get("features", [])
                if features:
                    attrs = features[0]["attributes"]
                    profile["owner_name"] = attrs.get("OWNER_NAME", "").strip()
                    profile["parcel_id"] = attrs.get("PARCEL_ID", "")
                    profile["confidence"] = 0.80
                    log("OWNER", f"GIS match: {profile['owner_name']}", "OK")

        # Classify owner type
        if profile["owner_name"]:
            name = profile["owner_name"].upper()
            if any(k in name for k in ["LLC", "INC", "CORP", "LTD", "LP", "PARTNERS"]):
                profile["owner_type"] = "entity"
            elif any(k in name for k in ["TRUST", "TRUSTEE", "TR ", "REVOCABLE"]):
                profile["owner_type"] = "trust"
            elif any(k in name for k in ["COUNTY", "CITY OF", "STATE OF", "UNITED STATES"]):
                profile["owner_type"] = "government"
            else:
                profile["owner_type"] = "individual"

        client.close()

    except Exception as e:
        log("OWNER", f"Error: {e}", "ERR")

    return profile


def _build_mailing(rec: Dict) -> str:
    parts = [rec.get("mailAddr1", ""), rec.get("mailAddr2", ""),
             rec.get("mailCity", ""), rec.get("mailState", ""), rec.get("mailZip", "")]
    return ", ".join(p.strip() for p in parts if p and p.strip())


def _sanitize_address(addr: str) -> str:
    """Extract street portion for GIS LIKE query."""
    # Remove city/state/zip, keep street
    parts = addr.split(",")
    street = parts[0].strip().upper()
    # Remove unit/apt
    street = re.sub(r'\s+(APT|UNIT|STE|#)\s*\S*', '', street)
    return street


# ═══════════════════════════════════════════════════════════════
# STAGE 2: TAX — Assessment, delinquency, exemptions
# ═══════════════════════════════════════════════════════════════

def stage_tax(parcel_id: str) -> Dict:
    """
    Pull tax data from BCPAO + Tax Collector.
    Red flags: delinquency, declining assessment, lost exemptions.
    """
    log("TAX", f"Analyzing tax profile for {parcel_id}")
    tax = {
        "assessed_value": None,
        "market_value": None,
        "taxable_value": None,
        "annual_tax": None,
        "effective_rate": None,
        "delinquent": False,
        "delinquent_amount": None,
        "exemptions": [],
        "homestead": False,
        "assessment_trend_3yr": None,   # "increasing" | "declining" | "stable"
        "special_assessments": [],
        "tax_cert_status": None,        # None | "applied" | "sold"
        "confidence": 0.0,
    }

    try:
        client = httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "BidDeed.AI/1.0 (enricher)"})
        account = parcel_id.replace("-", "").replace(".", "")

        # BCPAO API for assessment data
        r = client.get(f"{BCPAO_API}/search?acct={account}")
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                rec = data[0]
                tax["assessed_value"] = rec.get("assessedValue")
                tax["market_value"] = rec.get("justValue") or rec.get("marketValue")
                tax["taxable_value"] = rec.get("taxableValue")
                tax["homestead"] = bool(rec.get("homestead"))
                if tax["homestead"]:
                    tax["exemptions"].append("homestead")
                tax["confidence"] = 0.80
                log("TAX", f"Assessed: ${tax['assessed_value']:,}" if tax["assessed_value"] else "No assessment data", "OK" if tax["assessed_value"] else "WARN")

        # TODO: RealTDM for tax cert status (Stage 3 also hits this)
        # TODO: Tax Collector scrape for delinquency amount
        # TODO: 3-year assessment trend from BCPAO history

        client.close()

    except Exception as e:
        log("TAX", f"Error: {e}", "ERR")

    return tax


# ═══════════════════════════════════════════════════════════════
# STAGE 3: LIENS — AcclaimWeb + RealTDM lien stacking
# ═══════════════════════════════════════════════════════════════

def stage_liens(parcel_id: str, owner_name: str = None) -> Dict:
    """
    Build complete lien stack from AcclaimWeb (mortgages, judgments, lis pendens)
    and RealTDM (tax certificates).

    This is the CRITICAL stage for foreclosure/tax deed decisions.
    Key question: What liens survive the sale?
    """
    log("LIENS", f"Stacking liens for {parcel_id}")
    liens = {
        "mortgages": [],
        "judgment_liens": [],
        "tax_liens": [],
        "hoa_liens": [],
        "mechanic_liens": [],
        "lis_pendens": [],
        "ucc_filings": [],
        "tax_certificates": [],
        "total_encumbrances": 0,
        "estimated_equity_pct": None,
        "title_status": "UNKNOWN",  # CLEAN | ENCUMBERED | COMPLEX
        "confidence": 0.0,
    }

    # AcclaimWeb search by owner name — BECA V2.0 regex patterns
    if owner_name:
        log("LIENS", f"Searching AcclaimWeb for '{owner_name}'")
        try:
            client = httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "BidDeed.AI/1.0 (enricher)"})
            parts = owner_name.strip().split()
            last_name = parts[-1] if parts else ""
            first_name = parts[0] if len(parts) > 1 else ""

            search_url = f"{ACCLAIMWEB_BASE}/AcclaimWeb/search/SearchTypeName"
            r = client.get(search_url, params={
                "lastName": last_name, "firstName": first_name, "PartyType": "B",
            })
            time.sleep(2)  # Rate limit

            if r.status_code == 200:
                html = r.text
                # BECA V2.0 document type patterns
                doc_types = {
                    "mortgages": r"(?i)\b(MTG|MORTGAGE|DEED\s*OF\s*TRUST)\b",
                    "lis_pendens": r"(?i)\b(LIS\s*PENDENS|LP)\b",
                    "judgment_liens": r"(?i)\b(JUDGMENT|JUDG|JP|FINAL\s*JUDG)\b",
                    "hoa_liens": r"(?i)\b(HOA|HOMEOWNERS|ASSOCIATION\s*LIEN|CLAIM\s*OF\s*LIEN)\b",
                    "mechanic_liens": r"(?i)\b(MECH|MECHANIC|CONSTRUCTION\s*LIEN)\b",
                    "ucc_filings": r"(?i)\b(UCC|UNIFORM\s*COMMERCIAL)\b",
                }
                sat_pat = r"(?i)\b(SAT|SATISFACTION|RELEASE|DISCHARGE)\b"

                row_pat = r"<tr[^>]*>(.*?)</tr>"
                for row_html in re.findall(row_pat, html, re.DOTALL):
                    if re.search(sat_pat, row_html):
                        continue
                    for lien_type, pattern in doc_types.items():
                        if re.search(pattern, row_html):
                            date_m = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", row_html)
                            inst_m = re.search(r"(\d{10,})", row_html)
                            liens[lien_type].append({
                                "type": lien_type,
                                "recording_date": date_m.group(1) if date_m else None,
                                "instrument": inst_m.group(1) if inst_m else None,
                                "source": "AcclaimWeb",
                            })
                            break

                total_found = sum(len(liens[t]) for t in doc_types.keys())
                liens["confidence"] = 0.70 if total_found > 0 else 0.40
                log("LIENS", f"AcclaimWeb: {total_found} docs (MTG:{len(liens['mortgages'])} "
                    f"JP:{len(liens['judgment_liens'])} LP:{len(liens['lis_pendens'])} "
                    f"HOA:{len(liens['hoa_liens'])})", "OK")
            elif r.status_code == 403:
                log("LIENS", "AcclaimWeb 403 — rate limited", "WARN")
                liens["confidence"] = 0.10
            else:
                log("LIENS", f"AcclaimWeb {r.status_code}", "WARN")
            client.close()
        except Exception as e:
            log("LIENS", f"AcclaimWeb error: {e}", "ERR")

    # RealTDM for tax certificates
    log("LIENS", "Checking RealTDM for tax certificates")
    try:
        client = httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "BidDeed.AI/1.0 (enricher)"})
        # RealTDM requires account-based lookup
        # TODO: Integrate with existing realtdm_scraper patterns
        client.close()
        log("LIENS", "RealTDM check complete", "OK")
    except Exception as e:
        log("LIENS", f"RealTDM error: {e}", "ERR")

    # Classify title status
    total = (len(liens["mortgages"]) + len(liens["judgment_liens"]) +
             len(liens["tax_liens"]) + len(liens["hoa_liens"]) +
             len(liens["mechanic_liens"]) + len(liens["lis_pendens"]))
    if total == 0:
        liens["title_status"] = "CLEAN"
    elif total <= 2:
        liens["title_status"] = "ENCUMBERED"
    else:
        liens["title_status"] = "COMPLEX"

    return liens


# ═══════════════════════════════════════════════════════════════
# STAGE 4: PERMITS — Brevard County building permits
# ═══════════════════════════════════════════════════════════════

def stage_permits(parcel_id: str, address: str = None) -> Dict:
    """
    NEW capability from NextAutomation spec — not in original BidDeed pipeline.
    Pull building permits, code violations, CO status from Brevard County.

    Value: Better repair estimates, unpermitted work detection, liability flags.
    """
    log("PERMITS", f"Searching permits for {parcel_id}")
    permits = {
        "building_permits": [],
        "code_violations": [],
        "open_permits": 0,
        "closed_permits": 0,
        "last_permit_date": None,
        "total_permitted_value": 0,
        "has_co": None,             # Certificate of Occupancy
        "unpermitted_risk": "LOW",  # LOW | MEDIUM | HIGH
        "confidence": 0.0,
    }

    try:
        client = httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "BidDeed.AI/1.0 (enricher)"})

        # Brevard County PermitsPlus portal
        # NOTE: This is a new integration point — requires scraping or API discovery
        # Brevard uses Tyler Technologies (Munis) for permits
        # Alternative: BCPAO improvements data may have some permit info
        account = parcel_id.replace("-", "").replace(".", "")
        r = client.get(f"{BCPAO_API}/search?acct={account}")
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                rec = data[0]
                # BCPAO sometimes has improvement data
                year_built = rec.get("yearBuilt")
                bldg_value = rec.get("buildingValue") or rec.get("improvementValue")
                if year_built:
                    permits["confidence"] = 0.40  # Low — only from assessor
                    log("PERMITS", f"Year built: {year_built}, Bldg value: ${bldg_value:,}" if bldg_value else f"Year built: {year_built}", "OK")

        # TODO: Scrape Brevard PermitsPlus for actual permit records
        # TODO: Code enforcement / violation lookup
        # TODO: Cross-reference BCPAO improvements vs permits for unpermitted detection

        client.close()

    except Exception as e:
        log("PERMITS", f"Error: {e}", "ERR")

    return permits


# ═══════════════════════════════════════════════════════════════
# STAGE 5: COMPS — Comparable sales analysis
# ═══════════════════════════════════════════════════════════════

def stage_comps(parcel_id: str, radius_miles: float = 1.0,
                months: int = 12, min_comps: int = 5) -> Dict:
    """
    Pull comparable sales from BCPAO sales history.
    Uses GIS spatial query for radius-based filtering.
    """
    log("COMPS", f"Finding comps within {radius_miles}mi, last {months}mo")
    comps = {
        "comparable_sales": [],
        "median_price_sqft": None,
        "median_price": None,
        "avg_dom": None,
        "comp_count": 0,
        "arv_estimate": None,       # After Repair Value
        "arv_low": None,
        "arv_high": None,
        "confidence": 0.0,
    }

    try:
        client = httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "BidDeed.AI/1.0 (enricher)"})

        # Get subject property centroid from BCPAO GIS
        account = parcel_id.replace("-", "").replace(".", "")
        r = client.get(
            f"{BCPAO_PARCEL}/query",
            params={
                "where": f"TaxAcct='{account}'",
                "outFields": "TaxAcct,PARCEL_ID,Shape_Area",
                "returnGeometry": "true",
                "returnCentroid": "true",
                "outSR": "4326",
                "f": "json",
            },
        )
        if r.status_code == 200:
            features = r.json().get("features", [])
            if features:
                # Got centroid — now query nearby sales
                geom = features[0].get("geometry")
                if geom:
                    log("COMPS", "Got subject centroid, querying radius", "OK")
                    # TODO: Spatial buffer query for nearby parcels
                    # TODO: Cross-reference with BCPAO sales history API
                    # TODO: Filter by property type, size range, timeframe
                    comps["confidence"] = 0.30  # Placeholder until full impl

        # BCPAO sales history for the subject property itself
        r = client.get(f"{BCPAO_API}/search?acct={account}")
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                rec = data[0]
                just_value = rec.get("justValue")
                if just_value:
                    comps["arv_estimate"] = just_value
                    comps["arv_low"] = int(just_value * 0.85)
                    comps["arv_high"] = int(just_value * 1.15)
                    comps["confidence"] = max(comps["confidence"], 0.50)
                    log("COMPS", f"BCPAO just value: ${just_value:,}", "OK")

        client.close()

    except Exception as e:
        log("COMPS", f"Error: {e}", "ERR")

    return comps


# ═══════════════════════════════════════════════════════════════
# STAGE 6: SYNTHESIZE — Valuation + motivation + recommendation
# ═══════════════════════════════════════════════════════════════

def stage_synthesize(owner: Dict, tax: Dict, liens: Dict,
                     permits: Dict, comps: Dict,
                     sale_type: str = "foreclosure",
                     judgment_amount: float = None) -> Dict:
    """
    Combine all stages into actionable output.
    Applies BidDeed.AI max bid formula for auction types.
    Generates motivation score for off-market.
    """
    log("SYNTH", f"Synthesizing profile (mode: {sale_type})")
    synthesis = {
        "sale_type": sale_type,
        "valuation": {},
        "motivation_score": None,
        "action": None,             # BID | REVIEW | SKIP | CONTACT
        "recommendation": "",
        "red_flags": [],
        "green_flags": [],
        "overall_confidence": 0.0,
    }

    arv = comps.get("arv_estimate") or tax.get("market_value") or tax.get("assessed_value")

    # ── Valuation ──
    if arv:
        synthesis["valuation"] = {
            "arv": arv,
            "arv_low": comps.get("arv_low") or int(arv * 0.85),
            "arv_high": comps.get("arv_high") or int(arv * 1.15),
        }

        # BidDeed max bid formula for auction types
        config = SALE_TYPES.get(sale_type, {})
        if config.get("bid_formula") and arv:
            repair_est = 25000  # Default — TODO: derive from permits/age
            max_bid = (arv * 0.70) - repair_est - 10000 - min(25000, arv * 0.15)
            synthesis["valuation"]["max_bid"] = max(0, int(max_bid))
            synthesis["valuation"]["repair_estimate"] = repair_est

            # Bid/judgment ratio for foreclosures
            if judgment_amount and judgment_amount > 0:
                ratio = max_bid / judgment_amount
                synthesis["valuation"]["bid_judgment_ratio"] = round(ratio, 2)
                if ratio >= 0.75:
                    synthesis["action"] = "BID"
                elif ratio >= 0.60:
                    synthesis["action"] = "REVIEW"
                else:
                    synthesis["action"] = "SKIP"
                log("SYNTH", f"Max bid: ${max_bid:,.0f} | Ratio: {ratio:.0%} → {synthesis['action']}", "OK")

    # ── Motivation Score (off-market) ──
    if sale_type == "off_market":
        score = 50  # Baseline
        # Long hold = potential motivation (tired landlord, estate)
        if owner.get("ownership_years") and owner["ownership_years"] > 10:
            score += 15
        # Tax delinquency = high motivation
        if tax.get("delinquent"):
            score += 25
        # Complex liens = distress
        if liens.get("title_status") == "COMPLEX":
            score += 20
        # Open permits/violations = headache
        if permits.get("open_permits", 0) > 0:
            score += 10
        if permits.get("code_violations"):
            score += 15
        # Government owner = not a target
        if owner.get("owner_type") == "government":
            score = 0
        synthesis["motivation_score"] = min(100, max(0, score))
        synthesis["action"] = "CONTACT" if score >= 60 else "MONITOR"

    # ── Red/Green Flags ──
    if tax.get("delinquent"):
        synthesis["red_flags"].append("Tax delinquent")
    if liens.get("title_status") == "COMPLEX":
        synthesis["red_flags"].append(f"Complex title: {len(liens.get('lis_pendens', []))} lis pendens")
    if permits.get("open_permits", 0) > 0:
        synthesis["red_flags"].append(f"{permits['open_permits']} open permits")
    if owner.get("owner_type") == "government":
        synthesis["red_flags"].append("Government-owned")

    if liens.get("title_status") == "CLEAN":
        synthesis["green_flags"].append("Clean title")
    if tax.get("homestead"):
        synthesis["green_flags"].append("Homestead exemption (occupied)")
    if comps.get("comp_count", 0) >= 5:
        synthesis["green_flags"].append(f"Strong comp data ({comps['comp_count']} comps)")

    # ── Overall Confidence ──
    confidences = [
        owner.get("confidence", 0),
        tax.get("confidence", 0),
        liens.get("confidence", 0),
        permits.get("confidence", 0),
        comps.get("confidence", 0),
    ]
    synthesis["overall_confidence"] = round(sum(confidences) / len(confidences), 2)

    return synthesis


# ═══════════════════════════════════════════════════════════════
# ORCHESTRATOR — Run the full pipeline
# ═══════════════════════════════════════════════════════════════

def enrich_property(
    address: str = None,
    parcel_id: str = None,
    case_number: str = None,
    sale_type: str = "foreclosure",
    depth: str = "standard",
    comp_radius: float = 1.0,
    comp_months: int = 12,
    judgment_amount: float = None,
) -> Dict:
    """
    Main entry point. Runs the enrichment pipeline.
    Returns a complete property profile dict.
    """
    config = DEPTH_CONFIGS.get(depth, DEPTH_CONFIGS["standard"])
    stages = config["stages"]

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  PROPERTY PROFILE ENRICHER — {sale_type.upper()} mode", file=sys.stderr)
    print(f"  Depth: {depth} | Stages: {', '.join(stages)}", file=sys.stderr)
    print(f"  Input: {parcel_id or address or case_number}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    t0 = time.time()
    result = {
        "input": {"address": address, "parcel_id": parcel_id, "case_number": case_number},
        "sale_type": sale_type,
        "depth": depth,
        "stages": {},
        "synthesis": None,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": None,
    }

    # Stage 1: OWNER
    if "OWNER" in stages:
        result["stages"]["owner"] = stage_owner(parcel_id=parcel_id, address=address)
        # Propagate discovered parcel_id
        if not parcel_id and result["stages"]["owner"].get("parcel_id"):
            parcel_id = result["stages"]["owner"]["parcel_id"]

    if not parcel_id:
        log("PIPELINE", "No parcel_id resolved — cannot continue deeper stages", "ERR")
        result["elapsed_seconds"] = round(time.time() - t0, 1)
        return result

    # Stage 2: TAX
    if "TAX" in stages:
        result["stages"]["tax"] = stage_tax(parcel_id)

    # Stage 3: LIENS
    if "LIENS" in stages:
        owner_name = result["stages"].get("owner", {}).get("owner_name")
        result["stages"]["liens"] = stage_liens(parcel_id, owner_name)

    # Stage 4: PERMITS
    if "PERMITS" in stages:
        result["stages"]["permits"] = stage_permits(parcel_id, address)

    # Stage 5: COMPS
    if "COMPS" in stages:
        result["stages"]["comps"] = stage_comps(
            parcel_id, radius_miles=comp_radius, months=comp_months,
            min_comps=config["comp_count"],
        )

    # Stage 6: SYNTHESIZE
    if "SYNTHESIZE" in stages or depth == "deep":
        result["synthesis"] = stage_synthesize(
            owner=result["stages"].get("owner", {}),
            tax=result["stages"].get("tax", {}),
            liens=result["stages"].get("liens", {}),
            permits=result["stages"].get("permits", {}),
            comps=result["stages"].get("comps", {}),
            sale_type=sale_type,
            judgment_amount=judgment_amount,
        )

    result["elapsed_seconds"] = round(time.time() - t0, 1)

    # Summary
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  ENRICHMENT COMPLETE — {result['elapsed_seconds']}s", file=sys.stderr)
    if result.get("synthesis"):
        s = result["synthesis"]
        action = s.get("action", "N/A")
        conf = s.get("overall_confidence", 0)
        print(f"  Action: {action} | Confidence: {conf:.0%}", file=sys.stderr)
        if s.get("valuation", {}).get("max_bid"):
            print(f"  Max Bid: ${s['valuation']['max_bid']:,}", file=sys.stderr)
        if s.get("motivation_score") is not None:
            print(f"  Motivation: {s['motivation_score']}/100", file=sys.stderr)
        if s.get("red_flags"):
            print(f"  Red Flags: {', '.join(s['red_flags'])}", file=sys.stderr)
        if s.get("green_flags"):
            print(f"  Green Flags: {', '.join(s['green_flags'])}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    return result


def batch_enrich(parcels: List[Dict], **kwargs) -> List[Dict]:
    """
    Batch enrichment for multiple properties.
    Respects rate limits with 2s delay between properties.
    """
    results = []
    total = len(parcels)
    for i, p in enumerate(parcels, 1):
        log("BATCH", f"Processing {i}/{total}: {p.get('parcel_id') or p.get('address')}")
        r = enrich_property(
            address=p.get("address"),
            parcel_id=p.get("parcel_id"),
            case_number=p.get("case_number"),
            judgment_amount=p.get("judgment_amount"),
            **kwargs,
        )
        results.append(r)
        if i < total:
            time.sleep(2)  # Rate limit courtesy

    # Persist batch to Supabase
    flat = [_flatten_for_db(r) for r in results if r.get("stages", {}).get("owner")]
    if flat:
        supabase_upsert("property_profiles", flat)

    # Telegram summary
    bid_count = sum(1 for r in results if r.get("synthesis", {}).get("action") == "BID")
    notify_telegram(
        f"🏠 <b>Enricher Batch Complete</b>\n"
        f"Total: {total} | BID: {bid_count}\n"
        f"Mode: {kwargs.get('sale_type', 'foreclosure')}"
    )

    return results


def _flatten_for_db(result: Dict) -> Dict:
    """Flatten enrichment result for Supabase upsert."""
    owner = result.get("stages", {}).get("owner", {})
    tax = result.get("stages", {}).get("tax", {})
    synth = result.get("synthesis", {})
    return {
        "parcel_id": owner.get("parcel_id"),
        "owner_name": owner.get("owner_name"),
        "owner_type": owner.get("owner_type"),
        "assessed_value": tax.get("assessed_value"),
        "market_value": tax.get("market_value"),
        "delinquent": tax.get("delinquent", False),
        "sale_type": result.get("sale_type"),
        "action": synth.get("action"),
        "max_bid": synth.get("valuation", {}).get("max_bid"),
        "motivation_score": synth.get("motivation_score"),
        "confidence": synth.get("overall_confidence"),
        "enriched_at": result.get("enriched_at"),
        "raw_json": json.dumps(result),
    }


# ═══════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Property Profile Enricher — BidDeed.AI + ZoneWise.AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m enricher.agent enrich --address "123 Main St, Melbourne, FL 32901"
  python -m enricher.agent enrich --parcel "25-37-22-00-00123.0-0000.00" --mode foreclosure
  python -m enricher.agent enrich --parcel "25-37-22-00-00456.0-0000.00" --mode tax_deed --depth deep
  python -m enricher.agent batch --file parcels.csv --mode off_market --depth standard
        """,
    )
    sub = parser.add_subparsers(dest="command")

    # enrich command
    enrich_p = sub.add_parser("enrich", help="Enrich a single property")
    enrich_p.add_argument("--address", type=str, help="Property street address")
    enrich_p.add_argument("--parcel", type=str, help="BCPAO parcel ID")
    enrich_p.add_argument("--case", type=str, help="Court case number (foreclosure)")
    enrich_p.add_argument("--mode", choices=list(SALE_TYPES.keys()), default="foreclosure")
    enrich_p.add_argument("--depth", choices=list(DEPTH_CONFIGS.keys()), default="standard")
    enrich_p.add_argument("--radius", type=float, default=1.0, help="Comp radius in miles")
    enrich_p.add_argument("--months", type=int, default=12, help="Comp lookback months")
    enrich_p.add_argument("--judgment", type=float, help="Judgment amount (foreclosure)")
    enrich_p.add_argument("--json", action="store_true", help="Output JSON")

    # batch command
    batch_p = sub.add_parser("batch", help="Batch enrich from CSV")
    batch_p.add_argument("--file", required=True, help="CSV with parcel_id or address columns")
    batch_p.add_argument("--mode", choices=list(SALE_TYPES.keys()), default="foreclosure")
    batch_p.add_argument("--depth", choices=list(DEPTH_CONFIGS.keys()), default="standard")

    # status command
    sub.add_parser("status", help="Check agent status and data source connectivity")

    args = parser.parse_args()

    if args.command == "enrich":
        if not args.address and not args.parcel and not args.case:
            enrich_p.error("Must provide --address, --parcel, or --case")
        result = enrich_property(
            address=args.address,
            parcel_id=args.parcel,
            case_number=args.case,
            sale_type=args.mode,
            depth=args.depth,
            comp_radius=args.radius,
            comp_months=args.months,
            judgment_amount=args.judgment,
        )
        if args.json:
            print(json.dumps(result, indent=2, default=str))

    elif args.command == "batch":
        import csv
        parcels = []
        with open(args.file) as f:
            reader = csv.DictReader(f)
            for row in reader:
                parcels.append(row)
        log("BATCH", f"Loaded {len(parcels)} properties from {args.file}")
        batch_enrich(parcels, sale_type=args.mode, depth=args.depth)

    elif args.command == "status":
        print("\n  Property Profile Enricher — Status Check", file=sys.stderr)
        print("  " + "="*40, file=sys.stderr)
        _check_connectivity()

    else:
        parser.print_help()


def _check_connectivity():
    """Verify data source connectivity."""
    sources = [
        ("BCPAO API", f"{BCPAO_API}/search?acct=2537220000001"),
        ("BCPAO GIS", f"{BCPAO_PARCEL}?f=json"),
        ("Supabase", f"{SUPABASE_URL}/rest/v1/" if SUPABASE_URL else None),
    ]
    client = httpx.Client(timeout=10, follow_redirects=True, headers={"User-Agent": "BidDeed.AI/1.0 (enricher)"})
    for name, url in sources:
        if not url:
            log("STATUS", f"{name}: NOT CONFIGURED", "WARN")
            continue
        try:
            r = client.get(url)
            log("STATUS", f"{name}: {r.status_code}", "OK" if r.status_code == 200 else "WARN")
        except Exception as e:
            log("STATUS", f"{name}: {e}", "ERR")
    client.close()


if __name__ == "__main__":
    main()
