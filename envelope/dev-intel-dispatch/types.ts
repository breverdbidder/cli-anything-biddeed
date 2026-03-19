// zonewise/lib/development-analysis/types.ts

export interface Parcel {
  id: string;
  address: string;
  city: string;
  zip: string;
  zone: string;
  zoneDesc: string;
  lotWidth: number;
  lotDepth: number;
  landValue: number;
  improvValue: number;
  yearBuilt: number;
  photo: string | null;
  setbacks: { front: number; side: number; rear: number };
  maxHeight: number;
  maxCoverage: number;
  far: number;
  currentUse: string;
  lat: number;
  lng: number;
  floodZone: string;
  hasUtilities: boolean;
  roadFrontage: number | null;
  topography: string;
}

export interface Envelope {
  bw: number;        // buildable width
  bd: number;        // buildable depth
  lotArea: number;
  footprint: number;
  maxByCov: number;
  effFP: number;     // effective footprint
  maxGFA: number;
  floors: number;
  actualGFA: number;
  volume: number;
  covPct: string;
}

export interface HBUScenario {
  useType: string;
  use: string;         // display label
  legal: number;       // 0-100
  physical: number;    // 0-100
  financial: number;   // 0-100
  maximal: number;     // 0-100
  score: number;       // overall 0-100
  roi: number;         // projected ROI %
  risk: "Low" | "Medium" | "High";
  timeline: string;    // "8-12 mo"
  investReq: number;   // total investment $
  buildCost: number;   // construction only $
  projectedValue: number; // income approach $
  annualNOI: number;
  maxBid: number;      // (ARV×70%)-Repairs-$10K-MIN($25K,15%ARV)
  isConditional: boolean;
}

export interface CMAReport {
  id: string;
  parcel_id: string;
  hbu_scenarios: HBUScenario[];
  best_use: string;
  best_score: number;
  max_bid_amount: number;
  computed_at: string;
}

// Supabase envelope_cache row → Parcel mapping
export interface EnvelopeCacheRow {
  parcel_id: string;
  address: string;
  city: string;
  zip: string;
  zone_code: string;
  zone_description: string;
  lot_width_ft: number;
  lot_depth_ft: number;
  land_value: number;
  improvement_value: number;
  year_built: number;
  bcpao_photo_url: string | null;
  front_setback: number;
  side_setback: number;
  rear_setback: number;
  max_height_ft: number;
  max_lot_coverage_pct: number;
  floor_area_ratio: number;
  current_use: string;
  latitude: number;
  longitude: number;
  flood_zone: string;
  has_utilities: boolean;
  road_frontage_ft: number | null;
  topography: string;
  hbu_scores_json: string | null;
}
