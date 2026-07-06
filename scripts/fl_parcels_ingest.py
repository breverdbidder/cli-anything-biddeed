#!/usr/bin/env python3
"""FL statewide cadastral -> fl_parcels_stage bulk ingest worker.

Method: OBJECTID keyset windows of 2000 over the FGIO floor layer (dense ids
1..N verified 2026-07-06). CO_NO where-clauses are broken server-side on this
layer; CO_NO is tagged client-side from the payload. co_no scheme = LEGACY DOR
(Duval=26, Dixie=25, Miami-Dade=23) - matches production fl_parcels (verified).

Fail-closed: every fetched feature must be accounted (staged_new + updated +
dupes_logged + null_pid) by the fl_stage_upsert_batch RPC or the range fails.
Idempotent + resumable via fl_ingest_ranges ledger. Stdlib only.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse

FLOOR = ("https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
         "Florida_Statewide_Cadastral/FeatureServer/0/query")
WINDOW = 2000
SUB_BATCH = 500
MAX_RETRIES = 5
RETRY_CODES = {408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
OID_START = int(os.environ.get("OID_START", "0"))
OID_END = int(os.environ.get("OID_END", "0"))
LANE = os.environ.get("LANE", "lane-0")
AUTO_CONTINUE = os.environ.get("AUTO_CONTINUE", "false").lower() == "true"
MAX_MINUTES = float(os.environ.get("MAX_MINUTES", "320"))
REPO = os.environ.get("GH_REPO", "breverdbidder/cli-anything-biddeed")

T0 = time.time()


def die(msg, code=1):
    print(f"FATAL: {msg}", flush=True)
    sys.exit(code)


def http(method, url, headers=None, body=None, timeout=90):
    last = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, data=body, method=method,
                                         headers=headers or {})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read()[:200]!r}"
            if e.code in RETRY_CODES:
                time.sleep(5 * (attempt + 1))
                continue
            break
        except Exception as e:  # timeouts, resets
            last = repr(e)
            time.sleep(5 * (attempt + 1))
    return None, (last or "unknown").encode()


def sb(method, path, payload, prefer=None):
    headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
               "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    status, body = http(method, f"{SB_URL}{path}", headers,
                        json.dumps(payload).encode())
    if status is None or status >= 300:
        die(f"supabase {path} -> {status} {body[:300]!r}")
    return json.loads(body) if body else None


def fetch_window(lo, hi):
    params = urllib.parse.urlencode({
        "where": f"OBJECTID > {lo} AND OBJECTID <= {hi}",
        "outFields": "*", "returnGeometry": "true", "outSR": "4326",
        "f": "geojson"})
    status, body = http("POST", FLOOR,
                        {"Content-Type": "application/x-www-form-urlencoded"},
                        params.encode(), timeout=180)
    if status != 200:
        return None
    try:
        doc = json.loads(body)
        feats = doc.get("features")
        if feats is None or "error" in doc:
            return None
        return feats
    except Exception:
        return None


def upsert(features):
    """Returns accounted count across sub-batches. Fail-closed on mismatch."""
    accounted = 0
    counters = {"staged_new": 0, "staged_updated": 0, "intra_batch_dupes": 0,
                "cross_batch_dupes": 0, "null_pid": 0}
    for i in range(0, len(features), SUB_BATCH):
        chunk = features[i:i + SUB_BATCH]
        rows = []
        for f in chunk:
            props = dict(f.get("properties") or {})
            if "OBJECTID" not in props and f.get("id") is not None:
                props["OBJECTID"] = f["id"]
            rows.append({"attrs": props, "geometry": f.get("geometry")})
        res = sb("POST", "/rest/v1/rpc/fl_stage_upsert_batch",
                 {"p_rows": rows})
        if not isinstance(res, dict) or res.get("received") != len(chunk):
            die(f"rpc mismatch: sent {len(chunk)} got {res}")
        accounted += res["accounted"]
        for k in counters:
            counters[k] += res.get(k, 0)
    return accounted, counters


def record_range(lo, hi, fetched, accounted, counters, status):
    sb("POST", "/rest/v1/fl_ingest_ranges", {
        "oid_start": lo, "oid_end": hi, "fetched": fetched,
        "accounted": accounted, "staged_new": counters["staged_new"],
        "staged_updated": counters["staged_updated"],
        "dupes_logged": counters["intra_batch_dupes"] + counters["cross_batch_dupes"],
        "null_pid": counters["null_pid"], "status": status, "lane": LANE},
        prefer="resolution=merge-duplicates")


def resume_cursor():
    rows = sb("POST", "/rest/v1/rpc/fl_ingest_resume_cursor",
              {"p_start": OID_START, "p_end": OID_END})
    return int(rows) if rows is not None else OID_START


def self_continue(cursor):
    print(f"time budget reached at cursor={cursor}; re-dispatching lane {LANE}",
          flush=True)
    sb("POST", "/rest/v1/rpc/fire_workflow_dispatch", {
        "p_repo": REPO, "p_workflow_file": "fl-parcels-ingest.yml",
        "p_ref": "main", "p_inputs": {
            "oid_start": str(cursor), "oid_end": str(OID_END), "lane": LANE,
            "auto_continue": "true", "max_minutes": str(int(MAX_MINUTES))}})


def main():
    if not SB_URL or not SB_KEY:
        die("SUPABASE_URL / SUPABASE_SERVICE_KEY env missing")
    if OID_END <= OID_START:
        die(f"bad range [{OID_START},{OID_END}]")
    cursor = resume_cursor()
    print(f"lane={LANE} range=({OID_START},{OID_END}] resume cursor={cursor}",
          flush=True)
    totals = {"fetched": 0, "accounted": 0}
    while cursor < OID_END:
        if (time.time() - T0) > MAX_MINUTES * 60:
            if AUTO_CONTINUE:
                self_continue(cursor)
                return
            die(f"time budget exhausted at cursor={cursor}, "
                f"auto_continue=false", 2)
        lo, hi = cursor, min(cursor + WINDOW, OID_END)
        feats = None
        for attempt in range(MAX_RETRIES):
            feats = fetch_window(lo, hi)
            if feats is not None:
                break
            time.sleep(8 * (attempt + 1))
        if feats is None:
            record_range(lo, hi, None, None,
                         dict.fromkeys(["staged_new", "staged_updated",
                                        "intra_batch_dupes",
                                        "cross_batch_dupes", "null_pid"], 0),
                         "failed")
            die(f"fetch failed 3x for ({lo},{hi}]")
        accounted, counters = upsert(feats) if feats else (0, dict.fromkeys(
            ["staged_new", "staged_updated", "intra_batch_dupes",
             "cross_batch_dupes", "null_pid"], 0))
        if accounted != len(feats):
            record_range(lo, hi, len(feats), accounted, counters, "failed")
            die(f"ACCOUNTING MISMATCH ({lo},{hi}]: fetched={len(feats)} "
                f"accounted={accounted}")
        record_range(lo, hi, len(feats), accounted, counters, "done")
        totals["fetched"] += len(feats)
        totals["accounted"] += accounted
        cursor = hi
        time.sleep(0.25)  # <=5 req/s guardrail
    print(f"LANE COMPLETE {LANE}: fetched={totals['fetched']} "
          f"accounted={totals['accounted']} range=({OID_START},{OID_END}]",
          flush=True)


if __name__ == "__main__":
    main()
