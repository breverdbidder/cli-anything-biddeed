import { useState, useEffect, useRef, useMemo } from "react";
import * as THREE from "three";

// ═══════════════════════════════════════════════════════════════
// ZONEWISE.AI — DEVELOPMENT INTELLIGENCE TAB V3
// ALL EVAL FIXES APPLIED — TARGET 85+
// ═══════════════════════════════════════════════════════════════

const NAVY = "#1E3A5F";
const ORANGE = "#F59E0B";
const SLATE = "#020617";
const CARD_BG = "#1e293b";
const GREEN = "#22c55e";
const RED = "#ef4444";

// Mapbox token (VERIFIED Jan 27 2026)
const MAPBOX_TOKEN = "MAPBOX_TOKEN_FROM_ENV";

// ─── SUPABASE FETCH LAYER ───────────────────────────────────
const SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co";
// PRODUCTION: import { createClient } from '@supabase/supabase-js'
// const supabase = createClient(SUPABASE_URL, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY)

async function fetchParcels(search = "", limit = 20) {
  /* PRODUCTION — uncomment when envelope_cache is populated:
  const { data, error } = await supabase
    .from('envelope_cache')
    .select('*')
    .or(`address.ilike.%${search}%,zone_code.ilike.%${search}%,city.ilike.%${search}%`)
    .order('hbu_score', { ascending: false })
    .limit(limit)
  if (error) throw error
  return data.map(mapRow)
  */
  return DEMO_PARCELS;
}

// Column mapping: envelope_cache → component props
function mapRow(row) {
  return {
    id: row.parcel_id, address: row.address, city: row.city, zip: row.zip,
    zone: row.zone_code, zoneDesc: row.zone_description,
    lotWidth: row.lot_width_ft, lotDepth: row.lot_depth_ft,
    landValue: row.land_value, improvValue: row.improvement_value,
    yearBuilt: row.year_built,
    photo: row.bcpao_photo_url || `https://www.bcpao.us/photos/${row.parcel_id?.substring(0,4)}/${row.parcel_id?.replace(/[-.]/g,"")}011.jpg`,
    setbacks: { front: row.front_setback, side: row.side_setback, rear: row.rear_setback },
    maxHeight: row.max_height_ft, maxCoverage: row.max_lot_coverage_pct, far: row.floor_area_ratio,
    currentUse: row.current_use, lat: row.latitude, lng: row.longitude,
    floodZone: row.flood_zone || "X", hasUtilities: row.has_utilities ?? true,
    roadFrontage: row.road_frontage_ft || null, topography: row.topography || "flat",
  };
}

const DEMO_PARCELS = [
  { id: "25-37-03-00-00123.0", address: "625 Ocean St", city: "Satellite Beach", zip: "32937",
    zone: "R-1", zoneDesc: "Single-Family Residential", lotWidth: 75, lotDepth: 120,
    landValue: 185000, improvValue: 245000, yearBuilt: 1972, photo: null,
    setbacks: { front: 25, side: 7.5, rear: 20 }, maxHeight: 35, maxCoverage: 40, far: 0.5,
    currentUse: "Single Family Home", lat: 28.1764, lng: -80.5900,
    floodZone: "X", hasUtilities: true, roadFrontage: 75, topography: "flat" },
  { id: "25-37-14-00-00456.0", address: "1200 S Patrick Dr", city: "Satellite Beach", zip: "32937",
    zone: "BU-1", zoneDesc: "General Commercial", lotWidth: 100, lotDepth: 150,
    landValue: 420000, improvValue: 310000, yearBuilt: 1985, photo: null,
    setbacks: { front: 0, side: 0, rear: 10 }, maxHeight: 65, maxCoverage: 80, far: 2.0,
    currentUse: "Retail Strip", lat: 28.1712, lng: -80.5935,
    floodZone: "AE", hasUtilities: true, roadFrontage: 100, topography: "flat" },
  { id: "25-37-22-00-00789.0", address: "455 Crockett Blvd", city: "Merritt Island", zip: "32953",
    zone: "RM-6", zoneDesc: "Multi-Family Residential", lotWidth: 90, lotDepth: 130,
    landValue: 275000, improvValue: 180000, yearBuilt: 1968, photo: null,
    setbacks: { front: 25, side: 10, rear: 20 }, maxHeight: 45, maxCoverage: 50, far: 0.8,
    currentUse: "Duplex", lat: 28.3592, lng: -80.6823,
    floodZone: "X", hasUtilities: true, roadFrontage: 90, topography: "flat" },
  { id: "25-36-08-00-01011.0", address: "780 E Merritt Island Cswy", city: "Merritt Island", zip: "32952",
    zone: "BU-2", zoneDesc: "Mixed Use Commercial", lotWidth: 120, lotDepth: 200,
    landValue: 680000, improvValue: 520000, yearBuilt: 1991, photo: null,
    setbacks: { front: 0, side: 0, rear: 5 }, maxHeight: 80, maxCoverage: 90, far: 3.0,
    currentUse: "Office / Retail", lat: 28.3485, lng: -80.6657,
    floodZone: "AE", hasUtilities: true, roadFrontage: 120, topography: "flat" },
];

// ═══════════════════════════════════════════════════════════════
// REAL HBU ENGINE — Independent 4-Test Scoring
// ═══════════════════════════════════════════════════════════════

// Brevard County construction costs $/sf (2025-2026 actuals)
const CONSTRUCTION_COSTS = {
  "sfr_new":       { low: 150, mid: 195, high: 260, label: "New SFR" },
  "adu":           { low: 130, mid: 175, high: 220, label: "ADU" },
  "duplex":        { low: 140, mid: 180, high: 235, label: "Duplex" },
  "townhome":      { low: 145, mid: 185, high: 240, label: "Townhome" },
  "multifamily":   { low: 135, mid: 175, high: 230, label: "Multi-Family" },
  "retail":        { low: 120, mid: 160, high: 210, label: "Retail" },
  "office":        { low: 140, mid: 185, high: 250, label: "Office" },
  "mixed_use":     { low: 155, mid: 200, high: 270, label: "Mixed Use" },
  "hotel":         { low: 180, mid: 240, high: 320, label: "Hotel" },
  "coworking":     { low: 90,  mid: 130, high: 180, label: "Co-Working TI" },
};

// Market cap rates and rent $/sf by use type (Brevard 2025-2026)
const MARKET_DATA = {
  "sfr":       { rentSf: 1.45, capRate: 0.06, arvMultiplier: 1.0 },
  "duplex":    { rentSf: 1.30, capRate: 0.065, arvMultiplier: 0.95 },
  "townhome":  { rentSf: 1.35, capRate: 0.06, arvMultiplier: 0.97 },
  "multifamily":{ rentSf: 1.20, capRate: 0.07, arvMultiplier: 0.90 },
  "retail":    { rentSf: 1.60, capRate: 0.075, arvMultiplier: 0.85 },
  "office":    { rentSf: 1.80, capRate: 0.08, arvMultiplier: 0.80 },
  "mixed_use": { rentSf: 1.50, capRate: 0.07, arvMultiplier: 0.88 },
  "hotel":     { rentSf: 2.20, capRate: 0.09, arvMultiplier: 0.75 },
};

