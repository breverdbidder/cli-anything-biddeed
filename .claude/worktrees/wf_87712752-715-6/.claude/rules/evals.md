---
pattern: "*/eval/**"
---
# AUTOLOOP Eval Rules

- 25 binary assertions per eval.json. No partial credit
- L1 = activation (did it trigger?). L2 = output quality (is it correct?)
- eval_runner.py is canonical. Never create alternative eval scripts
- Results logged to Supabase with: harness_name, score, iteration, timestamp
- Threshold: score must IMPROVE to commit. Equal score = no commit
- Nightly GHA run at 2AM EST via autoloop.yml. No manual triggers
- Failed eval = revert to last good SKILL.md. Never push broken skills
