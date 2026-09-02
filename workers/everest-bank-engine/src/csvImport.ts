// Wells Fargo CSV export parser (issue #19749 Part 1). No header row. Columns: Date, Amount,
// *, *, Description -- the two middle columns are WF placeholder/status columns, unused here.
// WF's own convention (stated in the issue body): negative = debit (money leaving the account).
// This file only PARSES; the sign negation into this Worker's storage convention happens once,
// in fileImport.ts, so csvImport.ts/ofxImport.ts both hand back the same raw sign untouched.

import type { ParsedTxn } from "./importUtils";

function splitCsvLine(line: string): string[] {
  const fields: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        cur += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      fields.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  fields.push(cur);
  return fields.map((f) => f.trim());
}

function toIsoDate(mmddyyyy: string): string {
  const m = mmddyyyy.trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (!m) throw new Error(`unrecognized WF CSV date: ${mmddyyyy}`);
  const [, mo, day, yr] = m;
  return `${yr}-${mo.padStart(2, "0")}-${day.padStart(2, "0")}`;
}

export function parseWfCsv(text: string): ParsedTxn[] {
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  const out: ParsedTxn[] = [];
  for (const line of lines) {
    const fields = splitCsvLine(line);
    if (fields.length < 5) continue; // malformed/short row -- skip rather than fail the whole file
    const [dateRaw, amountRaw, , , ...descParts] = fields;
    out.push({
      date: toIsoDate(dateRaw),
      rawAmount: amountRaw.replace(/[,$]/g, ""),
      description: descParts.join(",").trim(),
      fitId: null,
    });
  }
  return out;
}
