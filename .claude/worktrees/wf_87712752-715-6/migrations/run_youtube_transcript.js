const { Client } = require("pg");

const hosts = [
  "aws-0-us-east-1.pooler.supabase.com",
  "aws-1-us-east-1.pooler.supabase.com",
  "aws-0-us-east-2.pooler.supabase.com",
  "aws-1-us-east-2.pooler.supabase.com",
  "aws-0-us-west-1.pooler.supabase.com",
  "aws-0-us-west-2.pooler.supabase.com",
];
const ports = [5432, 6543];
const user = "postgres.mocerqjnksmhcjzxrewo";

const SQL = `
CREATE TABLE IF NOT EXISTS public.youtube_transcript (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  video_id text UNIQUE NOT NULL,
  title text NOT NULL,
  channel text,
  url text NOT NULL,
  duration_seconds int,
  upload_date date,
  tags jsonb DEFAULT '[]'::jsonb,
  ai_summary text,
  ai_insights text,
  relevance_tags text[],
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
ALTER TABLE public.youtube_transcript ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
  CREATE POLICY "Service role full access" ON public.youtube_transcript
    FOR ALL USING (auth.role() = 'service_role');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
CREATE INDEX IF NOT EXISTS idx_yt_video_id ON public.youtube_transcript(video_id);
CREATE INDEX IF NOT EXISTS idx_yt_upload_date ON public.youtube_transcript(upload_date DESC);

INSERT INTO public.youtube_transcript (video_id, title, channel, url, duration_seconds, upload_date, tags, ai_summary, ai_insights, relevance_tags)
SELECT
  (description::jsonb)->>'video_id',
  (description::jsonb)->>'title',
  (description::jsonb)->>'channel',
  (description::jsonb)->>'url',
  ((description::jsonb)->>'duration_seconds')::int,
  ((description::jsonb)->>'upload_date')::date,
  (description::jsonb)->'tags',
  (description::jsonb)->>'ai_summary',
  (description::jsonb)->>'ai_insights',
  ARRAY(SELECT jsonb_array_elements_text((description::jsonb)->'five_rules'))
FROM public.insights
WHERE anomaly_type = 'YOUTUBE_TRANSCRIPT'
ON CONFLICT (video_id) DO NOTHING;

DELETE FROM public.insights WHERE anomaly_type = 'YOUTUBE_TRANSCRIPT';
`;

async function run() {
  const pw = (process.env.SUPABASE_DB_PASSWORD || "").trim();
  if (!pw) { console.error("No SUPABASE_DB_PASSWORD"); process.exit(1); }
  console.log("Trying " + (hosts.length * ports.length) + " connection combos...");

  let connected = false;
  let client;

  for (const host of hosts) {
    for (const port of ports) {
      const label = host.split(".")[0] + ":" + port;
      client = new Client({
        host, port, user, password: pw, database: "postgres",
        ssl: { rejectUnauthorized: false },
        connectionTimeoutMillis: 5000,
      });
      try {
        await client.connect();
        console.log("CONNECTED via " + label);
        connected = true;
        break;
      } catch (err) {
        var msg = err.message.slice(0, 60);
        if (msg.includes("password")) {
          console.log("AUTH FAIL " + label + " (host correct, password wrong)");
        } else if (msg.includes("Tenant")) {
          // Expected for wrong host
        } else {
          console.log("FAIL " + label + ": " + msg);
        }
        try { await client.end(); } catch(e) {}
      }
    }
    if (connected) break;
  }

  if (!connected) {
    console.error("All combos failed.");
    process.exit(1);
  }

  await client.query(SQL);
  console.log("Migration complete");

  const res = await client.query("SELECT count(*) FROM public.youtube_transcript");
  console.log("youtube_transcript rows: " + res.rows[0].count);

  const rows = await client.query("SELECT video_id, title FROM public.youtube_transcript LIMIT 5");
  rows.rows.forEach(r => console.log("  " + r.video_id + ": " + r.title));

  const cleanup = await client.query("SELECT count(*) FROM public.insights WHERE anomaly_type = 'YOUTUBE_TRANSCRIPT'");
  console.log("Remaining interim in insights: " + cleanup.rows[0].count);

  await client.end();
}
run();