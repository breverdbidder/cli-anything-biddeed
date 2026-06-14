"""
Validation / anomaly flags. Out-of-range or contradictory values are not dropped —
they are demoted to confidence='low' with a note so the human gate sees them.
Also enforces the site-specific rule mechanically, independent of the model.
"""
import config


def validate_row(row: dict) -> dict:
    notes = [row.get("notes")] if row.get("notes") else []

    # Mechanical enforcement of the PUD/site-specific rule (belt-and-suspenders vs the LLM).
    code = (row.get("zoning_code") or "")
    if config.SITE_SPECIFIC_RE.search(code):
        row["is_site_specific"] = True
        if row.get("max_density_num") is not None:
            notes.append("density nulled: site-specific district has no fixed table density")
            row["max_density_num"] = None
        if not row.get("density_basis"):
            row["density_basis"] = "site_development_order"

    # Range plausibility.
    for field, (lo, hi) in config.RANGES.items():
        v = row.get(field)
        if v is None:
            continue
        try:
            if not (lo <= float(v) <= hi):
                row["confidence"] = "low"
                notes.append(f"{field}={v} outside plausible [{lo},{hi}]")
        except (TypeError, ValueError):
            row["confidence"] = "low"
            notes.append(f"{field} non-numeric: {v!r}")
            row[field] = None

    # A populated standard with no citation cannot be high confidence.
    has_value = any(row.get(f) is not None for f in
                    ("max_density_num", "far", "parking_per_1000", "max_height_ft", "min_lot_size"))
    if has_value and not row.get("source_section") and row.get("confidence") != "low":
        row["confidence"] = "low"
        notes.append("value present without source_section citation")

    row["notes"] = "; ".join(n for n in notes if n) or None
    return row
