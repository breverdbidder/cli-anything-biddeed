// Single source of truth for the site's domain. Ariel has not chosen the final
// domain yet -- every absolute URL in the site derives from this constant so
// switching domains later is a one-line change, not a find-and-replace.
export const SITE_DOMAIN = import.meta.env.PUBLIC_SITE_DOMAIN || "protectionpartners.pages.dev";
export const SITE_URL = `https://${SITE_DOMAIN}`;
export const AGENCY_NAME = "Protection Partners";
export const AGENCY_TAGLINE = "AI-native independent insurance, human-bound.";

// Placeholders -- Ariel to fill in before go-live.
export const PHONE_DISPLAY = "[PHONE TBD]";
export const PHONE_TEL = "tel:+10000000000"; // TODO(Ariel): replace with RingCentral DID
export const LICENSE_LINE = "Florida Licensed Insurance Agency — License #TBD";
export const AGENCY_CITY = "Titusville, FL";
export const MOMENTUM_PORTAL_URL = "https://portal.momentum-ams.example/protection-partners"; // placeholder, Ariel to confirm
