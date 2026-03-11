"""Parser Agent — Extract swimmer data from USA Swimming psych sheet PDFs.

Agent #139.1 in the BidDeed AI Army.
Handles: PDF text extraction, event detection, swimmer row parsing, time normalization.
"""

import re
import json
from typing import Optional
from dataclasses import dataclass, field, asdict


@dataclass
class SwimmerEntry:
    seed_rank: int
    name: str
    age: int
    team: str
    seed_time: float  # in seconds
    seed_display: str  # original display format
    qualifier: str  # SRCH, B, L, etc.
    course: str = "SCY"  # SCY, LCM

    def to_dict(self):
        return asdict(self)


@dataclass
class EventCuts:
    u14: Optional[float] = None
    age_15_16: Optional[float] = None
    age_17_18: Optional[float] = None
    o19: Optional[float] = None


@dataclass
class SwimEvent:
    number: int
    name: str
    gender: str  # M, W, X
    distance: int
    stroke: str
    cuts: EventCuts = field(default_factory=EventCuts)
    entries: list = field(default_factory=list)

    def to_dict(self):
        return {
            "number": self.number,
            "name": self.name,
            "gender": self.gender,
            "distance": self.distance,
            "stroke": self.stroke,
            "cuts": asdict(self.cuts),
            "entries": [e.to_dict() for e in self.entries],
        }


@dataclass
class MeetInfo:
    name: str = ""
    dates: str = ""
    venue: str = ""


def parse_time_to_seconds(time_str: str) -> float:
    """Convert swim time string to seconds. Handles MM:SS.ss and SS.ss formats."""
    time_str = time_str.strip().rstrip("LY$ ")
    if ":" in time_str:
        parts = time_str.split(":")
        return float(parts[0]) * 60 + float(parts[1])
    return float(time_str)


def detect_course(time_str: str, qualifier: str) -> str:
    """Detect if time is SCY, LCM, or converted."""
    if "L" in qualifier or time_str.endswith("L"):
        return "LCM"
    return "SCY"


def detect_qualifier(tail: str) -> str:
    """Extract qualifier from the tail of a psych sheet line."""
    tail = tail.strip()
    if "SRCH" in tail:
        return "SRCH"
    if tail.endswith("B"):
        return "B"
    return ""


EVENT_PATTERN = re.compile(
    r"Event\s+(\d+)\s+(Women|Men|Mixed)\s+(\d+)\s+Yard\s+(.+?)(?:\s+Relay)?$",
    re.IGNORECASE,
)

CUT_PATTERN = re.compile(
    r"([\d:]+\.\d+)\s+(14&U|15-16|17-18|19&O)\s+SRCH"
)

# Swimmer line: rank name age team time qualifier
SWIMMER_PATTERN = re.compile(
    r"(\d+)\s+([A-Za-z\-\'\s,]+?)\s+(\d{2})\s+([A-Z0-9\-]+FL)\s+([\d:]+\.\d+[LY]?)\s*(.*)"
)


def parse_psych_sheet_text(text: str) -> dict:
    """Parse raw text extracted from a psych sheet PDF.

    Returns structured dict with meet info and events.
    """
    meet = MeetInfo()
    events = []
    current_event = None

    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detect meet name
        if "Championship" in line and not meet.name:
            meet.name = line.strip()

        # Detect event header
        event_match = EVENT_PATTERN.search(line)
        if event_match:
            num = int(event_match.group(1))
            gender = event_match.group(2)[0]  # M, W, X
            distance = int(event_match.group(3))
            stroke = event_match.group(4).strip()

            current_event = SwimEvent(
                number=num,
                name=f"{event_match.group(2)} {distance} Yard {stroke}",
                gender=gender,
                distance=distance,
                stroke=stroke,
            )
            events.append(current_event)
            continue

        # Detect cuts
        if current_event:
            cut_match = CUT_PATTERN.search(line)
            if cut_match:
                cut_time = parse_time_to_seconds(cut_match.group(1))
                age_group = cut_match.group(2)
                if age_group == "14&U":
                    current_event.cuts.u14 = cut_time
                elif age_group == "15-16":
                    current_event.cuts.age_15_16 = cut_time
                elif age_group == "17-18":
                    current_event.cuts.age_17_18 = cut_time
                elif age_group == "19&O":
                    current_event.cuts.o19 = cut_time
                continue

        # Detect swimmer entry
        if current_event:
            swimmer_match = SWIMMER_PATTERN.match(line)
            if swimmer_match:
                rank = int(swimmer_match.group(1))
                name = swimmer_match.group(2).strip().rstrip(",")
                age = int(swimmer_match.group(3))
                team = swimmer_match.group(4).strip()
                time_str = swimmer_match.group(5).strip()
                tail = swimmer_match.group(6).strip()

                qualifier = detect_qualifier(tail + " " + time_str)
                course = detect_course(time_str, qualifier + tail)

                try:
                    seed_seconds = parse_time_to_seconds(time_str)
                except ValueError:
                    continue

                entry = SwimmerEntry(
                    seed_rank=rank,
                    name=name,
                    age=age,
                    team=team,
                    seed_time=seed_seconds,
                    seed_display=time_str,
                    qualifier=qualifier if qualifier else "SRCH",
                    course=course,
                )
                current_event.entries.append(entry)

    return {
        "meet": asdict(meet),
        "events": [e.to_dict() for e in events],
        "stats": {
            "total_events": len(events),
            "total_entries": sum(len(e.entries) for e in events),
        },
    }


def parse_pdf(pdf_path: str) -> dict:
    """Parse a psych sheet PDF file. Returns structured JSON."""
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError(
            "pdfplumber required: pip install pdfplumber --break-system-packages"
        )

    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    full_text = "\n".join(text_parts)
    return parse_psych_sheet_text(full_text)


def save_parsed(data: dict, output_path: str) -> str:
    """Save parsed data to JSON file."""
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return output_path
