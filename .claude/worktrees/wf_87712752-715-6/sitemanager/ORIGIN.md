---
name: site-manager
description: Analyze construction site footage and reports to flag progress gaps, safety issues, and schedule deviations automatically
version: "1.0"
metadata:
  author: NextAutomation
---

# Site Manager

An automated construction monitoring skill that analyzes site photos, drone footage, daily reports, and inspection data to flag progress gaps, safety violations, and schedule deviations without requiring daily physical site visits. This skill replaces the manual process of reviewing site conditions, cross-referencing schedules, and compiling observations into actionable reports — giving developers real-time visibility across multiple active projects simultaneously.

## When to Use

- Monitoring multiple active construction projects across different locations
- Verifying contractor-reported progress against visual evidence
- Identifying safety compliance issues before they become OSHA citations
- Tracking weather delays and their impact on the critical path
- Preparing for lender inspections with current progress documentation
- Reviewing daily/weekly field reports for patterns and emerging issues

## Input Required

| Field | Required | Description |
|-------|----------|-------------|
| `project_id` | Yes | Unique identifier for the active project |
| `site_media` | Yes | Photos, drone footage, or 360-capture files from the site |
| `construction_schedule` | Yes | Current CPM schedule with baseline and actual dates |
| `daily_reports` | No | Superintendent daily logs and field reports |
| `inspection_reports` | No | Third-party inspection results and punch lists |
| `weather_data` | No | Local weather conditions for the reporting period |
| `safety_plan` | No | Project-specific safety plan for compliance benchmarking |

## Process

### Step 1: Visual Progress Analysis

Analyze site media to assess construction stage and completion percentage:

| Visual Indicator | What It Reveals | Verification Method |
|-----------------|----------------|---------------------|
| Foundation/Slab Status | Below-grade completion | Compare to structural drawings |
| Framing Progress | Structural completion by floor/section | Count completed bays/sections |
| Exterior Envelope | Weather-tight status | Identify open/sealed areas |
| MEP Rough-in | Systems installation progress | Visible conduit, ductwork, piping |
| Interior Finishes | Unit completion status | Compare to finish schedule |
| Site Work | Grading, paving, landscaping | Match to site plan |
| Equipment On-Site | Active trades and mobilization | Crane count, equipment inventory |
| Material Staging | Upcoming work readiness | Stockpile assessment |

Progress verification matrix:

| Schedule Phase | Expected Visual State | Behind Schedule Indicators |
|---------------|----------------------|---------------------------|
| Foundations | Forms/rebar visible, concrete pours | Standing water, no forms, idle equipment |
| Structural | Steel/wood framing rising floor-by-floor | Incomplete floors, missing connections |
| Envelope | Sheathing, windows, roofing installed | Open walls/roof, no weather barrier |
| MEP Rough | Conduit/pipe/duct visible in ceiling/walls | No visible MEP in areas past framing |
| Drywall | Boards hung and taped | Exposed framing in supposedly finished areas |
| Finishes | Paint, flooring, fixtures visible | Raw drywall, no fixtures in late-stage units |

### Step 2: Schedule Deviation Detection

Compare observed progress against the construction schedule:

| Deviation Type | Detection Method | Severity Scoring |
|---------------|-----------------|-----------------|
| Activity Behind Schedule | Visual completion vs. schedule % | Days behind × criticality factor |
| Critical Path Impact | Map delay to critical path activities | Binary: on critical path or not |
| Predecessor Delays | Activity started without predecessor complete | Sequence violation flag |
| Resource Gaps | Expected labor/equipment not observed | Missing trades identification |
| Weather Impact | Lost days vs. float available | Net impact on completion date |
| Concurrent Delays | Multiple activities behind simultaneously | Compound risk assessment |

Schedule health scoring:

| Score Range | Status | Recommended Action |
|-------------|--------|-------------------|
| 90-100 | On Track | Continue monitoring |
| 75-89 | Minor Delays | Increase reporting frequency |
| 60-74 | Significant Delays | Schedule recovery meeting |
| 40-59 | Major Delays | Recovery plan required |
| <40 | Critical | Owner/lender notification |

### Step 3: Safety Compliance Monitoring

Scan for common safety violations and hazardous conditions:

