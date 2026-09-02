import { Configuration, PlaidApi, PlaidEnvironments } from "plaid";
import type { Env } from "./env";

const ENV_MAP: Record<string, string> = {
  sandbox: PlaidEnvironments.sandbox,
  production: PlaidEnvironments.production,
};

export function plaidClient(env: Env): PlaidApi {
  const basePath = ENV_MAP[env.PLAID_ENV] ?? PlaidEnvironments.sandbox;
  const configuration = new Configuration({
    basePath,
    baseOptions: {
      headers: {
        "PLAID-CLIENT-ID": env.PLAID_CLIENT_ID,
        "PLAID-SECRET": env.PLAID_SECRET,
      },
    },
  });
  return new PlaidApi(configuration);
}
