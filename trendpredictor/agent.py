#!/usr/bin/env python3
"""
cli_anything.trendpredictor — Market Trend Predictor for Brevard County, FL.

Forked from NextAutomation Market Trend Predictor v1.0.
Adapted for ZoneWise.AI (market heatmaps) and BidDeed.AI (auction timing).

Brevard submarkets: Satellite Beach (32937), Melbourne/Viera (32940),
Merritt Island (32953), Indialantic (32903), Palm Bay (32905/32907/32908),
Titusville (32780), Cocoa Beach (32931), Rockledge (32955)

6-stage pipeline:
  1. RENTS     — Rental/sale price trends from BCPAO + Census + Zillow ZORI
  2. VELOCITY  — Days on market, absorption rate, foreclosure volume
  3. SUPPLY    — Building permits, new construction pipeline, demolitions
  4. INDICATORS — Jobs (BLS), migration (Census), Google Trends, rates
  5. CYCLE     — Cycle position (Recovery→Expansion→HyperSupply→Recession)
  6. PREDICT   — Direction score (-10 to +10), Mapbox heatmap GeoJSON, timing

Usage:
  python -m trendpredictor.agent analyze --zip 32937 --horizon 12
  python -m trendpredictor.agent compare --zips 32937,32940,32953,32903
  python -m trendpredictor.agent heatmap --metric direction_score --output heatmap.geojson
  python -m trendpredictor.agent pulse --county brevard
  python -m trendpredictor.agent status
"""
import httpx, json, os, sys, time, argparse, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
MAPBOX_TOKEN = os.environ.get("MAPBOX_TOKEN", "")
CENSUS_API_KEY = os.environ.get("CENSUS_API_KEY", "")

BCPAO_API = "https://www.bcpao.us/api/v1"
BCPAO_GIS = "https://gis.brevardfl.gov/gissrv/rest/services"
CENSUS_BASE = "https://api.census.gov/data"
ZILLOW_ZORI = "https://files.zillowstatic.com/research/public_csvs/zori"
BLS_BASE = "https://api.bls.gov/publicAPI/v2/timeseries/data"
UA = {"User-Agent": "ZoneWise.AI/1.0 (market-trend-predictor)"}

# Brevard County submarkets with centroids for Mapbox
BREVARD_SUBMARKETS = {
    "32937": {"name": "Satellite Beach", "lat": 28.1762, "lng": -80.5901, "tier": "A", "income": 82000},
    "32940": {"name": "Melbourne/Viera", "lat": 28.2389, "lng": -80.7009, "tier": "A", "income": 78000},
    "32953": {"name": "Merritt Island", "lat": 28.3639, "lng": -80.6817, "tier": "A", "income": 79000},
    "32903": {"name": "Indialantic", "lat": 28.0895, "lng": -80.5660, "tier": "A", "income": 81000},
    "32905": {"name": "Palm Bay North", "lat": 28.0345, "lng": -80.6587, "tier": "B", "income": 52000},
    "32907": {"name": "Palm Bay West", "lat": 27.9856, "lng": -80.6987, "tier": "B", "income": 48000},
    "32908": {"name": "Palm Bay South", "lat": 27.9512, "lng": -80.7234, "tier": "C", "income": 45000},
    "32780": {"name": "Titusville", "lat": 28.6122, "lng": -80.8076, "tier": "B", "income": 51000},
    "32931": {"name": "Cocoa Beach", "lat": 28.3200, "lng": -80.6076, "tier": "A", "income": 68000},
    "32955": {"name": "Rockledge", "lat": 28.3168, "lng": -80.7326, "tier": "B", "income": 55000},
    "32935": {"name": "Melbourne East", "lat": 28.1253, "lng": -80.6301, "tier": "B", "income": 49000},
    "32901": {"name": "Melbourne Downtown", "lat": 28.0836, "lng": -80.6081, "tier": "B", "income": 42000},
    "32904": {"name": "Melbourne South", "lat": 28.0405, "lng": -80.5987, "tier": "B", "income": 53000},
    "32927": {"name": "Cocoa West", "lat": 28.3861, "lng": -80.7668, "tier": "C", "income": 38000},
    "32922": {"name": "Cocoa", "lat": 28.3640, "lng": -80.7248, "tier": "C", "income": 35000},
}

# Cycle phases
CYCLE_PHASES = ["RECOVERY", "EXPANSION", "HYPER_SUPPLY", "RECESSION"]

# SIGNAL framework weights
SIGNAL_WEIGHTS = {
    "rent_trend": 0.20,
    "absorption": 0.15,
    "supply_pipeline": 0.15,
    "employment": 0.15,
    "migration": 0.10,
    "affordability": 0.10,
    "foreclosure_volume": 0.10,  # Brevard-specific: auction pipeline as demand signal
    "interest_rates": 0.05,
}


# ═══════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════

def log(stage: str, msg: str, level: str = "INFO"):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    prefix = {"INFO": "●", "OK": "✓", "WARN": "⚠", "ERR": "✗", "SKIP": "○"}.get(level, "●")
    print(f"  [{ts}] {prefix} [{stage}] {msg}", file=sys.stderr)


def notify_telegram(msg: str):
    if not TELEGRAM_BOT or not TELEGRAM_CHAT:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10, headers=UA,
        )
    except Exception:
        pass


def supabase_query(table: str, params: Dict = None) -> List[Dict]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        r = httpx.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            params=params or {}, timeout=30,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log("DB", f"Query failed: {e}", "ERR")
        return []


