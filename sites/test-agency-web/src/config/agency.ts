// Single load point for this site's agency.config.json (copied into the site
// root by scripts/new-agency-site.mjs -- see agency.config.schema.json at the
// template root for the field contract). Every agency-specific string, color,
// or copy block in the site flows through this module; components never
// import agency.config.json directly.
import rawConfig from "../../agency.config.json";

export interface LineOfBusiness {
  slug: string;
  nav_label: string;
  page_title: string;
  meta_description: string;
  eyebrow: string;
  h1: string;
  intro: string;
  hero_variant?: "dark" | "light";
  hero_cta_variant?: "ink" | "brass";
  coverages: { title: string; body: string }[];
  final_cta_variant?: "dark" | "light";
  final_cta_heading: string;
  final_cta_body?: string | null;
  final_cta_button_variant?: "ink" | "brass";
  final_cta_text: string;
}

export interface TeamMember {
  initials: string;
  name: string;
  role: string;
  bio: string;
}

export interface AgencyConfig {
  slug: string;
  agency_name: string;
  tagline: string;
  hero_description: string;
  meta_description: string;
  domain: { default: string };
  brand?: Record<string, string>;
  logo_path?: string | null;
  phone: { display: string; tel: string };
  city: string;
  license_line: string;
  licensed_states: string[];
  ams_vendor: "ezlynx" | "other";
  client_center?: { label: string; url: string; note?: string };
  carriers_note: string;
  why_points: string[];
  proof_points: { number: string; title: string; body: string }[];
  lines_of_business: LineOfBusiness[];
  team: TeamMember[];
  consent: { version: string; text_template: string };
  canopy_connect?: { public_alias_env?: string; dec_upload_url_env?: string };
  vapi?: { public_key_env?: string; assistant_id_env?: string };
  supabase_table?: string;
  supabase_storage_bucket?: string;
  intake?: {
    fallbacks?: {
      decUpload?: boolean;
      formEntry?: boolean;
      callback?: boolean;
      firstTimeBuyer?: boolean;
    };
  };
  posthog?: { enabled?: boolean };
}

export const config = rawConfig as AgencyConfig;

export const SITE_DOMAIN =
  import.meta.env.PUBLIC_SITE_DOMAIN || config.domain.default;
export const SITE_URL = `https://${SITE_DOMAIN}`;

export const AGENCY_NAME = config.agency_name;
export const AGENCY_TAGLINE = config.tagline;
export const PHONE_DISPLAY = config.phone.display;
export const PHONE_TEL = config.phone.tel;
export const LICENSE_LINE = config.license_line;
export const AGENCY_CITY = config.city;

export const CANOPY_PUBLIC_ALIAS_ENV =
  config.canopy_connect?.public_alias_env || "PUBLIC_CANOPY_CONNECT_PUBLIC_ALIAS";
export const VAPI_PUBLIC_KEY_ENV = config.vapi?.public_key_env || "PUBLIC_VAPI_PUBLIC_KEY";
export const VAPI_ASSISTANT_ID_ENV = config.vapi?.assistant_id_env || "PUBLIC_VAPI_ASSISTANT_ID";

export const SUPABASE_TABLE =
  config.supabase_table || `${config.slug.replace(/-/g, "_")}_intake`;

// Secondary/fallback intake sharing paths beneath the primary Canopy
// Connect CTA (issue #19602). Every key defaults to enabled -- an agency
// opts OUT of a specific path by setting it false in agency.config.json,
// not opts in.
export const INTAKE_FALLBACKS = {
  decUpload: config.intake?.fallbacks?.decUpload ?? true,
  formEntry: config.intake?.fallbacks?.formEntry ?? true,
  callback: config.intake?.fallbacks?.callback ?? true,
  firstTimeBuyer: config.intake?.fallbacks?.firstTimeBuyer ?? true,
};
