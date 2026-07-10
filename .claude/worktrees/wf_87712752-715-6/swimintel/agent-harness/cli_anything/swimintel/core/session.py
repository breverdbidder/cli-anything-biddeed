"""Session Agent — State management for SwimIntel CLI.

Agent #139.4 support module.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Session:
    """Maintains state between CLI commands."""
    parsed_data: Optional[dict] = None
    analysis: Optional[dict] = None
    swimmer_name: Optional[str] = None
    age_group: str = "15-16"
    pdf_path: Optional[str] = None
    output_dir: str = "."

    def save(self, path: str = ".swimintel_session.json"):
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2, default=str)

    @classmethod
    def load(cls, path: str = ".swimintel_session.json") -> "Session":
        if not os.path.exists(path):
            return cls()
        with open(path) as f:
            data = json.load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @property
    def has_data(self) -> bool:
        return self.parsed_data is not None

    @property
    def has_analysis(self) -> bool:
        return self.analysis is not None

    def status(self) -> dict:
        return {
            "pdf_loaded": self.pdf_path or "None",
            "events_parsed": len(self.parsed_data.get("events", [])) if self.parsed_data else 0,
            "swimmer": self.swimmer_name or "None",
            "age_group": self.age_group,
            "analysis_ready": self.has_analysis,
        }