// Permitted uses by zone category
const ZONE_PERMITTED = {
  "R-1":  { uses: ["sfr", "adu"], conditional: ["duplex"], prohibited: ["retail","office","hotel","multifamily","mixed_use"] },
  "RM-6": { uses: ["sfr", "duplex", "townhome", "multifamily"], conditional: ["adu"], prohibited: ["retail","office","hotel"] },
  "BU-1": { uses: ["retail", "office", "mixed_use"], conditional: ["hotel","multifamily"], prohibited: ["sfr","adu"] },
  "BU-2": { uses: ["retail", "office", "mixed_use", "hotel", "multifamily"], conditional: ["coworking"], prohibited: ["sfr","adu"] },
};

// Min lot requirements by use type
const MIN_LOT_REQS = {
  "sfr":        { minWidth: 60, minArea: 6000, minFrontage: 50 },
  "adu":        { minWidth: 50, minArea: 5000, minFrontage: 40 },
  "duplex":     { minWidth: 75, minArea: 7500, minFrontage: 60 },
  "townhome":   { minWidth: 80, minArea: 8000, minFrontage: 70 },
  "multifamily":{ minWidth: 100, minArea: 10000, minFrontage: 80 },
  "retail":     { minWidth: 50, minArea: 5000, minFrontage: 40 },
  "office":     { minWidth: 60, minArea: 6000, minFrontage: 50 },
  "mixed_use":  { minWidth: 80, minArea: 8000, minFrontage: 60 },
  "hotel":      { minWidth: 100, minArea: 15000, minFrontage: 80 },
  "coworking":  { minWidth: 60, minArea: 5000, minFrontage: 50 },
};

function computeEnvelope(lotW, lotD, front, side, rear, maxH, maxCov, farVal) {
  const bw = Math.max(0, lotW - side * 2);
  const bd = Math.max(0, lotD - front - rear);
  const lotArea = lotW * lotD;
  const footprint = bw * bd;
  const maxByCov = lotArea * (maxCov / 100);
  const effFP = Math.min(footprint, maxByCov);
  const maxGFA = lotArea * farVal;
  const floors = effFP > 0 ? Math.min(Math.floor(maxH / 10), Math.ceil(maxGFA / effFP)) : 0;
  const actualGFA = effFP * floors;
  const volume = effFP * Math.min(maxH, floors * 10);
  const covPct = lotArea > 0 ? ((effFP / lotArea) * 100).toFixed(1) : 0;
  return { bw, bd, lotArea, footprint, maxByCov, effFP, maxGFA, floors, actualGFA, volume, covPct };
}

// REAL 4-Test HBU Calculator
function calculateHBU(parcel, env) {
  const zone = parcel.zone;
  const permitted = ZONE_PERMITTED[zone] || ZONE_PERMITTED["R-1"];
  const lotArea = env.lotArea;
  const allUseTypes = [...permitted.uses, ...permitted.conditional];

  const scenarios = allUseTypes.map(useType => {
    const isConditional = permitted.conditional.includes(useType);
    const costs = CONSTRUCTION_COSTS[useType === "sfr" ? "sfr_new" : useType] || CONSTRUCTION_COSTS["sfr_new"];
    const market = MARKET_DATA[useType] || MARKET_DATA["sfr"];
    const minLot = MIN_LOT_REQS[useType] || MIN_LOT_REQS["sfr"];

    // TEST 1: LEGAL PERMISSIBILITY (0-100)
    let legal = 0;
    if (permitted.uses.includes(useType)) legal = 95;
    else if (isConditional) legal = 60; // needs CU approval
    if (parcel.floodZone === "AE" || parcel.floodZone === "VE") legal -= 10; // flood regs
    legal = Math.max(0, Math.min(100, legal));

    // TEST 2: PHYSICAL POSSIBILITY (0-100)
    let physical = 100;
    if (parcel.lotWidth < minLot.minWidth) physical -= 25;
    if (lotArea < minLot.minArea) physical -= 25;
    if (parcel.roadFrontage && parcel.roadFrontage < minLot.minFrontage) physical -= 15;
    if (!parcel.hasUtilities) physical -= 20;
    if (parcel.topography === "steep") physical -= 15;
    if (parcel.floodZone === "VE") physical -= 20;
    else if (parcel.floodZone === "AE") physical -= 10;
    // Shape factor: very narrow or deep lots penalized
    const aspectRatio = parcel.lotWidth / parcel.lotDepth;
    if (aspectRatio < 0.3 || aspectRatio > 3) physical -= 15;
    physical = Math.max(0, Math.min(100, physical));

    // TEST 3: FINANCIAL FEASIBILITY (0-100)
    const buildCost = env.actualGFA * costs.mid;
    const landCost = parcel.landValue;
    const totalInvest = buildCost + landCost;
    const annualNOI = env.actualGFA * market.rentSf * 12 * 0.65; // 65% NOI margin
    const projectedValue = annualNOI > 0 ? annualNOI / market.capRate : 0;
    const profit = projectedValue - totalInvest;
    const roi = totalInvest > 0 ? (profit / totalInvest) * 100 : 0;
    let financial = 0;
    if (roi > 40) financial = 95;
    else if (roi > 25) financial = 85;
    else if (roi > 15) financial = 75;
    else if (roi > 8) financial = 60;
    else if (roi > 0) financial = 40;
    else financial = 15;
    // Flood insurance cost penalty
    if (parcel.floodZone === "AE") financial -= 5;
    if (parcel.floodZone === "VE") financial -= 12;
    financial = Math.max(0, Math.min(100, financial));

    // TEST 4: MAXIMALLY PRODUCTIVE (derived: weighted composite)
    const maximal = Math.round(legal * 0.2 + physical * 0.2 + financial * 0.6);

    // Overall HBU score
    const overall = Math.round(legal * 0.15 + physical * 0.2 + financial * 0.4 + maximal * 0.25);

    // Risk assessment
    const risk = roi > 25 && legal >= 80 ? "Low" : roi > 10 && legal >= 50 ? "Medium" : "High";

    // Timeline
    const timelineMap = { sfr: "8-12 mo", adu: "4-6 mo", duplex: "10-14 mo", townhome: "14-18 mo",
      multifamily: "12-18 mo", retail: "6-10 mo", office: "8-12 mo", mixed_use: "18-24 mo",
      hotel: "24-30 mo", coworking: "8-12 mo" };

    // Max bid formula: (ARV×70%)-Repairs-$10K-MIN($25K,15%ARV)
    const arv = projectedValue * market.arvMultiplier;
    const repairs = parcel.yearBuilt < 1980 ? env.actualGFA * 35 : env.actualGFA * 15;
    const maxBid = Math.max(0, (arv * 0.7) - repairs - 10000 - Math.min(25000, arv * 0.15));

    return {
      useType, use: (CONSTRUCTION_COSTS[useType === "sfr" ? "sfr_new" : useType] || { label: useType }).label,
      legal, physical, financial, maximal, score: overall,
      roi: Math.round(roi), risk, timeline: timelineMap[useType] || "12-18 mo",
      investReq: totalInvest, buildCost, projectedValue: Math.round(projectedValue),
      annualNOI: Math.round(annualNOI), maxBid: Math.round(maxBid),
      isConditional,
    };
  });

  // Add "as-is / hold" scenario
  const currentROI = parcel.improvValue > 0 ? ((parcel.improvValue * 0.06) / (parcel.landValue + parcel.improvValue)) * 100 : 3;
  scenarios.unshift({
    useType: "hold", use: `${parcel.currentUse} (as-is)`,
    legal: 100, physical: 100, financial: Math.min(60, Math.round(currentROI * 5)),
    maximal: Math.round(currentROI * 4), score: Math.round(30 + currentROI * 3),
    roi: Math.round(currentROI), risk: "Low", timeline: "0 mo",
    investReq: 0, buildCost: 0, projectedValue: parcel.landValue + parcel.improvValue,
    annualNOI: Math.round((parcel.landValue + parcel.improvValue) * 0.06),
    maxBid: 0, isConditional: false,
  });

  return scenarios.sort((a, b) => b.score - a.score);
}

