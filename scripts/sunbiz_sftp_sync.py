#!/usr/bin/env python3
"""
Sunbiz bulk SFTP sync: hydrate/refresh public.sunbiz_entities from Florida
DOS/Division of Corporations' free public SFTP bulk-download service.

Host: sftp.floridados.gov (SFTP, port 22), user "Public". This is a
separate, unauthenticated-beyond-the-shared-public-login bulk-file service
-- NOT the login-gated search.sunbiz.org website.

Real directory layout (confirmed live via SFTP listing, 2026-08-28 --
differs from the original brief in two ways, logged here rather than
silently "corrected"):
  - Quarterly master: doc/quarterly/cor/cordata.zip (single ~1.8GB zip,
    one member) + corevent.zip (filing history). The split cordata0.zip..
    cordata9.zip files named in the brief do NOT exist on this server --
    only the single cordata.zip.
  - Daily deltas: doc/cor/<YYYYMMDD>c.txt (plain fixed-width text, NOT
    zipped, NOT under doc/daily/cor -- that path does not exist).
    doc/cor/Events/<YYYYMMDD>ce.txt holds filing-event deltas (not
    ingested by this script -- entity records only, per issue scope).

Record format: fixed-width, 1440 bytes/record, one record per line
(\\n-terminated), no header row. Confirmed empirically against real
20260823c.txt sample data because dos.sunbiz.org/data-definitions/cor.html
(the linked "Corporate File Definitions" page) is behind a Cloudflare
managed challenge that blocks direct fetch -- the field layout below was
reverse-engineered from real records, not transcribed from the spec page.
Byte ranges for document_number/entity_name/status/filing_type/both
addresses/FEI/dates/officer-block-stride are VERIFIED against multiple
real samples. The officer first-name/middle-initial sub-split inside each
128-byte officer block is INFERRED (best-effort, not independently
confirmed against a second source) -- flagged for a follow-up spot-check
once officer-heavy records are sampled at volume.

Usage:
  python scripts/sunbiz_sftp_sync.py --mode hydrate --limit 5000
  python scripts/sunbiz_sftp_sync.py --mode hydrate           # full cordata.zip, unbounded
  python scripts/sunbiz_sftp_sync.py --mode daily              # most recent doc/cor/*c.txt
  python scripts/sunbiz_sftp_sync.py --mode daily --date 20260827
  python scripts/sunbiz_sftp_sync.py --mode hydrate --limit 2000 --dry-run
"""
import argparse
import io
import os
import sys
import zipfile
from datetime import datetime, timezone

import httpx
import paramiko

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_KEY", "")

SFTP_HOST = os.environ.get("SUNBIZ_SFTP_HOST", "sftp.floridados.gov")
SFTP_USER = os.environ.get("SUNBIZ_SFTP_USER", "")
SFTP_PASSWORD = os.environ.get("SUNBIZ_SFTP_PASSWORD", "")

RECORD_LEN = 1440
BATCH_SIZE = 500
AGENT_OPS_TASK = "sunbiz-sync"

client = httpx.Client(timeout=60)


def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }


def log_ops(dispatch_id, status, evidence, severity="info"):
    """Best-effort write to public.agent_ops_log. Never raises."""
    try:
        client.post(
            f"{SUPABASE_URL}/rest/v1/agent_ops_log",
            headers=sb_headers(),
            json=[{
                "dispatch_id": dispatch_id, "task": AGENT_OPS_TASK,
                "status": status, "evidence": evidence[:2000], "severity": severity,
            }],
        )
    except Exception:
        pass


def sftp_connect():
    if not SFTP_USER or not SFTP_PASSWORD:
        raise RuntimeError("SUNBIZ_SFTP_USER / SUNBIZ_SFTP_PASSWORD not set")
    transport = paramiko.Transport((SFTP_HOST, 22))
    transport.connect(username=SFTP_USER, password=SFTP_PASSWORD)
    return transport, paramiko.SFTPClient.from_transport(transport)


def to_date(mmddyyyy):
    s = (mmddyyyy or "").strip()
    if not s or len(s) != 8 or not s.isdigit():
        return None
    try:
        return datetime.strptime(s, "%m%d%Y").date().isoformat()
    except ValueError:
        return None


def field(line, start, end):
    """1-based inclusive slice, matching the byte-range convention used
    throughout this module and its docstring."""
    return line[start - 1:end].strip()


