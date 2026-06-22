#!/usr/bin/env python3
"""
fl_parcel_centroids_all.py
Harvest centroids for ALL 67 FL counties from the FL Statewide Cadastral ArcGIS API.
Writes directly to fl_parcels.centroid_lat / centroid_lng via fl_parcel_centroid_upsert RPC.
Tracks progress per county in fl_parcel_centroid_progress.
OBJECTID keyset pagination — safe to restart, resumes from last_objectid stored in progress.
"""
import os, json, time, urllib.request, urllib.parse, sys

BASE = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest"
    "/services/Florida_Statewide_Cadastral/FeatureServer/0/query"
)
SB  = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
assert KEY, "SUPABASE_SERVICE_KEY required"

PAGE      = int(os.environ.get("PAGE_SIZE",  "2000"))
RPC_BATCH = int(os.environ.get("RPC_BATCH",  "2000"))
MAX_PAGES = int(os.environ.get("MAX_PAGES",  "300"))   # 300 pages x 2000 = 600K/run
TARGET_CO = int(os.environ.get("CO_NO",      "0"))     # 0 = auto-pick

HEADERS = {
    "apikey":        KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type":  "application/json",
}

# ── helpers ────────────────────────────────────────────────────────────────────

def get(url, tries=8):
    last_exc = RuntimeError("get() failed after all retries")
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "everest-fl-centroids/2"})
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
                try:
                    return json.loads(raw.decode("utf-8", "replace"))
                except json.JSONDecodeError:
                    # Truncated response — halve page size and retry
                    for size in ["resultRecordCount=2000", "resultRecordCount=1000"]:
                        if size in url:
                            smaller = str(int(size.split("=")[1]) // 2)
                            url = url.replace(size, f"resultRecordCount={smaller}")
                            break
                    last_exc = RuntimeError(f"JSON truncated at retry {i}")
                    time.sleep(5)
                    continue
        except Exception as e:
            last_exc = e
            time.sleep(4 * (i + 1))
    raise last_exc

def sb_get(path, params=""):
    url = f"{SB}/rest/v1/{path}{'?' + params if params else ''}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def sb_patch(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{SB}/rest/v1/{path}", data=data, method="PATCH")
    for k, v in HEADERS.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()

def rpc(fn, body, tries=5):
    data = json.dumps(body).encode()
    last_exc = RuntimeError("rpc() failed after all retries")
    for i in range(tries):
        try:
            req = urllib.request.Request(f"{SB}/rest/v1/rpc/{fn}", data=data, method="POST")
            for k, v in HEADERS.items():
                req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read().decode()
        except Exception as e:
            last_exc = e
            time.sleep(3 * (i + 1))
    raise last_exc

# ── county selection ────────────────────────────────────────────────────────────

def pick_county():
    if TARGET_CO > 0:
        return TARGET_CO
    rows = sb_get(
        "fl_parcel_centroid_progress",
        "status=eq.pending&centroids_needed=gt.0&order=centroids_needed.desc&limit=1"
    )
    if not rows:
        print("All counties done or none pending.")
        sys.exit(0)
    return rows[0]["co_no"]

def get_last_oid(co_no):
    rows = sb_get(
        "fl_parcel_centroid_progress",
        f"co_no=eq.{co_no}&select=last_parcel_id"
    )
    val = rows[0]["last_parcel_id"] if rows else None
    try:
        return int(val) if val else 0
    except (TypeError, ValueError):
        return 0

# ── main ───────────────────────────────────────────────────────────────────────

def main():
    co_no = pick_county()
    print(f"Processing co_no={co_no}", flush=True)

    # Mark running
    sb_patch(
        f"fl_parcel_centroid_progress?co_no=eq.{co_no}",
        {"status": "running",
         "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    )

    last_oid = get_last_oid(co_no)
    print(f"Resuming from OBJECTID>{last_oid}", flush=True)

    total = 0
    pages = 0

    while pages < MAX_PAGES:
        params = urllib.parse.urlencode({
            "where":             f"CO_NO={co_no} AND OBJECTID>{last_oid}",
            "outFields":         "PARCEL_ID,ALT_KEY,OBJECTID",
            "returnCentroid":    "true",
            "returnGeometry":    "true",
            "outSR":             "4326",
            "f":                 "json",
            "resultRecordCount": PAGE,
            "orderByFields":     "OBJECTID",
        })
        # Retry ArcGIS 400 "Invalid query parameters" — transient service errors
        arcgis_tries = 5
        data = None
        for arc_attempt in range(arcgis_tries):
            data = get(f"{BASE}?{params}")
            if data.get("error") and data["error"].get("code") == 400:
                wait = 30 * (arc_attempt + 1)
                print(f"ArcGIS 400 at OBJECTID>{last_oid}, retry {arc_attempt+1}/{arcgis_tries} in {wait}s", flush=True)
                time.sleep(wait)
                continue
            break
        if data.get("error"):
            raise RuntimeError(f"ArcGIS error: {data['error']}")
        feats = data.get("features") or []

        if not feats:
            print(f"No more features for co_no={co_no}. Marking done.", flush=True)
            sb_patch(
                f"fl_parcel_centroid_progress?co_no=eq.{co_no}",
                {"status": "done",
                 "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "updated_at":   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            )
            break

        rows = []
        max_oid = last_oid
        for ft in feats:
            attrs = ft.get("attributes") or {}
            centroid = ft.get("centroid") or {}
            oid = attrs.get("OBJECTID")
            alt_key = attrs.get("PARCEL_ID") or attrs.get("ALT_KEY")
            if oid is not None and oid > max_oid:
                max_oid = oid
            if alt_key and centroid.get("x") is not None and centroid.get("y") is not None:
                rows.append({
                    "alt_key": str(alt_key).strip(),
                    "lat":     centroid["y"],
                    "lon":     centroid["x"],
                })

        # Upsert in batches
        written = 0
        for i in range(0, len(rows), RPC_BATCH):
            result = rpc("fl_parcel_centroid_upsert", {
                "p":        rows[i:i + RPC_BATCH],
                "co_no_in": co_no,
            })
            written += int(result.strip() or 0)
            time.sleep(0.4)

        total += written
        pages += 1
        last_oid = max_oid

        # Checkpoint progress every 10 pages
        if pages % 10 == 0:
            sb_patch(
                f"fl_parcel_centroid_progress?co_no=eq.{co_no}",
                {"last_parcel_id": str(last_oid),
                 "updated_at":     time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            )

        print(
            f"page={pages} last_oid={last_oid} "
            f"feats={len(feats)} written={written} total={total}",
            flush=True
        )
        time.sleep(0.3)

    # Save last OBJECTID and reset to pending so next cron resumes
    sb_patch(
        f"fl_parcel_centroid_progress?co_no=eq.{co_no}",
        {"last_parcel_id": str(last_oid),
         "status":         "pending",
         "updated_at":     time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    )

    print(f"Run complete: co_no={co_no} pages={pages} total_written={total}", flush=True)

    # Write GH output for summary
    gh_out = os.environ.get("GITHUB_OUTPUT", "")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"co_no={co_no}\n")
            f.write(f"total_written={total}\n")
            f.write(f"last_oid={last_oid}\n")
            f.write(f"pages={pages}\n")

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"FATAL: {e}", flush=True)
        # Best-effort reset to pending so next cron retries this county
        try:
            co_env = int(os.environ.get("CO_NO", "0"))
            if co_env > 0:
                sb_patch(
                    f"fl_parcel_centroid_progress?co_no=eq.{co_env}&status=eq.running",
                    {"status": "pending",
                     "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
                )
        except Exception:
            pass
        sys.exit(1)
