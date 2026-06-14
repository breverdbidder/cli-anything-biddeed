"""
LLM extraction. Turns rendered ordinance text into structured, cited standards.
The prompt enforces the honesty protocol: NULL when not stated, never inferred;
PUD/planned flagged site-specific with NULL density; every value carries its section.
"""
import json
import anthropic
import config

SYSTEM = """You extract zoning dimensional standards from municipal ordinance text.
You are feeding a certification database where a WRONG value is far worse than a BLANK one.

ABSOLUTE RULES:
- Extract ONLY values explicitly stated in the provided text. If a field is not stated, return null.
- NEVER infer, average, round, or guess. No value from prior knowledge of the city.
- For any Planned Unit Development / Planned Development district (PUD, PD, RPUD, etc.):
  set is_site_specific=true, max_density_num=null, density_basis="site_development_order".
  Such districts have NO fixed district-table density; their standards come from a per-parcel order.
- max_density_num is dwelling units per ACRE as a number. If the text gives lot-area-per-unit
  or a range, put the raw phrasing in max_density_raw and the numeric CEILING (or null if a true
  range with no single ceiling) in max_density_num.
- source_section must be the exact ordinance citation you read the value from (e.g. "Sec. 173.022",
  "Sec. 62-1334"). If you cannot identify the section, set confidence="low".
- If a requested code does not appear in the text, return it with all standards null,
  confidence="low", notes="code not present in provided content".
- parking_per_1000 is usually NOT in a dimensional table (it lives in a separate parking chapter).
  Return null unless it is explicitly in this text.

Return ONLY a JSON array, no prose, no markdown fences."""

SCHEMA_HINT = """Each array element:
{
  "zoning_code": str,
  "zoning_desc": str | null,
  "max_density_raw": str | null,
  "max_density_num": number | null,
  "far": number | null,
  "parking_per_1000": number | null,
  "max_height_ft": number | null,
  "min_lot_size": str | null,
  "is_site_specific": bool,
  "density_basis": "district_table" | "site_development_order" | "flu_ceiling" | null,
  "source_section": str | null,
  "confidence": "high" | "medium" | "low",
  "notes": str | null
}"""


def extract_standards(text: str, target_codes: list[str], jurisdiction: str) -> list[dict]:
    # Cost canon: route via cliproxy/Smart Router when ANTHROPIC_BASE_URL is set, not a raw sk-ant key.
    kwargs = {"api_key": config.ANTHROPIC_API_KEY}
    if config.ANTHROPIC_BASE_URL:
        kwargs["base_url"] = config.ANTHROPIC_BASE_URL
    api = anthropic.Anthropic(**kwargs)
    user = (
        f"Jurisdiction: {jurisdiction}\n"
        f"Extract standards for exactly these zoning codes: {', '.join(target_codes)}\n\n"
        f"{SCHEMA_HINT}\n\n--- ORDINANCE TEXT ---\n{text[:120000]}"
    )
    msg = api.messages.create(
        model=config.MODEL,
        max_tokens=8000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1].lstrip("json").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # fail loud, never fabricate
        raise RuntimeError(f"LLM returned non-JSON for {jurisdiction}: {raw[:300]}")
    return data if isinstance(data, list) else [data]
