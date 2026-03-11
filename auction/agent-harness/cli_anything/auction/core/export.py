"""Export utilities for Auction CLI. Same pattern as ZoneWise."""

import csv
import json
from pathlib import Path
from typing import Optional


def to_json(data, output_path: str) -> dict:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))
    return {"format": "json", "path": str(path), "size_bytes": path.stat().st_size}


def to_csv(data: list[dict], output_path: str) -> dict:
    if not data:
        return {"format": "csv", "path": output_path, "records": 0}
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(data[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            flat = {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in row.items()}
            writer.writerow(flat)
    return {"format": "csv", "path": str(path), "records": len(data), "size_bytes": path.stat().st_size}


def to_supabase(data: list[dict], table: str = "auction_analysis") -> dict:
    try:
        from cli_anything_shared.supabase import upsert_rows
        count = upsert_rows(table, data, cli_name="auction")
        return {"format": "supabase", "table": table, "records_upserted": count}
    except Exception as e:
        return {"format": "supabase", "error": str(e)}
