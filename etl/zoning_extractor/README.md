# Zoning Ordinance Extractor

Autonomous, county-agnostic pipeline that reads municipal zoning ordinances and
stages structured dimensional standards (density, FAR, parking, height, min lot)
into `zoning_codes_staging` for human gating before promotion to `zoning_codes`.

Built because `web_fetch` cannot read these sources: Municode and American Legal
are JavaScript single-page apps (and American Legal bot-blocks plain HTTP). Headless
Chromium renders them; an LLM structures the rendered text. Robustness lives in the
LLM layer, not in brittle per-site selectors.

## Pipeline

```
zoning_source_map (discovery) ─┐
zoning_assignments (target codes)─┤→ render (Playwright) → extract (LLM) → validate → zoning_codes_staging
                                 └→ jurisdiction crosswalk
```

- `render.py`  – headless Chromium loads the node URL, returns rendered text. Only brittle surface; isolated.
- `extract.py` – LLM structures the text. Enforces BLANK > WRONG: null when not stated, never inferred; PUD ⇒ site-specific with null density; every value cites its `source_section`.
- `validate.py`– plausibility flags + mechanical site-specific enforcement. Never drops; demotes to `confidence='low'`.
- `db.py`      – reads source map + real assigned codes; upserts staging only.
- `main.py`    – orchestrator, `--county` parameterized.

## The gate (do not bypass)

The extractor writes **only** to `zoning_codes_staging` with `gated=false`. Nothing
reaches `zoning_codes` (the cert-feeding table) until a human reviews staged rows and
a separate promotion step copies `gated=true` rows over. Low-confidence and
out-of-range values are surfaced, never silently accepted.

## Run

```bash
pip install -r requirements.txt
python -m playwright install --with-deps chromium

export ANTHROPIC_API_KEY=... SUPABASE_URL=... SUPABASE_SERVICE_KEY=...

python main.py --county brevard --jurisdiction palm_bay   # one jurisdiction
python main.py --county brevard --dry-run                  # all, no writes
python main.py --county brevard                            # all, stage
```

Or trigger the `zoning-extract` GitHub Action with a county input. Secrets needed:
`ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`.

## Onboarding a new county (the only per-county manual step)

1. Add the county's jurisdictions to `zoning_jurisdiction_xwalk`
   (`assignment_jurisdiction` ↔ `codes_jurisdiction`).
2. Add a `zoning_source_map` row per jurisdiction: `platform`
   (`municode` | `american_legal`), `base_url`, `node_hint` (the deep-link node id),
   `dimensional_locator`, `priority`.
3. `python main.py --county <name>`.

Discovery is currently human-assisted (web search → source map). Extraction is fully autonomous once the map exists.

## Known limits (honest)

- **DOM selectors** in `config.CONTENT_SELECTORS` are best-effort and may need one
  live-tuning pass per platform; everything else is layout-agnostic.
- **Parking-per-1000** rarely lives in the dimensional table — it's usually a separate
  parking chapter. Expect mostly null from this pass; a second source/locator is needed for it.
- **Per-district ordinances** (e.g. Brevard County, sections per code) may need the
  source map to point at the division landing or iterate sections; consolidated-table
  jurisdictions (most) work in one render.
- **PUD** is identified and flagged site-specific here; its real buildability is a
  per-parcel development-order lookup, a separate pipeline.
