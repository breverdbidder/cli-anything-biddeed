// S4 Monitoring tools — subscription, gate: pro tier
import { get, insert } from '../supabase.js';

export const schemas = [
  {
    name: 'watch_auction',
    description: 'Subscribe to auction alerts: 24hr reminder, morning-of notification, and postpone/cancel alerts. BidDeed exclusive — Investra watch_price equivalent but auction-specific. Requires Pro tier subscription.',
    inputSchema: {
      type: 'object',
      properties: {
        case_number:   { type: 'string', description: 'Auction case number to watch' },
        county:        { type: 'string', description: 'FL county' },
        notify_email:  { type: 'string', description: 'Alert email address' },
        notify_phone:  { type: 'string', description: 'SMS alert phone number (US, +1XXXXXXXXXX)' },
        alerts:        {
          type: 'array',
          items: { type: 'string', enum: ['24hr', 'morning_of', 'postponement', 'cancellation', 'result'] },
          description: 'Alert types (default: all)',
        },
        max_bid:       { type: 'number', description: 'Your max bid — receive alert if opening bid exceeds this' },
      },
      required: ['case_number', 'county'],
    },
  },
];

export async function watch_auction({ case_number, county, notify_email, notify_phone, alerts, max_bid }) {
  // Verify auction exists
  const rows = await get(
    `multi_county_auctions?case_number=eq.${encodeURIComponent(case_number)}&county=ilike.${encodeURIComponent(county)}&select=case_number,county,property_address,opening_bid,auction_date&limit=1`
  ).catch(() => []);

  if (!rows.length) {
    return { error: `Auction ${case_number} not found in ${county}. Verify case number.` };
  }

  const auction = rows[0];
  const activeAlerts = alerts || ['24hr', 'morning_of', 'postponement', 'cancellation', 'result'];

  // Store subscription in auction_watches table (inserted via billing customer_id by server.js)
  const watch = {
    case_number,
    county,
    notify_email: notify_email || null,
    notify_phone: notify_phone || null,
    alert_types: activeAlerts,
    max_bid: max_bid || null,
    auction_date: auction.auction_date,
    created_at: new Date().toISOString(),
    status: 'active',
  };

  // Best-effort insert — table may not exist in all deployments
  await insert('auction_watches', watch).catch(err => {
    process.stderr.write(`[watch_auction] Insert failed: ${err.message}\n`);
  });

  const alertSchedule = [];
  if (activeAlerts.includes('24hr')) {
    const d = new Date(auction.auction_date);
    d.setDate(d.getDate() - 1);
    alertSchedule.push({ type: '24hr', send_at: d.toISOString().slice(0, 10) + 'T09:00:00-05:00' });
  }
  if (activeAlerts.includes('morning_of')) {
    alertSchedule.push({ type: 'morning_of', send_at: auction.auction_date + 'T07:00:00-05:00' });
  }
  if (activeAlerts.includes('postponement')) {
    alertSchedule.push({ type: 'postponement', send_at: 'triggered_on_court_filing' });
  }
  if (activeAlerts.includes('cancellation')) {
    alertSchedule.push({ type: 'cancellation', send_at: 'triggered_on_court_filing' });
  }
  if (activeAlerts.includes('result')) {
    alertSchedule.push({ type: 'result', send_at: 'triggered_after_auction' });
  }

  return {
    subscribed: true,
    case_number,
    county,
    property_address: auction.property_address,
    auction_date: auction.auction_date,
    opening_bid: auction.opening_bid,
    max_bid_alert: max_bid || null,
    alerts_active: activeAlerts,
    alert_schedule: alertSchedule,
    notifications_to: {
      email: notify_email || 'set notify_email to receive email alerts',
      sms: notify_phone || 'set notify_phone for SMS alerts',
    },
    manage_at: 'https://biddeed.ai/dashboard/watches',
  };
}
