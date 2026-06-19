# SHARD-13 Session Closeout Report
**Dispatch ID:** c60c8189-e784-4404-9cc5-535830f0cd62
**Loop Run:** 56
**Date:** 2026-06-19
**Counties:** st_johns, walton, santa_rosa, holmes

---

## Before / After DoD Scores

| County | BEFORE Score | BEFORE Passing | AFTER Score | AFTER Passing | Delta |
|--------|-------------|----------------|-------------|---------------|-------|
| st_johns | 3/10 (A,E,H) | A, E, H | 3/10 | A, E, H | 0 (already verified) |
| walton | 2/10 (A,E) | A, E | 3/10 | A, E, H | +1 (H now passing) |
| santa_rosa | 1/10 (A) | A | 3/10 | A, E, H | +2 (E, H now passing) |
| holmes | 0/10 | none | 0/10 | none | 0 (no auctions) |

---

## Full Evaluation JSON (AFTER)

### st_johns
```json
{
    "county": "st_johns",
    "auctions_total": 31,
    "A": {"pass": true,  "detail": "fc=28 td=3",                              "metric": 3},
    "B": {"pass": false, "detail": "verified=0 closed_sold=16",                "metric": 0.0},
    "C": {"pass": false, "detail": "matched_clean=24",                         "metric": 77.4},
    "D": {"pass": false, "detail": "matched_any=24",                           "metric": 77.4},
    "E": {"pass": true,  "detail": "parcel_linked=30",                         "metric": 96.8},
    "F": {"pass": false, "detail": "tier1_sold=1 closed_sold=16",              "metric": 6.3},
    "G": {"pass": false, "detail": "density= far= pk1000=",                    "metric": null},
    "H": {"pass": true,  "detail": "hours since last_seen (SLA 48h)",          "metric": 2.2},
    "I": {"pass": false, "detail": "card_complete=0 of 31",                    "metric": 0.0},
    "J": {"pass": false, "detail": "deal_complete=0 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 0.0}
}
```

### walton
```json
{
    "county": "walton",
    "auctions_total": 24,
    "A": {"pass": true,  "detail": "fc=19 td=5",                              "metric": 5},
    "B": {"pass": false, "detail": "verified=0 closed_sold=1",                 "metric": 0.0},
    "C": {"pass": false, "detail": "matched_clean=16",                         "metric": 66.7},
    "D": {"pass": false, "detail": "matched_any=16",                           "metric": 66.7},
    "E": {"pass": true,  "detail": "parcel_linked=24",                         "metric": 100.0},
    "F": {"pass": false, "detail": "tier1_sold=0 closed_sold=1",               "metric": 0.0},
    "G": {"pass": false, "detail": "density= far= pk1000=",                    "metric": null},
    "H": {"pass": true,  "detail": "hours since last_seen (SLA 48h)",          "metric": 0.1},
    "I": {"pass": false, "detail": "card_complete=0 of 24",                    "metric": 0.0},
    "J": {"pass": false, "detail": "deal_complete=0 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 0.0}
}
```

### santa_rosa
```json
{
    "county": "santa_rosa",
    "auctions_total": 57,
    "A": {"pass": true,  "detail": "fc=51 td=6",                              "metric": 6},
    "B": {"pass": false, "detail": "verified=0 closed_sold=5",                 "metric": 0.0},
    "C": {"pass": false, "detail": "matched_clean=46",                         "metric": 80.7},
    "D": {"pass": false, "detail": "matched_any=46",                           "metric": 80.7},
    "E": {"pass": true,  "detail": "parcel_linked=55",                         "metric": 96.5},
    "F": {"pass": false, "detail": "tier1_sold=0 closed_sold=5",               "metric": 0.0},
    "G": {"pass": false, "detail": "density= far= pk1000=",                    "metric": null},
    "H": {"pass": true,  "detail": "hours since last_seen (SLA 48h)",          "metric": 0.1},
    "I": {"pass": false, "detail": "card_complete=0 of 57",                    "metric": 0.0},
    "J": {"pass": false, "detail": "deal_complete=0 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 0.0}
}
```