| Safety Category | Violations Detected | OSHA Reference | Severity |
|----------------|--------------------|---------       |----------|
| Fall Protection | Missing guardrails, no harnesses at height | 1926.501 | Serious |
| Scaffolding | Incomplete platforms, missing toe boards | 1926.451 | Serious |
| Housekeeping | Debris accumulation, blocked egress | 1926.25 | Other |
| PPE Compliance | Missing hard hats, high-vis, eye protection | 1926.100-102 | Other |
| Excavation | Unshored trenches, no spoil setback | 1926.651 | Willful |
| Electrical | Exposed wiring, missing GFCIs | 1926.404-405 | Serious |
| Fire Prevention | Missing extinguishers, hot work violations | 1926.150-152 | Serious |
| Crane Operations | Swing radius issues, load chart violations | 1926.1400+ | Imminent Danger |

Safety score calculation:

| Finding | Points Deducted | Escalation |
|---------|----------------|------------|
| Observation (minor) | -2 per finding | Log only |
| Non-compliance | -5 per finding | Notify superintendent |
| Serious violation | -15 per finding | Stop work in affected area |
| Imminent danger | -30 per finding | Immediate stop work |

### Step 4: Quality Control Assessment

Identify workmanship issues visible in site documentation:

| Quality Check | What to Look For | Standard Reference |
|--------------|-----------------|-------------------|
| Concrete Placement | Honeycombing, cold joints, form blowouts | ACI 301 |
| Steel Connections | Missing bolts, weld quality, alignment | AISC standards |
| Waterproofing | Membrane continuity, flashing details | Manufacturer specs |
| Framing | Plumb/level, connection hardware | IRC/IBC |
| MEP Coordination | Clashes, improper routing, clearances | Project BIM model |
| Exterior Finishes | Alignment, material damage, installation defects | Spec sections |

### Step 5: Daily Report Intelligence

Extract actionable insights from superintendent daily logs:

| Report Element | Analysis Applied | Output |
|---------------|-----------------|--------|
| Manpower Count | Trend analysis vs. schedule requirements | Undermanned trade alerts |
| Equipment Log | Utilization tracking, idle equipment cost | Equipment optimization suggestions |
| Weather Notes | Correlate to productivity and delays | Weather impact quantification |
| Visitor Log | Inspector/subcontractor activity tracking | Coordination status |
| Issue Narrative | NLP extraction of problems and resolutions | Issue tracking and trending |
| Material Deliveries | Match to schedule needs | Delivery gap identification |

### Step 6: Composite Site Report Generation

Combine all analyses into a single project health report:

| Report Section | Content | Update Frequency |
|---------------|---------|------------------|
| Progress Dashboard | Phase completion %, visual evidence | Per media upload |
| Schedule Status | Deviation summary, critical path health | Weekly |
| Safety Scorecard | Violation count, trend, score | Per site visit |
| Quality Log | Issues found, status, resolution | Per inspection |
| Weather Impact | Lost days, float consumption | Weekly |
| Action Items | Prioritized issues requiring response | Real-time |
| Photo Documentation | Annotated progress photos | Per media upload |

## Output Format

The skill produces a Site Management Report containing:

1. **Progress Snapshot** - Visual completion assessment with schedule comparison
2. **Schedule Health Score** - Overall project timeline status (0-100)
3. **Safety Scorecard** - Violations detected with OSHA categories and severity
4. **Deviation Alerts** - Activities behind schedule with impact analysis
5. **Quality Observations** - Workmanship issues identified from visual review
6. **Daily Report Insights** - Trends extracted from field logs
7. **Annotated Media** - Key photos/frames with observations marked
8. **Action Register** - Prioritized items requiring immediate attention

## Methodology

This skill uses the **MONITOR Framework**:

- **M**edia analysis for visual progress verification
- **O**n-schedule tracking against critical path
- **N**on-compliance detection for safety and quality
- **I**ntelligence extraction from daily reports
- **T**rend identification across reporting periods
- **O**utcome prediction based on current trajectory
- **R**ecommendation engine for corrective actions

Each analysis dimension feeds into the composite Site Health Score, updated with each new data input.

## Advanced Configuration

