#!/usr/bin/env python3
"""
sumter_f_nal_probe.py

Probe the FL DOR Statewide Cadastral FeatureServer NAL sale-history fields
for sumter's 3 tax-deed parcels that have NULL tier1_sold_amount.

Target parcels (TD-5028/5031/5036, confirmed SOLD per surplus list):
  G03A014 - TD-5028 (ROBINSON KENNETH C, 1575 Hollyberry Pl, The Villages)
  D20G135 - TD-5031 (ROBINSON RONALD W, 4989 Sandpiper Dr, Oxford)
  J34A003 - TD-5036 (PERKINS DIXIE ADAMS ETAL, 3951 S US 301, Bushnell)

Also probe TD-5056 (G07F008 - $1,467.39 opening, NOT redeemed per prior research)
and the 2 foreclosure cases (D03F058/2023-CA-000091, R14X015/2024-CA-000364,
D09E270/2024-CA-000367) for any recent sale records.

Strategy: SALE_YR1/MO1/PRC1 + QUAL_CD1 where QUAL_CD=11 means "Tax Deed" -
same pattern used successfully for lafayette's TD-2022-28 fix.

Data source: FL DOR Statewide Cadastral FeatureServer Layer 0
(https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/
Florida_Statewide_Cadastral/FeatureServer/0)
Same authoritative layer used by scripts/ingest_county.py and
scripts/shard9_run3645_sumter_i_parcel_enrichment.py for this county.
"""
import json
import urllib.request
import urllib.error
import os

CADASTRAL_URL = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
    "Florida_Statewide_Cadastral/FeatureServer/0/query"
)

SUMTER_PARCELS = {
    "TD-5028": "G03A014",
    "TD-5031": "D20G135",
    "TD-5036": "J34A003",
    "TD-5056": "G07F008",
    "2023-CA-000091": "D03F058",
    "2024-CA-000364": "R14X015",
    "2024-CA-000367": "D09E270",
}


def fetch_parcel(parcel_id):
    params = {
        "where": f"PARCEL_ID='{parcel_id}'",
        "outFields": (
            "PARCEL_ID,OWN_NAME,PHY_ADDR1,PHY_CITY,"
            "SALE_YR1,SALE_MO1,SALE_PRC1,QUAL_CD1,OR_BOOK1,OR_PAGE1,"
            "SALE_YR2,SALE_MO2,SALE_PRC2,QUAL_CD2,OR_BOOK2,OR_PAGE2,"
            "JV,AV_SD,CO_NO"
        ),
        "f": "json",
        "resultRecordCount": "3",
    }
    query_str = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items())
    url = f"{CADASTRAL_URL}?{query_str}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            features = data.get("features", [])
            if features:
                return features[0]["attributes"]
            return None
    except Exception as e:
        return {"error": str(e)}


def main():
    print("=" * 70)
    print("FL DOR NAL SALE HISTORY PROBE — sumter tax-deed parcels")
    print("=" * 70)
    
    found_amounts = []
    
    for case_number, parcel_id in SUMTER_PARCELS.items():
        print(f"\n[{case_number}] Parcel: {parcel_id}")
        attrs = fetch_parcel(parcel_id)
        if attrs is None:
            print("  -> NO RECORD FOUND in cadastral")
            continue
        if "error" in attrs:
            print(f"  -> ERROR: {attrs['error']}")
            continue
        
        print(f"  OWN_NAME: {attrs.get('OWN_NAME')}")
        print(f"  PHY_ADDR1: {attrs.get('PHY_ADDR1')} {attrs.get('PHY_CITY')}")
        print(f"  CO_NO: {attrs.get('CO_NO')}")
        print(f"  JV: {attrs.get('JV')}, AV_SD: {attrs.get('AV_SD')}")
        
        sale1_yr = attrs.get("SALE_YR1")
        sale1_mo = attrs.get("SALE_MO1")
        sale1_prc = attrs.get("SALE_PRC1")
        qual1 = attrs.get("QUAL_CD1")
        book1 = attrs.get("OR_BOOK1")
        page1 = attrs.get("OR_PAGE1")
        
        if sale1_yr and sale1_prc:
            print(f"  SALE_YR1={sale1_yr} SALE_MO1={sale1_mo} SALE_PRC1={sale1_prc} QUAL_CD1={qual1}")
            print(f"  OR_BOOK1={book1} OR_PAGE1={page1}")
            if qual1 == 11:
                print(f"  *** QUAL_CD=11 = Tax Deed! Sale price: ${sale1_prc} ***")
                found_amounts.append({
                    "case_number": case_number,
                    "parcel_id": parcel_id,
                    "sale_yr": sale1_yr,
                    "sale_mo": sale1_mo,
                    "sale_prc": sale1_prc,
                    "qual_cd": qual1,
                    "or_book": book1,
                    "or_page": page1,
                    "own_name": attrs.get("OWN_NAME"),
                })
        
        sale2_yr = attrs.get("SALE_YR2")
        sale2_prc = attrs.get("SALE_PRC2")
        qual2 = attrs.get("QUAL_CD2")
        if sale2_yr and sale2_prc:
            print(f"  SALE_YR2={sale2_yr} SALE_MO2={attrs.get('SALE_MO2')} SALE_PRC2={sale2_prc} QUAL_CD2={qual2}")
            if qual2 == 11:
                print(f"  *** SALE_YR2 QUAL_CD=11 = Tax Deed! Sale price: ${sale2_prc} ***")
    
    print("\n" + "=" * 70)
    print("SUMMARY OF QUALIFIED TAX DEED NAL RECORDS:")
    print("=" * 70)
    if found_amounts:
        for r in found_amounts:
            print(json.dumps(r, indent=2))
    else:
        print("No QUAL_CD=11 (Tax Deed) NAL records found for sumter parcels.")
        print("F criterion will remain blocked by lack of verified amounts.")


if __name__ == "__main__":
    main()
