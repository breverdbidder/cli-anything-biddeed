---
name: county-setup
description: Interactive county onboarding configurator. Asks one free-text question about a new Florida county, then builds scraper configs, data source mappings, folder structure, and pipeline settings. Run when expanding beyond Brevard.
---

# County Setup — BidDeed.AI County Onboarding

Run from INSIDE the cli-anything-biddeed repo or any BidDeed project directory.

## STEP 1 — One question, free text

Display this message exactly, then wait for their response:

---

**Tell me about this county so I can build the full pipeline config.**

Answer these in whatever order feels natural:

- Which Florida county?
- In-person auction, online (realforeclose), or both?
- Do you know the Property Appraiser URL or GIS endpoint?
- Any contacts (attorneys, title agents) you have there?
- Are you targeting foreclosures, tax deeds, or both?

A few sentences is enough. I'll figure out the rest.

---

## STEP 2 — Infer and preview, don't ask more questions

From their free-text answer, infer:
- County name and FIPS code
- Auction format (in-person courthouse / online realforeclose / hybrid)
- Available data sources (Property Appraiser, Clerk, Tax Collector)
- Target auction types (foreclosure / tax deed / both)
- Whether they have local contacts

Then search the web for:
- `[county] property appraiser GIS` → find BCPAO-equivalent REST endpoint
- `[county] clerk of court records` → find AcclaimWeb-equivalent
- `[county].realforeclose.com` → verify if online auctions exist
- `[county] tax collector` → find delinquent tax search

Show a preview:

```
Here's your county config — ready to build when you are.

📁 counties/[county_name]/
├── config.yaml          County-specific pipeline settings
├── data_sources.json    GIS, clerk, tax collector endpoints
├── contacts.md          Local attorneys, title agents, closers
├── scraper_config.py    Scraper class with county-specific selectors
├── zoning/              ZoneWise municipal conquest configs
└── reports/             County-specific auction reports

Data sources detected:
  🏠 Property Appraiser: [URL or "needs research"]
  📋 Clerk of Court:     [URL or "needs research"]
  💰 Tax Collector:      [URL or "needs research"]
  🔨 Auction Platform:   [realforeclose URL or "in-person at courthouse"]

Pipeline: [foreclosure / tax deed / both]

Type "build it" to create this, or tell me what to change.
```

Wait for confirmation before building anything.

## STEP 3 — Build after confirmation

### Create folder structure
```bash
COUNTY="[county_name_lowercase]"
mkdir -p "counties/$COUNTY"/{zoning,reports}
```

### Write config.yaml
```yaml
county: [County Name]
fips: [FIPS code]
state: FL

auction:
  type: [foreclosure|tax_deed|both]
  format: [in_person|online|hybrid]
  platform: [county].realforeclose.com  # if online
  courthouse: [address]                  # if in-person
  schedule: [known schedule or "research needed"]

data_sources:
  property_appraiser:
    url: [detected URL]
    api: [REST endpoint if found]
    spatial_ref: [WKID if GIS detected]
  clerk:
    url: [detected URL]
    search_type: [party_name|case_number|both]
  tax_collector:
    url: [detected URL]
    delinquent_search: [true/false]

max_bid_formula:
  arv_multiplier: 0.70
  fixed_deduction: 10000
  variable_deduction_pct: 0.15
  variable_deduction_cap: 25000

thresholds:
  bid_ratio_bid: 0.75
  bid_ratio_review: 0.60
```

### Write data_sources.json
Structured JSON with all discovered endpoints, field mappings, and authentication requirements.

### Write contacts.md
```markdown
# [County Name] Contacts

## Attorneys
[from user input or "None yet"]

## Title Agents
[from user input or "None yet"]

## Closing Coordinators
[from user input or "None yet"]

## Notes
[any relevant context from user's free-text answer]
```

### Write scraper_config.py
Skeleton scraper class following cli-anything harness pattern with county-specific selectors and endpoints.

## STEP 4 — Supabase integration

After building, ask:

```
County config is ready. Want me to also:

1. Add to multi_county_auctions table schema (if not already there)
2. Create a GitHub Action scrape workflow for this county
3. Both
4. Skip for now
```

## STEP 5 — Final output

```
Done. [County Name] is configured.

Your county pipeline:
  config:    counties/[county]/config.yaml
  sources:   counties/[county]/data_sources.json
  contacts:  counties/[county]/contacts.md
  scraper:   counties/[county]/scraper_config.py

Next steps:
  1. Verify data source URLs (I've marked uncertain ones)
  2. Run test scrape: python counties/[county]/scraper_config.py --test
  3. Add to daily auction scrape workflow when ready

Need to onboard another county? Run /county-setup again.
```