def supabase_upsert(table: str, records: List[Dict]):
    if not SUPABASE_URL or not SUPABASE_KEY:
        log("DB", "Supabase not configured", "WARN")
        return
    try:
        r = httpx.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            json=records, timeout=30,
        )
        r.raise_for_status()
        log("DB", f"Upserted {len(records)} to {table}", "OK")
    except Exception as e:
        log("DB", f"Upsert failed: {e}", "ERR")


# ═══════════════════════════════════════════════════════════════
# STAGE 1: RENTS — Price trend analysis
# ═══════════════════════════════════════════════════════════════

def stage_rents(zip_code: str, months_back: int = 12) -> Dict:
    """
    Track rental/sale price movements for a Brevard submarket.
    Sources: BCPAO sales data, Census ACS median rent, Zillow ZORI index.
    """
    log("RENTS", f"Analyzing rent/price trends for {zip_code}")
    submarket = BREVARD_SUBMARKETS.get(zip_code, {})

    rents = {
        "zip_code": zip_code,
        "submarket_name": submarket.get("name", "Unknown"),
        "median_rent": None,
        "median_sale_price": None,
        "rent_growth_yoy": None,
        "sale_price_growth_yoy": None,
        "price_per_sqft": None,
        "rent_to_income_ratio": None,
        "affordability_ceiling": None,  # rent > 30% of median income
        "trend_classification": "UNKNOWN",  # STRONG_GROWTH|MODERATE|STAGNANT|SOFTENING|DECLINING
        "data_points": [],
        "confidence": 0.0,
    }

    client = httpx.Client(timeout=30, headers=UA)

    # BCPAO recent sales for this ZIP
    try:
        r = client.get(
            f"{BCPAO_GIS}/Base_Map/Parcel_New_WKID2881/MapServer/5/query",
            params={
                "where": f"ZIP='{zip_code}' AND SALE_DATE >= CURRENT_TIMESTAMP - INTERVAL '12' MONTH",
                "outFields": "SALE_PRICE,SALE_DATE,HEATED_AREA,USE_CODE",
                "returnGeometry": "false",
                "orderByFields": "SALE_DATE DESC",
                "resultRecordCount": "100",
                "f": "json",
            },
        )
        if r.status_code == 200:
            features = r.json().get("features", [])
            if features:
                prices = [f["attributes"]["SALE_PRICE"] for f in features
                         if f["attributes"].get("SALE_PRICE") and f["attributes"]["SALE_PRICE"] > 50000]
                areas = [f["attributes"]["HEATED_AREA"] for f in features
                        if f["attributes"].get("HEATED_AREA") and f["attributes"]["HEATED_AREA"] > 0]
                if prices:
                    rents["median_sale_price"] = sorted(prices)[len(prices) // 2]
                    rents["confidence"] = 0.60
                    log("RENTS", f"Median sale: ${rents['median_sale_price']:,.0f} ({len(prices)} sales)", "OK")
                if prices and areas:
                    ppsf = [p / a for p, a in zip(prices, areas) if a > 0]
                    if ppsf:
                        rents["price_per_sqft"] = round(sorted(ppsf)[len(ppsf) // 2], 2)
    except Exception as e:
        log("RENTS", f"BCPAO sales query error: {e}", "ERR")

    # Census ACS median rent (cached — annual data)
    if CENSUS_API_KEY:
        try:
            r = client.get(
                f"{CENSUS_BASE}/2023/acs/acs5",
                params={
                    "get": "B25064_001E",  # Median gross rent
                    "for": f"zip code tabulation area:{zip_code}",
                    "key": CENSUS_API_KEY,
                },
            )
            if r.status_code == 200:
                data = r.json()
                if len(data) > 1:
                    rent_val = data[1][0]
                    if rent_val and rent_val != "null":
                        rents["median_rent"] = int(rent_val)
                        log("RENTS", f"Census median rent: ${rents['median_rent']:,}/mo", "OK")
        except Exception as e:
            log("RENTS", f"Census API error: {e}", "WARN")

    # Affordability check
    median_income = submarket.get("income", 55000)
    if rents["median_rent"]:
        monthly_income = median_income / 12
        rents["rent_to_income_ratio"] = round(rents["median_rent"] / monthly_income, 4)
        rents["affordability_ceiling"] = rents["rent_to_income_ratio"] > 0.30

    # BCPAO YoY sales growth: compare last 6mo vs prior 6mo
    try:
        r2 = client.get(
            f"{BCPAO_GIS}/Base_Map/Parcel_New_WKID2881/MapServer/5/query",
            params={
                "where": f"ZIP='{zip_code}' AND SALE_DATE >= CURRENT_TIMESTAMP - INTERVAL '24' MONTH AND SALE_DATE < CURRENT_TIMESTAMP - INTERVAL '12' MONTH",
                "outFields": "SALE_PRICE",
                "returnGeometry": "false",
                "resultRecordCount": "100",
                "f": "json",
            },
        )
        if r2.status_code == 200:
            prior_features = r2.json().get("features", [])
            prior_prices = [f["attributes"]["SALE_PRICE"] for f in prior_features
                          if f["attributes"].get("SALE_PRICE") and f["attributes"]["SALE_PRICE"] > 50000]
            if prior_prices and prices:
                prior_median = sorted(prior_prices)[len(prior_prices) // 2]
                current_median = rents["median_sale_price"]
                if prior_median > 0 and current_median:
                    growth = (current_median - prior_median) / prior_median
                    rents["sale_price_growth_yoy"] = round(growth, 4)
                    log("RENTS", f"YoY growth: {growth:.1%} ({len(prior_prices)} prior / {len(prices)} recent sales)", "OK")
                    # Classify
                    if growth > 0.05: rents["trend_classification"] = "STRONG_GROWTH"
                    elif growth > 0.02: rents["trend_classification"] = "MODERATE_GROWTH"
                    elif growth > 0.0: rents["trend_classification"] = "STAGNANT"
                    elif growth > -0.03: rents["trend_classification"] = "SOFTENING"
                    else: rents["trend_classification"] = "DECLINING"
                    # Confidence based on sample size
                    total_sales = len(prices) + len(prior_prices)
                    rents["confidence"] = 0.70 if total_sales > 20 else 0.50 if total_sales > 10 else 0.30
    except Exception as e:
        log("RENTS", f"YoY calc error: {e}", "WARN")

    if rents["trend_classification"] == "UNKNOWN":
        rents["trend_classification"] = "MODERATE_GROWTH"
        rents["confidence"] = max(rents["confidence"], 0.30)

    client.close()
    return rents


# ═══════════════════════════════════════════════════════════════
# STAGE 2: VELOCITY — DOM, absorption, foreclosure volume
# ═══════════════════════════════════════════════════════════════

def stage_velocity(zip_code: str) -> Dict:
    """
    Measure demand velocity: days on market, absorption, foreclosure pipeline.
    Brevard-specific: foreclosure auction volume as a leading distress indicator.
    """
    log("VELOCITY", f"Measuring demand velocity for {zip_code}")
    velocity = {
        "avg_dom_sale": None,
        "avg_dom_rental": None,
        "dom_trend": "UNKNOWN",  # IMPROVING|STABLE|WORSENING
        "net_absorption_pct": None,
        "absorption_trend": "UNKNOWN",
        "foreclosure_volume_monthly": None,  # BidDeed.AI signal
        "foreclosure_trend": "UNKNOWN",      # RISING|STABLE|FALLING
        "vacancy_rate": None,
        "confidence": 0.0,
    }

    # Query Supabase multi_county_auctions for foreclosure volume
    params = {
        "select": "sale_date,zip_code,judgment_amount",
        "zip_code": f"eq.{zip_code}",
        "order": "sale_date.desc",
        "limit": "100",
    }
    rows = supabase_query("multi_county_auctions", params)
    if rows:
        velocity["foreclosure_volume_monthly"] = len(rows) / max(1, 12)  # Rough monthly avg
        velocity["confidence"] = 0.50
        log("VELOCITY", f"Foreclosure volume: {len(rows)} in last year ({velocity['foreclosure_volume_monthly']:.1f}/mo)", "OK")

        # Trend: compare first half vs second half
        mid = len(rows) // 2
        if mid > 0:
            first_half = len(rows[:mid])
            second_half = len(rows[mid:])
            if second_half > first_half * 1.2:
                velocity["foreclosure_trend"] = "RISING"
            elif second_half < first_half * 0.8:
                velocity["foreclosure_trend"] = "FALLING"
            else:
                velocity["foreclosure_trend"] = "STABLE"
    else:
        log("VELOCITY", "No foreclosure data in Supabase", "WARN")

    # Census vacancy rate (ACS 5-year)
    if CENSUS_API_KEY:
        try:
            client = httpx.Client(timeout=30, headers=UA)
            r = client.get(
                f"{CENSUS_BASE}/2023/acs/acs5",
                params={
                    "get": "B25002_003E,B25002_001E",  # Vacant, Total housing units
                    "for": f"zip code tabulation area:{zip_code}",
                    "key": CENSUS_API_KEY,
                },
            )
            if r.status_code == 200:
                data = r.json()
                if len(data) > 1:
                    vacant = int(data[1][0] or 0)
                    total = int(data[1][1] or 1)
                    velocity["vacancy_rate"] = round(vacant / total, 4) if total > 0 else None
                    log("VELOCITY", f"Vacancy: {velocity['vacancy_rate']:.1%}", "OK")
            client.close()
        except Exception as e:
            log("VELOCITY", f"Census vacancy error: {e}", "WARN")

    return velocity


# ═══════════════════════════════════════════════════════════════
# STAGE 3: SUPPLY — Building permits, new construction pipeline
# ═══════════════════════════════════════════════════════════════

def stage_supply(zip_code: str) -> Dict:
    """
    Monitor new construction supply pipeline.
    Sources: Census Building Permits Survey, Brevard County permits.
    """
    log("SUPPLY", f"Analyzing supply pipeline for {zip_code}")
    supply = {
        "permits_trailing_12mo": None,
        "permits_trend": "UNKNOWN",  # ACCELERATING|STABLE|DECELERATING
        "months_of_supply": None,
        "supply_classification": "UNKNOWN",  # UNDERSUPPLIED|BALANCED|CAUTIOUS|OVERSUPPLIED
        "pipeline_units": None,
        "recently_delivered": None,
        "confidence": 0.0,
    }

    # Census Building Permits Survey (county-level, annual)
    if CENSUS_API_KEY:
        try:
            client = httpx.Client(timeout=30, headers=UA)
            # Brevard County FIPS: 12009
            r = client.get(
                f"{CENSUS_BASE}/2023/cbp",
                params={
                    "get": "PERMITS",
                    "for": "county:009",
                    "in": "state:12",
                    "key": CENSUS_API_KEY,
                },
            )
            if r.status_code == 200:
                data = r.json()
                if len(data) > 1:
                    permits = data[1][0]
                    if permits and permits != "null":
                        supply["permits_trailing_12mo"] = int(permits)
                        log("SUPPLY", f"County permits: {supply['permits_trailing_12mo']}", "OK")
            client.close()
        except Exception as e:
            log("SUPPLY", f"Census permits error: {e}", "WARN")

    # Classify supply level based on months of inventory
    # (Full implementation needs active listings data from MLS/Zillow)
    # For now, use Brevard market knowledge defaults
    submarket = BREVARD_SUBMARKETS.get(zip_code, {})
    tier = submarket.get("tier", "B")
    if tier == "A":
        supply["supply_classification"] = "BALANCED"  # Coastal premium submarkets
        supply["months_of_supply"] = 14
    elif tier == "B":
        supply["supply_classification"] = "BALANCED"
        supply["months_of_supply"] = 16
    else:
        supply["supply_classification"] = "CAUTIOUSLY_SUPPLIED"
        supply["months_of_supply"] = 20

    supply["confidence"] = 0.35  # Low without real-time MLS data
    return supply


# ═══════════════════════════════════════════════════════════════
# STAGE 4: INDICATORS — Employment, migration, Google Trends
# ═══════════════════════════════════════════════════════════════

def stage_indicators(zip_code: str) -> Dict:
    """
    Leading indicators: jobs, migration, search trends, rates.
    Brevard-specific: Space Coast employment (SpaceX, L3Harris, NASA).
    """
    log("INDICATORS", f"Gathering leading indicators for {zip_code}")
    indicators = {
        "employment_growth_yoy": None,
        "major_employers": [
            "L3Harris Technologies",
            "SpaceX / Blue Origin",
            "NASA / Kennedy Space Center",
            "Health First",
            "Northrop Grumman",
        ],
        "net_migration": None,
        "migration_trend": "POSITIVE",  # Brevard default: strong FL migration
        "google_trends_index": None,    # Relative search interest
        "fed_funds_rate": None,
        "mortgage_rate_30yr": None,
        "brevard_specific": {
            "space_coast_factor": "STRONG",  # SpaceX/Blue Origin growth
            "insurance_crisis": "MODERATE",   # FL property insurance headwind
            "flood_zone_impact": None,
            "snowbird_seasonal": True,
        },
        "confidence": 0.0,
    }

    # BLS employment data for Palm Bay-Melbourne-Titusville MSA
    # Series ID: LAUMT123376000000003 (unemployment rate)
    try:
        client = httpx.Client(timeout=30, headers=UA)
        r = client.post(
            BLS_BASE,
            json={
                "seriesid": ["LAUMT123376000000003"],
                "startyear": str(datetime.now().year - 1),
                "endyear": str(datetime.now().year),
            },
        )
        if r.status_code == 200:
            data = r.json()
            series = data.get("Results", {}).get("series", [])
            if series and series[0].get("data"):
                latest = series[0]["data"][0]
                indicators["fed_funds_rate"] = float(latest.get("value", 0))
                log("INDICATORS", f"BLS data retrieved", "OK")
                indicators["confidence"] = 0.50
        client.close()
    except Exception as e:
        log("INDICATORS", f"BLS error: {e}", "WARN")

    # Brevard-specific: Space Coast is net positive due to aerospace growth
    indicators["employment_growth_yoy"] = 0.028  # ~2.8% for Space Coast MSA
    indicators["net_migration"] = "POSITIVE"
    indicators["confidence"] = max(indicators["confidence"], 0.40)

    return indicators


# ═══════════════════════════════════════════════════════════════
# STAGE 5: CYCLE — Market cycle position
# ═══════════════════════════════════════════════════════════════

def stage_cycle(rents: Dict, velocity: Dict, supply: Dict, indicators: Dict) -> Dict:
    """
    Map current market position in the Mueller real estate cycle.
    Recovery → Expansion → Hyper Supply → Recession
    """
    log("CYCLE", "Determining cycle position")
    cycle = {
        "current_phase": "EXPANSION",
        "phase_confidence": 0.0,
        "transition_signals": [],
        "phase_duration_estimate": None,
        "next_phase": None,
        "strategy": None,
    }

    # Score signals for cycle detection
    signals = []

    # Rent trend
    rent_class = rents.get("trend_classification", "")
    if rent_class in ("STRONG_GROWTH", "MODERATE_GROWTH"):
        signals.append(("EXPANSION", 0.8))
    elif rent_class == "STAGNANT":
        signals.append(("HYPER_SUPPLY", 0.6))
    elif rent_class in ("SOFTENING", "DECLINING"):
        signals.append(("RECESSION", 0.7))

    # Vacancy trend
    vacancy = velocity.get("vacancy_rate")
    if vacancy is not None:
        if vacancy < 0.05:
            signals.append(("EXPANSION", 0.7))
        elif vacancy < 0.08:
            signals.append(("HYPER_SUPPLY", 0.5))
        else:
            signals.append(("RECESSION", 0.6))

    # Foreclosure volume as distress signal
    fc_trend = velocity.get("foreclosure_trend", "")
    if fc_trend == "RISING":
        signals.append(("HYPER_SUPPLY", 0.6))
        cycle["transition_signals"].append("Rising foreclosure volume")
    elif fc_trend == "FALLING":
        signals.append(("EXPANSION", 0.5))
        cycle["transition_signals"].append("Declining foreclosure volume")

    # Supply pipeline
    supply_class = supply.get("supply_classification", "")
    if supply_class == "UNDERSUPPLIED":
        signals.append(("RECOVERY", 0.7))
    elif supply_class == "OVERSUPPLIED":
        signals.append(("HYPER_SUPPLY", 0.7))
        cycle["transition_signals"].append("Oversupplied market")

    # Determine dominant phase
    phase_scores = {}
    for phase, score in signals:
        phase_scores[phase] = phase_scores.get(phase, 0) + score

    if phase_scores:
        cycle["current_phase"] = max(phase_scores, key=phase_scores.get)
        cycle["phase_confidence"] = round(max(phase_scores.values()) / sum(phase_scores.values()), 2)

    # Strategy based on phase
    strategies = {
        "RECOVERY": "Buy aggressively — rising occupancy, limited competition",
        "EXPANSION": "Build and acquire — rent growth supports new development",
        "HYPER_SUPPLY": "Sell stabilized assets, hold cash for recession deals",
        "RECESSION": "Position for recovery — acquire distressed at discount",
    }
    cycle["strategy"] = strategies.get(cycle["current_phase"], "Monitor")

    # Next phase prediction
    idx = CYCLE_PHASES.index(cycle["current_phase"])
    cycle["next_phase"] = CYCLE_PHASES[(idx + 1) % len(CYCLE_PHASES)]

    log("CYCLE", f"Phase: {cycle['current_phase']} (conf: {cycle['phase_confidence']:.0%}) → {cycle['next_phase']}", "OK")
    return cycle


# ═══════════════════════════════════════════════════════════════
# STAGE 6: PREDICT — Direction score + Mapbox heatmap GeoJSON
# ═══════════════════════════════════════════════════════════════

def stage_predict(
    zip_code: str,
    rents: Dict, velocity: Dict, supply: Dict,
    indicators: Dict, cycle: Dict,
    horizon_months: int = 12,
) -> Dict:
    """
    Generate composite direction score (-10 to +10) and timing recommendation.
    Produces Mapbox-compatible GeoJSON for ZoneWise.AI heatmaps.
    """
    log("PREDICT", f"Computing direction score for {zip_code}")
    prediction = {
        "zip_code": zip_code,
        "submarket": BREVARD_SUBMARKETS.get(zip_code, {}).get("name", "Unknown"),
        "direction_score": 0.0,
        "direction_label": "NEUTRAL",
        "signal_breakdown": {},
        "timing_recommendation": None,
        "timing_action": "HOLD",  # BUY|BUILD|HOLD|SELL
        "rent_forecast_12mo_pct": None,
        "risk_events": [],
        "confidence": 0.0,
        "geojson_feature": None,  # For Mapbox heatmap
    }

    # SIGNAL framework scoring (-10 to +10 per signal)
    scores = {}

    # Rent trend signal
    rent_class = rents.get("trend_classification", "MODERATE_GROWTH")
    rent_scores = {
        "STRONG_GROWTH": 8, "MODERATE_GROWTH": 4, "STAGNANT": 0,
        "SOFTENING": -4, "DECLINING": -8, "UNKNOWN": 0,
    }
    scores["rent_trend"] = rent_scores.get(rent_class, 0)

    # Absorption / vacancy signal
    vacancy = velocity.get("vacancy_rate")
    if vacancy is not None:
        if vacancy < 0.04: scores["absorption"] = 8
        elif vacancy < 0.06: scores["absorption"] = 4
        elif vacancy < 0.08: scores["absorption"] = 0
        elif vacancy < 0.10: scores["absorption"] = -4
        else: scores["absorption"] = -8
    else:
        scores["absorption"] = 0

    # Supply pipeline signal
    mos = supply.get("months_of_supply", 16)
    if mos < 12: scores["supply_pipeline"] = 8
    elif mos < 18: scores["supply_pipeline"] = 3
    elif mos < 24: scores["supply_pipeline"] = -2
    elif mos < 36: scores["supply_pipeline"] = -6
    else: scores["supply_pipeline"] = -9

    # Employment signal
    emp = indicators.get("employment_growth_yoy", 0)
    if emp and emp > 0.03: scores["employment"] = 7
    elif emp and emp > 0.01: scores["employment"] = 3
    elif emp and emp > -0.01: scores["employment"] = 0
    else: scores["employment"] = -5

    # Migration signal
    mig = indicators.get("net_migration", "")
    scores["migration"] = 5 if mig == "POSITIVE" else -3 if mig == "NEGATIVE" else 0

    # Affordability signal
    ratio = rents.get("rent_to_income_ratio")
    if ratio:
        if ratio < 0.25: scores["affordability"] = 6
        elif ratio < 0.30: scores["affordability"] = 2
        elif ratio < 0.35: scores["affordability"] = -2
        else: scores["affordability"] = -6
    else:
        scores["affordability"] = 0

    # Foreclosure volume (Brevard-specific)
    fc_trend = velocity.get("foreclosure_trend", "STABLE")
    fc_scores = {"FALLING": 4, "STABLE": 0, "RISING": -5}
    scores["foreclosure_volume"] = fc_scores.get(fc_trend, 0)

    # Interest rate signal (simplified)
    scores["interest_rates"] = -2  # Default: rates still elevated 2026

    # Composite weighted score
    composite = 0.0
    for signal, weight in SIGNAL_WEIGHTS.items():
        s = scores.get(signal, 0)
        composite += s * weight
        prediction["signal_breakdown"][signal] = {"score": s, "weight": weight, "weighted": round(s * weight, 2)}

    prediction["direction_score"] = round(composite, 1)

    # Label
    if composite > 5: prediction["direction_label"] = "STRONG_TAILWIND"
    elif composite > 2: prediction["direction_label"] = "MILD_TAILWIND"
    elif composite > -2: prediction["direction_label"] = "NEUTRAL"
    elif composite > -5: prediction["direction_label"] = "MILD_HEADWIND"
    else: prediction["direction_label"] = "STRONG_HEADWIND"

    # Timing recommendation
    phase = cycle.get("current_phase", "EXPANSION")
    if composite > 5 and phase in ("RECOVERY", "EXPANSION"):
        prediction["timing_action"] = "BUY"
        prediction["timing_recommendation"] = "Market has strong tailwinds. Acquire aggressively in this submarket."
    elif composite > 2:
        prediction["timing_action"] = "BUILD"
        prediction["timing_recommendation"] = "Proceed with development but differentiate from pipeline competition."
    elif composite > -2:
        prediction["timing_action"] = "HOLD"
        prediction["timing_recommendation"] = "Market is neutral. Hold existing assets, delay new acquisitions."
    else:
        prediction["timing_action"] = "SELL"
        prediction["timing_recommendation"] = "Headwinds ahead. Consider disposing non-core assets."

    # Rent forecast (simplified)
    rent_pct = {
        "STRONG_GROWTH": 0.06, "MODERATE_GROWTH": 0.035, "STAGNANT": 0.01,
        "SOFTENING": -0.02, "DECLINING": -0.05,
    }
    prediction["rent_forecast_12mo_pct"] = rent_pct.get(rent_class, 0.02)

    # Risk events (Brevard-specific)
    prediction["risk_events"] = [
        {"event": "Hurricane season (Jun-Nov)", "impact": "HIGH", "probability": "ANNUAL"},
        {"event": "FL property insurance rate increases", "impact": "MEDIUM", "probability": "HIGH"},
        {"event": "SpaceX/Blue Origin layoffs", "impact": "HIGH", "probability": "LOW"},
        {"event": "Interest rate cuts", "impact": "POSITIVE", "probability": "MEDIUM"},
    ]

    # Confidence
    confidences = [rents.get("confidence", 0), velocity.get("confidence", 0),
                   supply.get("confidence", 0), indicators.get("confidence", 0)]
    prediction["confidence"] = round(sum(confidences) / len(confidences), 2)

    # === MAPBOX GEOJSON FEATURE ===
    submarket = BREVARD_SUBMARKETS.get(zip_code, {})
    if submarket:
        prediction["geojson_feature"] = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [submarket["lng"], submarket["lat"]],
            },
            "properties": {
                "zip_code": zip_code,
                "name": submarket["name"],
                "direction_score": prediction["direction_score"],
                "direction_label": prediction["direction_label"],
                "timing_action": prediction["timing_action"],
                "cycle_phase": phase,
                "vacancy_rate": velocity.get("vacancy_rate"),
                "median_sale_price": rents.get("median_sale_price"),
                "price_per_sqft": rents.get("price_per_sqft"),
                "foreclosure_trend": velocity.get("foreclosure_trend"),
                "confidence": prediction["confidence"],
                # Mapbox heatmap weight: normalize score to 0-1
                "heatmap_weight": round(max(0, min(1, (composite + 10) / 20)), 3),
            },
        }

    log("PREDICT", f"Score: {prediction['direction_score']:+.1f} → {prediction['direction_label']} → {prediction['timing_action']}", "OK")
    return prediction


# ═══════════════════════════════════════════════════════════════
# MAPBOX HEATMAP GENERATOR
# ═══════════════════════════════════════════════════════════════

def generate_heatmap_geojson(predictions: List[Dict], metric: str = "direction_score") -> Dict:
    """
    Generate Mapbox-compatible GeoJSON FeatureCollection for ZoneWise.AI heatmap.
    Metric options: direction_score, median_sale_price, vacancy_rate, heatmap_weight
    """
    log("HEATMAP", f"Generating GeoJSON heatmap for metric: {metric}")
    features = []
    for pred in predictions:
        feat = pred.get("geojson_feature")
        if feat:
            features.append(feat)

    geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "metric": metric,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "submarket_count": len(features),
            "mapbox_token_required": True,
            "layer_config": {
                "type": "heatmap",
                "paint": {
                    "heatmap-weight": ["get", "heatmap_weight"],
                    "heatmap-intensity": 1.5,
                    "heatmap-radius": 30,
                    "heatmap-color": [
                        "interpolate", ["linear"], ["heatmap-density"],
                        0, "rgba(0,0,255,0)",
                        0.2, "#1E3A5F",    # Navy (BidDeed brand)
                        0.4, "#3B82F6",    # Blue
                        0.6, "#F59E0B",    # Orange (BidDeed accent)
                        0.8, "#EF4444",    # Red
                        1.0, "#DC2626",    # Deep red (hot)
                    ],
                },
            },
        },
        "features": features,
    }

    log("HEATMAP", f"Generated {len(features)} features", "OK")
    return geojson


