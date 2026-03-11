"""Export utilities for ZoneWise CLI.

Supports JSON, CSV, and Supabase output formats.
"""

import csv
import json
from pathlib import Path
from typing import Optional


def to_json(data: list[dict], output_path: str) -> dict:
    """Export records to JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))
    return {"format": "json", "path": str(path), "records": len(data), "size_bytes": path.stat().st_size}


def to_csv(data: list[dict], output_path: str) -> dict:
    """Export records to CSV file."""
    if not data:
        return {"format": "csv", "path": output_path, "records": 0, "error": "No data to export"}

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(data[0].keys())

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            # Flatten nested dicts for CSV
            flat = {}
            for k, v in row.items():
                if isinstance(v, (dict, list)):
                    flat[k] = json.dumps(v)
                else:
                    flat[k] = v
            writer.writerow(flat)

    return {"format": "csv", "path": str(path), "records": len(data), "size_bytes": path.stat().st_size}


def to_supabase(data: list[dict], table: str = "zoning_records", county: Optional[str] = None) -> dict:
    """Upsert records to Supabase table."""
    try:
        from cli_anything_shared.supabase import upsert_rows
        if county:
            for row in data:
                row["county"] = county
        count = upsert_rows(table, data, cli_name="zonewise")
        return {"format": "supabase", "table": table, "records_upserted": count}
    except Exception as e:
        return {"format": "supabase", "error": str(e)}
