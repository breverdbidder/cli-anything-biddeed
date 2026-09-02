/**
 * Pure formatting helpers for the Winner Data FF worker, split out of
 * index.js so they can be unit tested with plain Node (no .html imports,
 * no Cloudflare Workers runtime, no bundler needed to run `node --test`).
 * index.js imports these rather than redefining them.
 */

export function money(n) {
  if (n === null || n === undefined) return 'Not established';
  return `$${Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

export function esc(s) {
  if (s === null || s === undefined) return '';
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

// issue #19747 defect 2: land-trust buyer names (entity_name/contact_name)
// carry the raw deed boilerplate through Section 689.071, Florida Statutes
// ("...with full power and authority to protect, conserve and to sell...")
// on every FF for a trust-vehicle buyer -- strip it to "<Trust Name> —
// <Trustee Name>, trustee". Non-trust names (no boilerplate clause present,
// e.g. "SMITH JOHN") pass through byte-identical -- the boilerplate-marker
// test is the only branch condition.
const TRUSTEE_BOILERPLATE_RE = /\s*,?\s*with full power and authority[\s\S]*$/i;
const TRUST_TRUSTEE_RE = /^(.+?),\s*(.+?)\s+as trustee\s*$/i;

export function titleCase(s) {
  return s.replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());
}

export function normalizeBuyerName(raw) {
  if (!raw || !TRUSTEE_BOILERPLATE_RE.test(raw)) return raw;
  const stripped = raw.replace(TRUSTEE_BOILERPLATE_RE, '').trim();
  const m = stripped.match(TRUST_TRUSTEE_RE);
  if (!m) return stripped;
  const [, trustName, trusteeName] = m;
  return `${trustName.trim()} — ${titleCase(trusteeName.trim())}, trustee`;
}

// issue #19747 defect 3: this line used to derive "recorded N days ago" from
// auction_date regardless of whether a certificate of title had actually
// been recorded -- contradicting the Property Profile row below it, which
// reads the real ct_recording_date field and correctly says "Not yet
// recorded" when it's null. Both now read the same field (ctRecordingDate,
// passed in by the caller) so they can never disagree again.
export function callScript(displayName, auction, ctRecordingDate) {
  const saleLine = ctRecordingDate
    ? `Certificate of title recorded ${ctRecordingDate}${auction.case_number ? `, case ${auction.case_number}` : ''}.`
    : `Sale held ${auction.auction_date || 'date not established'}, certificate of title not yet recorded.`;
  return [
    saleLine,
    auction.sold_amount ? `Winning bid was ${money(auction.sold_amount)}.` : null,
    `Calling ${esc(displayName)} re: property insurance on the new acquisition.`,
  ].filter(Boolean).join(' ');
}
