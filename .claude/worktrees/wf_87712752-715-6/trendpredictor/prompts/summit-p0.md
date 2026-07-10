You are working on the Market Trend Predictor agent in /opt/biddeed/cli-anything-biddeed/trendpredictor/

Read trendpredictor/CLAUDE.md FIRST. It is your root directive.

## SESSION GOAL

Create Supabase table, add persistence, wire Zillow ZORI rental data, improve BCPAO sales trend calc, generate full county heatmap HTML. 5 phases, 5 commits.

## PHASE 1: CREATE SUPABASE TABLE + --save FLAG

Create the market_trends table (schema in CLAUDE.md) via Supabase REST or migration SQL.

Then add --save flag to the analyze subcommand:
1. Add --save to argparse for analyze, compare, and pulse commands
2. When --save passed, upsert prediction result to market_trends table after pipeline runs
3. Map: zip_code, submarket_name, direction_score, direction_label, timing_action, cycle_phase, vacancy_rate, median_sale_price, foreclosure_trend, signal_breakdown (JSONB), geojson_feature (JSONB), confidence, horizon_months, analyzed_at

Verify: Run analyze with --save and confirm row in Supabase.

COMMIT: `git add -A && git commit -m "feat(trendpredictor): Supabase market_trends table + --save flag" && git push origin main`

## PHASE 2: BCPAO SALES TREND — YoY GROWTH

In `stage_rents()`, improve the BCPAO sales query to calculate actual YoY price growth:

1. Query BCPAO GIS for sales in last 12 months AND prior 12-24 months (two separate queries)
2. Calculate median sale price for each period
3. Compute sale_price_growth_yoy = (recent_median - prior_median) / prior_median
4. Use this growth rate to classify trend: >5% STRONG, 2-5% MODERATE, 0-2% STAGNANT, <0 SOFTENING/DECLINING
5. Update confidence based on sample size (>20 sales = 0.70, 10-20 = 0.50, <10 = 0.30)

Verify: Run against ZIP 32937 and check sale_price_growth_yoy is a reasonable float.

COMMIT: `git add -A && git commit -m "feat(trendpredictor): BCPAO YoY sales growth calculation" && git push origin main`

## PHASE 3: ZILLOW ZORI RENTAL INDEX

Add Zillow ZORI (Zillow Observed Rent Index) data to stage_rents():

1. Download ZORI CSV: https://files.zillowstatic.com/research/public_csvs/zori/Zip_zori_sm_month.csv
2. Parse CSV, filter for Brevard ZIP codes (32901-32955, 32780)
3. Extract last 12 months of rent data for the target ZIP
4. Calculate median_rent (latest month), rent_growth_yoy (latest vs 12mo ago), rent_growth_mom (latest vs prior month)
5. Cache the CSV download (check if already downloaded in this session — it's 50MB+)
6. If download fails, fall back to Census data (already implemented)

This replaces Census ACS rent data which is annual and 2 years stale. ZORI is monthly and current.

COMMIT: `git add -A && git commit -m "feat(trendpredictor): Zillow ZORI rental index integration" && git push origin main`

## PHASE 4: FULL COUNTY PULSE HEATMAP

Ensure the `pulse` command works end-to-end:

1. Run all 15 Brevard ZIPs through the pipeline
2. Generate the GeoJSON FeatureCollection with all 15 points
3. Generate the Mapbox HTML with heatmap + circle layers + popups
4. Write to trendpredictor/eval_outputs/brevard_pulse.html
5. Also write GeoJSON to trendpredictor/eval_outputs/brevard_pulse.geojson
6. Validate: HTML file contains mapboxgl.Map, GeoJSON has 15 features

Use the Mapbox token from env: MAPBOX_TOKEN. If not set, hardcode the public key from CLAUDE.md for testing only.

COMMIT: `git add -A && git commit -m "feat(trendpredictor): Full county pulse heatmap HTML" && git push origin main`

## PHASE 5: SMOKE TEST + EVAL

1. Run single analysis: `python3 -m trendpredictor.agent analyze --zip 32937 --horizon 12 --json 2>/dev/null > trendpredictor/eval_outputs/smoke_single.json`
2. Run comparison: `python3 -m trendpredictor.agent compare --zips 32937,32940,32903 --json 2>/dev/null > trendpredictor/eval_outputs/smoke_compare.json`
3. Validate both JSON files
4. Run status: `python3 -m trendpredictor.agent status 2>&1`
5. Run eval if available: `python3 scripts/eval_runner.py --eval-file trendpredictor/eval/eval.json --outputs-dir trendpredictor/eval_outputs/ || true`

COMMIT: `git add -A && git commit -m "test(trendpredictor): smoke test + county pulse $(date +%Y%m%d)" && git push origin main`

## RULES

- You are autonomous. The human is not available. Never ask questions.
- ONE commit per phase. Push after each. 5 total commits expected.
- All print() → sys.stderr. Only --json on stdout. ALREADY correct — don't break it.
- All httpx.Client() uses headers=UA. ALREADY correct — don't break it.
- Mapbox heatmap MUST use BidDeed brand colors (navy #1E3A5F, orange #F59E0B).
- Rate limit: time.sleep(2) between external API calls.
- If Zillow CSV download fails, log error and continue with Census fallback.
- If any external API is down, set confidence to 0.0 and continue.
- Context at 50% → stop and push. No /compact.
- No new deps beyond httpx (already installed) and csv (stdlib).
- Don't touch eval.json.
- Budget: under $5.
