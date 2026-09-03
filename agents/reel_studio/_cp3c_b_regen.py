#!/usr/bin/env python3
"""One-shot regeneration for issue #19792 PART 2 -- deterministic template
regeneration (not a live LLM call) for the 20 variants the fixed director_qa
validator now correctly fails. INFERRED choice, logged in docs/spec/19792.md:
templates are used instead of a live hook_writer LLM call because they are
free, deterministic, and directly testable against every one of the 5 named
checks before a single row is written -- the LLM path (router_client ->
OpenRouter) is not re-run here, but nothing in this file changes the
mechanism generate_variants_for_reel() itself uses, so it stays the path of
record for NEW reels.

Archetype reassignment is computed once (not per-title) from the row's own
facts: sale_type/phase and a public.multi_county_auctions lookup
(sale_result/winning_bidder/plaintiff), the same facts director_qa's
check_archetype_data_match() checks against.
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

VALID_POSTSALE_NO_BANK_ARCHETYPES = ["shock_number", "underdog_bidder", "red_flag_warning", "hidden_value_reveal"]

ARCHETYPE_EMOJI = {
    "shock_number": "\U0001F633\U0001F92F",       # 😳🤯
    "underdog_bidder": "\U0001F3C6\U0001F440",     # 🏆👀
    "red_flag_warning": "\U0001F630\U0001F440",    # 😰👀
    "hidden_value_reveal": "\U0001F92F\U0001F440",  # 🤯👀
    "bank_vs_house": "\U0001F494\U0001F3C6",       # 💔🏆
    "mystery_nobody_bid": "\U0001F631\U0001F440",  # 😱👀
    "countdown_presale": "\U0001F630\U0001F976",   # 😰🥶
}


def title_for(archetype: str, county_name: str, reel: dict) -> str:
    assessed = reel.get("assessed_value")
    days = reel.get("days_to_auction")
    emoji = ARCHETYPE_EMOJI[archetype]
    if archetype == "shock_number":
        stem = f"The County Valued This {county_name} Home At ${assessed:,.0f}" if assessed else f"This {county_name} Home Shocked The Whole Auction"
    elif archetype == "underdog_bidder":
        stem = f"An Underdog Bidder Beat The Field In {county_name}"
    elif archetype == "red_flag_warning":
        stem = f"This {county_name} Home Waved Every Red Flag"
    elif archetype == "hidden_value_reveal":
        stem = f"This {county_name} Home Hid Its Real Value"
    elif archetype == "bank_vs_house":
        stem = f"The Bank Fought Hard For This {county_name} House"
    elif archetype == "mystery_nobody_bid":
        stem = f"Nobody Dared To Bid On This {county_name} Home"
    elif archetype == "countdown_presale":
        stem = f"This {county_name} Home Hits Auction In {days} Days" if days is not None else f"This {county_name} Home Nears Its Auction Date"
    else:
        raise ValueError(f"no template for archetype {archetype!r}")
    return f"{stem}…{emoji}"


def choose_archetypes(current: list[str], reel_facts: dict) -> dict:
    """Returns {old_archetype_slot_index: new_archetype} keeping every
    already-valid archetype in place and filling reassigned slots with the
    smallest set of data-valid archetypes not already used in this reel."""
    valid_pool = list(VALID_POSTSALE_NO_BANK_ARCHETYPES) if reel_facts.get("phase") != "presale" else None
    result = {}
    used = set()
    needs_reassign = []
    for i, a in enumerate(current):
        ok, _ = hw.check_archetype_data_match(a, reel_facts, reel_facts.get("third_party_bidder"), reel_facts.get("plaintiff_confirmed_bank"))
        if ok:
            result[i] = a
            used.add(a)
        else:
            needs_reassign.append(i)
    if valid_pool is None:
        raise NotImplementedError("presale archetype reassignment not exercised by this batch")
    remaining = [a for a in valid_pool if a not in used]
    for i in needs_reassign:
        if not remaining:
            raise RuntimeError(f"no data-valid archetype left to assign for slot {i}")
        result[i] = remaining.pop(0)
    return result


def main():
    variants = lib.run_sql("""
        select id, reel_id, variant_key, title, variant_dna, script, caption_groups
        from winnerdata.reel_variants order by reel_id, variant_key;
    """)
    for v in variants:
        for col in ("variant_dna", "script", "caption_groups"):
            if isinstance(v.get(col), str):
                v[col] = json.loads(v[col])

    by_reel: dict[str, list[dict]] = {}
    for v in variants:
        by_reel.setdefault(v["reel_id"], []).append(v)

    all_report = []
    for reel_id, vs in by_reel.items():
        reel_facts = dqa.fetch_reel_facts(reel_id)
        county_name = reel_facts["county"].title()
        current_archetypes = [v["variant_dna"]["archetype"] for v in vs]
        reassignment = choose_archetypes(current_archetypes, reel_facts)

        for i, v in enumerate(vs):
            new_archetype = reassignment[i]
            new_dna = dict(v["variant_dna"])
            new_dna["archetype"] = new_archetype
            new_title = title_for(new_archetype, county_name, reel_facts)

            ok, reasons = hw.validate_title(new_title)
            leak_ok, leak_reasons = hw.check_payoff_leak(new_title, reel_facts)
            arch_ok, arch_reasons = hw.check_archetype_data_match(
                new_archetype, reel_facts, reel_facts.get("third_party_bidder"), reel_facts.get("plaintiff_confirmed_bank"))
            assert ok, f"{reel_facts['county']}/{v['variant_key']}: title invalid: {reasons} -- {new_title!r}"
            assert leak_ok, f"{reel_facts['county']}/{v['variant_key']}: payoff leak: {leak_reasons} -- {new_title!r}"
            assert arch_ok, f"{reel_facts['county']}/{v['variant_key']}: archetype mismatch: {arch_reasons}"

            beats = v["script"].get("beats", [])
            if beats:
                beats[0]["line"] = new_title.split("…")[0].strip()
            caps = v.get("caption_groups") or []
            if caps:
                caps[0]["words"] = " ".join(new_title.split("…")[0].strip().split()[:5])

            lib.run_sql(f"""
                update winnerdata.reel_variants
                set title = {lib.sql_str(new_title)},
                    variant_dna = {lib.sql_jsonb(new_dna)},
                    script = {lib.sql_jsonb(v['script'])},
                    caption_groups = {lib.sql_jsonb(caps)},
                    updated_at = now()
                where id = {lib.sql_str(v['id'])};
            """)
            all_report.append({
                "county": reel_facts["county"], "variant_key": v["variant_key"],
                "old_archetype": current_archetypes[i], "new_archetype": new_archetype,
                "old_title": v["title"], "new_title": new_title,
            })

    print(json.dumps(all_report, indent=2))


if __name__ == "__main__":
    main()
