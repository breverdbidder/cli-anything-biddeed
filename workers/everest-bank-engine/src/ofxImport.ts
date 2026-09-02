// OFX 1.x SGML / 2.x XML parser (issue #19749 Part 1) -- a small hand-written extractor rather
// than a vendored dependency, per K2 simplicity (no new npm package for ~40 lines of regex).
//
// OFX 1.x SGML leaf tags are NOT closed (e.g. "<TRNAMT>-52.13" with no "</TRNAMT>"); aggregate
// tags (<STMTTRN>...</STMTTRN>) ARE closed in both 1.x and 2.x. A regex that reads "<TAG>value"
// up to the next "<" works identically for both flavors, since 2.x's "<TAG>value</TAG>" also
// stops at its own closing tag's "<".
//
// TRNAMT sign convention (OFX spec): negative = debit (money leaving the account), positive =
// credit -- the same human convention as the WF CSV export. Negation into this Worker's storage
// convention happens once, in fileImport.ts.

import type { ParsedTxn } from "./importUtils";

function extractTag(block: string, tag: string): string | null {
  const m = block.match(new RegExp(`<${tag}>([^<\\r\\n]*)`, "i"));
  return m ? m[1].trim() : null;
}

function ofxDateToIso(raw: string): string {
  // DTPOSTED is YYYYMMDD[HHMMSS][.xxx][[gmt offset:TZ]] -- only the first 8 digits matter here.
  const digits = raw.replace(/[^0-9]/g, "");
  if (digits.length < 8) throw new Error(`unrecognized OFX date: ${raw}`);
  return `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6, 8)}`;
}

export function parseOfx(text: string): ParsedTxn[] {
  const blocks = text.match(/<STMTTRN>[\s\S]*?<\/STMTTRN>/gi) ?? [];
  const out: ParsedTxn[] = [];
  for (const block of blocks) {
    const dtposted = extractTag(block, "DTPOSTED");
    const trnamt = extractTag(block, "TRNAMT");
    if (!dtposted || !trnamt) continue; // malformed transaction block -- skip, don't fail the file
    const description = extractTag(block, "NAME") ?? extractTag(block, "PAYEE") ?? extractTag(block, "MEMO") ?? "";
    out.push({
      date: ofxDateToIso(dtposted),
      rawAmount: trnamt,
      description,
      fitId: extractTag(block, "FITID"),
    });
  }
  return out;
}

export function looksLikeOfx(text: string, filename?: string): boolean {
  if (filename && /\.(ofx|qfx)$/i.test(filename)) return true;
  const head = text.slice(0, 400).toUpperCase();
  return head.includes("OFXHEADER") || head.includes("<OFX>");
}
