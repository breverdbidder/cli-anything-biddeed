const { Client } = require('pg');

const POOLER_HOSTS = [
  "aws-0-us-east-1.pooler.supabase.com",
  "aws-1-us-east-1.pooler.supabase.com",
  "aws-0-us-east-2.pooler.supabase.com",
];

async function run() {
  const pw = (process.env.SUPABASE_DB_PASSWORD || "").trim();
  if (!pw) { console.error("❌ No SUPABASE_DB_PASSWORD"); process.exit(1); }

  const SQL = `
    -- Create youtube_transcript table
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

    -- RLS
    ALTER TABLE public.youtube_transcript ENABLE ROW LEVEL SECURITY;
    DO $$ BEGIN
      CREATE POLICY "Service role full access" ON public.youtube_transcript
        FOR ALL USING (auth.role() = 'service_role');
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$;

    -- Indexes
    CREATE INDEX IF NOT EXISTS idx_yt_video_id ON public.youtube_transcript(video_id);
    CREATE INDEX IF NOT EXISTS idx_yt_upload_date ON public.youtube_transcript(upload_date DESC);

    -- Migrate interim data from insights table
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

    -- Cleanup interim rows
    DELETE FROM public.insights WHERE anomaly_type = 'YOUTUBE_TRANSCRIPT';
  `;

  for (const host of POOLER_HOSTS) {
    console.log("Trying " + host + "...");
    const client = new Client({
      host, port: 6543, database: "postgres",
      user: "postgres.mocerqjnksmhcjzxrewo", password: pw,
      ssl: { rejectUnauthorized: false },
      connectionTimeoutMillis: 10000,
    });
    try {
      await client.connect();
      console.log("✅ Connected to " + host);
      await client.query(SQL);
      console.log("✅ Migration complete");

      // Verify
      const res = await client.query("SELECT count(*) FROM public.youtube_transcript");
      console.log("📊 youtube_transcript rows: " + res.rows[0].count);
      
      const verify = await client.query("SELECT video_id, title FROM public.youtube_transcript LIMIT 5");
      verify.rows.forEach(r => console.log("  → " + r.video_id + ": " + r.title));

      // Verify cleanup
      const cleanup = await client.query("SELECT count(*) FROM public.insights WHERE anomaly_type = 'YOUTUBE_TRANSCRIPT'");
      console.log("🧹 Remaining interim rows in insights: " + cleanup.rows[0].count);

      await client.end();
      process.exit(0);
    } catch (e) {
      console.log("  ⚠️ " + e.message);
      try { await client.end(); } catch(_) {}
    }
  }
  console.error("❌ All pooler hosts failed");
  process.exit(1);
}
run();