### holmes
```json
{
    "county": "holmes",
    "auctions_total": 0,
    "A": {"pass": false, "detail": "fc=0 td=0",                               "metric": 0},
    "B": {"pass": false, "detail": "verified=0 closed_sold=0",                 "metric": null},
    "C": {"pass": false, "detail": "matched_clean=0",                          "metric": null},
    "D": {"pass": false, "detail": "matched_any=0",                            "metric": null},
    "E": {"pass": false, "detail": "parcel_linked=0",                          "metric": null},
    "F": {"pass": false, "detail": "tier1_sold=0 closed_sold=0",               "metric": null},
    "G": {"pass": false, "detail": "density= far= pk1000=",                    "metric": null},
    "H": {"pass": false, "detail": "hours since last_seen (SLA 48h)",          "metric": null},
    "I": {"pass": false, "detail": "card_complete=0 of 0",                     "metric": null},
    "J": {"pass": false, "detail": "deal_complete=0 (triangle + two-arm CMA + ml_score + max_bid)", "metric": null}
}
```

---

## What Was Built This Session

### 1. Generalized County RealTDM Scraper (`702f741e`)
- `scripts/scrape_realtdm_county.py` — parameterized scraper targeting `{county}.realtdm.com`
- Covers panhandle counties: walton, santa_rosa, holmes, okaloosa (and any future realtdm counties)
- Scheduled via `.github/workflows/scrape-realtdm-counties.yml`
- walton: 19 auctions scraped (fc=19), santa_rosa: 51 auctions (fc=51)
- holmes: 0 auctions — realtdm.com/holmes returned no active listings

### 2. Parcel Linkage (E metric)
- walton E: 100% parcel linkage (24/24 auctions linked)
- santa_rosa E: 96.5% parcel linkage (55/57 auctions linked)
- st_johns E: 96.8% parcel linkage (30/31 auctions linked) — pre-existing

### 3. Freshness (H metric)
- walton H: 0.1h since last_seen (scraped ~6 minutes ago at eval time)
- santa_rosa H: 0.1h since last_seen
- st_johns H: 2.2h (within 48h SLA — pre-existing)

---

## Audit Rows Logged

| ID | County | Letter | Metric | Survived |
|----|--------|--------|--------|----------|
| 34 | santa_rosa | E | 96.5% | true |
| 35 | walton | H | 0.1h | true |
| 36 | santa_rosa | H | 0.1h | true |
| 37 | walton | E | 100.0% | true |

Holmes A: NOT logged — auctions_total=0, A=false. No data ingested from holmes.realtdm.com.

---

## Row Counts

| County | Auctions (fc) | Today-only (td) | Parcel-linked |
|--------|--------------|-----------------|---------------|
| st_johns | 28 | 3 | 30 (96.8%) |
| walton | 19 | 5 | 24 (100%) |
| santa_rosa | 51 | 6 | 55 (96.5%) |
| holmes | 0 | 0 | 0 |

Total auctions across shard: 98 (st_johns 31 + walton 24 + santa_rosa 57 + holmes 0)

---

## Next Steps

1. **Holmes (0/10):** holmes.realtdm.com returned 0 listings. Investigate alternate source — check Florida Clerk of Courts or holmes county tax collector portal for foreclosure auction listings.
2. **C/D metrics (address matching):** walton at 66.7%, santa_rosa at 80.7%, st_johns at 77.4%. All below 90% threshold. Needs address normalization pass.
3. **B metric (verification):** All 4 counties at 0% — no closed/sold comps verified. Requires MLS or public records integration.
4. **F metric (tier1 sold):** st_johns at 6.3%, others at 0%. Needs tier1 workflow to trigger on sold auctions.
5. **I/J metrics (deal cards + deal complete):** 0% across all counties — downstream of B/C/D gaps.

---

## SQL Verification

```sql
-- Audit rows for this dispatch
SELECT id, county_slug, letter, survived, created_at
FROM gold_standard_ultraloop_audit
WHERE dispatch_id = 'c60c8189-e784-4404-9cc5-535830f0cd62'
ORDER BY id;
-- Returns: 4 rows (IDs 34, 35, 36, 37)

-- Auction counts per county
SELECT county, COUNT(*) FROM multi_county_auctions
WHERE county IN ('st_johns','walton','santa_rosa','holmes')
GROUP BY county;
```
