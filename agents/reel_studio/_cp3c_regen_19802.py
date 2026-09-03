#!/usr/bin/env python3
"""One-shot regeneration for issue #19802 -- fixes 3 defects the shipped
20/22-variant batch has: (1) the sold-price/discount payoff spoken in beat 2
instead of confined to the 20-28s payoff beat, (2) a single hardcoded
"Next <County> countdown starts now" loop line on every variant regardless
of archetype/phase, (3) mad-lib titles -- one fixed sentence template per
archetype with only the county token substituted.

Deterministic (not live-LLM) regeneration, same INFERRED rationale as issue
#19792 PART 2's _cp3c_b_regen.py (docs/spec/19792.md): free, reproducible,
directly testable against every check below before a row is written. This
script does NOT touch archetype assignment (already fixed by #19792/#19793
and re-verified live here) -- it rewrites title/script/caption_groups only.

Template diversity (DEFECT 3): each archetype's title-template pool is
round-robined across that archetype's siblings in COUNTY NAME ORDER (a
stable, reproducible ordering) so no two counties collide on the same
template structure -- verified against
hook_writer.check_title_structural_similarity() before any UPDATE is issued.
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
        select rv.id, rv.reel_id, rv.variant_key, rv.title, rv.variant_dna, rv.script,
               rv.caption_groups, br.county
        from winnerdata.reel_variants rv
        join winnerdata.biddeed_reels br on br.id = rv.reel_id
        order by rv.archetype, br.county, (rv.variant_dna->>'lang') nulls first;
    """)
    for v in variants:
        for col in ("variant_dna", "script", "caption_groups"):
            if isinstance(v.get(col), str):
                v[col] = json.loads(v[col])

    print(f"TOTAL LIVE VARIANTS FOUND: {len(variants)}", file=sys.stderr)

    reel_facts_cache: dict[str, dict] = {}
    by_archetype: dict[str, list[dict]] = {}
    for v in variants:
        archetype = v["variant_dna"]["archetype"]
        by_archetype.setdefault(archetype, []).append(v)

    before_after = []
    all_new_titles = []  # for the batch-wide structural-similarity gate

    planned = []  # (variant, reel_facts, template_index, lang, new_title, new_stem)
    for archetype, group in by_archetype.items():
        # Stable order: english rows first (by county), spanish rows after --
        # round-robin template_index across EACH LANGUAGE'S OWN sequence so a
        # single es row never "steals" an index from the 5-wide en sequence.
        en_rows = [v for v in group if not v["variant_dna"].get("lang")]
        es_rows = [v for v in group if v["variant_dna"].get("lang") == "es"]
        for lang, rows in (("en", en_rows), ("es", es_rows)):
            for i, v in enumerate(rows):
                reel_id = v["reel_id"]
                if reel_id not in reel_facts_cache:
                    reel_facts_cache[reel_id] = dqa.fetch_reel_facts(reel_id)
                reel_facts = reel_facts_cache[reel_id]

                new_title = hw.generate_bespoke_title(archetype, reel_facts, template_index=i, lang=lang)
                new_stem = new_title.split(hw.ELLIPSIS)[0]
                planned.append((v, reel_facts, i, lang, new_title, new_stem))
                all_new_titles.append({
                    "title": new_title, "county": reel_facts.get("county", "").title(),
                    "archetype": archetype, "id": v["id"],
                })

    # Batch-wide structural-similarity gate BEFORE any DB write -- if the
    # round-robin assignment above still produced a collision, fail loudly
    # rather than write a batch that would immediately fail its own new QA check.
    sim_ok, sim_reasons = hw.check_title_structural_similarity(all_new_titles)
    if not sim_ok:
        print("ABORT: planned title batch fails structural-similarity gate:", file=sys.stderr)
        for r in sim_reasons:
            print(" -", r, file=sys.stderr)
        sys.exit(1)

    for v, reel_facts, template_index, lang, new_title, new_stem in planned:
        archetype = v["variant_dna"]["archetype"]

        title_ok, title_reasons = hw.validate_title(new_title)
        leak_ok, leak_reasons = hw.check_payoff_leak(new_title, reel_facts)
        arch_ok, arch_reasons = hw.check_archetype_data_match(
            archetype, reel_facts, reel_facts.get("third_party_bidder"), reel_facts.get("plaintiff_confirmed_bank"),
            reel_facts.get("auction_venue_online"))
        assert title_ok, f"{reel_facts['county']}/{v['variant_key']}/{lang}: title invalid: {title_reasons} -- {new_title!r}"
        assert leak_ok, f"{reel_facts['county']}/{v['variant_key']}/{lang}: payoff leak: {leak_reasons} -- {new_title!r}"
        assert arch_ok, f"{reel_facts['county']}/{v['variant_key']}/{lang}: archetype mismatch: {arch_reasons}"

        new_script = hw.build_bespoke_script(archetype, reel_facts, new_stem, lang=lang)
        payoff_ok, payoff_reasons = hw.check_script_payoff_confinement(new_script["beats"], reel_facts)
        assert payoff_ok, f"{reel_facts['county']}/{v['variant_key']}/{lang}: script payoff leak: {payoff_reasons}"

        loop_line = new_script["beats"][-1]["line"]
        loop_ok, loop_reasons = hw.check_loop_line_archetype_mismatch(loop_line, reel_facts)
        assert loop_ok, f"{reel_facts['county']}/{v['variant_key']}/{lang}: loop line mismatch: {loop_reasons}"

        new_caption_groups = hw.build_caption_groups_from_beats(new_script["beats"])

        old_beats = (v.get("script") or {}).get("beats", [])
        old_payoff_ok, old_payoff_reasons = hw.check_script_payoff_confinement(old_beats, reel_facts)
        old_loop_line = old_beats[-1]["line"] if old_beats else ""
        old_loop_ok, old_loop_reasons = hw.check_loop_line_archetype_mismatch(old_loop_line, reel_facts)

        lib.run_sql(f"""
            update winnerdata.reel_variants
            set title = {lib.sql_str(new_title)},
                script = {lib.sql_jsonb(new_script)},
                caption_groups = {lib.sql_jsonb(new_caption_groups)},
                updated_at = now()
            where id = {lib.sql_str(v['id'])};
        """)

        before_after.append({
            "county": reel_facts["county"], "variant_key": v["variant_key"], "lang": lang,
            "archetype": archetype, "template_index": template_index,
            "old_title": v["title"], "new_title": new_title,
            "old_payoff_confined": old_payoff_ok, "old_payoff_reasons": old_payoff_reasons,
            "new_payoff_confined": payoff_ok,
            "old_loop_line": old_loop_line, "old_loop_line_ok": old_loop_ok, "old_loop_line_reasons": old_loop_reasons,
            "new_loop_line": loop_line, "new_loop_line_ok": loop_ok,
        })

    print(json.dumps(before_after, indent=2, default=str))


if __name__ == "__main__":
    main()
