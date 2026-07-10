You are working on the Property Profile Enricher agent in /opt/biddeed/cli-anything-biddeed/enricher/

Read enricher/CLAUDE.md FIRST. It is your root directive.

## SESSION GOAL

Fix 2 deployment bugs, then wire up the 3 stubbed data sources (P0 priorities from CLAUDE.md).

## PHASE 1: BUG FIXES (do these first, they take 2 minutes)

### Bug 1 — Progress logs pollute JSON output
The `log()` function and all `print()` statements in agent.py write to stdout. When `--json` flag is used, the pipeline summary text mixes into the JSON redirect, breaking parsers.

FIX: In the `log()` function, change `print(...)` to `print(..., file=sys.stderr)`. Also change ALL bare `print()` calls in `enrich_property()` summary block and `_check_connectivity()` to use `file=sys.stderr`. The ONLY stdout output should be the final `json.dumps()` when `--json` is passed.

Verify: `python3 -m enricher.agent enrich --parcel "2537220000001" --mode foreclosure --depth quick --json 2>/dev/null | python3 -c "import json,sys; json.load(sys.stdin); print('✅ Valid JSON')"` must print "✅ Valid JSON".

### Bug 2 — BCPAO API returns 403 from Hetzner (no User-Agent)
All httpx.Client() instances lack a User-Agent header. Hetzner's IP gets blocked by BCPAO without one.

FIX: Add `headers={"User-Agent": "BidDeed.AI/1.0 (property-enricher)"}` to every `httpx.Client()` call in agent.py. There are 6 of them — find all with grep.

Verify: `python3 -m enricher.agent status` should show "BCPAO API: 200".

COMMIT after both fixes: `git add -A && git commit -m "fix(enricher): stderr for logs + User-Agent for BCPAO" && git push origin main`

## PHASE 2: WIRE ACCLAIMWEB LIEN SEARCH (P0-1)

In `stage_liens()`, the AcclaimWeb search is stubbed. Wire it up:

1. AcclaimWeb party name search URL: `https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName`
2. It returns HTML. Parse with these document type patterns (from BECA Scraper V2.0):
   - `MTG` or `MORTGAGE` → mortgage
   - `LIS` or `LIS PENDENS` → lis_pendens
   - `JUDGMENT` or `JP` or `JUDG` → judgment_liens
   - `LIEN` → general lien (check subtype: TAX, HOA, MECH, CODE)
   - `HOA` or `HOMEOWNERS` → hoa_liens
   - `UCC` → ucc_filings
   - `SAT` or `SATISFACTION` → skip (lien released)
3. For each found document, extract: doc_type, recording_date, book/page or instrument number, parties
4. Rate limit: `time.sleep(2)` between AcclaimWeb requests
5. Set confidence to 0.70 if results found, 0.40 if search ran but empty

DO NOT over-engineer. A simple `httpx.get()` + `re.findall()` on the HTML response is fine. No Selenium, no headless browser. If AcclaimWeb blocks or changes format, log the error and continue — never crash the pipeline.

Verify: Run against a known parcel with liens. Check that `liens["mortgages"]` or `liens["judgment_liens"]` is non-empty.

COMMIT: `git add -A && git commit -m "feat(enricher): AcclaimWeb lien search with BECA regex patterns" && git push origin main`

## PHASE 3: WIRE REALTDM TAX CERTIFICATES (P0-2)

In `stage_liens()`, add RealTDM tax certificate lookup after the AcclaimWeb block:

1. RealTDM search: `https://brevard.realtdm.com/TaxSys/taxCertSearch.aspx` — search by parcel/account number
2. Parse HTML response for tax certificate records: cert number, face value, year, status (applied/redeemed/outstanding)
3. Populate `liens["tax_certificates"]` list with dicts: `{cert_number, year, face_value, status}`
4. If any certificates are outstanding (not redeemed), set `liens["tax_liens"]` flag
5. Rate limit: `time.sleep(2)` after RealTDM request

Same rules: simple httpx + regex. No Selenium. Log errors, never crash.

COMMIT: `git add -A && git commit -m "feat(enricher): RealTDM tax certificate lookup" && git push origin main`

## PHASE 4: WIRE TAX COLLECTOR DELINQUENCY (P0-3)

In `stage_tax()`, add Tax Collector lookup after the BCPAO block:

1. Brevard Tax Collector: `https://brevardtc.com` — search by account number
2. Look for delinquent tax indicators in the response: past-due amounts, penalty text
3. If found, set `tax["delinquent"] = True` and `tax["delinquent_amount"]` to the dollar figure
4. This is the MOST IMPORTANT signal for tax deed analysis

Same rules: simple httpx + regex. Log errors, never crash.

COMMIT: `git add -A && git commit -m "feat(enricher): Tax Collector delinquency check" && git push origin main`

## PHASE 5: FINAL SMOKE TEST + EVAL

1. Run full smoke test: `python3 -m enricher.agent enrich --parcel "2537220000001" --mode foreclosure --depth deep --json 2>/dev/null > enricher/eval_outputs/smoke_deep.json`
2. Validate JSON: `python3 -c "import json; d=json.load(open('enricher/eval_outputs/smoke_deep.json')); print(f'Stages: {list(d[\"stages\"].keys())}'); print(f'Synthesis: {d.get(\"synthesis\",{}).get(\"action\",\"N/A\")}')"` 
3. Run eval if eval_runner.py exists: `python3 scripts/eval_runner.py --eval-file enricher/eval/eval.json --outputs-dir enricher/eval_outputs/ || true`
4. Final commit with results: `git add -A && git commit -m "test(enricher): smoke test deep mode $(date +%Y%m%d)" && git push origin main`

## RULES

- You are autonomous. The human is not available. Never ask questions.
- ONE commit per phase. Push after each commit. 5 total commits expected.
- If a scraper returns unexpected HTML or errors, log it and move on. Never block the pipeline.
- If AcclaimWeb or RealTDM or Tax Collector is down, set confidence to 0.0 for that stage and continue.
- If context window reaches 50%, stop and push what you have. Do not /compact.
- Do NOT refactor the entire file. Make targeted changes only.
- Do NOT add new dependencies beyond httpx (already installed).
- Do NOT touch eval.json — it's already correct.
- Total session budget: under $5. Be efficient.