def parse_officer_blocks(line):
    officers = []
    base = 669  # 1-based start of officer-block region, verified against sample data
    block_width = 128
    for i in range(6):
        s = base + i * block_width
        title = field(line, s, s + 3)
        otype = field(line, s + 4, s + 4)
        last = field(line, s + 5, s + 24)
        first_mi = field(line, s + 25, s + 46)
        addr1 = field(line, s + 47, s + 88)
        city = field(line, s + 89, s + 116)
        state = field(line, s + 117, s + 118)
        zipc = field(line, s + 119, s + 123)
        if not any([title, otype, last, first_mi, addr1, city, state, zipc]):
            continue
        officers.append({
            "title": title, "type": otype, "last_name": last,
            "first_name_mi": first_mi, "address_line1": addr1,
            "city": city, "state": state, "zip": zipc,
        })
    return officers


def parse_record(line, source_file):
    if len(line) < RECORD_LEN:
        return None
    doc_number = field(line, 1, 12)
    if not doc_number:
        return None

    ra_state = field(line, 504, 505)
    ra_last = field(line, 545, 564)
    ra_first = field(line, 565, 586)
    # 587 is a single-char RA type flag (P=person, C=corporation) sitting
    # between the name and address sub-blocks -- verified against sample
    # data; skipped here since it's not part of name or address.
    ra_addr1 = field(line, 588, 629)
    ra_city = field(line, 630, 657)
    ra_state2 = field(line, 658, 659)
    ra_zip = field(line, 660, 664)
    ra_name = " ".join(p for p in [ra_last, ra_first] if p).strip() or ra_last
    ra_address_parts = [ra_addr1, ", ".join(p for p in [ra_city, ra_state2] if p), ra_zip]
    ra_address = " ".join(p for p in ra_address_parts if p).strip()

    return {
        "document_number": doc_number,
        "entity_name": field(line, 13, 204) or "UNKNOWN",
        "entity_type": field(line, 206, 220) or None,
        "status": field(line, 205, 205) or None,
        "date_filed": to_date(field(line, 473, 480)),
        "last_transaction_date": to_date(field(line, 496, 503)),
        "more_than_six_officers": field(line, 495, 495) == "Y",
        "state_of_formation": ra_state or None,
        "fei_ein": field(line, 481, 494) or None,

        "principal_address_line1": field(line, 221, 304) or None,
        "principal_city": field(line, 305, 332) or None,
        "principal_state": field(line, 333, 334) or None,
        "principal_zip": field(line, 335, 339) or None,
        "principal_country": field(line, 340, 346) or None,

        "mailing_address_line1": field(line, 347, 430) or None,
        "mailing_city": field(line, 431, 458) or None,
        "mailing_state": field(line, 459, 460) or None,
        "mailing_zip": field(line, 461, 465) or None,
        "mailing_country": field(line, 466, 472) or None,

        "registered_agent_name": ra_name or None,
        "registered_agent_address": ra_address or None,

        "officers": parse_officer_blocks(line),
        "source_file": source_file,
        "last_synced_at": datetime.now(timezone.utc).isoformat(),
    }


def upsert(rows):
    if not rows:
        return 0
    resp = client.post(
        f"{SUPABASE_URL}/rest/v1/sunbiz_entities?on_conflict=document_number",
        headers=sb_headers(),
        json=rows,
    )
    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(f"upsert sunbiz_entities failed: {resp.status_code} {resp.text[:500]}")
    return len(rows)


def process_lines(line_iter, source_file, limit, dry_run):
    batch = []
    total_parsed = 0
    total_upserted = 0
    for raw in line_iter:
        line = raw.decode("latin-1") if isinstance(raw, bytes) else raw
        line = line.rstrip("\n").rstrip("\r")
        if len(line) < RECORD_LEN:
            continue
        rec = parse_record(line, source_file)
        if not rec:
            continue
        total_parsed += 1
        batch.append(rec)
        if len(batch) >= BATCH_SIZE:
            if not dry_run:
                total_upserted += upsert(batch)
            else:
                total_upserted += len(batch)
            batch = []
            print(f"  ... {total_parsed} parsed, {total_upserted} upserted so far", file=sys.stderr)
        if limit and total_parsed >= limit:
            break
    if batch:
        if not dry_run:
            total_upserted += upsert(batch)
        else:
            total_upserted += len(batch)
    return total_parsed, total_upserted


