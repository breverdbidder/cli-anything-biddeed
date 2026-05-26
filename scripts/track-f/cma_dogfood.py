"""
Track F CMA dogfooding driver — Duval
Pulls sold comps from HomeHarvest (Realtor.com source) for a single subject parcel,
applies arm's-length filters, computes CMA bands, writes CSV + JSON.

Run from GitHub Actions where Realtor.com IP block is less aggressive.
"""
import json, sys, os, warnings
from datetime import datetime
import pandas as pd
from homeharvest import scrape_property

warnings.filterwarnings("ignore")

SUBJECT = {
    "address": "2693 Sandusky Ave E, Jacksonville, FL 32216",
    "sqft": 1802, "beds": 3, "baths": 2.0, "lot_sqft": 7819,
    "lat": 30.296328, "lon": -81.559791, "po_avm": 279985,
}

print("="*70)
print(f"SUBJECT: {SUBJECT['address']}")
print(f"  {SUBJECT['beds']}BR/{SUBJECT['baths']}BA  {SUBJECT['sqft']} sqft")
print(f"  PropertyOnion AVM reference: ${SUBJECT['po_avm']:,}")
print("="*70)

t0 = datetime.now()
raw = scrape_property(
    location=SUBJECT["address"],
    listing_type="sold",
    radius=1.5,
    past_days=180,
    property_type=["single_family"],
    return_type="pandas",
)
print(f"\n[Fetch] {len(raw)} rows in {(datetime.now()-t0).total_seconds():.1f}s")

if len(raw) == 0:
    print("ABORT: zero rows"); sys.exit(2)

keep = ["property_url","street","city","state","zip_code","beds","full_baths","half_baths",
        "sqft","year_built","lot_sqft","list_price","sold_price","last_sold_date",
        "price_per_sqft","latitude","longitude","mls","mls_id","mls_status","status",
        "parcel_number","fips_code","tax_assessed_value"]
df = raw[[c for c in keep if c in raw.columns]].copy()

# Arm's-length filters
n0 = len(df)
df = df[df["sold_price"].notna() & (df["sold_price"] >= 10000) & (df["sold_price"] <= 1_500_000)]
sl, sh = int(SUBJECT["sqft"]*0.75), int(SUBJECT["sqft"]*1.25)
df = df[(df["sqft"] >= sl) & (df["sqft"] <= sh)]
df = df[(df["beds"] >= SUBJECT["beds"]-1) & (df["beds"] <= SUBJECT["beds"]+1)]
print(f"[Filter] {n0} -> {len(df)} after arm's-length + sqft({sl}-{sh}) + beds")

if len(df) < 3:
    print(f"WARNING: comp pool n={len(df)} — confidence LOW")

# CMA
df["ppsf"] = df["sold_price"] / df["sqft"]
ppsf_med = df["ppsf"].median()
cma_med = ppsf_med * SUBJECT["sqft"]
cma_p25 = df["ppsf"].quantile(0.25) * SUBJECT["sqft"]
cma_p75 = df["ppsf"].quantile(0.75) * SUBJECT["sqft"]
cv = (df["ppsf"].std()/df["ppsf"].mean()) if df["ppsf"].mean() else 0
conf = "HIGH" if (len(df)>=10 and cv<0.20) else ("MEDIUM" if len(df)>=5 else "LOW")

if "last_sold_date" in df.columns:
    df["last_sold_date"] = pd.to_datetime(df["last_sold_date"], errors="coerce")
    df["days_since_sale"] = (datetime.now() - df["last_sold_date"]).dt.days
    age_med = df["days_since_sale"].median()
else:
    age_med = None

print("\n" + "="*70)
print("CMA RESULT")
print("="*70)
print(f"comp_count:          {len(df)}")
print(f"comp_median_age:     {age_med:.0f} days" if age_med is not None else "comp_median_age:     unknown")
print(f"$/sqft median:       ${ppsf_med:,.2f}  (CV={cv:.1%})")
print(f"cma_market_value:    ${cma_med:,.0f}")
print(f"cma_low_p25:         ${cma_p25:,.0f}")
print(f"cma_high_p75:        ${cma_p75:,.0f}")
print(f"cma_confidence:      {conf}")
print(f"\nPropertyOnion AVM:   ${SUBJECT['po_avm']:,}")
print(f"PO_AVM / CMA_med:    {SUBJECT['po_avm']/cma_med:.2%}")
print(f"Delta CMA - PO:      ${cma_med - SUBJECT['po_avm']:,.0f}")
print("="*70)

# Persist
os.makedirs("/tmp/cma_out", exist_ok=True)
df.to_csv("/tmp/cma_out/comps.csv", index=False)
with open("/tmp/cma_out/result.json","w") as f:
    json.dump({
        "subject": SUBJECT,
        "cma_market_value": float(cma_med),
        "cma_low_p25": float(cma_p25),
        "cma_high_p75": float(cma_p75),
        "cma_confidence": conf,
        "comp_count": int(len(df)),
        "ppsf_median": float(ppsf_med),
        "ppsf_cv": float(cv),
        "comp_median_age_days": float(age_med) if age_med is not None else None,
        "po_avm": SUBJECT["po_avm"],
        "po_vs_cma_ratio": SUBJECT["po_avm"]/cma_med,
        "honesty_marker": "VERIFIED" if conf in ("HIGH","MEDIUM") else "INFERRED",
        "fetched_at": datetime.now().isoformat(),
    }, f, indent=2, default=str)
print("\nWrote /tmp/cma_out/comps.csv and /tmp/cma_out/result.json")
