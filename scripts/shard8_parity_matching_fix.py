#!/usr/bin/env python3
"""
SHARD-8 PARITY MATCHING FIX  
Improve Letters C/D (parity_clean >=95%, parity_any >=95%) for counties with poor matching

TARGET: indian_river
- Letter C: 14.7% (214 of 1,452) → need 1,379 matched_clean for 95%
- Letter D: 52.2% (758 of 1,452) → need 1,380 matched_any for 95%

ROOT CAUSE: Case number format inconsistencies between:
- Our scraped auctions (multi_county_auctions.case_number)
- PropertyOnion parity comparison source

APPROACH:
1. Analyze PropertyOnion case number patterns for indian_river
2. Normalize case numbers in multi_county_auctions
3. Build fuzzy matching algorithms for edge cases
4. Update parity_status records with improved matches
5. Verify Letters C/D improve

NOTE: PropertyOnion is litmus ONLY - never ingest as data source per guardrails.
"""
import os
import sys
import json
import re
import time
from datetime import datetime, timezone, date, timedelta
from typing import Dict, List, Optional, Tuple, Set
import logging
from difflib import SequenceMatcher

try:
    import httpx
    import requests
    from collections import defaultdict, Counter
except ImportError:
    print("ERROR: Required packages not available. Need: httpx, requests")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_KEY:
    print("ERROR: No Supabase API key found")
    sys.exit(1)

BASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

client = httpx.Client(timeout=60)

# Counties needing parity matching fixes
PARITY_FIX_TARGETS = {
    'indian_river': {
        'priority': 'critical',      # Worst parity rates: 14.7% clean, 52.2% any
        'current_clean_pct': 14.7,   # 214 of 1,452
        'current_any_pct': 52.2,     # 758 of 1,452
        'target_clean': 1379,        # Need for 95%
        'target_any': 1380,          # Need for 95%
        'total_auctions': 1452,
        'common_prefixes': ['FC-', 'TD-', 'FORECL-', 'TAX-'],
        'normalize_patterns': [
            (r'^(FC|TD|FORECL|TAX)-?', ''),    # Remove prefixes
            (r'[^A-Z0-9-]', ''),               # Keep only alphanumeric and dashes
            (r'-+', '-'),                       # Collapse multiple dashes
            (r'^-|-$', '')                      # Trim leading/trailing dashes
        ]
    },
    'volusia': {
        'priority': 'secondary',     # Better rates but room for improvement
        'current_clean_pct': 10.0,   # 1,551 of 15,577
        'current_any_pct': 47.8,     # 7,453 of 15,577
        'target_clean': 14798,       # Need for 95%
        'target_any': 14798,         # Need for 95%
        'total_auctions': 15577,
        'common_prefixes': ['2024-', '2023-', '2022-', 'FC-', 'TD-'],
        'normalize_patterns': [
            (r'^(FC|TD)-?', ''),
            (r'[^A-Z0-9-]', ''),
            (r'-+', '-'),
            (r'^-|-$', '')
        ]
    },
    'lee': {
        'priority': 'secondary',     # Better rates but room for improvement  
        'current_clean_pct': 11.4,   # 2,010 of 17,701
        'current_any_pct': 58.2,     # 10,298 of 17,701
        'target_clean': 16816,       # Need for 95%
        'target_any': 16816,         # Need for 95%
        'total_auctions': 17701,
        'common_prefixes': ['2024-', '2023-', 'FC-', 'FO-'],
        'normalize_patterns': [
            (r'^(FC|FO|TD)-?', ''),
            (r'[^A-Z0-9-]', ''),
            (r'-+', '-'),
            (r'^-|-$', '')
        ]
    }
}