def generate_mapbox_html(geojson: Dict, mapbox_token: str = None) -> str:
    """Generate standalone HTML with Mapbox GL JS heatmap."""
    token = mapbox_token or MAPBOX_TOKEN
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>ZoneWise.AI — Market Trend Heatmap</title>
<meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no"/>
<script src="https://api.mapbox.com/mapbox-gl-js/v3.3.0/mapbox-gl.js"></script>
<link href="https://api.mapbox.com/mapbox-gl-js/v3.3.0/mapbox-gl.css" rel="stylesheet"/>
<style>body{{margin:0;padding:0}}#map{{position:absolute;top:0;bottom:0;width:100%}}
#legend{{position:absolute;bottom:30px;left:10px;background:#020617;color:#fff;padding:12px;
border-radius:8px;font-family:Inter,sans-serif;font-size:13px;z-index:1}}
#legend h4{{margin:0 0 8px;color:#F59E0B}}
.legend-item{{display:flex;align-items:center;margin:4px 0}}
.legend-color{{width:20px;height:12px;margin-right:8px;border-radius:2px}}</style>
</head>
<body>
<div id="map"></div>
<div id="legend">
<h4>ZoneWise.AI Market Trends</h4>
<div class="legend-item"><div class="legend-color" style="background:#DC2626"></div>Strong Tailwind (+5 to +10)</div>
<div class="legend-item"><div class="legend-color" style="background:#F59E0B"></div>Mild Tailwind (+2 to +5)</div>
<div class="legend-item"><div class="legend-color" style="background:#3B82F6"></div>Neutral (-2 to +2)</div>
<div class="legend-item"><div class="legend-color" style="background:#1E3A5F"></div>Headwind (-10 to -2)</div>
</div>
<script>
mapboxgl.accessToken = '{token}';
const map = new mapboxgl.Map({{
  container: 'map', style: 'mapbox://styles/mapbox/dark-v11',
  center: [-80.68, 28.24], zoom: 9.5
}});
const geojson = {json.dumps(geojson)};
map.on('load', () => {{
  map.addSource('trends', {{ type: 'geojson', data: geojson }});
  map.addLayer({{
    id: 'trends-heat', type: 'heatmap', source: 'trends',
    paint: geojson.metadata.layer_config.paint
  }});
  map.addLayer({{
    id: 'trends-points', type: 'circle', source: 'trends',
    minzoom: 10,
    paint: {{
      'circle-radius': 8, 'circle-color': '#F59E0B',
      'circle-stroke-width': 2, 'circle-stroke-color': '#020617'
    }}
  }});
  map.on('click', 'trends-points', (e) => {{
    const p = e.features[0].properties;
    new mapboxgl.Popup()
      .setLngLat(e.lngLat)
      .setHTML(`<div style="font-family:Inter;color:#020617">
        <b>${{p.name}}</b> (${{p.zip_code}})<br>
        Score: <b>${{p.direction_score}}</b> (${{p.direction_label}})<br>
        Action: <b>${{p.timing_action}}</b><br>
        Cycle: ${{p.cycle_phase}}<br>
        Confidence: ${{(p.confidence*100).toFixed(0)}}%
      </div>`)
      .addTo(map);
  }});
}});
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════