| Parameter | Default | Options | Description |
|-----------|---------|---------|-------------|
| `analysis_depth` | `standard` | quick, standard, detailed | Level of visual analysis detail |
| `safety_standard` | `osha` | osha, local, custom | Safety compliance benchmark |
| `schedule_tolerance` | `5_days` | 1-14 days | Deviation threshold before alerting |
| `quality_checklist` | `standard` | standard, enhanced, spec_specific | QC inspection criteria |
| `alert_recipients` | `owner` | owner, pm, super, lender | Who receives automated alerts |
| `media_frequency` | `weekly` | daily, weekly, biweekly | Expected site documentation cadence |

## Example

### Input
```
project_id: NASH-MF-2025-042
site_media: [drone_capture_20260315.mp4, site_photos_20260315.zip]
construction_schedule: baseline_rev3.mpp
daily_reports: [daily_log_0310-0315.pdf]
weather_data: nashville_tn_0310-0316
```

### Output
```
SITE MANAGEMENT REPORT
======================
Project: Nashville Midtown 42-Unit | Week of 03/10-03/15

PROGRESS SNAPSHOT:
- Overall Completion: 62% (Schedule target: 67%)
- Status: 5% BEHIND SCHEDULE
- Schedule Health Score: 72/100 (SIGNIFICANT DELAYS)

Building A (24 units):
- Structural: 100% ✓
- MEP Rough: 85% (target: 95%) ← BEHIND
- Drywall: 60% (target: 70%) ← BEHIND
- Finishes: 15% (target: 20%) ← BEHIND

Building B (18 units):
- Structural: 100% ✓
- MEP Rough: 70% (target: 75%) — ON TRACK
- Drywall: 40% (target: 45%) — ON TRACK
- Finishes: 0% (target: 0%) ✓

SCHEDULE DEVIATIONS:
[ALERT] MEP Rough-in Building A: 8 days behind
  - Cause: HVAC subcontractor crew reduced from 6 to 4
  - Critical Path Impact: YES — delays drywall start
  - Projected Completion Delay: 5 days if not corrected
  - Action: Demand full crew restoration by Monday

[WATCH] Drywall Building A: 4 days behind
  - Cause: Dependent on MEP completion
  - Critical Path Impact: Cascading from MEP delay
  - Action: Dependent on MEP resolution

SAFETY SCORECARD: 82/100
[SERIOUS] Fall protection violation — Building B, 3rd floor
  - Missing guardrails on east elevation opening
  - Photo reference: IMG_4521.jpg (annotated)
  - Action: IMMEDIATE — install guardrails before next shift

[OBSERVATION] Housekeeping — Building A, ground floor
  - Debris accumulation in east stairwell
  - Action: Clean by end of day Friday

QUALITY OBSERVATIONS:
- Drywall taping Building A, Unit 207: tape bubbling at ceiling joint
- MEP: Ductwork clearance issue at Building A corridor (3" vs. 6" minimum)

DAILY REPORT INSIGHTS:
- Average daily manpower: 28 (down from 34 last week)
- HVAC sub consistently understaffed (noted 3 of 5 days)
- 1.5 weather days lost (rain Tuesday, half day Wednesday)
- Material delivery: drywall stock sufficient for 2 weeks

PRIORITY ACTIONS:
1. [URGENT] Install guardrails Building B, 3rd floor east
2. [HIGH] Meeting with HVAC sub re: crew staffing — demand recovery plan
3. [MEDIUM] Resolve ductwork clearance issue before drywall closes ceiling
4. [LOW] Clean stairwell debris
```

## Edge Cases & Best Practices

**Low-Quality Media**: When site photos are poorly lit, taken from limited angles, or low resolution, reduce confidence scores on visual assessments and flag gaps that need supplemental documentation.

**Multiple Concurrent Projects**: Run separate analyses per project but generate a portfolio-level dashboard that ranks projects by health score so the most critical issues surface first.

**Disputed Progress**: When your visual assessment conflicts with the GC's reported progress, document both assessments with photo evidence. This creates an objective record for draw request negotiations.

**Seasonal Considerations**: Adjust schedule expectations for winter concrete pours, summer heat advisories, and regional weather patterns. Build historical weather productivity factors into deviation calculations.

## Integration

**Feeds into:** Project Tracker (progress data), Cost Forecaster (delay cost impact)

**Receives from:** Construction schedule updates, daily field reports, drone/photo capture systems, weather APIs
