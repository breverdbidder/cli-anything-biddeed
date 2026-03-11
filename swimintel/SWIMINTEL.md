# SwimIntel CLI Agent — Agent #139

## Mission
Competitive intelligence for USA Swimming meets. Parses psych sheets, ranks swimmers by age group, calculates finals probability, and generates DOCX scouting reports.

## Agent Squad (4 soldiers)

| Agent | Role | Input | Output |
|-------|------|-------|--------|
| **Parser Agent** | Extract swimmer data from psych sheet PDFs | PDF file path | Structured JSON (events, swimmers, times) |
| **Analyzer Agent** | Rank by age group, calculate gaps & probability | Parsed JSON + target swimmer | Rankings, gaps, finals probability |
| **Report Agent** | Generate branded DOCX with tables & analysis | Analysis JSON | .docx file |
| **Orchestrator** | CLI entry point, coordinates squad | User commands | Pipeline execution |

## CLI Commands

```bash
# Parse a psych sheet
cli-anything-swimintel parse --pdf psychsheet.pdf --output parsed.json

# Analyze a swimmer's position
cli-anything-swimintel analyze --data parsed.json --swimmer "Shapira, Michael" --age-group 15-16

# Generate full report
cli-anything-swimintel report --data parsed.json --swimmer "Shapira, Michael" --age-group 15-16 --output report.docx

# Full pipeline (parse + analyze + report)
cli-anything-swimintel pipeline --pdf psychsheet.pdf --swimmer "Shapira, Michael" --age-group 15-16

# Enter REPL
cli-anything-swimintel
```

## Data Model

### Parsed Psych Sheet (JSON)
```json
{
  "meet": {
    "name": "2026 FL Swimming Spring Senior Championships",
    "dates": "3/12/2026 to 3/15/2026",
    "venue": null
  },
  "events": [
    {
      "number": 24,
      "name": "Men 50 Yard Freestyle",
      "gender": "M",
      "distance": 50,
      "stroke": "Free",
      "cuts": { "14U": 22.29, "15-16": 23.29, "17-18": 22.69, "19O": 22.29 },
      "entries": [
        {
          "seed": 1,
          "name": "Carrington, Liam",
          "age": 18,
          "team": "BSS-FL",
          "seed_time": 19.89,
          "qualifier": "SRCH",
          "course": "SCY"
        }
      ]
    }
  ]
}
```

### Analysis Output (JSON)
```json
{
  "swimmer": "Shapira, Michael",
  "age": 16,
  "team": "MELB-FL",
  "age_group": "15-16",
  "events": [
    {
      "event": "50 Free",
      "seed": 21.88,
      "age_group_rank": 14,
      "age_group_total": 70,
      "a_final_cut": 21.55,
      "b_final_cut": 21.91,
      "gap_to_a": -0.33,
      "gap_to_b": 0.03,
      "a_final_probability": 0.33,
      "b_final_probability": 0.75,
      "top_16": [ ... ],
      "verdict": "B-FINAL LIKELY"
    }
  ]
}
```

## Dependencies
- pdfplumber (PDF text extraction)
- click (CLI framework)
- prompt-toolkit (REPL)
- docx (DOCX generation via npm)
- cli-anything-shared (shared REPL skin)

## Integration
- Supabase: swim_meet_analysis table for historical tracking
- GitHub Actions: weekly psych sheet monitoring workflow
- SwimCloud API: cross-reference seed times with PBs
