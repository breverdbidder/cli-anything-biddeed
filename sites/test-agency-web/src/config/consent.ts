// TCPA consent text/version are config-driven so each generated agency site
// can carry its own agency name in the text without editing code -- but the
// version id must still be bumped by a human whenever text_template changes,
// same discipline as the hand-written v1 (see agency.config.schema.json).
import { config } from "./agency";

export const TCPA_CONSENT_VERSION = config.consent.version;

export const TCPA_CONSENT_TEXT = config.consent.text_template.replaceAll(
  "{{agency_name}}",
  config.agency_name
);
