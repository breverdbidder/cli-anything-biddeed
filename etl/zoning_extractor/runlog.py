"""
Self-verifying run log. Writes one summary row per run to public.zoning_extract_runs
so the outcome (render size, codes extracted, errors) is observable in Supabase —
no need to read GitHub Actions logs. Failures here never sink the run.
"""
import os


def github_run_url() -> str | None:
    s = os.environ.get("GITHUB_SERVER_URL")
    r = os.environ.get("GITHUB_REPOSITORY")
    i = os.environ.get("GITHUB_RUN_ID")
    return f"{s}/{r}/actions/runs/{i}" if (s and r and i) else None


def write(db, county: str, jurisdiction: str | None, mode: str,
          grand: dict, details: list[dict]) -> None:
    if grand.get("errors", 0) and grand.get("jurisdictions", 0) == 0:
        status = "failed"
    elif grand.get("errors", 0):
        status = "partial"
    else:
        status = "ok"
    row = {
        "county": county,
        "jurisdiction": jurisdiction,
        "mode": mode,
        "jurisdictions_processed": grand.get("jurisdictions", 0),
        "codes_extracted": grand.get("codes", 0),
        "staged": grand.get("staged", 0),
        "errors": grand.get("errors", 0),
        "status": status,
        "details": details,
        "github_run_url": github_run_url(),
    }
    try:
        db.table("zoning_extract_runs").insert(row).execute()
        print(f"[runlog] wrote run row: {mode} {county} status={status}")
    except Exception as e:
        print(f"[runlog] failed to write run log (non-fatal): {e}")