class ParityMatchingFixer:
    def __init__(self, dry_run=False, max_records=2000):
        self.dry_run = dry_run
        self.max_records = max_records
        self.results = {}
        self.session_stats = {
            'start_time': datetime.now(timezone.utc),
            'counties_processed': 0,
            'auctions_analyzed': 0,
            'new_matches_found': 0,
            'parity_improvements': {}
        }
        
    def get_current_parity_status(self, county: str) -> Dict:
        """Get current parity matching metrics for county"""
        try:
            # Get total auctions
            auctions_response = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                headers=BASE_HEADERS,
                params={
                    'county': f'eq.{county}',
                    'select': 'count'
                }
            )
            
            if auctions_response.status_code != 200:
                logger.error(f"Failed to get total auctions for {county}")
                return {}
            
            total_auctions = len(auctions_response.json())
            
            # Get parity status counts
            parity_response = client.get(
                f"{SUPABASE_URL}/rest/v1/parity_status",
                headers=BASE_HEADERS,
                params={
                    'county_slug': f'eq.{county}',
                    'select': 'matching_status,count(*)',
                    'group': 'matching_status'
                }
            )
            
            parity_counts = {}
            if parity_response.status_code == 200:
                for row in parity_response.json():
                    status = row.get('matching_status', 'unknown')
                    count = row.get('count', 0)
                    parity_counts[status] = count
            
            # Calculate rates
            matched_clean = parity_counts.get('clean_match', 0)
            matched_any = sum(parity_counts.get(status, 0) for status in ['clean_match', 'fuzzy_match', 'partial_match'])
            
            clean_pct = (matched_clean / total_auctions * 100) if total_auctions > 0 else 0
            any_pct = (matched_any / total_auctions * 100) if total_auctions > 0 else 0
            
            return {
                'county': county,
                'total_auctions': total_auctions,
                'matched_clean': matched_clean,
                'matched_any': matched_any,
                'clean_pct': clean_pct,
                'any_pct': any_pct,
                'target_clean_95': int(total_auctions * 0.95),
                'target_any_95': int(total_auctions * 0.95),
                'gap_clean': max(0, int(total_auctions * 0.95) - matched_clean),
                'gap_any': max(0, int(total_auctions * 0.95) - matched_any),
                'letter_c_status': 'PASS' if clean_pct >= 95.0 else 'FAIL',
                'letter_d_status': 'PASS' if any_pct >= 95.0 else 'FAIL',
                'parity_breakdown': parity_counts
            }
            
        except Exception as e:
            logger.error(f"Error getting parity status for {county}: {e}")
            return {}
    
    def analyze_case_number_patterns(self, county: str) -> Dict:
        """Analyze case number patterns in our auctions vs PropertyOnion"""
        logger.info(f"  📊 Analyzing case number patterns for {county}...")
        
        try:
            # Get sample of our auction case numbers
            our_auctions_response = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                headers=BASE_HEADERS,
                params={
                    'county': f'eq.{county}',
                    'case_number': 'not.is.null',
                    'select': 'case_number,auction_date',
                    'limit': '1000',
                    'order': 'auction_date.desc'
                }
            )
            
            # Get PropertyOnion case numbers from parity_status
            po_response = client.get(
                f"{SUPABASE_URL}/rest/v1/parity_status", 
                headers=BASE_HEADERS,
                params={
                    'county_slug': f'eq.{county}',
                    'propertyonion_case_number': 'not.is.null',
                    'select': 'propertyonion_case_number,our_case_number,matching_status',
                    'limit': '1000'
                }
            )
            
            if our_auctions_response.status_code != 200 or po_response.status_code != 200:
                logger.error(f"  Failed to get case numbers for pattern analysis")
                return {}
            
            our_cases = [a['case_number'] for a in our_auctions_response.json() if a.get('case_number')]
            po_cases = [p['propertyonion_case_number'] for p in po_response.json() if p.get('propertyonion_case_number')]
            parity_records = po_response.json()
            
            # Analyze patterns
            analysis = {
                'our_sample_size': len(our_cases),
                'po_sample_size': len(po_cases),
                'our_patterns': self._extract_patterns(our_cases),
                'po_patterns': self._extract_patterns(po_cases),
                'format_mismatches': [],
                'normalization_opportunities': []
            }
            
            # Find format mismatches
            for record in parity_records:
                our_case = record.get('our_case_number', '')
                po_case = record.get('propertyonion_case_number', '')
                status = record.get('matching_status', '')
                
                if our_case and po_case and status in ['no_match', 'mismatch']:
                    similarity = self._calculate_similarity(our_case, po_case)
                    if similarity > 0.7:  # High similarity but no match suggests format issue
                        analysis['format_mismatches'].append({
                            'our_case': our_case,
                            'po_case': po_case,
                            'similarity': similarity,
                            'status': status
                        })
            
            # Suggest normalization rules
            analysis['normalization_opportunities'] = self._suggest_normalizations(
                analysis['our_patterns'], 
                analysis['po_patterns'],
                analysis['format_mismatches']
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"  Error analyzing patterns: {e}")
            return {}
    
    def _extract_patterns(self, case_numbers: List[str]) -> Dict:
        """Extract common patterns from case number list"""
        patterns = {
            'prefixes': Counter(),
            'suffixes': Counter(),
            'lengths': Counter(),
            'formats': Counter(),
            'year_patterns': Counter()
        }
        
        for case in case_numbers:
            if not case:
                continue
                
            case = case.strip().upper()
            
            # Prefixes (first 2-3 chars)
            if len(case) >= 2:
                patterns['prefixes'][case[:2]] += 1
            if len(case) >= 3:
                patterns['prefixes'][case[:3]] += 1
            
            # Suffixes
            if len(case) >= 2:
                patterns['suffixes'][case[-2:]] += 1
            
            # Lengths
            patterns['lengths'][len(case)] += 1
            
            # Format patterns (simplified)
            format_pattern = re.sub(r'\d', 'N', case)
            format_pattern = re.sub(r'[A-Z]', 'L', format_pattern)
            patterns['formats'][format_pattern] += 1
            
            # Year patterns
            years = re.findall(r'20\d{2}', case)
            for year in years:
                patterns['year_patterns'][year] += 1
        
        # Return top patterns only
        return {
            'top_prefixes': patterns['prefixes'].most_common(10),
            'top_suffixes': patterns['suffixes'].most_common(5),
            'common_lengths': patterns['lengths'].most_common(5),
            'common_formats': patterns['formats'].most_common(10),
            'year_patterns': patterns['year_patterns'].most_common(5)
        }
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two case numbers"""
        if not str1 or not str2:
            return 0.0
        return SequenceMatcher(None, str1.upper(), str2.upper()).ratio()
    
    def _suggest_normalizations(self, our_patterns: Dict, po_patterns: Dict, mismatches: List[Dict]) -> List[Dict]:
        """Suggest case number normalization rules"""
        suggestions = []
        
        # Analyze prefix mismatches
        our_prefixes = {p[0] for p in our_patterns.get('top_prefixes', [])}
        po_prefixes = {p[0] for p in po_patterns.get('top_prefixes', [])}
        
        if 'FC-' in our_prefixes and 'FC' in po_prefixes:
            suggestions.append({
                'rule': 'remove_prefix_dash',
                'pattern': r'^(FC|TD|FORECL)-',
                'replacement': r'\1',
                'reason': 'PropertyOnion uses prefixes without dashes'
            })
        
        # Analyze format mismatches
        format_issues = defaultdict(int)
        for mismatch in mismatches:
            our_case = mismatch['our_case']
            po_case = mismatch['po_case']
            
            if '-' in our_case and '-' not in po_case:
                format_issues['remove_dashes'] += 1
            if len(our_case) != len(po_case):
                format_issues['length_mismatch'] += 1
                
        # Add format-based suggestions
        for issue, count in format_issues.most_common(3):
            if issue == 'remove_dashes' and count > 5:
                suggestions.append({
                    'rule': 'remove_internal_dashes',
                    'pattern': r'-',
                    'replacement': '',
                    'reason': f'{count} cases suggest dash removal helps matching'
                })
        
        return suggestions
    
    def normalize_case_number(self, case_number: str, county: str) -> str:
        """Normalize case number for better matching"""
        if not case_number:
            return case_number
            
        config = PARITY_FIX_TARGETS.get(county, {})
        patterns = config.get('normalize_patterns', [])
        
        normalized = case_number.strip().upper()
        
        # Apply county-specific normalization patterns
        for pattern, replacement in patterns:
            normalized = re.sub(pattern, replacement, normalized)
        
        return normalized
    
    def find_fuzzy_matches(self, county: str, unmatched_auctions: List[Dict], po_case_numbers: Set[str]) -> List[Dict]:
        """Find fuzzy matches between unmatched auctions and PropertyOnion cases"""
        fuzzy_matches = []
        
        logger.info(f"  🔍 Finding fuzzy matches for {len(unmatched_auctions)} unmatched auctions...")
        
        for auction in unmatched_auctions[:self.max_records]:  # Limit for performance
            our_case = auction.get('case_number', '')
            if not our_case:
                continue
                
            # Normalize our case number
            normalized_our = self.normalize_case_number(our_case, county)
            
            best_match = None
            best_score = 0.0
            
            # Try exact match with normalized
            if normalized_our in po_case_numbers:
                best_match = normalized_our
                best_score = 1.0
            else:
                # Try fuzzy matching
                for po_case in po_case_numbers:
                    score = self._calculate_similarity(normalized_our, po_case)
                    if score > best_score and score >= 0.8:  # High similarity threshold
                        best_match = po_case
                        best_score = score
            
            if best_match and best_score >= 0.8:
                fuzzy_matches.append({
                    'auction_id': auction['id'],
                    'our_case_original': our_case,
                    'our_case_normalized': normalized_our,
                    'po_case_matched': best_match,
                    'similarity_score': best_score,
                    'match_type': 'exact_normalized' if best_score == 1.0 else 'fuzzy',
                    'auction_date': auction.get('auction_date'),
                    'sale_type': auction.get('sale_type')
                })
        
        logger.info(f"  ✅ Found {len(fuzzy_matches)} potential fuzzy matches")
        return fuzzy_matches
    
    def update_parity_matches(self, county: str, new_matches: List[Dict]) -> int:
        """Update parity_status with new matches"""
        if not new_matches:
            return 0
        
        logger.info(f"  💾 Updating parity_status with {len(new_matches)} new matches...")
        
        if self.dry_run:
            logger.info(f"  Would update {len(new_matches)} parity records")
            return len(new_matches)
        
        updated_count = 0
        
        for match in new_matches:
            try:
                # Check if parity record exists
                existing_response = client.get(
                    f"{SUPABASE_URL}/rest/v1/parity_status",
                    headers=BASE_HEADERS,
                    params={
                        'county_slug': f'eq.{county}',
                        'our_case_number': f'eq.{match["our_case_original"]}',
                        'limit': '1'
                    }
                )
                
                parity_data = {
                    'county_slug': county,
                    'our_case_number': match['our_case_original'],
                    'propertyonion_case_number': match['po_case_matched'],
                    'matching_status': 'clean_match' if match['match_type'] == 'exact_normalized' else 'fuzzy_match',
                    'similarity_score': match['similarity_score'],
                    'match_method': f"shard8_normalize_{match['match_type']}",
                    'matched_at': datetime.now(timezone.utc).isoformat(),
                    'notes': f"Normalized: {match['our_case_normalized']}"
                }
                
                if existing_response.status_code == 200 and existing_response.json():
                    # Update existing record
                    record_id = existing_response.json()[0]['id']
                    update_response = client.patch(
                        f"{SUPABASE_URL}/rest/v1/parity_status",
                        headers=BASE_HEADERS,
                        params={'id': f'eq.{record_id}'},
                        json=parity_data
                    )
                    
                    if update_response.status_code in [200, 204]:
                        updated_count += 1
                    else:
                        logger.warning(f"    Failed to update parity record {record_id}: {update_response.status_code}")
                else:
                    # Insert new record
                    insert_response = client.post(
                        f"{SUPABASE_URL}/rest/v1/parity_status",
                        headers=BASE_HEADERS,
                        json=parity_data
                    )
                    
                    if insert_response.status_code in [200, 201]:
                        updated_count += 1
                    else:
                        logger.warning(f"    Failed to insert parity record: {insert_response.status_code}")
                
            except Exception as e:
                logger.warning(f"    Error updating parity for {match['our_case_original']}: {e}")
                continue
        
        logger.info(f"  ✅ Updated {updated_count} parity records")
        return updated_count
    
    def fix_county_parity(self, county: str, config: Dict) -> Dict:
        """Fix parity matching for a single county"""
        logger.info(f"\n{'='*60}")
        logger.info(f"FIXING PARITY: {county.upper()} (priority: {config['priority']})")
        logger.info(f"{'='*60}")
        
        # Get baseline metrics
        before_status = self.get_current_parity_status(county)
        if not before_status:
            return {'error': 'Failed to get baseline status'}
            
        logger.info(f"  Current status:")
        logger.info(f"    Total auctions: {before_status['total_auctions']:,}")
        logger.info(f"    Clean matches: {before_status['matched_clean']:,} ({before_status['clean_pct']:.1f}%)")
        logger.info(f"    Any matches: {before_status['matched_any']:,} ({before_status['any_pct']:.1f}%)")
        logger.info(f"    Gap to 95% clean: {before_status['gap_clean']:,}")
        logger.info(f"    Gap to 95% any: {before_status['gap_any']:,}")
        
        if before_status['clean_pct'] >= 95.0 and before_status['any_pct'] >= 95.0:
            logger.info(f"  ✅ Already above 95% thresholds!")
            return {
                'county': county,
                'status': 'already_passing',
                'before_status': before_status,
                'after_status': before_status
            }
        
        # Analyze case number patterns
        pattern_analysis = self.analyze_case_number_patterns(county)
        logger.info(f"  📊 Pattern analysis completed:")
        logger.info(f"    Our sample: {pattern_analysis.get('our_sample_size', 0):,} case numbers")
        logger.info(f"    PO sample: {pattern_analysis.get('po_sample_size', 0):,} case numbers")
        logger.info(f"    Format mismatches: {len(pattern_analysis.get('format_mismatches', [])):,}")
        
        # Get unmatched auctions
        unmatched_response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers=BASE_HEADERS,
            params={
                'county': f'eq.{county}',
                'case_number': 'not.is.null',
                'select': 'id,case_number,auction_date,sale_type',
                'limit': str(self.max_records)
            }
        )
        
        if unmatched_response.status_code != 200:
            logger.error(f"  Failed to get unmatched auctions")
            return {'error': 'Failed to get unmatched auctions'}
        
        all_auctions = unmatched_response.json()
        
        # Get PropertyOnion case numbers
        po_response = client.get(
            f"{SUPABASE_URL}/rest/v1/parity_status",
            headers=BASE_HEADERS,
            params={
                'county_slug': f'eq.{county}',
                'propertyonion_case_number': 'not.is.null',
                'select': 'propertyonion_case_number',
                'limit': '10000'
            }
        )
        
        po_case_numbers = set()
        if po_response.status_code == 200:
            po_case_numbers = {p['propertyonion_case_number'] for p in po_response.json() if p.get('propertyonion_case_number')}
        
        logger.info(f"  PropertyOnion cases available for matching: {len(po_case_numbers):,}")
        
        # Find fuzzy matches
        new_matches = self.find_fuzzy_matches(county, all_auctions, po_case_numbers)
        
        # Update parity status
        updated_count = self.update_parity_matches(county, new_matches)
        
        # Get final metrics
        after_status = self.get_current_parity_status(county)
        
        if after_status:
            clean_improvement = after_status['clean_pct'] - before_status['clean_pct']
            any_improvement = after_status['any_pct'] - before_status['any_pct']
            
            logger.info(f"  📊 Final status:")
            logger.info(f"    Clean matches: {after_status['matched_clean']:,} (+{after_status['matched_clean'] - before_status['matched_clean']:,}) = {after_status['clean_pct']:.1f}% (+{clean_improvement:.1f}%)")
            logger.info(f"    Any matches: {after_status['matched_any']:,} (+{after_status['matched_any'] - before_status['matched_any']:,}) = {after_status['any_pct']:.1f}% (+{any_improvement:.1f}%)")
            
            if after_status['clean_pct'] >= 95.0:
                logger.info(f"  🎯 LETTER C: PASS (≥95% clean matching)")
            else:
                logger.info(f"  📊 LETTER C: FAIL (need {95.0 - after_status['clean_pct']:.1f}% more)")
                
            if after_status['any_pct'] >= 95.0:
                logger.info(f"  🎯 LETTER D: PASS (≥95% any matching)")
            else:
                logger.info(f"  📊 LETTER D: FAIL (need {95.0 - after_status['any_pct']:.1f}% more)")
        else:
            after_status = before_status
            clean_improvement = any_improvement = 0
        
        result = {
            'county': county,
            'status': 'improved' if updated_count > 0 else 'no_change',
            'before_status': before_status,
            'after_status': after_status,
            'pattern_analysis': pattern_analysis,
            'new_matches_found': len(new_matches),
            'parity_records_updated': updated_count,
            'clean_improvement': clean_improvement,
            'any_improvement': any_improvement
        }
        
        self.session_stats['auctions_analyzed'] += len(all_auctions)
        self.session_stats['new_matches_found'] += len(new_matches)
        self.session_stats['parity_improvements'][county] = {
            'clean': clean_improvement,
            'any': any_improvement
        }
        
        return result
    
    def run_parity_fixes(self):
        """Run parity matching fixes for target counties"""
        logger.info(f"SHARD-8 PARITY MATCHING FIX")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        logger.info(f"Max records per county: {self.max_records:,}")
        logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        
        # Process counties by priority
        critical_counties = [k for k, v in PARITY_FIX_TARGETS.items() if v.get('priority') == 'critical']
        secondary_counties = [k for k, v in PARITY_FIX_TARGETS.items() if v.get('priority') == 'secondary']
        
        logger.info(f"\nCritical priority: {critical_counties}")
        logger.info(f"Secondary priority: {secondary_counties}")
        
        all_counties = critical_counties + secondary_counties
        
        for county in all_counties:
            config = PARITY_FIX_TARGETS[county]
            
            try:
                result = self.fix_county_parity(county, config)
                self.results[county] = result
                self.session_stats['counties_processed'] += 1
                
                # Rate limiting
                time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info(f"\n\n⚠️  Parity fix interrupted by user")
                break
            except Exception as e:
                logger.error(f"\n❌ FAILED to fix parity for {county}: {e}")
                self.results[county] = {
                    'county': county,
                    'status': 'failed',
                    'error': str(e)
                }
        
        # Final summary
        self.print_summary()
    
    def print_summary(self):
        """Print parity fix summary"""
        elapsed = datetime.now(timezone.utc) - self.session_stats['start_time']
        
        logger.info(f"\n{'='*80}")
        logger.info(f"PARITY MATCHING FIX SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Session time: {elapsed.total_seconds()/60:.1f} minutes")
        logger.info(f"Counties processed: {self.session_stats['counties_processed']}")
        logger.info(f"Auctions analyzed: {self.session_stats['auctions_analyzed']:,}")
        logger.info(f"New matches found: {self.session_stats['new_matches_found']:,}")
        
        for county, result in self.results.items():
            if result.get('error'):
                logger.info(f"\n{county.upper()}: ❌ FAILED - {result['error']}")
                continue
            
            status = result.get('status', 'unknown')
            before = result.get('before_status', {})
            after = result.get('after_status', {})
            
            logger.info(f"\n{county.upper()} ({status}):")
            logger.info(f"  Letter C (clean): {before.get('clean_pct', 0):.1f}% → {after.get('clean_pct', 0):.1f}% (+{result.get('clean_improvement', 0):.1f}%)")
            logger.info(f"  Letter D (any): {before.get('any_pct', 0):.1f}% → {after.get('any_pct', 0):.1f}% (+{result.get('any_improvement', 0):.1f}%)")
            logger.info(f"  New matches: {result.get('new_matches_found', 0):,}")
            logger.info(f"  Records updated: {result.get('parity_records_updated', 0):,}")
            
            # Letter status
            c_status = "PASS" if after.get('clean_pct', 0) >= 95.0 else "FAIL"
            d_status = "PASS" if after.get('any_pct', 0) >= 95.0 else "FAIL"
            logger.info(f"  🎯 Letter C: {c_status}, Letter D: {d_status}")
        
        logger.info(f"\n📋 NEXT ACTIONS:")
        logger.info(f"1. Verify improvements: SELECT public.pencil_dod_evaluate_county('<county>');")
        logger.info(f"2. For counties still failing: Analyze remaining unmatched patterns")
        logger.info(f"3. Consider PropertyOnion data quality issues affecting parity")
        logger.info(f"4. Implement automated normalization in auction ingestion pipeline")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix parity matching for SHARD-8 Letters C/D")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--county", help="Process single county only")
    parser.add_argument("--max-records", type=int, default=2000, help="Max records per county")
    args = parser.parse_args()
    
    # Filter to single county if specified
    targets = PARITY_FIX_TARGETS
    if args.county:
        if args.county in PARITY_FIX_TARGETS:
            targets = {args.county: PARITY_FIX_TARGETS[args.county]}
        else:
            print(f"ERROR: {args.county} not in target list: {list(PARITY_FIX_TARGETS.keys())}")
            sys.exit(1)
    
    fixer = ParityMatchingFixer(dry_run=args.dry_run, max_records=args.max_records)
    
    # Temporarily override targets
    global PARITY_FIX_TARGETS
    PARITY_FIX_TARGETS = targets
    
    try:
        fixer.run_parity_fixes()
    except KeyboardInterrupt:
        logger.info(f"\nParity fix interrupted by user")
    finally:
        client.close()

if __name__ == "__main__":
    main()