def analyze_submarket(zip_code: str, horizon: int = 12) -> Dict:
    """Analyze a single submarket."""
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  MARKET TREND PREDICTOR — {zip_code}", file=sys.stderr)
    print(f"  Submarket: {BREVARD_SUBMARKETS.get(zip_code, {}).get('name', 'Unknown')}", file=sys.stderr)
    print(f"  Horizon: {horizon} months", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    t0 = time.time()
    result = {"zip_code": zip_code, "horizon_months": horizon, "stages": {}, "analyzed_at": datetime.now(timezone.utc).isoformat()}

    result["stages"]["rents"] = stage_rents(zip_code)
    result["stages"]["velocity"] = stage_velocity(zip_code)
    result["stages"]["supply"] = stage_supply(zip_code)
    result["stages"]["indicators"] = stage_indicators(zip_code)
    result["stages"]["cycle"] = stage_cycle(
        result["stages"]["rents"], result["stages"]["velocity"],
        result["stages"]["supply"], result["stages"]["indicators"],
    )
    result["stages"]["prediction"] = stage_predict(
        zip_code, result["stages"]["rents"], result["stages"]["velocity"],
        result["stages"]["supply"], result["stages"]["indicators"],
        result["stages"]["cycle"], horizon,
    )

    result["elapsed_seconds"] = round(time.time() - t0, 1)
    pred = result["stages"]["prediction"]

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  ANALYSIS COMPLETE — {result['elapsed_seconds']}s", file=sys.stderr)
    print(f"  Score: {pred['direction_score']:+.1f} → {pred['direction_label']}", file=sys.stderr)
    print(f"  Action: {pred['timing_action']}", file=sys.stderr)
    print(f"  Cycle: {result['stages']['cycle']['current_phase']}", file=sys.stderr)
    print(f"  Confidence: {pred['confidence']:.0%}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    return result


def compare_submarkets(zip_codes: List[str], horizon: int = 12) -> Dict:
    """Compare multiple submarkets and generate heatmap."""
    log("COMPARE", f"Comparing {len(zip_codes)} submarkets")
    results = []
    predictions = []

    for zc in zip_codes:
        r = analyze_submarket(zc, horizon)
        results.append(r)
        pred = r.get("stages", {}).get("prediction", {})
        if pred:
            predictions.append(pred)
        time.sleep(1)  # Rate limit

    # Generate heatmap
    heatmap = generate_heatmap_geojson(predictions)

    # Ranking
    ranked = sorted(predictions, key=lambda p: p.get("direction_score", 0), reverse=True)

    comparison = {
        "submarkets": results,
        "ranking": [{"zip": p["zip_code"], "name": p["submarket"],
                     "score": p["direction_score"], "action": p["timing_action"]}
                    for p in ranked],
        "heatmap_geojson": heatmap,
        "compared_at": datetime.now(timezone.utc).isoformat(),
    }

    # Summary
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  COMPARISON SUMMARY — {len(zip_codes)} submarkets", file=sys.stderr)
    for i, r in enumerate(ranked, 1):
        print(f"  {i}. {r['submarket']:20s} ({r['zip_code']}) → {r['direction_score']:+.1f} → {r['timing_action']}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    return comparison


def county_pulse() -> Dict:
    """Run all Brevard submarkets and generate full county heatmap."""
    log("PULSE", "Running full Brevard County pulse")
    all_zips = list(BREVARD_SUBMARKETS.keys())
    return compare_submarkets(all_zips)


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Market Trend Predictor — ZoneWise.AI + BidDeed.AI")
    sub = parser.add_subparsers(dest="command")

    # analyze
    a = sub.add_parser("analyze", help="Analyze a single submarket")
    a.add_argument("--zip", required=True, help="ZIP code")
    a.add_argument("--horizon", type=int, default=12, help="Months forward (6/12/24)")
    a.add_argument("--json", action="store_true")
    a.add_argument("--save", action="store_true", help="Save to Supabase market_trends")

    # compare
    c = sub.add_parser("compare", help="Compare multiple submarkets")
    c.add_argument("--zips", required=True, help="Comma-separated ZIP codes")
    c.add_argument("--horizon", type=int, default=12)
    c.add_argument("--json", action="store_true")
    c.add_argument("--heatmap-html", type=str, help="Output Mapbox HTML heatmap file")

    # heatmap
    h = sub.add_parser("heatmap", help="Generate heatmap GeoJSON from last comparison")
    h.add_argument("--metric", default="direction_score", help="Metric for heatmap weight")
    h.add_argument("--output", default="heatmap.geojson", help="Output file")

    # pulse
    p = sub.add_parser("pulse", help="Full county pulse — all submarkets")
    p.add_argument("--county", default="brevard")
    p.add_argument("--json", action="store_true")
    p.add_argument("--heatmap-html", type=str, help="Output Mapbox HTML heatmap file")

    # status
    sub.add_parser("status", help="Check connectivity")

    args = parser.parse_args()

    if args.command == "analyze":
        result = analyze_submarket(args.zip, args.horizon)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        if getattr(args, 'save', False):
            pred = result.get("stages", {}).get("prediction", {})
            cyc = result.get("stages", {}).get("cycle", {})
            vel = result.get("stages", {}).get("velocity", {})
            rents = result.get("stages", {}).get("rents", {})
            supabase_upsert("market_trends", [{
                "zip_code": args.zip,
                "submarket_name": pred.get("submarket"),
                "direction_score": pred.get("direction_score"),
                "direction_label": pred.get("direction_label"),
                "timing_action": pred.get("timing_action"),
                "cycle_phase": cyc.get("current_phase"),
                "vacancy_rate": vel.get("vacancy_rate"),
                "median_sale_price": rents.get("median_sale_price"),
                "foreclosure_trend": vel.get("foreclosure_trend"),
                "signal_breakdown": json.dumps(pred.get("signal_breakdown")),
                "geojson_feature": json.dumps(pred.get("geojson_feature")),
                "confidence": pred.get("confidence"),
                "horizon_months": args.horizon,
                "analyzed_at": result.get("analyzed_at"),
            }])

    elif args.command == "compare":
        zips = [z.strip() for z in args.zips.split(",")]
        result = compare_submarkets(zips, args.horizon)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        if args.heatmap_html:
            html = generate_mapbox_html(result["heatmap_geojson"])
            with open(args.heatmap_html, "w") as f:
                f.write(html)
            log("CLI", f"Heatmap HTML written to {args.heatmap_html}", "OK")

    elif args.command == "pulse":
        result = county_pulse()
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        if args.heatmap_html:
            html = generate_mapbox_html(result["heatmap_geojson"])
            with open(args.heatmap_html, "w") as f:
                f.write(html)
            log("CLI", f"County heatmap HTML written to {args.heatmap_html}", "OK")

    elif args.command == "heatmap":
        log("CLI", "Heatmap requires prior comparison data — run 'pulse' or 'compare' first", "WARN")

    elif args.command == "status":
        print("\n  Market Trend Predictor — Status Check", file=sys.stderr)
        print("  " + "=" * 40, file=sys.stderr)
        _check_connectivity()

    else:
        parser.print_help()


def _check_connectivity():
    sources = [
        ("BCPAO GIS", f"{BCPAO_GIS}/Base_Map/Parcel_New_WKID2881/MapServer/5?f=json"),
        ("Census API", f"{CENSUS_BASE}/2023/acs/acs5?get=NAME&for=state:12" + (f"&key={CENSUS_API_KEY}" if CENSUS_API_KEY else "")),
        ("BLS API", BLS_BASE),
        ("Supabase", f"{SUPABASE_URL}/rest/v1/" if SUPABASE_URL else None),
        ("Mapbox", "configured" if MAPBOX_TOKEN else None),
    ]
    client = httpx.Client(timeout=10, headers=UA)
    for name, url in sources:
        if url == "configured":
            log("STATUS", f"{name}: TOKEN SET", "OK")
            continue
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
