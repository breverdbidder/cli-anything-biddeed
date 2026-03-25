# DESIGNWISE-S5-DISPATCH.md
# DesignWise Squad — Sprint 5: Design Intelligence Integration
# Status: READY FOR DISPATCH
# Author: Claude AI Architect | Date: 2026-03-24
# Target: Claude Code via Summit (Hetzner 87.99.129.125)
# Estimated: 45 min autonomous | Token budget: LOW

---

## OBJECTIVE

Deploy 4 new skills into `zonewise-web/.claude/skills/` that give every DesignWise agent access to:
1. **UI UX Pro Max** — BM25 design intelligence (161 palettes, 85 styles, 99 UX rules, 57 font pairs)
2. **Stitch shadcn-ui** — shadcn/ui component discovery + installation best practices
3. **Stitch enhance-prompt** — Professional UI/UX prompt engineering with keyword mappings
4. **Stitch design-md** — DESIGN.md generation from Stitch project analysis

## PROVENANCE

| Skill | Source | License | Security | Score |
|:---|:---|:---|:---|:---|
| ui-ux-pro-max | nextlevelbuilder/ui-ux-pro-max-skill v2.1.0 | MIT | Zero network calls, local CSV+Python only | 84 ADOPT |
| stitch-shadcn-ui | google-labs-code/stitch-skills | Apache-2.0 | Uses shadcn MCP (free, no API key) | 72 EVAL→ADOPT standalone |
| stitch-enhance-prompt | google-labs-code/stitch-skills | Apache-2.0 | Pure prompt knowledge, no deps | 72 EVAL→ADOPT standalone |
| stitch-design-md | google-labs-code/stitch-skills | Apache-2.0 | Pure template + examples, no deps | 72 EVAL→ADOPT standalone |

**REJECTED:** 21st.dev Magic MCP (score 58 CONDITIONAL — $20/mo, phone-home to magic.21st.dev, invasive git ops, React-only)

## EXECUTION STEPS

### Step 1: Clone Source Repos (temp)

```bash
cd /tmp
git clone --depth 1 https://github.com/google-labs-code/stitch-skills.git
git clone --depth 1 https://github.com/nextlevelbuilder/ui-ux-pro-max-skill.git
```

### Step 2: Deploy UI UX Pro Max

```bash
cd ~/repos/zonewise-web

# Create skill directory
mkdir -p .claude/skills/ui-ux-pro-max/scripts
mkdir -p .claude/skills/ui-ux-pro-max/data

# Copy search engine
cp /tmp/ui-ux-pro-max-skill/src/ui-ux-pro-max/scripts/core.py .claude/skills/ui-ux-pro-max/scripts/
cp /tmp/ui-ux-pro-max-skill/src/ui-ux-pro-max/scripts/search.py .claude/skills/ui-ux-pro-max/scripts/
cp /tmp/ui-ux-pro-max-skill/src/ui-ux-pro-max/scripts/design_system.py .claude/skills/ui-ux-pro-max/scripts/

# Copy essential data (skip design.csv, draft.csv = Chinese backups; google-fonts.csv = 728K bloat)
for f in app-interface charts colors icons landing products react-performance styles typography ui-reasoning ux-guidelines; do
  cp /tmp/ui-ux-pro-max-skill/src/ui-ux-pro-max/data/${f}.csv .claude/skills/ui-ux-pro-max/data/
done

# Copy stack-specific guidelines
cp -r /tmp/ui-ux-pro-max-skill/src/ui-ux-pro-max/data/stacks .claude/skills/ui-ux-pro-max/data/ 2>/dev/null || true
```

### Step 3: Create UI UX Pro Max SKILL.md

Write `.claude/skills/ui-ux-pro-max/SKILL.md` with content from the architect-prepared file.
Key sections: House Brand override, domain search commands, agent integration table.
**File provided in this dispatch — copy verbatim from `docs/skills/ui-ux-pro-max-SKILL.md`.**

### Step 4: Deploy Stitch Standalone Skills

```bash
cd ~/repos/zonewise-web

# shadcn-ui skill
mkdir -p .claude/skills/stitch-shadcn-ui
cp /tmp/stitch-skills/skills/shadcn-ui/SKILL.md .claude/skills/stitch-shadcn-ui/
cp -r /tmp/stitch-skills/skills/shadcn-ui/examples .claude/skills/stitch-shadcn-ui/ 2>/dev/null || true
cp -r /tmp/stitch-skills/skills/shadcn-ui/resources .claude/skills/stitch-shadcn-ui/ 2>/dev/null || true
cp -r /tmp/stitch-skills/skills/shadcn-ui/scripts .claude/skills/stitch-shadcn-ui/ 2>/dev/null || true

# enhance-prompt skill
mkdir -p .claude/skills/stitch-enhance-prompt
cp /tmp/stitch-skills/skills/enhance-prompt/SKILL.md .claude/skills/stitch-enhance-prompt/
cp -r /tmp/stitch-skills/skills/enhance-prompt/references .claude/skills/stitch-enhance-prompt/ 2>/dev/null || true

# design-md skill
mkdir -p .claude/skills/stitch-design-md
cp /tmp/stitch-skills/skills/design-md/SKILL.md .claude/skills/stitch-design-md/
cp -r /tmp/stitch-skills/skills/design-md/examples .claude/skills/stitch-design-md/ 2>/dev/null || true
```

