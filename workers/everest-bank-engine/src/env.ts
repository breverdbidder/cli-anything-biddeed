export interface Env {
  PLAID_CLIENT_ID: string;
  PLAID_SECRET: string;
  PLAID_ENV: string;
  SUPABASE_URL: string;
  SUPABASE_SERVICE_ROLE_KEY: string;
  CFO_AGENT_SHARED_SECRET: string;
  PLAID_WEBHOOK_URL?: string;
}
