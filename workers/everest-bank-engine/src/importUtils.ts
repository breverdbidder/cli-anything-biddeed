// Shared types/helpers for the non-Plaid ingestion paths (file import, SimpleFIN) -- issue
// #19749. Kept separate from csvImport.ts/ofxImport.ts/simplefin.ts so all three can depend on
// it without a circular import between the two file parsers.

export interface ParsedTxn {
  date: string; // YYYY-MM-DD
  rawAmount: string; // decimal string exactly as it appeared in the source (sign per source convention)
  description: string;
  fitId: string | null; // OFX FITID; null when the source has no native transaction id
}

export async function sha256Hex(input: string): Promise<string> {
  const bytes = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// Issue #19749 spec: "plaid_transaction_id = OFX FITID when present, else
// sha256(date|amount|description|mask)". Used by both csvImport (which has no FITID concept at
// all) and ofxImport (rare malformed OFX files that omit FITID).
export async function fallbackTransactionId(
  date: string,
  amount: string,
  description: string,
  mask: string
): Promise<string> {
  return sha256Hex(`${date}|${amount}|${description}|${mask}`);
}
