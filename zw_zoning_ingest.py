#!/usr/bin/env python3
"""
zw_zoning_ingest.py — FL 67-county parcel-level zoning ingest engine.
BidDeed.AI / ZoneWise.AI.  SSOT Supabase project: mocerqjnksmhcjzxrewo.

HONESTY V3: REGENERATED from project checkpoint after the original
(sha 7c8b43eb...) was lost to a container reset. Status = UNTESTED against
live ArcGIS + DB. Validate with --inspect / --discover before --batch.
Known risk: per-parcel point-in-polygon over fl_parcels (10.5M rows) is
heavy; tune indexes / restrict to auction parcels before full-county runs.

Modes:
  --inspect  CO_NO   county config + endpoint reachability + row counts
  --discover CO_NO   probe county zoning endpoint metadata (fields, count)
  --ingest   CO_NO   zoning polygons -> zw_zoning_src; parcels -> zw_zoning
  --resolve  CO_NO   auctions -> zw_zoning cascade -> mca_zoning
  --coverage CO_NO   % auction cards carrying zoning (GOLD GATE = 95%)
  --batch    KEY     ingest+resolve+coverage for every county in batch KEY

Env:  SUPABASE_DB_URL  (postgres conn string; secret by name only)
Deps: psycopg2-binary requests pyyaml
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests
import psycopg2
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "fl_counties_manifest.yml")
HTTP_TIMEOUT = 60
RETRY = 3
LABEL = "[zw_zoning_ingest]"


def log(level, msg):
    print(f"{LABEL} {level} {datetime.now(timezone.utc).isoformat()} {msg}", flush=True)


def db():
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        log("ERROR", "SUPABASE_DB_URL not set")
        sys.exit(2)
    conn = psycopg2.connect(url)
    conn.autocommit = False
    return conn


def load_manifest():
    with open(MANIFEST) as f:
        return yaml.safe_load(f)


def county_cfg(man, co_no):
    co_no = int(co_no)
    raw = man["counties"].get(co_no)
    name, slug = (raw[0], raw[1]) if isinstance(raw, list) else (None, None)
    return {
        "co_no": co_no,
        "name": name,
        "slug": slug,
        "zoning": man.get("zoning_endpoints", {}).get(co_no),
    }


def arcgis_get(url, params):
    p = {"f": "json"}
    p.update(params)
    last = None
    for attempt in range(1, RETRY + 1):
        try:
            r = requests.get(url, params=p, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            j = r.json()
            if "error" in j:
                raise RuntimeError(j["error"])
            return j
        except Exception as e:  # noqa: BLE001
            last = e
            log("WARN", f"arcgis {attempt}/{RETRY} {url} :: {e}")
            time.sleep(2 * attempt)
    raise RuntimeError(f"arcgis failed after {RETRY}: {last}")


def arcgis_query_geojson(url, where, mrc, out_sr=4326):
    offset, feats = 0, []
    while True:
        r = requests.get(
            url + "/query",
            params={
                "where": where, "outFields": "*", "returnGeometry": "true",
                "outSR": out_sr, "resultOffset": offset,
                "resultRecordCount": mrc, "f": "geojson",
            },
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        batch = (r.json() or {}).get("features", [])
        feats.extend(batch)
        if len(batch) < mrc:
            break
        offset += mrc
        log("INFO", f"  paged {len(feats)} features...")
    return feats


def mark_manual_queue(conn, cfg, reason):
    cur = conn.cursor()
    cur.execute(
        "UPDATE public.fl_county_xref SET zoning_status='manual_queue', updated_at=now() WHERE co_no=%s",
        (cfg["co_no"],),
    )
    conn.commit()
    log("WARN", f"manual_queue co_no={cfg['co_no']} ({cfg['name']}): {reason}")


def ingest_zoning(conn, cfg):
    z = cfg.get("zoning")
    if not z or not z.get("url"):
        mark_manual_queue(conn, cfg, "no zoning endpoint resolved")
        return 0
    field = z["field"]
    mrc = int(z.get("max_record_count", 2000))
    feats = arcgis_query_geojson(z["url"], "1=1", mrc)
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM public.zw_zoning_src WHERE co_no=%s AND source_url=%s",
        (cfg["co_no"], z["url"]),
    )
    rows = 0
    for ft in feats:
        geom = ft.get("geometry")
        if not geom:
            continue
        props = ft.get("properties") or {}

        def pick(*names):
            for n in names:
                for k in (n, n.upper(), n.lower()):
                    if k in props and props[k] not in (None, ""):
                        return props[k]
            return None

        cur.execute(
            """
            INSERT INTO public.zw_zoning_src
              (co_no, jurisdiction, zone_code, zone_desc, overlay, geom,
               source_url, source_layer, ingested_at)
            VALUES (%s,%s,%s,%s,%s, ST_SetSRID(ST_GeomFromGeoJSON(%s),4326), %s,%s, now())
            """,
            (
                cfg["co_no"], z.get("scope", "unincorporated"),
                pick(field), pick("zone_desc", "ZONE_DESC", "short_desc"),
                pick("ovly", "overlay", "OVLY"),
                json.dumps(geom), z["url"], z.get("layer_name"),
            ),
        )
        rows += 1
    conn.commit()
    log("INFO", f"zw_zoning_src +{rows} ({cfg['name']})")
    return rows


def ingest_parcels(conn, cfg):
    cur = conn.cursor()
    src_url = (cfg.get("zoning") or {}).get("url")
    cur.execute(
        """
        INSERT INTO public.zw_zoning
          (co_no, pin_clean, pin, county, site_addr, site_addr_clean, geom,
           zoning_code, zoning_desc, zoning_jurisdiction, flu_code,
           match_method, confidence, source_url, status, updated_at)
        SELECT
          p.co_no,
          public.fn_pin_clean(p.parcel_id),
          p.parcel_id,
          x.realauction_slug,
          NULLIF(TRIM(CONCAT_WS(' ', p.phy_addr1, p.phy_addr2, p.phy_city, p.phy_zipcd)), ''),
          public.fn_addr_clean(CONCAT_WS(' ', p.phy_addr1, p.phy_addr2, p.phy_city, p.phy_zipcd)),
          CASE WHEN p.centroid_lat IS NOT NULL AND p.centroid_lng IS NOT NULL
               THEN ST_SetSRID(ST_MakePoint(p.centroid_lng, p.centroid_lat), 4326) END,
          COALESCE(zs.zone_code, p.zone_code),
          zs.zone_desc,
          zs.jurisdiction,
          p.future_land_use,
          CASE WHEN zs.zone_code IS NOT NULL THEN 'point_in_polygon'
               WHEN p.zone_code  IS NOT NULL THEN 'fl_parcels_zone'
               ELSE 'none' END,
          CASE WHEN zs.zone_code IS NOT NULL THEN 0.6
               WHEN p.zone_code  IS NOT NULL THEN 0.5
               ELSE 0 END,
          %s, 'active', now()
        FROM public.fl_parcels p
        LEFT JOIN public.fl_county_xref x ON x.co_no = p.co_no
        LEFT JOIN LATERAL (
          SELECT s.zone_code, s.zone_desc, s.jurisdiction
          FROM public.zw_zoning_src s
          WHERE s.co_no = p.co_no
            AND p.centroid_lat IS NOT NULL AND p.centroid_lng IS NOT NULL
            AND ST_Contains(s.geom, ST_SetSRID(ST_MakePoint(p.centroid_lng, p.centroid_lat), 4326))
          LIMIT 1
        ) zs ON TRUE
        WHERE p.co_no = %s
        ON CONFLICT (co_no, pin_clean) DO UPDATE SET
          site_addr=excluded.site_addr, site_addr_clean=excluded.site_addr_clean,
          geom=excluded.geom, zoning_code=excluded.zoning_code, zoning_desc=excluded.zoning_desc,
          zoning_jurisdiction=excluded.zoning_jurisdiction, flu_code=excluded.flu_code,
          match_method=excluded.match_method, confidence=excluded.confidence, updated_at=now()
        """,
        (src_url, cfg["co_no"]),
    )
    n = cur.rowcount
    conn.commit()
    log("INFO", f"zw_zoning upsert {n} ({cfg['name']})")
    return n


def resolve_auctions(conn, cfg):
    if not cfg["slug"]:
        log("WARN", f"no slug for co_no={cfg['co_no']}; skip resolve")
        return 0
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO public.mca_zoning
          (auction_id, co_no, pin_clean, zoning_code, zoning_desc, zoning_category,
           zoning_jurisdiction, flu_code, match_method, confidence, resolved_at)
        SELECT a.id, %(co)s, z.pin_clean, z.zoning_code, z.zoning_desc, z.zoning_category,
               z.zoning_jurisdiction, z.flu_code, z.method, z.conf, now()
        FROM public.multi_county_auctions a
        CROSS JOIN LATERAL (
          SELECT * FROM (
            SELECT z1.*, 'parcel_id'::text AS method, 1.0::numeric AS conf
            FROM public.zw_zoning z1
            WHERE z1.co_no=%(co)s AND a.parcel_id IS NOT NULL
              AND z1.pin_clean = public.fn_pin_clean(a.parcel_id)
            UNION ALL
            SELECT z2.*, 'situs_address', 0.8
            FROM public.zw_zoning z2
            WHERE z2.co_no=%(co)s AND a.property_address IS NOT NULL
              AND z2.site_addr_clean = public.fn_addr_clean(a.property_address)
            UNION ALL
            SELECT z3.*, 'point_in_polygon', 0.6
            FROM public.zw_zoning z3
            WHERE z3.co_no=%(co)s AND a.latitude IS NOT NULL AND a.longitude IS NOT NULL
              AND z3.geom IS NOT NULL
              AND ST_DWithin(z3.geom, ST_SetSRID(ST_MakePoint(a.longitude, a.latitude),4326), 0.0005)
            ORDER BY conf DESC
            LIMIT 1
          ) best
        ) z
        WHERE a.county = %(slug)s
        ON CONFLICT (auction_id) DO UPDATE SET
          pin_clean=excluded.pin_clean, zoning_code=excluded.zoning_code,
          zoning_desc=excluded.zoning_desc, zoning_category=excluded.zoning_category,
          match_method=excluded.match_method, confidence=excluded.confidence, resolved_at=now()
        """,
        {"co": cfg["co_no"], "slug": cfg["slug"]},
    )
    n = cur.rowcount
    conn.commit()
    log("INFO", f"mca_zoning upsert {n} ({cfg['slug']})")
    return n