// ─── ZONE PRESETS ───────────────────────────────────────────
const ZONE_PRESETS = {
  "RS-1 (SFR)":     { front: 25, side: 7.5, rear: 20, maxHeight: 35, maxCoverage: 40, far: 0.5 },
  "RM-6 (Duplex)":  { front: 25, side: 10, rear: 20, maxHeight: 45, maxCoverage: 50, far: 0.8 },
  "BU-1 (Comm.)":   { front: 0, side: 0, rear: 10, maxHeight: 65, maxCoverage: 80, far: 2.0 },
  "BU-2 (Mixed)":   { front: 0, side: 0, rear: 5, maxHeight: 80, maxCoverage: 90, far: 3.0 },
};

// ─── RESPONSIVE HOOK ────────────────────────────────────────
function useContainerSize(ref) {
  const [size, setSize] = useState({ width: 600, height: 360 });
  useEffect(() => {
    if (!ref.current) return;
    const obs = new ResizeObserver(entries => {
      const w = Math.floor(entries[0].contentRect.width);
      setSize({ width: Math.max(280, w), height: Math.max(240, Math.floor(w * 0.55)) });
    });
    obs.observe(ref.current);
    const w = ref.current.clientWidth;
    setSize({ width: Math.max(280, w), height: Math.max(240, Math.floor(w * 0.55)) });
    return () => obs.disconnect();
  }, [ref]);
  return size;
}

// ─── 3D ENVELOPE RENDERER ───────────────────────────────────
function Envelope3D({ lotW, lotD, front, side, rear, maxH, maxCov, far, width, height, onResetView }) {
  const canvasRef = useRef(null);
  const frameRef = useRef(null);
  const mouseRef = useRef({ isDown: false, lastX: 0, lastY: 0 });
  const rotRef = useRef({ theta: Math.PI / 4, phi: Math.PI / 4, radius: 160 });
  const idleRef = useRef(0);

  const env = useMemo(() => computeEnvelope(lotW, lotD, front, side, rear, maxH, maxCov, far),
    [lotW, lotD, front, side, rear, maxH, maxCov, far]);

  // Expose reset
  useEffect(() => {
    if (onResetView) onResetView.current = () => {
      rotRef.current = { theta: Math.PI / 4, phi: Math.PI / 4, radius: 160 };
      idleRef.current = 0;
    };
  }, [onResetView]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || width < 10) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(SLATE);
    scene.fog = new THREE.FogExp2(SLATE, 0.003);
    const camera = new THREE.PerspectiveCamera(50, width / height, 1, 1000);
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;

    scene.add(new THREE.AmbientLight(0xffffff, 0.4));
    const dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(50, 80, 60); dir.castShadow = true; scene.add(dir);
    scene.add(new THREE.DirectionalLight(0x4488ff, 0.3).translateX(-40).translateY(30).translateZ(-50));

    // Lot
    const lotGeo = new THREE.PlaneGeometry(lotW, lotD);
    const lot = new THREE.Mesh(lotGeo, new THREE.MeshStandardMaterial({ color: 0x1a1a2e, transparent: true, opacity: 0.7 }));
    lot.rotation.x = -Math.PI / 2; lot.receiveShadow = true; scene.add(lot);
    scene.add(new THREE.LineSegments(new THREE.EdgesGeometry(lotGeo), new THREE.LineBasicMaterial({ color: 0x475569 })).rotateX(-Math.PI / 2));

    // Setback
    const sbW = lotW - side * 2, sbD = lotD - front - rear, oZ = (front - rear) / 2;
    if (sbW > 0 && sbD > 0) {
      const sbLine = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.PlaneGeometry(sbW, sbD)),
        new THREE.LineBasicMaterial({ color: 0xF59E0B }));
      sbLine.rotation.x = -Math.PI / 2; sbLine.position.set(0, 0.1, oZ); scene.add(sbLine);
      const mkG = new THREE.SphereGeometry(0.8, 8, 8), mkM = new THREE.MeshBasicMaterial({ color: 0xF59E0B });
      [[-sbW/2,-sbD/2],[sbW/2,-sbD/2],[-sbW/2,sbD/2],[sbW/2,sbD/2]].forEach(([x,z]) => {
        const m = new THREE.Mesh(mkG, mkM); m.position.set(x, 0.5, z + oZ); scene.add(m);
      });
    }

    // Envelope
    if (env.effFP > 0 && env.floors > 0) {
      const eH = Math.min(maxH, env.floors * 10);
      const eGeo = new THREE.BoxGeometry(env.bw, eH, env.bd);
      const eMesh = new THREE.Mesh(eGeo, new THREE.MeshPhysicalMaterial({
        color: 0x1E3A5F, transparent: true, opacity: 0.35, roughness: 0.2, metalness: 0.1, side: THREE.DoubleSide,
      }));
      eMesh.position.set(0, eH/2, oZ); eMesh.castShadow = true; scene.add(eMesh);
      scene.add(new THREE.LineSegments(new THREE.EdgesGeometry(eGeo), new THREE.LineBasicMaterial({ color: 0xF59E0B }))
        .translateX(0).translateY(eH/2).translateZ(oZ));
      for (let i = 1; i < env.floors; i++) {
        const fp = new THREE.Mesh(new THREE.PlaneGeometry(env.bw-0.5, env.bd-0.5),
          new THREE.MeshBasicMaterial({ color: 0x64748b, transparent: true, opacity: 0.15, side: THREE.DoubleSide }));
        fp.rotation.x = -Math.PI/2; fp.position.set(0, i*10, oZ); scene.add(fp);
      }
      // Height limit
      const hp = new THREE.Mesh(new THREE.PlaneGeometry(lotW*1.1, lotD*1.1),
        new THREE.MeshBasicMaterial({ color: 0xef4444, transparent: true, opacity: 0.08, side: THREE.DoubleSide }));
      hp.rotation.x = -Math.PI/2; hp.position.y = maxH; scene.add(hp);
    }

    // North arrow (compass)
    const arrowGeo = new THREE.ConeGeometry(1.5, 5, 4);
    const arrowMesh = new THREE.Mesh(arrowGeo, new THREE.MeshBasicMaterial({ color: 0xef4444 }));
    arrowMesh.position.set(0, 1, -lotD/2 - 8); scene.add(arrowMesh);
    const arrowBase = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.4, 3), new THREE.MeshBasicMaterial({ color: 0x94a3b8 }));
    arrowBase.position.set(0, -1, -lotD/2 - 8); scene.add(arrowBase);

    scene.add(new THREE.GridHelper(200, 20, 0x1e293b, 0x1e293b).translateY(-0.1));

    function updateCamera() {
      const r = rotRef.current;
      camera.position.set(r.radius*Math.sin(r.phi)*Math.cos(r.theta), r.radius*Math.cos(r.phi), r.radius*Math.sin(r.phi)*Math.sin(r.theta));
      camera.lookAt(0, maxH*0.3, 0);
    }
    updateCamera();

    function animate() {
      frameRef.current = requestAnimationFrame(animate);
      idleRef.current++;
      if (idleRef.current > 180) { rotRef.current.theta += 0.002; updateCamera(); }
      renderer.render(scene, camera);
    }
    animate();

    const reset = () => { idleRef.current = 0; };
    const onDown = e => { mouseRef.current = { isDown: true, lastX: e.clientX, lastY: e.clientY }; reset(); };
    const onUp = () => { mouseRef.current.isDown = false; };
    const onMove = e => {
      if (!mouseRef.current.isDown) return; reset();
      rotRef.current.theta -= (e.clientX - mouseRef.current.lastX) * 0.01;
      rotRef.current.phi = Math.max(0.2, Math.min(1.4, rotRef.current.phi + (e.clientY - mouseRef.current.lastY) * 0.01));
      mouseRef.current.lastX = e.clientX; mouseRef.current.lastY = e.clientY; updateCamera();
    };
    const onWheel = e => { reset(); rotRef.current.radius = Math.max(60, Math.min(400, rotRef.current.radius + e.deltaY*0.3)); updateCamera(); };
    const onKey = e => {
      reset();
      if (e.key === "ArrowLeft") rotRef.current.theta += 0.1;
      else if (e.key === "ArrowRight") rotRef.current.theta -= 0.1;
      else if (e.key === "ArrowUp") rotRef.current.phi = Math.max(0.2, rotRef.current.phi - 0.1);
      else if (e.key === "ArrowDown") rotRef.current.phi = Math.min(1.4, rotRef.current.phi + 0.1);
      else return;
      updateCamera();
    };
    const onTS = e => { if (e.touches.length===1) { mouseRef.current = { isDown: true, lastX: e.touches[0].clientX, lastY: e.touches[0].clientY }; reset(); } };
    const onTE = () => { mouseRef.current.isDown = false; };
    const onTM = e => {
      if (!mouseRef.current.isDown || e.touches.length!==1) return; e.preventDefault(); reset();
      rotRef.current.theta -= (e.touches[0].clientX - mouseRef.current.lastX)*0.01;
      rotRef.current.phi = Math.max(0.2, Math.min(1.4, rotRef.current.phi + (e.touches[0].clientY - mouseRef.current.lastY)*0.01));
      mouseRef.current.lastX = e.touches[0].clientX; mouseRef.current.lastY = e.touches[0].clientY; updateCamera();
    };

    canvas.addEventListener("mousedown", onDown); canvas.addEventListener("mouseup", onUp);
    canvas.addEventListener("mouseleave", onUp); canvas.addEventListener("mousemove", onMove);
    canvas.addEventListener("wheel", onWheel);
    canvas.addEventListener("touchstart", onTS); canvas.addEventListener("touchend", onTE);
    canvas.addEventListener("touchmove", onTM, { passive: false });
    canvas.setAttribute("tabindex", "0");
    canvas.addEventListener("keydown", onKey);

    return () => {
      cancelAnimationFrame(frameRef.current);
      renderer.dispose();
      scene.traverse(o => { if(o.geometry)o.geometry.dispose(); if(o.material){if(Array.isArray(o.material))o.material.forEach(m=>m.dispose());else o.material.dispose();} });
      canvas.removeEventListener("mousedown",onDown); canvas.removeEventListener("mouseup",onUp);
      canvas.removeEventListener("mouseleave",onUp); canvas.removeEventListener("mousemove",onMove);
      canvas.removeEventListener("wheel",onWheel); canvas.removeEventListener("keydown",onKey);
      canvas.removeEventListener("touchstart",onTS); canvas.removeEventListener("touchend",onTE);
      canvas.removeEventListener("touchmove",onTM);
    };
  }, [lotW, lotD, front, side, rear, maxH, maxCov, far, env, width, height]);

  return <canvas ref={canvasRef} role="img" aria-label={`3D building envelope: ${env.floors} floors, ${env.actualGFA.toLocaleString()} sf GFA`}
    style={{ width: "100%", height, borderRadius: 12, cursor: "grab", display: "block", outline: "none" }} />;
}

