#!/usr/bin/env python3
"""One-shot regeneration for issue #19803 -- the literal "unknown-condition"
placeholder token that leaked into 20/21 shipped scripts. Root cause was TWO
bugs, both fixed in hook_writer.py / director_qa.py before this script runs:

  1. director_qa.fetch_reel_facts()'s SELECT omitted condition_json, so every
     reel_facts dict built for the #19802 regen had condition_json=None even
     though the parent winnerdata.biddeed_reels row had a real
     general_condition_tier (VERIFIED live: 0/N rows actually had null
     condition_json -- the issue's own "property.condition is null" premise
     was INFERRED and wrong; the column just never reached the generator).
  2. hook_writer.py's spoken-text templates interpolated the internal
     "unknown" sentinel directly as an adjective ("{tier}-condition") with no
     graceful fallback for the genuinely-missing case.

This script re-derives script + caption_groups ONLY (title/archetype/loop-
line logic untouched, per the issue's non-goals) for every live variant,
using the now-fixed fetch_reel_facts() + build_bespoke_script(), and writes
back only the rows that actually changes.
"""
from __future__ import annotations

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
import hook_writer as hw  # noqa: E402
import director_qa as dqa  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import biddeed_reels_lib as lib  # noqa: E402


def main():
    variants = lib.run_sql("""
        select rv.id, rv.reel_id, rv.variant_key, rv.title, rv.variant_dna, rv.script, rv.caption_groups
        from winnerdata.reel_variants rv
        order by rv.id;
    """)
    for v in variants:
        for col in ("variant_dna", "script", "caption_groups"):
            if isinstance(v.get(col), str):
                v[col] = json.loads(v[col])

    print(f"TOTAL LIVE VARIANTS FOUND: {len(variants)}", file=sys.stderr)

    reel_facts_cache: dict[str, dict] = {}
    before_after = []

    for v in variants:
        reel_id = v["reel_id"]
        if reel_id not in reel_facts_cache:
            reel_facts_cache[reel_id] = dqa.fetch_reel_facts(reel_id)
        reel_facts = reel_facts_cache[reel_id]

        old_beats = (v.get("script") or {}).get("beats", [])
        old_blob = " ".join(str(b.get("line", "")) for b in old_beats)
        old_hits = dqa.check_no_placeholder_tokens({"title": v["title"], "script": {"beats": old_beats}})["hits"]

        archetype = (v["variant_dna"] or {}).get("archetype") or v.get("archetype")
        lang = (v["variant_dna"] or {}).get("lang") or "en"
        title_stem = v["title"].split(hw.ELLIPSIS)[0]

        new_script = hw.build_bespoke_script(archetype, reel_facts, title_stem, lang=lang)

        payoff_ok, payoff_reasons = hw.check_script_payoff_confinement(new_script["beats"], reel_facts)
        assert payoff_ok, f"{v['id']}/{v['variant_key']}: script payoff leak: {payoff_reasons}"
        loop_line = new_script["beats"][-1]["line"]
        loop_ok, loop_reasons = hw.check_loop_line_archetype_mismatch(loop_line, reel_facts)
        assert loop_ok, f"{v['id']}/{v['variant_key']}: loop line mismatch: {loop_reasons}"
        placeholder_check = dqa.check_no_placeholder_tokens({"title": v["title"], "script": new_script})
        assert placeholder_check["pass"], f"{v['id']}/{v['variant_key']}: still has placeholder tokens: {placeholder_check['hits']}"

        new_caption_groups = hw.build_caption_groups_from_beats(new_script["beats"])
        new_blob = " ".join(b["line"] for b in new_script["beats"])

        changed = new_blob != old_blob
        if changed:
            lib.run_sql(f"""
                update winnerdata.reel_variants
                set script = {lib.sql_jsonb(new_script)},
                    caption_groups = {lib.sql_jsonb(new_caption_groups)},
                    updated_at = now()
                where id = {lib.sql_str(v['id'])};
            """)

        before_after.append({
            "variant_id": v["id"], "variant_key": v["variant_key"], "archetype": archetype, "lang": lang,
            "changed": changed,
            "old_had_placeholder_tokens": len(old_hits) > 0,
            "old_placeholder_hits": old_hits,
            "old_blob": old_blob,
            "new_blob": new_blob,
            "new_placeholder_check_pass": placeholder_check["pass"],
        })

    print(json.dumps(before_after, indent=2, default=str))


if __name__ == "__main__":
    main()
