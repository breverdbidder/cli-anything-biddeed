"""
ZoneWise SSOT Consolidation — Modal Parallel Pipeline
67 counties processed simultaneously via Modal serverless compute.
"""
import modal

app = modal.App("zonewise-consolidation")

image = modal.Image.debian_slim(python_version="3.11").pip_install("psycopg2-binary")

DOR_COUNTIES = {
    1:"ALACHUA",2:"BAKER",3:"BAY",4:"BRADFORD",5:"BREVARD",6:"BROWARD",7:"CALHOUN",
    8:"CHARLOTTE",9:"CITRUS",10:"CLAY",11:"COLLIER",12:"COLUMBIA",13:"DESOTO",14:"DIXIE",
    15:"DUVAL",16:"ESCAMBIA",17:"FLAGLER",18:"FRANKLIN",19:"GADSDEN",20:"GILCHRIST",
    21:"GLADES",22:"GULF",23:"HAMILTON",24:"HARDEE",25:"HENDRY",26:"HERNANDO",
    27:"HIGHLANDS",28:"HILLSBOROUGH",29:"HOLMES",30:"INDIAN RIVER",31:"JACKSON",
    32:"JEFFERSON",33:"LAFAYETTE",34:"LAKE",35:"LEE",36:"LEON",37:"LEVY",38:"LIBERTY",
    39:"MADISON",40:"MANATEE",41:"MARION",42:"MARTIN",43:"MIAMI-DADE",44:"MONROE",
    45:"NASSAU",46:"OKALOOSA",47:"OKEECHOBEE",48:"ORANGE",49:"OSCEOLA",50:"PALM BEACH",
    51:"PASCO",52:"PINELLAS",53:"POLK",54:"PUTNAM",55:"ST JOHNS",56:"ST LUCIE",
    57:"SANTA ROSA",58:"SARASOTA",59:"SEMINOLE",60:"SUMTER",61:"SUWANNEE",62:"TAYLOR",
    63:"UNION",64:"VOLUSIA",65:"WAKULLA",66:"WALTON",67:"WASHINGTON"
}

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("supabase-db")],
    timeout=600,
    retries=2,
)
def consolidate_county(co_no: int) -> dict:
    """Consolidate one county from fl_parcels → zw_parcels"""
    import psycopg2
    import os
    
    county_name = DOR_COUNTIES.get(co_no, f"UNKNOWN_{co_no}")
    
    # Try pooler first (IPv4 native), fallback to direct
    try:
        conn = psycopg2.connect(
            host="aws-0-us-east-1.pooler.supabase.com",
            port=6543,
            user="postgres.mocerqjnksmhcjzxrewo",
            password=os.environ["SUPABASE_DB_PASSWORD"],
            database="postgres",
            sslmode="require",
            connect_timeout=30
        )
    except Exception:
        conn = psycopg2.connect(
            host="db.mocerqjnksmhcjzxrewo.supabase.co",
            port=5432,
            user="postgres",
            password=os.environ["SUPABASE_DB_PASSWORD"],
            database="postgres",
            sslmode="require",
            connect_timeout=30
        )
    conn.autocommit = True
    cur = conn.cursor()
    
    # Step 1: Insert parcels from fl_parcels
    cur.execute(f"""
        INSERT INTO zw_parcels (
            co_no, county, pin, pin_clean,
            owner_name, owner_addr1, owner_city, owner_state, owner_zip,
            site_addr, site_city, site_zip,
            luse_code, num_buildings, sqft_heated,
            year_built, year_built_eff,
            val_market, val_land, val_assessed, val_taxable,
            sale_price, acres_gis, photo_url, extracted_at, data_source
        )
        SELECT
            fp.co_no, '{county_name}', fp.parcel_id,
            REGEXP_REPLACE(fp.parcel_id, '[^0-9]', '', 'g'),
            fp.own_name, fp.own_addr1, fp.own_city, fp.own_state, fp.own_zipcd,
            fp.phy_addr1, fp.phy_city, fp.phy_zipcd,
            fp.dor_uc, fp.no_buldng, fp.tot_lvg_ar,
            fp.act_yr_blt, fp.eff_yr_blt,
            fp.jv, fp.lnd_val, fp.av_sd, fp.tv_sd,
            fp.sale_prc1,
            CASE WHEN fp.lnd_sqfoot > 0 THEN ROUND(fp.lnd_sqfoot::numeric / 43560.0, 4) END,
            fp.photo_url, fp.scraped_at::date, 'FL_DOR'
        FROM fl_parcels fp
        WHERE fp.co_no = {co_no}
        ON CONFLICT (co_no, pin) DO UPDATE SET
            owner_name = EXCLUDED.owner_name,
            val_market = EXCLUDED.val_market,
            val_assessed = EXCLUDED.val_assessed,
            updated_at = NOW()
    """)
    inserted = cur.rowcount
    
    # Step 2: Backfill zoning from zoning_assignments (if county has data)
    cur.execute(f"""
        UPDATE zw_parcels z
        SET zoning_code = za.zone_code,
            zoning_jurisdiction = za.jurisdiction,
            photo_url = COALESCE(z.photo_url, za.photo_url)
        FROM zoning_assignments za
        WHERE z.co_no = za.co_no AND z.pin = za.parcel_id
            AND za.zone_code IS NOT NULL AND z.zoning_code IS NULL
            AND z.co_no = {co_no}
    """)
    zoned_from_za = cur.rowcount
    
    # Step 3: Backfill zoning from fl_parcels.zone_code
    cur.execute(f"""
        UPDATE zw_parcels z
        SET zoning_code = fp.zone_code
        FROM fl_parcels fp
        WHERE z.co_no = fp.co_no AND z.pin = fp.parcel_id
            AND fp.zone_code IS NOT NULL AND z.zoning_code IS NULL
            AND z.co_no = {co_no}
    """)
    zoned_from_fp = cur.rowcount
    
    # Step 4: Decode zoning descriptions
    cur.execute(f"""
        UPDATE zw_parcels z
        SET zoning_desc = zc.zoning_desc,
            zoning_category = zc.category,
            zoning_permitted = zc.permitted_uses::jsonb,
            zoning_max_ht = zc.max_height_ft,
            zoning_min_lot = zc.min_lot_size,
            zoning_setbacks = zc.setbacks::jsonb
        FROM zoning_codes zc
        WHERE LOWER(z.county) = zc.county
            AND LOWER(COALESCE(z.zoning_jurisdiction, 'unincorporated')) = zc.jurisdiction
            AND z.zoning_code = zc.zoning_code
            AND z.zoning_desc IS NULL AND z.co_no = {co_no}
    """)
    decoded = cur.rowcount
    
    # Step 5: DOR land use descriptions
    cur.execute(f"""
        UPDATE zw_parcels z
        SET luse_desc = d.description
        FROM dor_land_use_codes d
        WHERE LPAD(z.luse_code, 3, '0') = d.dor_uc
            AND z.luse_desc IS NULL AND z.co_no = {co_no}
    """)
    luse = cur.rowcount
    
    # Step 6: Get final count
    cur.execute(f"SELECT count(*), count(zoning_code) FROM zw_parcels WHERE co_no = {co_no}")
    total, with_zoning = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return {
        "co_no": co_no,
        "county": county_name,
        "inserted": inserted,
        "zoned_from_assignments": zoned_from_za,
        "zoned_from_parcels": zoned_from_fp,
        "decoded": decoded,
        "luse_backfilled": luse,
        "total": total,
        "with_zoning": with_zoning,
        "zoning_pct": round(with_zoning / max(total, 1) * 100, 1)
    }


