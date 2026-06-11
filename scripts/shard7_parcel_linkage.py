#!/usr/bin/env python3
"""
SHARD-7 Parcel Linkage Implementation 
Letter E fix for hillsborough and lake (counties with GIS endpoints)

Links auction properties to county parcel data via GIS spatial queries.
This addresses the E metric which requires parcel linkage >=95%.
"""
import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
import time
import re

class Shard7ParcelLinkage:
    def __init__(self):
        self.supabase_url = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
        self.supabase_key = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
        
        # GIS endpoints for SHARD-7 counties that have them
        self.gis_config = {
            'hillsborough': {
                'base_url': 'https://maps.hillsboroughcounty.org/arcgis/rest/services',
                'parcel_layer': 'Property/Property_Information/MapServer/0',
                'parcel_id_field': 'PARCEL_ID',
                'address_field': 'PROPERTY_ADDRESS',
                'owner_field': 'OWNER_NAME'
            },
            'lake': {
                'base_url': 'https://gis.lakecountyfl.gov/arcgis/rest/services',
                'parcel_layer': 'Property/Parcels/MapServer/0', 
                'parcel_id_field': 'PARCEL_NO',
                'address_field': 'SITUS_ADDR',
                'owner_field': 'OWNER_NAME'
            }
        }
    
    def sb_headers(self):
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
    
    def sb_request(self, method, path, data=None):
        """Make Supabase API request"""
        url = f"{self.supabase_url}{path}"
        headers = self.sb_headers()
        
        if data:
            data = json.dumps(data).encode('utf-8')
        
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"Supabase request failed: {e}")
            return None
    
    def gis_request(self, url, params=None):
        """Make GIS ArcGIS REST API request"""
        if params:
            url += '?' + urllib.parse.urlencode(params)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (BidDeed-SHARD7-ParcelLinkage/1.0)'
        }
        
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"GIS request failed: {e}")
            return None
    
    def get_unllinked_auctions(self, county, limit=100):
        """Get auctions without parcel linkage for county"""
        params = urllib.parse.urlencode({
            'county': f'eq.{county}',
            'parcel_id': 'is.null',
            'property_address': 'not.is.null',
            'select': 'id,case_number,property_address,plaintiff,auction_date',
            'limit': limit
        })
        
        result = self.sb_request('GET', f'/rest/v1/multi_county_auctions?{params}')
        return result if result else []
    
    def normalize_address(self, address):
        """Normalize address for matching"""
        if not address:
            return ""
        
        # Common normalizations for Florida addresses
        normalized = address.upper().strip()
        
        # Replace common abbreviations
        replacements = {
            ' STREET': ' ST',
            ' AVENUE': ' AVE', 
            ' BOULEVARD': ' BLVD',
            ' DRIVE': ' DR',
            ' LANE': ' LN',
            ' ROAD': ' RD',
            ' CIRCLE': ' CIR',
            ' COURT': ' CT',
            ' PLACE': ' PL',
            ' TRAIL': ' TRL'
        }
        
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        
        # Remove extra whitespace and punctuation
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized.strip()
    
    def search_parcel_by_address(self, county, address):
        """Search for parcel using address via GIS"""
        gis_cfg = self.gis_config.get(county)
        if not gis_cfg:
            return None
        
        normalized_addr = self.normalize_address(address)
        if not normalized_addr:
            return None
        
        # Build query URL
        layer_url = f"{gis_cfg['base_url']}/{gis_cfg['parcel_layer']}/query"
        
        # Try different search strategies
        search_terms = [
            normalized_addr,
            normalized_addr.split(' ')[0] + ' ' + normalized_addr.split(' ')[1] if len(normalized_addr.split(' ')) > 1 else normalized_addr,
            ' '.join(normalized_addr.split(' ')[:3])  # First 3 words
        ]
        
        for search_term in search_terms:
            params = {
                'where': f"UPPER({gis_cfg['address_field']}) LIKE '%{search_term}%'",
                'outFields': f"{gis_cfg['parcel_id_field']},{gis_cfg['address_field']},{gis_cfg['owner_field']}",
                'returnGeometry': 'false',
                'f': 'json',
                'resultRecordCount': 5
            }
            
            result = self.gis_request(layer_url, params)
            
            if result and result.get('features'):
                # Return the best match (first result)
                feature = result['features'][0]
                attributes = feature.get('attributes', {})
                
                return {
                    'parcel_id': attributes.get(gis_cfg['parcel_id_field']),
                    'gis_address': attributes.get(gis_cfg['address_field']),
                    'owner_name': attributes.get(gis_cfg['owner_field']),
                    'search_term_used': search_term,
                    'confidence_score': self.calculate_address_similarity(address, attributes.get(gis_cfg['address_field'], ''))
                }
        
        return None
    
    def calculate_address_similarity(self, addr1, addr2):
        """Calculate similarity score between two addresses"""
        if not addr1 or not addr2:
            return 0.0
        
        norm1 = set(self.normalize_address(addr1).split())
        norm2 = set(self.normalize_address(addr2).split())
        
        if not norm1 or not norm2:
            return 0.0
        
        intersection = norm1 & norm2
        union = norm1 | norm2
        
        return len(intersection) / len(union) if union else 0.0
    
    def update_auction_parcel_link(self, auction_id, parcel_data):
        """Update auction record with parcel linkage"""
        update_data = {
            'parcel_id': parcel_data['parcel_id'],
            'parcel_address_gis': parcel_data['gis_address'],
            'parcel_owner_gis': parcel_data['owner_name'],
            'parcel_link_confidence': parcel_data['confidence_score'],
            'parcel_link_method': 'gis_address_search',
            'parcel_linked_at': datetime.now(timezone.utc).isoformat()
        }
        
        result = self.sb_request('PATCH', f'/rest/v1/multi_county_auctions?id=eq.{auction_id}', update_data)
        return bool(result)
    
    def process_county_parcel_linkage(self, county):
        """Process parcel linkage for a single county"""
        print(f"\n=== PROCESSING PARCEL LINKAGE: {county.upper()} ===")
        
        if county not in self.gis_config:
            print(f"No GIS configuration for {county} - skipping")
            return False
        
        # Get unlinked auctions
        unlinked_auctions = self.get_unllinked_auctions(county)
        print(f"Found {len(unlinked_auctions)} unlinked auctions")
        
        if not unlinked_auctions:
            print(f"No unlinked auctions for {county}")
            return True
        
        linked_count = 0
        high_confidence_count = 0
        
        for auction in unlinked_auctions:
            auction_id = auction.get('id')
            case_number = auction.get('case_number', 'Unknown')
            address = auction.get('property_address')
            
            if not address:
                print(f"  Skipping {case_number}: No address")
                continue
            
            print(f"  Linking {case_number}: {address}")
            
            # Search for parcel via GIS
            parcel_data = self.search_parcel_by_address(county, address)
            
            if parcel_data:
                confidence = parcel_data['confidence_score']
                if confidence > 0.7:  # High confidence threshold
                    # Update auction with parcel link
                    if self.update_auction_parcel_link(auction_id, parcel_data):
                        linked_count += 1
                        if confidence > 0.8:
                            high_confidence_count += 1
                        print(f"    ✅ Linked to parcel {parcel_data['parcel_id']} (confidence: {confidence:.2f})")
                    else:
                        print(f"    ❌ Failed to update auction record")
                else:
                    print(f"    ⚠️ Low confidence match ({confidence:.2f}) - skipping")
            else:
                print(f"    ❌ No parcel found")
            
            time.sleep(0.2)  # Rate limiting for GIS API
        
        success_rate = (linked_count / len(unlinked_auctions)) * 100 if unlinked_auctions else 0
        high_conf_rate = (high_confidence_count / linked_count) * 100 if linked_count else 0
        
        print(f"✅ {county}: Linked {linked_count}/{len(unlinked_auctions)} auctions ({success_rate:.1f}%)")
        print(f"   High confidence links: {high_confidence_count}/{linked_count} ({high_conf_rate:.1f}%)")
        
        return linked_count > 0
    
    def run_all_counties(self):
        """Run parcel linkage for all GIS-enabled SHARD-7 counties"""
        print("🚀 STARTING SHARD-7 PARCEL LINKAGE PROCESSING")
        print(f"Counties with GIS: {list(self.gis_config.keys())}")
        
        results = {}
        total_processed = 0
        
        for county in self.gis_config.keys():
            try:
                success = self.process_county_parcel_linkage(county)
                results[county] = 'SUCCESS' if success else 'NO_WORK_NEEDED'
                total_processed += 1
            except Exception as e:
                print(f"❌ Error processing {county}: {e}")
                results[county] = f'ERROR: {e}'
        
        print(f"\n=== PARCEL LINKAGE SUMMARY ===")
        print(f"Counties processed: {total_processed}")
        
        for county, status in results.items():
            icon = "✅" if 'SUCCESS' in status else "⚠️" if 'NO_WORK' in status else "❌"
            print(f"  {icon} {county}: {status}")
        
        return results

def main():
    """Main execution function"""
    start_time = datetime.now()
    print(f"SHARD-7 Parcel Linkage started at {start_time}")
    
    processor = Shard7ParcelLinkage()
    
    try:
        results = processor.run_all_counties()
        
        # Save results
        output_file = f"shard7_parcel_linkage_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': start_time.isoformat(),
                'results': results,
                'duration_seconds': (datetime.now() - start_time).total_seconds()
            }, f, indent=2)
        
        print(f"\n✅ Parcel linkage processing completed")
        print(f"📄 Results saved to: {output_file}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Parcel linkage processing failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())