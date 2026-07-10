---
name: deal-intel
description: Point at any folder of foreclosure documents (PDFs, DOCX, court filings) and get structured analysis. Extracts judgment amounts, property addresses, plaintiff names, lien positions, and generates Supabase-ready JSON. Adapted from Mark Kashef's /file-intel pattern.
---

# Deal Intel — Foreclosure Document Pipeline

Point at a folder. Read every file. Extract structured deal data.

## Process

1. List all files in the target folder (PDF, DOCX, TXT, MD)
2. For each file, extract:
   - Case number
   - Property address (street, city, zip)
   - Parcel ID / account number
   - Plaintiff name and type (bank, HOA, government)
   - Defendant name(s)
   - Judgment amount
   - Sale date (if set)
   - Liens mentioned (mortgage, HOA, tax cert, code enforcement)
   - Attorney of record
3. Cross-reference against Supabase `multi_county_auctions` if case number matches
4. Generate structured output

## Output

For each document, create a markdown summary in `inbox/`:

```markdown
# [Case Number] — [Property Address]

**Source:** [filename]
**Plaintiff:** [name] ([type])
**Judgment:** $[amount]
**Sale Date:** [date or "TBD"]
**Parcel:** [ID]

## Liens Detected
- [lien type]: [holder] — [amount if known]

## Red Flags
- [HOA foreclosure with senior mortgage surviving]
- [Tax certificate issues]
- [Any anomalies]

## Recommendation
[BID/REVIEW/SKIP with reasoning]
```

Also output a JSON summary array for Supabase insert.

If a file can't be parsed, log it and move on. Never guess amounts — mark as "UNREADABLE" if OCR fails.