def coverage(conn, cfg):
    if not cfg["slug"]:
        return {"slug": None, "total": 0, "matched": 0, "pct": 0.0, "gold": False}
    cur = conn.cursor()
    cur.execute(
        """
        SELECT count(*) AS total,
               count(*) FILTER (WHERE coalesce(mz.match_method,'none') <> 'none') AS matched
        FROM public.multi_county_auctions a
        LEFT JOIN public.mca_zoning mz ON mz.auction_id = a.id
        WHERE a.county = %s
        """,
        (cfg["slug"],),
    )
    total, matched = cur.fetchone()
    pct = round(100.0 * matched / total, 1) if total else 0.0
    res = {"slug": cfg["slug"], "total": total, "matched": matched, "pct": pct, "gold": pct >= 95.0}
    log("INFO", f"COVERAGE {res}")
    return res


def inspect(conn, cfg):
    z = cfg.get("zoning")
    out = {"co_no": cfg["co_no"], "name": cfg["name"], "slug": cfg["slug"],
           "zoning_endpoint": (z or {}).get("url"), "reachable": None}
    if z and z.get("url"):
        try:
            meta = arcgis_get(z["url"], {})
            out["reachable"] = True
            out["layer_name"] = meta.get("name")
            out["fields"] = [f["name"] for f in meta.get("fields", [])]
            out["field_present"] = z["field"] in out["fields"]
        except Exception as e:  # noqa: BLE001
            out["reachable"] = False
            out["error"] = str(e)
    print(json.dumps(out, indent=2))
    return out


