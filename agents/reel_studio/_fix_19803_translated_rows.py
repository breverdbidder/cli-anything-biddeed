#!/usr/bin/env python3
"""One-shot REPAIR for a mistake made while fixing issue #19803: the first
regen pass (_cp3c_regen_19803.py) called hook_writer.build_bespoke_script()
with lang=<row's lang> for ALL variants, including the 3 es/pt-BR rows that
are actually LLM-TRANSLATED sibling rows (produced by translator.py from an
English source, see that module's docstring) -- hook_writer.py has no
pt-BR branch at all (falls through to English) and its "es" branch
interpolates the raw English tier word untranslated ("condicion good").
That first pass silently overwrote those 3 rows' spoken script with
wrong-language / mixed-language text.

This script restores each row's ORIGINAL professionally-translated wording
(recovered from this session's own before/after log, /tmp/19803_regen_output.json,
which captured the live pre-fix text before the bad UPDATE ran) and applies
ONLY the minimal, surgical fix the issue actually asked for: the condition
clause ("de condicao desconhecida" / "en condicion desconocida" -- Portuguese/
Spanish for "unknown-condition") is dropped from the setup beat, exactly like
the English fix does for _has_condition_data()==False. No re-translation, no
new LLM call, no change to any other beat."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
import hook_writer as hw  # noqa: E402
import director_qa as dqa  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import biddeed_reels_lib as lib  # noqa: E402

TIMING = [(0, 2), (2, 9), (9, 20), (20, 28), (28, 32)]

FIXES = [
    {
        "id": "34e4ad24-ad7c-4c85-b6dc-9338e4d94d90",
        "lang": "pt-BR",
        "title_stem": "Os Registros de Martin Colocam Esta Casa em $902,653",
        "beats": [
            "Esta casa em Martin County foi avaliada em $902,653.",
            "Os licitantes tiveram exatamente um número para reagir antes de o martelo cair.",
            "Vendeu por $826,200... 8.5 por cento abaixo do valor avaliado.",
            "Esse número em Martin County... você teria adivinhado?",
        ],
    },
    {
        "id": "3d854c6c-9fac-4b3e-b28d-b5e07c454f78",
        "lang": "es",
        "title_stem": "Los compradores de Escambia nunca vieron venir este valor",
        "beats": [
            "Esta vivienda de Escambia County fue tasada en $112,410.",
            "Nada en el listado insinuaba el valor que esta propiedad realmente tenía.",
            "Se vendió por $39,600... 64.8 por ciento por debajo del valor tasado.",
            "El valor real estuvo ahí en Escambia County todo el tiempo... y nadie lo vio venir.",
        ],
    },
    {
        "id": "e90204ab-82ea-415d-b0dd-ed7fa460319d",
        "lang": "pt-BR",
        "title_stem": "Uma Aposta Improvável Levou Esta Propriedade em Polk Para Casa",
        "beats": [
            "Esta casa do Polk County foi avaliada em $238,169.",
            "Compradores maiores rondaram, mas o campo diminuiu rápido nos degraus do tribunal.",
            "Vendeu por $162,100... 31.9 por cento abaixo do valor avaliado.",
            "Um licitante seguiu firme no Polk County... é assim que se ganha uma.",
        ],
    },
]


def main():
    results = []
    for f in FIXES:
        lines = [f["title_stem"]] + f["beats"]
        beats = [{"start_s": s, "end_s": e, "line": l} for (s, e), l in zip(TIMING, lines)]
        script = {"beats": beats}

        placeholder_check = dqa.check_no_placeholder_tokens({"title": f["title_stem"], "script": script})
        assert placeholder_check["pass"], f"{f['id']}: still has placeholder tokens: {placeholder_check['hits']}"

        caption_groups = hw.build_caption_groups_from_beats(beats)

        lib.run_sql(f"""
            update winnerdata.reel_variants
            set script = {lib.sql_jsonb(script)},
                caption_groups = {lib.sql_jsonb(caption_groups)},
                updated_at = now()
            where id = {lib.sql_str(f['id'])};
        """)
        results.append({"id": f["id"], "lang": f["lang"], "restored_blob": " ".join(lines),
                         "placeholder_check_pass": placeholder_check["pass"]})

    import json
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
