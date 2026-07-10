#!/usr/bin/env python3
"""Modal: County Scraper — parallel county data ingestion with concurrency limit 50.
Issue: breverdbidder/cli-anything-biddeed#66
Deployed as: modal deploy modal/scraper.py
Trigger: modal run modal/scraper.py --county 12 (Brevard)
"""

import modal

app = modal.App("everest-county-scraper")

scraper_image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "requests",
    "httpx",
)

secrets = modal.Secret.from_name("everest-secrets")

# FL GIO Statewide Cadastral API
FL_GIO_BASE = "https://services1.arcgis.com/O1JpcwDW8sjYuddV/arcgis/rest/services/Statewide_Parcels/FeatureServer/0/query"
BATCH_SIZE = 2000
MAX_CONCURRENCY = 50  # Modal concurrency limit per issue spec


@app.function(
    image=scraper_image,
    secrets=[secrets],
    timeout=5400,  # 90 min per county ingestion
    max_containers=MAX_CONCURRENCY,
)
def scrape_batch(county: int, offset: int, batch_size: int = BATCH_SIZE) -> dict:
    """Fetch one paginated batch of parcels from FL GIO for a given county."""
    import requests, os

    SB_URL = os.environ["SUPABASE_URL"]
    SB_KEY = os.environ["SUPABASE_KEY"]

    sb_h = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    # FL GIO query
    params = {
        "where": f"CO_NO={county}",
        "outFields": "PARCEL_ID,CO_NO,DOR_UC,JV,TV_SD,ACREAGE,PHY_ADDR1,PHY_CITY,PHY_ZIPCD",
        "returnGeometry": "false",
        "f": "json",
        "resultOffset": offset,
        "resultRecordCount": batch_size,
        "orderByFields": "PARCEL_ID ASC",
    }

    r = requests.get(FL_GIO_BASE, params=params, timeout=60)
    if r.status_code != 200:
        return {"county": county, "offset": offset, "fetched": 0, "upserted": 0,
                "error": f"FL GIO HTTP {r.status_code}"}

    data = r.json()
    features = data.get("features", [])

    if not features:
        return {"county": county, "offset": offset, "fetched": 0, "upserted": 0}

    # Map FL GIO fields → zoning_assignments rows
    rows = []
    for f in features:
        attrs = f.get("attributes", {})
        parcel_id = attrs.get("PARCEL_ID")
        if not parcel_id:
            continue
        rows.append({
            "parcel_id": str(parcel_id),
            "co_no": county,
            "zone_code": str(attrs.get("DOR_UC", "00")),
            "zone_source": "fl_gio",
            "just_value": attrs.get("JV"),
            "total_value": attrs.get("TV_SD"),
            "acreage": attrs.get("ACREAGE"),
            "address": attrs.get("PHY_ADDR1"),
            "city": attrs.get("PHY_CITY"),
            "zip": attrs.get("PHY_ZIPCD"),
        })

    if not rows:
        return {"county": county, "offset": offset, "fetched": len(features), "upserted": 0}

    # Upsert to Supabase
    upsert_r = requests.post(
        f"{SB_URL}/rest/v1/zoning_assignments",
        headers={**sb_h, "Prefer": "resolution=merge-duplicates,return=minimal"},
        json=rows,
    )

    upserted = len(rows) if upsert_r.status_code in (200, 201) else 0
    return {
        "county": county,
        "offset": offset,
        "fetched": len(features),
        "upserted": upserted,
        "error": None if upserted > 0 else f"upsert HTTP {upsert_r.status_code}",
    }


@app.function(
    image=scraper_image,
    secrets=[secrets],
    timeout=7200,  # 2 hr orchestrator
    max_containers=1,
)
def scrape_county(county: int, full: bool = True) -> dict:
    """Orchestrate full county ingestion using parallel batches (concurrency≤50)."""
    import requests, os
    from datetime import datetime, timezone, timedelta

    SB_URL = os.environ["SUPABASE_URL"]
    SB_KEY = os.environ["SUPABASE_KEY"]
    TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

    EST = timezone(timedelta(hours=-5))
    NOW = datetime.now(EST)
    sb_h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}

    # Count total parcels for county
    count_r = requests.get(
        FL_GIO_BASE,
        params={"where": f"CO_NO={county}", "returnCountOnly": "true", "f": "json"},
        timeout=30,
    )
    total = count_r.json().get("count", 0) if count_r.status_code == 200 else 0
    print(f"County {county}: {total:,} parcels to ingest")

    if not full or total == 0:
        return {"county": county, "total": total, "fetched": 0, "upserted": 0}

    # Build batch offsets
    offsets = list(range(0, total, BATCH_SIZE))

    # Dispatch batches in parallel (max MAX_CONCURRENCY at a time)
    total_fetched = 0
    total_upserted = 0
    errors = []

    for chunk_start in range(0, len(offsets), MAX_CONCURRENCY):
        chunk = offsets[chunk_start: chunk_start + MAX_CONCURRENCY]
        results = list(scrape_batch.map(
            [county] * len(chunk),
            chunk,
            [BATCH_SIZE] * len(chunk),
        ))
        for res in results:
            total_fetched += res.get("fetched", 0)
            total_upserted += res.get("upserted", 0)
            if res.get("error"):
                errors.append(res["error"])

    print(f"County {county}: fetched={total_fetched:,} upserted={total_upserted:,} errors={len(errors)}")

    # Log to modal_runs
    requests.post(
        f"{SB_URL}/rest/v1/modal_runs",
        headers={**sb_h, "Prefer": "return=minimal"},
        json={
            "run_type": "county_scraper",
            "status": "completed" if not errors else "partial",
            "county": str(county),
            "parcels_fetched": total_fetched,
            "parcels_upserted": total_upserted,
            "ran_at": NOW.isoformat(),
        },
    )

    # Telegram notify
    msg = f"🗺️ County {county} Scrape Done\nTotal: {total:,} | Fetched: {total_fetched:,} | Upserted: {total_upserted:,}"
    if errors:
        msg += f"\n⚠️ {len(errors)} batch errors"
    if TG_TOKEN and TG_CHAT:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data={"chat_id": TG_CHAT, "text": msg},
        )

    return {"county": county, "total": total, "fetched": total_fetched, "upserted": total_upserted, "errors": len(errors)}


@app.local_entrypoint()
def main(county: int = 12, full: bool = False):
    """Run county scraper locally: modal run modal/scraper.py --county 12"""
    result = scrape_county.remote(county=county, full=full)
    print(f"Scrape result: {result}")
