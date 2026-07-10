// Claude Watch — SHA-256 hashing utility
// Zero shell execution policy: no child_process, no execSync
import { createHash } from "crypto";

export function sha256(content: string): string {
  return createHash("sha256").update(content, "utf8").digest("hex");
}