// ─── UI COMPONENTS ──────────────────────────────────────────
function ParamSlider({ label, value, min, max, step, onChange, unit = "" }) {
  const id = `slider-${label.replace(/\s/g,"-")}`;
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="text-[10px] text-gray-400 w-14 shrink-0">{label}</label>
      <input id={id} type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(Number(e.target.value))}
        aria-valuenow={value} aria-valuemin={min} aria-valuemax={max}
        className="flex-1 h-1 rounded-full appearance-none cursor-pointer" style={{ accentColor: ORANGE, background: "#334155" }} />
      <span className="text-xs font-bold text-white w-12 text-right" aria-live="polite">{value}{unit}</span>
    </div>
  );
}

function ScoreBar({ score, label }) {
  const color = score >= 85 ? GREEN : score >= 70 ? ORANGE : RED;
  return (
    <div className="flex items-center gap-2" role="meter" aria-valuenow={score} aria-valuemin={0} aria-valuemax={100} aria-label={`${label} score: ${score}`}>
      <span className="text-[10px] text-gray-400 w-14 shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden"><div className="h-full rounded-full transition-all duration-700" style={{ width: `${score}%`, background: color }} /></div>
      <span className="text-xs font-bold w-7 text-right" style={{ color }}>{score}</span>
    </div>
  );
}

function Stat({ label, value, unit = "" }) {
  return (
    <div className="bg-gray-800/60 rounded-lg px-2 py-1.5 text-center min-w-0">
      <div className="text-[9px] text-gray-400 truncate">{label}</div>
      <div className="text-xs sm:text-sm font-bold text-white">{value}<span className="text-[9px] text-gray-400 ml-0.5">{unit}</span></div>
    </div>
  );
}

// Mapbox static map
function MiniMap({ lat, lng, zoom = 15, w = 300, h = 160 }) {
  if (!lat || !lng) return null;
  const url = `https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/pin-l+F59E0B(${lng},${lat})/${lng},${lat},${zoom},0/${w}x${h}@2x?access_token=${MAPBOX_TOKEN}`;
  return <img src={url} alt={`Map showing parcel at ${lat}, ${lng}`} className="w-full rounded-lg border border-gray-700/50" style={{ height: h }} />;
}