def run_hydrate(limit, dry_run):
    """Streams directly from the remote SFTP file object (paramiko SFTPFile
    is seekable, so zipfile can read the central directory + member data
    without downloading the whole ~1.8GB archive first) -- a plain
    sftp.get() of the full file was tried first and reliably dropped the
    connection (EOFError in paramiko's prefetch thread) partway through;
    streaming sidesteps that entirely and is the only path exercised here.

    cordata.zip contains 10 members (cordata0.txt..cordata9.txt, ~500-600K
    records each) -- the brief's cordata0-9.zip naming was half right: the
    split by digit is real, it's just packaged as 10 members inside one
    zip, not 10 separate zip files."""
    dispatch_id = "sunbiz-hydrate-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    transport, sftp = sftp_connect()
    try:
        remote_path = "doc/quarterly/cor/cordata.zip"
        st = sftp.stat(remote_path)
        print(f"cordata.zip remote size: {st.st_size} bytes", file=sys.stderr)

        remote_fh = sftp.open(remote_path, "rb")
        remote_fh.set_pipelined(False)
        try:
            zf = zipfile.ZipFile(remote_fh)
            names = sorted(zf.namelist())
            if not names:
                raise RuntimeError("cordata.zip contains no members")
            print(f"members: {names}", file=sys.stderr)

            total_parsed = 0
            total_upserted = 0
            for member in names:
                remaining = (limit - total_parsed) if limit else None
                if limit and remaining <= 0:
                    break
                print(f"reading member: {member} (remaining budget={remaining})", file=sys.stderr)
                with zf.open(member) as fh:
                    p, u = process_lines(fh, f"cordata.zip/{member}", remaining, dry_run)
                total_parsed += p
                total_upserted += u
        finally:
            remote_fh.close()

        evidence = (
            f"hydrate: cordata.zip remote_size={st.st_size} members={len(names)} "
            f"parsed={total_parsed} upserted={total_upserted} "
            f"limit={limit or 'unbounded'} dry_run={dry_run}"
        )
        print(evidence)
        log_ops(dispatch_id, "VERIFIED" if not dry_run else "SKIPPED", evidence, "info")
        return total_parsed, total_upserted
    except Exception as e:
        log_ops(dispatch_id, "BLOCKED", f"hydrate failed: {e}", "blocker")
        raise
    finally:
        transport.close()


def run_daily(date_str, dry_run):
    dispatch_id = "sunbiz-daily-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    transport, sftp = sftp_connect()
    try:
        if date_str:
            fname = f"{date_str}c.txt"
        else:
            items = sftp.listdir_attr("doc/cor")
            files = sorted(
                [i.filename for i in items if i.filename.endswith("c.txt") and i.filename[0].isdigit()]
            )
            if not files:
                raise RuntimeError("no daily c.txt files found under doc/cor")
            fname = files[-1]

        remote_path = f"doc/cor/{fname}"
        st = sftp.stat(remote_path)
        print(f"{remote_path} remote size: {st.st_size} bytes", file=sys.stderr)

        local_path = f"/tmp/{fname}"
        sftp.get(remote_path, local_path)

        with open(local_path, "rb") as fh:
            total_parsed, total_upserted = process_lines(fh, fname, None, dry_run)

        evidence = (
            f"daily: file={fname} remote_size={st.st_size} parsed={total_parsed} "
            f"upserted={total_upserted} dry_run={dry_run}"
        )
        print(evidence)
        log_ops(dispatch_id, "VERIFIED" if not dry_run else "SKIPPED", evidence, "info")
        return total_parsed, total_upserted
    except Exception as e:
        log_ops(dispatch_id, "BLOCKED", f"daily sync failed: {e}", "blocker")
        raise
    finally:
        transport.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["hydrate", "daily"], required=True)
    ap.add_argument("--limit", type=int, default=None, help="max records to parse (hydrate only)")
    ap.add_argument("--date", default=None, help="YYYYMMDD for --mode daily (default: most recent)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
        sys.exit(1)

    if args.mode == "hydrate":
        run_hydrate(args.limit, args.dry_run)
    else:
        run_daily(args.date, args.dry_run)


if __name__ == "__main__":
    main()