@app.local_entrypoint()
def main():
    """Run consolidation for all 67 counties in parallel"""
    import json
    
    print("🚀 ZoneWise SSOT Consolidation — 67 Counties Parallel")
    print("=" * 60)
    
    # Launch all 67 counties in parallel
    results = list(consolidate_county.map(range(1, 68)))
    
    # Sort and display results
    total_parcels = 0
    total_zoned = 0
    enterprise = []
    
    print(f"\n{'County':<20} {'Parcels':>10} {'Zoned':>8} {'Zone%':>7} {'Status':>12}")
    print("-" * 60)
    
    for r in sorted(results, key=lambda x: -x["total"]):
        total_parcels += r["total"]
        total_zoned += r["with_zoning"]
        status = "ENTERPRISE" if r["zoning_pct"] >= 85 else "PARTIAL" if r["total"] > 0 else "EMPTY"
        if status == "ENTERPRISE":
            enterprise.append(r["county"])
        print(f"{r['county']:<20} {r['total']:>10,} {r['with_zoning']:>8,} {r['zoning_pct']:>6.1f}% {status:>12}")
    
    print("=" * 60)
    print(f"TOTAL: {total_parcels:,} parcels, {total_zoned:,} zoned ({round(total_zoned/max(total_parcels,1)*100,1)}%)")
    print(f"ENTERPRISE counties: {len(enterprise)}")
    print(f"\nResults JSON:")
    print(json.dumps(results, indent=2))