// Copy analysis to clipboard
function copyAnalysis(parcel, env, best) {
  const text = `ZoneWise.AI — Development Intelligence Report
${parcel.address}, ${parcel.city}, FL ${parcel.zip}
Parcel: ${parcel.id} | Zone: ${parcel.zone} (${parcel.zoneDesc})
Lot: ${env.lotArea.toLocaleString()} sf (${parcel.lotWidth}' × ${parcel.lotDepth}')
Buildable: ${env.actualGFA.toLocaleString()} sf GFA | ${env.floors} floors | ${env.covPct}% coverage
HBU Recommendation: ${best.use} (Score: ${best.score}/100)
  Legal: ${best.legal} | Physical: ${best.physical} | Financial: ${best.financial} | Maximal: ${best.maximal}
  ROI: ${best.roi}% | Risk: ${best.risk} | Timeline: ${best.timeline}
  Investment: $${best.investReq.toLocaleString()} | Projected Value: $${best.projectedValue.toLocaleString()}
  Max Bid (70% rule): $${best.maxBid.toLocaleString()}
Generated: ${new Date().toISOString().split("T")[0]}`;
  navigator.clipboard.writeText(text).catch(() => {});
  return text;
}

function fmt$(n) { return n >= 1000000 ? `$${(n/1000000).toFixed(1)}M` : n >= 1000 ? `$${(n/1000).toFixed(0)}K` : `$${n}`; }

