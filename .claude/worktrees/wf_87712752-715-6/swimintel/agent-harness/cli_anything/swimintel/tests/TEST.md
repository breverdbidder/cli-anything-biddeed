# SwimIntel CLI — Test Plan

## Agent #139 Test Strategy

### Test Inventory
- `test_core.py`: ~18 unit tests
- `test_full_e2e.py`: ~6 E2E tests

### Unit Tests (test_core.py)

#### Parser Module (8 tests)
- `test_parse_time_minutes` — "1:53.03" → 113.03
- `test_parse_time_seconds` — "21.88" → 21.88
- `test_detect_course_scy` — No L suffix → SCY
- `test_detect_course_lcm` — L suffix → LCM
- `test_detect_qualifier_srch` — SRCH in tail
- `test_detect_qualifier_bonus` — B suffix
- `test_event_pattern_match` — "Event 24 Men 50 Yard Freestyle"
- `test_swimmer_pattern_match` — "1 Carrington, Liam 18 BSS-FL 19.89 SRCH"

#### Analyzer Module (7 tests)
- `test_filter_age_group_15_16` — Only 15-16 year olds returned
- `test_rank_in_age_group` — Sorted by seed time
- `test_estimate_probability_inside` — Gap >= 0 → high probability
- `test_estimate_probability_outside_sprint` — Small gap in 50 → moderate
- `test_estimate_probability_outside_distance` — Large gap in 200 → low
- `test_determine_verdict` — Correct verdict strings
- `test_analyze_swimmer_full` — Full analysis pipeline

#### Session Module (3 tests)
- `test_session_create_save_load` — Round-trip persistence
- `test_session_status` — Status dict generation
- `test_session_has_data` — Boolean checks

### E2E Tests (test_full_e2e.py)

#### Pipeline Tests
- `test_parse_pdf` — Parse real psych sheet PDF
- `test_analyze_specific_swimmer` — Full analysis for known swimmer
- `test_generate_report` — DOCX output file created
- `test_full_pipeline` — parse → analyze → report
- `test_cli_parse_command` — CLI invocation via subprocess
- `test_cli_pipeline_command` — Full CLI pipeline
