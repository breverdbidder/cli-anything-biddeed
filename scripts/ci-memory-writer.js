import { createClient } from '@supabase/supabase-js';
import Anthropic from '@anthropic-ai/sdk';
import fs from 'fs';

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
);
const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

function writeGithubOutput(lines) {
  if (!process.env.GITHUB_OUTPUT) return;
  fs.appendFileSync(process.env.GITHUB_OUTPUT, lines);
}

async function updateAgentMemory({ competitor, runId, findingsFile }) {
  const findings = JSON.parse(fs.readFileSync(findingsFile, 'utf8'));

  const { data: existingMemories } = await supabase
    .from('ci_agent_memory')
    .select('*')
    .eq('competitor', competitor)
    .eq('is_active', true);

  const memoryPrompt = `
You are the memory-writer for a competitive intelligence agent tracking ${competitor}.

EXISTING MEMORIES:
${JSON.stringify(existingMemories, null, 2)}

TODAY'S FINDINGS:
${JSON.stringify(findings, null, 2)}

Return ONLY valid JSON (no preamble, no markdown):
{
  "confirmed_memory_ids": ["uuid"],
  "contradicted_memory_ids": [],
  "new_memories": [
    {
      "memory_type": "update_pattern",
      "observation": "observation text",
      "confidence": 0.6,
      "source_url": "https://..."
    }
  ],
  "change_magnitude": "none",
  "changes_detected": false,
  "agent_confidence": 0.85,
  "alert_worthy": false,
  "alert_reason": null
}`;

  const response = await anthropic.messages.create({
    model: 'claude-sonnet-5',
    max_tokens: 1000,
    messages: [{ role: 'user', content: memoryPrompt }]
  });

  const analysis = JSON.parse(response.content[0].text);

  if (analysis.new_memories.length > 0) {
    await supabase.from('ci_agent_memory').insert(
      analysis.new_memories.map(m => ({
        ...m,
        competitor,
        confirmed_at: [new Date().toISOString()],
        created_by: 'ci_agent'
      }))
    );
  }

  for (const memId of analysis.confirmed_memory_ids) {
    const mem = existingMemories.find(m => m.id === memId);
    if (!mem) continue;
    await supabase.from('ci_agent_memory').update({
      confidence: Math.min(1.0, mem.confidence + 0.1),
      confirmed_at: [...(mem.confirmed_at || []), new Date().toISOString()],
      last_evaluated: new Date().toISOString()
    }).eq('id', memId);
  }

  for (const memId of analysis.contradicted_memory_ids) {
    const mem = existingMemories.find(m => m.id === memId);
    if (!mem) continue;
    const newConf = Math.max(0.0, mem.confidence - 0.2);
    await supabase.from('ci_agent_memory').update({
      confidence: newConf,
      contradicted_at: [...(mem.contradicted_at || []), new Date().toISOString()],
      is_active: newConf > 0.1
    }).eq('id', memId);
  }

  await supabase.from('ci_agent_runs').insert({
    id: runId,
    competitor,
    changes_detected: analysis.changes_detected,
    change_magnitude: analysis.change_magnitude,
    raw_findings: findings,
    report_generated: analysis.change_magnitude !== 'none',
    alert_sent: analysis.alert_worthy,
    agent_confidence: analysis.agent_confidence,
    memories_used: (existingMemories || []).map(m => m.id),
    memories_updated: analysis.new_memories.length > 0 ? ['new'] : []
  });

  if (analysis.alert_worthy) {
    writeGithubOutput(
      `alert_worthy=true\nalert_reason=${analysis.alert_reason}\nchange_magnitude=${analysis.change_magnitude}\n`
    );
  } else {
    writeGithubOutput(
      `alert_worthy=false\nchange_magnitude=${analysis.change_magnitude}\n`
    );
  }
}

// CLI: node ci-memory-writer.js --competitor property_onion --run-id <uuid> --findings-file ./findings.json
const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, val, i, arr) => {
    if (val.startsWith('--')) acc.push([val.slice(2), arr[i + 1]]);
    return acc;
  }, [])
);
await updateAgentMemory({
  competitor: args.competitor,
  runId: args['run-id'],
  findingsFile: args['findings-file']
});