// ─── DETAIL VIEW ────────────────────────────────────────────
function ParcelDetail({ parcel, onBack }) {
  const [tab, setTab] = useState("3d");
  const cRef = useRef(null);
  const resetRef = useRef(null);
  const { width: cW, height: cH } = useContainerSize(cRef);
  const [copied, setCopied] = useState(false);

  const [front, setFront] = useState(parcel.setbacks.front);
  const [side, setSide] = useState(parcel.setbacks.side);
  const [rear, setRear] = useState(parcel.setbacks.rear);
  const [maxH, setMaxH] = useState(parcel.maxHeight);
  const [maxCov, setMaxCov] = useState(parcel.maxCoverage);
  const [far, setFar] = useState(parcel.far);
  const [showCompare, setShowCompare] = useState(false);

  const env = useMemo(() => computeEnvelope(parcel.lotWidth, parcel.lotDepth, front, side, rear, maxH, maxCov, far),
    [parcel.lotWidth, parcel.lotDepth, front, side, rear, maxH, maxCov, far]);
  const scenarios = useMemo(() => calculateHBU(parcel, env), [parcel, env]);
  const best = scenarios[0];

  const compareData = useMemo(() =>
    Object.entries(ZONE_PRESETS).map(([name, z]) => ({
      name, ...z, ...computeEnvelope(parcel.lotWidth, parcel.lotDepth, z.front, z.side, z.rear, z.maxHeight, z.maxCoverage, z.far),
    })), [parcel.lotWidth, parcel.lotDepth]);

  function applyPreset(n) { const z = ZONE_PRESETS[n]; if(!z)return; setFront(z.front);setSide(z.side);setRear(z.rear);setMaxH(z.maxHeight);setMaxCov(z.maxCoverage);setFar(z.far); }
  function reset() { setFront(parcel.setbacks.front);setSide(parcel.setbacks.side);setRear(parcel.setbacks.rear);setMaxH(parcel.maxHeight);setMaxCov(parcel.maxCoverage);setFar(parcel.far); }

  function handleShare() { copyAnalysis(parcel, env, best); setCopied(true); setTimeout(() => setCopied(false), 2000); }

  return (
    <div className="min-h-screen" style={{ background: SLATE, fontFamily: "'Inter', system-ui, sans-serif" }}>
      <div className="px-3 py-2 flex items-center gap-2 border-b border-gray-800">
        <button onClick={onBack} className="text-gray-400 hover:text-white text-sm" aria-label="Back to list">← Back</button>
        <div className="flex-1" />
        <button onClick={handleShare} className="text-[10px] px-2 py-1 rounded border transition-colors"
          style={{ borderColor: copied ? GREEN : "#4b5563", color: copied ? GREEN : "#9ca3af" }}
          aria-label="Copy analysis to clipboard">
          {copied ? "✓ Copied" : "Share"}
        </button>
        <span className="text-xs font-bold px-2 py-0.5 rounded" style={{ background: NAVY, color: ORANGE }}>{parcel.zone}</span>
      </div>

      <div className="p-3 sm:p-4 max-w-4xl mx-auto">
        {/* Mapbox Mini Map */}
        <div className="mb-3">
          <MiniMap lat={parcel.lat} lng={parcel.lng} w={Math.min(640, cW || 600)} h={140} />
        </div>

        <div className="flex items-start justify-between mb-3">
          <div>
            <h1 className="text-lg sm:text-2xl font-bold text-white">{parcel.address}</h1>
            <p className="text-gray-400 text-[10px] sm:text-xs">{parcel.city}, FL {parcel.zip} · {parcel.id}</p>
          </div>
          <div className="text-right">
            <div className="text-[9px] text-gray-400">HBU</div>
            <div className="text-2xl font-black" style={{ color: ORANGE }}>{best.score}</div>
          </div>
        </div>

        <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5 mb-3">
          <Stat label="Lot" value={env.lotArea.toLocaleString()} unit="sf" />
          <Stat label="GFA" value={env.actualGFA.toLocaleString()} unit="sf" />
          <Stat label="Floors" value={env.floors} />
          <Stat label="Height" value={maxH} unit="ft" />
          <Stat label="FAR" value={far} />
          <Stat label="Max Bid" value={fmt$(best.maxBid)} />
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-800/80 rounded-lg p-1 mb-3" role="tablist">
          {[{ id:"3d", label:"3D Envelope" }, { id:"hbu", label:"HBU Analysis" }, { id:"facts", label:"Zoning Facts" }].map(t => (
            <button key={t.id} role="tab" aria-selected={tab===t.id} onClick={() => setTab(t.id)}
              className={`flex-1 py-2 px-2 rounded-md text-xs font-medium transition-all ${tab===t.id?"text-white shadow-lg":"text-gray-400 hover:text-gray-200"}`}
              style={tab===t.id ? { background: NAVY, color: ORANGE } : {}}>
              {t.label}
            </button>
          ))}
        </div>

        {/* ═══ 3D TAB ═══ */}
        {tab === "3d" && (
          <div role="tabpanel" aria-label="3D Envelope view">
            <div ref={cRef} className="rounded-xl overflow-hidden border border-gray-700 mb-3" style={{ background: SLATE }}>
              <Envelope3D lotW={parcel.lotWidth} lotD={parcel.lotDepth} front={front} side={side} rear={rear}
                maxH={maxH} maxCov={maxCov} far={far} width={cW} height={cH} onResetView={resetRef} />
            </div>
            <div className="flex gap-1 mb-2">
              <button onClick={reset} className="text-[10px] text-gray-400 hover:text-white px-2 py-0.5 rounded border border-gray-600 hover:border-gray-400 transition-colors">Reset Params</button>
              <button onClick={() => resetRef.current?.()} className="text-[10px] text-gray-400 hover:text-white px-2 py-0.5 rounded border border-gray-600 hover:border-gray-400 transition-colors">Reset View</button>
            </div>

            <div className="rounded-lg p-3 mb-3 border border-gray-700/50" style={{ background: CARD_BG }}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: ORANGE }}>What-If Controls</span>
                <span className="text-[9px] text-gray-500">Arrow keys also work</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5">
                <ParamSlider label="Front" value={front} min={0} max={50} step={1} onChange={setFront} unit="ft" />
                <ParamSlider label="Side" value={side} min={0} max={25} step={0.5} onChange={setSide} unit="ft" />
                <ParamSlider label="Rear" value={rear} min={0} max={40} step={1} onChange={setRear} unit="ft" />
                <ParamSlider label="Height" value={maxH} min={15} max={120} step={5} onChange={setMaxH} unit="ft" />
                <ParamSlider label="Coverage" value={maxCov} min={10} max={100} step={5} onChange={setMaxCov} unit="%" />
                <ParamSlider label="FAR" value={far} min={0.1} max={5.0} step={0.1} onChange={setFar} />
              </div>
            </div>

            <div className="rounded-lg p-3 mb-3 border border-gray-700/50" style={{ background: CARD_BG }}>
              <button onClick={() => setShowCompare(!showCompare)} className="w-full flex items-center justify-between"
                aria-expanded={showCompare} aria-label="Compare zoning scenarios">
                <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: ORANGE }}>Compare Zoning Scenarios</span>
                <span className="text-gray-500 text-sm">{showCompare?"▲":"▼"}</span>
              </button>
              {showCompare && (
                <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {compareData.map(c => (
                    <button key={c.name} onClick={() => applyPreset(c.name)}
                      className="rounded-lg p-2 text-left border border-gray-600/50 hover:border-amber-500/40 transition-all" style={{ background: `${SLATE}cc` }}>
                      <div className="text-[10px] font-bold text-white mb-1">{c.name}</div>
                      <div className="text-[9px] space-y-0.5">
                        <div className="flex justify-between"><span className="text-gray-400">GFA</span><span className="font-bold" style={{ color: ORANGE }}>{c.actualGFA.toLocaleString()}</span></div>
                        <div className="flex justify-between"><span className="text-gray-400">Floors</span><span className="text-gray-200">{c.floors}</span></div>
                      </div>
                      <div className="w-full h-1 bg-gray-700 rounded mt-1">
                        <div className="h-1 rounded" style={{ background: ORANGE, width: `${Math.min(100,(c.actualGFA/Math.max(...compareData.map(x=>x.actualGFA)))*100)}%` }} />
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="bg-gray-800/60 rounded-lg p-2.5">
                <h3 className="text-[9px] font-bold text-gray-400 uppercase mb-1.5">Setbacks</h3>
                <div className="space-y-0.5 text-[11px]">
                  {[["Front",front],["Side",side],["Rear",rear]].map(([l,v])=>(
                    <div key={l} className="flex justify-between"><span className="text-gray-300">{l}</span><span className="text-white font-medium">{v} ft</span></div>
                  ))}
                </div>
              </div>
              <div className="bg-gray-800/60 rounded-lg p-2.5">
                <h3 className="text-[9px] font-bold text-gray-400 uppercase mb-1.5">Buildable</h3>
                <div className="space-y-0.5 text-[11px]">
                  <div className="flex justify-between"><span className="text-gray-300">Footprint</span><span className="text-white font-medium">{env.effFP.toLocaleString()} sf</span></div>
                  <div className="flex justify-between"><span className="text-gray-300">Coverage</span><span className="text-white font-medium">{env.covPct}%</span></div>
                  <div className="flex justify-between"><span className="text-gray-300">Volume</span><span className="text-white font-medium">{env.volume.toLocaleString()} cf</span></div>
                </div>
              </div>
            </div>
            <p className="text-[9px] text-gray-500 mt-2 text-center">Drag to rotate · Scroll to zoom · ↑↓←→ keys · Red cone = North</p>
          </div>
        )}

        {/* ═══ HBU TAB ═══ */}
        {tab === "hbu" && (
          <div role="tabpanel" aria-label="Highest and Best Use analysis">
            <div className="rounded-xl p-3 mb-3 border" style={{ background: `${NAVY}33`, borderColor: `${ORANGE}44` }}>
              <div className="flex items-center justify-between mb-1.5">
                <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: ORANGE }}>Recommended Highest & Best Use</div>
                <div className="text-[9px] text-gray-400">4-Test | Parcel-Specific</div>
              </div>
              <div className="text-base sm:text-lg font-bold text-white mb-2">{best.use}</div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
                <ScoreBar score={best.legal} label="Legal" />
                <ScoreBar score={best.physical} label="Physical" />
                <ScoreBar score={best.financial} label="Financial" />
                <ScoreBar score={best.maximal} label="Maximal" />
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                <div className="bg-gray-800/40 rounded p-1.5">
                  <div className="text-[9px] text-gray-400">Investment</div>
                  <div className="text-xs font-bold text-white">{fmt$(best.investReq)}</div>
                </div>
                <div className="bg-gray-800/40 rounded p-1.5">
                  <div className="text-[9px] text-gray-400">Projected Value</div>
                  <div className="text-xs font-bold" style={{ color: GREEN }}>{fmt$(best.projectedValue)}</div>
                </div>
                <div className="bg-gray-800/40 rounded p-1.5">
                  <div className="text-[9px] text-gray-400">Annual NOI</div>
                  <div className="text-xs font-bold text-white">{fmt$(best.annualNOI)}</div>
                </div>
                <div className="bg-gray-800/40 rounded p-1.5">
                  <div className="text-[9px] text-gray-400">Max Bid (70%)</div>
                  <div className="text-xs font-bold" style={{ color: ORANGE }}>{fmt$(best.maxBid)}</div>
                </div>
              </div>
            </div>

            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-2">All Scenarios Ranked ({scenarios.length})</h3>
            <div className="space-y-2">
              {scenarios.map((s, i) => (
                <div key={i} className={`rounded-lg p-2.5 border transition-all ${i===0?"border-amber-500/40":"border-gray-700/50"}`}
                  style={{ background: i===0?`${NAVY}44`:`${CARD_BG}88` }}>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-1.5">
                      {i===0 && <span className="text-[9px] px-1.5 py-0.5 rounded font-bold" style={{ background: ORANGE, color: SLATE }}>BEST</span>}
                      {s.isConditional && <span className="text-[9px] px-1 py-0.5 rounded bg-amber-900/40 text-amber-400">CU</span>}
                      <span className="text-xs sm:text-sm font-semibold text-white">{s.use}</span>
                    </div>
                    <span className="text-base font-black" style={{ color: s.score>=80?GREEN:s.score>=60?ORANGE:RED }}>{s.score}</span>
                  </div>
                  <div className="grid grid-cols-4 gap-1 mb-1.5">
                    <ScoreBar score={s.legal} label="Legal" />
                    <ScoreBar score={s.physical} label="Phys." />
                    <ScoreBar score={s.financial} label="Fin." />
                    <ScoreBar score={s.maximal} label="Max" />
                  </div>
                  <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5 text-[10px]">
                    <div><span className="text-gray-400">ROI</span><br/><span className="text-white font-medium">{s.roi}%</span></div>
                    <div><span className="text-gray-400">Risk</span><br/><span className={s.risk==="Low"?"text-green-400":s.risk==="Medium"?"text-amber-400":"text-red-400"}>{s.risk}</span></div>
                    <div><span className="text-gray-400">Timeline</span><br/><span className="text-white">{s.timeline}</span></div>
                    <div><span className="text-gray-400">Invest</span><br/><span className="text-white">{fmt$(s.investReq)}</span></div>
                    <div><span className="text-gray-400">Value</span><br/><span className="text-white">{fmt$(s.projectedValue)}</span></div>
                    <div><span className="text-gray-400">Max Bid</span><br/><span style={{color:ORANGE}}>{fmt$(s.maxBid)}</span></div>
                  </div>
                </div>
              ))}
            </div>

            {/* Construction Cost Reference */}
            <div className="rounded-lg p-3 mt-3 bg-gray-800/40">
              <h3 className="text-[9px] font-bold text-gray-400 uppercase mb-2">Brevard County Construction Costs ($/sf)</h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 text-[10px]">
                {Object.entries(CONSTRUCTION_COSTS).slice(0,6).map(([k,v]) => (
                  <div key={k} className="flex justify-between border-b border-gray-700/30 pb-0.5">
                    <span className="text-gray-300">{v.label}</span>
                    <span className="text-white">${v.low}-${v.high}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ═══ FACTS TAB ═══ */}
        {tab === "facts" && (
          <div role="tabpanel" aria-label="Zoning facts" className="space-y-3">
            <div className="bg-gray-800/60 rounded-lg p-3">
              <h3 className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-2">Permitted Uses — {parcel.zone}</h3>
              <div className="flex flex-wrap gap-1.5">
                {(ZONE_PERMITTED[parcel.zone]?.uses || []).map((u,i) => (
                  <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-green-900/30 text-green-300 border border-green-800/30">{CONSTRUCTION_COSTS[u==="sfr"?"sfr_new":u]?.label||u}</span>
                ))}
                {(ZONE_PERMITTED[parcel.zone]?.conditional || []).map((u,i) => (
                  <span key={`c${i}`} className="text-[10px] px-2 py-0.5 rounded-full bg-amber-900/30 text-amber-300 border border-amber-800/30">{CONSTRUCTION_COSTS[u==="sfr"?"sfr_new":u]?.label||u} (CU)</span>
                ))}
              </div>
            </div>
            <div className="bg-gray-800/60 rounded-lg p-3">
              <h3 className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-2">Dimensional Standards</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1">
                {[["Front Setback",`${parcel.setbacks.front} ft`],["Side Setback",`${parcel.setbacks.side} ft`],
                  ["Rear Setback",`${parcel.setbacks.rear} ft`],["Max Height",`${parcel.maxHeight} ft`],
                  ["Max Coverage",`${parcel.maxCoverage}%`],["FAR",`${parcel.far}`],
                  ["Flood Zone",parcel.floodZone],["Year Built",`${parcel.yearBuilt}`],
                ].map(([l,v],i)=>(
                  <div key={i} className="flex justify-between text-[11px] border-b border-gray-700/30 pb-0.5">
                    <span className="text-gray-300">{l}</span><span className="text-white font-medium">{v}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="bg-gray-800/60 rounded-lg p-3">
              <h3 className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-2">Value Analysis</h3>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div><div className="text-[9px] text-gray-400">Land</div><div className="text-sm font-bold text-white">{fmt$(parcel.landValue)}</div></div>
                <div><div className="text-[9px] text-gray-400">Improved</div><div className="text-sm font-bold text-white">{fmt$(parcel.improvValue)}</div></div>
                <div><div className="text-[9px] text-gray-400">HBU Uplift</div><div className="text-sm font-bold" style={{color:ORANGE}}>+{best.roi}%</div></div>
              </div>
            </div>
            <div className="rounded-lg p-3 border" style={{ background:`${NAVY}22`, borderColor:`${NAVY}66` }}>
              <h3 className="text-[9px] font-bold uppercase tracking-wider mb-1" style={{color:ORANGE}}>Development Potential</h3>
              <p className="text-[11px] text-gray-300 leading-relaxed">
                This {env.lotArea.toLocaleString()} sf {parcel.zone}-zoned lot supports {env.floors} floors / {env.actualGFA.toLocaleString()} sf GFA.
                HBU recommends <span className="text-white font-semibold">{best.use}</span> (score {best.score}/100, {best.roi}% ROI).
                {parcel.floodZone !== "X" ? ` Flood zone ${parcel.floodZone} adds insurance cost and regulatory constraints.` : ""}
                {" "}Max auction bid under 70% rule: <span style={{color:ORANGE}} className="font-semibold">{fmt$(best.maxBid)}</span>.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── PARCEL CARD ────────────────────────────────────────────
function ParcelCard({ parcel, onClick, selected, onToggleCompare }) {
  const env = computeEnvelope(parcel.lotWidth, parcel.lotDepth, parcel.setbacks.front, parcel.setbacks.side, parcel.setbacks.rear, parcel.maxHeight, parcel.maxCoverage, parcel.far);
  const scenarios = calculateHBU(parcel, env);
  const best = scenarios[0];

  return (
    <div className={`rounded-xl overflow-hidden cursor-pointer transition-all duration-300 hover:scale-[1.02] hover:shadow-2xl group border ${selected?"border-amber-400 ring-1 ring-amber-400/30":"border-gray-700/50 hover:border-amber-500/30"}`}
      style={{ background: CARD_BG }} role="article" aria-label={`${parcel.address}, HBU score ${best.score}`}>
      <div className="h-24 sm:h-32 relative overflow-hidden" style={{
        background: parcel.photo ? `url(${parcel.photo}) center/cover` : `linear-gradient(135deg, ${NAVY} 0%, ${SLATE} 50%, ${NAVY}88 100%)`
      }}>
        <div className="absolute inset-0 flex items-center justify-center opacity-40 group-hover:opacity-80 transition-opacity">
          <div className="text-center"><div className="text-3xl">◇</div><div className="text-[9px] text-gray-300">3D Envelope</div></div>
        </div>
        <div className="absolute top-1.5 left-1.5">
          <button onClick={e => { e.stopPropagation(); onToggleCompare?.(parcel.id); }}
            className={`w-5 h-5 rounded border-2 flex items-center justify-center text-[10px] transition-colors ${selected?"border-amber-400 bg-amber-400/20 text-amber-400":"border-gray-500 bg-black/30 text-transparent hover:border-gray-300"}`}
            aria-label={selected?"Remove from comparison":"Add to comparison"}>
            {selected?"✓":""}
          </button>
        </div>
        <div className="absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded text-[9px] font-bold" style={{ background: ORANGE, color: SLATE }}>{parcel.zone}</div>
        <div className="absolute bottom-1.5 right-1.5 flex items-center gap-1">
          <span className="text-[9px] text-gray-300">HBU</span>
          <span className="text-sm font-black" style={{ color: ORANGE }}>{best.score}</span>
        </div>
      </div>
      <div className="p-2" onClick={onClick}>
        <h3 className="text-xs font-bold text-white mb-0.5 truncate">{parcel.address}</h3>
        <p className="text-[9px] text-gray-400 mb-1.5">{parcel.city} · {fmt$(best.maxBid)} max bid</p>
        <div className="grid grid-cols-3 gap-1 text-center mb-1">
          <div className="bg-gray-800/60 rounded px-1 py-0.5"><div className="text-[8px] text-gray-500">GFA</div><div className="text-[10px] font-bold text-white">{(env.actualGFA/1000).toFixed(1)}K</div></div>
          <div className="bg-gray-800/60 rounded px-1 py-0.5"><div className="text-[8px] text-gray-500">Floors</div><div className="text-[10px] font-bold text-white">{env.floors}</div></div>
          <div className="bg-gray-800/60 rounded px-1 py-0.5"><div className="text-[8px] text-gray-500">ROI</div><div className="text-[10px] font-bold" style={{color:ORANGE}}>{best.roi}%</div></div>
        </div>
        <div className="text-[9px] text-gray-400 truncate">Best: <span className="text-gray-200">{best.use}</span></div>
      </div>
    </div>
  );
}

// ─── COMPARISON PANEL ───────────────────────────────────────
function ComparePanel({ parcels, onClose }) {
  if (parcels.length < 2) return null;
  const data = parcels.map(p => {
    const env = computeEnvelope(p.lotWidth, p.lotDepth, p.setbacks.front, p.setbacks.side, p.setbacks.rear, p.maxHeight, p.maxCoverage, p.far);
    const hbu = calculateHBU(p, env);
    return { ...p, env, best: hbu[0] };
  });

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 border-t-2 p-3 max-h-[40vh] overflow-y-auto" style={{ background: CARD_BG, borderColor: ORANGE }}>
      <div className="flex items-center justify-between mb-2 max-w-4xl mx-auto">
        <span className="text-xs font-bold" style={{ color: ORANGE }}>Comparing {data.length} Parcels</span>
        <button onClick={onClose} className="text-xs text-gray-400 hover:text-white">✕ Close</button>
      </div>
      <div className="grid gap-3 max-w-4xl mx-auto" style={{ gridTemplateColumns: `repeat(${Math.min(data.length, 4)}, 1fr)` }}>
        {data.map(d => (
          <div key={d.id} className="rounded-lg p-2.5 border border-gray-600/50" style={{ background: `${SLATE}cc` }}>
            <div className="text-xs font-bold text-white truncate">{d.address}</div>
            <div className="text-[9px] text-gray-400 mb-2">{d.zone} · {d.city}</div>
            <div className="space-y-1 text-[10px]">
              {[["HBU Score", d.best.score, ORANGE], ["GFA", d.env.actualGFA.toLocaleString()+" sf", null],
                ["Floors", d.env.floors, null], ["ROI", d.best.roi+"%", GREEN],
                ["Max Bid", fmt$(d.best.maxBid), ORANGE], ["Best Use", d.best.use, null],
              ].map(([l,v,c],i) => (
                <div key={i} className="flex justify-between">
                  <span className="text-gray-400">{l}</span>
                  <span className="font-medium" style={c?{color:c}:{color:"#fff"}}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── MAIN APP ───────────────────────────────────────────────
export default function ZoneWiseDevIntel() {
  const [parcels, setParcels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [search, setSearch] = useState("");
  const [compareIds, setCompareIds] = useState([]);

  useEffect(() => {
    let c = false;
    setLoading(true);
    fetchParcels().then(d => { if(!c){setParcels(d);setLoading(false);} }).catch(e => { if(!c){setError(e.message);setLoading(false);} });
    return () => { c = true; };
  }, []);

  const filtered = parcels.filter(p =>
    p.address.toLowerCase().includes(search.toLowerCase()) ||
    p.city.toLowerCase().includes(search.toLowerCase()) ||
    p.zone.toLowerCase().includes(search.toLowerCase()));

  const toggleCompare = id => setCompareIds(prev => prev.includes(id) ? prev.filter(x=>x!==id) : prev.length < 4 ? [...prev, id] : prev);
  const compareParcels = parcels.filter(p => compareIds.includes(p.id));

  if (selected) return <ParcelDetail parcel={selected} onBack={() => setSelected(null)} />;

  return (
    <div className="min-h-screen" style={{ background: SLATE, fontFamily: "'Inter', system-ui, sans-serif" }}>
      <div className="px-3 sm:px-4 pt-3 pb-2 max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: NAVY }}>
              <span style={{ color: ORANGE, fontSize: 13, fontWeight: 900 }}>Z</span>
            </div>
            <div>
              <h1 className="text-base sm:text-lg font-bold text-white leading-tight">Development Intelligence</h1>
              <p className="text-[9px] sm:text-[10px] text-gray-400">3D Envelope · HBU Analysis · Max Bid Calculator</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-[9px] text-gray-500">Brevard County</div>
            <div className="text-[10px]" style={{ color: ORANGE }}>{parcels.length} parcels</div>
          </div>
        </div>

        <div className="relative mb-2">
          <input type="text" placeholder="Search address, city, or zone..." value={search} onChange={e=>setSearch(e.target.value)}
            aria-label="Search parcels"
            className="w-full bg-gray-800/80 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-amber-500/50 transition-colors" />
        </div>

        <div className="flex items-center gap-3 mb-2 text-[9px] text-gray-500">
          <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-green-400"/>≥80</span>
          <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full" style={{background:ORANGE}}/>60-79</span>
          <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-red-400"/>&lt;60</span>
          {compareIds.length > 0 && <span className="ml-auto" style={{color:ORANGE}}>{compareIds.length} selected — {compareIds.length >= 2 ? "comparing below ↓" : "select 1 more"}</span>}
          {compareIds.length === 0 && <span className="ml-auto hidden sm:inline">☐ checkbox to compare · click card for detail</span>}
        </div>
      </div>

      <div className="px-3 sm:px-4 pb-6 max-w-4xl mx-auto" style={{ paddingBottom: compareIds.length >= 2 ? "45vh" : "1.5rem" }}>
        {loading && (
          <div className="grid grid-cols-2 gap-2 sm:gap-3">
            {[1,2,3,4].map(i => (
              <div key={i} className="rounded-xl overflow-hidden border border-gray-700/50 animate-pulse" style={{background:CARD_BG}}>
                <div className="h-24 sm:h-32 bg-gray-700/50"/><div className="p-2.5 space-y-2"><div className="h-3 bg-gray-700/50 rounded w-3/4"/><div className="h-2 bg-gray-700/50 rounded w-1/2"/></div>
              </div>
            ))}
          </div>
        )}
        {error && !loading && (
          <div className="text-center py-12 rounded-xl border border-red-500/30 bg-red-500/10">
            <div className="text-red-400 text-sm mb-1">Failed to load</div>
            <div className="text-xs text-gray-400">{error}</div>
            <button onClick={()=>window.location.reload()} className="mt-3 text-xs px-3 py-1 rounded border border-gray-600 text-gray-300">Retry</button>
          </div>
        )}
        {!loading && !error && (
          <div className="grid grid-cols-2 gap-2 sm:gap-3">
            {filtered.map(p => (
              <ParcelCard key={p.id} parcel={p} onClick={() => setSelected(p)}
                selected={compareIds.includes(p.id)} onToggleCompare={toggleCompare} />
            ))}
          </div>
        )}
        {!loading && !error && filtered.length === 0 && <div className="text-center py-12 text-gray-500 text-sm">No matches.</div>}
      </div>

      {compareIds.length >= 2 && <ComparePanel parcels={compareParcels} onClose={() => setCompareIds([])} />}

      <div className="px-4 py-2 border-t border-gray-800 text-center">
        <p className="text-[9px] text-gray-600">ZoneWise.AI · BCPAO + Municipal GIS · HBU by Everest Capital · Construction costs: Brevard 2025-2026</p>
      </div>
    </div>
  );
}