### Step 5: Validate

```bash
cd ~/repos/zonewise-web

# Verify all skills have SKILL.md
for skill in ui-ux-pro-max stitch-shadcn-ui stitch-enhance-prompt stitch-design-md; do
  if [ -f ".claude/skills/${skill}/SKILL.md" ]; then
    echo "✅ ${skill}: SKILL.md present"
  else
    echo "❌ ${skill}: MISSING"
    exit 1
  fi
done

# Verify search engine works
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "dark dashboard analytics" --domain style -n 2
echo "✅ BM25 search engine operational"

# Verify design system generator
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "real estate zoning SaaS" --design-system -p "ZoneWise"
echo "✅ Design system generator operational"

# Count total skill files
echo "Total skill files: $(find .claude/skills/ui-ux-pro-max .claude/skills/stitch-shadcn-ui .claude/skills/stitch-enhance-prompt .claude/skills/stitch-design-md -type f | wc -l)"
```

### Step 6: Update CLAUDE.md

Append to the skills section of `CLAUDE.md`:

```markdown
## Design Intelligence Skills (S5 - 2026-03-24)

### ui-ux-pro-max
- BM25 search over 11 CSV databases (580KB total)
- Domains: style, color, typography, ux, chart, landing, product, app-interface, icons, ui-reasoning, react-performance
- Usage: `python3 .claude/skills/ui-ux-pro-max/scripts/search.py "<query>" --domain <domain>`
- Design system: `python3 .claude/skills/ui-ux-pro-max/scripts/search.py "<query>" --design-system -p "<project>"`
- Source: nextlevelbuilder/ui-ux-pro-max-skill v2.1.0 (MIT)

### stitch-shadcn-ui
- shadcn/ui component discovery, installation, customization best practices
- Uses shadcn MCP tools (list_components, get_component_metadata, get_component_demo)
- Source: google-labs-code/stitch-skills (Apache-2.0)

### stitch-enhance-prompt
- Prompt enhancement pipeline for Stitch MCP generation
- Maps vague terms → professional UI/UX terminology
- Reference: KEYWORDS.md with atmosphere descriptors + UI component vocabulary
- Source: google-labs-code/stitch-skills (Apache-2.0)

### stitch-design-md
- Generates .stitch/DESIGN.md from existing Stitch projects
- Extracts design tokens (colors, typography, spacing) into structured format
- Source: google-labs-code/stitch-skills (Apache-2.0)
```

### Step 7: Commit & Push

```bash
cd ~/repos/zonewise-web
git add .claude/skills/ui-ux-pro-max/ .claude/skills/stitch-shadcn-ui/ .claude/skills/stitch-enhance-prompt/ .claude/skills/stitch-design-md/
git commit -m "feat(designwise): S5 — deploy design intelligence skills

- ui-ux-pro-max: BM25 search over 11 design databases (MIT)
- stitch-shadcn-ui: shadcn/ui component best practices (Apache-2.0)
- stitch-enhance-prompt: UI/UX prompt engineering (Apache-2.0)
- stitch-design-md: DESIGN.md generator (Apache-2.0)

Provenance: Architect evaluation score 84 ADOPT (ui-ux-pro-max), 72 ADOPT-standalone (stitch skills)
Rejected: 21st.dev Magic MCP (score 58, $20/mo, phone-home, invasive git ops)"

git push origin main
```

### Step 8: Cleanup

```bash
rm -rf /tmp/stitch-skills /tmp/ui-ux-pro-max-skill
```

---

## AGENT MAPPING

How each DesignWise agent uses the new skills:

```yaml
StitchWise:
  before_generation:
    - stitch-enhance-prompt → refine user prompt with UI/UX keywords
    - ui-ux-pro-max --design-system → generate style context
  after_generation:
    - stitch-design-md → extract tokens into DESIGN.md

BrandGuard:
  validation:
    - ui-ux-pro-max --domain color → validate palette against professional standards
    - ui-ux-pro-max --domain typography → validate font choices
    - ui-ux-pro-max --domain ux → check for anti-patterns

CodeWise:
  implementation:
    - stitch-shadcn-ui → component selection + installation
    - ui-ux-pro-max --domain react-performance → optimization patterns
    - ui-ux-pro-max --domain style → Tailwind class recommendations

ContentWise:
  copy:
    - ui-ux-pro-max --domain landing → conversion patterns for copy placement

SEOWise:
  performance:
    - ui-ux-pro-max --domain ux → Core Web Vitals UX decisions

IterateWise:
  ab_testing:
    - ui-ux-pro-max --design-system → generate variant styles
    - stitch-enhance-prompt → create diverse test prompts
```

---

## SUCCESS CRITERIA

- [ ] All 4 skills deployed to `.claude/skills/`
- [ ] `search.py --domain style` returns results
- [ ] `search.py --design-system` generates complete system
- [ ] CLAUDE.md updated with skill documentation
- [ ] Git commit pushed to main
- [ ] Zero new API keys required
- [ ] Zero recurring costs added

---

## COST

$0.00 — all tools are MIT/Apache-2.0, zero API dependencies, local execution only.
