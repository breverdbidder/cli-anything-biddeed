"""Title search and lien analysis for auction cases.

Data source: AcclaimWeb (vaclmweb1.brevardclerk.us)
"""

from typing import Optional


def search_liens(case_number: str) -> list[dict]:
    """Search for liens associated with a case.

    In production, scrapes AcclaimWeb by party name.
    Returns sample data for demonstration.
    """
    return [
        {"type": "mortgage", "amount": 198000, "position": 1, "holder": "Bank of America",
         "recorded": "2019-03-15", "doc_type": "MTG"},
        {"type": "hoa_lien", "amount": 5200, "position": 2, "holder": "Sunset HOA",
         "recorded": "2023-08-01", "doc_type": "LIEN"},
    ]


def get_lien_priority(liens: list[dict]) -> list[dict]:
    """Sort liens by priority position."""
    return sorted(liens, key=lambda x: x.get("position", 999))


def detect_senior_mortgage(liens: list[dict], plaintiff: str) -> dict:
    """Detect if foreclosure is by junior lienholder (HOA, 2nd mortgage).

    If plaintiff is NOT the first-position mortgage holder, the senior
    mortgage survives the foreclosure sale — critical risk factor.
    """
    if not liens:
        return {"senior_survives": False, "risk": "unknown", "message": "No liens found"}

    first_position = next((l for l in liens if l.get("position") == 1), None)
    if not first_position:
        return {"senior_survives": False, "risk": "low", "message": "No first-position lien found"}

    # Check if plaintiff matches first-position holder
    plaintiff_lower = plaintiff.lower()
    holder_lower = first_position.get("holder", "").lower()

    if plaintiff_lower in holder_lower or holder_lower in plaintiff_lower:
        return {
            "senior_survives": False,
            "risk": "low",
            "message": f"Plaintiff ({plaintiff}) IS the first-position holder",
        }
    else:
        return {
            "senior_survives": True,
            "risk": "high",
            "senior_amount": first_position.get("amount", 0),
            "senior_holder": first_position.get("holder", ""),
            "message": f"WARNING: Senior mortgage ({first_position.get('holder')}, ${first_position.get('amount', 0):,}) survives foreclosure",
        }
