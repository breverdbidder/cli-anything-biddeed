// GET /privacy (issue #19737 addendum, 2026-09-02). Renders §9 "Privacy and consumer data
// rights" of docs/security/EVEREST_INFOSEC_POLICY.md as plain HTML, no auth. Content is a
// build-time copy of that section -- keep the two in sync if the policy doc changes.

export function renderPrivacyPage(): string {
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Everest Capital — Privacy Policy</title>
</head>
<body style="font-family: -apple-system, sans-serif; background:#020617; color:#e2e8f0; padding:2rem; max-width:640px; margin:0 auto; line-height:1.6;">
  <h1>Everest Capital — Privacy Policy</h1>
  <p><strong>Entities covered:</strong> Everest Capital of Brevard LLC, Everest Capital USA, BidDeed.AI, ZoneWise.AI, Winner Data (winnerdataai.com)</p>
  <p><strong>Version:</strong> 1.0 — Effective 2026-09-02</p>

  <h2>Privacy and consumer data rights</h2>
  <ul>
    <li>Everest Capital connects <strong>its own business bank accounts</strong> via Plaid; no consumer end-users' bank data is collected or stored.</li>
    <li>Financial-data use is limited to internal bookkeeping, reconciliation, and reporting. Data is not sold or shared with third parties.</li>
    <li>Deletion: on request or when a connection is removed, the Plaid Item is removed via <code>/item/remove</code> and associated rows are purged; Stripe data is mirrored read-only and purged on account closure.</li>
    <li>Retention: financial records retained per statutory requirement (7 years); operational logs 90 days.</li>
  </ul>

  <p>Contact: Ariel Shapira, Founder &amp; CEO — everestcapital8@gmail.com</p>
</body>
</html>`;
}
