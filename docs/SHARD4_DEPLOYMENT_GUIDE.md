# SHARD-4 Gold Standard Deployment Guide

## Overview
This document describes the deployment of shard-4 gold standard improvements targeting counties: citrus, st_johns, hendry, walton, lafayette.

## Components Deployed

### Core Scripts
- `scripts/shard4_gold_standard_improvements.py`: Main improvement engine
- `scripts/verify_shard4_status.py`: Quick verification utility  
- `scrapers/st_johns_verified_outcomes.py`: St. Johns Letter B scraper

### Target Letters
- **Letter B**: Verified outcomes from independent sources (≥95%)
- **Letter E**: Parcel linkage via county property appraisers (≥95%)
- **Letter I**: Property card completion (≥95%)

### County Prioritization
1. **st_johns** (Priority 1): 2/10 passing, freshness good
2. **citrus** (Priority 2): 2/10 passing, freshness issues  
3. **walton** (Priority 3): 1/10 passing
4. **hendry** (Priority 4): 1/10 passing
5. **lafayette** (Priority 5): 0/10 passing

## Execution Commands

### Manual Execution
```bash
# Verify current status
python scripts/verify_shard4_status.py

# Run improvements for specific county
python scripts/shard4_gold_standard_improvements.py --county st_johns

# Run improvements for all counties
python scripts/shard4_gold_standard_improvements.py

# St. Johns verified outcomes (Letter B)
python scrapers/st_johns_verified_outcomes.py

# Dry run mode
python scrapers/st_johns_verified_outcomes.py --dry-run
```

### Scheduled Execution
Manual workflow dispatch until workflow permissions are resolved.

## County-Specific Implementations

### St. Johns County (Priority 1)
- **Appraiser**: sjcpa.us
- **Clerk Records**: stjohnsclerk.com/recording/
- **Tax Deed Results**: sjctax.us/auction-results
- **Status**: Letter B scraper implemented

### Other Counties
Property appraiser endpoints mapped but scrapers need implementation:
- citrus: citruspa.org
- hendry: hendrypa.net  
- walton: qpublic.schneidercorp.com
- lafayette: lafayettepa.com

## Wiring Status
- ✅ Core improvement scripts committed to main
- ✅ St. Johns verified outcomes scraper implemented
- ✅ County status verification utility created
- ⚠️ GitHub Actions workflow needs manual creation (permission restrictions)

## Next Steps
1. Execute improvements script manually
2. Verify Letter B improvements for St. Johns
3. Implement remaining county-specific scrapers
4. Create manual workflow dispatch for scheduling
5. Monitor daily improvements via verification script