def run_county(conn, cfg):
    log("INFO", f"=== co_no={cfg['co_no']} {cfg['name']} slug={cfg['slug']} ===")
    ingest_zoning(conn, cfg)
    ingest_parcels(conn, cfg)
    resolve_auctions(conn, cfg)
    return coverage(conn, cfg)


def main():
    ap = argparse.ArgumentParser(description="FL 67-county zoning ingest")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--inspect", metavar="CO_NO")
    g.add_argument("--discover", metavar="CO_NO")
    g.add_argument("--ingest", metavar="CO_NO")
    g.add_argument("--resolve", metavar="CO_NO")
    g.add_argument("--coverage", metavar="CO_NO")
    g.add_argument("--batch", metavar="KEY")
    args = ap.parse_args()

    man = load_manifest()
    conn = db()
    try:
        if args.batch:
            co_list = man["batches"][args.batch]
            summary = [run_county(conn, county_cfg(man, c)) for c in co_list]
            print(json.dumps({"batch": args.batch, "counties": summary}, indent=2))
        elif args.inspect:
            inspect(conn, county_cfg(man, args.inspect))
        elif args.discover:
            inspect(conn, county_cfg(man, args.discover))
        elif args.ingest:
            cfg = county_cfg(man, args.ingest)
            ingest_zoning(conn, cfg)
            ingest_parcels(conn, cfg)
        elif args.resolve:
            resolve_auctions(conn, county_cfg(man, args.resolve))
        elif args.coverage:
            print(json.dumps(coverage(conn, county_cfg(man, args.coverage)), indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
