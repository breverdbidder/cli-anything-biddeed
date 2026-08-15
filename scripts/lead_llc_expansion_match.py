#!/usr/bin/env python3
"""
Lead volume expansion: match multi_county_auctions LLC/corp winning bidders
against the FL Division of Corporations quarterly bulk data (cordata.txt,
fixed-width, downloaded free via public SFTP from sftp.floridados.gov) to
recover a mailing address + registered agent for each entity. Sunbiz's public
record layout has no email field, so this is a mail-only address match, not
an email lookup.

Usage:
  python scripts/lead_llc_expansion_match.py \
    --cordata /tmp/sunbiz/cordata.txt \
    --bidders /tmp/sunbiz/bidders_raw.json \
    --out /tmp/sunbiz/sunbiz_matches.json
"""
import argparse
import json
import re

RECORD_LEN = 1440
REC_STRIDE = 1442  # 1440 data bytes + trailing \r\n record terminator

FIELDS = {
    "corp_number": (0, 12),
    "corp_name": (12, 204),
    "status": (204, 205),
    "filing_type": (205, 220),
    "addr1": (220, 262),
    "addr2": (262, 304),
    "city": (304, 332),
    "state": (332, 334),
    "zip": (334, 344),
    "mail_addr1": (346, 388),
    "mail_addr2": (388, 430),
    "mail_city": (430, 458),
    "mail_state": (458, 460),
    "mail_zip": (460, 470),
    "ra_name": (544, 586),
    "ra_addr": (587, 629),
    "ra_city": (629, 657),
    "ra_state": (657, 659),
    "ra_zip": (659, 668),
}

QUALIFIER_RE = re.compile(
    r",?\s*A\s+[A-Z]+\s+(LIMITED\s+LIABILITY\s+COMPANY|CORPORATION|"
    r"LIMITED\s+PARTNERSHIP|GENERAL\s+PARTNERSHIP|PARTNERSHIP)\.?\s*$",
    re.I,
)


def normalize(name):
    if not name:
        return ""
    name = name.split(";")[0]
    name = QUALIFIER_RE.sub("", name)
    name = name.upper()
    name = re.sub(r"[.,]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def parse_record(raw):
    rec = {}
    for key, (start, end) in FIELDS.items():
        rec[key] = raw[start:end].strip()
    return rec


def best_address(rec):
    if rec["mail_addr1"]:
        return {
            "line1": rec["mail_addr1"],
            "line2": rec["mail_addr2"],
            "city": rec["mail_city"],
            "state": rec["mail_state"],
            "zip": rec["mail_zip"],
            "source_field": "mailing_address",
        }
    if rec["addr1"]:
        return {
            "line1": rec["addr1"],
            "line2": rec["addr2"],
            "city": rec["city"],
            "state": rec["state"],
            "zip": rec["zip"],
            "source_field": "principal_address",
        }
    if rec["ra_addr"]:
        return {
            "line1": rec["ra_addr"],
            "line2": "",
            "city": rec["ra_city"],
            "state": rec["ra_state"],
            "zip": rec["ra_zip"],
            "source_field": "registered_agent_address",
        }
    return None


def fmt_address(addr):
    if not addr:
        return None
    parts = [addr["line1"]]
    if addr["line2"]:
        parts.append(addr["line2"])
    csz = " ".join(p for p in [addr["city"], addr["state"], addr["zip"]] if p)
    if csz:
        parts.append(csz)
    return ", ".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cordata", required=True)
    ap.add_argument("--bidders", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    bidders = json.load(open(args.bidders))
    targets = {}
    for b in bidders:
        key = normalize(b["winning_bidder"])
        if not key:
            continue
        targets.setdefault(key, []).append(b)
    print(f"Loaded {len(bidders)} raw bidders -> {len(targets)} normalized target names")

    matches = {}
    n_records = 0
    with open(args.cordata, "rb") as f:
        buf = b""
        while True:
            chunk = f.read(REC_STRIDE * 20000)
            if not chunk:
                break
            buf += chunk
            n_full = len(buf) // REC_STRIDE
            for i in range(n_full):
                rec_start = i * REC_STRIDE
                raw = buf[rec_start:rec_start + RECORD_LEN].decode("latin-1")
                n_records += 1
                name_field = raw[12:204].strip()
                if not name_field:
                    continue
                key = normalize(name_field)
                if key in targets:
                    rec = parse_record(raw)
                    prev = matches.get(key)
                    if prev is None or (rec["status"] == "A" and prev["status"] != "A"):
                        matches[key] = rec
            buf = buf[n_full * REC_STRIDE:]

    print(f"Scanned {n_records} corp records; matched {len(matches)}/{len(targets)} target names")

    out = {}
    for key, bidder_list in targets.items():
        rec = matches.get(key)
        if rec:
            addr = best_address(rec)
            out[key] = {
                "matched": True,
                "sunbiz_name": rec["corp_name"],
                "status": rec["status"],
                "filing_type": rec["filing_type"],
                "mailing_address": fmt_address(addr),
                "address_source": addr["source_field"] if addr else None,
                "registered_agent": rec["ra_name"] or None,
                "bidders": bidder_list,
            }
        else:
            out[key] = {
                "matched": False,
                "bidders": bidder_list,
            }

    json.dump(out, open(args.out, "w"), indent=2)
    matched_with_addr = sum(1 for v in out.values() if v["matched"] and v["mailing_address"])
    print(f"Wrote {args.out}: {len(out)} target companies, "
          f"{sum(1 for v in out.values() if v['matched'])} sunbiz-matched, "
          f"{matched_with_addr} with a usable address")


if __name__ == "__main__":
    main()
